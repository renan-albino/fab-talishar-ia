"""
ai/policy_engine.py
===================
PolicyEngine: Motor de Decisão Híbrido com Poda Tática Baseada em Regras de Flesh and Blood.

Implementa podas táticas essenciais de FaB para guiar a busca MCTS e a Rede Neural:
  1. Poda de Sequenciamento de Cadeia (Preservação de Go Again e Action Points).
  2. Poda de Bloqueio (Overblocking desnecessário, Breakpoints e preservação de mão ofensiva).
  3. Poda de Arsenal (Regra oficial: Proibido Pitch do Arsenal — priorização estrita de cartas jogáveis).
  4. Poda de Pitch (Pitch Efficiency: Blue 3 > Yellow 2 > Red 1, evitando overpitching desnecessário).

Motor de Busca (v2):
  - MCTSEngine: Busca MCTS com Prior Threshold Pruning, Progressive Widening e avaliação sintética de folha.
  - ISMCTSEngine: Information Set MCTS para informação imperfeita (mão oculta do oponente).
    Ativo quando o oponente tem cartas na mão (opponentHandCount > 0).
"""

import os
import re
import json
import numpy as np
import torch
from typing import Dict, List, Optional, Tuple, Any

from .hero_strategies import (
    get_hero_strategy,
    HeroStrategy,
    TurnPlan,
    GuardianStrategy,
    JarlStrategy,
    BruteStrategy,
    WarriorStrategy,
    RangerStrategy,
    MarlynnStrategy,
    NinjaStrategy,
    MechanologistStrategy,
    RunebladeStrategy,
    WizardStrategy,
    IllusionistStrategy,
    AssassinStrategy,
    MerchantStrategy,
    is_resource_or_gem_card,
)
from .model import FaBPolicyValueNetwork, create_model, get_device
from .mcts import MCTSEngine, ISMCTSEngine
from .ismcts_logger import ISMCTSLogger

_FAB_CARDS_DB = None

def _get_cards_db() -> dict:
    global _FAB_CARDS_DB
    if _FAB_CARDS_DB is None:
        db_paths = [
            "data/fab_cards_db.json",
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

_load_cards_db = _get_cards_db


# ══════════════════════════════════════════════════════════════════
# CONSTANTES DE DOMÍNIO — FLESH AND BLOOD
# ══════════════════════════════════════════════════════════════════

# Palavras-chave de efeitos "On-Hit" perigosos que justificam bloqueio total
DANGEROUS_ON_HITS = {
    "crippling", "crush", "command_and_conquer", "red_in_the_ledger",
    "snatch", "mask_of_momentum", "bloodrot", "frailty", "inertia",
    "leave_no_witnesses", "surgical_extraction", "erase_face",
    "spitfire", "spinal_crush", "rightful_king", "hypothermia"
}

# Todas as 154+ armas oficiais mapeadas do Flesh and Blood
ALL_FAB_WEAPONS = {
    "aether_conduit", "annals_of_sutcliffe", "anothos", "aphrodias", "arcane_lantern",
    "aurum_aegis", "ball_breaker", "bank_breaker", "barbed_castaway", "bastion_of_duty",
    "bastion_of_unity", "beaming_blade", "beckoning_mistblade", "bloodied_oval", "bone_basher",
    "brush_of_heavenly_rites", "celebrant_broadsword", "cintari_saber", "cintari_saber_r",
    "claw_of_vynserakai", "cogwerx_blunderbuss", "compass_of_sunken_depths",
    "cosmo_scroll_of_ancestral_tapestry", "crows_nest", "crucible_of_aetherweave",
    "cutpurse_rapier", "dawnblade", "dawnblade_resplendent", "death_dealer",
    "decimator_great_axe", "dread_scythe", "dreadbore", "driftwood_quiver", "durendal",
    "duskblade", "edge_of_autumn", "enchanted_quiver", "farflight_longbow", "flail_of_agony",
    "fortitude_of_anvilheim", "galaxxi_black", "gavel_of_natural_order", "golden_grail",
    "graven_call", "graven_gaslight", "grimoire_of_fellingsong", "grimoire_of_the_haunt",
    "hammer_of_havenhold", "hanabi_blaster", "harmonized_kodachi", "harmonized_kodachi_r",
    "hatchet_of_body", "hatchet_of_mind", "hell_hammer", "hexagore_the_death_hydra",
    "high_riser", "hoarding_of_denial", "hot_streak", "hummingbird_call_of_adventure",
    "humour_plunge", "hunters_klaive", "hunters_klaive_r", "iris_of_reality",
    "jinglewood_smash_hit", "jubeel_spellbane", "krakens_aethervein", "kunai_of_retribution",
    "kunai_of_retribution_r", "lionclaw_maul", "luminaris", "luminaris_angels_glow",
    "luminaris_celestial_fury", "magrar", "mandible_claw", "mandible_claw_r",
    "mark_of_the_huntsman", "mark_of_the_huntsman_r", "merciless_battleaxe",
    "millers_grindstone", "mini_meataxe", "moment_maker", "nebula_blade", "nerve_scalpel",
    "nerve_scalpel_r", "obsidian_fire_vein", "obsidian_fire_vein_r", "orbitoclast",
    "orbitoclast_r", "ornate_tessen", "pile_driver", "plasma_barrel_shot",
    "proclamation_of_abundance", "proclamation_of_combat", "proclamation_of_production",
    "proclamation_of_requisition", "quicksilver_dagger", "quicksilver_dagger_r",
    "quiver_of_abyssal_depths", "quiver_of_rustling_leaves", "rampart_of_the_rams_head",
    "ravenous_meataxe", "raydn_duskbane", "reality_refractor", "reaping_blade", "red_liner",
    "redspine_manta", "redwood_hammer", "rok", "romping_club", "rosetta_thorn",
    "rotten_old_buckler", "rotwood_reaper", "rugged_roller", "sandscour_greatbow",
    "savage_claw", "scale_peeler", "scale_peeler_r", "scepter_of_pain", "scorpio_comet_tail",
    "searing_emberblade", "seasoned_saviour", "seerstone", "seven_sin_nebula", "shield_beater",
    "shiver", "silversheen_needle", "sledge_of_anvilheim", "spiders_bite", "spitfire",
    "staff_of_verdant_shoots", "stalagmite_bastion_of_isenloft", "star_fall",
    "steelbraid_buckler", "stonewall_impasse", "storm_of_sandikai", "summit_the_unforgiving",
    "surgent_aethertide", "symbiosis_shot", "talishar_the_lost_prince", "teklo_blaster",
    "teklo_plasma_pistol", "testament_of_valahai", "tiger_taming_khakkara", "titans_fist",
    "tremor_of_resistance", "voltaire_strike_twice", "volzar_meteor_storm",
    "volzar_the_lightning_rod", "vox_necropolis", "waning_moon", "winters_wail",
    "zenith_blade", "zephyr_needle", "zephyr_needle_r"
}

# Palavras-chave de armas adicionais para fallback
WEAPON_KEYWORDS = [
    "shot", "symbiosis", "blade", "kodachi", "flail", "hammer",
    "sword", "bow", "anothos", "scythe", "club", "staff", "axe",
    "scepter", "cynosure", "nebula", "weapon", "harmonised", "dawnblade",
    "saber", "cintari", "streak", "mandible", "hatchet", "duskblade",
    "raydn", "talishar", "rosetta", "reaper", "jubeel", "spider", "shield", "buckler"
]

# Custo de ativação de recursos para armas conhecidas no Flesh and Blood
KNOWN_WEAPON_COSTS = {
    "anothos": 3, "sledge_of_anvilheim": 3, "titans_fist": 3, "pile_driver": 3, "rok": 3,
    "hell_hammer": 3, "hammer_of_havenhold": 3, "redwood_hammer": 3, "ball_breaker": 3,
    "romping_club": 2, "flail_of_agony": 2, "dread_scythe": 2, "reaping_blade": 2,
    "zenith_blade": 2, "harmonious_pipe": 2, "claw_of_vynserakai": 2, "hunters_klaive": 2,
    "hunters_klaive_r": 2, "volzar_meteor_storm": 2, "symbiosis_shot": 2, "teklo_leveler": 2,
    "plasma_barrel_shot": 2, "hanabi_blaster": 2, "waning_moon": 2, "krakens_aethervein": 2,
    "cintari_saber": 1, "cintari_saber_r": 1, "hot_streak": 1, "dawnblade": 1, "dawnblade_resplendent": 1,
    "kunai_of_retribution": 1, "kunai_of_retribution_r": 1, "harmonized_kodachi": 1,
    "harmonized_kodachi_r": 1, "mandible_claw": 1, "mandible_claw_r": 1, "spiders_bite": 1,
    "nerve_scalpel": 1, "nerve_scalpel_r": 1, "scale_peeler": 1, "scale_peeler_r": 1,
    "orbitoclast": 1, "orbitoclast_r": 1, "teklo_plasma_pistol": 1, "death_dealer": 1,
    "hammerhead_harpoon_cannon": 1, "rosetta_thorn": 1, "nebula_blade": 1, "galaxxi_black": 1,
    "raydn_duskbane": 0, "redback_shroud": 0, "dreadbore": 0, "sandscour_greatbow": 0
}


class PolicyEngine:
    def __init__(
        self,
        hero_name: str = "generic",
        model_path: str = None,
        use_gpu: bool = True,
        num_mcts_sims: int = None,
        room_id: str = "unknown",
    ):
        self.hero_name = hero_name
        self.strategy: HeroStrategy = get_hero_strategy(hero_name)
        self.room_id = room_id

        try:
            from config.settings import SETTINGS
            default_model_path = SETTINGS.teacher_checkpoint
            default_mcts_sims  = SETTINGS.mcts_simulations
            default_device     = torch.device(SETTINGS.device if use_gpu else "cpu")
        except Exception:
            default_model_path = "data/checkpoints/teacher_latest.pt"
            default_mcts_sims  = 25
            default_device     = get_device() if use_gpu else torch.device("cpu")

        self.num_mcts_sims = num_mcts_sims if num_mcts_sims is not None else default_mcts_sims
        self.device = default_device
        self.model  = None

        target_path = model_path or default_model_path
        if target_path and os.path.exists(target_path):
            try:
                self.model, _ = create_model(target_path, str(self.device))
            except Exception as e:
                print(f"[PolicyEngine] Aviso ao inicializar modelo PyTorch: {e}")

        # Motor MCTS clássico (para estados com informação completa ou fallback)
        self.mcts = MCTSEngine(
            model=self.model,
            device=str(self.device),
            single_player_tree=True,
        )

        # Motor ISMCTS (para estados com mão oculta do oponente)
        self.ismcts = ISMCTSEngine(
            model=self.model,
            device=str(self.device),
        )

        # Logger de decisões ISMCTS
        self.ismcts_logger = ISMCTSLogger(
            room_id=self.room_id,
            hero=self.hero_name,
        )

    def set_model(self, model: FaBPolicyValueNetwork, device: torch.device = None):
        self.model = model
        if device:
            self.device = device
        self.mcts = MCTSEngine(
            model=self.model,
            device=str(self.device),
            single_player_tree=True,
        )
        self.ismcts = ISMCTSEngine(
            model=self.model,
            device=str(self.device),
        )

    def update_room_id(self, room_id: str, hero_name: str = None) -> None:
        """Atualiza room_id e hero do logger (chamado após o sideboard)."""
        self.room_id = room_id
        if hero_name:
            self.hero_name = hero_name
        self.ismcts_logger = ISMCTSLogger(
            room_id=self.room_id,
            hero=self.hero_name,
        )

    def get_weapon_cost(self, weapon_name: str, equip_dict: dict = None) -> int:
        """Retorna o custo em recursos para ativar a arma."""
        clean = str(weapon_name).lower()
        if clean in KNOWN_WEAPON_COSTS:
            return KNOWN_WEAPON_COSTS[clean]
        for kw, cost in [
            ("hammer", 3), ("anvilheim", 3), ("titans_fist", 3), ("pile_driver", 3), ("anothos", 3), ("rok", 3), ("club", 2),
            ("flail", 2), ("scythe", 2), ("staff", 2), ("meteor", 2), ("leveler", 2), ("symbiosis", 2), ("zenith", 2),
            ("saber", 1), ("sword", 1), ("dagger", 1), ("blade", 1), ("claw", 1), ("kodachi", 1), ("pistol", 1), ("bow", 1)
        ]:
            if kw in clean:
                return cost
        return 2

    # ── Extração e Normalização de Atributos de Cartas ─────────────

    def extract_card_info(self, card: dict) -> dict:
        card_number = str(card.get("cardNumber", "")).lower()
        pitch = 1
        if "_blue" in card_number:
            pitch = 3
        elif "_yellow" in card_number:
            pitch = 2
        elif "_red" in card_number:
            pitch = 1

        power = int(card.get("power", 0))
        block = int(card.get("defense", card.get("block", 0)))
        cost = 0
        has_go_again = False

        # Consulta banco de dados oficial (fab_cards_db.json)
        db_entry = _load_cards_db().get(card_number)
        if db_entry:
            if "cost" in db_entry:
                cost = max(0, int(db_entry["cost"]))
            if "pitch" in db_entry and db_entry["pitch"] > 0:
                pitch = int(db_entry["pitch"])
            if power == 0 and "power" in db_entry:
                power = int(db_entry["power"])
            if block == 0 and "defense" in db_entry:
                block = int(db_entry["defense"])
            if "has_go_again" in db_entry:
                has_go_again = bool(db_entry["has_go_again"])

        # Inferência de poder por heurística quando ausente no snapshot e banco
        if power == 0:
            if any(k in card_number for k in ["zipper", "throttle", "zero_to_sixty", "fast_and_furious", "out_pace", "expedite", "snatch"]):
                power = 4 if pitch == 1 else (3 if pitch == 2 else 2)
            elif "pounder" in card_number or "trebuchet" in card_number:
                power = 5
            elif "harpoon" in card_number or "command_and_conquer" in card_number:
                power = 6 if pitch == 1 else 4

        # Inferência de bloqueio padrão (FaB: maioria das cartas de ação defende 2 ou 3)
        if block == 0:
            if any(k in card_number for k in ["_red", "_yellow", "_blue"]) and not any(k in card_number for k in ["heart", "accelerator", "providence", "tunic"]):
                block = 3 if pitch == 3 else (2 if pitch == 2 else 2)

        # Custo de recurso heurístico se não estiver catalogado no banco
        if cost == 0 and not db_entry:
            if any(k in card_number for k in ["throttle", "pounder", "trebuchet", "staunch", "spinal", "mangle", "felling"]):
                cost = 2 if "throttle" in card_number else (4 if "mangle" in card_number else 3)
            elif any(k in card_number for k in ["zipper", "fast_and_furious", "out_pace", "expedite", "harpoon", "spark_of_genius", "command_and_conquer"]):
                cost = 1

        # Go Again heurístico se não estiver catalogado no banco
        if not has_go_again and not db_entry:
            if any(k in card_number for k in ["zero_to_sixty", "throttle", "zipper", "expedite", "out_pace", "fast_and_furious", "leg_tap", "snatch", "rising_knee", "fai"]):
                has_go_again = True

        # On-Hit Perigoso
        has_dangerous_on_hit = any(oh in card_number for oh in DANGEROUS_ON_HITS)

        return {
            "name": card_number,
            "raw": card,
            "pitch": pitch,
            "power": power,
            "block": block,
            "cost": cost,
            "has_go_again": has_go_again,
            "has_dangerous_on_hit": has_dangerous_on_hit,
            "action": card.get("action", 0),
            "actionDataOverride": card.get("actionDataOverride", ""),
            "borderColor": card.get("borderColor", 0),
            "subtype": card.get("subtype", ""),
            "text": card.get("text", ""),
            "type": card.get("type", ""),
        }

    def calculate_available_resources(self, state: dict) -> Tuple[int, int]:
        # Talishar armazena recursos flutuantes em playerPitchCount
        current_floating = int(state.get("playerPitchCount", 0))
        if current_floating == 0:
            resources = state.get("playerResources", [0, 0])
            current_floating = int(resources[0]) if isinstance(resources, list) and resources else 0
        hand = state.get("playerHand", [])
        total_potential_pitch = sum(self.extract_card_info(c)["pitch"] for c in hand)
        return current_floating, current_floating + total_potential_pitch

    # ══════════════════════════════════════════════════════════════
    # 1. PODA DE ATAQUE E SEQUENCIAMENTO DE CADEIA
    # ══════════════════════════════════════════════════════════════

    def select_best_attack(self, state: dict, unpayable_set: set) -> Optional[Dict[str, Any]]:
        turn_plan = self.strategy.analyze_turn_plan(state)
        floating_res, total_res = self.calculate_available_resources(state)
        hand = state.get("playerHand", [])
        player_ap = int(state.get("playerAP", state.get("actionPoints", 1)))
        
        candidates = []

        # ── 1.1 Coletar Ações na Mão ────────────────────────────────
        hand_attacks = []
        has_any_go_again = False

        for idx, c in enumerate(hand):
            info = self.extract_card_info(c)
            c_name = info["name"]
            c_id = info["actionDataOverride"] or str(idx)
            c_action = info["action"] if info["action"] > 0 else 27
            # Regra FaB CR 2.1.2: Cartas de Flecha (Arrow) NUNCA podem ser jogadas diretamente da mão!
            # Elas só podem ser jogadas a partir do Arsenal usando um Arco.
            c_db = _load_cards_db().get(c_name, {})
            c_subtype = str(c_db.get("subtype", "")).lower()
            if "arrow" in c_subtype or "arrow" in c_name:
                continue

            if info["action"] > 0 and c_name not in unpayable_set:
                card_cost = max(0, int(info.get("cost", 0)))
                # A própria carta atacante é gasta e não pode dar pitch para pagar a si mesma!
                # O pitch disponível para esta carta é (total_res - info["pitch"])
                pitch_from_other_cards = total_res - info["pitch"]
                if pitch_from_other_cards >= card_cost:
                    # ── Poda de Pitch Ineficiente para Guardião / Jarl:
                    # Se uma carta custa >= 3, mas para pagá-la precisaríamos pitchar 2 ou mais cartas vermelhas:
                    if (isinstance(self.strategy, GuardianStrategy) or self.strategy.is_heavy_hero) and card_cost >= 3:
                        has_blue_pitch = any(self.extract_card_info(x)["pitch"] == 3 for x in hand if x != c)
                        if floating_res < card_cost and not has_blue_pitch:
                            # Tentar pagar custo 3 apenas com cartas vermelhas destrói a mão e causa undos
                            base_score = self.strategy.evaluate_attack_card(
                                c_name, info["power"], card_cost, info["has_go_again"], info["pitch"]
                            ) - 25.0
                        else:
                            base_score = self.strategy.evaluate_attack_card(
                                c_name, info["power"], card_cost, info["has_go_again"], info["pitch"]
                            )
                    else:
                        base_score = self.strategy.evaluate_attack_card(
                            c_name, info["power"], card_cost, info["has_go_again"], info["pitch"]
                        )

                    # ── Ajustes Táticos Baseados no TurnPlan ─────────────────
                    c_clean = str(c.get("cardNumber") or c_name).lower()
                    if turn_plan.plan_type == "PIVOT_OAKEN_OLD_FUSED" and "oaken_old" in c_clean:
                        base_score += 35.0  # Fused Oaken Old é o finalizador absoluto
                    elif turn_plan.plan_type == "OVERPITCH_RECOVERY" and any(k in c_clean for k in ["codex_of_frailty", "sea_floor_salvage", "tip_the_barkeep"]):
                        base_score += 30.0  # Prioridade máxima: jogar NAA de recuperação para recarregar o arsenal
                    elif turn_plan.plan_type == "HARPOON_CHAIN" and any(k in c_clean for k in ["portside_exchange", "three_of_a_kind", "cheating_scoundrel"]):
                        base_score += 20.0  # Buffs antes do disparo do arsenal
                    elif c_name in turn_plan.reserved_card_names or c_clean in turn_plan.reserved_card_names:
                        base_score += 15.0  # Peça chave do plano ofensivo reservada

                    if info["has_go_again"]:
                        has_any_go_again = True
                    hand_attacks.append({
                        "type": "hand", "idx": idx, "card_id": c_id, "mode": c_action,
                        "name": c_name, "score": base_score, "cost": card_cost,
                        "power": info["power"], "has_go_again": info["has_go_again"],
                        "pitch": info["pitch"]
                    })

        # ── 1.2 Poda Tática de Go Again (Evitar quebrar a cadeia prematuramente)
        # Se temos AP == 1 e múltiplos ataques na mão, e pelo menos um tem Go Again:
        # Penalizamos severamente iniciar o turno com um ataque SEM Go Again.
        for atk in hand_attacks:
            if player_ap <= 1 and has_any_go_again and not atk["has_go_again"] and len(hand_attacks) > 1:
                # Se não for letal (power < oponente_hp), penaliza iniciar com non-go-again
                atk["score"] -= 4.0
            elif atk["has_go_again"] and atk["cost"] == 0:
                # Bônus para abrir cadeia com starter de custo zero
                atk["score"] += 1.5

            candidates.append(atk)

        # ── 1.3 Armas ───────────────────────────────────────────────
        equip = state.get("playerEquipment", [])
        for eq in equip:
            action = eq.get("action", 0)
            eq_name = str(eq.get("cardNumber", "Equip")).lower()
            if action > 0 and eq_name not in unpayable_set:
                eq_id = eq.get("actionDataOverride", eq_name)
                is_weapon = (
                    eq_name in ALL_FAB_WEAPONS
                    or any(w in eq_name for w in WEAPON_KEYWORDS)
                    or str(eq.get("slot", "")).lower() in ("weapon", "off-hand", "hands")
                )
                if is_weapon:
                    weapon_cost = self.get_weapon_cost(eq_name, eq)
                    # Poda estrita de Ranger/Marlynn: canhão/arco NUNCA carrega flecha se o Arsenal já estiver cheio!
                    is_bow_or_cannon = (
                        "bow" in str(_load_cards_db().get(eq_name, {}).get("subtype", "")).lower()
                        or any(b in eq_name for b in ["hammerhead", "shiver", "death_dealer", "dread_bore", "redback", "cannon"])
                    )
                    if is_bow_or_cannon:
                        arsenal_cards = state.get("playerArsenal", [])
                        if isinstance(arsenal_cards, list) and len(arsenal_cards) > 0:
                            # Arsenal já ocupado -> proibido ativar arco/canhão para evitar 'Arsenal is full'
                            continue
                        if turn_plan.plan_type == "DEFENSIVE_TRAP":
                            # Sem flechas viáveis: não gastar recursos ativando o arco à toa!
                            continue

                    # Poda estrita: toda a mão + flutuante deve suprir o custo da arma
                    if total_res >= weapon_cost:
                        eq_info = self.extract_card_info(eq)
                        weapon_power = eq_info.get("power", 0) or int(eq.get("power", 0))
                        if weapon_power == 0:
                            weapon_power = int(_load_cards_db().get(eq_name, {}).get("power", 0))
                        weapon_score = self.strategy.evaluate_weapon_attack(
                            eq_name, floating_res, total_res, len(hand_attacks) > 0
                        )
                        if not has_any_go_again and len(hand_attacks) == 0:
                            weapon_score += 2.0
                        if is_bow_or_cannon:
                            weapon_score += 8.0  # Prioridade para carregar flecha no arsenal livre
                            if turn_plan.plan_type == "HARPOON_CHAIN":
                                weapon_score += 15.0  # Carga de canhão essencial para a cadeia
                        candidates.append({
                            "type": "weapon", "idx": 0, "card_id": str(eq_id), "mode": action,
                            "name": eq_name, "score": weapon_score, "cost": weapon_cost,
                            "power": weapon_power
                        })

        # ── 1.4 Arsenal e Banish ────────────────────────────────────
        for zone_name, key in [("Arsenal", "playerArsenal"), ("Banish", "playerBanish")]:
            zone = state.get(key, [])
            for c in zone:
                action = c.get("action", 0)
                c_name = str(c.get("cardNumber", "Card")).lower()
                if action > 0 and c_name not in unpayable_set:
                    c_id = c.get("actionDataOverride", c_name)
                    c_info = self.extract_card_info(c)
                    card_cost = max(0, int(c_info.get("cost", 0)))
                    # Cartas de Arsenal/Banish usam total_res da mão inteira
                    if total_res >= card_cost:
                        base_score = self.strategy.evaluate_attack_card(
                            c_name, c_info["power"], card_cost, c_info["has_go_again"], c_info["pitch"]
                        )
                        # Jogar do Arsenal executa a ofensiva e libera o slot para o canhão carregar nova flecha
                        arsenal_score = base_score + 4.0
                        # Se a carta no Arsenal for uma Non-Attack Action (ex: Portside Exchange, Codex of Frailty):
                        # Jogar do Arsenal PRIMEIRO libera o slot e concede bônus antes do disparo!
                        c_type = str(_load_cards_db().get(c_name, {}).get("type", "")).upper()
                        is_naa = ("AA" not in c_type and "ATTACK" not in c_type) or any(k in c_name for k in ["portside", "codex", "salvage", "three_of_a_kind", "tip_the_barkeep"])
                        if is_naa:
                            arsenal_score += 15.0  # Prioridade máxima: jogue a NAA do arsenal para liberar o slot!
                            if turn_plan.plan_type == "OVERPITCH_RECOVERY":
                                arsenal_score += 15.0
                        elif any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy"]) or isinstance(self.strategy, RangerStrategy):
                            arsenal_score += 10.0  # Flecha carregada no arsenal pronta para disparo!
                            if turn_plan.plan_type == "HARPOON_CHAIN":
                                arsenal_score += 15.0
                        candidates.append({
                            "type": zone_name.lower(), "idx": 0, "card_id": str(c_id), "mode": action,
                            "name": c_name, "score": arsenal_score, "cost": card_cost,
                            "power": c_info["power"], "has_go_again": c_info["has_go_again"]
                        })

        if not candidates:
            return None

        # ── 1.5 Refinamento via Busca em Árvore ─────────────────────
        if len(candidates) > 1 and self.num_mcts_sims > 0:
            opp_hand = state.get("opponentHand", [])
            if isinstance(opp_hand, list) and len(opp_hand) > 0:
                opp_hand_count = len(opp_hand)
            else:
                opp_hand_count = int(
                    state.get("opponentHandCount", state.get("theirHandCount", 0))
                )

            # Usa ISMCTS quando o oponente tem cartas na mão (informação imperfeita real)
            if opp_hand_count > 0:
                best_idx, policy_dist, ismcts_log = self.ismcts.search_ismcts(
                    state=state,
                    legal_actions=candidates,
                    num_simulations=self.num_mcts_sims,
                )
                # Enriquece a ação escolhida com metadados ISMCTS para logging no bot
                chosen = candidates[best_idx]
                chosen["_ismcts_log"] = ismcts_log
                chosen["_policy_dist"] = policy_dist

                # ── Persistência de Telemetria ISMCTS Direta ──────────
                try:
                    self.ismcts_logger.log(
                        ismcts_log=ismcts_log,
                        turn=int(state.get("turnNo", state.get("turn", 0))),
                        phase=str(state.get("turnPhase", state.get("phase", "M"))),
                    )
                except Exception:
                    pass

                return chosen
            else:
                # MCTS clássico: estado de informação completa (mão do oponente vazia / início de turno)
                best_mcts_idx, policy_dist = self.mcts.search(
                    state=state,
                    legal_actions=candidates,
                    num_simulations=self.num_mcts_sims,
                )
                chosen = candidates[best_mcts_idx]
                chosen["_policy_dist"] = policy_dist
                return chosen

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[0]


    # ══════════════════════════════════════════════════════════════
    # 2. PODA DE PITCH (Pitch Efficiency: Blue > Yellow > Red com ISMCTS)
    # ══════════════════════════════════════════════════════════════

    def select_best_pitch_card(self, state: dict) -> Optional[Tuple[int, str, int]]:
        hand = state.get("playerHand", [])
        if not hand:
            return None

        turn_plan = self.strategy.analyze_turn_plan(state)
        pitch_candidates = []
        for idx, c in enumerate(hand):
            info = self.extract_card_info(c)
            c_clean_name = str(c.get("cardNumber") or info["name"]).lower()
            c_action = info["action"] if info["action"] > 0 else 27
            score = self.strategy.evaluate_pitch_card(
                info["name"], info["pitch"], info["cost"], info["power"], info["has_go_again"]
            )
            # Poda estrita de pitch: JAMAIS dar pitch em finalizador reservado do plano ofensivo
            is_reserved_finisher = (
                (info["name"] in turn_plan.reserved_card_names or c_clean_name in turn_plan.reserved_card_names)
                and info["pitch"] == 1
            )
            if is_reserved_finisher:
                score -= 100.0

            # Poda estrita: dar pitch em carta vermelha com alto poder (power >= 5)
            # é penalizado pesadamente a menos que seja a única carta da mão
            if info["pitch"] == 1 and info["power"] >= 4:
                score -= 3.0
            # Prioridade absoluta para Azuis (Pitch 3)
            elif info["pitch"] == 3:
                score += 4.0

            pitch_candidates.append({
                "type": "pitch",
                "idx": idx,
                "card_id": info["actionDataOverride"] or str(idx),
                "mode": c_action,
                "name": info["name"],
                "pitch": info["pitch"],
                "score": score
            })

        if not pitch_candidates:
            return None

        # Refinamento ISMCTS / MCTS quando há múltiplas escolhas de pitch
        if len(pitch_candidates) > 1 and self.num_mcts_sims > 0:
            opp_hand = state.get("opponentHand", [])
            opp_hand_count = len(opp_hand) if isinstance(opp_hand, list) and len(opp_hand) > 0 else int(
                state.get("opponentHandCount", state.get("theirHandCount", 0))
            )
            if opp_hand_count > 0:
                best_idx, _, ismcts_log = self.ismcts.search_ismcts(
                    state=state,
                    legal_actions=pitch_candidates,
                    num_simulations=self.num_mcts_sims,
                )
                try:
                    self.ismcts_logger.log(
                        ismcts_log=ismcts_log,
                        turn=int(state.get("turnNo", state.get("turn", 0))),
                        phase="PITCH",
                    )
                except Exception:
                    pass
                chosen = pitch_candidates[best_idx]
                return chosen["idx"], chosen["name"], chosen["mode"]
            else:
                best_idx, _ = self.mcts.search(
                    state=state,
                    legal_actions=pitch_candidates,
                    num_simulations=self.num_mcts_sims,
                )
                chosen = pitch_candidates[best_idx]
                return chosen["idx"], chosen["name"], chosen["mode"]

        pitch_candidates.sort(key=lambda x: x["score"], reverse=True)
        best = pitch_candidates[0]
        return best["idx"], best["name"], best["mode"]

    # ══════════════════════════════════════════════════════════════
    # 3. PODA DE BLOQUEIO E DEFESA (Overblocking, Breakpoint & ISMCTS Defense)
    # ══════════════════════════════════════════════════════════════

    def select_defense_blocks(self, state: dict) -> List[Tuple[int, str, str, int]]:
        hand = state.get("playerHand", [])
        my_hp = int(state.get("playerHealth", 20))
        
        active_chain = state.get("activeChainLink", {})
        if not isinstance(active_chain, dict):
            active_chain = {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 4)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()
        has_dangerous_on_hit = any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        # ── 3.1 Detecção Holística de Plano de Turno e Pivot ────────
        turn_plan = self.strategy.analyze_turn_plan(state)
        is_heavy_hero = getattr(self.strategy, "is_heavy_hero", False)

        block_candidates = []
        for idx, c in enumerate(hand):
            info = self.extract_card_info(c)
            if info["action"] > 0 or info["borderColor"] > 0 or info["block"] > 0:
                c_id = info["actionDataOverride"] or str(idx)
                c_action = info["action"] if info["action"] > 0 else 27
                score = self.strategy.evaluate_block_card(
                    info["name"], info["block"], info["pitch"], info["power"], info["has_go_again"]
                )

                # ── Poda Estrita de Peças Reservadas pelo TurnPlan ────────
                c_clean_name = str(c.get("cardNumber") or info["name"]).lower()
                is_reserved = (
                    info["name"] in turn_plan.reserved_card_names
                    or c_clean_name in turn_plan.reserved_card_names
                    or any(r.lower() == c_clean_name for r in turn_plan.reserved_card_names)
                )
                if is_reserved and turn_plan.can_absorb_damage:
                    # Se o plano determinou absorver dano para pivotar, peças reservadas
                    # NUNCA bloqueiam a menos que estejamos sob risco letal iminente
                    if my_hp > 6 and not (has_dangerous_on_hit and opp_power >= my_hp):
                        score -= 150.0

                # ── Poda de Preservação de Mão Ofensiva:
                # Se temos vida alta (> 20) e o ataque inimigo é fraco (<= 2 sem on-hit),
                # penaliza queimar cartas vermelhas de ataque chave (power >= 4 e pitch == 1)
                if my_hp > 20 and not has_dangerous_on_hit and opp_power <= 2:
                    if info["power"] >= 4 and info["pitch"] == 1:
                        score -= 5.0

                # ── Poda de Tempo Pivot e Reserva Estrita de Azul (Guardião / Jarl):
                if (is_heavy_hero or turn_plan.can_absorb_damage) and my_hp >= 8 and not has_dangerous_on_hit:
                    if info["pitch"] == 1 and info["power"] >= 6:
                        score -= 25.0  # Nunca bloqueia com a bomba de ataque de Pivot
                    elif info["pitch"] == 3:
                        blue_count = len([x for x in hand if self.extract_card_info(x)["pitch"] == 3])
                        # Se Jarl/Guardião só tem 1 azul na mão: PRESERVAÇÃO ABSOLUTA para o turno de ataque!
                        if blue_count <= 1:
                            score -= 30.0  # Bloquear com a única azul deixaria o herói desativado no contra-ataque
                        elif blue_count == 2 and is_heavy_hero:
                            score -= 15.0  # Preserva a 2ª azul para fusão elemental / pagar ataque de custo 3 + Titan's Fist

                # Bônus para reações de defesa dedicadas (Sink, Fate, Staunch)
                if info["block"] >= 3 and any(k in info["name"] for k in ["sink", "fate", "staunch", "unmovable"]):
                    score += 3.0

                if score > -100.0 and info["block"] > 0:
                    block_candidates.append({
                        "type": "block", "score": score, "idx": idx, "card_id": c_id,
                        "name": info["name"], "mode": c_action, "block": info["block"],
                        "pitch": info["pitch"], "power": info["power"]
                    })

        # ── 3.1b Cartas no Arsenal que podem defender (Ambush e Down and Dirty) ──
        cards_db = _get_cards_db()
        arsenal = state.get("playerArsenal", [])
        for a_idx, c in enumerate(arsenal):
            info = self.extract_card_info(c)
            c_name_low = info["name"].lower()
            c_action = info.get("action", 0)
            db_entry = cards_db.get(c_name_low, {})
            card_text = (db_entry.get("text", "") if db_entry else "").lower()
            subtype = (db_entry.get("subtype", "") if db_entry else "").lower()
            is_down_and_dirty = "down_and_dirty" in c_name_low or "down and dirty" in c_name_low
            has_ambush = (
                "ambush" in subtype
                or "ambush" in card_text
                or "defend with this from your arsenal" in card_text
                or "ambush" in c_name_low
                or is_down_and_dirty
            )
            if has_ambush and info["block"] > 0:
                # Down and Dirty ganha +1 de defesa defendendo do arsenal (defende 4 em vez de 3!)
                effective_block = info["block"] + (1 if is_down_and_dirty else 0)
                # Defender do arsenal é altamente vantajoso: preserva a mão ofensiva e limpa o arsenal!
                score = float(effective_block) * 2.5 + 5.0
                c_id = info["actionDataOverride"] or str(a_idx)
                block_candidates.append({
                    "type": "block", "score": score, "idx": a_idx, "card_id": c_id,
                    "name": info["name"], "mode": c_action if c_action > 0 else 27,
                    "block": effective_block, "pitch": info["pitch"], "power": info["power"],
                    "from_arsenal": True
                })

        if not block_candidates:
            return []

        # ── 3.2 Refinamento ISMCTS para Bloqueio ────────────────────
        if len(block_candidates) > 1 and self.num_mcts_sims > 0:
            opp_hand = state.get("opponentHand", [])
            opp_hand_count = len(opp_hand) if isinstance(opp_hand, list) and len(opp_hand) > 0 else int(
                state.get("opponentHandCount", state.get("theirHandCount", 0))
            )
            if opp_hand_count > 0:
                best_idx, _, ismcts_log = self.ismcts.search_ismcts(
                    state=state,
                    legal_actions=block_candidates,
                    num_simulations=self.num_mcts_sims,
                )
                try:
                    self.ismcts_logger.log(
                        ismcts_log=ismcts_log,
                        turn=int(state.get("turnNo", state.get("turn", 0))),
                        phase="BLOCK",
                    )
                except Exception:
                    pass
                # Prioriza a melhor carta selecionada pelo ISMCTS
                best_item = block_candidates[best_idx]
                best_item["score"] += 10.0

        # Ordenar melhores cartas defensivas primeiro
        block_candidates.sort(key=lambda x: x["score"], reverse=True)
        
        chosen_blocks = []
        current_blocked = 0

        # Limite máximo de cartas para bloquear
        if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= my_hp):
            max_blocks = len(block_candidates)  # Modo Sobrevivência (Bloqueio total)
        elif turn_plan.can_absorb_damage:
            # Respeita estritamente o limite de bloqueios do plano (ex: 0 no Fused Oaken Old pivot!)
            max_blocks = min(turn_plan.max_block_cards, len(block_candidates))
        elif my_hp <= 12:
            max_blocks = min(3, len(block_candidates))
        else:
            max_blocks = min(2, len(block_candidates))

        for item in block_candidates:
            if len(chosen_blocks) >= max_blocks:
                break
            
            # Poda de Bloqueio Ineficiente: Não bloqueia se score for muito negativo com HP alto
            if my_hp > 15 and item["score"] < 0 and not has_dangerous_on_hit:
                continue

            chosen_blocks.append((item["idx"], item["card_id"], item["name"], item["mode"]))
            current_blocked += item["block"]

            # ── Poda de Overblocking Exato:
            # Se já bloqueamos todo o dano do ataque e não estamos em perigo letal,
            # pára imediatamente de adicionar cartas para não queimar a mão do próximo turno
            if current_blocked >= opp_power and my_hp > 6:
                break

        return chosen_blocks

    # ══════════════════════════════════════════════════════════════
    # 4. PODA DE ARSENAL (Regra Oficial: Proibido Pitch do Arsenal)
    # ══════════════════════════════════════════════════════════════

    def select_arsenal_card(self, state: dict) -> Optional[Tuple[str, str]]:
        """
        Seleciona a melhor carta para colocar no Arsenal no fim do turno.
        
        Regra Oficial de FaB (CR 3.1.5): Cartas no Arsenal NÃO podem ser dadas pitch.
        Portanto, colocar cartas de recurso (R), gemas ou pitch puro no Arsenal tranca o slot.
        Se nenhuma carta for taticamente vantajosa ou todas forem recursos, retorna None (passar).
        """
        hand = state.get("playerHand", [])
        if not hand:
            return None

        cards_db = _get_cards_db()
        valid_candidates = []

        for c in hand:
            info = self.extract_card_info(c)
            c_name = info["name"].lower()
            c_id = info["actionDataOverride"] or info["name"]
            db_entry = cards_db.get(c_name, {})

            # 1. Filtro Global Universal: Recursos e Gemas são ESTRITAMENTE PROIBIDOS no Arsenal para qualquer herói!
            if is_resource_or_gem_card(c_name, info, db_entry):
                continue

            # 2. Avaliação polimórfica via HeroStrategy (com desvalorização estrita de cartas de bloco não-DR)
            score = self.strategy.evaluate_arsenal_card(info, db_entry)

            # Só considera cartas com score positivo (vantajosas de verdade para o próximo turno)
            if score > 0:
                valid_candidates.append((score, info["name"], c_id))

        if not valid_candidates:
            # ── 2. Modo Cavar (Digging Mode) para Mão Travada de Recursos (len(hand) >= 3) ───
            # Se nenhuma carta atingiu score > 0 e a mão possui 3 ou mais cartas:
            # Se não colocarmos nada no Arsenal, o jogador compra 0 ou 1 carta no End of Turn
            # e continua travado com recursos. Então, deve-se arsenalar 1 carta para cavar!
            if len(hand) >= 3:
                dig_candidates = []
                for c in hand:
                    info = self.extract_card_info(c)
                    c_name = info["name"].lower()
                    c_id = info["actionDataOverride"] or info["name"]
                    db_entry = cards_db.get(c_name, {})

                    # Gemas puras lendárias são a última opção possível (pois não têm ação jogável)
                    is_pure_gem = "gem" in (db_entry.get("subtype", "")).lower() or any(
                        k in c_name for k in ["heart_of_fyendal", "eye_of_ophidia", "grandeur_of_valahai", "arknight_shard"]
                    )

                    # Priorização para Cavar:
                    # 1. Prefere cartas de ação que possam ser jogadas no próximo turno para limpar o Arsenal
                    # 2. Cartas com poder de ataque maior ganham preferência
                    # 3. Cartas de menor custo ganham preferência
                    # 4. Gemas puras sofrem forte penalidade (-100.0)
                    dig_score = float(info.get("power", 0)) * 3.0
                    card_type = (db_entry.get("type", "") or info.get("type", "")).upper()
                    if "A" in card_type or info.get("action", 0) > 0:
                        dig_score += 10.0
                    if info.get("cost", 0) == 0:
                        dig_score += 2.0
                    if is_pure_gem:
                        dig_score -= 100.0

                    dig_candidates.append((dig_score, info["name"], c_id))

                if dig_candidates:
                    dig_candidates.sort(key=lambda x: x[0], reverse=True)
                    best_dig = dig_candidates[0]
                    return best_dig[1], best_dig[2]

            # Se tem 1 ou 2 recursos na mão, NÃO ARSENALA:
            # Mantém para pitch no próximo turno e compra cartas até o intelecto normalmente
            return None

        valid_candidates.sort(key=lambda x: x[0], reverse=True)
        best = valid_candidates[0]
        return best[1], best[2]
