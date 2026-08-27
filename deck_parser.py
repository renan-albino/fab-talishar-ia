import re
import json
import os

# Build dictionary map from Talishar if available
TALISHAR_DIR = "/home/renan/Documentos/talishar_workspace/Talishar"
GEN_DICT_PATH = os.path.join(TALISHAR_DIR, "GeneratedCode", "GeneratedCardDictionaries.php")

_CARD_DICT_CACHE = {}

def load_card_dictionary():
    global _CARD_DICT_CACHE
    if _CARD_DICT_CACHE:
        return _CARD_DICT_CACHE
    
    mapping = {}
    if os.path.exists(GEN_DICT_PATH):
        try:
            with open(GEN_DICT_PATH, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            matches = re.findall(r'"([a-zA-Z0-9_]+)"\s*=>\s*"([^"]+)"', content)
            for cid, name in matches:
                # Store by clean name
                clean = re.sub(r"[^a-zA-Z0-9]+", "", name).lower()
                mapping[clean] = cid
                # Also store by ID
                mapping[cid] = cid
        except Exception as e:
            print(f"Aviso ao carregar dicionario: {e}")
            
    _CARD_DICT_CACHE = mapping
    return mapping

# Hero name overrides
HERO_MAP = {
    "dash_io": "dash_io",
    "dash_i_o": "dash_io",
    "dash_database": "dash_database",
    "dash_inventor_extraordinaire": "dash_inventor_extraordinaire",
    "dash": "dash",
    "ira_crimson_haze": "ira_crimson_haze",
    "ira": "ira_crimson_haze",
    "dorinthea_ironsong": "dorinthea_ironsong",
    "dorinthea": "dorinthea_ironsong",
    "bravo_showstopper": "bravo_showstopper",
    "bravo": "bravo_showstopper",
    "katsu_the_wanderer": "katsu_the_wanderer",
    "katsu": "katsu_the_wanderer",
    "rhinar_reckless_rampage": "rhinar_reckless_rampage",
    "rhinar": "rhinar_reckless_rampage",
    "kano_dracai_of_aether": "kano_dracai_of_aether",
    "kano": "kano_dracai_of_aether",
    "viserai_rune_blood": "viserai_rune_blood",
    "viserai": "viserai_rune_blood",
    "azalea_ace_in_the_hole": "azalea_ace_in_the_hole",
    "azalea": "azalea_ace_in_the_hole",
    "chane_bound_by_shadow": "chane_bound_by_shadow",
    "chane": "chane_bound_by_shadow",
    "prism_sculptor_of_arc_light": "prism_sculptor_of_arc_light",
    "prism": "prism_sculptor_of_arc_light",
    "boltyn": "ser_boltyn_breaker_of_dawn",
    "ser_boltyn": "ser_boltyn_breaker_of_dawn",
    "levia_shadowborn_abomination": "levia_shadowborn_abomination",
    "levia": "levia_shadowborn_abomination",
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
    "arakni_huntsman": "arakni_huntsman",
    "arakni": "arakni_huntsman",
    "riptide_lurker_of_the_deep": "riptide_lurker_of_the_deep",
    "riptide": "riptide_lurker_of_the_deep",
    "kassai_of_the_golden_sand": "kassai_of_the_golden_sand",
    "kassai": "kassai_of_the_golden_sand",
    "victor_goldmane": "victor_goldmane",
    "betsy_skin_in_the_game": "betsy_skin_in_the_game",
    "kayo_armed_and_dangerous": "kayo_armed_and_dangerous",
    "olympia_prized_fighter": "olympia_prized_fighter",
    "zen_tamer_of_purpose": "zen_tamer_of_purpose",
    "nuu_alluring_desire": "nuu_alluring_desire",
    "enigma_ledger_of_ancestry": "enigma_ledger_of_ancestry",
    "aurora_shooting_star": "aurora_shooting_star",
    "florian_rotwood_harbinger": "florian_rotwood_harbinger",
    "verdance_thorn_of_the_rose": "verdance_thorn_of_the_rose",
    "oscilio_constellation_seeker": "oscilio_constellation_seeker"
}

def slugify_card_name(name: str, is_hero: bool = False) -> str:
    name = name.strip()
    
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
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", clean_name).strip("_").lower()
    
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
        # Check if hero is already in cards list
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

def save_deck_to_workspace(deck_obj: dict, base_dir: str = "/home/renan/Documentos/talishar_workspace") -> dict:
    deck_name = deck_obj.get("name", "Custom_Deck")
    safe_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", deck_name).strip("_").lower()
    if not safe_slug:
        safe_slug = "custom_deck"
        
    deck_str = json.dumps(deck_obj, indent=2)
    saved_files = []
    
    # Save to decks/ directory
    for folder in [os.path.join(base_dir, "Talishar", "decks"), os.path.join(base_dir, "decks")]:
        os.makedirs(folder, exist_ok=True)
        file_path = os.path.join(folder, f"{safe_slug}.json")
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(deck_str)
        saved_files.append(file_path)
        
    # Also set as current active deck
    for main_file in [os.path.join(base_dir, "Talishar", "deck.json"), os.path.join(base_dir, "deck.json")]:
        with open(main_file, "w", encoding="utf-8") as f:
            f.write(deck_str)
        saved_files.append(main_file)
        
    return {
        "slug": safe_slug,
        "saved_files": saved_files,
        "deck": deck_obj
    }

def list_saved_decks(base_dir: str = "/home/renan/Documentos/talishar_workspace") -> list:
    decks_dir = os.path.join(base_dir, "decks")
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

def set_active_deck(deck_data: dict, base_dir: str = "/home/renan/Documentos/talishar_workspace"):
    deck_str = json.dumps(deck_data, indent=2)
    for main_file in [os.path.join(base_dir, "Talishar", "deck.json"), os.path.join(base_dir, "deck.json")]:
        with open(main_file, "w", encoding="utf-8") as f:
            f.write(deck_str)

def load_current_deck(base_dir: str = "/home/renan/Documentos/talishar_workspace") -> dict:
    deck_path = os.path.join(base_dir, "Talishar", "deck.json")
    if not os.path.exists(deck_path):
        deck_path = os.path.join(base_dir, "deck.json")
    if os.path.exists(deck_path):
        try:
            with open(deck_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}
