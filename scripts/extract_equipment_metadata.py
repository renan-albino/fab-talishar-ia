"""
scripts/extract_equipment_metadata.py
=====================================
Extrai metadados semânticos completos de equipamentos oficiais do Flesh and Blood
a partir de Talishar/CardDictionaries/, Talishar/CurrentEffectAbilities.php e data/fab_cards_db.json.

Gera data/equipment_metadata.json eliminando a necessidade de hardcodes
de nomes de cartas nas estratégias de IA.
"""

import os
import re
import json
from typing import Dict, Any


def extract_php_switch_map(content: str, func_name_pattern: str, val_type: str = "str") -> Dict[str, Any]:
    """Extrai mapeamento de funções PHP estilo switch($cardID) ou match($cardID)."""
    result = {}
    func_pattern = re.compile(
        rf"function\s+([a-zA-Z0-9_]*{func_name_pattern})\s*\([^)]*\)\s*(?::\s*[a-zA-Z0-9_]+)?\s*\{{",
        re.MULTILINE
    )
    for m in func_pattern.finditer(content):
        start = m.end()
        depth = 1
        idx = start
        while idx < len(content) and depth > 0:
            if content[idx] == "{":
                depth += 1
            elif content[idx] == "}":
                depth -= 1
            idx += 1
        body = content[start:idx]

        # 1. Match formato match ($cardID)
        for line in body.split("\n"):
            line_s = line.strip()
            if "=>" in line_s and not line_s.startswith("//"):
                parts = line_s.split("=>")
                left, right = parts[0], parts[1]
                card_keys = re.findall(r'"([a-zA-Z0-9_]+)"', left)
                if not card_keys:
                    continue
                if val_type == "bool":
                    val = True if "true" in right.lower() else (False if "false" in right.lower() else None)
                elif val_type == "int":
                    m_val = re.search(r"(-?\d+)", right)
                    val = int(m_val.group(1)) if m_val else 0
                else:
                    m_val = re.search(r'"([a-zA-Z0-9_]+)"', right)
                    val = m_val.group(1) if m_val else ""
                if val is not None:
                    for c in card_keys:
                        result[c] = val

        # 2. Match formato switch ($cardID)
        case_blocks = re.split(r"return\s+([^;]+);", body)
        for i in range(0, len(case_blocks) - 1, 2):
            block = case_blocks[i]
            ret_expr = case_blocks[i + 1].strip()
            cards = re.findall(r'case\s+"([a-zA-Z0-9_]+)"', block)
            if not cards:
                continue
            if val_type == "bool":
                val = True if "true" in ret_expr.lower() else (False if "false" in ret_expr.lower() else None)
            elif val_type == "int":
                m_val = re.search(r"(-?\d+)", ret_expr)
                val = int(m_val.group(1)) if m_val else 0
            else:
                m_val = re.search(r'"([a-zA-Z0-9_]+)"', ret_expr)
                val = m_val.group(1) if m_val else ret_expr.strip('"')
            if val is not None:
                for c in cards:
                    result[c] = val

    return result


def extract_equipment_metadata(base_dir: str) -> Dict[str, Dict[str, Any]]:
    # Carrega base de dados oficial de cartas
    db_path = os.path.join(base_dir, "data", "fab_cards_db.json")
    cards_db = {}
    if os.path.exists(db_path):
        with open(db_path, "r", encoding="utf-8") as f:
            cards_db = json.load(f)

    # Carrega custos de habilidade extraídos
    ability_costs = {}
    costs_path = os.path.join(base_dir, "data", "ability_costs.json")
    if os.path.exists(costs_path):
        with open(costs_path, "r", encoding="utf-8") as f:
            ability_costs = json.load(f)

    # Localiza arquivos PHP relevantes do Talishar
    talishar_root = os.path.join(base_dir, "Talishar")
    php_files = []
    card_dict_php = os.path.join(talishar_root, "CardDictionary.php")
    if os.path.exists(card_dict_php):
        php_files.append(card_dict_php)
    cd_dir = os.path.join(talishar_root, "CardDictionaries")
    if os.path.exists(cd_dir):
        for root, _, files in os.walk(cd_dir):
            for f in files:
                if f.endswith(".php"):
                    php_files.append(os.path.join(root, f))

    all_ability_types = {}
    all_go_agains = {}
    all_power_mods = {}
    min_attack_costs = {}
    grants_resources_map = {}
    creates_token_map = {}
    cost_discount_map = {}

    for p in php_files:
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as fp:
                content = fp.read()
        except Exception:
            continue

        # Extrai AbilityType
        ab_types = extract_php_switch_map(content, "AbilityType", "str")
        all_ability_types.update(ab_types)

        # Extrai AbilityHasGoAgain
        go_agains = extract_php_switch_map(content, "AbilityHasGoAgain", "bool")
        all_go_agains.update(go_agains)

        # Extrai EffectPowerModifier
        p_mods = extract_php_switch_map(content, "EffectPowerModifier", "int")
        all_power_mods.update(p_mods)

        # Extrai condições de CombatEffectActive (ex: CardCost >= 2)
        func_pattern = re.compile(
            r"function\s+[a-zA-Z0-9_]*CombatEffectActive\s*\([^)]*\)\s*\{",
            re.MULTILINE
        )
        for m in func_pattern.finditer(content):
            start = m.end()
            depth = 1
            idx = start
            while idx < len(content) and depth > 0:
                if content[idx] == "{":
                    depth += 1
                elif content[idx] == "}":
                    depth -= 1
                idx += 1
            body = content[start:idx]
            for line in body.split("\n"):
                if "CardCost" in line and ">=" in line:
                    m_cost = re.search(r"CardCost\s*\([^)]*\)\s*>=\s*(\d+)", line)
                    if m_cost:
                        min_c = int(m_cost.group(1))
                        cards = re.findall(r'"([a-zA-Z0-9_]+)"', line)
                        for c in cards:
                            min_attack_costs[c] = min_c

        # Extrai GainResources e PlayAura nas funções de efeito ativado
        for line in content.split("\n"):
            if "GainResources" in line:
                m_res = re.search(r"GainResources\s*\([^,]+,\s*(\d+)\)", line)
                if m_res:
                    res_val = int(m_res.group(1))
                    # Encontra o case ou match correspondente nas proximidades
                    pass
        # Extrai por blocos de case em switch($cardID)
        case_chunks = re.finditer(r'case\s+"([a-zA-Z0-9_]+)":\s*(.*?)(?=case\s+"|\bdefault\b|\}\s*$)', content, re.DOTALL)
        for chunk in case_chunks:
            c_name = chunk.group(1)
            c_body = chunk.group(2)
            m_res = re.search(r"GainResources\s*\([^,]+,\s*(\d+)\)", c_body)
            if m_res:
                grants_resources_map[c_name] = int(m_res.group(1))
            m_aura = re.search(r'PlayAura\s*\(\s*"([a-zA-Z0-9_]+)"', c_body)
            if m_aura:
                creates_token_map[c_name] = m_aura.group(1)

    # Varre CurrentEffectAbilities.php para costModifier
    curr_eff_path = os.path.join(talishar_root, "CurrentEffectAbilities.php")
    if os.path.exists(curr_eff_path):
        try:
            with open(curr_eff_path, "r", encoding="utf-8", errors="ignore") as fp:
                c_content = fp.read()
            case_chunks = re.finditer(r'case\s+"([a-zA-Z0-9_]+)":\s*(.*?)(?=case\s+"|\bdefault\b|\}\s*$)', c_content, re.DOTALL)
            for chunk in case_chunks:
                c_name = chunk.group(1)
                c_body = chunk.group(2)
                m_mod = re.search(r"\$costModifier\s*-=\s*(\d+)", c_body)
                if m_mod:
                    cost_discount_map[c_name] = int(m_mod.group(1))
        except Exception:
            pass

    # Compila metadados de equipamentos
    metadata = {}
    for card_name, entry in cards_db.items():
        c_type = str(entry.get("type", "")).upper()
        c_subtype = str(entry.get("subtype", "")).lower()
        c_text = str(entry.get("text", "")).lower()

        # Verifica se é equipamento
        is_equipment = (
            c_type == "E"
            or "equipment" in c_type.lower()
            or any(s in c_subtype for s in ["head", "chest", "arms", "legs", "off-hand", "shield"])
        )
        if not is_equipment:
            continue

        # Determina o Slot
        slot = "equipment"
        for s in ["head", "chest", "arms", "legs", "off-hand", "shield"]:
            if s in c_subtype:
                slot = "off-hand" if s == "shield" else s
                break

        # Habilidade ativa
        ab_type = all_ability_types.get(card_name, "")
        if not ab_type:
            # Tenta inferir do texto
            if "action -" in c_text or "**action**" in c_text:
                ab_type = "A"
            elif "attack reaction -" in c_text or "**attack reaction**" in c_text:
                ab_type = "AR"
            elif "instant -" in c_text or "**instant**" in c_text:
                ab_type = "I"
            elif "defense reaction -" in c_text or "**defense reaction**" in c_text:
                ab_type = "DR"

        has_go_again = all_go_agains.get(card_name, False)
        if not has_go_again:
            if "go again" in c_text:
                if re.search(r"\bgo again\b", c_text):
                    has_go_again = True

        ab_cost = ability_costs.get(card_name, 0)
        power_buff = all_power_mods.get(card_name, 0)
        if power_buff == 0:
            m_pow = re.search(r"(?:gets|gain)\s*\+(\d+)\s*(?:\{p\}|power|\[attack\])", c_text)
            if m_pow:
                power_buff = int(m_pow.group(1))

        min_cost = min_attack_costs.get(card_name, 0)
        if min_cost == 0:
            m_min = re.search(r"cost(?:ing)?\s*(\d+)\s*or\s*more", c_text)
            if m_min:
                min_cost = int(m_min.group(1))

        # Recursos concedidos
        grants_res = grants_resources_map.get(card_name, 0)
        if grants_res == 0:
            if "gain {r}{r}" in c_text:
                grants_res = 2
            elif "gain {r}" in c_text or "gain 1 resource" in c_text:
                grants_res = 1

        # Desconto de custo
        cost_discount = cost_discount_map.get(card_name, 0)
        if cost_discount == 0:
            m_disc = re.search(r"costs\s*\{r\}(\{r\})?\s*less", c_text)
            if m_disc:
                cost_discount = 2 if m_disc.group(1) else 1

        # Contadores necessários
        req_counters = 0
        if "tunic" in card_name:
            req_counters = 3
        else:
            m_cnt = re.search(r"remove\s*(\d+)\s*[a-zA-Z0-9_\s]*counters?", c_text)
            if m_cnt:
                req_counters = int(m_cnt.group(1))

        # Concessão de Go Again a ataques
        grants_ga = bool(
            "gains go again" in c_text or "gain go again" in c_text
        )

        # Criação de tokens
        creates_token = creates_token_map.get(card_name, "")
        if not creates_token:
            if "seismic surge token" in c_text or "seismic surge" in c_text:
                creates_token = "seismic_surge"
            elif "quicken token" in c_text:
                creates_token = "quicken"
            elif "runechant token" in c_text:
                creates_token = "runechant"
            elif "ponder token" in c_text:
                creates_token = "ponder"
            elif "gold token" in c_text or "create a gold" in c_text:
                creates_token = "gold"

        # Palavras-chave de armadura
        has_bw = bool(entry.get("has_battleworn") or "battleworn" in c_subtype or "battleworn" in c_text)
        has_bb = bool(entry.get("has_blade_break") or "blade break" in c_subtype or "blade break" in c_text)
        has_temp = bool(entry.get("has_temper") or "temper" in c_subtype or "temper" in c_text)

        metadata[card_name] = {
            "name": card_name,
            "slot": slot,
            "ability_type": ab_type,
            "ability_cost": ab_cost,
            "has_go_again": has_go_again,
            "power_buff": power_buff,
            "min_attack_cost": min_cost,
            "grants_resource": grants_res,
            "cost_discount": cost_discount,
            "req_counters": req_counters,
            "grants_go_again": grants_ga,
            "creates_token": creates_token,
            "has_battleworn": has_bw,
            "has_blade_break": has_bb,
            "has_temper": has_temp,
            "block": int(entry.get("defense", entry.get("block", 0)) or 0),
        }

    return metadata


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    meta = extract_equipment_metadata(base_dir)
    out_path = os.path.join(base_dir, "data", "equipment_metadata.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Extraídos metadados de {len(meta)} equipamentos em {out_path}!")

    # Exibe amostra dos equipamentos clássicos para validação
    for sample in [
        "goliath_gauntlet", "heartened_cross_strap", "fyendals_spring_tunic",
        "tectonic_plating", "snapdragon_scalers", "ironrot_gauntlet", "crown_of_providence"
    ]:
        if sample in meta:
            print(f"  • {sample}: {meta[sample]}")


if __name__ == "__main__":
    main()
