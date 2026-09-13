import os
import sys
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai.hero_strategies import (
    get_hero_strategy,
    HalaStrategy,
    DashIOStrategy,
    VynnsetStrategy,
    ArakniMarionetteStrategy,
    GravyBonesStrategy,
    MarioStrategy,
    MarlinnStrategy,
    WarriorStrategy,
    MechanologistStrategy,
    RunebladeStrategy,
    AssassinStrategy,
    MerchantStrategy,
)
from ai.trainer import RoundRobinMatchupEngine
from deck_parser import enrich_deck_metadata, list_saved_decks
from bot_client import FabBotClient


# =====================================================================
# 1. Resolução Canônica das Estratégias Específicas
# =====================================================================

def test_hero_strategies_resolution():
    """Testa que os heróis identificados resolvem para suas classes específicas com herança correta."""
    strat_hala = get_hero_strategy("hala")
    assert isinstance(strat_hala, HalaStrategy)
    assert isinstance(strat_hala, WarriorStrategy)
    assert strat_hala.hero_name == "hala"

    strat_dash = get_hero_strategy("dash_io")
    assert isinstance(strat_dash, DashIOStrategy)
    assert isinstance(strat_dash, MechanologistStrategy)
    assert strat_dash.hero_name == "dash_io"

    strat_vynn = get_hero_strategy("vynnset")
    assert isinstance(strat_vynn, VynnsetStrategy)
    assert isinstance(strat_vynn, RunebladeStrategy)
    assert strat_vynn.hero_name == "vynnset"

    strat_gravy = get_hero_strategy("gravy_bones")
    assert isinstance(strat_gravy, GravyBonesStrategy)
    assert isinstance(strat_gravy, MerchantStrategy)
    assert strat_gravy.hero_name == "gravy_bones"

    strat_mario = get_hero_strategy("mario")
    assert isinstance(strat_mario, MarioStrategy)
    assert isinstance(strat_mario, AssassinStrategy)
    assert strat_mario.hero_name == "mario"

    strat_marlinn = get_hero_strategy("marlinn")
    assert isinstance(strat_marlinn, MarlinnStrategy)

    strat_arakni = get_hero_strategy("arakni_marionette")
    assert isinstance(strat_arakni, ArakniMarionetteStrategy)
    assert isinstance(strat_arakni, AssassinStrategy)


# =====================================================================
# 2. Heurísticas Específicas dos Heróis
# =====================================================================

def test_hala_heuristics():
    """Testa heurísticas de Hala Bladesaint (Warrior / Zenith Blade)."""
    strat = HalaStrategy()
    
    # Avaliação de ataque com bônus para buffs de lâmina / armas
    boosted = strat.evaluate_attack_card("edict_of_steel", power=3, cost=1, has_go_again=False, pitch=1)
    base = strat.evaluate_attack_card("generic_attack", power=3, cost=1, has_go_again=False, pitch=1)
    assert boosted > base, f"Edict of Steel ({boosted}) deve ter score maior que generic ({base})"

    # Avaliação de ataque com arma (Zenith Blade)
    zenith_score = strat.evaluate_weapon_attack("zenith_blade", floating_res=2, total_res=4, has_hand_attacks=False)
    assert zenith_score >= 12.0

    # Avaliação de bloqueio
    block_score = strat.evaluate_block_card("ironrot_helm", block_val=1, pitch=2, power=0, has_go_again=False)
    assert block_score > 0.0


def test_dash_io_heuristics():
    """Testa heurísticas de Dash I/O (Mechanologist / Items com Crank)."""
    strat = DashIOStrategy()

    # Bônus para itens mecanologistas (Boom Grenade, Convection Amplifier)
    item_score = strat.evaluate_attack_card("boom_grenade", power=0, cost=1, has_go_again=False, pitch=2)
    generic_score = strat.evaluate_attack_card("generic_item", power=0, cost=1, has_go_again=False, pitch=2)
    assert item_score > generic_score, f"Boom Grenade ({item_score}) deve superar genérico ({generic_score})"

    # Ataque com arma Symbiosis Shot
    weapon_score = strat.evaluate_weapon_attack("symbiosis_shot", floating_res=1, total_res=3, has_hand_attacks=False)
    assert weapon_score >= 8.0

    # Habilidade de equipamento Teklo Foundry Heart
    eq_score = strat.evaluate_equipment_ability("teklo_foundry_heart", floating_res=0, total_res=1)
    assert eq_score >= 15.0


def test_vynnset_heuristics():
    """Testa heurísticas de Vynnset (Shadow Runeblade / Rune Gate)."""
    strat = VynnsetStrategy()

    # Rune Gate card com Shadow synergy
    rg_score = strat.evaluate_attack_card("runegate_shadow_strike", power=5, cost=2, has_go_again=False, pitch=1)
    gen_score = strat.evaluate_attack_card("generic_swing", power=5, cost=2, has_go_again=False, pitch=1)
    assert rg_score > gen_score, f"Rune gate card ({rg_score}) deve superar genérico ({gen_score})"

    # Habilidade de herói (banir ataque de Runegate para criar Runechant e Piercing 1)
    ability_score = strat.evaluate_hero_ability(state={"playerHand": [{"cardNumber": "cull_red"}, {"cardNumber": "card2"}]}, hero_info={})
    assert ability_score >= 15.0


def test_gravy_bones_and_mario_heuristics():
    """Testa heurísticas de Gravy Bones e Mario (Assassin / Pirate)."""
    g_strat = GravyBonesStrategy()
    # Ataque finalizador de pirata (Conqueror of the High Seas)
    conq_score = g_strat.evaluate_attack_card("conqueror_of_the_high_seas", power=6, cost=2, has_go_again=False, pitch=1)
    assert conq_score >= 15.0

    # Equipamento Gold Baited Hook
    hook_score = g_strat.evaluate_equipment_ability("gold_baited_hook", floating_res=1, total_res=2)
    assert hook_score >= 10.0

    # Arma Compass of Sunken Depths
    compass_score = g_strat.evaluate_weapon_attack("compass_of_sunken_depths", floating_res=1, total_res=3, has_hand_attacks=False)
    assert compass_score >= 8.0

    # Mario / Arakni Marionette
    m_strat = MarioStrategy()
    m_score = m_strat.evaluate_attack_card("surgical_extraction", power=3, cost=1, has_go_again=False, pitch=1)
    assert m_score >= 8.0


# =====================================================================
# 3. Motor de Pareamento Round-Robin
# =====================================================================

def test_round_robin_matchup_engine():
    """Testa que o RoundRobinMatchupEngine distribui todos os pares uniformemente sem repetição viciada."""
    pool = ["dash_io", "hala", "mario", "gravy_bones", "nuu", "oscilio"]
    n = len(pool)
    expected_cycle_len = n * (n - 1)  # 6 * 5 = 30 pares distintos

    engine = RoundRobinMatchupEngine(seed=12345)

    # 1. Gerar exatamente um ciclo completo
    cycle_1 = [engine.next_pair(pool) for _ in range(expected_cycle_len)]
    
    # Todos os 30 pares devem ser únicos no primeiro ciclo
    assert len(set(cycle_1)) == expected_cycle_len, "Todos os confrontos de um ciclo devem ser únicos"

    # Nenhum confronto deve ser com o mesmo herói em ambos os lados
    for d1, d2 in cycle_1:
        assert d1 != d2, f"Matchup com mesmo deck inesperado: {d1} vs {d2}"

    # 2. Gerar o segundo ciclo completo
    cycle_2 = [engine.next_pair(pool) for _ in range(expected_cycle_len)]
    assert len(set(cycle_2)) == expected_cycle_len

    # No acumulado de 2 ciclos, cada par ordenado (d1, d2) deve ter sido jogado exatamente 2 vezes
    stats = engine.get_stats()
    assert stats["total_pairs_dispatched"] == 2 * expected_cycle_len
    assert stats["unique_matchups"] == expected_cycle_len
    for pair, count in engine.pair_counts.items():
        assert count == 2, f"Par {pair} esperado com contagem 2, mas teve {count}"


# =====================================================================
# 4. Enriquecimento de Metadados e Normalização de Decks
# =====================================================================

def test_deck_parser_metadata_enrichment():
    """Testa a extração canônica de classe, talentos e formato pelo deck_parser."""
    # Deck de exemplo Dash I/O (Adulto no Classic Constructed)
    dash_raw = {
        "name": "Dash IO Control",
        "format": "cc",
        "cards": [
            {"identifier": "dash_io", "slot": "Hero"},
            {"identifier": "teklo_plasma_pistol", "slot": "Weapon"},
            {"identifier": "convection_amplifier", "count": 3}
        ]
    }
    enriched = enrich_deck_metadata(dash_raw)
    assert enriched["class"].upper() == "MECHANOLOGIST"
    assert enriched["is_young"] is False
    assert enriched["hero_name"] == "Dash I/O"
    assert enriched["format"] == "cc"

    # Verificar que os decks salvos possuem metadados válidos
    saved_decks = list_saved_decks()
    assert len(saved_decks) >= 10, "Esperado pelo menos 10 decks em decks/"
    
    for d in saved_decks:
        assert "hero" in d or "hero_name" in d, f"Deck {d.get('slug')} sem identificação de herói"
        assert "class" in d, f"Deck {d.get('slug')} sem metadado 'class'"
        assert "format" in d, f"Deck {d.get('slug')} sem metadado 'format'"


# =====================================================================
# 5. Ranqueamento Inteligente de Escolhas em 1ª Tentativa
# =====================================================================

def test_multichoose_candidate_ranking():
    """Testa o scoring semântico de candidatos para botões de escolha única e múltipla."""
    bot = FabBotClient("test_room", "decks/dash_io.json", "host", "TestBot")

    # Candidatos simulados
    candidates = [
        {"mode": 10, "buttonInput": "Pass", "caption": "Pass Priority"},
        {"mode": 20, "buttonInput": "codex_of_frailty", "caption": "Codex of Frailty"},
        {"mode": 20, "buttonInput": "leave_no_witnesses", "caption": "Leave No Witnesses"},
        {"mode": 20, "buttonInput": "sink_below_red", "caption": "Sink Below"},
    ]

    ranked = bot._rank_choice_candidates(candidates)
    assert len(ranked) == len(candidates)

    top_card = ranked[0]["buttonInput"]
    # Codex of Frailty ou Leave No Witnesses devem liderar o ranking
    assert top_card in ("codex_of_frailty", "leave_no_witnesses"), f"Esperado top card prioritário, obtido {top_card}"


def test_dash_io_strategy_accepts_hand_attacks_kwarg():
    """Garante que DashIOStrategy, Arakni e Gravy aceitam hand_attacks sem erro de assinatura."""
    dash_strat = DashIOStrategy("dash_io")
    state = {"playerHand": [], "playerEquipment": []}
    eq = {"cardNumber": "teklo_foundry_heart", "action": 3}
    hand_attacks = [{"cardNumber": "zero_to_sixty_red", "power": 4}]

    # Chamada estilo PolicyEngine:evaluate_equipment_ability(state, eq, hand_attacks=hand_attacks)
    score = dash_strat.evaluate_equipment_ability(state, eq, hand_attacks=hand_attacks)
    assert score == 16.0, f"Esperado 16.0 para Teklo Foundry Heart em Dash I/O, obtido {score}"

    # Chamada legada (eq_name, floating, total)
    leg_score = dash_strat.evaluate_equipment_ability("teklo_foundry_heart", 0, 2)
    assert leg_score == 16.0

    # Gravy Bones
    gravy_strat = GravyBonesStrategy("gravy_bones")
    g_score = gravy_strat.evaluate_equipment_ability(state, {"cardNumber": "gold_baited_hook"}, hand_attacks=hand_attacks)
    assert g_score == 14.0


def test_multichoose_sink_protects_arsenal_from_cnc():
    """Ao afundar carta com Crown of Providence sob ameaça de Command and Conquer, a carta do Arsenal é priorizada."""
    bot = FabBotClient("test_room", "decks/dash_io.json", "host", "TestBot")

    state = {
        "promptText": "Choose a card to sink (or Pass)",
        "playerArsenal": [{"cardNumber": "crucial_defense_red"}],
        "activeChainLink": {"cardNumber": "command_and_conquer", "totalPower": 6},
    }
    popup = {"title": "Choose a card to sink (or Pass)"}

    arsenal_cand = {"cardNumber": "crucial_defense_red", "actionDataOverride": "MYARS-0", "label": "Arsenal"}
    hand_cand = {"cardNumber": "zero_to_sixty_red", "actionDataOverride": "MYHAND-0", "label": "Hand"}

    score_ars = bot._score_choice_candidate(arsenal_cand, turn_phase="CHOOSEMULTIZONE", state=state, popup=popup)
    score_hand = bot._score_choice_candidate(hand_cand, turn_phase="CHOOSEMULTIZONE", state=state, popup=popup)

    assert score_ars > score_hand, "A carta do Arsenal DEVE ser escolhida para afundar e se salvar de Command and Conquer!"


def test_multichoose_sink_cycles_worst_card_when_arsenal_safe():
    """Ao afundar carta sem ameaça ao Arsenal, a pior carta da mão é afundada para ciclar (preservando o Arsenal e cartas fortes)."""
    bot = FabBotClient("test_room", "decks/dash_io.json", "host", "TestBot")

    state = {
        "promptText": "Choose a card to sink (or Pass)",
        "playerArsenal": [{"cardNumber": "valuable_arsenal_card"}],
        "activeChainLink": {"cardNumber": "snatch_red", "totalPower": 4},
    }
    popup = {"title": "Choose a card to sink (or Pass)"}

    arsenal_cand = {"cardNumber": "valuable_arsenal_card", "actionDataOverride": "MYARS-0", "label": "Arsenal"}
    good_hand_card = {"cardNumber": "codex_of_frailty", "actionDataOverride": "MYHAND-0"}
    weak_hand_card = {"cardNumber": "generic_weak_card", "actionDataOverride": "MYHAND-1"}

    score_ars = bot._score_choice_candidate(arsenal_cand, turn_phase="CHOOSEMULTIZONE", state=state, popup=popup)
    score_good = bot._score_choice_candidate(good_hand_card, turn_phase="CHOOSEMULTIZONE", state=state, popup=popup)
    score_weak = bot._score_choice_candidate(weak_hand_card, turn_phase="CHOOSEMULTIZONE", state=state, popup=popup)

    assert score_weak > score_good, "A pior carta deve ter pontuação mais alta para ser afundada (invertida)"
    assert score_weak > score_ars, "O Arsenal NÃO deve ser afundado quando está seguro"

