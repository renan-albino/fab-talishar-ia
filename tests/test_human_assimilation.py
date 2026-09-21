"""
tests/test_human_assimilation.py
================================
Testes para o sistema de aprendizado acelerado com humanos, assimilação pós-partida
e motor de recomendações de heróis para treino humano.
"""

import os
import time
import pytest
from unittest.mock import patch

from config.settings import SETTINGS
from ai.training.assimilation import (
    get_assimilation_status,
    clear_assimilation_status,
    trigger_human_match_assimilation,
    STATUS_FILE,
)
from stats.recommendations import get_hero_training_recommendations


def test_human_weight_multipliers_configured():
    """Valida que os multiplicadores de peso para partidas humanas estão configurados e coerentes."""
    assert hasattr(SETTINGS, "human_win_sample_weight")
    assert hasattr(SETTINGS, "human_loss_sample_weight")
    assert hasattr(SETTINGS, "human_post_match_training_steps")

    assert SETTINGS.human_win_sample_weight >= 2.0
    assert SETTINGS.human_loss_sample_weight >= SETTINGS.human_win_sample_weight
    assert SETTINGS.human_post_match_training_steps >= 5


def test_assimilation_status_lifecycle(tmp_path):
    """Testa o ciclo de vida do arquivo de status de assimilação."""
    mock_status_file = str(tmp_path / ".test_assimilation.json")

    with patch("ai.training.assimilation.STATUS_FILE", mock_status_file):
        # 1. Arquivo não existe -> idle
        st = get_assimilation_status()
        assert st["status"] == "idle"

        # 2. Inicia assimilação
        trigger_human_match_assimilation(room_id="room_999", bot_player_id=2, winner_id=1)
        st = get_assimilation_status()
        assert st["status"] in ("assimilating", "completed")
        assert st["room_id"] == "room_999"

        # 3. Limpeza de status
        clear_assimilation_status()
        st = get_assimilation_status()
        assert st["status"] == "idle"


def test_hero_training_recommendations():
    """Testa a identificação de gargalos de ELO, baixa amostragem e inéditos humanos."""
    sample_stats = {
        "Kassai": {
            "matches": 20,
            "wins": 5,      # 25% WR -> Gargalo de ELO
            "losses": 15,
            "human_matches": 2,
        },
        "Dash IO": {
            "matches": 30,
            "wins": 25,     # 83% WR
            "losses": 5,
            "human_matches": 0,  # Inédito contra humano
        },
        "Teklovossen": {
            "matches": 2,   # Baixa amostragem (< 5)
            "wins": 1,
            "losses": 1,
            "human_matches": 0,
        },
    }

    saved_decks = [
        {"slug": "kassai", "name": "Kassai", "hero": "Kassai"},
        {"slug": "dash_io", "name": "Dash IO", "hero": "Dash I/O"},
        {"slug": "teklovossen", "name": "Teklovossen", "hero": "Teklovossen"},
        {"slug": "dorinthea", "name": "Dorinthea", "hero": "Dorinthea"},  # Novo, sem partidas
    ]

    recs = get_hero_training_recommendations(sample_stats, saved_decks)

    # 1. Valida detecção de gargalo
    bottlenecks = [r["deck"] for r in recs["bottlenecks"]]
    assert "Kassai" in bottlenecks

    # 2. Valida inédito humano
    untested = [r["deck"] for r in recs["untested_human"]]
    assert "Dash IO" in untested

    # 3. Valida baixa amostragem (Teklovossen + Dorinthea)
    under = [r["deck"] for r in recs["under_sampled"]]
    assert "Teklovossen" in under
    assert "Dorinthea" in under

    # 4. Valida top picks consolidados
    assert len(recs["top_picks"]) >= 3
