import sys
import os
import re

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.hero_strategies import (
    get_hero_strategy,
    HERO_CLASS_REGISTRY,
    HeroStrategy,
    GuardianStrategy,
    JarlStrategy,
    BruteStrategy,
    WarriorStrategy,
    NinjaStrategy,
    RangerStrategy,
    MechanologistStrategy,
    RunebladeStrategy,
    WizardStrategy,
    IllusionistStrategy,
    AssassinStrategy,
    MerchantStrategy,
)
from ai.policy_engine import PolicyEngine

def test_all_139_official_heroes_resolution():
    print("=== TESTE 1: RESOLUÇÃO DOS 139 HERÓIS OFICIAIS ===")
    helper_path = "Talishar/Libraries/LegalHeroesHelper.php"
    assert os.path.exists(helper_path), f"Arquivo não encontrado: {helper_path}"

    with open(helper_path, "r", encoding="utf-8") as f:
        php_content = f.read()

    hero_slugs = re.findall(r"'heroId'\s*=>\s*'([^']+)'", php_content)
    print(f"Total de heróis extraídos de LegalHeroesHelper.php: {len(hero_slugs)}")
    assert len(hero_slugs) >= 130, f"Esperado pelo menos 130 heróis, encontrado {len(hero_slugs)}"

    unmapped = []
    generic_count = 0
    class_counts = {}

    for hid in hero_slugs:
        strat = get_hero_strategy(hid)
        cls_name = strat.__class__.__name__
        class_counts[cls_name] = class_counts.get(cls_name, 0) + 1
        
        # Apenas heróis sem classe definida podem cair em HeroStrategy
        if cls_name == "HeroStrategy":
            generic_count += 1
            unmapped.append(hid)

    print("\nDistribuição de estratégias dos heróis oficiais:")
    for cls_name, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {cls_name:25s}: {count:3d} heróis")

    assert generic_count == 0, f"Existem heróis oficiais caindo na estratégia genérica: {unmapped}"
    print("\n[OK] 100% dos heróis oficiais mapeados para suas classes especializadas com sucesso!\n")


def test_dynamic_fallback():
    print("=== TESTE 2: FALLBACK DINÂMICO VIA CARD DATABASE ===")
    # Herói desconhecido que tenha raiz ou classe no DB
    strat1 = get_hero_strategy("rhinar_custom_deck_variant")
    assert isinstance(strat1, BruteStrategy), f"Esperado BruteStrategy, obtido {type(strat1)}"

    strat2 = get_hero_strategy("dorinthea_experimental_version")
    assert isinstance(strat2, WarriorStrategy), f"Esperado WarriorStrategy, obtido {type(strat2)}"

    strat3 = get_hero_strategy("azalea_tournament_edition")
    assert isinstance(strat3, RangerStrategy), f"Esperado RangerStrategy, obtido {type(strat3)}"

    strat4 = get_hero_strategy("jarl_veteran_cold")
    assert isinstance(strat4, JarlStrategy), f"Esperado JarlStrategy, obtido {type(strat4)}"

    print("[OK] Fallback dinâmico funcionando perfeitamente!\n")


def test_archetype_specific_heuristics():
    print("=== TESTE 3: VALIDAÇÃO DAS HEURÍSTICAS DE CADA CLASSE ===")

    # 1. GUARDIAN & JARL
    g_strat = get_hero_strategy("bravo_showstopper")
    assert g_strat.is_heavy_hero is True
    assert g_strat.has_heavy_attack({"power": 7, "pitch": 1, "name": "spinal_crush_red"}) is True
    assert g_strat.evaluate_pitch_card("blue_card", pitch=3, cost=0, power=3, has_go_again=False) > 20.0
    assert g_strat.evaluate_weapon_attack("anothos", floating_res=2, total_res=4, has_hand_attacks=False) >= 6.5
    print("  ✓ GuardianStrategy: Pivot line + Pitch 3 + Heavy weapon swing")

    j_strat = get_hero_strategy("jarl_vetreidi")
    assert isinstance(j_strat, JarlStrategy)
    assert j_strat.evaluate_attack_card("oaken_old_red", power=7, cost=3, has_go_again=False, pitch=1) >= 20.0
    print("  ✓ JarlStrategy: Bônus de Oaken Old e Frostbite")

    # 2. BRUTE
    b_strat = get_hero_strategy("rhinar_reckless_rampage")
    assert b_strat.is_heavy_hero is True
    assert b_strat.has_heavy_attack({"power": 6, "pitch": 1}) is True
    assert b_strat.has_heavy_attack({"power": 4, "pitch": 1}) is False
    score_6pow = b_strat.evaluate_attack_card("pack_hunt_red", power=6, cost=2, has_go_again=False, pitch=1)
    score_3pow = b_strat.evaluate_attack_card("weak_hit_red", power=3, cost=0, has_go_again=False, pitch=1)
    assert score_6pow > score_3pow + 6.0
    print("  ✓ BruteStrategy: Prioridade absoluta para cartas de Poder 6+")

    # 3. WARRIOR
    w_strat = get_hero_strategy("dorinthea_ironsong")
    assert w_strat.is_heavy_hero is False
    w_score = w_strat.evaluate_weapon_attack("dawnblade", floating_res=1, total_res=3, has_hand_attacks=True)
    assert w_score >= 10.0, f"Guerreiro deve ter prioridade máxima de ataque de arma, obtido {w_score}"
    assert w_strat.evaluate_block_card("ironsong_response_red", block_val=3, pitch=1, power=0, has_go_again=False) < -10.0
    print("  ✓ WarriorStrategy: Arma como ataque primário + Preservação de Reações de Ataque")

    # 4. NINJA
    n_strat = get_hero_strategy("katsu_the_wanderer")
    assert n_strat.is_heavy_hero is False
    score_combo = n_strat.evaluate_attack_card("leg_tap_red", power=4, cost=0, has_go_again=True, pitch=1)
    assert score_combo >= 13.0
    print("  ✓ NinjaStrategy: Bônus de Combo e Go Again starter")

    # 5. RANGER
    r_strat = get_hero_strategy("marlynn_treasure_hunter")
    assert r_strat.is_heavy_hero is False
    ars_gem = r_strat.evaluate_arsenal_card({"name": "riches_of_tropal_dhani_yellow", "pitch": 2})
    ars_arrow = r_strat.evaluate_arsenal_card({"name": "endless_arrow_red", "pitch": 1, "power": 5})
    assert ars_gem <= -9000.0
    assert ars_arrow >= 25.0
    print("  ✓ RangerStrategy: Rejeição estrita de gemas e prioridade total para flechas")

    # 6. MECHANOLOGIST
    m_strat = get_hero_strategy("dash_inventor_extraordinaire")
    assert m_strat.should_boost("zero_to_sixty", hand_size=3, deck_size=10) is True
    assert m_strat.should_boost("zero_to_sixty", hand_size=3, deck_size=4) is False
    print("  ✓ MechanologistStrategy: Proteção contra fadiga no Boost (deck <= 6)")

    # 7. RUNEBLADE
    rb_strat = get_hero_strategy("viserai_rune_blood")
    rb_weap = rb_strat.evaluate_weapon_attack("rosetta_thorn", floating_res=1, total_res=3, has_hand_attacks=False)
    assert rb_weap >= 7.0
    print("  ✓ RunebladeStrategy: Ataque híbrido de Rosetta Thorn")

    # 8. WIZARD
    wz_strat = get_hero_strategy("kano_dracai_of_aether")
    pitch_blue = wz_strat.evaluate_pitch_card("energy_potion_blue", pitch=3, cost=0, power=0, has_go_again=False)
    assert pitch_blue >= 20.0
    print("  ✓ WizardStrategy: Demanda crítica por pitch azul para Crucible")

    # 9. ASSASSIN
    a_strat = get_hero_strategy("arakni_huntsman")
    stealth_score = a_strat.evaluate_attack_card("surgical_extraction_red", power=4, cost=1, has_go_again=False, pitch=1)
    assert stealth_score >= 8.0
    print("  ✓ AssassinStrategy: Bônus para cartas de Contrato e Stealth")

    print("\n[OK] Todas as heurísticas especializadas de arquétipo validadas!\n")


def test_policy_engine_integration():
    print("=== TESTE 4: INTEGRAÇÃO COM O POLICY ENGINE ===")

    # Teste de seleção de ataque para Warrior (deve atacar com a arma Dawnblade primeiro)
    engine_warrior = PolicyEngine(hero_name="dorinthea", num_mcts_sims=0)
    state_warrior = {
        "playerHealth": 20,
        "playerAP": 1,
        "playerResources": [1, 0],
        "playerHand": [
            {"cardNumber": "ironsong_response_red", "power": 0, "pitch": 1, "cost": 1, "action": 0},
            {"cardNumber": "steelblade_shunt_blue", "power": 0, "pitch": 3, "cost": 2, "action": 0},
        ],
        "playerEquipment": [
            {"cardNumber": "dawnblade", "action": 28, "slot": "Weapon"}
        ]
    }
    atk_w = engine_warrior.select_best_attack(state_warrior, set())
    assert atk_w is not None and atk_w["name"] == "dawnblade", f"Warrior deveria atacar com Dawnblade, obtido {atk_w}"
    print("  ✓ PolicyEngine com Warrior: Dawnblade selecionada com sucesso")

    # Teste de preservação de pivot para Brute (Rhinar não bloqueia com ataque 6+)
    engine_brute = PolicyEngine(hero_name="rhinar", num_mcts_sims=0)
    state_brute = {
        "playerHealth": 22,
        "playerHand": [
            {"cardNumber": "pack_hunt_red", "power": 6, "pitch": 1, "defense": 3, "action": 27},
            {"cardNumber": "blue_bark_blue", "power": 2, "pitch": 3, "defense": 3, "action": 27},
            {"cardNumber": "blue_block_blue", "power": 2, "pitch": 3, "defense": 3, "action": 27},
        ],
        "activeChainLink": {"totalPower": 4, "cardNumber": "generic_attack"}
    }
    blocks_brute = engine_brute.select_defense_blocks(state_brute)
    b_names = [b[2] for b in blocks_brute]
    assert "pack_hunt_red" not in b_names, f"Rhinar não deve bloquear com Pack Hunt (power 6+), bloqueou com: {b_names}"
    print("  ✓ PolicyEngine com Brute: Pack Hunt preservado para pivot de 6+ poder")

    print("\n[OK] Integração completa com PolicyEngine validada!\n")


if __name__ == "__main__":
    test_all_139_official_heroes_resolution()
    test_dynamic_fallback()
    test_archetype_specific_heuristics()
    test_policy_engine_integration()
    print("=" * 60)
    print(">>> TODOS OS TESTES PASSARAM COM SUCESSO! ARQUITETURA 100% HOMOLOGADA <<<")
    print("=" * 60)
