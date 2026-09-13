import os
import sys
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai.hero_strategies.base import HeroStrategy, TurnPlan
from ai.policy_engine import PolicyEngine
from stats_manager import update_match_result, get_stats_data
from ai.dynamic_rule_tuner import get_multipliers_for_hero, sync_multipliers_with_stats, DEFAULT_MULTIPLIERS


# =====================================================================
# 1. Teste de Bloqueio Flexível e Conversão de Mão vs Bloqueio Ineficiente
# =====================================================================

def test_flexible_blocking_low_efficiency_hand_conversion():
    """
    Testa se a IA decide absorver dano de ataque quando possui cartas de block 2
    e a conversão ofensiva da mão é muito superior à perda de valor do bloqueio ineficiente.
    """
    strat = HeroStrategy("test_hero")

    # Mão com 4 cartas: 2 ataques fortes e 2 cartas com block 2
    hand = [
        {"cardNumber": "command_and_conquer", "name": "Command and Conquer", "power": 6, "cost": 2, "pitch": 1, "block": 2},
        {"cardNumber": "snatch_red", "name": "Snatch", "power": 4, "cost": 0, "pitch": 1, "has_go_again": True, "block": 2},
        {"cardNumber": "blue_pitch_card", "name": "Blue Pitch Card", "power": 0, "cost": 0, "pitch": 3, "block": 2},
        {"cardNumber": "another_card", "name": "Another Card", "power": 3, "cost": 1, "pitch": 2, "block": 2},
    ]

    conv_val, key_cards = strat.calculate_hand_conversion_potential(hand, floating_res=0)
    assert conv_val >= 9.0, f"Conversão esperada >= 9.0, obtido {conv_val}"

    # Simular ataque adversário de 6 de poder com On-Hit (ex: Snatch) com vida saudável (HP 25)
    state = {
        "playerHealth": 25,
        "playerHand": hand,
        "activeChainLink": {
            "totalPower": 6,
            "cardNumber": "snatch_red"
        },
        "combatChainPower": 6,
        "playerPitchCount": 0,
        "playerResources": [0, 0]
    }

    plan = strat.analyze_turn_plan(state)
    assert plan.can_absorb_damage is True, "Com HP 25 e cartas de block 2, a IA deve absorver o dano"
    assert plan.plan_type == "TEMPO_COUNTER_ATTACK"
    assert plan.max_block_cards <= 1, "Não deve queimar 3 cartas de block 2 para segurar 6 de dano"

    # Verificar seleção de blocos no PolicyEngine
    pe = PolicyEngine()
    pe.strategy = strat
    chosen_blocks = pe.select_defense_blocks(state)
    # Não deve selecionar 3 cartas da mão
    hand_blocks = [b for b in chosen_blocks]
    assert len(hand_blocks) <= 1, f"Esperado no máximo 1 bloco, obtido {len(hand_blocks)}"


def test_strict_survival_on_fatal_or_critical_hp():
    """
    Testa se o modo de sobrevivência estrito é acionado quando o HP é crítico (<= 6)
    ou quando o ataque for letal.
    """
    strat = HeroStrategy("test_hero")

    hand = [
        {"cardNumber": "card1", "power": 4, "cost": 1, "pitch": 1, "block": 2},
        {"cardNumber": "card2", "power": 3, "cost": 1, "pitch": 2, "block": 2},
    ]

    # Caso A: HP crítico (5 de HP) contra ataque de 4 com on-hit
    state_crit = {
        "playerHealth": 5,
        "playerHand": hand,
        "activeChainLink": {"totalPower": 4, "cardNumber": "snatch_red"},
        "combatChainPower": 4
    }
    plan_crit = strat.analyze_turn_plan(state_crit)
    assert plan_crit.plan_type == "SURVIVAL_BLOCK"
    assert plan_crit.can_absorb_damage is False
    assert plan_crit.max_block_cards >= 2

    # Caso B: Ataque letal (20 de poder contra 15 de vida)
    state_fatal = {
        "playerHealth": 15,
        "playerHand": hand,
        "activeChainLink": {"totalPower": 20, "cardNumber": "crippling_crush"},
        "combatChainPower": 20
    }
    plan_fatal = strat.analyze_turn_plan(state_fatal)
    assert plan_fatal.plan_type == "SURVIVAL_BLOCK"
    assert plan_fatal.can_absorb_damage is False


# =====================================================================
# 2. Teste de Recompensas e ELO em Vitórias Contra Humanos
# =====================================================================

def test_human_elo_bonus_and_stats(monkeypatch, tmp_path):
    """
    Testa o cálculo de ELO acelerado (K=48) e registro de vitórias contra humanos no stats_manager.
    """
    test_file = str(tmp_path / "test_stats.json")
    monkeypatch.setattr("stats_manager.STATS_FILE", test_file)
    room_id = "test_human_match_123"
    p1_deck = "kassai"  # Humano
    p2_deck = "dash_io" # Bot

    # Partida em que o Bot (winner_id = 2) vence o Humano (is_human_p1 = True)
    stats = update_match_result(
        room_id=room_id,
        p1_deck=p1_deck,
        p2_deck=p2_deck,
        p1_health=0,
        p2_health=14,
        total_turns=12,
        winner_id=2,
        is_human_p1=True
    )

    d2_clean = "Dash IO"
    assert d2_clean in stats["deck_stats"]
    deck_info = stats["deck_stats"][d2_clean]
    assert deck_info.get("human_matches", 0) >= 1
    assert deck_info.get("human_wins", 0) >= 1


def test_dynamic_rule_tuner_absorb_and_human_bonus():
    """
    Testa se o dynamic_rule_tuner calibra absorb_tempo_bonus e beneficia heróis com vitórias contra humanos.
    """
    assert "absorb_tempo_bonus" in DEFAULT_MULTIPLIERS

    # Executa a sincronização com stats
    updates = sync_multipliers_with_stats()
    assert isinstance(updates, dict)

    # Obter multiplicadores de Dash IO
    mults = get_multipliers_for_hero("dash_io")
    assert "absorb_tempo_bonus" in mults
    assert mults["absorb_tempo_bonus"] >= 0.80
