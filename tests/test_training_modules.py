"""
tests/test_training_modules.py - Testes unitários para a decomposição modular de ai/training/.
"""

import math
import os
import tempfile
import threading
from unittest.mock import MagicMock, patch

import pytest

import ai.training as trainer_facade
from ai.training import (
    GPUTrainingOrchestrator,
    RoundRobinMatchupEngine,
    get_active_pids,
    is_process_alive,
    kill_active_processes,
    kill_orphan_bots,
    wait_for_processes,
)


def test_facade_compatibility():
    """Valida que ai/trainer.py re-exporta as classes e constantes esperadas."""
    assert trainer_facade.GPUTrainingOrchestrator is GPUTrainingOrchestrator
    assert trainer_facade.RoundRobinMatchupEngine is RoundRobinMatchupEngine
    assert hasattr(trainer_facade, "DATA_DIR")
    assert hasattr(trainer_facade, "METRICS_FILE")


def test_matchup_engine_edge_cases():
    """Valida RoundRobinMatchupEngine com pools vazios, unitários e múltiplos."""
    engine = RoundRobinMatchupEngine(seed=42)

    # Pool vazio
    p_empty = engine.next_pair([])
    assert p_empty == ("calling_hamburg_1st", "calling_hamburg_1st")

    # Pool com 1 elemento
    p_single = engine.next_pair(["dash_io"])
    assert p_single == ("dash_io", "dash_io")

    # Pool com 3 elementos
    pool = ["deck_a", "deck_b", "deck_c"]
    pairs = [engine.next_pair(pool) for _ in range(6)]
    assert len(set(pairs)) == 6
    for h, j in pairs:
        assert h != j
        assert h in pool and j in pool

    stats = engine.get_stats()
    assert stats["total_pairs_dispatched"] == 6
    assert stats["unique_matchups"] == 6


def test_process_supervisor_primitives():
    """Valida utilitários de monitoramento de PID e finalização segura de processos."""
    # Mock de processos
    p1 = MagicMock()
    p1.poll.return_value = None
    p1.pid = 1001

    p2 = MagicMock()
    p2.poll.return_value = 0
    p2.pid = 1002

    # is_process_alive
    assert is_process_alive(p1) is True
    assert is_process_alive(p2) is False
    assert is_process_alive(None) is False

    # get_active_pids
    active_procs = [(p1, p2)]
    pids = get_active_pids(active_procs)
    assert pids == [1001]

    # wait_for_processes - finalização imediata
    all_done = wait_for_processes([], timeout=1.0)
    assert all_done is True

    # wait_for_processes - com processo rodando e cancelamento via flag
    running = True
    assert wait_for_processes(active_procs, timeout=0.1, is_running_check=lambda: running, check_interval=0.01) is False

    # kill_active_processes
    lock = threading.Lock()
    kill_active_processes(active_procs, proc_lock=lock)
    p1.kill.assert_called_once()
    assert len(active_procs) == 0

    # kill_orphan_bots sem disparar exceções
    kill_orphan_bots()


def test_orchestrator_singleton_and_sanitize():
    """Valida o padrão singleton e a sanitização JSON de valores float especiais."""
    orch1 = GPUTrainingOrchestrator()
    orch2 = GPUTrainingOrchestrator()
    assert orch1 is orch2

    # Sanitização de NaN e inf
    raw_data = {
        "loss": float("nan"),
        "entropy": float("inf"),
        "nested": [1.0, float("-inf"), 3.5],
        "valid": 42.0,
    }
    clean = GPUTrainingOrchestrator._sanitize_for_json(raw_data)
    assert clean["loss"] == 0.0
    assert clean["entropy"] == 0.0
    assert clean["nested"] == [1.0, 0.0, 3.5]
    assert clean["valid"] == 42.0
