import pytest
from unittest.mock import MagicMock
from ai.bot_runtime.choice_handler import extract_popup_cards, handle_popup_and_choices
from ai.bot_runtime.phase_decider import handle_reaction_phase

def test_extract_popup_cards_various_structures():
    # 1. Talishar CreatePopupAPI format (popup["cards"])
    popup1 = {"cards": [{"cardNumber": "kunai_of_retribution", "action": 16, "actionDataOverride": "MYCHAR-1"}]}
    assert len(extract_popup_cards(popup1)) == 1
    assert extract_popup_cards(popup1)[0]["actionDataOverride"] == "MYCHAR-1"

    # 2. Legacy cardsArray format
    popup2 = {"data": {"cardsArray": [{"cardNumber": "spider's_bite"}]}}
    assert len(extract_popup_cards(popup2)) == 1

    # 3. cardsMultiZone format
    popup3 = {"cardsMultiZone": [{"cardNumber": "nerve_scalpel"}]}
    assert len(extract_popup_cards(popup3)) == 1

    # 4. State playerInputPopUp fallback
    state4 = {"playerInputPopUp": {"cards": [{"cardNumber": "orbitoclast"}]}}
    assert len(extract_popup_cards({}, state4)) == 1
    assert extract_popup_cards({}, state4)[0]["cardNumber"] == "orbitoclast"

def test_choose_multizone_dagger_mode_16_target():
    """Valida que no popup de adaga de Pain in the Backside / Flick Knives, o bot escolhe a faca com Mode 16."""
    client = MagicMock()
    client.player_id = 1
    client.policy_engine = MagicMock()
    client.policy_engine.extract_card_info.return_value = {"power": 1, "pitch": 1}
    client.send_action = MagicMock()
    client.log = MagicMock()

    # Simula o popup exato gerado pelo Talishar para CHOOSEMULTIZONE de adaga
    state = {
        "turnPhase": "CHOOSEMULTIZONE",
        "popup": {
            "active": True,
            "cards": [
                {
                    "cardNumber": "kunai_of_retribution",
                    "action": 16,
                    "actionDataOverride": "MYCHAR-1"
                }
            ],
            "formOptions": {}
        }
    }

    result = handle_popup_and_choices(
        client=client,
        state=state,
        turn_phase="CHOOSEMULTIZONE",
        popup=state["popup"],
        prompt_buttons=[],
        unpayable_set=set()
    )

    assert result is True
    # O bot DEVE enviar mode=16 com card_id="MYCHAR-1"
    client.send_action.assert_called_once()
    call_kwargs = client.send_action.call_args[1]
    assert call_kwargs.get("mode") == 16
    assert call_kwargs.get("card_id") == "MYCHAR-1"

def test_flick_knives_pruning_detects_broken_daggers():
    """Valida que Flick Knives não é ativado se todas as adagas tiverem isBroken=True ou overlay=1."""
    client = MagicMock()
    client.player_id = 1
    client.last_attempted_play = None
    client.reaction_attempts = {}
    client.log = MagicMock()
    client.send_chat_log = MagicMock()
    client.get_combat_chain_desc = MagicMock(return_value="Dagger Attack")
    client.blocks_declared_count = 0
    client.policy_engine = MagicMock()
    client.policy_engine.cards_db = {}
    client.policy_engine.calculate_available_resources.return_value = (2, 2)
    client.policy_engine.get_weapon_cost.return_value = 0
    client.policy_engine.strategy.evaluate_equipment_ability.return_value = 10.0

    # Estado onde a Kunai foi arremessada no turno anterior (isBroken=True ou overlay=1)
    state_broken = {
        "turnPhase": "A",
        "turnPlayer": 1,
        "amIActivePlayer": True,
        "activeChainLink": {"attackingPlayer": 1, "isDefending": False},
        "playerEquipment": [
            {"cardNumber": "flick_knives", "action": 1, "actionDataOverride": "EQ-0", "status": 1},
            {"cardNumber": "kunai_of_retribution", "subtype": "Dagger", "isBroken": True, "overlay": 1}
        ]
    }

    handle_reaction_phase(client, state_broken, 1, "A", [], unpayable_set=set())
    # Não deve ativar Flick Knives (mode 1 / EQ-0), mas sim passar a reação (mode 99)
    assert client.send_action.call_args[1].get("mode") == 99

    client.send_action.reset_mock()

    # Estado com adaga íntegra (isBroken=False, overlay=0)
    state_intact = {
        "turnPhase": "A",
        "turnPlayer": 1,
        "amIActivePlayer": True,
        "activeChainLink": {"attackingPlayer": 1, "isDefending": False},
        "playerEquipment": [
            {"cardNumber": "flick_knives", "action": 1, "actionDataOverride": "EQ-0", "status": 1},
            {"cardNumber": "kunai_of_retribution", "subtype": "Dagger", "isBroken": False, "overlay": 0}
        ]
    }

    handle_reaction_phase(client, state_intact, 1, "A", [], unpayable_set=set())
    # Deve ativar Flick Knives (mode 1, EQ-0)
    assert client.send_action.call_args[1].get("mode") == 1
    assert client.send_action.call_args[1].get("card_id") == "EQ-0"
