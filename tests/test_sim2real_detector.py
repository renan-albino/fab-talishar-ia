"""
tests/test_sim2real_detector.py
===============================
Testes unitários para o detector de anomalias Sim2Real e auditoria de erros de motor.
"""

import os
import json
import pytest
from ai.sim2real_detector import scan_log_for_anomalies, record_anomaly
from stats.db import get_recent_sim2real_anomalies, get_connection
from ai.shadow_mode import compare


def test_scan_flick_knives_target_lost():
    sample_log = "The targeted dagger is no longer there, the layer fails to resolve"
    anomalies = scan_log_for_anomalies(sample_log)
    assert len(anomalies) == 1
    assert anomalies[0]["code"] == "LAYER_TARGET_LOST"
    assert "The targeted dagger is no longer there" in anomalies[0]["raw_message"]


def test_scan_generic_layer_failure():
    html_log = "<p><span style='color:red;'>The ability fails to resolve due to lack of targets.</span></p>"
    anomalies = scan_log_for_anomalies(html_log)
    assert len(anomalies) == 1
    assert anomalies[0]["code"] == "LAYER_FAILED_TO_RESOLVE"


def test_scan_clean_log_no_anomalies():
    clean_log = (
        "Player 1 played Wounded Bull\n"
        "Player 2 pitched Blue Card\n"
        "Combat resolved with a hit for 4 damage\n"
    )
    anomalies = scan_log_for_anomalies(clean_log)
    assert len(anomalies) == 0


def test_scan_php_engine_error():
    log_err = "<b>Fatal error</b>: Uncaught Error: Call to a member function Index() on null in /var/www/html/Search.php"
    anomalies = scan_log_for_anomalies(log_err)
    assert len(anomalies) == 1
    assert anomalies[0]["code"] == "PHP_ENGINE_FATAL"


def test_record_and_query_anomaly():
    test_room = "TestRoom_Sim2Real_99"
    test_hero = "Kassai"
    test_msg = "The targeted dagger is no longer there, the layer fails to resolve"

    record_anomaly(
        room_id=test_room,
        hero=test_hero,
        turn=4,
        phase="M",
        anomaly_type="LAYER_TARGET_LOST",
        message=test_msg,
        opponent_hero="Dorinthea",
        last_action={"mode": 27, "card_id": "flick_knives"},
        extra_context={"test": True},
    )

    recent = get_recent_sim2real_anomalies(limit=10)
    matched = [a for a in recent if a["room_id"] == test_room]
    assert len(matched) >= 1
    item = matched[0]
    assert item["hero"] == test_hero
    assert item["anomaly_type"] == "LAYER_TARGET_LOST"
    assert item["raw_message"] == test_msg
    assert "flick_knives" in item["last_action_json"]


def test_shadow_mode_card_unconsumed():
    expected = {
        "hand_count": 3,
        "resources": 0,
        "action_points": 0,
        "arsenal_count": 0,
        "player_health": 40,
        "opponent_health": 40,
        "card_consumed": "snatch_red",
    }
    pre_state = {
        "turnNo": 1,
        "turnPlayer": 1,
        "playerHand": [{"cardNumber": "snatch_red"}, {"cardNumber": "sink_below_red"}],
        "playerResources": [0, 0],
        "playerAP": 1,
        "playerArsenal": [],
        "playerHealth": 40,
        "opponentHealth": 40,
    }
    # Simulando rejeição: a carta snatch_red continua na mão no post_state
    post_state = {
        "turnNo": 1,
        "turnPlayer": 1,
        "playerHand": [{"cardNumber": "snatch_red"}, {"cardNumber": "sink_below_red"}],
        "playerResources": [0, 0],
        "playerAP": 1,
        "playerArsenal": [],
        "playerHealth": 40,
        "opponentHealth": 40,
    }

    diffs, confounded = compare(expected, pre_state, post_state)
    assert not confounded
    assert "card_unconsumed" in diffs
    assert "snatch_red" in diffs["card_unconsumed"]["expected"]


def test_flick_knives_dagger_thrown_or_missing_pruning():
    """Valida que Flick Knives só ativa se houver adaga não-arremessada (ativa), e poda se a adaga foi arremessada."""
    from ai.bot_runtime.phase_decider import handle_reaction_phase

    class DummyPolicyEngine:
        def __init__(self):
            self.cards_db = {
                "spider's_bite": {"subtype": "Dagger"},
                "cintari_saber": {"subtype": "Sword"}
            }
            class DummyStrategy:
                def evaluate_equipment_ability(self, s, eq):
                    return 5.0
            self.strategy = DummyStrategy()

        def get_weapon_cost(self, name, eq, s):
            return 0

        def calculate_available_resources(self, s):
            return (2, 2)

    class DummyClient:
        def __init__(self, equip):
            self.player_id = 1
            self.deck_format = "cc"
            self.reaction_attempts = {}
            self.last_attempted_play = None
            self.sent_actions = []
            self.logs = []
            self.policy_engine = DummyPolicyEngine()
            self.state = {
                "turnPhase": "M",
                "activeChainLink": {"attackingCard": {"cardNumber": "command_and_conquer_red", "controller": 1}},
                "playerHand": [{"cardNumber": "sink_below_red"}],
                "playerEquipment": equip,
                "playerResources": [2, 0],
                "playerHealth": 40,
                "opponentHealth": 40
            }

        def log(self, msg):
            self.logs.append(msg)

        def send_chat_log(self, *args, **kwargs):
            pass

        def get_combat_chain_desc(self, state):
            return "Command and Conquer"

        def send_action(self, mode, card_id=None, button_input=None, **kwargs):
            self.sent_actions.append({"mode": mode, "card_id": card_id, "button_input": button_input})

    # Caso 1: Guerreiro com Cintari Saber (espada, sem adaga) -> Não pode ativar Flick Knives
    c1 = DummyClient(equip=[
        {"cardNumber": "cintari_saber", "subType": "Sword", "status": 1},
        {"cardNumber": "flick_knives", "action": 3, "actionDataOverride": "1", "status": 1}
    ])
    result1 = handle_reaction_phase(c1, c1.state, turn_num=1, turn_phase="A", prompt_buttons=[], unpayable_set=set())
    assert not any(a.get("button_input") == "flick_knives" for a in c1.sent_actions)

    # Caso 2: Assassino com adaga equipada e intacta (faca ainda NÃO foi arremessada, status=1) -> Pode ativar
    c2 = DummyClient(equip=[
        {"cardNumber": "spider's_bite", "subType": "Dagger", "status": 1},
        {"cardNumber": "flick_knives", "action": 3, "actionDataOverride": "1", "status": 1}
    ])
    result2 = handle_reaction_phase(c2, c2.state, turn_num=1, turn_phase="A", prompt_buttons=[], unpayable_set=set())
    assert any(a.get("button_input") == "flick_knives" for a in c2.sent_actions)

    # Caso 3: Adaga JÁ FOI ARREMESSADA / destruída (status=0) -> Poda estrita, não ativa novamente
    c3 = DummyClient(equip=[
        {"cardNumber": "spider's_bite", "subType": "Dagger", "status": 0, "destroyed": True},
        {"cardNumber": "flick_knives", "action": 3, "actionDataOverride": "1", "status": 1}
    ])
    result3 = handle_reaction_phase(c3, c3.state, turn_num=1, turn_phase="A", prompt_buttons=[], unpayable_set=set())
    assert not any(a.get("button_input") == "flick_knives" for a in c3.sent_actions)


def test_popup_buttons_fallback_mode_23():
    """Valida que modais com botões (ex.: Transformação do Arakni Marionette) despacham modo 23 e não travam em stall."""
    from ai.bot_runtime.choice_handler import handle_popup_and_choices

    class DummyClient:
        def __init__(self):
            self.player_id = 1
            self.sent_actions = []
            self.logs = []
            self.decision_history = []
            self.recent_phases = []
            self.consecutive_same_state = 0

        def log(self, msg):
            self.logs.append(msg)

        def send_action(self, mode, card_id=None, button_input=None, **kwargs):
            self.sent_actions.append({"mode": mode, "card_id": card_id, "button_input": button_input})

    client = DummyClient()
    popup = {
        "active": True,
        "popup": {
            "id": "OPT",
            "title": "Choose ",
            "cards": [{"cardNumber": "arakni_black_widow", "action": 0}]
        },
        "buttons": [
            {"mode": 23, "buttonInput": "arakni_black_widow", "caption": "Choose"},
            {"mode": 23, "buttonInput": "arakni_funnel_web", "caption": "Choose"}
        ]
    }
    state = {
        "turnPhase": "CHOOSECARD",
        "playerInputPopUp": popup
    }

    handled = handle_popup_and_choices(client, state, turn_phase="CHOOSECARD", popup=popup, prompt_buttons=[], unpayable_set=set())
    assert handled is True
    assert len(client.sent_actions) == 1
    assert client.sent_actions[0]["mode"] == 23
    assert client.sent_actions[0]["button_input"] == "arakni_black_widow"


def test_shadow_mode_predict_resolves_hand_indices():
    """Valida que predict() mapeia índice numérico ('0') para a carta real em playerHand e deduz corretamente."""
    from ai.shadow_mode import predict

    pre_state = {
        "turnPhase": "M",
        "turnNo": 1,
        "playerHand": [
            {"cardNumber": "zero_to_sixty_red", "name": "zero_to_sixty_red"},
            {"cardNumber": "sink_below_red", "name": "sink_below_red"}
        ],
        "playerResources": [0, 0],
        "playerAP": 1,
        "playerHealth": 40,
        "opponentHealth": 40
    }

    # Jogando índice "0" (zero_to_sixty_red) no modo 27
    pred = predict(pre_state, card_id="0", mode=27)
    assert pred is not None
    # Deve prever que a mão diminuiu de 2 para 1
    assert pred["hand_count"] == 1
    assert pred["card_consumed"] == "zero_to_sixty_red"

