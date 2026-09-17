"""
stats
=====
Pacote de telemetria, normalização de decks, persistência com locks e cálculo de ELO.
"""

from stats.deck_names import (
    CANONICAL_DECK_NAMES,
    DECKS_DIR,
    canonicalize_deck_name,
    consolidate_deck_stats,
    get_expected_starting_health,
)
from stats.elo import (
    calculate_elo_ratings,
    calculate_k_factor,
    expected_score,
)
from stats.storage import (
    BASE_DIR,
    STATS_FILE,
    delete_deck_stat,
    get_stats_data,
    reset_all_elos,
    reset_stats,
    update_match_result,
)
from stats.sync import (
    clean_stalled_matches,
    sync_training_matches,
)

__all__ = [
    "CANONICAL_DECK_NAMES",
    "DECKS_DIR",
    "BASE_DIR",
    "STATS_FILE",
    "canonicalize_deck_name",
    "consolidate_deck_stats",
    "get_expected_starting_health",
    "expected_score",
    
    "calculate_k_factor",
    
    "calculate_elo_ratings",
    
    "get_stats_data",
    "update_match_result",
    "delete_deck_stat",
    "reset_stats",
    "reset_all_elos",
    "sync_training_matches",
    "clean_stalled_matches",
]
