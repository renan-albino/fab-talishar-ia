#!/usr/bin/env python3
"""
scripts/analyze_ismcts.py
==========================
Analisador local de decisões ISMCTS para o FAB AI Engine.

Lê o arquivo `logs/ismcts_decisions.jsonl` e gera:
  1. Tabela de ações mais escolhidas por fase de turno.
  2. Distribuição de confiança (histograma ASCII).
  3. Casos de alta divergência entre mundos (baixa confiança).
  4. Comparação turno a turno (valor da raiz vs confiança).

Modos de Uso:
  # Analisar log real de uma partida:
  python scripts/analyze_ismcts.py

  # Especificar arquivo:
  python scripts/analyze_ismcts.py logs/ismcts_decisions.jsonl

  # Dry-run: gera dados sintéticos e roda ISMCTS sem servidor:
  python scripts/analyze_ismcts.py --dry-run

  # Mostrar as últimas N decisões:
  python scripts/analyze_ismcts.py --tail 20
"""

import sys
import os
import json
import argparse
import random
from collections import defaultdict, Counter
from datetime import datetime, timezone

# Garantir que o root do projeto está no path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ══════════════════════════════════════════════════════════════════
# FORMATADORES AUXILIARES
# ══════════════════════════════════════════════════════════════════

def _bar_h(value: float, max_val: float = 1.0, width: int = 30, char: str = "█") -> str:
    """Barra horizontal ASCII proporcional."""
    if max_val <= 0:
        filled = 0
    else:
        filled = int(width * min(value, max_val) / max_val)
    return char * filled + "░" * (width - filled)


def _histogram(values: list, bins: int = 10, width: int = 40) -> str:
    """Histograma ASCII horizontal para uma lista de floats [0, 1]."""
    if not values:
        return "  (sem dados)"

    counts = [0] * bins
    for v in values:
        idx = min(int(v * bins), bins - 1)
        counts[idx] += 1

    max_count = max(counts) if counts else 1
    lines = []
    for i, c in enumerate(counts):
        low  = i / bins
        high = (i + 1) / bins
        bar  = _bar_h(c, max_count, width)
        lines.append(f"  [{low:.1f}-{high:.1f})  {bar}  {c}")
    return "\n".join(lines)


def _divider(char: str = "═", width: int = 70) -> str:
    return char * width


# ══════════════════════════════════════════════════════════════════
# DRY-RUN — Geração de Dados Sintéticos + Execução ISMCTS
# ══════════════════════════════════════════════════════════════════

def _run_dry_run(n_states: int = 5) -> list:
    """
    Gera estados sintéticos e roda ISMCTSEngine diretamente.
    Útil para verificar que o fluxo funciona sem servidor Talishar.
    """
    print(_divider())
    print("  🧪  DRY-RUN: Gerando estados sintéticos e rodando ISMCTS...")
    print(_divider())

    try:
        from ai.mcts import ISMCTSEngine
        from ai.ismcts_logger import ISMCTSLogger
    except ImportError as e:
        print(f"\n  ❌ Erro ao importar módulos de IA: {e}")
        print("  Verifique se está rodando do diretório raiz do projeto.")
        return []

    engine = ISMCTSEngine(model=None, device="cpu")  # Sem modelo — usa priors uniformes
    entries = []

    phases = ["M", "M", "B", "M", "A"]
    heroes = ["dorinthea_ironsong", "bravo_showstopper", "katsu", "dash", "kano"]

    for i in range(n_states):
        phase = phases[i % len(phases)]
        hero  = heroes[i % len(heroes)]

        # Estado sintético com mão oculta do oponente
        opp_hand_count = random.randint(2, 5)
        state = {
            "playerHealth"      : random.randint(10, 40),
            "opponentHealth"    : random.randint(10, 40),
            "playerHand"        : [
                {"cardNumber": f"card_{j}_red",   "pitch": 1, "power": random.randint(3, 8), "defense": 2, "action": 27}
                for j in range(random.randint(2, 5))
            ],
            "playerResources"   : [random.randint(0, 3), 0],
            "playerAP"          : 1,
            "opponentHandCount" : opp_hand_count,
            "opponentDiscard"   : [
                {"cardNumber": f"opp_card_{k}_blue", "pitch": 3, "power": 2, "defense": 3, "action": 27}
                for k in range(3)
            ],
            "turnPhase"         : phase,
            "turnNo"            : i + 1,
            "playerHero"        : hero,
        }

        # Candidatos sintéticos de ação
        candidates = [
            {"name": f"zero_to_sixty_red_{i}", "mode": 27, "card_id": f"c{i*3}",   "score": random.uniform(4, 9), "has_go_again": True,  "type": "hand", "idx": 0, "cost": 0, "pitch": 1, "power": 4},
            {"name": f"throttle_red_{i}",       "mode": 27, "card_id": f"c{i*3+1}", "score": random.uniform(2, 7), "has_go_again": False, "type": "hand", "idx": 1, "cost": 2, "pitch": 1, "power": 6},
            {"name": f"anothos_{i}",            "mode": 5,  "card_id": f"w{i}",     "score": random.uniform(1, 5), "has_go_again": False, "type": "weapon", "idx": 0, "cost": 0, "pitch": 0, "power": 4},
        ]
        if random.random() > 0.5:
            candidates.append({
                "name": f"blue_pitch_{i}", "mode": 27, "card_id": f"p{i}", "score": random.uniform(0, 3),
                "has_go_again": False, "type": "hand", "idx": 2, "cost": 0, "pitch": 3, "power": 2
            })

        num_sims = 10  # Poucas simulações para dry-run ser rápido
        best_idx, policy_dist, ismcts_log = engine.search_ismcts(
            state=state,
            legal_actions=candidates,
            num_simulations=num_sims,
        )

        entry = {
            "timestamp"      : datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "room_id"        : "dry_run",
            "hero"           : hero,
            "turn"           : i + 1,
            "phase"          : phase,
            **ismcts_log,
        }
        entries.append(entry)

        print(f"\n  Estado {i+1} | Turno {i+1} | Fase: {phase} | Herói: {hero}")
        print(f"  Oponente tem {opp_hand_count} cartas na mão (mundos gerados: {ismcts_log['worlds_sampled']})")
        print(f"  Candidatos: {[c['name'] for c in candidates]}")
        print(f"  Votos:     {ismcts_log['votes']}")
        print(f"  Escolhido: {ismcts_log['chosen']}  (confiança: {ismcts_log['confidence']:.1%})")
        print(f"  Value Raiz (rede neural): {ismcts_log['mcts_value_root']:.3f}")

    print(f"\n  ✅ Dry-run concluído — {n_states} estados avaliados.")
    return entries


# ══════════════════════════════════════════════════════════════════
# ANÁLISE DO LOG REAL
# ══════════════════════════════════════════════════════════════════

def analyze(entries: list) -> None:
    if not entries:
        print("\n  ⚠  Nenhuma entrada encontrada. Use --dry-run para testar sem partida real.")
        return

    W = 70
    print(_divider("═", W))
    print("  🌐  FAB ISMCTS — Relatório de Análise de Decisões")
    print(_divider("═", W))
    print(f"  Total de decisões analisadas: {len(entries)}")

    # ── 1. Distribuição por fase ──────────────────────────────────
    phase_counts = Counter(e.get("phase", "?") for e in entries)
    print(f"\n  Decisões por fase de turno:")
    for phase, count in sorted(phase_counts.items(), key=lambda x: -x[1]):
        bar = _bar_h(count, max(phase_counts.values()), 25)
        print(f"    {phase:<12} {bar}  {count}")

    # ── 2. Ações mais escolhidas ──────────────────────────────────
    chosen_counts = Counter(e.get("chosen", "?") for e in entries)
    print(f"\n  Top 10 ações mais escolhidas pelo ISMCTS:")
    for action, count in chosen_counts.most_common(10):
        bar = _bar_h(count, chosen_counts.most_common(1)[0][1], 25)
        pct = count / len(entries) * 100
        print(f"    {action:<40} {bar}  {count} ({pct:.1f}%)")

    # ── 3. Distribuição de confiança ──────────────────────────────
    confidences = [e.get("confidence", 0.0) for e in entries]
    mean_conf   = sum(confidences) / len(confidences) if confidences else 0
    print(f"\n  Distribuição de Confiança (média: {mean_conf:.1%}):")
    print(_histogram(confidences, bins=10, width=35))

    # ── 4. Casos de alta divergência (confiança < 0.3) ────────────
    low_conf = [e for e in entries if e.get("confidence", 1.0) < 0.30]
    print(f"\n  Decisões de alta incerteza (confiança < 30%): {len(low_conf)} de {len(entries)}")
    if low_conf:
        print(f"  Turnos mais incertos:")
        for e in sorted(low_conf, key=lambda x: x.get("confidence", 1.0))[:5]:
            print(
                f"    Turno {e.get('turn', '?'):>3} | Fase: {e.get('phase', '?'):<4} | "
                f"Herói: {e.get('hero', '?'):<25} | "
                f"Confiança: {e.get('confidence', 0.0):.1%} | "
                f"Escolhido: {e.get('chosen', '?')}"
            )

    # ── 5. Distribuição de mundos amostrados ──────────────────────
    worlds_counts = Counter(e.get("worlds_sampled", 0) for e in entries)
    print(f"\n  Distribuição de mundos amostrados por decisão:")
    for w, count in sorted(worlds_counts.items()):
        bar = _bar_h(count, max(worlds_counts.values()), 20)
        print(f"    {w} mundos  {bar}  {count}")

    # ── 6. Value médio da raiz por turno ──────────────────────────
    turns_with_entries = defaultdict(list)
    for e in entries:
        turns_with_entries[e.get("turn", 0)].append(e.get("mcts_value_root", 0.0))

    if turns_with_entries:
        print(f"\n  Evolução do Value da Raiz por turno:")
        for turn in sorted(turns_with_entries.keys())[:20]:  # Máximo 20 turnos
            vals    = turns_with_entries[turn]
            avg_val = sum(vals) / len(vals)
            bar     = _bar_h(abs(avg_val), 1.0, 20, "▓" if avg_val >= 0 else "░")
            sign    = "+" if avg_val >= 0 else ""
            print(f"    Turno {turn:>3}  {bar}  {sign}{avg_val:.3f}")

    print(_divider("═", W))
    print(f"  ✅ Análise concluída.")
    print(_divider("═", W))


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Analisador local de decisões ISMCTS para o FAB AI Engine.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "log_file",
        nargs="?",
        default=os.path.join("logs", "ismcts_decisions.jsonl"),
        help="Caminho para o arquivo JSONL de decisões ISMCTS. (default: logs/ismcts_decisions.jsonl)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Gera estados sintéticos e roda ISMCTS sem servidor Talishar.",
    )
    parser.add_argument(
        "--tail",
        type=int,
        default=None,
        metavar="N",
        help="Analisar apenas as últimas N decisões do log.",
    )
    args = parser.parse_args()

    if args.dry_run:
        entries = _run_dry_run(n_states=5)
        if entries:
            print()
            analyze(entries)
        return

    # Carregar do arquivo
    log_path = args.log_file
    if not os.path.exists(log_path):
        print(f"\n  ⚠  Arquivo não encontrado: {log_path}")
        print(f"  Execute uma partida com o bot_client.py primeiro, ou use --dry-run para testar.")
        sys.exit(1)

    entries = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if args.tail:
        entries = entries[-args.tail:]

    print(f"\n  Carregadas {len(entries)} entradas de: {log_path}")
    analyze(entries)


if __name__ == "__main__":
    main()
