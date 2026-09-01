"""
FaBPolicyValueNetwork: Rede Neural Profunda Dual-Head (Actor-Critic / AlphaZero Style) para Flesh and Blood.
Mapeia o estado completo da partida para distribuição de ações ótimas (Policy) e probabilidade de vitória (Value).
"""

import os
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Dict, Any, List

STATE_DIM = 192
ACTION_DIM = 32

class ResidualBlock(nn.Module):
    def __init__(self, hidden_dim: int = 256, dropout: float = 0.1):
        super().__init__()
        self.fc1 = nn.Linear(hidden_dim, hidden_dim)
        self.norm1 = nn.LayerNorm(hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.norm2 = nn.LayerNorm(hidden_dim)
        self.dropout = nn.Dropout(dropout)
        self.act = nn.LeakyReLU(0.1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x
        out = self.act(self.norm1(self.fc1(x)))
        out = self.dropout(out)
        out = self.norm2(self.fc2(out))
        out = self.act(out + residual)
        return out

class FaBPolicyValueNetwork(nn.Module):
    def __init__(
        self,
        state_dim: int = None,
        action_dim: int = None,
        hidden_dim: int = None,
        num_res_blocks: int = None,
        dropout: float = None,
    ):
        super().__init__()
        # Lê do SETTINGS se não fornecido — garante que toda a codebase
        # usa automaticamente a arquitetura correta para o hardware atual.
        try:
            from config.settings import SETTINGS
            state_dim     = state_dim     if state_dim     is not None else SETTINGS.state_dim
            action_dim    = action_dim    if action_dim    is not None else SETTINGS.action_dim
            hidden_dim    = hidden_dim    if hidden_dim    is not None else SETTINGS.hidden_dim
            num_res_blocks= num_res_blocks if num_res_blocks is not None else SETTINGS.num_res_blocks
            dropout       = dropout       if dropout       is not None else SETTINGS.dropout
        except Exception:
            state_dim     = state_dim     or STATE_DIM
            action_dim    = action_dim    or ACTION_DIM
            hidden_dim    = hidden_dim    or 256
            num_res_blocks= num_res_blocks or 3
            dropout       = dropout       or 0.1

        self.state_dim     = state_dim
        self.action_dim    = action_dim
        self.hidden_dim    = hidden_dim
        self.num_res_blocks= num_res_blocks

        # Backbone Compartilhado
        self.input_layer = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Dropout(dropout)
        )

        self.res_blocks = nn.ModuleList(
            [ResidualBlock(hidden_dim, dropout) for _ in range(num_res_blocks)]
        )

        # Policy Head (Distribuição de Probabilidades de Ação)
        policy_mid = max(64, hidden_dim // 2)
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_dim, policy_mid),
            nn.LayerNorm(policy_mid),
            nn.LeakyReLU(0.1),
            nn.Linear(policy_mid, action_dim)
        )

        # Value Head (Estimativa de Vitória [-1, 1])
        value_mid = max(32, hidden_dim // 4)
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, value_mid),
            nn.LayerNorm(value_mid),
            nn.LeakyReLU(0.1),
            nn.Linear(value_mid, 1),
            nn.Tanh()
        )

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        h = self.input_layer(x)
        for block in self.res_blocks:
            h = block(h)

        policy_logits = self.policy_head(h)
        value = self.value_head(h)
        return policy_logits, value

    def count_parameters(self) -> int:
        """Retorna o número total de parâmetros treináveis."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def model_info(self) -> str:
        """Resumo legível da arquitetura."""
        params = self.count_parameters()
        return (
            f"FaBPolicyValueNetwork | "
            f"{self.state_dim}→{self.hidden_dim}×{self.num_res_blocks}→{self.action_dim}|1 | "
            f"{params:,} parâmetros"
        )

    @staticmethod
    def extract_state_vector(state: Dict[str, Any], player_id: int = 1) -> np.ndarray:
        """Converte o estado JSON do Talishar em um vetor contínuo de 192 dimensões."""
        try:
            from config.settings import SETTINGS
            dim = SETTINGS.state_dim
        except Exception:
            dim = STATE_DIM
        vec = np.zeros(dim, dtype=np.float32)

        if not isinstance(state, dict):
            return vec

        # 1. Vida e Recursos Básicos (Índices 0-9)
        p_health = float(state.get("playerHealth", state.get("yourHealth", 40)))
        o_health = float(state.get("opponentHealth", state.get("theirHealth", 40)))
        vec[0] = p_health / 40.0
        vec[1] = o_health / 40.0
        
        resources = state.get("playerResources", [0, 0])
        floating_res = float(resources[0]) if isinstance(resources, list) and resources else 0.0
        vec[2] = min(floating_res / 10.0, 1.0)

        ap = float(state.get("playerAP", state.get("actionPoints", 1)))
        vec[3] = min(ap / 5.0, 1.0)

        # Turn Phase One-Hot (Índices 4-15)
        phase = str(state.get("turnPhase", state.get("phase", ""))).upper()
        phases = ["M", "B", "A", "D", "P", "PDECK", "ARS", "STARTTURN", "INSTANT", "RESOLUTIONSTEP"]
        for idx, p in enumerate(phases):
            if p in phase:
                vec[4 + idx] = 1.0

        # 2. Combat Chain Status (Índices 16-25)
        combat_chain = state.get("combatChain", [])
        if isinstance(combat_chain, list) and combat_chain:
            vec[16] = min(len(combat_chain) / 5.0, 1.0)
            curr_atk = combat_chain[0] if isinstance(combat_chain[0], dict) else {}
            atk_power = float(curr_atk.get("attackPower", curr_atk.get("power", 4)))
            vec[17] = min(atk_power / 15.0, 1.0)
            
            # Soma de bloqueio
            total_def = sum(float(c.get("defenseValue", 0)) for c in combat_chain[1:] if isinstance(c, dict))
            vec[18] = min(total_def / 15.0, 1.0)

        # 3. Embeddings das Cartas na Mão (Índices 26-105: até 8 cartas x 10 features cada)
        hand = state.get("playerHand", [])
        if isinstance(hand, list):
            for i, c in enumerate(hand[:8]):
                base_idx = 26 + (i * 10)
                if isinstance(c, dict):
                    card_num = str(c.get("cardNumber", "")).lower()
                    vec[base_idx + 0] = 1.0
                    vec[base_idx + 1] = 1.0 if "red" in card_num else (0.5 if "yellow" in card_num else 0.0)
                    vec[base_idx + 2] = 1.0 if "blue" in card_num else 0.0
                    vec[base_idx + 3] = 1.0 if c.get("action", 0) > 0 else 0.0
                    vec[base_idx + 4] = 0.5
                    vec[base_idx + 5] = 1.0 if any(k in card_num for k in ["sixty", "out_pace", "furious", "surging", "leg_tap"]) else 0.0
                    vec[base_idx + 6] = 1.0 if "reaction" in card_num else 0.0
                    vec[base_idx + 7] = 1.0 if any(k in card_num for k in ["item", "grenade", "processor", "core"]) else 0.0
                    vec[base_idx + 8] = 1.0 if any(k in card_num for k in ["crush", "crippling", "spinal"]) else 0.0
                    vec[base_idx + 9] = 1.0 if c.get("actionDataOverride") else 0.0

        # 4. Embeddings de Equipamentos e Arsenal (Índices 106-145)
        equip = state.get("playerEquipment", [])
        if isinstance(equip, list):
            for i, eq in enumerate(equip[:4]):
                b_idx = 106 + (i * 5)
                if isinstance(eq, dict):
                    vec[b_idx + 0] = 1.0
                    vec[b_idx + 1] = 1.0 if eq.get("action", 0) > 0 else 0.0
                    vec[b_idx + 2] = float(eq.get("counters", 0)) / 5.0

        arsenal = state.get("playerArsenal", [])
        if isinstance(arsenal, list) and arsenal:
            vec[126] = 1.0
            if isinstance(arsenal[0], dict) and arsenal[0].get("action", 0) > 0:
                vec[127] = 1.0

        # 5. Profundidade de Zonas (Índices 146-160)
        vec[146] = min(len(state.get("playerDeck", [])) / 60.0, 1.0)
        vec[147] = min(len(state.get("playerDiscard", [])) / 40.0, 1.0)
        vec[148] = min(len(state.get("playerBanish", [])) / 20.0, 1.0)
        vec[149] = min(len(state.get("playerPitch", [])) / 10.0, 1.0)

        # 6. Hero Classes & Archetypes (Índices 161-191)
        hero = str(state.get("playerHero", state.get("character", ""))).lower()
        if "dash" in hero: vec[161] = 1.0
        if "bravo" in hero: vec[162] = 1.0
        if "katsu" in hero or "ira" in hero or "fai" in hero: vec[163] = 1.0
        if "dorinthea" in hero: vec[164] = 1.0
        if "kano" in hero or "oscilio" in hero: vec[165] = 1.0

        return vec

    def predict_state(self, state_vector: np.ndarray, device: str = "cpu") -> Tuple[np.ndarray, float]:
        """Avalia um estado único e retorna as probabilidades da política e a estimativa de valor."""
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(state_vector).unsqueeze(0).float().to(device)
            logits, val = self(x)
            probs = F.softmax(logits, dim=-1).cpu().numpy()[0]
            value = float(val.cpu().numpy()[0][0])
        return probs, value

def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")

def create_model(
    checkpoint_path: str = None,
    device: str = None,
    strict_load: bool = False,
) -> Tuple[FaBPolicyValueNetwork, torch.device]:
    """
    Cria ou carrega um modelo FaBPolicyValueNetwork.

    A arquitetura é lida automaticamente do SETTINGS (hardware-aware).
    Se o checkpoint existir mas a arquitetura mudou, tenta carregamento
    relaxado (strict=False) para reaproveitar pesos compatíveis.
    """
    dev = torch.device(device) if device else get_device()
    model = FaBPolicyValueNetwork().to(dev)

    # Tenta o checkpoint fornecido; se não, tenta o padrão do SETTINGS
    if not checkpoint_path:
        try:
            from config.settings import SETTINGS
            checkpoint_path = SETTINGS.teacher_checkpoint
        except Exception:
            checkpoint_path = os.path.join("data", "checkpoints", "teacher_latest.pt")

    if checkpoint_path and os.path.exists(checkpoint_path):
        try:
            state_dict = torch.load(checkpoint_path, map_location=dev)
            model.load_state_dict(state_dict, strict=strict_load)
            print(f"[Modelo] ✓ Checkpoint carregado: {checkpoint_path}")
        except RuntimeError as e:
            # Arquitetura mudou — tenta carregamento parcial
            try:
                state_dict = torch.load(checkpoint_path, map_location=dev)
                compatible = {k: v for k, v in state_dict.items()
                              if k in model.state_dict() and
                              model.state_dict()[k].shape == v.shape}
                model.load_state_dict(compatible, strict=False)
                pct = 100 * len(compatible) / len(model.state_dict())
                print(f"[Modelo] ⚠ Checkpoint parcial ({pct:.0f}% de pesos reutilizados): {e}")
            except Exception as e2:
                print(f"[Modelo] ✗ Checkpoint ignorado (incompatível): {e2}")
        except Exception as e:
            print(f"[Modelo] ✗ Erro ao carregar checkpoint: {e}")
    else:
        print(f"[Modelo] Iniciando com pesos aleatórios — nenhum checkpoint em: {checkpoint_path}")

    print(f"[Modelo] {model.model_info()}")
    return model, dev

