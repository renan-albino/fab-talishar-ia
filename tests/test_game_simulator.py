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
