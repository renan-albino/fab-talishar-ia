"""
scripts/bench_engine.py
=======================
Benchmark de baseline para medir latência MCTS/ISMCTS, throughput de headless
e performance do Replay Buffer (PER) no FaB Talishar AI Engine.
"""

import os
import sys
import time
import numpy as np
import torch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai.model import FaBCardTransformerNetwork, get_device
from ai.mcts.ismcts import ISMCTSEngine
from ai.training.headless_env import HeadlessSelfPlayLoop
from ai.experience_collector import ReplayBuffer
from ai.mcts.state import ImmutableGameState


def bench_mcts(num_decisions: int = 25, num_sims: int = 25, num_worlds: int = 4):
    print(f"\n[Bench 1/3] Testando ISMCTS ({num_decisions} decisões, {num_worlds} mundos, {num_sims} sims)...")
    device = get_device()
    model = FaBCardTransformerNetwork().to(device)
    model.eval()

    forward_count = 0
    orig_forward = model.forward

    def counting_forward(*args, **kwargs):
        nonlocal forward_count
        forward_count += 1
        return orig_forward(*args, **kwargs)

    model.forward = counting_forward

    engine = ISMCTSEngine(
        model=model,
        num_worlds=num_worlds,
        device=device,
        concurrency_mode="sequential"
    )

    # Cria estado sintetizado típico de combate
    raw_state = {
        "playerHealth": 20,
        "opponentHealth": 18,
        "playerResources": [2, 2],
        "playerAP": 1,
        "turnPhase": "M",
        "combatChain": [],
        "playerHand": [
            {"cardNumber": "WTR001", "name": "Snatch", "pitch": 1, "cost": 0, "power": 4},
            {"cardNumber": "WTR002", "name": "Razor Reflex", "pitch": 1, "cost": 1, "power": 3},
            {"cardNumber": "WTR003", "name": "Energy Potion", "pitch": 3, "cost": 0, "power": 0},
        ],
        "opponentHandCount": 4,
        "opponentHero": "rhinar",
        "yourHero": "kassai",
        "actionPoints": 1,
    }
    state = ImmutableGameState(raw_state)
    legal_actions = [
        {"type": "attack", "card_name": "Snatch", "card_index": 0, "mode": 1},
        {"type": "play", "card_name": "Energy Potion", "card_index": 2, "mode": 2},
        {"type": "pitch", "card_name": "Energy Potion", "card_index": 2, "mode": 3},
        {"type": "pass", "mode": 0},
    ]

    # Warmup
    _ = engine.search_ismcts(state, legal_actions, num_simulations=num_sims)
    forward_count = 0

    latencies = []
    t_start = time.perf_counter()
    for _ in range(num_decisions):
        t0 = time.perf_counter()
        _ = engine.search_ismcts(state, legal_actions, num_simulations=num_sims)
        latencies.append((time.perf_counter() - t0) * 1000.0)
    total_time = time.perf_counter() - t_start

    p50 = float(np.percentile(latencies, 50))
    p95 = float(np.percentile(latencies, 95))
    fps = num_decisions / total_time
    forwards_per_decision = forward_count / num_decisions

    print(f"  -> Latência p50: {p50:.2f} ms | p95: {p95:.2f} ms")
    print(f"  -> Decisões/seg: {fps:.2f} dec/s")
    print(f"  -> Forward passes por decisão: {forwards_per_decision:.1f}")
    return {"p50_ms": p50, "p95_ms": p95, "dec_per_sec": fps, "forwards_per_dec": forwards_per_decision}


def bench_headless(num_games: int = 5):
    print(f"\n[Bench 2/3] Testando Headless Self-Play ({num_games} partidas rápidas)...")
    device = get_device()
    model = FaBCardTransformerNetwork().to(device)
    model.eval()

    loop = HeadlessSelfPlayLoop(model=model, mcts_sims=8, device=device)

    t0 = time.perf_counter()
    total_steps = 0
    completed = 0
    for g in range(num_games):
        try:
            traj, winner = loop.play_game("kassai", "boltyn")
            total_steps += len(traj)
            completed += 1
        except Exception as e:
            print(f"  -> Partida {g+1} erro: {e}")

    elapsed = time.perf_counter() - t0
    games_per_min = (completed / elapsed) * 60.0 if elapsed > 0 else 0
    steps_per_sec = total_steps / elapsed if elapsed > 0 else 0

    print(f"  -> Partidas completadas: {completed}/{num_games} em {elapsed:.2f}s")
    print(f"  -> Throughput: {games_per_min:.2f} partidas/min")
    print(f"  -> Decisões de jogo: {steps_per_sec:.2f} steps/s")
    return {"games_per_min": games_per_min, "steps_per_sec": steps_per_sec}


def bench_buffer():
    print("\n[Bench 3/3] Testando Replay Buffer (PER / SumTree)...")
    buffer = ReplayBuffer(max_capacity=50000)

    # Inserção sintética
    dummy_state = np.random.randn(832).astype(np.float32)
    dummy_policy = np.zeros(32, dtype=np.float32)
    dummy_policy[0] = 1.0

    t0 = time.perf_counter()
    for _ in range(1000):
        buffer.add(dummy_state, dummy_policy, 1.0, 1.0, 1)
    insert_1k = (time.perf_counter() - t0) * 1000.0

    # Amostragem
    t0 = time.perf_counter()
    for _ in range(50):
        _ = buffer.sample_batch(batch_size=64, device="cpu", prioritized=True, return_is_weights=True)
    sample_50 = (time.perf_counter() - t0) * 1000.0

    print(f"  -> Inserção de 1k amostras: {insert_1k:.2f} ms")
    print(f"  -> 50 amostragens em lote (batch 64): {sample_50:.2f} ms")
    return {"insert_1k_ms": insert_1k, "sample_50_ms": sample_50}


def main():
    print("=" * 60)
    print("FaB Talishar AI Engine — Benchmark de Desempenho (Baseline)")
    print("=" * 60)
    res_mcts = bench_mcts()
    res_headless = bench_headless()
    res_buffer = bench_buffer()
    print("\n" + "=" * 60)
    print("Resumo do Baseline:")
    print(f"  ISMCTS: {res_mcts['dec_per_sec']:.1f} dec/s ({res_mcts['p50_ms']:.1f} ms p50) | {res_mcts['forwards_per_dec']:.1f} forwards/dec")
    print(f"  Headless: {res_headless['games_per_min']:.1f} jogos/min ({res_headless['steps_per_sec']:.1f} steps/s)")
    print(f"  Buffer: 1k insert em {res_buffer['insert_1k_ms']:.1f} ms | 50 samples em {res_buffer['sample_50_ms']:.1f} ms")
    print("=" * 60)


if __name__ == "__main__":
    main()
