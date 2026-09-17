import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from conftest import make_policy_engine

def test_unpayable_hand_attack_pruning():
    pe = make_policy_engine()

    # Cenário A: Mão com Mangle (custo 4) e apenas 1 carta vermelha (pitch 1).
    # Pitch restante das outras cartas = 1 < 4. Mangle NÃO pode ser jogado!
    state_cannot_pay = {
        "playerAP": 1,
        "playerPitchCount": 0,
        "playerHand": [
            {"cardNumber": "mangle_red", "action": 27, "actionDataOverride": "0"},
            {"cardNumber": "sink_below_red", "action": 0, "actionDataOverride": "1"},
        ],
        "playerEquipment": [],
        "opponentHand": [{"cardNumber": "CardBack"}]
    }
    atk = pe.select_best_attack(state_cannot_pay, unpayable_set=set())
    assert atk is None, f"Esperado None pois não há pitch suficiente para Mangle, mas retornou {atk}"

    # Cenário B: Mão com Mangle (custo 4) e duas cartas azuis (pitch 3 cada = 6).
    # Pitch restante das outras cartas = 6 >= 4. Mangle PODE ser jogado!
    state_can_pay = {
        "playerAP": 1,
        "playerPitchCount": 0,
        "playerHand": [
            {"cardNumber": "mangle_red", "action": 27, "actionDataOverride": "0"},
            {"cardNumber": "sink_below_blue", "action": 0, "actionDataOverride": "1"},
            {"cardNumber": "crumble_to_eternity_blue", "action": 0, "actionDataOverride": "2"},
        ],
        "playerEquipment": [],
        "opponentHand": [{"cardNumber": "CardBack"}]
    }
    atk_ok = pe.select_best_attack(state_can_pay, unpayable_set=set())
    assert atk_ok is not None, "Mangle deveria ser selecionado pois há 6 de pitch disponível!"
    assert atk_ok["name"] == "mangle_red"
    assert atk_ok["cost"] == 4

def test_unpayable_weapon_pruning():
    pe = make_policy_engine()

    # Cenário A: Sledge of Anvilheim (Hammer, custo real 4 no FaB/Talishar) com apenas 2 cartas vermelhas (pitch 1 cada = 2).
    # Total pitch = 2 < 4. A arma NÃO pode ser usada!
    state_weapon_unpayable = {
        "playerAP": 1,
        "playerPitchCount": 0,
        "playerHand": [
            {"cardNumber": "sink_below_red", "action": 0, "actionDataOverride": "0"},
            {"cardNumber": "fate_foreseen_red", "action": 0, "actionDataOverride": "1"},
        ],
        "playerEquipment": [
            {"cardNumber": "sledge_of_anvilheim", "action": 27, "actionDataOverride": "W1", "slot": "Weapon"}
        ],
        "opponentHand": [{"cardNumber": "CardBack"}]
    }
    atk_w_fail = pe.select_best_attack(state_weapon_unpayable, unpayable_set=set())
    assert atk_w_fail is None, f"Arma custo 4 não deveria ser jogável com apenas 2 de pitch na mão, mas retornou {atk_w_fail}"

    # Cenário B: Sledge of Anvilheim com 1 carta azul (pitch 3) + 1 carta vermelha (pitch 1) na mão.
    # Total pitch = 4 >= 4. A arma PODE ser usada!
    state_weapon_payable = {
        "playerAP": 1,
        "playerPitchCount": 0,
        "playerHand": [
            {"cardNumber": "crumble_to_eternity_blue", "action": 0, "actionDataOverride": "0"},
            {"cardNumber": "sink_below_red", "action": 0, "actionDataOverride": "1"},
        ],
        "playerEquipment": [
            {"cardNumber": "sledge_of_anvilheim", "action": 27, "actionDataOverride": "W1", "slot": "Weapon"}
        ],
        "opponentHand": [{"cardNumber": "CardBack"}]
    }
    atk_w_ok = pe.select_best_attack(state_weapon_payable, unpayable_set=set())
    assert atk_w_ok is not None, "Arma custo 4 deveria ser jogável com 4 de pitch na mão!"
    assert atk_w_ok["name"] == "sledge_of_anvilheim"
    assert atk_w_ok["cost"] == 4

def test_combat_chain_desc():
    from bot_client import FabBotClient
    bot = FabBotClient("test_room", "decks/jarl.json", "host", "Bot1")
    
    state_with_chain = {
        "activeChainLink": {
            "reactions": [{"cardNumber": "cintari_saber"}],
            "totalPower": 4,
            "totalDefense": 2,
            "goAgain": True,
            "dominate": False
        }
    }
    desc = bot.get_combat_chain_desc(state_with_chain)
    assert "cintari_saber" in desc
    assert "Poder: 4" in desc
    assert "Bloqueio: 2" in desc
    assert "Go Again" in desc

def test_ismcts_hand_detection():
    pe = make_policy_engine(num_mcts_sims=5)
    
    state_with_opp_hand = {
        "playerAP": 1,
        "playerPitchCount": 0,
        "playerHand": [
            {"cardNumber": "mangle_red", "action": 27, "actionDataOverride": "0"},
            {"cardNumber": "sink_below_blue", "action": 0, "actionDataOverride": "1"},
            {"cardNumber": "crumble_to_eternity_blue", "action": 0, "actionDataOverride": "2"},
            {"cardNumber": "felling_of_the_crown_red", "action": 27, "actionDataOverride": "3"},
        ],
        "playerEquipment": [],
        "opponentHand": [{"cardNumber": "CardBack"}, {"cardNumber": "CardBack"}]
    }
    # Deve executar search_ismcts porque len(opponentHand) == 2 > 0
    atk = pe.select_best_attack(state_with_opp_hand, unpayable_set=set())
    assert atk is not None
    # Deve conter metadados _ismcts_log
    assert "_ismcts_log" in atk
    log_data = atk["_ismcts_log"]
    assert log_data["worlds_sampled"] > 0
    assert "confidence" in log_data

def test_weapon_power_and_cost():
    pe = make_policy_engine()
    state_pile_driver = {
        "playerAP": 1,
        "playerPitchCount": 0,
        "playerHand": [
            {"cardNumber": "sink_below_blue", "action": 0, "actionDataOverride": "0"}
        ],
        "playerEquipment": [
            {"cardNumber": "pile_driver", "action": 27, "actionDataOverride": "W1", "slot": "Weapon"}
        ],
        "opponentHand": [{"cardNumber": "CardBack"}]
    }
    atk = pe.select_best_attack(state_pile_driver, unpayable_set=set())
    assert atk is not None
    assert atk["name"] == "pile_driver"
    assert atk["power"] == 6, f"Esperado poder 6 para pile_driver, obteve {atk['power']}"
    assert atk["cost"] == 3

def test_ranger_arrow_hand_pruning():
    pe = make_policy_engine()
    # Flechas na mão NÃO podem ser jogadas diretamente como ação de ataque (CR 2.1.2)
    state_arrow_in_hand = {
        "playerAP": 1,
        "playerPitchCount": 0,
        "playerHand": [
            {"cardNumber": "endless_arrow_red", "action": 27, "actionDataOverride": "0"},
            {"cardNumber": "king_kraken_harpoon_red", "action": 27, "actionDataOverride": "1"}
        ],
        "playerEquipment": [],
        "opponentHand": [{"cardNumber": "CardBack"}]
    }
    atk_hand = pe.select_best_attack(state_arrow_in_hand, unpayable_set=set())
    assert atk_hand is None, "Flechas na mão devem ser podadas da lista de ataques diretos!"

    # Flecha no Arsenal PODE ser jogada
    state_arrow_in_arsenal = {
        "playerAP": 1,
        "playerPitchCount": 0,
        "playerHand": [
            {"cardNumber": "sink_below_blue", "action": 0, "actionDataOverride": "0"}
        ],
        "playerArsenal": [
            {"cardNumber": "endless_arrow_red", "action": 27, "actionDataOverride": "A0"}
        ],
        "playerEquipment": [],
        "opponentHand": [{"cardNumber": "CardBack"}]
    }
    atk_arsenal = pe.select_best_attack(state_arrow_in_arsenal, unpayable_set=set())
    assert atk_arsenal is not None, "Flecha no Arsenal deve ser um ataque válido!"
    assert atk_arsenal["name"] == "endless_arrow_red"

def test_sideboard_2h_weapon_no_shield():
    import json
    from bot_client import FabBotClient
    bot = FabBotClient("test_room_sb", "decks/jarl.json", "host", "BotJarl")
    bot.game_id = "test_game"
    bot.player_id = 1
    bot.auth_key = "dummy_key"
    bot.deck_format = "cc"
    # Forçar oponente de fadiga para selecionar Sledge 2H
    bot.get_opponent_info = lambda: ("bravo_showstopper", "guardian")
    
    posted_payload = {}
    def mock_post(url, json=None):
        nonlocal posted_payload
        posted_payload = json
        return type("Response", (), {"status_code": 200, "json": lambda: {"status": "OK"}})()

    bot.session.post = mock_post
    
    # Executar submit_sideboard
    bot.submit_sideboard()
    
    sub_data = json.loads(posted_payload["submission"])
    # A arma 2H (sledge_of_anvilheim) deve estar sozinha em 'hands'
    assert sub_data["hands"] == ["sledge_of_anvilheim"], f"Esperado ['sledge_of_anvilheim'], obteve {sub_data['hands']}"
    # Nenhum escudo pode estar equipado em 'hands'
    assert "rampart_of_the_rams_head" not in sub_data["hands"]
    assert "stalagmite_bastion_of_isenloft" not in sub_data["hands"]
    # Escudos devem estar no inventário (sideboard)
    assert "rampart_of_the_rams_head" in sub_data["inventory"]
    assert "stalagmite_bastion_of_isenloft" in sub_data["inventory"]


