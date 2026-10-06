import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from deck_parser import (
    _load_hero_map,
    HERO_MAP,
    slugify_card_name,
    list_saved_decks,
    validate_deck_against_db,
    parse_deck_text,
    extract_hero_from_deck,
    enrich_deck_metadata,
)
import deck_manager

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

def test_deck_manager_exports_match_facade():
    # Garantir paridade entre deck_manager e deck_parser
    expected_exports = [
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
    for fn_name in expected_exports:
        assert hasattr(deck_manager, fn_name), f"deck_manager missing {fn_name}"
        assert getattr(deck_manager, fn_name) is getattr(sys.modules["deck_parser"], fn_name)

def test_validate_deck_against_db_valid_saved_decks():
    decks = list_saved_decks()
    assert len(decks) > 0
    for d in decks:
        is_valid, errors, meta = validate_deck_against_db(d["data"])
        assert is_valid, f"Deck {d['slug']} failed validation: {errors}"
        assert len(errors) == 0
        assert len(meta["heroes"]) == 1

def test_validate_deck_missing_hero():
    deck = {
        "format": "cc",
        "cards": [
            {"identifier": "sink_below_red", "total": 3},
            {"identifier": "fate_foreseen_red", "total": 3},
        ]
    }
    is_valid, errors, meta = validate_deck_against_db(deck)
    assert not is_valid
    assert any("Nenhum Herói reconhecido" in e for e in errors)

def test_validate_deck_card_copy_limits_and_minimums():
    # CC with > 3 copies
    deck_cc = {
        "format": "cc",
        "cards": [
            {"identifier": "betsy_skin_in_the_game", "total": 1},
            {"identifier": "pile_driver", "total": 1},
            {"identifier": "sink_below_red", "total": 4},
        ] + [{"identifier": "fate_foreseen_red", "total": 3} for _ in range(20)]
    }
    is_valid, errors, meta = validate_deck_against_db(deck_cc)
    assert not is_valid
    assert any("excede o limite de 3 cópias" in e for e in errors)

    # Blitz with > 2 copies
    deck_blitz = {
        "format": "blitz",
        "cards": [
            {"identifier": "betsy_skin_in_the_game", "total": 1},
            {"identifier": "pile_driver", "total": 1},
            {"identifier": "sink_below_red", "total": 3},
        ]
    }
    is_valid_b, errors_b, _ = validate_deck_against_db(deck_blitz)
    assert not is_valid_b
    assert any("excede o limite de 2 cópias" in e for e in errors_b)

def test_extract_hero_from_deck_both_signatures():
    # Passando dict
    d = {"hero_name": "Betsy Test", "cards": []}
    assert extract_hero_from_deck(d) == "Betsy Test"

    # Passando lista de cartas
    cards = [{"identifier": "betsy_skin_in_the_game", "total": 1}]
    hero = extract_hero_from_deck(cards)
    assert "Betsy" in hero


def test_delete_saved_deck_slug_variants(tmp_path):
    """Garante que delete_saved_deck aceita slug simples, com .json ou com decks/."""
    from deck_manager.repository import save_deck_to_workspace, delete_saved_deck, list_saved_decks
    test_deck = {
        "name": "Temp Test Hero",
        "format": "blitz",
        "cards": [{"identifier": "kayo_armed_and_dangerous", "total": 1}]
    }
    # Cria deck no diretório temporário
    base_dir = str(tmp_path)
    res = save_deck_to_workspace(test_deck, base_dir=base_dir)
    slug = res["slug"]
    assert slug == "temp_test_hero"

    # Testa exclusão passando slug com .json
    assert delete_saved_deck(f"{slug}.json", base_dir=base_dir) is True
    # Uma segunda tentativa deve retornar False
    assert delete_saved_deck(slug, base_dir=base_dir) is False

    # Recria e testa com prefixo decks/
    save_deck_to_workspace(test_deck, base_dir=base_dir)
    assert delete_saved_deck(f"decks/{slug}.json", base_dir=base_dir) is True

