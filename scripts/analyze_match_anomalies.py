import sqlite3
import os
from collections import Counter, defaultdict

db_path = "data/talishar_stats.db"
conn = sqlite3.connect(db_path)
c = conn.cursor()

c.execute("SELECT id, room_id, date, winner, p1_deck, p2_deck, p1_health, p2_health, turns FROM match_history")
matches = c.fetchall()

print(f"=== ANÁLISE QUANTITATIVA DE {len(matches)} PARTIDAS ===")

winners = Counter()
outcome_types = Counter()
turns_list = []
annulled_matches = []
short_matches = []
long_matches = []
overkill_matches = []
deck_stats = defaultdict(lambda: {"wins": 0, "losses": 0, "draws": 0, "total": 0})

for m in matches:
    m_id, room_id, date, winner, p1_deck, p2_deck, p1_hp, p2_hp, turns = m
    turns_list.append(turns)
    
    # Classificar resultado
    if "Anulada" in winner or "Timeout" in winner:
        outcome_types["Timeout/Anulada"] += 1
        annulled_matches.append(m)
    elif "Empate" in winner or "Stalemate" in winner:
        outcome_types["Empate Técnico"] += 1
        deck_stats[p1_deck]["draws"] += 1
        deck_stats[p2_deck]["draws"] += 1
    elif "Bot 1" in winner:
        outcome_types["Bot 1 Vitória"] += 1
        deck_stats[p1_deck]["wins"] += 1
        deck_stats[p2_deck]["losses"] += 1
    elif "Bot 2" in winner:
        outcome_types["Bot 2 Vitória"] += 1
        deck_stats[p2_deck]["wins"] += 1
        deck_stats[p1_deck]["losses"] += 1
    else:
        outcome_types[winner] += 1
        
    deck_stats[p1_deck]["total"] += 1
    deck_stats[p2_deck]["total"] += 1

    # Desvios de duração
    if turns <= 6:
        short_matches.append(m)
    elif turns >= 20:
        long_matches.append(m)

    # Overkills extremos (perdedor com <= -5 HP)
    if p1_hp <= -5 or p2_hp <= -5:
        overkill_matches.append(m)

print("\n--- Distribuição de Desfechos ---")
for out, cnt in outcome_types.items():
    pct = (cnt / len(matches)) * 100
    print(f"  {out}: {cnt} ({pct:.1f}%)")

if turns_list:
    print(f"\n--- Estatísticas de Duração (Turnos) ---")
    print(f"  Média: {sum(turns_list)/len(turns_list):.1f} turnos")
    print(f"  Mínimo: {min(turns_list)} turnos | Máximo: {max(turns_list)} turnos")

print(f"\n--- Partidas Anuladas / Timeouts ({len(annulled_matches)}) ---")
for m in annulled_matches:
    print(f"  ID {m[0]} ({m[2]}): {m[4]} ({m[6]} HP) vs {m[5]} ({m[7]} HP) - {m[8]} turnos - {m[3]}")

print(f"\n--- Partidas Ultra-Curtas (<= 6 turnos) ({len(short_matches)}) ---")
for m in short_matches:
    print(f"  ID {m[0]}: {m[4]} ({m[6]} HP) vs {m[5]} ({m[7]} HP) - {m[8]} turnos -> Vencedor: {m[3]}")

print(f"\n--- Overkills Extremos (HP <= -5) ({len(overkill_matches)}) ---")
for m in overkill_matches:
    print(f"  ID {m[0]}: {m[4]} ({m[6]} HP) vs {m[5]} ({m[7]} HP) - {m[8]} turnos -> Vencedor: {m[3]}")

print("\n--- Desempenho por Baralho / Herói ---")
deck_summary = []
for deck, s in deck_stats.items():
    wr = (s["wins"] / s["total"]) * 100 if s["total"] > 0 else 0
    deck_summary.append((deck, s["wins"], s["losses"], s["draws"], s["total"], wr))

deck_summary.sort(key=lambda x: x[4], reverse=True)
print(f"{'Baralho':<22} | {'V':<3} | {'D':<3} | {'E':<3} | {'Total':<5} | {'WR (%)':<6}")
print("-" * 55)
for d in deck_summary:
    print(f"{d[0]:<22} | {d[1]:<3} | {d[2]:<3} | {d[3]:<3} | {d[4]:<5} | {d[5]:.1f}%")

print("\n--- Tabela hero_elo ---")
c.execute("SELECT deck_name, elo, matches, wins, losses FROM hero_elo ORDER BY elo DESC")
elos = c.fetchall()
for e in elos:
    wr = (e[3] / e[2]) * 100 if e[2] > 0 else 0
    print(f"  {e[0]:<18}: ELO {e[1]:.1f} ({e[3]}V - {e[4]}D / {e[2]} partidas) - WR {wr:.1f}%")

print("\n--- Multiplicadores Dinâmicos de Regras (dynamic_rules) ---")
c.execute("SELECT hero_name, attack_weight, block_weight, absorb_tempo_bonus, pivot_bonus, arsenal_bonus, last_win_rate FROM dynamic_rules")
rules = c.fetchall()
for r in rules:
    print(f"  {r[0]:<15}: atk={r[1]:.2f}, blk={r[2]:.2f}, absorb={r[3]:.2f}, pivot={r[4]:.2f}, arse={r[5]:.2f} (WR: {r[6]*100:.1f}%)")
