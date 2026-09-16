"""
ai/hero_strategies/guardian.py
==============================
Estratégia para Guardian (Bravo, Oldhim, Valda, Betsy, Victor, Brevant, etc.)
e especialização para Jarl Vetreiði (Guardião Elemental de Terra e Gelo).
"""

from functools import lru_cache
from typing import Set, List, Optional
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS, _get_cards_db


class GuardianStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Guardian.
    Prioriza ataques pesados de Crush/Overpower, swing de martelo e pivot ofensivo com pitch 3 azul.
    """
    is_heavy_hero: bool = True

    def has_heavy_attack(self, card_info: dict) -> bool:
        c_name = str(card_info.get("name") or card_info.get("cardNumber", "")).lower()
        pitch = int(card_info.get("pitch", 1))
        power = int(card_info.get("power", 0))
        return (pitch == 1 and power >= 6) or any(w in c_name for w in [
            "crush", "wager", "overpower", "bet_big", "spinal", "crippling", "buckling",
            "macho", "pulverize", "star_struck", "anothos", "thunderquake", "chokeslam",
            "cartilage", "oaken", "boulder", "mangle", "felling", "plow_under",
            "command_and_conquer", "sledge", "titans_fist"
        ])

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in [
            "crush", "wager", "overpower", "bet_big", "spinal", "crippling", "buckling",
            "macho", "pulverize", "star_struck", "anothos", "thunderquake", "chokeslam",
            "cartilage", "oaken", "boulder", "mangle", "felling", "plow_under",
            "command_and_conquer", "sledge", "titans_fist"
        ]):
            score += 6.0
        if pitch == 1 and power >= 6:
            score += 4.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        score = float(pitch) * 5.0
        if pitch == 3:
            score += 6.0
        elif pitch == 1:
            score -= 8.0  # Nunca pitcha ataques vermelhos pesados
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()
        if pitch == 1 and (power >= 6 or any(w in c_low for w in ["oaken", "boulder", "mangle", "felling", "crush", "command_and_conquer"])):
            return -25.0
        return float(block_val) * 2.0 - (power * 0.5)

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 4.5 + (2.0 if floating_res >= 1 else 0.0)
        if not has_hand_attacks:
            score += 4.5  # Martelo pesado para aplicar pressão quando sem ataque na mão
        return score

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        score = super().evaluate_arsenal_card(card_info, db_entry)
        if score <= -1000:
            return score
        c_name = str(card_info.get("name") or card_info.get("cardNumber", "")).lower()
        pitch = int(card_info.get("pitch", 1))
        power = int(card_info.get("power", 0))
        # Ataques vermelhos pesados de Guardião (power >= 6) superam a penalidade de bloco porque são o Pivot
        if pitch == 1 and (power >= 6 or any(w in c_name for w in ["oaken", "boulder", "mangle", "felling", "crush", "command_and_conquer"])):
            score += 12.0
        # Reações de defesa e Auras defensivas (Channel Lake Frigid, Blizzard, Staunch Response)
        if any(k in c_name for k in ["staunch", "channel_lake", "channel_ice", "blizzard", "sink_below"]):
            score += 9.0
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
                reason="Guardian survival mode: blocking critical or fatal damage"
            )

        # Pivot com Ataque Pesado
        if my_hp >= 10 and not has_dangerous_on_hit:
            heavy_atk = None
            for c in all_cards:
                c_pitch = int(c.get("pitch", 1))
                c_power = int(c.get("power", 0))
                if self.has_heavy_attack(c) or (c_pitch == 1 and c_power >= 6):
                    heavy_atk = c
                    break

            blue_card = None
            for c in hand:
                if c is heavy_atk:
                    continue
                if int(c.get("pitch", 1)) == 3:
                    blue_card = c
                    break

            if heavy_atk is not None and (blue_card is not None or floating_res >= 3):
                h_name = str(heavy_atk.get("cardNumber") or heavy_atk.get("name", ""))
                reserved: Set[str] = {h_name}
                if blue_card is not None:
                    b_name = str(blue_card.get("cardNumber") or blue_card.get("name", ""))
                    reserved.add(b_name)

                reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
                max_blocks = max(0, len(hand) - len(reserved_in_hand))
                return TurnPlan(
                    plan_type="PIVOT_HEAVY_ATTACK",
                    reserved_card_names=reserved,
                    can_absorb_damage=True,
                    max_block_cards=max_blocks,
                    offensive_potential=float(heavy_atk.get("power", 7)),
                    reason=f"Guardian heavy pivot line: reserving {h_name} + pitch"
                )

        return super().analyze_turn_plan(state)

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        hero_name = str(hero_info.get("name") or hero_info.get("cardNumber", "")).lower()
        if "bravo" in hero_name:
            hand = state.get("playerHand", [])
            arsenal = state.get("playerArsenal", [])
            db = _get_cards_db()
            has_cost_3_attack = any(
                int(c.get("cost", db.get(str(c.get("cardNumber", c.get("name", ""))).lower(), {}).get("cost", 0))) >= 3
                for c in list(hand) + list(arsenal)
            )
            if has_cost_3_attack:
                return 16.0
        return 0.0

    def is_critical_pitch_resource(self, card_info: dict, hand: list, state: dict) -> bool:
        """Preservação de pitch azul para Guardião/Jarl quando há apenas 1 azul na mão."""
        if card_info.get("pitch") == 3:
            blue_count = sum(1 for c in hand if (c.get("pitch") == 3 or str(c.get("cardNumber", "")).lower().endswith("blue") or "blue" in str(c.get("name", "")).lower()))
            if blue_count <= 1:
                return True
        return False

    def modify_attack_candidate_score(self, card_name: str, card_info: dict, turn_plan: TurnPlan, base_score: float, state: dict) -> float:
        score = base_score
        c_clean = str(card_info.get("cardNumber") or card_name).lower()
        if turn_plan.plan_type == "PIVOT_OAKEN_OLD_FUSED" and "oaken_old" in c_clean:
            score += 35.0
        card_cost = max(0, int(card_info.get("cost", 0)))
        if card_cost >= 3:
            hand = state.get("playerHand", [])
            resources = state.get("playerResources", [0, 0])
            floating_res = resources[0] if isinstance(resources, list) and resources else 0
            has_blue_pitch = any(x != card_info and int(x.get("pitch", 0)) == 3 for x in hand if isinstance(x, dict))
            if floating_res < card_cost and not has_blue_pitch:
                score -= 25.0
        return score



class JarlStrategy(GuardianStrategy):
    """
    Estratégia especializada para Jarl Vetreiði (Guardião Elemental de Terra e Gelo).
    Mecânica e Podas Críticas:
    1. Preservação de Azuis (Pitch 3) para Titan's Fist e finalizadores.
    2. Fusão Elemental (Ice & Earth) para habilitar a devastadora linha de Oaken Old.
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "oaken_old" in c_low:
            score += 8.0
        elif "boulder_drop" in c_low or "felling_of_the_crown" in c_low:
            score += 6.0
        elif "command_and_conquer" in c_low:
            score += 6.5
        if any(k in c_low for k in ["ice", "blizzard", "frigid", "frost", "glaze"]):
            score += 3.5
        if any(k in c_low for k in ["earth", "autumn", "rootbound", "boulder", "oaken"]):
            score += 2.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        c_low = card_name.lower()
        if pitch == 3:
            score = 25.0
            if any(k in c_low for k in ["pulse_of_isenloft", "crumble", "autumn", "channel", "glaze", "winter"]):
                score += 5.0
            return score

        if pitch == 2:
            return 8.0

        score = -30.0
        if power >= 6 or any(w in c_low for w in ["oaken", "boulder", "mangle", "felling", "command_and_conquer"]):
            score = -60.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()

        if pitch == 1 and (power >= 6 or any(w in c_low for w in ["oaken", "boulder", "mangle", "felling", "command_and_conquer"])):
            return -35.0

        if pitch == 3:
            if any(k in c_low for k in ["sink", "fate", "staunch", "unmovable"]):
                return float(block_val) * 2.5
            return float(block_val) * 1.0 - 4.0

        return float(block_val) * 2.0 - (power * 0.5)

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
                reason="Jarl survival mode: blocking critical or fatal damage"
            )

        # Detecção de Fusão Oaken Old (Oaken Old + Terra + Gelo + Blue pitch)
        if my_hp >= 10 and not has_dangerous_on_hit and not is_fatal:
            cards_db = _get_cards_db()
            oaken_card = None
            for c in all_cards:
                c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
                if "oaken_old" in c_name:
                    oaken_card = c
                    break

            if oaken_card is not None:
                # Procura carta de Terra e de Gelo na mão (ou cartas que cumpram os papéis)
                earth_card = None
                ice_card = None
                blue_pitch_card = None

                for c in hand:
                    if c is oaken_card:
                        continue
                    c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
                    c_db = cards_db.get(c_name, {})
                    c_sub = str(c_db.get("subtype", "")).lower()
                    c_text = str(c_db.get("text", "")).lower()
                    pitch = int(c.get("pitch", 1))

                    is_earth = "earth" in c_name or "earth" in c_sub or "earth" in c_text or any(
                        k in c_name for k in ["autumn", "rootbound", "boulder", "fruits", "crumble", "channel_lake"]
                    )
                    is_ice = "ice" in c_name or "ice" in c_sub or "ice" in c_text or any(
                        k in c_name for k in ["blizzard", "frigid", "frost", "glaze", "winter", "pulse_of_isenloft", "hypothermia"]
                    )

                    if earth_card is None and is_earth:
                        earth_card = c
                    elif ice_card is None and is_ice:
                        ice_card = c

                    if pitch == 3 and blue_pitch_card is None:
                        blue_pitch_card = c

                # Se temos uma carta híbrida de Terra e Gelo (como pulse_of_isenloft)
                for c in hand:
                    if c is oaken_card:
                        continue
                    c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
                    if "pulse_of_isenloft" in c_name:
                        if earth_card is None:
                            earth_card = c
                        if ice_card is None:
                            ice_card = c

                has_resources = (blue_pitch_card is not None or floating_res >= 3)
                if earth_card is not None and ice_card is not None and has_resources:
                    reserved: Set[str] = {str(oaken_card.get("cardNumber") or oaken_card.get("name", ""))}
                    reserved.add(str(earth_card.get("cardNumber") or earth_card.get("name", "")))
                    reserved.add(str(ice_card.get("cardNumber") or ice_card.get("name", "")))
                    if blue_pitch_card is not None:
                        reserved.add(str(blue_pitch_card.get("cardNumber") or blue_pitch_card.get("name", "")))

                    reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
                    max_blocks = max(0, len(hand) - len(reserved_in_hand))
                    return TurnPlan(
                        plan_type="PIVOT_OAKEN_OLD_FUSED",
                        reserved_card_names=reserved,
                        can_absorb_damage=True,
                        max_block_cards=max_blocks,
                        offensive_potential=10.0,
                        reason="Jarl fused Oaken Old combo ready: holding Earth, Ice, and Blue pitch for crushing swing"
                    )

        # Fallback para pivot pesado de Guardião comum (Boulder Drop, C&C, etc.)
        return super().analyze_turn_plan(state)
