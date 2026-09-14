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
# 3. Teste das Cabeças Auxiliares KataGo na Rede Neural (David J. Wu)
# =====================================================================

def test_katago_auxiliary_heads_shapes_and_compatibility():
    """
    Valida que a FaBPolicyValueNetwork calcula as saídas auxiliares (delta_hp e turn_dmg)
    quando return_aux=True e preserva 100% de compatibilidade quando return_aux=False.
    """
    model = FaBPolicyValueNetwork(hidden_dim=128, num_res_blocks=2)
    model.eval()

    x = torch.randn(3, 192)

    # Modo padrão (retrocompatível)
    policy_logits, value = model(x)
    assert policy_logits.shape == (3, 32)
    assert value.shape == (3, 1)

    # Modo com alvos auxiliares KataGo
    p_logits, val, aux_dict = model(x, return_aux=True)
    assert p_logits.shape == (3, 32)
    assert val.shape == (3, 1)
    assert "delta_hp" in aux_dict
    assert "turn_dmg" in aux_dict
    assert aux_dict["delta_hp"].shape == (3, 1)
    assert aux_dict["turn_dmg"].shape == (3, 1)

    # Validação dos intervalos de ativação (Tanh [-1, 1] e ReLU [0, inf))
    assert torch.all(aux_dict["delta_hp"] >= -1.0) and torch.all(aux_dict["delta_hp"] <= 1.0)
    assert torch.all(aux_dict["turn_dmg"] >= 0.0)


# =====================================================================
# 4. Teste de Importance Sampling no ReplayBuffer (Schaul et al. 2016)
# =====================================================================

def test_replay_buffer_importance_sampling_weights():
    """
    Valida o cálculo dos pesos de Importance Sampling normalizados w_i = (N * P(i))^(-beta) / max(w)
    garantindo que o viés de superamostragem do PER seja compensado no gradiente.
    """
    buffer = ReplayBuffer(max_capacity=50)
    dummy_s = np.zeros(192, dtype=np.float32)
    dummy_p = np.zeros(32, dtype=np.float32)

    # Amostras com pesos variados
    for i in range(10):
        buffer.add(dummy_s, dummy_p, 0.0, weight=1.0)
    buffer.add(dummy_s, dummy_p, 1.0, weight=10.0)

    states, policies, values, is_weights = buffer.sample_batch(
        batch_size=15, prioritized=True, beta=0.6, return_is_weights=True
    )

    assert states.shape == (15, 192)
    assert is_weights.shape == (15,)
    # Pesos normalizados devem estar no intervalo (0, 1]
    assert torch.all(is_weights > 0.0)
    assert torch.all(is_weights <= 1.00001)
    # A amostra de maior peso (10.0) é a mais provável, logo deve receber menor peso IS
    assert float(torch.min(is_weights)) < float(torch.max(is_weights))


# =====================================================================
# 5. Teste de Features de Pitch Cycle (DouZero & GDC Talk)
# =====================================================================

def test_pitch_cycle_vector_features():
    """
    Valida a extração das features de ciclo de pitch nos índices 158-160 do vetor de estado.
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
    assert vec.shape == (192,)

    # Total vistos: 4 (2 azuis, 2 vermelhos) -> 50% azul, 50% vermelho
    assert pytest.approx(vec[158], 0.01) == 0.50  # Blue ratio
    assert pytest.approx(vec[159], 0.01) == 0.50  # Red ratio
    assert pytest.approx(vec[160], 0.01) == 24.0 / 60.0  # Deck density
