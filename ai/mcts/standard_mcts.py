"""
ai/mcts/standard_mcts.py
========================
MCTSEngine (v2): Busca MCTS guiada por Rede Neural com pruning melhorado e batch evaluation.

Melhorias de Pruning (v2):
  1. Prior Threshold Pruning — elimina ramos com shaped_logit < média - 1.5σ.
  2. Progressive Widening — expande filhos gradualmente proporcional a √N.
  3. Single-Player Backpropagation — desativa inversão de sinal para árvore rasa.
  4. Batch Leaf Evaluation — todas as folhas de uma simulação são avaliadas em UM
     único forward pass batch do Value Head, em vez de ~num_sims passes individuais.
     Reduz a latência de inferência de O(num_sims) para O(1) chamadas ao PyTorch.
"""

import math
import random
import numpy as np
import torch
from typing import Dict, Any, List, Optional, Tuple

from ai.model import FaBPolicyValueNetwork
from ai.game_simulator import GameSimulator
from ai.logger import get_logger
from .node import MCTSNode

logger = get_logger("mcts")


# ══════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════

def _get_c_puct() -> float:
    try:
        from config.settings import SETTINGS
        return SETTINGS.ismcts_c_puct
    except Exception as e:
        logger.warning(f"Erro em _get_c_puct: {e}. Usando fallback 1.4.")
        return 1.4


DIRICHLET_ALPHA     = 0.3    # Concentração Dirichlet (AlphaZero: 0.3)
DIRICHLET_EPSILON   = 0.25   # Peso do ruído na raiz
VIRTUAL_LOSS        = 3      # Penalidade virtual para suporte a futuro multi-thread

# Pruning — ramos com logit < média - PRIOR_PRUNE_STD * std são podados na expansão
PRIOR_PRUNE_STD     = 1.5

# Progressive Widening
PW_K                = 2.0    # Coeficiente base
PW_ALPHA            = 0.5    # Expoente (0.5 = √N)

# Mínimo de candidatos após pruning
MIN_CANDIDATES_AFTER_PRUNE = 3

# Perturbação sintética de folha — magnitude do ruído no vetor de estado
LEAF_PERTURB_SCALE  = 0.05


# ══════════════════════════════════════════════════════════════════
# MOTOR MCTS (v2 — Pruning Melhorado + Batch Leaf Evaluation)
# ══════════════════════════════════════════════════════════════════

class MCTSEngine:
    """
    Motor MCTS guiado por rede neural Policy-Value.

    Melhorias v2:
      - Prior Threshold Pruning na expansão.
      - Progressive Widening na seleção.
      - Single-Player backpropagação (sem inversão de perspectiva).
      - Batch Leaf Evaluation: todas as folhas de 1 rodada são avaliadas
        em um único forward pass batch do Value Head (O(1) chamadas GPU/CPU).
    """

    def __init__(
        self,
        model: Optional[FaBPolicyValueNetwork] = None,
        device: str = "cpu",
        c_puct: Optional[float] = None,
        single_player_tree: bool = True,
    ):
        self.model              = model
        self.device             = device
        self.c_puct             = c_puct if c_puct is not None else _get_c_puct()
        self.single_player_tree = single_player_tree

    # ── API pública ────────────────────────────────────────────────

    def search(
        self,
        state: Dict[str, Any],
        legal_actions: List[Dict[str, Any]],
        num_simulations: int = 25,
        training_mode: bool = False,
        state_vec: Optional[np.ndarray] = None,
    ) -> Tuple[int, np.ndarray]:
        """
        Busca MCTS com batch leaf evaluation.

        Fluxo:
          1. Avaliar estado raiz (1 forward pass).
          2. Expandir raiz com Prior Threshold Pruning.
          3. [Opcional] Adicionar Dirichlet na raiz (treino).
          4. Para cada simulação: Progressive Widen → Selecionar folha.
          5. Batch evaluate TODAS as folhas com 1 único forward pass.
          6. Backpropagate todos os resultados.
          7. Selecionar ação por temperatura.

        Returns:
            best_action_idx : Índice em `legal_actions` da melhor ação.
            policy_dist     : np.ndarray (32,) com distribuição de visitas.
        """
        num_legal = len(legal_actions)
        if num_legal == 0:
            return 0, np.zeros(32, dtype=np.float32)

        # ── 1. Avaliar estado raiz ─────────────────────────────────
        if state_vec is None:
            state_vec = FaBPolicyValueNetwork.extract_state_vector(state)
        priors, base_value = self._evaluate(state_vec)

        # ── 2. Expandir raiz com Prior Threshold Pruning ──────────
        root = MCTSNode(prior=1.0)
        self._expand(root, legal_actions, priors)

        # ── 3. Ruído Dirichlet (treino) ───────────────────────────
        if training_mode and root.children:
            self._add_dirichlet_noise(root, len(root.children) + len(root.pending))

        # ── 4. Seleção de todas as folhas (Phase 1) ───────────────
        leaf_nodes: List[MCTSNode] = []
        for sim_idx in range(num_simulations):
            self._progressive_widen(root, sim_idx)
            node = self._select(root)
            leaf_nodes.append(node)

        # ── 5. Batch Evaluation das folhas (1 forward pass) ───────
        leaf_values = self._batch_evaluate_leaves(
            root_state_vec=state_vec,
            nodes=leaf_nodes,
            base_value=base_value,
            state=state,
            legal_actions=legal_actions,
        )

        # ── 6. Backpropagação de todos os resultados ──────────────
        for node, leaf_value in zip(leaf_nodes, leaf_values):
            self._backpropagate(node, leaf_value)

        # ── 7. Distribuição de visitas e seleção de ação ─────────
        policy_dist = np.zeros(32, dtype=np.float32)
        total_visits = sum(
            c.visit_count for k, c in root.children.items() if k >= 0
        )
        if total_visits == 0:
            active = [k for k in root.children if k >= 0]
            for idx in active:
                policy_dist[idx % 32] = 1.0 / max(len(active), 1)
        else:
            for idx, child in root.children.items():
                if idx >= 0:
                    policy_dist[idx % 32] += child.visit_count / total_visits

        best_idx = self._select_action(root, legal_actions, training_mode)
        return best_idx, policy_dist

    # ── Avaliação ──────────────────────────────────────────────────

    def _evaluate(self, state_vec: np.ndarray) -> Tuple[np.ndarray, float]:
        """Avalia estado raiz. Retorna priors uniformes e value=0 sem modelo."""
        if self.model is None:
            return np.ones(32, dtype=np.float32) / 32.0, 0.0
        try:
            priors, value = self.model.predict_state(state_vec, self.device)
            return priors, value
        except Exception as e:
            logger.warning(f"Erro na avaliação da rede: {e}. Usando fallback.")
            return np.ones(32, dtype=np.float32) / 32.0, 0.0

    def _batch_evaluate_leaves(
        self,
        root_state_vec: np.ndarray,
        nodes: List[MCTSNode],
        base_value: float,
        state: Optional[dict] = None,
        legal_actions: Optional[List[Dict[str, Any]]] = None,
    ) -> List[float]:
        """
        Avalia todas as folhas selecionadas em UM ÚNICO forward pass batch.

        Usa o GameSimulator para projetar o estado real pós-ação (recursos, dano, bloqueio).
        Fallback determinístico e desconto por profundidade garantem segurança total.
        """
        if not nodes:
            return []

        if self.model is None:
            return [
                base_value * (0.97 ** self._node_depth(node))
                for node in nodes
            ]

        try:
            leaf_vecs = []
            for node in nodes:
                if state is not None and legal_actions and 0 <= node.action_id < len(legal_actions):
                    try:
                        _, leaf_vec = GameSimulator.simulate_step(state, legal_actions[node.action_id])
                    except Exception:
                        rng = np.random.default_rng(seed=(node.action_id + 1) % (2**31))
                        noise = rng.normal(0.0, LEAF_PERTURB_SCALE, size=root_state_vec.shape).astype(np.float32)
                        leaf_vec = np.clip(root_state_vec + noise, 0.0, 1.0)
                else:
                    rng = np.random.default_rng(seed=(node.action_id + 1) % (2**31))
                    noise = rng.normal(0.0, LEAF_PERTURB_SCALE, size=root_state_vec.shape).astype(np.float32)
                    leaf_vec = np.clip(root_state_vec + noise, 0.0, 1.0)
                leaf_vecs.append(leaf_vec)

            # Batch: shape (num_sims, state_dim)
            batch = np.stack(leaf_vecs, axis=0)

            self.model.eval()
            with torch.no_grad():
                x = torch.from_numpy(batch).float().to(self.device)
                _, values = self.model(x)           # values: (num_sims, 1)
                values_flat = values.cpu().numpy().flatten().tolist()

            return values_flat

        except Exception:
            # Fallback: desconto por profundidade (nunca trava o bot)
            return [
                base_value * (0.97 ** self._node_depth(node))
                for node in nodes
            ]

    # ── Expansão com Prior Threshold Pruning ───────────────────────

    def _expand(
        self,
        node: MCTSNode,
        legal_actions: List[Dict[str, Any]],
        priors: np.ndarray,
    ) -> None:
        """
        Expande o nó com Prior Threshold Pruning e Progressive Widening.

        1. Calcula shaped_logit = log(p_neural) + score_tático / 2.5 para cada ação.
        2. Poda ramos com logit < média - 1.5σ (preserva mínimo MIN_CANDIDATES_AFTER_PRUNE).
        3. Softmax sobre sobreviventes → priors ajustados.
        4. Filhos imediatos: top PW_K candidatos; restante em `pending` para PW.
        """
        if node.is_expanded:
            return

        raw_scores = []
        for idx, action in enumerate(legal_actions):
            mode = action.get("mode", 99)
            dist_idx = min(mode, 31) if mode < 32 else (mode % 32)
            p_neural = max(1e-6, float(priors[dist_idx]))
            t_score  = float(action.get("score", 0.0))
            shaped   = np.log(p_neural) + (t_score / 2.5)
            raw_scores.append((idx, shaped, action.get("name", str(idx))))

        # ── Prior Threshold Pruning ──────────────────────────────
        logits_arr = np.array([s for _, s, _ in raw_scores], dtype=np.float32)
        mean_l = float(logits_arr.mean())
        std_l  = float(logits_arr.std()) if len(logits_arr) > 1 else 1.0
        threshold = mean_l - PRIOR_PRUNE_STD * std_l

        survivors = [(i, s, n) for i, s, n in raw_scores if s >= threshold]
        pruned    = [(i, s, n) for i, s, n in raw_scores if s <  threshold]

        if len(survivors) < MIN_CANDIDATES_AFTER_PRUNE and pruned:
            pruned.sort(key=lambda x: x[1], reverse=True)
            needed = MIN_CANDIDATES_AFTER_PRUNE - len(survivors)
            survivors.extend(pruned[:needed])
            pruned = pruned[needed:]

        # ── Softmax estável sobre sobreviventes ──────────────────
        surv_logits = np.array([s for _, s, _ in survivors], dtype=np.float32)
        surv_logits -= surv_logits.max()
        exp_s = np.exp(surv_logits)
        norm_priors = exp_s / max(1e-9, exp_s.sum())

        # ── Criar nós: top PW_K ativos, restante em pending ──────
        initial_active = max(1, min(int(PW_K), len(survivors)))
        survivors_sorted = sorted(
            zip(norm_priors, survivors),
            key=lambda x: x[0],
            reverse=True,
        )

        for rank, (p_val, (idx, _, name)) in enumerate(survivors_sorted):
            child = MCTSNode(prior=float(p_val), parent=node, action_id=idx, action_name=name)
            if rank < initial_active:
                node.children[idx] = child
            else:
                node.pending.append(idx)
                node.children[-(idx + 1)] = child   # Guarda com chave negativa até PW liberar

        node.is_expanded = True

    # ── Progressive Widening ───────────────────────────────────────

    def _progressive_widen(self, root: MCTSNode, sim_idx: int) -> None:
        """Libera filhos pendentes de acordo com floor(PW_K × sim_idx^PW_ALPHA)."""
        if not root.pending:
            return
        current = len([k for k in root.children if k >= 0])
        target  = max(current, int(PW_K * max(sim_idx, 1) ** PW_ALPHA))
        while root.pending and len([k for k in root.children if k >= 0]) < target:
            next_idx = root.pending.pop(0)
            neg_key  = -(next_idx + 1)
            if neg_key in root.children:
                child = root.children.pop(neg_key)
                root.children[next_idx] = child

    # ── Dirichlet ─────────────────────────────────────────────────

    def _add_dirichlet_noise(self, root: MCTSNode, num_legal: int) -> None:
        active = [c for k, c in root.children.items() if k >= 0]
        n = len(active)
        if n == 0:
            return
        alpha = np.full(n, DIRICHLET_ALPHA, dtype=np.float32)
        try:
            noise = np.random.dirichlet(alpha)
        except Exception:
            return
        for i, child in enumerate(active):
            if i < len(noise):
                child.prior = (
                    (1.0 - DIRICHLET_EPSILON) * child.prior
                    + DIRICHLET_EPSILON * float(noise[i])
                )

    # ── Seleção PUCT ──────────────────────────────────────────────

    def _select(self, root: MCTSNode) -> MCTSNode:
        """Desce a árvore por PUCT considerando apenas filhos ativos (chave ≥ 0)."""
        node = root
        path = [node]
        while node.is_expanded and any(k >= 0 for k in node.children):
            best_score, best_child = -float("inf"), None
            for key, child in node.children.items():
                if key < 0:
                    continue
                score = child.ucb_score(self.c_puct, node.visit_count)
                if score > best_score:
                    best_score = score
                    best_child = child
            if best_child is None:
                break
            node = best_child
            path.append(node)
        for n in path:
            n.virtual_loss += VIRTUAL_LOSS
        return node

    # ── Backpropagação ────────────────────────────────────
    def _backpropagate(self, node: MCTSNode, value: float) -> None:
        """
        Sobe a árvore atualizando visit_count e value_sum.

        single_player_tree=True (padrão FaB): não inverte perspectiva.
          A árvore tem profundidade 1 — representa escolhas do bot, não alternância.
        single_player_tree=False (AlphaZero clássico): inverte a cada nível.
        """
        curr = node
        sign = 1.0
        while curr is not None:
            curr.virtual_loss = max(0, curr.virtual_loss - VIRTUAL_LOSS)
            curr.visit_count += 1
            curr.value_sum   += value * sign
            if not self.single_player_tree:
                sign *= -1.0
            curr = curr.parent

    # ── Seleção de Ação Final ─────────────────────────────────────

    def _select_action(
        self,
        root: MCTSNode,
        legal_actions: List[Dict[str, Any]],
        training_mode: bool,
    ) -> int:
        active = {k: v for k, v in root.children.items() if k >= 0}
        if not active:
            return 0
        indices = list(active.keys())
        visits  = np.array([active[i].visit_count for i in indices], dtype=np.float32)
        if training_mode:
            total = visits.sum()
            if total > 0:
                return indices[int(np.random.choice(len(indices), p=visits / total))]
        return indices[int(np.argmax(visits))]

    @staticmethod
    def _node_depth(node: MCTSNode) -> int:
        depth = 0
        curr  = node
        while curr.parent is not None:
            depth += 1
            curr   = curr.parent
        return depth
