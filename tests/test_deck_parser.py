import os
import pytest
from deck_parser import (
    _load_hero_map,
    HERO_MAP,
    slugify_card_name,
    list_saved_decks,
    validate_deck_against_db,
)

def test_hero_map_loaded():
    hero_map = _load_hero_map()
    assert isinstance(hero_map, dict)
    assert len(hero_map) > 0
    assert "betsy" in hero_map or "kassai" in hero_map

def test_slugify_card_name_pitch_and_accents():
    # Pitch extraction
    assert slugify_card_name("Sink Below (red)") == "sink_below_red"
    assert slugify_card_name("Sink Below (1)") == "sink_below_red"
    assert slugify_card_name("Sink Below (blue)") == "sink_below_blue"
    assert slugify_card_name("Sink Below (3)") == "sink_below_blue"
    assert slugify_card_name("Sink Below (yellow)") == "sink_below_yellow"
    assert slugify_card_name("Sink Below (2)") == "sink_below_yellow"

    # Accents removal
    assert slugify_card_name("Élan Macho (red)") == "elan_macho_red"

    # Hero resolution
    hero_slug = slugify_card_name("Betsy, Skin in the Game", is_hero=True)
    assert hero_slug == HERO_MAP.get("betsy", hero_slug)

def test_list_saved_decks():
    decks = list_saved_decks()
    assert isinstance(decks, list)
    assert len(decks) > 0
    # Check that at least one deck has name and format
    first_deck = decks[0]
    assert "name" in first_deck
    assert "format" in first_deck
