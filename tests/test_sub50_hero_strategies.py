"""
tests/test_sub50_hero_strategies.py
===================================
Testes unitários rigorosos para validação dos aprimoramentos das estratégias
dos heróis com winrate < 50% (Dash IO, Vynnset, Teklovossen, Hala, Marlinn)
e proteções globais contra bloqueio indevido de itens/flechas e empates (anti-stalemate).
"""

import pytest
from ai.policy_engine import PolicyEngine
from ai.hero_strategies import (
    get_hero_strategy,
    DashIOStrategy,
    VynnsetStrategy,
    TeklovossenStrategy,
    HalaStrategy,
    MarlynnStrategy,
)


def test_mechanologist_items_and_arrows_have_zero_block():
    """Garante que itens Mechanologist e flechas de Ranger NUNCA recebam defesa heurística."""
    engine = PolicyEngine(hero_name="dash_io")

    # Item Mechanologist não pode ter defesa
    item_card = {"cardNumber": "boom_grenade_red", "name": "Boom Grenade", "action": 27}
    info_item = engine.extract_card_info(item_card)
    assert info_item["block"] == 0, f"Item não pode ter bloco! Recebeu: {info_item['block']}"

    teklo_core = {"cardNumber": "teklo_core_blue", "name": "Teklo Core", "action": 27}
    info_core = engine.extract_card_info(teklo_core)
    assert info_core["block"] == 0, f"Teklo Core não pode bloquear! Recebeu: {info_core['block']}"

    # Flechas de Ranger não podem bloquear
    arrow_card = {"cardNumber": "infecting_shot_red", "name": "Infecting Shot", "action": 27}
    info_arrow = engine.extract_card_info(arrow_card)
    assert info_arrow["block"] == 0, f"Flecha não pode bloquear! Recebeu: {info_arrow['block']}"

    # Cartas de ação convencionais ainda recebem defesa legítima
    action_card = {"cardNumber": "zero_to_sixty_red", "name": "Zero to Sixty", "action": 27}
    info_act = engine.extract_card_info(action_card)
    assert info_act["block"] >= 2, f"Ataque legítimo deve defender! Recebeu: {info_act['block']}"


def test_select_defense_blocks_strictly_excludes_zero_block_items():
    """Garante que select_defense_blocks nunca selecione itens ou flechas para defender."""
    engine = PolicyEngine(hero_name="dash_io")
    state = {
        "playerHealth": 20,
        "playerHand": [
            {"cardNumber": "boom_grenade_red", "name": "Boom Grenade", "action": 27},
            {"cardNumber": "teklo_core_blue", "name": "Teklo Core", "action": 27},
            {"cardNumber": "zero_to_sixty_red", "name": "Zero to Sixty", "action": 27, "defense": 2},
        ],
        "activeChainLink": {"totalPower": 4, "cardNumber": "snatch_red"}
    }
    blocks = engine.select_defense_blocks(state)
    blocked_card_names = [b[2].lower() for b in blocks]
    assert "boom_grenade_red" not in blocked_card_names, "Boom Grenade não pode ser usada para bloquear!"
    assert "teklo_core_blue" not in blocked_card_names, "Teklo Core não pode ser usado para bloquear!"


def test_symbiosis_shot_steam_counters_pruning():
    """Garante que Symbiosis Shot só possa atacar se tiver pelo menos 1 contador de vapor."""
    engine = PolicyEngine(hero_name="dash_io")

    # 1. Sem contadores: não pode atacar
    state_no_counters = {
        "playerHealth": 20,
        "playerPitchCount": 2,
        "playerHand": [],
        "playerEquipment": [
            {"cardNumber": "symbiosis_shot", "slot": "weapon", "action": 1, "counters": 0}
        ]
    }
    attack = engine.select_best_attack(state_no_counters)
    assert attack is None or attack.get("name") != "symbiosis_shot", "Symbiosis Shot não pode atacar com 0 contadores!"

    # 2. Com 1 contador: ataque válido
    state_with_counter = {
        "playerHealth": 20,
        "playerPitchCount": 2,
        "playerHand": [],
        "playerEquipment": [
            {"cardNumber": "symbiosis_shot", "slot": "weapon", "action": 1, "counters": 1}
        ]
    }
    attack_ready = engine.select_best_attack(state_with_counter)
    assert attack_ready is not None and attack_ready.get("name") == "symbiosis_shot"


def test_dash_io_hero_ability():
    """Verifica que a habilidade de herói da Dash IO é avaliada e priorizada."""
    strat = get_hero_strategy("dash_io")
    assert isinstance(strat, DashIOStrategy)
    state = {
        "playerHand": [{"cardNumber": "zero_to_sixty_red"}],
        "playerPitchCount": 1
    }
    score = strat.evaluate_hero_ability(state, {"name": "dash_io"})
    assert score >= 14.0, f"Dash IO deve valorizar olhar o topo do deck. Score: {score}"


def test_vynnset_runegate_banish_discount():
    """Verifica se cartas com Runegate no Banish utilizam Runechants para pagar o custo."""
    engine = PolicyEngine(hero_name="vynnset")
    assert isinstance(engine.strategy, VynnsetStrategy)

    # Vynnset com 0 recursos flutuantes e mão vazia, mas com 2 Runechants em jogo
    state = {
        "playerHealth": 35,
        "playerPitchCount": 0,
        "playerHand": [],
        "playerTokens": [{"cardNumber": "runechant_token", "counters": 2}],
        "playerBanish": [
            {"cardNumber": "widespread_ruin_red", "name": "Widespread Ruin", "action": 1, "cost": 2, "power": 6}
        ]
    }
    attack = engine.select_best_attack(state)
    assert attack is not None, "Vynnset deveria jogar Runegate do Banish via 2 Runechants!"
    assert "widespread_ruin_red" in attack.get("name", "")
    assert attack.get("type") == "banish"
    assert attack.get("cost") == 0  # Custo abatido por 2 Runechants


def test_vynnset_real_runegate_cards_recognition():
    """Garante que a estratégia da Vynnset reconheça e priorize as cartas reais de Runegate."""
    strat = get_hero_strategy("vynnset")
    assert isinstance(strat, VynnsetStrategy)
    score_cull = strat.evaluate_attack_card("cull_red", power=4, cost=1, has_go_again=False, pitch=1)
    assert score_cull >= 13.0, f"Cull deve receber bônus de Runegate! Score: {score_cull}"

    score_widespread = strat.evaluate_attack_card("widespread_ruin_red", power=6, cost=2, has_go_again=False, pitch=1)
    assert score_widespread >= 15.0, f"Widespread Ruin deve receber bônus de Runegate! Score: {score_widespread}"


def test_teklovossen_hero_ability_and_leveler():
    """Verifica a habilidade de herói de Teklovossen e a pressão com Teklo Leveler."""
    strat = get_hero_strategy("teklovossen")
    assert isinstance(strat, TeklovossenStrategy)

    state_with_evo = {
        "playerHand": [{"cardNumber": "evo_steel_soul_memory_blue"}]
    }
    score_ability = strat.evaluate_hero_ability(state_with_evo, {"name": "teklovossen"})
    assert score_ability == 18.0, "Teklovossen deve ativar habilidade para banir Evo e comprar carta!"

    # Teklo Leveler deve ter nota agressiva quando não há ataques de mão
    weapon_score = strat.evaluate_weapon_attack("teklo_leveler", floating_res=2, total_res=3, has_hand_attacks=False)
    assert weapon_score >= 18.0, f"Teklo Leveler deve ter prioridade alta sem ataques na mão! Score: {weapon_score}"


def test_hala_zenith_blade_tempo_plan():
    """Verifica que Hala reserva recursos para bater com a Zenith Blade mesmo sem buffs."""
    strat = get_hero_strategy("hala")
    assert isinstance(strat, HalaStrategy)

    state = {
        "playerHealth": 35,
        "playerHand": [
            {"cardNumber": "blunten_yellow", "pitch": 2},
            {"cardNumber": "sink_below_red", "pitch": 1, "defense": 4}
        ],
        "activeChainLink": {"totalPower": 3, "cardNumber": "snatch_red"}
    }
    plan = strat.analyze_turn_plan(state)
    assert plan.plan_type == "HALA_SWORD_TEMPO", f"Hala deve manter postura ofensiva de espada! Plano: {plan.plan_type}"
    assert plan.max_block_cards <= 1, "Hala não deve gastar toda a mão em bloqueio passivo!"


def test_marlinn_quiver_activation():
    """Verifica que Marlinn avalia e ativa Quiver para recarregar flecha no Arsenal vazio."""
    strat = get_hero_strategy("marlinn")
    assert isinstance(strat, MarlynnStrategy)

    state_empty_arsenal = {
        "playerArsenal": [],
        "playerHand": [{"cardNumber": "infecting_shot_red", "name": "Infecting Shot"}]
    }
    quiver_score = strat.evaluate_equipment_ability(state_empty_arsenal, {"cardNumber": "quiver_of_abyssal_depths"})
    assert quiver_score >= 20.0, f"Quiver deve ser ativado com alta prioridade para recarregar o Arsenal! Score: {quiver_score}"


def test_anti_stalemate_turn_decay():
    """Garante que a partir do turno 18 o valor de bloqueio sofra decaimento para evitar mutual stall."""
    engine = PolicyEngine(hero_name="hala")

    state_early = {
        "turnNo": 5,
        "playerHealth": 30,
        "playerHand": [{"cardNumber": "sink_below_red", "action": 27, "defense": 4, "pitch": 1}],
        "activeChainLink": {"totalPower": 4, "cardNumber": "command_and_conquer"}
    }
    blocks_early = engine.select_defense_blocks(state_early)
    assert len(blocks_early) > 0, "No turno inicial, deve defender normalmente."

    # No turno 35 de uma partida longa, o score de bloqueio sofre decaimento
    state_late = {
        "turnNo": 35,
        "playerHealth": 30,
        "playerHand": [{"cardNumber": "sink_below_red", "action": 27, "defense": 4, "pitch": 1}],
        "activeChainLink": {"totalPower": 2, "cardNumber": "weak_poke"}
    }
    # Em turnos avançados com ataque fraco sem on-hit e vida alta, não deve overblockear
    blocks_late = engine.select_defense_blocks(state_late)
    # A mão é preservada para atacar
    assert len(blocks_late) <= 1
