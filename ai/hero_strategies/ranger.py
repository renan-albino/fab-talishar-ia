"""
ai/hero_strategies/ranger.py
============================
Estratégias para Ranger (Azalea, Lexi, Riptide) e especialização para Marlynn / Marlinn.
"""

from functools import lru_cache
from typing import Set, List, Optional, Dict, Any
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS, is_resource_or_gem_card, KNOWN_AMBUSH_CARDS, _get_cards_db


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
        arsenal = state.get("playerArsenal") or state.get("playerArse") or []
        if arsenal:
            return 0.0  # Arsenal já ocupado, não gasta Gold em vão

        items = list(state.get("playerItems", [])) + list(state.get("playerTokens", []))
        has_gold = any("gold" in str(it.get("cardNumber", it.get("name", it))).lower() for it in items if isinstance(it, dict))
        has_gold = has_gold or any("gold" in str(it).lower() for it in items if not isinstance(it, dict))
        gold_count = int(state.get("goldCount", state.get("playerGold", state.get("gold", 0))))
        if not has_gold and gold_count <= 0:
            return 0.0

        return 18.0

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        if isinstance(state_or_name, dict):
            state = state_or_name
            eq_info = eq_info_or_floating if isinstance(eq_info_or_floating, dict) else kwargs.get("eq_info", {})
            eq_name = str(eq_info.get("cardNumber") or eq_info.get("name", "")).lower()
        else:
            state = kwargs.get("state", {})
            eq_name = str(state_or_name or "").lower()

        # Quiver of Abyssal Depths: {r}{r}{r} para colocar flecha do cemitério no fundo do deck.
        # Regra Oficial: NÃO carrega flecha no arsenal! Serve estritamente para reciclar flechas no fim de jogo (anti-fadiga).
        if "quiver_of_abyssal_depths" in eq_name:
            deck = state.get("playerDeck", [])
            deck_count = len(deck) if isinstance(deck, list) and deck else int(state.get("playerDeckCount", 30))
            gy = state.get("playerDiscard", []) or state.get("playerGraveyard", [])
            cards_db = _get_cards_db()
            def _is_gy_arrow(c):
                c_num = str(c.get("cardNumber") or c.get("name", "")).lower()
                db_c = cards_db.get(c_num, {})
                subtype = str(db_c.get("subtype", "")).lower()
                return "arrow" in subtype or any(k in c_num for k in ["arrow", "shot", "harpoon", "bolt", "goldfin", "king_kraken", "king_shark"])

            has_gy_arrow = any(_is_gy_arrow(c) for c in gy if isinstance(c, dict))
            # Só ativa se o deck estiver no fim (<= 10 cartas) e houver flechas para reciclar
            if deck_count <= 10 and has_gy_arrow:
                return 18.0
            return 0.0

        # Outros Quivers convencionais (Enchanted Quiver, Driftwood Quiver): carregam flecha no Arsenal
        if "quiver" in eq_name:
            arsenal = state.get("playerArsenal") or state.get("playerArse") or []
            if not arsenal:
                hand = state.get("playerHand", [])
                cards_db = _get_cards_db()
                def _is_arrow(c):
                    c_num = str(c.get("cardNumber") or c.get("name", "")).lower()
                    db_c = cards_db.get(c_num, {})
                    subtype = str(db_c.get("subtype", "")).lower()
                    return "arrow" in subtype or any(k in c_num for k in ["arrow", "shot", "harpoon", "bolt", "cast", "goldfin", "king_kraken", "king_shark"])

                has_arrow_in_hand = any(_is_arrow(c) for c in hand)
                if has_arrow_in_hand:
                    return 24.0  # Prioridade altíssima: recarrega a flecha para armar o canhão e disparar!
            return 0.0

        if "bulls_eye_bracers" in eq_name:
            # Concede +1 power e Go Again na próxima flecha
            arsenal = state.get("playerArsenal") or state.get("playerArse") or []
            if arsenal:
                return 16.0

        if "trench_of_sunken_treasure" in eq_name:
            return 8.0

        return super().evaluate_equipment_ability(state_or_name, eq_info_or_floating, hand_attacks=hand_attacks, **kwargs)

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

    def evaluate_weapon_ability(
        self,
        weapon_name: str,
        weapon_cost: int,
        state: dict,
        total_res: int,
        turn_plan: Optional[TurnPlan] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Validação e pontuação especializada para Hammerhead, Harpoon Cannon.
        Regra FaB CR 2.1.2: Flechas só podem ser atacadas a partir do ARSENAL.
        Exceção Tática Especial: se segurar Codex of Frailty com Arsenal vazio, ativa antes para pitchar a mão
        e recarregar flecha do cemitério no Arsenal vazio via Codex.
        """
        w_low = str(weapon_name).lower()
        if "hammerhead" not in w_low:
            return None  # Tratar como arma convencional de ataque

        arsenal_cards = list(state.get("playerArsenal") or state.get("playerArse") or [])
        arrows_in_arsenal = [
            c for c in arsenal_cards
            if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["arrow", "harpoon", "bolt", "trophy", "goldfin", "king_kraken", "king_shark", "endless"])
        ]

        hand = state.get("playerHand", [])
        has_codex_in_hand = any(
            "codex_of_frailty" in str(c.get("cardNumber") or c.get("name", "")).lower()
            for c in hand
        )
        is_codex_setup = has_codex_in_hand and not arsenal_cards

        # Sem flecha no ARSENAL e sem setup de Codex of Frailty: proibido ativar o canhão à toa!
        if not arrows_in_arsenal and not is_codex_setup:
            return {}

        cards_db = _get_cards_db()
        plan_type = turn_plan.plan_type if turn_plan else "DEFAULT"

        if is_codex_setup:
            # Requer recursos suficientes para o canhão (4)
            if total_res < weapon_cost:
                return {}
            weapon_score = 36.0  # Prioridade máxima para abrir a sequência antes do Codex
            if plan_type in ("OVERPITCH_RECOVERY", "HARPOON_CHAIN"):
                weapon_score += 15.0
        else:
            def _get_cost(c):
                num = str(c.get("cardNumber") or c.get("name", "")).lower()
                db_c = cards_db.get(num, {})
                if "cost" in db_c:
                    return max(0, int(db_c["cost"]))
                return max(0, int(c.get("cost", 0)))

            min_arrow_cost = min(_get_cost(c) for c in arrows_in_arsenal)
            # Só ativa se houver recursos para o Hammerhead (4) + a flecha
            if total_res < (weapon_cost + min_arrow_cost):
                return {}
            weapon_score = 32.0
            if plan_type == "HARPOON_CHAIN":
                weapon_score += 20.0

        return {
            "type": "weapon_buff",
            "name": weapon_name,
            "score": weapon_score,
            "cost": weapon_cost,
            "power": 0,
            "has_go_again": True
        }

    def evaluate_zone_card_play(self, zone_name: str, c_name: str, c_info: dict, base_score: float, state: dict, turn_plan: TurnPlan) -> Optional[Tuple[float, bool, bool]]:
        play_score, is_instant, has_ga = super().evaluate_zone_card_play(zone_name, c_name, c_info, base_score, state, turn_plan)
        if zone_name == "Arsenal":
            c_low = c_name.lower()
            if any(k in c_low for k in ["arrow", "harpoon", "bolt", "trophy", "goldfin", "king_kraken", "king_shark", "endless"]):
                play_score += 10.0  # Flecha pronta
                if turn_plan.plan_type == "HARPOON_CHAIN":
                    play_score += 15.0
        return play_score, is_instant, has_ga

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
        arsenal = state.get("playerArsenal") or state.get("playerArse") or []
        discard = state.get("playerDiscard") or state.get("discard") or []
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        # 1. Modo Sobrevivência
        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Marlynn survival mode: blocking critical or fatal damage"
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
