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

from .hero_strategies import get_hero_strategy, HeroStrategy
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

        # Inferência de poder por heurística quando ausente no snapshot
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

        # Custo de recurso
        cost = 0
        if any(k in card_number for k in ["throttle", "pounder", "trebuchet", "staunch", "spinal"]):
            cost = 2
        elif any(k in card_number for k in ["zipper", "fast_and_furious", "out_pace", "expedite", "harpoon", "spark_of_genius", "command_and_conquer"]):
            cost = 1
        elif any(k in card_number for k in ["zero_to_sixty", "bios_update", "convection", "boom_grenade", "snatch", "leg_tap", "rising_knee"]):
            cost = 0

        # Go Again
        has_go_again = False
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
            "borderColor": card.get("borderColor", 0)
        }

    def calculate_available_resources(self, state: dict) -> Tuple[int, int]:
        resources = state.get("playerResources", [0, 0])
        current_floating = int(resources[0]) if isinstance(resources, list) and resources else 0
        hand = state.get("playerHand", [])
        total_potential_pitch = sum(self.extract_card_info(c)["pitch"] for c in hand)
        return current_floating, current_floating + total_potential_pitch

    # ══════════════════════════════════════════════════════════════
    # 1. PODA DE ATAQUE E SEQUENCIAMENTO DE CADEIA
    # ══════════════════════════════════════════════════════════════

    def select_best_attack(self, state: dict, unpayable_set: set) -> Optional[Dict[str, Any]]:
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
            if info["action"] > 0 and c_name not in unpayable_set:
                remaining_pitch = total_res - info["pitch"]
                if remaining_pitch >= info["cost"]:
                    c_id = info["actionDataOverride"] or str(idx)
                    c_action = 27 if info["action"] == 27 else info["action"]
                    base_score = self.strategy.evaluate_attack_card(
                        c_name, info["power"], info["cost"], info["has_go_again"], info["pitch"]
                    )
                    if info["has_go_again"]:
                        has_any_go_again = True
                    hand_attacks.append({
                        "type": "hand", "idx": idx, "card_id": c_id, "mode": c_action,
                        "name": c_name, "score": base_score, "cost": info["cost"],
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
                    # Ataques de arma geralmente finalizam turnos ou gastam recursos flutuantes
                    weapon_score = 2.5 + (1.5 if floating_res >= 1 else 0.0)
                    if not has_any_go_again and len(hand_attacks) == 0:
                        weapon_score += 2.0
                    candidates.append({
                        "type": "weapon", "idx": 0, "card_id": str(eq_id), "mode": action,
                        "name": eq_name, "score": weapon_score, "cost": 0
                    })

        # ── 1.4 Arsenal e Banish ────────────────────────────────────
        for zone_name, key in [("Arsenal", "playerArsenal"), ("Banish", "playerBanish")]:
            zone = state.get(key, [])
            for c in zone:
                action = c.get("action", 0)
                c_name = str(c.get("cardNumber", "Card")).lower()
                if action > 0 and c_name not in unpayable_set:
                    c_id = c.get("actionDataOverride", c_name)
                    # Jogar do Arsenal libera o slot para o final do turno (+2.0 de valor tático)
                    arsenal_score = 4.5
                    candidates.append({
                        "type": zone_name.lower(), "idx": 0, "card_id": str(c_id), "mode": action,
                        "name": c_name, "score": arsenal_score, "cost": 0
                    })

        if not candidates:
            return None

        # ── 1.5 Refinamento via Busca em Árvore ─────────────────────
        if self.model is not None and len(candidates) > 1 and self.num_mcts_sims > 0:
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

        pitch_candidates = []
        for idx, c in enumerate(hand):
            info = self.extract_card_info(c)
            c_action = info["action"] if info["action"] > 0 else 27
            score = self.strategy.evaluate_pitch_card(
                info["name"], info["pitch"], info["cost"], info["power"], info["has_go_again"]
            )
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
        if self.model is not None and len(pitch_candidates) > 1 and self.num_mcts_sims > 0:
            opp_hand_count = int(state.get("opponentHandCount", state.get("theirHandCount", 0)))
            if opp_hand_count > 0:
                best_idx, _, ismcts_log = self.ismcts.search_ismcts(
                    state=state,
                    legal_actions=pitch_candidates,
                    num_simulations=self.num_mcts_sims,
                )
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

        # ── 3.1 Detecção de Linha de Tempo Pivot (Guardião / Bruto / Ataques Pesados)
        # Identifica se temos uma mão ofensiva para virar a partida (1 ataque pesado + 1 pitch azul)
        has_heavy_attack = False
        has_blue_pitch = False
        for c in hand:
            c_info = self.extract_card_info(c)
            c_name_low = c_info["name"].lower()
            if c_info["pitch"] == 3:
                has_blue_pitch = True
            if (c_info["pitch"] == 1 and c_info["power"] >= 6) or any(
                w in c_name_low for w in ["crush", "wager", "bet_big", "spinal", "crippling", "macho", "pulverize", "buckling", "star_struck"]
            ):
                has_heavy_attack = True

        is_heavy_hero = any(h in str(self.hero_name).lower() for h in ["betsy", "bravo", "victor", "valda", "guardian", "rhinar", "kayo", "levia", "brute"])
        has_pivot_line = has_heavy_attack and has_blue_pitch

        block_candidates = []
        for idx, c in enumerate(hand):
            info = self.extract_card_info(c)
            if info["action"] > 0 or info["borderColor"] > 0 or info["block"] > 0:
                c_id = info["actionDataOverride"] or str(idx)
                c_action = info["action"] if info["action"] > 0 else 27
                score = self.strategy.evaluate_block_card(
                    info["name"], info["block"], info["pitch"], info["power"], info["has_go_again"]
                )
                
                # ── Poda de Preservação de Mão Ofensiva:
                # Se temos vida alta (> 20) e o ataque inimigo é fraco (<= 2 sem on-hit),
                # penaliza queimar cartas vermelhas de ataque chave (power >= 4 e pitch == 1)
                if my_hp > 20 and not has_dangerous_on_hit and opp_power <= 2:
                    if info["power"] >= 4 and info["pitch"] == 1:
                        score -= 5.0

                # ── Poda de Tempo Pivot para Guardião:
                # Protege a carta de ataque pesado e o pitch azul da mão de serem queimados em bloqueios fúteis
                if (is_heavy_hero or has_pivot_line) and my_hp >= 10 and not has_dangerous_on_hit:
                    if info["pitch"] == 1 and info["power"] >= 6:
                        score -= 20.0  # Nunca bloqueia com a arma principal de Pivot
                    elif info["pitch"] == 3 and len([x for x in hand if self.extract_card_info(x)["pitch"] == 3]) <= 1:
                        score -= 8.0   # Preserva pelo menos 1 azul para pagar o ataque pesado

                # Bônus para cartas azuis de bloqueio 3 ou reações de defesa pura
                if info["block"] >= 3 and (info["pitch"] == 3 or "sink" in info["name"] or "fate" in info["name"] or "staunch" in info["name"]):
                    score += 2.0

                if score > -100.0 and info["block"] > 0:
                    block_candidates.append({
                        "type": "block", "score": score, "idx": idx, "card_id": c_id,
                        "name": info["name"], "mode": c_action, "block": info["block"],
                        "pitch": info["pitch"], "power": info["power"]
                    })

        if not block_candidates:
            return []

        # ── 3.2 Refinamento ISMCTS para Bloqueio ────────────────────
        if self.model is not None and len(block_candidates) > 1 and self.num_mcts_sims > 0:
            opp_hand_count = int(state.get("opponentHandCount", state.get("theirHandCount", 0)))
            if opp_hand_count > 0:
                best_idx, _, _ = self.ismcts.search_ismcts(
                    state=state,
                    legal_actions=block_candidates,
                    num_simulations=self.num_mcts_sims,
                )
                # Prioriza a melhor carta selecionada pelo ISMCTS
                best_item = block_candidates[best_idx]
                best_item["score"] += 10.0

        # Ordenar melhores cartas defensivas primeiro
        block_candidates.sort(key=lambda x: x["score"], reverse=True)
        
        chosen_blocks = []
        current_blocked = 0

        # Limite máximo de cartas para bloquear
        if my_hp <= 8:
            max_blocks = len(block_candidates)  # Modo Sobrevivência (Bloqueio total)
        elif my_hp <= 15:
            max_blocks = min(3, len(block_candidates))
        else:
            max_blocks = min(2, len(block_candidates))

        # Se o Guardião tem uma jogada ofensiva de Pivot preparada e vida segura (> 10 HP),
        # limita os blocos para no máximo 1 ou 2 cartas, absorvendo dano menor e virando o tempo!
        if (is_heavy_hero or has_pivot_line) and my_hp >= 10 and not has_dangerous_on_hit:
            max_blocks = min(max_blocks, 1 if my_hp > 18 else 2)

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

            # Avaliação polimórfica via HeroStrategy (com poda estrita de tipo R e Gem)
            score = self.strategy.evaluate_arsenal_card(info, db_entry)

            # Só considera cartas com score positivo (vantajosas de verdade para o próximo turno)
            if score > 0:
                valid_candidates.append((score, info["name"], c_id))

        if not valid_candidates:
            # Poda estrita: se todas são recursos ou prejudicariam o jogo -> NÃO ARSENALA NADA
            return None

        valid_candidates.sort(key=lambda x: x[0], reverse=True)
        best = valid_candidates[0]
        return best[1], best[2]
