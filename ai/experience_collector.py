"""
ExperienceCollector / ReplayBuffer:
Armazena trajetórias de partidas em memória e disco, gerando batches balanceados para o treinamento da rede neural.
"""

import os
import time
import random
import numpy as np
import torch
from typing import List, Tuple, Dict, Any

class ReplayBuffer:
    def __init__(self, max_capacity: int = 100000):
        self.max_capacity = max_capacity
        self.states = np.zeros((max_capacity, 192), dtype=np.float32)
        self.policies = np.zeros((max_capacity, 32), dtype=np.float32)
        self.values = np.zeros((max_capacity, 1), dtype=np.float32)
        self.current_size = 0
        self.pointer = 0

    def add(self, state: np.ndarray, policy: np.ndarray, value: float):
        idx = self.pointer
        self.states[idx] = state
        self.policies[idx] = policy
        self.values[idx] = float(value)
        self.pointer = (self.pointer + 1) % self.max_capacity
        self.current_size = min(self.current_size + 1, self.max_capacity)

    def add_trajectory(self, trajectory: List[Tuple[np.ndarray, np.ndarray, int]], winner_player_id: int):
        for state, policy, p_id in trajectory:
            reward = 1.0 if p_id == winner_player_id else -1.0
            self.add(state, policy, reward)

    def sample_batch(self, batch_size: int = 256, device: torch.device = None) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
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
                values=self.values[:self.current_size]
            )
            os.replace(tmp_path, filepath)
        except Exception:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

    def load(self, filepath: str = "data/replay_buffer.npz") -> bool:
        if not os.path.exists(filepath):
            return False
        try:
            data = np.load(filepath)
            loaded_states = data["states"]
            loaded_policies = data["policies"]
            loaded_values = data["values"]
            n = min(len(loaded_states), self.max_capacity)
            self.states[:n] = loaded_states[:n]
            self.policies[:n] = loaded_policies[:n]
            self.values[:n] = loaded_values[:n]
            self.current_size = n
            self.pointer = n % self.max_capacity
            return True
        except Exception as e:
            print(f"Erro ao carregar buffer {filepath}: {e}")
            return False

_GLOBAL_BUFFER = None

def get_global_buffer(capacity: int = 100000) -> ReplayBuffer:
    global _GLOBAL_BUFFER
    if _GLOBAL_BUFFER is None:
        _GLOBAL_BUFFER = ReplayBuffer(max_capacity=capacity)
        _GLOBAL_BUFFER.load()
    return _GLOBAL_BUFFER
