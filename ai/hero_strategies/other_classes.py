"""
ai/hero_strategies/other_classes.py
===================================
Estratégias especializadas para as demais classes oficiais de Flesh and Blood:
Mechanologist, Runeblade, Wizard, Illusionist, Assassin e Merchant.
"""

from functools import lru_cache
from typing import Set, Any, Optional, List
from .base import HeroStrategy, TurnPlan, DANGEROUS_ON_HITS


class MechanologistStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Mechanologist (Dash, Maxx, Teklovossen, Data Doll, Puffin, etc.).
    Gerenciamento de Boost com proteção contra fadiga, Crank de itens e Scrap.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "zero_to_sixty" in c_low or "zipper" in c_low:
            score += 3.5
        elif "throttle" in c_low or "fast_and_furious" in c_low or "high_octane" in c_low:
            score += 3.0
        elif any(k in c_low for k in ["boom_grenade", "convection_amplifier", "penetration_script", "bios_update", "expedite", "t_bone", "sparks_of_strength", "pulsewave_harpoon"]):
            score += 4.0
        return score

    def should_boost(self, card_name: str, hand_size: int, deck_size: int) -> bool:
        return deck_size > 6

    def should_crank(self, item_name: str, has_actions_left: bool) -> bool:
        return True

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        deck_size = int(state.get("deckCount", state.get("playerDeckCount", 20)))
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        # Dash IO e heróis jovens de Blitz começam com 20 HP, calibrando thresholds proporcionais
        is_young = "dash_io" in self.hero_name or "young" in self.hero_name or my_hp <= 20
        survival_threshold = 3 if is_young else 6
        tempo_hp_threshold = 5 if is_young else 10
        absorb_threshold = 7 if is_young else 12

        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand, survival_hp_threshold=survival_threshold):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Mechanologist survival mode: blocking critical or fatal damage"
            )

        if deck_size > 6 and my_hp >= tempo_hp_threshold and not has_dangerous_on_hit:
            boost_cards = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["zero_to_sixty", "zipper", "throttle", "boost", "t_bone", "expedite"])]
            if boost_cards:
                b_name = str(boost_cards[0].get("cardNumber") or boost_cards[0].get("name", ""))
                reserved: Set[str] = {b_name}
                reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
                max_blocks = max(0, len(hand) - len(reserved_in_hand))
                return TurnPlan(
                    plan_type="MECH_BOOST_TEMPO",
                    reserved_card_names=reserved,
                    can_absorb_damage=(my_hp >= absorb_threshold),
                    max_block_cards=max_blocks,
                    priority_action_types=["boost_attack"],
                    offensive_potential=float(boost_cards[0].get("power", 4)),
                    reason=f"Mechanologist boost tempo plan: holding {b_name} with safe deck count"
                )

        return super().analyze_turn_plan(state)


class DashIOStrategy(MechanologistStrategy):
    """
    Estratégia especializada para Dash I/O.
    Foco absoluto em itens com Crank (Boom Grenade, Convection Amplifier, Penetration Script, etc.),
    ativação de Teklo Foundry Heart para geração de 2 recursos livres, e pressão com Symbiosis Shot.
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()

        # Itens com Crank geram Action Points, contadores na Symbiosis Shot e buffs cumulativos gigantescos
        if "boom_grenade" in c_low:
            score += 15.0  # +4 de dano no próximo ataque de arma ou boost
        elif "convection_amplifier" in c_low:
            score += 14.0   # Concede Dominate
        elif "penetration_script" in c_low:
            score += 13.0   # Concede Piercing 1
        elif "teklo_core" in c_low:
            score += 14.0   # Gera 2 recursos por 2 turnos
        elif "cerebellum_processor" in c_low:
            score += 13.0   # Compra cartas
        elif any(k in c_low for k in ["heatsink", "prismatic_lens", "backup_protocol", "plasma_mainline"]):
            score += 12.0
        elif "pulsewave_harpoon" in c_low:
            score += 11.0  # Disrupt de mão / bloqueio
        elif "zero_to_sixty" in c_low or "zipper" in c_low:
            score += 7.0
        elif any(k in c_low for k in ["t_bone", "expedite", "sparks_of_strength", "maximum_velocity"]):
            score += 8.0

        if has_go_again:
            score += 4.0
        score -= cost * 0.5
        return score

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """Habilidade de Dash IO: olhar o topo do deck para jogar itens como Instant."""
        hand = state.get("playerHand", [])
        floating = int(state.get("playerPitchCount", 0))
        # Se tiver recursos ou cartas na mão para pitch, olhar o topo abre jogadas extras
        if len(hand) >= 1 or floating >= 1:
            return 15.0
        return 0.0

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Symbiosis Shot: arma barata que acumula steam counters com cada item jogado
        score = 9.0 + (3.0 if floating_res >= 1 else 0.0)
        return score

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        if isinstance(state_or_name, dict):
            eq_info = eq_info_or_floating if isinstance(eq_info_or_floating, dict) else kwargs.get("eq_info", {})
            eq_name = str(eq_info.get("cardNumber") or eq_info.get("name", "")).lower()
        else:
            eq_name = str(state_or_name or "").lower()

        if "teklo_foundry_heart" in eq_name or "foundry_heart" in eq_name:
            # Ativação do peito gera 2 recursos livres por turno (crucial para pagar itens/boost)
            return 16.0
        elif "achilles_accelerator" in eq_name:
            return 12.0  # Concede Action Point extra
        return super().evaluate_equipment_ability(state_or_name, eq_info_or_floating, hand_attacks=hand_attacks, **kwargs)

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 20))
        hand = state.get("playerHand", [])
        active_chain = state.get("activeChainLink") or {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()

        is_fatal = (my_hp - opp_power) <= 0
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand, survival_hp_threshold=3):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Dash IO survival mode: blocking critical or fatal damage"
            )

        # Buscar itens com Crank e ataques com boost na mão
        crank_items = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["boom_grenade", "convection_amplifier", "penetration_script", "teklo_core", "cerebellum", "heatsink", "prismatic_lens", "backup_protocol"])]
        boost_atks = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["zero_to_sixty", "zipper", "pulsewave", "t_bone", "expedite", "maximum_velocity"])]

        if (crank_items or boost_atks) and my_hp >= 4:
            primary = crank_items[0] if crank_items else boost_atks[0]
            p_name = str(primary.get("cardNumber") or primary.get("name", ""))
            reserved: Set[str] = {p_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="DASH_IO_CRANK_CHAIN",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 8),
                max_block_cards=max_blocks,
                priority_action_types=["crank_item", "hero_ability", "weapon", "boost_attack"],
                offensive_potential=float(boost_atks[0].get("power", 4) if boost_atks else 5.0) + 4.0,
                reason=f"Dash IO plan: sequencing Crank item {p_name} into weapon/boost attacks"
            )

        return super().analyze_turn_plan(state)


class RunebladeStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Runeblade (Viserai, Chane, Briar, Vynnset, Florian, Aurora, etc.).
    Dano híbrido físico e arcano, Runechants e armas mistas (Rosetta Thorn).
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["runeblood", "arknight", "rift_bind", "mauvrion", "rosetta", "revel", "meat_grinder", "duskpath"]):
            score += 4.0
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 6.0 + (2.0 if floating_res >= 1 else 0.0)
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
                reason="Runeblade survival mode: blocking critical or fatal damage"
            )

        if my_hp >= 10 and not has_dangerous_on_hit:
            # Sequenciamento NAA -> AA
            naa_cards = [c for c in hand if int(c.get("power", 0)) == 0 and bool(c.get("has_go_again", False))]
            aa_cards = [c for c in hand if int(c.get("power", 0)) > 0]
            if naa_cards and aa_cards:
                n_name = str(naa_cards[0].get("cardNumber") or naa_cards[0].get("name", ""))
                a_name = str(aa_cards[0].get("cardNumber") or aa_cards[0].get("name", ""))
                reserved: Set[str] = {n_name, a_name}
                reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
                max_blocks = max(0, len(hand) - len(reserved_in_hand))
                return TurnPlan(
                    plan_type="RUNEBLADE_HYBRID_STRIKE",
                    reserved_card_names=reserved,
                    can_absorb_damage=(my_hp >= 12),
                    max_block_cards=max_blocks,
                    priority_action_types=["naa_buff", "hybrid_attack"],
                    offensive_potential=float(aa_cards[0].get("power", 4)) + 3.0,
                    reason="Runeblade hybrid plan: sequencing NAA aura into physical/arcane attack"
                )

        return super().analyze_turn_plan(state)


_VYNNSET_RUNEGATE_ATTACKS = {
    "cull", "deathly_delight", "deathly_wail",
    "widespread_ruin", "widespread_destruction", "widespread_annihilation",
    "oblivion", "eloquent_eulogy"
}


class VynnsetStrategy(RunebladeStrategy):
    """
    Estratégia especializada para Vynnset, Iron Maiden.
    Sinergia com Shadow e Runegate: banimento no início do turno de ataques com Runegate
    para criar Runechants, reduzindo o custo de ataques jogados do Banish.
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if any(k in c_low for k in [
            "cull", "deathly_delight", "deathly_wail",
            "widespread_ruin", "widespread_destruction", "widespread_annihilation",
            "oblivion", "eloquent_eulogy", "beseech_the_demigon", "runegate"
        ]):
            score += 10.0
        elif any(k in c_low for k in ["funeral_moon", "shadow_puppetry", "dimenxxional", "revel_in_runeblood", "malefic_incantation", "tear_through_the_portal", "reduce_to_runechant"]):
            score += 8.0
        elif "flail_of_agony" in c_low:
            score += 6.0
        return score

    def evaluate_block_card(self, card_name: str, block_val: int, pitch: int, power: int, has_go_again: bool, runegate_in_hand: int = 1, **kwargs) -> float:
        if block_val <= 0:
            return -999.0
        c_low = card_name.lower()
        is_runegate_atk = any(k in c_low for k in _VYNNSET_RUNEGATE_ATTACKS)

        # Regra tática de Vynnset: se houver 2+ ataques de Runegate na mão, ela não se importa de bloquear
        # com a carta sobressalente, pois dificilmente conseguirá converter mais de um ataque da mão no mesmo turno.
        if is_runegate_atk and runegate_in_hand >= 2:
            return float(block_val) * 2.0 - (power * 0.5)

        # Preserva única carta vermelha de Runegate e geradores de Runechant na mão para atacar
        if pitch == 1 and (power >= 4 or is_runegate_atk or any(k in c_low for k in ["shadow_puppetry", "revel_in_runeblood"])):
            return -12.0
        return float(block_val) * 2.0 - (power * 0.5)

    def evaluate_hero_ability(self, state: dict, hero_info: dict) -> float:
        """
        Habilidade de início da fase de ação de Vynnset:
        Bane uma carta da mão para criar um Runechant e dar Piercing 1 ao próximo ataque Runegate.
        Regra estrita: DEVE banir quase que estritamente ataques de Runegate para convertê-los do Banish!
        Se a mão não possuir nenhum ataque de Runegate, NÃO ativa para não prender cartas não jogáveis no Banish.
        """
        hand = state.get("playerHand", [])
        has_runegate_attack_in_hand = any(
            any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in _VYNNSET_RUNEGATE_ATTACKS)
            for c in hand
        )
        if has_runegate_attack_in_hand and len(hand) >= 2:
            return 25.0
        return 0.0

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 8.0 + (3.0 if floating_res >= 1 else 0.0)
        return score

    def analyze_turn_plan(self, state: dict) -> TurnPlan:
        my_hp = int(state.get("playerHealth", 40))
        hand = state.get("playerHand", [])
        banish = state.get("playerBanish", [])
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
                reason="Vynnset survival mode: blocking critical or fatal damage"
            )

        runegate_cards = [
            c for c in list(banish) + list(hand)
            if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in [
                "cull", "deathly", "widespread", "oblivion",
                "beseech", "runegate", "shadow", "flail"
            ])
        ]
        if runegate_cards and my_hp >= 10:
            rg_name = str(runegate_cards[0].get("cardNumber") or runegate_cards[0].get("name", ""))
            reserved: Set[str] = {rg_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="VYNNSET_RUNEGATE_PRESSURE",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["banish_ability", "runegate_attack", "weapon"],
                offensive_potential=7.0,
                reason=f"Vynnset plan: setting up Runegate attack {rg_name} via Runechants"
            )

        return super().analyze_turn_plan(state)


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
        if "gone_in_a_flash" in c_low:
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

        if self.should_trigger_survival_block(my_hp, opp_power, is_fatal, has_dangerous_on_hit, hand, survival_hp_threshold=3):
            return TurnPlan(
                plan_type="SURVIVAL_BLOCK",
                can_absorb_damage=False,
                max_block_cards=len(hand),
                reason="Oscilio survival mode: blocking critical or fatal damage"
            )

        giaf_cards = [c for c in hand if "gone_in_a_flash" in str(c.get("cardNumber") or c.get("name", "")).lower()]
        if giaf_cards and my_hp >= 6:
            primary = giaf_cards[0]
            p_name = str(primary.get("cardNumber") or primary.get("name", ""))
            reserved: Set[str] = {p_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand) - 1)
            return TurnPlan(
                plan_type="OSCILIO_LIGHTNING_BURST",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 10),
                max_block_cards=max_blocks,
                priority_action_types=["attack_card", "weapon", "hero_ability"],
                offensive_potential=7.0,
                reason=f"Oscilio burst plan: chaining {p_name} with lightning tempo"
            )

        return super().analyze_turn_plan(state)


class IllusionistStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Illusionist (Prism, Dromai, Enigma, Pleiades, Zyggy, etc.).
    Heralds, Phantasm, dragões e auras de suporte.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["herald", "phantasm", "miragai", "kyloria", "cromai", "spectral", "ward"]):
            score += 4.5
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        score = 4.0 + (2.0 if floating_res >= 1 else 0.0)
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
                reason="Illusionist survival mode: blocking critical or fatal damage"
            )

        heralds = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["herald", "phantasm"])]
        if heralds and my_hp >= 10 and not has_dangerous_on_hit:
            h_name = str(heralds[0].get("cardNumber") or heralds[0].get("name", ""))
            reserved: Set[str] = {h_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="ILLUSIONIST_HERALD_PRESSURE",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["herald_attack"],
                offensive_potential=float(heralds[0].get("power", 5)),
                reason=f"Illusionist plan: holding {h_name} for soul charge and herald pressure"
            )

        return super().analyze_turn_plan(state)


class AssassinStrategy(HeroStrategy):
    """
    Estratégia especializada para a classe Assassin (Arakni, Uzuri, Nuu, Dr. Mortimer, etc.).
    Stealth, Contratos de banimento, adagas com Piercing 1 e reações punitivas.
    """
    is_heavy_hero: bool = False

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = float(power)
        c_low = card_name.lower()
        if any(w in c_low for w in ["stealth", "contract", "surgical", "leave_no_witnesses", "erase_face", "sneak", "infiltrate"]):
            score += 5.0
        if has_go_again:
            score += 4.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Spider's Bite / Scale Peeler (Dagger com Piercing 1)
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
                reason="Assassin survival mode: blocking critical or fatal damage"
            )

        contracts = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["contract", "stealth", "surgical", "leave_no_witnesses"])]
        if contracts and my_hp >= 10 and not has_dangerous_on_hit:
            c_name = str(contracts[0].get("cardNumber") or contracts[0].get("name", ""))
            reserved: Set[str] = {c_name}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="ASSASSIN_STEALTH_BANISH",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["stealth_attack", "contract"],
                offensive_potential=float(contracts[0].get("power", 4)),
                reason=f"Assassin plan: holding {c_name} for contract banish and silver generation"
            )

        return super().analyze_turn_plan(state)


class ArakniMarionetteStrategy(AssassinStrategy):
    """
    Estratégia especializada para Arakni, Marionette ("Mario").
    Combina contratos de banimento (Leave no Witnesses, Cut from the Same Cloth),
    ataques com adagas com Piercing (Hunters Klaive), ativação punitiva de
    Flick Knives na etapa de reação e recuperação via Codex of Frailty.
    """

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "leave_no_witnesses" in c_low:
            score += 12.0  # On-hit bane todo o arsenal e gera prata
        elif "cut_from_the_same_cloth" in c_low:
            score += 9.0
        elif "art_of_desire" in c_low:
            score += 8.0
        elif "codex_of_frailty" in c_low:
            score += 14.0  # Cria ponder, força descarte no oponente e recupera ataque do cemitério
        elif any(k in c_low for k in ["incision", "kiss_of_death", "meet_madness", "mark_of_the_black_widow"]):
            score += 7.0
        return score

    def evaluate_weapon_attack(self, card_name: str, floating_res: int, total_res: int, has_hand_attacks: bool) -> float:
        # Hunters Klaive com Piercing 1 é pressão contínua
        score = 6.0 + (3.0 if floating_res >= 2 else 0.0)
        return score

    def evaluate_equipment_ability(self, state_or_name, eq_info_or_floating: Any = None, hand_attacks: list = None, **kwargs) -> float:
        if isinstance(state_or_name, dict):
            eq_info = eq_info_or_floating if isinstance(eq_info_or_floating, dict) else kwargs.get("eq_info", {})
            eq_name = str(eq_info.get("cardNumber") or eq_info.get("name", "")).lower()
        else:
            eq_name = str(state_or_name or "").lower()

        if "flick_knives" in eq_name:
            # Arremessar adaga na Reaction Step é a finalização perfeita de Arakni Marionette
            return 18.0
        elif "blacktek_whisperers" in eq_name:
            return 14.0  # Concede Go Again ao ataque de adaga/contrato
        return super().evaluate_equipment_ability(state_or_name, eq_info_or_floating, hand_attacks=hand_attacks, **kwargs)

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
                reason="Arakni Marionette survival mode: blocking critical or fatal damage"
            )

        # Se tiver Codex of Frailty na mão: jogar primeiro para forçar oponente a descartar e recuperar ataque
        has_codex = any("codex_of_frailty" in str(c.get("cardNumber") or c.get("name", "")).lower() for c in hand)
        contracts = [c for c in hand if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in ["leave_no_witnesses", "cut_from_the_same_cloth", "art_of_desire", "incision"])]

        if (has_codex or contracts) and my_hp >= 10:
            c_target = "codex_of_frailty" if has_codex else str(contracts[0].get("cardNumber") or contracts[0].get("name", ""))
            reserved: Set[str] = {c_target}
            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="ARAKNI_MARIONETTE_CONTRACT",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["codex_disrupt", "contract_attack", "flick_knives", "weapon"],
                offensive_potential=8.0,
                reason=f"Arakni Marionette plan: holding {c_target} for contract banish and dagger tempo"
            )

        return super().analyze_turn_plan(state)


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
    """
    is_ally_hero: bool = True

    @lru_cache(maxsize=1024)
    def evaluate_attack_card(self, card_name: str, power: int, cost: int, has_go_again: bool, pitch: int) -> float:
        score = super().evaluate_attack_card(card_name, power, cost, has_go_again, pitch)
        c_low = card_name.lower()
        if "conqueror_of_the_high_seas" in c_low:
            score += 12.0  # Finalizador massivo com alto poder
        elif "riggermortis" in c_low:
            score += 10.0
        elif "saltwater_swell" in c_low:
            score += 7.0
        elif "sawbones_dock_hand" in c_low:
            score += 7.0
        elif "blood_in_the_water" in c_low:
            score += 8.0
        elif any(k in c_low for k in ["anka", "chum", "scooba", "swiftwater", "scoundrel"]):
            score += 7.0
        elif any(k in c_low for k in ["fearless_confrontation", "avast_ye"]):
            score += 6.0
        return score

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
                reason="Gravy Bones survival mode: blocking critical or fatal damage"
            )

        # 1. Aliados Ativos na Mesa (playerAllies): se houver aliados prontos, ativar ataque do enxame
        allies = state.get("playerAllies", [])
        if isinstance(allies, list) and allies and my_hp >= 8:
            active_allies = [a for a in allies if isinstance(a, dict) and a.get("action", 0) > 0]
            if active_allies:
                ally_target = active_allies[0]
                al_name = str(ally_target.get("cardNumber") or ally_target.get("name", "ally"))
                max_blocks = max(0, len(hand) - 1) if hand else 0
                return TurnPlan(
                    plan_type="GRAVY_ALLY_SWARM",
                    can_absorb_damage=(my_hp >= 10),
                    max_block_cards=max_blocks,
                    priority_action_types=["ally_attack", "pirate_attack"],
                    offensive_potential=float(ally_target.get("power", 5)),
                    reason=f"Gravy Bones plan: commanding arena ally {al_name} for swarm pressure"
                )

        # 2. Buscar ataques de pirata e aliados na mão para ofensiva agressiva
        pirate_keywords = [
            "conqueror_of_the_high_seas", "riggermortis", "sawbones", "saltwater_swell",
            "blood_in_the_water", "anka", "chum", "scooba", "swiftwater_sloop", "cheating_scoundrel"
        ]
        heavy_atks = [
            c for c in hand
            if any(k in str(c.get("cardNumber") or c.get("name", "")).lower() for k in pirate_keywords)
        ]
        pitch_cards = [c for c in hand if int(c.get("pitch", 1)) >= 2]

        if heavy_atks and my_hp >= 10:
            atk_card = heavy_atks[0]
            a_name = str(atk_card.get("cardNumber") or atk_card.get("name", ""))
            reserved: Set[str] = {a_name}
            if pitch_cards and pitch_cards[0] is not atk_card:
                reserved.add(str(pitch_cards[0].get("cardNumber") or pitch_cards[0].get("name", "")))

            reserved_in_hand = [c for c in hand if str(c.get("cardNumber") or c.get("name", "")) in reserved]
            max_blocks = max(0, len(hand) - len(reserved_in_hand))
            return TurnPlan(
                plan_type="GRAVY_PIRATE_ASSAULT",
                reserved_card_names=reserved,
                can_absorb_damage=(my_hp >= 12),
                max_block_cards=max_blocks,
                priority_action_types=["compass_ability", "pirate_attack", "ally_play"],
                offensive_potential=float(atk_card.get("power", 6)),
                reason=f"Gravy Bones plan: reserving {a_name} for pirate assault and treasure pressure"
            )

        return super().analyze_turn_plan(state)

