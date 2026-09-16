#!/usr/bin/env python3
"""
benchmark_mcts.py
=================
Benchmark de vazão e latência para os motores de busca MCTS e ISMCTS do FaB Talishar AI.

Avalia:
  - Taxa de decisões por segundo (Throughput / dec/s);
  - Taxa de rollouts por segundo (rollouts/s = decisões * sims [* worlds] / tempo);
  - Distribuição estatística de latência por decisão: Média, Mín, Máx, p50, p90, p95, p99;
  - Desempenho concorrente multi-thread via ThreadPoolExecutor (`--threads`);
  - Modos com e sem Rede Neural (`FaBPolicyValueNetwork`).

Gera tabela comparativa formatada em terminal ou saída estruturada em JSON.
"""

import os
import sys
import time
import json
import argparse
import statistics
import concurrent.futures
from typing import Dict, Any, List, Tuple, Optional

# ── Resolução de Caminho Raiz do Repositório ──────────────────────────────
def _find_repo_root() -> str:
    curr = os.path.abspath(os.path.dirname(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "bot_client.py")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

ROOT_DIR = _find_repo_root()
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ai.mcts.standard_mcts import MCTSEngine
from ai.mcts.ismcts import ISMCTSEngine

# Cores ANSI
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[0;32m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED = "\033[0;31m"
COLOR_CYAN = "\033[0;36m"
COLOR_BOLD = "\033[1m"


# ── Estados e Ações de Amostra Representativos ─────────────────────────────
BENCHMARK_SCENARIOS = [
    {
        "name": "Guardian_Hammer_Turn",
        "state": {
            "playerAP": 1,
            "playerPitchCount": 0,
            "playerHand": [
                {"cardNumber": "mangle_red", "action": 27, "actionDataOverride": "0"},
                {"cardNumber": "sink_below_blue", "action": 0, "actionDataOverride": "1"},
                {"cardNumber": "crumble_to_eternity_blue", "action": 0, "actionDataOverride": "2"},
                {"cardNumber": "fate_foreseen_red", "action": 0, "actionDataOverride": "3"},
            ],
            "playerEquipment": [
                {"cardNumber": "sledge_of_anvilheim", "action": 27, "actionDataOverride": "W1", "slot": "Weapon"},
                {"cardNumber": "crown_of_seeds", "action": 27, "actionDataOverride": "H", "slot": "Head"},
            ],
            "opponentHand": [{"cardNumber": "CardBack"}, {"cardNumber": "CardBack"}, {"cardNumber": "CardBack"}],
            "myHero": "jarl_vetreidi",
            "theirHero": "bravo_showstopper",
        },
        "legal_actions": [
            {"name": "mangle_red", "cost": 4, "mode": 27, "score": 8.5},
            {"name": "sledge_of_anvilheim", "cost": 4, "mode": 27, "score": 7.0},
            {"name": "crown_of_seeds", "cost": 1, "mode": 27, "score": 4.0},
            {"name": "pass", "cost": 0, "mode": 99, "score": 0.0},
        ],
    },
    {
        "name": "Runeblade_MultiAttack_Turn",
        "state": {
            "playerAP": 2,
            "playerPitchCount": 2,
            "playerHand": [
                {"cardNumber": "mauvrion_skies_red", "action": 27, "actionDataOverride": "0"},
                {"cardNumber": "rune_flash_red", "action": 27, "actionDataOverride": "1"},
                {"cardNumber": "spellbound_creep_blue", "action": 0, "actionDataOverride": "2"},
            ],
            "playerEquipment": [
                {"cardNumber": "rosetta_thorn", "action": 27, "actionDataOverride": "W1", "slot": "Weapon"},
                {"cardNumber": "grasp_of_the_arknight", "action": 27, "actionDataOverride": "A", "slot": "Arms"},
            ],
            "opponentHand": [{"cardNumber": "CardBack"}, {"cardNumber": "CardBack"}],
            "myHero": "vynnset_iron_maiden",
            "theirHero": "kassai_of_the_golden_sand",
        },
        "legal_actions": [
            {"name": "mauvrion_skies_red", "cost": 1, "mode": 27, "score": 9.0},
            {"name": "rune_flash_red", "cost": 0, "mode": 27, "score": 8.0},
            {"name": "rosetta_thorn", "cost": 1, "mode": 27, "score": 6.5},
            {"name": "grasp_of_the_arknight", "cost": 1, "mode": 27, "score": 5.0},
            {"name": "pass", "cost": 0, "mode": 99, "score": 0.0},
        ],
    }
]


def run_benchmark_for_engine(
    engine_type: str,
    num_simulations: int,
    num_worlds: int,
    num_threads: int,
    iterations: int,
    use_nn: bool,
    device: str
) -> Dict[str, Any]:
    """Executa o benchmark para um motor específico (MCTS ou ISMCTS)."""
    # 1. Instanciação de rede neural se solicitada
    model = None
    if use_nn:
        try:
            from ai.model import FaBPolicyValueNetwork
            model = FaBPolicyValueNetwork()
            model.to(device)
            model.eval()
        except Exception as e:
            print(f"{COLOR_YELLOW}[AVISO] Não foi possível instanciar FaBPolicyValueNetwork ({e}). Rodando sem rede.{COLOR_RESET}")
            model = None

    # 2. Instanciação do motor
    if engine_type.upper() == "MCTS":
        engine = MCTSEngine(model=model, device=device)
        def _execute_search(scen):
            return engine.search(
                state=scen["state"],
                legal_actions=scen["legal_actions"],
                num_simulations=num_simulations
            )
        rollouts_per_decision = num_simulations
    else:
        engine = ISMCTSEngine(model=model, device=device, num_worlds=num_worlds)
        def _execute_search(scen):
            return engine.search_ismcts(
                state=scen["state"],
                legal_actions=scen["legal_actions"],
                num_simulations=num_simulations
            )
        rollouts_per_decision = num_simulations * num_worlds

    # 3. Warm-up (1 ciclo para aquecer JIT / PyTorch e caches)
    try:
        _execute_search(BENCHMARK_SCENARIOS[0])
    except Exception:
        pass

    # 4. Execução do Benchmark
    latencies_ms: List[float] = []
    t_start = time.perf_counter()

    if num_threads <= 1:
        for i in range(iterations):
            scen = BENCHMARK_SCENARIOS[i % len(BENCHMARK_SCENARIOS)]
            t0 = time.perf_counter()
            _execute_search(scen)
            lat = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(lat)
    else:
        def _worker_task(idx):
            scen = BENCHMARK_SCENARIOS[idx % len(BENCHMARK_SCENARIOS)]
            t0 = time.perf_counter()
            _execute_search(scen)
            return (time.perf_counter() - t0) * 1000.0

        with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as pool:
            futures = [pool.submit(_worker_task, i) for i in range(iterations)]
            for fut in concurrent.futures.as_completed(futures):
                latencies_ms.append(fut.result())

    total_wall_time = time.perf_counter() - t_start
    total_rollouts = iterations * rollouts_per_decision
    throughput_dec_s = iterations / total_wall_time if total_wall_time > 0 else 0.0
    throughput_rollouts_s = total_rollouts / total_wall_time if total_wall_time > 0 else 0.0

    sorted_lats = sorted(latencies_ms)
    n = len(sorted_lats)

    def _percentile(p: float) -> float:
        if n == 0:
            return 0.0
        idx = int(round(p * (n - 1)))
        return sorted_lats[min(max(idx, 0), n - 1)]

    stats = {
        "engine": engine_type.upper(),
        "use_nn": bool(model is not None),
        "device": device,
        "threads": num_threads,
        "sims": num_simulations,
        "worlds": num_worlds if engine_type.upper() == "ISMCTS" else 1,
        "iterations": iterations,
        "total_time_s": round(total_wall_time, 4),
        "throughput_dec_s": round(throughput_dec_s, 2),
        "throughput_rollouts_s": round(throughput_rollouts_s, 2),
        "lat_mean_ms": round(statistics.mean(sorted_lats), 2) if sorted_lats else 0.0,
        "lat_min_ms": round(min(sorted_lats), 2) if sorted_lats else 0.0,
        "lat_max_ms": round(max(sorted_lats), 2) if sorted_lats else 0.0,
        "lat_p50_ms": round(_percentile(0.50), 2),
        "lat_p90_ms": round(_percentile(0.90), 2),
        "lat_p95_ms": round(_percentile(0.95), 2),
        "lat_p99_ms": round(_percentile(0.99), 2),
    }

    return stats


def print_table(results: List[Dict[str, Any]]) -> None:
    """Imprime tabela formatada de resultados do benchmark."""
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}   FaB Talishar AI — Benchmark de Vazão MCTS / ISMCTS (Throughput & Percentis de Latência)                             {COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════{COLOR_RESET}\n")

    header = f"{'ENGINE':<8} | {'NN':<5} | {'TH':<3} | {'SIMS':<5} | {'W':<3} | {'DEC':<4} | {'ROLLOUTS/S':<12} | {'DEC/S':<8} | {'MÉDIA':<8} | {'p50':<8} | {'p95':<8}"
    print(header)
    print("-" * len(header))

    for r in results:
        nn_str = "Sim" if r["use_nn"] else "Não"
        line = (
            f"{r['engine']:<8} | "
            f"{nn_str:<5} | "
            f"{r['threads']:<3} | "
            f"{r['sims']:<5} | "
            f"{r['worlds']:<3} | "
            f"{r['iterations']:<4} | "
            f"{COLOR_GREEN}{r['throughput_rollouts_s']:>10.1f}/s{COLOR_RESET} | "
            f"{COLOR_CYAN}{r['throughput_dec_s']:>6.2f}{COLOR_RESET} | "
            f"{r['lat_mean_ms']:>6.1f}ms | "
            f"{r['lat_p50_ms']:>6.1f}ms | "
            f"{COLOR_YELLOW}{r['lat_p95_ms']:>6.1f}ms{COLOR_RESET}"
        )
        print(line)

    print("-" * len(header))
    print(f"{COLOR_BOLD}Legenda:{COLOR_RESET} TH=Threads | SIMS=Simulações/decisão | W=Mundos ISMCTS | DEC=Decisões amostradas | Latências em milissegundos (ms).\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark de Vazão e Latência MCTS / ISMCTS para FaB Talishar AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  ./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py
  ./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py --sims 50 --worlds 4
  ./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py --threads 4 --decisions 20
  ./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py --engine ismcts --no-nn
  ./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py --json
        """
    )
    parser.add_argument(
        "--engine",
        type=str,
        default="both",
        choices=["both", "mcts", "ismcts"],
        help="Motor para benchmark: both (padrão), mcts ou ismcts."
    )
    parser.add_argument(
        "--sims",
        type=int,
        default=25,
        help="Número de simulações MCTS por decisão (padrão: 25)."
    )
    parser.add_argument(
        "--worlds",
        type=int,
        default=4,
        help="Número de mundos determinizados no ISMCTS (padrão: 4)."
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="Número de threads simultâneas para despacho de buscas (padrão: 1)."
    )
    parser.add_argument(
        "--decisions", "--iterations",
        type=int,
        dest="iterations",
        default=10,
        help="Número de decisões a avaliar no benchmark (padrão: 10)."
    )
    parser.add_argument(
        "--no-nn",
        action="store_true",
        help="Desativa inferência da rede neural, avaliando pura vazão estrutural MCTS."
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        help="Device PyTorch para o modelo: cpu (padrão) ou cuda."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Gera saída em JSON estruturado para análise ou dashboards."
    )

    args = parser.parse_args()

    engines = ["MCTS", "ISMCTS"] if args.engine == "both" else [args.engine.upper()]
    results = []

    for eng in engines:
        res = run_benchmark_for_engine(
            engine_type=eng,
            num_simulations=args.sims,
            num_worlds=args.worlds,
            num_threads=args.threads,
            iterations=args.iterations,
            use_nn=not args.no_nn,
            device=args.device
        )
        results.append(res)

    if args.output_json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print_table(results)

    return 0


if __name__ == "__main__":
    sys.exit(main())
