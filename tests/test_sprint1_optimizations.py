"""
tests/test_sprint1_optimizations.py
===================================
Testes unitários para validar as otimizações da Sprint 1:
1. Memoização 1-ply no MCTS/ISMCTS: contagem exata de forward passes (1 raiz + W mundos).
2. Fast immutability em ImmutableGameState: _from_frozen, replace e without.
3. Extração opcional de vetor em GameSimulator.simulate_step(with_vector=False).
"""

import numpy as np
import pytest
from ai.mcts.state import ImmutableGameState
from ai.mcts.ismcts import ISMCTSEngine
from ai.mcts.standard_mcts import MCTSEngine
from ai.game_simulator import GameSimulator
from ai.model import FaBCardTransformerNetwork


def test_immutable_game_state_fast_replace():
    """Valida que _from_frozen e replace mantêm consistência e imutabilidade."""
    initial = ImmutableGameState({
        "hero": "kassai",
        "health": 20,
        "hand": ["WTR001", "WTR002"],
        "arsenal": {"card": "WTR003"},
    })

    # Teste de replace
    updated = initial.replace(health=18, resources=[2, 0])
    assert updated["health"] == 18
    assert updated["hero"] == "kassai"
    assert isinstance(updated["hand"], tuple)
    assert isinstance(updated["resources"], tuple)
    assert updated["resources"] == (2, 0)

    # Teste de without
    without_ars = updated.without("arsenal")
    assert "arsenal" not in without_ars
    assert without_ars["health"] == 18

    # Imutabilidade e hash
    assert hash(initial) != hash(updated)
    assert initial["health"] == 20


def test_game_simulator_lazy_vector():
    """Garante que simulate_step com with_vector=False retorna vetor None sem alocações."""
    state = ImmutableGameState({
        "playerHealth": 20,
        "opponentHealth": 20,
        "turnPhase": "M",
        "playerAP": 1,
        "playerHand": [{"cardNumber": "WTR001", "pitch": 1, "cost": 0, "power": 4}],
    })
    action = {"type": "pass"}

    next_state, vec = GameSimulator.simulate_step(state, action, with_vector=False)
    assert next_state is not None
    assert vec is None

    # Com with_vector=True padrão
    next_state2, vec2 = GameSimulator.simulate_step(state, action, with_vector=True)
    assert next_state2 is not None
    assert vec2 is not None
    assert isinstance(vec2, np.ndarray)
    assert len(vec2) == 832


def test_ismcts_memoization_forward_count():
    """Garante que ISMCTS com W mundos realiza exatamente W + 1 forwards (1 raiz + W batches)."""
    model = FaBCardTransformerNetwork()
    model.eval()

    forward_count = 0
    orig_forward = model.forward

    def counting_forward(*args, **kwargs):
        nonlocal forward_count
        forward_count += 1
        return orig_forward(*args, **kwargs)

    model.forward = counting_forward

    engine = ISMCTSEngine(
        model=model,
        num_worlds=3,
        concurrency_mode="sequential"
    )

    raw_state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerResources": [2, 0],
        "playerAP": 1,
        "turnPhase": "M",
        "combatChain": [],
        "playerHand": [{"cardNumber": "WTR001", "pitch": 1, "cost": 0, "power": 4}],
        "opponentHandCount": 3,
        "opponentHero": "rhinar",
        "yourHero": "kassai",
        "actionPoints": 1,
    }
    state = ImmutableGameState(raw_state)
    legal_actions = [
        {"type": "attack", "card_name": "Snatch", "card_index": 0, "mode": 1},
        {"type": "pass", "mode": 0},
    ]

    best_idx, policy_dist, ismcts_log = engine.search_ismcts(state, legal_actions, num_simulations=20, adaptive_budget=False)
    assert best_idx in (0, 1)

    # 1 forward para a raiz em search_ismcts + 1 forward em batch por mundo (3 mundos) = 4 forwards no total!
    assert forward_count == 4, f"Esperado 4 forwards (1 raiz + 3 mundos), obtido: {forward_count}"
