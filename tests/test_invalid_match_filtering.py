import os
import json
import pytest
from stats_manager import update_match_result, clean_stalled_matches, get_stats_data

TEST_STATS_FILE = "data/test_training_stats_filtering.json"

@pytest.fixture(autouse=True)
def setup_teardown_test_stats(monkeypatch):
    """Configura um arquivo temporário de stats para isolar os testes."""
    os.makedirs("data", exist_ok=True)
    monkeypatch.setattr("stats_manager.STATS_FILE", TEST_STATS_FILE)
    if os.path.exists(TEST_STATS_FILE):
        os.remove(TEST_STATS_FILE)
    bak = TEST_STATS_FILE + ".bak"
    if os.path.exists(bak):
        os.remove(bak)
    yield
    if os.path.exists(TEST_STATS_FILE):
        os.remove(TEST_STATS_FILE)
    if os.path.exists(bak):
        os.remove(bak)

def test_zero_damage_draw_is_discarded():
    """Valida que empate técnico com zero dano trocado não altera ELO nem contabiliza partida."""
    stats = update_match_result(
        room_id="room_zero_dmg",
        p1_deck="Dash IO",
        p2_deck="Kassai",
        p1_health=20,
        p2_health=20,
        total_turns=46,
        winner_id=0,
        is_invalid_match=True,
        invalid_reason="Empate 0 Dano (Mutual Stall)"
    )

    assert stats["total_matches"] == 0
    assert stats["bot1_wins"] == 0
    assert stats["bot2_wins"] == 0
    assert stats["draws"] == 0
    assert stats["bot1_elo"] == 1200
    assert stats["bot2_elo"] == 1200
    assert len(stats["recent_matches"]) == 1
    assert "Anulada (Empate 0 Dano" in stats["recent_matches"][0]["winner"]
    assert "Dash IO" not in stats.get("deck_stats", {})

def test_punching_bag_bot_is_discarded():
    """Valida que partida onde o perdedor travou só apanhando (0 dano em >= 6 turnos) é anulada."""
    stats = update_match_result(
        room_id="room_punching_bag",
        p1_deck="Marlynn Treasure Hunter",
        p2_deck="Dash IO",
        p1_health=40,
        p2_health=0,
        total_turns=6,
        winner_id=1,
        is_invalid_match=True,
        invalid_reason="Bot Inerte (Punching Bag)"
    )

    assert stats["total_matches"] == 0
    assert stats["bot1_wins"] == 0
    assert stats["bot1_elo"] == 1200
    assert len(stats["recent_matches"]) == 1
    assert "Anulada" in stats["recent_matches"][0]["winner"]
    assert "Marlynn Treasure Hunter" not in stats.get("deck_stats", {})

def test_auto_detection_of_punching_bag():
    """Valida a detecção de segurança automática de punching bag quando não explicitamente sinalizada."""
    stats = update_match_result(
        room_id="room_auto_detect",
        p1_deck="Marlynn",
        p2_deck="Dash IO",
        p1_health=40,
        p2_health=0,
        total_turns=7,
        winner_id=1
    )

    # Detecção automática identificou vencedor com 40 HP e perdedor com 0 HP em 7 turnos
    assert stats["total_matches"] == 0
    assert stats["bot1_wins"] == 0
    assert "Anulada (Bot Inerte (Punching Bag))" in stats["recent_matches"][0]["winner"]

def test_legitimate_fatigue_draw_is_preserved():
    """Valida que um empate legítimo com troca substancial de dano (fadiga) é contabilizado."""
    stats = update_match_result(
        room_id="room_legit_draw",
        p1_deck="Jarl",
        p2_deck="Ira Blitz",
        p1_health=4,
        p2_health=3,
        total_turns=35,
        winner_id=0,
        is_invalid_match=False
    )

    assert stats["total_matches"] == 1
    assert stats["draws"] == 1
    assert stats["recent_matches"][0]["winner"] == "Empate"
    assert stats["deck_stats"]["Jarl"]["matches"] == 1
    assert stats["deck_stats"]["Ira Blitz"]["matches"] == 1

def test_clean_stalled_matches_routine():
    """Valida que clean_stalled_matches remove empates residuais dos decks e ajusta contagens."""
    initial_data = {
        "total_matches": 100,
        "bot1_wins": 30,
        "bot2_wins": 30,
        "draws": 40,
        "bot1_elo": 1200,
        "bot2_elo": 1200,
        "deck_stats": {
            "Gravy Bones": {"matches": 50, "wins": 20, "losses": 0, "elo": 1250},
            "Dash IO": {"matches": 50, "wins": 10, "losses": 30, "elo": 1150}
        },
        "recent_matches": [
            {"room": "Train_match_1", "winner": "Empate", "p1_health": 20, "p2_health": 20, "turns": 45},
            {"room": "Train_match_2", "winner": "Bot 1", "p1_health": 40, "p2_health": 0, "turns": 8},
            {"room": "test_room_discard", "winner": "Empate", "p1_health": 20, "p2_health": 20, "turns": 45}
        ]
    }
    with open(TEST_STATS_FILE, "w", encoding="utf-8") as f:
        json.dump(initial_data, f)

    cleaned = clean_stalled_matches(TEST_STATS_FILE)

    # Gravy Bones: tinha 50 jogos (20 vitórias, 0 derrotas, 30 empates artificiais)
    # Após limpeza: matches deve ser 20 (apenas jogos resolvidos)
    assert cleaned["deck_stats"]["Gravy Bones"]["matches"] == 20
    assert cleaned["deck_stats"]["Gravy Bones"]["wins"] == 20
    assert cleaned["deck_stats"]["Gravy Bones"]["losses"] == 0

    # Dash IO: tinha 50 jogos (10 vitórias, 30 derrotas, 10 empates artificiais)
    # Após limpeza: matches deve ser 40
    assert cleaned["deck_stats"]["Dash IO"]["matches"] == 40

    # Salas de teste são descartadas e salas reais são marcadas como anuladas
    assert len(cleaned["recent_matches"]) == 2
    assert "Anulada" in cleaned["recent_matches"][0]["winner"]
    assert "Anulada" in cleaned["recent_matches"][1]["winner"]
    assert all("test" not in m["room"].lower() for m in cleaned["recent_matches"])
