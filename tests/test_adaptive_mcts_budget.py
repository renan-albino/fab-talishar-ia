"""
tests/test_adaptive_mcts_budget.py
==================================
Testes unitários para o Orçamento Adaptativo de MCTS (calculate_adaptive_mcts_budget),
integração com ISMCTSEngine, MCTSEngine, PolicyEngine e HeadlessSelfPlayLoop.
"""

import pytest
import numpy as np
from unittest.mock import MagicMock

from ai.mcts import calculate_adaptive_mcts_budget, ISMCTSEngine, MCTSEngine
from ai.policy.engine import PolicyEngine


def test_adaptive_budget_zero_or_empty():
    assert calculate_adaptive_mcts_budget(0, [{"name": "act1"}]) == 0
    assert calculate_adaptive_mcts_budget(-5, [{"name": "act1"}]) == 0
    assert calculate_adaptive_mcts_budget(25, []) == 0


def test_adaptive_budget_single_legal_action():
    # Apenas 1 ação legal: escolha forçada -> reduz para min(3, base_sims)
    actions = [{"name": "pass_priority", "mode": 31}]
    assert calculate_adaptive_mcts_budget(25, actions) == 3
    assert calculate_adaptive_mcts_budget(2, actions) == 2
    assert calculate_adaptive_mcts_budget(50, actions) == 3


def test_adaptive_budget_two_actions_trivial_choice():
    # 2 ações com score muito discrepante (delta >= 15.0) -> trivial -> max(5, int(base_sims * 0.6))
    actions = [
        {"name": "great_attack", "score": 25.0, "mode": 1},
        {"name": "pass_priority", "score": 0.0, "mode": 31, "type": "pass_priority"},
    ]
    assert calculate_adaptive_mcts_budget(25, actions) == 15  # int(25 * 0.6) = 15
    assert calculate_adaptive_mcts_budget(10, actions) == 6   # int(10 * 0.6) = 6
    assert calculate_adaptive_mcts_budget(6, actions) == 5    # max(5, 3) = 5
    assert calculate_adaptive_mcts_budget(4, actions) == 3    # base < 5 fallback min(3, 4) = 3


def test_adaptive_budget_normal_turn():
    # Turno equilibrado, vida saudável, sem alta entropia -> respeita rigorosamente base_sims
    actions = [
        {"name": "attack_1", "score": 10.0, "mode": 1},
        {"name": "attack_2", "score": 8.0, "mode": 2},
        {"name": "pass_priority", "score": 0.0, "mode": 31},
    ]
    state = {"playerHealth": 30, "opponentHealth": 30}
    # Priors com pico claro (baixa entropia)
    priors = np.zeros(32, dtype=np.float32)
    priors[1] = 0.8
    priors[2] = 0.15
    priors[31] = 0.05

    assert calculate_adaptive_mcts_budget(25, actions, priors=priors, state=state) == 25
    assert calculate_adaptive_mcts_budget(12, actions, priors=priors, state=state) == 12


def test_adaptive_budget_high_entropy_uncertainty():
    # Alta incerteza na rede neural (priors quase uniformes entre candidatos -> entropia >= 0.85)
    actions = [
        {"name": "choice_a", "score": 10.0, "mode": 1},
        {"name": "choice_b", "score": 10.0, "mode": 2},
        {"name": "choice_c", "score": 10.0, "mode": 3},
    ]
    state = {"playerHealth": 25, "opponentHealth": 25}
    # Priors perfeitamente uniformes -> entropia máxima (H_norm = 1.0)
    priors = np.zeros(32, dtype=np.float32)
    priors[1] = 0.33
    priors[2] = 0.33
    priors[3] = 0.34

    budget = calculate_adaptive_mcts_budget(20, actions, priors=priors, state=state)
    assert budget == 30  # int(20 * 1.5) = 30


def test_adaptive_budget_delta_eval():
    actions = [
        {"name": "act1", "score": 10.0, "mode": 1},
        {"name": "act2", "score": 8.0, "mode": 2},
    ]
    # Delta-eval moderado (1.5) -> escala 1.5x
    assert calculate_adaptive_mcts_budget(20, actions, delta_eval=1.5) == 30

    # Delta-eval extremo (2.0) -> escala 2.0x
    assert calculate_adaptive_mcts_budget(20, actions, delta_eval=2.2) == 40


def test_adaptive_budget_critical_lethality():
    actions = [
        {"name": "swing", "score": 10.0, "mode": 1},
        {"name": "block", "score": 8.0, "mode": 2},
    ]
    # Bot em perigo de letalidade (HP <= 6)
    danger_state = {"playerHealth": 5, "opponentHealth": 25}
    assert calculate_adaptive_mcts_budget(20, actions, state=danger_state) == 30

    # Oponente em alcance de letalidade (HP <= 6)
    opp_danger_state = {"playerHealth": 25, "opponentHealth": 4}
    assert calculate_adaptive_mcts_budget(20, actions, state=opp_danger_state) == 30

    # Letalidade extrema (HP <= 3) -> escala 2.0x
    extreme_danger = {"playerHealth": 2, "opponentHealth": 20}
    assert calculate_adaptive_mcts_budget(20, actions, state=extreme_danger) == 40


def test_policy_engine_calculate_adaptive_budget():
    pe = PolicyEngine(hero_name="generic", num_mcts_sims=20)
    actions = [{"name": "pass_priority", "mode": 31}]
    # 1 ação legal -> min(3, 20) = 3
    assert pe.calculate_adaptive_budget({}, actions) == 3

    # Múltiplas ações com base_sims customizado
    actions_multi = [
        {"name": "act1", "score": 10.0, "mode": 1},
        {"name": "act2", "score": 10.0, "mode": 2},
    ]
    assert pe.calculate_adaptive_budget({}, actions_multi, base_sims=15, delta_eval=2.0) == 30


def test_ismcts_search_records_adaptive_budget_in_log():
    ismcts = ISMCTSEngine(num_worlds=1, concurrency_mode="sequential")
    state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerHand": [{"id": "c1", "name": "Card 1"}],
        "opponentHand": [{"id": "o1", "name": "Opp 1"}],
    }
    # 1 única ação legal -> adaptativo deve reduzir para min(3, base_sims) = 3
    legal_actions = [{"name": "only_action", "mode": 0, "score": 5.0}]

    best_idx, policy_dist, ismcts_log = ismcts.search_ismcts(
        state=state,
        legal_actions=legal_actions,
        num_simulations=25,
        adaptive_budget=True,
    )

    assert best_idx == 0
    assert ismcts_log["base_simulations"] == 25
    assert ismcts_log["num_simulations"] == 3
