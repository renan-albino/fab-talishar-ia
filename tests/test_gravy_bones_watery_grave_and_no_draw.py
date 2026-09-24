import os
import json
import pytest
from ai.policy_engine import PolicyEngine
from ai.hero_strategies.other_classes import GravyBonesStrategy
from stats_manager import update_match_result, get_stats_data

TEST_STATS_FILE = "data/test_gravy_bones_stats.json"

@pytest.fixture(autouse=True)
def setup_teardown_test_stats(monkeypatch):
    from stats_manager import reset_stats
    import sqlite3
    import tempfile
    
    fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    def mock_get_connection():
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL, room_id TEXT, winner TEXT,
                p1_health INTEGER, p2_health INTEGER, total_turns INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hero_elo (
                deck_name TEXT PRIMARY KEY, elo REAL,
                matches INTEGER, wins INTEGER, losses INTEGER,
                human_matches INTEGER, human_wins INTEGER
            )
        ''')
        conn.commit()
        return conn

    import stats.db
    monkeypatch.setattr(stats.db, "get_connection", mock_get_connection)
    reset_stats()
    
    yield
    
    if os.path.exists(temp_db):
        os.remove(temp_db)


def test_gravy_bones_ally_stock_tracking():
    """Valida que o Ally Stock Tracker cataloga com precisão aliados na mesa, mão, face-up e face-down no cemitério."""
    strat = GravyBonesStrategy()

    fake_state = {
        "playerAllies": [
            {"cardNumber": "riggermortis_yellow", "name": "Riggermortis", "action": 24, "power": 6}
        ],
        "playerHand": [
            {"cardNumber": "anka_drag_under_yellow", "name": "Anka", "pitch": 2, "cost": 2, "action": 27}
        ],
        "playerDiscard": [
            # Aliado morto em combate (virado para baixo - overlay: 1 / facing: DOWN)
            {"cardNumber": "chum_friendly_first_mate_yellow", "name": "Chum", "overlay": 1, "facing": "DOWN", "action": 0},
            # Aliado descartado/pitchado (virado para cima - overlay: 0)
            {"cardNumber": "sawbones_dock_hand_yellow", "name": "Sawbones", "overlay": 0, "facing": "UP", "action": 36},
            # Carta normal
            {"cardNumber": "blood_in_the_water_red", "name": "Blood in the Water", "overlay": 0}
        ],
        "playerBanish": [
            {"cardNumber": "scooba_salty_sea_dog_yellow", "name": "Scooba"}
        ]
    }

    stock = strat.get_ally_stock(fake_state)

    assert len(stock["arena_allies"]) == 1
    assert len(stock["hand_allies"]) == 1
    assert len(stock["grave_facedown_allies"]) == 1
    assert len(stock["grave_faceup_allies"]) == 1
    assert len(stock["banish_allies"]) == 1
    assert stock["total_dead_facedown"] == 1
    # Conhecidos: 1 arena + 1 mão + 1 face-down + 1 face-up + 1 banish = 5
    # Restante no deck: 15 - 5 = 10
    assert stock["estimated_deck_allies"] == 10
    # Disponíveis para jogo: 1 arena + 1 mão + 1 face-up + 10 deck = 13
    assert stock["total_available_allies"] == 13


def test_gravy_bones_ignores_facedown_allies_in_graveyard():
    """Garante que aliados virados para baixo no cemitério (mortos em combate) NUNCA sejam selecionados."""
    pe = PolicyEngine(hero_name="gravy_bones_shipwrecked_looter", use_gpu=False, num_mcts_sims=0)

    # Estado onde há apenas aliados virados para baixo no cemitério e nenhum ataque na mão
    state = {
        "playerHand": [
            {"cardNumber": "blood_in_the_water_red", "name": "Blood in the Water", "pitch": 1, "action": 0, "defense": 4}
        ],
        "playerAllies": [],
        "playerArsenal": [],
        "playerDiscard": [
            {
                "cardNumber": "riggermortis_yellow",
                "name": "Riggermortis",
                "action": 36,
                "actionDataOverride": "0",
                "overlay": 1,
                "facing": "DOWN",
                "power": 6,
                "cost": 1
            }
        ],
        "playerResources": [2, 2],
        "actionPoints": 1
    }

    atk = pe.select_best_attack(state)
    # Não deve escolher o aliado virado para baixo mesmo que action > 0
    assert atk is None or atk.get("type") != "graveyard"


def test_gravy_bones_selects_faceup_graveyard_ally_when_playable():
    """Valida que aliados virados para cima com Watery Grave ativo (action == 36) são selecionados e usam mode 36."""
    pe = PolicyEngine(hero_name="gravy_bones_shipwrecked_looter", use_gpu=False, num_mcts_sims=0)

    state = {
        "playerHand": [
            {"cardNumber": "tip_the_barkeep_blue", "name": "Tip the Barkeep", "pitch": 3, "action": 0}
        ],
        "playerAllies": [],
        "playerArsenal": [],
        "playerDiscard": [
            {
                "cardNumber": "riggermortis_yellow",
                "name": "Riggermortis",
                "action": 36,
                "actionDataOverride": "0",
                "overlay": 0,
                "facing": "UP",
                "power": 6,
                "cost": 1
            }
        ],
        "playerResources": [1, 3],
        "actionPoints": 1
    }

    atk = pe.select_best_attack(state)
    assert atk is not None
    assert atk.get("type") == "graveyard"
    assert atk.get("mode") == 36
    assert atk.get("card_id") == "0"
    assert "riggermortis" in atk.get("name")


def test_gravy_bones_triggers_watery_grave_with_blue_enabler():
    """Valida que o bot sequencia uma ação azul da mão com prioridade máxima para ativar Watery Grave."""
    pe = PolicyEngine(hero_name="gravy_bones_shipwrecked_looter", use_gpu=False, num_mcts_sims=0)

    state = {
        "playerHand": [
            {
                "cardNumber": "call_to_the_grave_blue",
                "name": "Call to the Grave",
                "pitch": 3,
                "cost": 0,
                "action": 27,
                "power": 0,
                "has_go_again": True
            },
            {
                "cardNumber": "blood_in_the_water_red",
                "name": "Blood in the Water",
                "pitch": 1,
                "cost": 0,
                "action": 0,
                "defense": 4
            }
        ],
        "playerAllies": [],
        "playerArsenal": [],
        "playerDiscard": [
            {
                "cardNumber": "anka_drag_under_yellow",
                "name": "Anka",
                "overlay": 0,
                "facing": "UP",
                "power": 5,
                "cost": 2,
                "action": 0
            }
        ],
        "playerResources": [0, 3],
        "actionPoints": 1
    }

    best_action = pe.select_best_attack(state)
    assert best_action is not None
    assert best_action.get("name") == "call_to_the_grave_blue"
    assert best_action.get("mode") == 27


def test_gravy_bones_shutout_win_preservation():
    """Valida que vitórias com vida intacta (40 HP) em 22 e 25 turnos são registradas como vitórias legítimas."""
    stats = update_match_result(
        room_id="Train_shutout_22_turns",
        p1_deck="Gravy Bones",
        p2_deck="Kassai",
        p1_health=40,
        p2_health=-1,
        total_turns=22,
        winner_id=1,
        is_invalid_match=False
    )

    assert stats["total_matches"] == 1
    assert stats["bot1_wins"] == 1
    assert stats["draws"] == 0
    assert "Bot 1 (Gravy Bones)" in stats["recent_matches"][0]["winner"]
    assert stats["deck_stats"]["Gravy Bones"]["wins"] == 1
    assert stats["deck_stats"]["Gravy Bones"]["losses"] == 0
