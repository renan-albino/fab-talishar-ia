import os
import json
import pytest
from ai.hero_strategies.base import HeroStrategy
from ai.policy_engine import PolicyEngine, get_on_hit_threat, ON_HIT_THREAT_VALUES
from ai.equipment_learning import (
    load_equipment_metadata,
    EquipmentTracker,
    EquipmentLearningEngine,
    EquipmentEvent,
    get_equipment_learning_engine,
)


def test_equipment_metadata_extraction():
    """Valida que data/equipment_metadata.json contém as propriedades mecânicas genéricas corretas."""
    meta = load_equipment_metadata()
    assert len(meta) >= 500, f"Esperado >= 500 equipamentos no banco, encontrado {len(meta)}"

    # Goliath Gauntlet: +2 de poder, requer ataque de custo >= 2, concede Go Again
    goliath = meta.get("goliath_gauntlet")
    assert goliath is not None
    assert goliath["power_buff"] == 2
    assert goliath["min_attack_cost"] == 2
    assert goliath["has_go_again"] is True
    assert goliath["slot"] == "arms"

    # Heartened Cross Strap: Desconto de 2 recursos, concede Go Again
    cross_strap = meta.get("heartened_cross_strap")
    assert cross_strap is not None
    assert cross_strap["cost_discount"] == 2
    assert cross_strap["has_go_again"] is True
    assert cross_strap["slot"] == "chest"

    # Fyendal's Spring Tunic: Gera 1 recurso, requer 3 contadores, defende 1 com Blade Break
    tunic = meta.get("fyendals_spring_tunic")
    assert tunic is not None
    assert tunic["grants_resource"] == 1
    assert tunic["req_counters"] == 3
    assert tunic["block"] == 1
    assert tunic["has_blade_break"] is True

    # Tectonic Plating: Cria Seismic Surge, Battleworn, defende 2, custo 1
    tectonic = meta.get("tectonic_plating")
    assert tectonic is not None
    assert tectonic["creates_token"] == "seismic_surge"
    assert tectonic["has_battleworn"] is True
    assert tectonic["block"] == 2
    assert tectonic["ability_cost"] == 1


def test_no_hardcoded_equipment_names():
    """Garante que evaluate_equipment_ability em ai/hero_strategies/base.py não possui nomes fixos hardcoded."""
    base_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ai", "hero_strategies", "base.py")
    with open(base_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Isola o corpo de evaluate_equipment_ability
    func_start = content.find("def evaluate_equipment_ability(")
    func_end = content.find("def evaluate_arsenal_card(", func_start)
    assert func_start != -1 and func_end != -1
    func_body = content[func_start:func_end]

    # Verifica ausência de verificações por substring de nome fixo de equipamento
    for forbidden in ['"goliath"', '"cross_strap"', '"tunic"', '"tectonic"', '"snapdragon"']:
        assert forbidden not in func_body, f"Encontrado hardcode de nome {forbidden} em evaluate_equipment_ability!"

    # Avaliação orientada a dados: mesmo equipamento fictício com metadata é avaliado perfeitamente
    strat = HeroStrategy(hero_name="generic")
    state = {
        "playerHand": [{"cardNumber": "heavy_attack", "cost": 2, "action": 27}],
        "playerArsenal": [],
    }
    # Equipamento com power_buff = 2
    eq_info = {"cardNumber": "goliath_gauntlet", "name": "Goliath Gauntlet"}
    score = strat.evaluate_equipment_ability(state, eq_info)
    assert score > 15.0, f"Esperado score positivo para buff de poder, obtido {score}"


def test_on_hit_threat_quantification():
    """Comprova a escala hierárquica de ameaça de efeitos On-Hit (Catastrófico > Alto > Médio > Nulo)."""
    # Catastróficos: >= 8.5
    assert get_on_hit_threat("command_and_conquer") >= 9.0
    assert get_on_hit_threat("red_in_the_ledger") >= 9.0
    assert get_on_hit_threat("spinal_crush") >= 9.0
    assert get_on_hit_threat("crippling_crush") >= 9.0

    # Altos: >= 5.5
    assert get_on_hit_threat("snatch") >= 6.0
    assert get_on_hit_threat("mask_of_momentum") >= 6.0
    assert get_on_hit_threat("herald_of_erudition") >= 6.0
    assert get_on_hit_threat("surgical_extraction") >= 6.0

    # Médios: >= 3.5
    assert get_on_hit_threat("bloodrot") >= 3.5
    assert get_on_hit_threat("frailty") >= 3.5
    assert get_on_hit_threat("inertia") >= 3.5

    # Vanilla / Sem On-Hit: exatamente 0.0
    assert get_on_hit_threat("raging_onslaught") == 0.0
    assert get_on_hit_threat("wounded_bull") == 0.0
    assert get_on_hit_threat("generic_attack") == 0.0
    assert get_on_hit_threat("strike_red") == 0.0


def test_armor_strictly_pruned_on_vanilla_attacks():
    """Ataques vanilla sem On-Hit com vida saudável (HP > 12) NUNCA queimam equipamentos."""
    pe = PolicyEngine(hero_name="kassai_of_the_golden_sand")

    state_vanilla = {
        "turnPlayer": 2,
        "playerID": 1,
        "playerHealth": 20,
        "combatChainPower": 4,
        "activeChainLink": {"cardNumber": "raging_onslaught", "totalPower": 4},
        "playerHand": [
            {"cardNumber": "strike_blue", "action": 27, "block": 3, "defense": 3, "pitch": 3},
            {"cardNumber": "clash_blue", "action": 27, "block": 3, "defense": 3, "pitch": 3},
        ],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "ironrot_gauntlet", "slot": "Arms", "action": 3, "defense": 1, "actionDataOverride": "10"},
            {"cardNumber": "tectonic_plating", "slot": "Chest", "action": 3, "defense": 2, "actionDataOverride": "11"},
        ],
    }

    blocks = pe.select_defense_blocks(state_vanilla)
    blocked_card_ids = [str(b[1]) for b in blocks]

    # Armaduras não podem ser gastas para mitigar ataque comum quando a vida está alta
    assert "10" not in blocked_card_ids, "Ironrot não deve bloquear ataque vanilla quando HP > 12"
    assert "11" not in blocked_card_ids, "Tectonic Plating não deve bloquear ataque vanilla quando HP > 12"

    # Preservação de mão: usa no máximo 1 carta de mão (não desperdiça as 2)
    assert len(blocks) <= 1, f"Esperado no máximo 1 bloqueio para ataque vanilla, obteve {len(blocks)}"


def test_armor_minimal_breakpoint_on_hit():
    """
    Em ataques com On-Hit (ex: Snatch de poder 4), o otimizador escolhe o subconjunto de menor custo:
    Usa exatamente 1 carta de mão (def 3) + 1 armadura (def 1) = 4 de defesa total,
    anulando o On-Hit e poupando a 2ª carta da mão para o contra-ataque (Pivot)!
    """
    pe = PolicyEngine(hero_name="dorinthea_ironsong")

    state_on_hit = {
        "turnPlayer": 2,
        "playerID": 1,
        "playerHealth": 18,
        "combatChainPower": 4,
        "activeChainLink": {"cardNumber": "snatch", "totalPower": 4},
        "playerHand": [
            {"cardNumber": "dawn_strike_red", "action": 27, "block": 3, "defense": 3, "power": 5, "pitch": 1, "actionDataOverride": "h1"},
            {"cardNumber": "glint_the_iron_blue", "action": 27, "block": 3, "defense": 3, "power": 3, "pitch": 3, "actionDataOverride": "h2"},
        ],
        "playerArsenal": [],
        "playerEquipment": [
            {"cardNumber": "ironrot_gauntlet", "slot": "Arms", "action": 3, "defense": 1, "actionDataOverride": "eq_ironrot"},
        ],
    }

    blocks = pe.select_defense_blocks(state_on_hit)
    blocked_ids = [str(b[1]) for b in blocks]

    # Subconjunto ótimo: 1 carta de mão (3) + Ironrot (1) = 4 block total
    assert "eq_ironrot" in blocked_ids, "Ironrot deve ser usado para fechar o breakpoint exato de 4 e anular o On-Hit"
    hand_blocks_used = [b for b in blocks if str(b[1]) in ("h1", "h2")]
    assert len(hand_blocks_used) == 1, (
        f"Deveria ter usado apenas 1 carta da mão + armadura para salvar a outra carta para o pivot, mas usou {len(hand_blocks_used)}"
    )


def test_equipment_experience_learning_persistence(tmp_path):
    """Testa rastreamento em tempo de partida e persistência com calibração dinâmica pós-jogo."""
    test_stats_file = str(tmp_path / "equipment_usage_stats_test.json")
    engine = EquipmentLearningEngine(stats_path=test_stats_file)

    # Multiplicador inicial deve ser 1.0 (neutro)
    assert engine.get_equipment_multiplier("kassai", "goliath_gauntlet") == 1.0

    # Simula partida 1: Vitória usando Goliath Gauntlet (+ delta de eval positivo)
    tracker = EquipmentTracker(hero_name="kassai")
    tracker.track_activation("kassai", "goliath_gauntlet", slot="arms", turn=2, pre_eval=1.0, post_eval=3.0)
    tracker.track_block("kassai", "ironrot_gauntlet", slot="arms", turn=3, pre_eval=0.0, post_eval=1.0)

    events = tracker.get_events()
    assert len(events) == 2

    # Registra vitória
    engine.record_match_result("kassai", events, won=True)

    # Multiplicador de Goliath Gauntlet deve subir (> 1.0) devido à vitória e delta positivo
    mult_win = engine.get_equipment_multiplier("kassai", "goliath_gauntlet")
    assert mult_win > 1.0, f"Multiplicador pós-vitória deveria subir (> 1.0), mas foi {mult_win}"

    # Simula 3 derrotas consecutivas
    tracker.clear()
    tracker.track_activation("kassai", "goliath_gauntlet", slot="arms", turn=1, pre_eval=2.0, post_eval=-1.0)
    for _ in range(3):
        engine.record_match_result("kassai", tracker.get_events(), won=False)

    # Agora a taxa de vitórias caiu (1 win, 3 losses) -> multiplicador deve cair (< 1.0)
    mult_loss = engine.get_equipment_multiplier("kassai", "goliath_gauntlet")
    assert mult_loss < 1.0, f"Multiplicador com mais derrotas deveria cair (< 1.0), mas foi {mult_loss}"
