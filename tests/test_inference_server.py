"""
tests/test_inference_server.py
==============================
Testes unitários para:
  1. RemoteModelProxy (interface de simulação do modelo no worker).
  2. BatchedInferenceServer (servidor de inferência em lote dinâmico via IPC Pipes).
  3. Integração ISMCTS Actor-Evaluator com retorno de Nível 1 (Escolha C).
"""

import multiprocessing as mp
import threading
import time
import numpy as np
import pytest
import torch
import torch.nn as nn

from ai.mcts.inference_server import RemoteModelProxy, BatchedInferenceServer, STATE_DIM, ACTION_DIM
from ai.mcts.ismcts import ISMCTSEngine, _extract_level1_summary
from ai.mcts.node import MCTSNode
from ai.model import FaBCardTransformerNetwork


# ══════════════════════════════════════════════════════════════════
# DUMMY MODELS PARA TESTES
# ══════════════════════════════════════════════════════════════════

class MockPolicyValueModel(nn.Module):
    """Modelo dummy previsível para testar inferência e fatiamento exato."""

    def __init__(self):
        super().__init__()
        self.dummy_param = nn.Parameter(torch.zeros(1))

    def forward(self, x: torch.Tensor, return_aux: bool = False):
        batch_size = x.shape[0]
        # Política fixa: logit decrescente 31..0 para cada item no lote
        logits = torch.arange(ACTION_DIM, 0, -1, dtype=torch.float32).unsqueeze(0).repeat(batch_size, 1)
        # Valor baseado no primeiro elemento do vetor de entrada
        values = x[:, 0:1] * 0.5
        if return_aux:
            aux = {
                "delta_hp": values.clone(),
                "turn_dmg": torch.abs(values) * 2.0,
            }
            return logits, values, aux
        return logits, values


# ══════════════════════════════════════════════════════════════════
# TESTES DO RemoteModelProxy
# ══════════════════════════════════════════════════════════════════

def test_remote_model_proxy_no_ops():
    """Valida métodos de compatibilidade de interface (eval, train, to, parameters)."""
    p_serv, p_work = mp.Pipe(duplex=True)
    try:
        proxy = RemoteModelProxy(p_work)
        assert proxy.eval() is proxy
        assert proxy.train() is proxy
        assert proxy.to("cuda:0") is proxy
        assert list(proxy.parameters()) == []
    finally:
        p_serv.close()
        p_work.close()


def test_remote_model_proxy_call_and_predict_state():
    """Valida chamadas do proxy e comunicação via Pipe simulando o servidor."""
    p_serv, p_work = mp.Pipe(duplex=True)
    proxy = RemoteModelProxy(p_work)

    def fake_server():
        msg = p_serv.recv()
        assert msg[0] == "infer"
        batch_in = msg[1]
        n = batch_in.shape[0]
        logits = np.ones((n, ACTION_DIM), dtype=np.float32) * 2.0
        values = np.ones((n, 1), dtype=np.float32) * 0.75
        aux = {"delta_hp": values * 1.0}
        p_serv.send((logits, values, aux))

    # 1. Teste predict_state
    t = threading.Thread(target=fake_server)
    t.start()
    vec = np.zeros(STATE_DIM, dtype=np.float32)
    probs, val = proxy.predict_state(vec)
    t.join()

    assert probs.shape == (ACTION_DIM,)
    assert pytest.approx(probs.sum(), 0.001) == 1.0
    assert pytest.approx(val, 0.001) == 0.75

    # 2. Teste __call__ com retorno de tensores CPU
    t = threading.Thread(target=fake_server)
    t.start()
    x = torch.zeros((2, STATE_DIM), dtype=torch.float32)
    pol_t, val_t = proxy(x, return_aux=False)
    t.join()

    assert isinstance(pol_t, torch.Tensor)
    assert isinstance(val_t, torch.Tensor)
    assert pol_t.shape == (2, ACTION_DIM)
    assert val_t.shape == (2, 1)
    assert pytest.approx(val_t[0, 0].item(), 0.001) == 0.75

    # 3. Teste __call__ com return_aux=True
    t = threading.Thread(target=fake_server)
    t.start()
    pol_t, val_t, aux_t = proxy(x, return_aux=True)
    t.join()

    assert "delta_hp" in aux_t
    assert isinstance(aux_t["delta_hp"], torch.Tensor)

    p_serv.close()
    p_work.close()


def test_remote_model_proxy_empty_inputs():
    """Valida comportamento com tensores vazios sem bloquear o pipe."""
    p_serv, p_work = mp.Pipe(duplex=True)
    proxy = RemoteModelProxy(p_work)

    pol, val = proxy(np.zeros((0, STATE_DIM), dtype=np.float32))
    assert pol.shape == (0, ACTION_DIM)
    assert val.shape == (0, 1)

    probs, vals = proxy.predict_states([])
    assert probs.shape == (0, ACTION_DIM)
    assert vals.shape == (0, 1)

    p_serv.close()
    p_work.close()


# ══════════════════════════════════════════════════════════════════
# TESTES DO BatchedInferenceServer
# ══════════════════════════════════════════════════════════════════

def test_batched_inference_server_batch_slicing():
    """
    Testa se o BatchedInferenceServer agrupa múltiplos requests
    concorrentes de diferentes pipes e fatia as respostas perfeitamente.
    """
    model = MockPolicyValueModel()
    server = BatchedInferenceServer(model=model, device="cpu", batch_timeout_ms=5.0)

    p1_s, p1_w = mp.Pipe(duplex=True)
    p2_s, p2_w = mp.Pipe(duplex=True)

    results_p1 = {}
    results_p2 = {}

    def worker1():
        # Envia batch de tamanho 2
        req = np.ones((2, STATE_DIM), dtype=np.float32) * 1.5
        p1_w.send(("infer", req))
        results_p1["infer"] = p1_w.recv()
        # Envia resumo nível 1 e conclui
        p1_w.send(("done", {"worker": 1, "status": "ok"}))

    def worker2():
        # Envia batch de tamanho 3
        req = np.ones((3, STATE_DIM), dtype=np.float32) * 2.0
        p2_w.send(("infer", req))
        results_p2["infer"] = p2_w.recv()
        p2_w.send(("done", {"worker": 2, "status": "ok"}))

    t1 = threading.Thread(target=worker1)
    t2 = threading.Thread(target=worker2)
    t1.start()
    t2.start()

    summaries = server.serve([p1_s, p2_s], timeout=5.0)

    t1.join()
    t2.join()

    # Verifica fatiamento do Worker 1 (tamanho 2)
    pol1, val1, aux1 = results_p1["infer"]
    assert pol1.shape == (2, ACTION_DIM)
    assert val1.shape == (2, 1)
    # Valor esperado: 1.5 * 0.5 = 0.75
    assert pytest.approx(val1[0, 0], 0.001) == 0.75

    # Verifica fatiamento do Worker 2 (tamanho 3)
    pol2, val2, aux2 = results_p2["infer"]
    assert pol2.shape == (3, ACTION_DIM)
    assert val2.shape == (3, 1)
    # Valor esperado: 2.0 * 0.5 = 1.0
    assert pytest.approx(val2[0, 0], 0.001) == 1.0

    # Verifica resumos coletados
    assert len(summaries) == 2
    worker_ids = {s["worker"] for s in summaries}
    assert worker_ids == {1, 2}

    p1_s.close()
    p1_w.close()
    p2_s.close()
    p2_w.close()


def test_batched_inference_server_none_model_fallback():
    """Valida que o servidor não quebra se model=None (preenche com zeros)."""
    server = BatchedInferenceServer(model=None, device="cpu")
    p_s, p_w = mp.Pipe(duplex=True)

    def worker():
        req = np.ones((2, STATE_DIM), dtype=np.float32)
        p_w.send(("infer", req))
        pol, val, _ = p_w.recv()
        p_w.send(("done", {"pol_shape": pol.shape, "val_shape": val.shape}))

    t = threading.Thread(target=worker)
    t.start()
    summaries = server.serve([p_s], timeout=2.0)
    t.join()

    assert len(summaries) == 1
    assert summaries[0]["pol_shape"] == (2, ACTION_DIM)
    assert summaries[0]["val_shape"] == (2, 1)

    p_s.close()
    p_w.close()


def test_batched_inference_server_unexpected_worker_eof():
    """Valida resiliência quando um worker fecha abruptamente a conexão."""
    server = BatchedInferenceServer(model=None, device="cpu")
    p1_s, p1_w = mp.Pipe(duplex=True)
    p2_s, p2_w = mp.Pipe(duplex=True)

    # Worker 1 fecha sem mandar 'done'
    p1_w.close()

    def worker2():
        p2_w.send(("done", {"worker": 2}))

    t = threading.Thread(target=worker2)
    t.start()
    summaries = server.serve([p1_s, p2_s], timeout=2.0)
    t.join()

    assert len(summaries) == 1
    assert summaries[0]["worker"] == 2

    p1_s.close()
    p2_s.close()
    p2_w.close()


# ══════════════════════════════════════════════════════════════════
# TESTES DE INTEGRAÇÃO ISMCTS (ACTOR-EVALUATOR + ESCOLHA C)
# ══════════════════════════════════════════════════════════════════

def test_extract_level1_summary():
    """Valida extração serializável de nós diretos da raiz (Nível 1)."""
    root = MCTSNode(prior=1.0)
    c1 = MCTSNode(prior=0.6, parent=root, action_id=0, action_name="Slash")
    c1.visit_count = 10
    c1.value_sum = 5.0
    c2 = MCTSNode(prior=0.4, parent=root, action_id=1, action_name="Block")
    c2.visit_count = 5
    c2.value_sum = 2.5

    root.children = {0: c1, 1: c2, -1: MCTSNode()}  # -1 é pendente de progressive widening
    root.visit_count = 15
    root.value_sum = 7.5

    summary = _extract_level1_summary(root, best_idx=0, world_idx=2)

    assert summary["world_idx"] == 2
    assert summary["best_idx"] == 0
    assert summary["root_stats"]["visit_count"] == 15
    assert pytest.approx(summary["root_stats"]["q_value"], 0.001) == 0.5
    # Filhos diretos
    c_stats = summary["children_stats"]
    assert len(c_stats) == 2  # Ignorou o pendente (-1)
    assert c_stats[0]["action_name"] == "Slash"
    assert c_stats[0]["visit_count"] == 10
    assert pytest.approx(c_stats[0]["q_value"], 0.001) == 0.5
    assert c_stats[1]["action_name"] == "Block"
    assert c_stats[1]["visit_count"] == 5
    assert pytest.approx(c_stats[1]["q_value"], 0.001) == 0.5


def test_ismcts_actor_evaluator_multiprocessing_end_to_end():
    """
    Testa execução real com multiprocessing (spawn), pipes e agregação de votos/estatísticas.
    """
    model = MockPolicyValueModel()
    engine = ISMCTSEngine(model=model, device="cpu", num_worlds=2)

    state = {
        "playerHealth": 20,
        "opponentHealth": 15,
        "playerAP": 1,
        "opponentHandCount": 2,
        "opponentHand": [{"cardNumber": "CardBack"}, {"cardNumber": "CardBack"}],
    }
    legal_actions = [
        {"name": "Heavy Attack", "mode": 0, "score": 8.0, "power": 6, "cost": 2},
        {"name": "Quick Strike", "mode": 1, "score": 6.0, "power": 3, "cost": 0},
    ]

    # Força multiprocessing real (spawn)
    best_idx, policy_dist, ismcts_log = engine.search_ismcts(
        state=state,
        legal_actions=legal_actions,
        num_simulations=5,
        training_mode=False,
        use_multiprocessing=True,
    )

    assert best_idx in [0, 1]
    assert policy_dist.shape == (32,)
    assert pytest.approx(policy_dist.sum(), 0.001) == 1.0

    # Valida estrutura de diagnóstico e retorno Nível 1
    assert ismcts_log["worlds_sampled"] == 2
    assert ismcts_log["num_simulations"] == 5
    assert ismcts_log["total_votes"] > 0
    assert "level1_summary" in ismcts_log

    l1 = ismcts_log["level1_summary"]
    assert "Heavy Attack" in l1
    assert "Quick Strike" in l1
    assert "votes" in l1["Heavy Attack"]
    assert "mean_q" in l1["Heavy Attack"]
    assert "mean_prior" in l1["Heavy Attack"]


def test_ismcts_in_process_fallback_single_world():
    """Valida caminho sequencial/in-process quando actual_worlds == 1."""
    model = MockPolicyValueModel()
    engine = ISMCTSEngine(model=model, device="cpu", num_worlds=1)

    state = {
        "playerHealth": 20,
        "opponentHealth": 15,
        "opponentHandCount": 0,
        "opponentHand": [],
    }
    legal_actions = [
        {"name": "Slash", "mode": 0, "score": 5.0},
    ]

    best_idx, policy_dist, ismcts_log = engine.search_ismcts(
        state=state,
        legal_actions=legal_actions,
        num_simulations=4,
        training_mode=False,
        use_multiprocessing=False,
    )

    assert best_idx == 0
    assert ismcts_log["worlds_sampled"] == 1
    assert ismcts_log["total_votes"] > 0
    assert "level1_summary" in ismcts_log
    assert "Slash" in ismcts_log["level1_summary"]


def test_ismcts_empty_legal_actions():
    """Valida comportamento de borda quando não há ações válidas."""
    engine = ISMCTSEngine(model=None, device="cpu", num_worlds=2)
    state = {"playerHealth": 20}
    best_idx, policy_dist, ismcts_log = engine.search_ismcts(
        state=state,
        legal_actions=[],
        num_simulations=5,
    )
    assert best_idx == 0
    assert policy_dist.sum() == 0.0
    assert ismcts_log == {}
