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

    def evaluate_card(self, card_name: str, card_meta: dict = None, context: dict = None) -> float:
        if card_meta is None:
            card_meta = {}
        power = int(card_meta.get("power", 0)) if str(card_meta.get("power", 0)).isdigit() else 0
        score = float(power)
        c_low = card_name.lower()
        cost = int(card_meta.get("cost", 0)) if str(card_meta.get("cost", 0)).isdigit() else 0
        subtype = str(card_meta.get("subtype", "")).lower()

        # Priorização e Hierarquia Oficial de Evos (Transformações e Upgrades)
        if "evo" in subtype or "evo" in c_low:
            # 1. Prioridade Máxima: Evos que reduzem custo
            if "controller" in c_low:
                score += 16.0  # Reduz custo de futuros upgrades por 2 recursos
            elif "heartdrive" in c_low:
                score += 14.0  # Reduz custo de ações Mechanologist por 1 recurso
            elif "base" in c_low:
                score += 12.0  # Evos Base preenchem slots vazios e reduzem custo de upgrade
            # 2. Prioridade Secundária: Evo Steel Soul Memory (+1 intelecto permanente)
            elif "memory" in c_low:
                # Prioridade entre os outros Evos, condicionada a não esgotar as opções do turno
                score += 15.0
            elif "tower" in c_low:
                score += 11.0  # Armadura e bloco maciço
            elif "processor" in c_low:
                score += 10.0  # Ciclo e filtragem
            else:
                score += 8.0

        # Ataques fundamentais de Teklovossen
        if "terminator_tank" in c_low:
            score += 10.0
        elif "war_machine" in c_low:
            score += 9.5
        elif "command_and_conquer" in c_low:
            score += 11.0
        elif "singularity" in c_low:
            score += 35.0  # Condição de vitória absoluta: Mechropotent
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

        if "singularity" in c_low:
            score += 35.0  # Mechropotent
        elif "command_and_conquer" in c_low:
            score += 12.0
        elif "terminator_tank" in c_low:
            score += 10.0
        elif "war_machine" in c_low:
            score += 9.0
        elif "scrap_trader" in c_low:
            score += 6.0
        elif "controller" in c_low:
            score += 16.0
        elif "heartdrive" in c_low:
            score += 14.0
        elif "memory" in c_low:
            score += 15.0
        elif "base" in c_low:
            score += 12.0

        if has_go_again:
            score += 4.0
        score -= cost * 0.4
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        c_low = card_name.lower()
        if "singularity" in c_low:
            return -999.0  # NUNCA dar pitch em Singularity!

        score = float(pitch) * 4.5

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

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """
        Habilidade ativada de Teklovossen:
        {r}{r}: Bane um card Evo da mão. Se o fizer, compra um card.
        Até o fim do turno, você pode jogar cards Evo da sua zona banida como se fossem Instant.
        """
        hand = state.get("playerHand", [])
        banish = state.get("playerBanish", [])
        has_evo_in_hand = any("evo" in str(c.get("cardNumber") or c.get("name", "")).lower() for c in hand)
        has_evo_in_banish = any("evo" in str(c.get("cardNumber") or c.get("name", "")).lower() for c in banish)
        if has_evo_in_hand:
            score = 18.0
            if has_evo_in_banish:
                score += 8.0  # Ativar a habilidade desbloqueia os Evos do banish para serem jogados como Instant!
            return score
        return 0.0

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool, **kwargs) -> float:
        c_low = str(card_name).lower()
        if "teklo_leveler" in c_low or "leveler" in c_low:
            evos_equipped = kwargs.get("evos_equipped", None)
            if evos_equipped is None:
                state = kwargs.get("state", {})
                equip = state.get("playerEquipment", []) if isinstance(state, dict) else []
                evos_equipped = sum(1 for eq in equip if isinstance(eq, dict) and ("evo" in str(eq.get("cardNumber", "")).lower() or "evo" in str(eq.get("subtype", "")).lower()))

            # Regra Oficial Teklo Leveler (EVO009):
            # • 0 ou 1 Evo: Custo 3 ({r}{r}{r}), Poder 2, sem Go Again (arma é igual com 0 e 1 Evos)
            # • 2 Evos: Custo {r}{r} a menos -> Custo 1 ({r}), Poder 2
            # • 3 Evos: Custo 1 ({r}), Poder 2, GANHA GO AGAIN!
            # • 4 Evos: Custo 1 ({r}), Poder 3 (+1{p}), GANHA GO AGAIN!
            if evos_equipped <= 1:
                score = 4.0 + (2.0 if floating_res >= 3 else 0.0)
            elif evos_equipped == 2:
                score = 12.0 + (3.0 if floating_res >= 1 else 0.0)
            elif evos_equipped == 3:
                score = 18.0 + (3.0 if floating_res >= 1 else 0.0)
            else: # 4 ou mais
                score = 25.0 + (4.0 if floating_res >= 1 else 0.0)

            if not has_hand_attacks:
                score += 7.0
            return score
        return super().evaluate_weapon_attack(card_name, floating_res, total_res, has_hand_attacks, **kwargs)

    def evaluate_arsenal_card(self, card_info: dict, db_entry: dict = None) -> float:
        """
        Avaliação de Arsenal especializada para Teklovossen:
        Permite e prioriza cartas Evo no Arsenal para serem equipadas diretamente no próximo turno,
        além de reações de defesa e The Singularity.
        """
        c_name = str(card_info.get("name", "")).lower()
        subtype = (card_info.get("subtype") or (db_entry.get("subtype", "") if db_entry else "")).lower()
        pitch = int(card_info.get("pitch", 1))

        # 1. Singularity: proteção máxima no arsenal para finalização com Mechropotent
        if "singularity" in c_name:
            return 30.0

        # 2. Reações de Defesa (Sink Below, Fate Foreseen, Shelter from the Storm)
        if any(dr in c_name for dr in ["sink_below", "fate_foreseen", "shelter_from_the_storm", "oasis_respite"]):
            return 16.0

        # 3. Evos no Arsenal: jogada de altíssimo valor em Teklovossen!
        # Equipar do arsenal libera a mão e transforma o herói
        if "evo" in c_name or "evo" in subtype:
            if "controller" in c_name or "heartdrive" in c_name:
                return 15.0
            elif "memory" in c_name:
                return 14.5
            return 13.0

        # 4. Ataques pesados vermelhos de finalização
        if pitch == 1 and any(atk in c_name for atk in ["terminator_tank", "war_machine", "command_and_conquer"]):
            return 11.0

        return super().evaluate_arsenal_card(card_info, db_entry)

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        if isinstance(state_or_name, dict):
            eq_info = eq_info_or_floating if isinstance(eq_info_or_floating, dict) else kwargs.get("eq_info", {})
            eq_name = str(eq_info.get("cardNumber") or eq_info.get("name", "")).lower()
        else:
            eq_name = str(state_or_name or "").lower()

        if "teklovossen" in eq_name:
            return 18.0
        if "evo" in eq_name and "equip" in eq_name:
            return 12.0
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

        # Detectar Evos já equipados nos 4 slots fundamentais (Head, Chest, Arms, Legs)
        equipped_evo_slots = set()
        for eq in (state.get("playerEquipment") or []):
            slot = str(eq.get("slot", "")).lower()
            if slot in ("head", "chest", "arms", "legs"):
                c_num = str(eq.get("cardNumber", "")).lower()
                subtype = str(eq.get("subtype", "")).lower()
                if "evo" in c_num or "evo" in subtype:
                    equipped_evo_slots.add(slot)

        singularity_cards = [
            c for c in hand
            if "singularity" in str(c.get("cardNumber") or c.get("name", "")).lower()
        ]

        # Em partidas lentas contra oponentes sem burst agressivo (opp_power <= 5),
        # prioriza absolutamente montar os 4 Evos para abusar de valor defensivo contínuo e finalizar com Singularity
        if evo_cards and len(equipped_evo_slots) < 4 and opp_power <= 5 and my_hp >= 6:
            primary_evo = evo_cards[0]
            evo_name = str(primary_evo.get("cardNumber") or primary_evo.get("name", ""))
            reserved: Set[str] = {evo_name}
            if singularity_cards:
                s_name = str(singularity_cards[0].get("cardNumber") or singularity_cards[0].get("name", ""))
                reserved.add(s_name)
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="TEKLOVOSSEN_EVO_ASSEMBLY",
                reserved_card_names=reserved,
                can_absorb_damage=True,
                max_block_cards=max_blocks,
                priority_action_types=["evo_equip", "hero_ability", "weapon"],
                offensive_potential=6.0,
                reason=f"Teklovossen assembly: assembling 4 Evos ({len(equipped_evo_slots)}/4) to build Mechropotent"
            )

        if heavy_attacks and my_hp >= 6:
            primary = heavy_attacks[0]
            p_name = str(primary.get("cardNumber") or primary.get("name", ""))
            reserved: Set[str] = {p_name}
            if singularity_cards:
                s_name = str(singularity_cards[0].get("cardNumber") or singularity_cards[0].get("name", ""))
                reserved.add(s_name)
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
            if singularity_cards:
                s_name = str(singularity_cards[0].get("cardNumber") or singularity_cards[0].get("name", ""))
                reserved.add(s_name)
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

    def is_hero_ability_active(self, state: dict) -> bool:
        """Verifica se a habilidade de Teklovossen ({r}{r}: Bane Evo da mão, compra carta) foi ativada neste turno."""
        if state.get("teklovossen_ability_active") is not None:
            return bool(state.get("teklovossen_ability_active"))
        if state.get("teklo_ability_active") is not None:
            return bool(state.get("teklo_ability_active"))
        if state.get("hero_ability_active") is not None:
            return bool(state.get("hero_ability_active"))

        # No Talishar, o herói fica em playerEquipment:
        # numUses inicia em 1 e se torna 0 quando a habilidade do herói é ativada no turno.
        for eq in state.get("playerEquipment", []):
            if not isinstance(eq, dict):
                continue
            eq_name = str(eq.get("cardNumber") or eq.get("name", "")).lower()
            eq_slot = str(eq.get("slot", "")).lower()
            if "teklo" in eq_name or eq_slot in ("hero", "character"):
                num_uses = eq.get("numUses")
                if num_uses is not None:
                    return int(num_uses) == 0

        return False

    def can_play_banished_card(self, card_name: str, card_info: dict, state: dict) -> bool:
        """Regra oficial Teklovossen: equipar Evo da zona banida é jogado como Instant se habilidade do herói estiver ativa."""
        c_low = card_name.lower()
        if "evo" in c_low:
            return self.is_hero_ability_active(state)
        return False

    def should_preserve_equipment_on_block(self, eq_name: str, eq_info: dict, state: dict, opp_power: int, is_lethal: bool) -> bool:
        """Preservação Sagrada dos Evos com TEMPER: não queimar a última defesa de 1 que destruiria a peça do Mechropotent."""
        eq_low = eq_name.lower()
        if "evo" in eq_low:
            eff_def = int(eq_info.get("defenseValue", eq_info.get("effective_block", 0)))
            if eff_def == 1 and not is_lethal:
                p_health = float(state.get("playerHealth", 20))
                if p_health > 8 and opp_power < 6:
                    return True
        return False

    def modify_attack_candidate_score(self, card_name: str, card_info: dict, turn_plan: TurnPlan, base_score: float, state: dict) -> float:
        score = base_score
        c_clean = str(card_info.get("cardNumber") or card_name).lower()
        if "singularity" in c_clean:
            score += 35.0
        return score
