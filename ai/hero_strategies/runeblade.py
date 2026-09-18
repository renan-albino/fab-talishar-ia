"""
ai/hero_strategies/runeblade.py
===============================
Estratégia para a classe Runeblade (Viserai, Chane, Briar, Vynnset, Florian, Aurora, etc.)
e especializações como Vynnset, Iron Maiden.
"""

import logging
from typing import Optional, List, Tuple, Dict, Any, Set, Union,  Optional, List, Tuple, Dict, Any
from functools import lru_cache
from typing import Optional, List, Tuple, Dict, Any, Set, Union,  Set
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class RunebladeStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Runeblade (Viserai, Chane, Briar, Vynnset, Florian, Aurora, etc.).
    Dano híbrido físico e arcano, Runechants e armas mistas (Rosetta Thorn).
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["runeblood", "arknight", "rift_bind", "mauvrion", "rosetta", "revel", "meat_grinder", "duskpath"]):
            score += 4.0
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 6.0 + (2.0 if floating_res >= 1 else 0.0)
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
                reason="Runeblade survival mode: blocking critical or fatal damage"
            )

        if my_hp >= 10 and not has_dangerous_on_hit:
            # Sequenciamento NAA -> AA
            naa_cards = [c for c in hand if int(c.get("power", 0)) == 0 and bool(c.get("has_go_again", False))]
            aa_cards = [c for c in hand if int(c.get("power", 0)) > 0]
            if naa_cards and aa_cards:
                n_name = str(naa_cards[0].get("cardNumber") or naa_cards[0].get("name", ""))
                a_name = str(aa_cards[0].get("cardNumber") or aa_cards[0].get("name", ""))
                reserved: Set[str] = {n_name, a_name}
                reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
                max_blocks = max(0, len(hand) - len(reserved_in_hand))
                return TurnPlan(
                    plan_type="RUNEBLADE_HYBRID_STRIKE",
                    reserved_card_names=reserved,
                    can_absorb_damage=(my_hp >= 12),
                    max_block_cards=max_blocks,
                    priority_action_types=["naa_buff", "hybrid_attack"],
                    offensive_potential=float(aa_cards[0].get("power", 4)) + 3.0,
                    reason="Runeblade hybrid plan: sequencing NAA aura into physical/arcane attack"
                )

        return super().analyze_turn_plan(state)


_VYNNSET_RUNEGATE_ATTACKS = {
    "cull", "deathly_delight", "deathly_wail",
    "widespread_ruin", "widespread_destruction", "widespread_annihilation",
    "oblivion", "eloquent_eulogy"
}


class VynnsetStrategy(RunebladeStrategy):
    """
    Estratégia especializada para Vynnset, Iron Maiden.
    Sinergia com Shadow e Runegate: banimento no início do turno de ataques com Runegate
    para criar Runechants, reduzindo o custo de ataques jogados do Banish.
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if any(k in c_low for k in [
            "cull", "deathly_delight", "deathly_wail",
            "widespread_ruin", "widespread_destruction", "widespread_annihilation",
            "oblivion", "eloquent_eulogy", "beseech_the_demigon", "runegate"
        ]):
            score += 10.0
        elif any(k in c_low for k in ["funeral_moon", "shadow_puppetry", "dimenxxional", "revel_in_runeblood", "malefic_incantation", "tear_through_the_portal", "reduce_to_runechant"]):
            score += 8.0
        elif "flail_of_agony" in c_low:
            score += 6.0
        return score

    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool, runegate_in_hand: int = 1, **kwargs) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()
        is_runegate_atk = any(k in c_low for k in _VYNNSET_RUNEGATE_ATTACKS)

        # Regra tática de Vynnset: se houver 2+ ataques de Runegate na mão, ela não se importa de bloquear
        # com a carta sobressalente, pois dificilmente conseguirá converter mais de um ataque da mão no mesmo turno.
        if is_runegate_atk and runegate_in_hand >= 2:
            return float(block_val) * 2.0 - (power * 0.5)

        # Preserva única carta vermelha de Runegate e geradores de Runechant na mão para atacar
        if pitch == 1 and (power >= 4 or is_runegate_atk or any(k in c_low for k in ["shadow_puppetry", "revel_in_runeblood"])):
            return -12.0
        return float(block_val) * 2.0 - (power * 0.5)

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """
        Habilidade de início da fase de ação de Vynnset:
        Bane uma carta da mão para criar um Runechant e dar Piercing 1 ao próximo ataque Runegate.
        Regra estrita: DEVE banir quase que estritamente ataques de Runegate para convertê-los do Banish!
        Se a mão não possuir nenhum ataque de Runegate, NÃO ativa para não prender cartas não jogáveis no Banish.
        """
        hand = state.get("playerHand", [])
        has_runegate_attack_in_hand = any(
            any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in _VYNNSET_RUNEGATE_ATTACKS)
            for c in hand
        )
        if has_runegate_attack_in_hand and len(hand) >= 2:
            return 25.0
        return 0.0

    def evaluate_zone_card_play(self, zone_name: str, c_name: str, c_info: dict, base_score: float, state: dict, turn_plan: TurnPlan) -> Optional[Tuple[float, bool, bool]]:
        play_score, is_instant, has_ga = super().evaluate_zone_card_play(zone_name, c_name, c_info, base_score, state, turn_plan)
        if zone_name == "Banish":
            play_score += 15.0  # Vynnset quer esvaziar o Banish para não morrer de Blood Debt
        return play_score, is_instant, has_ga

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 8.0 + (3.0 if floating_res >= 1 else 0.0)
        return score

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 40))
        hand = state.get("playerHand", [])
        banish = state.get("playerBanish", [])
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
                reason="Vynnset survival mode: blocking critical or fatal damage"
            )

        runegate_cards = [
            c for c in list(banish) + list(hand)
            if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in [
                "cull", "deathly", "widespread", "oblivion",
                "beseech", "runegate", "shadow", "flail"
            ])
        ]
        if runegate_cards and my_hp >= 10:
            rg_name = str(runegate_cards[0].get("cardNumber") or runegate_cards[0].get("name", ""))
            reserved: Set[str] = {rg_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="VYNNSET_RUNEGATE_PRESSURE",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["banish_ability", "runegate_attack", "weapon"],
                offensive_potential=7.0,
                reason=f"Vynnset plan: setting up Runegate attack {rg_name} via Runechants"
            )

        return super().analyze_turn_plan(state)
