from .slugifier import load_fab_cards_db

def validate_deck_against_db(deck_obj: dict) -> tuple[bool, list[str], dict]:
    """Valida minuciosamente um deck contra a base de cartas suportadas pelo Talishar.
    
    Verifica:
    - Existência e suporte de todas as cartas no DB do Talishar;
    - Validação estrita do Herói (presença única, jovem para Blitz, adulto para CC);
    - Formato (Classic Constructed min 60 cartas no deck, Blitz min 40 cartas);
    - Limites de cópias de cartas (máx 3 em CC, máx 2 em Blitz, máx 1 para Herói);
    - Slots de equipamentos (Head, Chest, Arms, Legs, Weapon 1H/2H, Off-Hand, Equipment).
    """
    db = load_fab_cards_db()
    cards = deck_obj.get("cards", [])
    fmt = deck_obj.get("format", "cc").lower()
    
    errors = []
    missing_cards = []
    heroes = []
    slots = {
        "Hero": [],
        "Head": [],
        "Chest": [],
        "Arms": [],
        "Legs": [],
        "Weapon": [],
        "Off-Hand": [],
        "Equipment": [],
        "Deck": []
    }
    
    total_deck_cards = 0
    card_totals = {}
    
    # 1. Agregação e categorização de slots
    for c in cards:
        cid = c.get("identifier", "") if isinstance(c, dict) else str(c)
        tot = int(c.get("count", c.get("total", 1))) if isinstance(c, dict) else 1
        
        if not cid:
            continue
            
        card_totals[cid] = card_totals.get(cid, 0) + tot
        
        if cid not in db:
            missing_cards.append(cid)
        else:
            meta = db[cid]
            slot = meta.get("slot", "Deck")
            if slot == "Hero" or meta.get("type") == "C":
                heroes.append(cid)
                slots["Hero"].append(cid)
            elif slot in ("Head", "Chest", "Arms", "Legs", "Weapon", "Off-Hand", "Equipment"):
                slots[slot].append((cid, tot))
            else:
                slots["Deck"].append((cid, tot))
                total_deck_cards += tot
                
    # 2. Cartas não suportadas
    if missing_cards:
        errors.append(f"Cartas não suportadas pelo Talishar: {', '.join(sorted(set(missing_cards)))}")
        
    # 3. Validação estrita de Herói
    if not heroes:
        errors.append("Nenhum Herói reconhecido no deck. Certifique-se de incluir a linha do Herói (ex: 'Hero: Betsy').")
    elif len(set(heroes)) > 1:
        errors.append(f"Múltiplos heróis diferentes detectados no deck: {', '.join(sorted(set(heroes)))}.")
    else:
        hero_id = heroes[0]
        hero_meta = db.get(hero_id, {})
        hero_count = card_totals.get(hero_id, 1)
        if hero_count > 1:
            errors.append(f"Herói '{hero_id}' possui mais de 1 cópia ({hero_count}).")
            
        subtype_low = str(hero_meta.get("subtype", "")).lower()
        is_young_hero = "young" in subtype_low
        
        if fmt in ("cc", "compcc") and is_young_hero:
            errors.append(f"Herói Jovem ('{hero_meta.get('name', hero_id)}') não é permitido no formato Classic Constructed (CC). Utilize a versão Adulta.")
        elif fmt == "blitz" and not is_young_hero and hero_meta:
            errors.append(f"Herói Adulto ('{hero_meta.get('name', hero_id)}') não é permitido no formato BLITZ. Utilize a versão Jovem (Young).")
            
    # 4. Limites de cópias de cartas por formato
    max_copies = 2 if fmt == "blitz" else 3
    for cid, tot in card_totals.items():
        if cid in heroes:
            continue
        meta = db.get(cid, {})
        slot = meta.get("slot", "Deck")
        # Base Evos (subtype 'Base' ou slot 'Equipment' com Base) podem ter múltiplas cópias
        subtype = meta.get("subtype", "")
        if tot > max_copies:
            errors.append(f"Carta '{cid}' excede o limite de {max_copies} cópias para o formato {fmt.upper()} ({tot} cópias).")

    # 5. Tamanho mínimo do deck principal
    min_deck = 60 if fmt in ("cc", "compcc") else 40
    if total_deck_cards < min_deck:
        errors.append(f"Quantidade de cartas de Deck principal ({total_deck_cards}) abaixo do mínimo exigido para o formato {fmt.upper()} ({min_deck} cartas).")

    # 6. Validação de slots de equipamentos e armas
    total_equipment_pieces = (
        len(slots["Head"]) + len(slots["Chest"]) + len(slots["Arms"]) +
        len(slots["Legs"]) + len(slots["Equipment"])
    )
    total_weapons = len(slots["Weapon"]) + len(slots["Off-Hand"])
    
    if total_equipment_pieces == 0 and total_weapons == 0 and not missing_cards:
        errors.append("Deck não possui nenhum equipamento ou arma cadastrada.")
        
    is_valid = len(errors) == 0
    return is_valid, errors, {
        "heroes": heroes,
        "slots": slots,
        "total_deck_cards": total_deck_cards,
        "missing_cards": list(set(missing_cards))
    }
