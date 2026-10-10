"""
ai/policy/on_hit_evaluator.py
=============================
Modelo Dinâmico de Impacto no Grafo de Ações para On-Hits (CR Combat Rules & Semantic Valuation).
Quantifica numericamente o impacto de efeitos on-hit (compra de cartas, descarte/banimento,
destruição de arsenal, tokens de aflição e dano extra) escalados pela alavancagem de HP do herói.
"""

import os
import json
import re
import math
from typing import Dict, Any, Optional

_SEMANTICS_DB: Optional[Dict[str, Dict[str, Any]]] = None


def _load_semantics_db() -> Dict[str, Dict[str, Any]]:
    global _SEMANTICS_DB
    if _SEMANTICS_DB is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        db_path = os.path.join(base_dir, "data", "fab_card_semantics.json")
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    _SEMANTICS_DB = json.load(f)
            except Exception:
                _SEMANTICS_DB = {}
        else:
            _SEMANTICS_DB = {}
    return _SEMANTICS_DB


def normalize_card_slug(card_name: str) -> str:
    """
    Normaliza o slug da carta removendo sufixos de pitch (_red, _yellow, _blue, _r, _y, _b)
    e pontuação, convertendo para snake_case.
    """
    if not card_name:
        return ""
    slug = str(card_name).lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    for suffix in ("_red", "_yellow", "_blue", "_r", "_y", "_b"):
        if slug.endswith(suffix):
            slug = slug[:-len(suffix)]
            break
    return slug


def _get_card_draw_value(state: dict) -> float:
    """
    Valor dinâmico de compra de cartas baseado na taxa de conversão do deck/arquétipo (~3.5 a 4.0 pts).
    - Ninjas, Runeblades, Assassins, Rangers: alto poder de conversão por carta (~4.0 pts).
    - Guardians, Warriors e controle: ~3.5 pts.
    - Padrão geral: 3.8 pts.
    """
    if not state:
        return 3.8
    hero_class = str(
        state.get("playerClass")
        or state.get("heroClass")
        or state.get("hero", "")
        or state.get("heroName", "")
    ).lower()
    if any(c in hero_class for c in ["ninja", "runeblade", "assassin", "ranger", "katsu", "fai", "chane"]):
        return 4.0
    if any(c in hero_class for c in ["guardian", "warrior", "merchant", "bravo", "victor", "dorinthea"]):
        return 3.5
    return 3.8


def estimate_on_hit_value(attack_name: str, state: Optional[dict] = None) -> float:
    """
    Estima o impacto dinâmico do efeito on-hit de um ataque no grafo de ações.
    Consulta fab_card_semantics.json e metadados de regras do FaB:
    - Compra de cartas (snatch, mask_of_momentum no 3º link da cadeia): ~3.5 a 4.0 pts.
    - Descarte / Remoção da mão ou banimento (felling_of_the_crown com decompose, pummel,
      command_and_conquer, erase_face): perda de teto de ação do oponente (~3.0 a 4.0 pts).
      Para felling_of_the_crown_red, o valor somado ao ataque base atinge ~11.0+ pts.
    - Destruição de Arsenal (command_and_conquer, leave_no_witnesses): ~4.0 a 5.0 pts.
    - Tokens de tributo (frostbite, bloodrot_pox, frailty, inertia): ~1.5 a 2.5 pts.
    - Escala exponencial conforme o HP do herói diminui (alavancagem de vida).
    """
    if not attack_name:
        return 0.0

    state = state or {}
    slug = normalize_card_slug(attack_name)
    raw_name_lower = str(attack_name).lower().strip()

    chain_link = int(
        state.get("currentChainLink", state.get("chainLink", state.get("combatChainLink", 1)))
    )

    base_value = 0.0

    # 1. Regras e cartas canônicas do FaB
    if slug == "mask_of_momentum":
        # Mask of Momentum só dispara no 3º link da cadeia ou superior
        if chain_link >= 3:
            base_value = _get_card_draw_value(state)
        else:
            base_value = 0.0
    elif slug == "command_and_conquer":
        # Destruição de Arsenal (~4.0) + Bloqueio de Defense Reaction (~1.0) = 5.0 pts
        base_value = 5.0
    elif slug in ("snatch",):
        base_value = _get_card_draw_value(state)
    elif slug == "felling_of_the_crown":
        # Banish da mão com Decompose: perda de teto de ação (~4.0 pts).
        # Somado ao poder de ataque base (7 para a vermelha), atinge 11.0+ pts.
        base_value = 4.0
    elif slug == "erase_face":
        # Perda de identidade de classe/talento da mão/deck: restrição de teto de ação (~4.0 pts)
        base_value = 4.0
    elif slug == "pummel":
        # Descarte forçado da mão: perda de recurso e teto de ação (~3.8 pts)
        base_value = 3.8
    elif slug == "spinal_crush":
        # Turn lock / desativação de Go Again: 6.0 pts
        base_value = 6.0
    elif slug == "leave_no_witnesses":
        # Banimento de Arsenal: 4.0 pts
        base_value = 4.0
    else:
        # 2. Consulta à base semântica canonical fab_card_semantics.json
        sem_db = _load_semantics_db()
        entry = None
        for cand in [raw_name_lower, slug, f"{slug}_red", f"{slug}_yellow", f"{slug}_blue"]:
            if cand in sem_db:
                entry = sem_db[cand]
                break

        if entry:
            disruption = entry.get("on_hit_disruption")
            severity = float(entry.get("on_hit_severity", 0.0))
            extra_dmg = int(entry.get("extra_on_hit_damage", 0))

            if disruption == "draw_cards":
                base_value = _get_card_draw_value(state)
            elif disruption == "discard_hand":
                base_value = 3.8
            elif disruption == "destroy_arsenal":
                base_value = 4.0
            elif disruption == "turn_lock":
                base_value = 6.0
            elif disruption == "affliction":
                card_low = raw_name_lower + "_" + slug
                if "bloodrot" in card_low:
                    base_value = 2.5
                elif "inertia" in card_low:
                    base_value = 2.5
                elif "frostbite" in card_low:
                    base_value = 2.0
                elif "frailty" in card_low:
                    base_value = 2.0
                else:
                    base_value = 2.2
            elif severity > 0:
                base_value = min(6.0, severity * 0.5)

            if extra_dmg > 0:
                base_value += float(extra_dmg)

        # 3. Fallback heurístico para tokens de tributo
        if base_value == 0.0:
            card_str = raw_name_lower + "_" + slug
            if "bloodrot" in card_str:
                base_value = 2.5
            elif "frostbite" in card_str:
                base_value = 2.0
            elif "frailty" in card_str:
                base_value = 2.0
            elif "inertia" in card_str:
                base_value = 2.5

    if base_value <= 0.0:
        return 0.0

    # 4. Alavancagem de Vida (Hero Life Leverage):
    # Conforme o HP diminui abaixo de 20, On-Hits perigosos ganham peso exponencial.
    my_hp = int(state.get("playerHealth", 20))
    if my_hp < 20:
        leverage = math.exp((20.0 - max(1, my_hp)) / 18.0)
        return round(base_value * leverage, 2)

    return round(base_value, 2)
