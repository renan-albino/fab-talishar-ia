#!/usr/bin/env python3
"""
diagnose_sim2real.py
====================
Diagnóstico enxuto de divergências Sim2Real e telemetria do Modo Sombra (shadow_steps).
Inspeciona anomalias via SQLite (stats.db) + fallback JSONL e calcula taxas de fidelidade.
"""

import os
import sys
import json
import argparse
from collections import Counter
from typing import Dict, Any, List, Optional

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from stats.db import get_connection, get_recent_sim2real_anomalies


def load_anomalies(limit: int, hero: Optional[str], anomaly_type: Optional[str]) -> List[Dict[str, Any]]:
    rows = get_recent_sim2real_anomalies(limit=limit, hero=hero, anomaly_type=anomaly_type)
    if rows:
        return rows

    jsonl_path = os.path.join(ROOT_DIR, "logs", "sim2real_anomalies.jsonl")
    if not os.path.exists(jsonl_path):
        return []

    fallback: List[Dict[str, Any]] = []
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                item = json.loads(line)
                if hero and hero.lower() not in str(item.get("hero", "")).lower():
                    continue
                if anomaly_type and item.get("anomaly_type") != anomaly_type:
                    continue
                fallback.append(item)
    except Exception:
        pass
    return list(reversed(fallback[-limit:]))


def analyze_shadow_steps(hero: Optional[str] = None) -> Dict[str, Any]:
    total = 0
    exact_matches = 0
    confounded_count = 0
    diff_keys_counter: Counter = Counter()
    cards_counter: Counter = Counter()
    heroes_counter: Counter = Counter()

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            if hero:
                cursor.execute(
                    "SELECT hero, card_id, diffs_json, confounded FROM shadow_steps WHERE LOWER(hero) LIKE ?",
                    (f"%{hero.lower()}%",),
                )
            else:
                cursor.execute("SELECT hero, card_id, diffs_json, confounded FROM shadow_steps")

            for row in cursor.fetchall():
                total += 1
                h = str(row["hero"] or "unknown")
                c = str(row["card_id"] or "unknown")
                conf = int(row["confounded"] or 0)
                diffs_raw = row["diffs_json"] or "{}"

                if conf == 1:
                    confounded_count += 1

                if diffs_raw == "{}":
                    exact_matches += 1
                else:
                    try:
                        diffs = json.loads(diffs_raw)
                        if isinstance(diffs, dict) and diffs:
                            for k in diffs.keys():
                                diff_keys_counter[k] += 1
                            cards_counter[c] += 1
                            heroes_counter[h] += 1
                        else:
                            exact_matches += 1
                    except Exception:
                        pass
    except Exception:
        pass

    clean_total = max(0, total - confounded_count)
    exact_pct = round((exact_matches / total) * 100.0, 2) if total > 0 else 100.0
    confounded_pct = round((confounded_count / total) * 100.0, 2) if total > 0 else 0.0

    return {
        "total_steps": total,
        "clean_steps": clean_total,
        "exact_matches": exact_matches,
        "exact_fidelity_pct": exact_pct,
        "confounded_steps": confounded_count,
        "confounded_pct": confounded_pct,
        "top_diff_keys": dict(diff_keys_counter.most_common(10)),
        "top_divergent_cards": dict(cards_counter.most_common(10)),
        "top_divergent_heroes": dict(heroes_counter.most_common(10)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnóstico Sim2Real e Fidelidade do Modo Sombra")
    parser.add_argument("--limit", type=int, default=25, help="Limite de anomalias recentes (padrão: 25).")
    parser.add_argument("--hero", type=str, default=None, help="Filtrar por nome/slug do herói.")
    parser.add_argument("--type", dest="anomaly_type", type=str, default=None, help="Filtrar por tipo de anomalia.")
    parser.add_argument("--json", action="store_true", help="Saída estruturada em JSON.")
    args = parser.parse_args()

    anomalies = load_anomalies(limit=args.limit, hero=args.hero, anomaly_type=args.anomaly_type)
    type_counts = Counter(str(a.get("anomaly_type", "UNKNOWN")) for a in anomalies)
    hero_counts = Counter(str(a.get("hero", "unknown")) for a in anomalies)
    shadow = analyze_shadow_steps(hero=args.hero)

    report = {
        "filters": {"limit": args.limit, "hero": args.hero, "type": args.anomaly_type},
        "anomalies_summary": {
            "count": len(anomalies),
            "by_type": dict(type_counts.most_common(10)),
            "by_hero": dict(hero_counts.most_common(10)),
            "recent": anomalies[:10],
        },
        "shadow_steps": shadow,
    }

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0

    print("\n=== FaB Talishar AI — Diagnóstico Sim2Real & Shadow Mode ===")
    print(f"Passos Avaliados (shadow_steps): {shadow['total_steps']} "
          f"| Fidelidade Exata: {shadow['exact_fidelity_pct']:.2f}% ({shadow['exact_matches']}) "
          f"| Ticks Transitórios (confounded): {shadow['confounded_pct']:.2f}% ({shadow['confounded_steps']})")
    if shadow["top_diff_keys"]:
        print(f"Chaves Divergentes: {shadow['top_diff_keys']}")
    if shadow["top_divergent_cards"]:
        print(f"Cartas Mais Divergentes: {shadow['top_divergent_cards']}")
    if shadow["top_divergent_heroes"]:
        print(f"Heróis Mais Divergentes: {shadow['top_divergent_heroes']}")

    print(f"\nAnomalias Recentes (sim2real_anomalies): {len(anomalies)} encontradas")
    if type_counts:
        print(f"Por Tipo: {dict(type_counts)}")
    for a in anomalies[:5]:
        print(f"  - [{a.get('anomaly_type')}] Hero={a.get('hero')} Turn={a.get('turn')} Phase={a.get('phase')}: {str(a.get('raw_message', ''))[:80]}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
