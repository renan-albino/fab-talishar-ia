"""
ai/mcts.py
==========
MCTSEngine (v2): Busca MCTS guiada por Rede Neural com pruning melhorado e batch evaluation.
ISMCTSEngine: Information Set MCTS para jogos de informação imperfeita (FaB).

Melhorias de Pruning (v2):
  1. Prior Threshold Pruning — elimina ramos com shaped_logit < média - 1.5σ.
  2. Progressive Widening — expande filhos gradualmente proporcional a √N.
  3. Single-Player Backpropagation — desativa inversão de sinal para árvore rasa.
  4. Batch Leaf Evaluation — todas as folhas de uma simulação são avaliadas em UM
     único forward pass batch do Value Head, em vez de ~num_sims passes individuais.
     Reduz a latência de inferência de O(num_sims) para O(1) chamadas ao PyTorch.

ISMCTS (Information Set MCTS):
  1. _generate_worlds: Cria mundos determinizados preenchendo a mão oculta.
  2. _run_world_mcts: Roda MCTS em um mundo e retorna (best_idx, children).
  3. search_ismcts: Agrega votos de todos os mundos e retorna ismcts_log.

Referências:
  - Silver et al., "Mastering the Game of Go without Human Knowledge" (AlphaZero, 2017)
  - Cowling, Powley & Whitehouse, "Information Set MCTS" (IEEE ToG, 2012)
"""

import os
import math
import random
import numpy as np
import torch
from typing import Dict, Any, List, Optional, Tuple

from ai.model import FaBPolicyValueNetwork
from ai.game_simulator import GameSimulator


# ══════════════════════════════════════════════════════════════════
# CONSTANTES
# ══════════════════════════════════════════════════════════════════

def _get_c_puct() -> float:
    try:
        from config.settings import SETTINGS
        return SETTINGS.ismcts_c_puct
    except Exception:
        return 1.4

def _get_ismcts_worlds() -> int:
    """Retorna número de mundos ISMCTS calculado por hardware scan no startup."""
    try:
        from config.settings import SETTINGS
        return SETTINGS.ismcts_worlds
    except Exception:
        return 4

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
# NÓ DA ÁRVORE
# ══════════════════════════════════════════════════════════════════

class MCTSNode:
    """
    Nó da árvore MCTS.

    Atributos:
        prior        (float) : Probabilidade da POLICY HEAD para esta ação.
        visit_count  (int)   : N(s, a) — número de visitas.
        value_sum    (float) : W(s, a) — soma dos valores backpropagados.
        virtual_loss (int)   : Penalidade virtual durante seleção multi-thread.
        children     (dict)  : {action_idx: MCTSNode} — filhos ativos (chave ≥ 0)
                               e filhos pendentes de PW (chave negativa -(idx+1)).
        pending      (list)  : Fila de índices aguardando Progressive Widening.
        is_expanded  (bool)  : True se os filhos já foram criados.
        parent       (MCTSNode | None)
        action_id    (int)   : Índice da ação que levou a este nó.
        action_name  (str)   : Nome legível da ação (para logging ISMCTS).
    """

    __slots__ = (
        "prior", "visit_count", "value_sum", "virtual_loss",
        "children", "pending", "is_expanded", "parent", "action_id", "action_name"
    )

    def __init__(
        self,
        prior: float = 1.0,
        parent: Optional["MCTSNode"] = None,
        action_id: int = 0,
        action_name: str = "",
    ):
        self.prior        = float(prior)
        self.visit_count  = 0
        self.value_sum    = 0.0
        self.virtual_loss = 0
        self.children: Dict[int, "MCTSNode"] = {}
        self.pending: List[int]              = []
        self.is_expanded  = False
        self.parent       = parent
        self.action_id    = action_id
        self.action_name  = action_name

    @property
    def q_value(self) -> float:
        effective_visits = self.visit_count + self.virtual_loss
        if effective_visits == 0:
            return 0.0
        return (self.value_sum - self.virtual_loss) / effective_visits

    def ucb_score(self, c_puct: float, parent_visit_count: int) -> float:
        """PUCT(s,a) = Q(s,a) + c_puct × P(s,a) × √N(s) / (1 + N(s,a))"""
        u = (
            c_puct
            * self.prior
            * math.sqrt(max(parent_visit_count, 1))
            / (1.0 + self.visit_count)
        )
        return self.q_value + u

    def __repr__(self) -> str:
        return (
            f"MCTSNode(action={self.action_id}, name='{self.action_name}', "
            f"N={self.visit_count}, Q={self.q_value:.3f}, prior={self.prior:.3f})"
        )


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
        except Exception:
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
        while node.is_expanded and any(k >= 0 for k in node.children):
            node.virtual_loss += VIRTUAL_LOSS
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
        node.virtual_loss += VIRTUAL_LOSS
        return node

    # ── Backpropagação ────────────────────────────────────────────

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


_CARD_DB_CACHE: Optional[Dict[str, Any]] = None

def _get_card_db() -> Dict[str, Any]:
    global _CARD_DB_CACHE
    if _CARD_DB_CACHE is None:
        db_path = "data/fab_cards_db.json"
        if not os.path.exists(db_path):
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(base_dir, "data", "fab_cards_db.json")
        if os.path.exists(db_path):
            try:
                import json
                with open(db_path, "r", encoding="utf-8") as f:
                    _CARD_DB_CACHE = json.load(f)
            except Exception:
                _CARD_DB_CACHE = {}
        else:
            _CARD_DB_CACHE = {}
    return _CARD_DB_CACHE


# ══════════════════════════════════════════════════════════════════
# ISMCTS — Information Set MCTS
# ══════════════════════════════════════════════════════════════════

class ISMCTSEngine:
    """
    Information Set MCTS para Flesh and Blood (informação imperfeita).

    Estratégia:
      1. Gera W mundos determinizados preenchendo a mão oculta do oponente.
      2. Em cada mundo, roda MCTSEngine com batch leaf evaluation.
      3. Agrega votos: a ação com maior total de visit_counts entre mundos é escolhida.

    Número de mundos: calculado em startup via hardware scan (_probe_inference_latency_ms)
    e armazenado em SETTINGS.ismcts_worlds — proporcional à latência real medida.

    Referência: Cowling, Powley & Whitehouse (2012), IEEE Transactions on Games.
    """

    def __init__(
        self,
        model: Optional[FaBPolicyValueNetwork] = None,
        device: str = "cpu",
        c_puct: Optional[float] = None,
        num_worlds: Optional[int] = None,
    ):
        self.model      = model
        self.device     = device
        self.c_puct     = c_puct if c_puct is not None else _get_c_puct()
        self.num_worlds = num_worlds if num_worlds is not None else _get_ismcts_worlds()

        self._mcts = MCTSEngine(
            model=model,
            device=device,
            c_puct=self.c_puct,
            single_player_tree=True,
        )

    def set_model(self, model: FaBPolicyValueNetwork, device: str = None) -> None:
        self.model        = model
        self.device       = device or self.device
        self._mcts.model  = model
        self._mcts.device = self.device

    # ── API pública ────────────────────────────────────────────────

    def search_ismcts(
        self,
        state: Dict[str, Any],
        legal_actions: List[Dict[str, Any]],
        num_simulations: int = 25,
        training_mode: bool = False,
    ) -> Tuple[int, np.ndarray, Dict[str, Any]]:
        """
        Executa ISMCTS e retorna (best_idx, policy_dist, ismcts_log).

        Fluxo por mundo:
          1. Amostra mão oculta do oponente → estado determinizado.
          2. Roda MCTSEngine com batch leaf evaluation (1 forward pass por mundo).
          3. Acumula visit_counts de cada filho em vote_counts.

        Agregação:
          A ação com maior total de votos entre W mundos é escolhida.
          Confiança = votos_vencedor / total_votos.

        Returns:
            best_action_idx : Índice da melhor ação em `legal_actions`.
            policy_dist     : np.ndarray (32,) distribuição de votos normalizada.
            ismcts_log      : Dict com diagnóstico completo para análise offline.
        """
        num_legal = len(legal_actions)
        if num_legal == 0:
            return 0, np.zeros(32, dtype=np.float32), {}

        # Vetor raiz: calculado uma vez, compartilhado entre mundos
        state_vec = FaBPolicyValueNetwork.extract_state_vector(state)

        vote_counts: Dict[int, int] = {i: 0 for i in range(num_legal)}
        worlds = self._generate_worlds(state, self.num_worlds)
        actual_worlds = len(worlds)

        for world_state in worlds:
            try:
                _, world_children = self._run_world_mcts(
                    world_state=world_state,
                    legal_actions=legal_actions,
                    num_simulations=num_simulations,
                    training_mode=training_mode,
                    state_vec=state_vec,
                )
                for idx, child in world_children.items():
                    if 0 <= idx < num_legal:
                        vote_counts[idx] = vote_counts.get(idx, 0) + child.visit_count
            except Exception:
                continue

        # ── Agregação ─────────────────────────────────────────────
        total_votes = sum(vote_counts.values())
        policy_dist = np.zeros(32, dtype=np.float32)
        best_idx, best_votes = 0, -1

        if total_votes > 0:
            for idx, votes in vote_counts.items():
                if idx < num_legal:
                    mode     = legal_actions[idx].get("mode", 99)
                    dist_idx = min(mode, 31) if mode < 32 else (mode % 32)
                    policy_dist[dist_idx] += votes / total_votes
                if votes > best_votes:
                    best_votes = votes
                    best_idx   = idx
        else:
            # Fallback: heurística de scores táticos
            scored   = sorted(enumerate(legal_actions), key=lambda x: x[1].get("score", 0), reverse=True)
            best_idx = scored[0][0] if scored else 0

        confidence = best_votes / total_votes if total_votes > 0 else 0.0

        # ── Log de Diagnóstico ────────────────────────────────────
        _, base_value = self._mcts._evaluate(state_vec)
        action_names  = [a.get("name", str(i)) for i, a in enumerate(legal_actions)]
        chosen_name   = action_names[best_idx] if best_idx < len(action_names) else str(best_idx)

        ismcts_log = {
            "worlds_sampled"  : actual_worlds,
            "num_simulations" : num_simulations,
            "candidates"      : action_names,
            "votes"           : {action_names[i]: vote_counts.get(i, 0) for i in range(num_legal)},
            "chosen"          : chosen_name,
            "chosen_idx"      : best_idx,
            "confidence"      : round(confidence, 4),
            "mcts_value_root" : round(float(base_value), 4),
            "total_votes"     : total_votes,
        }

        return best_idx, policy_dist, ismcts_log

    # ── Helpers internos ──────────────────────────────────────────

    def _run_world_mcts(
        self,
        world_state: Dict[str, Any],
        legal_actions: List[Dict[str, Any]],
        num_simulations: int,
        training_mode: bool,
        state_vec: np.ndarray,
    ) -> Tuple[int, Dict[int, MCTSNode]]:
        """
        Executa MCTSEngine em um mundo determinizado com batch leaf evaluation.

        Retorna (best_idx, dict de filhos ativos) para extração de vote_counts.
        Reutiliza o `state_vec` da raiz entre mundos — os mundos diferem apenas
        na mão oculta do oponente, não no vetor de estado do próprio bot.
        """
        num_legal = len(legal_actions)
        if num_legal == 0:
            return 0, {}

        priors, base_value = self._mcts._evaluate(state_vec)

        root = MCTSNode(prior=1.0)
        self._mcts._expand(root, legal_actions, priors)

        if training_mode and root.children:
            self._mcts._add_dirichlet_noise(root, len(root.children) + len(root.pending))

        # ── Phase 1: Selecionar todas as folhas ───────────────────
        leaf_nodes: List[MCTSNode] = []
        for sim_idx in range(num_simulations):
            self._mcts._progressive_widen(root, sim_idx)
            node = self._mcts._select(root)
            leaf_nodes.append(node)

        # ── Phase 2: Batch evaluate (1 forward pass) ──────────────
        leaf_values = self._mcts._batch_evaluate_leaves(
            root_state_vec=state_vec,
            nodes=leaf_nodes,
            base_value=base_value,
            state=world_state,
            legal_actions=legal_actions,
        )

        # ── Phase 3: Backpropagate ─────────────────────────────────
        for node, lv in zip(leaf_nodes, leaf_values):
            self._mcts._backpropagate(node, lv)

        best_idx = self._mcts._select_action(root, legal_actions, training_mode)
        active_children = {k: v for k, v in root.children.items() if k >= 0}
        return best_idx, active_children

    def _generate_worlds(
        self,
        state: Dict[str, Any],
        num_worlds: int,
    ) -> List[Dict[str, Any]]:
        """
        Gera `num_worlds` mundos determinizados com amostragem Deck-Aware.

        Prioridade do pool de amostragem da mão oculta:
          1. Cartas reais vistas no opponentDiscard (proxy de alta fidelidade).
          2. Cartas do banco de dados oficial (fab_cards_db.json) compatíveis
             com a classe do herói oponente (ex: Guardian/Generic para Bravo).
          3. Cartas genéricas Red/Yellow/Blue como fallback.
        """
        opp_hand_count = int(state.get("opponentHandCount", state.get("theirHandCount", 4)))
        if opp_hand_count == 0:
            return [state]

        opp_discard = state.get("opponentDiscard", state.get("theirDiscard", []))
        opp_deck_pool = list(opp_discard) if isinstance(opp_discard, list) and opp_discard else []

        # ── Identificar classe do herói adversário para amostragem Deck-Aware ──
        opp_hero = str(
            state.get("opponentHero",
            state.get("theirCharacter",
            state.get("initialLoad", {}).get("theirHeroName", "")))
        ).lower()

        card_db = _get_card_db()
        class_cards = []
        if card_db and opp_hero:
            for c_slug, meta in card_db.items():
                if not isinstance(meta, dict):
                    continue
                c_class = str(meta.get("class", "")).lower()
                c_slot = str(meta.get("slot", "")).lower()
                if c_slot == "deck" or not c_slot:
                    if any(ch in opp_hero for ch in ["bravo", "betsy", "victor", "valda", "guardian"]) and "guardian" in c_class:
                        class_cards.append({"cardNumber": c_slug, "pitch": int(meta.get("pitch", 1)), "power": int(meta.get("power", 4)), "defense": int(meta.get("defense", 3)), "action": 27})
                    elif any(ch in opp_hero for ch in ["katsu", "fai", "ira", "zen", "ninja"]) and "ninja" in c_class:
                        class_cards.append({"cardNumber": c_slug, "pitch": int(meta.get("pitch", 1)), "power": int(meta.get("power", 3)), "defense": int(meta.get("defense", 2)), "action": 27})
                    elif any(ch in opp_hero for ch in ["dash", "maxx", "mechanologist"]) and "mechanologist" in c_class:
                        class_cards.append({"cardNumber": c_slug, "pitch": int(meta.get("pitch", 1)), "power": int(meta.get("power", 4)), "defense": int(meta.get("defense", 2)), "action": 27})
                    elif "generic" in c_class:
                        class_cards.append({"cardNumber": c_slug, "pitch": int(meta.get("pitch", 1)), "power": int(meta.get("power", 3)), "defense": int(meta.get("defense", 2)), "action": 27})

        if class_cards:
            opp_deck_pool.extend(random.sample(class_cards, min(len(class_cards), 20)))

        generic_cards = [
            {"cardNumber": "generic_red",    "pitch": 1, "power": 4, "defense": 2, "action": 27},
            {"cardNumber": "generic_yellow", "pitch": 2, "power": 3, "defense": 3, "action": 27},
            {"cardNumber": "generic_blue",   "pitch": 3, "power": 2, "defense": 3, "action": 27},
        ]
        while len(opp_deck_pool) < 9:
            opp_deck_pool.extend(generic_cards)

        worlds = []
        for _ in range(num_worlds):
            sampled = random.sample(opp_deck_pool, min(opp_hand_count, len(opp_deck_pool)))
            world = dict(state)
            world["opponentHand"] = sampled
            world["opponentHandCount"] = len(sampled)
            worlds.append(world)

        return worlds
