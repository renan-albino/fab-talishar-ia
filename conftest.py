import os
import sys
import pytest

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))


@pytest.fixture
def mock_player_hand():
    """Retorna uma mão sintética típica de jogador com cartas de ataque, defesa e pitch."""
    return [
        {"cardNumber": "ironsong_response_red", "power": 0, "pitch": 1, "cost": 1, "action": 0},
        {"cardNumber": "steelblade_shunt_blue", "power": 0, "pitch": 3, "cost": 2, "action": 0},
        {"cardNumber": "sink_below_red", "power": 0, "pitch": 1, "cost": 0, "action": 0},
    ]


@pytest.fixture
def mock_game_state(mock_player_hand):
    """Retorna um estado de jogo sintético e realista para testes dos subsistemas de IA."""
    return {
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerAP": 1,
        "playerResources": [1, 0],
        "playerHand": mock_player_hand,
        "playerEquipment": [
            {"cardNumber": "dawnblade", "action": 28, "slot": "Weapon"}
        ],
        "playerArsenal": [],
        "combatChain": [],
        "myTurn": True,
        "isAttacking": False,
        "isDefending": False,
    }
