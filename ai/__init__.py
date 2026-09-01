"""
Módulo de Inteligência Artificial para Flesh and Blood (FaB Talishar).
Inclui PolicyEngine tático, simulador de combate e estratégias especializadas por classe de herói.
"""

from .policy_engine import PolicyEngine
from .hero_strategies import get_hero_strategy, HeroStrategy

__all__ = ["PolicyEngine", "get_hero_strategy", "HeroStrategy"]
