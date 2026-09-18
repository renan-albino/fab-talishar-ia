import os
import sys
import pytest
import numpy as np
import torch

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai.hero_strategies.base import HeroStrategy
from ai.policy_engine import PolicyEngine
from ai.model import FaBPolicyValueNetwork
from ai.experience_collector import ReplayBuffer
from ai.mcts import ISMCTSEngine


# =====================================================================
# 1. Teste do Solucionador Exato Knapsack de Turno (arXiv:2501.11683)
# =====================================================================

def test_knapsack_turn_solver_multi_attack_chain():
    """
    Testa se o solucionador combinatório Knapsack encontra a sequência ótima de múltiplos
    ataques conectados por Go Again com pitch compartilhado, superando abordagens gulosas.
    """
    strat = HeroStrategy("ninja_test")

    # Mão com 4 cartas:
    # 1. Starter com Go Again (cost 0, power 3)
    # 2. Link attack com Go Again (cost 1, power 4)
    # 3. Finisher sem Go Again (cost 2, power 6)
    # 4. Blue Pitch (pitch 3, power 0, cost 0)
    hand = [
        {"cardNumber": "starter_go_again", "name": "Starter", "power": 3, "cost": 0, "pitch": 1, "has_go_again": True, "block": 2},
        {"cardNumber": "mid_chain_ga", "name": "Mid Chain", "power": 4, "cost": 1, "pitch": 1, "has_go_again": True, "block": 2},
        {"cardNumber": "heavy_finisher", "name": "Heavy Finisher", "power": 6, "cost": 2, "pitch": 1, "has_go_again": False, "block": 2},
        {"cardNumber": "blue_pitch_card", "name": "Blue Pitch", "power": 0, "cost": 0, "pitch": 3, "block": 2},
    ]

    max_val, attacks, pitches, surplus = strat.solve_knapsack_turn(hand, floating_res=0, base_ap=1)

    # Todos os 3 ataques devem ser viabilizados pelo pitch único da carta azul (custo total 3, pitch 3)
    atk_names = [a["name"] for a in attacks]
    assert "starter_go_again" in atk_names
    assert "mid_chain_ga" in atk_names
    assert "heavy_finisher" in atk_names
    assert len(pitches) == 1
    assert pitches[0]["name"] == "blue_pitch_card"
    assert len(surplus) == 0

    # Valor: 3 + 2.5 + 4 + 2.5 + 6 = 18.0
    assert max_val >= 15.0


def test_knapsack_ap_constraint_enforcement():
    """
    Testa se a restrição de Action Points é estritamente obedecida:
    não pode jogar dois ataques sem Go Again com AP = 1.
    """
    strat = HeroStrategy("guardian_test")

    # Dois ataques sem Go Again e 1 pitch azul
    hand = [
        {"cardNumber": "crush_atk_1", "name": "Crush 1", "power": 8, "cost": 3, "pitch": 1, "has_go_again": False, "block": 3},
        {"cardNumber": "crush_atk_2", "name": "Crush 2", "power": 7, "cost": 3, "pitch": 1, "has_go_again": False, "block": 3},
        {"cardNumber": "blue_pitch", "name": "Blue Pitch", "power": 0, "cost": 0, "pitch": 3, "block": 3},
    ]

    max_val, attacks, pitches, surplus = strat.solve_knapsack_turn(hand, floating_res=0, base_ap=1)

    # Apenas um ataque pode ser selecionado com AP 1
    assert len(attacks) == 1
    assert attacks[0]["name"] == "crush_atk_1"
    assert len(pitches) == 1
    assert len(surplus) == 1
    assert surplus[0]["name"] == "crush_atk_2"


# =====================================================================
# 2. Teste de Custo de Oportunidade Dinâmico na Defesa (Felt Table)
# =====================================================================

def test_card_opportunity_cost_surplus_vs_essential():
    """
    Valida que cartas essenciais para o plano ofensivo possuem alto custo de oportunidade,
    enquanto cartas excedentes (surplus) têm custo de oportunidade zero.
    """
    strat = HeroStrategy("test_hero")

    hand = [
        {"cardNumber": "key_finisher", "name": "Key Finisher", "power": 7, "cost": 3, "pitch": 1, "has_go_again": False, "block": 2},
        {"cardNumber": "blue_fuel", "name": "Blue Fuel", "power": 0, "cost": 0, "pitch": 3, "block": 3},
        {"cardNumber": "extra_card", "name": "Extra Card", "power": 2, "cost": 2, "pitch": 1, "has_go_again": False, "block": 2},
    ]

    cost_finisher = strat.calculate_card_opportunity_cost(hand, hand[0], floating_res=0)
    cost_blue = strat.calculate_card_opportunity_cost(hand, hand[1], floating_res=0)
    cost_extra = strat.calculate_card_opportunity_cost(hand, hand[2], floating_res=0)

    # Finisher e Blue Fuel são vitais para o turno de 7 de dano:
    # Finisher adiciona marginalmente 5.0 (7.0 com finisher vs 2.0 de fallback com extra_card)
    assert cost_finisher >= 4.5
    # Blue Fuel permite pagar os ataques (sem ela, nenhum ataque é pago -> perda de 7.0)
    assert cost_blue >= 6.0
    # Extra card não é usada no plano ótimo de ataque, custo de oportunidade marginal é 0.0
    assert cost_extra == 0.0


# =====================================================================
# 3. Teste de Features de Pitch Cycle (Densidade e Cores Vistas)
# =====================================================================

def test_pitch_cycle_vector_features():
    """
    Valida a extração das features de ciclo de pitch nos índices 19 (deck density) e 27-28 (blue/red ratios).
    """
    state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerDiscard": [
            {"cardNumber": "card_blue_1"},
            {"cardNumber": "card_blue_2"},
            {"cardNumber": "card_red_1"},
        ],
        "playerPitch": [
            {"cardNumber": "card_red_2"},
        ],
        "playerDeck": [{"cardNumber": f"card_{i}"} for i in range(24)],
    }

    vec = FaBPolicyValueNetwork.extract_state_vector(state)
    assert vec.shape == (832,)

    # Deck density no índice 19 (24 cartas / 60)
    assert pytest.approx(vec[19], 0.01) == 24.0 / 60.0
    # Total vistos: 4 (2 azuis, 2 vermelhos) -> 50% azul, 50% vermelho
    assert pytest.approx(vec[27], 0.01) == 0.50  # Blue ratio
    assert pytest.approx(vec[28], 0.01) == 0.50  # Red ratio
