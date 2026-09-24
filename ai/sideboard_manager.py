"""
ai/sideboard_manager.py
=======================
Gerenciador de resolução e conformidade de Sideboard para Flesh and Blood.
Trata:
  - Capacidade estrita de 2 mãos para armas e off-hands (CR 2.8.2 e CR 3.0).
  - Resolução de equipamentos e peças Base Evo (Teklovossen).
  - Adaptação tática contra dano arcano (Arcane Barrier / Spellvoid / Quelling) e fadiga.
  - Dimensionamento de baralho mínimo (40 para Blitz, 60 para CC, 65 vs fadiga).
"""

import os
import json
from typing import Dict, Any, List, Tuple, Callable, Optional


def resolve_sideboard(
    deck_url: str,
    deck_format: str,
    opp_hero: str,
    opp_class: str,
    get_card_meta: Callable[[str], dict],
    log_fn: Optional[Callable[[str], None]] = None,
    game_id: str = "",
    player_id: int = 1,
) -> Dict[str, Any]:
    """
    Resolve a configuração ótima e estritamente legal de Herói, Equipamentos,
    Armas e Deck Principal vs Inventário (Sideboard).
    """
    is_cc = deck_format.lower() in ("cc", "compcc", "llcc", "compllcc", "futurecc", "futurell", "gage")
    is_arcane = "wizard" in opp_class or "runeblade" in opp_class

    # Detecção dinâmica de fadiga baseada no histórico de turnos médios do oponente (SQLite)
    is_fatigue = False
    try:
        from stats.db import get_average_match_length
        avg_turns = get_average_match_length(opp_hero)
        if avg_turns is not None:
            is_fatigue = avg_turns >= 12.0
        else:
            is_fatigue = opp_class in ("guardian", "assassin", "mechanologist")
    except Exception:
        is_fatigue = opp_class in ("guardian", "assassin", "mechanologist")

    min_main = 60 if is_cc else 40
    if is_fatigue and is_cc:
        min_main = 65

    deck_file = deck_url if deck_url.endswith(".json") else f"decks/{deck_url}.json"
    if not os.path.exists(deck_file):
        for p in [f"Talishar/decks/{deck_url}.json", f"Talishar/decks/{deck_url}", "deck.json", "Talishar/deck.json"]:
            if os.path.exists(p):
                deck_file = p
                break

    raw_cards = []
    if os.path.exists(deck_file):
        try:
            with open(deck_file, "r", encoding="utf-8") as f:
                deck_data = json.load(f)
                raw_cards = deck_data.get("cards", [])
        except Exception as e:
            if log_fn:
                log_fn(f"[AVISO] Erro ao ler deck_file {deck_file}: {e}")

    if not raw_cards:
        pdeck_path = f"Talishar/Games/{game_id}/p{player_id}Deck.txt"
        if not os.path.exists(pdeck_path):
            pdeck_path = f"Games/{game_id}/p{player_id}Deck.txt"
        if os.path.exists(pdeck_path):
            try:
                with open(pdeck_path, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f if l.strip()]
                if len(lines) >= 2:
                    for cid in lines[0].split() + lines[1].split():
                        raw_cards.append({"identifier": cid, "total": 1})
            except Exception:
                pass

    hero = ""
    head = ""
    chest = ""
    arms = ""
    legs = ""
    quiver = ""
    raw_weapon_candidates = []
    raw_quivers = []
    main_cards = []
    inv = []

    base_head_cands = []
    base_chest_cands = []
    base_arms_cands = []
    base_legs_cands = []

    for c in raw_cards:
        cid = c.get("identifier", "") if isinstance(c, dict) else str(c)
        tot = int(c.get("count", c.get("total", 1))) if isinstance(c, dict) else 1
        if not cid:
            continue
        meta = get_card_meta(cid)
        slot = meta.get("slot", "Deck")
        subtype = str(meta.get("subtype", "")).lower()

        if slot == "Hero":
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
                inv.append(cid)
        elif "quiver" in subtype or "quiver" in cid.lower():
            raw_quivers.append(cid)
        elif slot in ("Weapon", "Off-Hand") or meta.get("type") == "W":
            raw_weapon_candidates.append(cid)
        else:
            if "base" in subtype:
                if "head" in subtype:
                    base_head_cands.append(cid)
                elif "chest" in subtype:
                    base_chest_cands.append(cid)
                elif "arms" in subtype:
                    base_arms_cands.append(cid)
                elif "legs" in subtype:
                    base_legs_cands.append(cid)
            main_cards.extend([cid] * tot)

    # ── Resolução de Equipamentos Base / Evo Base (ex: Teklovossen) ─────────────
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
            main_cards.remove(legs)

    # ── Resolução de Quivers (Aljavas de Ranger) ───────────────────────────────
    if raw_quivers:
        quiver = raw_quivers[0]
        inv.extend(raw_quivers[1:])

    if not hero:
        hero = "ira_crimson_haze"

    # ── Resolução Legal de Armas e Mãos (FaB CR 2.8.2 e CR 3.0) ────────────────
    w_2h = []
    w_1h = []
    offhands = []

    for cid in raw_weapon_candidates:
        meta = get_card_meta(cid)
        slot = meta.get("slot", "")
        subtype = str(meta.get("subtype", "")).lower()
        is_1h = bool(meta.get("is1h", False))
        is_off = (slot == "Off-Hand" or "off-hand" in subtype or "shield" in subtype)
        if is_off:
            offhands.append(cid)
        elif is_1h:
            w_1h.append(cid)
        else:
            w_2h.append(cid)

    chosen_weapons = []
    if w_2h and is_fatigue and not is_arcane:
        chosen_weapons = [w_2h[0]]
    elif w_1h and offhands:
        best_off = offhands[0]
        for off in offhands:
            if "stalagmite" in off:
                best_off = off
                break
        chosen_weapons = [w_1h[0], best_off]
    elif len(w_1h) >= 2:
        chosen_weapons = [w_1h[0], w_1h[1]]
    elif w_2h:
        chosen_weapons = [w_2h[0]]
    elif w_1h:
        chosen_weapons = [w_1h[0]]
    elif offhands:
        chosen_weapons = [offhands[0]]

    weapons = chosen_weapons
    for cid in raw_weapon_candidates:
        if cid not in weapons:
            inv.append(cid)

    equipped_arcane_count = 0
    if is_arcane:
        equip_slots = {"Head": head, "Chest": chest, "Arms": arms, "Legs": legs}
        new_inv = []
        for item in inv:
            meta = get_card_meta(item)
            slot = meta.get("slot", "")
            text = meta.get("text", "").lower()
            name = meta.get("name", "").lower()
            keywords = [k.lower() for k in meta.get("keywords", [])]
            is_arcane_item = (
                "arcane barrier" in text
                or "nullrune" in name
                or "quelling" in text
                or "spellvoid" in text
                or "spellvoid" in name
                or any("spellvoid" in k or "arcane" in k for k in keywords)
            )
            if slot in equip_slots and is_arcane_item:
                old_item = equip_slots[slot]
                if old_item:
                    new_inv.append(old_item)
                equip_slots[slot] = item
            else:
                new_inv.append(item)
        head, chest, arms, legs = equip_slots.get("Head", ""), equip_slots.get("Chest", ""), equip_slots.get("Arms", ""), equip_slots.get("Legs", "")
        inv = new_inv

        for eq in [head, chest, arms, legs] + weapons:
            if not eq:
                continue
            meta = get_card_meta(eq)
            text = meta.get("text", "").lower()
            name = meta.get("name", "").lower()
            keywords = [k.lower() for k in meta.get("keywords", [])]
            if (
                "arcane barrier" in text
                or "nullrune" in name
                or "quelling" in text
                or "spellvoid" in text
                or "spellvoid" in name
                or any("spellvoid" in k or "arcane" in k for k in keywords)
            ):
                equipped_arcane_count += 1

    flat_deck = main_cards
    if len(flat_deck) > min_main:
        def card_score(cid):
            meta = get_card_meta(cid)
            pitch = int(meta.get("pitch", 0)) if str(meta.get("pitch", 0)).isdigit() else 0
            defense = int(meta.get("defense", 0)) if str(meta.get("defense", 0)).isdigit() else 0
            power = int(meta.get("power", 0)) if str(meta.get("power", 0)).isdigit() else 0
            if is_arcane:
                if equipped_arcane_count >= 2:
                    if pitch == 3:
                        return 100 + power + defense
                else:
                    if pitch == 3:
                        return (defense * 2) + power - 10
            return power + defense + (3 - pitch)

        flat_deck.sort(key=card_score, reverse=True)
        inv.extend(flat_deck[min_main:])
        flat_deck = flat_deck[:min_main]
    elif len(flat_deck) < min_main:
        needed = min_main - len(flat_deck)
        deck_inv = [i for i in inv if get_card_meta(i).get("slot", "Deck") == "Deck"]
        if len(deck_inv) >= needed:
            flat_deck.extend(deck_inv[:needed])
            for c in deck_inv[:needed]:
                inv.remove(c)

    sub_obj = {
        "hero": hero,
        "head": head,
        "chest": chest,
        "arms": arms,
        "legs": legs,
        "hands": weapons,
        "deck": flat_deck,
        "inventory": inv
    }
    if quiver:
        sub_obj["quiver"] = quiver

    return sub_obj
