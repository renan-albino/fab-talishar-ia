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
from ai.atomic_io import file_lock

class ReplayBuffer:
    def __init__(self, max_capacity: int = 100000):
        self.max_capacity = max_capacity
        self.states = np.zeros((max_capacity, 192), dtype=np.float32)
        self.policies = np.zeros((max_capacity, 32), dtype=np.float32)
        self.values = np.zeros((max_capacity, 1), dtype=np.float32)
        self.weights = np.ones(max_capacity, dtype=np.float32)
        # Alvos Auxiliares (Metodologia KataGo - David J. Wu, 2019)
        self.aux_delta_hp = np.zeros((max_capacity, 1), dtype=np.float32)
        self.aux_turn_dmg = np.zeros((max_capacity, 1), dtype=np.float32)
        self.current_size = 0
        self.pointer = 0

    def add(
        self,
        state: np.ndarray,
        policy: np.ndarray,
        value: float,
        weight: float = 1.0,
        aux_delta_hp: float = 0.0,
        aux_turn_dmg: float = 0.0,
    ):
        idx = self.pointer
        self.states[idx] = state
        self.policies[idx] = policy
        self.values[idx] = float(value)
        self.weights[idx] = max(float(weight), 0.01)
        self.aux_delta_hp[idx] = float(aux_delta_hp)
        self.aux_turn_dmg[idx] = float(aux_turn_dmg)
        self.pointer = (self.pointer + 1) % self.max_capacity
        self.current_size = min(self.current_size + 1, self.max_capacity)

    def add_trajectory(
        self,
        trajectory: List[Any],
        winner_player_id: int,
        weights: Optional[List[float]] = None
    ):
        """
        Adiciona trajetória completa ao buffer calculando Recompensa Densa (Reward Shaping),
        alvos auxiliares (KataGo) e aplicando pesos de Prioritized Experience Replay (PER).
        
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
                    aux_delta = norm_eval
                    aux_dmg = max(0.0, float(board_eval) / 5.0)
                except Exception:
                    reward = r_term
                    aux_delta = 0.0
                    aux_dmg = 0.0
            else:
                reward = r_term
                aux_delta = 0.0
                aux_dmg = 0.0

            w = weights[i] if weights and i < len(weights) else 1.0
            self.add(state, policy, reward, weight=w, aux_delta_hp=aux_delta, aux_turn_dmg=aux_dmg)

    def sample_batch(
        self,
        batch_size: int = 256,
        device: torch.device = None,
        prioritized: bool = True,
        beta: float = 0.6,
        return_is_weights: bool = False,
        return_aux: bool = False,
    ):
        """
        Amostra um batch balanceado com suporte opcional a Importance Sampling (Schaul et al. 2016)
        e alvos auxiliares KataGo (David J. Wu, 2019).
        """
        if self.current_size == 0:
            raise ValueError("Buffer vazio, não é possível amostrar batch.")

        if prioritized and self.current_size > 1:
            active_weights = self.weights[:self.current_size]
            sum_w = float(np.sum(active_weights))
            if sum_w > 0:
                probs = active_weights / sum_w
                indices = np.random.choice(self.current_size, batch_size, replace=True, p=probs)
                # Cálculo de Importance Sampling Weights: w_i = (N * P(i))^(-beta)
                sampled_probs = np.maximum(probs[indices], 1e-8)
                is_weights = (float(self.current_size) * sampled_probs) ** (-beta)
                is_weights = is_weights / np.max(is_weights)  # Normalização para estabilidade de gradiente
            else:
                indices = np.random.choice(self.current_size, batch_size, replace=True)
                is_weights = np.ones(batch_size, dtype=np.float32)
        else:
            if self.current_size < batch_size:
                indices = np.random.choice(self.current_size, self.current_size, replace=True)
            else:
                indices = np.random.choice(self.current_size, batch_size, replace=False)
            is_weights = np.ones(len(indices), dtype=np.float32)

        b_states = torch.from_numpy(self.states[indices]).float()
        b_policies = torch.from_numpy(self.policies[indices]).float()
        b_values = torch.from_numpy(self.values[indices]).float()
        b_is = torch.from_numpy(is_weights.astype(np.float32)).float()

        if device:
            b_states = b_states.to(device)
            b_policies = b_policies.to(device)
            b_values = b_values.to(device)
            b_is = b_is.to(device)

        if return_aux:
            b_aux_delta = torch.from_numpy(self.aux_delta_hp[indices]).float()
            b_aux_dmg = torch.from_numpy(self.aux_turn_dmg[indices]).float()
            if device:
                b_aux_delta = b_aux_delta.to(device)
                b_aux_dmg = b_aux_dmg.to(device)
            aux_dict = {"delta_hp": b_aux_delta, "turn_dmg": b_aux_dmg}

            if return_is_weights:
                return b_states, b_policies, b_values, b_is, aux_dict
            return b_states, b_policies, b_values, aux_dict

        if return_is_weights:
            return b_states, b_policies, b_values, b_is

        return b_states, b_policies, b_values

    def __len__(self) -> int:
        return self.current_size

    def save(self, filepath: str = "data/replay_buffer.npz"):
        with file_lock(filepath):
            os.makedirs(os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True)
            tmp_path = f"{filepath}.{os.getpid()}_{time.time_ns()}.tmp.npz"
            try:
                np.savez_compressed(
                    tmp_path,
                    states=self.states[:self.current_size],
                    policies=self.policies[:self.current_size],
                    values=self.values[:self.current_size],
                    weights=self.weights[:self.current_size],
                    aux_delta_hp=self.aux_delta_hp[:self.current_size],
                    aux_turn_dmg=self.aux_turn_dmg[:self.current_size],
                    schema_version=np.int32(2),
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
        new_aux_delta = np.zeros((new_capacity, 1), dtype=np.float32)
        new_aux_dmg = np.zeros((new_capacity, 1), dtype=np.float32)

        copy_n = min(self.current_size, new_capacity)
        if copy_n > 0:
            new_states[:copy_n] = self.states[:copy_n]
            new_policies[:copy_n] = self.policies[:copy_n]
            new_values[:copy_n] = self.values[:copy_n]
            new_weights[:copy_n] = self.weights[:copy_n]
            new_aux_delta[:copy_n] = self.aux_delta_hp[:copy_n]
            new_aux_dmg[:copy_n] = self.aux_turn_dmg[:copy_n]

        self.states = new_states
        self.policies = new_policies
        self.values = new_values
        self.weights = new_weights
        self.aux_delta_hp = new_aux_delta
        self.aux_turn_dmg = new_aux_dmg
        self.max_capacity = new_capacity
        self.current_size = copy_n
        self.pointer = copy_n % new_capacity

    def load(self, filepath: str = "data/replay_buffer.npz") -> bool:
        if not os.path.exists(filepath):
            return False
        try:
            data = np.load(filepath)
            loaded_states = data["states"]
            # Prevenção de Distribution Shift (Kumagai et al. 2021)
            if loaded_states.ndim != 2 or loaded_states.shape[1] != 192:
                print(f"[ReplayBuffer] ⚠ Shape incompatível detectado ({loaded_states.shape}). Reiniciando buffer.")
                return False

            loaded_policies = data["policies"]
            loaded_values = data["values"]
            loaded_weights = data["weights"] if "weights" in data.files else None
            loaded_aux_delta = data["aux_delta_hp"] if "aux_delta_hp" in data.files else None
            loaded_aux_dmg = data["aux_turn_dmg"] if "aux_turn_dmg" in data.files else None

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

            if loaded_aux_delta is not None and len(loaded_aux_delta) >= n:
                self.aux_delta_hp[:n] = loaded_aux_delta[:n]
            else:
                self.aux_delta_hp[:n] = 0.0

            if loaded_aux_dmg is not None and len(loaded_aux_dmg) >= n:
                self.aux_turn_dmg[:n] = loaded_aux_dmg[:n]
            else:
                self.aux_turn_dmg[:n] = 0.0

            self.current_size = n
            self.pointer = n % self.max_capacity
            return True
        except Exception as e:
            print(f"Erro ao carregar buffer {filepath}: {e}")
            return False

    def ingest_trajectories(self, trajectories_dir: str = "data/trajectories") -> int:
        """Carrega e remove arquivos compactos de trajetória gerados concorrentemente por bots."""
        if not os.path.exists(trajectories_dir):
            return 0
        ingested = 0
        for fname in sorted(os.listdir(trajectories_dir)):
            if fname.endswith(".npz") and not fname.endswith(".tmp.npz"):
                fpath = os.path.join(trajectories_dir, fname)
                try:
                    data = np.load(fpath, allow_pickle=True)
                    states = data["states"]
                    policies = data["policies"]
                    rewards = data["rewards"]
                    weights = data["weights"]
                    aux_delta = data["aux_delta_hp"]
                    aux_dmg = data["aux_turn_dmg"]
                    for s, p, r, w, ad, adm in zip(states, policies, rewards, weights, aux_delta, aux_dmg):
                        self.add(s, p, r, w, ad, adm)
                        ingested += 1
                    os.remove(fpath)
                except Exception:
                    pass
        return ingested


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


def save_trajectory_file(
    trajectory: List[Any],
    winner_player_id: int,
    weights: Optional[List[float]] = None,
    room_id: str = "",
    player_id: int = 1,
    out_dir: str = "data/trajectories"
) -> str:
    """Salva uma trajetória individual de forma atômica e ultrarrápida sem contenção de disco."""
    os.makedirs(out_dir, exist_ok=True)
    parsed_states = []
    parsed_policies = []
    parsed_rewards = []
    parsed_weights = []
    parsed_aux_delta = []
    parsed_aux_dmg = []

    for i, step in enumerate(trajectory):
        state = step[0]
        policy = step[1]
        p_id = step[2]
        board_eval = step[3] if len(step) > 3 else None

        r_term = (1.0 if p_id == winner_player_id else -1.0) if winner_player_id in (1, 2) else 0.0
        if board_eval is not None:
            try:
                norm_eval = float(np.tanh(float(board_eval) / 10.0))
                reward = float(np.clip(0.6 * r_term + 0.4 * norm_eval, -1.0, 1.0))
                aux_delta = norm_eval
                aux_dmg = max(0.0, float(board_eval) / 5.0)
            except Exception:
                reward = r_term
                aux_delta = 0.0
                aux_dmg = 0.0
        else:
            reward = r_term
            aux_delta = 0.0
            aux_dmg = 0.0

        w = weights[i] if weights and i < len(weights) else 1.0

        parsed_states.append(state)
        parsed_policies.append(policy)
        parsed_rewards.append(reward)
        parsed_weights.append(max(float(w), 0.01))
        parsed_aux_delta.append(aux_delta)
        parsed_aux_dmg.append(aux_dmg)

    if not parsed_states:
        return ""

    filepath = os.path.join(out_dir, f"traj_{room_id}_{player_id}_{time.time_ns()}.npz")
    tmp_path = f"{filepath}.tmp.npz"
    np.savez_compressed(
        tmp_path,
        states=np.array(parsed_states, dtype=np.float32),
        policies=np.array(parsed_policies, dtype=np.float32),
        rewards=np.array(parsed_rewards, dtype=np.float32),
        weights=np.array(parsed_weights, dtype=np.float32),
        aux_delta_hp=np.array(parsed_aux_delta, dtype=np.float32),
        aux_turn_dmg=np.array(parsed_aux_dmg, dtype=np.float32),
    )
    os.replace(tmp_path, filepath)
    return filepath

