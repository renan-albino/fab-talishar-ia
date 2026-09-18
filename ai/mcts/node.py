"""
ai/mcts/node.py
===============
Nó da árvore MCTS para busca AlphaZero / PUCT.
"""

import math
import threading
from typing import Dict, List, Optional


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
        "children", "pending", "is_expanded", "parent", "action_id", "action_name", "_lock"
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
        self._lock        = threading.Lock()

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
