"""
tests/test_sub50_hero_strategies.py
===================================
Testes unitários rigorosos para validação dos aprimoramentos das estratégias
dos heróis com winrate < 50% (Dash IO, Vynnset, Teklovossen, Hala, Kassai, Marlinn)
e proteções globais contra bloqueio indevido de itens/goldfin, aprendizado de ordem de turno
e defesa mínima viável (anti-stalemate).
"""

import pytest
from ai.policy_engine import PolicyEngine
from ai.hero_strategies import (
    get_hero_strategy,
    DashIOStrategy,
    VynnsetStrategy,
    TeklovossenStrategy,
    HalaStrategy,
    KassaiStrategy,
    MarlynnStrategy,
)
from ai.turn_order_learning import get_turn_order_learner, TurnOrderLearner


def test_mechanologist_items_and_goldfin_have_zero_block_and_arrows_can_block():
    """
    Garante que itens Mechanologist e Goldfin Harpoon tenham 0 de defesa,
    enquanto flechas legítimas de Ranger POSSUEM defesa padrão de FaB (>= 2).
    """
    engine = PolicyEngine(hero_name="marlinn")

    # Item Mechanologist não pode ter defesa
    item_card = {"cardNumber": "boom_grenade_red", "name": "Boom Grenade", "action": 27}
    info_item = engine.extract_card_info(item_card)
    assert info_item["block"] == 0, f"Item não pode ter bloco! Recebeu: {info_item['block']}"

    teklo_core = {"cardNumber": "teklo_core_blue", "name": "Teklo Core", "action": 27}
    info_core = engine.extract_card_info(teklo_core)
    assert info_core["block"] == 0, f"Teklo Core não pode bloquear! Recebeu: {info_core['block']}"

    # Exceção FaB: Goldfin Harpoon Yellow não defende (0) e não gera recurso (pitch 0)
    goldfin_card = {"cardNumber": "goldfin_harpoon_yellow", "name": "Goldfin Harpoon", "action": 27}
    info_goldfin = engine.extract_card_info(goldfin_card)
    assert info_goldfin["block"] == 0, f"Goldfin Harpoon deve ter 0 de bloco! Recebeu: {info_goldfin['block']}"
    assert info_goldfin["pitch"] == 0, f"Goldfin Harpoon deve ter 0 de pitch! Recebeu: {info_goldfin['pitch']}"

    # Regra Oficial FaB: Flechas comuns POSSUEM defesa e podem ser usadas para bloquear!
    arrow_card = {"cardNumber": "infecting_shot_red", "name": "Infecting Shot", "action": 27}
    info_arrow = engine.extract_card_info(arrow_card)
    assert info_arrow["block"] >= 2, f"Flecha legítima deve defender! Recebeu: {info_arrow['block']}"

    # Ataque convencional
    action_card = {"cardNumber": "zero_to_sixty_red", "name": "Zero to Sixty", "action": 27}
    info_act = engine.extract_card_info(action_card)
    assert info_act["block"] >= 2, f"Ataque legítimo deve defender! Recebeu: {info_act['block']}"


def test_select_defense_blocks_allows_arrows_and_excludes_items_and_goldfin():
    """Garante que select_defense_blocks bloqueie com flechas, mas exclua itens e Goldfin Harpoon."""
    engine = PolicyEngine(hero_name="marlinn")
    state = {
        "playerHealth": 20,
        "playerHand": [
            {"cardNumber": "boom_grenade_red", "name": "Boom Grenade", "action": 27},
            {"cardNumber": "goldfin_harpoon_yellow", "name": "Goldfin Harpoon", "action": 27},
            {"cardNumber": "infecting_shot_red", "name": "Infecting Shot", "action": 27, "defense": 3},
        ],
        "activeChainLink": {"totalPower": 4, "cardNumber": "snatch_red"}
    }
    blocks = engine.select_defense_blocks(state)
    blocked_card_names = [b[2].lower() for b in blocks]
    assert "boom_grenade_red" not in blocked_card_names, "Boom Grenade não pode ser usada para bloquear!"
    assert "goldfin_harpoon_yellow" not in blocked_card_names, "Goldfin Harpoon não pode bloquear!"
    assert any("infecting_shot" in name for name in blocked_card_names), "Infecting Shot deve ser usada para bloquear!"


def test_turn_order_learner_priors():
    """Verifica se heróis de setup (Dash IO, Vynnset, Teklovossen) escolhem 'Go First' por padrão."""
    learner = TurnOrderLearner(stats_file="data/test_turn_order_temp.json")
    
    # Setup heroes devem preferir 'Go First' (epsilon=0 para teste determinístico)
    assert learner.get_optimal_turn_order("dash_io", epsilon=0.0) == "Go First"
    assert learner.get_optimal_turn_order("vynnset", epsilon=0.0) == "Go First"
    assert learner.get_optimal_turn_order("teklovossen", epsilon=0.0) == "Go First"

    # Heróis genéricos sem prior preferem 'Go Second' por padrão para ter carta extra no fim do primeiro turno
    assert learner.get_optimal_turn_order("bravo", epsilon=0.0) == "Go Second"


def test_symbiosis_shot_steam_counters_pruning():
    """Garante que Symbiosis Shot só possa atacar se tiver pelo menos 1 contador de vapor."""
    engine = PolicyEngine(hero_name="dash_io")

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


def test_vynnset_hero_ability_strictly_requires_runegate_attack():
    """Garante que Vynnset só ative sua habilidade se houver um ataque de Runegate na mão para banir."""
    strat = get_hero_strategy("vynnset")
    assert isinstance(strat, VynnsetStrategy)

    # 1. Mão SEM ataque de Runegate (apenas auras e cartas genéricas): NÃO deve ativar a habilidade
    state_without_runegate = {
        "playerHand": [
            {"cardNumber": "fasting_carcass_red", "name": "Fasting Carcass"},
            {"cardNumber": "sink_below_red", "name": "Sink Below"}
        ]
    }
    score_no = strat.evaluate_hero_ability(state_without_runegate, {"name": "vynnset"})
    assert score_no == 0.0, "Vynnset não deve ativar habilidade sem ataque de Runegate na mão!"

    # 2. Mão COM ataque de Runegate (ex: Cull Red): DEVE ativar para criar Runechant e Piercing 1
    state_with_runegate = {
        "playerHand": [
            {"cardNumber": "cull_red", "name": "Cull"},
            {"cardNumber": "sink_below_red", "name": "Sink Below"}
        ]
    }
    score_yes = strat.evaluate_hero_ability(state_with_runegate, {"name": "vynnset"})
    assert score_yes >= 20.0, "Vynnset deve ativar habilidade com alta prioridade quando tem Runegate na mão!"


def test_vynnset_blocks_with_second_runegate_attack():
    """
    Garante que Vynnset não penalize bloquear com um ataque de Runegate
    se ela tiver 2 ou mais ataques de Runegate na mão.
    """
    strat = get_hero_strategy("vynnset")
    assert isinstance(strat, VynnsetStrategy)

    # Com apenas 1 Runegate na mão: penaliza com -12.0 para preservar o ataque ofensivo
    score_single = strat.evaluate_block_card("cull_red", block_val=3, pitch=1, power=4, has_go_again=False, runegate_in_hand=1)
    assert score_single < 0, f"Com apenas 1 Runegate, deve preservar! Score: {score_single}"

    # Com 2 Runegates na mão: não penaliza o sobressalente
    score_double = strat.evaluate_block_card("cull_red", block_val=3, pitch=1, power=4, has_go_again=False, runegate_in_hand=2)
    assert score_double > 0, f"Com 2 Runegates, Vynnset pode bloquear com o sobressalente! Score: {score_double}"


def test_teklovossen_evo_assembly_and_singularity():
    """Verifica que Teklovossen foca em montar os 4 Evos em jogos lentos e valoriza Singularity."""
    strat = get_hero_strategy("teklovossen")
    assert isinstance(strat, TeklovossenStrategy)

    # Estado com apenas 1 Evo equipado contra ataque moderado (power=3)
    state = {
        "playerHealth": 35,
        "playerHand": [
            {"cardNumber": "evo_steel_soul_tower_blue", "name": "Evo Steel Soul Tower"},
            {"cardNumber": "singularity_blue", "name": "Singularity", "pitch": 3},
            {"cardNumber": "teklo_core_blue", "name": "Teklo Core", "pitch": 3}
        ],
        "playerEquipment": [
            {"slot": "head", "cardNumber": "evo_circuit_breaker_head"}
        ],
        "activeChainLink": {"totalPower": 3, "cardNumber": "snatch_red"}
    }
    plan = strat.analyze_turn_plan(state)
    assert plan.plan_type == "TEKLOVOSSEN_EVO_ASSEMBLY", f"Deveria ativar plano TEKLOVOSSEN_EVO_ASSEMBLY! Plano: {plan.plan_type}"
    assert "singularity_blue" in plan.reserved_card_names, "Singularity deve ser reservada para não bloquear!"

    # Singularity nunca deve ser dada pitch
    pitch_score_singularity = strat.evaluate_pitch_card("singularity_blue", pitch=3, cost=0, power=0, has_go_again=False)
    assert pitch_score_singularity <= -50.0, "Singularity NUNCA pode ser dada pitch!"


def test_teklovossen_banish_evo_instant_speed():
    """
    Garante que equipar Evo do Banish só seja possível se a habilidade do Teklovossen foi ativada.
    Sem a ativação prévia da habilidade no turno, o Evo permanece banido e inerte.
    Com a habilidade ativada, ele ganha velocidade Instant (custo 0 de AP, sem ganho de AP).
    """
    engine = PolicyEngine(hero_name="teklovossen")

    # 1. Sem ativar a habilidade de herói: o Evo fica lá banido e NÃO é selecionado
    state_without_ability = {
        "playerHealth": 30,
        "playerPitchCount": 4,
        "playerHand": [],
        "playerBanish": [
            {"cardNumber": "evo_steel_soul_memory_blue", "name": "Evo Steel Soul Memory", "action": 1, "cost": 4, "power": 0}
        ],
        "teklo_ability_active": False
    }
    attack_inactive = engine.select_best_attack(state_without_ability)
    assert attack_inactive is None, "Evo no Banish não pode ser jogado se a habilidade do Teklovossen não foi ativada!"

    # 2. Com a habilidade de herói ativada no turno: joga na velocidade Instant (ap_cost = 0)
    state_with_ability = {
        "playerHealth": 30,
        "playerPitchCount": 4,
        "playerHand": [],
        "playerBanish": [
            {"cardNumber": "evo_steel_soul_memory_blue", "name": "Evo Steel Soul Memory", "action": 1, "cost": 4, "power": 0}
        ],
        "teklo_ability_active": True
    }
    attack_active = engine.select_best_attack(state_with_ability)
    assert attack_active is not None
    assert "evo" in attack_active["name"]
    assert attack_active.get("is_instant") is True
    assert attack_active.get("ap_cost") == 0
    assert attack_active.get("gains_ap") is not True

    # 3. Também valida detecção nativa via playerEquipment com numUses == 0
    state_via_equipment = {
        "playerHealth": 30,
        "playerPitchCount": 4,
        "playerHand": [],
        "playerEquipment": [
            {"cardNumber": "teklovossen_esteemed_magnate", "slot": "hero", "numUses": 0}
        ],
        "playerBanish": [
            {"cardNumber": "evo_steel_soul_memory_blue", "name": "Evo Steel Soul Memory", "action": 1, "cost": 4, "power": 0}
        ]
    }
    attack_eq = engine.select_best_attack(state_via_equipment)
    assert attack_eq is not None
    assert attack_eq.get("is_instant") is True
    assert attack_eq.get("ap_cost") == 0


def test_warrior_hala_and_kassai_sequence_naa_buff_before_weapon():
    """Garante que cartas NAA de buff de Guerreiro (Hala e Kassai) sejam jogadas antes de bater com a arma."""
    engine_hala = PolicyEngine(hero_name="hala")

    # Hala com Imperial Seal of Command e Zenith Blade pronta
    state_hala = {
        "playerHealth": 35,
        "playerPitchCount": 3,
        "playerHand": [
            {"cardNumber": "imperial_seal_of_command_red", "name": "Imperial Seal of Command", "action": 27, "power": 0, "cost": 0, "pitch": 1}
        ],
        "playerEquipment": [
            {"cardNumber": "zenith_blade", "slot": "weapon", "action": 1, "power": 4}
        ]
    }
    best_act_hala = engine_hala.select_best_attack(state_hala)
    assert best_act_hala is not None
    assert "imperial_seal" in best_act_hala["name"].lower(), (
        f"Hala deve jogar o buff NAA (Imperial Seal) ANTES de bater com a Zenith Blade! Escolheu: {best_act_hala['name']}"
    )

    # Kassai com Blood on Her Hands e Cintari Saber pronta
    engine_kassai = PolicyEngine(hero_name="kassai")
    state_kassai = {
        "playerHealth": 35,
        "playerPitchCount": 3,
        "playerHand": [
            {"cardNumber": "blood_on_her_hands_red", "name": "Blood on Her Hands", "action": 27, "power": 0, "cost": 1, "pitch": 1}
        ],
        "playerEquipment": [
            {"cardNumber": "cintari_saber", "slot": "weapon", "action": 1, "power": 3}
        ]
    }
    best_act_kassai = engine_kassai.select_best_attack(state_kassai)
    assert best_act_kassai is not None
    assert "blood_on_her_hands" in best_act_kassai["name"].lower(), (
        f"Kassai deve jogar Blood on Her Hands ANTES de bater com a espada! Escolheu: {best_act_kassai['name']}"
    )


def test_marlinn_quiver_only_in_late_game():
    """
    Garante que Quiver of Abyssal Depths só seja ativado no fim de jogo (deck <= 10)
    para reciclar flechas do cemitério, e nunca no early game com deck cheio.
    """
    strat = get_hero_strategy("marlinn")
    assert isinstance(strat, MarlynnStrategy)

    # 1. Early game com deck cheio (30 cartas) e cemitério com flecha: NÃO ativa Quiver
    state_early = {
        "playerDeckCount": 30,
        "playerGraveyard": [{"cardNumber": "infecting_shot_red", "name": "Infecting Shot", "subtype": "Arrow"}]
    }
    score_early = strat.evaluate_equipment_ability(state_early, {"cardNumber": "quiver_of_abyssal_depths"})
    assert score_early == 0.0, "Quiver of Abyssal Depths não deve ativar no early game com 30 cartas no deck!"

    # 2. Late game com deck acabando (8 cartas) e cemitério com flecha: ATIVA para reciclar
    state_late = {
        "playerDeckCount": 8,
        "playerGraveyard": [{"cardNumber": "infecting_shot_red", "name": "Infecting Shot", "subtype": "Arrow"}]
    }
    score_late = strat.evaluate_equipment_ability(state_late, {"cardNumber": "quiver_of_abyssal_depths"})
    assert score_late >= 15.0, f"Quiver deve ativar no late game para reciclar flechas! Score: {score_late}"


def test_minimum_viable_defense_preserves_counterattack():
    """
    Garante que em cenários de final de jogo, o bot execute a Defesa Mínima Viável:
    Ex: com 3 HP enfrentando ataque de 4 poder, bloqueia com 1 carta (bloqueia 3 para sobreviver a 2 HP)
    e PRESERVA a segunda carta na mão para pagar o contra-ataque letal.
    """
    engine = PolicyEngine(hero_name="hala")
    state = {
        "playerHealth": 3,
        "opponentHealth": 4,
        "playerHand": [
            {"cardNumber": "sink_below_red", "name": "Sink Below", "action": 27, "defense": 3, "pitch": 1},
            {"cardNumber": "blunten_blue", "name": "Blunten Blue", "action": 27, "defense": 3, "pitch": 3},
        ],
        "activeChainLink": {"totalPower": 4, "cardNumber": "command_and_conquer"}
    }
    blocks = engine.select_defense_blocks(state)
    # Deve bloquear apenas o suficiente para sobreviver (1 carta bloqueia 3, projetando 2 HP de vida)
    # preservando a última carta para o contra-ataque
    assert len(blocks) == 1, f"Defesa Mínima Viável deveria usar exatamente 1 carta para sobreviver a 2 HP! Usou: {len(blocks)}"


def test_talishar_native_negative_def_counters_reduces_block_and_excludes_zero_block():
    """Garante que defCounters negativos nativos do Talishar (-1, -2) reduzam a defesa e impeçam re-bloqueio inútil."""
    pe = PolicyEngine(hero_name="oscilio")

    # Equipamento de 1 defesa (Bracers of Belief) com defCounters = -1 (já bloqueou 1 vez)
    state_depleted = {
        "playerHealth": 15,
        "playerHand": [],
        "activeChainLink": {"cardNumber": "command_and_conquer", "totalPower": 6},
        "playerEquipment": [
            {"cardNumber": "bracers_of_belief", "slot": "arms", "defense": 1, "defCounters": -1, "action": 3}
        ]
    }
    blocks = pe.select_defense_blocks(state_depleted)
    assert len(blocks) == 0, f"Equipamento com defCounters=-1 (defesa zerada) NÃO deve bloquear! Bloqueou: {blocks}"

    # Também suporta string "-1"
    state_depleted_str = {
        "playerHealth": 15,
        "playerHand": [],
        "activeChainLink": {"cardNumber": "command_and_conquer", "totalPower": 6},
        "playerEquipment": [
            {"cardNumber": "bracers_of_belief", "slot": "arms", "defense": 1, "defCounters": "-1", "action": 3}
        ]
    }
    blocks_str = pe.select_defense_blocks(state_depleted_str)
    assert len(blocks_str) == 0, f"Equipamento com defCounters='-1' NÃO deve ser selecionado! Bloqueou: {blocks_str}"


def test_teklovossen_evo_preservation_against_slow_and_aggro_decks():
    """
    Garante que Teklovossen NUNCA quebre ou degrade seus Evos aleatoriamente:
    - Contra decks lentos: só bloqueia com Evo se for estritamente fatal.
    - Contra decks agressivos: só usa Evos bem para o final do jogo (late game) ou se for fatal.
    """
    pe = PolicyEngine(hero_name="teklovossen")

    # 1. Contra deck lento com ataque comum (não-fatal, HP 20, opp_power 4): Evo NÃO DEVE BLOQUEAR!
    state_slow_non_fatal = {
        "playerHealth": 20,
        "currentTurn": 3,
        "opponentHero": "victor_goldmane",
        "activeChainLink": {"cardNumber": "machismo_red", "totalPower": 4},
        "playerHand": [],
        "playerEquipment": [
            {"cardNumber": "cogwerx_base_chest", "slot": "chest", "defense": 2, "action": 3}
        ]
    }
    blocks_slow = pe.select_defense_blocks(state_slow_non_fatal)
    assert len(blocks_slow) == 0, "Teklovossen NUNCA deve gastar Evo contra deck lento se não for dano fatal!"

    # 2. Contra deck lento MAS dano fatal (HP 4, opp_power 6): Evo DEVE BLOQUEAR para sobreviver!
    state_slow_fatal = {
        "playerHealth": 4,
        "currentTurn": 5,
        "opponentHero": "victor_goldmane",
        "activeChainLink": {"cardNumber": "spinal_crush_red", "totalPower": 6},
        "playerHand": [],
        "playerEquipment": [
            {"cardNumber": "cogwerx_base_chest", "slot": "chest", "defense": 2, "action": 3}
        ]
    }
    blocks_fatal = pe.select_defense_blocks(state_slow_fatal)
    assert len(blocks_fatal) == 1, "Teklovossen DEVE bloquear com Evo em situação fatal para não morrer!"

    # 3. Contra deck agressivo no início/meio de jogo (Turno 2, HP 18, opp_power 6): Evo NÃO BLOQUEIA!
    state_aggro_early = {
        "playerHealth": 18,
        "currentTurn": 2,
        "opponentHero": "fai_rising_rebellion",
        "activeChainLink": {"cardNumber": "snatch_red", "totalPower": 6},
        "playerHand": [],
        "playerEquipment": [
            {"cardNumber": "cogwerx_base_chest", "slot": "chest", "defense": 2, "action": 3}
        ]
    }
    blocks_early = pe.select_defense_blocks(state_aggro_early)
    assert len(blocks_early) == 0, "Teklovossen NÃO deve queimar Evo no início de jogo contra aggro!"


def test_oscilio_strategy_giaf_and_lightning():
    """Garante que a OscilioStrategy valorize o pilar GIAF (Gone in a Flash) e a arma Volzar."""
    strat = get_hero_strategy("oscilio_constella_intelligence")
    assert strat.__class__.__name__ == "OscilioStrategy"

    # Gone in a Flash deve receber pontuação altíssima
    score_giaf = strat.evaluate_attack_card("gone_in_a_flash_red", power=4, cost=1, has_go_again=True, pitch=1)
    score_vanilla = strat.evaluate_attack_card("generic_attack_red", power=4, cost=1, has_go_again=True, pitch=1)
    assert score_giaf >= score_vanilla + 10.0, f"GIAF deve ter prioridade máxima para Oscilio! GIAF: {score_giaf}, Vanilla: {score_vanilla}"

    # Volzar, Meteor Storm deve ser valorizada para dano arcano
    score_weapon = strat.evaluate_weapon_attack("volzar_meteor_storm", floating_res=1, total_res=2, has_hand_attacks=False)
    assert score_weapon >= 12.0, f"Volzar com recurso flutuante deve ter score alto! Score: {score_weapon}"

    # TurnPlan OSCILIO_LIGHTNING_BURST
    state_oscilio = {
        "playerHealth": 18,
        "playerHand": [
            {"cardNumber": "gone_in_a_flash_red", "name": "Gone in a Flash", "power": 4, "cost": 1, "pitch": 1},
            {"cardNumber": "echoflash_yellow", "name": "Echoflash", "pitch": 2}
        ]
    }
    plan = strat.analyze_turn_plan(state_oscilio)
    assert plan.plan_type == "OSCILIO_LIGHTNING_BURST", f"Deveria ativar plano OSCILIO_LIGHTNING_BURST! Plano: {plan.plan_type}"
