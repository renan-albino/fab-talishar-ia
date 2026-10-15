"""
tests/test_sprint4_sideboard_and_mcdropout.py
=============================================
Suíte de testes de validação para a Sprint 4:
1. Monte Carlo Dropout na cabeça de valor da rede Transformer (variância, sigma e restauração de estado).
2. Orçamento adaptativo MCTS escalonado por incerteza Bayesiana (value_uncertainty >= 0.20 e >= 0.35).
3. Resolução dinâmica de Sideboard guiada por metadados de herói (classes/keywords sem hardcoding).
4. Seleção competitiva de off-hands e armas (CR 2.8.2 e CR 3.0) baseada em atributos semânticos.
5. Preservação defensiva sob incerteza no resolvedor de defesa (defense_pruner).
"""

import numpy as np
import pytest
import torch
from ai.model import FaBCardTransformerNetwork
from ai.mcts.ismcts import calculate_adaptive_mcts_budget
from ai.sideboard_manager import resolve_sideboard
from ai.policy.defense_pruner import select_defense_blocks


def test_mc_dropout_variance_and_shape():
    """Valida o cálculo estocástico de Monte Carlo Dropout e restauração de flags."""
    model = FaBCardTransformerNetwork(dropout=0.2)
    model.eval()

    vec = np.zeros(832, dtype=np.float32)
    vec[0] = 0.5  # Player HP
    vec[1] = 0.5  # Opponent HP

    # 1 amostra: sem variância
    mean_single, sigma_single = model.predict_value_with_uncertainty(vec, num_samples=1)
    assert isinstance(mean_single, float)
    assert sigma_single == 0.0

    # 8 amostras: estimativa bayesiana com desvio padrão
    mean_multi, sigma_multi = model.predict_value_with_uncertainty(vec, num_samples=8)
    assert isinstance(mean_multi, float)
    assert isinstance(sigma_multi, float)
    assert -1.0 <= mean_multi <= 1.0
    assert sigma_multi >= 0.0

    # Garante que o modelo e o dropout retornaram ao estado eval
    assert not model.training
    assert not model.value_dropout.training


def test_adaptive_budget_with_value_uncertainty():
    """Valida a modulação de simulações MCTS pelo valor de incerteza da rede neural."""
    base_sims = 20
    actions = [{"score": 10.0, "mode": 1}, {"score": 8.0, "mode": 2}]

    # Incerteza baixa (sigma = 0.05): mantém simulações base
    sims_low = calculate_adaptive_mcts_budget(
        base_sims=base_sims,
        legal_actions=actions,
        value_uncertainty=0.05,
    )
    assert sims_low == base_sims

    # Incerteza moderada/alta (sigma = 0.25): escalona para 1.5x
    sims_high = calculate_adaptive_mcts_budget(
        base_sims=base_sims,
        legal_actions=actions,
        value_uncertainty=0.25,
    )
    assert sims_high == int(base_sims * 1.5)

    # Incerteza extrema (sigma = 0.38): escalona para 2.0x
    sims_extreme = calculate_adaptive_mcts_budget(
        base_sims=base_sims,
        legal_actions=actions,
        value_uncertainty=0.38,
    )
    assert sims_extreme == int(base_sims * 2.0)


def test_sideboard_dynamic_arcane_detection():
    """Valida a detecção dinâmica de classes arcanas sem hardcodes de nomes de heróis."""
    mock_db = {
        "mystic_sorcerer": {
            "slot": "Hero",
            "classes": ["Wizard", "Shadow"],
            "types": ["Hero", "Wizard"],
            "text": "Whenever you deal arcane damage...",
        },
        "head_physical": {
            "slot": "Head",
            "defense": 2,
            "text": "Physical helmet",
        },
        "head_arcane": {
            "slot": "Head",
            "defense": 0,
            "has_arcane_barrier": True,
            "text": "Arcane Barrier 1",
        },
    }

    def get_card_meta(c):
        return mock_db.get(c, {})

    # Mock de leitura de baralho sem arquivos em disco
    import ai.sideboard_manager as sm
    original_exists = sm.os.path.exists

    # Simula baralho com as 2 opções de cabeça
    cards_in_deck = [
        {"identifier": "head_physical", "total": 1},
        {"identifier": "head_arcane", "total": 1},
    ]

    import unittest.mock as mock
    with mock.patch("builtins.open", mock.mock_open(read_data='{"cards": [{"identifier": "head_physical"}, {"identifier": "head_arcane"}]}')), \
         mock.patch("os.path.exists", return_value=True):
        # Matchup contra herói Wizard dinâmico (não listado em nenhuma lista estática)
        res = resolve_sideboard(
            deck_url="test_deck",
            deck_format="blitz",
            opp_hero="mystic_sorcerer",
            opp_class="unknown",
            get_card_meta=get_card_meta,
        )

        # Deve equipar o item de Arcane Barrier devido à detecção por metadados de classe
        assert res.get("head") == "head_arcane"
        assert "head_physical" in res.get("inventory", [])


def test_sideboard_dynamic_offhand_and_weapon_selection():
    """Valida a seleção ótima de escudo/off-hand por defesa e atributos sem amarras nominais."""
    mock_db = {
        "sword_1h": {
            "slot": "Weapon",
            "is1h": True,
            "power": 3,
        },
        "shield_weak": {
            "slot": "Off-Hand",
            "subtype": "Shield",
            "defense": 1,
            "text": "Small buckler",
        },
        "shield_tower": {
            "slot": "Off-Hand",
            "subtype": "Shield",
            "defense": 3,
            "text": "Tower shield with high defense",
        },
    }

    def get_card_meta(c):
        return mock_db.get(c, {})

    import unittest.mock as mock
    with mock.patch("builtins.open", mock.mock_open(read_data='{"cards": [{"identifier": "sword_1h"}, {"identifier": "shield_weak"}, {"identifier": "shield_tower"}]}')), \
         mock.patch("os.path.exists", return_value=True):
        res = resolve_sideboard(
            deck_url="weapon_test_deck",
            deck_format="blitz",
            opp_hero="brute_hero",
            opp_class="brute",
            get_card_meta=get_card_meta,
        )

        # Deve selecionar 1H + melhor Off-Hand (shield_tower com defesa 3)
        assert res.get("hands") == ["sword_1h", "shield_tower"]
        assert "shield_weak" in res.get("inventory", [])


def test_defense_pruner_high_uncertainty_safety():
    """Valida que incerteza Bayesiana elevada impede o bot de pular bloqueio levianamente."""
    from ai.policy_engine import PolicyEngine
    engine = PolicyEngine(hero_name="generic")
    engine.num_mcts_sims = 0

    state = {
        "turnNo": 3,
        "playerHealth": 14,
        "opponentHealth": 14,
        "playerHand": [{"cardNumber": "attack_card_1", "name": "Attack Card 1", "block": 3, "power": 4, "action": 27}],
        "playerArsenal": [],
        "activeChainLink": {"totalPower": 3, "cardNumber": "generic_attack"},
        "combatChainPower": 3,
        "opponentHandCount": 0,
    }

    blocks_uncertain = select_defense_blocks(engine, state, value_uncertainty=0.35)
    # Deve escolher bloquear para preservar vida sob incerteza
    assert len(blocks_uncertain) > 0
