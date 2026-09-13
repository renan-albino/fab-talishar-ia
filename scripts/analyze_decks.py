#!/usr/bin/env python3
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATS_FILE = os.path.join(BASE_DIR, "data", "training_stats.json")

def main():
    with open(STATS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    deck_stats = data.get("deck_stats", {})
    recent_matches = data.get("recent_matches", [])

    print("=" * 80)
    print(f"TOTAL MATCHES: {data.get('total_matches', 0)} | Bot1 Wins: {data.get('bot1_wins', 0)} | Bot2 Wins: {data.get('bot2_wins', 0)} | Draws: {data.get('draws', 0)}")
    print("=" * 80)
    print(f"{'Hero / Deck':<20} | {'Matches':<8} | {'Wins':<6} | {'Losses':<6} | {'Win Rate':<10} | {'ELO':<6}")
    print("-" * 80)

    calculated = []
    for deck, stats in deck_stats.items():
        matches = stats.get("matches", 0)
        wins = stats.get("wins", 0)
        losses = stats.get("losses", 0)
        wr = (wins / matches * 100) if matches > 0 else 0.0
        elo = stats.get("elo", 1200)
        calculated.append((deck, matches, wins, losses, wr, elo))

    calculated.sort(key=lambda x: x[4]) # Ordenar por winrate

    sub_50 = []
    for deck, matches, wins, losses, wr, elo in calculated:
        status = "🚨 < 50%" if wr < 50.0 else "✅ >= 50%"
        if wr < 50.0 and deck != "👤 Humano (Você)":
            sub_50.append(deck)
        print(f"{deck:<20} | {matches:<8} | {wins:<6} | {losses:<6} | {wr:6.1f}%    | {elo:<6.0f} {status}")
    print("=" * 80)
    print(f"HERÓIS COM WINRATE < 50%: {', '.join(sub_50)}")

    # Inspecionar as últimas 35 partidas
    print("\nÚLTIMAS 35 PARTIDAS REGISTRADAS:")
    print("-" * 115)
    print(f"{'Room':<16} | {'P1 Deck':<14} | {'P2 Deck':<14} | {'P1 HP':<6} | {'P2 HP':<6} | {'Turns':<6} | {'Winner':<22} | {'Invalid / Motivo'}")
    print("-" * 115)
    for m in recent_matches[-35:]:
        room = str(m.get("room", ""))[:16]
        p1 = str(m.get("p1_deck", ""))[:14]
        p2 = str(m.get("p2_deck", ""))[:14]
        p1_hp = m.get("p1_health", "?")
        p2_hp = m.get("p2_health", "?")
        turns = m.get("turns", "?")
        winner = str(m.get("winner", ""))[:22]
        inv = m.get("invalid_reason", "") if m.get("is_invalid") else ""
        print(f"{room:<16} | {p1:<14} | {p2:<14} | {str(p1_hp):<6} | {str(p2_hp):<6} | {str(turns):<6} | {winner:<22} | {inv}")

if __name__ == "__main__":
    main()
