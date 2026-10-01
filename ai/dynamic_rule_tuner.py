"""
ai/dynamic_rule_tuner.py
========================
Auto-Tuning Dinâmico de Multiplicadores Heurísticos por Herói e Arquétipo.

Ajusta dinamicamente os pesos de tomada de decisão (ataque, bloqueio, pivot e arsenal)
com base nas taxas de vitória empíricas registradas pelo stats_manager.py.
"""

import os
import time
from typing import Dict, Any, Tuple
from stats.db import get_connection

DEFAULT_MULTIPLIERS = {
    "attack_weight": 1.0,
    "block_weight": 1.0,
    "pivot_bonus": 1.0,
    "arsenal_bonus": 1.0,
    "absorb_tempo_bonus": 1.0,
}

def is_aggro_or_combo_hero(name: str) -> bool:
    """Retorna True se o herói pertence a uma classe aggro/combo ou possui arquétipo focado em ofensiva/setup."""
    try:
        from ai.policy.constants import _load_cards_db
        db = _load_cards_db()
    except Exception:
        db = {}
    slug = str(name).lower().strip().replace(" ", "_").replace("-", "_")
    # Heróis específicos de combo / setup / sinergia ofensiva que nunca devem ser forçados a bloqueio passivo
    known_combo_slugs = {
        "marlinn", "marlynn", "teklovossen", "boltyn", "levia", "rhinar", "kayo",
        "chane", "briar", "viserai", "katsu", "fai", "dash", "dash_io", "maxx",
        "prism", "dromai", "cindra", "arakni", "nuu", "enigma", "zen"
    }
    if any(k in slug for k in known_combo_slugs):
        return True

    hero_data = db.get(slug) or db.get(slug.split("_")[0], {})
    hero_class = str(hero_data.get("class", "")).lower()
    aggro_classes = {"ninja", "mechanologist", "runeblade", "ranger", "wizard", "illusionist", "brute", "assassin"}
    return hero_class in aggro_classes


def load_multipliers() -> Dict[str, Dict[str, float]]:
    """Carrega o mapa de multiplicadores a partir do SQLite."""
    res = {}
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dynamic_rules")
        for row in cursor.fetchall():
            res[row["hero_name"]] = {
                "attack_weight": row["attack_weight"],
                "block_weight": row["block_weight"],
                "pivot_bonus": row["pivot_bonus"],
                "arsenal_bonus": row["arsenal_bonus"],
                "absorb_tempo_bonus": row["absorb_tempo_bonus"],
                "last_win_rate": row["last_win_rate"],
                "human_wins": row["human_wins"],
                "matches_evaluated": row["matches_evaluated"],
                "updated_at": row["updated_at"],
            }
    return res


def get_multipliers_for_hero(hero_name: str) -> Dict[str, float]:
    """
    Retorna os multiplicadores calibrados para o herói ou arquétipo especificado.
    Se não houver calibração prévia, retorna os valores padrão (1.0).
    """
    if not hero_name:
        return dict(DEFAULT_MULTIPLIERS)

    h_clean = str(hero_name).lower().strip().replace(" ", "_")
    root = h_clean.split("_")[0]

    all_mults = load_multipliers()
    # 1. Correspondência exata do herói (ex: 'jarl_vetreidi' ou 'bravo_showstopper')
    if h_clean in all_mults:
        return {**DEFAULT_MULTIPLIERS, **all_mults[h_clean]}
    # 2. Correspondência por raiz (ex: 'jarl' ou 'bravo')
    if root in all_mults:
        return {**DEFAULT_MULTIPLIERS, **all_mults[root]}

    return dict(DEFAULT_MULTIPLIERS)


MAX_DEVIATION = 0.15
MIN_WEIGHT = 1.0 - MAX_DEVIATION  # 0.85
MAX_WEIGHT = 1.0 + MAX_DEVIATION  # 1.15

STEP_NORMAL = 0.02
STEP_SUBTLE = 0.015
DECAY_RATE = 0.96


def _fetch_deck_match_metrics(deck_name: str) -> Dict[str, Any]:
    """Extrai médias reais da tabela match_history para o deck especificado."""
    try:
        from stats.deck_names import canonicalize_deck_name
        clean_name = canonicalize_deck_name(deck_name)
    except Exception:
        clean_name = deck_name

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            query = """
                SELECT 
                    turns,
                    CASE WHEN p1_deck = ? COLLATE NOCASE OR p1_deck = ? COLLATE NOCASE THEN p1_health ELSE p2_health END as my_hp,
                    CASE WHEN p1_deck = ? COLLATE NOCASE OR p1_deck = ? COLLATE NOCASE THEN p2_health ELSE p1_health END as opp_hp,
                    CASE WHEN ((p1_deck = ? COLLATE NOCASE OR p1_deck = ? COLLATE NOCASE) AND (winner LIKE '%Bot 1%' OR winner LIKE '%Humano%')) OR 
                              ((p2_deck = ? COLLATE NOCASE OR p2_deck = ? COLLATE NOCASE) AND winner LIKE '%Bot 2%') THEN 1 ELSE 0 END as won
                FROM match_history
                WHERE (p1_deck = ? COLLATE NOCASE OR p1_deck = ? COLLATE NOCASE OR 
                       p2_deck = ? COLLATE NOCASE OR p2_deck = ? COLLATE NOCASE)
                  AND winner NOT LIKE 'Anulada%'
                ORDER BY id DESC LIMIT 50
            """
            cursor.execute(query, (
                deck_name, clean_name,
                deck_name, clean_name,
                deck_name, clean_name,
                deck_name, clean_name,
                deck_name, clean_name,
                deck_name, clean_name,
            ))
            rows = cursor.fetchall()
            if not rows:
                return {}

            total = len(rows)
            avg_turns = sum(float(r[0] or 0) for r in rows) / total
            avg_my_hp = sum(float(r[1] or 0) for r in rows) / total
            avg_opp_hp = sum(float(r[2] or 0) for r in rows) / total
            wins = sum(int(r[3] or 0) for r in rows)

            return {
                "matches": total,
                "win_rate": wins / total,
                "avg_turns": avg_turns,
                "avg_my_hp": avg_my_hp,
                "avg_opp_hp": avg_opp_hp,
            }
    except Exception:
        return {}


def diagnose_deck_losses(metrics: Dict[str, Any], hero_name: str) -> str:
    """Diagnóstico causal de Flesh and Blood com normalização por formato."""
    avg_turns = float(metrics.get("avg_turns", 10.0))
    avg_opp_hp = float(metrics.get("avg_opp_hp", 20.0))

    try:
        from stats.deck_names import get_expected_starting_health
        start_hp = float(get_expected_starting_health(hero_name))
    except Exception:
        is_young = "young" in str(hero_name).lower()
        start_hp = 20.0 if is_young else 40.0

    is_blitz = start_hp <= 20.0
    expected_turns = 6.0 if is_blitz else 14.0
    expected_dps = 3.2 if is_blitz else 2.5

    dps_bot = max(0.0, start_hp - avg_opp_hp) / max(1.0, avg_turns)

    # 1. Corrida de Tempo Apertada: oponente sobreviveu com <= 15% de HP
    if avg_opp_hp <= (start_hp * 0.15):
        return "tempo_race"

    # 2. Overblocking Passivo: muitos turnos e DPS do bot muito baixo
    if avg_turns > (expected_turns * 1.3) and dps_bot < (expected_dps * 0.75):
        return "overblocking"

    # 3. Baixa Conversão de Mão: em turnos normais, não conseguiu tirar vida suficiente
    if dps_bot < (expected_dps * 0.65):
        return "low_hand_conversion"

    # 4. Vazamento Rápido em Breakpoints: jogo acabou muito rápido
    if avg_turns < (expected_turns * 0.7):
        return "fast_bleed"

    return "generic_loss"


def apply_causal_tuning(multipliers: Dict[str, float], cause: str, human_wins: int = 0) -> Dict[str, float]:
    """Aplica ajustes específicos para a causa diagnosticada com clamp rígido anti-espiral [0.85, 1.15]."""
    m = dict(multipliers)

    if cause == "overblocking":
        m["block_weight"] = max(MIN_WEIGHT, m.get("block_weight", 1.0) - STEP_NORMAL)
        m["absorb_tempo_bonus"] = min(MAX_WEIGHT, m.get("absorb_tempo_bonus", 1.0) + STEP_NORMAL)
        m["pivot_bonus"] = min(MAX_WEIGHT, m.get("pivot_bonus", 1.0) + STEP_NORMAL)

    elif cause == "low_hand_conversion":
        m["attack_weight"] = min(MAX_WEIGHT, m.get("attack_weight", 1.0) + STEP_NORMAL)
        m["pivot_bonus"] = min(MAX_WEIGHT, m.get("pivot_bonus", 1.0) + STEP_NORMAL)
        m["arsenal_bonus"] = min(MAX_WEIGHT, m.get("arsenal_bonus", 1.0) + STEP_NORMAL)

    elif cause == "fast_bleed":
        m["block_weight"] = min(1.0 + 0.08, m.get("block_weight", 1.0) + STEP_SUBTLE)
        m["pivot_bonus"] = min(MAX_WEIGHT, m.get("pivot_bonus", 1.0) + STEP_NORMAL)

    elif cause == "tempo_race":
        m["pivot_bonus"] = min(MAX_WEIGHT, m.get("pivot_bonus", 1.0) + STEP_NORMAL)
        m["arsenal_bonus"] = min(MAX_WEIGHT, m.get("arsenal_bonus", 1.0) + STEP_SUBTLE)

    else:
        for k in ["attack_weight", "block_weight", "pivot_bonus", "arsenal_bonus", "absorb_tempo_bonus"]:
            current_val = m.get(k, 1.0)
            m[k] = current_val * DECAY_RATE + 1.0 * (1.0 - DECAY_RATE)

    if human_wins > 0:
        m["attack_weight"] = min(MAX_WEIGHT, m.get("attack_weight", 1.0) + min(0.03, human_wins * 0.01))
        m["absorb_tempo_bonus"] = min(MAX_WEIGHT, m.get("absorb_tempo_bonus", 1.0) + min(0.03, human_wins * 0.01))

    for k in ["attack_weight", "block_weight", "pivot_bonus", "arsenal_bonus", "absorb_tempo_bonus"]:
        val = m.get(k, 1.0)
        m[k] = round(float(max(MIN_WEIGHT, min(MAX_WEIGHT, val))), 3)

    return m


def sync_multipliers_with_stats() -> Dict[str, Any]:
    """
    Lê o histórico de partidas do stats_manager e atualiza os
    multiplicadores heurísticos dos heróis usando diagnóstico causal (HVCR)
    e delimitação rígida anti-espiral em [0.85, 1.15].
    """
    try:
        from stats_manager import get_stats_data
        stats = get_stats_data()
    except Exception:
        return {}

    deck_stats = stats.get("deck_stats", {})
    updates_summary = {}

    all_mults = load_multipliers()

    with get_connection() as conn:
        cursor = conn.cursor()

        for d_name, d_info in deck_stats.items():
            if "Humano" in d_name:
                continue

            matches = d_info.get("matches", 0)
            if matches < 3:
                continue

            key = str(d_name).lower().strip().replace(" ", "_")
            current = all_mults.get(key, dict(DEFAULT_MULTIPLIERS)).copy()

            metrics = _fetch_deck_match_metrics(d_name)
            if metrics and "win_rate" in metrics:
                win_rate = metrics["win_rate"]
                eval_matches = metrics.get("matches", matches)
            else:
                wins = d_info.get("wins", 0)
                win_rate = wins / matches if matches > 0 else 0.5
                eval_matches = matches
                default_turns = 7.0 if not is_aggro_or_combo_hero(key) else 10.0
                metrics = {
                    "matches": matches,
                    "win_rate": win_rate,
                    "avg_turns": default_turns,
                    "avg_my_hp": 0.0,
                    "avg_opp_hp": 25.0,
                }

            human_wins = d_info.get("human_wins", 0)

            if win_rate < 0.45:
                cause = diagnose_deck_losses(metrics, key)
                tuned = apply_causal_tuning(current, cause, human_wins)
            elif win_rate > 0.60:
                tuned = dict(current)
                tuned["attack_weight"] = min(MAX_WEIGHT, tuned.get("attack_weight", 1.0) + STEP_NORMAL)
                tuned["absorb_tempo_bonus"] = min(MAX_WEIGHT, tuned.get("absorb_tempo_bonus", 1.0) + STEP_NORMAL)
                if human_wins > 0:
                    tuned["attack_weight"] = min(MAX_WEIGHT, tuned.get("attack_weight", 1.0) + min(0.03, human_wins * 0.01))
            else:
                tuned = apply_causal_tuning(current, "equilibrium", human_wins)

            for field in ["attack_weight", "block_weight", "pivot_bonus", "arsenal_bonus", "absorb_tempo_bonus"]:
                val = tuned.get(field, 1.0)
                tuned[field] = round(float(max(MIN_WEIGHT, min(MAX_WEIGHT, val))), 3)

            updated = {
                "hero_name": key,
                "attack_weight": tuned["attack_weight"],
                "block_weight": tuned["block_weight"],
                "pivot_bonus": tuned["pivot_bonus"],
                "arsenal_bonus": tuned["arsenal_bonus"],
                "absorb_tempo_bonus": tuned["absorb_tempo_bonus"],
                "last_win_rate": round(float(win_rate), 3),
                "human_wins": human_wins,
                "matches_evaluated": eval_matches,
                "updated_at": time.time(),
            }

            is_modified = False
            for k_field, v_field in updated.items():
                if k_field not in ("hero_name", "updated_at"):
                    if current.get(k_field) != v_field:
                        is_modified = True
                        break

            if is_modified or key not in all_mults:
                cursor.execute('''
                    INSERT INTO dynamic_rules 
                    (hero_name, attack_weight, block_weight, pivot_bonus, arsenal_bonus, absorb_tempo_bonus, last_win_rate, human_wins, matches_evaluated, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(hero_name) DO UPDATE SET
                    attack_weight=excluded.attack_weight,
                    block_weight=excluded.block_weight,
                    pivot_bonus=excluded.pivot_bonus,
                    arsenal_bonus=excluded.arsenal_bonus,
                    absorb_tempo_bonus=excluded.absorb_tempo_bonus,
                    last_win_rate=excluded.last_win_rate,
                    human_wins=excluded.human_wins,
                    matches_evaluated=excluded.matches_evaluated,
                    updated_at=excluded.updated_at
                ''', (
                    updated["hero_name"],
                    updated["attack_weight"],
                    updated["block_weight"],
                    updated["pivot_bonus"],
                    updated["arsenal_bonus"],
                    updated["absorb_tempo_bonus"],
                    updated["last_win_rate"],
                    updated["human_wins"],
                    updated["matches_evaluated"],
                    updated["updated_at"]
                ))
                updates_summary[key] = updated

        conn.commit()

    return updates_summary

