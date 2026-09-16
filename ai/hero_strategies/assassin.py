"""
ai/hero_strategies/assassin.py
==============================
Estratégia para a classe Assassin (Arakni, Uzuri, Nuu, Dr. Mortimer, etc.)
e especializações como Arakni, Marionette.
"""

from functools import lru_cache
from typing import Set, Any
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class AssassinStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Assassin (Arakni, Uzuri, Nuu, Dr. Mortimer, etc.).
    Stealth, Contratos de banimento, adagas com Piercing 1 e reações punitivas.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["stealth", "contract", "surgical", "leave_no_witnesses", "erase_face", "sneak", "infiltrate"]):
            score += 5.0
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Spider's Bite / Scale Peeler (Dagger com Piercing 1)
        score = 5.0 + (2.0 if floating_res >= 1 else 0.0)
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
                reason="Assassin survival mode: blocking critical or fatal damage"
            )

        contracts = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["contract", "stealth", "surgical", "leave_no_witnesses"])]
        if contracts and my_hp >= 10 and not has_dangerous_on_hit:
            c_name = str(contracts[0].get("cardNumber") or contracts[0].get("name", ""))
            reserved: Set[str] = {c_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="ASSASSIN_STEALTH_BANISH",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["stealth_attack", "contract"],
                offensive_potential=float(contracts[0].get("power", 4)),
                reason=f"Assassin plan: holding {c_name} for contract banish and silver generation"
            )

        return super().analyze_turn_plan(state)


class ArakniMarionetteStrategy(AssassinStrategy):
    """
    Estratégia especializada para Arakni, Marionette ("Mario").
    Combina contratos de banimento (Leave no Witnesses, Cut from the Same Cloth),
    ataques com adagas com Piercing (Hunters Klaive), ativação punitiva de
    Flick Knives na etapa de reação e recuperação via Codex of Frailty.
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "leave_no_witnesses" in c_low:
            score += 12.0  # On-hit bane todo o arsenal e gera prata
        elif "cut_from_the_same_cloth" in c_low:
            score += 9.0
        elif "art_of_desire" in c_low:
            score += 8.0
        elif "codex_of_frailty" in c_low:
            score += 14.0  # Cria ponder, força descarte no oponente e recupera ataque do cemitério
        elif any(k in c_low for k in ["incision", "kiss_of_death", "meet_madness", "mark_of_the_black_widow"]):
            score += 7.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Hunters Klaive com Piercing 1 é pressão contínua
        score = 6.0 + (3.0 if floating_res >= 2 else 0.0)
        return score

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        if isinstance(state_or_name, dict):
            eq_info = eq_info_or_floating if isinstance(eq_info_or_floating, dict) else kwargs.get("eq_info", {})
            eq_name = str(eq_info.get("cardNumber") or eq_info.get("name", "")).lower()
        else:
            eq_name = str(state_or_name or "").lower()

        if "flick_knives" in eq_name:
            # Arremessar adaga na Reaction Step é a finalização perfeita de Arakni Marionette
            return 18.0
        elif "blacktek_whisperers" in eq_name:
            return 14.0  # Concede Go Again ao ataque de adaga/contrato
        return super().evaluate_equipment_ability(state_or_name, eq_info_or_floating, hand_attacks=hand_attacks, **kwargs)

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 40))
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
                reason="Arakni Marionette survival mode: blocking critical or fatal damage"
            )

        # Se tiver Codex of Frailty na mão: jogar primeiro para forçar oponente a descartar e recuperar ataque
        has_codex = any("codex_of_frailty" in str(c.get("cardNumber") or c.get("name", "")).lower() for c in hand)
        contracts = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["leave_no_witnesses", "cut_from_the_same_cloth", "art_of_desire", "incision"])]

        if (has_codex or contracts) and my_hp >= 10:
            c_target = "codex_of_frailty" if has_codex else str(contracts[0].get("cardNumber") or contracts[0].get("name", ""))
            reserved: Set[str] = {c_target}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="ARAKNI_MARIONETTE_CONTRACT",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["codex_disrupt", "contract_attack", "flick_knives", "weapon"],
                offensive_potential=8.0,
                reason=f"Arakni Marionette plan: holding {c_target} for contract banish and dagger tempo"
            )

        return super().analyze_turn_plan(state)
