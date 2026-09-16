"""
ai/policy_engine.py
===================
Fachada de compatibilidade retroativa para o pacote modular ai.policy.
Todos os componentes foram modularizados em ai/policy/:
  - ai.policy.constants
  - ai.policy.card_evaluator
  - ai.policy.attack_pruner
  - ai.policy.defense_pruner
  - ai.policy.pitch_pruner
  - ai.policy.arsenal_pruner
  - ai.policy.engine
"""

from .policy import (
    PolicyEngine,
    _get_cards_db,
    _load_cards_db,
    _load_ability_costs,
    get_on_hit_threat,
    DANGEROUS_ON_HITS,
    ON_HIT_THREAT_VALUES,
    ALL_FAB_WEAPONS,
    WEAPON_KEYWORDS,
    KNOWN_WEAPON_COSTS,
    extract_card_info,
    calculate_available_resources,
    get_weapon_cost,
    get_all_known_zone_cards,
    select_best_attack,
    select_defense_blocks,
    select_best_pitch_card,
    select_arsenal_card,
)

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
