"""
ai/hero_strategies/base.py
==========================
Definição base de HeroStrategy, utilitários globais de cartas e re-exportação
de TurnPlan e submódulos táticos (knapsack_solver, turn_planner, equipment_evaluator).
"""

from functools import lru_cache
from typing import Optional, Dict, Any, Set, List, Tuple

from .knapsack_solver import (
    solve_knapsack_turn,
    calculate_card_opportunity_cost,
    calculate_hand_conversion_potential,
)
from ai.policy.constants import _get_cards_db, DANGEROUS_ON_HITS
from .turn_planner import (
    TurnPlan,
    analyze_turn_plan,
    should_trigger_survival_block,
)
from .equipment_evaluator import (
    evaluate_equipment_ability,
)


def is_resource_or_gem_card(card_name: str, card_info: dict = None, db_entry: dict = None) -> bool:
    """CR 3.1.5: Recursos e Gemas NUNCA podem ser colocados no Arsenal."""
    c_low = str(card_name).lower()
    card_type = (db_entry.get("type", "") if db_entry else "").upper()
    subtype = (db_entry.get("subtype", "") if db_entry else "").lower()
    if card_type in ("R", "RESOURCE") or "gem" in subtype:
        return True
    return any(k in c_low for k in [
        "riches_of_tropal", "heart_of_fyendal", "eye_of_ophidia", "grandeur_of_valahai",
        "arknight_shard", "fools_gold", "cracked_bauble", "cracker_bauble", "inner_chi",
        "copper", "silver", "gold_token"
    ])


KNOWN_AMBUSH_CARDS: Set[str] = {
    "down_and_dirty_red", "down_and_dirty", "stadium_security_red",
    "stadium_security_yellow", "stadium_security_blue", "no_hero_stands_alone_yellow",
    "overcrowded_blue", "tiger_eye_reflex_yellow", "tiger_eye_reflex_blue",
}


class HeroStrategy:
    """Estratégia base genérica para heróis de Flesh and Blood."""
    is_heavy_hero: bool = False
    intellect: int = 4

    def __init__(self, hero_name: str = "generic"):
        self.hero_name = str(hero_name).lower().strip()

    def get_intellect(self, state: Optional[dict] = None) -> int:
        """Retorna o Intelecto do herói (CR 4.3.2), com padrão 4 para heróis adultos."""
        if state and ("playerIntellect" in state or "intellect" in state):
            return int(state.get("playerIntellect", state.get("intellect", self.intellect)))
        name = getattr(self, "hero_name", "").lower()
        if any(h in name for h in ["rhinar", "kayo"]):
            return 3
        return getattr(self, "intellect", 4)

    def get_dynamic_multiplier(self, key: str, default: float = 1.0) -> float:
        """Obtém o multiplicador tático calibrado para o herói atual."""
        try:
            from ai.dynamic_rule_tuner import get_multipliers_for_hero
            return float(get_multipliers_for_hero(self.hero_name).get(key, default))
        except Exception:
            return default

    def has_heavy_attack(self, card_info: dict) -> bool:
        return False

    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        atk_mult = self.get_dynamic_multiplier("attack_weight", 1.0)
        score = float(power) * atk_mult + (4.0 if has_go_again else 0.0) - (cost * 0.5)
        return score + (2.0 if pitch == 1 else (-1.0 if pitch == 3 else 0.0))

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        if pitch <= 0:
            return -9999.0
        score = float(pitch) * 4.0 - (2.0 if power >= 4 else 0.0) - (2.0 if has_go_again else 0.0)
        return score - (3.0 if pitch == 1 else 0.0)

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        return 0.0

    def evaluate_zone_card_play(self, zone_name: str, c_name: str, c_info: dict, base_score: float, state: dict, turn_plan: TurnPlan) -> Optional[Tuple[float, bool, bool]]:
        """
        Avalia taticamente jogar cartas de zonas específicas (Arsenal, Banish, Graveyard).
        Retorna (score, is_instant, has_go_again) ou None se inválido.
        """
        has_ga = c_info.get("has_go_again", False)
        is_instant = False
        play_score = base_score
        
        if zone_name == "Arsenal":
            play_score += 4.0
            # NAA ganha bônus no Arsenal padrão
            c_type = str(c_info.get("type", "")).upper()
            is_arrow = any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy", "goldfin", "king_kraken", "king_shark", "endless"])
            is_naa = (not is_arrow) and (("AA" not in c_type and "ATTACK" not in c_type) or any(k in c_name for k in ["portside", "codex", "salvage", "three_of_a_kind", "tip_the_barkeep"]))
            if is_naa:
                play_score += 15.0
                if turn_plan.plan_type == "OVERPITCH_RECOVERY":
                    play_score += 15.0
            return play_score, is_instant, has_ga
            
        if zone_name == "Banish":
            play_score += 10.0
            return play_score, is_instant, has_ga
            
        if zone_name == "Graveyard":
            play_score += 18.0
            return play_score, is_instant, has_ga
            
        return play_score, is_instant, has_ga

    def evaluate_card_priority(self, card_name: str, cost: int, pitch: int, power: int, has_go_again: bool) -> float:
        return self.evaluate_attack_card(card_name, power, cost, has_go_again, pitch)

    def should_boost(self, card_name: str, hand_size: int, deck_size: int) -> bool:
        return deck_size > 5

    def should_crank(self, item_name: str, has_actions_left: bool) -> bool:
        return True

    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool, **kwargs) -> float:
        if block_val <= 0:
            return -999.0
        blk_mult = self.get_dynamic_multiplier("block_weight", 1.0)
        return (float(block_val) * 2.0 * blk_mult) - (power + (3.0 if has_go_again else 0.0))

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool, **kwargs) -> float:
        score = 3.0 + (2.0 if floating_res >= 1 else 0.0)
        return score + (2.5 if not has_hand_attacks else 0.0)

    def evaluate_weapon_ability(self, weapon_name: str, weapon_cost: int, state: dict, total_res: int, turn_plan: Optional[TurnPlan] = None) -> Optional[Dict[str, Any]]:
        return None

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        """Pontuação tática para ativar habilidades de equipamento delegada ao equipment_evaluator."""
        return evaluate_equipment_ability(self.hero_name, state_or_name, eq_info_or_floating, hand_attacks=hand_attacks, **kwargs)

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        """Calcula score de utilidade para colocar carta no Arsenal no fim do turno (CR 3.1.5)."""
        c_name = card_info.get("name", "").lower()
        pitch, power = card_info.get("pitch", 1), card_info.get("power", 0)
        block_val = card_info.get("block", card_info.get("defense", 0))
        subtype = (card_info.get("subtype") or (db_entry.get("subtype", "") if db_entry else "")).lower()
        card_type = (card_info.get("type") or (db_entry.get("type", "") if db_entry else "")).upper()
        card_text = (card_info.get("text") or (db_entry.get("text", "") if db_entry else "")).lower()

        if is_resource_or_gem_card(c_name, card_info, db_entry):
            return -9999.0

        score = float(power)
        is_down_and_dirty = "down_and_dirty" in c_name or "down and dirty" in c_name
        has_ambush = (
            c_name in KNOWN_AMBUSH_CARDS
            or any(k in c_name for k in ["stadium_security", "down_and_dirty", "no_hero_stands_alone", "overcrowded", "tiger_eye_reflex"])
            or "ambush" in subtype or "ambush" in card_text
            or "defend with this from your arsenal" in card_text or "ambush" in c_name or is_down_and_dirty
        )
        is_defense_reaction = (
            card_type == "DR" or "defense reaction" in subtype or "trap" in subtype
            or any(k in c_name for k in ["sink_below", "fate_foreseen", "staunch", "unmovable", "shelter", "take_cover"])
        )

        if is_down_and_dirty:
            return score + 12.0 + (3.0 if pitch == 1 else 0.0)
        elif has_ambush:
            return score + 9.0 + (3.0 if block_val >= 3 else 0.0)
        elif is_defense_reaction:
            score += 7.0 + (2.0 if card_info.get("cost", 0) <= 1 else 0.0)
        else:
            if block_val >= 3:
                score -= 8.0 + (6.0 if power <= 3 else 0.0)
            elif block_val == 2 and power <= 2:
                score -= 5.0

        if pitch == 1:
            score += 5.0
        elif pitch == 3:
            score -= 8.0

        if card_info.get("has_go_again", False):
            score += 2.0
        if card_info.get("cost", 0) == 0:
            score += 1.5
        if card_type == "I" or any(k in c_name for k in ["sigil", "oasis", "whisper"]):
            score += 4.0

        return score * self.get_dynamic_multiplier("arsenal_bonus", 1.0) if score > 0 else score

    def solve_knapsack_turn(self, hand: list, floating_res: int = 0, base_ap: int = 1, arsenal: Optional[list] = None, **kwargs) -> Tuple[float, List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Delega para knapsack_solver.solve_knapsack_turn."""
        return solve_knapsack_turn(self.hero_name, hand=hand, floating_res=floating_res, base_ap=base_ap, arsenal=arsenal, **kwargs)

    def calculate_card_opportunity_cost(self, hand: list, card_candidate: dict, floating_res: int = 0, **kwargs) -> float:
        """Delega para knapsack_solver.calculate_card_opportunity_cost."""
        return calculate_card_opportunity_cost(self.hero_name, hand=hand, card_candidate=card_candidate, floating_res=floating_res, **kwargs)

    def calculate_hand_conversion_potential(self, hand: list, floating_res: int = 0, **kwargs) -> Tuple[float, Set[str]]:
        """Delega para knapsack_solver.calculate_hand_conversion_potential."""
        return calculate_hand_conversion_potential(self.hero_name, hand=hand, floating_res=floating_res, **kwargs)

    def should_trigger_survival_block(self, my_hp: Any, opp_power: int = 0, is_fatal: bool = False, has_dangerous_on_hit: bool = False, hand: list = None, floating_res: int = 0, survival_hp_threshold: int = 6, **kwargs) -> bool:
        """Delega para turn_planner.should_trigger_survival_block."""
        return should_trigger_survival_block(my_hp, opp_power=opp_power, is_lethal=is_fatal, has_dangerous_on_hit=has_dangerous_on_hit, hand=hand, floating_res=floating_res, survival_hp_threshold=survival_hp_threshold, hero_name=self.hero_name, strategy=self, **kwargs)

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        """Delega para turn_planner.analyze_turn_plan."""
        return analyze_turn_plan(self.hero_name, state, strategy=self)

    # ── Hooks Polimórficos Especializados de Classe / Herói ───────────────────
    def modify_attack_candidate_score(self, card_name: str, card_info: dict, turn_plan: TurnPlan, base_score: float, state: dict) -> float:
        return base_score

    def can_play_banished_card(self, card_name: str, card_info: dict, state: dict) -> bool:
        return False

    def should_preserve_equipment_on_block(self, eq_name: str, eq_info: dict, state: dict, opp_power: int, is_lethal: bool) -> bool:
        return False

    def is_critical_pitch_resource(self, card_info: dict, hand: list, state: dict) -> bool:
        return False

    def is_hero_ability_active(self, state: dict) -> bool:
        return bool(state.get("hero_ability_active", False))
