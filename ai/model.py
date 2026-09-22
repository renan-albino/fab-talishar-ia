"""
ai/model.py
===========
FaBCardTransformerNetwork: Rede Neural com Atenção Carta-a-Carta e Contexto Global (v2).
Substitui o antigo MLP estático por uma arquitetura moderna baseada em Card Embeddings
tensoriais em O(1), Transformer Encoder e Cross-Attention contextual.
"""

import os
import json
import shutil
import logging
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Dict, Any, List, Optional

STATE_DIM = 832
ACTION_DIM = 32
CARD_EMBEDDING_DIM = 48
NUM_CARD_SLOTS = 16

# ══════════════════════════════════════════════════════════════════
# CARREGAMENTO EM MEMÓRIA DA MATRIZ DE EMBEDDINGS (CACHED O(1))
# ══════════════════════════════════════════════════════════════════

_CARD_EMBEDDINGS_TABLE: Optional[torch.Tensor] = None
_CARD_TO_IDX: Optional[Dict[str, int]] = None


def _get_card_embeddings_table() -> Tuple[torch.Tensor, Dict[str, int]]:
    global _CARD_EMBEDDINGS_TABLE, _CARD_TO_IDX
    if _CARD_EMBEDDINGS_TABLE is None or _CARD_TO_IDX is None:
        try:
            from config.settings import DATA_DIR
            pt_path = DATA_DIR / "card_embeddings.pt"
            idx_path = DATA_DIR / "card_to_idx.json"

            if pt_path.exists() and idx_path.exists():
                _CARD_EMBEDDINGS_TABLE = torch.load(pt_path, map_location="cpu", weights_only=True)
                with open(idx_path, "r", encoding="utf-8") as f:
                    _CARD_TO_IDX = json.load(f)
            else:
                raise FileNotFoundError("Embeddings not found")
        except Exception as e:
            print(f"[Model] ⚠ Erro ao carregar card_embeddings.pt: {e}. Criando matriz vazia.")
            _CARD_EMBEDDINGS_TABLE = torch.zeros(1, CARD_EMBEDDING_DIM, dtype=torch.float32)
            _CARD_TO_IDX = {"<PAD>": 0}

    return _CARD_EMBEDDINGS_TABLE, _CARD_TO_IDX


# ══════════════════════════════════════════════════════════════════
# ARQUITETURA CARD TRANSFORMER (DUAL HEAD + KATA-GO AUXILIARY)
# ══════════════════════════════════════════════════════════════════

class FaBCardTransformerNetwork(nn.Module):
    """
    Rede Neural Dual-Head com Atenção Carta-a-Carta e Contexto Global.
    Utiliza Self-Attention para relações de sinergia entre cartas ativas e
    Cross-Attention para conectar o estado da partida às ações ótimas.
    """

    def __init__(
        self,
        state_dim: int = None,
        action_dim: int = None,
        hidden_dim: int = None,
        num_layers: int = None,
        num_heads: int = None,
        dropout: float = None,
    ):
        super().__init__()
        try:
            from config.settings import SETTINGS
            state_dim = state_dim or SETTINGS.state_dim
            action_dim = action_dim or SETTINGS.action_dim
            hidden_dim = hidden_dim or SETTINGS.hidden_dim
            dropout = dropout if dropout is not None else SETTINGS.dropout
        except Exception:
            state_dim = state_dim or STATE_DIM
            action_dim = action_dim or ACTION_DIM
            hidden_dim = hidden_dim or 256
            dropout = dropout if dropout is not None else 0.1

        num_layers = num_layers or 2
        num_heads = num_heads or 4

        # Garante que hidden_dim seja divisível pelo número de cabeças
        if hidden_dim % num_heads != 0:
            hidden_dim = (hidden_dim // num_heads) * num_heads

        self.state_dim = state_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.num_heads = num_heads

        # 1. Projeção das Entradas
        self.global_proj = nn.Sequential(
            nn.Linear(64, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.LeakyReLU(0.1),
        )

        self.card_proj = nn.Sequential(
            nn.Linear(CARD_EMBEDDING_DIM, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.LeakyReLU(0.1),
        )

        # 2. Zone Embeddings (5 zonas):
        # 0: Mão (8 slots), 1: Equip (4 slots), 2: Arsenal (2 slots), 3: Cadeia (1 slot), 4: Arena (1 slot)
        self.zone_embedding = nn.Embedding(5, hidden_dim)
        slot_zones = [0] * 8 + [1] * 4 + [2] * 2 + [3] * 1 + [4] * 1
        self.register_buffer("slot_zones", torch.tensor(slot_zones, dtype=torch.long))

        # 3. Backbone de Self-Attention (Interação entre cartas)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            dropout=dropout,
            activation="gelu",
            batch_first=True,
            norm_first=True,  # Pre-LN para convergência estável
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)

        # 4. Cross-Attention Contextual (Global State consulta Cartas Ativas)
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=hidden_dim,
            num_heads=num_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.cross_norm = nn.LayerNorm(hidden_dim)

        # 5. Camada de Fusão
        self.fusion_fc = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
        )

        # 6. Policy Head (32 ações)
        policy_mid = max(64, hidden_dim // 2)
        self.policy_head = nn.Sequential(
            nn.Linear(hidden_dim, policy_mid),
            nn.LayerNorm(policy_mid),
            nn.LeakyReLU(0.1),
            nn.Linear(policy_mid, action_dim),
        )

        # 7. Value Head ([-1.0, +1.0])
        value_mid = max(32, hidden_dim // 4)
        self.value_head = nn.Sequential(
            nn.Linear(hidden_dim, value_mid),
            nn.LayerNorm(value_mid),
            nn.LeakyReLU(0.1),
            nn.Linear(value_mid, 1),
            nn.Tanh(),
        )

        # 8. Auxiliary Heads (KataGo - Delta HP e Turn Damage)
        aux_mid = max(32, hidden_dim // 4)
        self.aux_delta_hp = nn.Sequential(
            nn.Linear(hidden_dim, aux_mid),
            nn.LeakyReLU(0.1),
            nn.Linear(aux_mid, 1),
            nn.Tanh(),
        )
        self.aux_turn_dmg = nn.Sequential(
            nn.Linear(hidden_dim, aux_mid),
            nn.LeakyReLU(0.1),
            nn.Linear(aux_mid, 1),
            nn.ReLU(),
        )

    def forward(
        self,
        x: torch.Tensor,
        return_aux: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor] | Tuple[torch.Tensor, torch.Tensor, Dict[str, torch.Tensor]]:
        """
        Recebe x no formato [batch, 832] (ou [batch, state_dim]).
        Sintetiza features globais e tokens de cartas por atenção e projeta nas saídas.
        """
        batch_size = x.shape[0]

        # Decomposição do vetor flat-packed
        global_features = x[:, :64]
        card_features = x[:, 64:]

        # Se houver inconsistência de tamanho residual, ajusta por corte ou preenchimento
        target_len = NUM_CARD_SLOTS * CARD_EMBEDDING_DIM
        if card_features.shape[1] < target_len:
            pad_len = target_len - card_features.shape[1]
            card_features = F.pad(card_features, (0, pad_len))
        elif card_features.shape[1] > target_len:
            card_features = card_features[:, :target_len]

        card_tokens = card_features.view(batch_size, NUM_CARD_SLOTS, CARD_EMBEDDING_DIM)

        # Máscara de Padding para ignorar slots vazios no cálculo de atenção
        valid_slots = (card_tokens.abs().sum(dim=-1) > 1e-5)
        padding_mask = ~valid_slots

        # Garante que amostras vazias não causem NaNs no Transformer
        all_pad = padding_mask.all(dim=-1)
        if all_pad.any():
            padding_mask[all_pad, 0] = False

        # Projeção das cartas + Zone Embeddings
        h_cards = self.card_proj(card_tokens)
        h_zones = self.zone_embedding(self.slot_zones)
        h_cards = h_cards + h_zones.unsqueeze(0)

        # 1. Self-Attention entre cartas ativas
        encoded_cards = self.transformer(h_cards, src_key_padding_mask=padding_mask)

        # 2. Projeção do contexto global
        h_global = self.global_proj(global_features).unsqueeze(1)

        # 3. Cross-Attention: Global Context consulta Encoded Cards
        attn_out, _ = self.cross_attn(
            query=h_global,
            key=encoded_cards,
            value=encoded_cards,
            key_padding_mask=padding_mask,
        )
        h_context = self.cross_norm(h_global + attn_out).squeeze(1)

        # 4. Pooling mascarado das cartas
        card_mask_weights = valid_slots.float().unsqueeze(-1)
        card_pool = (encoded_cards * card_mask_weights).sum(dim=1) / card_mask_weights.sum(dim=1).clamp(min=1.0)

        # 5. Fusão final
        fused = self.fusion_fc(torch.cat([h_context, card_pool], dim=-1))

        policy_logits = self.policy_head(fused)
        value = self.value_head(fused)

        if return_aux:
            aux_dict = {
                "delta_hp": self.aux_delta_hp(fused),
                "turn_dmg": self.aux_turn_dmg(fused),
            }
            return policy_logits, value, aux_dict

        return policy_logits, value

    def predict_state(self, state_vector: np.ndarray, device: str = "cpu") -> Tuple[np.ndarray, float]:
        """Avalia um estado único e retorna probabilidades e value escalar."""
        self.eval()
        with torch.no_grad():
            x = torch.from_numpy(state_vector).unsqueeze(0).float().to(device)
            logits, val = self(x)
            probs = F.softmax(logits, dim=-1).cpu().numpy()[0]
            value = float(val.cpu().numpy()[0][0])
        return probs, value

    def predict_states(
        self,
        state_vectors: List[np.ndarray],
        device: Optional[str] = None,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Avalia múltiplos vetores de estado simultaneamente em batch.
        Retorna (probs, values) com probs [N, action_dim] e values [N, 1].
        """
        if not state_vectors:
            return np.zeros((0, self.action_dim), dtype=np.float32), np.zeros((0, 1), dtype=np.float32)

        self.eval()
        dev = torch.device(device) if device else next(self.parameters()).device
        with torch.no_grad():
            if isinstance(state_vectors, np.ndarray):
                batch_arr = state_vectors.astype(np.float32)
            else:
                batch_arr = np.stack(state_vectors, axis=0).astype(np.float32)
            x = torch.from_numpy(batch_arr).to(dev)
            logits, val = self(x)
            probs = F.softmax(logits, dim=-1).cpu().numpy()
            values = val.cpu().numpy()
        return probs, values

    def count_parameters(self) -> int:
        return sum(p.numel() for p in self.parameters() if p.requires_grad)

    def model_info(self) -> str:
        params = self.count_parameters()
        return (
            f"FaBCardTransformerNetwork (v2) | "
            f"{self.state_dim}-dim→{self.hidden_dim}×{self.num_layers}L-{self.num_heads}H→{self.action_dim}|1 | "
            f"{params:,} parâmetros"
        )

    # ══════════════════════════════════════════════════════════════════
    # EXTRAÇÃO DE VETOR DE ESTADO EM O(1) VIA EMBEDDINGS TENSORIAIS
    # ══════════════════════════════════════════════════════════════════

    @staticmethod
    def extract_state_vector(state: Dict[str, Any], player_id: int = 1) -> np.ndarray:
        """
        Converte o estado do Talishar em um vetor contíguo de 832 dimensões (Flat-Packed)
        usando lookup tensorial O(1) sem dependência de expressões regulares ou strings lentas.
        """
        vec = np.zeros(STATE_DIM, dtype=np.float32)
        if not isinstance(state, dict):
            return vec

        table, c2idx = _get_card_embeddings_table()
        table_np = table.numpy() if isinstance(table, torch.Tensor) else table

        # ── 1. Contexto Global (Índices 0 a 31) ───────────────────────
        p_hp = float(state.get("playerHealth", state.get("yourHealth", 40)))
        o_hp = float(state.get("opponentHealth", state.get("theirHealth", 40)))
        vec[0] = p_hp / 40.0
        vec[1] = o_hp / 40.0

        resources = state.get("playerResources", [0, 0])
        fl_res = float(resources[0]) if isinstance(resources, list) and resources else 0.0
        vec[2] = min(fl_res / 10.0, 1.0)

        ap = float(state.get("playerAP", state.get("actionPoints", 1)))
        vec[3] = min(ap / 5.0, 1.0)

        # Fases do Turno (Índices 4 a 13)
        phase = str(state.get("turnPhase", state.get("phase", ""))).upper()
        phases = ["M", "B", "A", "D", "P", "PDECK", "ARS", "STARTTURN", "INSTANT", "RESOLUTIONSTEP"]
        for idx, p in enumerate(phases):
            if p in phase:
                vec[4 + idx] = 1.0

        # Combat Chain (Índices 14 a 16)
        combat_chain = state.get("combatChain", [])
        if isinstance(combat_chain, list) and combat_chain:
            vec[14] = min(len(combat_chain) / 5.0, 1.0)
            curr_atk = combat_chain[0] if isinstance(combat_chain[0], dict) else {}
            atk_power = float(curr_atk.get("attackPower", curr_atk.get("power", 4)))
            vec[15] = min(atk_power / 15.0, 1.0)
            total_def = sum(float(c.get("defenseValue", 0)) for c in combat_chain[1:] if isinstance(c, dict))
            vec[16] = min(total_def / 15.0, 1.0)

        # Janela de Letalidade e Diferencial de Vida
        vec[17] = 1.0 if o_hp <= 6.0 else 0.0
        vec[18] = max(-1.0, min(1.0, (p_hp - o_hp) / 40.0))

        # Contagens de Zonas (Índices 19 a 25)
        deck_cards = state.get("playerDeck", [])
        grave_cards = state.get("playerDiscard", state.get("playerGraveyard", []))
        banish_cards = state.get("playerBanish", [])
        soul_cards = state.get("playerSoul", [])
        allies = state.get("playerAllies", [])

        vec[19] = min(len(deck_cards) / 60.0, 1.0)
        vec[20] = min(len(grave_cards) / 40.0, 1.0)
        vec[21] = min(len(banish_cards) / 20.0, 1.0)
        vec[22] = min(len(soul_cards) / 10.0, 1.0)
        vec[23] = min(len(allies) / 5.0, 1.0)

        auras_tokens = (state.get("playerAuras") or []) + (state.get("playerTokens") or [])
        gold_count = sum(1 for t in auras_tokens if isinstance(t, dict) and "gold" in str(t.get("cardNumber") or t.get("name", "")).lower())
        vec[24] = min(float(gold_count) / 4.0, 1.0)

        runechants = float(state.get("playerRunechants", 0) or 0)
        for a in (state.get("playerAuras") or []):
            if isinstance(a, dict) and "runechant" in str(a.get("cardNumber", "")).lower():
                runechants += max(1, int(a.get("counters", a.get("count", 1))))
        vec[25] = min(runechants / 10.0, 1.0)

        # Heróis e Formato (Índice 26)
        hero = str(state.get("playerHero", state.get("character", ""))).lower()
        vec[26] = 1.0 if (p_hp <= 20 or "young" in hero) else 0.0

        # Ciclo de Pitch e Densidade de Cores Vistas (Índices 27 e 28)
        pitch_cards = state.get("playerPitch", [])
        seen_cards = (grave_cards if isinstance(grave_cards, list) else []) + (pitch_cards if isinstance(pitch_cards, list) else [])
        if seen_cards:
            total_seen = len(seen_cards)
            blue_cnt = sum(1 for c in seen_cards if "blue" in str(c.get("cardNumber") if isinstance(c, dict) else c).lower())
            red_cnt = sum(1 for c in seen_cards if "red" in str(c.get("cardNumber") if isinstance(c, dict) else c).lower())
            vec[27] = blue_cnt / total_seen
            vec[28] = red_cnt / total_seen

        # ── 2. Preenchimento de Slots de Cartas em O(1) (Índices 64 a 831) ──
        def _fill_slot(slot_idx: int, card_dict_or_name: Any):
            if slot_idx >= NUM_CARD_SLOTS:
                return
            c_id = ""
            if isinstance(card_dict_or_name, dict):
                c_id = str(card_dict_or_name.get("cardNumber") or card_dict_or_name.get("name", "")).lower().strip()
            elif isinstance(card_dict_or_name, str):
                c_id = card_dict_or_name.lower().strip()

            idx = c2idx.get(c_id, 0)
            if idx > 0 and idx < len(table_np):
                start = 64 + (slot_idx * CARD_EMBEDDING_DIM)
                end = start + CARD_EMBEDDING_DIM
                vec[start:end] = table_np[idx]

        # Slots 0..7: Mão (até 8 cartas)
        hand = state.get("playerHand", [])
        if isinstance(hand, list):
            for i, c in enumerate(hand[:8]):
                _fill_slot(i, c)

        # Slots 8..11: Equipamentos (4 slots)
        equip = state.get("playerEquipment", [])
        if isinstance(equip, list):
            for i, eq in enumerate(equip[:4]):
                _fill_slot(8 + i, eq)

        # Slots 12..13: Arsenal (até 2 slots)
        arsenal = state.get("playerArsenal") or state.get("playerArse") or []
        if isinstance(arsenal, list):
            for i, ars in enumerate(arsenal[:2]):
                _fill_slot(12 + i, ars)

        # Slot 14: Active Chain Link
        active_chain = state.get("activeChainLink", {})
        if isinstance(active_chain, dict) and active_chain.get("cardNumber"):
            _fill_slot(14, active_chain.get("cardNumber"))

        # Slot 15: Opponent Key Arena Threat (ex: Boom Grenade armada)
        opp_items = state.get("opponentItems") or state.get("theirItems") or []
        if isinstance(opp_items, list) and opp_items:
            # Seleciona o primeiro item perigoso da arena
            _fill_slot(15, opp_items[0])

        return vec


# Alias retrocompatível para evitar quebras em módulos existentes
FaBPolicyValueNetwork = FaBCardTransformerNetwork


# ══════════════════════════════════════════════════════════════════
# FÁBRICA E CARREGAMENTO DE MODELO
# ══════════════════════════════════════════════════════════════════

def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda:0")
    return torch.device("cpu")


def create_model(
    checkpoint_path: str = None,
    device: str = None,
    strict_load: bool = False,
) -> Tuple[FaBCardTransformerNetwork, torch.device]:
    """
    Cria ou carrega um modelo FaBCardTransformerNetwork (v2).
    Se nenhum checkpoint existir, inicializa com pesos aleatórios e salva em data/model_latest.pt.
    """
    dev = torch.device(device) if device else get_device()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if not checkpoint_path:
        checkpoint_path = os.path.join(base_dir, "data", "model_latest.pt")

    model = FaBCardTransformerNetwork().to(dev)

    if checkpoint_path and os.path.exists(checkpoint_path):
        try:
            state_dict = torch.load(checkpoint_path, map_location=dev, weights_only=True)
            model.load_state_dict(state_dict, strict=strict_load)
            print(f"[Modelo] ✓ Checkpoint v2 carregado (100%): {checkpoint_path}")
        except Exception as e:
            bak_path = f"{checkpoint_path}.corrupted.bak"
            logging.error(f"[Modelo] ⚠ Falha ao carregar checkpoint '{checkpoint_path}': {e}. Criando backup '{bak_path}' e mantendo checkpoint sem sobrescrita.")
            print(f"[Modelo] ⚠ Checkpoint incompatível ou corrompido ({e}). Criando backup em: {bak_path}. NÃO sobrescrevendo o arquivo original.")
            try:
                shutil.copyfile(checkpoint_path, bak_path)
            except Exception as be:
                logging.error(f"[Modelo] ⚠ Falha ao copiar arquivo para backup: {be}")
            print(f"[Modelo] {model.model_info()}")
            return model, dev
    else:
        # Salva o novo modelo limpo em data/model_latest.pt
        os.makedirs(os.path.dirname(checkpoint_path) if os.path.dirname(checkpoint_path) else ".", exist_ok=True)
        torch.save(model.state_dict(), checkpoint_path)
        print(f"[Modelo] ✓ Novo modelo v2 inicializado e salvo em: {checkpoint_path}")

    print(f"[Modelo] {model.model_info()}")
    return model, dev


# Alias retrocompatível
load_model = create_model
