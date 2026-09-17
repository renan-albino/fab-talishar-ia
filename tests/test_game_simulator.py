import pytest
from ai.game_simulator import GameSimulator, _shallow_clone_state

def test_shallow_clone_state_isolation():
    original_state = {
        "playerHealth": 20,
        "playerResources": [2, 0],
        "playerHand": [{"cardNumber": "zero_to_sixty_red"}],
        "playerPitch": [],
        "playerDiscard": [],
        "playerArsenal": [{"cardNumber": "sink_below_red"}],
        "playerBanish": [],
        "activeChainLink": {"power": 4}
    }
    
    cloned = _shallow_clone_state(original_state)
    
    # Mutate cloned state
    cloned["playerHealth"] = 15
    cloned["playerHand"].append({"cardNumber": "throttle_blue"})
    cloned["playerResources"][0] = 5
    cloned["activeChainLink"]["power"] = 8
    
    # Original must remain untouched
    assert original_state["playerHealth"] == 20
    assert len(original_state["playerHand"]) == 1
    assert original_state["playerResources"][0] == 2
    assert original_state["activeChainLink"]["power"] == 4

def test_extract_card_meta_pitches_and_power():
    blue_card = {"cardNumber": "throttle_blue", "power": 4}
    meta_blue = GameSimulator.extract_card_meta(blue_card)
    assert meta_blue["pitch"] == 3
    assert meta_blue["power"] == 4
    assert meta_blue["has_go_again"] is True

    yellow_card = {"cardNumber": "convection_yellow"}
    meta_yellow = GameSimulator.extract_card_meta(yellow_card)
    assert meta_yellow["pitch"] == 2

    red_card = {"cardNumber": "fast_and_furious_red"}
    meta_red = GameSimulator.extract_card_meta(red_card)
    assert meta_red["pitch"] == 1
    assert meta_red["has_go_again"] is True

def test_simulate_attack_with_go_again():
    state = {
        "playerAP": 1,
        "playerResources": [3, 0],
        "playerHand": [{"cardNumber": "zero_to_sixty_red"}],
        "playerPitch": [],
        "playerDiscard": [],
        "opponentHealth": 30,
        "opponentHandCount": 2
    }
    action = {
        "name": "zero_to_sixty_red",
        "type": "hand",
        "cost": 0,
        "power": 4,
        "has_go_again": True
    }
    
    result = GameSimulator.simulate_attack(state, action)
    
    # With go again, AP should be preserved
    assert result["playerAP"] == 1
    # Opponent health should be reduced
    assert result["opponentHealth"] < 30
    # Card should be moved from hand to discard
    assert len(result["playerHand"]) == 0
    assert len(result["playerDiscard"]) == 1

def test_simulate_attack_without_go_again():
    state = {
        "playerAP": 1,
        "playerResources": [2, 0],
        "playerHand": [{"cardNumber": "wounding_blow_red"}],
        "playerPitch": [],
        "playerDiscard": [],
        "opponentHealth": 30,
        "opponentHandCount": 0
    }
    action = {
        "name": "wounding_blow_red",
        "type": "hand",
        "cost": 0,
        "power": 4,
        "has_go_again": False
    }
    
    result = GameSimulator.simulate_attack(state, action)
    assert result["playerAP"] == 0
    assert result["opponentHealth"] == 26

def test_simulate_pitch():
    state = {
        "playerResources": [0, 0],
        "playerHand": [{"cardNumber": "sink_below_blue"}],
        "playerPitch": []
    }
    card = {"cardNumber": "sink_below_blue"}
    result = GameSimulator.simulate_pitch(state, card)
    assert result["playerResources"][0] == 3
    assert len(result["playerHand"]) == 0
    assert len(result["playerPitch"]) == 1

def test_extract_card_meta_from_db_and_semantics():
    # 1. Dominate
    meta_dom = GameSimulator.extract_card_meta({"cardNumber": "arknight_ascendancy_red"})
    assert meta_dom["dominate"] is True
    assert meta_dom["power"] == 5
    assert meta_dom["cost"] == 6

    # 2. Overpower
    meta_op = GameSimulator.extract_card_meta({"cardNumber": "annihilator_engine_red"})
    assert meta_op["overpower"] is True
    assert meta_op["power"] == 6
    assert meta_op["cost"] == 6

    # 3. Piercing
    meta_pierce = GameSimulator.extract_card_meta({"cardNumber": "drill_shot_red"})
    assert meta_pierce["piercing"] >= 1
    assert meta_pierce["power"] == 4

    # 4. Phantasm
    meta_phan = GameSimulator.extract_card_meta({"cardNumber": "coalescence_mirage_red"})
    assert meta_phan["phantasm"] is True
    assert meta_phan["power"] == 7

    # 5. On-hit severity
    meta_sev = GameSimulator.extract_card_meta({"cardNumber": "blizzard_bolt_red"})
    assert meta_sev["on_hit_severity"] > 0
    assert meta_sev["has_on_hit"] is True

    # 6. Command & Conquer
    meta_cnc = GameSimulator.extract_card_meta({"cardNumber": "command_and_conquer_red"})
    assert meta_cnc["power"] == 6
    assert meta_cnc["cost"] == 2
    assert meta_cnc["has_on_hit"] is True
    assert meta_cnc["on_hit_severity"] >= 10.0

    # 7. Defense
    meta_sink = GameSimulator.extract_card_meta({"cardNumber": "sink_below_red"})
    assert meta_sink["defense"] == 4

    # 8. Safe fallback for absent card
    meta_absent = GameSimulator.extract_card_meta({"cardNumber": "unknown_absent_card_blue"})
    assert meta_absent["pitch"] == 3
    assert meta_absent["power"] == 0
    assert meta_absent["defense"] == 3

def test_shallow_clone_state_card_dict_mutation_isolation():
    original_state = {
        "playerHealth": 20,
        "playerHand": [{"cardNumber": "zero_to_sixty_red", "custom_tag": "original"}],
        "activeChainLink": {"power": 4, "metadata": {"origin": "active"}}
    }
    cloned = _shallow_clone_state(original_state)
    cloned["playerHand"][0]["custom_tag"] = "mutated"
    cloned["playerHand"][0]["new_field"] = 999

    assert original_state["playerHand"][0]["custom_tag"] == "original"
    assert "new_field" not in original_state["playerHand"][0]

def test_simulate_attack_duplicate_hand_cards_pitch():
    # Hand with two identical throttle_blue cards (cost 2, pitch 3)
    # Playing one should pitch the other and discard the played card
    state = {
        "playerAP": 1,
        "playerResources": [0, 0],
        "playerHand": [
            {"cardNumber": "throttle_blue"},
            {"cardNumber": "throttle_blue"}
        ],
        "playerPitch": [],
        "playerDiscard": [],
        "opponentHealth": 30,
        "opponentHandCount": 0
    }
    action = {
        "name": "throttle_blue",
        "type": "hand",
        "cost": 2,
        "power": 4,
        "has_go_again": True
    }
    result = GameSimulator.simulate_attack(state, action)
    assert len(result["playerHand"]) == 0
    assert len(result["playerPitch"]) == 1
    assert result["playerPitch"][0]["cardNumber"] == "throttle_blue"
    assert len(result["playerDiscard"]) == 1
    assert result["playerDiscard"][0]["cardNumber"] == "throttle_blue"
    assert result["playerResources"][0] == 1  # 3 pitched - 2 cost = 1 floating

    # Hand with two identical 0-cost cards: playing one leaves the other in hand
    state2 = {
        "playerAP": 1,
        "playerResources": [0, 0],
        "playerHand": [
            {"cardNumber": "zero_to_sixty_red"},
            {"cardNumber": "zero_to_sixty_red"}
        ],
        "playerPitch": [],
        "playerDiscard": [],
        "opponentHealth": 30,
        "opponentHandCount": 0
    }
    action2 = {
        "name": "zero_to_sixty_red",
        "type": "hand",
        "cost": 0,
        "power": 4,
        "has_go_again": True
    }
    result2 = GameSimulator.simulate_attack(state2, action2)
    assert len(result2["playerHand"]) == 1
    assert len(result2["playerDiscard"]) == 1
    assert len(result2["playerPitch"]) == 0

def test_simulate_attack_cr_1_14_2_payment_order():
    # Hand contains Red (pitch 1), Yellow (pitch 2), Blue (pitch 3), and attack card
    # Cost is 3. Under CR 1.14.2, Blue (3) must be pitched first to cover cost.
    state = {
        "playerAP": 1,
        "playerResources": [0, 0],
        "playerHand": [
            {"cardNumber": "command_and_conquer_red"},
            {"cardNumber": "sink_below_red"},     # pitch 1
            {"cardNumber": "invigorate_yellow"},   # pitch 2
            {"cardNumber": "throttle_blue"},       # pitch 3
        ],
        "playerPitch": [],
        "playerDiscard": [],
        "opponentHealth": 30,
        "opponentHandCount": 0
    }
    action = {
        "name": "command_and_conquer_red",
        "type": "hand",
        "cost": 3,
        "power": 6
    }
    result = GameSimulator.simulate_attack(state, action)
    assert len(result["playerPitch"]) == 1
    assert result["playerPitch"][0]["cardNumber"] == "throttle_blue"
    # Red and Yellow should remain in hand untouched
    rem_cards = [c["cardNumber"] for c in result["playerHand"]]
    assert "sink_below_red" in rem_cards
    assert "invigorate_yellow" in rem_cards
    assert len(result["playerHand"]) == 2
    assert len(result["playerDiscard"]) == 1

def test_simulate_attack_equipment_buff_augments_attack_not_opponent_hp():
    state = {
        "playerAP": 1,
        "playerResources": [0, 0],
        "playerHand": [{"cardNumber": "zero_to_sixty_red"}],
        "playerPitch": [],
        "playerDiscard": [],
        "opponentHealth": 30,
        "opponentHandCount": 0
    }
    buff_action = {
        "type": "equipment_ability",
        "name": "goliath_gauntlet",
        "buff_power": 2,
        "has_go_again": True
    }
    state_after_buff = GameSimulator.simulate_attack(state, buff_action)
    # Equipment buff must NOT subtract opponent HP directly!
    assert state_after_buff["opponentHealth"] == 30
    assert state_after_buff["currentAttackBuff"] == 2

    # Subsequent attack receives the +2 power buff
    attack_action = {
        "name": "zero_to_sixty_red",
        "type": "hand",
        "cost": 0,
        "power": 4,
        "has_go_again": True
    }
    result = GameSimulator.simulate_attack(state_after_buff, attack_action)
    # Opponent health should decrease by 4 + 2 = 6
    assert result["opponentHealth"] == 24
    assert result.get("currentAttackBuff", 0) == 0

def test_simulate_defense_multi_card_block_sums_defense():
    # Multi-card block in a single action: 7 power incoming, blocked with 4 + 2 = 6
    state = {
        "playerHealth": 20,
        "combatChainPower": 7,
        "activeChainLink": {"totalPower": 7},
        "playerHand": [
            {"cardNumber": "sink_below_red"},
            {"cardNumber": "invigorate_yellow"}
        ],
        "playerDiscard": []
    }
    block_action = {
        "cards": [
            {"cardNumber": "sink_below_red", "defense": 4},
            {"cardNumber": "invigorate_yellow", "defense": 2}
        ]
    }
    result = GameSimulator.simulate_defense(state, block_action)
    # Damage should be 7 - (4 + 2) = 1, NOT (7 - 4) + (7 - 2) = 8!
    assert result["playerHealth"] == 19
    assert len(result["playerHand"]) == 0
    assert len(result["playerDiscard"]) == 2

def test_simulate_defense_sequential_multi_card_blocks():
    # Sequential single-card blocks on the same chain link
    state = {
        "playerHealth": 20,
        "combatChainPower": 7,
        "activeChainLink": {"totalPower": 7},
        "playerHand": [
            {"cardNumber": "sink_below_red"},
            {"cardNumber": "invigorate_yellow"}
        ],
        "playerDiscard": []
    }
    # Step 1: block with 4
    step1 = GameSimulator.simulate_defense(state, {"name": "sink_below_red", "defense": 4})
    assert step1["playerHealth"] == 17  # 7 - 4 = 3 damage taken
    assert len(step1["playerHand"]) == 1

    # Step 2: block with 2 on same chain link
    step2 = GameSimulator.simulate_defense(step1, {"name": "invigorate_yellow", "defense": 2})
    # Total def is 6. Net damage should be 7 - 6 = 1. Player health should be 19!
    assert step2["playerHealth"] == 19
    assert len(step2["playerHand"]) == 0
    assert len(step2["playerDiscard"]) == 2
