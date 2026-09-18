"""
ai/hero_strategies/mechanologist.py
===================================
Estratégia para a classe Mechanologist (Dash, Maxx, Teklovossen, Data Doll, Puffin, etc.)
e especializações como Dash I/O.
"""

from functools import lru_cache
from typing import Optional, List, Tuple, Dict, Any, Set, Union,  Set, Any
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
            score += 3.5
        elif "throttle" in c_low or "fast_and_furious" in c_low or "high_octane" in c_low:
            score += 3.0
        elif any(k in c_low for k in ["boom_grenade", "convection_amplifier", "penetration_script", "bios_update", "expedite", "t_bone", "sparks_of_strength", "pulsewave_harpoon"]):
            score += 4.0
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

        # Dash IO e heróis jovens de Blitz começam com 20 HP, calibrando thresholds proporcionais
        is_young = "dash_io" in self.hero_name or "young" in self.hero_name or my_hp <= 20
        survival_threshold = 3 if is_young else 6
        tempo_hp_threshold = 5 if is_young else 10
        absorb_threshold = 7 if is_young else 12

        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand, survival_hp_threshold=survival_threshold):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Mechanologist survival mode: blocking critical or fatal damage"
            )

        if deck_size > 6 and my_hp >= tempo_hp_threshold and not has_dangerous_on_hit:
            boost_cards = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["zero_to_sixty", "zipper", "throttle", "boost", "t_bone", "expedite"])]
            if boost_cards:
                b_name = str(boost_cards[0].get("cardNumber") or boost_cards[0].get("name", ""))
                reserved: Set[str] = {b_name}
                reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
                max_blocks = max(0, len(hand) - len(reserved_in_hand))
                return TurnPlan(
                    plan_type="MECH_BOOST_TEMPO",
                    reserved_card_names=reserved,
                    can_absorb_damage=(my_hp >= absorb_threshold),
                    max_block_cards=max_blocks,
                    priority_action_types=["boost_attack"],
                    offensive_potential=float(boost_cards[0].get("power", 4)),
                    reason=f"Mechanologist boost tempo plan: holding {b_name} with safe deck count"
                )

        return super().analyze_turn_plan(state)


class DashIOStrategy(MechanologistStrategy):
    """
    Estratégia especializada para Dash I/O.
    Foco absoluto em itens com Crank (Boom Grenade, Convection Amplifier, Penetration Script, etc.),
    ativação de Teklo Foundry Heart para geração de 2 recursos livres, e pressão com Symbiosis Shot.
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()

        # Itens com Crank geram Action Points, contadores na Symbiosis Shot e buffs cumulativos gigantescos
        if "boom_grenade" in c_low:
            score += 15.0  # +4 de dano no próximo ataque de arma ou boost
        elif "convection_amplifier" in c_low:
            score += 14.0   # Concede Dominate
        elif "penetration_script" in c_low:
            score += 13.0   # Concede Piercing 1
        elif "teklo_core" in c_low:
            score += 14.0   # Gera 2 recursos por 2 turnos
        elif "cerebellum_processor" in c_low:
            score += 13.0   # Compra cartas
        elif any(k in c_low for k in ["heatsink", "prismatic_lens", "backup_protocol", "plasma_mainline"]):
            score += 12.0
        elif "pulsewave_harpoon" in c_low:
            score += 11.0  # Disrupt de mão / bloqueio
        elif "zero_to_sixty" in c_low or "zipper" in c_low:
            score += 7.0
        elif any(k in c_low for k in ["t_bone", "expedite", "sparks_of_strength", "maximum_velocity"]):
            score += 8.0

        if has_go_again:
            score += 4.0
        score -= cost * 0.5
        return score

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """Habilidade de Dash IO: olhar o topo do deck para jogar itens como Instant."""
        hand = state.get("playerHand", [])
        floating = int(state.get("playerPitchCount", 0))
        # Se tiver recursos ou cartas na mão para pitch, olhar o topo abre jogadas extras
        if len(hand) >= 1 or floating >= 1:
            return 15.0
        return 0.0

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Symbiosis Shot: arma barata que acumula steam counters com cada item jogado
        score = 9.0 + (3.0 if floating_res >= 1 else 0.0)
        return score

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        if isinstance(state_or_name, dict):
            eq_info = eq_info_or_floating if isinstance(eq_info_or_floating, dict) else kwargs.get("eq_info", {})
            eq_name = str(eq_info.get("cardNumber") or eq_info.get("name", "")).lower()
        else:
            eq_name = str(state_or_name or "").lower()

        if "teklo_foundry_heart" in eq_name or "foundry_heart" in eq_name:
            # Ativação do peito gera 2 recursos livres por turno (crucial para pagar itens/boost)
            return 16.0
        elif "achilles_accelerator" in eq_name:
            return 12.0  # Concede Action Point extra
        return super().evaluate_equipment_ability(state_or_name, eq_info_or_floating, hand_attacks=hand_attacks, **kwargs)

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand, survival_hp_threshold=3):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Dash IO survival mode: blocking critical or fatal damage"
            )

        # Buscar itens com Crank e ataques com boost na mão
        crank_items = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["boom_grenade", "convection_amplifier", "penetration_script", "teklo_core", "cerebellum", "heatsink", "prismatic_lens", "backup_protocol"])]
        boost_atks = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["zero_to_sixty", "zipper", "pulsewave", "t_bone", "expedite", "maximum_velocity"])]

        if (crank_items or boost_atks) and my_hp >= 4:
            primary = crank_items[0] if crank_items else boost_atks[0]
            p_name = str(primary.get("cardNumber") or primary.get("name", ""))
            reserved: Set[str] = {p_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="DASH_IO_CRANK_CHAIN",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 8),
                max_block_cards=max_blocks,
                priority_action_types=["crank_item", "hero_ability", "weapon", "boost_attack"],
                offensive_potential=float(boost_atks[0].get("power", 4) if boost_atks else 5.0) + 4.0,
                reason=f"Dash IO plan: sequencing Crank item {p_name} into weapon/boost attacks"
            )

        return super().analyze_turn_plan(state)
