"""
tests/test_dynamic_learning_and_per.py
======================================
Testes unitários para:
  1. Recompensa Densa (Reward Shaping) e Prioritized Experience Replay (PER).
  2. Módulo de Revisão Automática de Blunders (ai/blunder_reviewer.py).
  3. Auto-Tuning Dinâmico de Multiplicadores Heurísticos por Herói (ai/dynamic_rule_tuner.py).
"""

import os
import sys
import json
import tempfile
import numpy as np
import pytest
import torch

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai.experience_collector import ReplayBuffer
from ai.model import STATE_DIM
from ai.blunder_reviewer import review_trajectory_for_blunders
from ai.dynamic_rule_tuner import (
    get_multipliers_for_hero,
    sync_multipliers_with_stats,
    DEFAULT_MULTIPLIERS,
    MULTIPLIERS_FILE,
)
from ai.hero_strategies.base import HeroStrategy


def test_replay_buffer_dense_reward_shaping():
    """Valida o cálculo de recompensa densa no ReplayBuffer."""
    buffer = ReplayBuffer(max_capacity=100)

    dummy_state = np.zeros(STATE_DIM, dtype=np.float32)
    dummy_policy = np.zeros(32, dtype=np.float32)
    dummy_policy[0] = 1.0

    # Trajetória com board_eval positivo e vitória
    # board_eval = +10.0 -> tanh(1.0) ~= 0.7616
    # expected reward = 0.6 * 1.0 + 0.4 * 0.7616 ~= 0.9046
    traj_win = [
        (dummy_state, dummy_policy, 1, 10.0),
        (dummy_state, dummy_policy, 1, -5.0),  # board_eval negativo mesmo com vitória
    ]
    buffer.add_trajectory(traj_win, winner_player_id=1)

    assert buffer.current_size == 2
    val_step0 = buffer.values[0, 0]
    val_step1 = buffer.values[1, 0]

    assert 0.85 <= val_step0 <= 0.95
    # Step 1: 0.6 * 1.0 + 0.4 * tanh(-0.5) ~= 0.6 - 0.185 = ~0.415
    assert 0.35 <= val_step1 <= 0.50


def test_replay_buffer_prioritized_sampling():
    """Valida amostragem ponderada (PER)."""
    buffer = ReplayBuffer(max_capacity=100)
    dummy_state = np.zeros(STATE_DIM, dtype=np.float32)
    dummy_policy = np.zeros(32, dtype=np.float32)

    # Adiciona 10 amostras com peso 0.01 e 1 amostra com peso 100.0 no índice 5
    for i in range(10):
        buffer.add(dummy_state, dummy_policy, 0.0, weight=0.01)
    buffer.add(dummy_state, dummy_policy, 1.0, weight=100.0)

    # Ao amostrar batch, a amostra com peso 100 deve ser selecionada na grande maioria das vezes
    np.random.seed(42)
    _, _, sampled_values = buffer.sample_batch(batch_size=20, prioritized=True)
    val_list = sampled_values.squeeze(-1).numpy().tolist()

    # O valor 1.0 (peso 100) deve dominar as amostras
    assert val_list.count(1.0) >= 15


def test_replay_buffer_save_load_weights(tmp_path):
    """Valida persistência dos pesos PER no arquivo npz."""
    save_file = str(tmp_path / "test_buffer.npz")
    buf1 = ReplayBuffer(max_capacity=50)

    s = np.ones(STATE_DIM, dtype=np.float32)
    p = np.zeros(32, dtype=np.float32)
    buf1.add(s, p, 0.5, weight=4.2)
    buf1.add(s, p, -0.5, weight=1.8)
    buf1.save(save_file)

    buf2 = ReplayBuffer(max_capacity=50)
    loaded = buf2.load(save_file)

    assert loaded is True
    assert buf2.current_size == 2
    assert pytest.approx(buf2.sum_tree.tree[buf2.sum_tree.capacity - 1 + 0], 0.01) == 4.2
    assert pytest.approx(buf2.sum_tree.tree[buf2.sum_tree.capacity - 1 + 1], 0.01) == 1.8


def test_replay_buffer_importance_sampling_weights():
    """
    Valida o cálculo dos pesos de Importance Sampling normalizados w_i = (N * P(i))^(-beta) / max(w)
    garantindo que o viés de superamostragem do PER seja compensado no gradiente.
    """
    buffer = ReplayBuffer(max_capacity=50, state_dim=STATE_DIM)
    dummy_s = np.zeros(STATE_DIM, dtype=np.float32)
    dummy_p = np.zeros(32, dtype=np.float32)

    # Amostras com pesos variados
    for i in range(10):
        buffer.add(dummy_s, dummy_p, 0.0, weight=1.0)
    buffer.add(dummy_s, dummy_p, 1.0, weight=10.0)

    states, policies, values, is_weights = buffer.sample_batch(
        batch_size=15, prioritized=True, beta=0.6, return_is_weights=True
    )

    assert states.shape == (15, STATE_DIM)
    assert is_weights.shape == (15,)
    # Pesos normalizados devem estar no intervalo (0, 1]
    assert torch.all(is_weights > 0.0)
    assert torch.all(is_weights <= 1.00001)
    # A amostra de maior peso (10.0) é a mais provável, logo deve receber menor peso IS
    assert float(torch.min(is_weights)) < float(torch.max(is_weights))


def test_blunder_reviewer():
    """Valida a identificação de blunders e atribuição de pesos."""
    s = np.zeros(STATE_DIM, dtype=np.float32)
    p = np.zeros(32, dtype=np.float32)

    # Trajetória:
    # Passo 0: eval = +4.0
    # Passo 1: eval = -2.0 (queda de 6.0 pontos -> BLUNDER severo!)
    # Passo 2: eval = -1.0
    # Passo 3: eval = +3.0 (virada de 4.0 pontos -> LANCE BRILHANTE)
    trajectory = [
        (s, p, 1, 4.0),
        (s, p, 1, -2.0),
        (s, p, 1, -1.0),
        (s, p, 1, 3.0),
    ]

    weights, stats = review_trajectory_for_blunders(
        trajectory,
        winner_player_id=2,  # Bot 1 perdeu
        bot_player_id=1,
    )

    assert len(weights) == 4
    assert stats["blunders"] >= 1
    assert stats["brilliants"] >= 1
    # O passo 0 provocou a queda drástica para -2.0
    assert weights[0] == 3.5
    # Por ter perdido, os últimos passos ganham no mínimo 2.5
    assert weights[-1] >= 2.0


def test_dynamic_rule_tuner_and_hero_strategy(monkeypatch, tmp_path):
    """Valida o auto-tuning dos multiplicadores por taxa de vitória e consumo no HeroStrategy."""
    fake_mults_file = str(tmp_path / "hero_rule_multipliers.json")
    monkeypatch.setattr("ai.dynamic_rule_tuner.MULTIPLIERS_FILE", fake_mults_file)

    # Simula dados de partidas:
    # "Guardian Underperforming": 1 vitória, 9 derrotas (win rate 10%)
    # "Ninja Dominant": 9 vitórias, 1 derrota (win rate 90%)
    fake_stats = {
        "deck_stats": {
            "guardian_struggling": {"matches": 10, "wins": 1, "losses": 9},
            "ninja_winning": {"matches": 10, "wins": 9, "losses": 1},
        }
    }
    monkeypatch.setattr("stats_manager.get_stats_data", lambda: fake_stats)

    updates = sync_multipliers_with_stats()

    assert "guardian_struggling" in updates
    assert "ninja_winning" in updates

    # Herói com dificuldades deve ter aumentado a defesa
    g_mults = get_multipliers_for_hero("guardian_struggling")
    assert g_mults["block_weight"] > 1.0
    assert g_mults["pivot_bonus"] > 1.0

    # Herói dominante deve ter aumentado o ataque
    n_mults = get_multipliers_for_hero("ninja_winning")
    assert n_mults["attack_weight"] > 1.0

    # Valida consumo no HeroStrategy
    strat_g = HeroStrategy("guardian_struggling")
    strat_n = HeroStrategy("ninja_winning")

    # Ataque base 6:
    atk_score_g = strat_g.evaluate_attack_card("card", power=6, cost=0, has_go_again=False, pitch=2)
    atk_score_n = strat_n.evaluate_attack_card("card", power=6, cost=0, has_go_again=False, pitch=2)

    # O herói dominante (Ninja) ataca com score maior devido ao attack_weight ampliado
    assert atk_score_n > atk_score_g

    # Bloqueio base 3:
    blk_score_g = strat_g.evaluate_block_card("card", block_val=3, pitch=2, power=0, has_go_again=False)
    blk_score_n = strat_n.evaluate_block_card("card", block_val=3, pitch=2, power=0, has_go_again=False)

    # O herói com dificuldades defensivas (Guardian) prioriza o bloqueio mais alto
    assert blk_score_g > blk_score_n


def test_replay_buffer_dynamic_resize():
    """Valida o redimensionamento em tempo de execução do ReplayBuffer preservando amostras."""
    buf = ReplayBuffer(max_capacity=10, state_dim=STATE_DIM)
    for i in range(10):
        buf.add(np.ones(STATE_DIM) * i, np.ones(32), 1.0)
    assert len(buf) == 10
    assert buf.max_capacity == 10

    # Redimensiona para 25
    buf.resize(25)
    assert buf.max_capacity == 25
    assert len(buf) == 10
    assert buf.states[0, 0] == 0.0
    assert buf.states[9, 0] == 9.0

    # Adiciona mais 5 amostras
    for i in range(10, 15):
        buf.add(np.ones(STATE_DIM) * i, np.ones(32), 1.0)
    assert len(buf) == 15
    assert buf.states[14, 0] == 14.0
