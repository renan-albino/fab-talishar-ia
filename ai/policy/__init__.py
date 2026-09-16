"""
ai/policy/__init__.py
=====================
Pacote modular de políticas de decisão tática e poda para Flesh and Blood.
"""

from .constants import (
    _get_cards_db,
    _load_cards_db,
    _load_ability_costs,
    get_on_hit_threat,
    DANGEROUS_ON_HITS,
    ON_HIT_THREAT_VALUES,
    ALL_FAB_WEAPONS,
    WEAPON_KEYWORDS,
    KNOWN_WEAPON_COSTS,
)
from .card_evaluator import (
    extract_card_info,
    calculate_available_resources,
    get_weapon_cost,
    get_all_known_zone_cards,
)
from .attack_pruner import select_best_attack
from .defense_pruner import select_defense_blocks
from .pitch_pruner import select_best_pitch_card
from .arsenal_pruner import select_arsenal_card
from .engine import PolicyEngine

__all__ = [
    "PolicyEngine",
    "_get_cards_db",
    "_load_cards_db",
    "_load_ability_costs",
    "get_on_hit_threat",
    "DANGEROUS_ON_HITS",
    "ON_HIT_THREAT_VALUES",
    "ALL_FAB_WEAPONS",
    "WEAPON_KEYWORDS",
    "KNOWN_WEAPON_COSTS",
    "extract_card_info",
    "calculate_available_resources",
    "get_weapon_cost",
    "get_all_known_zone_cards",
    "select_best_attack",
    "select_defense_blocks",
    "select_best_pitch_card",
    "select_arsenal_card",
]
