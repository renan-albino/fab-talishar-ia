"""
tests/test_go_again_resolver.py
===============================
Testes unitários para o módulo de resolução dinâmica de Go Again (ai/policy/go_again_resolver.py),
a poda rígida de sequenciamento de ataque (-35.0) e integração com a estratégia Ninja.
"""

import pytest
from ai.policy.go_again_resolver import resolve_attack_go_again, is_draconic_card
from ai.policy.engine import PolicyEngine
from ai.policy.attack_pruner import select_best_attack
from ai.hero_strategies.ninja import NinjaStrategy


# ──────────────────────────────────────────────────────────────────
# 1. TESTES DO GO_AGAIN_RESOLVER
# ──────────────────────────────────────────────────────────────────

def test_natural_go_again():
    """Cartas com Go Again natural retornam (True, 'natural_go_again')."""
    state_empty = {"currentChainLink": 1, "combatChainLinks": []}
    
    has_ga, reason = resolve_attack_go_again("leg_tap_red", state_empty)
    assert has_ga is True
    assert reason == "natural_go_again"

    has_ga, reason = resolve_attack_go_again("snatch_red", state_empty)
    assert has_ga is False
    assert reason == "no_go_again"


def test_quicken_and_agility_tokens():
    """Tokens quicken/agility no 1º elo da cadeia concedem Go Again."""
    state_quicken_link_1 = {
        "currentChainLink": 1,
        "playerTokens": ["quicken"],
        "combatChainLinks": [],
    }
    has_ga, reason = resolve_attack_go_again("snatch_red", state_quicken_link_1)
    assert has_ga is True
    assert reason == "token_granted"

    # No 2º elo da cadeia, o token já foi consumido / não é o 1º ataque
    state_quicken_link_2 = {
        "currentChainLink": 2,
        "playerTokens": ["quicken"],
        "combatChainLinks": [{"cardNumber": "atk1"}],
    }
    has_ga, reason = resolve_attack_go_again("snatch_red", state_quicken_link_2)
    assert has_ga is False
    assert reason == "no_go_again"


def test_draconic_chain_links_threshold():
    """
    Cartas Dracônicas (burning_blade_dance, lava_vein_loyalty, etc.)
    exigem >= 2 links dracônicos prévios no combate ativo.
    """
    state_0_draconic = {
        "currentChainLink": 1,
        "combatChainLinks": [],
    }
    has_ga, reason = resolve_attack_go_again("burning_blade_dance_red", state_0_draconic)
    assert has_ga is False
    assert reason == "insufficient_draconic_links"

    state_1_draconic = {
        "currentChainLink": 2,
        "combatChainLinks": [
            {"cardNumber": "ronin_renegade_red", "talent": "DRACONIC"},
        ],
    }
    has_ga, reason = resolve_attack_go_again("burning_blade_dance_red", state_1_draconic)
    assert has_ga is False
    assert reason == "insufficient_draconic_links"

    state_2_draconic = {
        "currentChainLink": 3,
        "combatChainLinks": [
            {"cardNumber": "ronin_renegade_red", "talent": "DRACONIC"},
            {"cardNumber": "phoenix_flame_red", "talent": "DRACONIC"},
        ],
    }
    has_ga, reason = resolve_attack_go_again("burning_blade_dance_red", state_2_draconic)
    assert has_ga is True
    assert reason == "draconic_threshold_met"

    # Outras cartas dracônicas com exigência idêntica
    has_ga, reason = resolve_attack_go_again("lava_vein_loyalty_red", state_2_draconic)
    assert has_ga is True
    assert reason == "draconic_threshold_met"

    has_ga, reason = resolve_attack_go_again("cinderskin_devotion_red", state_0_draconic)
    assert has_ga is False
    assert reason == "insufficient_draconic_links"


def test_blaze_headlong_red_card_requirement():
    """Blaze Headlong só tem Go Again se outra carta vermelha já foi jogada no turno."""
    state_no_red = {
        "currentChainLink": 1,
        "currentTurnEffects": [],
        "currentTurnActions": [],
        "combatChainLinks": [],
    }
    has_ga, reason = resolve_attack_go_again("blaze_headlong_red", state_no_red)
    assert has_ga is False
    assert reason == "no_prior_red_card"

    # Com carta vermelha em currentTurnActions
    state_with_red_action = {
        "currentChainLink": 2,
        "currentTurnActions": [{"cardNumber": "ronin_renegade_red", "pitch": 1}],
        "combatChainLinks": [],
    }
    has_ga, reason = resolve_attack_go_again("blaze_headlong_red", state_with_red_action)
    assert has_ga is True
    assert reason == "red_card_played"

    # Com carta vermelha no combatChainLinks
    state_with_red_link = {
        "currentChainLink": 2,
        "combatChainLinks": [{"cardNumber": "snatch_red", "pitch": 1}],
    }
    has_ga, reason = resolve_attack_go_again("blaze_headlong_red", state_with_red_link)
    assert has_ga is True
    assert reason == "red_card_played"


def test_ninja_combos():
    """Combos Ninja avaliam se o último ataque da cadeia satisfaz o gatilho."""
    # Rising Knee Thrust requer Leg Tap
    state_rising_knee_satisfied = {
        "currentChainLink": 2,
        "activeChainLink": {"cardNumber": "leg_tap_red"},
    }
    has_ga, reason = resolve_attack_go_again("rising_knee_thrust_red", state_rising_knee_satisfied)
    assert has_ga is True
    assert reason == "combo_active"

    state_rising_knee_unsatisfied = {
        "currentChainLink": 2,
        "activeChainLink": {"cardNumber": "snatch_red"},
    }
    has_ga, reason = resolve_attack_go_again("rising_knee_thrust_red", state_rising_knee_unsatisfied)
    assert has_ga is False
    assert reason == "combo_inactive"

    # Crane Dance requer Soulbead Strike
    state_crane_satisfied = {
        "currentChainLink": 2,
        "combatChainLinks": [{"cardNumber": "soulbead_strike_red"}],
    }
    has_ga, reason = resolve_attack_go_again("crane_dance_red", state_crane_satisfied)
    assert has_ga is True
    assert reason == "combo_active"

    # Whelming Gustwave requer Surging Strike
    state_whelming_satisfied = {
        "currentChainLink": 2,
        "combatChainLinks": [{"cardNumber": "surging_strike_red"}],
    }
    has_ga, reason = resolve_attack_go_again("whelming_gustwave_red", state_whelming_satisfied)
    assert has_ga is True
    assert reason == "combo_active"


# ──────────────────────────────────────────────────────────────────
# 2. TESTES DA PODA RÍGIDA NO ATTACK_PRUNER (-35.0)
# ──────────────────────────────────────────────────────────────────

def test_attack_pruner_rigid_penalty_burning_blade_dance():
    """
    Quando player_ap <= 1 e len(hand_attacks) > 1, ataque sem Go Again garantido
    (como burning_blade_dance_red sem links dracônicos) recebe penalidade -35.0,
    garantindo que o opener seja a carta com Go Again (leg_tap_red).
    """
    engine = PolicyEngine(hero_name="fai")
    engine.num_mcts_sims = 0

    state = {
        "myTurn": True,
        "isCombatPhase": True,
        "currentChainLink": 1,
        "actionPoints": 1,
        "playerHealth": 20,
        "playerHand": [
            {
                "cardNumber": "burning_blade_dance_red",
                "name": "burning_blade_dance_red",
                "cost": 0,
                "power": 3,
                "type": "AA",
                "action": 1,
                "pitch": 1,
            },
            {
                "cardNumber": "leg_tap_red",
                "name": "leg_tap_red",
                "cost": 0,
                "power": 4,
                "type": "AA",
                "action": 2,
                "pitch": 1,
            },
            {
                "cardNumber": "blue_pitch_blue",
                "name": "blue_pitch_blue",
                "cost": 0,
                "power": 0,
                "type": "A",
                "action": 0,
                "pitch": 3,
            },
        ],
        "combatChainLinks": [],
        "playerTokens": [],
    }

    best_attack = select_best_attack(engine, state)
    assert best_attack is not None
    assert best_attack["name"] == "leg_tap_red"
    assert best_attack["has_go_again"] is True


def test_attack_pruner_rigid_penalty_blaze_headlong():
    """
    Blaze Headlong sem carta vermelha prévia não tem Go Again e é severamente penalizada
    como abertura de cadeia quando há outra opção com Go Again garantido na mão.
    """
    engine = PolicyEngine(hero_name="generic")
    engine.num_mcts_sims = 0

    state = {
        "myTurn": True,
        "isCombatPhase": True,
        "currentChainLink": 1,
        "actionPoints": 1,
        "playerHealth": 20,
        "playerHand": [
            {
                "cardNumber": "blaze_headlong_red",
                "name": "blaze_headlong_red",
                "cost": 0,
                "power": 4,
                "type": "AA",
                "action": 1,
                "pitch": 1,
            },
            {
                "cardNumber": "leg_tap_red",
                "name": "leg_tap_red",
                "cost": 0,
                "power": 4,
                "type": "AA",
                "action": 2,
                "pitch": 1,
            },
        ],
        "combatChainLinks": [],
        "currentTurnActions": [],
        "playerTokens": [],
    }

    best_attack = select_best_attack(engine, state)
    assert best_attack is not None
    assert best_attack["name"] == "leg_tap_red"


# ──────────────────────────────────────────────────────────────────
# 3. TESTES DA ESTRATÉGIA NINJA (STARTERS DINÂMICOS)
# ──────────────────────────────────────────────────────────────────

def test_ninja_strategy_turn_plan_ignores_unmet_conditional_starters():
    """
    NinjaStrategy.analyze_turn_plan não deve selecionar burning_blade_dance
    como starter se ela não tiver Go Again garantido pelo estado atual.
    """
    strat = NinjaStrategy("katsu")

    # Caso 1: 0 links dracônicos prévios -> burning_blade_dance NÃO é starter
    state_unmet = {
        "playerHealth": 16,
        "currentChainLink": 1,
        "combatChainLinks": [],
        "playerHand": [
            {"cardNumber": "burning_blade_dance_red", "power": 3, "cost": 0, "pitch": 1},
            {"cardNumber": "rising_knee_red", "power": 4, "cost": 1, "pitch": 1},
            {"cardNumber": "blue_block_blue", "power": 2, "cost": 0, "pitch": 3},
        ],
    }
    plan_unmet = strat.analyze_turn_plan(state_unmet)
    assert plan_unmet.plan_type != "NINJA_COMBO_CHAIN"

    # Caso 2: 2 links dracônicos prévios -> burning_blade_dance TEM Go Again garantido
    # e é selecionada com sucesso como starter do plano NINJA_COMBO_CHAIN
    state_met = {
        "playerHealth": 16,
        "currentChainLink": 3,
        "combatChainLinks": [
            {"cardNumber": "ronin_renegade_red", "talent": "DRACONIC"},
            {"cardNumber": "phoenix_flame_red", "talent": "DRACONIC"},
        ],
        "playerHand": [
            {"cardNumber": "burning_blade_dance_red", "power": 3, "cost": 0, "pitch": 1},
            {"cardNumber": "rising_knee_red", "power": 4, "cost": 1, "pitch": 1},
            {"cardNumber": "blue_block_blue", "power": 2, "cost": 0, "pitch": 3},
        ],
    }
    plan_met = strat.analyze_turn_plan(state_met)
    assert plan_met.plan_type == "NINJA_COMBO_CHAIN"
    assert "burning_blade_dance_red" in plan_met.reserved_card_names
