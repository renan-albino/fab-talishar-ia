"""
stats/sync.py
=============
Rotinas de sincronização de métricas e higienização de partidas estagnadas / travadas.
"""

import json
import os
from typing import Optional, Union

from ai.atomic_io import atomic_json_save
from ai.logger import get_logger
from stats.deck_names import (
    canonicalize_deck_name,
    consolidate_deck_stats,
    get_expected_starting_health,
)
from stats.storage import (
    BASE_DIR,
    STATS_FILE,
    _get_stats_data_unlocked,
    _resolve_stats_file,
    stats_file_lock,
)

logger = get_logger("stats_sync")


def sync_training_matches(
    target_total_matches: Optional[int] = None,
    stats_file: Optional[str] = None,
) -> bool:
    """
    Sincroniza o volume de partidas de training_stats.json com o total_games de training_metrics.json,
    escalando proporcionalmente o número de partidas disputadas por deck e mantendo os ratings ELO e Win Rates intactos.
    """
    target_file = _resolve_stats_file(stats_file)
    if target_total_matches is None:
        metrics_file = os.path.join(BASE_DIR, "data", "training_metrics.json")
        if os.path.exists(metrics_file):
            try:
                with open(metrics_file, "r", encoding="utf-8") as f:
                    target_total_matches = json.load(f).get("total_games", 0)
            except Exception:
                target_total_matches = 0

    if not target_total_matches or target_total_matches <= 0:
        return False

    with stats_file_lock(target_file):
        stats = _get_stats_data_unlocked(target_file)
        current_m = stats.get("total_matches", 0)
        if current_m <= 0:
            stats["total_matches"] = target_total_matches
            atomic_json_save(stats, target_file)
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

        atomic_json_save(stats, target_file)
        return True


def clean_stalled_matches(
    stats_file: Optional[Union[str, int]] = None,
    max_age_seconds: int = 1800,
) -> dict:
    """
    Expurga partidas de empate sem dano e bots inertes acumulados historicamente em training_stats.json.
    Corrige contadores de partidas, vitórias, derrotas e empates, normalizando as taxas de vitória reais dos heróis.
    """
    if isinstance(stats_file, (int, float)):
        max_age_seconds = int(stats_file)
        stats_file = None

    target_file = _resolve_stats_file(stats_file)
    if not os.path.exists(target_file):
        return {}

    with stats_file_lock(target_file):
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
                (p1_h >= 18 and p2_h >= 18)
                or (p1_h >= 38 and p2_h >= 38)
                or (p1_h >= (p1_init - 2) and p2_h >= (p2_init - 2))
            )
            if is_zero_dmg_draw:
                m["winner"] = "Anulada (Empate 0 Dano)"
            elif (p1_h >= p1_init and p2_h <= 0 and 5 <= t <= 8) or (
                p2_h >= p2_init and p1_h <= 0 and 5 <= t <= 8
            ):
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
        data["total_matches"] = (
            data.get("bot1_wins", 0) + data.get("bot2_wins", 0) + data.get("draws", 0)
        )

        atomic_json_save(data, target_file)
        logger.info(
            f"Higienização concluída: {total_cleaned_draws} slots de empate/travamento expurgados de {len(deck_stats)} decks."
        )
        return data
