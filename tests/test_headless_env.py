"""
tests/test_headless_env.py
==========================
Testes unitários para o simulador HeadlessSelfPlayLoop com baralhos reais,
validando integridade vetorial (832 dimensões), transições de regras e
ingestão direta no ReplayBuffer.
"""

import pytest
import numpy as np
import torch

from ai.model import FaBPolicyValueNetwork
from ai.training.headless_env import HeadlessSelfPlayLoop
from ai.experience_collector import ReplayBuffer


def test_headless_deck_parsing():
    """Valida que baralhos reais de decks/*.json são parseados com herói, equipamentos e main deck."""
    net = FaBPolicyValueNetwork()
    env = HeadlessSelfPlayLoop(net, mcts_sims=2, device="cpu")

    hero, equipment, weapons, main_deck = env._parse_deck("kassai")
    assert hero is not None
    assert "kassai" in hero.get("id", "").lower() or "kassai" in hero.get("name", "").lower()
    assert len(equipment) > 0
    assert len(weapons) > 0
    assert len(main_deck) >= 30

    # Verifica se os cards possuem metadados válidos
    first_card = main_deck[0]
    assert "cardNumber" in first_card
    assert "pitch" in first_card
    assert "cost" in first_card


def test_headless_init_state():
    """Valida a montagem do estado inicial com mãos de 4 cartas e equipamentos nos slots."""
    net = FaBPolicyValueNetwork()
    env = HeadlessSelfPlayLoop(net, mcts_sims=2, device="cpu")

    state = env._init_state("kassai", "boltyn")
    assert state.get("playerHealth") == 40
    assert state.get("opponentHealth") == 40
    assert len(state.get("playerHand")) == 4
    assert len(state.get("opponentHand")) == 4
    assert len(state.get("playerDeck")) > 25
    assert len(state.get("opponentDeck")) > 25
    assert len(state.get("playerEquipment")) > 0


def test_headless_play_game_and_vector_integrity():
    """Executa partida completa em memória e valida dimensões e embeddings da trajetória."""
    net = FaBPolicyValueNetwork()
    env = HeadlessSelfPlayLoop(net, mcts_sims=3, device="cpu")

    trajectory, winner = env.play_game("kassai", "boltyn")
    assert len(trajectory) > 0
    assert winner in (0, 1, 2)

    # Valida cada step da trajetória
    first_step = trajectory[0]
    state_vec, policy_vec, player_id = first_step

    assert state_vec.shape == (832,)
    assert state_vec.dtype == np.float32
    assert policy_vec.shape == (32,)
    assert player_id in (1, 2)
    assert np.isclose(policy_vec.sum(), 1.0, atol=1e-3)

    # Verifica se os slots de carta (64..831) têm embeddings reais não zerados
    card_slots_region = state_vec[64:]
    assert (card_slots_region != 0).any(), "Os embeddings de cartas não devem estar vazios com decks reais"


def test_headless_replay_buffer_ingestion():
    """Valida que trajetórias geradas pelo headless alimentam o ReplayBuffer sem erros de shape."""
    buf = ReplayBuffer(max_capacity=1000, state_dim=832)
    assert buf.current_size == 0

    net = FaBPolicyValueNetwork()
    env = HeadlessSelfPlayLoop(net, mcts_sims=2, device="cpu")

    trajectory, winner = env.play_game("kassai", "boltyn")
    ingested = buf.ingest_from_memory([(trajectory, winner)])

    assert ingested == len(trajectory)
    assert buf.current_size == len(trajectory)

    # Amostragem de batch
    batch_states, batch_policies, batch_values = buf.sample_batch(batch_size=min(16, buf.current_size), prioritized=False)
    assert batch_states.shape[1] == 832
    assert batch_policies.shape[1] == 32
    assert batch_values.shape[1] == 1
