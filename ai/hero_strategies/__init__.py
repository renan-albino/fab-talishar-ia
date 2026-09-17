"""
ai/hero_strategies/__init__.py
==============================
Pacote modular de estratégias especializadas por classe e herói de Flesh and Blood.
Mapeamento canônico de todos os 139+ heróis oficiais e arquétipos de classe.
"""

from functools import lru_cache
from typing import Dict, Any

from .base import (
    HeroStrategy,
    TurnPlan,
    is_resource_or_gem_card,
    KNOWN_AMBUSH_CARDS,
)

from .guardian import GuardianStrategy, JarlStrategy
from .brute import BruteStrategy
from .warrior import WarriorStrategy, KassaiStrategy, HalaStrategy
from .ninja import NinjaStrategy
from .ranger import RangerStrategy, MarlynnStrategy
from .mechanologist import MechanologistStrategy, DashIOStrategy
from .runeblade import RunebladeStrategy, VynnsetStrategy
from .wizard import WizardStrategy, OscilioStrategy
from .illusionist import IllusionistStrategy
from .assassin import AssassinStrategy, ArakniMarionetteStrategy
from .merchant import MerchantStrategy, GravyBonesStrategy
from .teklovossen import TeklovossenStrategy

MarioStrategy = ArakniMarionetteStrategy
MarlinnStrategy = MarlynnStrategy

__all__ = [
    "HeroStrategy",
    "TurnPlan",
    "GuardianStrategy",
    "JarlStrategy",
    "BruteStrategy",
    "WarriorStrategy",
    "KassaiStrategy",
    "HalaStrategy",
    "NinjaStrategy",
    "RangerStrategy",
    "MarlynnStrategy",
    "MarlinnStrategy",
    "MechanologistStrategy",
    "DashIOStrategy",
    "RunebladeStrategy",
    "VynnsetStrategy",
    "WizardStrategy",
    "OscilioStrategy",
    "IllusionistStrategy",
    "AssassinStrategy",
    "ArakniMarionetteStrategy",
    "MarioStrategy",
    "MerchantStrategy",
    "GravyBonesStrategy",
    "TeklovossenStrategy",
    "is_resource_or_gem_card",
    "KNOWN_AMBUSH_CARDS",
    "get_hero_strategy",
    "HERO_CLASS_REGISTRY",
]


# ══════════════════════════════════════════════════════════════════
# REGISTRO CANÔNICO EXAUSTIVO DOS 139 HERÓIS DE FLESH AND BLOOD
# ══════════════════════════════════════════════════════════════════

HERO_CLASS_REGISTRY: Dict[str, type] = {
    # ── GUARDIAN ────────────────────────────────────────────────
    "bravo_showstopper": GuardianStrategy,
    "bravo": GuardianStrategy,
    "bravo_star_of_the_show": GuardianStrategy,
    "bravo_flattering_showman": GuardianStrategy,
    "oldhim_grandfather_of_eternity": GuardianStrategy,
    "oldhim": GuardianStrategy,
    "valda_brightaxe": GuardianStrategy,
    "valda_seismic_impact": GuardianStrategy,
    "valda": GuardianStrategy,
    "betsy_skin_in_the_game": GuardianStrategy,
    "betsy": GuardianStrategy,
    "victor_goldmane_high_and_mighty": GuardianStrategy,
    "victor_goldmane": GuardianStrategy,
    "victor": GuardianStrategy,
    "yoji_royal_protector": GuardianStrategy,
    "yoji": GuardianStrategy,
    "brevant_civic_protector": GuardianStrategy,
    "brevant": GuardianStrategy,
    "tuffnut_bumbling_hulkster": GuardianStrategy,
    "tuffnut": GuardianStrategy,
    "lyath_goldmane_vile_savant": GuardianStrategy,
    "lyath_goldmane": GuardianStrategy,
    "lyath": GuardianStrategy,
    "terra": GuardianStrategy,
    "guardian": GuardianStrategy,

    # ── JARL (Elemental Guardian Terra/Gelo) ─────────────────────
    "jarl_vetreidi": JarlStrategy,
    "jarl": JarlStrategy,

    # ── BRUTE ───────────────────────────────────────────────────
    "rhinar_reckless_rampage": BruteStrategy,
    "rhinar": BruteStrategy,
    "kayo_berserker_runt": BruteStrategy,
    "kayo_armed_and_dangerous": BruteStrategy,
    "kayo_underhanded_cheat": BruteStrategy,
    "kayo_strong-arm": BruteStrategy,
    "kayo": BruteStrategy,
    "levia_shadowborn_abomination": BruteStrategy,
    "levia": BruteStrategy,
    "baalghor_omen_of_the_end": BruteStrategy,
    "baalghor": BruteStrategy,
    "brute": BruteStrategy,

    # ── RANGER ──────────────────────────────────────────────────
    "azalea_ace_in_the_hole": RangerStrategy,
    "azalea": RangerStrategy,
    "lexi_livewire": RangerStrategy,
    "lexi": RangerStrategy,
    "riptide_lurker_of_the_deep": RangerStrategy,
    "riptide": RangerStrategy,
    "marlynn_treasure_hunter": MarlynnStrategy,
    "marlynn": MarlynnStrategy,
    "marlinn": MarlynnStrategy,
    "ranger": RangerStrategy,

    # ── NINJA ───────────────────────────────────────────────────
    "katsu_the_wanderer": NinjaStrategy,
    "katsu": NinjaStrategy,
    "ira_crimson_haze": NinjaStrategy,
    "ira_scarlet_revenger": NinjaStrategy,
    "ira": NinjaStrategy,
    "benji_the_piercing_wind": NinjaStrategy,
    "benji": NinjaStrategy,
    "fai_rising_rebellion": NinjaStrategy,
    "fai": NinjaStrategy,
    "zen_tamer_of_purpose": NinjaStrategy,
    "zen": NinjaStrategy,
    "cindra_dracai_of_retribution": NinjaStrategy,
    "cindra": NinjaStrategy,
    "ninja": NinjaStrategy,

    # ── WARRIOR ─────────────────────────────────────────────────
    "dorinthea_ironsong": WarriorStrategy,
    "dorinthea_quicksilver_prodigy": WarriorStrategy,
    "dorinthea": WarriorStrategy,
    "kassai_cintari_sellsword": KassaiStrategy,
    "kassai_of_the_golden_sand": KassaiStrategy,
    "kassai": KassaiStrategy,
    "ser_boltyn_breaker_of_dawn": WarriorStrategy,
    "boltyn": WarriorStrategy,
    "olympia_prized_fighter": WarriorStrategy,
    "olympia": WarriorStrategy,
    "fang_dracai_of_blades": WarriorStrategy,
    "fang": WarriorStrategy,
    "hala_bladesaint_of_the_vow": HalaStrategy,
    "hala": HalaStrategy,
    "killjoy_the_crooked_blade": WarriorStrategy,
    "killjoy": WarriorStrategy,
    "warrior": WarriorStrategy,

    # ── MECHANOLOGIST ───────────────────────────────────────────
    "dash_inventor_extraordinaire": MechanologistStrategy,
    "dash_io": DashIOStrategy,
    "dash_database": DashIOStrategy,
    "dash": MechanologistStrategy,
    "data_doll_mkii": MechanologistStrategy,
    "data_doll": MechanologistStrategy,
    "professor_teklovossen": TeklovossenStrategy,
    "teklovossen_esteemed_magnate": TeklovossenStrategy,
    "teklovossen": TeklovossenStrategy,
    "maxx_the_hype_nitro": MechanologistStrategy,
    "maxx_nitro": MechanologistStrategy,
    "maxx": MechanologistStrategy,
    "puffin_hightail": MechanologistStrategy,
    "puffin": MechanologistStrategy,
    "mechanologist": MechanologistStrategy,

    # ── RUNEBLADE ───────────────────────────────────────────────
    "viserai_rune_blood": RunebladeStrategy,
    "viserai_the_forsaken": RunebladeStrategy,
    "viserai_between_worlds": RunebladeStrategy,
    "viserai": RunebladeStrategy,
    "chane_bound_by_shadow": RunebladeStrategy,
    "chane": RunebladeStrategy,
    "briar_warden_of_thorns": RunebladeStrategy,
    "briar": RunebladeStrategy,
    "vynnset_iron_maiden": VynnsetStrategy,
    "vynnset": VynnsetStrategy,
    "vynsett": VynnsetStrategy,
    "florian_rotwood_harbinger": RunebladeStrategy,
    "florian": RunebladeStrategy,
    "aurora_shooting_star": RunebladeStrategy,
    "aurora_legacy_of_tempest": RunebladeStrategy,
    "aurora_emissary_of_lightning": RunebladeStrategy,
    "aurora": RunebladeStrategy,
    "runeblade": RunebladeStrategy,

    # ── WIZARD ──────────────────────────────────────────────────
    "kano_dracai_of_aether": WizardStrategy,
    "kano": WizardStrategy,
    "iyslander_stormbind": WizardStrategy,
    "iyslander": WizardStrategy,
    "blaze_firemind": WizardStrategy,
    "blaze": WizardStrategy,
    "verdance_thorn_of_the_rose": WizardStrategy,
    "verdance": WizardStrategy,
    "oscilio_constella_intelligence": OscilioStrategy,
    "oscilio_forked_continuum": OscilioStrategy,
    "oscilio_scion_of_the_third_age": OscilioStrategy,
    "oscilio": OscilioStrategy,
    "emperor_dracai_of_aesir": WizardStrategy,
    "emperor": WizardStrategy,
    "wizard": WizardStrategy,

    # ── ILLUSIONIST ─────────────────────────────────────────────
    "prism_sculptor_of_arc_light": IllusionistStrategy,
    "prism_awakener_of_sol": IllusionistStrategy,
    "prism_advent_of_thrones": IllusionistStrategy,
    "prism": IllusionistStrategy,
    "dromai_ash_artist": IllusionistStrategy,
    "dromai": IllusionistStrategy,
    "enigma_ledger_of_ancestry": IllusionistStrategy,
    "enigma_new_moon": IllusionistStrategy,
    "enigma": IllusionistStrategy,
    "pleiades_superstar": IllusionistStrategy,
    "pleiades": IllusionistStrategy,
    "zyggy_starlight": IllusionistStrategy,
    "zyggy": IllusionistStrategy,
    "illusionist": IllusionistStrategy,

    # ── ASSASSIN ────────────────────────────────────────────────
    "arakni_huntsman": AssassinStrategy,
    "arakni_solitary_confinement": AssassinStrategy,
    "arakni_marionette": ArakniMarionetteStrategy,
    "arakni_web_of_deceit": AssassinStrategy,
    "arakni_5lp3d_7hru_7h3_cr4x": AssassinStrategy,
    "arakni": AssassinStrategy,
    "uzuri_switchblade": AssassinStrategy,
    "uzuri": AssassinStrategy,
    "nuu_alluring_desire": AssassinStrategy,
    "nuu": AssassinStrategy,
    "dr_mortimer_blight_of_the_pits": AssassinStrategy,
    "dr_mortimer": AssassinStrategy,
    "mario": ArakniMarionetteStrategy,
    "mario_deck": ArakniMarionetteStrategy,
    "assassin": AssassinStrategy,

    # ── MERCHANT / BARD / MISC ──────────────────────────────────
    "kavdaen_trader_of_skins": MerchantStrategy,
    "kavdaen": MerchantStrategy,
    "genis_wotchuneed": MerchantStrategy,
    "genis": MerchantStrategy,
    "melody_sing-along": MerchantStrategy,
    "melody": MerchantStrategy,
    "shiyana_diamond_gemini": MerchantStrategy,
    "shiyana": MerchantStrategy,
    "gravy_bones_shipwrecked_looter": GravyBonesStrategy,
    "gravy_bones": GravyBonesStrategy,
    "gravy": GravyBonesStrategy,
    "scurv_stowaway": MerchantStrategy,
    "scurv": MerchantStrategy,
    "malice_domina_of_the_dead": MerchantStrategy,
    "malice": MerchantStrategy,
    "zane_broadly_beloved": MerchantStrategy,
    "zane": MerchantStrategy,
}


@lru_cache(maxsize=256)
def get_hero_strategy(hero_name: str) -> HeroStrategy:
    """
    Fábrica canônica de estratégias de herói de Flesh and Blood.
    Hierarquia em 3 etapas:
      Etapa 1: Herói específico (JarlStrategy, MarlynnStrategy, etc.).
      Etapa 2: Estratégia de classe (Guardian, Brute, Ranger, Ninja, Warrior,
               Mechanologist, Runeblade, Wizard, Illusionist, Assassin, Merchant)
               via correspondência de nome, prefixo/raiz ou busca em _get_cards_db().
      Etapa 3: Fallback para HeroStrategy base.
    """
    h = str(hero_name).lower().strip()
    root = h.split('_')[0]

    # ── ETAPA 1: Verificação de herói específico ───────────────────
    if "jarl" in h or "jarl" in root:
        return JarlStrategy(h)
    if "marlynn" in h or "marlinn" in h or "marlynn" in root or "marlinn" in root:
        return MarlynnStrategy(h)
    if "oscilio" in h or "oscilio" in root:
        return OscilioStrategy(h)

    # ── ETAPA 2: Verificação de estratégia por classe ─────────────
    # 2.1 Correspondência direta no registro canônico
    if h in HERO_CLASS_REGISTRY:
        return HERO_CLASS_REGISTRY[h](h)

    # 2.2 Correspondência por raiz do nome
    if root in HERO_CLASS_REGISTRY:
        return HERO_CLASS_REGISTRY[root](h)

    # 2.3 Fallback dinâmico via Card Database
    from ai.policy.constants import _get_cards_db
    cards_db = _get_cards_db()
    for candidate in (h, f"{h}_young", f"{h}_adult", root):
        cdata = cards_db.get(candidate, {})
        c_class = str(cdata.get("class", "")).upper()
        subtype = str(cdata.get("subtype", "")).upper()

        if "JARL" in candidate.upper():
            return JarlStrategy(h)
        elif "MARLYNN" in candidate.upper() or "MARLINN" in candidate.upper():
            return MarlynnStrategy(h)
        elif "GUARDIAN" in c_class or "GUARDIAN" in subtype:
            return GuardianStrategy(h)
        elif "BRUTE" in c_class or "BRUTE" in subtype:
            return BruteStrategy(h)
        elif "RANGER" in c_class or "RANGER" in subtype:
            return RangerStrategy(h)
        elif "NINJA" in c_class or "NINJA" in subtype:
            return NinjaStrategy(h)
        elif "WARRIOR" in c_class or "WARRIOR" in subtype:
            return WarriorStrategy(h)
        elif "MECHANOLOGIST" in c_class or "MECHANOLOGIST" in subtype:
            return MechanologistStrategy(h)
        elif "RUNEBLADE" in c_class or "RUNEBLADE" in subtype:
            return RunebladeStrategy(h)
        elif "WIZARD" in c_class or "WIZARD" in subtype:
            return WizardStrategy(h)
        elif "ILLUSIONIST" in c_class or "ILLUSIONIST" in subtype:
            return IllusionistStrategy(h)
        elif "ASSASSIN" in c_class or "ASSASSIN" in subtype:
            return AssassinStrategy(h)
        elif "MERCHANT" in c_class or "BARD" in c_class or "PIRATE" in c_class:
            return MerchantStrategy(h)

    # ── ETAPA 3: Fallback genérico ────────────────────────────────
    return HeroStrategy(h)
