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
