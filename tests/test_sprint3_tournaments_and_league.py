"""
Testes unitários automatizados para a Sprint 3:
- HeadlessSelfPlayLoop com opp_model (duelo direto entre dois modelos/checkpoints)
- TournamentManager: Sistema Suíço oficial, pareamento sem rematches e suporte a Bye
- Cálculo exato de desempates oficiais (Buchholz e Sonneborn-Berger)
- Rating ELO real em torneios
- Self-Play League com amostragem de oponentes históricos no GPUTrainingOrchestrator
"""

import pytest
import os
import json
import torch
import numpy as np
from unittest.mock import MagicMock, patch

from ai.model import FaBPolicyValueNetwork
from ai.training.headless_env import HeadlessSelfPlayLoop
from stats.tournament_manager import TournamentManager
from ai.training.orchestrator import GPUTrainingOrchestrator


def test_headless_opp_model_dueling():
    """Valida execução headless entre duas redes neurais distintas (p1_model vs opp_model)."""
    m1 = FaBPolicyValueNetwork()
    m2 = FaBPolicyValueNetwork()
    m1.eval()
    m2.eval()

    env = HeadlessSelfPlayLoop(model=m1, opp_model=m2, mcts_sims=2, device="cpu")
    assert env.model is m1
    assert env.opp_model is m2

    trajectory, winner = env.play_game("kassai", "boltyn")
    assert winner in (0, 1, 2)
    assert len(trajectory) > 0
    assert trajectory[0][0].shape == (832,)


def test_swiss_tournament_multi_round_progression(tmp_path):
    """Valida progressão multi-rodadas do torneio suíço sem rematches."""
    decks = [
        {"id": "deckA", "name": "Deck A", "hero": "Kassai", "points": 0, "wins": 0, "losses": 0, "draws": 0, "byes": 0, "elo": 1200, "opponents": [], "buchholz": 0.0, "sonneborn_berger": 0.0},
        {"id": "deckB", "name": "Deck B", "hero": "Boltyn", "points": 0, "wins": 0, "losses": 0, "draws": 0, "byes": 0, "elo": 1200, "opponents": [], "buchholz": 0.0, "sonneborn_berger": 0.0},
        {"id": "deckC", "name": "Deck C", "hero": "Dorinthea", "points": 0, "wins": 0, "losses": 0, "draws": 0, "byes": 0, "elo": 1200, "opponents": [], "buchholz": 0.0, "sonneborn_berger": 0.0},
        {"id": "deckD", "name": "Deck D", "hero": "Kayo", "points": 0, "wins": 0, "losses": 0, "draws": 0, "byes": 0, "elo": 1200, "opponents": [], "buchholz": 0.0, "sonneborn_berger": 0.0},
    ]

    with patch("stats.tournament_manager.TournamentManager.load_available_decks", return_value=decks):
        tm = TournamentManager(format_type="swiss", execution_mode="headless", num_rounds=2)
        tm.setup_tournament(["deckA", "deckB", "deckC", "deckD"])

        # Rodada 1
        assert len(tm.matches) == 2
        r1_pairs = {(m["deck1"], m["deck2"]) for m in tm.matches}

        # Simula resultados da R1
        tm.matches[0]["winner"] = "Deck A"
        tm.matches[0]["status"] = "Concluída"
        tm._update_standings(tm.matches[0])

        tm.matches[1]["winner"] = "Deck C"
        tm.matches[1]["status"] = "Concluída"
        tm._update_standings(tm.matches[1])

        # Gera Rodada 2
        tm._generate_swiss_round(2)
        r2_matches = [m for m in tm.matches if m.get("round") == 2]
        assert len(r2_matches) == 2

        # Verifica proibição estrita de rematch
        for m in r2_matches:
            pair = (m["deck1"], m["deck2"])
            rev_pair = (m["deck2"], m["deck1"])
            assert pair not in r1_pairs and rev_pair not in r1_pairs, f"Rematch detectado: {pair}!"


def test_swiss_tournament_bye_for_odd_participants():
    """Valida concessão correta de Bye (+3 pts) para número ímpar de participantes."""
    decks = [
        {"id": f"deck_{i}", "name": f"Deck {i}", "hero": f"Hero {i}", "points": (5 - i) * 3, "wins": 0, "losses": 0, "draws": 0, "byes": 0, "elo": 1200, "opponents": [], "buchholz": 0.0, "sonneborn_berger": 0.0}
        for i in range(5)
    ]

    with patch("stats.tournament_manager.TournamentManager.load_available_decks", return_value=decks):
        tm = TournamentManager(format_type="swiss", num_rounds=2)
        tm.setup_tournament([d["id"] for d in decks])

        # R1: 5 participantes -> 1 Bye e 2 partidas
        bye_matches = [m for m in tm.matches if m.get("is_bye")]
        assert len(bye_matches) == 1
        # O Bye deve ser concedido ao de menor ranking (deck_4)
        assert bye_matches[0]["deck1"] == "deck_4"
        assert bye_matches[0]["winner"] == "Deck 4"
        assert bye_matches[0]["status"] == "Concluída"


def test_buchholz_and_sonneborn_berger_calculation():
    """Valida o cálculo formal de desempate Buchholz e Sonneborn-Berger."""
    tm = TournamentManager(format_type="swiss")
    tm.participants = [
        {"id": "dA", "name": "Deck A", "points": 6, "wins": 2, "losses": 0, "draws": 0, "byes": 0, "elo": 1232, "opponents": ["dB", "dC"]},
        {"id": "dB", "name": "Deck B", "points": 3, "wins": 1, "losses": 1, "draws": 0, "byes": 0, "elo": 1200, "opponents": ["dA", "dD"]},
        {"id": "dC", "name": "Deck C", "points": 3, "wins": 1, "losses": 1, "draws": 0, "byes": 0, "elo": 1200, "opponents": ["dD", "dA"]},
        {"id": "dD", "name": "Deck D", "points": 0, "wins": 0, "losses": 2, "draws": 0, "byes": 0, "elo": 1168, "opponents": ["dC", "dB"]},
    ]
    tm.matches = [
        {"deck1": "dA", "deck2": "dB", "winner": "Deck A", "status": "Concluída", "is_bye": False},
        {"deck1": "dC", "deck2": "dD", "winner": "Deck C", "status": "Concluída", "is_bye": False},
        {"deck1": "dA", "deck2": "dC", "winner": "Deck A", "status": "Concluída", "is_bye": False},
        {"deck1": "dB", "deck2": "dD", "winner": "Deck B", "status": "Concluída", "is_bye": False},
    ]

    tm._calculate_tie_breakers()

    p_a = next(p for p in tm.participants if p["id"] == "dA")
    p_b = next(p for p in tm.participants if p["id"] == "dB")

    # Buchholz(A): pontos de dB(3) + dC(3) = 6.0
    assert p_a["buchholz"] == 6.0
    # Sonneborn-Berger(A): venceu dB(3) e dC(3) = 6.0
    assert p_a["sonneborn_berger"] == 6.0

    # Buchholz(B): pontos de dA(6) + dD(0) = 6.0
    assert p_b["buchholz"] == 6.0
    # Sonneborn-Berger(B): venceu apenas dD(0) = 0.0
    assert p_b["sonneborn_berger"] == 0.0


def test_orchestrator_sample_league_opponent(tmp_path):
    """Valida amostragem de oponentes históricos da liga no orquestrador."""
    GPUTrainingOrchestrator.reset_instance()
    orch = GPUTrainingOrchestrator()

    # League desabilitada
    assert orch._sample_league_opponent({"league_play": False}) is None

    # League habilitada sem checkpoints
    cfg_empty = {"league_play": True, "league_prob": 1.0, "checkpoint_dir": str(tmp_path)}
    assert orch._sample_league_opponent(cfg_empty) is None

    # Cria checkpoint falso
    fake_net = FaBPolicyValueNetwork()
    ckpt_file = str(tmp_path / "model_checkpoint_ep1.pt")
    torch.save(fake_net.state_dict(), ckpt_file)

    cfg_with_ckpt = {"league_play": True, "league_prob": 1.0, "checkpoint_dir": str(tmp_path)}
    opp = orch._sample_league_opponent(cfg_with_ckpt)
    assert opp is not None
    assert isinstance(opp, FaBPolicyValueNetwork)
    GPUTrainingOrchestrator.reset_instance()
