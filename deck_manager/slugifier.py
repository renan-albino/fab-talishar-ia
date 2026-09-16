import re
import json
import os
import unicodedata

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "data", "fab_cards_db.json")
_DATA_DIR = os.path.join(BASE_DIR, "data")

_CARD_DB_CACHE = None

CARD_NAME_CORRECTIONS = {
    "ð": "d", "Ð": "D",
    "þ": "th", "Þ": "TH",
    "æ": "ae", "Æ": "AE",
    "ø": "o", "Ø": "O",
    "œ": "oe", "Œ": "OE"
}

CARD_SLUG_ALIASES = {
    "pounding_shuko_red": "pounding_gale_red",
    "pounding_shuko": "pounding_gale_red",
    "autumn_touch_red": "autumns_touch_red",
    "autumn_touch_yellow": "autumns_touch_yellow",
    "autumn_touch_blue": "autumns_touch_blue",
    "goldfin_harpoon": "goldfin_harpoon_yellow",
    "convection_amplifier_red": "convection_amplifier_red",
    "backup_protocol_red_red": "backup_protocol_red_red",
    "backup_protocol_yel_yellow": "backup_protocol_yel_yellow",
    "backup_protocol_blu_blue": "backup_protocol_blu_blue",
}

DEFAULT_HERO_MAP = {
    "arakni_marionette": "arakni_marionette",
    "arakni_solitary_confinement": "arakni_solitary_confinement",
    "arakni_5lp3d_7hru_7h3_cr4x": "arakni_5lp3d_7hru_7h3_cr4x",
    "arakni_huntsman": "arakni_huntsman",
    "arakni": "arakni_huntsman",
    "jarl_vetreidi": "jarl_vetreidi",
    "jarl": "jarl_vetreidi",
    "florian_rotwood_harbinger": "florian_rotwood_harbinger",
    "florian": "florian_rotwood_harbinger",
    "aurora_shooting_star": "aurora_shooting_star",
    "aurora": "aurora_shooting_star",
    "verdance_thorn_of_the_rose": "verdance_thorn_of_the_rose",
    "verdance": "verdance_thorn_of_the_rose",
    "oscilio_constellation_seeker": "oscilio_constellation_seeker",
    "oscilio": "oscilio_constellation_seeker",
    "nuu_alluring_desire": "nuu_alluring_desire",
    "nuu": "nuu_alluring_desire",
    "zen_tamer_of_purpose": "zen_tamer_of_purpose",
    "zen": "zen_tamer_of_purpose",
    "enigma_ledger_of_ancestry": "enigma_ledger_of_ancestry",
    "enigma_new_moon": "enigma_new_moon",
    "enigma": "enigma_ledger_of_ancestry",
    "victor_goldmane_high_and_mighty": "victor_goldmane_high_and_mighty",
    "victor_goldmane": "victor_goldmane_high_and_mighty",
    "victor": "victor_goldmane_high_and_mighty",
    "betsy_skin_in_the_game": "betsy_skin_in_the_game",
    "betsy": "betsy_skin_in_the_game",
    "kassai_of_the_golden_sand": "kassai_of_the_golden_sand",
    "kassai_cintari_sellsword": "kassai_cintari_sellsword",
    "kassai": "kassai_of_the_golden_sand",
    "kayo_armed_and_dangerous": "kayo_armed_and_dangerous",
    "kayo_berserker_runt": "kayo_berserker_runt",
    "kayo": "kayo_armed_and_dangerous",
    "olympia_prized_fighter": "olympia_prized_fighter",
    "olympia": "olympia_prized_fighter",
    "dash_io": "dash_io",
    "dash_database": "dash_database",
    "dash_inventor_extraordinaire": "dash_inventor_extraordinaire",
    "dash": "dash_inventor_extraordinaire",
    "gravy_bones_shipwrecked_looter": "gravy_bones_shipwrecked_looter",
    "gravy_bones": "gravy_bones_shipwrecked_looter",
    "hala_bladesaint_of_the_vow": "hala_bladesaint_of_the_vow",
    "hala": "hala_bladesaint_of_the_vow",
    "vynnset_iron_maiden": "vynnset_iron_maiden",
    "vynnset": "vynnset_iron_maiden",
    "vynsett": "vynnset_iron_maiden",
    "cindra": "cindra",
    "bravo_showstopper": "bravo_showstopper",
    "bravo": "bravo_showstopper",
    "dorinthea_ironsong": "dorinthea_ironsong",
    "dorinthea": "dorinthea_ironsong",
    "rhinar_reckless_rampage": "rhinar_reckless_rampage",
    "rhinar": "rhinar_reckless_rampage",
    "katsu_the_wanderer": "katsu_the_wanderer",
    "katsu": "katsu_the_wanderer",
    "kano_dracai_of_aether": "kano_dracai_of_aether",
    "kano": "kano_dracai_of_aether",
    "azalea_ace_in_the_hole": "azalea_ace_in_the_hole",
    "azalea": "azalea_ace_in_the_hole",
    "viserai_rune_blood": "viserai_rune_blood",
    "viserai": "viserai_rune_blood",
    "chane_bound_by_shadow": "chane_bound_by_shadow",
    "chane": "chane_bound_by_shadow",
    "prism_sculptor_of_arc_light": "prism_sculptor_of_arc_light",
    "prism": "prism_sculptor_of_arc_light",
    "levia_shadowborn_abomination": "levia_shadowborn_abomination",
    "levia": "levia_shadowborn_abomination",
    "ser_boltyn_breaker_of_dawn": "ser_boltyn_breaker_of_dawn",
    "boltyn": "ser_boltyn_breaker_of_dawn",
    "oldhim_grandfather_of_eternity": "oldhim_grandfather_of_eternity",
    "oldhim": "oldhim_grandfather_of_eternity",
    "briar_warden_of_thorns": "briar_warden_of_thorns",
    "briar": "briar_warden_of_thorns",
    "lexi_livewire": "lexi_livewire",
    "lexi": "lexi_livewire",
    "dromai_ash_artist": "dromai_ash_artist",
    "dromai": "dromai_ash_artist",
    "fai_rising_rebellion": "fai_rising_rebellion",
    "fai": "fai_rising_rebellion",
    "iyslander_stormbind": "iyslander_stormbind",
    "iyslander": "iyslander_stormbind",
    "uzuri_switchblade": "uzuri_switchblade",
    "uzuri": "uzuri_switchblade",
    "riptide_lurker_of_the_deep": "riptide_lurker_of_the_deep",
    "riptide": "riptide_lurker_of_the_deep",
}

def load_fab_cards_db() -> dict:
    """Carrega o banco de cartas oficial do FAB a partir do JSON data/fab_cards_db.json."""
    global _CARD_DB_CACHE
    if _CARD_DB_CACHE is not None:
        return _CARD_DB_CACHE
    for p in [DB_PATH, os.path.join(BASE_DIR, "data", "fab_cards_db.json"), "data/fab_cards_db.json"]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    _CARD_DB_CACHE = json.load(f)
                    return _CARD_DB_CACHE
            except Exception:
                pass
    _CARD_DB_CACHE = {}
    return _CARD_DB_CACHE

def load_card_dictionary() -> dict:
    """Alias retrocompatível para load_fab_cards_db."""
    return load_fab_cards_db()

def _load_hero_map() -> dict:
    """Carrega o mapeamento de heróis do arquivo JSON ou gera fallback a partir do banco de cartas."""
    path = os.path.join(_DATA_DIR, "hero_map.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data:
                    return data
        except Exception:
            pass

    hero_map = dict(DEFAULT_HERO_MAP)
    try:
        db = load_fab_cards_db()
        for card_id, meta in db.items():
            if meta.get("slot") == "Hero":
                if card_id not in hero_map:
                    hero_map[card_id] = card_id
                first = card_id.split("_")[0]
                if first not in hero_map:
                    hero_map[first] = card_id
    except Exception:
        pass
    return hero_map

HERO_MAP = _load_hero_map()

def slugify_card_name(name: str, is_hero: bool = False) -> str:
    """Normaliza o nome bruto de uma carta ou herói para o slug canônico do Talishar."""
    name = name.strip()

    # 1. Substituir caracteres nórdicos / especiais antes da normalização ASCII
    for char, rep in CARD_NAME_CORRECTIONS.items():
        name = name.replace(char, rep)

    # Normalização de acentos (é -> e, á -> a, etc.)
    name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('utf-8')

    # Split / Dual-faced cards (ex: Everbloom // Life -> everbloom__life)
    if "//" in name:
        name = name.replace("//", "__")
    elif " / " in name:
        name = name.replace(" / ", "__")

    # Check pitch in parentheses or numbers
    name = re.sub(r"\s*\(\s*(?:1|red)\s*\)$", " (red)", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(\s*(?:2|yellow)\s*\)$", " (yellow)", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(\s*(?:3|blue)\s*\)$", " (blue)", name, flags=re.IGNORECASE)

    pitch = ""
    if re.search(r"\s*\(red\)$", name, flags=re.IGNORECASE):
        pitch = "_red"
        name = re.sub(r"\s*\(red\)$", "", name, flags=re.IGNORECASE)
    elif re.search(r"\s*\(yellow\)$", name, flags=re.IGNORECASE):
        pitch = "_yellow"
        name = re.sub(r"\s*\(yellow\)$", "", name, flags=re.IGNORECASE)
    elif re.search(r"\s*\(blue\)$", name, flags=re.IGNORECASE):
        pitch = "_blue"
        name = re.sub(r"\s*\(blue\)$", "", name, flags=re.IGNORECASE)

    clean_name = name.replace("'", "").replace(",", "").replace("-", " ").replace(":", " ")

    # Preservar marcador duplo __ para split cards
    tokens = clean_name.split("__")
    clean_tokens = []
    for t in tokens:
        sub_slug = re.sub(r"[^a-zA-Z0-9]+", "_", t).strip("_").lower()
        if sub_slug:
            clean_tokens.append(sub_slug)

    slug = "__".join(clean_tokens)

    if is_hero:
        if slug in HERO_MAP:
            return HERO_MAP[slug]
        for k, v in HERO_MAP.items():
            if k in slug or slug in k:
                return v
        return slug

    card_id = slug + pitch

    if card_id in CARD_SLUG_ALIASES:
        card_id = CARD_SLUG_ALIASES[card_id]

    return card_id
