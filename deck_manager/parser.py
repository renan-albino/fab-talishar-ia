import re
from .slugifier import slugify_card_name, load_fab_cards_db

def enrich_deck_metadata(deck_obj: dict, db: dict = None) -> dict:
    """Extrai e preenche metadados canônicos de herói, classe, talentos e formato no deck."""
    if db is None:
        db = load_fab_cards_db()
        
    cards = deck_obj.get("cards", [])
    hero_id = deck_obj.get("hero", "")
    hero_name = deck_obj.get("hero_name", "")
    hero_class = deck_obj.get("class", "")
    talents = deck_obj.get("talents", [])
    is_young = bool(deck_obj.get("is_young", False))
    
    # 1. Localizar a carta do Herói nos cards se não estiver identificada
    hero_meta = None
    if hero_id and hero_id in db:
        hero_meta = db[hero_id]
    else:
        for c in cards:
            cid = c.get("identifier", "") if isinstance(c, dict) else str(c)
            meta = db.get(cid, {})
            if meta.get("slot") == "Hero" or meta.get("type") == "C":
                hero_id = cid
                hero_meta = meta
                break

    if hero_meta:
        if not hero_name:
            hero_name = hero_meta.get("name", hero_id.replace("_", " ").title())
        if not hero_class:
            hero_class = hero_meta.get("class", "GENERIC")
        is_young = "young" in str(hero_meta.get("subtype", "")).lower()
        
        # Detectar talentos conhecidos de Flesh and Blood
        h_low = f"{hero_id} {hero_name} {hero_class}".lower()
        detected_talents = []
        for t_candidate in ["SHADOW", "LIGHT", "DRACONIC", "ELEMENTAL", "EARTH", "ICE", "LIGHTNING", "CHAOS", "MYSTIC", "PIRATE", "NECROMANCER"]:
            if t_candidate.lower() in h_low:
                detected_talents.append(t_candidate)
        if not talents:
            talents = detected_talents
    else:
        if not hero_name:
            hero_name = deck_obj.get("name", "Unknown Hero")
        if not hero_class:
            hero_class = "GENERIC"

    deck_obj["hero"] = hero_id or deck_obj.get("name", "").lower().replace(" ", "_")
    deck_obj["hero_name"] = hero_name
    deck_obj["class"] = hero_class
    deck_obj["talents"] = talents
    deck_obj["is_young"] = is_young
    if "format" not in deck_obj:
        deck_obj["format"] = "cc"
        
    return deck_obj

def extract_hero_from_deck(d: dict | list, db: dict = None) -> str:
    """Extrai o nome canônico do Herói de um deck FAB ou de uma lista de cartas."""
    if db is None:
        db = load_fab_cards_db()
        
    if isinstance(d, list):
        deck_dict = {"cards": d}
    elif isinstance(d, dict):
        deck_dict = d
    else:
        return "Herói"
        
    if deck_dict.get("hero_name"):
        return str(deck_dict["hero_name"])
    if deck_dict.get("hero"):
        return str(deck_dict["hero"]).replace("_", " ").title()
        
    cards = deck_dict.get("cards", [])
    if db:
        for c in cards:
            cid = c.get("identifier", "") if isinstance(c, dict) else str(c)
            c_info = db.get(cid, {})
            if c_info.get("slot") == "Hero" or c_info.get("type") == "C":
                return c_info.get("name", cid.replace("_", " ").title())
                
    if cards:
        first_c = cards[0]
        first_id = first_c.get("identifier", "") if isinstance(first_c, dict) else str(first_c)
        for prefix in ["betsy", "cindra", "dash", "gravy", "hala", "jarl", "kassai", "mario", "oscilio", "vynnset", "dorinthea", "katsu", "rhinar", "bravo", "fai", "briar", "zen", "nuu", "enigma", "aurora", "florian", "verdance", "arakni", "chane", "prism", "lexi", "oldhim", "dromai", "islander"]:
            if prefix in first_id.lower():
                return first_id.replace("_", " ").title()
                
    return deck_dict.get("name", "Herói")

def parse_deck_text(deck_text: str, default_name: str = "Meu Deck") -> dict:
    """Faz o parse do formato de texto bruto exportado pelo FaBrary ou gerado pelo usuário."""
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
        if re.match(r"^(hero|weapons?|equipment|arena cards|deck cards|pitch\s*\d|deck|sideboard|inventory|other|cards|format)\s*(:|(\(\d+\)))?\s*$", line, re.IGNORECASE):
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
    
    deck_dict = {
        "name": final_name,
        "format": format_type,
        "cards": cards
    }
    return enrich_deck_metadata(deck_dict)
