"""
ai/mcts/batched_evaluator.py
============================
Dynamic Thread-Batched Evaluator para MCTS / Headless Self-Play.

Permite que múltiplos workers (threads de self-play MCTS) submetam vetores
de estado concorrentemente. Um worker centralizado em background agrupa as
requisições em batches dinâmicos [N, 832], executa um único forward pass no
dispositivo alvo (GPU CUDA / CPU) em torch.inference_mode() e devolve as fatias
resolvidas para as threads chamadoras via concurrent.futures.Future.

Em GPU, isso substitui dezenas de pequenos forward passes com overhead de kernel
launch por uma única execução batched de alta vazão e baixa latência amortizada.
"""

import time
import queue
import threading
import concurrent.futures
from typing import List, Tuple, Dict, Any, Optional, Union
import numpy as np
import torch

from ai.logger import get_logger

logger = get_logger("mcts.batched_evaluator")

STATE_DIM = 832
ACTION_DIM = 32


class ThreadBatchedEvaluator:
    """
    Fachada thread-safe que simula o modelo neural e agrupa requisições de inferência
    de múltiplas threads de MCTS em batches dinâmicos para o forward pass.
    """

    def __init__(
        self,
        model: Any,
        device: Union[str, torch.device] = "cpu",
        max_batch_size: int = 128,
        batch_timeout_ms: float = 1.0,
        use_amp: bool = True,
    ):
        self.model = model
        self.device = torch.device(device) if isinstance(device, str) else device
        self.max_batch_size = max(1, max_batch_size)
        self.batch_timeout_s = max(0.0002, batch_timeout_ms / 1000.0)
        self.use_amp = use_amp and (self.device.type == "cuda")

        self._queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self.start()

    def start(self) -> None:
        """Inicia a thread coletora de background se não estiver rodando."""
        with self._lock:
            if self._worker_thread is None or not self._worker_thread.is_alive():
                self._stop_event.clear()
                self._worker_thread = threading.Thread(
                    target=self._batch_loop,
                    name="ThreadBatchedEvaluator-Worker",
                    daemon=True,
                )
                self._worker_thread.start()

    def stop(self) -> None:
        """Encerra a thread coletora de background graciosamente."""
        with self._lock:
            if self._worker_thread is not None and self._worker_thread.is_alive():
                self._stop_event.set()
                # Envia sentinela para desbloquear queue.get()
                self._queue.put(None)
                self._worker_thread.join(timeout=2.0)
                self._worker_thread = None

    def __enter__(self) -> "ThreadBatchedEvaluator":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def eval(self) -> "ThreadBatchedEvaluator":
        """Compatibilidade com model.eval()."""
        if hasattr(self.model, "eval"):
            self.model.eval()
        return self

    def train(self, mode: bool = True) -> "ThreadBatchedEvaluator":
        """Compatibilidade com model.train()."""
        if hasattr(self.model, "train"):
            self.model.train(mode)
        return self

    def to(self, device: Any) -> "ThreadBatchedEvaluator":
        """Move o modelo subjacente e atualiza o device do evaluator."""
        self.device = torch.device(device) if isinstance(device, str) else device
        self.use_amp = self.use_amp and (self.device.type == "cuda")
        if hasattr(self.model, "to"):
            self.model.to(self.device)
        return self

    def parameters(self):
        """Retorna parâmetros do modelo subjacente."""
        return self.model.parameters() if hasattr(self.model, "parameters") else iter([])

    def predict_state(
        self,
        state_vector: Union[torch.Tensor, np.ndarray],
        device: Optional[str] = None,
    ) -> Tuple[np.ndarray, float]:
        """
        Avalia um estado único e retorna (probs [32], value: float).
        Interface transparente idêntica a FaBPolicyValueNetwork.predict_state.
        """
        if isinstance(state_vector, torch.Tensor):
            s_np = state_vector.detach().cpu().numpy()
        else:
            s_np = np.asarray(state_vector, dtype=np.float32)

        if s_np.size == 0:
            return np.ones(ACTION_DIM, dtype=np.float32) / float(ACTION_DIM), 0.0

        if s_np.ndim == 1:
            s_np = s_np[np.newaxis, :]

        probs, values = self.predict_states(s_np)
        p = probs[0] if len(probs) > 0 else np.ones(ACTION_DIM, dtype=np.float32) / float(ACTION_DIM)
        v = float(values.flat[0]) if values.size > 0 else 0.0
        return p, v

    def predict_states(
        self,
        state_vectors: Union[List[np.ndarray], np.ndarray],
        device: Optional[str] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Avalia múltiplos vetores em batch e retorna (probs [N, 32], values [N, 1]).
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

        # Submete requisição e aguarda future
        future: concurrent.futures.Future = concurrent.futures.Future()
        self._queue.put((batch_arr, future, False))

        policy_np, values_np, _ = future.result()

        if values_np.ndim == 1:
            values_np = values_np[:, np.newaxis]

        exp_logits = np.exp(policy_np - np.max(policy_np, axis=-1, keepdims=True))
        probs = (exp_logits / np.sum(exp_logits, axis=-1, keepdims=True)).astype(np.float32)
        return probs, values_np

    def __call__(
        self,
        x: Union[torch.Tensor, np.ndarray],
        return_aux: bool = False,
    ) -> Union[Tuple[torch.Tensor, torch.Tensor], Tuple[torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]]:
        """
        Executa inferência batched retornando torch.Tensor (em CPU para desacoplamento de threads).
        """
        if isinstance(x, torch.Tensor):
            x_np = x.detach().cpu().numpy()
        else:
            x_np = np.asarray(x, dtype=np.float32)

        if x_np.ndim == 1:
            x_np = x_np[np.newaxis, :]

        if x_np.shape[0] == 0:
            empty_p = torch.zeros((0, ACTION_DIM), dtype=torch.float32)
            empty_v = torch.zeros((0, 1), dtype=torch.float32)
            if return_aux:
                return empty_p, empty_v, {}
            return empty_p, empty_v

        future: concurrent.futures.Future = concurrent.futures.Future()
        self._queue.put((x_np, future, return_aux))

        policy_np, values_np, aux_dict = future.result()

        p_t = torch.from_numpy(policy_np)
        v_t = torch.from_numpy(values_np)

        if return_aux:
            aux_t = {k: torch.from_numpy(v) for k, v in aux_dict.items()}
            return p_t, v_t, aux_t
        return p_t, v_t

    def _batch_loop(self) -> None:
        """Loop central executado na thread de background que agrega e processa batches."""
        while not self._stop_event.is_set():
            try:
                item = self._queue.get(timeout=0.05)
            except queue.Empty:
                continue

            if item is None or self._stop_event.is_set():
                break

            batch_items = [item]
            curr_size = item[0].shape[0]
            deadline = time.perf_counter() + self.batch_timeout_s

            # Agrupa requisições subsequentes que já chegaram ou chegam dentro da janela
            while curr_size < self.max_batch_size:
                rem_time = deadline - time.perf_counter()
                if rem_time <= 0:
                    break
                try:
                    next_item = self._queue.get(timeout=rem_time)
                    if next_item is None:
                        break
                    batch_items.append(next_item)
                    curr_size += next_item[0].shape[0]
                except queue.Empty:
                    break

            self._dispatch_batch(batch_items)

    def _dispatch_batch(self, batch_items: List[Tuple[np.ndarray, concurrent.futures.Future, bool]]) -> None:
        """Executa forward pass conjunto para os items agrupados e distribui os resultados."""
        sizes = [it[0].shape[0] for it in batch_items]
        combined_np = np.concatenate([it[0] for it in batch_items], axis=0)
        total_n = combined_np.shape[0]

        try:
            if hasattr(self.model, "eval"):
                self.model.eval()

            with torch.inference_mode():
                x_tensor = torch.from_numpy(combined_np).float().to(self.device, non_blocking=True)

                if self.use_amp:
                    with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                        try:
                            out = self.model(x_tensor, return_aux=True)
                        except TypeError:
                            out = self.model(x_tensor)
                else:
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
            logger.error(f"[ThreadBatchedEvaluator] Falha no forward pass batched: {e}", exc_info=True)
            for _, fut, _ in batch_items:
                if not fut.done():
                    fut.set_exception(e)
            return

        if val_np.ndim == 1:
            val_np = val_np[:, np.newaxis]
        elif val_np.ndim == 0:
            val_np = np.full((total_n, 1), float(val_np), dtype=np.float32)

        if logits_np.ndim == 1:
            logits_np = logits_np[np.newaxis, :]

        offset = 0
        for (_, fut, _), size in zip(batch_items, sizes):
            w_policy = logits_np[offset : offset + size]
            w_val = val_np[offset : offset + size]
            w_aux = {k: v[offset : offset + size] for k, v in aux_np.items()}
            if not fut.done():
                fut.set_result((w_policy, w_val, w_aux))
            offset += size
