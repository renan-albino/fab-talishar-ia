import pytest
import os
import json
from unittest.mock import patch, MagicMock
from stats.tournament_manager import TournamentManager

@pytest.fixture
def mock_decks():
    return [
        {"id": "deckA", "name": "Deck A", "hero": "Hero A", "format": "cc", "file": "decks/deckA.json", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
        {"id": "deckB", "name": "Deck B", "hero": "Hero B", "format": "cc", "file": "decks/deckB.json", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
        {"id": "deckC", "name": "Deck C", "hero": "Hero C", "format": "cc", "file": "decks/deckC.json", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
        {"id": "deckD", "name": "Deck D", "hero": "Hero D", "format": "cc", "file": "decks/deckD.json", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
    ]

@patch("stats.tournament_manager.TournamentManager.load_available_decks")
def test_swiss_bracket_creation(mock_load, mock_decks):
    mock_load.return_value = mock_decks
    tm = TournamentManager(format_type="swiss")
    
    # Simulate points for swiss pairing
    mock_decks[0]["points"] = 6
    mock_decks[1]["points"] = 3
    mock_decks[2]["points"] = 3
    mock_decks[3]["points"] = 0
    
    tm.setup_tournament(["deckA", "deckB", "deckC", "deckD"])
    
    # It should have generated matches for round 1 based on points (deckA vs deckB, deckC vs deckD)
    assert len(tm.matches) == 2
    assert tm.matches[0]["deck1"] == "deckA"
    assert tm.matches[0]["deck2"] == "deckB"
    assert tm.matches[1]["deck1"] == "deckC"
    assert tm.matches[1]["deck2"] == "deckD"

def test_update_standings_win():
    tm = TournamentManager()
    tm.participants = [
        {"id": "deckA", "name": "Deck A", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
        {"id": "deckB", "name": "Deck B", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
    ]
    match = {
        "deck1_name": "Deck A",
        "deck2_name": "Deck B",
        "winner": "Deck A"
    }
    tm._update_standings(match)
    
    assert tm.participants[0]["wins"] == 1
    assert tm.participants[0]["points"] == 3
    assert tm.participants[0]["elo"] > 1200
    
    assert tm.participants[1]["losses"] == 1
    assert tm.participants[1]["points"] == 0
    assert tm.participants[1]["elo"] < 1200

def test_update_standings_draw():
    tm = TournamentManager()
    tm.participants = [
        {"id": "deckA", "name": "Deck A", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
        {"id": "deckB", "name": "Deck B", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
    ]
    match = {
        "deck1_name": "Deck A",
        "deck2_name": "Deck B",
        "winner": "Empate"
    }
    tm._update_standings(match)
    
    assert tm.participants[0]["draws"] == 1
    assert tm.participants[0]["points"] == 1
    assert tm.participants[0]["elo"] == 1200
    
    assert tm.participants[1]["draws"] == 1
    assert tm.participants[1]["points"] == 1
    assert tm.participants[1]["elo"] == 1200

@patch("stats.tournament_manager.subprocess.Popen")
@patch("stats.tournament_manager.stats_manager.update_match_result")
@patch("stats.tournament_manager.time.sleep")
def test_stat_manager_timeout_update(mock_sleep, mock_update, mock_popen):
    tm = TournamentManager()
    tm.participants = [
        {"id": "deckA", "name": "Deck A", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
        {"id": "deckB", "name": "Deck B", "points": 0, "wins": 0, "losses": 0, "draws": 0, "elo": 1200},
    ]
    match = {
        "id": 1,
        "deck1": "deckA",
        "deck2": "deckB",
        "deck1_name": "Deck A",
        "deck2_name": "Deck B",
    }
    
    mock_process = MagicMock()
    mock_process.poll.return_value = None  # simulate timeout
    mock_popen.return_value = mock_process
    
    # We also mock time.time to exit the while loop immediately
    with patch("stats.tournament_manager.time.time", side_effect=[0, 150]):
        tm.run_single_match(match)
        
    assert match["winner"] == "Empate"
    mock_update.assert_called_once()
    args, kwargs = mock_update.call_args
    assert kwargs["winner_id"] == 0
    assert kwargs["is_invalid_match"] == True
    assert kwargs["invalid_reason"] == "Timeout do Torneio"
