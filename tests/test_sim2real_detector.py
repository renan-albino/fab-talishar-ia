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
