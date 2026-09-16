"""
deck_parser.py - Fachada retrocompatível para o pacote deck_manager.
"""

from deck_manager import (
    BASE_DIR,
    DB_PATH,
    DEFAULT_HERO_MAP,
    HERO_MAP,
    load_fab_cards_db,
    validate_deck_against_db,
    load_card_dictionary,
    _load_hero_map,
    slugify_card_name,
    parse_deck_text,
    enrich_deck_metadata,
    extract_hero_from_deck,
    save_deck_to_workspace,
    update_saved_deck,
    list_saved_decks,
    delete_saved_deck,
    set_active_deck,
    load_current_deck,
    normalize_all_saved_decks,
)

__all__ = [
    "BASE_DIR",
    "DB_PATH",
    "DEFAULT_HERO_MAP",
    "HERO_MAP",
    "load_fab_cards_db",
    "validate_deck_against_db",
    "load_card_dictionary",
    "_load_hero_map",
    "slugify_card_name",
    "parse_deck_text",
    "enrich_deck_metadata",
    "extract_hero_from_deck",
    "save_deck_to_workspace",
    "update_saved_deck",
    "list_saved_decks",
    "delete_saved_deck",
    "set_active_deck",
    "load_current_deck",
    "normalize_all_saved_decks",
]
