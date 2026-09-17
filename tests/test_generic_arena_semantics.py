"""
tests/test_generic_arena_semantics.py
======================================
Testes unitários para o motor semântico genérico de cartas e contexto de arena
(ai/policy/card_semantics.py, ai/policy/defense_pruner.py, ai/policy/attack_pruner.py).
"""

import pytest
from unittest.mock import MagicMock
from ai.policy.card_semantics import (
    CardSemanticProfile,
    ArenaThreatContext,
    parse_card_semantics,
    build_arena_threat_context,
)
from ai.policy.defense_pruner import select_defense_blocks
from ai.policy.attack_pruner import select_best_attack


class MockStrategy:
    is_heavy_hero = False

    def analyze_turn_plan(self, state):
        plan = MagicMock()
        plan.plan_type = "STANDARD"
        plan.reserved_card_names = []
        plan.can_absorb_damage = True
        plan.max_block_cards = 2
        return plan

    def is_critical_pitch_resource(self, info, hand, state):
        return False

    def evaluate_block_card(self, name, block, pitch, power, has_go_again):
        return float(block) * 5.0

    def evaluate_attack_card(self, name, power, cost, has_go_again, pitch):
        return float(power) * 2.0

    def modify_attack_candidate_score(self, name, info, turn_plan, score, state):
        return score

    def should_preserve_equipment_on_block(self, name, eq, state, opp_power, is_fatal):
        return False


class MockEngine:
    hero_name = "Kayo"
    hero_class = "BRUTE"
    model = None
    num_mcts_sims = 0
    strategy = MockStrategy()

    def calculate_available_resources(self, state):
        return 0, 3

    def extract_card_info(self, c):
        if isinstance(c, dict):
            return {
                "name": c.get("name", c.get("cardNumber", "")),
                "block": int(c.get("defense", c.get("block", 0))),
                "pitch": int(c.get("pitch", 1)),
                "power": int(c.get("power", 0)),
                "has_go_again": False,
                "action": int(c.get("action", 27)),
                "actionDataOverride": c.get("actionDataOverride"),
            }
        return {
            "name": str(c),
            "block": 3,
            "pitch": 1,
            "power": 3,
            "has_go_again": False,
            "action": 27,
            "actionDataOverride": None,
        }


# ══════════════════════════════════════════════════════════════════
# 1. TESTES DO PARSER SEMÂNTICO (parse_card_semantics)
# ══════════════════════════════════════════════════════════════════

def test_parse_card_semantics_on_hit_damage():
    red = parse_card_semantics("boom_grenade_red")
    assert red.extra_on_hit_damage == 4
    assert red.on_hit_severity == 6.0

    yellow = parse_card_semantics("boom_grenade_yellow")
    assert yellow.extra_on_hit_damage == 3

    blue = parse_card_semantics("boom_grenade_blue")
    assert blue.extra_on_hit_damage == 2

    mauling = parse_card_semantics("mauling_qi_red")
    assert mauling.extra_on_hit_damage == 1


def test_parse_card_semantics_disruption():
    cnc = parse_card_semantics("command_and_conquer_red")
    assert cnc.on_hit_disruption == "destroy_arsenal"
    assert cnc.on_hit_severity == 10.0

    cc = parse_card_semantics("crippling_crush_red")
    assert cc.on_hit_disruption == "discard_hand"
    assert cc.on_hit_severity == 7.5

    ritl = parse_card_semantics("red_in_the_ledger_red")
    assert ritl.on_hit_disruption == "turn_lock"
    assert ritl.on_hit_severity == 9.0

    snatch = parse_card_semantics("snatch_red")
    assert snatch.on_hit_disruption == "draw_cards"
    assert snatch.on_hit_severity == 6.0


def test_parse_card_semantics_grants_modifiers():
    conv = parse_card_semantics("convection_amplifier_red")
    assert "dominate" in conv.grants_evasion

    pen = parse_card_semantics("penetration_script_yellow")
    assert pen.grants_piercing == 1


def test_parse_card_semantics_runtime_fallback():
    # Carta fictícia ou não catalogada, inferida via texto dinâmico
    custom_card = {
        "text": "When this attack hits, deal 5 damage to the opposing hero. Dominate",
        "type": "AA",
        "keywords": ["dominate", "piercing"],
    }
    profile = parse_card_semantics("unknown_super_attack", custom_card)
    assert profile.evasion["dominate"] is True
    assert profile.evasion["piercing"] == 1
    assert profile.extra_on_hit_damage == 5
    assert profile.on_hit_severity == 7.5


# ══════════════════════════════════════════════════════════════════
# 2. TESTES DO CONTEXTO DE AMEAÇA DA ARENA (build_arena_threat_context)
# ══════════════════════════════════════════════════════════════════

def test_build_arena_threat_context_basic():
    state = {
        "playerHealth": 20,
        "activeChainLink": {
            "cardNumber": "snatch_red",
            "totalPower": 4,
            "type": "AA",
        }
    }
    ctx = build_arena_threat_context(state)
    assert ctx.chain_attack_name == "snatch_red"
    assert ctx.chain_base_power == 4
    assert ctx.total_effective_physical_damage == 4
    assert ctx.extra_on_hit_damage == 0
    assert ctx.total_concurrent_arcane_damage == 0
    assert ctx.has_active_dominate is False
    assert ctx.is_lethal_danger is False


def test_build_arena_threat_context_with_opponent_boom_grenade():
    state = {
        "playerHealth": 20,
        "activeChainLink": {
            "cardNumber": "zero_to_sixty_red",
            "totalPower": 4,
            "type": "AA",
        },
        "opponentItems": [
            {"cardNumber": "boom_grenade_red", "counters": 1}
        ]
    }
    ctx = build_arena_threat_context(state)
    assert ctx.chain_base_power == 4
    assert ctx.extra_on_hit_damage == 4
    assert ctx.total_effective_physical_damage == 8
    assert ctx.composite_threat_score >= 6.0
    assert any("boom_grenade_red" in r for r in ctx.threat_reasons)


def test_build_arena_threat_context_with_opponent_convection_amplifier():
    state = {
        "playerHealth": 20,
        "activeChainLink": {
            "cardNumber": "command_and_conquer_red",
            "totalPower": 6,
            "type": "AA",
        },
        "opponentItems": [
            {"cardNumber": "convection_amplifier_red", "counters": 1}
        ]
    }
    ctx = build_arena_threat_context(state)
    assert ctx.has_active_dominate is True
    assert any("Concede Dominate" in r for r in ctx.threat_reasons)


def test_build_arena_threat_context_with_opponent_penetration_script():
    state = {
        "playerHealth": 20,
        "activeChainLink": {
            "cardNumber": "payload_red",
            "totalPower": 6,
            "type": "AA",
        },
        "theirItems": [
            {"cardNumber": "penetration_script_yellow", "counters": 1}
        ]
    }
    ctx = build_arena_threat_context(state)
    assert ctx.has_active_piercing is True
    assert any("Piercing" in r for r in ctx.threat_reasons)


def test_build_arena_threat_context_with_runechants():
    state = {
        "playerHealth": 20,
        "activeChainLink": {
            "cardNumber": "meat_axe",
            "totalPower": 3,
            "type": "W",
        },
        "opponentAuras": [
            {"cardNumber": "runechant", "counters": 4}
        ]
    }
    ctx = build_arena_threat_context(state)
    assert ctx.total_concurrent_arcane_damage == 4
    assert any("Runechants" in r for r in ctx.threat_reasons)


def test_build_arena_threat_context_lethal_danger():
    state = {
        "playerHealth": 7,
        "activeChainLink": {
            "cardNumber": "command_and_conquer_red",
            "totalPower": 6,
            "type": "AA",
        },
        "opponentAuras": [
            {"cardNumber": "runechant", "counters": 2}
        ]
    }
    # Dano físico 6 + arcano 2 = 8 >= HP 7 -> Perigo Letal
    ctx = build_arena_threat_context(state)
    assert ctx.is_lethal_danger is True
    assert any("PERIGO LETAL" in r for r in ctx.threat_reasons)


# ══════════════════════════════════════════════════════════════════
# 3. TESTES DE PODA DE DEFESA COM SEMÂNTICA DA ARENA
# ══════════════════════════════════════════════════════════════════

def test_defense_pruner_respects_arena_dominate():
    engine = MockEngine()
    state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "activeChainLink": {
            "cardNumber": "zero_to_sixty_red",
            "totalPower": 4,
            "type": "AA",
        },
        # Convection Amplifier na arena do oponente ativa Dominate
        "opponentItems": [
            {"cardNumber": "convection_amplifier_red", "counters": 1}
        ],
        "playerHand": [
            {"name": "sink_below_red", "defense": 4, "type": "DR", "pitch": 1, "actionDataOverride": "0"},
            {"name": "fate_foreseen_red", "defense": 4, "type": "DR", "pitch": 1, "actionDataOverride": "1"},
        ],
        "playerEquipment": [],
    }
    blocks = select_defense_blocks(engine, state)
    # Sob dominate, não pode selecionar mais de 1 carta da mão
    hand_blocks = [b for b in blocks if b[1] in ("0", "1")]
    assert len(hand_blocks) <= 1


def test_defense_pruner_accounts_for_arena_boom_grenade():
    engine = MockEngine()
    state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "activeChainLink": {
            "cardNumber": "zero_to_sixty_red",
            "totalPower": 4,
            "type": "AA",
        },
        # Boom grenade no oponente adiciona 4 de dano on-hit (efetivo = 8)
        "opponentItems": [
            {"cardNumber": "boom_grenade_red", "counters": 1}
        ],
        "playerHand": [
            {"name": "card_a", "defense": 3, "type": "AA", "pitch": 1, "actionDataOverride": "0"},
            {"name": "card_b", "defense": 3, "type": "AA", "pitch": 1, "actionDataOverride": "1"},
            {"name": "card_c", "defense": 3, "type": "AA", "pitch": 1, "actionDataOverride": "2"},
        ],
        "playerEquipment": [],
    }
    blocks = select_defense_blocks(engine, state)
    # Com 8 de poder efetivo (4 base + 4 granada), para cobrir breakpoint e mitigar on-hit,
    # deve selecionar múltiplos bloqueadores se disponíveis
    total_blocked = sum(3 for b in blocks if b[1] in ("0", "1", "2"))
    assert total_blocked >= 6 or len(blocks) >= 2


def test_defense_pruner_piercing_avoids_vanilla_equipment_overuse():
    engine = MockEngine()
    state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "activeChainLink": {
            "cardNumber": "drill_shot_red",
            "totalPower": 4,
            "type": "AA",
            "hasPiercing": True,
        },
        "playerHand": [
            {"name": "def_card", "defense": 3, "type": "AA", "pitch": 1, "actionDataOverride": "0"},
        ],
        "playerEquipment": [
            {"name": "ironrot_helm", "defense": 1, "bladeBreak": True, "actionDataOverride": "eq_0"}
        ],
    }
    blocks = select_defense_blocks(engine, state)
    # Ataque com Piercing ganha +1 se bloqueado por equipamento,
    # armadura com block 1 gera mitigação líquida 0 e deve ser penalizada/evitada
    eq_blocks = [b for b in blocks if b[1] == "eq_0"]
    assert len(eq_blocks) == 0


# ══════════════════════════════════════════════════════════════════
# 4. TESTES DE PODA DE ATAQUE COM ITENS PRÓPRIOS NA ARENA
# ══════════════════════════════════════════════════════════════════

def test_attack_pruner_prioritizes_hit_with_own_boom_grenade():
    engine = MockEngine()
    state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerAP": 1,
        # Nosso próprio item na arena
        "playerItems": [
            {"cardNumber": "boom_grenade_red", "counters": 1}
        ],
        "playerHand": [
            {"name": "zero_to_sixty_red", "cardNumber": "zero_to_sixty_red", "power": 4, "type": "AA", "pitch": 1, "cost": 0, "action": 27, "actionDataOverride": "0"},
            {"name": "high_octane_red", "cardNumber": "high_octane_red", "power": 0, "type": "A", "pitch": 1, "cost": 0, "action": 27, "actionDataOverride": "1"},
        ]
    }
    best = select_best_attack(engine, state)
    assert best is not None
    assert best["name"] == "zero_to_sixty_red"
    # Base score = power 4 * 2 = 8.0, + 3.0 por has_own_on_hit_item
    assert best["score"] >= 11.0

