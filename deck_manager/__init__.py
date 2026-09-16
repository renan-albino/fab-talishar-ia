"""
deck_manager - Módulo de gerenciamento, parsing, validação e persistência de decks de Flesh and Blood.
"""

from .slugifier import (
    BASE_DIR,
    DB_PATH,
    DEFAULT_HERO_MAP,
    HERO_MAP,
    CARD_NAME_CORRECTIONS,
    CARD_SLUG_ALIASES,
    load_fab_cards_db,
    load_card_dictionary,
    _load_hero_map,
    slugify_card_name,
)
from .parser import (
    parse_deck_text,
    extract_hero_from_deck,
    enrich_deck_metadata,
)
from .validator import (
    validate_deck_against_db,
)
from .repository import (
    save_deck_to_workspace,
    list_saved_decks,
    delete_saved_deck,
    update_saved_deck,
    set_active_deck,
    load_current_deck,
    normalize_all_saved_decks,
)

__all__ = [
    "BASE_DIR",
    "DB_PATH",
    "DEFAULT_HERO_MAP",
    "HERO_MAP",
    "CARD_NAME_CORRECTIONS",
    "CARD_SLUG_ALIASES",
    "load_fab_cards_db",
    "load_card_dictionary",
    "_load_hero_map",
    "slugify_card_name",
    "parse_deck_text",
    "extract_hero_from_deck",
    "enrich_deck_metadata",
    "validate_deck_against_db",
    "save_deck_to_workspace",
    "list_saved_decks",
    "delete_saved_deck",
    "update_saved_deck",
    "set_active_deck",
    "load_current_deck",
    "normalize_all_saved_decks",
]
