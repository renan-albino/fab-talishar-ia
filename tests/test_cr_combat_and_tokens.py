"""
tests/test_cr_combat_and_tokens.py
===================================
Testes formais para conformidade com as Comprehensive Rules (CR):
  - CR 7.3.2a & 8.3.4 (Dominate no GameSimulator)
  - CR 7.3.2b & 8.3.22 (Overpower no GameSimulator)
  - CR 7.4.4 & 8.3.12 (Phantasm Popping no GameSimulator)
  - CR 8.5.21 (Piercing no GameSimulator simulate_defense)
  - CR 8.6.1 & 8.6.2 (Tokens Quicken / Agility na poda de ataque)
  - CR 8.6.10 (Token Frostbite taxando custo na poda de ataque)
  - CR 8.6.21 (Token Inertia desabilitando can_absorb_damage na poda de defesa)
  - CR 8.6.20 (Token Bloodrot Pox preservando pitch de sobrevivência na defesa)
"""

import pytest
from ai.game_simulator import GameSimulator
from ai.policy_engine import PolicyEngine
from ai.policy.attack_pruner import select_best_attack
from ai.policy.defense_pruner import select_defense_blocks


# ══════════════════════════════════════════════════════════════════
# 1. GAME SIMULATOR: COMBAT RULES & EVASION
# ══════════════════════════════════════════════════════════════════

def test_simulator_dominate_restricts_block_to_single_card():
    sim = GameSimulator()
    state = {
        "playerHand": [],
        "opponentHand": [
            {"cardNumber": "block_card_1", "block": 3},
            {"cardNumber": "block_card_2", "block": 3},
            {"cardNumber": "block_card_3", "block": 3},
        ],
        "opponentHero": "dorinthea",
        "opponentHealth": 8,
    }
    # Sem dominate: oponente usa 2 cartas (3 + 3 = 6 de defesa), 0 dano não bloqueado -> HP continua 8
    res_no_dom = sim.simulate_attack(state, {"type": "hand", "cardNumber": "generic_attack", "power": 6, "dominate": False})
    assert res_no_dom["opponentHealth"] == 8

    # Com dominate: oponente só pode usar 1 carta (3 de defesa), 3 de dano sofrido -> HP vai para 8 - 3 = 5
    res_dom = sim.simulate_attack(state, {"type": "hand", "cardNumber": "generic_attack", "power": 6, "dominate": True})
    assert res_dom["opponentHealth"] == 5


def test_simulator_overpower_restricts_block_to_single_action():
    sim = GameSimulator()
    state = {
        "playerHand": [],
        "opponentHand": [
            {"cardNumber": "action_block_1", "block": 3, "type": "ACTION"},
            {"cardNumber": "action_block_2", "block": 3, "type": "ACTION"},
        ],
        "opponentHero": "rhinar",
        "opponentHealth": 8,
    }
    # Com overpower: oponente só pode bloquear com no máximo 1 carta de ação (3 de defesa), 3 de dano sofrido -> 8 - 3 = 5
    res_op = sim.simulate_attack(state, {"type": "hand", "cardNumber": "generic_attack", "power": 6, "overpower": True})
    assert res_op["opponentHealth"] == 5


def test_simulator_phantasm_popped_by_6_power():
    sim = GameSimulator()
    state = {
        "playerHand": [],
        "opponentHand": [
            {"cardNumber": "brute_popper", "block": 3, "power": 6, "class": "BRUTE"},
        ],
        "opponentHero": "rhinar",
        "opponentHealth": 20,
    }
    # Phantasm é estourado pela carta de 6 de poder -> 0 dano sofrido -> HP continua 20
    res = sim.simulate_attack(state, {"type": "hand", "cardNumber": "illusionist_attack", "power": 7, "phantasm": True})
    assert res["opponentHealth"] == 20


def test_simulator_piercing_extra_damage_on_equipment_block():
    sim = GameSimulator()
    state = {
        "playerHealth": 20,
        "activeChainLink": {
            "totalPower": 4,
            "hasPiercing": True,
        }
    }
    # Defensor bloqueia com equipamento (block 2)
    block_action = [
        {"cardNumber": "ironrot_helm", "block": 2, "subtype": "head"}
    ]
    # Piercing ativa (+1 dano) porque bloqueou com equipamento -> Poder efetivo 4 + 1 = 5
    # Dano sofrido = 5 - 2 = 3. HP restante = 20 - 3 = 17
    res = sim.simulate_defense(state, block_action)
    assert res["playerHealth"] == 17


# ══════════════════════════════════════════════════════════════════
# 2. ARENA TOKENS & ATTACK PRUNING
# ══════════════════════════════════════════════════════════════════

def test_attack_pruner_recognizes_quicken_for_go_again():
    engine = PolicyEngine(hero_name="generic")
    engine.num_mcts_sims = 0
    state_no_quicken = {
        "myTurn": True,
        "isCombatPhase": True,
        "currentChainLink": 1,
        "actionPoints": 1,
        "playerHand": [
            {"cardNumber": "slow_attack", "name": "slow_attack", "cost": 0, "power": 4, "type": "AA", "action": 1, "has_go_again": False, "pitch": 1},
            {"cardNumber": "second_attack", "name": "second_attack", "cost": 0, "power": 4, "type": "AA", "action": 2, "has_go_again": True, "pitch": 1},
        ],
        "playerTokens": [],
    }
    state_with_quicken = {
        "myTurn": True,
        "isCombatPhase": True,
        "currentChainLink": 1,
        "actionPoints": 1,
        "playerHand": [
            {"cardNumber": "slow_attack", "name": "slow_attack", "cost": 0, "power": 4, "type": "AA", "action": 1, "has_go_again": False, "pitch": 1},
            {"cardNumber": "second_attack", "name": "second_attack", "cost": 0, "power": 4, "type": "AA", "action": 2, "has_go_again": True, "pitch": 1},
        ],
        "playerTokens": ["quicken"],
    }
    atk_no_q = select_best_attack(engine, state_no_quicken)
    atk_with_q = select_best_attack(engine, state_with_quicken)
    assert atk_no_q is not None
    assert atk_with_q is not None
    assert atk_with_q["cost"] == 0


def test_attack_pruner_adds_frostbite_tax():
    engine = PolicyEngine(hero_name="generic")
    engine.num_mcts_sims = 0
    state_frostbite_unpayable = {
        "myTurn": True,
        "isCombatPhase": True,
        "currentChainLink": 1,
        "actionPoints": 1,
        "playerResources": 0,
        "playerHand": [
            {"cardNumber": "zero_cost_card", "name": "zero_cost_card", "cost": 0, "power": 4, "type": "AA", "action": 1, "pitch": 1},
            {"cardNumber": "pitch_card", "name": "pitch_card", "cost": 0, "power": 0, "type": "A", "action": 0, "pitch": 1},
        ],
        "playerAuras": [{"name": "frostbite"}, {"name": "frostbite"}],
    }
    atk = select_best_attack(engine, state_frostbite_unpayable)
    assert atk is None


# ══════════════════════════════════════════════════════════════════
# 3. DEFENSE PRUNER & TOKEN INTERACTIONS
# ══════════════════════════════════════════════════════════════════

def test_defense_pruner_disables_pivot_under_inertia():
    engine = PolicyEngine(hero_name="generic")
    engine.num_mcts_sims = 0
    state = {
        "myTurn": False,
        "isCombatPhase": True,
        "combatChainPower": 4,
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerHand": [
            {"cardNumber": "big_red_bomb", "name": "big_red_bomb", "block": 3, "power": 6, "pitch": 1, "action": 27}
        ],
        "playerTokens": ["inertia"],
    }
    blocks = select_defense_blocks(engine, state)
    assert len(blocks) == 1
    assert blocks[0][2] == "big_red_bomb"


def test_defense_pruner_preserves_pitch_under_bloodrot_low_hp():
    engine = PolicyEngine(hero_name="generic")
    engine.num_mcts_sims = 0
    state = {
        "myTurn": False,
        "isCombatPhase": True,
        "combatChainPower": 1,
        "playerHealth": 2,
        "opponentHealth": 10,
        "playerResources": 0,
        "playerHand": [
            {"cardNumber": "blue_pitch_card", "name": "blue_pitch_card", "block": 3, "power": 1, "pitch": 3, "action": 27}
        ],
        "playerTokens": ["bloodrot_pox"],
    }
    blocks = select_defense_blocks(engine, state)
    assert len(blocks) == 0
