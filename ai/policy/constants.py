"""
ai/policy/constants.py
======================
Constantes de domínio, bancos de cartas e habilidades para o motor de decisão FaB.
"""

import os
import json

_FAB_CARDS_DB = None


def _get_cards_db() -> dict:
    global _FAB_CARDS_DB
    if _FAB_CARDS_DB is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_paths = [
            "data/fab_cards_db.json",
            os.path.join(base_dir, "data", "fab_cards_db.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "fab_cards_db.json"),
        ]
        for p in db_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        _FAB_CARDS_DB = json.load(f)
                    break
                except Exception:
                    pass
        if _FAB_CARDS_DB is None:
            _FAB_CARDS_DB = {}
    return _FAB_CARDS_DB


_load_cards_db = _get_cards_db

_FAB_ABILITY_COSTS = None


def _load_ability_costs() -> dict:
    global _FAB_ABILITY_COSTS
    if _FAB_ABILITY_COSTS is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        db_paths = [
            "data/ability_costs.json",
            os.path.join(base_dir, "data", "ability_costs.json"),
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ability_costs.json"),
        ]
        for p in db_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        _FAB_ABILITY_COSTS = json.load(f)
                    break
                except Exception:
                    pass
        if _FAB_ABILITY_COSTS is None:
            _FAB_ABILITY_COSTS = {}
    return _FAB_ABILITY_COSTS


# ══════════════════════════════════════════════════════════════════
# CONSTANTES DE DOMÍNIO — FLESH AND BLOOD
# ══════════════════════════════════════════════════════════════════

# Palavras-chave de efeitos "On-Hit" perigosos que justificam bloqueio total
DANGEROUS_ON_HITS = {
    "crippling", "crush", "command_and_conquer", "red_in_the_ledger",
    "snatch", "mask_of_momentum", "bloodrot", "frailty", "inertia",
    "leave_no_witnesses", "surgical_extraction", "erase_face",
    "spitfire", "spinal_crush", "rightful_king", "hypothermia",
    "dishonor", "bonds_of_ancestry", "star_struck", "pummel"
}

# Mapeamento hierárquico de valor de ameaça de On-Hit (0.0 = vanilla, 10.0 = catastrófico)
ON_HIT_THREAT_VALUES = {
    # Catastrófico (8.0 - 10.0): Destrói arsenal / Trava o próximo turno / Descarta cartas / Dano letal
    "command_and_conquer": 10.0,
    "dishonor": 10.0,
    "star_struck": 9.5,
    "red_in_the_ledger": 9.5,
    "spinal_crush": 9.0,
    "crippling_crush": 9.0,
    "rightful_king": 8.5,
    "hypothermia": 8.0,
    "bonds_of_ancestry": 8.0,

    # Alto (5.0 - 7.5): Compra de cartas pelo oponente / Banimento / Interrupção
    "herald_of_erudition": 7.0,
    "mask_of_momentum": 6.5,
    "surgical_extraction": 6.5,
    "snatch": 6.0,
    "leave_no_witnesses": 6.0,
    "pummel": 6.0,
    "erase_face": 5.5,
    "spitfire": 5.0,

    # Médio (3.0 - 4.5): Efeitos de aflição / Debuff / Taxa de recurso
    "bloodrot": 4.0,
    "frailty": 3.5,
    "inertia": 3.5,
    "frostbite": 3.5,
    "freeze": 3.5,
    "widespread_ruin": 3.5,
}


def get_on_hit_threat(card_name: str, card_text: str = "", defending_hp: float = 40.0) -> float:
    """
    Calcula o valor numérico de ameaça de um efeito On-Hit (0.0 a 10.0).
    Escala dinamicamente para 10.0 se a vida do defensor estiver crítica (<= 2.0)
    e a ameaça infligir dano letal direto ou aflição (Bloodrot Pox).
    """
    name_low = str(card_name or "").lower().strip()
    text_low = str(card_text or "").lower()

    threat = 0.0
    for k, t_val in ON_HIT_THREAT_VALUES.items():
        if k in name_low:
            threat = t_val
            break

    if threat == 0.0 and ("when this hits" in text_low or "if this hits" in text_low or "hit effect" in text_low):
        if "destroy" in text_low and "arsenal" in text_low:
            threat = 10.0
        elif "discard" in text_low:
            threat = 7.0
        elif "draw" in text_low:
            threat = 6.0
        elif any(token in text_low for token in ["bloodrot", "frailty", "inertia"]):
            threat = 4.0
        else:
            threat = 3.0

    # Escalonamento dinâmico por vida crítica (CR 8.6.19 - Bloodrot Pox causa 2 dano no fim do turno)
    if defending_hp <= 2.0:
        if "bloodrot" in name_low or "bloodrot" in text_low:
            return 10.0
        if threat >= 4.0:
            return min(10.0, threat + 3.0)

    return threat



# Todas as 154+ armas oficiais mapeadas do Flesh and Blood
ALL_FAB_WEAPONS = {
    "aether_conduit", "annals_of_sutcliffe", "anothos", "aphrodias", "arcane_lantern",
    "aurum_aegis", "ball_breaker", "bank_breaker", "barbed_castaway", "bastion_of_duty",
    "bastion_of_unity", "beaming_blade", "beckoning_mistblade", "bloodied_oval", "bone_basher",
    "brush_of_heavenly_rites", "celebrant_broadsword", "cintari_saber", "cintari_saber_r",
    "claw_of_vynserakai", "cogwerx_blunderbuss", "compass_of_sunken_depths",
    "cosmo_scroll_of_ancestral_tapestry", "crows_nest", "crucible_of_aetherweave",
    "cutpurse_rapier", "dawnblade", "dawnblade_resplendent", "death_dealer",
    "decimator_great_axe", "dread_scythe", "dreadbore", "driftwood_quiver", "durendal",
    "duskblade", "edge_of_autumn", "enchanted_quiver", "farflight_longbow", "flail_of_agony",
    "fortitude_of_anvilheim", "galaxxi_black", "gavel_of_natural_order", "golden_grail",
    "graven_call", "graven_gaslight", "grimoire_of_fellingsong", "grimoire_of_the_haunt",
    "hammer_of_havenhold", "hammerhead_harpoon_cannon", "hanabi_blaster", "harmonized_kodachi", "harmonized_kodachi_r",
    "hatchet_of_body", "hatchet_of_mind", "hell_hammer", "hexagore_the_death_hydra",
    "high_riser", "hoarding_of_denial", "hot_streak", "hummingbird_call_of_adventure",
    "humour_plunge", "hunters_klaive", "hunters_klaive_r", "iris_of_reality",
    "jinglewood_smash_hit", "jubeel_spellbane", "krakens_aethervein", "kunai_of_retribution",
    "kunai_of_retribution_r", "lionclaw_maul", "luminaris", "luminaris_angels_glow",
    "luminaris_celestial_fury", "magrar", "mandible_claw", "mandible_claw_r",
    "mark_of_the_huntsman", "mark_of_the_huntsman_r", "merciless_battleaxe",
    "millers_grindstone", "mini_meataxe", "moment_maker", "nebula_blade", "nerve_scalpel",
    "nerve_scalpel_r", "obsidian_fire_vein", "obsidian_fire_vein_r", "orbitoclast",
    "orbitoclast_r", "ornate_tessen", "pile_driver", "plasma_barrel_shot",
    "proclamation_of_abundance", "proclamation_of_combat", "proclamation_of_production",
    "proclamation_of_requisition", "quicksilver_dagger", "quicksilver_dagger_r",
    "quiver_of_abyssal_depths", "quiver_of_rustling_leaves", "rampart_of_the_rams_head",
    "ravenous_meataxe", "raydn_duskbane", "reality_refractor", "reaping_blade", "red_liner",
    "redspine_manta", "redwood_hammer", "rok", "romping_club", "rosetta_thorn",
    "rotten_old_buckler", "rotwood_reaper", "rugged_roller", "sandscour_greatbow",
    "savage_claw", "scale_peeler", "scale_peeler_r", "scepter_of_pain", "scorpio_comet_tail",
    "searing_emberblade", "seasoned_saviour", "seerstone", "seven_sin_nebula", "shield_beater",
    "shiver", "silversheen_needle", "sledge_of_anvilheim", "spiders_bite", "spitfire",
    "staff_of_verdant_shoots", "stalagmite_bastion_of_isenloft", "star_fall",
    "steelbraid_buckler", "stonewall_impasse", "storm_of_sandikai", "summit_the_unforgiving",
    "surgent_aethertide", "symbiosis_shot", "talishar_the_lost_prince", "teklo_blaster",
    "teklo_plasma_pistol", "testament_of_valahai", "tiger_taming_khakkara", "titans_fist",
    "tremor_of_resistance", "voltaire_strike_twice", "volzar_meteor_storm",
    "volzar_the_lightning_rod", "vox_necropolis", "waning_moon", "winters_wail",
    "zenith_blade", "zephyr_needle", "zephyr_needle_r"
}

# Palavras-chave de armas adicionais para fallback
WEAPON_KEYWORDS = [
    "shot", "symbiosis", "blade", "kodachi", "flail", "hammer",
    "sword", "bow", "anothos", "scythe", "club", "staff", "axe",
    "scepter", "cynosure", "nebula", "weapon", "harmonised", "dawnblade",
    "saber", "cintari", "streak", "mandible", "hatchet", "duskblade",
    "raydn", "talishar", "rosetta", "reaper", "jubeel", "spider", "shield", "buckler"
]

# Custo de ativação de recursos para armas conhecidas no Flesh and Blood
KNOWN_WEAPON_COSTS = {
    "hammerhead_harpoon_cannon": 4,
    "anothos": 3, "sledge_of_anvilheim": 3, "titans_fist": 3, "pile_driver": 3, "rok": 3,
    "hell_hammer": 3, "hammer_of_havenhold": 3, "redwood_hammer": 3, "ball_breaker": 3,
    "romping_club": 2, "flail_of_agony": 2, "dread_scythe": 2, "reaping_blade": 2,
    "zenith_blade": 2, "harmonious_pipe": 2, "claw_of_vynserakai": 2, "hunters_klaive": 2,
    "hunters_klaive_r": 2, "volzar_meteor_storm": 2, "symbiosis_shot": 2,
    "plasma_barrel_shot": 2, "hanabi_blaster": 2, "waning_moon": 2, "krakens_aethervein": 2,
    "cintari_saber": 1, "cintari_saber_r": 1, "hot_streak": 1, "dawnblade": 1, "dawnblade_resplendent": 1,
    "kunai_of_retribution": 1, "kunai_of_retribution_r": 1, "harmonized_kodachi": 1,
    "harmonized_kodachi_r": 1, "mandible_claw": 1, "mandible_claw_r": 1, "spiders_bite": 1,
    "nerve_scalpel": 1, "nerve_scalpel_r": 1, "scale_peeler": 1, "scale_peeler_r": 1,
    "orbitoclast": 1, "orbitoclast_r": 1, "teklo_plasma_pistol": 1, "death_dealer": 1,
    "rosetta_thorn": 1, "nebula_blade": 1, "galaxxi_black": 1,
    "raydn_duskbane": 0, "redback_shroud": 0, "dreadbore": 0, "sandscour_greatbow": 0
}
