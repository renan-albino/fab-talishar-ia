import re
import json
import os
import unicodedata

BASE_DIR = "/home/renan/fab-talishar-ia"
DB_PATH = os.path.join(BASE_DIR, "data", "fab_cards_db.json")

_CARD_DB_CACHE = None

def load_fab_cards_db() -> dict:
    global _CARD_DB_CACHE
    if _CARD_DB_CACHE is not None:
        return _CARD_DB_CACHE
    for p in [DB_PATH, "data/fab_cards_db.json", "/home/renan/fab-talishar-ia/data/fab_cards_db.json"]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    _CARD_DB_CACHE = json.load(f)
                    return _CARD_DB_CACHE
            except Exception:
                pass
    _CARD_DB_CACHE = {}
    return _CARD_DB_CACHE

def validate_deck_against_db(deck_obj: dict) -> tuple[bool, list[str], dict]:
    """Valida minuciosamente um deck contra a base de cartas suportadas pelo Talishar."""
    db = load_fab_cards_db()
    cards = deck_obj.get("cards", [])
    fmt = deck_obj.get("format", "cc").lower()
    
    errors = []
    missing_cards = []
    heroes = []
    slots = {"Hero": [], "Head": [], "Chest": [], "Arms": [], "Legs": [], "Weapon": [], "Off-Hand": [], "Equipment": [], "Deck": []}
    
    total_deck_cards = 0
    
    for c in cards:
        cid = c.get("identifier", "") if isinstance(c, dict) else str(c)
        tot = int(c.get("count", c.get("total", 1))) if isinstance(c, dict) else 1
        
        if not cid:
            continue
            
        if cid not in db:
            missing_cards.append(cid)
        else:
            meta = db[cid]
            slot = meta.get("slot", "Deck")
            if slot == "Hero":
                heroes.append(cid)
                slots["Hero"].append(cid)
            elif slot in ("Head", "Chest", "Arms", "Legs", "Weapon", "Off-Hand", "Equipment"):
                slots[slot].append((cid, tot))
            else:
                slots["Deck"].append((cid, tot))
                total_deck_cards += tot
                
    if missing_cards:
        errors.append(f"Cartas não suportadas pelo Talishar: {', '.join(sorted(set(missing_cards)))}")
        
    if not heroes:
        errors.append("Nenhum Herói reconhecido no deck. Certifique-se de incluir a linha do Herói (ex: 'Hero: Betsy').")
        
    min_deck = 60 if fmt in ("cc", "compcc") else 40
    if total_deck_cards < min_deck:
        errors.append(f"Quantidade de cartas de Deck principal ({total_deck_cards}) abaixo do mínimo exigido para o formato {fmt.upper()} ({min_deck} cartas).")
        
    is_valid = len(errors) == 0
    return is_valid, errors, {
        "heroes": heroes,
        "slots": slots,
        "total_deck_cards": total_deck_cards,
        "missing_cards": list(set(missing_cards))
    }

def load_card_dictionary():
    return load_fab_cards_db()

# Hero name overrides
HERO_MAP = {
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

def slugify_card_name(name: str, is_hero: bool = False) -> str:
    name = name.strip()
    
    # 1. Substituir caracteres nórdicos / especiais antes da normalização ASCII
    replacements = {
        "ð": "d", "Ð": "D",
        "þ": "th", "Þ": "TH",
        "æ": "ae", "Æ": "AE",
        "ø": "o", "Ø": "O",
        "œ": "oe", "Œ": "OE"
    }
    for char, rep in replacements.items():
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
    
    # Common aliases & typo fixes
    aliases = {
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
    
    if card_id in aliases:
        card_id = aliases[card_id]
        
    return card_id

def parse_deck_text(deck_text: str, default_name: str = "Meu Deck") -> dict:
    cards = []
    lines = deck_text.strip().splitlines()
    format_type = None
    extracted_name = None
    hero_id = None
    
    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            continue
            
        # Metadata checks
        if line.lower().startswith("name:"):
            extracted_name = line.split(":", 1)[1].strip()
            # Strip emojis for file saving
            extracted_name = re.sub(r"[^\w\s-]", "", extracted_name).strip()
            continue
        if line.lower().startswith("format:"):
            fmt_str = line.split(":", 1)[1].strip().lower()
            if "classic" in fmt_str or "cc" in fmt_str:
                format_type = "cc"
            elif "blitz" in fmt_str:
                format_type = "blitz"
            continue
        if line.lower().startswith("hero:"):
            h_str = line.split(":", 1)[1].strip()
            hero_id = slugify_card_name(h_str, is_hero=True)
            continue
            
        # Skip section headers and footer lines
        if re.match(r"^(hero|weapons?|equipment|arena cards|deck cards|pitch\s*\d|deck|sideboard|inventory|other|cards|format):?", line, re.IGNORECASE):
            continue
        if line.startswith("#") or line.startswith("//") or "fabrary" in line.lower() or "see the full deck" in line.lower():
            continue
            
        qty = 1
        card_name = line
        
        m_prefix = re.match(r"^(\d+)\s*x?\s*(.+)$", line, re.IGNORECASE)
        m_suffix = re.match(r"^(.+?)\s*[xX]\s*(\d+)$", line)
        if m_prefix:
            qty = int(m_prefix.group(1))
            card_name = m_prefix.group(2)
        elif m_suffix:
            card_name = m_suffix.group(1)
            qty = int(m_suffix.group(2))
            
        card_id = slugify_card_name(card_name)
        if card_id:
            cards.append({"identifier": card_id, "total": qty})
            
    # If a hero was defined and not in cards, prepend it
    if hero_id:
        has_hero = any(c["identifier"] == hero_id for c in cards)
        if not has_hero:
            cards.insert(0, {"identifier": hero_id, "total": 1})
            
    total_count = sum(c["total"] for c in cards)
    if not format_type:
        format_type = "cc" if total_count >= 60 else "blitz"
        
    final_name = extracted_name if extracted_name else default_name
    
    return {
        "name": final_name,
        "format": format_type,
        "cards": cards
    }

def save_deck_to_workspace(deck_obj: dict, base_dir: str = "/home/renan/fab-talishar-ia") -> dict:
    deck_name = deck_obj.get("name", "Custom_Deck")
    safe_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", deck_name).strip("_").lower()
    if not safe_slug:
        safe_slug = "custom_deck"
        
    deck_str = json.dumps(deck_obj, indent=2)
    saved_files = []
    
    # Save to decks/ directory
    for root in [base_dir, ".", "/home/renan/fab-talishar-ia"]:
        for folder in [os.path.join(root, "Talishar", "decks"), os.path.join(root, "decks")]:
            try:
                os.makedirs(folder, exist_ok=True)
                file_path = os.path.join(folder, f"{safe_slug}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(deck_str)
                saved_files.append(file_path)
            except Exception:
                pass
        
    # Also set as current active deck
    for root in [base_dir, "."]:
        for main_file in [os.path.join(root, "Talishar", "deck.json"), os.path.join(root, "deck.json")]:
            try:
                with open(main_file, "w", encoding="utf-8") as f:
                    f.write(deck_str)
                saved_files.append(main_file)
            except Exception:
                pass
        
    return {
        "slug": safe_slug,
        "saved_files": saved_files,
        "deck": deck_obj
    }

def update_saved_deck(slug: str, new_name: str, new_format: str, cards_list: list, base_dir: str = "/home/renan/fab-talishar-ia") -> dict:
    """Atualiza as propriedades e cartas de um deck salvo existente."""
    deck_obj = {
        "name": new_name,
        "format": new_format.lower(),
        "cards": cards_list
    }
    new_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", new_name).strip("_").lower()
    if new_slug and new_slug != slug:
        delete_saved_deck(slug, base_dir=base_dir)
    return save_deck_to_workspace(deck_obj, base_dir=base_dir)

def list_saved_decks(base_dir: str = "/home/renan/fab-talishar-ia") -> list:
    decks_dir = os.path.join(base_dir, "decks")
    if not os.path.exists(decks_dir):
        decks_dir = "decks"
    os.makedirs(decks_dir, exist_ok=True)
    deck_files = [f for f in os.listdir(decks_dir) if f.endswith(".json")]
    decks = []
    for df in sorted(deck_files):
        path = os.path.join(decks_dir, df)
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
                decks.append({
                    "filename": df,
                    "slug": df[:-5],
                    "name": d.get("name", df[:-5]),
                    "format": d.get("format", "blitz"),
                    "total_cards": sum(c.get("total", 1) for c in d.get("cards", [])),
                    "data": d
                })
        except Exception:
            pass
    return decks

def delete_saved_deck(slug: str, base_dir: str = "/home/renan/fab-talishar-ia") -> bool:
    """Remove o arquivo JSON do deck do diretório decks/."""
    for root in [base_dir, ".", "/home/renan/fab-talishar-ia"]:
        deck_path = os.path.join(root, "decks", f"{slug}.json")
        if os.path.exists(deck_path):
            try:
                os.remove(deck_path)
                return True
            except Exception as e:
                print(f"Erro ao remover {deck_path}: {e}")
    return False

def set_active_deck(deck_data: dict, base_dir: str = "/home/renan/fab-talishar-ia"):
    deck_str = json.dumps(deck_data, indent=2)
    for root in [base_dir, "."]:
        for main_file in [os.path.join(root, "Talishar", "deck.json"), os.path.join(root, "deck.json")]:
            try:
                with open(main_file, "w", encoding="utf-8") as f:
                    f.write(deck_str)
            except Exception:
                pass

def load_current_deck(base_dir: str = "/home/renan/fab-talishar-ia") -> dict:
    for root in [base_dir, "."]:
        for main_file in [os.path.join(root, "Talishar", "deck.json"), os.path.join(root, "deck.json")]:
            if os.path.exists(main_file):
                try:
                    with open(main_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
    return {}
