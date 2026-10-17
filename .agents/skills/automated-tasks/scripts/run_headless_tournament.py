#!/usr/bin/env python3
"""
run_headless_tournament.py
==========================
Executa torneios Swiss ou Round-Robin em modo Headless (em memória via GameSimulator/MCTS)
e exibe a classificação final com Pontos, W-L-D, Buchholz, Sonneborn-Berger e ELO.
"""

import os
import sys
import io
import json
import argparse
import contextlib

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from stats.tournament_manager import TournamentManager


def main() -> int:
    parser = argparse.ArgumentParser(description="Executa torneio Headless (Swiss ou Round-Robin)")
    parser.add_argument("--format", choices=["swiss", "round_robin"], default="swiss", help="Formato do torneio (padrão: swiss).")
    parser.add_argument("--rounds", type=int, default=None, help="Número de rodadas para formato Swiss.")
    parser.add_argument("--sims", type=int, default=2, help="Simulações MCTS por decisão no modo headless (padrão: 2).")
    parser.add_argument("--decks", type=str, default=None, help="Lista de slugs separados por vírgula (ex: jarl,dash_io,kayo,ira).")
    parser.add_argument("--max-decks", type=int, default=4, help="Máximo de decks caso --decks não seja informado (padrão: 4).")
    parser.add_argument("--json", action="store_true", help="Saída estruturada em JSON.")
    args = parser.parse_args()

    tm = TournamentManager(
        tournament_name=f"Headless_{args.format.upper()}",
        format_type=args.format,
        execution_mode="headless",
        mcts_sims=args.sims,
        num_rounds=args.rounds,
    )

    available = tm.load_available_decks(os.path.join(ROOT_DIR, "decks"))
    if args.decks:
        wanted = [s.strip().lower() for s in args.decks.split(",") if s.strip()]
        selected_ids = [d["id"] for d in available if d["id"].lower() in wanted or d["name"].lower() in wanted]
    else:
        selected_ids = [d["id"] for d in sorted(available, key=lambda x: x["id"])[: max(2, args.max_decks)]]

    if len(selected_ids) < 2:
        if args.json:
            print(json.dumps({"error": "Menos de 2 decks encontrados para o torneio."}, ensure_ascii=False))
        else:
            print("Erro: menos de 2 decks encontrados para o torneio.")
        return 1

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf if args.json else sys.stdout):
        tm.setup_tournament(selected_ids)
        tm.run_all_matches()

    standings = tm.participants
    if args.json:
        print(json.dumps({
            "tournament_id": tm.id,
            "format": tm.format_type,
            "execution_mode": tm.execution_mode,
            "mcts_sims": tm.mcts_sims,
            "total_matches": len(tm.matches),
            "standings": standings,
            "matches": tm.matches,
        }, indent=2, ensure_ascii=False))
        return 0

    print(f"\n=== Classificação Final ({tm.tournament_name} | {tm.format_type.upper()} | sims={tm.mcts_sims}) ===")
    header = f"{'#':<3} | {'DECK / HERÓI':<26} | {'PTS':<4} | {'W-L-D':<9} | {'BUCHHOLZ':<8} | {'S-BERGER':<8} | {'ELO':<6}"
    print(header)
    print("-" * len(header))
    for idx, p in enumerate(standings, 1):
        wld = f"{p['wins']}-{p['losses']}-{p['draws']}"
        print(
            f"{idx:<3} | {p['name'][:26]:<26} | {p['points']:<4} | {wld:<9} | "
            f"{p.get('buchholz', 0.0):<8.1f} | {p.get('sonneborn_berger', 0.0):<8.1f} | {p.get('elo', 1200):<6.0f}"
        )
    print("-" * len(header) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
