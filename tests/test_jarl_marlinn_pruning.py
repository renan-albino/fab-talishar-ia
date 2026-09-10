import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.policy_engine import PolicyEngine
from ai.hero_strategies import JarlStrategy, GuardianStrategy, RangerStrategy, MarlynnStrategy, HeroStrategy

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

    # 4. TurnPlan Pivot: Fused Oaken Old (Oaken Old + Terra + Gelo + Blue pitch)
    state_fused = {
        "playerHealth": 20,
        "playerHand": [
            {"cardNumber": "oaken_old_red", "power": 7, "pitch": 1, "defense": 3, "action": 27},
            {"cardNumber": "autumns_touch_blue", "power": 3, "pitch": 3, "defense": 3, "action": 27},
            {"cardNumber": "channel_lake_frigid_blue", "power": 0, "pitch": 3, "defense": 3, "action": 27},
            {"cardNumber": "fruits_of_the_forest_blue", "power": 3, "pitch": 3, "defense": 3, "action": 27},
        ],
        "activeChainLink": {"totalPower": 4, "cardNumber": "wounding_blow_red"}
    }
    plan_fused = engine_jarl.strategy.analyze_turn_plan(state_fused)
    print(f"Plano de Turno Jarl: {plan_fused.plan_type} ({plan_fused.reason})")
    assert plan_fused.plan_type == "PIVOT_OAKEN_OLD_FUSED", f"Esperado PIVOT_OAKEN_OLD_FUSED, obtido {plan_fused.plan_type}"
    assert plan_fused.can_absorb_damage is True, "Jarl deve aceitar absorver dano para executar a fusão"
    assert "oaken_old_red" in plan_fused.reserved_card_names

    blocks_fused = engine_jarl.select_defense_blocks(state_fused)
    print(f"Cartas selecionadas para bloquear (Pivot Oaken Old): {blocks_fused}")
    assert len(blocks_fused) == 0, f"Jarl deve absorver o dano (0 blocos) para manter o combo intacto, mas bloqueou: {blocks_fused}"

    # 5. Sobrevivência com vida baixa (HP <= 6): aborta pivot e bloqueia
    state_survival = {
        "playerHealth": 4,
        "playerHand": [
            {"cardNumber": "oaken_old_red", "power": 7, "pitch": 1, "defense": 3, "action": 27},
            {"cardNumber": "autumns_touch_blue", "power": 3, "pitch": 3, "defense": 3, "action": 27},
            {"cardNumber": "channel_lake_frigid_blue", "power": 0, "pitch": 3, "defense": 3, "action": 27},
        ],
        "activeChainLink": {"totalPower": 4, "cardNumber": "wounding_blow_red"}
    }
    plan_survival = engine_jarl.strategy.analyze_turn_plan(state_survival)
    assert plan_survival.plan_type == "SURVIVAL_BLOCK", f"Esperado SURVIVAL_BLOCK, obtido {plan_survival.plan_type}"
    blocks_surv = engine_jarl.select_defense_blocks(state_survival)
    print(f"Cartas selecionadas no modo sobrevivência: {blocks_surv}")
    assert len(blocks_surv) > 0, "Com HP crítico o bot deve bloquear para sobreviver"

    print("[OK] Testes de Jarl passaram com sucesso!\n")


def test_marlinn():
    print("=== TESTANDO MARLINN / RANGER ===")

    # 1. Resolução de estratégia
    engine_marlinn = PolicyEngine(hero_name="marlinn", num_mcts_sims=0)
    assert isinstance(engine_marlinn.strategy, MarlynnStrategy), f"Esperado MarlynnStrategy, obtido {type(engine_marlinn.strategy)}"
    assert isinstance(engine_marlinn.strategy, RangerStrategy), "MarlynnStrategy deve herdar de RangerStrategy"

    engine_marlynn_full = PolicyEngine(hero_name="marlynn_treasure_hunter", num_mcts_sims=0)
    assert isinstance(engine_marlynn_full.strategy, MarlynnStrategy), f"Esperado MarlynnStrategy para marlynn_treasure_hunter, obtido {type(engine_marlynn_full.strategy)}"
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

    # 4. TurnPlan Overpitch Recovery (Flecha no cemitério + Codex na mão)
    state_recovery = {
        "playerHealth": 20,
        "playerAP": 1,
        "playerResources": [0, 0],
        "playerHand": [
            {"cardNumber": "codex_of_frailty_yellow", "cost": 0, "action": 27, "pitch": 2},
            {"cardNumber": "blue_fin_harpoon_blue", "cost": 1, "pitch": 3, "action": 27, "defense": 3},
        ],
        "playerDiscard": [
            {"cardNumber": "king_kraken_harpoon_red", "power": 9, "pitch": 1}
        ],
        "playerArsenal": [],
        "activeChainLink": {"totalPower": 4, "cardNumber": "wounding_blow_red"}
    }
    plan_rec = engine_marlinn.strategy.analyze_turn_plan(state_recovery)
    print(f"Plano de Turno Marlinn: {plan_rec.plan_type} ({plan_rec.reason})")
    assert plan_rec.plan_type == "OVERPITCH_RECOVERY", f"Esperado OVERPITCH_RECOVERY, obtido {plan_rec.plan_type}"
    assert plan_rec.can_absorb_damage is True

    blocks_rec = engine_marlinn.select_defense_blocks(state_recovery)
    print(f"Cartas selecionadas para bloquear (Recovery): {blocks_rec}")
    assert len(blocks_rec) == 0, f"Marlynn deve absorver dano para manter linha de recuperação, obteve: {blocks_rec}"

    best_rec_atk = engine_marlinn.select_best_attack(state_recovery, set())
    print(f"Ataque escolhido (Recovery): {best_rec_atk['name']}")
    assert best_rec_atk["name"] == "codex_of_frailty_yellow", "Deve jogar a NAA de recuperação primeiro para carregar o arsenal!"

    # 5. TurnPlan Defensive Trap (Sem flechas, apenas armadilhas)
    state_trap = {
        "playerHealth": 20,
        "playerAP": 1,
        "playerHand": [
            {"cardNumber": "boulder_trap_yellow", "action": 27, "block": 3, "defense": 3, "pitch": 2},
            {"cardNumber": "tarpit_trap_yellow", "action": 27, "block": 3, "defense": 3, "pitch": 2},
        ],
        "playerDiscard": [],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "hammerhead_harpoon_cannon", "action": 28, "slot": "Weapon"}
        ],
        "activeChainLink": {"totalPower": 4, "cardNumber": "wounding_blow_red"}
    }
    plan_trap = engine_marlinn.strategy.analyze_turn_plan(state_trap)
    assert plan_trap.plan_type == "DEFENSIVE_TRAP"
    blocks_trap = engine_marlinn.select_defense_blocks(state_trap)
    print(f"Cartas selecionadas com armadilhas defensivas: {blocks_trap}")
    assert len(blocks_trap) == 2, "Deve bloquear com as armadilhas para absorver o dano"

    print("[OK] Testes de Marlinn passaram com sucesso!\n")


def test_generic_pivot():
    print("=== TESTANDO PIVOT GENÉRICO ===")
    engine_gen = PolicyEngine(hero_name="generic", num_mcts_sims=0)
    state_gen = {
        "playerHealth": 20,
        "playerHand": [
            {"cardNumber": "massive_blow_red", "power": 7, "cost": 2, "pitch": 1, "action": 27, "defense": 3},
            {"cardNumber": "blue_energy_blue", "power": 2, "cost": 0, "pitch": 3, "action": 27, "defense": 3},
            {"cardNumber": "filler_card_red", "power": 2, "cost": 0, "pitch": 1, "action": 27, "defense": 2},
        ],
        "activeChainLink": {"totalPower": 3, "cardNumber": "wounding_blow_red"}
    }
    plan = engine_gen.strategy.analyze_turn_plan(state_gen)
    print(f"Plano Genérico: {plan.plan_type} ({plan.reason})")
    assert plan.plan_type == "GENERIC_PIVOT", f"Esperado GENERIC_PIVOT, obtido {plan.plan_type}"
    assert plan.can_absorb_damage is True
    assert "massive_blow_red" in plan.reserved_card_names

    blocks = engine_gen.select_defense_blocks(state_gen)
    block_names = [b[2] for b in blocks]
    print(f"Cartas selecionadas no Pivot Genérico: {block_names}")
    assert "massive_blow_red" not in block_names, "Ataque forte não deve ser usado para bloquear no pivot!"
    print("[OK] Teste de Pivot Genérico passou com sucesso!\n")


if __name__ == "__main__":
    test_jarl()
    test_marlinn()
    test_generic_pivot()
    print(">>> TODOS OS TESTES DE PRUNING E TURNPLAN FORAM APROVADOS COM 100% DE SUCESSO! <<<")
