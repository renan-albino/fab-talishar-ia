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
import itertools
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
    KassaiStrategy,
    HalaStrategy,
    RangerStrategy,
    MarlynnStrategy,
    NinjaStrategy,
    MechanologistStrategy,
    RunebladeStrategy,
    VynnsetStrategy,
    TeklovossenStrategy,
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

_FAB_ABILITY_COSTS = None

def _load_ability_costs() -> dict:
    global _FAB_ABILITY_COSTS
    if _FAB_ABILITY_COSTS is None:
        db_paths = [
            "data/ability_costs.json",
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "ability_costs.json")
        ]
        for p in db_paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        _FAB_ABILITY_COSTS = json.load(f)
                    break
                except Exception:
                    pass
        if _FAB_ABILITY_COSTS is None:
            _FAB_ABILITY_COSTS = {}
    return _FAB_ABILITY_COSTS


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

# Mapeamento hierárquico de valor de ameaça de On-Hit (0.0 = vanilla, 10.0 = catastrófico)
ON_HIT_THREAT_VALUES = {
    # Catastrófico (8.0 - 10.0): Destrói arsenal / Trava o próximo turno / Descarta cartas
    "command_and_conquer": 10.0,
    "red_in_the_ledger": 9.5,
    "spinal_crush": 9.0,
    "crippling_crush": 9.0,
    "rightful_king": 8.5,
    "hypothermia": 8.0,

    # Alto (5.0 - 7.5): Compra de cartas pelo oponente / Banimento / Interrupção
    "herald_of_erudition": 7.0,
    "mask_of_momentum": 6.5,
    "surgical_extraction": 6.5,
    "snatch": 6.0,
    "leave_no_witnesses": 6.0,
    "erase_face": 5.5,
    "spitfire": 5.0,

    # Médio (3.0 - 4.5): Efeitos de aflição / Debuff / Taxa de recurso
    "bloodrot": 4.0,
    "frailty": 3.5,
    "inertia": 3.5,
    "frostbite": 3.5,
    "freeze": 3.5,
    "widespread_ruin": 3.5,
}

def get_on_hit_threat(card_name: str, card_text: str = "") -> float:
    """Calcula o valor numérico de ameaça de um efeito On-Hit (0.0 a 10.0)."""
    name_low = str(card_name or "").lower().strip()
    text_low = str(card_text or "").lower()

    for k, threat in ON_HIT_THREAT_VALUES.items():
        if k in name_low:
            return threat

    if "when this hits" in text_low or "if this hits" in text_low or "hit effect" in text_low:
        if "destroy" in text_low and "arsenal" in text_low:
            return 10.0
        if "draw" in text_low:
            return 6.0
        if "discard" in text_low:
            return 7.0
        if any(token in text_low for token in ["bloodrot", "frailty", "inertia"]):
            return 4.0
        return 3.0

    return 0.0

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
    "hammer_of_havenhold", "hammerhead_harpoon_cannon", "hanabi_blaster", "harmonized_kodachi", "harmonized_kodachi_r",
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
    "hammerhead_harpoon_cannon": 4,
    "anothos": 3, "sledge_of_anvilheim": 3, "titans_fist": 3, "pile_driver": 3, "rok": 3,
    "hell_hammer": 3, "hammer_of_havenhold": 3, "redwood_hammer": 3, "ball_breaker": 3,
    "romping_club": 2, "flail_of_agony": 2, "dread_scythe": 2, "reaping_blade": 2,
    "zenith_blade": 2, "harmonious_pipe": 2, "claw_of_vynserakai": 2, "hunters_klaive": 2,
    "hunters_klaive_r": 2, "volzar_meteor_storm": 2, "symbiosis_shot": 2,
    "plasma_barrel_shot": 2, "hanabi_blaster": 2, "waning_moon": 2, "krakens_aethervein": 2,
    "cintari_saber": 1, "cintari_saber_r": 1, "hot_streak": 1, "dawnblade": 1, "dawnblade_resplendent": 1,
    "kunai_of_retribution": 1, "kunai_of_retribution_r": 1, "harmonized_kodachi": 1,
    "harmonized_kodachi_r": 1, "mandible_claw": 1, "mandible_claw_r": 1, "spiders_bite": 1,
    "nerve_scalpel": 1, "nerve_scalpel_r": 1, "scale_peeler": 1, "scale_peeler_r": 1,
    "orbitoclast": 1, "orbitoclast_r": 1, "teklo_plasma_pistol": 1, "death_dealer": 1,
    "rosetta_thorn": 1, "nebula_blade": 1, "galaxxi_black": 1,
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

    def get_weapon_cost(self, weapon_name: str, equip_dict: dict = None, state: dict = None) -> int:
        """Retorna o custo em recursos para ativar a arma ou habilidade de equipamento."""
        clean = str(weapon_name).lower()

        # Regra Oficial Teklo Leveler (Joseph Qiu - EVO009):
        # • Com 0 ou 1 Evo equipado: Custo {r}{r}{r} (3 recursos), Poder 2, sem Go Again (arma é igual com 0 e 1 Evos).
        # • Com 2+ Evos equipados: Custa {r}{r} a menos -> Custa apenas {r} (1 recurso)!
        if "leveler" in clean or "teklo_leveler" in clean:
            equip_list = state.get("playerEquipment", []) if state else []
            evos_equipped = sum(1 for eq in equip_list if isinstance(eq, dict) and ("evo" in str(eq.get("cardNumber", "")).lower() or "evo" in str(eq.get("subtype", "")).lower()))
            if evos_equipped <= 1:
                return 3
            else:
                return 1

        # 1. Consulta banco dinâmico de custos de habilidades extraídos do Talishar
        ability_costs = _load_ability_costs()
        cost = None
        if clean in ability_costs:
            cost = ability_costs[clean]
        elif clean in _load_cards_db() and "ability_cost" in _load_cards_db()[clean]:
            cost = int(_load_cards_db()[clean]["ability_cost"])
        elif clean in KNOWN_WEAPON_COSTS:
            cost = KNOWN_WEAPON_COSTS[clean]
        else:
            for kw, kw_cost in [
                ("hammer", 3), ("anvilheim", 3), ("titans_fist", 3), ("pile_driver", 3), ("anothos", 3), ("rok", 3), ("club", 2),
                ("flail", 2), ("scythe", 2), ("staff", 2), ("meteor", 2), ("symbiosis", 2), ("zenith", 2),
                ("saber", 1), ("sword", 1), ("dagger", 1), ("blade", 1), ("claw", 1), ("kodachi", 1), ("pistol", 1), ("bow", 1)
            ]:
                if kw in clean:
                    cost = kw_cost
                    break
            if cost is None:
                cost = 2

        # 2. Modificadores Dinâmicos de Custo Baseados em Estado
        if state:
            # Passiva da Kassai: Se comprou carta no turno e ataca com Espada, reduz o custo em 1
            hero_name = str(self.hero_name).lower()
            if "kassai" in hero_name or "kassai" in str(state.get("playerHero", "")).lower():
                num_drawn = int(state.get("cardsDrawnThisTurn", state.get("numCardsDrawn", state.get("num_drawn", state.get("numDrawn", 0)))))
                if num_drawn >= 1 and any(s in clean for s in ["saber", "sword", "blade", "cintari"]):
                    cost = max(0, cost - 1)

        return cost

    @staticmethod
    def get_all_known_zone_cards(state: dict) -> Dict[str, List[dict]]:
        """
        Retorna um mapa consolidado de todas as cartas em todas as zonas do jogo:
        Mão, Equipamentos, Arsenal, Banish, Cemitério (Discard), Alma (Soul), Pitch e Combat Chain.
        Permite que qualquer herói ou módulo de IA faça contagem de cartas (card counting),
        verificação de recursão e rastreamento de peças do deck em todas as zonas.
        """
        if not isinstance(state, dict):
            return {}
        return {
            "hand": [c for c in state.get("playerHand", []) if isinstance(c, dict)],
            "equipment": [c for c in state.get("playerEquipment", []) if isinstance(c, dict)],
            "arsenal": [c for c in (state.get("playerArsenal") or state.get("playerArse") or []) if isinstance(c, dict)],
            "banish": [c for c in state.get("playerBanish", []) if isinstance(c, dict)],
            "graveyard": [c for c in (state.get("playerGraveyard") or state.get("playerDiscard") or []) if isinstance(c, dict)],
            "soul": [c for c in state.get("playerSoul", []) if isinstance(c, dict)],
            "pitch": [c for c in state.get("playerPitch", []) if isinstance(c, dict)],
            "combat_chain": [c for c in state.get("combatChain", []) if isinstance(c, dict)],
            "opponent_graveyard": [c for c in (state.get("opponentGraveyard") or state.get("opponentDiscard") or []) if isinstance(c, dict)],
            "opponent_banish": [c for c in state.get("opponentBanish", []) if isinstance(c, dict)],
        }

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
            if "pitch" in db_entry:
                pitch = int(db_entry["pitch"])
            if power == 0 and "power" in db_entry:
                power = int(db_entry["power"])
            if block == 0 and "defense" in db_entry:
                block = int(db_entry["defense"])
            if "has_go_again" in db_entry:
                has_go_again = bool(db_entry["has_go_again"])

        is_equip_or_weapon = (
            "hammerhead" in card_number
            or (db_entry and db_entry.get("type") in ("W", "E", "C"))
            or str(card.get("slot", "")).lower() in ("weapon", "head", "chest", "arms", "legs", "off-hand", "hero")
        )

        # Inferência de poder por heurística quando ausente no snapshot e banco (somente cartas jogáveis do deck)
        if power == 0 and not is_equip_or_weapon:
            if any(k in card_number for k in ["zipper", "throttle", "zero_to_sixty", "fast_and_furious", "out_pace", "expedite", "snatch"]):
                power = 4 if pitch == 1 else (3 if pitch == 2 else 2)
            elif "pounder" in card_number or "trebuchet" in card_number:
                power = 5
            elif ("harpoon" in card_number and "hammerhead" not in card_number) or "command_and_conquer" in card_number:
                power = 6 if pitch == 1 else 4

        # Exceção especial FaB: Goldfin Harpoon não defende (block = 0) e não gera recurso (pitch = 0)
        if "goldfin" in card_number:
            pitch = 0
            block = 0

        # Inferência de bloqueio padrão (FaB: maioria das cartas de ação e flechas defende 2 ou 3)
        # Regra Oficial FaB: Itens (Item), Aliados (Ally) e certas Auras NÃO possuem defesa (defense: None)
        # e NUNCA podem ser usados para defender. Flechas (Arrows) POSSUEM defesa legítima (exceto Goldfin Harpoon).
        subtype_str = str((db_entry.get("subtype") if db_entry else "") or card.get("subtype", "")).lower()
        is_non_blocking_type = (
            any(nb in subtype_str for nb in ["item", "ally", "landmark"])
            or "goldfin" in card_number
            or any(k in card_number for k in [
                "boom_grenade", "convection_amplifier", "penetration_script",
                "teklo_core", "cerebellum_processor", "null_time_zone",
                "teklo_pounder", "teklo_trebuchet", "plasma_mainline",
                "dissolving_shield", "hyper_driver", "payload", "quiver"
            ])
        )
        if is_non_blocking_type:
            block = 0
        elif block == 0 and not is_equip_or_weapon:
            # Para cartas de ação convencionais (AA ou A) e Flechas onde a defesa não veio catalogada no banco,
            # infere a defesa padrão do Flesh and Blood (3 para azul, 2 para amarelo/vermelho)
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

    def is_teklovossen_ability_active(self, state: dict) -> bool:
        """
        Regra oficial FaB: Evos do Banish só ganham a opção de serem jogados como Instant
        se a habilidade de Teklovossen ({r}{r}: Bane Evo da mão, compra carta) tiver sido ativada no turno.
        Caso contrário, permanecem banidos e indisponíveis para jogo ("fica lá banido").
        """
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

    def select_best_attack(self, state: dict, unpayable_set: Optional[set] = None) -> Optional[Dict[str, Any]]:
        if unpayable_set is None:
            unpayable_set = set()
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
                    elif "singularity" in c_clean:
                        base_score += 35.0  # Singularity é a condição de vitória absoluta de Teklovossen
                    elif turn_plan.plan_type == "HALA_ZENITH_PRESSURE" and any(k in c_clean for k in ["edict_of_steel", "imperial_seal", "brimming_blade", "ironsong"]):
                        base_score += 25.0  # Buffs de Guerreiro DEVEM ser jogados antes do ataque da espada!
                    elif (isinstance(self.strategy, WarriorStrategy) or "warrior" in str(self.hero_name).lower() or "hala" in str(self.hero_name).lower() or "kassai" in str(self.hero_name).lower()) and any(k in c_clean for k in ["edict_of_steel", "imperial_seal", "brimming_blade", "blood_on_her_hands", "spoils_of_war", "hit_and_run"]):
                        base_score += 20.0  # Sequenciar NAA buffs sempre antes do swing da arma
                    elif "avast_ye" in c_clean:
                        # Avast Ye! concede Go Again ao aliado/ataque e gera Gold no hit!
                        allies = state.get("playerAllies", [])
                        has_ready_allies = any(isinstance(a, dict) and a.get("action", 0) > 0 for a in (allies or []))
                        has_other_attacks = any(
                            self.extract_card_info(x)["power"] > 0 for x in hand if x != c
                        )
                        if has_ready_allies or has_other_attacks:
                            base_score += 30.0  # Prioridade máxima: jogar Avast Ye! antes do aliado/ataque!
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

        # ── 1.3 Equipamentos, Armas e Habilidades de Herói ─────────
        equip = state.get("playerEquipment", [])
        for eq in equip:
            action = eq.get("action", 0)
            eq_name = str(eq.get("cardNumber", "Equip")).lower()
            if action > 0 and eq_name not in unpayable_set:
                eq_id = eq.get("actionDataOverride", eq_name)
                eq_slot = str(eq.get("slot", "")).lower()
                eq_type = str(eq.get("type", "")).upper()

                # 1.3.1 Habilidade Ativa do Herói (Character Ability)
                is_hero = (
                    eq_slot == "hero"
                    or eq_type == "C"
                    or str(eq.get("actionDataOverride", "")) == "0"
                    or any(h in eq_name for h in ["marlynn", "kassai", "bravo", "dash", "dorinthea", "rhinar", "kayo", "jarl", "azalea", "riptide", "teklovossen", "vynnset", "hala", "mario", "arakni"])
                )
                if is_hero:
                    hero_score = self.strategy.evaluate_hero_ability(state, eq)
                    if hero_score > 0:
                        candidates.append({
                            "type": "hero_ability", "idx": 0, "card_id": str(eq_id), "mode": action,
                            "name": eq_name, "score": hero_score, "cost": 0,
                            "power": 0, "has_go_again": True
                        })
                    continue

                # 1.3.2 Armas de Combate e Buffs de Equipamento
                is_weapon = (
                    eq_name in ALL_FAB_WEAPONS
                    or any(w in eq_name for w in WEAPON_KEYWORDS)
                    or eq_slot in ("weapon", "off-hand", "hands")
                )
                if is_weapon:
                    weapon_cost = self.get_weapon_cost(eq_name, eq, state=state)
                    is_traditional_bow = (
                        ("bow" in str(_load_cards_db().get(eq_name, {}).get("subtype", "")).lower()
                         or any(b in eq_name for b in ["shiver", "death_dealer", "dread_bore", "dreadbore", "redback", "sandscour"]))
                        and "hammerhead" not in eq_name
                    )

                    # Poda de arcos tradicionais: só carrega flecha se o Arsenal estiver livre
                    if is_traditional_bow:
                        arsenal_cards = state.get("playerArsenal") or state.get("playerArse") or []
                        if isinstance(arsenal_cards, list) and len(arsenal_cards) > 0:
                            continue
                        if turn_plan.plan_type == "DEFENSIVE_TRAP":
                            continue

                    # Habilidade especial de arma delegada à estratégia do herói (ex: Hammerhead em MarlynnStrategy)
                    weapon_ability_candidate = self.strategy.evaluate_weapon_ability(
                        eq_name, weapon_cost, state, total_res, turn_plan=turn_plan
                    )
                    if weapon_ability_candidate is not None:
                        if weapon_ability_candidate:  # Não foi podada pela estratégia
                            weapon_ability_candidate["idx"] = 0
                            weapon_ability_candidate["card_id"] = str(eq_id)
                            weapon_ability_candidate["mode"] = action
                            candidates.append(weapon_ability_candidate)
                        continue

                    # Poda de Symbiosis Shot: requer 1+ steam counters para poder atacar
                    if "symbiosis" in eq_name:
                        steam_counters = int(eq.get("counters", eq.get("steam_counters", 0)))
                        if steam_counters <= 0:
                            continue

                    # Teklo Leveler: igual com 0 e 1 Evos (custo 3), escala com 2+ Evos
                    evos_equipped = 0
                    if "leveler" in eq_name or "teklo_leveler" in eq_name:
                        equip_list = state.get("playerEquipment", []) if state else []
                        evos_equipped = sum(1 for e in equip_list if isinstance(e, dict) and ("evo" in str(e.get("cardNumber", "")).lower() or "evo" in str(e.get("subtype", "")).lower()))

                    # Armas convencionais de ataque
                    if total_res >= weapon_cost:
                        eq_info = self.extract_card_info(eq)
                        weapon_power = eq_info.get("power", 0) or int(eq.get("power", 0))
                        if weapon_power == 0:
                            weapon_power = int(_load_cards_db().get(eq_name, {}).get("power", 0))

                        weapon_has_ga = False
                        if "leveler" in eq_name or "teklo_leveler" in eq_name:
                            if evos_equipped >= 3:
                                weapon_has_ga = True
                            if evos_equipped >= 4:
                                weapon_power = 3
                            else:
                                weapon_power = 2

                        try:
                            weapon_score = self.strategy.evaluate_weapon_attack(
                                eq_name, floating_res, total_res, len(hand_attacks) > 0,
                                state=state, evos_equipped=evos_equipped
                            )
                        except TypeError:
                            weapon_score = self.strategy.evaluate_weapon_attack(
                                eq_name, floating_res, total_res, len(hand_attacks) > 0
                            )
                        if not has_any_go_again and len(hand_attacks) == 0:
                            weapon_score += 2.0
                        if is_traditional_bow:
                            weapon_score += 8.0
                        candidates.append({
                            "type": "weapon", "idx": 0, "card_id": str(eq_id), "mode": action,
                            "name": eq_name, "score": weapon_score, "cost": weapon_cost,
                            "power": weapon_power, "has_go_again": weapon_has_ga
                        })
                    continue

                # 1.3.3 Habilidade Ativada de Equipamento (Head, Chest, Arms, Legs, Off-Hand)
                is_equipment_slot = (
                    eq_slot in ("head", "chest", "arms", "legs", "off-hand", "equipment")
                    or eq_type == "E"
                ) and not is_weapon and not is_hero

                if is_equipment_slot:
                    eq_cost = self.get_weapon_cost(eq_name, eq, state=state)
                    if total_res >= eq_cost:
                        eq_score = self.strategy.evaluate_equipment_ability(state, eq, hand_attacks=hand_attacks)
                        if eq_score > 0:
                            candidates.append({
                                "type": "equipment_ability",
                                "idx": 0,
                                "card_id": str(eq_id),
                                "mode": action,
                                "name": eq_name,
                                "score": eq_score,
                                "cost": eq_cost,
                                "power": 0,
                                "has_go_again": True
                            })

        # ── 1.4 Arsenal e Banish ────────────────────────────────────
        # Contagem de tokens/auras de Runechant para o desconto oficial de Runegate
        runechant_count = 0
        for aura in (state.get("playerAuras") or []):
            if isinstance(aura, dict) and "runechant" in str(aura.get("cardNumber") or aura.get("name", "")).lower():
                runechant_count += max(1, int(aura.get("counters", aura.get("count", 1))))
        for token in (state.get("playerTokens") or []):
            if isinstance(token, dict) and "runechant" in str(token.get("cardNumber") or token.get("name", "")).lower():
                runechant_count += max(1, int(token.get("counters", token.get("count", 1))))
        if "playerRunechants" in state:
            try:
                runechant_count = max(runechant_count, int(state.get("playerRunechants", 0)))
            except Exception:
                pass

        for zone_name, key in [("Arsenal", "playerArsenal"), ("Banish", "playerBanish"), ("Graveyard", "playerGraveyard")]:
            zone = state.get(key) or (state.get("playerArse", []) if key == "playerArsenal" else (state.get("playerDiscard", []) if key == "playerGraveyard" else []))
            for c in zone:
                action = c.get("action", 0)
                c_name = str(c.get("cardNumber", "Card")).lower()
                if action > 0 and c_name not in unpayable_set:
                    c_id = c.get("actionDataOverride", c_name)
                    c_info = self.extract_card_info(c)
                    card_cost = max(0, int(c_info.get("cost", 0)))
                    effective_cost = card_cost

                    # No FaB oficial, Runegate permite jogar do Banish destruindo Runechants em vez de pagar recursos
                    # Regra FaB: apenas cartas de ATAQUE possuem Runegate (fasting_carcass NÃO possui Runegate)
                    if zone_name == "Banish":
                        db_c = _load_cards_db().get(c_name, {})
                        is_runegate = (
                            any(k in c_name for k in [
                                "cull", "deathly", "widespread",
                                "oblivion", "beseech", "runegate"
                            ])
                            or "runegate" in str(db_c.get("text", "")).lower()
                            or "runegate" in str(c.get("text", "")).lower()
                        )
                        if is_runegate:
                            effective_cost = max(0, card_cost - runechant_count)

                    # Cartas de Arsenal/Banish/Graveyard usam total_res da mão inteira (ou effective_cost de Runegate)
                    if total_res >= effective_cost:
                        base_score = self.strategy.evaluate_attack_card(
                            c_name, c_info["power"], effective_cost, c_info["has_go_again"], c_info["pitch"]
                        )
                        has_ga = c_info["has_go_again"]
                        is_instant = False

                        if zone_name == "Banish":
                            # Jogar do Banish alivia Blood Debt e projeta dano alto
                            play_score = base_score + 10.0
                            if isinstance(self.strategy, RunebladeStrategy) or "vynnset" in str(self.hero_name).lower():
                                play_score += 15.0  # Vynnset quer esvaziar o Banish para não morrer de Blood Debt
                            # Regra oficial Teklovossen: equipar Evo da zona banida é jogado como Instant (custo 0 de Action Point)
                            # MAS APENAS se a habilidade de Teklovossen tiver sido ativada neste turno!
                            # Se a habilidade NÃO foi ativada, o Evo permanece banido e NÃO ganha opção de ser jogado ("fica lá banido").
                            if ("teklo" in str(self.hero_name).lower() or isinstance(self.strategy, TeklovossenStrategy)) and "evo" in c_name:
                                if "singularity" not in c_name:
                                    if not self.is_teklovossen_ability_active(state):
                                        continue  # Não ativou a habilidade: Evo permanece banido e inerte!
                                is_instant = True
                                has_ga = True  # Instant resolve sem consumir Action Point
                                play_score += 12.0
                            if "singularity" in c_name:
                                play_score += 35.0  # Mechropotent Singularity é o finalizador absoluto
                        elif zone_name == "Graveyard":
                            # Cartas jogáveis do cemitério (ex: Instant liberada por Astral Bridge ou recursão de cartas)
                            play_score = base_score + 18.0
                            db_entry = _load_cards_db().get(c_name, {})
                            c_type = str(c_info.get("type") or db_entry.get("type", "")).upper()
                            if c_type == "I" or "instant" in c_type.lower() or action == 27:
                                is_instant = True
                                has_ga = True
                        else:
                            # Jogar do Arsenal executa a ofensiva e libera o slot para o canhão carregar nova flecha
                            play_score = base_score + 4.0
                            # Se a carta no Arsenal for uma Non-Attack Action (ex: Portside Exchange, Codex of Frailty):
                            # Jogar do Arsenal PRIMEIRO libera o slot e concede bônus antes do disparo!
                            c_type = str(_load_cards_db().get(c_name, {}).get("type", "")).upper()
                            is_naa = ("AA" not in c_type and "ATTACK" not in c_type) or any(k in c_name for k in ["portside", "codex", "salvage", "three_of_a_kind", "tip_the_barkeep"])
                            if is_naa:
                                play_score += 15.0  # Prioridade máxima: jogue a NAA do arsenal para liberar o slot!
                                if turn_plan.plan_type == "OVERPITCH_RECOVERY":
                                    play_score += 15.0
                            elif any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy"]) or isinstance(self.strategy, RangerStrategy):
                                play_score += 10.0  # Flecha carregada no arsenal pronta para disparo!
                                if turn_plan.plan_type == "HARPOON_CHAIN":
                                    play_score += 15.0

                        candidate_item = {
                            "type": zone_name.lower(), "idx": 0, "card_id": str(c_id), "mode": action,
                            "name": c_name, "score": play_score, "cost": effective_cost,
                            "power": c_info["power"], "has_go_again": has_ga
                        }
                        if is_instant:
                            candidate_item["is_instant"] = True
                            candidate_item["ap_cost"] = 0
                        candidates.append(candidate_item)

        # ── 1.5 Aliados em Jogo (playerAllies) ───────────────────────
        allies = state.get("playerAllies", [])
        if isinstance(allies, list):
            for idx, ally in enumerate(allies):
                if not isinstance(ally, dict):
                    continue
                action = ally.get("action", 0)
                a_name = str(ally.get("cardNumber") or ally.get("name", "")).lower()
                if action > 0 and a_name not in unpayable_set:
                    a_id = ally.get("actionDataOverride") or str(ally.get("uniqueID", idx))
                    a_info = self.extract_card_info(ally)
                    ability_cost = int(_load_cards_db().get(a_name, {}).get("ability_cost", 0))
                    if total_res >= ability_cost:
                        ally_power = a_info.get("power", 0) or int(_load_cards_db().get(a_name, {}).get("power", 0))
                        base_score = float(ally_power) * 2.0
                        if getattr(self.strategy, "is_ally_hero", False) or "gravy" in str(self.hero_name).lower():
                            base_score += 15.0  # Gravy Bones valoriza ataques de aliados agressivamente
                            # Se temos Avast Ye! na mão e AP <= 1, jogue Avast Ye! PRIMEIRO para conceder Go Again ao aliado!
                            has_avast = any("avast_ye" in str(h.get("cardNumber") or h.get("name", "")).lower() for h in state.get("playerHand", []))
                            if player_ap <= 1 and has_avast:
                                base_score -= 20.0  # Dá prioridade a Avast Ye! para conceder Go Again e continuar a cadeia
                            else:
                                # Se o oponente está na zona crítica (<= 6 HP), priorizar aliados pesados para perfurar o bloco
                                opp_h = int(state.get("opponentHealth", state.get("oppHealth", 40)))
                                if opp_h <= 6:
                                    if ally_power >= opp_h:
                                        base_score += 15.0  # Golpe de misericórdia letal direto
                                    elif ally_power >= 4:
                                        base_score += 10.0  # Quebrador de defesa que força múltiplos bloqueios
                        candidates.append({
                            "type": "ally", "idx": idx, "card_id": str(a_id), "mode": action,
                            "name": a_name, "score": base_score, "cost": ability_cost,
                            "power": ally_power, "has_go_again": False
                        })

        if player_ap <= 0:
            # Se não possui Action Points disponíveis, apenas ações Instantâneas (custo 0 de AP) podem ser jogadas
            candidates = [c for c in candidates if c.get("is_instant") is True or c.get("ap_cost") == 0]

        if not candidates:
            return None

        # ── 1.6 Refinamento via Busca em Árvore ─────────────────────
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

            # Regra Oficial de FaB: Cartas sem pitch (pitch <= 0, ex: Gorganian Tome)
            # NUNCA podem ser dadas pitch! Ignora imediatamente para evitar loop no servidor.
            if int(info.get("pitch", 1)) <= 0 or "gorganian" in c_clean_name:
                continue

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
        opp_hp = int(state.get("opponentHealth", 20))
        cards_db = _get_cards_db()
        
        active_chain = state.get("activeChainLink", {})
        if not isinstance(active_chain, dict):
            active_chain = {}
        opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 4)))
        incoming_name = str(active_chain.get("cardNumber", "")).lower()
        db_incoming = cards_db.get(incoming_name, {})
        incoming_text = str(db_incoming.get("text", "")).lower()
        
        on_hit_threat = get_on_hit_threat(incoming_name, incoming_text)
        has_dangerous_on_hit = on_hit_threat >= 3.0 or any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

        # ── 3.1 Detecção Holística de Plano de Turno e Pivot ────────
        turn_plan = self.strategy.analyze_turn_plan(state)
        is_heavy_hero = getattr(self.strategy, "is_heavy_hero", False)
        current_turn = int(state.get("turnNo", state.get("currentTurn", 1)))

        # Contagem de cartas de ataque Runegate na mão para Vynnset
        runegate_in_hand = 0
        if "vynnset" in str(self.hero_name).lower():
            runegate_in_hand = sum(
                1 for hc in hand
                if any(rk in str(hc.get("cardNumber", "")).lower() for rk in [
                    "cull", "deathly_delight", "deathly_wail", "widespread_ruin",
                    "widespread_destruction", "widespread_annihilation", "oblivion", "eloquent_eulogy"
                ])
            )

        block_candidates = []
        for idx, c in enumerate(hand):
            info = self.extract_card_info(c)
            if info["block"] <= 0:
                continue

            c_id = info["actionDataOverride"] or str(idx)
            c_action = info["action"] if info["action"] > 0 else 27
            if isinstance(self.strategy, VynnsetStrategy):
                score = self.strategy.evaluate_block_card(
                    info["name"], info["block"], info["pitch"], info["power"], info["has_go_again"],
                    runegate_in_hand=runegate_in_hand
                )
            else:
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

            # ── Custo de Oportunidade Dinâmico de Bloqueio (Felt Table & AI Unsheathed)
            opp_cost = 0.0
            if hasattr(self.strategy, "calculate_card_opportunity_cost"):
                avail_fl, _ = self.calculate_available_resources(state)
                opp_cost = self.strategy.calculate_card_opportunity_cost(hand, c, floating_res=avail_fl)

            if opp_cost > 0:
                absorb_mult = self.strategy.get_dynamic_multiplier("absorb_tempo_bonus", 1.0)
                score -= opp_cost * 1.5 * absorb_mult
                is_catastrophic = on_hit_threat >= 8.0 or (my_hp - opp_power) <= 0
                if not is_catastrophic and my_hp > 8 and info["block"] < opp_cost:
                    score -= 25.0

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

            hand_cost = 3.5 + opp_cost
            if is_reserved:
                hand_cost = 25.0
            elif info["power"] >= 5 or (info["pitch"] == 1 and info["power"] >= 4):
                hand_cost = 5.0 + opp_cost

            if score > -100.0 and info["block"] > 0:
                block_candidates.append({
                    "type": "block", "score": score, "idx": idx, "card_id": c_id,
                    "name": info["name"], "mode": c_action, "block": info["block"],
                    "pitch": info["pitch"], "power": info["power"],
                    "is_equipment": False, "is_hand": True, "cost": hand_cost,
                    "opp_cost": opp_cost
                })

        # ── 3.1b Cartas no Arsenal que podem defender (Ambush e Down and Dirty) ──
        arsenal = state.get("playerArsenal") or state.get("playerArse") or []
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
                    "from_arsenal": True, "is_equipment": False, "is_hand": False,
                    "cost": 1.0
                })

        # ── 3.1c Bloqueio com Equipamentos (Defesa Otimizada e Anti-Queima) ────────
        equip = state.get("playerEquipment", [])
        for eq_idx, eq in enumerate(equip):
            if not isinstance(eq, dict):
                continue
            eq_name = str(eq.get("cardNumber", "")).lower()
            slot = str(eq.get("slot", "")).lower()
            if slot == "hero":
                continue
            # Armas só podem bloquear se forem especificamente do tipo equipamento/escudo
            db_entry = cards_db.get(eq_name, {})
            eq_type = str(eq.get("type") or db_entry.get("type", "")).upper()
            if slot == "weapon" and eq_type != "E":
                continue

            eq_action = int(eq.get("action", 0))
            if eq.get("isBroken") or eq.get("onChain"):
                continue

            info = self.extract_card_info(eq)
            base_block = info["block"]

            # ── Cálculo da Defesa Efetiva com Marcadores (-1 counters / defCounters) ──
            # No Talishar nativo, marcadores de perda de defesa são números negativos (-1, -2).
            # Em mocks/testes, podem vir como positivos (+1 para indicar 1 marcador de -1).
            raw_def_counters = eq.get("defCounters")
            if raw_def_counters is None and isinstance(eq.get("countersMap"), dict):
                raw_def_counters = eq["countersMap"].get("defense")
            try:
                def_val = int(raw_def_counters) if raw_def_counters is not None and str(raw_def_counters).lstrip("-").isdigit() else 0
            except Exception:
                def_val = 0

            if def_val < 0:
                effective_block = max(0, base_block + def_val)  # Talishar nativo: 1 + (-1) = 0
            elif def_val > 0:
                effective_block = max(0, base_block - def_val)  # Mocks/testes: 1 - 1 = 0
            else:
                effective_block = base_block

            # Se a engine do Talishar enviou explicitamente action <= 0, o equipamento não pode defender agora
            if eq_action <= 0 and "action" in eq:
                continue

            is_crown = "crown_of_providence" in eq_name
            is_ironhide = "ironhide" in eq_name
            is_rampart = "rampart" in eq_name

            # Equipamentos com ativações defensivas que pagam recursos (Ironhide +2d, Rampart +1d)
            # No FaB oficial, mesmo com base 0 no banco, Ironhide defende 2 pagando 1 recurso,
            # e Rampart defende 1 pagando 1 recurso.
            avail_floating, avail_pitch = self.calculate_available_resources(state)
            has_defense_resource = (avail_floating + avail_pitch) >= 1

            if is_ironhide and has_defense_resource:
                effective_block = max(effective_block, max(0, 2 + def_val))
            elif is_rampart and has_defense_resource:
                effective_block = max(effective_block, max(0, 1 + def_val))

            is_teklo = "teklo" in str(self.hero_name).lower() or isinstance(self.strategy, TeklovossenStrategy)
            is_evo = "evo" in eq_name or "cogwerx_base" in eq_name or "evo" in str(db_entry.get("subtype", "")).lower()

            has_bw = bool(db_entry.get("has_battleworn") or "battleworn" in str(db_entry.get("subtype", "")).lower())
            has_bb = bool(db_entry.get("has_blade_break") or "blade break" in str(db_entry.get("subtype", "")).lower() or "ironrot" in eq_name or eq.get("has_blade_break"))
            has_temp = bool(db_entry.get("has_temper") or "temper" in str(db_entry.get("subtype", "")).lower() or is_evo or eq.get("has_temper"))

            has_defend_trigger = (
                is_crown
                or (is_ironhide and has_defense_resource)
                or (is_rampart and has_defense_resource)
                or "defend" in str(db_entry.get("text", "")).lower()
                or any(k in eq_name for k in ["providence", "ironhide", "rampart", "constellas", "carrion_husk"])
            )

            # Equipamentos cuja defesa foi zerada (ou base 0):
            # Se NÃO possui efeito ao defender, descarta para não bloquear inutilmente por 0 de dano!
            if effective_block <= 0 and not has_defend_trigger:
                continue

            arsenal = state.get("playerArsenal") or state.get("playerArse") or []
            has_arsenal = len(arsenal) > 0
            is_arsenal_threat = has_arsenal and (
                any(k in incoming_name for k in ["command_and_conquer", "leave_no_witnesses", "wreck_havoc", "eradicate", "humble", "righteous_cleansing"])
                or ("arsenal" in incoming_text and any(w in incoming_text for w in ["destroy", "banish", "put"]))
            )
            # Avaliação de mão para Crown of Providence ciclar cartas
            hand_cards = state.get("playerHand", [])
            hand_info = [self.extract_card_info(c) for c in hand_cards]
            num_attacks = sum(1 for c in hand_info if c["power"] > 0)
            num_pitches = sum(1 for c in hand_info if c["pitch"] >= 2)
            is_awkward_hand = (len(hand_cards) >= 3 and (num_pitches == 0 or num_attacks == 0))

            will_break = has_bb or (has_temp and effective_block <= 1)

            # ── Poda Estrita de Armadura em Ataques Vanilla ──
            # Se o ataque NÃO possui efeito On-Hit e nossa vida está saudável (HP > 12),
            # armaduras em geral não devem ser gastas para mitigar dano comum!
            # Exceções:
            # 1. Crown of Providence quando a mão está disfuncional e precisa de ciclo
            # 2. Teklovossen com Evos que possuem Temper e effective_block > 1 (primeiro bloco seguro de 2 def)
            is_safe_evo_temper = is_teklo and is_evo and has_temp and effective_block > 1
            if on_hit_threat == 0.0 and my_hp > 12:
                if not ((is_crown and is_awkward_hand) or is_safe_evo_temper):
                    continue

            # ── REGRA ESPECIAL TEKLOVOSSEN: Preservação Sagrada dos Evos com TEMPER ──
            if is_teklo and is_evo:
                # Evos são a condição de vitória do Teklovossen (4 Evos montados para Singularity / Mechropotent).
                # No Flesh and Blood oficial, Evos possuem TEMPER:
                # - Enquanto effective_block > 1: O Evo bloqueia, recebe um marcador de -1 de defesa quando
                #   a cadeia de combate fecha, mas permanece com >= 1 de defesa e NÃO É DESTRUÍDO!
                #   Ele continua equipado no herói, mantendo o slot ativo para a Singularity.
                #   Esse primeiro bloqueio é seguro e deve ser aproveitado livremente para mitigar dano!
                # - Quando effective_block <= 1 (ou Blade Break): O próximo bloqueio reduzirá a defesa a 0,
                #   fazendo o Temper DESTRUIR o Evo! Esse é o ÚLTIMO bloqueio, de altíssimo risco.
                is_fatal = (my_hp - opp_power) <= 0
                opp_hero_str = str(state.get("opponentHero", "")).lower()
                is_aggro_opp = opp_power >= 6 or any(h in opp_hero_str for h in [
                    "fai", "katsu", "dash", "kayo", "rhinar", "chane", "briar", "vynnset", "azalea", "riptide", "aurora", "zen"
                ])
                is_late_game = my_hp <= 8 or current_turn >= 8

                if will_break:
                    # Este é o ÚLTIMO bloqueio que destruirá o Evo e deixará Teklovossen sem a peça!
                    # Só é permitido se for dano estritamente fatal, ou perigo extremo no late game contra aggro.
                    if not is_fatal and not (is_aggro_opp and is_late_game and my_hp <= 6):
                        continue
                else:
                    # O Evo possui Temper com 2+ de defesa e sobreviverá com 1 de defesa restante.
                    # PODE BLOQUEAR normalmente para mitigar dano!
                    pass

            has_active_ability = bool(db_entry.get("ability_cost") is not None or any(k in eq_name for k in [
                "goliath_gauntlet", "heartened_cross_strap", "snapdragon_scalers",
                "fyendals_spring_tunic", "scabskin_leathers", "barkbone_strapping", "tunic"
            ]))

            eq_cost = 3.5
            eq_score = float(effective_block) * 3.0

            if is_crown:
                if is_arsenal_threat:
                    eq_score += 35.0  # Prioridade máxima: salva o Arsenal de destruição/on-hit e puxa carta nova
                    eq_cost = 1.0
                elif my_hp <= 6 or (has_dangerous_on_hit and opp_power >= my_hp):
                    eq_score += 20.0  # Modo sobrevivência: salva vida crítica
                    eq_cost = 1.5
                elif has_dangerous_on_hit and not (any(k in incoming_name for k in ["command_and_conquer", "leave_no_witnesses", "wreck_havoc", "eradicate"]) and not has_arsenal):
                    eq_score += 16.0  # Parar on-hit perigoso ativo
                    eq_cost = 2.0
                elif my_hp <= 12 or is_awkward_hand:
                    eq_score += 10.0  # Pressão ou ciclo de mão disfuncional
                    eq_cost = 2.5
                else:
                    eq_score -= 25.0  # Poupar Crown (Blade Break valioso)
                    eq_cost = 25.0
            elif is_ironhide and has_defense_resource:
                eq_score += 6.0
                eq_cost = 2.0
            elif is_rampart and has_defense_resource:
                eq_score += 4.0
                eq_cost = 2.0
            elif has_defend_trigger:
                eq_score += 8.0
                eq_cost = 2.0
            elif effective_block <= 0:
                # Equipamento de defesa zero sem gatilho ativo explícito:
                # A rede neural / ISMCTS avaliará o valor da ação no rollout
                eq_score = 0.0
                eq_cost = 5.0
            elif has_bw:
                eq_score += 8.0  # Battleworn é prioridade máxima: bloqueia de graça e sobrevive
                eq_cost = 1.5
            elif has_temp:
                eq_score += 5.0  # Temper sobrevive se defCounters < base_block - 1
                eq_cost = 2.5
            elif has_bb:
                if has_active_ability:
                    if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= my_hp):
                        eq_score += 2.0  # Modo Sobrevivência: salva vida a qualquer custo
                        eq_cost = 6.0
                    else:
                        eq_score -= 25.0  # Preserva equipamento com habilidade ativa
                        eq_cost = 25.0
                else:
                    if opp_power <= 2 and my_hp > 20 and not has_dangerous_on_hit:
                        eq_score -= 3.0  # Economiza armadura descartável se dano for irrelevante
                        eq_cost = 5.0
                    else:
                        eq_score += 3.0  # Ironrot / armadura pura bloqueia para mitigar dano e economizar mão
                        eq_cost = 3.5

            if eq_score <= -20.0 and my_hp > 6:
                continue

            c_id = eq.get("actionDataOverride") or str(eq_idx)
            c_action = eq_action if eq_action > 0 else 3
            block_candidates.append({
                "type": "block", "score": eq_score, "idx": eq_idx, "card_id": str(c_id),
                "name": info["name"], "mode": c_action,
                "block": effective_block, "pitch": 0, "power": 0,
                "is_equipment": True, "is_hand": False, "cost": eq_cost
            })

        if not block_candidates:
            return []

        # ── 3.2 Otimização de Subconjunto Mínimo de Defesa (Knapsack Breakpoint) ──
        # Quando há On-Hit perigoso e não estamos em modo sobrevivência de desespero:
        # Encontra o subconjunto de menor custo total (poupando cartas da mão para o pivot)
        # que neutraliza completamente o dano (total_block >= opp_power).
        if has_dangerous_on_hit and opp_power > 0 and my_hp > 6:
            valid_subsets = []
            max_hand_in_subset = turn_plan.max_block_cards if turn_plan.can_absorb_damage else (
                2 if my_hp > 12 else 3
            )
            for r in range(1, min(len(block_candidates) + 1, 5)):
                for subset in itertools.combinations(block_candidates, r):
                    tot_block = sum(item["block"] for item in subset)
                    if tot_block >= opp_power:
                        hand_count = sum(1 for item in subset if item.get("is_hand"))
                        if hand_count > max_hand_in_subset:
                            continue
                        # Poda de Bloqueio Ineficiente: Se o plano permite absorver dano para pivotar
                        # ou vida saudável (> 12), rejeitar subconjuntos com 2+ cartas de mão com média <= 2.0 block
                        if turn_plan.can_absorb_damage and hand_count >= 2:
                            avg_hand_block = sum(item["block"] for item in subset if item.get("is_hand")) / hand_count
                            if avg_hand_block <= 2.0:
                                continue
                        overblock = tot_block - opp_power
                        sub_cost = sum(item["cost"] for item in subset) + (overblock * 0.7)
                        valid_subsets.append((sub_cost, subset))

            if valid_subsets:
                valid_subsets.sort(key=lambda x: x[0])
                best_subset = valid_subsets[0][1]
                return [(item["idx"], item["card_id"], item["name"], item["mode"]) for item in best_subset]

        # ── 3.3 Avaliação da Rede Neural Policy-Value e Refinamento ISMCTS ──
        if self.model is not None and block_candidates:
            try:
                state_vec = FaBPolicyValueNetwork.extract_state_vector(state, getattr(self, "player_id", 1))
                probs, _ = self.model.predict_state(state_vec, str(self.device))
                for item in block_candidates:
                    action_id = int(item.get("mode", 3)) % 32
                    prior_prob = float(probs[action_id]) if action_id < len(probs) else 0.0
                    item["score"] += prior_prob * 10.0
            except Exception:
                pass

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
                best_item = block_candidates[best_idx]
                best_item["score"] += 10.0

        # Ordenar melhores cartas defensivas primeiro
        block_candidates.sort(key=lambda x: x["score"], reverse=True)
        
        chosen_blocks = []
        current_blocked = 0

        # Limite máximo de cartas da MÃO para bloquear
        if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= my_hp):
            max_hand_blocks = len(block_candidates)  # Modo Sobrevivência (Bloqueio total)
        elif turn_plan.plan_type in ("DEFENSIVE_TRAP", "FULL_DEFENSE", "DEFENSIVE"):
            max_hand_blocks = min(turn_plan.max_block_cards, len(block_candidates))
        elif turn_plan.can_absorb_damage:
            max_hand_blocks = min(turn_plan.max_block_cards, len(block_candidates))
        elif not has_dangerous_on_hit and my_hp > 15:
            # Em ataques comuns sem On-Hit com vida saudável (> 15), limita a no máximo 1 carta de mão para preservar a mão!
            max_hand_blocks = 1
        elif my_hp <= 12:
            max_hand_blocks = min(3, len(block_candidates))
        else:
            max_hand_blocks = min(2, len(block_candidates))

        hand_blocks_count = 0
        for item in block_candidates:
            is_equip = item.get("is_equipment", False)
            if not is_equip and hand_blocks_count >= max_hand_blocks:
                continue

            # Poda de Bloqueio Ineficiente com Block <= 2 quando o plano é absorver dano:
            if turn_plan.can_absorb_damage and not is_equip and item["block"] <= 2 and my_hp > 12:
                continue

            # Poda de Bloqueio Ineficiente: Não bloqueia se score for muito negativo com HP alto
            if my_hp > 15 and item["score"] < 0 and not has_dangerous_on_hit:
                continue

            chosen_blocks.append((item["idx"], item["card_id"], item["name"], item["mode"]))
            current_blocked += item["block"]
            if not is_equip:
                hand_blocks_count += 1

            # ── Defesa Mínima Viável (FaB Minimum Viable Defense / Preservação de Contra-Ataque) ──
            # Em vez de decaimento artificial baseado em turnos, preserva recurso de contra-ataque (pitch ou arma)
            # se já mitigamos o dano para uma faixa segura de sobrevivência (projetado >= 2 HP, ou >= 1 se opp_hp <= 4).
            # Não se aplica quando o plano tático for explicitamente DEFENSIVE_TRAP ou FULL_DEFENSE.
            remaining_dmg = max(0, opp_power - current_blocked)
            projected_hp = my_hp - remaining_dmg
            if current_blocked > 0 and turn_plan.plan_type not in ("DEFENSIVE_TRAP", "FULL_DEFENSE"):
                remaining_hand = len(hand) - hand_blocks_count
                # Se o ataque ameaça destruir Arsenal mas não temos cartas no Arsenal, o on-hit é inócuo
                arsenal_cards = state.get("playerArsenal") or state.get("playerArse") or []
                is_real_on_hit = has_dangerous_on_hit and not (
                    any(k in incoming_name for k in ["command_and_conquer", "leave_no_witnesses", "wreck_havoc", "eradicate"])
                    and len(arsenal_cards) == 0
                )
                if projected_hp >= 2 and remaining_hand <= 1 and not is_real_on_hit:
                    # Preserva a última carta da mão para poder dar pitch / jogar ação ofensiva
                    break
                elif projected_hp >= 1 and opp_hp <= 4 and remaining_hand <= 1:
                    # Risco tático de vitória: aceita dano residual seguro para garantir o swing letal!
                    break

            # ── Poda de Overblocking Exato:
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
