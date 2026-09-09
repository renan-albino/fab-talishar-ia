import os
import json
import tempfile
import pytest
from stats_manager import canonicalize_deck_name, consolidate_deck_stats
from ai.atomic_io import atomic_json_save

def test_canonicalize_deck_name():
    assert canonicalize_deck_name("dash_io") == "Dash IO"
    assert canonicalize_deck_name("dash io") == "Dash IO"
    assert canonicalize_deck_name("gravy_bones") == "Gravy Bones"
    assert canonicalize_deck_name("marlynn") == "Marlinn"
    assert canonicalize_deck_name("kassai_cintari") == "Kassai Cintari"
    assert canonicalize_deck_name("👤 Humano (Você)") == "👤 Humano (Você)"

def test_consolidate_deck_stats():
    deck_stats = {
        "dash_io": {"matches": 10, "wins": 6, "losses": 4, "elo": 1300},
        "Dash IO": {"matches": 10, "wins": 4, "losses": 6, "elo": 1200}
    }
    consolidated, had_dups = consolidate_deck_stats(deck_stats)
    assert had_dups is True
    assert "Dash IO" in consolidated
    assert len(consolidated) == 1
    info = consolidated["Dash IO"]
    assert info["matches"] == 20
    assert info["wins"] == 10
    assert info["losses"] == 10
    # Weighted Elo: (1300*10 + 1200*10) / 20 = 1250
    assert info["elo"] == 1250

def test_atomic_json_save():
    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(tmp_dir, "test_stats.json")
        sample_data = {"test_key": "test_val", "count": 42}
        
        atomic_json_save(sample_data, target_file)
        
        assert os.path.exists(target_file)
        with open(target_file, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded == sample_data
