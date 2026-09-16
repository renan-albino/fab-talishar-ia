"""
ai/hero_strategies/merchant.py
==============================
Estratégia para a classe Merchant / Bard / Misc (Genis, Kavdaen, Melody, Shiyana, Gravy Bones, etc.)
e especializações como Gravy Bones, Shipwrecked Looter.
"""

from functools import lru_cache
from typing import Set, Any
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class MerchantStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Merchant / Bard / Misc
    (Genis, Kavdaen, Melody, Shiyana, Gravy Bones, Scurv, Malice, Zane, etc.).
    Gerenciamento de recursos utilitários e moedas Gold/Silver.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(k in c_low for k in ["gold", "silver", "treasure", "bounty", "cash"]):
            score += 4.0
        if has_go_again:
            score += 3.5
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 5.0 + (2.0 if floating_res >= 2 else 0.0)
        return score


class GravyBonesStrategy(MerchantStrategy):
    """
    Estratégia especializada para Gravy Bones, Shipwrecked Looter (Pirata / Necromante).
    Utiliza ativamente Compass of Sunken Depths e Gold Baited Hook para geração de valor,
    comanda Aliados da arena (Riggermortis, Sawbones, Anka, Chum, Scooba) e finaliza com
    ataques de pirata devastadores em vez de permanecer passivo em bloqueio infinito.

    Possui Ally Stock Tracker para contabilizar cópias disponíveis (arena, mão, cemitério
    face-up vs face-down e deck residual), respeitando a regra onde aliados mortos em combate
    ficam virados para baixo (face-down / overlay: 1) e não podem ser re-invocados.
    """
    is_ally_hero: bool = True

    ALLIES_DATABASE = {
        "anka_drag_under_yellow": {"copies": 3, "cost": 2, "power": 5, "ability_cost": 1},
        "chum_friendly_first_mate_yellow": {"copies": 3, "cost": 4, "power": 4, "ability_cost": 0},
        "riggermortis_yellow": {"copies": 3, "cost": 1, "power": 6, "ability_cost": 1},
        "sawbones_dock_hand_yellow": {"copies": 3, "cost": 2, "power": 6, "ability_cost": 1},
        "scooba_salty_sea_dog_yellow": {"copies": 3, "cost": 0, "power": 4, "ability_cost": 3},
    }

    def get_ally_stock(self, state: dict) -> dict:
        """
        Rastreia detalhadamente as 15 cópias de aliados do baralho do Gravy Bones.
        Identifica aliados na arena, mão, banish, e distingue no cemitério aliados
        face-up (recorrentes via Watery Grave) de face-down (mortos na arena, impossibilitados de reuso).
        """
        stock = {
            "arena_allies": [],
            "hand_allies": [],
            "grave_faceup_allies": [],
            "grave_facedown_allies": [],
            "banish_allies": [],
            "total_dead_facedown": 0,
            "total_available_allies": 0,
            "estimated_deck_allies": 0,
        }

        def _is_ally(card_str: str) -> bool:
            c_low = str(card_str).lower()
            return any(a_name in c_low for a_name in ["anka", "chum", "riggermortis", "sawbones", "scooba"])

        # 1. Aliados vivos na arena
        for a in state.get("playerAllies", []):
            if isinstance(a, dict) and _is_ally(a.get("cardNumber") or a.get("name", "")):
                stock["arena_allies"].append(a)

        # 2. Aliados na mão
        for c in state.get("playerHand", []):
            if isinstance(c, dict) and _is_ally(c.get("cardNumber") or c.get("name", "")):
                stock["hand_allies"].append(c)

        # 3. Aliados no cemitério (face-up vs face-down)
        discard = state.get("playerDiscard", []) or state.get("playerGraveyard", [])
        for c in discard:
            if isinstance(c, dict) and _is_ally(c.get("cardNumber") or c.get("name", "")):
                is_down = c.get("overlay") == 1 or str(c.get("facing", "")).upper() == "DOWN"
                if is_down:
                    stock["grave_facedown_allies"].append(c)
                else:
                    stock["grave_faceup_allies"].append(c)

        # 4. Aliados na zona banida
        for b in state.get("playerBanish", []):
            if isinstance(b, dict) and _is_ally(b.get("cardNumber") or b.get("name", "")):
                stock["banish_allies"].append(b)

        known_count = (
            len(stock["arena_allies"]) +
            len(stock["hand_allies"]) +
            len(stock["grave_faceup_allies"]) +
            len(stock["grave_facedown_allies"]) +
            len(stock["banish_allies"])
        )
        stock["total_dead_facedown"] = len(stock["grave_facedown_allies"])
        stock["estimated_deck_allies"] = max(0, 15 - known_count)
        stock["total_available_allies"] = (
            len(stock["arena_allies"]) +
            len(stock["hand_allies"]) +
            len(stock["grave_faceup_allies"]) +
            stock["estimated_deck_allies"]
        )
        return stock

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "conqueror_of_the_high_seas" in c_low:
            score += 16.0  # Finalizador massivo com alto poder que supera blocos de 3
        elif "riggermortis" in c_low:
            score += 14.0  # Aliado com poder 6 massivo
        elif "avast_ye" in c_low:
            score += 14.0  # Concede Go Again essencial e gera Gold no hit
        elif "saltwater_swell" in c_low:
            score += 10.0  # Go Again essencial para sobrecarregar defesas
        elif "swiftwater_sloop" in c_low:
            score += 9.0
        elif "sawbones_dock_hand" in c_low:
            score += 7.0
        elif any(k in c_low for k in ["anka", "chum", "scooba", "scoundrel"]):
            score += 7.0
        elif "fearless_confrontation" in c_low:
            score += 6.0
        # Enablers de Watery Grave (ações azuis com Go Again que vão ao cemitério e liberam Watery Grave)
        elif any(k in c_low for k in ["call_to_the_grave", "portside_exchange", "tip_the_barkeep", "loot_the_hold", "golden_tipple"]):
            score += 12.0
        return score

    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool, **kwargs) -> float:
        c_low = card_name.lower()
        # Blood in the Water é uma Defense Reaction excelente de 4 de defesa a custo 0
        if "blood_in_the_water" in c_low:
            return 14.0
        # Evita queimar cartas finalizadoras de ataque no bloqueio para não perder poder de letalidade
        if any(k in c_low for k in ["conqueror_of_the_high_seas", "riggermortis", "swiftwater_sloop"]):
            return -8.0
        return super().evaluate_block_card(card_name, block_val, pitch, power, has_go_again, **kwargs)

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Compass of Sunken Depths / Armas de Pirata
        score = 8.0 + (2.0 if floating_res >= 1 else 0.0)
        return score

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        if isinstance(state_or_name, dict):
            eq_info = eq_info_or_floating if isinstance(eq_info_or_floating, dict) else kwargs.get("eq_info", {})
            eq_name = str(eq_info.get("cardNumber") or eq_info.get("name", "")).lower()
        else:
            eq_name = str(state_or_name or "").lower()
        if "gold_baited_hook" in eq_name or "hook" in eq_name:
            return 14.0
        elif "dead_threads" in eq_name:
            return 10.0
        return super().evaluate_equipment_ability(state_or_name, eq_info_or_floating, hand_attacks=hand_attacks, **kwargs)

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 40))
        opp_hp = int(state.get("opponentHealth", 40))
        hand = state.get("playerHand", [])
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        # 1. Modo Sobrevivência / Proteção contra On-Hits Críticos:
        if is_fatal or (has_dangerous_on_hit and opp_power >= 4) or self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Gravy Bones survival mode: blocking critical on-hit or fatal damage"
            )

        # 2. Rastreamento de Estoque de Aliados (Ally Stock Tracking)
        ally_stock = self.get_ally_stock(state)
        available_allies_cnt = ally_stock["total_available_allies"]

        reserved: Set[str] = set()
        offensive_potential = 0.0

        # Identifica se há Avast Ye! para conceder Go Again ao ataque/aliado
        avast_cards = [c for c in hand if "avast_ye" in str(c.get("cardNumber") or c.get("name", "")).lower()]
        if avast_cards:
            avast_name = str(avast_cards[0].get("cardNumber") or avast_cards[0].get("name", ""))
            reserved.add(avast_name)
            offensive_potential += 4.0

        # Identifica ataques de pirata na mão
        pirate_keywords = [
            "conqueror_of_the_high_seas", "riggermortis", "sawbones", "saltwater_swell",
            "swiftwater_sloop", "anka", "chum", "scooba", "cheating_scoundrel"
        ]
        hand_attacks = [
            c for c in hand
            if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in pirate_keywords)
        ]
        hand_attacks.sort(key=lambda c: int(c.get("power", 0)), reverse=True)

        allies = state.get("playerAllies", [])
        active_allies = [a for a in allies if isinstance(a, dict) and a.get("action", 0) > 0] if isinstance(allies, list) else []

        needed_cost = 0
        if active_allies:
            needed_cost += len(active_allies)
            offensive_potential += sum(float(a.get("power", 2)) for a in active_allies)

        if hand_attacks:
            primary_atk = hand_attacks[0]
            p_name = str(primary_atk.get("cardNumber") or primary_atk.get("name", ""))
            reserved.add(p_name)
            needed_cost += int(primary_atk.get("cost", 0))
            offensive_potential += float(primary_atk.get("power", 4))

            # Se temos Go Again nativo ou Avast Ye!, um segundo ataque converte
            if ("saltwater_swell" in p_name.lower() or avast_cards) and len(hand_attacks) > 1:
                sec_atk = hand_attacks[1]
                s_name = str(sec_atk.get("cardNumber") or sec_atk.get("name", ""))
                reserved.add(s_name)
                needed_cost += int(sec_atk.get("cost", 0))
                offensive_potential += float(sec_atk.get("power", 3))

        # 3. Se não há ataques de mão e nem aliados na arena, verificar recursão de aliados face-up no cemitério
        faceup_grave = ally_stock["grave_faceup_allies"]
        if not active_allies and not hand_attacks and faceup_grave:
            # Procurar ativadores azuis na mão para disparar Watery Grave
            blue_enablers = [
                c for c in hand
                if any(k in str(c.get("cardNumber") or "").lower() for k in [
                    "call_to_the_grave", "portside_exchange", "tip_the_barkeep",
                    "loot_the_hold", "golden_tipple", "avast_ye"
                ]) or int(c.get("pitch", 0)) == 3
            ]
            if blue_enablers:
                b_starter = blue_enablers[0]
                b_name = str(b_starter.get("cardNumber") or b_starter.get("name", ""))
                reserved.add(b_name)
                # O melhor aliado face-up no cemitério projeta ataque
                best_faceup = max(faceup_grave, key=lambda x: int(x.get("power", 4)))
                needed_cost += max(1, int(best_faceup.get("cost", 1)))
                offensive_potential += float(best_faceup.get("power", 5))

        # Reservar os pitches estritamente necessários para cobrir needed_cost
        pitch_cards = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) not in reserved and int(c.get("pitch", 0)) > 0]
        pitch_cards.sort(key=lambda c: int(c.get("pitch", 1)), reverse=True)
        res_gathered = 0
        for pc in pitch_cards:
            if res_gathered < needed_cost:
                res_gathered += int(pc.get("pitch", 1))
                reserved.add(str(pc.get("cardNumber") or pc.get("name", "")))

        # As cartas da mão que NÃO convertem ficam disponíveis para bloquear
        reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
        non_converting_cards = len(hand) - len(reserved_in_hand)
        max_blocks = max(0, non_converting_cards)

        # Postura de sobrevivência de aliados: se restam poucos aliados no ciclo (<= 2), bloquear com mais prudência
        conserve_board = (available_allies_cnt <= 2)

        # 0. MODO EXECUÇÃO LETAL (FINISHER KILL TURN):
        if opp_hp <= 8 and not is_fatal:
            return TurnPlan(
                plan_type="GRAVY_LETHAL_EXECUTION",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 8 and not has_dangerous_on_hit),
                max_block_cards=max_blocks,
                priority_action_types=["avast_ye", "ally_attack", "pirate_attack"],
                offensive_potential=max(offensive_potential, 14.0),
                reason=f"Gravy Bones LETHAL EXECUTION: opponent at {opp_hp} HP! Converting {len(reserved_in_hand)} hand cards ({max_blocks} non-converting to block)."
            )

        # 1. Aliados Ativos na Mesa (Pressão Máxima de Dilema):
        if active_allies:
            absorb_hp = 14 if conserve_board else 10
            return TurnPlan(
                plan_type="GRAVY_ALLY_SWARM",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= absorb_hp and not has_dangerous_on_hit),
                max_block_cards=max_blocks,
                priority_action_types=["ally_attack", "avast_ye", "pirate_attack"],
                offensive_potential=offensive_potential,
                reason=f"Gravy Bones swarm: commanding {len(active_allies)} allies ({available_allies_cnt} total left in deck/stock)"
            )

        # 2. Ataques de Pirata da Mão:
        if hand_attacks:
            return TurnPlan(
                plan_type="GRAVY_PIRATE_ASSAULT",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12 and not has_dangerous_on_hit),
                max_block_cards=max_blocks,
                priority_action_types=["avast_ye", "compass_ability", "pirate_attack"],
                offensive_potential=offensive_potential,
                reason=f"Gravy Bones pirate assault: hand conversion reserved {len(reserved_in_hand)} cards ({max_blocks} non-converting to block)"
            )

        # 3. Recursão de Aliados Face-Up via Watery Grave do Cemitério:
        if faceup_grave:
            return TurnPlan(
                plan_type="GRAVY_WATERY_GRAVE_RECURSION",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12 and not has_dangerous_on_hit),
                max_block_cards=max_blocks,
                priority_action_types=["blue_starter", "watery_grave_ally", "ally_attack"],
                offensive_potential=offensive_potential,
                reason=f"Gravy Bones Watery Grave recursion: reviving {len(faceup_grave)} face-up allies ({ally_stock['total_dead_facedown']} dead face-down)"
            )

        return super().analyze_turn_plan(state)
