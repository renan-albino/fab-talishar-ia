"""
tests/test_matchup_modes_and_cli.py
===================================
Testes unitários para validar os modos de pareamento:
- mirror: confrontos estritamente espelhados (A vs A, B vs B, C vs C)
- cross: confrontos todos-contra-todos (A vs B, B vs C, etc.)
- mixed: combinação de espelhados e cruzados
- Integração de CLI e custom_config no orchestrator
"""

import pytest
from ai.training.matchup_engine import RoundRobinMatchupEngine
from ai.training.orchestrator import GPUTrainingOrchestrator


def test_matchup_engine_mirror_mode():
    """Valida que o modo mirror gera exclusivamente pares espelhados."""
    engine = RoundRobinMatchupEngine(seed=42)
    pool = ["jarl", "levia", "cindra"]

    seen_pairs = set()
    for _ in range(9):
        p1, p2 = engine.next_pair(pool, mode="mirror")
        assert p1 == p2, f"Modo mirror gerou par não-espelhado: {p1} vs {p2}"
        assert p1 in pool
        seen_pairs.add((p1, p2))

    # Garante que todos os 3 heróis foram contemplados
    assert seen_pairs == {("jarl", "jarl"), ("levia", "levia"), ("cindra", "cindra")}


def test_matchup_engine_cross_mode():
    """Valida que o modo cross nunca gera pares espelhados quando len(pool) > 1."""
    engine = RoundRobinMatchupEngine(seed=42)
    pool = ["jarl", "levia", "cindra"]

    for _ in range(12):
        p1, p2 = engine.next_pair(pool, mode="cross")
        assert p1 != p2, f"Modo cross gerou par espelhado: {p1} vs {p2}"
        assert p1 in pool and p2 in pool


def test_matchup_engine_mixed_mode():
    """Valida que o modo mixed inclui tanto pares espelhados quanto cruzados."""
    engine = RoundRobinMatchupEngine(seed=42)
    pool = ["jarl", "levia"]

    pairs = [engine.next_pair(pool, mode="mixed") for _ in range(8)]
    has_mirror = any(p1 == p2 for p1, p2 in pairs)
    has_cross = any(p1 != p2 for p1, p2 in pairs)

    assert has_mirror, "Modo mixed deveria conter partidas espelhadas"
    assert has_cross, "Modo mixed deveria conter partidas cruzadas"


def test_orchestrator_custom_decks_and_mirror_mode():
    """Valida que o orchestrator respeita training_decks e matchup_mode passados em custom_config."""
    GPUTrainingOrchestrator.reset_instance()
    orch = GPUTrainingOrchestrator()
    orch._extra = {
        "training_decks": ["jarl", "levia", "cindra"],
        "matchup_mode": "mirror",
    }

    assert orch.config["training_decks"] == ["jarl", "levia", "cindra"]
    assert orch.config["matchup_mode"] == "mirror"

    # Simula 6 chamadas de _next_deck_pair
    for _ in range(6):
        d1, d2 = orch._next_deck_pair(orch.config["training_decks"])
        assert d1 == d2
        assert d1 in ["jarl", "levia", "cindra"]

    GPUTrainingOrchestrator.reset_instance()
