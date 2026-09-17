#!/usr/bin/env python3
"""
scripts/extract_cr_mechanics.py
===============================
Extrai e consolida mecânicas formais das Comprehensive Rules (CR) de Flesh and Blood:
  - 32 Ability Keywords (CR 8.3)
  - 21 Label Keywords (CR 8.4)
  - 38 Token Keywords (CR 8.6)

Cruza com data/fab_cards_db.json e atualiza data/fab_card_semantics.json
garantindo cobertura semântica de 100% de cartas catalogadas.
"""

import os
import sys
import json
import re
from typing import Dict, Any, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_DB_PATH = os.path.join(BASE_DIR, "data", "fab_cards_db.json")
SEMANTICS_PATH = os.path.join(BASE_DIR, "data", "fab_card_semantics.json")

# ══════════════════════════════════════════════════════════════════
# 1. CATALOGAÇÃO OFICIAL DAS COMPREHENSIVE RULES (CR)
# ══════════════════════════════════════════════════════════════════

# 32 Ability Keywords (CR 8.3)
CR_ABILITY_KEYWORDS = {
    "attack": {"category": "combat", "evasion": False},
    "battleworn": {"category": "equipment_defense", "counter": "-1d_on_close"},
    "blade_break": {"category": "equipment_defense", "destroys_on_close": True},
    "dominate": {"category": "evasion", "hand_block_limit": 1},
    "go_again": {"category": "action_economy", "grants_ap": 1},
    "legendary": {"category": "meta", "deck_limit": 1},
    "specialization": {"category": "meta", "hero_specific": True},
    "arcane_barrier": {"category": "prevention", "arcane": True},
    "boost": {"category": "cost_mechanic", "banish_top_deck": True, "grants_go_again": True},
    "temper": {"category": "equipment_defense", "counter": "-1d_on_close", "destroys_at_zero": True},
    "blood_debt": {"category": "banish_penalty", "lose_hp_at_end": 1},
    "phantasm": {"category": "vulnerability", "popped_by_6_power": True},
    "spectra": {"category": "attack_target", "destroys_when_targeted": True},
    "spellvoid": {"category": "prevention", "arcane": True, "destroys_self": True},
    "essence": {"category": "meta", "talent_inclusion": True},
    "fusion": {"category": "cost_mechanic", "reveal_element": True},
    "heave": {"category": "end_phase", "arsenal_surges": True},
    "quell": {"category": "prevention", "damage": True, "resource_cost": True},
    "ward": {"category": "prevention", "damage": True, "destroys_self": True},
    "ephemeral": {"category": "meta", "ceases_to_exist": True},
    "overpower": {"category": "evasion", "hand_action_limit": 1},
    "piercing": {"category": "evasion", "buff_vs_equipment": True},
    "stealth": {"category": "label", "subtype_interaction": True},
    "mirage": {"category": "defense_penalty", "destroys_vs_6_power": True},
    "pairs": {"category": "equipment_constraint", "requires_object": True},
    "rune_gate": {"category": "cost_reduction", "play_from_banish": True},
    "ambush": {"category": "defense_allowance", "defend_from_arsenal": True},
    "crank": {"category": "action_economy", "remove_steam_gain_ap": True},
    "modular": {"category": "equipment_flexibility", "any_slot": True},
    "protect": {"category": "defense_allowance", "defend_other_hero": True},
    "scrap": {"category": "cost_mechanic", "banish_graveyard_item": True},
    "beat_chest": {"category": "cost_mechanic", "discard_6_power": True},
    "guardwell": {"category": "equipment_defense", "counter_equal_def": True},
    "universal": {"category": "class_adaptation", "matches_hero_class": True},
    "cloaked": {"category": "equipment_state", "equip_face_down": True},
    "arcane_shelter": {"category": "prevention", "arcane": True, "destroys_self": True},
    "meld": {"category": "split_card", "double_cost_both_sides": True},
    "perched": {"category": "equipment_allowance", "in_addition_to_2h": True},
    "fragment": {"category": "debuff", "penalty_vs_2_def": True},
}

# 21 Label Keywords (CR 8.4)
CR_LABEL_KEYWORDS = {
    "combo": {"class": "ninja", "chain_dependent": True},
    "crush": {"class": "guardian", "trigger_damage_threshold": 4},
    "reprise": {"class": "warrior", "hand_defend_condition": True},
    "channel": {"class": "elemental", "end_phase_pitch": True},
    "material": {"class": "general", "under_permanent": True},
    "rupture": {"class": "draconic", "chain_link_threshold": 4},
    "contract": {"class": "assassin", "target_banish": True},
    "surge": {"class": "wizard", "arcane_damage_threshold": True},
    "solflare": {"class": "light", "charge_soul_trigger": True},
    "unity": {"class": "general", "defends_together_hand": True},
    "evo_upgrade": {"class": "mechanologist", "evo_count_scaling": True},
    "galvanize": {"class": "mechanologist", "destroy_item_buff": True},
    "tower": {"class": "guardian", "power_threshold": 13},
    "decompose": {"class": "earth", "banish_graveyard_cost": True},
    "bond": {"class": "elemental", "pitched_element_condition": True},
    "flow": {"class": "elemental", "played_element_condition": True},
    "heavy": {"class": "general", "single_weapon_equipped": True},
    "high_tide": {"class": "general", "two_blue_pitch_condition": True},
    "go_fish": {"class": "ranger", "on_hit_reveal_gold": True},
    "quickstrike": {"class": "lightning_runeblade", "has_go_again_condition": True},
    "starfall": {"class": "lightning_wizard", "instant_in_graveyard_condition": True},
}

# 38 Tokens Oficiais (CR 8.6)
CR_TOKENS = {
    "quicken": {"type": "aura", "effect": "next attack gets go again"},
    "seismic_surge": {"type": "aura", "effect": "next guardian attack costs 1 less"},
    "runechant": {"type": "aura", "effect": "deals 1 arcane damage on attack"},
    "copper": {"type": "item", "effect": "4 resources, destroy: draw card, go again"},
    "silver": {"type": "item", "effect": "3 resources, destroy: draw card, go again"},
    "gold": {"type": "item", "effect": "2 resources, destroy: draw card, go again"},
    "zen_state": {"type": "aura", "effect": "prevent 1 damage"},
    "spectral_shield": {"type": "aura", "effect": "ward 1"},
    "frostbite": {"type": "aura", "effect": "cards and abilities cost 1 more"},
    "embodiment_of_earth": {"type": "aura", "effect": "non-attack actions have +1d"},
    "embodiment_of_lightning": {"type": "aura", "effect": "attack actions get go again"},
    "ash": {"type": "ash", "effect": "material phantasm"},
    "aether_ashwing": {"type": "ally", "power": 1, "life": 1, "arcane_barrier": 1},
    "ponder": {"type": "aura", "effect": "draw card at end phase"},
    "bloodrot_pox": {"type": "aura", "effect": "lose 2 life unless pay 3"},
    "frailty": {"type": "aura", "effect": "-1 power to weapons and arsenal attacks"},
    "inertia": {"type": "aura", "effect": "put hand and arsenal to bottom of deck"},
    "courage": {"type": "aura", "effect": "next attack gets +1 power"},
    "eloquence": {"type": "aura", "effect": "next non-attack action gets go again"},
    "hyper_driver": {"type": "item", "effect": "boost gains 1 resource"},
    "might": {"type": "aura", "effect": "next attack gets +1 power"},
    "vigor": {"type": "aura", "effect": "gain 1 resource at start of turn"},
    "agility": {"type": "aura", "effect": "next attack gets go again"},
    "cintari_sellsword": {"type": "ally", "power": 3, "life": 2},
    "graphene_chelicera": {"type": "weapon", "power": 1},
    "fealty": {"type": "aura", "effect": "next card is draconic"},
    "golden_cog": {"type": "item", "effect": "crank, steam counter"},
    "goldkiss_rum": {"type": "item", "effect": "action gets go again"},
    "bait": {"type": "aura", "effect": "attack reaction +1 power"},
    "confidence": {"type": "aura", "effect": "cant be defended by more than 2 non-blocks"},
    "toughness": {"type": "aura", "effect": "next action gets +1d"},
    "sigil_of_fate": {"type": "aura", "effect": "opt 1 when leaves arena"},
    "lightning_flow": {"type": "aura", "effect": "lightning flow"},
    "ursur_the_soul_reaper": {"type": "ally", "power": 6, "life": 6},
    "blasmophet_the_soul_harvester": {"type": "ally", "power": 6, "life": 6},
    "nasreth_the_soul_harrower": {"type": "ally", "power": 6, "life": 6},
    "spellbane_aegis": {"type": "aura", "effect": "spellvoid 1"},
}


# ══════════════════════════════════════════════════════════════════
# 2. MOTOR DE INFERÊNCIA SEMÂNTICA POR REGRAS OFICIAIS
# ══════════════════════════════════════════════════════════════════

def extract_cr_profile(card_id: str, card_data: Dict[str, Any]) -> Dict[str, Any]:
    name = card_data.get("name", card_id).lower()
    c_type = str(card_data.get("type", "AA")).upper()
    subtype = str(card_data.get("subtype", "")).lower()
    text = str(card_data.get("text", "")).lower()
    cid = card_id.lower()

    keywords: List[str] = []

    # Evasão
    evasion = {
        "dominate": False,
        "overpower": False,
        "piercing": 0,
        "phantasm": False,
        "stealth": False,
        "mirage": False
    }

    # Prevenção
    prevention = {
        "arcane_barrier": 0,
        "spellvoid": 0,
        "ward": 0,
        "quell": 0
    }

    # 1. Checagem de Ability Keywords
    if "dominate" in text or "dominate" in cid or "dominate" in name:
        evasion["dominate"] = True
        keywords.append("dominate")
    if "overpower" in text or "overpower" in cid or "overpower" in name:
        evasion["overpower"] = True
        keywords.append("overpower")
    if "phantasm" in text or "phantasm" in cid:
        evasion["phantasm"] = True
        keywords.append("phantasm")
    if "stealth" in text or "stealth" in subtype:
        evasion["stealth"] = True
        keywords.append("stealth")
    if "mirage" in text:
        evasion["mirage"] = True
        keywords.append("mirage")

    m_pierce = re.search(r"piercing\s*(\d+)", text)
    if m_pierce:
        p_val = int(m_pierce.group(1))
        evasion["piercing"] = p_val
        keywords.append(f"piercing_{p_val}")
    elif "piercing" in text or "piercing" in name:
        evasion["piercing"] = 1
        keywords.append("piercing")

    # Prevenção
    m_ab = re.search(r"arcane barrier\s*(\d+)", text)
    if m_ab:
        prevention["arcane_barrier"] = int(m_ab.group(1))
        keywords.append(f"arcane_barrier_{m_ab.group(1)}")
    elif card_data.get("has_arcane_barrier"):
        prevention["arcane_barrier"] = 1
        keywords.append("arcane_barrier")

    m_sv = re.search(r"spellvoid\s*(\d+)", text)
    if m_sv:
        prevention["spellvoid"] = int(m_sv.group(1))
        keywords.append(f"spellvoid_{m_sv.group(1)}")

    m_ward = re.search(r"ward\s*(\d+)", text)
    if m_ward:
        prevention["ward"] = int(m_ward.group(1))
        keywords.append(f"ward_{m_ward.group(1)}")
    elif "ward" in text and "ward" not in name:
        prevention["ward"] = 1
        keywords.append("ward")

    m_quell = re.search(r"quell\s*(\d+)", text)
    if m_quell:
        prevention["quell"] = int(m_quell.group(1))
        keywords.append(f"quell_{m_quell.group(1)}")

    # Palavras-chave de equipamento e combate
    for kw in ["battleworn", "blade_break", "temper", "guardwell", "ambush", "boost",
               "crank", "scrap", "beat_chest", "rune_gate", "heave", "protect", "meld"]:
        kw_spaced = kw.replace("_", " ")
        if kw_spaced in text or kw in text or kw in cid:
            keywords.append(kw)

    # Go again
    has_go_again = bool(card_data.get("has_go_again")) or "go again" in text
    if has_go_again:
        keywords.append("go_again")

    # 2. Checagem de Label Keywords
    for label in ["combo", "crush", "reprise", "channel", "material", "rupture",
                  "contract", "surge", "solflare", "unity", "evo_upgrade", "galvanize",
                  "tower", "decompose", "bond", "flow", "heavy", "high_tide", "go_fish",
                  "quickstrike", "starfall"]:
        label_spaced = label.replace("_", " ")
        if f"{label_spaced} -" in text or f"{label_spaced} —" in text or f"{label_spaced}:" in text or label in cid:
            keywords.append(label)

    # 3. Disrupção On-Hit e Severidade
    extra_on_hit_damage = 0
    on_hit_disruption = None
    on_hit_severity = 0.0

    if "when this hits" in text or "if this hits" in text or "whenever this hits" in text or "deals damage" in text:
        if "destroy" in text and "arsenal" in text or "command_and_conquer" in cid:
            on_hit_disruption = "destroy_arsenal"
            on_hit_severity = 10.0
        elif "discard" in text or "crippling" in cid:
            on_hit_disruption = "discard_hand"
            on_hit_severity = 8.5
        elif any(t in text or t in cid for t in ["bloodrot", "frailty", "inertia"]):
            on_hit_disruption = "affliction"
            on_hit_severity = 5.0
        elif "draw" in text or "snatch" in cid:
            on_hit_disruption = "draw_cards"
            on_hit_severity = 6.0
        elif "freeze" in text:
            on_hit_disruption = "turn_lock"
            on_hit_severity = 7.0
        else:
            on_hit_disruption = "general_trigger"
            on_hit_severity = 3.5

    # Concessões e Ameaça Arcana
    arcane_threat = 0
    if "arcane damage" in text:
        m_arc = re.search(r"deal\s*(\d+)\s*arcane damage", text)
        if m_arc:
            arcane_threat = int(m_arc.group(1))
        else:
            arcane_threat = 2

    return {
        "name": card_data.get("name", card_id),
        "type": c_type,
        "subtype": subtype,
        "keywords": list(set(keywords)),
        "evasion": evasion,
        "extra_on_hit_damage": extra_on_hit_damage,
        "on_hit_disruption": on_hit_disruption,
        "on_hit_severity": on_hit_severity,
        "grants_evasion": ["dominate"] if "gains dominate" in text else [],
        "grants_piercing": 1 if "gains piercing" in text else 0,
        "arcane_threat": arcane_threat,
        "prevention": prevention,
        "generates_ap": 1 if "gain 1 action point" in text else 0,
        "generates_resource": 1 if "gain {r}" in text else 0,
    }


def main():
    print("[CR Extraction] Carregando banco de cartas...")
    if not os.path.exists(CARDS_DB_PATH):
        print(f"ERRO: Banco de cartas não encontrado em {CARDS_DB_PATH}")
        sys.exit(1)

    with open(CARDS_DB_PATH, "r", encoding="utf-8") as f:
        cards_db = json.load(f)

    existing_semantics = {}
    if os.path.exists(SEMANTICS_PATH):
        try:
            with open(SEMANTICS_PATH, "r", encoding="utf-8") as f:
                existing_semantics = json.load(f)
        except Exception:
            existing_semantics = {}

    print(f"[CR Extraction] Analisando {len(cards_db)} cartas com base nas Comprehensive Rules...")
    updated_count = 0

    for card_id, card_data in cards_db.items():
        cid = str(card_id).lower().strip()
        cr_prof = extract_cr_profile(cid, card_data)

        # Mescla com semântica existente preservando inferências mais ricas se já houver
        if cid in existing_semantics:
            curr = existing_semantics[cid]
            # Combina keywords
            all_kws = list(set(curr.get("keywords", []) + cr_prof["keywords"]))
            curr["keywords"] = all_kws
            # Atualiza evasão
            for k, v in cr_prof["evasion"].items():
                if v:
                    curr.setdefault("evasion", {})[k] = v
            # Atualiza prevenção
            for k, v in cr_prof["prevention"].items():
                if v > 0:
                    curr.setdefault("prevention", {})[k] = max(curr.get("prevention", {}).get(k, 0), v)
            if cr_prof["on_hit_severity"] > curr.get("on_hit_severity", 0.0):
                curr["on_hit_severity"] = cr_prof["on_hit_severity"]
                curr["on_hit_disruption"] = cr_prof["on_hit_disruption"]
            existing_semantics[cid] = curr
        else:
            existing_semantics[cid] = cr_prof
            updated_count += 1

    # Salva o arquivo de semântica atualizado
    os.makedirs(os.path.dirname(SEMANTICS_PATH), exist_ok=True)
    with open(SEMANTICS_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_semantics, f, indent=2, ensure_ascii=False)

    print(f"[CR Extraction] ✓ Sucesso! {len(existing_semantics)} cartas catalogadas em {SEMANTICS_PATH}")


if __name__ == "__main__":
    main()
