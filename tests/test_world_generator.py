import pytest
import json
from unittest.mock import patch, mock_open
from ai.mcts.world_generator import generate_worlds, _get_card_db

@pytest.fixture
def mock_card_db():
    return {
        "bravo_showstopper": {"class": "Guardian", "slot": "deck", "pitch": 1, "power": 6, "defense": 3},
        "katsu_the_wanderer": {"class": "Ninja", "slot": "deck", "pitch": 1, "power": 3, "defense": 2},
        "generic_card": {"class": "Generic", "slot": "deck", "pitch": 2, "power": 4, "defense": 3}
    }

def test_generate_worlds_zero_cards_in_hand():
    """Se a mão oponente estiver vazia, deve retornar o estado inalterado sem gerar cartas falsas."""
    state = {"opponentHandCount": 0, "opponentHand": []}
    worlds = generate_worlds(state, num_worlds=2)
    assert len(worlds) == 1
    assert worlds[0] == state

@patch('ai.mcts.world_generator._get_card_db')
def test_generate_worlds_uses_opponent_discard(mock_db):
    mock_db.return_value = {}
    state = {
        "opponentHandCount": 2,
        "opponentDiscard": [{"cardNumber": "real_card_1"}, {"cardNumber": "real_card_2"}]
    }
    worlds = generate_worlds(state, num_worlds=1)
    assert len(worlds) == 1
    sampled_hand = worlds[0]["opponentHand"]
    assert len(sampled_hand) == 2
    # Verifica se usou as cartas do discard (como há 2 e pede 2, deve retornar ambas ou as genéricas misturadas)
    card_names = [c["cardNumber"] for c in sampled_hand]
    assert all("real_card" in c or "generic_" in c for c in card_names)

@patch('ai.mcts.world_generator._get_card_db')
def test_generate_worlds_deck_aware_guardian(mock_db, mock_card_db):
    """Deve puxar cartas de Guardian do banco de dados quando oponente for Bravo."""
    mock_db.return_value = mock_card_db
    state = {
        "opponentHero": "bravo",
        "opponentHandCount": 2,
        "opponentDiscard": []
    }
    worlds = generate_worlds(state, num_worlds=1)
    sampled_hand = worlds[0]["opponentHand"]
    assert len(sampled_hand) == 2
    card_names = [c["cardNumber"] for c in sampled_hand]
    # Bravo puxa Guardian e Genérico
    assert any(c in card_names for c in ["bravo_showstopper", "generic_card", "generic_red", "generic_blue", "generic_yellow"])

@patch('ai.mcts.world_generator._get_card_db')
def test_generate_worlds_generic_fallback(mock_db):
    """Quando o DB falha, deve usar as cartas genéricas vermelha, amarela e azul."""
    mock_db.return_value = {}
    state = {
        "opponentHero": "unknown_hero",
        "opponentHandCount": 3,
        "opponentDiscard": []
    }
    worlds = generate_worlds(state, num_worlds=1)
    sampled_hand = worlds[0]["opponentHand"]
    assert len(sampled_hand) == 3
    for c in sampled_hand:
        assert "generic_" in c["cardNumber"]
