import os
import json
import time
from datetime import datetime
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "data", "training_stats.json")

CANONICAL_DECK_NAMES = {
    "dash_io": "Dash IO",
    "dash io": "Dash IO",
    "oscilio_giaf": "Oscilio GIAF",
    "oscilio giaf": "Oscilio GIAF",
    "gravy_bones": "Gravy Bones",
    "gravy bones": "Gravy Bones",
    "marlynn": "Marlinn",
    "marlinn": "Marlinn",
}

def canonicalize_deck_name(name: str) -> str:
    """Normaliza o nome do deck para um nome canônico legível e consistente."""
    if not name or name.strip() == "👤 Humano (Você)":
        return name
    clean = str(name).strip()
    low = clean.lower().replace("-", "_")
    if low in CANONICAL_DECK_NAMES:
        return CANONICAL_DECK_NAMES[low]
    if "_" in clean:
        clean = clean.replace("_", " ")
    return clean.title()

def consolidate_deck_stats(deck_stats: dict):
    """Compila e unifica entradas duplicadas (ex: Marlinn e marlinn, dash_io e Dash IO)."""
    consolidated = {}
    had_duplicates = False

    for d_name, d_info in deck_stats.items():
        c_name = canonicalize_deck_name(d_name)
        if c_name != d_name:
            had_duplicates = True

        matches = d_info.get("matches", 0)
        wins = d_info.get("wins", 0)
        losses = d_info.get("losses", matches - wins)
        elo = d_info.get("elo", 1200)

        if c_name not in consolidated:
            consolidated[c_name] = {
                "matches": matches,
                "wins": wins,
                "losses": losses,
                "elo": elo
            }
        else:
            had_duplicates = True
            prev = consolidated[c_name]
            tot_matches = prev["matches"] + matches
            tot_wins = prev["wins"] + wins
            tot_losses = prev["losses"] + losses
            
            # ELO ponderado pelo número de partidas disputadas
            if tot_matches > 0:
                weighted_elo = round((prev["elo"] * prev["matches"] + elo * matches) / tot_matches)
            else:
                weighted_elo = prev["elo"]
                
            consolidated[c_name] = {
                "matches": tot_matches,
                "wins": tot_wins,
                "losses": tot_losses,
                "elo": weighted_elo
            }

    return consolidated, had_duplicates

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
            data = json.load(f)
            # Consolida decks duplicados se existirem
            if "deck_stats" in data:
                consolidated, modified = consolidate_deck_stats(data["deck_stats"])
                if modified:
                    data["deck_stats"] = consolidated
                    try:
                        with open(STATS_FILE, "w") as fw:
                            json.dump(data, fw, indent=2)
                    except Exception:
                        pass
            return data
    except Exception:
        return {
            "total_matches": 0, "bot1_wins": 0, "bot2_wins": 0, "draws": 0,
            "bot1_elo": 1200, "bot2_elo": 1200, "elo_history": [], "deck_stats": {}, "recent_matches": []
        }

def update_match_result(room_id, p1_deck, p2_deck, p1_health, p2_health, total_turns, winner_id, is_human_p1=False):
    stats = get_stats_data()
    stats["total_matches"] += 1
    
    p1_deck_clean = canonicalize_deck_name(p1_deck)
    p2_deck_clean = canonicalize_deck_name(p2_deck)
    tracked_p1 = "👤 Humano (Você)" if is_human_p1 else p1_deck_clean
    tracked_p2 = p2_deck_clean

    # Calculate Global Elo
    r1 = stats.get("bot1_elo", 1200)
    r2 = stats.get("bot2_elo", 1200)
    k = 32
    
    e1 = 1 / (1 + 10 ** ((r2 - r1) / 400))
    e2 = 1 / (1 + 10 ** ((r1 - r2) / 400))
    
    if winner_id == 1:
        s1, s2 = 1.0, 0.0
        stats["bot1_wins"] += 1
        winner_name = f"👤 Humano ({p1_deck_clean})" if is_human_p1 else f"Bot 1 ({p1_deck_clean})"
    elif winner_id == 2:
        s1, s2 = 0.0, 1.0
        stats["bot2_wins"] += 1
        winner_name = f"🤖 Bot 2 ({p2_deck_clean})"
    else:
        s1, s2 = 0.5, 0.5
        stats["draws"] += 1
        winner_name = "Empate"
        
    new_r1 = round(r1 + k * (s1 - e1))
    new_r2 = round(r2 + k * (s2 - e2))
    stats["bot1_elo"] = new_r1
    stats["bot2_elo"] = new_r2
    
    # Initialize Deck Stats if missing
    if "deck_stats" not in stats:
        stats["deck_stats"] = {}
        
    for d_name in [tracked_p1, tracked_p2]:
        if d_name not in stats["deck_stats"]:
            stats["deck_stats"][d_name] = {"matches": 0, "wins": 0, "losses": 0, "elo": 1200}

    # Calculate Individual Deck / Human ELO
    d1_elo = stats["deck_stats"][tracked_p1].get("elo", 1200)
    d2_elo = stats["deck_stats"][tracked_p2].get("elo", 1200)
    ed1 = 1 / (1 + 10 ** ((d2_elo - d1_elo) / 400))
    ed2 = 1 / (1 + 10 ** ((d1_elo - d2_elo) / 400))
    
    stats["deck_stats"][tracked_p1]["elo"] = round(d1_elo + k * (s1 - ed1))
    stats["deck_stats"][tracked_p2]["elo"] = round(d2_elo + k * (s2 - ed2))
    stats["deck_stats"][tracked_p1]["matches"] += 1
    stats["deck_stats"][tracked_p2]["matches"] += 1

    if winner_id == 1:
        stats["deck_stats"][tracked_p1]["wins"] += 1
        stats["deck_stats"][tracked_p2]["losses"] += 1
    elif winner_id == 2:
        stats["deck_stats"][tracked_p2]["wins"] += 1
        stats["deck_stats"][tracked_p1]["losses"] += 1

    if "deck_elo_history" not in stats:
        stats["deck_elo_history"] = []

    # Registrar snapshot do ELO de todos os decks e do Humano
    deck_snapshot = {"match": stats["total_matches"]}
    for d_k, d_v in stats["deck_stats"].items():
        deck_snapshot[d_k] = d_v.get("elo", 1200)
    stats["deck_elo_history"].append(deck_snapshot)
    if len(stats["deck_elo_history"]) > 500:
        stats["deck_elo_history"] = stats["deck_elo_history"][-500:]

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
        "p1_deck": f"👤 Humano ({p1_deck_clean})" if is_human_p1 else p1_deck_clean,
        "p2_deck": f"🤖 Bot ({p2_deck_clean})" if is_human_p1 else p2_deck_clean,
        "p1_health": p1_health,
        "p2_health": p2_health,
        "turns": total_turns
    }
    stats["recent_matches"].insert(0, match_entry)
    stats["recent_matches"] = stats["recent_matches"][:30]
    
    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)
    return stats

def delete_deck_stat(deck_name: str):
    """Remove um deck específico das estatísticas de ranking de competência."""
    stats = get_stats_data()
    c_name = canonicalize_deck_name(deck_name)
    deleted = False
    if "deck_stats" in stats:
        for k in list(stats["deck_stats"].keys()):
            if k == deck_name or k == c_name or canonicalize_deck_name(k) == c_name:
                del stats["deck_stats"][k]
                deleted = True
        if "deck_elo_history" in stats:
            for snap in stats["deck_elo_history"]:
                snap.pop(deck_name, None)
                snap.pop(c_name, None)
        if deleted:
            with open(STATS_FILE, "w") as f:
                json.dump(stats, f, indent=2)
            return True
    return False

def reset_stats():
    if os.path.exists(STATS_FILE):
        os.remove(STATS_FILE)
    return get_stats_data()

def sync_training_matches(target_total_matches: int = None):
    """
    Sincroniza o volume de partidas de training_stats.json com o total_games de training_metrics.json,
    escalando proporcionalmente o número de partidas disputadas por deck e mantendo os ratings ELO e Win Rates intactos.
    """
    if target_total_matches is None:
        metrics_file = os.path.join(BASE_DIR, "data", "training_metrics.json")
        if os.path.exists(metrics_file):
            try:
                with open(metrics_file, "r") as f:
                    target_total_matches = json.load(f).get("total_games", 0)
            except Exception:
                target_total_matches = 0

    if not target_total_matches or target_total_matches <= 0:
        return False

    stats = get_stats_data()
    current_m = stats.get("total_matches", 0)
    if current_m <= 0:
        stats["total_matches"] = target_total_matches
        with open(STATS_FILE, "w") as f:
            json.dump(stats, f, indent=2)
        return True

    if current_m == target_total_matches:
        return True

    scale = target_total_matches / current_m
    stats["total_matches"] = target_total_matches
    stats["bot1_wins"] = round(stats.get("bot1_wins", 0) * scale)
    stats["bot2_wins"] = round(stats.get("bot2_wins", 0) * scale)

    if "deck_stats" in stats:
        for d_k, d_v in stats["deck_stats"].items():
            m = d_v.get("matches", 0)
            w = d_v.get("wins", 0)
            scaled_m = round(m * scale)
            scaled_w = round(w * scale)
            d_v["matches"] = scaled_m
            d_v["wins"] = scaled_w
            d_v["losses"] = max(0, scaled_m - scaled_w)

    with open(STATS_FILE, "w") as f:
        json.dump(stats, f, indent=2)
    return True
