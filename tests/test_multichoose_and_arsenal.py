import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from ai.policy_engine import PolicyEngine
from ai.hero_strategies import get_hero_strategy, AssassinStrategy
from ai.hero_strategies.other_classes import MechanologistStrategy
from ai.hero_strategies.ranger import MarlynnStrategy


def test_mario_maps_to_assassin():
    strat = get_hero_strategy("mario")
    assert isinstance(strat, AssassinStrategy)


def test_player_arse_support_in_policy_engine():
    engine = PolicyEngine(hero_name="marlynn_treasure_hunter")
    state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "actionPoints": 1,
        "amIActivePlayer": True,
        "turnPhase": "M",
        "playerHand": [
            {"cardNumber": "yellow_fin_harpoon_blue", "pitch": 3, "action": 27, "cost": 0, "power": 1, "has_go_again": False}
        ],
        # Backend Talishar envia como playerArse
        "playerArse": [
            {"cardNumber": "king_kraken_harpoon_red", "action": 5, "actionDataOverride": "0", "cost": 0, "power": 8, "has_go_again": False}
        ]
    }
    attack = engine.select_best_attack(state)
    assert attack is not None
    assert attack["name"] == "king_kraken_harpoon_red"
    assert attack["mode"] == 5


def test_mechanologist_young_hero_hp_threshold():
    strat = MechanologistStrategy("dash_io")
    state = {
        "playerHealth": 8,
        "opponentHealth": 20,
        "deckCount": 20,
        "playerHand": [
            {"cardNumber": "zero_to_sixty_red", "power": 4, "cost": 0, "pitch": 1}
        ]
    }
    plan = strat.analyze_turn_plan(state)
    # Com 8 HP, para herói jovem de 20 HP, não deve entrar em SURVIVAL_BLOCK mas sim MECH_BOOST_TEMPO
    assert plan.plan_type == "MECH_BOOST_TEMPO"
