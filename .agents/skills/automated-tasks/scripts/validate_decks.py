#!/usr/bin/env python3
"""
validate_decks.py
=================
Script utilitário para validar e corrigir baralhos JSON do FaB Talishar AI.

Varre a pasta `decks/*.json` (ou um baralho individual via `--deck`),
validando contra o banco oficial `data/fab_cards_db.json` e as regras de
torneio do Flesh and Blood (Classic Constructed vs Blitz):
  - Existência e suporte de todas as cartas no DB do Talishar;
  - Presença única e coerência do Herói (Adulto para CC, Jovem para Blitz);
  - Mínimo de cartas do deck principal (>=60 para CC, >=40 para Blitz);
  - Limite de cópias por carta (máx 3 em CC, máx 2 em Blitz, máx 1 para Herói);
  - Equipamentos e armas cadastrados.

Suporta correção automática com `--fix` e relatórios em terminal ou JSON.
"""

import os
import sys
import json
import argparse
from typing import Dict, Any, List, Tuple, Optional

# ── Resolução de Caminho Raiz do Repositório ──────────────────────────────
def _find_repo_root() -> str:
    curr = os.path.abspath(os.path.dirname(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "bot_client.py")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

ROOT_DIR = _find_repo_root()
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from deck_manager.validator import validate_deck_against_db
from deck_manager.slugifier import load_fab_cards_db
from deck_manager.parser import enrich_deck_metadata, extract_hero_from_deck

# Cores ANSI para terminal
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[0;32m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED = "\033[0;31m"
COLOR_CYAN = "\033[0;36m"
COLOR_BOLD = "\033[1m"


def fix_deck_obj(deck_obj: Dict[str, Any], db: Dict[str, Any]) -> Tuple[Dict[str, Any], List[str]]:
    """Tenta corrigir inconformidades comuns em um deck JSON.

    Ações de autocorreção:
      1. Normalização de campos de cartas (`count` -> `total`, identifiers limpos).
      2. Enriquecimento de metadados (hero, hero_name, class, talents, is_young).
      3. Ajuste de formato coerente com o Herói (se Young e <60 cards -> Blitz; se Adulto e >=60 -> CC).
      4. Inclusão da carta do Herói em `cards` caso ausente na lista mas definida nos metadados.
    """
    fixes: List[str] = []
    cards = deck_obj.get("cards", [])

    # 1. Normalizar formato das cartas
    normalized_cards = []
    for c in cards:
        if isinstance(c, str):
            cid = c.strip().lower()
            tot = 1
            normalized_cards.append({"identifier": cid, "total": tot})
            fixes.append(f"Convertida carta string '{cid}' para formato objeto.")
        elif isinstance(c, dict):
            cid = str(c.get("identifier", c.get("id", ""))).strip().lower()
            tot = int(c.get("total", c.get("count", 1)))
            if "count" in c and "total" not in c:
                fixes.append(f"Normalizada chave 'count' -> 'total' para '{cid}'.")
            normalized_cards.append({"identifier": cid, "total": tot})
        else:
            normalized_cards.append(c)

    deck_obj["cards"] = normalized_cards

    # 2. Enriquecer metadados
    deck_obj = enrich_deck_metadata(deck_obj, db=db)
    fixes.append("Metadados de herói, classe e talentos sincronizados.")

    # 3. Detectar e corrigir herói ausente na lista
    hero_id = deck_obj.get("hero", "")
    if hero_id and hero_id in db:
        has_hero_in_cards = any(c.get("identifier") == hero_id for c in normalized_cards if isinstance(c, dict))
        if not has_hero_in_cards:
            deck_obj["cards"].insert(0, {"identifier": hero_id, "total": 1})
            fixes.append(f"Adicionada carta do herói '{hero_id}' à lista de cartas.")

    # 4. Ajustar formato se conflitante
    is_young = bool(deck_obj.get("is_young", False))
    current_fmt = str(deck_obj.get("format", "cc")).lower()
    total_cards = sum(c.get("total", 1) for c in deck_obj.get("cards", []) if isinstance(c, dict))

    if is_young and current_fmt in ("cc", "compcc"):
        deck_obj["format"] = "blitz"
        fixes.append("Formato alterado de CC para BLITZ (herói jovem detectado).")
    elif not is_young and current_fmt == "blitz" and total_cards >= 60:
        deck_obj["format"] = "cc"
        fixes.append("Formato alterado de BLITZ para CC (herói adulto com >=60 cartas).")

    return deck_obj, fixes


def validate_single_deck(
    filepath: str,
    db: Dict[str, Any],
    auto_fix: bool = False,
    verbose: bool = False
) -> Dict[str, Any]:
    """Valida um único arquivo de deck JSON e opcionalmente aplica correções."""
    result: Dict[str, Any] = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "valid": False,
        "hero": "Desconhecido",
        "format": "N/A",
        "total_deck_cards": 0,
        "total_cards": 0,
        "errors": [],
        "fixed": False,
        "fixes": [],
    }

    if not os.path.exists(filepath):
        result["errors"].append(f"Arquivo não encontrado: {filepath}")
        return result

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            deck_data = json.load(f)
    except Exception as e:
        result["errors"].append(f"Erro ao decodificar JSON: {e}")
        return result

    # Validação inicial
    valid, errors, meta = validate_deck_against_db(deck_data)
    hero_name = extract_hero_from_deck(deck_data, db=db)
    result["hero"] = hero_name
    result["format"] = str(deck_data.get("format", "cc")).upper()
    result["total_deck_cards"] = meta.get("total_deck_cards", 0)
    result["total_cards"] = sum(c.get("total", 1) for c in deck_data.get("cards", []) if isinstance(c, dict))
    result["slots"] = meta.get("slots", {})
    result["errors"] = errors
    result["valid"] = valid

    # Tenta autocorreção se solicitado e se houver erros ou se faltarem metadados
    if auto_fix:
        deck_data, applied_fixes = fix_deck_obj(deck_data, db=db)
        if applied_fixes:
            # Revalida após aplicar correções
            new_valid, new_errors, new_meta = validate_deck_against_db(deck_data)
            # Salva de volta se melhorou ou se é válido
            if new_valid or len(new_errors) < len(errors):
                try:
                    with open(filepath, "w", encoding="utf-8") as f:
                        json.dump(deck_data, f, indent=2, ensure_ascii=False)
                    result["fixed"] = True
                    result["fixes"] = applied_fixes
                    result["valid"] = new_valid
                    result["errors"] = new_errors
                    result["hero"] = extract_hero_from_deck(deck_data, db=db)
                    result["format"] = str(deck_data.get("format", "cc")).upper()
                    result["total_deck_cards"] = new_meta.get("total_deck_cards", 0)
                    result["slots"] = new_meta.get("slots", {})
                except Exception as e:
                    result["errors"].append(f"Erro ao salvar correções em disco: {e}")

    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validador de Baralhos FaB Talishar AI contra data/fab_cards_db.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  ./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py
  ./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py --deck decks/jarl.json
  ./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py --fix
  ./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py --json
        """
    )
    parser.add_argument(
        "--deck",
        type=str,
        default=None,
        help="Caminho para validar um arquivo de deck específico (ex: decks/jarl.json)."
    )
    parser.add_argument(
        "--decks-dir",
        type=str,
        default="decks",
        help="Diretório onde os baralhos JSON estão localizados (padrão: decks)."
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Tenta corrigir automaticamente inconformidades de metadados e formatos e sobrescreve o arquivo."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Exibe o relatório em formato JSON estruturado (útil para automações/CI)."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Exibe detalhes completos dos slots de equipamentos e armas de cada deck."
    )

    args = parser.parse_args()

    # Carrega banco de cartas oficial
    db = load_fab_cards_db()
    if not db:
        print(f"{COLOR_RED}[ERRO CRÍTICO]{COLOR_RESET} Não foi possível carregar data/fab_cards_db.json.", file=sys.stderr)
        return 2

    decks_to_check: List[str] = []

    if args.deck:
        target_path = os.path.abspath(args.deck)
        decks_to_check.append(target_path)
    else:
        decks_dir = os.path.abspath(os.path.join(ROOT_DIR, args.decks_dir))
        if not os.path.exists(decks_dir):
            print(f"{COLOR_RED}[ERRO]{COLOR_RESET} Diretório de decks não encontrado: {decks_dir}", file=sys.stderr)
            return 1
        for fname in sorted(os.listdir(decks_dir)):
            if fname.endswith(".json"):
                decks_to_check.append(os.path.join(decks_dir, fname))

    if not decks_to_check:
        print(f"{COLOR_YELLOW}[AVISO]{COLOR_RESET} Nenhum baralho JSON encontrado para validação.")
        return 0

    results: List[Dict[str, Any]] = []
    total_valid = 0
    total_fixed = 0
    total_invalid = 0

    for fpath in decks_to_check:
        res = validate_single_deck(fpath, db=db, auto_fix=args.fix, verbose=args.verbose)
        results.append(res)
        if res["valid"]:
            total_valid += 1
            if res["fixed"]:
                total_fixed += 1
        else:
            total_invalid += 1

    # Saída JSON se solicitada
    if args.output_json:
        payload = {
            "total_scanned": len(results),
            "total_valid": total_valid,
            "total_invalid": total_invalid,
            "total_fixed": total_fixed,
            "results": results
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if total_invalid == 0 else 1

    # Saída visual em terminal
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════════════════════════════{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}   FaB Talishar AI — Validação de Baralhos (Torneio & Banco Oficial)                                    {COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════════════════════════════{COLOR_RESET}\n")

    header = f"{'ARQUIVO':<22} | {'HERÓI':<30} | {'FORMATO':<8} | {'CARTAS':<8} | {'STATUS'}"
    print(header)
    print("-" * len(header) + "-----------")

    for res in results:
        status_str = f"{COLOR_GREEN}✓ VÁLIDO{COLOR_RESET}" if res["valid"] else f"{COLOR_RED}✗ INVÁLIDO{COLOR_RESET}"
        if res["fixed"]:
            status_str += f" {COLOR_YELLOW}(CORRIGIDO){COLOR_RESET}"

        deck_count_str = f"{res['total_deck_cards']} ({res['total_cards']})"
        fname_display = res["filename"][:22]
        hero_display = res["hero"][:30]
        fmt_display = res["format"][:8]

        print(f"{fname_display:<22} | {hero_display:<30} | {fmt_display:<8} | {deck_count_str:<8} | {status_str}")

        if not res["valid"] or args.verbose:
            if res["errors"]:
                for err in res["errors"]:
                    print(f"   {COLOR_RED}↳ [ERRO]{COLOR_RESET} {err}")
            if res["fixes"]:
                for fix in res["fixes"]:
                    print(f"   {COLOR_YELLOW}↳ [FIX]{COLOR_RESET} {fix}")

        if args.verbose and res.get("slots"):
            slots = res["slots"]
            eq_count = sum(len(slots.get(k, [])) for k in ("Head", "Chest", "Arms", "Legs", "Equipment"))
            wp_count = sum(len(slots.get(k, [])) for k in ("Weapon", "Off-Hand"))
            print(f"   {COLOR_CYAN}↳ Slots:{COLOR_RESET} Deck={res['total_deck_cards']} | Equipamentos={eq_count} | Armas={wp_count}")

    print("-" * len(header) + "-----------")
    print(f"Total avaliado: {len(results)} | Válidos: {COLOR_GREEN}{total_valid}{COLOR_RESET} | Inválidos: {COLOR_RED if total_invalid > 0 else COLOR_GREEN}{total_invalid}{COLOR_RESET} | Corrigidos: {COLOR_YELLOW}{total_fixed}{COLOR_RESET}\n")

    return 0 if total_invalid == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
