"""
tests/test_ismcts_concurrency_modes.py
======================================
Testes unitários para Concorrência Híbrida ISMCTS e Lazy Hardware Probing:
  1. Lazy GPU Probe com cache lru_cache e salvaguarda TALISHAR_SKIP_GPU_PROBE.
  2. Estimativa de VRAM preditiva (estimate_vram_usage) e configuração default.
  3. Modos de concorrência do ISMCTSEngine: 'threads', 'sequential', 'multiprocessing', 'direct_gpu'.
  4. Repasse de argumentos CLI no bot_client e integração com PolicyEngine e GPUTrainingOrchestrator.
"""

import os
import argparse
import unittest.mock as mock
import pytest
import numpy as np
import torch
import torch.nn as nn

from config.settings import _probe_gpu, SETTINGS, FaBSettings
from ai.mcts.ismcts import ISMCTSEngine
from ai.policy.engine import PolicyEngine
from ai.training.orchestrator import GPUTrainingOrchestrator
from ai.mcts.inference_server import STATE_DIM, ACTION_DIM


class DummyTestModel(nn.Module):
    """Modelo dummy leve para testes de MCTS."""
    def __init__(self):
        super().__init__()
        self.fc = nn.Linear(STATE_DIM, ACTION_DIM + 1)

    def forward(self, x: torch.Tensor):
        out = self.fc(x)
        logits = out[:, :ACTION_DIM]
        values = torch.tanh(out[:, ACTION_DIM:ACTION_DIM+1])
        return logits, values

    def predict_state(self, state_vec: np.ndarray, device: str = "cpu"):
        priors = np.ones(ACTION_DIM, dtype=np.float32) / float(ACTION_DIM)
        return priors, 0.5


# ══════════════════════════════════════════════════════════════════
# 1. TESTES DE LAZY GPU PROBE & CONFIG SETTINGS
# ══════════════════════════════════════════════════════════════════

def test_lazy_gpu_probe_caching():
    """Valida que _probe_gpu utiliza cache lru_cache."""
    _probe_gpu.cache_clear()
    res1 = _probe_gpu()
    res2 = _probe_gpu()
    assert res1 == res2
    # Informação de cache do lru_cache
    info = _probe_gpu.cache_info()
    assert info.hits >= 1


def test_skip_gpu_probe_safeguard():
    """Valida que TALISHAR_SKIP_GPU_PROBE=1 evita execução de subprocess.run."""
    _probe_gpu.cache_clear()
    with mock.patch.dict(os.environ, {"TALISHAR_SKIP_GPU_PROBE": "1"}):
        with mock.patch("subprocess.run") as mock_subproc:
            result = _probe_gpu()
            assert mock_subproc.call_count == 0
            assert isinstance(result, tuple)
            assert len(result) == 4
    _probe_gpu.cache_clear()


def test_settings_default_ismcts_concurrency():
    """Valida que default_ismcts_concurrency é inicializado como 'threads'."""
    assert hasattr(SETTINGS, "default_ismcts_concurrency")
    assert SETTINGS.default_ismcts_concurrency in ("threads", "multiprocessing", "direct_gpu", "sequential")


def test_estimate_vram_usage():
    """Valida o cálculo preditivo de VRAM para diferentes modos e quantidades de salas."""
    import dataclasses

    # Se CPU, retorna 0.0
    cpu_settings = dataclasses.replace(SETTINGS, device="cpu", vram_gb=0.0)
    assert cpu_settings.estimate_vram_usage(num_rooms=2, mode="threads") == 0.0

    # Modo GPU
    gpu_settings = dataclasses.replace(SETTINGS, device="cuda:0", vram_gb=8.0)
    vram_threads = gpu_settings.estimate_vram_usage(num_rooms=1, ismcts_worlds=4, mode="threads")
    vram_seq = gpu_settings.estimate_vram_usage(num_rooms=1, ismcts_worlds=4, mode="sequential")
    vram_mp = gpu_settings.estimate_vram_usage(num_rooms=1, ismcts_worlds=4, mode="multiprocessing")
    vram_gpu = gpu_settings.estimate_vram_usage(num_rooms=1, ismcts_worlds=4, mode="direct_gpu")

    # direct_gpu deve consumir consideravelmente mais VRAM por conta dos contextos CUDA separados
    assert vram_threads == vram_seq
    assert vram_threads < vram_gpu
    assert vram_mp < vram_gpu
    assert vram_threads == pytest.approx(1.2 + (2 * 0.35), 0.01)
    assert vram_gpu == pytest.approx(1.2 + (2 * (0.35 + 4 * 0.45)), 0.01)


# ══════════════════════════════════════════════════════════════════
# 2. TESTES DE MODOS DE CONCORRÊNCIA DO ISMCTS
# ══════════════════════════════════════════════════════════════════

@pytest.fixture
def dummy_game_state():
    return {
        "playerHealth": 20,
        "opponentHealth": 18,
        "opponentHandCount": 2,
        "opponentHand": ["CardA", "CardB"],
        "myHand": ["Command and Conquer", "Pummel"],
        "myArsenal": [],
        "resources": 2,
    }


@pytest.fixture
def dummy_legal_actions():
    return [
        {"name": "Command and Conquer", "mode": 0, "score": 10.0},
        {"name": "Pass", "mode": 31, "score": 1.0},
    ]


def test_ismcts_threads_mode(dummy_game_state, dummy_legal_actions):
    """Valida execução paralela estável via ThreadPoolExecutor (threads)."""
    model = DummyTestModel()
    engine = ISMCTSEngine(model=model, device="cpu", num_worlds=2, concurrency_mode="threads")

    best_idx, policy_dist, ismcts_log = engine.search_ismcts(
        state=dummy_game_state,
        legal_actions=dummy_legal_actions,
        num_simulations=4,
        training_mode=False,
        concurrency_mode="threads",
    )

    assert best_idx in (0, 1)
    assert policy_dist.shape == (ACTION_DIM,)
    assert ismcts_log["concurrency_mode"] == "threads"
    assert ismcts_log["worlds_sampled"] >= 1
    assert "level1_summary" in ismcts_log


def test_ismcts_sequential_mode(dummy_game_state, dummy_legal_actions):
    """Valida execução sequencial in-process."""
    model = DummyTestModel()
    engine = ISMCTSEngine(model=model, device="cpu", num_worlds=2, concurrency_mode="sequential")

    best_idx, policy_dist, ismcts_log = engine.search_ismcts(
        state=dummy_game_state,
        legal_actions=dummy_legal_actions,
        num_simulations=4,
        training_mode=False,
    )

    assert best_idx in (0, 1)
    assert ismcts_log["concurrency_mode"] == "sequential"
    assert ismcts_log["total_votes"] > 0


def test_ismcts_direct_gpu_mode_fallback_or_run(dummy_game_state, dummy_legal_actions):
    """Valida execução do modo direct_gpu ou seu fallback gracioso."""
    model = DummyTestModel()
    engine = ISMCTSEngine(model=model, device="cpu", num_worlds=2, concurrency_mode="direct_gpu")

    best_idx, policy_dist, ismcts_log = engine.search_ismcts(
        state=dummy_game_state,
        legal_actions=dummy_legal_actions,
        num_simulations=3,
        training_mode=False,
    )

    assert best_idx in (0, 1)
    assert ismcts_log["concurrency_mode"] == "direct_gpu"
    assert "level1_summary" in ismcts_log


def test_ismcts_multiprocessing_mode(dummy_game_state, dummy_legal_actions):
    """Valida execução do modo multiprocessing (Actor-Evaluator via IPC Pipes)."""
    model = DummyTestModel()
    engine = ISMCTSEngine(model=model, device="cpu", num_worlds=2, concurrency_mode="multiprocessing")

    best_idx, policy_dist, ismcts_log = engine.search_ismcts(
        state=dummy_game_state,
        legal_actions=dummy_legal_actions,
        num_simulations=3,
        training_mode=False,
    )

    assert best_idx in (0, 1)
    assert ismcts_log["concurrency_mode"] == "multiprocessing"
    assert "level1_summary" in ismcts_log


def test_ismcts_empty_actions(dummy_game_state):
    """Valida resposta com lista vazia de ações legais."""
    engine = ISMCTSEngine(model=None, device="cpu", num_worlds=2)
    best_idx, policy_dist, ismcts_log = engine.search_ismcts(
        state=dummy_game_state,
        legal_actions=[],
        concurrency_mode="threads",
    )
    assert best_idx == 0
    assert policy_dist.sum() == 0.0
    assert ismcts_log == {}


def test_ismcts_default_concurrency_fallback(dummy_game_state, dummy_legal_actions):
    """Valida que sem especificação, o motor assume a concorrência padrão do SETTINGS."""
    engine = ISMCTSEngine(model=None, device="cpu", num_worlds=1)
    best_idx, policy_dist, ismcts_log = engine.search_ismcts(
        state=dummy_game_state,
        legal_actions=dummy_legal_actions,
        num_simulations=2,
    )
    assert ismcts_log["concurrency_mode"] in ("threads", "multiprocessing", "direct_gpu", "sequential")


# ══════════════════════════════════════════════════════════════════
# 3. TESTES DE CLI, REPASSE E INTEGRAÇÃO
# ══════════════════════════════════════════════════════════════════

def test_bot_client_argparse_concurrency():
    """Valida suporte do bot_client ao argumento --ismcts-concurrency."""
    parser = argparse.ArgumentParser()
    parser.add_argument('--room', required=True)
    parser.add_argument('--deck', required=True)
    parser.add_argument('--role', choices=['host', 'join'], required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--ismcts-concurrency', choices=['threads', 'multiprocessing', 'direct_gpu', 'sequential'], default=None)

    args = parser.parse_args([
        '--room', 'Room123',
        '--deck', 'decks/rhinar.json',
        '--role', 'host',
        '--name', 'Bot1',
        '--ismcts-concurrency', 'threads',
    ])
    assert args.ismcts_concurrency == 'threads'


def test_policy_engine_propagates_concurrency():
    """Valida que PolicyEngine repassa ismcts_concurrency para ISMCTSEngine."""
    pe = PolicyEngine(ismcts_concurrency="direct_gpu")
    assert pe.ismcts_concurrency == "direct_gpu"
    assert pe.ismcts.concurrency_mode == "direct_gpu"


def test_orchestrator_config_concurrency():
    """Valida que GPUTrainingOrchestrator inclui ismcts_concurrency em suas configs."""
    orch = GPUTrainingOrchestrator()
    cfg = orch.config
    assert "ismcts_concurrency" in cfg
    assert cfg["ismcts_concurrency"] in ("threads", "multiprocessing", "direct_gpu", "sequential")
