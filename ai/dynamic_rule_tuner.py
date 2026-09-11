"""
ai/dynamic_rule_tuner.py
========================
Auto-Tuning Dinâmico de Multiplicadores Heurísticos por Herói e Arquétipo.

Ajusta dinamicamente os pesos de tomada de decisão (ataque, bloqueio, pivot e arsenal)
com base nas taxas de vitória empíricas registradas pelo stats_manager.py.
"""

import os
import json
import time
from typing import Dict, Any, Tuple
from ai.atomic_io import atomic_json_save

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MULTIPLIERS_FILE = os.path.join(DATA_DIR, "hero_rule_multipliers.json")

DEFAULT_MULTIPLIERS = {
    "attack_weight": 1.0,
    "block_weight": 1.0,
    "pivot_bonus": 1.0,
    "arsenal_bonus": 1.0,
}

_CACHE = {
    "mtime": 0.0,
    "data": {},
}


def load_multipliers() -> Dict[str, Dict[str, float]]:
    """Carrega o mapa de multiplicadores com cache em memória baseado em mtime."""
    global _CACHE
    if not os.path.exists(MULTIPLIERS_FILE):
        return {}

    try:
        cur_mtime = os.path.getmtime(MULTIPLIERS_FILE)
        if cur_mtime != _CACHE["mtime"]:
            with open(MULTIPLIERS_FILE, "r", encoding="utf-8") as f:
                _CACHE["data"] = json.load(f)
            _CACHE["mtime"] = cur_mtime
        return _CACHE["data"]
    except Exception:
        return _CACHE.get("data", {})


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


def sync_multipliers_with_stats() -> Dict[str, Any]:
    """
    Lê o histórico de partidas do stats_manager e atualiza gradualmente os
    multiplicadores heurísticos dos heróis com base em suas taxas de vitória.

    Regras de Calibração:
      - Taxa de Vitória < 45% (em >= 3 partidas):
        Aumenta block_weight (+0.04) e pivot_bonus (+0.03) para reforçar sobrevivência;
        atenua attack_weight (-0.02) se estava atacando de forma imprudente.
      - Taxa de Vitória > 60% (em >= 3 partidas):
        Reforça o perfil vitorioso com attack_weight (+0.03) e estabiliza defesas.
      - Limites Estritos de Segurança:
        Todos os multiplicadores são delimitados entre 0.70 e 1.40 para evitar
        comportamentos aberrantes ou travamento de ações.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    all_mults = load_multipliers()
    modified = False

    try:
        from stats_manager import get_stats_data
        stats = get_stats_data()
    except Exception:
        return {}

    deck_stats = stats.get("deck_stats", {})
    updates_summary = {}

    for d_name, d_info in deck_stats.items():
        if "Humano" in d_name:
            continue

        matches = d_info.get("matches", 0)
        if matches < 3:
            continue

        wins = d_info.get("wins", 0)
        win_rate = wins / matches

        key = str(d_name).lower().strip().replace(" ", "_")
        current = all_mults.get(key, dict(DEFAULT_MULTIPLIERS)).copy()

        old_atk = current.get("attack_weight", 1.0)
        old_blk = current.get("block_weight", 1.0)
        old_piv = current.get("pivot_bonus", 1.0)
        old_ars = current.get("arsenal_bonus", 1.0)

        if win_rate < 0.45:
            # Herói com dificuldades: reforçar postura defensiva e sobrevivência
            new_blk = min(1.40, old_blk + 0.04)
            new_piv = min(1.35, old_piv + 0.03)
            new_atk = max(0.80, old_atk - 0.02)
            new_ars = min(1.25, old_ars + 0.02)
        elif win_rate > 0.60:
            # Herói dominante: manter agressividade controlada
            new_atk = min(1.35, old_atk + 0.03)
            new_blk = max(0.85, old_blk - 0.01)
            new_piv = max(0.90, old_piv)
            new_ars = min(1.30, old_ars + 0.01)
        else:
            # Equilíbrio (45% a 60%): decaimento suave em direção ao neutro (1.0)
            new_atk = old_atk * 0.98 + 1.0 * 0.02
            new_blk = old_blk * 0.98 + 1.0 * 0.02
            new_piv = old_piv * 0.98 + 1.0 * 0.02
            new_ars = old_ars * 0.98 + 1.0 * 0.02

        updated = {
            "attack_weight": round(float(new_atk), 3),
            "block_weight": round(float(new_blk), 3),
            "pivot_bonus": round(float(new_piv), 3),
            "arsenal_bonus": round(float(new_ars), 3),
            "last_win_rate": round(float(win_rate), 3),
            "matches_evaluated": matches,
            "updated_at": time.time(),
        }

        if updated != all_mults.get(key):
            all_mults[key] = updated
            updates_summary[key] = updated
            modified = True

    if modified:
        atomic_json_save(all_mults, MULTIPLIERS_FILE)

    return updates_summary
