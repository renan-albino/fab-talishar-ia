"""
ai/hero_strategies/turn_planner.py
==================================
Módulo de planejamento tático de turno (TurnPlan), formulação de planos de ataque/defesa
e decisão inteligente de bloqueio de sobrevivência (Survival Block) para Flesh and Blood.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Set, List
from .knapsack_solver import (
    calculate_hand_conversion_potential,
)


@dataclass
class TurnPlan:
    """
    Plano tático de ação para o turno atual.
    Coordena decisões ofensivas e defensivas entre a etapa de bloqueio e ataque.
    """
    plan_type: str = "DEFAULT"
    reserved_card_names: Set[str] = field(default_factory=set)
    can_absorb_damage: bool = False
    max_block_cards: int = 4
    priority_action_types: List[str] = field(default_factory=list)
    offensive_potential: float = 0.0
    reason: str = ""
    key_cards: Set[str] = field(default_factory=set)

    def __post_init__(self):
        if not self.key_cards and self.reserved_card_names:
            self.key_cards = set(self.reserved_card_names)
        elif not self.reserved_card_names and self.key_cards:
            self.reserved_card_names = set(self.key_cards)


def should_trigger_survival_block(
    state_or_hp: Any,
    opp_power: int = 0,
    is_lethal: bool = False,
    has_dangerous_on_hit: bool = False,
    hand: Optional[list] = None,
    floating_res: int = 0,
    survival_hp_threshold: int = 6,
    hero_name: str = "generic",
    strategy: Any = None,
    **kwargs
) -> bool:
    """
    Determina se o herói DEVE entrar em SURVIVAL_BLOCK estrito.
    Não força bloqueio cego se:
      - A vida estiver saudável (my_hp > 12)
      - O dano não for fatal
      - A conversão ofensiva da mão superar o dano recebido + on-hit
      - O bloqueio exigiria queimar múltiplas cartas com block baixo (<= 2).
    """
    if isinstance(state_or_hp, dict):
        state = state_or_hp
        my_hp = int(state.get("playerHealth", 20))
        active_chain = state.get("activeChainLink") or {}
        if opp_power == 0:
            opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        from ai.policy.constants import DANGEROUS_ON_HITS
        
        incoming_name = str(active_chain.get("cardNumber", "")).lower()
        incoming_power = opp_power
        # 1. Checagem direta de On-Hits Perigosos e breakpoints letais
        if incoming_power > 0:
            has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)
        is_fatal = bool(is_lethal) or ((my_hp - opp_power) <= 0)
        if hand is None:
            hand = state.get("playerHand", [])
        if floating_res == 0:
            floating_res = int(state.get("playerPitchCount", 0))
            if floating_res == 0:
                resources = state.get("playerResources", [0, 0])
                floating_res = int(resources[0]) if isinstance(resources, list) and resources else 0
    else:
        my_hp = int(state_or_hp)
        is_fatal = bool(is_lethal)

    if is_fatal or my_hp <= survival_hp_threshold:
        return True

    if not has_dangerous_on_hit:
        return False

    # Se há on-hit perigoso e vida saudável (> 12), avalia conversão da mão
    if my_hp > 12 and hand:
        hand_conv, _ = calculate_hand_conversion_potential(hero_name, hand=hand, floating_res=floating_res)
        from ai.policy.constants import _get_cards_db
        cards_db = _get_cards_db()
        block_vals = [
            int(c.get("block", c.get("defense", cards_db.get(str(c.get("cardNumber") or c.get("name", "")).lower(), {}).get("block", 0))) or 0)
            for c in hand
        ]
        sorted_b = sorted([b for b in block_vals if b > 0], reverse=True)
        acc = 0
        cards_needed = 0
        for b in sorted_b:
            acc += b
            cards_needed += 1
            if acc >= opp_power:
                break

        absorb_mult = 1.0
        if strategy is not None and hasattr(strategy, "get_dynamic_multiplier"):
            absorb_mult = strategy.get_dynamic_multiplier("absorb_tempo_bonus", 1.0)
        else:
            try:
                from ai.dynamic_rule_tuner import get_multipliers_for_hero
                mults = get_multipliers_for_hero(hero_name)
                absorb_mult = float(mults.get("absorb_tempo_bonus", 1.0))
            except Exception:
                absorb_mult = 1.0

        if cards_needed >= 2 and (hand_conv * absorb_mult) >= (float(opp_power) + 3.5):
            return False

    return opp_power >= 4


def analyze_turn_plan(
    hero_name: Any = "generic",
    state: Optional[Dict[str, Any]] = None,
    strategy: Any = None,
    **kwargs
) -> TurnPlan:
    """
    Analisa o estado atual (mão, arsenal, vida, recursos, poder inimigo)
    e formula o TurnPlan com avaliação flexível de conversão de mão vs bloqueio.
    """
    if isinstance(hero_name, dict):
        actual_state = hero_name
        if isinstance(state, str):
            actual_hero = state
        elif strategy is not None and hasattr(strategy, "hero_name"):
            actual_hero = strategy.hero_name
        elif hasattr(state, "hero_name"):
            actual_hero = state.hero_name
            strategy = state
        else:
            actual_hero = "generic"
    else:
        actual_hero = str(hero_name or "generic").lower().strip()
        actual_state = state or {}

    my_hp = int(actual_state.get("playerHealth", 20))
    hand = actual_state.get("playerHand", [])
    active_chain = actual_state.get("activeChainLink") or {}
    opp_power = int(active_chain.get("totalPower", actual_state.get("combatChainPower", 0)))
    incoming_name = str(active_chain.get("cardNumber", "")).lower()

    is_fatal = (my_hp - opp_power) <= 0
    from ai.policy.constants import DANGEROUS_ON_HITS
    has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

    floating_res = int(actual_state.get("playerPitchCount", 0))
    if floating_res == 0:
        resources = actual_state.get("playerResources", [0, 0])
        floating_res = int(resources[0]) if isinstance(resources, list) and resources else 0

    # 1. Modo Sobrevivência Flexível: avalia letalidade e valor
    if should_trigger_survival_block(
        my_hp,
        opp_power=opp_power,
        is_lethal=is_fatal,
        has_dangerous_on_hit=has_dangerous_on_hit,
        hand=hand,
        floating_res=floating_res,
        hero_name=actual_hero,
        strategy=strategy
    ):
        return TurnPlan(
            plan_type="SURVIVAL_BLOCK",
            can_absorb_damage=False,
            max_block_cards=len(hand),
            reason="Critical HP, fatal attack or unavoidable on-hit: blocking with available resources"
        )

    # 2. Avaliação de Conversão Ofensiva da Mão (Hand Conversion vs Inefficient Block)
    hand_conversion, key_cards = calculate_hand_conversion_potential(actual_hero, hand=hand, floating_res=floating_res)
    from ai.policy.constants import _get_cards_db
    cards_db = _get_cards_db()
    block_values = [
        int(c.get("block", c.get("defense", cards_db.get(str(c.get("cardNumber") or c.get("name", "")).lower(), {}).get("block", 0))) or 0)
        for c in hand
    ]
    sorted_blocks = sorted([b for b in block_values if b > 0], reverse=True)
    acc_block = 0
    cards_needed_to_block = 0
    for b in sorted_blocks:
        acc_block += b
        cards_needed_to_block += 1
        if acc_block >= opp_power:
            break

    on_hit_penalty = 3.5 if has_dangerous_on_hit else 0.0

    absorb_mult = 1.0
    if strategy is not None and hasattr(strategy, "get_dynamic_multiplier"):
        absorb_mult = strategy.get_dynamic_multiplier("absorb_tempo_bonus", 1.0)
    else:
        try:
            from ai.dynamic_rule_tuner import get_multipliers_for_hero
            mults = get_multipliers_for_hero(actual_hero)
            absorb_mult = float(mults.get("absorb_tempo_bonus", 1.0))
        except Exception:
            absorb_mult = 1.0

    # Condição de Absorção Inteligente (Início/Meio de jogo com vida saudável):
    # Se bloquear consumiria 2 ou mais cartas da mão e a conversão ofensiva supera o dano
    if my_hp > 12 and cards_needed_to_block >= 2 and opp_power > 0:
        if (hand_conversion * absorb_mult) >= (float(opp_power) + on_hit_penalty):
            max_allowed_blocks = max(0, len(hand) - len(key_cards))
            return TurnPlan(
                plan_type="TEMPO_COUNTER_ATTACK",
                reserved_card_names=key_cards,
                key_cards=key_cards,
                can_absorb_damage=True,
                max_block_cards=min(1, max_allowed_blocks),
                offensive_potential=hand_conversion,
                reason=f"Hand offensive conversion ({hand_conversion:.1f}) exceeds inefficient block ({opp_power} dmg needing {cards_needed_to_block} cards); absorbing to counter-attack"
            )

    # 3. Generic Pivot Check
    if my_hp >= 12 and not has_dangerous_on_hit and hand:
        best_attack = None
        best_pitch = None
        max_attack_power = -1

        for c in hand:
            c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
            c_power = int(c.get("power", 0))
            c_cost = int(c.get("cost", 0))
            c_pitch = int(c.get("pitch", 1))
            has_ga = bool(c.get("has_go_again", False))

            if c_power >= 5 or (c_power >= 4 and has_ga):
                needed_pitch = max(0, c_cost - floating_res)
                candidate_pitch = None
                for p in hand:
                    if p is c:
                        continue
                    p_pitch = int(p.get("pitch", 1))
                    if p_pitch >= needed_pitch:
                        candidate_pitch = p
                        break
                if needed_pitch == 0 or candidate_pitch is not None:
                    potential = float(c_power) + (2.0 if has_ga else 0.0)
                    if potential > max_attack_power:
                        max_attack_power = potential
                        best_attack = c
                        best_pitch = candidate_pitch

        if best_attack is not None and max_attack_power >= opp_power + 2:
            reserved: Set[str] = {str(best_attack.get("cardNumber") or best_attack.get("name", ""))}
            if best_pitch is not None:
                reserved.add(str(best_pitch.get("cardNumber") or best_pitch.get("name", "")))
            max_blocks = max(0, len(hand) - len(reserved))
            return TurnPlan(
                plan_type="GENERIC_PIVOT",
                reserved_card_names=reserved,
                key_cards=reserved,
                can_absorb_damage=True,
                max_block_cards=max_blocks,
                offensive_potential=max_attack_power,
                reason=f"Strong attack line ({list(reserved)[0]}) ready; absorbing damage to counter-attack"
            )

    # 4. Fallback: Troca de valor
    return TurnPlan(
        plan_type="VALUE_TRADE",
        can_absorb_damage=False,
        max_block_cards=min(2, len(hand)),
        offensive_potential=0.0,
        reason="Value trade: block cleanly and preserve action tempo"
    )
