"""
stats/storage.py
================
Persistência e gerenciamento de estatísticas com exclusão mútua estrita (file_lock)
e salvamento atômico seguro (atomic_json_save).
"""

import json
import os
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from ai.atomic_io import atomic_json_save, file_lock
from ai.logger import get_logger
from stats.deck_names import (
    DECKS_DIR,
    canonicalize_deck_name,
    consolidate_deck_stats,
    get_expected_starting_health,
)
from stats.elo import calculate_elo_ratings, calculate_k_factor

logger = get_logger("stats_manager")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS_FILE = "data/training_stats.json"
DEFAULT_STATS_FILE = "data/training_stats.json"

_thread_local = threading.local()


@contextmanager
def stats_file_lock(filepath: str):
    """
    Context manager de file_lock reentrante para o mesmo thread/processo.
    Evita deadlocks de fcntl.flock quando rotinas encadeadas (ex: update_match_result ->
    sync_multipliers_with_stats -> get_stats_data) tentam reobter o lock sobre o mesmo arquivo.
    """
    if not hasattr(_thread_local, "active_locks"):
        _thread_local.active_locks = set()

    abs_path = os.path.abspath(filepath)
    if abs_path in _thread_local.active_locks:
        yield
    else:
        _thread_local.active_locks.add(abs_path)
        try:
            with file_lock(filepath):
                yield
        finally:
            _thread_local.active_locks.discard(abs_path)


def _resolve_stats_file(file_path: Optional[str] = None) -> str:
    """Resolve dinamicamente o caminho do arquivo de estatísticas considerando monkeypatches e overrides."""
    if file_path:
        return file_path
    curr_storage_file = globals().get("STATS_FILE", DEFAULT_STATS_FILE)
    if curr_storage_file != DEFAULT_STATS_FILE:
        return curr_storage_file
    sm = sys.modules.get("stats_manager")
    if sm is not None and hasattr(sm, "STATS_FILE") and sm.STATS_FILE != DEFAULT_STATS_FILE:
        return sm.STATS_FILE
    st = sys.modules.get("stats")
    if st is not None and hasattr(st, "STATS_FILE") and st.STATS_FILE != DEFAULT_STATS_FILE:
        return st.STATS_FILE
    return curr_storage_file


def _get_stats_data_unlocked(target_file: str) -> dict:
    """Lê e inicializa o arquivo de dados."""
    dir_name = os.path.dirname(target_file) or "data"
    os.makedirs(dir_name, exist_ok=True)
    if not os.path.exists(target_file):
        default_data = {
            "total_matches": 0,
            "bot1_wins": 0,
            "bot2_wins": 0,
            "draws": 0,
            "bot1_elo": 1200,
            "bot2_elo": 1200,
            "elo_history": [{"match": 0, "bot1_elo": 1200, "bot2_elo": 1200, "timestamp": time.time()}],
            "deck_stats": {},
            "recent_matches": [],
        }
        atomic_json_save(default_data, target_file)
        return default_data
    try:
        with open(target_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        modified_any = False
        # Consolida decks duplicados se existirem
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
                atomic_json_save(data, target_file)
            except Exception as e:
                logger.warning(f"Erro ao salvar stats consolidado: {e}")
        return data
    except Exception as e:
        logger.warning(f"Erro lendo STATS_FILE ({target_file}): {e}")
        return {
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


def get_stats_data(stats_file: Optional[str] = None) -> dict:
    """Lê os dados de estatísticas protegendo contra concorrência com file_lock."""
    target_file = _resolve_stats_file(stats_file)
    with stats_file_lock(target_file):
        return _get_stats_data_unlocked(target_file)


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
    """Registra resultado de partida com exclusão mútua estrita (file_lock) para evitar perda de dados em concorrência."""
    target_file = _resolve_stats_file(stats_file)
    with stats_file_lock(target_file):
        return _update_match_result_unlocked(
            room_id=room_id,
            p1_deck=p1_deck,
            p2_deck=p2_deck,
            p1_health=p1_health,
            p2_health=p2_health,
            total_turns=total_turns,
            winner_id=winner_id,
            is_human_p1=is_human_p1,
            is_invalid_match=is_invalid_match,
            invalid_reason=invalid_reason,
            stats_file=target_file,
        )


def _update_match_result_unlocked(
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
    target_file = _resolve_stats_file(stats_file)
    stats = _get_stats_data_unlocked(target_file)

    # Bloqueio de partidas de teste automatizado na base oficial de produção
    is_test_room = any(
        prefix in str(room_id).lower()
        for prefix in ("test_", "test_room", "test_deadlock", "test_blitz", "test_human")
    )
    prod_target = os.path.abspath(os.path.join(BASE_DIR, "data", "training_stats.json"))
    is_prod_file = os.path.abspath(target_file) == prod_target
    if is_test_room and is_prod_file:
        logger.debug(f"Ignorando partida de teste '{room_id}' no arquivo de produção STATS_FILE.")
        return stats

    # Deduplicação de partidas já registradas recentemente
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
        # Caso 2: Bot travou só apanhando (Punching Bag): vencedor com vida intacta (>= vida inicial) e perdedor <= 0 em 5 a 8 turnos
        elif not is_human_p1 and winner_id == 1:
            p1_init_expected = get_expected_starting_health(p1_deck_clean)
            if p1_health >= p1_init_expected and p2_health <= 0 and (5 <= total_turns <= 8):
                is_invalid_match = True
                invalid_reason = "Bot Inerte (Punching Bag)"
        elif not is_human_p1 and winner_id == 2:
            p2_init_expected = get_expected_starting_health(p2_deck_clean)
            if p2_health >= p2_init_expected and p1_health <= 0 and (5 <= total_turns <= 8):
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
            "turns": total_turns,
        }
        stats["recent_matches"].insert(0, match_entry)
        stats["recent_matches"] = stats["recent_matches"][:30]
        atomic_json_save(stats, target_file)
        return stats

    stats["total_matches"] += 1

    # Cálculo do K-Factor dinâmico e ELO Global
    r1 = stats.get("bot1_elo", 1200)
    r2 = stats.get("bot2_elo", 1200)
    k = calculate_k_factor(
        matches_played=stats.get("total_matches", 0),
        is_human_p1=is_human_p1,
        winner_id=winner_id,
    )

    new_r1, new_r2 = calculate_elo_ratings(r1, r2, winner_id, k=k)

    if winner_id == 1:
        stats["bot1_wins"] += 1
        winner_name = f"👤 Humano ({p1_deck_clean})" if is_human_p1 else f"Bot 1 ({p1_deck_clean})"
    elif winner_id == 2:
        stats["bot2_wins"] += 1
        winner_name = f"🤖 Bot 2 ({p2_deck_clean})"
    else:
        stats["draws"] += 1
        winner_name = "Empate"

    stats["bot1_elo"] = new_r1
    stats["bot2_elo"] = new_r2

    # Inicializa estatísticas individuais dos decks
    if "deck_stats" not in stats:
        stats["deck_stats"] = {}

    for d_name in [tracked_p1, tracked_p2]:
        if d_name not in stats["deck_stats"]:
            stats["deck_stats"][d_name] = {
                "matches": 0,
                "wins": 0,
                "losses": 0,
                "elo": 1200,
                "human_matches": 0,
                "human_wins": 0,
            }

    # Cálculo do ELO Individual de Decks / Humano
    d1_elo = stats["deck_stats"][tracked_p1].get("elo", 1200)
    d2_elo = stats["deck_stats"][tracked_p2].get("elo", 1200)
    new_d1, new_d2 = calculate_elo_ratings(d1_elo, d2_elo, winner_id, k=k)

    stats["deck_stats"][tracked_p1]["elo"] = new_d1
    stats["deck_stats"][tracked_p2]["elo"] = new_d2
    stats["deck_stats"][tracked_p1]["matches"] += 1
    stats["deck_stats"][tracked_p2]["matches"] += 1

    if is_human_p1:
        stats["deck_stats"][tracked_p2]["human_matches"] = (
            stats["deck_stats"][tracked_p2].get("human_matches", 0) + 1
        )
        if winner_id == 2:
            stats["deck_stats"][tracked_p2]["human_wins"] = (
                stats["deck_stats"][tracked_p2].get("human_wins", 0) + 1
            )

    if winner_id == 1:
        stats["deck_stats"][tracked_p1]["wins"] += 1
        stats["deck_stats"][tracked_p2]["losses"] += 1
    elif winner_id == 2:
        stats["deck_stats"][tracked_p2]["wins"] += 1
        stats["deck_stats"][tracked_p1]["losses"] += 1

    if "deck_elo_history" not in stats:
        stats["deck_elo_history"] = []

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
        "timestamp": time.time(),
    })

    match_entry = {
        "room": room_id,
        "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "winner": winner_name,
        "p1_deck": f"👤 Humano ({p1_deck_clean})" if is_human_p1 else p1_deck_clean,
        "p2_deck": f"🤖 Bot ({p2_deck_clean})" if is_human_p1 else p2_deck_clean,
        "p1_health": p1_health,
        "p2_health": p2_health,
        "turns": total_turns,
    }
    stats["recent_matches"].insert(0, match_entry)
    stats["recent_matches"] = stats["recent_matches"][:30]

    atomic_json_save(stats, target_file)

    try:
        from ai.dynamic_rule_tuner import sync_multipliers_with_stats

        sync_multipliers_with_stats()
    except Exception as e:
        logger.warning(f"Erro ao sincronizar multiplicadores dinâmicos: {e}")

    return stats


def delete_deck_stat(deck_name: str, stats_file: Optional[str] = None) -> bool:
    """Remove um deck específico das estatísticas de ranking de competência sob lock."""
    target_file = _resolve_stats_file(stats_file)
    with stats_file_lock(target_file):
        stats = _get_stats_data_unlocked(target_file)
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
                atomic_json_save(stats, target_file)
                return True
        return False


def reset_stats(stats_file: Optional[str] = None) -> dict:
    """Limpa e reinicializa os dados de estatísticas com proteção de lock."""
    target_file = _resolve_stats_file(stats_file)
    with stats_file_lock(target_file):
        if os.path.exists(target_file):
            os.remove(target_file)
        return _get_stats_data_unlocked(target_file)


def reset_all_elos(stats_file: Optional[str] = None) -> dict:
    """
    Reinicializa todos os ratings de ELO para 1200 e zera as métricas de partidas,
    mantendo os decks conhecidos inicializados em 1200 para avaliar a progressão do modelo.
    """
    target_file = _resolve_stats_file(stats_file)
    with stats_file_lock(target_file):
        stats = _get_stats_data_unlocked(target_file)

        # Coleta os decks existentes para manter a estrutura e histórico limpo
        known_decks = set(stats.get("deck_stats", {}).keys())

        # Também inclui decks canônicos da pasta de baralhos se disponíveis
        if os.path.exists(DECKS_DIR):
            for fname in os.listdir(DECKS_DIR):
                if fname.endswith((".json", ".txt")):
                    base = os.path.splitext(fname)[0]
                    c_name = canonicalize_deck_name(base)
                    known_decks.add(c_name)

        reset_deck_stats = {}
        for d_name in sorted(known_decks):
            reset_deck_stats[d_name] = {
                "matches": 0,
                "wins": 0,
                "losses": 0,
                "elo": 1200,
                "human_matches": 0,
                "human_wins": 0,
            }

        now_ts = time.time()
        new_stats = {
            "total_matches": 0,
            "bot1_wins": 0,
            "bot2_wins": 0,
            "draws": 0,
            "bot1_elo": 1200,
            "bot2_elo": 1200,
            "elo_history": [
                {
                    "match": 0,
                    "bot1_elo": 1200,
                    "bot2_elo": 1200,
                    "timestamp": now_ts,
                }
            ],
            "deck_stats": reset_deck_stats,
            "deck_elo_history": [
                {
                    "match": 0,
                    **{d: 1200 for d in reset_deck_stats},
                }
            ] if reset_deck_stats else [],
            "recent_matches": [],
        }

        atomic_json_save(new_stats, target_file)

        try:
            from ai.dynamic_rule_tuner import sync_multipliers_with_stats

            sync_multipliers_with_stats()
        except Exception as e:
            logger.warning(f"Erro ao sincronizar multiplicadores dinâmicos após reset de ELO: {e}")

        return new_stats

