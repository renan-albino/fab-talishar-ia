"""
ai/hero_strategies/brute.py
===========================
Estratégia para a classe Brute (Rhinar, Kayo, Levia, Baalghor, etc.).
Prioriza cartas com Poder 6+ para ativar Intimidate, Beat Chest e pivot ofensivo.
"""

from functools import lru_cache
from typing import Set, Optional
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class BruteStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Brute.
    Foco em manter cartas de poder 6+ na mão para pivot, descarte de habilidades
    e intimidar a mão do oponente.
    """
    is_heavy_hero: bool = True
    intellect: int = 3

    def get_intellect(self, state: Optional[dict] = None) -> int:
        """Retorna o Intelecto do herói Brute (CR 4.3.2), padrão 3 para heróis Brute (Rhinar, Kayo)."""
        if state and ("playerIntellect" in state or "intellect" in state):
            return int(state.get("playerIntellect", state.get("intellect", self.intellect)))
        return self.intellect

    def has_heavy_attack(self, card_info: dict) -> bool:
        return int(card_info.get("power", 0)) >= 6

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if power >= 6:
            score += 6.0
        if any(w in c_low for w in ["intimidate", "bloodrush", "beat_chest", "pummel", "swing_big", "pack_hunt", "scabskin", "wreck_havoc"]):
            score += 5.0
        if has_go_again:
            score += 4.0
        score -= cost * 0.4
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        score = float(pitch) * 4.5
        if power >= 6:
            score -= 3.0
        if pitch == 3:
            score += 4.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        if pitch == 1 and power >= 6:
            return -20.0
        return float(block_val) * 2.0 - (power * 0.5)

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 4.0 + (2.0 if floating_res >= 1 else 0.0)
        if not has_hand_attacks:
            score += 3.5
        return score

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        arsenal = state.get("playerArsenal", [])
        all_cards = list(hand) + list(arsenal)
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        floating_res = int(state.get("playerPitchCount", 0))
        if floating_res == 0:
            resources = state.get("playerResources", [0, 0])
            floating_res = int(resources[0]) if isinstance(resources, list) and resources else 0

        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand, floating_res):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Brute survival mode: blocking incoming lethal or critical damage"
            )

        # PIVOT_BRUTE_SMASH: Ataque de poder 6+ com pitch disponível
        if my_hp >= 10 and not has_dangerous_on_hit:
            smash_card = None
            for c in all_cards:
                power = int(c.get("power", 0))
                if power >= 6 or self.has_heavy_attack(c):
                    smash_card = c
                    break

            if smash_card is not None:
                cost = int(smash_card.get("cost", 0))
                needed_pitch = max(0, cost - floating_res)
                pitch_card = None
                for c in hand:
                    if c is smash_card:
                        continue
                    if int(c.get("pitch", 1)) >= needed_pitch:
                        pitch_card = c
                        break

                if needed_pitch == 0 or pitch_card is not None:
                    s_name = str(smash_card.get("cardNumber") or smash_card.get("name", ""))
                    reserved: Set[str] = {s_name}
                    if pitch_card is not None:
                        reserved.add(str(pitch_card.get("cardNumber") or pitch_card.get("name", "")))

                    reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
                    max_blocks = max(0, len(hand) - len(reserved_in_hand))
                    return TurnPlan(
                        plan_type="PIVOT_BRUTE_SMASH",
                        reserved_card_names=reserved,
                        can_absorb_damage=True,
                        max_block_cards=max_blocks,
                        offensive_potential=float(smash_card.get("power", 6)),
                        reason=f"Brute pivot smash: holding 6+ power attack {s_name} and pitch for aggressive turn"
                    )

        return super().analyze_turn_plan(state)
