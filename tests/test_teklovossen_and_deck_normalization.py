import os
import json
import pytest
from stats_manager import canonicalize_deck_name, update_match_result, get_stats_data
from ai.hero_strategies import get_hero_strategy, TeklovossenStrategy
from bot_client import FabBotClient
from ai.policy_engine import PolicyEngine

TEST_STATS_FILE = "data/test_training_stats_normalization.json"

@pytest.fixture(autouse=True)
def setup_teardown_test_stats(monkeypatch):
    os.makedirs("data", exist_ok=True)
    monkeypatch.setattr("stats_manager.STATS_FILE", TEST_STATS_FILE)
    if os.path.exists(TEST_STATS_FILE):
        os.remove(TEST_STATS_FILE)
    yield
    if os.path.exists(TEST_STATS_FILE):
        os.remove(TEST_STATS_FILE)

def test_canonical_deck_name_resolution():
    """Valida que todas as variantes de nomes de heróis mapeiam para os nomes dos decks cadastrados."""
    assert canonicalize_deck_name("Teklovossen Esteemed Magnate") == "Teklovossen"
    assert canonicalize_deck_name("teklovossen_esteemed_magnate") == "Teklovossen"
    assert canonicalize_deck_name("Betsy Skin In The Game") == "Betsy"
    assert canonicalize_deck_name("betsy_skin_in_the_game") == "Betsy"
    assert canonicalize_deck_name("Kassai Of The Golden Sand") == "Kassai"
    assert canonicalize_deck_name("kassai_of_the_golden_sand") == "Kassai"
    assert canonicalize_deck_name("Oscilio Constella Intelligence") == "Oscilio GIAF"
    assert canonicalize_deck_name("oscilio_constella_intelligence") == "Oscilio GIAF"
    assert canonicalize_deck_name("Cindra Dracai Of Retribution") == "Cindra"
    assert canonicalize_deck_name("cindra_dracai_of_retribution") == "Cindra"
    assert canonicalize_deck_name("Jarl Vetreidi") == "Jarl"
    assert canonicalize_deck_name("jarl_vetreidi") == "Jarl"
    assert canonicalize_deck_name("Vynnset Iron Maiden") == "Vynsett"
    assert canonicalize_deck_name("vynnset_iron_maiden") == "Vynsett"
    assert canonicalize_deck_name("Arakni Marionette") == "Mario"
    assert canonicalize_deck_name("arakni_marionette") == "Mario"
    assert canonicalize_deck_name("Gravy Bones Shipwrecked Looter") == "Gravy Bones"
    assert canonicalize_deck_name("gravy_bones_shipwrecked_looter") == "Gravy Bones"
    assert canonicalize_deck_name("Marlynn Treasure Hunter") == "Marlinn"
    assert canonicalize_deck_name("marlynn_treasure_hunter") == "Marlinn"

def test_room_deduplication_in_update_match_result():
    """Valida que uma mesma sala não é registrada em duplicidade."""
    stats = update_match_result(
        room_id="room_unique_123",
        p1_deck="Teklovossen Esteemed Magnate",
        p2_deck="Oscilio Constella Intelligence",
        p1_health=0,
        p2_health=25,
        total_turns=16,
        winner_id=2
    )
    assert stats["total_matches"] == 1
    assert stats["deck_stats"]["Oscilio GIAF"]["wins"] == 1
    assert stats["deck_stats"]["Teklovossen"]["losses"] == 1

    # Segunda chamada com a mesma sala (ex: chamada de trainer.py após bot_client)
    stats2 = update_match_result(
        room_id="room_unique_123",
        p1_deck="teklovossen",
        p2_deck="oscilio_giaf",
        p1_health=0,
        p2_health=25,
        total_turns=15,
        winner_id=2
    )
    # Não deve inflar total_matches nem recalcular ELO
    assert stats2["total_matches"] == 1
    assert stats2["deck_stats"]["Oscilio GIAF"]["wins"] == 1
    assert stats2["deck_stats"]["Teklovossen"]["losses"] == 1

def test_teklovossen_strategy_registration():
    """Valida que Teklovossen possui estratégia dedicada TeklovossenStrategy."""
    strat = get_hero_strategy("teklovossen")
    assert isinstance(strat, TeklovossenStrategy)
    strat_full = get_hero_strategy("teklovossen_esteemed_magnate")
    assert isinstance(strat_full, TeklovossenStrategy)

def test_teklovossen_sideboard_equips_all_four_slots():
    """Valida que o bot equipa os 4 slots de armadura usando Base Evos quando necessário."""
    client = FabBotClient.__new__(FabBotClient)
    client.deck_url = "decks/teklovossen.json"
    client.clean_deck = "teklovossen"
    client.deck_name = "Teklovossen"
    client.deck_format = "cc"
    client.game_id = "test_game"
    client.player_id = 1
    client.auth_key = "test_key"
    client.metrics = {}
    client.room_id = "test_room"
    client.player_name = "Bot1"
    client.mcts_sims = 10
    client.use_gpu = False
    client.session = type("MockSession", (), {"post": lambda self, url, json: type("Res", (), {"status_code": 200, "json": lambda: {"status": "OK"}})()})()
    client.log = lambda msg: None
    client._card_db = json.load(open("data/fab_cards_db.json"))
    client.get_card_meta = lambda cid: client._card_db.get(cid, {})
    client.get_opponent_info = lambda: ("kassai", "warrior")

    client.submit_sideboard()
    eq = client.metrics.get("sideboard_info", {}).get("equipment", {})
    assert eq.get("head") != "", "Head deve estar equipada"
    assert eq.get("chest") != "", "Chest deve estar equipada com Base Evo"
    assert eq.get("arms") != "", "Arms deve estar equipada com Base Evo"
    assert eq.get("legs") != "", "Legs deve estar equipada com Base Evo"
    assert len(eq.get("weapons", [])) > 0, "Arma deve estar equipada"

def test_hammerhead_requires_arrow_in_arsenal():
    """Garante que Hammerhead não é ativado sem flecha no Arsenal para evitar desperdício de pitch."""
    pe = PolicyEngine(hero_name="marlynn_treasure_hunter", num_mcts_sims=5, use_gpu=False)
    # Cenário: flecha apenas na mão (sem flecha no arsenal), recursos disponíveis
    state_arrow_in_hand_only = {
        "turnPlayer": 1,
        "playerID": 1,
        "amIActivePlayer": True,
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerHand": [
            {"cardNumber": "blue_fin_harpoon_blue", "pitch": 3, "cost": 0, "action": 27},
            {"cardNumber": "red_fin_harpoon_blue", "pitch": 3, "cost": 0, "action": 27},
            {"cardNumber": "king_kraken_harpoon_red", "pitch": 1, "cost": 1, "power": 7, "action": 27}
        ],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "marlynn_treasure_hunter", "slot": "Hero", "action": 0},
            {"cardNumber": "hammerhead_harpoon_cannon", "action": 3, "slot": "Weapon", "type": "W", "actionDataOverride": "5"}
        ],
        "playerResources": [6, 6],
        "playerPitchCount": 6,
        "actionPoints": 1
    }
    action = pe.select_best_attack(state_arrow_in_hand_only)
    assert action is None or action["name"] != "hammerhead_harpoon_cannon", "Hammerhead não pode ativar sem flecha pronta no Arsenal"

def test_hammerhead_activates_with_codex_and_empty_arsenal():
    """Valida a exceção tática: Hammerhead PODE e DEVE ser ativado sem flecha no Arsenal se tiver Codex of Frailty na mão."""
    pe = PolicyEngine(hero_name="marlynn_treasure_hunter", num_mcts_sims=5, use_gpu=False)
    state_with_codex = {
        "turnPlayer": 1,
        "playerID": 1,
        "amIActivePlayer": True,
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerHand": [
            {"cardNumber": "blue_fin_harpoon_blue", "pitch": 3, "cost": 0, "action": 27},
            {"cardNumber": "red_fin_harpoon_blue", "pitch": 3, "cost": 0, "action": 27},
            {"cardNumber": "codex_of_frailty_yellow", "pitch": 2, "cost": 0, "action": 27}
        ],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "marlynn_treasure_hunter", "slot": "Hero", "action": 0},
            {"cardNumber": "hammerhead_harpoon_cannon", "action": 3, "slot": "Weapon", "type": "W", "actionDataOverride": "5"}
        ],
        "playerResources": [6, 6],
        "playerPitchCount": 6,
        "actionPoints": 1
    }
    action = pe.select_best_attack(state_with_codex)
    assert action is not None
    assert action["name"] == "hammerhead_harpoon_cannon", "Hammerhead deve ser ativado com alta prioridade quando holding Codex of Frailty!"
    assert action["type"] == "weapon_buff"

def test_player_allies_attack_candidate():
    """Valida que o policy_engine gera candidatos de ataque para Aliados em jogo (playerAllies)."""
    pe = PolicyEngine(hero_name="gravy_bones_shipwrecked_looter", num_mcts_sims=5, use_gpu=False)
    state_with_allies = {
        "turnPlayer": 1,
        "playerID": 1,
        "amIActivePlayer": True,
        "playerHealth": 35,
        "opponentHealth": 30,
        "playerHand": [
            {"cardNumber": "avast_ye_blue", "pitch": 3, "cost": 0, "action": 27}
        ],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "gravy_bones_shipwrecked_looter", "slot": "Hero", "action": 0},
            {"cardNumber": "compass_of_sunken_depths", "slot": "Off-Hand", "type": "E"}
        ],
        "playerAllies": [
            {
                "cardNumber": "riggermortis_yellow",
                "name": "Riggermortis",
                "action": 27,
                "power": 6,
                "actionDataOverride": "ally_1"
            }
        ],
        "playerResources": [3, 3],
        "playerPitchCount": 3,
        "actionPoints": 1
    }
    action = pe.select_best_attack(state_with_allies)
    assert action is not None
    assert action["name"] == "riggermortis_yellow"
    assert action["type"] == "ally"
    assert action["power"] == 6

def test_marlynn_strategy_direct_weapon_ability():
    """Garante que a lógica do canhão reside em MarlynnStrategy.evaluate_weapon_ability."""
    from ai.hero_strategies.ranger import MarlynnStrategy
    strat = MarlynnStrategy(hero_name="marlynn_treasure_hunter")

    # Caso 1: Sem flecha e sem Codex -> podado ({})
    state_empty = {"playerHand": [], "playerArsenal": []}
    res = strat.evaluate_weapon_ability("hammerhead_harpoon_cannon", 4, state_empty, 6)
    assert res == {}

    # Caso 2: Com flecha no Arsenal e recursos -> candidato válido
    state_with_arrow = {
        "playerHand": [{"cardNumber": "blue_card", "pitch": 3}],
        "playerArsenal": [{"cardNumber": "red_fin_harpoon_red", "cost": 0}]
    }
    res_arrow = strat.evaluate_weapon_ability("hammerhead_harpoon_cannon", 4, state_with_arrow, 6)
    assert res_arrow.get("type") == "weapon_buff"
    assert res_arrow.get("score") >= 32.0

    # Caso 3: Com Codex of Frailty e Arsenal vazio -> exceção tática ativada
    state_codex = {
        "playerHand": [{"cardNumber": "codex_of_frailty_yellow", "pitch": 2}],
        "playerArsenal": []
    }
    res_codex = strat.evaluate_weapon_ability("hammerhead_harpoon_cannon", 4, state_codex, 6)
    assert res_codex.get("type") == "weapon_buff"
    assert res_codex.get("score") >= 36.0

def test_teklo_leveler_dynamic_scaling_and_evos():
    """Valida a regra oficial de Teklo Leveler (EVO009) para 0, 1, 2, 3 e 4 Evos equipados."""
    pe = PolicyEngine(hero_name="teklovossen", use_gpu=False, num_mcts_sims=5)

    # Caso 1: 0 Evos equipados -> A arma é IGUAL com 0 e 1 Evos: Custo 3, Poder 2, sem Go Again
    state_0_evos = {
        "playerEquipment": [
            {"cardNumber": "teklo_leveler", "slot": "weapon", "action": 27, "type": "W"}
        ],
        "playerHand": [{"cardNumber": "blue_card", "pitch": 3}],
        "playerResources": [3, 3],
        "actionPoints": 1
    }
    cost_0 = pe.get_weapon_cost("teklo_leveler", state=state_0_evos)
    assert cost_0 == 3
    candidate_0 = pe.select_best_attack(state_0_evos)
    assert candidate_0 is not None and candidate_0.get("name") == "teklo_leveler"
    assert candidate_0.get("power") == 2
    assert not candidate_0.get("has_go_again")

    # Caso 2: 1 Evo equipado -> Custo 3, Poder 2, sem Go Again
    state_1_evo = {
        "playerEquipment": [
            {"cardNumber": "teklo_leveler", "slot": "weapon", "action": 27, "type": "W"},
            {"cardNumber": "evo_beta_base_chest_blue_equip", "slot": "chest", "type": "E"}
        ],
        "playerHand": [{"cardNumber": "blue_card", "pitch": 3}],
        "playerResources": [3, 3],
        "actionPoints": 1
    }
    cost_1 = pe.get_weapon_cost("teklo_leveler", state=state_1_evo)
    assert cost_1 == 3
    cand_1 = pe.select_best_attack(state_1_evo)
    assert cand_1 is not None and cand_1.get("name") == "teklo_leveler"
    assert cand_1.get("power") == 2
    assert not cand_1.get("has_go_again")

    # Caso 3: 2 Evos equipados -> Custo {r}{r} a menos -> Custo 1! Poder 2, sem Go Again
    state_2_evos = {
        "playerEquipment": [
            {"cardNumber": "teklo_leveler", "slot": "weapon", "action": 27, "type": "W"},
            {"cardNumber": "evo_beta_base_chest_blue_equip", "slot": "chest", "type": "E"},
            {"cardNumber": "evo_beta_base_legs_blue_equip", "slot": "legs", "type": "E"}
        ],
        "playerHand": [{"cardNumber": "blue_card", "pitch": 3}],
        "playerResources": [1, 1],
        "actionPoints": 1
    }
    cost_2 = pe.get_weapon_cost("teklo_leveler", state=state_2_evos)
    assert cost_2 == 1

    # Caso 4: 3 Evos equipados -> Custo 1, Poder 2, GANHA GO AGAIN!
    state_3_evos = {
        "playerEquipment": [
            {"cardNumber": "teklo_leveler", "slot": "weapon", "action": 27, "type": "W"},
            {"cardNumber": "evo_beta_base_chest_blue_equip", "slot": "chest", "type": "E"},
            {"cardNumber": "evo_beta_base_legs_blue_equip", "slot": "legs", "type": "E"},
            {"cardNumber": "evo_beta_base_arms_blue_equip", "slot": "arms", "type": "E"}
        ],
        "playerHand": [{"cardNumber": "blue_card", "pitch": 3}],
        "playerResources": [1, 1],
        "actionPoints": 1
    }
    cost_3 = pe.get_weapon_cost("teklo_leveler", state=state_3_evos)
    assert cost_3 == 1
    cand_3 = pe.select_best_attack(state_3_evos)
    assert cand_3 is not None and cand_3.get("name") == "teklo_leveler"
    assert cand_3.get("power") == 2
    assert cand_3.get("has_go_again") is True

    # Caso 5: 4 Evos equipados -> Custo 1, Poder 3 (+1{p}), GANHA GO AGAIN!
    state_4_evos = {
        "playerEquipment": [
            {"cardNumber": "teklo_leveler", "slot": "weapon", "action": 27, "type": "W"},
            {"cardNumber": "evo_beta_base_chest_blue_equip", "slot": "chest", "type": "E"},
            {"cardNumber": "evo_beta_base_legs_blue_equip", "slot": "legs", "type": "E"},
            {"cardNumber": "evo_beta_base_arms_blue_equip", "slot": "arms", "type": "E"},
            {"cardNumber": "evo_beta_base_head_blue_equip", "slot": "head", "type": "E"}
        ],
        "playerHand": [{"cardNumber": "blue_card", "pitch": 3}],
        "playerResources": [1, 1],
        "actionPoints": 1
    }
    cand_4 = pe.select_best_attack(state_4_evos)
    assert cand_4 is not None and cand_4.get("name") == "teklo_leveler"
    assert cand_4.get("power") == 3
    assert cand_4.get("has_go_again") is True

def test_teklovossen_evo_priorities_and_arsenal():
    """Valida priorização de redutores de custo e avaliação especializada de Arsenal em Teklovossen."""
    strat = TeklovossenStrategy(hero_name="teklovossen")

    # Controller (+16.0) tem prioridade sobre Processor (+10.0)
    score_ctrl = strat.evaluate_card("evo_steel_soul_controller_blue", {"cost": 1})
    score_proc = strat.evaluate_card("evo_steel_soul_processor_blue", {"cost": 1})
    assert score_ctrl > score_proc

    # Avaliação de Arsenal: Singularity e Evos têm pontuação elevada
    ars_sing = strat.evaluate_arsenal_card({"name": "singularity_red", "pitch": 1})
    assert ars_sing >= 30.0

    ars_evo = strat.evaluate_arsenal_card({"name": "evo_steel_soul_controller_blue", "pitch": 3, "block": 3})
    assert ars_evo >= 14.0

def test_oscilio_astral_bridge_and_overblocking():
    """Valida que Oscilio prioriza Astral Bridge no ataque e não bloqueia com peças nobres."""
    from ai.hero_strategies.other_classes import OscilioStrategy
    strat = OscilioStrategy(hero_name="oscilio_constella_intelligence")

    # Astral Bridge tem pontuação alta no ataque (+16.0)
    score_astral = strat.evaluate_attack_card("astral_bridge_red", power=0, cost=0, has_go_again=False, pitch=1)
    assert score_astral >= 16.0

    # Bloquear com peças ofensivas de Lightning é fortemente desvalorizado (evitando overblocking)
    blk_giaf = strat.evaluate_block_card("gone_in_a_flash_red", block_val=3, pitch=1, power=5, has_go_again=True)
    assert blk_giaf <= -10.0

    blk_astral = strat.evaluate_block_card("astral_bridge_red", block_val=2, pitch=1, power=0, has_go_again=False)
    assert blk_astral <= -10.0

def test_policy_engine_graveyard_zone_awareness():
    """Valida que cartas jogáveis no cemitério (ex: Instant liberada por Astral Bridge) são reconhecidas pelo PolicyEngine."""
    pe = PolicyEngine(hero_name="oscilio_constella_intelligence", use_gpu=False, num_mcts_sims=5)

    # Estado onde Astral Bridge colocou Electrostatic Discharge no cemitério com permissão de jogar (action > 0)
    state = {
        "playerHand": [],
        "playerArsenal": [],
        "playerBanish": [],
        "playerGraveyard": [
            {
                "cardNumber": "electrostatic_discharge_red",
                "name": "Electrostatic Discharge",
                "action": 27,
                "power": 0,
                "cost": 0,
                "type": "I",
                "actionDataOverride": "grave_0"
            }
        ],
        "playerResources": [1, 1],
        "actionPoints": 1
    }
    atk = pe.select_best_attack(state)
    assert atk is not None
    assert atk.get("type") == "graveyard"
    assert atk.get("name") == "electrostatic_discharge_red"
    assert atk.get("has_go_again") is True

def test_all_known_zone_cards_and_state_vector():
    """Valida que get_all_known_zone_cards consolida todas as zonas e extract_state_vector reconhece jovens e adultos."""
    from ai.model import FaBPolicyValueNetwork

    state = {
        "playerHero": "teklovossen_esteemed_magnate",
        "opponentHero": "oscilio_constellation_seeker",
        "playerHealth": 40,
        "opponentHealth": 20,
        "playerHand": [{"cardNumber": "card1"}],
        "playerArsenal": [{"cardNumber": "card2"}],
        "playerBanish": [{"cardNumber": "card3"}],
        "playerGraveyard": [{"cardNumber": "card4"}],
        "playerSoul": [{"cardNumber": "card5"}],
        "playerPitch": [{"cardNumber": "card6"}],
        "playerEquipment": [
            {"cardNumber": "evo_beta_base_chest_blue_equip", "slot": "chest", "type": "E"},
            {"cardNumber": "evo_beta_base_legs_blue_equip", "slot": "legs", "type": "E"}
        ],
        "combatChain": []
    }
    zones = PolicyEngine.get_all_known_zone_cards(state)
    assert len(zones["hand"]) == 1
    assert len(zones["arsenal"]) == 1
    assert len(zones["banish"]) == 1
    assert len(zones["graveyard"]) == 1
    assert len(zones["soul"]) == 1
    assert len(zones["pitch"]) == 1

    vec = FaBPolicyValueNetwork.extract_state_vector(state)
    assert vec.shape[0] == 192
    # Mechanologist class (161) e Teklovossen (173)
    assert vec[161] == 1.0
    assert vec[173] == 1.0
    # Oponente é Wizard (188 = 0.5) e Jovem (189 = 1.0)
    assert vec[188] == 0.5
    assert vec[189] == 1.0
    # 2 Evos equipados (183 = 0.5)
    assert vec[183] == 0.5


def test_gravy_bones_lethal_execution_and_finisher_boost():
    """Valida o modo de Execução Letal, proteção de finalizadores e escolha agressiva de aliados pesados."""
    from ai.hero_strategies.other_classes import GravyBonesStrategy
    strat = GravyBonesStrategy(hero_name="gravy_bones_shipwrecked_looter")

    # 1. Modo de Execução Letal: Quando oponente <= 8 HP e Gravy >= 10 HP, proíbe bloqueio (max_block_cards = 0)
    state_kill = {
        "playerHealth": 38,
        "opponentHealth": 4,
        "playerHand": [{"cardNumber": "conqueror_of_the_high_seas_red", "power": 7, "block": 3}],
        "activeChainLink": {"totalPower": 3, "cardNumber": "generic_attack"}
    }
    plan = strat.analyze_turn_plan(state_kill)
    assert plan.plan_type == "GRAVY_LETHAL_EXECUTION"
    assert plan.max_block_cards == 0
    assert plan.can_absorb_damage is True

    # 2. Proteção de cartas finalizadoras contra descarte em bloqueio
    assert strat.evaluate_block_card("conqueror_of_the_high_seas_red", 3, 1, 7, False) <= -8.0
    assert strat.evaluate_block_card("riggermortis_yellow", 2, 2, 6, False) <= -8.0

    # 3. PolicyEngine com oponente na zona crítica prioriza aliado com poder letal
    pe = PolicyEngine(hero_name="gravy_bones_shipwrecked_looter", num_mcts_sims=5, use_gpu=False)
    state_allies_kill = {
        "turnPlayer": 1, "playerID": 1, "amIActivePlayer": True,
        "playerHealth": 38, "opponentHealth": 4,
        "playerHand": [{"cardNumber": "blue_card", "pitch": 3, "cost": 0, "action": 27}],
        "playerAllies": [
            {"cardNumber": "scooba_salty_sea_dog_yellow", "name": "Scooba", "action": 27, "power": 1, "actionDataOverride": "ally_1"},
            {"cardNumber": "riggermortis_yellow", "name": "Riggermortis", "action": 27, "power": 6, "actionDataOverride": "ally_2"}
        ],
        "playerResources": [3, 3], "actionPoints": 1
    }
    action = pe.select_best_attack(state_allies_kill)
    assert action is not None
    assert action["name"] == "riggermortis_yellow"  # Poder 6 perfura o oponente de 4 HP


