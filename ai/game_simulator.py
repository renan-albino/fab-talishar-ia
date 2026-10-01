"""
ai/game_simulator.py
====================
Simulador determinístico de regras e transições de estado para Flesh and Blood.

Permite ao MCTS / ISMCTS projetar estados futuros reais nas folhas da árvore de busca,
simulando com precisão:
  - Consumo e geração de recursos (Pitch e Floating Resources)
  - Consumo e restauração de Pontos de Ação (Action Points / Go Again)
  - Resolução de combate (Poder de Ataque vs Bloqueio Esperado)
  - Cálculo de dano não bloqueado e perda de vida
  - Efeitos on-hit e redução de cartas na mão do oponente
  - Zonas de jogo (Mão, Arsenal, Pitch, Descarte, Banidas)
  - Vetorização do estado resultante (832 dimensões) para avaliação imediata pelo Value Head
"""

import os
import json
import numpy as np
from typing import Dict, Any, Tuple, List, Optional
from ai.model import FaBPolicyValueNetwork, STATE_DIM

_FAB_CARDS_DB: Optional[dict] = None
_FAB_CARD_SEMANTICS: Optional[dict] = None


def _get_cards_db() -> dict:
    global _FAB_CARDS_DB
    if _FAB_CARDS_DB is None:
        try:
            from config.settings import DATA_DIR
            db_path = DATA_DIR / "fab_cards_db.json"
            if db_path.exists():
                with open(db_path, "r", encoding="utf-8") as f:
                    _FAB_CARDS_DB = json.load(f)
        except Exception:
            pass
        if _FAB_CARDS_DB is None:
            _FAB_CARDS_DB = {}
    return _FAB_CARDS_DB


def _get_card_semantics() -> dict:
    global _FAB_CARD_SEMANTICS
    if _FAB_CARD_SEMANTICS is None:
        try:
            from config.settings import DATA_DIR
            sem_path = DATA_DIR / "fab_card_semantics.json"
            if sem_path.exists():
                with open(sem_path, "r", encoding="utf-8") as f:
                    _FAB_CARD_SEMANTICS = json.load(f)
        except Exception:
            pass
        if _FAB_CARD_SEMANTICS is None:
            _FAB_CARD_SEMANTICS = {}
    return _FAB_CARD_SEMANTICS


DANGEROUS_ON_HITS = {
    "crippling", "crush", "command_and_conquer", "red_in_the_ledger",
    "snatch", "mask_of_momentum", "bloodrot", "frailty", "inertia",
    "leave_no_witnesses", "surgical_extraction", "erase_face",
    "spitfire", "spinal_crush", "rightful_king", "hypothermia"
}

from ai.mcts.state import ImmutableGameState

class GameSimulator:
    """
    Motor de transição determinística para rollouts e expansão de folhas do MCTS.
    """

    @staticmethod
    def _safe_int(val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    @classmethod
    def extract_card_meta(cls, card: Any) -> dict:
        """
        Extrai metadados táticos e semânticos de uma carta consultando
        data/fab_cards_db.json e data/fab_card_semantics.json.
        Properly extracts base power, base defense, cost, pitch, and keywords:
        (has_go_again, dominate, overpower, piercing, phantasm, on_hit_severity)
        for any card in the database, with safe fallbacks only if absent.
        """
        if hasattr(card, "to_dict"):
            card = card.to_dict()
            
        if isinstance(card, dict):
            card_num = str(card.get("cardNumber") or card.get("name") or card.get("id") or "").lower().strip()
        elif isinstance(card, str):
            card_num = card.lower().strip()
        else:
            card_num = ""

        db = _get_cards_db()
        sem = _get_card_semantics()

        # Resolução de chave no DB e Semântica
        db_entry = db.get(card_num)
        sem_entry = sem.get(card_num)

        if db_entry is None or sem_entry is None:
            # Tentar slug sem pontuação
            slug = card_num.replace(" ", "_").replace("-", "_").replace("'", "").replace(",", "")
            while "__" in slug:
                slug = slug.replace("__", "_")
            if db_entry is None:
                db_entry = db.get(slug)
            if sem_entry is None:
                sem_entry = sem.get(slug)

        # 1. Pitch
        if isinstance(card, dict) and card.get("pitch") is not None and cls._safe_int(card.get("pitch", 0)) > 0:
            pitch = cls._safe_int(card["pitch"])
        elif db_entry and "pitch" in db_entry:
            pitch = cls._safe_int(db_entry["pitch"])
        elif "_blue" in card_num:
            pitch = 3
        elif "_yellow" in card_num:
            pitch = 2
        elif "_red" in card_num:
            pitch = 1
        else:
            pitch = 1

        # 2. Power
        power = cls._safe_int(card.get("power", 0)) if isinstance(card, dict) else 0
        if power == 0 and db_entry and "power" in db_entry:
            power = cls._safe_int(db_entry["power"])
        if power == 0 and not db_entry:
            # Fallback seguro somente se carta completamente ausente da base
            if any(k in card_num for k in ["zipper", "throttle", "zero_to_sixty", "fast_and_furious", "out_pace", "expedite", "snatch"]):
                power = 4 if pitch == 1 else (3 if pitch == 2 else 2)
            elif "pounder" in card_num or "trebuchet" in card_num:
                power = 5
            elif "harpoon" in card_num or "command_and_conquer" in card_num:
                power = 6 if pitch == 1 else 4

        # 3. Defense / Block
        defense = cls._safe_int(card.get("defenseValue") or card.get("defense") or card.get("block") or 0) if isinstance(card, dict) else 0
        if defense == 0 and db_entry and "defense" in db_entry:
            defense = cls._safe_int(db_entry["defense"])
        if defense == 0 and not db_entry:
            # Fallback seguro somente se carta completamente ausente da base
            if any(k in card_num for k in ["_red", "_yellow", "_blue"]) and not any(k in card_num for k in ["heart", "accelerator", "providence", "tunic"]):
                defense = 3 if pitch == 3 else 2

        # 4. Cost
        cost = cls._safe_int(card.get("cost", 0)) if (isinstance(card, dict) and "cost" in card) else 0
        if cost == 0 and db_entry and "cost" in db_entry:
            cost = cls._safe_int(db_entry["cost"])
        if cost == 0 and not db_entry:
            # Fallback seguro somente se carta completamente ausente da base
            if any(k in card_num for k in ["throttle", "pounder", "trebuchet", "staunch", "spinal", "pulverize", "buckling"]):
                cost = 2 if "spinal" not in card_num and "pulverize" not in card_num else 4
            elif any(k in card_num for k in ["zipper", "fast_and_furious", "out_pace", "expedite", "harpoon", "spark_of_genius", "command_and_conquer"]):
                cost = 1
            elif any(k in card_num for k in ["zero_to_sixty", "bios_update", "convection", "boom_grenade", "snatch", "leg_tap", "rising_knee"]):
                cost = 0

        # 5. Keywords e Propriedades de Combate
        sem_keywords = sem_entry.get("keywords", []) if sem_entry else []
        sem_evasion = sem_entry.get("evasion", {}) if sem_entry else {}

        # has_go_again
        has_go_again = False
        if isinstance(card, dict) and (card.get("has_go_again") or card.get("go_again")):
            has_go_again = True
        elif db_entry and db_entry.get("has_go_again"):
            has_go_again = True
        elif sem_entry and ("go_again" in sem_keywords or "boost" in sem_keywords):
            has_go_again = True
        elif not db_entry:
            has_go_again = any(k in card_num for k in [
                "zero_to_sixty", "throttle", "zipper", "expedite", "out_pace", "fast_and_furious", "leg_tap", "snatch", "rising_knee", "fai"
            ])

        # dominate
        card_dom = bool(card.get("dominate") or card.get("has_dominate")) if isinstance(card, dict) else False
        sem_dom = bool(sem_evasion.get("dominate") or "dominate" in sem_keywords) if sem_entry else False
        dominate = card_dom or sem_dom or (not sem_entry and "dominate" in card_num)

        # overpower
        card_op = bool(card.get("overpower") or card.get("has_overpower")) if isinstance(card, dict) else False
        sem_op = bool(sem_evasion.get("overpower") or "overpower" in sem_keywords) if sem_entry else False
        overpower = card_op or sem_op or (not sem_entry and "overpower" in card_num)

        # piercing
        card_pierce = int(card.get("piercing", 0)) if isinstance(card, dict) else 0
        sem_pierce = int(sem_evasion.get("piercing", 0) or sem_entry.get("grants_piercing", 0) or (1 if "piercing" in sem_keywords else 0)) if sem_entry else 0
        piercing = card_pierce if card_pierce > 0 else (sem_pierce if sem_entry else (1 if "piercing" in card_num else 0))

        # phantasm
        card_phan = bool(card.get("phantasm") or card.get("has_phantasm")) if isinstance(card, dict) else False
        sem_phan = bool(sem_evasion.get("phantasm") or "phantasm" in sem_keywords) if sem_entry else False
        phantasm = card_phan or sem_phan or (not sem_entry and "phantasm" in card_num)

        # on_hit_severity
        card_sev = float(card.get("on_hit_severity", 0.0)) if isinstance(card, dict) else 0.0
        sem_sev = float(sem_entry.get("on_hit_severity", 0.0)) if sem_entry else 0.0
        if card_sev > 0:
            on_hit_severity = card_sev
        elif sem_entry:
            on_hit_severity = sem_sev
        else:
            on_hit_severity = 4.0 if any(oh in card_num for oh in DANGEROUS_ON_HITS) else 0.0

        # has_on_hit
        has_on_hit = False
        if isinstance(card, dict) and card.get("has_on_hit"):
            has_on_hit = True
        elif on_hit_severity > 0.0:
            has_on_hit = True
        elif sem_entry and (int(sem_entry.get("extra_on_hit_damage", 0)) > 0 or sem_entry.get("on_hit_disruption") is not None):
            has_on_hit = True
        elif any(oh in card_num for oh in DANGEROUS_ON_HITS):
            has_on_hit = True

        # Intimidate
        has_intimidate = False
        if isinstance(card, dict) and (card.get("has_intimidate") or card.get("intimidate")):
            has_intimidate = True
        elif sem_entry and "intimidate" in sem_keywords:
            has_intimidate = True
        elif any(k in card_num for k in ["pack_hunt", "alpha_rampage", "barraging_beatdown", "intimidate"]):
            has_intimidate = True

        intimidate_count = 0
        if has_intimidate:
            raw_i = card.get("intimidate_count", card.get("intimidate", 1)) if isinstance(card, dict) else 1
            intimidate_count = int(raw_i) if isinstance(raw_i, (int, float)) and not isinstance(raw_i, bool) else 1

        return {
            "name": card_num,
            "pitch": pitch,
            "power": power,
            "defense": defense,
            "cost": cost,
            "has_go_again": has_go_again,
            "has_on_hit": has_on_hit,
            "has_intimidate": has_intimidate,
            "intimidate_count": intimidate_count,
            "dominate": dominate,
            "has_dominate": dominate,
            "overpower": overpower,
            "has_overpower": overpower,
            "piercing": piercing,
            "has_piercing": piercing > 0,
            "phantasm": phantasm,
            "has_phantasm": phantasm,
            "on_hit_severity": on_hit_severity,
            "raw": card
        }

    @classmethod
    def simulate_attack(cls, state, action: dict):
        """
        Simula a execução de um ataque na fase principal (Phase M).
        Aplica desconto de pitch conforme CR 1.14.2, AP, buffs de equipamento,
        poder de combate vs bloqueio do oponente e vida.
        """
        if not isinstance(state, ImmutableGameState):
            state = ImmutableGameState(state)
            
        updates = {}
        act_type = str(action.get("type", "hand")).lower()
        act_name = str(action.get("cardNumber") or action.get("name") or "").lower().strip()

        if act_type in ("equipment_ability", "weapon_buff", "hero_ability"):
            buff_power = int(action.get("buff_power", 4 if "hammerhead" in act_name else (2 if "goliath" in act_name else 1)))
            updates["currentAttackBuff"] = int(state.get("currentAttackBuff", 0)) + buff_power
            ap = int(state.get("playerAP", state.get("actionPoints", 1)))
            has_go_again = bool(action.get("has_go_again", False))
            new_ap = ap if has_go_again else max(0, ap - 1)
            updates["playerAP"] = new_ap
            updates["actionPoints"] = new_ap
            return state.without("_simulated_projected_damage").replace(**updates)

        hand = list(state.get("playerHand", []))
        pitch_zone = list(state.get("playerPitch", []))
        discard_zone = list(state.get("playerDiscard", []))

        played_card = None
        if act_type == "hand":
            new_hand = []
            for c in hand:
                if played_card is None and cls.extract_card_meta(c)["name"] == act_name:
                    played_card = c
                else:
                    new_hand.append(c)
            hand = new_hand
            updates["playerHand"] = tuple(hand)
            if played_card is None:
                played_card = action.get("raw") or action
        elif act_type == "arsenal":
            ars = state.get("playerArsenal", [])
            updates["playerArsenal"] = tuple([c for c in ars if cls.extract_card_meta(c)["name"] != act_name])
            played_card = action.get("raw") or action
        elif act_type == "banish":
            banish = state.get("playerBanish", [])
            updates["playerBanish"] = tuple([c for c in banish if cls.extract_card_meta(c)["name"] != act_name])
            played_card = action.get("raw") or action
        else:
            played_card = action.get("raw") or action

        card_meta = cls.extract_card_meta(played_card)
        cost = int(action.get("cost", card_meta.get("cost", 0)))

        resources = state.get("playerResources", [0, 0])
        floating = int(resources[0]) if resources and isinstance(resources, (list, tuple)) else 0

        if floating < cost:
            needed = cost - floating
            candidates = [(c, cls.extract_card_meta(c)) for c in hand]
            candidates.sort(key=lambda item: -item[1]["pitch"])
            rem_hand = []
            for c, meta in candidates:
                if needed > 0:
                    floating += meta["pitch"]
                    needed -= meta["pitch"]
                    pitch_zone.append(c)
                else:
                    rem_hand.append(c)
            hand = rem_hand
            updates["playerHand"] = tuple(hand)

        floating = max(0, floating - cost)
        updates["playerResources"] = (floating, 0)

        ap = int(state.get("playerAP", state.get("actionPoints", 1)))
        has_go_again = bool(action.get("has_go_again", card_meta.get("has_go_again", False)))
        new_ap = ap if has_go_again else max(0, ap - 1)
        updates["playerAP"] = new_ap
        updates["actionPoints"] = new_ap

        if act_type == "hand":
            discard_zone.append(played_card)

        updates["playerPitch"] = tuple(pitch_zone)
        updates["playerDiscard"] = tuple(discard_zone)

        atk_buff = int(state.get("currentAttackBuff", 0))
        base_power = int(action.get("power", card_meta.get("power", 4)))
        atk_power = base_power + atk_buff

        updates["combatChainPower"] = atk_power
        active_chain = dict(state.get("activeChainLink", {}))
        if active_chain or state.get("activeChainLink") is not None:
            active_chain["totalPower"] = atk_power
            active_chain["power"] = atk_power
            active_chain["cardNumber"] = act_name
            updates["activeChainLink"] = ImmutableGameState(active_chain)

        opp_hp = int(state.get("opponentHealth", state.get("theirHealth", 40)))
        opp_hand = list(state.get("opponentHand", []))

        raw_intim = action.get("intimidate")
        if raw_intim is None:
            raw_intim = action.get("intimidate_count", card_meta.get("intimidate_count", 0))
        if isinstance(raw_intim, bool):
            intimidate_count = 1 if raw_intim else 0
        elif isinstance(raw_intim, (int, float)):
            intimidate_count = max(0, int(raw_intim))
        elif action.get("has_intimidate") or card_meta.get("has_intimidate"):
            intimidate_count = int(action.get("intimidate_count", card_meta.get("intimidate_count", 1)))
        elif any(k in act_name.lower() for k in ["pack_hunt", "alpha_rampage", "barraging_beatdown", "intimidate"]):
            intimidate_count = int(action.get("intimidate_count", 1))
        else:
            intimidate_count = 0

        is_dominate = bool(action.get("dominate", card_meta.get("dominate", False)))
        is_overpower = bool(action.get("overpower", card_meta.get("overpower", False)))
        has_phantasm = bool(action.get("phantasm", card_meta.get("phantasm", False)))

        # CR 8.3.13: Phantasm Popping (destruído por carta 6+ poder)
        phantasm_popped = False
        has_opp_card_objs = bool(opp_hand and (isinstance(opp_hand[0], (dict, ImmutableGameState)) or hasattr(opp_hand[0], "get")))
        if has_phantasm and has_opp_card_objs:
            for c in opp_hand:
                if cls.extract_card_meta(c).get("power", 0) >= 6:
                    phantasm_popped = True
                    break

        base_hand_count = int(state.get("opponentHandCount", state.get("theirHandCount", len(opp_hand) if opp_hand else 3)))
        opp_hand_count = max(0, (len(opp_hand) if opp_hand else base_hand_count) - intimidate_count)

        if phantasm_popped:
            expected_block = atk_power
            cards_used_to_block = 1
        elif is_dominate:
            # CR 7.3.2a & CR 8.3.4: Defesa restrita a no máximo 1 carta da mão
            if has_opp_card_objs:
                usable_hand = opp_hand[intimidate_count:] if intimidate_count > 0 else opp_hand
                cards_def = [int(c.get("defense", c.get("block", 3))) for c in usable_hand]
                cards_def.sort(reverse=True)
                opp_hand_count = len(usable_hand)
                expected_block = min(atk_power, cards_def[0] if cards_def else 0)
                cards_used_to_block = 1 if (expected_block > 0 and opp_hand_count > 0) else 0
            else:
                base_hand_count = int(state.get("opponentHandCount", state.get("theirHandCount", 3)))
                opp_hand_count = max(0, base_hand_count - intimidate_count)
                expected_block = min(atk_power, 3 if opp_hand_count > 0 else 0)
                cards_used_to_block = 1 if opp_hand_count > 0 else 0
        elif is_overpower:
            # CR 7.3.2b & CR 8.3.22: Máximo de 1 carta de ação da mão para bloquear
            if has_opp_card_objs:
                usable_hand = opp_hand[intimidate_count:] if intimidate_count > 0 else opp_hand
                cards_def = [int(c.get("defense", c.get("block", 3))) for c in usable_hand]
                cards_def.sort(reverse=True)
                opp_hand_count = len(usable_hand)
                expected_block = min(atk_power, cards_def[0] if cards_def else 0)
                cards_used_to_block = 1 if (expected_block > 0 and opp_hand_count > 0) else 0
            else:
                base_hand_count = int(state.get("opponentHandCount", state.get("theirHandCount", 3)))
                opp_hand_count = max(0, base_hand_count - intimidate_count)
                expected_block = min(atk_power, 3 if opp_hand_count > 0 else 0)
                cards_used_to_block = min(opp_hand_count, 1)
        elif has_opp_card_objs:
            usable_hand = opp_hand[intimidate_count:] if intimidate_count > 0 else opp_hand
            cards_def = [int(c.get("defense", c.get("block", 3))) for c in usable_hand]
            cards_def.sort(reverse=True)
            opp_hand_count = len(usable_hand)

            if opp_hp <= 8:
                expected_block = min(atk_power, sum(cards_def))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)
            elif opp_hp <= 18:
                expected_block = min(atk_power, sum(cards_def[:max(1, len(cards_def) // 2)]))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)
            else:
                expected_block = min(atk_power, cards_def[0] if cards_def else 0)
                cards_used_to_block = 1 if expected_block > 0 else 0
        else:
            base_hand_count = int(state.get("opponentHandCount", state.get("theirHandCount", 3)))
            opp_hand_count = max(0, base_hand_count - intimidate_count)
            if opp_hp <= 8:
                expected_block = min(atk_power, int(opp_hand_count * 2.8))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)
            elif opp_hp <= 18:
                expected_block = min(atk_power, int(opp_hand_count * 1.8))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)
            else:
                expected_block = min(atk_power, int(opp_hand_count * 1.0))
                cards_used_to_block = min(opp_hand_count, (expected_block + 2) // 3)

        unblocked_damage = max(0, atk_power - expected_block)
        updates["opponentHealth"] = max(0, opp_hp - unblocked_damage)
        updates["theirHealth"] = max(0, opp_hp - unblocked_damage)

        new_opp_hand = max(0, opp_hand_count - cards_used_to_block)
        
        has_on_hit = bool(action.get("has_on_hit", card_meta.get("has_on_hit", False)))
        if unblocked_damage > 0 and has_on_hit:
            new_opp_hand = max(0, new_opp_hand - 1)

        updates["opponentHandCount"] = new_opp_hand
        updates["theirHandCount"] = new_opp_hand

        return state.without("_simulated_projected_damage", "currentAttackBuff").replace(**updates)

    @classmethod
    def simulate_defense(cls, state, block_action: dict):
        """
        Simula a decisão de bloqueio na fase defensiva (Phase B).
        Soma a defesa total de multi-cartas contra o ataque recebido (CR 7.3 e 7.5),
        em vez de deduzir dano líquido por carta individualmente.
        """
        if not isinstance(state, ImmutableGameState):
            state = ImmutableGameState(state)
            
        updates = {}
        my_hp = int(state.get("playerHealth", state.get("yourHealth", 20)))
        active_chain = dict(state.get("activeChainLink", {}))
        
        incoming_power = int(active_chain.get("totalPower", active_chain.get("power", state.get("combatChainPower", 4))))

        if isinstance(block_action, list):
            cards_to_block = block_action
        elif isinstance(block_action, dict) and "cards" in block_action and isinstance(block_action["cards"], list):
            cards_to_block = block_action["cards"]
        elif isinstance(block_action, dict) and "blocking_cards" in block_action and isinstance(block_action["blocking_cards"], list):
            cards_to_block = block_action["blocking_cards"]
        elif isinstance(block_action, dict) and "card_names" in block_action and isinstance(block_action["card_names"], list):
            cards_to_block = block_action["card_names"]
        else:
            cards_to_block = [block_action]

        hand = list(state.get("playerHand", []))
        discard = list(state.get("playerDiscard", []))

        has_piercing = bool(active_chain.get("piercing") or active_chain.get("hasPiercing") or state.get("piercing"))
        used_equipment_block = False

        action_def = 0
        for c in cards_to_block:
            if isinstance(c, dict):
                c_meta = cls.extract_card_meta(c)
                val = int(c.get("defense", c.get("block", c_meta.get("defense", 0))))
                c_name = str(c.get("name") or c.get("cardNumber") or c_meta.get("name", "")).lower()
                c_sub = str(c.get("subtype", "")).lower()
                if any(slot in c_sub or slot in c_name for slot in ["head", "chest", "arms", "legs", "equipment", "shield"]):
                    used_equipment_block = True
            else:
                c_name = str(c).lower()
                c_meta = cls.extract_card_meta({"cardNumber": c_name})
                val = int(c_meta.get("defense", 0))
                if any(slot in c_name for slot in ["head", "chest", "arms", "legs", "equipment", "shield"]):
                    used_equipment_block = True

            action_def += val

            found_idx = -1
            for idx, h_card in enumerate(hand):
                h_name = cls.extract_card_meta(h_card)["name"]
                if h_name == c_name or str(h_card.get("cardNumber", "")).lower() == c_name:
                    found_idx = idx
                    break
            if found_idx >= 0:
                discard.append(hand.pop(found_idx))

        updates["playerHand"] = tuple(hand)
        updates["playerDiscard"] = tuple(discard)

        prev_def = int(active_chain.get("totalDefense", 0))
        
        projected_damage = int(state.get("_simulated_projected_damage", 0))
        base_hp = my_hp + projected_damage

        total_def = prev_def + action_def
        active_chain["totalDefense"] = total_def
        active_chain["defense"] = total_def
        active_chain["block"] = total_def
        updates["activeChainLink"] = ImmutableGameState(active_chain)

        eff_incoming = incoming_power + (1 if (has_piercing and used_equipment_block) else 0)
        taken_damage = max(0, eff_incoming - total_def)
        updates["playerHealth"] = max(0, base_hp - taken_damage)
        updates["yourHealth"] = max(0, base_hp - taken_damage)
        updates["_simulated_projected_damage"] = taken_damage

        return state.replace(**updates)

    @classmethod
    def simulate_pitch(cls, state, pitch_action: dict):
        """
        Simula a geração de recursos na fase de Pitch (Phase P / PDECK).
        """
        if not isinstance(state, ImmutableGameState):
            state = ImmutableGameState(state)
            
        updates = {}
        resources = state.get("playerResources", [0, 0])
        floating = int(resources[0]) if resources and isinstance(resources, (list, tuple)) else 0
        
        card_name = cls.extract_card_meta(pitch_action)["name"]
        if "pitch" in pitch_action:
            pitch_val = cls._safe_int(pitch_action["pitch"], 0)
        else:
            meta = cls.extract_card_meta(pitch_action)
            pitch_val = meta["pitch"]

        hand = list(state.get("playerHand", []))
        pitch_zone = list(state.get("playerPitch", []))
        new_hand = []
        found = False
        for c in hand:
            if not found and cls.extract_card_meta(c)["name"] == card_name:
                found = True
                pitch_zone.append(c)
            else:
                new_hand.append(c)

        updates["playerHand"] = tuple(new_hand)
        updates["playerPitch"] = tuple(pitch_zone)
        if found:
            updates["playerResources"] = (floating + pitch_val, 0)

        return state.replace(**updates)

    @classmethod
    def simulate_step(cls, state, action: dict):
        """
        Ponto de entrada unificado para simulação de passo.
        """
        if not isinstance(state, ImmutableGameState):
            state = ImmutableGameState(state)
            
        act_type = str(action.get("type", "")).lower()
        phase = str(state.get("turnPhase", state.get("phase", "M"))).upper()

        if act_type in ("pass", "end_turn", "close_chain", "pass_priority"):
            next_state = state
        elif "block" in act_type or phase in ("B", "DEFENSE"):
            next_state = cls.simulate_defense(state, action)
        elif "pitch" in act_type or phase in ("P", "PDECK"):
            next_state = cls.simulate_pitch(state, action)
        else:
            next_state = cls.simulate_attack(state, action)

        vec = FaBPolicyValueNetwork.extract_state_vector(next_state.to_dict())
        return next_state, vec
