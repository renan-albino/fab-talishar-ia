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
    """Retorna True se o herói pertence a uma classe aggro/combo."""
    try:
        from ai.game_simulator import GameSimulator
        db = GameSimulator._get_cards_db() if hasattr(GameSimulator, '_get_cards_db') else {}
    except Exception:
        db = {}
    slug = str(name).lower().strip().replace(" ", "_").replace("-", "_")
    hero_data = db.get(slug) or db.get(slug.split("_")[0], {})
    hero_class = str(hero_data.get("class", "")).lower()
    aggro_classes = {"ninja", "mechanologist", "runeblade", "ranger", "wizard", "illusionist"}
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

            wins = d_info.get("wins", 0)
            win_rate = wins / matches

            key = str(d_name).lower().strip().replace(" ", "_")
            current = all_mults.get(key, dict(DEFAULT_MULTIPLIERS)).copy()

            old_atk = current.get("attack_weight", 1.0)
            old_blk = current.get("block_weight", 1.0)
            old_piv = current.get("pivot_bonus", 1.0)
            old_ars = current.get("arsenal_bonus", 1.0)
            old_abs = current.get("absorb_tempo_bonus", 1.0)

            human_wins = d_info.get("human_wins", 0)

            if win_rate < 0.45:
                if is_aggro_or_combo_hero(key):
                    # Heróis aggro/combo/sinergia em dificuldade: NUNCA reduza ataque nem force bloqueio com peças de combo!
                    # Devem reforçar o timing de pivot, absorção de tempo e manter agressividade
                    new_atk = min(1.35, max(1.10, old_atk + 0.03))
                    new_blk = max(0.80, min(0.95, old_blk - 0.02))
                    new_piv = min(1.35, old_piv + 0.03)
                    new_ars = min(1.30, old_ars + 0.02)
                    new_abs = min(1.35, max(1.10, old_abs + 0.03))
                else:
                    # Herói defensivo / midrange clássico (Guardian, Brute/Warrior defensivo): reforçar postura defensiva
                    new_blk = min(1.40, old_blk + 0.04)
                    new_piv = min(1.35, old_piv + 0.03)
                    new_atk = max(0.80, old_atk - 0.02)
                    new_ars = min(1.25, old_ars + 0.02)
                    new_abs = max(0.85, old_abs - 0.02)
            elif win_rate > 0.60:
                # Herói dominante: manter agressividade controlada e capacidade de absorver e punir
                new_atk = min(1.35, old_atk + 0.03)
                new_blk = max(0.85, old_blk - 0.01)
                new_piv = max(0.90, old_piv)
                new_ars = min(1.30, old_ars + 0.01)
                new_abs = min(1.35, old_abs + 0.03)
            else:
                # Equilíbrio (45% a 60%): decaimento suave em direção ao neutro (1.0)
                new_atk = old_atk * 0.98 + 1.0 * 0.02
                new_blk = old_blk * 0.98 + 1.0 * 0.02
                new_piv = old_piv * 0.98 + 1.0 * 0.02
                new_ars = old_ars * 0.98 + 1.0 * 0.02
                new_abs = old_abs * 0.98 + 1.0 * 0.02

            # Bônus de prestígio por vitórias contra humanos
            if human_wins > 0:
                new_atk = min(1.40, new_atk + min(0.05, human_wins * 0.015))
                new_abs = min(1.40, new_abs + min(0.05, human_wins * 0.02))

            updated = {
                "hero_name": key,
                "attack_weight": round(float(new_atk), 3),
                "block_weight": round(float(new_blk), 3),
                "pivot_bonus": round(float(new_piv), 3),
                "arsenal_bonus": round(float(new_ars), 3),
                "absorb_tempo_bonus": round(float(new_abs), 3),
                "last_win_rate": round(float(win_rate), 3),
                "human_wins": human_wins,
                "matches_evaluated": matches,
                "updated_at": time.time(),
            }
            
            # Check if really updated
            is_modified = False
            for k_field, v_field in updated.items():
                if k_field != "hero_name" and k_field != "updated_at":
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
                ''', (updated["hero_name"], updated["attack_weight"], updated["block_weight"], updated["pivot_bonus"], updated["arsenal_bonus"], updated["absorb_tempo_bonus"], updated["last_win_rate"], updated["human_wins"], updated["matches_evaluated"], updated["updated_at"]))
                updates_summary[key] = updated
        
        conn.commit()

    return updates_summary

