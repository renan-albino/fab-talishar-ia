"""
Módulo de Inteligência Artificial para Flesh and Blood (FaB Talishar).
Inclui PolicyEngine tático, simulador de combate e estratégias especializadas por classe de herói.
"""

__all__ = ["PolicyEngine", "get_hero_strategy", "HeroStrategy"]

def __getattr__(name):
    if name == "PolicyEngine":
        from .policy_engine import PolicyEngine
        return PolicyEngine
    if name == "get_hero_strategy":
        from .hero_strategies import get_hero_strategy
        return get_hero_strategy
    if name == "HeroStrategy":
        from .hero_strategies import HeroStrategy
        return HeroStrategy
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
