"""
ai/hero_strategies/teklovossen.py
==================================
Estratégia especializada para o herói Teklovossen (Mechanologist Evo).
Foco em equipar melhorias Evo (Base e Steel Soul), ciclar a habilidade de herói,
gerenciar recursos de Mechanologist e evitar colapso de overblocking.
"""

from functools import lru_cache
from typing import Set, Any
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class TeklovossenStrategy(HeroStrategy):
    """
    Estratégia de jogo para Professor Teklovossen e Teklovossen, Esteemed Magnate.
    - Prioriza equipar/transformar Evos (Base e Steel Soul) para aumentar defesa persistente.
    - Preserva ataques de Mechanologist de alto impacto (Terminator Tank, War Machine, C&C).
    - Ativa habilidade de herói para ciclar cartas e reciclar Evos.
    - Evita queimar toda a mão em bloqueios passivos (overblocking) para garantir contra-ataques com Teklo Leveler ou ataques pesados.
    """
    is_heavy_hero: bool = True

    def has_heavy_attack(self, card_info: dict) -> bool:
        power = int(card_info.get("power", 0)) if str(card_info.get("power", 0)).isdigit() else 0
        c_low = str(card_info.get("cardNumber") or card_info.get("name", "")).lower()
        return power >= 6 or any(k in c_low for k in ["terminator_tank", "war_machine", "command_and_conquer"])

    def evaluate_card(self, card_name: str, card_meta: dict, context: dict = None) -> float:
        score = super().evaluate_card(card_name, card_meta, context)
        c_low = card_name.lower()
        cost = int(card_meta.get("cost", 0)) if str(card_meta.get("cost", 0)).isdigit() else 0
        subtype = str(card_meta.get("subtype", "")).lower()

        # Priorização de cartas Evo (Upgrades e Transformações)
        if "evo" in subtype or "evo" in c_low:
            score += 8.0
            if "steel_soul" in c_low:
                score += 4.0  # Upgrades nobres com habilidades contínuas
            elif "base" in c_low:
                score += 3.0

        # Ataques fundamentais de Teklovossen
        if "terminator_tank" in c_low:
            score += 10.0
        elif "war_machine" in c_low:
            score += 9.5
        elif "command_and_conquer" in c_low:
            score += 11.0
        elif "singularity" in c_low:
            score += 14.0  # Condição de vitória do Mechropotent
        elif "fabricate" in c_low:
            score += 8.5
        elif "scrap_trader" in c_low:
            score += 7.0

        score -= cost * 0.4
        return score

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power) * 1.5
        c_low = card_name.lower()

        if "command_and_conquer" in c_low:
            score += 12.0
        elif "terminator_tank" in c_low:
            score += 10.0
        elif "war_machine" in c_low:
            score += 9.0
        elif "scrap_trader" in c_low:
            score += 6.0

        if has_go_again:
            score += 4.0
        score -= cost * 0.4
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        score = float(pitch) * 4.5
        c_low = card_name.lower()

        # Evos azuis e cards azuis são ótimos pitches para pagar Teklo Leveler ou Evo upgrades
        if pitch == 3:
            score += 5.0
            if "evo" in c_low:
                score += 2.0

        # Não gastar ataques vermelhos no pitch a menos que estritamente necessário
        if pitch == 1 and power >= 5:
            score -= 6.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()

        # Proteger ataques pesados vermelhos de serem gastos em bloqueio comum
        if pitch == 1 and (power >= 6 or any(k in c_low for k in ["terminator_tank", "war_machine", "command_and_conquer"])):
            return -18.0

        # Preservar Singularity
        if "singularity" in c_low:
            return -99.0

        return float(block_val) * 2.0 - (power * 0.4)

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        c_low = str(card_name).lower()
        if "teklo_leveler" in c_low:
            # Teklo Leveler bate por 3+ dependendo dos Evos equipados
            score = 7.5 + (3.0 if floating_res >= 2 else 0.0)
            if not has_hand_attacks:
                score += 5.0
            return score
        return super().evaluate_weapon_attack(card_name, floating_res, total_res, has_hand_attacks)

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        if isinstance(state_or_name, dict):
            eq_info = eq_info_or_floating if isinstance(eq_info_or_floating, dict) else kwargs.get("eq_info", {})
            eq_name = str(eq_info.get("cardNumber") or eq_info.get("name", "")).lower()
        else:
            eq_name = str(state_or_name or "").lower()

        if "teklovossen" in eq_name:
            # Habilidade do herói Teklovossen: banir/equipar Evo e comprar
            return 14.0
        if "evo" in eq_name and "equip" in eq_name:
            return 10.0
        return super().evaluate_equipment_ability(state_or_name, eq_info_or_floating, hand_attacks=hand_attacks, **kwargs)

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 40))
        hand = state.get("playerHand", [])
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        # Se houver risco letal ou on-hit catastrófico, entrar em sobrevivência estrita
        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand, survival_hp_threshold=4):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Teklovossen survival mode: blocking critical or fatal damage"
            )

        # Identificar ataques de alto valor e Evos na mão
        heavy_attacks = [
            c for c in hand
            if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["terminator_tank", "war_machine", "command_and_conquer"])
        ]
        evo_cards = [
            c for c in hand
            if "evo" in str(c.get("cardNumber") or c.get("name", "")).lower()
        ]

        if heavy_attacks and my_hp >= 6:
            primary = heavy_attacks[0]
            p_name = str(primary.get("cardNumber") or primary.get("name", ""))
            reserved: Set[str] = {p_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand) - 1)  # poupa o ataque e um recurso de pitch
            return TurnPlan(
                plan_type="TEKLOVOSSEN_ATTACK_PIVOT",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 10),
                max_block_cards=max_blocks,
                priority_action_types=["attack_card", "weapon", "hero_ability"],
                offensive_potential=float(primary.get("power", 6)),
                reason=f"Teklovossen pivot: preserving {p_name} and pitch for counter-attack"
            )

        if evo_cards and my_hp >= 8:
            primary_evo = evo_cards[0]
            evo_name = str(primary_evo.get("cardNumber") or primary_evo.get("name", ""))
            reserved = {evo_name}
            max_blocks = max(0, len(hand) - len(reserved))
            return TurnPlan(
                plan_type="TEKLOVOSSEN_EVO_UPGRADE",
                reserved_card_names=reserved,
                can_absorb_damage=True,
                max_block_cards=max_blocks,
                priority_action_types=["evo_equip", "hero_ability", "weapon"],
                offensive_potential=4.0,
                reason=f"Teklovossen upgrade: preserving Evo {evo_name} to equip or banish"
            )

        return super().analyze_turn_plan(state)
