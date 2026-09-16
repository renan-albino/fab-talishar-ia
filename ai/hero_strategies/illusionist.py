"""
ai/hero_strategies/illusionist.py
=================================
Estratégia para a classe Illusionist (Prism, Dromai, Enigma, Pleiades, Zyggy, etc.).
Heralds, Phantasm, dragões e auras de suporte.
"""

from functools import lru_cache
from typing import Set
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class IllusionistStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Illusionist (Prism, Dromai, Enigma, Pleiades, Zyggy, etc.).
    Heralds, Phantasm, dragões e auras de suporte.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["herald", "phantasm", "miragai", "kyloria", "cromai", "spectral", "ward"]):
            score += 4.5
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 4.0 + (2.0 if floating_res >= 1 else 0.0)
        return score

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Illusionist survival mode: blocking critical or fatal damage"
            )

        heralds = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["herald", "phantasm"])]
        if heralds and my_hp >= 10 and not has_dangerous_on_hit:
            h_name = str(heralds[0].get("cardNumber") or heralds[0].get("name", ""))
            reserved: Set[str] = {h_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="ILLUSIONIST_HERALD_PRESSURE",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["herald_attack"],
                offensive_potential=float(heralds[0].get("power", 5)),
                reason=f"Illusionist plan: holding {h_name} for soul charge and herald pressure"
            )

        return super().analyze_turn_plan(state)
