"""
tests/test_decompose_and_jarl_equipment.py
=========================================
Valida:
1. Resolução correta da mecânica de Decompose em MAYCHOOSEMULTIZONE / mode 19.
2. Seleção inteligente de equipamentos no Sideboard (Arcane Barrier vs Dano Físico).
3. Avaliação contextual de Gauntlets of the Boreal Domain (Turno 0/1 com pitch vs Mangle vs sem alvo).
"""

import pytest
from unittest.mock import MagicMock
from ai.sideboard_manager import resolve_sideboard
from ai.hero_strategies.equipment_evaluator import evaluate_equipment_ability
from ai.bot_runtime.choice_handler import handle_popup_and_choices
from ai.policy.constants import _get_cards_db


def test_sideboard_selects_providence_vs_physical_and_everbloom_vs_arcane():
    cards_db = _get_cards_db()
    def get_card_meta(c):
        return cards_db.get(c, {})

    # Matchup físico (Jarl ou Ninja Cindra): deve priorizar Crown of Providence (defesa + utilidade)
    res_physical = resolve_sideboard("jarl", "cc", "cindra", "ninja", get_card_meta)
    assert res_physical.get("head") == "crown_of_providence"
    assert res_physical.get("arms") == "gauntlets_of_the_boreal_domain"

    # Matchup arcano (Kano Wizard): deve priorizar Arcane Barrier (Crown of Everbloom e Nullrune)
    res_arcane = resolve_sideboard("jarl", "cc", "kano", "wizard", get_card_meta)
    assert res_arcane.get("head") == "crown_of_everbloom"
    assert res_arcane.get("arms") == "nullrune_gloves"


def test_gauntlets_activation_scoring():
    # 1. Com Mangle na mão: score alto (+22.0)
    state_with_mangle = {
        "turnNo": 3,
        "playerHand": [{"cardNumber": "mangle_red", "cost": 3, "power": 6, "pitch": 1}],
        "playerArsenal": [],
        "playerResources": [2, 0],
    }
    score_mangle = evaluate_equipment_ability(
        "jarl",
        state=state_with_mangle,
        eq_item={"cardNumber": "gauntlets_of_the_boreal_domain"},
        floating_resources=2,
        total_resources=5
    )
    assert score_mangle >= 20.0

    # 2. Em Turno 0/1 com pitch abundante para ciclar a mão: score positivo (+8.0)
    state_early_cycle = {
        "turnNo": 0,
        "playerHand": [
            {"cardNumber": "blue_card_1", "pitch": 3},
            {"cardNumber": "blue_card_2", "pitch": 3},
        ],
        "playerArsenal": [],
        "playerResources": [3, 0],
    }
    score_early = evaluate_equipment_ability(
        "jarl",
        state=state_early_cycle,
        eq_item={"cardNumber": "gauntlets_of_the_boreal_domain"},
        floating_resources=3,
        total_resources=6
    )
    assert score_early > 0.0

    # 3. No meio do jogo (Turno 4) sem Mangle: deve pontuar 0.0 para não queimar recursos
    state_mid_game_no_mangle = {
        "turnNo": 4,
        "playerHand": [{"cardNumber": "autumns_touch_blue", "cost": 0, "power": 3, "pitch": 3}],
        "playerArsenal": [],
        "playerResources": [0, 0],
    }
    score_mid = evaluate_equipment_ability(
        "jarl",
        state=state_mid_game_no_mangle,
        eq_item={"cardNumber": "gauntlets_of_the_boreal_domain"},
        floating_resources=0,
        total_resources=3
    )
    assert score_mid == 0.0


def test_decompose_selects_3_items_in_maychoosemultizone():
    client = MagicMock()
    client.player_id = 2
    client.recent_phases = []
    client.consecutive_same_state = 0
    client.log = MagicMock()
    client.send_action = MagicMock()

    # Cenário de Decompose: Graveyard com 2 Earth cards e 1 Action card
    target_list = [
        {"cardNumber": "crumble_to_eternity_blue"},  # Earth
        {"cardNumber": "autumns_touch_blue"},        # Earth
        {"cardNumber": "sink_below_red"},            # Action
        {"cardNumber": "mangle_red"},                # Action
    ]

    state = {
        "turnPhase": "MAYCHOOSEMULTIZONE",
        "promptText": "Choose 2 Earth cards and an action card to banish",
        "popup": {
            "formOptions": {"minNo": 3, "maxNo": 3, "mode": 19},
            "cards": target_list,
        }
    }

    handled = handle_popup_and_choices(
        client,
        state=state,
        turn_phase="MAYCHOOSEMULTIZONE",
        popup=state["popup"],
        prompt_buttons=[],
        unpayable_set=set(),
    )
    assert handled is True
    # Deve ter chamado send_action com mode=19, chk_count=3
    client.send_action.assert_called_once()
    call_kwargs = client.send_action.call_args.kwargs
    assert call_kwargs.get("mode") == 19
    assert call_kwargs.get("chk_count") == 3
    assert len(call_kwargs.get("chk_input")) == 3
