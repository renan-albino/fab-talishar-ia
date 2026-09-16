"""
ai/hero_strategies/wizard.py
============================
Estratégia para a classe Wizard (Kano, Iyslander, Verdance, Oscilio, Blaze, Emperor, etc.)
e especializações como Oscilio, Constella Intelligence.
"""

from functools import lru_cache
from typing import Set
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class WizardStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Wizard (Kano, Iyslander, Verdance, Oscilio, Blaze, Emperor, etc.).
    Dano arcano direto, velocidade Instant e demanda máxima por pitch azul para Crucible.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["sonic_boom", "zap", "aether", "spindle", "chain_lightning", "emergent"]):
            score += 5.0
        return score

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        score = float(pitch) * 5.0
        if pitch == 3:
            score += 8.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 5.0 + (2.0 if floating_res >= 1 else 0.0)
        return score

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
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
                reason="Wizard survival mode: blocking critical or fatal damage"
            )

        blue_pitches = [c for c in hand if int(c.get("pitch", 1)) == 3]
        if len(blue_pitches) >= 2 and my_hp >= 8:
            reserved: Set[str] = {str(c.get("cardNumber") or c.get("name", "")) for c in blue_pitches[:2]}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="WIZARD_ARCANE_BURN",
                reserved_card_names=reserved,
                can_absorb_damage=True,
                max_block_cards=max_blocks,
                priority_action_types=["arcane_burn", "instant_ability"],
                offensive_potential=6.0,
                reason="Wizard arcane burn plan: holding blue pitches for Crucible activation and instant damage"
            )

        return super().analyze_turn_plan(state)


class OscilioStrategy(WizardStrategy):
    """
    Estratégia especializada para Oscilio, Constella Intelligence / Forked Continuum (Elemental Wizard - Lightning).
    - Foco em cadência agressiva de dano arcano e ataques relâmpago físicos (Gone in a Flash, Electrostatic Discharge).
    - Sinergias de Lightning (Gone in a Flash, Comet Storm, Flittering Charge, Lightning Press).
    - Uso dinâmico de Volzar, Meteor Storm para projetar dano arcano com recursos flutuantes.
    - Banir cartas de ação com a habilidade de herói para desbloquear conjuração da zona banida.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power) * 1.5
        c_low = card_name.lower()

        # Ataques centrais do arquétipo GIAF (Gone in a Flash) e Lightning
        if "astral_bridge" in c_low:
            score += 16.0  # Abre o topo, gera 1 dano arcano imediato e libera Instant para o ataque!
        elif "gone_in_a_flash" in c_low:
            score += 15.0  # Pilar do deck GIAF: Go Again e dano arcano com Lightning
        elif "electrostatic_discharge" in c_low:
            score += 12.0
        elif "enlightened_strike" in c_low:
            score += 11.0
        elif "comet_storm" in c_low:
            score += 10.0
        elif "flittering_charge" in c_low:
            score += 8.5
        elif "entwine_lightning" in c_low:
            score += 8.0
        elif "ravenous_rabble" in c_low:
            score += 7.5
        elif "scar_for_a_scar" in c_low:
            score += 7.0
        elif "second_strike" in c_low:
            score += 6.5

        if has_go_again:
            score += 5.0
        score -= cost * 0.4
        return score

    @lru_cache(maxsize=1024)
    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool, **kwargs) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()
        # Oscilio extrai seu maior valor mantendo cartas na mão para turnos ofensivos com Go Again e dano arcano.
        # Penalizar estritamente o bloqueio com peças centrais de ataque/combo para evitar overblocking:
        if any(k in c_low for k in [
            "gone_in_a_flash", "electrostatic_discharge", "enlightened_strike",
            "comet_storm", "flittering_charge", "astral_bridge", "second_strike",
            "entwine_lightning", "lightning_press"
        ]):
            return -18.0
        if has_go_again:
            return -12.0
        return float(block_val) * 1.5 - (power * 0.6)

    @lru_cache(maxsize=1024)
    def evaluate_pitch_card(self, card_name: str, pitch: int, cost: int, power: int, has_go_again: bool) -> float:
        score = float(pitch) * 4.0
        c_low = card_name.lower()
        # Amarelas de suporte (Constella Contemplation, Echoflash) funcionam bem como pitch para alimentar Volzar e custos 1/2
        if pitch == 2:
            score += 4.0
        # Preserva Gone in a Flash e E-Strike de serem pitchadas se houver alternativa
        if "gone_in_a_flash" in c_low or "enlightened_strike" in c_low:
            score -= 10.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        c_low = str(card_name).lower()
        if "volzar" in c_low or "meteor_storm" in c_low:
            # Volzar, Meteor Storm projeta dano arcano
            score = 8.0 + (4.0 if floating_res >= 1 else 0.0)
            if not has_hand_attacks:
                score += 5.0
            return score
        return super().evaluate_weapon_attack(card_name, floating_res, total_res, has_hand_attacks)

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """
        Habilidade de Oscilio:
        Bane uma carta de ação da mão para jogar cartas do banish de custo <= dano arcano causado.
        """
        hand = state.get("playerHand", [])
        banish = state.get("playerBanish", [])
        if len(hand) >= 2 and len(banish) >= 1:
            return 14.0
        return 0.0

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        # Oscilio só deve acionar bloqueio de sobrevivência em risco iminente de morte
        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand, survival_hp_threshold=2):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Oscilio survival mode: blocking critical or fatal damage"
            )

        lightning_attacks = [
            c for c in hand
            if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in [
                "gone_in_a_flash", "astral_bridge", "electrostatic", "flittering",
                "entwine", "enlightened", "comet", "scar_for_a_scar", "second_strike"
            ])
        ]
        if lightning_attacks and my_hp >= 4:
            primary = lightning_attacks[0]
            p_name = str(primary.get("cardNumber") or primary.get("name", ""))
            reserved: Set[str] = {p_name}
            astral = [c for c in hand if "astral_bridge" in str(c.get("cardNumber") or c.get("name", "")).lower()]
            if astral:
                reserved.add(str(astral[0].get("cardNumber") or astral[0].get("name", "")))
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            # Permite absorver dano a partir de 6 HP e limita bloqueio a no máximo 1 carta para não drenar a mão ofensiva
            max_blocks = min(1, max(0, len(hand) - len(reserved_in_hand)))
            return TurnPlan(
                plan_type="OSCILIO_LIGHTNING_BURST",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 6),
                max_block_cards=max_blocks,
                priority_action_types=["astral_bridge", "attack_card", "weapon", "hero_ability"],
                offensive_potential=8.0,
                reason=f"Oscilio burst plan: holding {p_name} to chain lightning and arcane damage"
            )

        return super().analyze_turn_plan(state)
