"""
stats/storage.py
================
Persistência e gerenciamento de estatísticas via SQLite3.
"""

import os
import time
from datetime import datetime
from typing import Optional

from ai.logger import get_logger
from stats.deck_names import (
    DECKS_DIR,
    canonicalize_deck_name,
    get_expected_starting_health,
)
from stats.elo import calculate_elo_ratings, calculate_k_factor
from stats.db import get_connection

logger = get_logger("stats_manager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS_FILE = "data/talishar_stats.db"

def get_stats_data(stats_file: Optional[str] = None) -> dict:
    """Lê os dados de estatísticas a partir do SQLite."""
    stats = {
        "total_matches": 0,
        "bot1_wins": 0,
        "bot2_wins": 0,
        "draws": 0,
        "bot1_elo": 1200,
        "bot2_elo": 1200,
        "elo_history": [],
        "deck_stats": {},
        "recent_matches": [],
    }

    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Matches count
        cursor.execute("SELECT COUNT(*) as c FROM match_history WHERE winner NOT LIKE 'Anulada%'")
        stats["total_matches"] = cursor.fetchone()["c"]
        
        # Win stats
        cursor.execute("SELECT winner, COUNT(*) as c FROM match_history GROUP BY winner")
        for row in cursor.fetchall():
            w = row["winner"]
            if w == "Empate":
                stats["draws"] = row["c"]
            elif w.startswith("👤") or w.startswith("Bot 1"):
                stats["bot1_wins"] = row["c"]
            elif w.startswith("🤖"):
                stats["bot2_wins"] = row["c"]
        
        # Deck stats
        cursor.execute("SELECT * FROM hero_elo")
        for row in cursor.fetchall():
            d = row["deck_name"]
            stats["deck_stats"][d] = {
                "matches": row["matches"],
                "wins": row["wins"],
                "losses": row["losses"],
                "elo": row["elo"],
                "human_matches": row["human_matches"],
                "human_wins": row["human_wins"]
            }
            
        # Recent matches
        cursor.execute("SELECT * FROM match_history ORDER BY id DESC LIMIT 30")
        for row in cursor.fetchall():
            stats["recent_matches"].append({
                "room": row["room_id"],
                "date": row["date"],
                "winner": row["winner"],
                "p1_deck": row["p1_deck"],
                "p2_deck": row["p2_deck"],
                "p1_health": row["p1_health"],
                "p2_health": row["p2_health"],
                "turns": row["turns"],
            })

    return stats


def update_match_result(
    room_id: str,
    p1_deck: str,
    p2_deck: str,
    p1_health: int,
    p2_health: int,
    total_turns: int,
    winner_id: int,
    is_human_p1: bool = False,
    is_invalid_match: bool = False,
    invalid_reason: str = "",
    stats_file: Optional[str] = None,
) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Deduplication
        cursor.execute("SELECT 1 FROM match_history WHERE room_id = ?", (room_id,))
        if cursor.fetchone():
            logger.debug(f"Partida '{room_id}' já registrada previamente.")
            return get_stats_data()
            
        p1_deck_clean = canonicalize_deck_name(p1_deck)
        p2_deck_clean = canonicalize_deck_name(p2_deck)
        tracked_p1 = "👤 Humano (Você)" if is_human_p1 else p1_deck_clean
        tracked_p2 = p2_deck_clean

        if not is_invalid_match:
            if winner_id == 0 and (
                (p1_health >= 18 and p2_health >= 18) or
                (p1_health >= 38 and p2_health >= 38)
            ):
                is_invalid_match = True
                invalid_reason = "Empate 0 Dano (Mutual Stall)"
            elif not is_human_p1 and winner_id == 1:
                p1_init = get_expected_starting_health(p1_deck_clean)
                if p1_health >= p1_init and p2_health <= 0 and (5 <= total_turns <= 8):
                    is_invalid_match = True
                    invalid_reason = "Bot Inerte (Punching Bag)"
            elif not is_human_p1 and winner_id == 2:
                p2_init = get_expected_starting_health(p2_deck_clean)
                if p2_health >= p2_init and p1_health <= 0 and (5 <= total_turns <= 8):
                    is_invalid_match = True
                    invalid_reason = "Bot Inerte (Punching Bag)"

        if is_invalid_match:
            logger.warning(f"⚠️ [PARTIDA ANULADA] {room_id} descartada ({invalid_reason}).")
            winner_name = f"Anulada ({invalid_reason or 'Travamento'})"
            cursor.execute('''
                INSERT INTO match_history (room_id, date, winner, p1_deck, p2_deck, p1_health, p2_health, turns)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (room_id, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), winner_name,
                  f"👤 Humano ({p1_deck_clean})" if is_human_p1 else p1_deck_clean,
                  f"🤖 Bot ({p2_deck_clean})" if is_human_p1 else p2_deck_clean,
                  p1_health, p2_health, total_turns))
            conn.commit()
            return get_stats_data()

        # Get elo of decks
        def get_or_create_hero(name):
            cursor.execute("SELECT * FROM hero_elo WHERE deck_name = ?", (name,))
            r = cursor.fetchone()
            if r: return dict(r)
            cursor.execute("INSERT INTO hero_elo (deck_name) VALUES (?)", (name,))
            return {"deck_name": name, "matches": 0, "wins": 0, "losses": 0, "elo": 1200, "human_matches": 0, "human_wins": 0}

        d1_stats = get_or_create_hero(tracked_p1)
        d2_stats = get_or_create_hero(tracked_p2)
        
        cursor.execute("SELECT COUNT(*) as c FROM match_history WHERE winner NOT LIKE 'Anulada%'")
        total_matches = cursor.fetchone()["c"] + 1

        k = calculate_k_factor(matches_played=total_matches, is_human_p1=is_human_p1, winner_id=winner_id)
        d1_elo = d1_stats["elo"]
        d2_elo = d2_stats["elo"]
        new_d1, new_d2 = calculate_elo_ratings(d1_elo, d2_elo, winner_id, k=k)

        d1_stats["elo"] = new_d1
        d2_stats["elo"] = new_d2
        d1_stats["matches"] += 1
        d2_stats["matches"] += 1

        if is_human_p1:
            d2_stats["human_matches"] += 1
            if winner_id == 2:
                d2_stats["human_wins"] += 1

        if winner_id == 1:
            d1_stats["wins"] += 1
            d2_stats["losses"] += 1
            winner_name = f"👤 Humano ({p1_deck_clean})" if is_human_p1 else f"Bot 1 ({p1_deck_clean})"
        elif winner_id == 2:
            d2_stats["wins"] += 1
            d1_stats["losses"] += 1
            winner_name = f"🤖 Bot 2 ({p2_deck_clean})"
        else:
            winner_name = "Empate"

        def update_hero(d):
            cursor.execute('''
                UPDATE hero_elo SET matches=?, wins=?, losses=?, elo=?, human_matches=?, human_wins=?
                WHERE deck_name=?
            ''', (d["matches"], d["wins"], d["losses"], d["elo"], d["human_matches"], d["human_wins"], d["deck_name"]))

        update_hero(d1_stats)
        update_hero(d2_stats)

        cursor.execute('''
            INSERT INTO match_history (room_id, date, winner, p1_deck, p2_deck, p1_health, p2_health, turns)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (room_id, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), winner_name,
              f"👤 Humano ({p1_deck_clean})" if is_human_p1 else p1_deck_clean,
              f"🤖 Bot ({p2_deck_clean})" if is_human_p1 else p2_deck_clean,
              p1_health, p2_health, total_turns))
        
        conn.commit()

    try:
        from ai.dynamic_rule_tuner import sync_multipliers_with_stats
        sync_multipliers_with_stats()
    except Exception as e:
        logger.warning(f"Erro ao sincronizar multiplicadores dinâmicos: {e}")

    return get_stats_data()


def delete_deck_stat(deck_name: str, stats_file: Optional[str] = None) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        c_name = canonicalize_deck_name(deck_name)
        cursor.execute("DELETE FROM hero_elo WHERE deck_name IN (?, ?)", (deck_name, c_name))
        conn.commit()
        return cursor.rowcount > 0


def reset_stats(stats_file: Optional[str] = None) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM match_history")
        cursor.execute("DELETE FROM hero_elo")
        conn.commit()
    return get_stats_data()


def reset_all_elos(stats_file: Optional[str] = None) -> dict:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE hero_elo SET elo = 1200, matches = 0, wins = 0, losses = 0, human_matches = 0, human_wins = 0")
        cursor.execute("DELETE FROM match_history")
        conn.commit()
    
    try:
        from ai.dynamic_rule_tuner import sync_multipliers_with_stats
        sync_multipliers_with_stats()
    except Exception as e:
        logger.warning(f"Erro ao sincronizar após reset de ELO: {e}")
        
    return get_stats_data()

