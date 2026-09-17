"""
tests/test_model.py
===================
Testes unitários canônicos para o motor neural FaBCardTransformerNetwork (v2):
- Integridade da matriz de embeddings tensoriais em O(1) (data/card_embeddings.pt)
- Extração do vetor de estado flat-packed de 800 dimensões e fallback defensivo
- Invariância a permutações das cartas da mão (Self-Attention)
- Forward e Backward pass com cálculo de gradientes e cabeças auxiliares KataGo
- Predição de estado com interface JSON e integração com ReplayBuffer (800 dimensões)
"""

import os
import json
import pytest
import numpy as np
import torch
import torch.nn.functional as F

from ai.model import (
    FaBCardTransformerNetwork,
    FaBPolicyValueNetwork,
    STATE_DIM,
    ACTION_DIM,
    CARD_EMBEDDING_DIM,
    NUM_CARD_SLOTS,
    _get_card_embeddings_table,
    create_model,
)
from ai.experience_collector import ReplayBuffer


# ══════════════════════════════════════════════════════════════════
# 1. TESTES DA MATRIZ TENSORIAL DE EMBEDDINGS (data/card_embeddings.pt)
# ══════════════════════════════════════════════════════════════════

def test_card_embeddings_table_integrity():
    table, c2idx = _get_card_embeddings_table()
    assert isinstance(table, torch.Tensor)
    assert table.shape[1] == CARD_EMBEDDING_DIM
    assert table.shape[0] >= 5000, "A tabela deve conter ao menos 5.000 cartas catalogadas"
    assert not torch.isnan(table).any(), "A matriz de embeddings contém NaNs!"
    assert not torch.isinf(table).any(), "A matriz de embeddings contém Infs!"

    # Índice 0 é reservado para PAD / vazio (deve ser vetor de zeros)
    assert torch.all(table[0] == 0.0)

    # Verifica se cartas canônicas conhecidas possuem features preenchidas
    assert "boom_grenade_red" in c2idx
    bg_idx = c2idx["boom_grenade_red"]
    bg_vec = table[bg_idx]
    # Índice 6 é extra_on_hit_damage normalizado (4 / 4.0 = 1.0)
    assert bg_vec[6] > 0.0
    # Índice 19 é flag de Item
    assert bg_vec[19] == 1.0

    assert "snatch_red" in c2idx
    snatch_idx = c2idx["snatch_red"]
    snatch_vec = table[snatch_idx]
    # Índice 12 é Attack Action (AA)
    assert snatch_vec[12] == 1.0
    # Índice 34 é draw_cards disruption
    assert snatch_vec[34] == 1.0


# ══════════════════════════════════════════════════════════════════
# 2. TESTES DA EXTRAÇÃO DE VETOR DE ESTADO (800 dimensões)
# ══════════════════════════════════════════════════════════════════

def test_extract_state_vector_shape_and_fallback():
    """Valida o fallback seguro com None ou entrada vazia e a integridade de dimensões."""
    vec_none = FaBCardTransformerNetwork.extract_state_vector(None)
    assert isinstance(vec_none, np.ndarray)
    assert vec_none.shape == (STATE_DIM,)
    assert np.all(vec_none == 0.0)

    vec_empty = FaBPolicyValueNetwork.extract_state_vector({})
    assert isinstance(vec_empty, np.ndarray)
    assert vec_empty.shape == (STATE_DIM,)


def test_extract_state_vector_shape_and_values():
    state = {
        "playerHealth": 20,
        "opponentHealth": 18,
        "playerResources": [2, 0],
        "playerAP": 1,
        "turnPhase": "M",
        "combatChain": [
            {"cardNumber": "zero_to_sixty_red", "attackPower": 4}
        ],
        "playerHand": [
            {"cardNumber": "snatch_red"},
            {"cardNumber": "command_and_conquer_red"},
        ],
        "playerEquipment": [
            {"cardNumber": "ironrot_helm"},
            {"cardNumber": "ironrot_legs"},
        ],
        "playerArsenal": [
            {"cardNumber": "sink_below_red"}
        ],
        "activeChainLink": {
            "cardNumber": "zero_to_sixty_red"
        },
        "opponentItems": [
            {"cardNumber": "boom_grenade_red"}
        ],
    }

    vec = FaBCardTransformerNetwork.extract_state_vector(state)
    assert isinstance(vec, np.ndarray)
    assert vec.shape == (800,)
    assert not np.isnan(vec).any()

    # Contexto Global (0 a 31)
    assert vec[0] == 20.0 / 40.0  # Player HP
    assert vec[1] == 18.0 / 40.0  # Opponent HP
    assert vec[2] == 2.0 / 10.0   # Resources
    assert vec[3] == 1.0 / 5.0    # AP
    assert vec[4] == 1.0          # Phase 'M'

    # Slot 0 da Mão (32 a 79): Deve conter o embedding de snatch_red
    slot0 = vec[32 : 32 + CARD_EMBEDDING_DIM]
    assert np.any(slot0 != 0.0)

    # Slot 1 da Mão (80 a 127): Deve conter command_and_conquer_red
    slot1 = vec[32 + CARD_EMBEDDING_DIM : 32 + 2 * CARD_EMBEDDING_DIM]
    assert np.any(slot1 != 0.0)

    # Slot 7 da Mão (não preenchido): Deve ser nulo
    slot7 = vec[32 + 7 * CARD_EMBEDDING_DIM : 32 + 8 * CARD_EMBEDDING_DIM]
    assert np.all(slot7 == 0.0)

    # Slot 8 Equip (cabeça): ironrot_helm
    slot8 = vec[32 + 8 * CARD_EMBEDDING_DIM : 32 + 9 * CARD_EMBEDDING_DIM]
    assert np.any(slot8 != 0.0)

    # Slot 14 (Active Chain Link): zero_to_sixty_red
    slot14 = vec[32 + 14 * CARD_EMBEDDING_DIM : 32 + 15 * CARD_EMBEDDING_DIM]
    assert np.any(slot14 != 0.0)

    # Slot 15 (Opponent Arena Threat): boom_grenade_red
    slot15 = vec[32 + 15 * CARD_EMBEDDING_DIM : 32 + 16 * CARD_EMBEDDING_DIM]
    assert np.any(slot15 != 0.0)


# ══════════════════════════════════════════════════════════════════
# 3. TESTES DE FORWARD PASS E CABEÇOTES DO TRANSFORMER
# ══════════════════════════════════════════════════════════════════

def test_transformer_forward_single_and_batch():
    model = FaBCardTransformerNetwork(hidden_dim=128, num_layers=2, num_heads=4)
    model.eval()

    # 1. Amostra única
    x_single = torch.randn(1, 800)
    policy_logits, value = model(x_single)
    assert policy_logits.shape == (1, 32)
    assert value.shape == (1, 1)
    assert -1.0 <= value.item() <= 1.0

    # 2. Batch de 8 amostras com alvos auxiliares KataGo
    x_batch = torch.randn(8, 800)
    p_batch, v_batch, aux_dict = model(x_batch, return_aux=True)
    assert p_batch.shape == (8, 32)
    assert v_batch.shape == (8, 1)
    assert "delta_hp" in aux_dict
    assert "turn_dmg" in aux_dict
    assert aux_dict["delta_hp"].shape == (8, 1)
    assert aux_dict["turn_dmg"].shape == (8, 1)
    assert torch.all(aux_dict["delta_hp"] >= -1.0) and torch.all(aux_dict["delta_hp"] <= 1.0)
    assert torch.all(aux_dict["turn_dmg"] >= 0.0)


def test_transformer_predict_state():
    model = FaBCardTransformerNetwork(hidden_dim=128, num_layers=2, num_heads=4)
    vec = np.random.randn(800).astype(np.float32)
    probs, val = model.predict_state(vec, device="cpu")

    assert isinstance(probs, np.ndarray)
    assert probs.shape == (32,)
    assert np.isclose(probs.sum(), 1.0, atol=1e-4)
    assert isinstance(val, float)
    assert -1.0 <= val <= 1.0


# ══════════════════════════════════════════════════════════════════
# 4. TESTE DE INVARIÂNCIA A PERMUTAÇÕES DA MÃO (Self-Attention)
# ══════════════════════════════════════════════════════════════════

def test_hand_permutation_robustness():
    """
    Testa que a ordem das cartas da mão (slots 0 a 7 que pertencem à Zone 0)
    é agregada consistentemente por atenção e pooling, ao contrário do antigo MLP.
    """
    model = FaBCardTransformerNetwork(hidden_dim=128, num_layers=2, num_heads=4)
    model.eval()

    state_orig = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerHand": [
            {"cardNumber": "snatch_red"},
            {"cardNumber": "command_and_conquer_red"},
            {"cardNumber": "sink_below_red"},
        ],
    }

    state_perm = {
        "playerHealth": 20,
        "opponentHealth": 20,
        # Mesmas cartas em ordem diferente
        "playerHand": [
            {"cardNumber": "sink_below_red"},
            {"cardNumber": "snatch_red"},
            {"cardNumber": "command_and_conquer_red"},
        ],
    }

    vec_orig = FaBCardTransformerNetwork.extract_state_vector(state_orig)
    vec_perm = FaBCardTransformerNetwork.extract_state_vector(state_perm)

    with torch.no_grad():
        x1 = torch.from_numpy(vec_orig).unsqueeze(0).float()
        x2 = torch.from_numpy(vec_perm).unsqueeze(0).float()

        _, val1 = model(x1)
        _, val2 = model(x2)

    diff = abs(val1.item() - val2.item())
    # O valor deve ser próximo o suficiente mesmo com pesos não-treinados
    assert diff < 0.25, f"Diferença entre mãos permutadas foi excessiva: {diff}"


# ══════════════════════════════════════════════════════════════════
# 5. TESTES DE TREINAMENTO E BACKPROPAGAÇÃO
# ══════════════════════════════════════════════════════════════════

def test_transformer_training_backward_pass():
    model = FaBCardTransformerNetwork(hidden_dim=128, num_layers=2, num_heads=4)
    model.train()
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)

    x = torch.randn(4, 800)
    target_policy = F.softmax(torch.randn(4, 32), dim=-1)
    target_value = torch.tensor([[0.5], [-0.5], [1.0], [0.0]], dtype=torch.float32)
    target_aux_delta = torch.randn(4, 1)
    target_aux_dmg = torch.randn(4, 1)

    logits, value, aux_dict = model(x, return_aux=True)
    loss_p = -(target_policy * F.log_softmax(logits, dim=-1)).sum(dim=-1).mean()
    loss_v = F.mse_loss(value, target_value)
    loss_aux_delta = F.mse_loss(aux_dict["delta_hp"], target_aux_delta)
    loss_aux_dmg = F.mse_loss(aux_dict["turn_dmg"], target_aux_dmg)
    total_loss = loss_p + loss_v + 0.2 * (loss_aux_delta + loss_aux_dmg)

    optimizer.zero_grad()
    total_loss.backward()

    # Verifica se os gradientes foram propagados para todos os blocos
    for name, param in model.named_parameters():
        if param.requires_grad:
            assert param.grad is not None, f"Gradiente None para {name}"
            assert not torch.isnan(param.grad).any(), f"NaN no gradiente de {name}"

    optimizer.step()


# ══════════════════════════════════════════════════════════════════
# 6. TESTES DO REPLAY BUFFER COM 800 DIMENSÕES
# ══════════════════════════════════════════════════════════════════

def test_replay_buffer_800_dims():
    buf = ReplayBuffer(max_capacity=100, state_dim=800)
    assert buf.states.shape == (100, 800)

    for i in range(10):
        s = np.full(800, fill_value=i, dtype=np.float32)
        p = np.zeros(32, dtype=np.float32)
        p[i % 32] = 1.0
        v = 0.5
        buf.add(s, p, v)

    assert len(buf) == 10
    b_states, b_policies, b_values = buf.sample_batch(batch_size=4, prioritized=False)

    assert b_states.shape == (4, 800)
    assert b_policies.shape == (4, 32)
    assert b_values.shape == (4, 1)
