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


import copy
def _shallow_clone_state(state: dict) -> dict:
    """
    Faz uma cópia rápida do estado, garantindo isolamento de estruturas mutáveis
    e de dicionários de cartas (ex: playerHand, activeChainLink) para evitar
    vazamento de estado entre rollouts do MCTS.
    """
    if not isinstance(state, dict):
        return {}
    cloned = state.copy()
    for key in ("playerHand", "activeChainLink", "playerEquipment", "opponentHand", "combatChain"):
        if key in cloned:
            cloned[key] = copy.deepcopy(cloned[key])
    return cloned


DANGEROUS_ON_HITS = {
    "crippling", "crush", "command_and_conquer", "red_in_the_ledger",
    "snatch", "mask_of_momentum", "bloodrot", "frailty", "inertia",
    "leave_no_witnesses", "surgical_extraction", "erase_face",
    "spitfire", "spinal_crush", "rightful_king", "hypothermia"
}

class GameSimulator:
    """
    Motor de transição determinística para rollouts e expansão de folhas do MCTS.
    """

    @classmethod
    def extract_card_meta(cls, card: Any) -> dict:
        """
        Extrai metadados táticos e semânticos de uma carta consultando
        data/fab_cards_db.json e data/fab_card_semantics.json.
        Properly extracts base power, base defense, cost, pitch, and keywords:
        (has_go_again, dominate, overpower, piercing, phantasm, on_hit_severity)
        for any card in the database, with safe fallbacks only if absent.
        """
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
        if isinstance(card, dict) and card.get("pitch") is not None and int(card.get("pitch", 0)) > 0:
            pitch = int(card["pitch"])
        elif db_entry and "pitch" in db_entry:
            pitch = int(db_entry["pitch"])
        elif "_blue" in card_num:
            pitch = 3
        elif "_yellow" in card_num:
            pitch = 2
        elif "_red" in card_num:
            pitch = 1
        else:
            pitch = 1

        # 2. Power
        power = int(card.get("power", 0)) if isinstance(card, dict) else 0
        if power == 0 and db_entry and "power" in db_entry:
            power = int(db_entry["power"])
        if power == 0 and not db_entry:
            # Fallback seguro somente se carta completamente ausente da base
            if any(k in card_num for k in ["zipper", "throttle", "zero_to_sixty", "fast_and_furious", "out_pace", "expedite", "snatch"]):
                power = 4 if pitch == 1 else (3 if pitch == 2 else 2)
            elif "pounder" in card_num or "trebuchet" in card_num:
                power = 5
            elif "harpoon" in card_num or "command_and_conquer" in card_num:
                power = 6 if pitch == 1 else 4

        # 3. Defense / Block
        defense = int(card.get("defense", card.get("block", 0))) if isinstance(card, dict) else 0
        if defense == 0 and db_entry and "defense" in db_entry:
            defense = int(db_entry["defense"])
        if defense == 0 and not db_entry:
            # Fallback seguro somente se carta completamente ausente da base
            if any(k in card_num for k in ["_red", "_yellow", "_blue"]) and not any(k in card_num for k in ["heart", "accelerator", "providence", "tunic"]):
                defense = 3 if pitch == 3 else 2

        # 4. Cost
        cost = int(card.get("cost", 0)) if (isinstance(card, dict) and "cost" in card) else 0
        if cost == 0 and db_entry and "cost" in db_entry:
            cost = int(db_entry["cost"])
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
    def simulate_attack(cls, state: dict, action: dict) -> dict:
        """
        Simula a execução de um ataque na fase principal (Phase M).
        Aplica desconto de pitch conforme CR 1.14.2, AP, buffs de equipamento,
        poder de combate vs bloqueio do oponente e vida.
        """
        sim_state = _shallow_clone_state(state)
        act_type = str(action.get("type", "hand")).lower()
        act_name = str(action.get("name", action.get("cardNumber", "")))

        # Tratar buffs de equipamento / arma / herói (não causam dano direto ao oponente!)
        if act_type in ("equipment_ability", "weapon_buff", "hero_ability"):
            buff_power = int(action.get("buff_power", 4 if "hammerhead" in act_name else (2 if "goliath" in act_name else 1)))
            sim_state["currentAttackBuff"] = int(sim_state.get("currentAttackBuff", 0)) + buff_power
            # Consumir AP se aplicável
            ap = int(sim_state.get("playerAP", sim_state.get("actionPoints", 1)))
            has_go_again = bool(action.get("has_go_again", False))
            new_ap = ap if has_go_again else max(0, ap - 1)
            sim_state["playerAP"] = new_ap
            sim_state["actionPoints"] = new_ap
            return sim_state

        hand = sim_state.get("playerHand", [])
        pitch_zone = sim_state.get("playerPitch", [])
        discard_zone = sim_state.get("playerDiscard", [])

        # 1. Isolar a carta jogada de sua zona de origem
        played_card = None
        if act_type == "hand":
            new_hand = []
            for c in hand:
                if played_card is None and cls.extract_card_meta(c)["name"] == act_name:
                    played_card = c
                else:
                    new_hand.append(c)
            hand = new_hand
            sim_state["playerHand"] = hand
            if played_card is None:
                played_card = action.get("raw") or action
        elif act_type == "arsenal":
            sim_state["playerArsenal"] = []
            played_card = action.get("raw") or action
        elif act_type == "banish":
            banish = sim_state.get("playerBanish", [])
            sim_state["playerBanish"] = [c for c in banish if cls.extract_card_meta(c)["name"] != act_name]
            played_card = action.get("raw") or action
        else:
            played_card = action.get("raw") or action

        card_meta = cls.extract_card_meta(played_card)
        cost = int(action.get("cost", card_meta.get("cost", 0)))

        # 2. Recursos e Pitch conforme CR 1.14.2:
        # Usa recursos flutuantes primeiro; se insuficiente, pitch Blue (3) -> Yellow (2) -> Red (1)
        resources = sim_state.get("playerResources", [0, 0])
        floating = int(resources[0]) if isinstance(resources, list) and resources else 0

        if floating < cost:
            needed = cost - floating
            # Candidatos a pitch são as cartas restantes na mão (excluindo a carta atacante já separada)
            candidates = [(c, cls.extract_card_meta(c)) for c in hand]
            # Ordenação estável por pitch decrescente: Blue (3) -> Yellow (2) -> Red (1)
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
            sim_state["playerHand"] = hand

        floating = max(0, floating - cost)
        sim_state["playerResources"] = [floating, 0]

        # 3. Consumo de Action Points (AP) e Go Again
        ap = int(sim_state.get("playerAP", sim_state.get("actionPoints", 1)))
        has_go_again = bool(action.get("has_go_again", card_meta.get("has_go_again", False)))
        if has_go_again:
            new_ap = ap  # Gastou 1 e recuperou com Go Again
        else:
            new_ap = max(0, ap - 1)
        sim_state["playerAP"] = new_ap
        sim_state["actionPoints"] = new_ap

        # 4. Enviar carta jogada da mão para o descarte
        if act_type == "hand":
            discard_zone.append(played_card)

        sim_state["playerPitch"] = pitch_zone
        sim_state["playerDiscard"] = discard_zone

        # 5. Resolução de Combate e Dano contra o Oponente
        # Incorporar buff acumulado de equipamentos/armas
        atk_buff = int(sim_state.pop("currentAttackBuff", 0))
        base_power = int(action.get("power", card_meta.get("power", 4)))
        atk_power = base_power + atk_buff

        # Atualizar cadeia de combate se presente
        sim_state["combatChainPower"] = atk_power
        active_chain = sim_state.get("activeChainLink")
        if isinstance(active_chain, dict):
            active_chain["totalPower"] = atk_power
            active_chain["power"] = atk_power
            active_chain["cardNumber"] = act_name

        opp_hp = int(sim_state.get("opponentHealth", sim_state.get("theirHealth", 40)))
        opp_hand = sim_state.get("opponentHand", [])

        # Intimidate (CR 8.5.8)
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

        if isinstance(opp_hand, list) and len(opp_hand) > 0 and isinstance(opp_hand[0], dict):
            # Mundo determinizado com cartas concretas amostradas (Cowling 2012 / ReBel 2020)
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
            base_hand_count = int(sim_state.get("opponentHandCount", sim_state.get("theirHandCount", 3)))
            opp_hand_count = max(0, base_hand_count - intimidate_count)
            # Estimativa de Bloqueio do Oponente baseada na contagem de mão dele (com desconto de intimidate)
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
        sim_state["opponentHealth"] = max(0, opp_hp - unblocked_damage)
        sim_state["theirHealth"] = max(0, opp_hp - unblocked_damage)

        # Atualizar mão estimada do oponente pós-bloqueio
        new_opp_hand = max(0, opp_hand_count - cards_used_to_block)
        
        # 6. On-Hit Effects
        has_on_hit = bool(action.get("has_on_hit", card_meta.get("has_on_hit", False)))
        if unblocked_damage > 0 and has_on_hit:
            new_opp_hand = max(0, new_opp_hand - 1)

        sim_state["opponentHandCount"] = new_opp_hand
        sim_state["theirHandCount"] = new_opp_hand

        return sim_state

    @classmethod
    def simulate_defense(cls, state: dict, block_action: dict) -> dict:
        """
        Simula a decisão de bloqueio na fase defensiva (Phase B).
        Soma a defesa total de multi-cartas contra o ataque recebido (CR 7.3 e 7.5),
        em vez de deduzir dano líquido por carta individualmente.
        """
        sim_state = _shallow_clone_state(state)
        
        my_hp = int(sim_state.get("playerHealth", sim_state.get("yourHealth", 20)))
        active_chain = sim_state.get("activeChainLink")
        if not isinstance(active_chain, dict):
            active_chain = {}
            sim_state["activeChainLink"] = active_chain

        incoming_power = int(active_chain.get("totalPower", active_chain.get("power", sim_state.get("combatChainPower", 4))))

        # Identificar lista de cartas usadas no bloqueio
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

        hand = sim_state.get("playerHand", [])
        discard = sim_state.get("playerDiscard", [])

        action_def = 0
        for c in cards_to_block:
            if isinstance(c, dict):
                c_meta = cls.extract_card_meta(c)
                val = int(c.get("defense", c.get("block", c_meta.get("defense", 0))))
                c_name = str(c.get("name") or c.get("cardNumber") or c_meta.get("name", "")).lower()
            else:
                c_name = str(c).lower()
                c_meta = cls.extract_card_meta({"cardNumber": c_name})
                val = int(c_meta.get("defense", 0))

            action_def += val

            # Remover exatamente uma instância correspondente da mão
            found_idx = -1
            for idx, h_card in enumerate(hand):
                h_name = cls.extract_card_meta(h_card)["name"]
                if h_name == c_name or str(h_card.get("cardNumber", "")).lower() == c_name:
                    found_idx = idx
                    break
            if found_idx >= 0:
                discard.append(hand.pop(found_idx))

        sim_state["playerHand"] = hand
        sim_state["playerDiscard"] = discard

        # Defesa prévia acumulada nesta chain link (se houver múltiplos bloqueadores)
        prev_def = int(active_chain.get("totalDefense", 0))
        
        # Recupera a vida base verdadeira desfazendo o dano projetado de simulações sequenciais (se houver)
        # Estados reais do Talishar não terão essa flag, logo base_hp = my_hp (sem cura fantasma)
        projected_damage = int(state.get("_simulated_projected_damage", 0))
        base_hp = my_hp + projected_damage

        total_def = prev_def + action_def
        active_chain["totalDefense"] = total_def
        active_chain["defense"] = total_def
        active_chain["block"] = total_def

        # Dano líquido sofrido contra a defesa total acumulada
        taken_damage = max(0, incoming_power - total_def)
        sim_state["playerHealth"] = max(0, base_hp - taken_damage)
        sim_state["yourHealth"] = max(0, base_hp - taken_damage)
        
        # Marca o dano projetado no estado simulado para a próxima iteração
        sim_state["_simulated_projected_damage"] = taken_damage

        return sim_state

    @classmethod
    def simulate_pitch(cls, state: dict, pitch_action: dict) -> dict:
        """
        Simula a geração de recursos na fase de Pitch (Phase P / PDECK).
        """
        sim_state = _shallow_clone_state(state)
        
        resources = sim_state.get("playerResources", [0, 0])
        floating = int(resources[0]) if isinstance(resources, list) and resources else 0
        
        card_name = pitch_action.get("name", "")
        if "pitch" in pitch_action:
            pitch_val = int(pitch_action["pitch"])
        else:
            meta = cls.extract_card_meta(pitch_action)
            pitch_val = meta["pitch"]
            if not card_name:
                card_name = meta["name"]

        hand = sim_state.get("playerHand", [])
        pitch_zone = sim_state.get("playerPitch", [])
        new_hand = []
        found = False
        for c in hand:
            if not found and cls.extract_card_meta(c)["name"] == card_name:
                found = True
                pitch_zone.append(c)
            else:
                new_hand.append(c)

        sim_state["playerHand"] = new_hand
        sim_state["playerPitch"] = pitch_zone
        sim_state["playerResources"] = [floating + pitch_val, 0]

        return sim_state

    @classmethod
    def simulate_step(cls, state: dict, action: dict) -> Tuple[dict, np.ndarray]:
        """
        Ponto de entrada unificado para simulação de passo:
        Identifica a fase e tipo de ação, projeta o novo estado e retorna o vetor normalizado.
        """
        act_type = str(action.get("type", "")).lower()
        phase = str(state.get("turnPhase", state.get("phase", "M"))).upper()

        if "block" in act_type or phase in ("B", "DEFENSE"):
            next_state = cls.simulate_defense(state, action)
        elif "pitch" in act_type or phase in ("P", "PDECK"):
            next_state = cls.simulate_pitch(state, action)
        else:
            next_state = cls.simulate_attack(state, action)

        vec = FaBPolicyValueNetwork.extract_state_vector(next_state)
        return next_state, vec
