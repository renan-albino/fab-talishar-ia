import sqlite3
import os
from typing import Optional
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_FILE = os.path.join(BASE_DIR, "data", "talishar_stats.db")

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hero_elo (
                deck_name TEXT PRIMARY KEY,
                matches INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                elo REAL DEFAULT 1200,
                human_matches INTEGER DEFAULT 0,
                human_wins INTEGER DEFAULT 0
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS match_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT,
                date TEXT,
                winner TEXT,
                p1_deck TEXT,
                p2_deck TEXT,
                p1_health INTEGER,
                p2_health INTEGER,
                turns INTEGER
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dynamic_rules (
                hero_name TEXT PRIMARY KEY,
                attack_weight REAL DEFAULT 1.0,
                block_weight REAL DEFAULT 1.0,
                pivot_bonus REAL DEFAULT 1.0,
                arsenal_bonus REAL DEFAULT 1.0,
                absorb_tempo_bonus REAL DEFAULT 1.0,
                last_win_rate REAL DEFAULT 0.0,
                human_wins INTEGER DEFAULT 0,
                matches_evaluated INTEGER DEFAULT 0,
                updated_at REAL DEFAULT 0.0
            )
        ''')
        conn.commit()

@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_FILE, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def get_average_match_length(hero_name: str) -> Optional[float]:
    """Calcula a duração média (em turnos) de partidas envolvendo o herói especificado."""
    if not hero_name:
        return None
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT AVG(turns) as avg_turns FROM match_history
                WHERE (p1_deck LIKE ? OR p2_deck LIKE ?) AND turns > 0
            ''', (f"%{hero_name}%", f"%{hero_name}%"))
            row = cursor.fetchone()
            if row and row["avg_turns"] is not None:
                return float(row["avg_turns"])
    except Exception:
        pass
    return None

# Initialize DB on load
init_db()
