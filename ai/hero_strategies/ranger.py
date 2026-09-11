"""
ai/hero_strategies/ranger.py
============================
Estratégias para Ranger (Azalea, Lexi, Riptide) e especialização para Marlynn / Marlinn.
"""

from functools import lru_cache
from typing import Set, List, Optional
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS, is_resource_or_gem_card, KNOWN_AMBUSH_CARDS


class RangerStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Ranger.
    Prioriza disparo de flechas a partir do Arsenal, carregamento via arco
    e poda estrita de recursos/gemas.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(k in c_low for k in ["arrow", "harpoon", "bolt", "trophy", "scoundrel", "rabble"]):
            score += 6.0
        if has_go_again:
            score += 4.0
        score -= cost * 0.5
        if pitch == 1:
            score += 3.0
        return score

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        c_name = str(card_info.get("name") or card_info.get("cardNumber", "")).lower()
        pitch = int(card_info.get("pitch", 1))
        power = int(card_info.get("power", 0))
        block_val = int(card_info.get("block", card_info.get("defense", 0)))
        subtype = (card_info.get("subtype") or (db_entry.get("subtype", "") if db_entry else "")).lower()
        card_type = (card_info.get("type") or (db_entry.get("type", "") if db_entry else "")).upper()
        card_text = (card_info.get("text") or (db_entry.get("text", "") if db_entry else "")).lower()

        # 1. Poda estrita universal: Recursos e Gemas proibidos no Arsenal
        if is_resource_or_gem_card(c_name, card_info, db_entry):
            return -9999.0

        # 2. Exceções com Vantagem: Ambush e Down and Dirty
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
        if is_down_and_dirty:
            return 16.0
        if has_ambush:
            return 13.0

        # 3. Flechas (Arrows): Prioridade #1 absoluta do Ranger
        is_arrow = "arrow" in subtype or any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy_shot", "endless_arrow"])
        if is_arrow:
            if pitch == 1:
                return 26.0
            elif pitch == 2:
                return 20.0
            return 14.0

        # 4. Buffs de ataque / Ações Não-Ataque de Ranger
        if any(k in c_name for k in ["three_of_a_kind", "rain_razors", "take_aim", "seek_horizon", "premeditation", "codex"]):
            score = 12.0
            if pitch == 1:
                score += 2.0
            return score

        # 5. Reações de Defesa e Armadilhas (Traps)
        is_dr = "trap" in subtype or card_type == "DR" or any(k in c_name for k in ["trap", "sink_below", "fate_foreseen", "shelter", "take_cover"])
        if is_dr:
            return 9.0

        # 6. Cartas comuns de ação com valor de bloqueio que NÃO são flechas nem DR:
        score = float(power)
        if block_val >= 3:
            score -= 8.0
            if power <= 3:
                score -= 6.0
        if pitch == 3:
            score -= 14.0

        return score


class MarlynnStrategy(RangerStrategy):
    """
    Estratégia especializada para Marlynn, Treasure Hunter (Ranger / Pirata).
    Mecânicas e Podas Fundamentais:
    1. Sequenciamento de Arsenal: flechas disparadas do Arsenal via Hammerhead.
    2. Sequenciamento de NAAs de compra/buff antes de carregar o canhão.
    3. Poda de ativação do canhão: nunca carregar se o Arsenal estiver ocupado.
    4. Poda de Arsenal no Fim do Turno: flechas vermelhas prioritárias (score >= 25.0).
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()

        # Flechas / Harpoons de Marlynn (Dano devastador + On-Hit)
        if "king_kraken" in c_low:
            score += 10.0
        elif "goldfin" in c_low:
            score += 9.0
        elif "king_shark" in c_low:
            score += 8.5
        elif any(k in c_low for k in ["battering_bolt", "endless_arrow", "trophy_shot"]):
            score += 7.5
        elif any(k in c_low for k in ["harpoon", "arrow"]):
            score += 6.0

        # NAAs de Buff, Compra e Setup
        if "gorganian" in c_low:
            score += 16.0  # Compra 0 custo com go again: abastece mão para canhão e harpoons
        elif "three_of_a_kind" in c_low:
            score += 15.0
        elif "codex_of_frailty" in c_low:
            score += 11.0
        elif "portside_exchange" in c_low:
            score += 10.0
        elif any(k in c_low for k in ["sea_floor_salvage", "tip_the_barkeep", "cheating_scoundrel"]):
            score += 8.0

        if has_go_again:
            score += 5.0
        score -= cost * 0.4
        if pitch == 1:
            score += 3.0
        return score

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """
        Habilidade ativada de Marlynn, Treasure Hunter:
        Destrói 1 Gold para carregar uma flecha (LoadArrow).
        Regras táticas:
        - Só ativar se o jogador possuir Gold (itens, auras ou contador).
        - Só ativar se o Arsenal estiver vazio (LoadArrow requer slot livre).
        """
        arsenal = state.get("playerArsenal", [])
        if arsenal:
            return 0.0  # Arsenal já ocupado, não gasta Gold em vão

        items = list(state.get("playerItems", [])) + list(state.get("playerTokens", []))
        has_gold = any("gold" in str(it.get("cardNumber", it.get("name", it))).lower() for it in items if isinstance(it, dict))
        has_gold = has_gold or any("gold" in str(it).lower() for it in items if not isinstance(it, dict))
        gold_count = int(state.get("goldCount", state.get("playerGold", state.get("gold", 0))))
        if not has_gold and gold_count <= 0:
            return 0.0

        return 18.0

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        score = super().evaluate_arsenal_card(card_info, db_entry)
        if score <= -1000:
            return score
        c_name = str(card_info.get("name") or card_info.get("cardNumber", "")).lower()
        pitch = int(card_info.get("pitch", 1))

        # 1. Cartas Azuis de Harpoon / Recursos: NUNCA colocar no Arsenal
        if pitch == 3:
            return -9999.0

        # 2. Flechas vermelhas no Arsenal de Marlynn (score >= 25.0 para pitch 1)
        if any(k in c_name for k in ["king_kraken", "goldfin", "king_shark"]):
            return 26.0
        if any(k in c_name for k in ["harpoon", "arrow", "trophy", "bolt"]):
            return 26.0 if pitch == 1 else 18.0

        # 3. Armadilhas (Traps) e Reações de Defesa
        if any(k in c_name for k in ["boulder_trap", "tarpit_trap", "shelter", "take_cover", "sink_below"]):
            return 17.0

        # 4. NAAs fortes de abertura para o próximo turno
        if any(k in c_name for k in ["portside_exchange", "codex_of_frailty", "three_of_a_kind"]):
            return 15.0

        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        if pitch <= 0:
            return -9999.0
        c_low = card_name.lower()
        if pitch == 3:
            score = 22.0
            if any(k in c_low for k in ["harpoon", "rabble", "salvage", "treasure"]):
                score += 3.0
            return score

        if pitch == 2:
            return 6.0

        if any(k in c_low for k in ["king_kraken", "goldfin", "king_shark", "battering"]):
            return -40.0
        return -15.0

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        arsenal = state.get("playerArsenal", [])
        discard = state.get("playerDiscard") or state.get("discard") or []
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
                reason="Marlynn survival mode: blocking dangerous damage"
            )

        def _is_arrow(c):
            name = str(c.get("cardNumber") or c.get("name", "")).lower()
            return any(k in name for k in ["arrow", "harpoon", "bolt", "trophy_shot", "goldfin", "king_kraken", "king_shark", "endless_arrow"])

        def _is_trap_or_dr(c):
            name = str(c.get("cardNumber") or c.get("name", "")).lower()
            return "trap" in name or "sink" in name or "fate" in name or "shelter" in name or "take_cover" in name or c.get("type") == "DR"

        def _is_recovery(c):
            name = str(c.get("cardNumber") or c.get("name", "")).lower()
            return any(k in name for k in ["codex_of_frailty", "sea_floor_salvage", "tip_the_barkeep"])

        def _is_buff(c):
            name = str(c.get("cardNumber") or c.get("name", "")).lower()
            return any(k in name for k in ["three_of_a_kind", "portside_exchange", "premeditation", "rain_razors", "seek_horizon", "take_aim", "cheating_scoundrel"])

        arrows_in_zones = [c for c in list(hand) + list(arsenal) if _is_arrow(c)]

        # 2. DEFENSIVE_TRAP: 2+ armadilhas/defesas na mão e nenhuma flecha pronta
        traps = [c for c in hand if _is_trap_or_dr(c)]
        if not arrows_in_zones and len(traps) >= 2:
            return TurnPlan(
                plan_type="DEFENSIVE_TRAP",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Defensive trap plan: holding traps and defense reactions for defensive turn"
            )

        # 3. OVERPITCH_RECOVERY: Flecha no cemitério + recuperação na mão/arsenal + pitch azul
        has_arrow_in_discard = any(_is_arrow(c) for c in discard)
        recovery_card = next((c for c in list(hand) + list(arsenal) if _is_recovery(c)), None)
        blue_pitch = next((c for c in hand if c is not recovery_card and int(c.get("pitch", 1)) == 3), None)

        if has_arrow_in_discard and recovery_card is not None and blue_pitch is not None:
            r_name = str(recovery_card.get("cardNumber") or recovery_card.get("name", ""))
            b_name = str(blue_pitch.get("cardNumber") or blue_pitch.get("name", ""))
            reserved: Set[str] = {r_name, b_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="OVERPITCH_RECOVERY",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 10 and not has_dangerous_on_hit),
                max_block_cards=max_blocks,
                priority_action_types=["recovery", "pitch", "attack"],
                offensive_potential=8.0,
                reason="Overpitch recovery plan: recovering arrow from discard and reloading via blue pitch"
            )

        # 4. HARPOON_CHAIN: Flecha no Arsenal ou Mão + buff NAA
        if arrows_in_zones:
            arrow_card = arrows_in_zones[0]
            buff_card = next((c for c in list(hand) + list(arsenal) if c is not arrow_card and _is_buff(c)), None)
            a_name = str(arrow_card.get("cardNumber") or arrow_card.get("name", ""))
            reserved = {a_name}
            if buff_card is not None:
                reserved.add(str(buff_card.get("cardNumber") or buff_card.get("name", "")))

            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="HARPOON_CHAIN",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12 and not has_dangerous_on_hit),
                max_block_cards=max_blocks,
                priority_action_types=["buff", "load_bow", "attack"],
                offensive_potential=float(arrow_card.get("power", 6)) + (3.0 if buff_card else 0.0),
                reason=f"Harpoon chain plan: setting up {a_name} with bow load sequence"
            )

        return super().analyze_turn_plan(state)
