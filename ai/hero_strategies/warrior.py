"""
ai/hero_strategies/warrior.py
=============================
Estratégia para a classe Warrior (Dorinthea, Kassai, Boltyn, Olympia, Fang, Hala, etc.).
Foco central no ataque com a arma (Dawnblade, Sabers, etc.), ativação de Reprise
e preservação de reações de ataque na mão.
"""

from functools import lru_cache
from typing import Set
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class WarriorStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Warrior.
    Prioriza o ataque de arma como eixo tático principal, punindo defesas do oponente
    com reações de ataque seguradas na mão (Reprise).
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["reprise", "glint", "ironsong", "singing_steel", "spoils_of_war", "out_for_blood", "hit_and_run", "stroke"]):
            score += 5.0
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Guerreiro: o ataque com a arma é o centro absoluto da estratégia!
        score = 10.0 + (2.0 if floating_res >= 1 else 0.0)
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()
        # Preserva Reações de Ataque na mão para forçar dano na etapa de reações
        if any(w in c_low for w in ["ironsong", "glint", "steelblade", "stroke", "blade_runner", "reprise"]):
            return -15.0
        return float(block_val) * 2.0 - power

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
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
                reason="Warrior survival mode: blocking critical or fatal damage"
            )

        # Identificar reações de ataque na mão
        def _is_attack_reaction(c):
            name = str(c.get("cardNumber") or c.get("name", "")).lower()
            return any(w in name for w in ["ironsong", "glint", "steelblade", "stroke", "blade_runner", "reprise", "out_for_blood"])

        atk_reactions = [c for c in hand if _is_attack_reaction(c)]
        if atk_reactions and my_hp >= 10 and not has_dangerous_on_hit:
            rx = atk_reactions[0]
            r_name = str(rx.get("cardNumber") or rx.get("name", ""))
            reserved: Set[str] = {r_name}

            # Procura carta de pitch para garantir swing da arma + reação
            needed_pitch = max(0, int(rx.get("cost", 1)) + 1 - floating_res)
            pitch_card = next((c for c in hand if c is not rx and int(c.get("pitch", 1)) >= needed_pitch), None)
            if pitch_card is not None:
                reserved.add(str(pitch_card.get("cardNumber") or pitch_card.get("name", "")))

            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="WARRIOR_REPRISE_STRIKE",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["weapon", "attack_reaction"],
                offensive_potential=7.0,
                reason="Warrior Reprise plan: reserving weapon pitch and attack reactions for lethal turn"
            )

        return super().analyze_turn_plan(state)

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        hero_name = str(hero_info.get("name") or hero_info.get("cardNumber", "")).lower()
        if "kassai" in hero_name:
            return 17.0
        return 0.0


class KassaiStrategy(WarriorStrategy):
    """
    Estratégia especializada para Kassai (Cintari Sellsword / Golden Sand).
    Foco em sequenciamento de compras para ativar a redução passiva de custo de espadas (-1),
    e ativação da habilidade de herói para geração de Gold no acerto de arma.
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        # Cartas de compra ativam o desconto passivo de -1 de custo nas espadas de Kassai
        if "gorganian" in c_low:
            score += 15.0  # Compra 0 custo com go again: habilita redução passiva e mantém turno
        elif "cash_in" in c_low or "spoils_of_war" in c_low:
            score += 14.0
        elif "blood_on_her_hands" in c_low:
            score += 18.0
        elif any(k in c_low for k in ["blade_cuff", "raise_an_army", "run_through"]):
            score += 6.0
        return score

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """
        Habilidade ativada de Kassai of the Golden Sand:
        Concede o efeito de que o próximo acerto de arma cria um token de Gold.
        Custo 0 e possui Go Again. Deve ser ativada antes dos ataques de espada.
        """
        return 17.0


class HalaStrategy(WarriorStrategy):
    """
    Estratégia especializada para Hala, Bladesaint of the Vow.
    Foco absoluto em pressão com a Zenith Blade, potencializada por buffs como
    Edict of Steel, Brimming Blade e Imperial Seal of Command.
    Evita passar turnos jogando curas passivas (Sigil of Solace) quando pode atacar.
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "imperial_seal" in c_low:
            score += 12.0
        elif "edict_of_steel" in c_low:
            score += 10.0
        elif "brimming_blade" in c_low:
            score += 8.0
        elif "command_and_conquer" in c_low:
            score += 8.0
        elif "sigil_of_solace" in c_low:
            # Não prioriza cura passiva se estiver em condição de atacar
            score -= 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Zenith Blade é o motor de dano de Hala: valoriza swing em qualquer oportunidade
        score = 12.0 + (3.0 if floating_res >= 2 else 1.0)
        return score

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 40))
        hand = state.get("playerHand", [])
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Hala survival mode: blocking fatal or critical damage"
            )

        # Buscar buffs de arma na mão para sequenciar com a Zenith Blade
        buffs = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["edict_of_steel", "imperial_seal", "brimming_blade", "ironsong"])]
        pitch_cards = [c for c in hand if int(c.get("pitch", 1)) >= 2]

        if buffs and pitch_cards and my_hp >= 10:
            b_name = str(buffs[0].get("cardNumber") or buffs[0].get("name", ""))
            p_name = str(pitch_cards[0].get("cardNumber") or pitch_cards[0].get("name", ""))
            reserved: Set[str] = {b_name, p_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="HALA_ZENITH_PRESSURE",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["weapon_buff", "weapon"],
                offensive_potential=8.0,
                reason=f"Hala Zenith Blade plan: reserving {b_name} and pitch for boosted weapon strike"
            )

        return super().analyze_turn_plan(state)

