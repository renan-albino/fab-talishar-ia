import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.policy_engine import PolicyEngine
from ai.hero_strategies import JarlStrategy, GuardianStrategy, RangerStrategy

def test_jarl():
    print("=== TESTANDO JARL VETREIDI ===")
    
    # 1. Resolução de estratégia
    engine_jarl = PolicyEngine(hero_name="jarl", num_mcts_sims=0)
    assert isinstance(engine_jarl.strategy, JarlStrategy), f"Esperado JarlStrategy, obtido {type(engine_jarl.strategy)}"
    assert isinstance(engine_jarl.strategy, GuardianStrategy), "JarlStrategy deve herdar de GuardianStrategy"

    engine_jarl_full = PolicyEngine(hero_name="jarl_vetreidi", num_mcts_sims=0)
    assert isinstance(engine_jarl_full.strategy, JarlStrategy), f"Esperado JarlStrategy para jarl_vetreidi, obtido {type(engine_jarl_full.strategy)}"
    print("[OK] Resolução de estratégia para Jarl / Jarl_Vetreidi")

    # 2. Avaliação de ataques de Guardião / Terra / Gelo
    score_oaken = engine_jarl.strategy.evaluate_attack_card("oaken_old_red", power=7, cost=3, has_go_again=False, pitch=1)
    score_boulder = engine_jarl.strategy.evaluate_attack_card("boulder_drop_red", power=8, cost=4, has_go_again=False, pitch=1)
    print(f"Scores de Ataque - Oaken Old: {score_oaken}, Boulder Drop: {score_boulder}")
    assert score_oaken >= 18.0, f"Oaken Old deveria ter score alto, obtido {score_oaken}"
    assert score_boulder >= 17.0, f"Boulder Drop deveria ter score alto, obtido {score_boulder}"

    # 3. Poda de Pitch: Guardião valoriza azul e penaliza vermelho
    score_pitch_blue = engine_jarl.strategy.evaluate_pitch_card("autumns_touch_blue", pitch=3, cost=0, power=3, has_go_again=False)
    score_pitch_red = engine_jarl.strategy.evaluate_pitch_card("oaken_old_red", pitch=1, cost=3, power=7, has_go_again=False)
    print(f"Scores de Pitch - Azul: {score_pitch_blue}, Vermelho: {score_pitch_red}")
    assert score_pitch_blue > score_pitch_red + 15, "Azul deve ter prioridade absoluta de pitch sobre vermelho"

    # 4. Poda de Defesa: Preservação de carta de Pivot
    state_def = {
        "playerHealth": 20,
        "playerHand": [
            {"cardNumber": "oaken_old_red", "power": 7, "pitch": 1, "defense": 3, "action": 27},
            {"cardNumber": "autumns_touch_blue", "power": 3, "pitch": 3, "defense": 3, "action": 27},
            {"cardNumber": "fruits_of_the_forest_blue", "power": 3, "pitch": 3, "defense": 3, "action": 27},
        ],
        "activeChainLink": {"totalPower": 4, "cardNumber": "snatch_red"}
    }
    blocks = engine_jarl.select_defense_blocks(state_def)
    block_names = [b[2] for b in blocks]
    print(f"Cartas selecionadas para bloquear: {block_names}")
    assert "oaken_old_red" not in block_names, "Oaken Old NUNCA deve ser usada para bloquear com HP alto (preservar pivot)!"
    assert len(blocks) <= 2, "Guardião com Pivot line não deve gastar toda a mão em bloqueio menor!"
    print("[OK] Testes de Jarl passaram com sucesso!\n")


def test_marlinn():
    print("=== TESTANDO MARLINN / RANGER ===")

    # 1. Resolução de estratégia
    engine_marlinn = PolicyEngine(hero_name="marlinn", num_mcts_sims=0)
    assert isinstance(engine_marlinn.strategy, RangerStrategy), f"Esperado RangerStrategy, obtido {type(engine_marlinn.strategy)}"

    engine_marlynn_full = PolicyEngine(hero_name="marlynn_treasure_hunter", num_mcts_sims=0)
    assert isinstance(engine_marlynn_full.strategy, RangerStrategy), f"Esperado RangerStrategy para marlynn_treasure_hunter, obtido {type(engine_marlynn_full.strategy)}"
    print("[OK] Resolução de estratégia para Marlinn / Marlynn_Treasure_Hunter")

    # 2. Seleção de Ataque: Flecha no Arsenal deve vencer ataque comum da mão
    state_atk = {
        "playerHealth": 20,
        "playerAP": 1,
        "playerResources": [1, 0],
        "playerHand": [
            {"cardNumber": "cheating_scoundrel_red", "power": 4, "pitch": 1, "cost": 0, "action": 27},
            {"cardNumber": "autumns_touch_blue", "power": 3, "pitch": 3, "cost": 0, "action": 27},
        ],
        "playerArsenal": [
            {"cardNumber": "king_kraken_harpoon_red", "power": 6, "pitch": 1, "cost": 1, "action": 5}
        ],
        "playerEquipment": [
            {"cardNumber": "hammerhead_harpoon_cannon", "action": 28, "slot": "Weapon"}
        ]
    }
    best_atk = engine_marlinn.select_best_attack(state_atk, set())
    print(f"Ataque escolhido para Marlinn: {best_atk['name']} (Tipo: {best_atk['type']}, Score: {best_atk['score']})")
    assert best_atk["name"] == "king_kraken_harpoon_red", f"Flecha do Arsenal deveria ser escolhida, obtido: {best_atk['name']}"
    assert best_atk["type"] == "arsenal", f"Deveria atacar do arsenal, obtido: {best_atk['type']}"

    # 3. Poda de Arsenal: Gemas e recursos bloqueados
    state_ars = {
        "playerHand": [
            {"cardNumber": "riches_of_tropal_dhani_yellow", "actionDataOverride": "1"},
            {"cardNumber": "endless_arrow_red", "actionDataOverride": "2", "power": 5, "pitch": 1}
        ]
    }
    ars_pick = engine_marlinn.select_arsenal_card(state_ars)
    print(f"Arsenal selecionado: {ars_pick}")
    assert ars_pick is not None and ars_pick[0] == "endless_arrow_red", f"Deveria escolher endless_arrow_red, obtido: {ars_pick}"

    print("[OK] Testes de Marlinn passaram com sucesso!\n")


if __name__ == "__main__":
    test_jarl()
    test_marlinn()
    print(">>> TODOS OS TESTES DE PRUNING PARA JARL E MARLINN FORAM APROVADOS! <<<")
