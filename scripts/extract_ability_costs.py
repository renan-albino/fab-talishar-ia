"""
scripts/extract_ability_costs.py
================================
Extrai os custos e tipos de habilidades ativadas (AbilityCost, AbilityType)
de todos os arquivos de dicionário de cartas do Talishar (CardDictionaries/ e CardDictionary.php).
Gera data/ability_costs.json para consumo pelo PolicyEngine e motor de IA,
eliminando a necessidade de hardcodes para armas e equipamentos.
"""

import os
import re
import json

def extract_ability_costs(talishar_root: str = "Talishar") -> dict:
    ability_db = {}
    
    # 1. Varre todos os arquivos PHP em Talishar/CardDictionaries e Talishar/CardDictionary.php
    target_files = []
    card_dict_php = os.path.join(talishar_root, "CardDictionary.php")
    if os.path.exists(card_dict_php):
        target_files.append(card_dict_php)
        
    cd_dir = os.path.join(talishar_root, "CardDictionaries")
    if os.path.exists(cd_dir):
        for root, _, files in os.walk(cd_dir):
            for f in files:
                if f.endswith(".php"):
                    target_files.append(os.path.join(root, f))

    cost_func_pattern = re.compile(
        r"function\s+([a-zA-Z0-9_]*AbilityCost)\s*\([^)]*\)\s*(?::\s*[a-zA-Z0-9_]+)?\s*\{",
        re.MULTILINE
    )

    for path in target_files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                content = fp.read()
        except Exception:
            continue

        for m in cost_func_pattern.finditer(content):
            start = m.end()
            # Encontra o fim da função contando chaves balanceadas
            depth = 1
            idx = start
            while idx < len(content) and depth > 0:
                if content[idx] == "{":
                    depth += 1
                elif content[idx] == "}":
                    depth -= 1
                idx += 1
            body = content[start:idx]

            # 1. Match no formato match ($cardID) { "card1", "card2" => N, default => 0 }
            for line in body.split("\n"):
                if "=>" in line and not line.strip().startswith("//"):
                    parts = line.split("=>")
                    left, right = parts[0], parts[1]
                    # Extrai o número da direita
                    val_match = re.search(r"(-?\d+)", right)
                    if val_match:
                        cost_val = max(0, int(val_match.group(1)))
                        card_keys = re.findall(r'"([a-zA-Z0-9_]+)"', left)
                        for c in card_keys:
                            ability_db[c] = cost_val

            # 2. Match no formato switch ($cardID) { case "card1": case "card2": return N; }
            # Divide por blocos de case/return
            case_blocks = re.split(r"return\s+(-?\d+)\s*;", body)
            for i in range(0, len(case_blocks) - 1, 2):
                block = case_blocks[i]
                val = max(0, int(case_blocks[i + 1]))
                # Pega todos os case "card" imediatamente anteriores
                cards = re.findall(r'case\s+"([a-zA-Z0-9_]+)"', block)
                for c in cards:
                    ability_db[c] = val

    # 2. Escaneia recursivamente Talishar/Classes/CardObjects/*.php
    card_objects_dir = os.path.join(talishar_root, "Classes", "CardObjects")
    if os.path.exists(card_objects_dir):
        for root, _, files in os.walk(card_objects_dir):
            for f in sorted(files):
                if f.endswith(".php"):
                    path = os.path.join(root, f)
                    try:
                        with open(path, "r", encoding="utf-8", errors="ignore") as fp:
                            content = fp.read()
                    except Exception:
                        continue
                    cls_matches = list(re.finditer(r"class\s+([a-zA-Z0-9_]+)\s+extends\s+[a-zA-Z0-9_]+", content))
                    for i, cm in enumerate(cls_matches):
                        cname = cm.group(1)
                        start = cm.end()
                        end = cls_matches[i + 1].start() if i + 1 < len(cls_matches) else len(content)
                        block = content[start:end]
                        ac_match = re.search(r"function\s+AbilityCost\s*\([^)]*\)[^{]*\{[^}]*?return\s+(-?\d+)\s*;", block, re.DOTALL)
                        if ac_match:
                            ability_db[cname] = max(0, int(ac_match.group(1)))

    return ability_db


def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    talishar_path = os.path.join(base_dir, "Talishar")
    costs = extract_ability_costs(talishar_path)
    output_path = os.path.join(base_dir, "data", "ability_costs.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(costs, f, indent=2)
    print(f"Extraídos {len(costs)} custos de habilidade com sucesso em {output_path}!")
    for test_card in ["hammerhead_harpoon_cannon", "romping_club", "tectonic_plating", "cintari_saber", "high_riser", "pile_driver"]:
        print(f"  • {test_card}: {costs.get(test_card, 'N/A')}")

if __name__ == "__main__":
    main()
