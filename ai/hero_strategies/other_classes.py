"""
ai/hero_strategies/other_classes.py
===================================
Módulo de re-export para retrocompatibilidade.
As estratégias especializadas foram modularizadas em:
  - mechanologist.py
  - runeblade.py
  - wizard.py
  - illusionist.py
  - assassin.py
  - merchant.py
"""

from .mechanologist import MechanologistStrategy, DashIOStrategy
from .runeblade import RunebladeStrategy, VynnsetStrategy
from .wizard import WizardStrategy, OscilioStrategy
from .illusionist import IllusionistStrategy
from .assassin import AssassinStrategy, ArakniMarionetteStrategy
from .merchant import MerchantStrategy, GravyBonesStrategy

__all__ = [
    "MechanologistStrategy",
    "DashIOStrategy",
    "RunebladeStrategy",
    "VynnsetStrategy",
    "WizardStrategy",
    "OscilioStrategy",
    "IllusionistStrategy",
    "AssassinStrategy",
    "ArakniMarionetteStrategy",
    "MerchantStrategy",
    "GravyBonesStrategy",
]
