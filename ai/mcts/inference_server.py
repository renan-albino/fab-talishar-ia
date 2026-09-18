"""
ai/mcts/inference_server.py
===========================
Arquitetura Actor-Evaluator (Centralized Batch Inference) para ISMCTS.

Permite escalabilidade multicore real para a simulação do ISMCTS,
contornando o Global Interpreter Lock (GIL) do Python sem exaurir a VRAM
ou causar problemas de contexto CUDA entre subprocessos.

Componentes:
  1. RemoteModelProxy: Interface injetada nos workers (Actors) que simula
     o modelo PyTorch, enviando requisições de inferência via multiprocessing.Pipe
     e recebendo priors, values e saídas auxiliares.
  2. BatchedInferenceServer: Executado no processo principal (Evaluator).
     Ouve múltiplos pipes usando multiprocessing.connection.wait, agrupa tensores
     em batches dinâmicos [N, 832], executa forward pass único na GPU/CPU
     e fatia as respostas de volta para cada worker correspondente.
"""

import time
import numpy as np
import torch
import torch.nn.functional as F
from multiprocessing import connection
from typing import List, Tuple, Dict, Any, Optional, Union

from ai.logger import get_logger

logger = get_logger("mcts.inference_server")

STATE_DIM = 832
ACTION_DIM = 32


class RemoteModelProxy:
    """
    Interface que simula o modelo FaBPolicyValueNetwork nos workers de MCTS (Actors).

    Envia requisições de inferência via multiprocessing.Pipe em lote e aguarda
    a resposta (policy_logits, values, aux_dict).
    Totalmente desacoplado de CUDA/GPU — opera estritamente com tensores CPU / NumPy.
    """

    def __init__(self, conn: connection.Connection):
        self.conn = conn

    def eval(self) -> "RemoteModelProxy":
        """No-op para compatibilidade com código que chama model.eval()."""
        return self

    def train(self, mode: bool = True) -> "RemoteModelProxy":
        """No-op para compatibilidade."""
        return self

    def to(self, device: Any) -> "RemoteModelProxy":
        """No-op para compatibilidade com código que chama model.to(device)."""
        return self

    def parameters(self):
        """Retorna gerador vazio para compatibilidade."""
        return iter([])

    def __call__(
        self,
        x: Union[torch.Tensor, np.ndarray],
        return_aux: bool = False,
    ) -> Union[Tuple[torch.Tensor, torch.Tensor], Tuple[torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]]:
        """
        Executa inferência enviando tensores pelo Pipe IPC e aguardando resposta.
        Retorna torch.Tensor em CPU para compatibilidade transparente com downstream.
        """
        if isinstance(x, torch.Tensor):
            x_np = x.detach().cpu().numpy()
        else:
            x_np = np.asarray(x, dtype=np.float32)

        if x_np.ndim == 1:
            x_np = x_np[np.newaxis, :]

        if x_np.shape[0] == 0:
            empty_policy = torch.zeros((0, ACTION_DIM), dtype=torch.float32)
            empty_val = torch.zeros((0, 1), dtype=torch.float32)
            if return_aux:
                return empty_policy, empty_val, {}
            return empty_policy, empty_val

        self.conn.send(("infer", x_np))
        policy_np, values_np, aux_dict = self.conn.recv()

        policy_tensor = torch.from_numpy(policy_np)
        values_tensor = torch.from_numpy(values_np)

        if return_aux:
            aux_tensors = {k: torch.from_numpy(v) for k, v in aux_dict.items()}
            return policy_tensor, values_tensor, aux_tensors
        return policy_tensor, values_tensor

    def predict_state(
        self,
        state_vector: Union[torch.Tensor, np.ndarray],
        device: str = "cpu",
    ) -> Tuple[np.ndarray, float]:
        """
        Avalia um estado único e retorna probabilidades (softmax) e value escalar.
        Compatível com a API de FaBPolicyValueNetwork.predict_state.
        """
        if isinstance(state_vector, torch.Tensor):
            s_np = state_vector.detach().cpu().numpy()
        else:
            s_np = np.asarray(state_vector, dtype=np.float32)

        if s_np.size == 0:
            return np.ones(ACTION_DIM, dtype=np.float32) / float(ACTION_DIM), 0.0

        if s_np.ndim == 1:
            s_np = s_np[np.newaxis, :]

        self.conn.send(("infer", s_np))
        policy_np, values_np, _ = self.conn.recv()

        # Softmax nos logits para retornar distribuição de probabilidade
        logits = policy_np[0]
        exp_logits = np.exp(logits - np.max(logits))
        probs = (exp_logits / np.sum(exp_logits)).astype(np.float32)
        value = float(values_np.flat[0]) if values_np.size > 0 else 0.0
        return probs, value

    def predict_states(
        self,
        state_vectors: Union[List[np.ndarray], np.ndarray],
        device: Optional[str] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Avalia múltiplos vetores de estado simultaneamente em batch.
        Retorna (probs, values) com probs [N, 32] e values [N, 1].
        """
        if isinstance(state_vectors, list):
            if not state_vectors:
                return np.zeros((0, ACTION_DIM), dtype=np.float32), np.zeros((0, 1), dtype=np.float32)
            batch_arr = np.stack(state_vectors, axis=0).astype(np.float32)
        else:
            batch_arr = np.asarray(state_vectors, dtype=np.float32)

        if batch_arr.size == 0:
            return np.zeros((0, ACTION_DIM), dtype=np.float32), np.zeros((0, 1), dtype=np.float32)

        if batch_arr.ndim == 1:
            batch_arr = batch_arr[np.newaxis, :]

        self.conn.send(("infer", batch_arr))
        policy_np, values_np, _ = self.conn.recv()

        if values_np.ndim == 1:
            values_np = values_np[:, np.newaxis]

        exp_logits = np.exp(policy_np - np.max(policy_np, axis=-1, keepdims=True))
        probs = (exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)).astype(np.float32)
        return probs, values_np


class BatchedInferenceServer:
    """
    Servidor de Inferência em Lote executado no processo principal (Evaluator).

    Escuta conexões de múltiplos workers via multiprocessing.connection.wait,
    agrupa requisições concorrentes em batches dinâmicos [N, 832], executa
    o forward pass no modelo real (com acesso à GPU/CUDA) e distribui as fatias
    de volta aos workers correspondentes.
    """

    def __init__(
        self,
        model: Optional[Any] = None,
        device: Union[str, torch.device] = "cpu",
        batch_timeout_ms: float = 2.0,
    ):
        self.model = model
        self.device = torch.device(device) if isinstance(device, str) else device
        self.batch_timeout_s = max(0.0005, batch_timeout_ms / 1000.0)

    def serve(
        self,
        pipes: List[connection.Connection],
        timeout: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Loop principal de serviço.
        Ouve os pipes até que todos os workers enviem a mensagem 'done' ou desconectem.

        Returns:
            Lista de payloads retornados pelos workers com a tag 'done' (Resumos de Nível 1).
        """
        active_conns = list(pipes)
        results: List[Dict[str, Any]] = []
        start_time = time.time()

        while active_conns:
            elapsed = time.time() - start_time
            if timeout is not None and elapsed >= timeout:
                logger.error(f"Timeout de {timeout}s atingido no BatchedInferenceServer.")
                break

            remaining = timeout - elapsed if timeout is not None else 0.05
            poll_timeout = min(0.05, max(0.0, remaining))
            ready = connection.wait(active_conns, timeout=poll_timeout)
            if not ready:
                continue

            batch_requests: List[Tuple[connection.Connection, np.ndarray]] = []
            done_conns: List[connection.Connection] = []

            for conn in ready:
                try:
                    msg = conn.recv()
                except (EOFError, BrokenPipeError, ConnectionResetError):
                    done_conns.append(conn)
                    continue
                except Exception as e:
                    logger.warning(f"Erro ao ler mensagem do pipe: {e}")
                    done_conns.append(conn)
                    continue

                if isinstance(msg, tuple) and len(msg) == 2:
                    tag, payload = msg
                    if tag == "infer":
                        batch_requests.append((conn, payload))
                    elif tag == "done":
                        results.append(payload)
                        done_conns.append(conn)
                    else:
                        logger.warning(f"Tag desconhecida recebida: {tag}")
                else:
                    logger.warning(f"Mensagem inesperada no pipe: {type(msg)}")

            for conn in done_conns:
                if conn in active_conns:
                    active_conns.remove(conn)

            # Agrupamento dinâmico: se temos requisições parciais, checa se outros workers
            # completam suas fases de CPU dentro da janela batch_timeout_s
            if batch_requests and len(batch_requests) < len(active_conns):
                remaining_conns = [c for c in active_conns if c not in [r[0] for r in batch_requests]]
                if remaining_conns:
                    more_ready = connection.wait(remaining_conns, timeout=self.batch_timeout_s)
                    for conn in more_ready:
                        try:
                            msg = conn.recv()
                            if isinstance(msg, tuple) and len(msg) == 2:
                                tag, payload = msg
                                if tag == "infer":
                                    batch_requests.append((conn, payload))
                                elif tag == "done":
                                    results.append(payload)
                                    if conn in active_conns:
                                        active_conns.remove(conn)
                                else:
                                    logger.warning(f"Tag desconhecida recebida em janela batch: {tag}")
                            else:
                                logger.warning(f"Mensagem inesperada no pipe em janela batch: {type(msg)}")
                        except Exception:
                            if conn in active_conns:
                                active_conns.remove(conn)

            # Processa o lote de inferência acumulado
            if batch_requests:
                self._process_batch(batch_requests)

        return results

    def _process_batch(self, batch_requests: List[Tuple[connection.Connection, np.ndarray]]) -> None:
        """Executa um forward pass batched para todas as requisições acumuladas e fatia as respostas."""
        sizes = [req[1].shape[0] for req in batch_requests]
        combined_np = np.concatenate([req[1] for req in batch_requests], axis=0)
        total_n = combined_np.shape[0]

        if self.model is not None:
            try:
                if hasattr(self.model, "eval"):
                    self.model.eval()
                with torch.no_grad():
                    x_tensor = torch.from_numpy(combined_np).float().to(self.device)
                    try:
                        out = self.model(x_tensor, return_aux=True)
                    except TypeError:
                        out = self.model(x_tensor)

                    if isinstance(out, (tuple, list)) and len(out) == 3:
                        logits_t, val_t, aux_t = out
                        logits_np = logits_t.detach().cpu().numpy()
                        val_np = val_t.detach().cpu().numpy()
                        aux_np = (
                            {k: v.detach().cpu().numpy() for k, v in aux_t.items()}
                            if isinstance(aux_t, dict)
                            else {}
                        )
                    elif isinstance(out, (tuple, list)) and len(out) == 2:
                        logits_t, val_t = out
                        logits_np = logits_t.detach().cpu().numpy()
                        val_np = val_t.detach().cpu().numpy()
                        aux_np = {}
                    else:
                        logits_np = out.detach().cpu().numpy()
                        val_np = np.zeros((total_n, 1), dtype=np.float32)
                        aux_np = {}
            except Exception as e:
                logger.error(f"Erro na execução da rede neural no BatchedInferenceServer: {e}", exc_info=True)
                logits_np = np.zeros((total_n, ACTION_DIM), dtype=np.float32)
                val_np = np.zeros((total_n, 1), dtype=np.float32)
                aux_np = {}
        else:
            logits_np = np.zeros((total_n, ACTION_DIM), dtype=np.float32)
            val_np = np.zeros((total_n, 1), dtype=np.float32)
            aux_np = {}

        if val_np.ndim == 1:
            val_np = val_np[:, np.newaxis]
        elif val_np.ndim == 0:
            val_np = np.full((total_n, 1), float(val_np), dtype=np.float32)

        if logits_np.ndim == 1:
            logits_np = logits_np[np.newaxis, :]

        # Fatiamento e envio direto a cada worker
        offset = 0
        for (conn, _), size in zip(batch_requests, sizes):
            w_policy = logits_np[offset : offset + size]
            w_val = val_np[offset : offset + size]
            w_aux = {k: v[offset : offset + size] for k, v in aux_np.items()}
            try:
                conn.send((w_policy, w_val, w_aux))
            except Exception as e:
                logger.warning(f"Erro ao despachar resposta para worker: {e}")
            offset += size
