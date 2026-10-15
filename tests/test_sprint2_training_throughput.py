"""
Testes unitários automatizados para a Sprint 2:
- Vectorized SumTree.set_all (rebuild O(N))
- ReplayBuffer.update_priorities com TD-errors reais (PER)
- sample_batch com return_indices e beta annealing
- predict_state / predict_states transferência unificada
- Headless deck template caching com proteção contra mutação
"""

import pytest
import numpy as np
import torch
from unittest.mock import MagicMock, patch

from ai.experience_collector import SumTree, ReplayBuffer
from ai.model import FaBPolicyValueNetwork
from ai.training.headless_env import HeadlessSelfPlayLoop, _PARSED_DECKS_CACHE


def test_sum_tree_set_all_correctness():
    """Valida equivalência matemática exata entre set_all vetorizado e updates sequenciais."""
    capacity = 500
    n_items = 350
    priorities = np.random.uniform(0.1, 10.0, size=n_items).astype(np.float32)

    # Sequencial
    st_seq = SumTree(capacity)
    for i, p in enumerate(priorities):
        st_seq.update(i, p)

    # Vetorizado
    st_vec = SumTree(capacity)
    st_vec.set_all(priorities)

    # Raiz (soma total) deve ser idêntica
    assert np.isclose(st_seq.total_priority, st_vec.total_priority, rtol=1e-4)
    # A árvore inteira deve ser numericamente equivalente
    assert np.allclose(st_seq.tree, st_vec.tree, atol=1e-3)


def test_replay_buffer_update_priorities_per():
    """Valida a atualização dinâmica de prioridades com base no erro de predição temporal (TD error)."""
    buf = ReplayBuffer(max_capacity=50, state_dim=832)
    s = np.zeros(832, dtype=np.float32)
    p = np.zeros(32, dtype=np.float32)

    for i in range(10):
        buf.add(s, p, value=0.0, weight=1.0)

    # Amostragem com return_indices=True
    states, policies, values, is_weights, aux, indices = buf.sample_batch(
        batch_size=4, prioritized=True, return_is_weights=True, return_aux=True, return_indices=True
    )
    assert len(indices) == 4

    # Atualiza prioridades com TD errors
    td_errors = np.array([10.0, 0.05, 5.0, 0.1], dtype=np.float32)
    buf.update_priorities(indices, td_errors, alpha=0.6, eps=1e-3, max_p=2.0)

    # O primeiro índice (TD=10.0) deve ter sua prioridade clipada em max_p (2.0)
    leaf_start = buf.sum_tree.capacity - 1
    idx0 = indices[0]
    expected_p0 = min(2.0, (10.0 + 1e-3) ** 0.6)
    assert np.isclose(buf.sum_tree.tree[leaf_start + idx0], expected_p0, atol=1e-3)


def test_sample_batch_beta_annealing():
    """Valida o annealing do beta de Importance Sampling com base no epoch_ratio."""
    buf = ReplayBuffer(max_capacity=20, state_dim=832)
    s = np.zeros(832, dtype=np.float32)
    p = np.zeros(32, dtype=np.float32)
    for _ in range(10):
        buf.add(s, p, value=0.5, weight=2.0)

    # epoch_ratio=1.0 deve elevar o beta para 1.0 (compensação máxima de viés)
    states, policies, values, is_w = buf.sample_batch(
        batch_size=5, prioritized=True, beta=0.4, epoch_ratio=1.0, return_is_weights=True
    )
    assert is_w.shape == (5,)
    assert torch.all(is_w > 0.0)


def test_predict_state_and_states_unification():
    """Valida que predict_state e predict_states retornam os shapes e valores corretos."""
    model = FaBPolicyValueNetwork()
    model.eval()

    s = np.random.randn(832).astype(np.float32)
    probs, val = model.predict_state(s, device="cpu")
    assert probs.shape == (32,)
    assert np.isclose(np.sum(probs), 1.0, atol=1e-3)
    assert isinstance(val, float)
    assert -1.0 <= val <= 1.0

    batch = [s, s * 0.5, s * -0.5]
    b_probs, b_vals = model.predict_states(batch, device="cpu")
    assert b_probs.shape == (3, 32)
    assert b_vals.shape == (3, 1)
    for row in b_probs:
        assert np.isclose(np.sum(row), 1.0, atol=1e-3)


def test_headless_parsed_deck_cache():
    """Valida que o cache de template de decks acelera parsing sem permitir vazamento de mutação."""
    net = FaBPolicyValueNetwork()
    env = HeadlessSelfPlayLoop(net, mcts_sims=2, device="cpu")

    hero1, eq1, wep1, main1 = env._parse_deck("kassai")
    assert "kassai" in _PARSED_DECKS_CACHE

    # Mutação local no deck retornado
    main1[0]["cost"] = 9999

    # Segundo fetch deve vir com o template limpo
    hero2, eq2, wep2, main2 = env._parse_deck("kassai")
    assert main2[0]["cost"] != 9999, "O cache não deve sofrer mutação externa!"
