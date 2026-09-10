"""
ai/hero_strategies/base.py
==========================
Definição base de TurnPlan, utilitários globais de cartas e HeroStrategy.
"""

import os
import json
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Optional, Dict, Any, Set, List

_FAB_CARDS_DB = None

def _get_cards_db() -> dict:
    global _FAB_CARDS_DB
    if _FAB_CARDS_DB is None:
        db_paths = [
            "data/fab_cards_db.json",
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "fab_cards_db.json"),
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "fab_cards_db.json")
        ]
        for p in db_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        _FAB_CARDS_DB = json.load(f)
                    break
                except Exception:
                    pass
        if _FAB_CARDS_DB is None:
            _FAB_CARDS_DB = {}
    return _FAB_CARDS_DB


def is_resource_or_gem_card(card_name: str, card_info: dict = None, db_entry: dict = None) -> bool:
    """
    Verificação global universal de Flesh and Blood (CR 3.1.5):
    Recursos e Gemas NUNCA podem ser colocados no Arsenal por NENHUM herói de NENHUMA classe.
    Arsenal não dá pitch e cartas de Recurso não podem ser jogadas como ação/defesa.
    """
    c_low = str(card_name).lower()
    card_type = (db_entry.get("type", "") if db_entry else "").upper()
    subtype = (db_entry.get("subtype", "") if db_entry else "").lower()

    if card_type in ("R", "RESOURCE") or "gem" in subtype:
        return True

    # Gemas e recursos lendários/conhecidos de Flesh and Blood
    if any(k in c_low for k in [
        "riches_of_tropal", "heart_of_fyendal", "eye_of_ophidia",
        "grandeur_of_valahai", "arknight_shard", "fools_gold",
        "cracked_bauble", "cracker_bauble", "inner_chi",
        "copper", "silver", "gold_token"
    ]):
        return True

    return False


KNOWN_AMBUSH_CARDS: Set[str] = {
    "down_and_dirty_red", "down_and_dirty",
    "stadium_security_red", "stadium_security_yellow", "stadium_security_blue",
    "no_hero_stands_alone_yellow", "overcrowded_blue",
    "tiger_eye_reflex_yellow", "tiger_eye_reflex_blue",
}

DANGEROUS_ON_HITS = [
    "command_and_conquer", "cn_c", "snatch", "red_in_the_ledger",
    "crippling_crush", "spinal_crush", "star_struck", "leave_no_witnesses",
    "bloodrush_bellow", "warmonger", "inertia", "blood_drop",
    "shake_down", "mask_of_momentum", "codex_of_frailty"
]


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


class HeroStrategy:
    """Estratégia base genérica para heróis de Flesh and Blood."""
    is_heavy_hero: bool = False

    def __init__(self, hero_name: str = "generic"):
        self.hero_name = str(hero_name).lower().strip()

    def has_heavy_attack(self, card_info: dict) -> bool:
        """Determina se uma carta é um ataque pesado que justifica linha de Pivot."""
        return False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        """Calcula score de prioridade de ataque na cadeia de combate."""
        score = float(power)
        if has_go_again:
            score += 4.0
        score -= cost * 0.5
        if pitch == 1:
            score += 2.0
        elif pitch == 3:
            score -= 1.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        """Calcula score para escolher qual carta dar Pitch (Pitch 3 > Pitch 2 > Pitch 1)."""
        score = float(pitch) * 4.0
        if power >= 4:
            score -= 2.0
        if has_go_again:
            score -= 2.0
        if pitch == 1:
            score -= 3.0
        return score

    def evaluate_card_priority(self, card_name: str, cost: int, pitch: int, power: int, has_go_again: bool) -> float:
        return self.evaluate_attack_card(card_name, power, cost, has_go_again, pitch)

    def should_boost(self, card_name: str, hand_size: int, deck_size: int) -> bool:
        return deck_size > 5

    def should_crank(self, item_name: str, has_actions_left: bool) -> bool:
        return True

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        offensive_value = power + (3.0 if has_go_again else 0.0)
        return float(block_val) * 2.0 - offensive_value

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        """Pontuação tática para atacar com a arma equipada."""
        score = 3.0 + (2.0 if floating_res >= 1 else 0.0)
        if not has_hand_attacks:
            score += 2.5
        return score

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        """
        Calcula score de utilidade para colocar carta no Arsenal no fim do turno.
        
        Regras Globais de FaB (CR 3.1.5):
          1. Recursos e Gemas são normalmente proibidos no Arsenal (-9999.0).
          2. Cartas com Ambush ou Down and Dirty têm permissão de defender do Arsenal e ganham vantagem (+9.0 a +12.0).
          3. Reações de Defesa (DR) e Traps podem ser jogadas do Arsenal (+7.0 a +9.0).
          4. Cartas de ação comuns com alto valor de bloqueio (block >= 3) que NÃO têm Ambush nem são DR:
             Perdem 100% do seu valor defensivo no Arsenal e devem ficar na mão para defender (-8.0 a -14.0).
        """
        c_name = card_info.get("name", "").lower()
        pitch = card_info.get("pitch", 1)
        power = card_info.get("power", 0)
        block_val = card_info.get("block", card_info.get("defense", 0))
        subtype = (card_info.get("subtype") or (db_entry.get("subtype", "") if db_entry else "")).lower()
        card_type = (card_info.get("type") or (db_entry.get("type", "") if db_entry else "")).upper()
        card_text = (card_info.get("text") or (db_entry.get("text", "") if db_entry else "")).lower()

        # 1. Poda estrita universal: tipo R (Resource) ou Gem NUNCA vai para o Arsenal!
        if is_resource_or_gem_card(c_name, card_info, db_entry):
            return -9999.0

        score = float(power)

        # 2. Exceções com Vantagem no Arsenal: Ambush e Down and Dirty
        is_down_and_dirty = "down_and_dirty" in c_name or "down and dirty" in c_name
        has_ambush = (
            c_name in KNOWN_AMBUSH_CARDS
            or any(k in c_name for k in ["stadium_security", "down_and_dirty", "no_hero_stands_alone", "overcrowded", "tiger_eye_reflex"])
            or "ambush" in subtype
            or "ambush" in card_text
            or "defend with this from your arsenal" in card_text
            or "ambush" in c_name
            or is_down_and_dirty
        )

        is_defense_reaction = (
            card_type == "DR"
            or "defense reaction" in subtype
            or "trap" in subtype
            or any(k in c_name for k in ["sink_below", "fate_foreseen", "staunch", "unmovable", "shelter", "take_cover"])
        )

        if is_down_and_dirty:
            score += 12.0
            if pitch == 1:
                score += 3.0
            return score
        elif has_ambush:
            score += 9.0
            if block_val >= 3:
                score += 3.0
            return score
        elif is_defense_reaction:
            score += 7.0
            if card_info.get("cost", 0) <= 1:
                score += 2.0
        else:
            if block_val >= 3:
                score -= 8.0
                if power <= 3:
                    score -= 6.0
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

        return score

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        """
        Analisa o estado atual (mão, arsenal, vida, recursos, poder inimigo)
        e formula o TurnPlan genérico.
        """
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        # 1. Modo Sobrevivência
        if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= 4) or is_fatal:
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Low HP or dangerous/fatal on-hit: blocking with all available resources"
            )

        floating_res = int(state.get("playerPitchCount", 0))
        if floating_res == 0:
            resources = state.get("playerResources", [0, 0])
            floating_res = int(resources[0]) if isinstance(resources, list) and resources else 0

        # 2. Generic Pivot Check
        if my_hp >= 12 and not has_dangerous_on_hit and hand:
            best_attack = None
            best_pitch = None
            max_attack_power = -1

            # Procura cartas de ataque na mão
            for c in hand:
                c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
                c_power = int(c.get("power", 0))
                c_cost = int(c.get("cost", 0))
                c_pitch = int(c.get("pitch", 1))
                has_ga = bool(c.get("has_go_again", False))

                # Ataque sólido: poder >= 5 ou (poder >= 4 com go again)
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
                    can_absorb_damage=True,
                    max_block_cards=max_blocks,
                    offensive_potential=max_attack_power,
                    reason=f"Strong attack line ({list(reserved)[0]}) ready; absorbing damage to counter-attack"
                )

        # 3. Fallback: Troca de valor
        return TurnPlan(
            plan_type="VALUE_TRADE",
            can_absorb_damage=False,
            max_block_cards=min(2, len(hand)),
            offensive_potential=0.0,
            reason="Value trade: block cleanly and preserve action tempo"
        )
