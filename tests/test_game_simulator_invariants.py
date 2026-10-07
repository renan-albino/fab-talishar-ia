"""
tests/test_game_simulator_invariants.py
======================================
Testes unitários determinísticos para validar invariantes estritas do GameSimulator:
- Conservação de zonas de cartas (nenhuma carta desaparece ou se duplica).
- Aritmética de pitch e consistência de custos de recursos.
- Resolução de cadeia de combate (ataque, defesa e dano líquido sofrido).
"""

import pytest
from ai.game_simulator import GameSimulator
from ai.mcts.state import ImmutableGameState


def test_game_simulator_zone_conservation_in_defense():
    """Valida que cartas de defesa transitam da mão para o cemitério/discard sem duplicar."""
    initial_hand = [
        {"cardNumber": "WTR001", "name": "Sink Below", "defense": 4},
        {"cardNumber": "WTR002", "name": "Fate Foreseen", "defense": 4},
        {"cardNumber": "WTR003", "name": "Pummel", "defense": 2},
    ]
    initial_discard = [{"cardNumber": "WTR004", "name": "Old Card"}]

    state = ImmutableGameState({
        "playerHP": 20,
        "opponentHP": 20,
        "playerHand": initial_hand,
        "playerDiscard": initial_discard,
        "playerPitch": [],
        "playerDeck": [{"cardNumber": "WTR005"}],
        "combatChain": [{"cardNumber": "ARC001", "attackPower": 6}],
    })

    # Bloqueia com Sink Below
    block_action = {"cards": [initial_hand[0]]}
    next_state = GameSimulator.simulate_defense(state, block_action)

    assert len(next_state.get("playerHand")) == 2
    assert len(next_state.get("playerDiscard")) == 2  # Old Card + Sink Below
    total_cards_before = len(state.get("playerHand")) + len(state.get("playerDiscard"))
    total_cards_after = len(next_state.get("playerHand")) + len(next_state.get("playerDiscard"))
    assert total_cards_before == total_cards_after


def test_game_simulator_pitch_arithmetic():
    """Valida cálculo de recursos após pitch de cartas (P - C)."""
    hand = [
        {"cardNumber": "WTR010", "name": "Blue Pitch", "pitch": 3, "cost": 0},
    ]
    state = ImmutableGameState({
        "playerHP": 20,
        "opponentHP": 20,
        "playerResources": [0, 0],
        "playerHand": hand,
        "playerPitch": [],
        "playerActionPoints": 1,
    })

    attack_action = {
        "cardNumber": "WTR020",
        "name": "Heavy Attack",
        "cost": 2,
        "attackPower": 5,
    }

    next_state = GameSimulator.simulate_attack(state, attack_action)
    resources = next_state.get("playerResources")
    # Tinha 0, gerou 3 de pitch, gastou 2 de custo => sobra 1
    assert resources[0] == 1
    assert len(next_state.get("playerPitch")) == 1


def test_game_simulator_combat_chain_damage_resolution():
    """Valida dano líquido sofrido em cadeia de combate e alteração de HP."""
    state = ImmutableGameState({
        "playerHP": 20,
        "opponentHP": 20,
        "playerHand": [{"cardNumber": "DEF01", "defense": 3}],
        "combatChain": [{"cardNumber": "ATK01", "attackPower": 7}],
        "playerDiscard": [],
    })

    # Ataque de 7 bloqueado por 3 => dano líquido = 4
    block_action = {"cards": [{"cardNumber": "DEF01", "defense": 3}]}
    next_state = GameSimulator.simulate_defense(state, block_action)

    assert next_state.get("playerHP") == 16
    assert next_state.get("opponentHP") == 20


def test_game_simulator_overblock_no_healing():
    """Valida que bloqueio superior ao ataque não gera cura nem vida negativa de dano."""
    state = ImmutableGameState({
        "playerHP": 15,
        "opponentHP": 20,
        "playerHand": [{"cardNumber": "DEF01", "defense": 6}],
        "combatChain": [{"cardNumber": "ATK01", "attackPower": 4}],
    })

    block_action = {"cards": [{"cardNumber": "DEF01", "defense": 6}]}
    next_state = GameSimulator.simulate_defense(state, block_action)

    assert next_state.get("playerHP") == 15
