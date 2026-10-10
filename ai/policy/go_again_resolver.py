"""
ai/policy/go_again_resolver.py
==============================
Módulo de resolução dinâmica de Go Again e sequenciamento de ataque para Flesh and Blood.
Avalia Go Again natural (GeneratedGoAgain/cards_db) e condicionais (Links Dracônicos,
Cartas Vermelhas como Blaze Headlong, Combos Ninja e Tokens como Quicken/Agility).
"""

from __future__ import annotations

import os
import re
from typing import Any, Tuple, Optional, Set

from .constants import _load_cards_db

# Diretório raiz para localização de GeneratedCode se necessário
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Cartas canônicas que exigem links dracônicos prévios (limiar de >= 2 links)
DRACONIC_CHAIN_REQUIREMENT_CARDS: Set[str] = {
    "burning_blade_dance",
    "display_loyalty",
    "demonstrate_devotion",
    "cinderskin_devotion",
    "lava_vein_loyalty",
    "hot_on_their_heels",
    "mark_with_magma",
}

# Requisitos canônicos de combo Ninja (nome da carta -> lista de prefixos/nomes aceitos do último ataque)
NINJA_COMBO_REQUIREMENTS: dict[str, list[str]] = {
    "rising_knee_thrust": ["leg_tap"],
    "crane_dance": ["soulbead_strike", "soulbead"],
    "find_center": ["crane_dance"],
    "herons_flight": ["crane_dance"],
    "whelming_gustwave": ["surging_strike"],
    "descendent_gustwave": ["surging_strike"],
    "gustwave_of_the_second_wind": ["surging_strike"],
    "mugenshi_release": ["whelming_gustwave"],
    "hurricane_technique": ["rising_knee_thrust", "rising_knee"],
    "blackout_kick": ["rising_knee_thrust", "rising_knee"],
    "open_the_center": ["head_jab"],
    "pounding_gale": ["open_the_center"],
    "fluster_fist": ["open_the_center"],
    "recoil": ["head_jab"],
    "one_two_punch": ["head_jab"],
    "rushing_river": ["torrent_of_tempo"],
    "flood_of_force": ["rushing_river", "flood_of_force"],
    "break_tide": ["rushing_river", "flood_of_force"],
    "winds_of_eternity": ["hundred_winds"],
    "hundred_winds": ["hundred_winds"],
    "tiger_swipe": ["crouching_tiger", "tiger"],
    "pouncing_qi": ["crouching_tiger", "tiger"],
    "qi_unleashed": ["crouching_tiger", "tiger"],
    "mauling_qi": ["crouching_tiger", "tiger"],
    "chase_the_tail": ["crouching_tiger", "tiger"],
    "breed_anger": ["crouching_tiger", "tiger"],
    "aspect_of_tiger_body": ["crouching_tiger", "tiger"],
    "aspect_of_tiger_soul": ["crouching_tiger", "tiger"],
    "aspect_of_tiger_mind": ["crouching_tiger", "tiger"],
    "cyclone_roundhouse": ["spinning_wheel_kick"],
    "dishonor": ["bonds_of_ancestry"],
}

_DRACONIC_CARDS_CACHE: Optional[Set[str]] = None
_NATURAL_GO_AGAIN_CACHE: Optional[Set[str]] = None


def _load_draconic_cards() -> Set[str]:
    """Carrega o conjunto de cartas com talento DRACONIC a partir do GeneratedCardTalent.php."""
    global _DRACONIC_CARDS_CACHE
    if _DRACONIC_CARDS_CACHE is not None:
        return _DRACONIC_CARDS_CACHE
    draconic = set()
    php_path = os.path.join(_BASE_DIR, "Talishar", "GeneratedCode", "GeneratedFunctions", "GeneratedCardTalent.php")
    if os.path.isfile(php_path):
        try:
            with open(php_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "DRACONIC" in line and "=>" in line:
                        parts = line.split("=>")
                        card_id = parts[0].strip().strip('"\'')
                        draconic.add(card_id.lower())
        except Exception:
            pass
    _DRACONIC_CARDS_CACHE = draconic
    return _DRACONIC_CARDS_CACHE


def _load_natural_go_again_cards() -> Set[str]:
    """Carrega o conjunto de cartas com Go Again natural a partir do GeneratedGoAgain.php."""
    global _NATURAL_GO_AGAIN_CACHE
    if _NATURAL_GO_AGAIN_CACHE is not None:
        return _NATURAL_GO_AGAIN_CACHE
    go_agains = set()
    php_path = os.path.join(_BASE_DIR, "Talishar", "GeneratedCode", "GeneratedFunctions", "GeneratedGoAgain.php")
    if os.path.isfile(php_path):
        try:
            with open(php_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    if "=> true" in line or "=> 1" in line:
                        parts = line.split("=>")
                        card_id = parts[0].strip().strip('"\'')
                        go_agains.add(card_id.lower())
        except Exception:
            pass
    _NATURAL_GO_AGAIN_CACHE = go_agains
    return _NATURAL_GO_AGAIN_CACHE


def is_draconic_card(card: Any) -> bool:
    """Verifica se uma carta ou link possui talento DRACONIC."""
    if isinstance(card, dict):
        talent = str(card.get("talent") or card.get("cardTalent") or "").upper()
        if "DRACONIC" in talent:
            return True
        subtypes = str(card.get("subtype") or card.get("subtypes") or "").upper()
        if "DRACONIC" in subtypes:
            return True
        name = str(card.get("cardNumber") or card.get("name") or card.get("cardID") or card.get("id") or "").lower()
    else:
        name = str(card or "").lower()

    clean = name.strip().replace(" ", "_").replace("-", "_").replace("'", "")
    base = re.sub(r"_(red|yellow|blue)$", "", clean)
    draconic_set = _load_draconic_cards()
    return (
        clean in draconic_set
        or base in draconic_set
        or f"{clean}_red" in draconic_set
        or f"{clean}_yellow" in draconic_set
        or f"{clean}_blue" in draconic_set
    )


def _extract_card_identifier(card: Any) -> str:
    """Extrai identificador normalizado de uma carta (objeto ou string)."""
    if isinstance(card, dict):
        return str(card.get("cardNumber") or card.get("name") or card.get("cardID") or card.get("id") or "").lower().strip()
    return str(card or "").lower().strip()


def has_prior_red_card_played(state: dict) -> bool:
    """Verifica se ao menos uma carta vermelha foi jogada no turno atual (CR 8.5 / Regras FaB)."""
    if state.get("redCardsPlayed", 0) > 0 or state.get("redCardsPlayedThisTurn", 0) > 0 or state.get("numRedPlayed", 0) > 0 or state.get("redCardPlayed"):
        return True

    turn_effects = state.get("currentTurnEffects", [])
    for eff in turn_effects:
        eff_str = str(eff).lower()
        if "red" in eff_str or eff_str.endswith("_red"):
            return True

    actions = (
        state.get("currentTurnActions", [])
        or state.get("turnActions", [])
        or state.get("actionsThisTurn", [])
        or state.get("cardsPlayedThisTurn", [])
        or state.get("playedCards", [])
    )
    for act in actions:
        act_str = _extract_card_identifier(act)
        pitch = act.get("pitch", 0) if isinstance(act, dict) else 0
        if "_red" in act_str or pitch == 1:
            return True

    chain_cards = list(state.get("combatChainLinks") or []) + list(state.get("combatChain") or [])
    if state.get("activeChainLink") and state.get("activeChainLink") not in chain_cards:
        chain_cards.append(state.get("activeChainLink"))
    for cc in chain_cards:
        cc_str = _extract_card_identifier(cc)
        cc_pitch = cc.get("pitch", 0) if isinstance(cc, dict) else 0
        if "_red" in cc_str or cc_pitch == 1:
            return True

    return False


def resolve_attack_go_again(
    card_name: str, state: dict, hand_info: Optional[dict] = None
) -> Tuple[bool, str]:
    """
    Avalia se um candidato de ataque tem Go Again garantido no estado atual.
    
    Retorna:
        tuple[bool, str]: (tem_go_again, motivo_ou_condicao)
        
    Motivos:
        - "natural_go_again": Go Again intrínseco (GeneratedGoAgain / cards_db)
        - "token_granted": Concedido por Quicken ou Agility no 1º link da cadeia
        - "draconic_threshold_met": Links dracônicos anteriores >= 2
        - "insufficient_draconic_links": Menos de 2 links dracônicos
        - "red_card_played": Blaze Headlong com carta vermelha prévia jogada
        - "no_prior_red_card": Blaze Headlong sem carta vermelha prévia
        - "combo_active": Pré-requisito de combo satisfeito pelo ataque anterior
        - "combo_inactive": Pré-requisito de combo não satisfeito
        - "no_go_again": Não possui Go Again
    """
    clean_name = _extract_card_identifier(card_name).replace(" ", "_").replace("-", "_").replace("'", "")
    base_name = re.sub(r"_(red|yellow|blue)$", "", clean_name)

    # ── 1. Tokens de Arena (Quicken / Agility) ──
    # CR 8.6.1 & CR 8.6.28: Concedem Go Again gratuito ao primeiro ataque da cadeia
    chain_link = int(state.get("currentChainLink", 1))
    combat_chain_links = state.get("combatChainLinks", [])
    combat_chain = state.get("combatChain", [])
    is_first_attack = chain_link <= 1 and len(combat_chain_links) == 0 and len(combat_chain) == 0 and not state.get("activeChainLink")

    player_auras = (state.get("playerAuras") or state.get("myAuras") or []) + (state.get("playerTokens") or state.get("myTokens") or [])
    turn_effects = state.get("currentTurnEffects", [])
    has_quicken = any("quicken" in str(a.get("cardNumber", a.get("name", "")) if isinstance(a, dict) else a).lower() for a in player_auras) or any("quicken" in str(e).lower() for e in turn_effects)
    has_agility = any("agility" in str(a.get("cardNumber", a.get("name", "")) if isinstance(a, dict) else a).lower() for a in player_auras) or any("agility" in str(e).lower() for e in turn_effects)

    # Identificação de condicionais
    is_conditional_draconic = any(d in clean_name for d in DRACONIC_CHAIN_REQUIREMENT_CARDS) or base_name in DRACONIC_CHAIN_REQUIREMENT_CARDS
    is_blaze_headlong = "blaze_headlong" in clean_name or base_name == "blaze_headlong"
    is_ninja_combo = base_name in NINJA_COMBO_REQUIREMENTS or clean_name in NINJA_COMBO_REQUIREMENTS

    # ── 2. Go Again Natural ──
    if not (is_conditional_draconic or is_blaze_headlong or is_ninja_combo):
        # Verifica hand_info se fornecido
        if hand_info and hand_info.get("has_go_again"):
            return True, "natural_go_again"

        # Verifica GeneratedGoAgain
        natural_cards = _load_natural_go_again_cards()
        if (
            clean_name in natural_cards
            or f"{clean_name}_red" in natural_cards
            or f"{clean_name}_yellow" in natural_cards
            or f"{clean_name}_blue" in natural_cards
            or base_name in natural_cards
            or f"{base_name}_red" in natural_cards
        ):
            return True, "natural_go_again"

        # Verifica cards_db oficial
        db = _load_cards_db()
        entry = (
            db.get(clean_name)
            or db.get(f"{clean_name}_red")
            or db.get(f"{clean_name}_yellow")
            or db.get(f"{clean_name}_blue")
            or db.get(base_name)
            or db.get(f"{base_name}_red")
        )
        if entry and entry.get("has_go_again"):
            return True, "natural_go_again"

    # Token Quicken / Agility no 1º ataque da cadeia concede Go Again
    if (has_quicken or has_agility) and is_first_attack:
        return True, "token_granted"

    # ── 3. Links Dracônicos ──
    if is_conditional_draconic:
        prior_links = list(state.get("combatChainLinks") or [])
        if not prior_links and state.get("combatChain"):
            prior_links = list(state.get("combatChain") or [])
        active_link = state.get("activeChainLink")
        if active_link and isinstance(active_link, dict) and active_link not in prior_links:
            if active_link.get("cardNumber") or active_link.get("name") or active_link.get("cardID"):
                prior_links.append(active_link)

        draconic_count = sum(1 for link in prior_links if is_draconic_card(link))
        if "draconicLinksCount" in state:
            draconic_count = max(draconic_count, int(state["draconicLinksCount"]))
        if "draconicChainLinks" in state:
            draconic_count = max(draconic_count, int(state["draconicChainLinks"]))

        if draconic_count >= 2:
            return True, "draconic_threshold_met"
        return False, "insufficient_draconic_links"

    # ── 4. Cartas Vermelhas (Blaze Headlong) ──
    if is_blaze_headlong:
        if has_prior_red_card_played(state):
            return True, "red_card_played"
        return False, "no_prior_red_card"

    # ── 5. Combos de Ninja ──
    if is_ninja_combo:
        req_triggers = NINJA_COMBO_REQUIREMENTS.get(base_name) or NINJA_COMBO_REQUIREMENTS.get(clean_name) or []

        prev_attack = None
        active_link = state.get("activeChainLink")
        chain_links = list(state.get("combatChainLinks") or []) + list(state.get("combatChain") or [])
        if active_link and isinstance(active_link, dict) and (active_link.get("cardNumber") or active_link.get("name")):
            prev_attack = active_link
        elif chain_links:
            prev_attack = chain_links[-1]
        elif state.get("lastAttack") or state.get("lastAttackName"):
            prev_attack = state.get("lastAttack") or state.get("lastAttackName")

        if prev_attack:
            prev_name = _extract_card_identifier(prev_attack).replace(" ", "_").replace("-", "_").replace("'", "")
            prev_base = re.sub(r"_(red|yellow|blue)$", "", prev_name)
            if any(req in prev_name or req in prev_base for req in req_triggers):
                return True, "combo_active"

        return False, "combo_inactive"

    return False, "no_go_again"
