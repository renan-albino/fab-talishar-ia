#!/usr/bin/env python3
"""
scripts/review_sim2real.py
==========================
Utilitário CLI para auditoria e diagnóstico de erros Sim2Real
(falhas de layers, alvos perdidos, watchdog stalls e divergências de simulador).

Uso:
  python scripts/review_sim2real.py [--limit=50] [--type=LAYER_TARGET_LOST] [--hero=Kassai]
"""

import sys
import os
import json
from collections import Counter, defaultdict

# Adicionar raiz ao PYTHONPATH
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from stats.db import get_recent_sim2real_anomalies


def review_anomalies(limit: int = 50, filter_type: str = None, filter_hero: str = None):
    print("=" * 65)
    print("   RELATÓRIO DE DIAGNÓSTICO SIM2REAL (TALISHAR vs AI ENGINE)")
    print("=" * 65)

    anomalies = get_recent_sim2real_anomalies(limit=limit)

    if not anomalies:
        # Fallback para JSONL caso o banco ainda não tenha registros
        jsonl_path = os.path.join(BASE_DIR, "logs", "sim2real_anomalies.jsonl")
        if os.path.exists(jsonl_path):
            try:
                with open(jsonl_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            anomalies.append(json.loads(line))
                anomalies.reverse()
                anomalies = anomalies[:limit]
            except Exception:
                pass

    if not anomalies:
        print("\n[OK] Nenhuma anomalia Sim2Real detectada recentemente!")
        print("     O motor e o simulador estão operando em harmonia.")
        return

    # Filtros
    if filter_type:
        anomalies = [a for a in anomalies if a.get("anomaly_type") == filter_type]
    if filter_hero:
        anomalies = [a for a in anomalies if filter_hero.lower() in str(a.get("hero", "")).lower()]

    type_counter = Counter()
    card_counter = Counter()
    hero_counter = Counter()

    for a in anomalies:
        t = a.get("anomaly_type", "UNKNOWN")
        type_counter[t] += 1
        hero_counter[a.get("hero", "Unknown")] += 1

        last_action = a.get("last_action_json") or a.get("last_action") or {}
        if isinstance(last_action, str):
            try:
                last_action = json.loads(last_action)
            except Exception:
                last_action = {}
        cid = last_action.get("card_id", "")
        if cid:
            card_counter[cid] += 1

    print(f"\n📊 Total de Anomalias Analisadas: {len(anomalies)}")

    print("\n--- Por Tipo de Anomalia ---")
    for atype, count in type_counter.most_common():
        pct = (count / len(anomalies)) * 100
        print(f"  • {atype:<26}: {count:>3} ({pct:.1f}%)")

    if card_counter:
        print("\n--- Cartas / Ações Mais Problemáticas ---")
        for card, count in card_counter.most_common(5):
            print(f"  • {card:<26}: {count:>3} falha(s)")

    print("\n--- Últimas Ocorrências Registradas ---")
    print(f"{'Turno':<6} | {'Herói':<15} | {'Tipo':<22} | {'Mensagem / Causa'}")
    print("-" * 65)

    for a in anomalies[:15]:
        turn = a.get("turn", 0)
        hero = str(a.get("hero", "Unknown"))[:14]
        atype = str(a.get("anomaly_type", ""))[:21]
        msg = str(a.get("raw_message", a.get("message", "")))
        if len(msg) > 60:
            msg = msg[:57] + "..."
        print(f"{turn:<6} | {hero:<15} | {atype:<22} | {msg}")

    print("\n" + "=" * 65)
    print("Dica: Use `python scripts/fast_search.py '<carta>' Talishar/` para investigar")
    print("a implementação do efeito no motor do jogo.")
    print("=" * 65)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Auditor Sim2Real")
    parser.add_argument("--limit", type=int, default=50, help="Número de anomalias a inspecionar")
    parser.add_argument("--type", type=str, default=None, help="Filtrar por código de anomalia")
    parser.add_argument("--hero", type=str, default=None, help="Filtrar por nome de herói")
    args = parser.parse_args()

    review_anomalies(limit=args.limit, filter_type=args.type, filter_hero=args.hero)
