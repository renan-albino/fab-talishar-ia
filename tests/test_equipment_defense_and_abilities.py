import pytest
from ai.policy_engine import PolicyEngine, _load_ability_costs, _get_cards_db


def test_dynamic_ability_costs_lookup():
    """Testa se custos de ativação são lidos dinamicamente de data/ability_costs.json e fab_cards_db.json."""
    costs = _load_ability_costs()
    assert costs.get("hammerhead_harpoon_cannon") == 4
    assert costs.get("romping_club") == 2
    assert costs.get("tectonic_plating") == 1
    assert costs.get("high_riser") == 3

    cards_db = _get_cards_db()
    assert cards_db.get("hammerhead_harpoon_cannon", {}).get("ability_cost") == 4
    assert cards_db.get("romping_club", {}).get("ability_cost") == 2

    pe = PolicyEngine(hero_name="marlynn_treasure_hunter")
    assert pe.get_weapon_cost("hammerhead_harpoon_cannon") == 4
    assert pe.get_weapon_cost("romping_club") == 2
    assert pe.get_weapon_cost("tectonic_plating") == 1


def test_dynamic_kassai_sword_discount():
    """Testa modificador dinâmico de custo de espada com a habilidade de compra da Kassai."""
    pe = PolicyEngine(hero_name="kassai_of_the_golden_sand")
    
    # Sem ter comprado carta: custo normal da Cintari Saber é 1
    state_no_draw = {"num_drawn": 0}
    assert pe.get_weapon_cost("cintari_saber", state=state_no_draw) == 1

    # Após comprar carta: custo reduz em 1 (fica 0)
    state_drawn = {"num_drawn": 1}
    assert pe.get_weapon_cost("cintari_saber", state=state_drawn) == 0


def test_equipment_defense_battleworn_vs_blade_break():
    """Testa seleção de bloqueio com equipamentos: Battleworn é priorizado e Blade Break com habilidade é preservado."""
    pe = PolicyEngine(hero_name="bravo_showstopper")

    # Caso 1: HP alto (30). Ataque inimigo = 5.
    # Temos na mão uma carta defensiva (def 3) e dois equipamentos:
    # - Crown of Providence (Blade Break, def 2, tem habilidade ativa) -> DEVE SER PRESERVADO (-25 de score)
    # - Ironrot Gauntlet (Blade Break, def 1, SEM habilidade ativa) -> Pode bloquear (+3 de bônus)
    # - Tectonic Plating (Battleworn, def 2) -> Prioridade máxima (+8 de bônus)
    state_defense = {
        "turnPlayer": 2,
        "playerID": 1,
        "playerHealth": 30,
        "combatChainPower": 5,
        "activeChainLink": {"cardNumber": "command_and_conquer", "totalPower": 5},
        "playerHand": [
            {"cardNumber": "staunch_response_blue", "action": 27, "block": 3, "defense": 3, "pitch": 3}
        ],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "bravo_showstopper", "slot": "Hero", "action": 0},
            {"cardNumber": "anothos", "slot": "Weapon", "action": 0},
            {"cardNumber": "crown_of_providence", "slot": "Head", "action": 3, "defense": 2, "actionDataOverride": "2"},
            {"cardNumber": "tectonic_plating", "slot": "Chest", "action": 3, "defense": 2, "actionDataOverride": "3"},
            {"cardNumber": "ironrot_gauntlet", "slot": "Arms", "action": 3, "defense": 1, "actionDataOverride": "4"},
        ],
    }

    blocks = pe.select_defense_blocks(state_defense)
    blocked_card_ids = [b[1] for b in blocks]

    # Tectonic Plating (Battleworn) deve ser escolhido para defender
    assert "3" in blocked_card_ids, "Equipamento Battleworn deve bloquear para absorver dano"
    # Crown of Providence (Blade Break com habilidade em vida alta) NÃO deve ser sacrificado
    assert "2" not in blocked_card_ids, "Blade Break com habilidade ativa NÃO deve ser sacrificado com HP alto"


def test_equipment_defense_survival_mode():
    """Em risco letal (HP <= 6), até equipamentos Blade Break com habilidades ativas bloqueiam para salvar a vida."""
    pe = PolicyEngine(hero_name="dorinthea_ironsong")

    state_survival = {
        "turnPlayer": 2,
        "playerID": 1,
        "playerHealth": 4,
        "combatChainPower": 6,
        "activeChainLink": {"cardNumber": "raging_onslaught", "totalPower": 6},
        "playerHand": [
            {"cardNumber": "strike_red", "action": 27, "block": 2, "defense": 2, "pitch": 1}
        ],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "crown_of_providence", "slot": "Head", "action": 3, "defense": 2, "actionDataOverride": "2"},
        ],
    }

    blocks = pe.select_defense_blocks(state_survival)
    blocked_card_ids = [b[1] for b in blocks]
    assert "2" in blocked_card_ids, "Em modo sobrevivência (HP <= 6), Blade Break deve bloquear para evitar morte"


def test_equipment_defense_respects_def_counters():
    """Equipamento com defCounters perde defesa efetiva. Se defesa chegar a 0, não bloqueia."""
    pe = PolicyEngine(hero_name="dorinthea_ironsong")

    state_depleted_equip = {
        "turnPlayer": 2,
        "playerID": 1,
        "playerHealth": 20,
        "combatChainPower": 4,
        "activeChainLink": {"cardNumber": "generic_attack", "totalPower": 4},
        "playerHand": [],
        "playerArsenal": [],
        "playerEquipment": [
            # Tunic base def 1, mas já possui 1 defCounter -> defesa efetiva = 0
            {"cardNumber": "fyendals_spring_tunic", "slot": "Chest", "action": 3, "defense": 1, "defCounters": 1, "actionDataOverride": "3"},
        ],
    }

    blocks = pe.select_defense_blocks(state_depleted_equip)
    assert len(blocks) == 0, "Equipamento com defCounters zerando a defesa não deve ser selecionado para bloquear"


def test_equipment_defense_preserves_hand_during_pivot():
    """Durante pivot com max_block_cards == 0, cartas da mão não bloqueiam, mas equipamento pode bloquear."""
    pe = PolicyEngine(hero_name="jarl_vetur_frost")

    state_pivot = {
        "turnPlayer": 2,
        "playerID": 1,
        "playerHealth": 14,
        "combatChainPower": 3,
        "activeChainLink": {"cardNumber": "herald_of_erudition", "totalPower": 3},
        "playerHand": [
            {"cardNumber": "fused_oaken_old_red", "action": 27, "block": 3, "defense": 3, "power": 7, "pitch": 1},
            {"cardNumber": "ice_eternal_blue", "action": 27, "block": 3, "defense": 3, "pitch": 3},
        ],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "ironrot_helm", "slot": "Head", "action": 3, "defense": 1, "actionDataOverride": "2"},
        ],
    }

    blocks = pe.select_defense_blocks(state_pivot)
    # Hand cards têm score penalizado pela preservação de mão ofensiva/pivot de Oaken Old
    # Mas o Ironrot pode ser usado para reduzir o dano sem queimar a mão
    blocked_names = [b[2].lower() for b in blocks]
    assert "fused_oaken_old_red" not in blocked_names, "Peça reservada do combo ofensivo nunca deve bloquear"


def test_equipment_activated_ability_main_phase():
    """Testa ativação de habilidade de equipamento na Fase Principal (M)."""
    pe = PolicyEngine(hero_name="rhinar_reckless_rampage")

    state_eq_ability = {
        "turnPlayer": 1,
        "playerID": 1,
        "amIActivePlayer": True,
        "turnPhase": "M",
        "actionPoints": 1,
        "playerHand": [
            {"cardNumber": "romping_club_blue", "action": 27, "pitch": 3, "cost": 0},
            {"cardNumber": "pack_hunt_red", "action": 27, "power": 6, "cost": 2, "pitch": 1},
        ],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "rhinar_reckless_rampage", "slot": "Hero", "action": 0},
            {"cardNumber": "romping_club", "slot": "Weapon", "action": 3, "actionDataOverride": "1"},
            {"cardNumber": "goliath_gauntlet", "slot": "Arms", "action": 3, "actionDataOverride": "2"},
        ],
        "playerResources": [3, 3],
        "playerPitchCount": 3,
    }

    best_action = pe.select_best_attack(state_eq_ability)
    assert best_action is not None
    # Goliath Gauntlet dá +2 e Go Again no próximo ataque de custo >= 2 (Pack Hunt)
    # Deve ser ativado como prioridade máxima antes de atacar da mão
    assert best_action["type"] == "equipment_ability"
    assert best_action["name"] == "goliath_gauntlet"
