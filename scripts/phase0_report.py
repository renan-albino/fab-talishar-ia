import os
import json
from stats.db import get_connection

def generate_report():
    out = ["# Relatório Fase 0\n"]
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Winrates contra Humanos
        cursor.execute("SELECT deck_name, human_matches, human_wins FROM hero_elo WHERE human_matches > 0")
        rows = cursor.fetchall()
        
        out.append("## 1. Winrate contra Humanos\n")
        if not rows:
            out.append("Nenhuma partida contra humano registrada.")
        else:
            for r in rows:
                wr = (r["human_wins"] / r["human_matches"]) * 100
                out.append(f"- **{r['deck_name']}**: {wr:.1f}% ({r['human_wins']}/{r['human_matches']})\n")
                
        # Simulador Fidelidade
        cursor.execute("SELECT count(*) as c, sum(confounded) as conf FROM shadow_steps")
        row = cursor.fetchone()
        
        out.append("\n## 2. Simulador vs Talishar (Shadow Mode)\n")
        if row and row["c"] > 0:
            total = row["c"]
            conf = row["conf"]
            fidelidade = ((total - conf) / total) * 100
            out.append(f"- **Fidelidade Estimada**: {fidelidade:.1f}% ({total - conf}/{total} steps intactos)")
        else:
            out.append("Nenhum dado de shadow mode registrado.")
            
    os.makedirs("docs/reports", exist_ok=True)
    with open("docs/reports/phase0.md", "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    print("Relatório salvo em docs/reports/phase0.md")

if __name__ == "__main__":
    generate_report()
