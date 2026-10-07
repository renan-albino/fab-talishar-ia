"""
tests/test_ismcts_tactical_puzzles.py
====================================
Testes de integração para convergência de árvore do ISMCTS em cenários de puzzle tático:
- Lethal Puzzle (Mate em 1): convergência para ação vitoriosa sem rede neural real.
- Survival Puzzle: priorização de defesa mandatória contra dano letal iminente.
- Determinismo e consistência sob buscas repetidas.
"""

import numpy as np
import pytest
from ai.mcts.standard_mcts import MCTSEngine
from ai.mcts.node import MCTSNode
from ai.mcts.state import ImmutableGameState


class MockLethalEvaluator:
    """Avaliador oráculo que retorna +1.0 apenas para estados onde o oponente foi derrotado."""
    def __init__(self, action_dim: int = 32):
        self.action_dim = action_dim

    def predict_state(self, state_vec, device=None):
        return np.ones(self.action_dim, dtype=np.float32) / float(self.action_dim), 0.0

    def predict_states(self, batch_states):
        n = len(batch_states)
        priors = np.ones((n, self.action_dim), dtype=np.float32) / float(self.action_dim)
        values = np.zeros((n, 1), dtype=np.float32)
        return priors, values

    def predict_simulated_states(self, simulated_states):
        values = []
        for s in simulated_states:
            if s is not None and (isinstance(s, dict) or hasattr(s, "get")):
                opp_hp = s.get("opponentHealth", s.get("theirHealth", s.get("opponentHP", 20)))
                val = 1.0 if opp_hp <= 0 else -0.5
            else:
                val = 0.0
            values.append(val)
        return values

    def __call__(self, x, return_aux=False):
        n = x.shape[0] if hasattr(x, "shape") else len(x)
        logits = np.zeros((n, self.action_dim), dtype=np.float32)
        vals = np.zeros((n, 1), dtype=np.float32)
        if return_aux:
            return logits, vals, {}
        return logits, vals


class MockSurvivalEvaluator:
    """Avaliador oráculo que penaliza mortalmente com -1.0 se o HP do jogador cair a 0."""
    def __init__(self, action_dim: int = 32):
        self.action_dim = action_dim

    def predict_state(self, state_vec, device=None):
        return np.ones(self.action_dim, dtype=np.float32) / float(self.action_dim), 0.0

    def predict_states(self, batch_states):
        n = len(batch_states)
        priors = np.ones((n, self.action_dim), dtype=np.float32) / float(self.action_dim)
        values = np.zeros((n, 1), dtype=np.float32)
        return priors, values

    def predict_simulated_states(self, simulated_states):
        values = []
        for s in simulated_states:
            if s is not None and (isinstance(s, dict) or hasattr(s, "get")):
                my_hp = s.get("playerHealth", s.get("yourHealth", s.get("playerHP", 20)))
                val = -1.0 if my_hp <= 0 else 0.8
            else:
                val = 0.0
            values.append(val)
        return values

    def __call__(self, x, return_aux=False):
        n = x.shape[0] if hasattr(x, "shape") else len(x)
        logits = np.zeros((n, self.action_dim), dtype=np.float32)
        vals = np.zeros((n, 1), dtype=np.float32)
        if return_aux:
            return logits, vals, {}
        return logits, vals


def test_mcts_converges_to_lethal_action():
    """Valida se o MCTS seleciona a ação letal que reduz o oponente a 0 de vida."""
    mock_model = MockLethalEvaluator()
    engine = MCTSEngine(model=mock_model, c_puct=1.4)

    state = ImmutableGameState({
        "playerHP": 20,
        "opponentHP": 3,
        "opponentHandCount": 0,
        "playerHand": [{"cardNumber": "ATK_LETHAL", "attackPower": 5, "cost": 0}],
        "playerResources": [1, 0],
        "playerActionPoints": 1,
    })

    legal_actions = [
        {"action_type": "pass", "mode": 0, "name": "Pass Turn"},
        {"action_type": "attack", "mode": 1, "cardNumber": "ATK_WEAK", "attackPower": 1, "cost": 0, "name": "Weak Attack"},
        {"action_type": "attack", "mode": 2, "cardNumber": "ATK_LETHAL", "attackPower": 5, "cost": 0, "name": "Lethal Strike"},
    ]

    best_action_idx, policy_dist = engine.search(state, legal_actions, num_simulations=60, training_mode=False)

    # A ação letal é o índice 2
    assert best_action_idx == 2, f"MCTS deveria ter selecionado ação 2 (Lethal Strike), mas selecionou {best_action_idx}"
    assert policy_dist[2] > policy_dist[0]
    assert policy_dist[2] > policy_dist[1]


def test_mcts_converges_to_survival_block():
    """Valida se o MCTS prioriza o bloqueio que evita morte iminente."""
    mock_model = MockSurvivalEvaluator()
    engine = MCTSEngine(model=mock_model, c_puct=1.4)

    state = ImmutableGameState({
        "playerHP": 3,
        "playerHealth": 3,
        "opponentHP": 15,
        "activeChainLink": {"cardNumber": "INCOMING_ATK", "totalPower": 5, "power": 5},
        "combatChain": [{"cardNumber": "INCOMING_ATK", "attackPower": 5}],
        "playerHand": [{"cardNumber": "SHIELD", "defense": 3, "name": "Shield"}],
        "turnPhase": "B",
    })

    legal_actions = [
        {"action_type": "no_block", "type": "pass", "mode": 0, "cards": [], "name": "Take 5 Damage (Lethal)"},
        {"action_type": "block", "type": "block", "mode": 1, "cards": [{"cardNumber": "SHIELD", "defense": 3, "name": "Shield"}], "name": "Block 3 (Survive with 1 HP)"},
    ]

    best_action_idx, policy_dist = engine.search(state, legal_actions, num_simulations=60, training_mode=False)

    # A ação sobrevivente é o índice 1
    assert best_action_idx == 1, f"MCTS deveria ter bloqueado para sobreviver, mas escolheu {best_action_idx}"
    assert policy_dist[1] > policy_dist[0]
