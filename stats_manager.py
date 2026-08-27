import os
import json
import time
from datetime import datetime

STATS_FILE = "data/training_stats.json"

def get_stats_data():
    os.makedirs("data", exist_ok=True)
    if not os.path.exists(STATS_FILE):
        default_data = {
            "total_matches": 0,
            "bot1_wins": 0,
            "bot2_wins": 0,
            "draws": 0,
            "bot1_elo": 1200,
            "bot2_elo": 1200,
            "elo_history": [{"match": 0, "bot1_elo": 1200, "bot2_elo": 1200, "timestamp": time.time()}],
            "deck_stats": {},
            "recent_matches": []
        }
        with open(STATS_FILE, "w") as f:
            json.dump(default_data, f, indent=2)
        return default_data
    try:
        with open(STATS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {
            "total_matches": 0, "bot1_wins": 0, "bot2_wins": 0, "draws": 0,
            "bot1_elo": 1200, "bot2_elo": 1200, "elo_history": [], "deck_stats": {}, "recent_matches": []
        }

def update_match_result(room_id, p1_deck, p2_deck, p1_health, p2_health, total_turns, winner_id):
    stats = get_stats_data()
    stats["total_matches"] += 1
    
    # Calculate Elo
    r1 = stats.get("bot1_elo", 1200)
    r2 = stats.get("bot2_elo", 1200)
    k = 32
    
    e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
    e2 = 1 / (1 + 10 ** ((r1 - r2) / 400))
    
    if winner_id == 1:
        s1, s2 = 1.0, 0.0
        stats["bot1_wins"] += 1
        winner_name = "Bot 1 (Host)"
    elif winner_id == 2:
        s1, s2 = 0.0, 1.0
        stats["bot2_wins"] += 1
        winner_name = "Bot 2 (Join)"
    else:
        s1, s2 = 0.5, 0.5
        stats["draws"] += 1
        winner_name = "Empate"
        
    new_r1 = round(r1 + k * (s1 - e1))
    new_r2 = round(r2 + k * (s2 - e2))
    
    stats["bot1_elo"] = new_r1
    stats["bot2_elo"] = new_r2
    
    # Update Deck stats
    for d_name, won in [(p1_deck, winner_id == 1), (p2_deck, winner_id == 2)]:
        if d_name not in stats["deck_stats"]:
            stats["deck_stats"][d_name] = {"matches": 0, "wins": 0}
        stats["deck_stats"][d_name]["matches"] += 1
        if won:
            stats["deck_stats"][d_name]["wins"] += 1

    stats["elo_history"].append({
        "match": stats["total_matches"],
        "bot1_elo": new_r1,
        "bot2_elo": new_r2,
        "timestamp": time.time()
    })
    
    match_entry = {
        "room": room_id,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "winner": winner_name,
        "p1_deck": p1_deck,
        "p2_deck": p2_deck,
        "p1_health": p1_health,
        "p2_health": p2_health,
        "turns": total_turns
    }
    stats["recent_matches"].insert(0, match_entry)
    stats["recent_matches"] = stats["recent_matches"][:30]
    
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)
    return stats

def reset_stats():
    if os.path.exists(STATS_FILE):
        os.remove(STATS_FILE)
    return get_stats_data()
