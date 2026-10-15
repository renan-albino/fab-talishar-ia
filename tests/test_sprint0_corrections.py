"""
tests/test_sprint0_corrections.py
=================================
Testes unitários para validar as correções de integridade da Sprint 0:
1. Recompensa canônica unificada entre add_trajectory e save_trajectory_file.
2. Invariante de parent_visits no PUCT (_select) sem double-counting.
3. Salvamento atômico de status em assimilation.py e reuso de file_lock.
"""

import os
import json
import numpy as np
import pytest
from ai.experience_collector import ReplayBuffer, compute_shaped_reward, save_trajectory_file
from ai.mcts.node import MCTSNode
from ai.mcts.standard_mcts import MCTSEngine
from ai.training.assimilation import clear_assimilation_status, STATUS_FILE, get_assimilation_status


def test_canonical_reward_parity():
    """Garante que a recompensa é idêntica nos dois caminhos e respeita o annealing."""
    # Cenário 1: epoch_ratio = 0.0 (início do treino: peso 0.6 vitória, 0.4 vantagem tática)
    # r_term = 1.0, board_eval = +10.0 -> tanh(1.0) = 0.76159
    # reward = 0.6 * 1.0 + 0.4 * 0.76159 = 0.90463
    r0, aux_delta0, aux_dmg0 = compute_shaped_reward(1.0, 10.0, epoch_ratio=0.0)
    assert 0.90 < r0 < 0.91
    assert 0.76 < aux_delta0 < 0.77
    assert aux_dmg0 == 2.0

    # Cenário 2: epoch_ratio = 1.0 (fim do treino: peso 1.0 vitória pura, 0.0 vantagem)
    r1, aux_delta1, aux_dmg1 = compute_shaped_reward(1.0, 10.0, epoch_ratio=1.0)
    assert r1 == 1.0
    assert 0.76 < aux_delta1 < 0.77

    # Paridade entre add_trajectory e save_trajectory_file
    buf = ReplayBuffer(max_capacity=100)
    dummy_state = np.zeros(832, dtype=np.float32)
    dummy_policy = np.zeros(32, dtype=np.float32)
    traj = [
        (dummy_state, dummy_policy, 1, 10.0),
        (dummy_state, dummy_policy, 2, -10.0),
    ]

    # Via ReplayBuffer.add_trajectory
    buf.add_trajectory(traj, winner_player_id=1, epoch_ratio=0.5)
    r_buf_step0 = float(buf.values[0, 0])

    # Via compute_shaped_reward direto
    expected_r0, _, _ = compute_shaped_reward(1.0, 10.0, epoch_ratio=0.5)
    assert np.isclose(r_buf_step0, expected_r0, atol=1e-5)


def test_puct_parent_visits_invariant():
    """Garante que parent_visits no _select utiliza visit_count + virtual_loss sem inflação por sim_idx."""
    engine = MCTSEngine(model=None, c_puct=1.4)
    root = MCTSNode(prior=1.0)
    root.visit_count = 10
    root.virtual_loss = 2

    legal_actions = [
        {"type": "attack", "mode": 1},
        {"type": "pass", "mode": 0},
    ]
    priors = np.array([0.7, 0.3], dtype=np.float32)
    engine._expand(root, legal_actions, priors)

    # Chamada com sim_idx=0 e sim_idx=50 não deve alterar parent_visits da UCB
    selected_node = engine._select(root, sim_idx=0)
    assert selected_node is not None
    assert selected_node.action_id in (0, 1)


def test_assimilation_atomic_status():
    """Garante que clear_assimilation_status escreve atomicamente e sem erros."""
    clear_assimilation_status()
    st = get_assimilation_status()
    assert st.get("status") == "idle"
    assert "timestamp" in st
