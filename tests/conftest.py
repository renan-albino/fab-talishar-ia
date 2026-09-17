"""Fixtures compartilhadas para a suíte de testes do FaB Talishar AI."""

import pytest
from ai.policy.engine import PolicyEngine


def make_policy_engine(hero_name="generic", num_mcts_sims=0, use_gpu=False, **kwargs):
    """Factory para PolicyEngine com defaults seguros para testes unitários.

    Uso:
        pe = make_policy_engine()                           # genérico, sem MCTS
        pe = make_policy_engine("rhinar")                   # herói específico
        pe = make_policy_engine("marlinn", num_mcts_sims=5) # com MCTS
    """
    return PolicyEngine(hero_name=hero_name, num_mcts_sims=num_mcts_sims, use_gpu=use_gpu, **kwargs)


@pytest.fixture
def policy_engine():
    """PolicyEngine genérico sem MCTS para testes rápidos."""
    return make_policy_engine()
