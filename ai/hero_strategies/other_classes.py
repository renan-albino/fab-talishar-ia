"""
ai/hero_strategies/other_classes.py
===================================
Estratégias especializadas para as demais classes oficiais de Flesh and Blood:
Mechanologist, Runeblade, Wizard, Illusionist, Assassin e Merchant.
"""

from functools import lru_cache
from typing import Set
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class MechanologistStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Mechanologist (Dash, Maxx, Teklovossen, Data Doll, Puffin, etc.).
    Gerenciamento de Boost com proteção contra fadiga, Crank de itens e Scrap.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "zero_to_sixty" in c_low or "zipper" in c_low:
            score += 3.0
        elif "throttle" in c_low or "fast_and_furious" in c_low or "high_octane" in c_low:
            score += 2.5
        return score

    def should_boost(self, card_name: str, hand_size: int, deck_size: int) -> bool:
        return deck_size > 6

    def should_crank(self, item_name: str, has_actions_left: bool) -> bool:
        return True

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        deck_size = int(state.get("deckCount", state.get("playerDeckCount", 20)))
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= 4) or is_fatal:
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Mechanologist survival mode: blocking dangerous damage"
            )

        if deck_size > 6 and my_hp >= 10 and not has_dangerous_on_hit:
            boost_cards = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["zero_to_sixty", "zipper", "throttle", "boost"])]
            if boost_cards:
                b_name = str(boost_cards[0].get("cardNumber") or boost_cards[0].get("name", ""))
                reserved: Set[str] = {b_name}
                reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
                max_blocks = max(0, len(hand) - len(reserved_in_hand))
                return TurnPlan(
                    plan_type="MECH_BOOST_TEMPO",
                    reserved_card_names=reserved,
                    can_absorb_damage=(my_hp >= 12),
                    max_block_cards=max_blocks,
                    priority_action_types=["boost_attack"],
                    offensive_potential=float(boost_cards[0].get("power", 4)),
                    reason=f"Mechanologist boost tempo plan: holding {b_name} with safe deck count"
                )

        return super().analyze_turn_plan(state)


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

        if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= 4) or is_fatal:
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Runeblade survival mode: blocking dangerous damage"
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


class WizardStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Wizard (Kano, Iyslander, Verdance, Oscilio, Blaze, Emperor, etc.).
    Dano arcano direto, velocidade Instant e demanda máxima por pitch azul para Crucible.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["sonic_boom", "zap", "aether", "spindle", "chain_lightning", "emergent"]):
            score += 5.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        score = float(pitch) * 5.0
        if pitch == 3:
            score += 8.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
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

        if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= 4) or is_fatal:
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Wizard survival mode: blocking dangerous physical damage"
            )

        blue_pitches = [c for c in hand if int(c.get("pitch", 1)) == 3]
        if len(blue_pitches) >= 2 and my_hp >= 8:
            reserved: Set[str] = {str(c.get("cardNumber") or c.get("name", "")) for c in blue_pitches[:2]}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="WIZARD_ARCANE_BURN",
                reserved_card_names=reserved,
                can_absorb_damage=True,
                max_block_cards=max_blocks,
                priority_action_types=["arcane_burn", "instant_ability"],
                offensive_potential=6.0,
                reason="Wizard arcane burn plan: holding blue pitches for Crucible activation and instant damage"
            )

        return super().analyze_turn_plan(state)


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

        if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= 4) or is_fatal:
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Illusionist survival mode: blocking dangerous damage"
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

        if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= 4) or is_fatal:
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Assassin survival mode: blocking dangerous damage"
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


class MerchantStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Merchant / Bard / Misc
    (Genis, Kavdaen, Melody, Shiyana, Gravy Bones, Scurv, Malice, Zane, etc.).
    Gerenciamento de recursos utilitários e moedas Gold/Silver.
    """
    is_heavy_hero: bool = False
