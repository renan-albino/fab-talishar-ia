import re

with open('ai/sideboard_manager.py', 'r', encoding='utf-8') as f:
    content = f.read()

# I will replace the equipment slot assignment block.
old_loop = r'''        if slot == "Hero":
            if not hero:
                hero = cid
        elif slot == "Head":
            if not head:
                head = cid
            else:
                inv.append(cid)
        elif slot == "Chest":
            if not chest:
                chest = cid
            else:
                inv.append(cid)
        elif slot == "Arms":
            if not arms:
                arms = cid
            else:
                inv.append(cid)
        elif slot == "Legs":
            if not legs:
                legs = cid
            else:
                inv.append(cid)'''
                
new_loop = r'''        if slot == "Hero":
            if not hero:
                hero = cid
        elif slot == "Head":
            base_head_cands.append(cid)
        elif slot == "Chest":
            base_chest_cands.append(cid)
        elif slot == "Arms":
            base_arms_cands.append(cid)
        elif slot == "Legs":
            base_legs_cands.append(cid)'''
            
content = content.replace(old_loop, new_loop)

# Now we need to add the intelligent selection logic AFTER the loop and BEFORE 'if not head and base_head_cands:'
old_resolution = r'''    # ── Resolução de Equipamentos Base / Evo Base (ex: Teklovossen) ─────────────
    if not head and base_head_cands:
        head = base_head_cands[0]
        if head in main_cards:
            main_cards.remove(head)
    if not chest and base_chest_cands:
        chest = base_chest_cands[0]
        if chest in main_cards:
            main_cards.remove(chest)
    if not arms and base_arms_cands:
        if is_arcane and any("arcbane" in x for x in base_arms_cands):
            arms = next(x for x in base_arms_cands if "arcbane" in x)
        else:
            arms = base_arms_cands[0]
        if arms in main_cards:
            main_cards.remove(arms)
    if not legs and base_legs_cands:
        legs = base_legs_cands[0]
        if legs in main_cards:
            main_cards.remove(legs)'''

new_resolution = r'''    # ── Resolução Inteligente de Equipamentos ─────────────
    def pick_best_equip(cands, is_arcane):
        if not cands: return None
        if len(cands) == 1: return cands[0]
        
        # Se for arcano, procura Arcane Barrier, Spellvoid, Ward
        # Senao, EVITA equipamentos com arcane barrier se houver alternativas melhores.
        for c in cands:
            meta = get_card_meta(c)
            text = str(meta.get("text", "")).lower()
            keywords = str(meta.get("keywords", "")).lower()
            has_ab = "arcane barrier" in text or "spellvoid" in text or "quell" in text or "ward" in text
            if is_arcane and has_ab:
                return c
                
        # Se is_arcane é falso, priorize quem NÃO tem arcane barrier
        if not is_arcane:
            for c in cands:
                meta = get_card_meta(c)
                text = str(meta.get("text", "")).lower()
                has_ab = "arcane barrier" in text or "spellvoid" in text
                if not has_ab:
                    return c
        
        return cands[0]

    # Filter out Evo bases if needed, but normally they just exist in the cands
    if base_head_cands:
        head = pick_best_equip(base_head_cands, is_arcane)
        inv.extend([c for c in base_head_cands if c != head])
    if base_chest_cands:
        chest = pick_best_equip(base_chest_cands, is_arcane)
        inv.extend([c for c in base_chest_cands if c != chest])
    if base_arms_cands:
        arms = pick_best_equip(base_arms_cands, is_arcane)
        inv.extend([c for c in base_arms_cands if c != arms])
    if base_legs_cands:
        legs = pick_best_equip(base_legs_cands, is_arcane)
        inv.extend([c for c in base_legs_cands if c != legs])
        
    if head in main_cards: main_cards.remove(head)
    if chest in main_cards: main_cards.remove(chest)
    if arms in main_cards: main_cards.remove(arms)
    if legs in main_cards: main_cards.remove(legs)'''

if old_resolution in content:
    content = content.replace(old_resolution, new_resolution)
    with open('ai/sideboard_manager.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Success patched sideboard!")
else:
    print("Could not find old resolution")
