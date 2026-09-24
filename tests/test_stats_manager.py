import os
import json
import tempfile
import pytest
from stats_manager import canonicalize_deck_name, consolidate_deck_stats

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

def test_elo_calculations():
    import stats
    from stats.elo import expected_score, calculate_k_factor, calculate_elo_ratings

    # 1. Expected score
    e_equal = expected_score(1200, 1200)
    assert round(e_equal, 2) == 0.50

    # Jogador superior tem maior chance esperada
    e_higher = expected_score(1600, 1200)
    assert e_higher > 0.90

    # 2. Dynamic K-factor
    # Vitória contra humano acelera K para 48
    assert calculate_k_factor(matches_played=10, is_human_p1=True, winner_id=2) == 48
    # Partidas iniciais: K=32
    assert calculate_k_factor(matches_played=10, is_human_p1=False, winner_id=1) == 32
    # Partidas intermediárias: K=24
    assert calculate_k_factor(matches_played=50, is_human_p1=False, winner_id=1) == 24
    # Partidas avançadas: K=16
    assert calculate_k_factor(matches_played=150, is_human_p1=False, winner_id=1) == 16

    # 3. New ratings
    # P1 vence
    new_r1, new_r2 = calculate_elo_ratings(1200, 1200, winner_id=1, k=32)
    assert new_r1 == 1216
    assert new_r2 == 1184

    # P2 vence
    new_r1, new_r2 = calculate_elo_ratings(1200, 1200, winner_id=2, k=32)
    assert new_r1 == 1184
    assert new_r2 == 1216

    # Empate
    new_r1, new_r2 = calculate_elo_ratings(1200, 1200, winner_id=0, k=32)
    assert new_r1 == 1200
    assert new_r2 == 1200

    # Re-exportação pelo pacote stats e stats_manager
    assert stats.expected_score == expected_score
    assert stats.calculate_k_factor == calculate_k_factor
    assert stats.calculate_elo_ratings == calculate_elo_ratings


def test_reset_all_elos():
    from stats_manager import reset_all_elos, get_stats_data
    
    res = reset_all_elos()

    # Totais zerados
    assert res["total_matches"] == 0
    assert res["bot1_wins"] == 0
    assert res["bot2_wins"] == 0
    assert res["draws"] == 0
    assert res["bot1_elo"] == 1200
    assert res["bot2_elo"] == 1200
    assert res["recent_matches"] == []

    # Decks mantidos e resetados para 1200
    for d_name, d_info in res.get("deck_stats", {}).items():
        assert d_info["elo"] == 1200
        assert d_info["matches"] == 0
        assert d_info["wins"] == 0
        assert d_info["losses"] == 0
        assert d_info["human_matches"] == 0
        assert d_info["human_wins"] == 0

    # Leitura subsequente do arquivo confirma persistência
    loaded = get_stats_data()
    assert loaded["total_matches"] == 0

