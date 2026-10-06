"""
Inspeção detalhada da sessão de treino de hoje (partidas e anomalias Sim2Real).
"""
import sqlite3
import datetime
import time

conn = sqlite3.connect("data/talishar_stats.db")
c = conn.cursor()

# 1. Partidas de hoje
c.execute("SELECT count(*), min(date), max(date) FROM match_history WHERE date LIKE '05/10/2026%'")
cnt_matches, min_m, max_m = c.fetchone()
print(f"=== PARTIDAS HOJE (05/10/2026) ===")
print(f"Total de Partidas Concluídas: {cnt_matches}")
print(f"Primeira Partida: {min_m}")
print(f"Última Partida: {max_m}")

c.execute("SELECT winner, count(*) FROM match_history WHERE date LIKE '05/10/2026%' GROUP BY winner ORDER BY count(*) DESC")
print("\nDesfecho das Partidas:")
for w, cnt in c.fetchall():
    print(f"  • {w}: {cnt}")

# 2. Anomalias Sim2Real de hoje (últimas 12 horas)
ts_12h = time.time() - (12 * 3600)
c.execute("SELECT count(*), min(created_at), max(created_at) FROM sim2real_anomalies WHERE created_at >= ?", (ts_12h,))
cnt_anom, min_a, max_a = c.fetchone()
print(f"\n=== ANOMALIAS SIM2REAL (ÚLTIMAS 12H) ===")
print(f"Total de Anomalias Registradas: {cnt_anom}")
print(f"Primeira Anomalia: {datetime.datetime.fromtimestamp(min_a) if min_a else 'N/A'}")
print(f"Última Anomalia: {datetime.datetime.fromtimestamp(max_a) if max_a else 'N/A'}")

c.execute("SELECT anomaly_type, count(*) FROM sim2real_anomalies WHERE created_at >= ? GROUP BY anomaly_type ORDER BY count(*) DESC", (ts_12h,))
print("\nPor Tipo de Anomalia:")
for t, cnt in c.fetchall():
    pct = (cnt / cnt_anom * 100) if cnt_anom else 0
    print(f"  • {t:<26}: {cnt:>5} ({pct:.1f}%)")

c.execute("SELECT hero, count(*) FROM sim2real_anomalies WHERE created_at >= ? GROUP BY hero ORDER BY count(*) DESC LIMIT 5", (ts_12h,))
print("\nTop 5 Heróis com mais anomalias:")
for h, cnt in c.fetchall():
    print(f"  • {h:<26}: {cnt:>5}")

# 3. Análise detalhada dos erros críticos (não apenas divergência do simulador):
print("\n=== DETALHE DAS ANOMALIAS CRÍTICAS (LAYER e STALL) ===")
c.execute("""
    SELECT anomaly_type, hero, turn, raw_message, count(*)
    FROM sim2real_anomalies 
    WHERE created_at >= ? AND anomaly_type IN ('LAYER_TARGET_LOST', 'PRIORITY_STALL', 'LAYER_FAILED_TO_RESOLVE')
    GROUP BY anomaly_type, raw_message
    ORDER BY count(*) DESC LIMIT 10
""", (ts_12h,))
for atype, hero, turn, raw_msg, cnt in c.fetchall():
    msg_snip = raw_msg[:80].replace("\n", " ")
    print(f"  [{atype}] ({cnt}x) - Herói: {hero} (Turno {turn}) -> {msg_snip}")

# 4. Amostra de SIMULATOR_DIVERGENCE
print("\n=== EXEMPLO DE SIMULATOR_DIVERGENCE (Diferença de previsão) ===")
c.execute("""
    SELECT hero, turn, raw_message 
    FROM sim2real_anomalies 
    WHERE created_at >= ? AND anomaly_type = 'SIMULATOR_DIVERGENCE'
    ORDER BY id DESC LIMIT 5
""", (ts_12h,))
for hero, turn, raw_msg in c.fetchall():
    print(f"  • {hero} (T{turn}): {raw_msg[:120]}")
