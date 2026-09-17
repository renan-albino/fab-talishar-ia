"""
ai/mcts/ismcts.py
=================
ISMCTSEngine: Information Set MCTS para jogos de informação imperfeita (Flesh and Blood).

Estratégia:
  1. Gera W mundos determinizados preenchendo a mão oculta do oponente.
  2. Em cada mundo, roda MCTSEngine com batch leaf evaluation.
  3. Agrega votos: a ação com maior total de visit_counts entre mundos é escolhida.

Número de mundos: calculado em startup via hardware scan (_probe_inference_latency_ms)
e armazenado em SETTINGS.ismcts_worlds — proporcional à latência real medida.

Referência: Cowling, Powley & Whitehouse (2012), IEEE Transactions on Games.
"""

import concurrent.futures
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

from ai.model import FaBPolicyValueNetwork
from ai.logger import get_logger
from .node import MCTSNode
from .standard_mcts import MCTSEngine, _get_c_puct
from .world_generator import generate_worlds

logger = get_logger("mcts")


def _get_ismcts_worlds() -> int:
    """Retorna número de mundos ISMCTS calculado por hardware scan no startup."""
    try:
        from config.settings import SETTINGS
        return SETTINGS.ismcts_worlds
    except Exception as e:
        logger.warning(f"Erro em _get_ismcts_worlds: {e}. Usando fallback 4.")
        return 4


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

        # Vetor raiz base: para telemetria de diagnóstico
        state_vec = FaBPolicyValueNetwork.extract_state_vector(state)

        vote_counts: Dict[int, int] = {i: 0 for i in range(num_legal)}
        worlds = generate_worlds(state=state, opp_hand_count=None, num_worlds=self.num_worlds)
        actual_worlds = len(worlds)

        def _evaluate_world(world_state):
            try:
                # Condicionamento de Mundo Determinizado (Cowling 2012 & ReBel 2020)
                world_vec = FaBPolicyValueNetwork.extract_state_vector(world_state)
                _, world_children = self._run_world_mcts(
                    world_state=world_state,
                    legal_actions=legal_actions,
                    num_simulations=num_simulations,
                    training_mode=training_mode,
                    state_vec=world_vec,
                )
                return world_children
            except Exception:
                return {}

        if actual_worlds > 1:
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, actual_worlds)) as executor:
                futures = [executor.submit(_evaluate_world, w) for w in worlds]
                for fut in concurrent.futures.as_completed(futures):
                    world_children = fut.result()
                    for idx, child in world_children.items():
                        if 0 <= idx < num_legal:
                            vote_counts[idx] = vote_counts.get(idx, 0) + child.visit_count
        else:
            for world_state in worlds:
                world_children = _evaluate_world(world_state)
                for idx, child in world_children.items():
                    if 0 <= idx < num_legal:
                        vote_counts[idx] = vote_counts.get(idx, 0) + child.visit_count

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

