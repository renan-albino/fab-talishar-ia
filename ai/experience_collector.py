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

try:
    from config.settings import SETTINGS
    DEFAULT_STATE_DIM = SETTINGS.state_dim
except Exception:
    DEFAULT_STATE_DIM = 832

import contextlib
import logging

logger = logging.getLogger(__name__)

@contextlib.contextmanager
def file_lock(path, timeout=5.0):
    try:
        from filelock import FileLock
        lock = FileLock(f"{path}.lock", timeout=timeout)
        with lock:
            yield
    except ImportError:
        # Fallback para ambientes sem filelock usando arquivo exclusivo
        lock_file = f"{path}.lock"
        start_t = time.time()
        fd = None
        while time.time() - start_t < timeout:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
            except OSError:
                time.sleep(0.05)
        try:
            yield
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                    os.remove(lock_file)
                except OSError:
                    pass
    except Exception as e:
        logger.warning("[file_lock] Aviso ao obter lock em %s: %s. Prosseguindo.", path, e)
        yield

class SumTree:
    def __init__(self, capacity: int):
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity - 1, dtype=np.float32)

    def update(self, idx: int, priority: float):
        tree_idx = idx + self.capacity - 1
        change = priority - self.tree[tree_idx]
        self.tree[tree_idx] = priority
        while tree_idx != 0:
            tree_idx = (tree_idx - 1) // 2
            self.tree[tree_idx] += change

    def get_leaf(self, v: float) -> Tuple[int, int, float]:
        parent_idx = 0
        while True:
            left_child_idx = 2 * parent_idx + 1
            right_child_idx = left_child_idx + 1
            if left_child_idx >= len(self.tree):
                break
            if v <= self.tree[left_child_idx] or self.tree[right_child_idx] == 0:
                parent_idx = left_child_idx
            else:
                v -= self.tree[left_child_idx]
                parent_idx = right_child_idx
        data_idx = parent_idx - self.capacity + 1
        return parent_idx, data_idx, self.tree[parent_idx]

    @property
    def total_priority(self) -> float:
        return self.tree[0]


class ReplayBuffer:
    def __init__(self, max_capacity: int = 100000, state_dim: int = None):
        self.max_capacity = max_capacity
        self.state_dim = state_dim or DEFAULT_STATE_DIM
        self.states = np.zeros((max_capacity, self.state_dim), dtype=np.float32)
        self.policies = np.zeros((max_capacity, 32), dtype=np.float32)
        self.values = np.zeros((max_capacity, 1), dtype=np.float32)
        
        self.sum_tree = SumTree(max_capacity)
        
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
        
        self.sum_tree.update(idx, max(float(weight), 0.01))
        
        self.aux_delta_hp[idx] = float(aux_delta_hp)
        self.aux_turn_dmg[idx] = float(aux_turn_dmg)
        self.pointer = (self.pointer + 1) % self.max_capacity
        self.current_size = min(self.current_size + 1, self.max_capacity)

    def add_trajectory(
        self,
        trajectory: List[Any],
        winner_player_id: int,
        weights: Optional[List[float]] = None,
        epoch_ratio: float = 0.0
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

            # 2. Reward Shaping Intermediário (Dense Reward) com Annealing
            if board_eval is not None:
                try:
                    # Normaliza a vantagem de mesa do FaB com tanh (escala típica [-15, +15] -> [-1, 1])
                    norm_eval = float(np.tanh(float(board_eval) / 10.0))
                    # Annealing: peso da vantagem posicional decai de 0.4 para 0.0 com o avanço das épocas
                    eval_weight = 0.4 * (1.0 - epoch_ratio)
                    term_weight = 1.0 - eval_weight
                    reward = term_weight * r_term + eval_weight * norm_eval
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
            indices = []
            is_weights_list = []
            segment = self.sum_tree.total_priority / batch_size
            for i in range(batch_size):
                a = segment * i
                b = segment * (i + 1)
                v = random.uniform(a, b)
                parent_idx, data_idx, priority = self.sum_tree.get_leaf(v)
                if data_idx >= self.current_size:
                    data_idx = random.randint(0, self.current_size - 1)
                    priority = self.sum_tree.tree[data_idx + self.sum_tree.capacity - 1]
                indices.append(data_idx)
                
                prob = priority / max(self.sum_tree.total_priority, 1e-8)
                sampled_prob = max(prob, 1e-8)
                is_weight = (float(self.current_size) * sampled_prob) ** (-beta)
                is_weights_list.append(is_weight)
                
            indices = np.array(indices)
            is_weights = np.array(is_weights_list, dtype=np.float32)
            if np.max(is_weights) > 0:
                is_weights = is_weights / np.max(is_weights)
        else:
            if self.current_size < batch_size:
                indices = np.random.choice(self.current_size, batch_size, replace=True)
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
                tree_start = self.sum_tree.capacity - 1
                current_weights = self.sum_tree.tree[tree_start : tree_start + self.current_size]
                np.savez_compressed(
                    tmp_path,
                    states=self.states[:self.current_size],
                    policies=self.policies[:self.current_size],
                    values=self.values[:self.current_size],
                    weights=current_weights,
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
        new_states = np.zeros((new_capacity, self.state_dim), dtype=np.float32)
        new_policies = np.zeros((new_capacity, 32), dtype=np.float32)
        new_values = np.zeros((new_capacity, 1), dtype=np.float32)
        new_sum_tree = SumTree(new_capacity)
        new_aux_delta = np.zeros((new_capacity, 1), dtype=np.float32)
        new_aux_dmg = np.zeros((new_capacity, 1), dtype=np.float32)

        copy_n = min(self.current_size, new_capacity)
        if copy_n > 0:
            new_states[:copy_n] = self.states[:copy_n]
            new_policies[:copy_n] = self.policies[:copy_n]
            new_values[:copy_n] = self.values[:copy_n]
            new_aux_delta[:copy_n] = self.aux_delta_hp[:copy_n]
            new_aux_dmg[:copy_n] = self.aux_turn_dmg[:copy_n]
            
            tree_start = self.sum_tree.capacity - 1
            for i in range(copy_n):
                new_sum_tree.update(i, self.sum_tree.tree[tree_start + i])

        self.states = new_states
        self.policies = new_policies
        self.values = new_values
        self.sum_tree = new_sum_tree
        self.aux_delta_hp = new_aux_delta
        self.aux_turn_dmg = new_aux_dmg
        self.max_capacity = new_capacity
        self.current_size = copy_n
        self.pointer = copy_n % new_capacity

    def load(self, filepath: str = "data/replay_buffer.npz") -> bool:
        if not os.path.exists(filepath):
            return False
        try:
            with np.load(filepath) as data:
                loaded_states = data["states"]
                # Prevenção de Distribution Shift (Kumagai et al. 2021)
                if loaded_states.ndim != 2 or loaded_states.shape[1] != self.state_dim:
                    print(f"[ReplayBuffer] ⚠ Shape incompatível detectado ({loaded_states.shape}, esperado {self.state_dim}). Reiniciando buffer.")
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
                
                # Repopular SumTree
                self.sum_tree = SumTree(self.max_capacity)
                for i in range(n):
                    w = float(loaded_weights[i]) if (loaded_weights is not None and len(loaded_weights) > i) else 1.0
                    self.sum_tree.update(i, w)

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
            print(f"[ReplayBuffer] Erro ao carregar buffer corrompido {filepath}: {e}. Reiniciando buffer vazio.")
            self.current_size = 0
            self.pointer = 0
            self.states.fill(0)
            self.policies.fill(0)
            self.values.fill(0)
            self.sum_tree = SumTree(self.max_capacity)
            return False

    def ingest_from_memory(self, trajectories: List[Tuple[List[Any], int]]) -> int:
        """
        Recebe uma lista de trajetórias em memória (do HeadlessSelfPlayLoop) 
        e insere diretamente no buffer sem I/O de disco.
        Cada item deve ser (trajectory, winner_id).
        """
        ingested = 0
        for traj, winner_player_id in trajectories:
            weights = [1.0] * len(traj)
            # Reaproveita a lógica robusta de cálculo de recompensas do add_trajectory
            self.add_trajectory(traj, winner_player_id, weights, epoch_ratio=0.0)
            ingested += len(traj)
        return ingested

    def ingest_trajectories(self, trajectories_dir: str = "data/trajectories") -> int:
        """Carrega e remove arquivos compactos de trajetória gerados concorrentemente por bots."""
        if not os.path.exists(trajectories_dir):
            return 0
        ingested = 0
        for fname in sorted(os.listdir(trajectories_dir)):
            if fname.endswith(".npz") and not fname.endswith(".tmp.npz"):
                fpath = os.path.join(trajectories_dir, fname)
                try:
                    with np.load(fpath, allow_pickle=True) as data:
                        states = data["states"]
                        policies = data["policies"]
                        rewards = data["rewards"]
                        weights = data["weights"]
                        aux_delta = data.get("aux_delta_hp", np.zeros(len(states)))
                        aux_dmg = data.get("aux_turn_dmg", np.zeros(len(states)))
                        for s, p, r, w, ad, adm in zip(states, policies, rewards, weights, aux_delta, aux_dmg):
                            self.add(s, p, r, w, ad, adm)
                            ingested += 1
                    os.remove(fpath)
                except Exception as e:
                    import logging
                    logging.warning(f"[ReplayBuffer] Erro ao ingerir trajetória {fpath}: {e}")
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
    out_dir: str = "data/trajectories",
    epoch_ratio: float = 0.0
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
                
                # Reward Annealing (MCTS Value Network Scaling)
                # Início (ratio=0): Confia mais na avaliação tática de curto prazo (0.8) vs (0.2) vitória
                # Fim (ratio=1): Confia mais na vitória real da partida (0.8) vs (0.2) avaliação
                w_term = 0.2 + (0.6 * epoch_ratio)
                w_eval = 0.8 - (0.6 * epoch_ratio)
                
                reward = float(np.clip(w_term * r_term + w_eval * norm_eval, -1.0, 1.0))
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

