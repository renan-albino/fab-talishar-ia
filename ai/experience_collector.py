"""
ExperienceCollector / ReplayBuffer:
Armazena trajetórias de partidas em memória e disco, gerando batches balanceados para o treinamento da rede neural.
"""

import os
import time
import random
import numpy as np
import torch
from typing import List, Tuple, Dict, Any, Optional

class ReplayBuffer:
    def __init__(self, max_capacity: int = 100000):
        self.max_capacity = max_capacity
        self.states = np.zeros((max_capacity, 192), dtype=np.float32)
        self.policies = np.zeros((max_capacity, 32), dtype=np.float32)
        self.values = np.zeros((max_capacity, 1), dtype=np.float32)
        self.weights = np.ones(max_capacity, dtype=np.float32)
        self.current_size = 0
        self.pointer = 0

    def add(self, state: np.ndarray, policy: np.ndarray, value: float, weight: float = 1.0):
        idx = self.pointer
        self.states[idx] = state
        self.policies[idx] = policy
        self.values[idx] = float(value)
        self.weights[idx] = max(float(weight), 0.01)
        self.pointer = (self.pointer + 1) % self.max_capacity
        self.current_size = min(self.current_size + 1, self.max_capacity)

    def add_trajectory(
        self,
        trajectory: List[Any],
        winner_player_id: int,
        weights: Optional[List[float]] = None
    ):
        """
        Adiciona trajetória completa ao buffer calculando Recompensa Densa (Reward Shaping)
        e aplicando pesos de Prioritized Experience Replay (PER).
        
        Suporta tuplas:
          - (state, policy, p_id)
          - (state, policy, p_id, board_eval)
        """
        for i, step in enumerate(trajectory):
            state = step[0]
            policy = step[1]
            p_id = step[2]
            board_eval = step[3] if len(step) > 3 else None

            # 1. Recompensa terminal (-1.0, 0.0, +1.0)
            if winner_player_id in (1, 2):
                r_term = 1.0 if p_id == winner_player_id else -1.0
            else:
                r_term = 0.0

            # 2. Reward Shaping Intermediário (Dense Reward)
            if board_eval is not None:
                try:
                    # Normaliza a vantagem de mesa do FaB com tanh (escala típica [-15, +15] -> [-1, 1])
                    norm_eval = float(np.tanh(float(board_eval) / 10.0))
                    # Combinação convexa: 60% ancorado no resultado final, 40% na vantagem posicional do turno
                    reward = 0.6 * r_term + 0.4 * norm_eval
                    reward = float(np.clip(reward, -1.0, 1.0))
                except Exception:
                    reward = r_term
            else:
                reward = r_term

            w = weights[i] if weights and i < len(weights) else 1.0
            self.add(state, policy, reward, weight=w)

    def sample_batch(
        self,
        batch_size: int = 256,
        device: torch.device = None,
        prioritized: bool = True
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.current_size == 0:
            raise ValueError("Buffer vazio, não é possível amostrar batch.")

        if prioritized and self.current_size > 1:
            active_weights = self.weights[:self.current_size]
            sum_w = float(np.sum(active_weights))
            if sum_w > 0:
                probs = active_weights / sum_w
                indices = np.random.choice(self.current_size, batch_size, replace=True, p=probs)
            else:
                indices = np.random.choice(self.current_size, batch_size, replace=True)
        else:
            if self.current_size < batch_size:
                indices = np.random.choice(self.current_size, self.current_size, replace=True)
            else:
                indices = np.random.choice(self.current_size, batch_size, replace=False)

        b_states = torch.from_numpy(self.states[indices]).float()
        b_policies = torch.from_numpy(self.policies[indices]).float()
        b_values = torch.from_numpy(self.values[indices]).float()

        if device:
            b_states = b_states.to(device)
            b_policies = b_policies.to(device)
            b_values = b_values.to(device)

        return b_states, b_policies, b_values

    def __len__(self) -> int:
        return self.current_size

    def save(self, filepath: str = "data/replay_buffer.npz"):
        os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
        tmp_path = f"{filepath}.{os.getpid()}_{time.time_ns()}.tmp.npz"
        try:
            np.savez_compressed(
                tmp_path,
                states=self.states[:self.current_size],
                policies=self.policies[:self.current_size],
                values=self.values[:self.current_size],
                weights=self.weights[:self.current_size],
            )
            os.replace(tmp_path, filepath)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def resize(self, new_capacity: int):
        """Redimensiona a capacidade máxima do buffer preservando os dados já coletados."""
        if new_capacity <= 0 or new_capacity == self.max_capacity:
            return
        new_states = np.zeros((new_capacity, 192), dtype=np.float32)
        new_policies = np.zeros((new_capacity, 32), dtype=np.float32)
        new_values = np.zeros((new_capacity, 1), dtype=np.float32)
        new_weights = np.ones(new_capacity, dtype=np.float32)

        copy_n = min(self.current_size, new_capacity)
        if copy_n > 0:
            new_states[:copy_n] = self.states[:copy_n]
            new_policies[:copy_n] = self.policies[:copy_n]
            new_values[:copy_n] = self.values[:copy_n]
            new_weights[:copy_n] = self.weights[:copy_n]

        self.states = new_states
        self.policies = new_policies
        self.values = new_values
        self.weights = new_weights
        self.max_capacity = new_capacity
        self.current_size = copy_n
        self.pointer = copy_n % new_capacity

    def load(self, filepath: str = "data/replay_buffer.npz") -> bool:
        if not os.path.exists(filepath):
            return False
        try:
            data = np.load(filepath)
            loaded_states = data["states"]
            loaded_policies = data["policies"]
            loaded_values = data["values"]
            loaded_weights = data["weights"] if "weights" in data.files else None
            n_loaded = len(loaded_states)
            if n_loaded > self.max_capacity:
                self.resize(n_loaded)
            n = min(n_loaded, self.max_capacity)
            self.states[:n] = loaded_states[:n]
            self.policies[:n] = loaded_policies[:n]
            self.values[:n] = loaded_values[:n]
            if loaded_weights is not None and len(loaded_weights) >= n:
                self.weights[:n] = loaded_weights[:n]
            else:
                self.weights[:n] = 1.0
            self.current_size = n
            self.pointer = n % self.max_capacity
            return True
        except Exception as e:
            print(f"Erro ao carregar buffer {filepath}: {e}")
            return False

_GLOBAL_BUFFER = None

def get_global_buffer(capacity: int = None) -> ReplayBuffer:
    global _GLOBAL_BUFFER
    env_cap = os.environ.get("FAB_BUFFER_CAPACITY")
    default_cap = int(env_cap) if env_cap and env_cap.isdigit() else 100000
    target_cap = capacity if capacity is not None else default_cap

    if _GLOBAL_BUFFER is None:
        _GLOBAL_BUFFER = ReplayBuffer(max_capacity=target_cap)
        _GLOBAL_BUFFER.load()
    elif target_cap > _GLOBAL_BUFFER.max_capacity:
        _GLOBAL_BUFFER.resize(target_cap)
    return _GLOBAL_BUFFER
