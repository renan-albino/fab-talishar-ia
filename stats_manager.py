"""
stats_manager.py
================
Fachada retrocompatível para o pacote modular `stats`.
Re-exporta todas as funções de ELO, normalização de decks, persistência e sincronização.
"""

from stats import (
    BASE_DIR, CANONICAL_DECK_NAMES, DECKS_DIR, STATS_FILE,
    calculate_elo_ratings, calculate_k_factor,
    canonicalize_deck_name, clean_stalled_matches, consolidate_deck_stats, delete_deck_stat,
    expected_score, get_expected_starting_health, get_stats_data,
    reset_all_elos, reset_stats, sync_training_matches, update_match_result,
    get_hero_training_recommendations,
)

__all__ = [
    "BASE_DIR", "CANONICAL_DECK_NAMES", "DECKS_DIR", "STATS_FILE",
    "calculate_elo_ratings", "calculate_k_factor",
    "canonicalize_deck_name", "clean_stalled_matches", "consolidate_deck_stats", "delete_deck_stat",
    "expected_score", "get_expected_starting_health", "get_stats_data",
    "reset_all_elos", "reset_stats", "sync_training_matches", "update_match_result",
    "get_hero_training_recommendations",
]
