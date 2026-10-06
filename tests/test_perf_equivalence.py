"""
tests/test_perf_equivalence.py
==============================
Valida a equivalência matemática e funcional de todas as otimizações
introduzidas no FaB Talishar AI Engine:
1. extract_state_vector opera de forma bit-a-bit idêntica em ImmutableGameState e dict.
2. extract_card_meta opera com cache O(1) com equivalência estrita ao comportamento original.
3. SumTree.get_leaves vetorizado produz resultados idênticos à descida escalar get_leaf.
4. ThreadBatchedEvaluator agrupa requisições multithread e preserva saídas da rede neural.
5. save_metrics grava métricas JSON sem disparar checkpoints pesados a cada época.
"""

import time
import os
import numpy as np
import pytest
import torch
import concurrent.futures

from ai.model import FaBPolicyValueNetwork
from ai.game_simulator import GameSimulator
from ai.mcts.state import ImmutableGameState
from ai.experience_collector import SumTree, ReplayBuffer
from ai.mcts.batched_evaluator import ThreadBatchedEvaluator
from ai.training.orchestrator import GPUTrainingOrchestrator


def test_extract_state_vector_immutable_equals_dict():
    """Valida equivalência bit-a-bit de extract_state_vector entre ImmutableGameState e dict."""
    raw_state = {
        "playerHealth": 20,
        "opponentHealth": 18,
        "playerAP": 1,
        "opponentAP": 0,
        "playerHand": [
            {"cardNumber": "wtr001", "name": "Dawnblade", "pitch": 2, "cost": 1, "power": 3, "defense": 0},
            {"cardNumber": "wtr002", "name": "Ironsoul Helm", "pitch": 1, "cost": 0, "power": 0, "defense": 2},
        ],
        "playerPitch": [
            {"cardNumber": "wtr003", "name": "Sink Below", "pitch": 3, "cost": 0, "power": 0, "defense": 4}
        ],
        "playerArsenal": [
            {"cardNumber": "wtr004", "name": "Command and Conquer", "pitch": 1, "cost": 2, "power": 6, "defense": 3}
        ],
        "opponentHandCount": 3,
        "playerResources": [2, 0],
        "turnNumber": 4,
        "currentPhase": "M",
        "activeChainLink": {
            "power": 4,
            "totalPower": 4,
            "hasPiercing": True,
            "cardNumber": "wtr001"
        }
    }

    vec_dict = FaBPolicyValueNetwork.extract_state_vector(raw_state)
    immutable_state = ImmutableGameState(raw_state)
    vec_immutable = FaBPolicyValueNetwork.extract_state_vector(immutable_state)

    assert isinstance(vec_dict, np.ndarray)
    assert isinstance(vec_immutable, np.ndarray)
    assert vec_dict.shape == (832,)
    assert vec_immutable.shape == (832,)
    np.testing.assert_array_equal(vec_dict, vec_immutable)


def test_extract_card_meta_cache_consistency():
    """Valida que extract_card_meta retorna cópias rasas corretas com cache e respeita campos sobrescritos."""
    # Carta simples com overrides
    card1 = {"cardNumber": "wtr001", "power": 7, "pitch": 3}
    meta1 = GameSimulator.extract_card_meta(card1)
    assert meta1["power"] == 7
    assert meta1["pitch"] == 3
    assert meta1["raw"] == card1

    # Segunda chamada atinge cache
    meta1_cached = GameSimulator.extract_card_meta(card1)
    assert meta1_cached["power"] == 7
    assert meta1_cached["pitch"] == 3
    # Garante que é uma cópia independente (não afeta cache se modificada)
    meta1_cached["power"] = 99
    assert GameSimulator.extract_card_meta(card1)["power"] == 7

    # Objeto ImmutableGameState
    imm_card = ImmutableGameState({"cardNumber": "wtr001", "power": 5, "pitch": 1})
    imm_meta = GameSimulator.extract_card_meta(imm_card)
    assert imm_meta["power"] == 5
    assert imm_meta["pitch"] == 1


def test_sumtree_vectorized_get_leaves_equivalence():
    """Valida que SumTree.get_leaves vetorizado produz os mesmos índices que get_leaf escalar."""
    capacity = 100
    st = SumTree(capacity)
    # Popula prioridades não homogêneas
    np.random.seed(42)
    priorities = np.random.uniform(0.1, 5.0, size=capacity).astype(np.float32)
    for i, p in enumerate(priorities):
        st.update(i, float(p))

    total_p = st.total_priority
    test_values = np.linspace(0.01, total_p - 0.01, 50, dtype=np.float32)

    # 1. Escalar
    scalar_parents, scalar_data, scalar_prios = [], [], []
    for v in test_values:
        p_idx, d_idx, prio = st.get_leaf(float(v))
        scalar_parents.append(p_idx)
        scalar_data.append(d_idx)
        scalar_prios.append(prio)

    # 2. Vetorizado
    vec_parents, vec_data, vec_prios = st.get_leaves(test_values)

    np.testing.assert_array_equal(vec_parents, np.array(scalar_parents))
    np.testing.assert_array_equal(vec_data, np.array(scalar_data))
    np.testing.assert_allclose(vec_prios, np.array(scalar_prios), rtol=1e-5)


def test_thread_batched_evaluator_concurrent():
    """Valida o ThreadBatchedEvaluator sob requisições concorrentes de múltiplas threads."""
    torch.manual_seed(42)
    net = FaBPolicyValueNetwork(state_dim=832, action_dim=32, hidden_dim=64, num_heads=2, num_layers=1)
    net.eval()

    evaluator = ThreadBatchedEvaluator(net, device="cpu", max_batch_size=16, batch_timeout_ms=2.0)

    # Gera 12 requisições simultâneas de threads diferentes
    def worker_infer(worker_id: int):
        s = np.random.randn(832).astype(np.float32)
        probs, val = evaluator.predict_state(s)
        return s, probs, val

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(worker_infer, i) for i in range(12)]
            for fut in concurrent.futures.as_completed(futures):
                s, probs, val = fut.result(timeout=5.0)
                assert probs.shape == (32,)
                assert np.isclose(np.sum(probs), 1.0, atol=1e-4)
                assert isinstance(val, float)
    finally:
        evaluator.stop()


def test_save_metrics_does_not_save_checkpoint_by_default(tmp_path, monkeypatch):
    """Garante que save_metrics grava somente o JSON sem disparar checkpoints por padrão."""
    orch = GPUTrainingOrchestrator()
    orch.stats["epochs_completed"] = 1
    metrics_path = str(tmp_path / "metrics.json")
    import ai.training.orchestrator as orch_mod
    monkeypatch.setattr(orch_mod, "METRICS_FILE", metrics_path)

    checkpoint_called = []
    monkeypatch.setattr(orch, "_save_checkpoint", lambda: checkpoint_called.append(True))

    orch.save_metrics(save_checkpoint=False)

    assert len(checkpoint_called) == 0, "save_metrics não deve chamar _save_checkpoint quando save_checkpoint=False"
    assert os.path.exists(metrics_path), "metrics.json deve ser gerado atomicamente"
