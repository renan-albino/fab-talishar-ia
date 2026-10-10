"""
tests/test_on_hit_and_turn_zero_rules.py
========================================
Testes unitários para o Modelo Dinâmico de On-Hits e Bloqueio Seletivo no Turno 0 (CR 4.4.3f):
1. Normalização de slug e metadados semânticos em on_hit_evaluator.
2. Compra de cartas com valor dinâmico de arquétipo (Snatch, Mask of Momentum no 3º link).
3. Descarte, banimento e remoção de teto de ação (Felling of the Crown, Pummel, C&C, Erase Face).
4. Tokens de tributo e escala exponencial de alavancagem de HP.
5. Bloqueio Seletivo no Turno 0 (CR 4.4.3f):
   - Detecção de primeiro turno da partida.
   - Desativação de absorção cega e planos de tempo.
   - Custo de oportunidade zero para cartas comuns da mão.
   - Preservação de peças insubstituíveis de combo enquanto demais cartas cobrem opp_power.
   - Proibição de ativação de habilidades de armadura no vazio (Boots of Omni's Ward, Flick Knives).
"""

import pytest
from ai.policy.on_hit_evaluator import estimate_on_hit_value, normalize_card_slug
from ai.policy.defense_pruner import select_defense_blocks
from ai.policy_engine import PolicyEngine


# ══════════════════════════════════════════════════════════════════
# 1. MODELO DINÂMICO DE IMPACTO ON-HIT
# ══════════════════════════════════════════════════════════════════

def test_slug_normalization():
    assert normalize_card_slug("Command and Conquer") == "command_and_conquer"
    assert normalize_card_slug("command_and_conquer_red") == "command_and_conquer"
    assert normalize_card_slug("snatch_r") == "snatch"
    assert normalize_card_slug("snatch_yellow") == "snatch"
    assert normalize_card_slug("snatch_blue") == "snatch"
    assert normalize_card_slug("Felling of the Crown") == "felling_of_the_crown"
    assert normalize_card_slug("felling_of_the_crown_red") == "felling_of_the_crown"
    assert normalize_card_slug("Erase Face") == "erase_face"
    assert normalize_card_slug("pummel_red") == "pummel"
    assert normalize_card_slug("Mask of Momentum") == "mask_of_momentum"


def test_card_draw_archetype_and_chain_link():
    # Snatch para Ninjas / Aggro (~4.0 pts)
    state_ninja = {"playerClass": "ninja", "playerHealth": 20}
    assert estimate_on_hit_value("snatch_red", state_ninja) == 4.0

    # Snatch para Guardians / Controle (~3.5 pts)
    state_guardian = {"playerClass": "guardian", "playerHealth": 20}
    assert estimate_on_hit_value("snatch_red", state_guardian) == 3.5

    # Mask of Momentum no 1º link não dispara on-hit (0.0 pts)
    state_link1 = {"currentChainLink": 1, "playerHealth": 20}
    assert estimate_on_hit_value("mask_of_momentum", state_link1) == 0.0

    # Mask of Momentum no 3º link dispara compra de carta (~3.5 a 4.0 pts)
    state_link3 = {"currentChainLink": 3, "playerHealth": 20}
    val_link3 = estimate_on_hit_value("mask_of_momentum", state_link3)
    assert 3.5 <= val_link3 <= 4.0


def test_hand_removal_and_arsenal_destruction():
    state_20 = {"playerHealth": 20}

    # Felling of the Crown (Decompose / banish da mão = 4.0 pts).
    # Somado aos 7 de poder de ataque, atinge 11.0 pts.
    felling_on_hit = estimate_on_hit_value("felling_of_the_crown_red", state_20)
    assert felling_on_hit == 4.0
    total_felling_threat = 7 + felling_on_hit
    assert total_felling_threat >= 11.0

    # Erase Face (destrói sinergias de classe/talento da mão/deck = 4.0 pts)
    assert estimate_on_hit_value("erase_face_red", state_20) == 4.0

    # Pummel (descarte forçado da mão = 3.8 pts)
    assert estimate_on_hit_value("pummel_red", state_20) == 3.8

    # Command and Conquer (destruição de arsenal = 5.0 pts com d-react lock)
    assert estimate_on_hit_value("command_and_conquer_red", state_20) == 5.0

    # Leave No Witnesses (banimento de arsenal = 4.0 pts)
    assert estimate_on_hit_value("leave_no_witnesses", state_20) == 4.0


def test_tribute_tokens_and_life_leverage():
    state_20 = {"playerHealth": 20}

    # Tokens de tributo entre 1.5 e 2.5 pts
    assert 1.5 <= estimate_on_hit_value("bloodrot_pox", state_20) <= 2.5
    assert 1.5 <= estimate_on_hit_value("frostbite", state_20) <= 2.5
    assert 1.5 <= estimate_on_hit_value("frailty", state_20) <= 2.5

    # Alavancagem de HP: conforme HP diminui, peso cresce exponencialmente
    state_hp20 = {"playerHealth": 20}
    state_hp12 = {"playerHealth": 12}
    state_hp6 = {"playerHealth": 6}
    state_hp2 = {"playerHealth": 2}

    val_20 = estimate_on_hit_value("snatch_red", state_hp20)
    val_12 = estimate_on_hit_value("snatch_red", state_hp12)
    val_6 = estimate_on_hit_value("snatch_red", state_hp6)
    val_2 = estimate_on_hit_value("snatch_red", state_hp2)

    assert val_20 < val_12 < val_6 < val_2
    assert val_2 > val_20 * 2.0  # Em 2 HP, on-hit perigoso ganha peso exponencial dobrado


# ══════════════════════════════════════════════════════════════════
# 2. BLOQUEIO SELETIVO NO TURNO 0 (CR 4.4.3f)
# ══════════════════════════════════════════════════════════════════

def test_turn_0_blocks_up_to_opp_power_with_free_hand_cards():
    """
    No Turno 0 (CR 4.4.3f), cartas da mão têm custo de oportunidade 0 (recompra até intelecto).
    O bot não deve absorver dano cegamente; deve cobrir opp_power usando cartas comuns.
    """
    engine = PolicyEngine(hero_name="generic")
    engine.num_mcts_sims = 0

    state_turn_0 = {
        "turnNo": 1,
        "turnPlayer": 1,
        "playerID": 2,
        "playerHealth": 20,
        "opponentHealth": 20,
        "combatChainPower": 6,
        "activeChainLink": {"cardNumber": "generic_attack", "totalPower": 6},
        "playerHand": [
            {"cardNumber": "card_a", "name": "Card A", "block": 3, "power": 4, "pitch": 1, "action": 27},
            {"cardNumber": "card_b", "name": "Card B", "block": 3, "power": 4, "pitch": 1, "action": 27},
            {"cardNumber": "card_c", "name": "Card C", "block": 3, "power": 3, "pitch": 2, "action": 27},
            {"cardNumber": "card_d", "name": "Card D", "block": 3, "power": 3, "pitch": 3, "action": 27},
        ],
    }

    blocks = select_defense_blocks(engine, state_turn_0)
    total_blocked = sum(engine.extract_card_info(state_turn_0["playerHand"][b[0]])["block"] for b in blocks)
    # Deve bloquear exatamente 6 (2 cartas de 3 block) para cobrir opp_power sem overblocking
    assert len(blocks) == 2
    assert total_blocked == 6


def test_turn_0_preserves_irreplaceable_combo_piece():
    """
    No Turno 0, peças reservadas de combo insubstituíveis são poupadas,
    enquanto outras cartas da mão bloqueiam até cobrir opp_power.
    """
    engine = PolicyEngine(hero_name="generic")
    engine.num_mcts_sims = 0

    # Simular peça de combo reservada no TurnPlan
    turn_plan = engine.strategy.analyze_turn_plan({})
    turn_plan.reserved_card_names.add("combo_finisher")
    turn_plan.plan_type = "COMBO_KILL"
    engine.strategy.analyze_turn_plan = lambda s: turn_plan

    state_turn_0 = {
        "turnNo": 1,
        "turnPlayer": 1,
        "playerID": 2,
        "playerHealth": 20,
        "opponentHealth": 20,
        "combatChainPower": 6,
        "activeChainLink": {"cardNumber": "opp_swing", "totalPower": 6},
        "playerHand": [
            {"cardNumber": "combo_finisher", "name": "combo_finisher", "block": 3, "power": 8, "pitch": 1, "action": 27},
            {"cardNumber": "blocker_1", "name": "Blocker 1", "block": 3, "power": 3, "pitch": 2, "action": 27},
            {"cardNumber": "blocker_2", "name": "Blocker 2", "block": 3, "power": 3, "pitch": 3, "action": 27},
        ],
    }

    blocks = select_defense_blocks(engine, state_turn_0)
    blocked_names = [b[2].lower() for b in blocks]

    assert "combo_finisher" not in blocked_names, "Peça única de combo deve ser preservada no Turno 0"
    assert "blocker_1" in blocked_names
    assert "blocker_2" in blocked_names


def test_turn_0_prohibits_armor_abilities_in_the_void():
    """
    No Turno 0, armaduras com habilidades ativáveis de sacrifício (boots_of_omnis_ward, flick_knives, etc.)
    são proibidas de serem ativadas no vazio ou gastas para bloquear quando a mão recompra de graça.
    """
    engine = PolicyEngine(hero_name="generic")
    engine.num_mcts_sims = 0

    state_turn_0 = {
        "turnNo": 1,
        "turnPlayer": 1,
        "playerID": 2,
        "playerHealth": 20,
        "opponentHealth": 20,
        "combatChainPower": 4,
        "activeChainLink": {"cardNumber": "opp_attack", "totalPower": 4},
        "playerHand": [
            {"cardNumber": "hand_blocker", "name": "Hand Blocker", "block": 3, "power": 3, "pitch": 3, "action": 27},
        ],
        "playerEquipment": [
            {"cardNumber": "boots_of_omnis_ward", "slot": "Legs", "action": 3, "defense": 1, "actionDataOverride": "10"},
            {"cardNumber": "flick_knives", "slot": "Arms", "action": 3, "defense": 1, "actionDataOverride": "11"},
            {"cardNumber": "ironrot_gauntlet", "slot": "Arms", "action": 3, "defense": 1, "actionDataOverride": "12"},
        ],
    }

    blocks = select_defense_blocks(engine, state_turn_0)
    blocked_cards = [b[2].lower() for b in blocks]

    assert "boots_of_omnis_ward" not in blocked_cards, "Boots of Omni's Ward não pode ser gasta no Turno 0"
    assert "flick_knives" not in blocked_cards, "Flick Knives não pode ser gasta no Turno 0"
