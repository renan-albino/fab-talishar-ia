"""
tests/test_hammerhead_tome_and_hero.py
=======================================
Testes unitários rigorosos para:
1. Legalidade de Pitch de Gorganian Tome (pitch 0 nunca pode ser pitchado).
2. Propriedades de Hammerhead Harpoon Cannon (Poder 0, arma de buff, poda correta).
3. Habilidades de Herói ativadas (Marlynn destruindo Gold para Arsenal, Kassai gerando Gold, Bravo Dominate).
"""

import pytest
from ai.policy_engine import PolicyEngine, ALL_FAB_WEAPONS
from ai.hero_strategies import get_hero_strategy, MarlynnStrategy, KassaiStrategy, GuardianStrategy


def test_gorganian_tome_pitch_zero():
    """Gorganian Tome tem pitch 0 e NUNCA pode ser selecionado como pitch."""
    pe = PolicyEngine(hero_name="generic", num_mcts_sims=0)
    info = pe.extract_card_info({"cardNumber": "gorganian_tome"})
    assert info["pitch"] == 0, f"Esperado pitch 0 para Gorganian Tome, obtido {info['pitch']}"
    assert info["power"] == 0

    # Teste de seleção de pitch com Gorganian Tome e azul na mão
    state = {
        "playerHand": [
            {"cardNumber": "gorganian_tome", "action": 27},
            {"cardNumber": "sink_below_red", "action": 27, "pitch": 1},
            {"cardNumber": "wounded_bull_blue", "action": 27, "pitch": 3},
        ],
        "playerPitchCount": 0,
        "playerResources": [0, 0],
    }
    choice = pe.select_best_pitch_card(state)
    assert choice is not None
    p_idx, p_name, p_mode = choice
    assert p_name != "gorganian_tome", "Gorganian Tome NUNCA deve ser selecionado para pitch!"
    assert "blue" in p_name.lower(), f"Deveria priorizar azul, escolheu {p_name}"

    # Teste quando a mão SÓ tem Gorganian Tome: deve retornar None (sem pitch legal)
    state_only_tome = {
        "playerHand": [
            {"cardNumber": "gorganian_tome", "action": 27},
        ],
        "playerPitchCount": 0,
        "playerResources": [0, 0],
    }
    choice_none = pe.select_best_pitch_card(state_only_tome)
    assert choice_none is None, "Mão apenas com cartas sem pitch deve retornar None"


def test_hammerhead_harpoon_cannon_attributes_and_pruning():
    """Hammerhead Harpoon Cannon deve ter poder 0 (não 6), custo 4 e ser podado quando não há flechas ou recursos < 4."""
    pe = PolicyEngine(hero_name="marlinn", num_mcts_sims=0)
    assert "hammerhead_harpoon_cannon" in ALL_FAB_WEAPONS

    info = pe.extract_card_info({"cardNumber": "hammerhead_harpoon_cannon"})
    assert info["power"] == 0, f"Hammerhead não deve ter poder heurístico 6! Obtido: {info['power']}"

    # Custo de ativação oficial é 4 recursos
    w_cost = pe.get_weapon_cost("hammerhead_harpoon_cannon")
    assert w_cost == 4, f"Custo de ativação de Hammerhead deve ser 4 recursos! Obtido: {w_cost}"

    # Caso 1: Sem flechas na mão e sem flechas no Arsenal -> Hammerhead deve ser PODADO
    state_no_arrows = {
        "turnPlayer": 1,
        "playerID": 1,
        "amIActivePlayer": True,
        "playerHand": [{"cardNumber": "gorganian_tome", "action": 27}],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "marlynn_treasure_hunter", "slot": "Hero", "action": 0},
            {"cardNumber": "hammerhead_harpoon_cannon", "slot": "Weapon", "action": 3, "actionDataOverride": "5"},
        ],
        "playerResources": [6, 6],
        "playerPitchCount": 6,
    }
    action = pe.select_best_attack(state_no_arrows)
    assert action is not None
    assert action["name"] != "hammerhead_harpoon_cannon", "Hammerhead sem flechas para disparar deve ser podado!"

    # Caso 2: Com flecha no Arsenal mas recursos insuficientes (< 4 recursos) -> Hammerhead deve ser PODADO
    state_low_resources = {
        "turnPlayer": 1,
        "playerID": 1,
        "amIActivePlayer": True,
        "playerHand": [{"cardNumber": "red_card", "action": 27, "pitch": 1}],
        "playerArsenal": [{"cardNumber": "goldfin_harpoon_red", "action": 27, "power": 4, "cost": 0}],
        "playerEquipment": [
            {"cardNumber": "marlynn_treasure_hunter", "slot": "Hero", "action": 0},
            {"cardNumber": "hammerhead_harpoon_cannon", "slot": "Weapon", "action": 3, "actionDataOverride": "5"},
        ],
        "playerResources": [2, 2],
        "playerPitchCount": 2,
    }
    action_low = pe.select_best_attack(state_low_resources)
    assert action_low is not None
    assert action_low["name"] != "hammerhead_harpoon_cannon", "Hammerhead com menos de 4 recursos deve ser podado!"

    # Caso 3: Com flecha no Arsenal e recursos suficientes (>= 4 recursos) -> Hammerhead pode ser ativado
    state_with_resources = {
        "turnPlayer": 1,
        "playerID": 1,
        "amIActivePlayer": True,
        "playerHand": [
            {"cardNumber": "blue_pitch_card_1", "action": 27, "pitch": 3},
            {"cardNumber": "blue_pitch_card_2", "action": 27, "pitch": 3},
        ],
        "playerArsenal": [{"cardNumber": "goldfin_harpoon_red", "action": 27, "power": 4, "cost": 0}],
        "playerEquipment": [
            {"cardNumber": "marlynn_treasure_hunter", "slot": "Hero", "action": 0},
            {"cardNumber": "hammerhead_harpoon_cannon", "slot": "Weapon", "action": 3, "actionDataOverride": "5"},
        ],
        "playerResources": [5, 5],
        "playerPitchCount": 5,
    }
    action_ok = pe.select_best_attack(state_with_resources)
    assert action_ok is not None
    assert action_ok["name"] == "hammerhead_harpoon_cannon"
    assert action_ok["cost"] == 4
    assert action_ok["type"] == "weapon_buff"


def test_marlynn_hero_ability():
    """Marlynn ativa habilidade destruindo Gold para carregar Arsenal quando vazio."""
    pe = PolicyEngine(hero_name="marlynn_treasure_hunter", num_mcts_sims=0)
    strat = pe.strategy
    assert isinstance(strat, MarlynnStrategy)

    # Com Gold e Arsenal vazio -> habilidade viável (score 18.0)
    state_with_gold = {
        "playerArsenal": [],
        "playerItems": [{"cardNumber": "gold", "name": "Gold"}],
        "playerHand": [{"cardNumber": "goldfin_harpoon_red", "pitch": 1}],
    }
    score = strat.evaluate_hero_ability(state_with_gold, {"cardNumber": "marlynn_treasure_hunter"})
    assert score >= 18.0

    # Sem Gold -> habilidade deve pontuar 0.0
    state_no_gold = {
        "playerArsenal": [],
        "playerItems": [],
        "goldCount": 0,
        "playerHand": [{"cardNumber": "goldfin_harpoon_red", "pitch": 1}],
    }
    score_no_gold = strat.evaluate_hero_ability(state_no_gold, {"cardNumber": "marlynn_treasure_hunter"})
    assert score_no_gold == 0.0

    # Com Arsenal ocupado -> não deve ativar habilidade para não gastar Gold
    state_full_arsenal = {
        "playerArsenal": [{"cardNumber": "some_arrow"}],
        "playerItems": [{"cardNumber": "gold"}],
        "playerHand": [],
    }
    score_full_ars = strat.evaluate_hero_ability(state_full_arsenal, {"cardNumber": "marlynn_treasure_hunter"})
    assert score_full_ars == 0.0

    # Priorização de Gorganian Tome na estratégia de Marlynn
    score_tome = strat.evaluate_attack_card("gorganian_tome", power=0, cost=0, has_go_again=True, pitch=0)
    assert score_tome >= 15.0, f"Gorganian Tome deve ter prioridade alta para compra, obtido {score_tome}"


def test_kassai_strategy_and_hero_ability():
    """Kassai reconhece sua estratégia, ativa habilidade e valoriza compras para redução passiva."""
    strat = get_hero_strategy("kassai_of_the_golden_sand")
    assert isinstance(strat, KassaiStrategy)

    strat_sellsword = get_hero_strategy("kassai_cintari_sellsword")
    assert isinstance(strat_sellsword, KassaiStrategy)

    # Avaliação da habilidade de herói
    score_h = strat.evaluate_hero_ability({}, {"cardNumber": "kassai_of_the_golden_sand"})
    assert score_h >= 17.0

    # Gorganian Tome ativa desconto passivo de espadas e dá go again
    score_tome = strat.evaluate_attack_card("gorganian_tome", power=0, cost=0, has_go_again=True, pitch=0)
    assert score_tome >= 15.0


def test_bravo_hero_ability():
    """Bravo avalia Dominate quando tem ataque de custo >= 3."""
    strat = get_hero_strategy("bravo_showstopper")
    assert isinstance(strat, GuardianStrategy)

    # Com ataque pesado na mão (cost 4)
    state_heavy = {
        "playerHand": [{"cardNumber": "spinal_crush", "cost": 4, "pitch": 1}],
        "playerArsenal": [],
    }
    score = strat.evaluate_hero_ability(state_heavy, {"cardNumber": "bravo_showstopper"})
    assert score >= 16.0

    # Sem ataque pesado
    state_light = {
        "playerHand": [{"cardNumber": "herald_of_protection", "cost": 1, "pitch": 1}],
        "playerArsenal": [],
    }
    score_light = strat.evaluate_hero_ability(state_light, {"cardNumber": "bravo_showstopper"})
    assert score_light == 0.0
