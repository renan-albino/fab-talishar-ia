import numpy as np
import pytest
from ai.blunder_reviewer import review_trajectory_for_blunders
from ai.experience_collector import ReplayBuffer
from ai.mcts.world_generator import generate_worlds
from ai.model import STATE_DIM


def test_blunder_reviewer_temporal_consistency():
    """Valida a atenuação de supostos blunders que revertem imediatamente no passo seguinte."""
    s = np.zeros(STATE_DIM, dtype=np.float32)
    p = np.zeros(32, dtype=np.float32)

    # Trajetória com reversão favorável:
    # Passo 0: eval = +4.0
    # Passo 1: eval = -1.0 (queda de 5.0 -> suposto blunder)
    # Passo 2: eval = +2.0 (subida de 3.0 -> reversão favorável >= +2.0)
    # Passo 3: eval = +2.0 (estável)
    traj_with_reversal = [
        (s, p, 1, 4.0),
        (s, p, 1, -1.0),
        (s, p, 1, 2.0),
        (s, p, 1, 2.0),
    ]

    weights, stats = review_trajectory_for_blunders(
        traj_with_reversal,
        winner_player_id=1,
        bot_player_id=1,
    )
    # O passo 0 teve swing de -5.0 mas seguido por swing de +3.0 -> peso atenuado (1.5)
    assert weights[0] == 1.5
    assert stats["blunders"] == 0

    # Trajetória sem reversão:
    traj_no_reversal = [
        (s, p, 1, 4.0),
        (s, p, 1, -1.0),
        (s, p, 1, -1.5),
        (s, p, 1, -2.0),
    ]
    weights2, stats2 = review_trajectory_for_blunders(
        traj_no_reversal,
        winner_player_id=2,
        bot_player_id=1,
    )
    assert weights2[0] == 3.5
    assert stats2["blunders"] >= 1


def test_replay_buffer_hero_ids_and_stratification(tmp_path):
    """Valida hero_ids, persistência retrocompatível e amostragem estratificada."""
    buf = ReplayBuffer(max_capacity=50, state_dim=STATE_DIM)
    assert hasattr(buf, "hero_ids")
    assert buf.hero_ids.dtype == np.int32
    assert len(buf.hero_ids) == 50

    dummy_s = np.zeros(STATE_DIM, dtype=np.float32)
    dummy_p = np.zeros(32, dtype=np.float32)

    # Adiciona amostras de 3 heróis distintos: 101, 102, 103
    for _ in range(10):
        buf.add(dummy_s, dummy_p, 0.0, weight=1.0, hero_id=101)
    for _ in range(10):
        buf.add(dummy_s, dummy_p, 0.0, weight=1.0, hero_id=102)
    for _ in range(5):
        buf.add(dummy_s, dummy_p, 0.0, weight=1.0, hero_id=103)

    assert buf.current_size == 25
    assert set(np.unique(buf.hero_ids[:buf.current_size])) == {101, 102, 103}

    # Redimensionamento
    buf.resize(60)
    assert buf.max_capacity == 60
    assert buf.current_size == 25
    assert set(np.unique(buf.hero_ids[:buf.current_size])) == {101, 102, 103}

    # Salva e carrega
    save_path = str(tmp_path / "hero_buf.npz")
    buf.save(save_path)

    buf_loaded = ReplayBuffer(max_capacity=60, state_dim=STATE_DIM)
    assert buf_loaded.load(save_path) is True
    assert set(np.unique(buf_loaded.hero_ids[:buf_loaded.current_size])) == {101, 102, 103}

    # Retrocompatibilidade com npz legado sem hero_ids
    legacy_path = str(tmp_path / "legacy_buf.npz")
    np.savez_compressed(
        legacy_path,
        states=buf.states[:10],
        policies=buf.policies[:10],
        values=buf.values[:10],
        weights=np.ones(10, dtype=np.float32),
        aux_delta_hp=buf.aux_delta_hp[:10],
        aux_turn_dmg=buf.aux_turn_dmg[:10],
    )
    buf_legacy = ReplayBuffer(max_capacity=60, state_dim=STATE_DIM)
    assert buf_legacy.load(legacy_path) is True
    assert np.all(buf_legacy.hero_ids[:10] == 0)

    # Amostragem Estratificada
    b_states, b_policies, b_values = buf.sample_batch(batch_size=10, stratified=True)
    assert b_states.shape == (10, STATE_DIM)

    # add_trajectory com hero_id
    traj = [(dummy_s, dummy_p, 1, 0.0)]
    buf.add_trajectory(traj, winner_player_id=1, hero_id=999)
    assert buf.hero_ids[buf.pointer - 1] == 999


def test_world_generator_pitch_stacking():
    """Valida a modelagem de cartas pitchadas preservadas no fundo do deck simulado."""
    state = {
        "opponentHero": "generic",
        "opponentHandCount": 2,
        "playerPitch": [
            {"cardNumber": "throttle_blue", "pitch": 3},
            {"cardNumber": "fast_and_furious_red", "pitch": 1},
        ],
        "playerDeck": [{"cardNumber": "top_card"}],
    }
    worlds = generate_worlds(state, num_worlds=2)
    assert len(worlds) == 2
    for w in worlds:
        assert "playerDeckBottom" in w
        assert len(w["playerDeckBottom"]) == 2
        assert w["playerDeckBottom"][0]["cardNumber"] == "throttle_blue"
        assert w["playerDeckBottom"][1]["cardNumber"] == "fast_and_furious_red"
