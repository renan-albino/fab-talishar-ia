#!/usr/bin/env python3
"""
scripts/extract_card_semantics.py
=================================
Extrai metadados semânticos canônicos e completos das cartas de Flesh and Blood
a partir de:
  - Talishar/GeneratedCode/GeneratedCardDictionaries.php
  - Talishar/CardLogic.php
  - Talishar/ItemAbilities.php
  - Talishar/CardDictionaries/HitEffects.php
  - data/fab_cards_db.json

Gera data/fab_card_semantics.json no esquema padronizado:
{
  "<card_id>": {
    "name": str,
    "type": str,
    "subtype": str,
    "keywords": list[str],
    "evasion": {
      "dominate": bool,
      "overpower": bool,
      "piercing": int,
      "phantasm": bool,
      "stealth": bool
    },
    "extra_on_hit_damage": int,
    "on_hit_disruption": str | None,
    "on_hit_severity": float,
    "grants_evasion": list[str],
    "grants_piercing": int,
    "arcane_threat": int,
    "prevention": {
      "arcane_barrier": int,
      "spellvoid": int,
      "ward": int,
      "quell": int
    },
    "generates_ap": int,
    "generates_resource": int
  }
}
"""

import os
import sys
import json
import re
from typing import Dict, Any, Set, List, Optional, Tuple


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
GENERATED_DICT_PATH = os.path.join(REPO_ROOT, "Talishar", "GeneratedCode", "GeneratedCardDictionaries.php")
CARD_LOGIC_PATH = os.path.join(REPO_ROOT, "Talishar", "CardLogic.php")
ITEM_ABILITIES_PATH = os.path.join(REPO_ROOT, "Talishar", "ItemAbilities.php")
HIT_EFFECTS_PATH = os.path.join(REPO_ROOT, "Talishar", "CardDictionaries", "HitEffects.php")
CARDS_DB_PATH = os.path.join(REPO_ROOT, "data", "fab_cards_db.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "fab_card_semantics.json")


def parse_php_match_dictionaries(filepath: str) -> Dict[str, Dict[str, Any]]:
    """
    Analisa funções PHP em GeneratedCardDictionaries.php que utilizam
    expressões match($cardID) e retorna um dicionário:
    { function_name: { card_id: value } }
    """
    if not os.path.exists(filepath):
        print(f"[WARN] Arquivo não encontrado: {filepath}", file=sys.stderr)
        return {}

    funcs: Dict[str, Dict[str, Any]] = {}
    current_func: Optional[str] = None

    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            line_s = line.strip()
            if line_s.startswith("function "):
                m = re.match(r"function\s+([A-Za-z0-9_]+)", line_s)
                if m:
                    current_func = m.group(1)
                    funcs[current_func] = {}
            elif current_func:
                if "=>" in line_s:
                    parts = line_s.split("=>")
                    k = parts[0].strip().strip("\"'")
                    v = parts[1].strip().rstrip(",").rstrip(";")
                    if k != "default":
                        if v == "true":
                            val: Any = True
                        elif v == "false":
                            val = False
                        else:
                            try:
                                val = int(v)
                            except ValueError:
                                val = v.strip("\"'")
                        funcs[current_func][k] = val
                elif line_s.startswith("};"):
                    current_func = None

    return funcs


def parse_on_hit_damage_from_php() -> Dict[str, int]:
    """
    Identifica dano adicional On-Hit a partir de ItemAbilities.php, CardLogic.php
    e HitEffects.php.
    Exemplos canônicos:
      boom_grenade_red -> 4, boom_grenade_yellow -> 3, boom_grenade_blue -> 2
      mauling_qi_red -> 1
      pay_up_red -> 1
    """
    extra_dmg: Dict[str, int] = {}

    # 1. Regras canônicas conhecidas
    extra_dmg["boom_grenade_red"] = 4
    extra_dmg["boom_grenade_yellow"] = 3
    extra_dmg["boom_grenade_blue"] = 2
    extra_dmg["mauling_qi_red"] = 1
    extra_dmg["pay_up_red"] = 1

    # 2. Varredura dinâmica em CardLogic.php (ProcessItemsEffect e blocos case)
    if os.path.exists(CARD_LOGIC_PATH):
        with open(CARD_LOGIC_PATH, "r", encoding="utf-8", errors="replace") as f:
            logic_content = f.read()

        # Procura blocos boom_grenade caso valores mudem
        bg_match = re.search(
            r'case\s+"boom_grenade_red":.*?case\s+"boom_grenade_blue":.*?'
            r'\$cardID\s*==\s*"boom_grenade_red"\)\s*\$amount\s*=\s*(\d+);.*?'
            r'\$cardID\s*==\s*"boom_grenade_yellow"\)\s*\$amount\s*=\s*(\d+);.*?'
            r'else\s*\$amount\s*=\s*(\d+);',
            logic_content,
            re.DOTALL
        )
        if bg_match:
            extra_dmg["boom_grenade_red"] = int(bg_match.group(1))
            extra_dmg["boom_grenade_yellow"] = int(bg_match.group(2))
            extra_dmg["boom_grenade_blue"] = int(bg_match.group(3))

    # 3. Varredura dinâmica em HitEffects.php
    if os.path.exists(HIT_EFFECTS_PATH):
        with open(HIT_EFFECTS_PATH, "r", encoding="utf-8", errors="replace") as f:
            hit_content = f.read()

        # Busca casos com DamageTrigger(...) ou DEAL1DAMAGE
        # ex: case "mauling_qi_red": ... DamageTrigger(..., damage: 1, ...)
        cases = re.split(r'case\s+["\']([a-zA-Z0-9_-]+)["\']\s*:', hit_content)
        # cases alterna [preamble, case_name_1, block_1, case_name_2, block_2, ...]
        for i in range(1, len(cases), 2):
            cid = cases[i]
            block = cases[i+1] if i+1 < len(cases) else ""
            dmg_match = re.search(r'DamageTrigger\([^,]+,\s*(?:damage:\s*)?(\d+)', block)
            if dmg_match:
                extra_dmg[cid] = int(dmg_match.group(1))
            elif "DEAL1DAMAGE" in block:
                extra_dmg[cid] = 1

    return extra_dmg


def classify_on_hit_disruption(card_id: str, name: str, subtype: str = "") -> Tuple[Optional[str], float]:
    """
    Identifica efeitos On-Hit com ruptura/disrupção e severidade (0.0 a 10.0):
      - "destroy_arsenal" (10.0): command_and_conquer, leave_no_witnesses, wreck_havoc, eradicate, strength_rules_all, war_machine, command_respect
      - "discard_hand" (7.5, 8.5 para crippling): crippling_crush, surgical_extraction, pummel, blizzard_bolt, dwarf_anvil, concuss, terminator_tank, judge_jury_executioner
      - "turn_lock" (9.0): red_in_the_ledger, spinal_crush, hypothermia
      - "affliction" (4.0): bloodrot, frailty, inertia, frostbite
      - "draw_cards" (6.0): snatch, mask_of_momentum, herald_of_erudition
    """
    c_lower = card_id.lower()
    n_lower = name.lower()

    # 1. Destroy Arsenal (Severidade máxima 10.0)
    destroy_arsenal_patterns = [
        "command_and_conquer",
        "leave_no_witnesses",
        "wreck_havoc",
        "eradicate",
        "strength_rules_all",
        "war_machine",
        "command_respect",
    ]
    if any(p in c_lower for p in destroy_arsenal_patterns):
        return "destroy_arsenal", 10.0

    # 2. Turn Lock (Severidade 9.0)
    turn_lock_patterns = [
        "red_in_the_ledger",
        "spinal_crush",
        "hypothermia",
    ]
    if any(p in c_lower for p in turn_lock_patterns):
        return "turn_lock", 9.0

    # 3. Discard Hand (Severidade 7.5)
    discard_hand_patterns = [
        "crippling_crush",
        "surgical_extraction",
        "pummel",
        "blizzard_bolt",
        "dwarf_anvil",
        "terminator_tank",
        "concuss",
        "judge_jury_executioner",
    ]
    if any(p in c_lower for p in discard_hand_patterns):
        return "discard_hand", 7.5

    # 4. Draw Cards on Hit (Severidade 6.0)
    draw_patterns = [
        "snatch",
        "mask_of_momentum",
        "herald_of_erudition",
        "erudition",
    ]
    if any(p in c_lower for p in draw_patterns):
        return "draw_cards", 6.0

    # 5. Affliction (Severidade 4.0)
    # Inclui fichas de aflição e cartas cujo objetivo on-hit seja infligir aflições
    affliction_patterns = [
        "bloodrot",
        "frailty",
        "inertia",
        "frostbite",
        "infect",
        "withering_shot",
        "bonds_of_agony",
    ]
    if any(p in c_lower for p in affliction_patterns):
        return "affliction", 4.0

    return None, 0.0


def identify_arena_item_aura_effects(card_id: str, name: str, subtype: str = "") -> Tuple[List[str], int, int, int, int]:
    """
    Identifica efeitos de itens / auras de arena:
      - convection_amplifier: concede Dominate se tiver contador -> grants_evasion: ["dominate"]
      - penetration_script: concede Piercing 1 se tiver contador -> grants_piercing: 1
      - teklo_core: gera recursos -> generates_resource: 2
      - auras:
          might (+1 atk)
          vigor (+1 recurso) -> generates_resource: 1
          agility (go again) -> generates_ap: 1
          runechant (1 dano arcano no ataque) -> arcane_threat: 1

    Retorna: (grants_evasion, grants_piercing, arcane_threat, generates_ap, generates_resource)
    """
    c_lower = card_id.lower()

    grants_evasion: List[str] = []
    grants_piercing = 0
    arcane_threat = 0
    generates_ap = 0
    generates_resource = 0

    # Convection Amplifier
    if "convection_amplifier" in c_lower:
        grants_evasion.append("dominate")

    # Penetration Script
    if "penetration_script" in c_lower:
        grants_piercing = 1

    # Teklo Core
    if "teklo_core" in c_lower:
        generates_resource = 2

    # Runechant
    if "runechant" in c_lower:
        arcane_threat = 1

    # Vigor
    if c_lower == "vigor" or c_lower.startswith("vigor_"):
        generates_resource = 1

    # Agility
    if c_lower == "agility" or c_lower.startswith("agility_"):
        generates_ap = 1

    # Might
    # (Might concede ataque direto na resolução, sem campos específicos além de keywords)

    return grants_evasion, grants_piercing, arcane_threat, generates_ap, generates_resource


def extract_card_semantics() -> Dict[str, Any]:
    """
    Executa a extração completa combinando todas as fontes de dados e
    produz o dicionário semântico consolidado.
    """
    # 1. Carrega banco de cartas base
    cards_db: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(CARDS_DB_PATH):
        with open(CARDS_DB_PATH, "r", encoding="utf-8") as f:
            cards_db = json.load(f)
    print(f"[INFO] Cartas carregadas de fab_cards_db.json: {len(cards_db)}")

    # 2. Analisa GeneratedCardDictionaries.php
    gen_funcs = parse_php_match_dictionaries(GENERATED_DICT_PATH)
    print(f"[INFO] Funções parseadas de GeneratedCardDictionaries.php: {len(gen_funcs)}")

    # Mapeamentos rápidos de GeneratedCardDictionaries
    has_dominate = gen_funcs.get("GeneratedHasDominate", {})
    has_overpower = gen_funcs.get("GeneratedHasOverpower", {})
    has_piercing = gen_funcs.get("GeneratedHasPiercing", {})
    has_phantasm = gen_funcs.get("GeneratedHasPhantasm", {})
    has_stealth = gen_funcs.get("GeneratedHasStealth", {})

    has_go_again = gen_funcs.get("GeneratedGoAgain", {})
    has_crush = gen_funcs.get("GeneratedHasCrush", {})
    has_reprise = gen_funcs.get("GeneratedHasReprise", {})
    has_rupture = gen_funcs.get("GeneratedHasRupture", {})
    has_crank = gen_funcs.get("GeneratedHasCrank", {})
    has_boost = gen_funcs.get("GeneratedHasBoost", {})
    has_combo = gen_funcs.get("GeneratedHasCombo", {})
    has_contract = gen_funcs.get("GeneratedHasContract", {})
    has_heave = gen_funcs.get("GeneratedHasHeave", {})
    heave_amounts = gen_funcs.get("GeneratedHeaveAmount", {})
    has_blood_debt = gen_funcs.get("GeneratedHasBloodDebt", {})
    has_rune_gate = gen_funcs.get("GeneratedHasRuneGate", {})

    has_arcane_barrier = gen_funcs.get("GeneratedHasArcaneBarrier", {})
    ab_amounts = gen_funcs.get("GeneratedArcaneBarrierAmount", {})
    has_spellvoid = gen_funcs.get("GeneratedHasSpellvoid", {})
    spellvoid_amounts = gen_funcs.get("GeneratedSpellvoidAmount", {})
    has_ward = gen_funcs.get("GeneratedHasWard", {})
    ward_amounts = gen_funcs.get("GeneratedWardAmount", {})
    has_quell = gen_funcs.get("GeneratedHasQuell", {})
    quell_amounts = gen_funcs.get("GeneratedQuellAmount", {})

    has_battleworn = gen_funcs.get("GeneratedHasBattleworn", {})
    has_blade_break = gen_funcs.get("GeneratedHasBladeBreak", {})
    has_temper = gen_funcs.get("GeneratedHasTemper", {})
    has_ambush = gen_funcs.get("GeneratedHasAmbush", {})

    has_amp = gen_funcs.get("GeneratedHasAmp", {})
    amp_amounts = gen_funcs.get("GeneratedAmpAmount", {})
    has_solflare = gen_funcs.get("GeneratedHasSolflare", {})
    has_transcend = gen_funcs.get("GeneratedHasTranscend", {})
    has_galvanize = gen_funcs.get("GeneratedHasGalvanize", {})

    # Metadados complementares de tipos/subtipos
    gen_card_types = gen_funcs.get("GeneratedCardType", {})
    gen_card_subtypes = gen_funcs.get("GeneratedCardSubtype", {})
    gen_card_names = gen_funcs.get("GeneratedCardName", {})

    # 3. Analisa dano On-Hit extra de CardLogic / ItemAbilities / HitEffects
    on_hit_damage_map = parse_on_hit_damage_from_php()
    print(f"[INFO] Entradas de dano extra On-Hit identificadas: {len(on_hit_damage_map)}")

    # 4. Compila todos os card_ids canônicos
    all_card_ids: Set[str] = set(cards_db.keys())

    # Adiciona card_ids válidos presentes nas funções de lógica que são nomes de cartas snake_case
    for fn_name, fn_map in gen_funcs.items():
        if fn_name == "GeneratedSetIDtoCardID":
            continue
        for k in fn_map.keys():
            if isinstance(k, str) and "_" in k and not k.startswith("SEA") and not k.startswith("DTD") and not k.startswith("MON") and not k.startswith("WTR") and not k.startswith("ARC") and not k.startswith("CRU"):
                all_card_ids.add(k)

    for cid in on_hit_damage_map.keys():
        all_card_ids.add(cid)

    print(f"[INFO] Total de card_ids a processar: {len(all_card_ids)}")

    semantics_db: Dict[str, Dict[str, Any]] = {}

    for card_id in sorted(all_card_ids):
        card_raw = cards_db.get(card_id, {})

        name = card_raw.get("name") or gen_card_names.get(card_id) or card_id.replace("_", " ").title()
        card_type = card_raw.get("type") or gen_card_types.get(card_id) or "AA"
        subtype = card_raw.get("subtype") or gen_card_subtypes.get(card_id) or ""

        keywords: Set[str] = set()

        # ── 1. Evasão ──
        is_dominate = bool(has_dominate.get(card_id))
        is_overpower = bool(has_overpower.get(card_id))
        piercing_val = 1 if has_piercing.get(card_id) else 0
        is_phantasm = bool(has_phantasm.get(card_id))
        is_stealth = bool(has_stealth.get(card_id))

        if is_dominate:
            keywords.add("dominate")
        if is_overpower:
            keywords.add("overpower")
        if piercing_val > 0:
            keywords.add("piercing")
        if is_phantasm:
            keywords.add("phantasm")
        if is_stealth:
            keywords.add("stealth")

        evasion = {
            "dominate": is_dominate,
            "overpower": is_overpower,
            "piercing": piercing_val,
            "phantasm": is_phantasm,
            "stealth": is_stealth,
        }

        # ── 2. Combate / Ação ──
        if has_go_again.get(card_id) or card_raw.get("has_go_again"):
            keywords.add("go_again")
        if has_crush.get(card_id):
            keywords.add("crush")
        if has_reprise.get(card_id):
            keywords.add("reprise")
        if has_rupture.get(card_id):
            keywords.add("rupture")
        if has_crank.get(card_id):
            keywords.add("crank")
        if has_boost.get(card_id):
            keywords.add("boost")
        if has_combo.get(card_id):
            keywords.add("combo")
        if has_contract.get(card_id):
            keywords.add("contract")
        if has_blood_debt.get(card_id):
            keywords.add("blood_debt")
        if has_rune_gate.get(card_id):
            keywords.add("rune_gate")

        if has_heave.get(card_id):
            keywords.add("heave")
            heave_amt = heave_amounts.get(card_id, 0)
            if heave_amt > 0:
                keywords.add(f"heave_{heave_amt}")

        # ── 3. Prevenção / Defesa ──
        ab_val = int(ab_amounts.get(card_id, 0))
        if ab_val == 0 and (has_arcane_barrier.get(card_id) or card_raw.get("has_arcane_barrier")):
            ab_val = 1

        sv_val = int(spellvoid_amounts.get(card_id, 0))
        if sv_val == 0 and has_spellvoid.get(card_id):
            sv_val = 1

        ward_val = int(ward_amounts.get(card_id, 0))
        if ward_val == 0 and has_ward.get(card_id):
            ward_val = 1

        quell_val = int(quell_amounts.get(card_id, 0))
        if quell_val == 0 and has_quell.get(card_id):
            quell_val = 1

        prevention = {
            "arcane_barrier": ab_val,
            "spellvoid": sv_val,
            "ward": ward_val,
            "quell": quell_val,
        }

        if ab_val > 0:
            keywords.add("arcane_barrier")
            keywords.add(f"arcane_barrier_{ab_val}")
        if sv_val > 0:
            keywords.add("spellvoid")
            keywords.add(f"spellvoid_{sv_val}")
        if ward_val > 0:
            keywords.add("ward")
            keywords.add(f"ward_{ward_val}")
        if quell_val > 0:
            keywords.add("quell")
            keywords.add(f"quell_{quell_val}")

        if has_battleworn.get(card_id) or card_raw.get("has_battleworn"):
            keywords.add("battleworn")
        if has_blade_break.get(card_id) or card_raw.get("has_blade_break"):
            keywords.add("blade_break")
        if has_temper.get(card_id) or card_raw.get("has_temper"):
            keywords.add("temper")
        if has_ambush.get(card_id) or card_raw.get("has_ambush"):
            keywords.add("ambush")

        # ── 4. Arcana / Gatilhos ──
        amp_val = int(amp_amounts.get(card_id, 0))
        if amp_val == 0 and has_amp.get(card_id):
            amp_val = 1
        if amp_val > 0:
            keywords.add("amp")
            keywords.add(f"amp_{amp_val}")

        if has_solflare.get(card_id):
            keywords.add("solflare")
        if has_transcend.get(card_id):
            keywords.add("transcend")
        if has_galvanize.get(card_id):
            keywords.add("galvanize")

        # ── 5. Efeitos On-Hit adicionais (Dano extra e Disrupção) ──
        extra_on_hit_damage = int(on_hit_damage_map.get(card_id, 0))

        disruption_category, severity = classify_on_hit_disruption(card_id, name, subtype)

        # Se não tiver categoria de disrupção mas tiver dano extra On-Hit
        if not disruption_category and extra_on_hit_damage > 0:
            severity = min(10.0, float(extra_on_hit_damage) * 1.5)

        # ── 6. Efeitos de Itens e Auras de Arena ──
        (
            grants_evasion,
            grants_piercing,
            arcane_threat,
            item_ap,
            item_res,
        ) = identify_arena_item_aura_effects(card_id, name, subtype)

        # Geração de AP (Crank gera 1 AP)
        generates_ap = item_ap
        if "crank" in keywords:
            generates_ap = max(generates_ap, 1)

        generates_resource = item_res

        # Auras complementares
        if card_id == "might" or card_id.startswith("might_"):
            keywords.add("might")
        elif card_id == "vigor" or card_id.startswith("vigor_"):
            keywords.add("vigor")
        elif card_id == "agility" or card_id.startswith("agility_"):
            keywords.add("agility")
            keywords.add("go_again")
        elif card_id == "runechant" or card_id.startswith("runechant_"):
            keywords.add("runechant")
            keywords.add("arcane")

        profile: Dict[str, Any] = {
            "name": name,
            "type": card_type,
            "subtype": subtype,
            "keywords": sorted(list(keywords)),
            "evasion": evasion,
            "extra_on_hit_damage": extra_on_hit_damage,
            "on_hit_disruption": disruption_category,
            "on_hit_severity": round(severity, 2),
            "grants_evasion": grants_evasion,
            "grants_piercing": grants_piercing,
            "arcane_threat": arcane_threat,
            "prevention": prevention,
            "generates_ap": generates_ap,
            "generates_resource": generates_resource,
        }

        semantics_db[card_id] = profile

    return semantics_db


def main():
    print("Iniciando extração semântica de cartas FaB...")
    semantics_db = extract_card_semantics()

    # Salva com formatação compacta/legível
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(semantics_db, f, indent=2, ensure_ascii=False)

    size_mb = os.path.getsize(OUTPUT_PATH) / (1024 * 1024)
    print(f"\n[SUCESSO] Metadados semânticos salvos em: {OUTPUT_PATH}")
    print(f"  Tamanho do arquivo: {size_mb:.2f} MB")
    print(f"  Total de cartas indexadas: {len(semantics_db)}")

    # Estatísticas de cobertura
    with_keywords = sum(1 for p in semantics_db.values() if p["keywords"])
    with_evasion = sum(1 for p in semantics_db.values() if any(p["evasion"].values()))
    with_on_hit_damage = sum(1 for p in semantics_db.values() if p["extra_on_hit_damage"] > 0)
    with_disruption = sum(1 for p in semantics_db.values() if p["on_hit_disruption"] is not None)
    with_prevention = sum(1 for p in semantics_db.values() if any(p["prevention"].values()))
    with_arena_grants = sum(1 for p in semantics_db.values() if p["grants_evasion"] or p["grants_piercing"] > 0 or p["arcane_threat"] > 0)

    print("\n--- Estatísticas de Cobertura Semântica ---")
    print(f"  Cartas com Keywords: {with_keywords}")
    print(f"  Cartas com Evasão ativa: {with_evasion}")
    print(f"  Cartas com Dano Extra On-Hit: {with_on_hit_damage}")
    print(f"  Cartas com Ruptura/Disrupção On-Hit: {with_disruption}")
    print(f"  Cartas com Prevenção (Ward/Barrier/Spellvoid/Quell): {with_prevention}")
    print(f"  Cartas com Concessões de Arena/Auras/Ameaças: {with_arena_grants}")

    # Amostras de verificação
    sample_cards = [
        "boom_grenade_red",
        "mauling_qi_red",
        "command_and_conquer_red",
        "crippling_crush_red",
        "red_in_the_ledger_red",
        "snatch_red",
        "convection_amplifier_red",
        "penetration_script_yellow",
        "teklo_core_blue",
        "runechant",
        "crown_of_reflection",
        "sink_below_red",
    ]
    print("\n--- Amostras Verificadas ---")
    for sc in sample_cards:
        if sc in semantics_db:
            p = semantics_db[sc]
            print(f"  [{sc}] -> {p['name']} | KW: {p['keywords']} | OnHit: {p['on_hit_disruption']} (sev: {p['on_hit_severity']}, +{p['extra_on_hit_damage']} dmg) | Evasion: {p['evasion']} | Prev: {p['prevention']} | Grants: {p['grants_evasion']}")


if __name__ == "__main__":
    main()
