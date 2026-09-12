"""
ai/hero_strategies/ninja.py
===========================
Estratégia para a classe Ninja (Katsu, Ira, Fai, Benji, Zen, Cindra, etc.).
Foco em cadeias de combo, starters de custo zero com Go Again e múltiplos ataques rápidos.
"""

from functools import lru_cache
from typing import Set
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class NinjaStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Ninja.
    Prioriza ataques rápidos de baixo custo com Go Again (Kodachi, Leg Tap, Rising Knee, etc.)
    para manter o fluxo de ações e acionar Mask of Momentum.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["surge", "leg_tap", "rising_knee", "roaring_tiger", "combo", "blackout_kick"]):
            score += 4.0
        if has_go_again:
            score += 5.0
        if cost == 0:
            score += 2.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Harmonized Kodachi swings
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
                reason="Ninja survival mode: blocking critical or fatal damage"
            )

        # Identificar starter com Go Again de custo baixo
        starters = []
        follow_ups = []
        for c in hand:
            c_cost = int(c.get("cost", 0))
            c_ga = bool(c.get("has_go_again", False))
            c_pow = int(c.get("power", 0))
            if c_cost == 0 and c_ga and c_pow > 0:
                starters.append(c)
            elif c_pow > 0:
                follow_ups.append(c)

        if starters and follow_ups and my_hp >= 10 and not has_dangerous_on_hit:
            s_card = starters[0]
            f_card = follow_ups[0]
            s_name = str(s_card.get("cardNumber") or s_card.get("name", ""))
            f_name = str(f_card.get("cardNumber") or f_card.get("name", ""))
            reserved: Set[str] = {s_name, f_name}

            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            total_pot = float(s_card.get("power", 0)) + float(f_card.get("power", 0))
            return TurnPlan(
                plan_type="NINJA_COMBO_CHAIN",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["go_again_attack", "combo_attack"],
                offensive_potential=total_pot,
                reason=f"Ninja combo chain plan: holding {s_name} into {f_name}"
            )

        return super().analyze_turn_plan(state)
