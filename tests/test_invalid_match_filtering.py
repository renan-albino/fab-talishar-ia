import os
import json
import pytest
from stats_manager import update_match_result, clean_stalled_matches, get_stats_data

TEST_STATS_FILE = "data/test_training_stats_filtering.json"

@pytest.fixture(autouse=True)
def setup_teardown_test_stats(monkeypatch):
    from stats_manager import reset_stats
    import sqlite3
    
    # Use um banco de dados em memória ou arquivo temporário para os testes
    # O ideal seria injetar o mock no get_connection, mas como não temos 
    # controle do stats.db local facilmente, vamos usar um banco de dados sqlite3 
    # temporário via monkeypatch no get_connection
    import tempfile
    fd, temp_db = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    def mock_get_connection():
        conn = sqlite3.connect(temp_db)
        # Create tables as expected by db.py
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL,
                room_id TEXT,
                winner TEXT,
                p1_health INTEGER,
                p2_health INTEGER,
                total_turns INTEGER
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hero_elo (
                deck_name TEXT PRIMARY KEY,
                elo REAL,
                matches INTEGER,
                wins INTEGER,
                losses INTEGER,
                human_matches INTEGER,
                human_wins INTEGER
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

def test_cc_winner_with_20_hp_is_not_punching_bag():
    """Valida que vencedor em formato CC (40 HP) terminando com 20 HP (sofreu 20 dano) NÃO é anulado como Punching Bag."""
    stats = update_match_result(
        room_id="room_ce73adf8_repro",
        p1_deck="Vynsett",
        p2_deck="Kassai",
        p1_health=-1,
        p2_health=20,
        total_turns=8,
        winner_id=2
    )

    # Não deve ser anulado: Kassai sofreu 20 de dano e venceu de forma legítima
    assert stats["total_matches"] == 1
    assert stats["bot2_wins"] == 1
    assert stats["recent_matches"][0]["winner"] == "🤖 Bot 2 (Kassai)"
    assert stats["deck_stats"]["Kassai"]["wins"] == 1
    assert stats["deck_stats"]["Vynsett"]["losses"] == 1

def test_human_victory_with_full_health_is_not_annulled():
    """Valida que vitória de jogador humano terminando com 40 HP (defendendo ou curando) JAMAIS é anulada como Punching Bag."""
    stats = update_match_result(
        room_id="room_human_40_hp_legit",
        p1_deck="Teklovossen",
        p2_deck="Oscilio GIAF",
        p1_health=40,
        p2_health=-4,
        total_turns=16,
        winner_id=1,
        is_human_p1=True
    )

    assert stats["total_matches"] == 1
    assert stats["bot1_wins"] == 1
    assert "👤 Humano" in stats["recent_matches"][0]["winner"]
    assert "Anulada" not in stats["recent_matches"][0]["winner"]
    assert "👤 Humano (Você)" in stats["deck_stats"]
    assert stats["deck_stats"]["👤 Humano (Você)"]["wins"] == 1


