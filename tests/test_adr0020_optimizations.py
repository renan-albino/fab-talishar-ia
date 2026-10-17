"""
Testes unitários dedicados para as otimizações e garantias do ADR-0020:
1. Vetorização e invariância a duplicatas em SumTree.update_batch.
2. Equivalência determinística de _encode_fused no MC Dropout (predict_value_with_uncertainty).
3. Resiliência do Shadow Mode contra modos de passe/modal e detecção de confounded=True.
4. Fidelidade física dos alvos auxiliares KataGo no _TrajectoryStep e ReplayBuffer.
"""

import numpy as np
import pytest
import torch

from ai.experience_collector import SumTree, ReplayBuffer, compute_shaped_reward
from ai.model import FaBCardTransformerNetwork
from ai.shadow_mode import predict, compare
from ai.training.headless_env import _TrajectoryStep


def test_sum_tree_update_batch_equivalence_and_duplicates():
    """Valida equivalência exata de update_batch contra updates escalares e imunidade a duplicatas."""
    capacity = 16
    tree_scalar = SumTree(capacity)
    tree_batch = SumTree(capacity)

    # 1. Atualizações distintas
    indices = np.array([0, 3, 4, 7, 12], dtype=np.int64)
    priorities = np.array([1.5, 0.8, 3.2, 2.0, 0.5], dtype=np.float32)

    for idx, p in zip(indices, priorities):
        tree_scalar.update(int(idx), float(p))

    tree_batch.update_batch(indices, priorities)

    np.testing.assert_allclose(tree_batch.tree, tree_scalar.tree, rtol=1e-5, atol=1e-5)
    assert tree_batch.tree[0] == pytest.approx(sum(priorities), rel=1e-5)

    # 2. Atualizações com duplicatas no mesmo lote (ex: [2, 2, 5])
    dup_indices = np.array([2, 2, 5], dtype=np.int64)
    dup_priorities = np.array([1.0, 4.0, 2.5], dtype=np.float32)

    # No loop escalar, a última prioridade do índice 2 sobrescreve a anterior (fica 4.0)
    for idx, p in zip(dup_indices, dup_priorities):
        tree_scalar.update(int(idx), float(p))

    tree_batch.update_batch(dup_indices, dup_priorities)

    np.testing.assert_allclose(tree_batch.tree, tree_scalar.tree, rtol=1e-5, atol=1e-5)
    assert tree_batch.tree[tree_batch.capacity - 1 + 2] == pytest.approx(4.0)


def test_mc_dropout_single_pass_encode_fused_equivalence():
    """Valida o helper _encode_fused e a predição com incerteza Bayesiana."""
    model = FaBCardTransformerNetwork(hidden_dim=64, num_heads=2)
    model.eval()

    x = torch.randn(1, 832)

    with torch.no_grad():
        fused = model._encode_fused(x)
        assert fused.shape == (1, model.hidden_dim)

        # Checa predict_value_with_uncertainty
        val_mean, val_std = model.predict_value_with_uncertainty(x.numpy(), num_samples=6)
        assert isinstance(val_mean, float)
        assert isinstance(val_std, float)
        assert val_std >= 0.0


def test_shadow_mode_modes_and_confounded():
    """Valida filtro de modos de modal/passe e marcação confounded=True no Shadow Mode."""
    pre_state = {
        "turnPhase": "M",
        "playerHand": [{"cardNumber": "WTR001", "name": "Scar for a Scar"}],
        "playerEquipment": [{"cardNumber": "OUT001", "name": "Flick Knives"}],
        "playerHealth": 20,
        "opponentHealth": 20,
        "resources": 0,
        "action_points": 1,
    }

    # Modos que não representam cartas da mão devem retornar None
    assert predict(pre_state, "PASS", mode=99) is None
    assert predict(pre_state, "flick_knives", mode=16) is None
    assert predict(pre_state, "0", mode=24) is None

    # Modos de equipamento devem ser mapeados para zone='equipment'
    act = predict(pre_state, "EQ-0", mode=1)
    assert act is not None
    assert act["zone"] == "equipment"

    # Transição intermediária de popup/resolução deve marcar confounded=True
    expected = {"hand_count": 0, "resources": 0, "action_points": 0, "player_health": 20, "opponent_health": 20}
    post_state = dict(pre_state, turnPhase="CHOOSEMULTIZONE")
    diffs, confounded = compare(expected, pre_state, post_state)
    assert confounded is True

    # Abertura de combate (M -> B) e alternância de prioridade ativa marca confounded=True
    post_combat = dict(pre_state, turnPhase="B", amIActivePlayer=False)
    diffs, confounded = compare(expected, dict(pre_state, amIActivePlayer=True), post_combat)
    assert confounded is True

    # Enlightened Strike retido durante sub-modal não gera falso positivo
    e_strike_exp = {"hand_count": 1, "action_points": 0, "card_consumed": "enlightened_strike_red"}
    post_e_strike = dict(pre_state, playerHand=[{"cardNumber": "WTR001", "name": "Enlightened Strike"}, {"name": "Blue"}])
    diffs, confounded = compare(e_strike_exp, pre_state, post_e_strike)
    assert "hand_count" not in diffs
    assert "action_points" not in diffs
    assert "card_unconsumed" not in diffs

    # Blizzard jogado como Instant em Phase B não gera falso positivo de card_unconsumed
    blizzard_exp = {"hand_count": 1, "card_consumed": "blizzard_blue"}
    pre_b = dict(pre_state, turnPhase="B", playerHand=[{"name": "Blizzard"}])
    post_b = dict(pre_b, playerHand=[{"name": "Blizzard"}])
    diffs, confounded = compare(blizzard_exp, pre_b, post_b)
    assert "card_unconsumed" not in diffs
    assert "hand_count" not in diffs


def test_headless_trajectory_step_and_aux_targets():
    """Valida que _TrajectoryStep desempacota 3 itens mas retém 6, alimentando os alvos KataGo."""
    vec = np.zeros(832, dtype=np.float32)
    policy = np.zeros(32, dtype=np.float32)
    policy[0] = 1.0
    active_player = 1
    board_eval = 8.0
    step_delta_hp = 4.0
    step_dmg = 4.0

    step = _TrajectoryStep((vec, policy, active_player, board_eval, step_delta_hp, step_dmg))

    # Desempacotamento de 3 variáveis
    s, p, a = step
    assert a == 1
    assert len(step) == 6
    assert step[3] == 8.0
    assert step[4] == 4.0
    assert step[5] == 4.0

    # Ingestão no ReplayBuffer e cálculo de shaped reward
    buffer = ReplayBuffer(max_capacity=100)
    buffer.add_trajectory([step], winner_player_id=1, epoch_ratio=0.5)

    assert len(buffer) == 1
    # aux_delta_hp deve refletir tanh(4.0 / 10.0)
    expected_delta = float(np.tanh(4.0 / 10.0))
    # aux_turn_dmg deve refletir 4.0 / 5.0 = 0.8
    expected_dmg = 4.0 / 5.0
    assert buffer.aux_delta_hp[0] == pytest.approx(expected_delta, rel=1e-4)
    assert buffer.aux_turn_dmg[0] == pytest.approx(expected_dmg, rel=1e-4)
