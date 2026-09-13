import os
import glob
import json
import time
from datetime import datetime
from ai.atomic_io import atomic_json_save
from ai.logger import get_logger

logger = get_logger("stats_manager")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATS_FILE = os.path.join(BASE_DIR, "data", "training_stats.json")
DECKS_DIR = os.path.join(BASE_DIR, "decks")

CANONICAL_DECK_NAMES = {
    # Dash IO
    "dash_io": "Dash IO",
    "dash io": "Dash IO",
    "dash_i/o": "Dash IO",
    "dash i/o": "Dash IO",
    # Oscilio GIAF
    "oscilio_giaf": "Oscilio GIAF",
    "oscilio giaf": "Oscilio GIAF",
    "oscilio_constella_intelligence": "Oscilio GIAF",
    "oscilio constella intelligence": "Oscilio GIAF",
    # Gravy Bones
    "gravy_bones": "Gravy Bones",
    "gravy bones": "Gravy Bones",
    "gravy_bones_shipwrecked_looter": "Gravy Bones",
    "gravy bones shipwrecked looter": "Gravy Bones",
    # Marlinn
    "marlynn": "Marlinn",
    "marlinn": "Marlinn",
    "marlynn_treasure_hunter": "Marlinn",
    "marlynn treasure hunter": "Marlinn",
    "marlinn_treasure_hunter": "Marlinn",
    "marlinn treasure hunter": "Marlinn",
    # Teklovossen
    "teklovossen": "Teklovossen",
    "teklovossen_esteemed_magnate": "Teklovossen",
    "teklovossen esteemed magnate": "Teklovossen",
    "professor_teklovossen": "Teklovossen",
    "professor teklovossen": "Teklovossen",
    # Betsy
    "betsy": "Betsy",
    "betsy_skin_in_the_game": "Betsy",
    "betsy skin in the game": "Betsy",
    # Kassai
    "kassai": "Kassai",
    "kassai_of_the_golden_sand": "Kassai",
    "kassai of the golden sand": "Kassai",
    # Cindra
    "cindra": "Cindra",
    "cindra_dracai_of_retribution": "Cindra",
    "cindra dracai of retribution": "Cindra",
    # Jarl
    "jarl": "Jarl",
    "jarl_vetreidi": "Jarl",
    "jarl vetreidi": "Jarl",
    "jarl_vetreiði": "Jarl",
    "jarl vetreiði": "Jarl",
    # Vynsett
    "vynsett": "Vynsett",
    "vynnset": "Vynsett",
    "vynnset_iron_maiden": "Vynsett",
    "vynnset iron maiden": "Vynsett",
    # Mario (Arakni)
    "mario": "Mario",
    "arakni_marionette": "Mario",
    "arakni marionette": "Mario",
    # Hala
    "hala": "Hala",
    "hala_bladesaint_of_the_vow": "Hala",
    "hala bladesaint of the vow": "Hala",
}

def canonicalize_deck_name(name: str) -> str:
    """Normaliza o nome do deck para um nome canônico legível e consistente."""
    if not name or name.strip() == "👤 Humano (Você)":
        return name
    clean = str(name).strip()
    low = clean.lower().replace("-", "_").replace(",", "")
    while "  " in low:
        low = low.replace("  ", " ")
    if low in CANONICAL_DECK_NAMES:
        return CANONICAL_DECK_NAMES[low]
    # Fallback dinâmico: verificar decks salvos no workspace
    try:
        from deck_parser import list_saved_decks
        for d in list_saved_decks():
            d_name = d.get("name", "")
            d_slug = d.get("slug", "").lower()
            d_hero = d.get("hero", "").lower().replace("-", "_").replace(",", "")
            if low in (d_slug, d_name.lower(), d_hero):
                return d_name
    except Exception:
        pass
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

def get_expected_starting_health(deck_name: str) -> int:
    """Retorna o total de vida inicial esperado para o deck (40 para CC, 20 para Blitz)."""
    clean = canonicalize_deck_name(deck_name).lower()
    for d_path in glob.glob(os.path.join(DECKS_DIR, "*.json")):
        try:
            with open(d_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            name = (d.get("name") or "").lower()
            hero = (d.get("hero") or "").lower()
            if clean in name or clean in hero or name in clean or hero in clean:
                fmt = str(d.get("format", "")).lower()
                if "blitz" in fmt:
                    return 20
                if "cc" in fmt or "classic" in fmt:
                    return 40
        except Exception:
            pass
    return 40

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
        atomic_json_save(default_data, STATS_FILE)
        return default_data
    try:
        with open(STATS_FILE, "r") as f:
            data = json.load(f)
            # Consolida decks duplicados se existirem
            modified_any = False
            if "deck_stats" in data:
                consolidated, modified = consolidate_deck_stats(data["deck_stats"])
                if modified:
                    data["deck_stats"] = consolidated
                    modified_any = True
            # Também consolidar recent_matches se contiver nomes legados de heróis
            if "recent_matches" in data:
                for m in data["recent_matches"]:
                    p1_d = m.get("p1_deck", "")
                    p2_d = m.get("p2_deck", "")
                    c1 = canonicalize_deck_name(p1_d)
                    c2 = canonicalize_deck_name(p2_d)
                    if c1 != p1_d:
                        m["p1_deck"] = c1
                        modified_any = True
                    if c2 != p2_d:
                        m["p2_deck"] = c2
                        modified_any = True
            if modified_any:
                try:
                    atomic_json_save(data, STATS_FILE)
                except Exception as e:
                    logger.warning(f"Erro ao salvar stats consolidado: {e}")
            return data
    except Exception as e:
        logger.warning(f"Erro lendo STATS_FILE: {e}")
        return {
            "total_matches": 0, "bot1_wins": 0, "bot2_wins": 0, "draws": 0,
            "bot1_elo": 1200, "bot2_elo": 1200, "elo_history": [], "deck_stats": {}, "recent_matches": []
        }

def update_match_result(room_id, p1_deck, p2_deck, p1_health, p2_health, total_turns, winner_id, is_human_p1=False, is_invalid_match=False, invalid_reason=""):
    stats = get_stats_data()
    
    # Bloqueio de partidas de teste automatizado na base oficial de produção
    is_test_room = any(prefix in str(room_id).lower() for prefix in ("test_", "test_room", "test_deadlock", "test_blitz", "test_human"))
    is_prod_file = os.path.abspath(STATS_FILE) == os.path.abspath(os.path.join(BASE_DIR, "data", "training_stats.json"))
    if is_test_room and is_prod_file:
        logger.debug(f"Ignorando partida de teste '{room_id}' no arquivo de produção STATS_FILE.")
        return stats

    # Deduplicação de partidas já registradas recentemente (evita contagem dupla entre bot_client e trainer)
    if not is_test_room and "recent_matches" in stats:
        for rm in stats["recent_matches"]:
            if rm.get("room") == room_id:
                logger.debug(f"Partida '{room_id}' já registrada previamente. Ignorando duplicata.")
                return stats

    p1_deck_clean = canonicalize_deck_name(p1_deck)
    p2_deck_clean = canonicalize_deck_name(p2_deck)
    tracked_p1 = "👤 Humano (Você)" if is_human_p1 else p1_deck_clean
    tracked_p2 = p2_deck_clean

    # Verificação de segurança adicional para anulação automática caso não tenha sido sinalizada
    if not is_invalid_match:
        # Caso 1: Empate com 0 dano ou vida quase intacta (<= 3 dano total trocado)
        if winner_id == 0 and (
            (p1_health >= 18 and p2_health >= 18) or
            (p1_health >= 38 and p2_health >= 38)
        ):
            is_invalid_match = True
            invalid_reason = "Empate 0 Dano (Mutual Stall)"
        # Caso 2: Bot travou só apanhando (Punching Bag): vencedor com vida intacta (>= vida inicial) e perdedor <= 0 em >= 6 turnos
        elif winner_id == 1:
            p1_init_expected = get_expected_starting_health(p1_deck_clean)
            if p1_health >= p1_init_expected and p2_health <= 0 and total_turns >= 6:
                is_invalid_match = True
                invalid_reason = "Bot Inerte (Punching Bag)"
        elif winner_id == 2:
            p2_init_expected = get_expected_starting_health(p2_deck_clean)
            if p2_health >= p2_init_expected and p1_health <= 0 and total_turns >= 6:
                is_invalid_match = True
                invalid_reason = "Bot Inerte (Punching Bag)"

    if is_invalid_match:
        logger.warning(
            f"⚠️ [PARTIDA ANULADA] {room_id} descartada ({invalid_reason}). "
            f"Sem impacto no ELO, histórico de vitórias ou contagem de partidas."
        )
        match_entry = {
            "room": room_id,
            "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "winner": f"Anulada ({invalid_reason or 'Travamento'})",
            "p1_deck": f"👤 Humano ({p1_deck_clean})" if is_human_p1 else p1_deck_clean,
            "p2_deck": f"🤖 Bot ({p2_deck_clean})" if is_human_p1 else p2_deck_clean,
            "p1_health": p1_health,
            "p2_health": p2_health,
            "turns": total_turns
        }
        stats["recent_matches"].insert(0, match_entry)
        stats["recent_matches"] = stats["recent_matches"][:30]
        atomic_json_save(stats, STATS_FILE)
        return stats

    stats["total_matches"] += 1

    # Calculate Global Elo
    r1 = stats.get("bot1_elo", 1200)
    r2 = stats.get("bot2_elo", 1200)
    # Recompensa acelerada de ELO (K=48) quando o bot vence um jogador humano
    k = 48 if (is_human_p1 and winner_id == 2) else 32
    
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
            stats["deck_stats"][d_name] = {"matches": 0, "wins": 0, "losses": 0, "elo": 1200, "human_matches": 0, "human_wins": 0}

    # Calculate Individual Deck / Human ELO
    d1_elo = stats["deck_stats"][tracked_p1].get("elo", 1200)
    d2_elo = stats["deck_stats"][tracked_p2].get("elo", 1200)
    ed1 = 1 / (1 + 10 ** ((d2_elo - d1_elo) / 400))
    ed2 = 1 / (1 + 10 ** ((d1_elo - d2_elo) / 400))
    
    stats["deck_stats"][tracked_p1]["elo"] = round(d1_elo + k * (s1 - ed1))
    stats["deck_stats"][tracked_p2]["elo"] = round(d2_elo + k * (s2 - ed2))
    stats["deck_stats"][tracked_p1]["matches"] += 1
    stats["deck_stats"][tracked_p2]["matches"] += 1

    if is_human_p1:
        stats["deck_stats"][tracked_p2]["human_matches"] = stats["deck_stats"][tracked_p2].get("human_matches", 0) + 1
        if winner_id == 2:
            stats["deck_stats"][tracked_p2]["human_wins"] = stats["deck_stats"][tracked_p2].get("human_wins", 0) + 1

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
    
    atomic_json_save(stats, STATS_FILE)

    # Auto-Tuning Dinâmico dos Multiplicadores de Regras por Herói com base nos resultados
    try:
        from ai.dynamic_rule_tuner import sync_multipliers_with_stats
        sync_multipliers_with_stats()
    except Exception as e:
        logger.warning(f"Erro ao sincronizar multiplicadores dinâmicos: {e}")

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
            atomic_json_save(stats, STATS_FILE)
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

def clean_stalled_matches(stats_file: str = None) -> dict:
    """
    Expurga partidas de empate sem dano e bots inertes acumulados historicamente em training_stats.json.
    Corrige contadores de partidas, vitórias, derrotas e empates, normalizando as taxas de vitória reais dos heróis.
    """
    target_file = stats_file or STATS_FILE
    if not os.path.exists(target_file):
        return {}

    with open(target_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Backup de segurança antes da higienização
    backup_file = target_file + ".bak"
    try:
        atomic_json_save(data, backup_file)
        logger.info(f"Backup de segurança salvo em: {backup_file}")
    except Exception as e:
        logger.warning(f"Não foi possível salvar backup: {e}")

    # 1. Higienização de recent_matches (remover testes, normalizar decks e marcar empates/inertes)
    cleaned_recent = []
    seen_rooms = set()
    for m in data.get("recent_matches", []):
        r_id = str(m.get("room", "")).lower()
        if "test" in r_id or "deadlock" in r_id:
            continue
        if r_id in seen_rooms:
            continue
        seen_rooms.add(r_id)

        m["p1_deck"] = canonicalize_deck_name(m.get("p1_deck", ""))
        m["p2_deck"] = canonicalize_deck_name(m.get("p2_deck", ""))

        p1_h = m.get("p1_health", 0)
        p2_h = m.get("p2_health", 0)
        t = m.get("turns", 0)
        w = m.get("winner", "")
        p1_init = get_expected_starting_health(m["p1_deck"])
        p2_init = get_expected_starting_health(m["p2_deck"])
        is_zero_dmg_draw = w == "Empate" and (
            (p1_h >= 18 and p2_h >= 18) or
            (p1_h >= 38 and p2_h >= 38) or
            (p1_h >= (p1_init - 2) and p2_h >= (p2_init - 2))
        )
        if is_zero_dmg_draw:
            m["winner"] = "Anulada (Empate 0 Dano)"
        elif (p1_h >= p1_init and p2_h <= 0 and t >= 6) or (p2_h >= p2_init and p1_h <= 0 and t >= 6):
            if "Anulada" not in w:
                m["winner"] = "Anulada (Bot Inerte / Travado)"
        cleaned_recent.append(m)
    data["recent_matches"] = cleaned_recent

    # 2. Consolidação e higienização de deck_stats
    total_cleaned_draws = 0
    raw_deck_stats = data.get("deck_stats", {})
    consolidated_decks, _ = consolidate_deck_stats(raw_deck_stats)
    deck_stats = consolidated_decks
    for deck_name, d_info in deck_stats.items():
        wins = d_info.get("wins", 0)
        losses = d_info.get("losses", 0)
        matches = d_info.get("matches", 0)
        legit_matches = wins + losses
        if matches > legit_matches:
            stalled_draws = matches - legit_matches
            total_cleaned_draws += stalled_draws
            d_info["matches"] = legit_matches

    # Remove decks residuais de teste com 0 partidas
    for d_k in list(deck_stats.keys()):
        if deck_stats[d_k].get("matches", 0) == 0:
            del deck_stats[d_k]
    data["deck_stats"] = deck_stats

    # 3. Atualizar totais globais
    old_draws = data.get("draws", 0)
    data["draws"] = max(0, old_draws - (total_cleaned_draws // 2))
    data["total_matches"] = data.get("bot1_wins", 0) + data.get("bot2_wins", 0) + data.get("draws", 0)

    atomic_json_save(data, target_file)
    logger.info(f"Higienização concluída: {total_cleaned_draws} slots de empate/travamento expurgados de {len(deck_stats)} decks.")
    return data

