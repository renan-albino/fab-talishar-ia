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
  - Vetorização do estado resultante (192 dimensões) para avaliação imediata pelo Value Head
"""

import copy
import numpy as np
from typing import Dict, Any, Tuple, List, Optional
from ai.model import FaBPolicyValueNetwork, STATE_DIM

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

    @staticmethod
    def extract_card_meta(card: dict) -> dict:
        """Extrai metadados táticos de uma carta (pitch, poder, defesa, custo, go again)."""
        card_num = str(card.get("cardNumber", "")).lower()
        pitch = 1
        if "_blue" in card_num:
            pitch = 3
        elif "_yellow" in card_num:
            pitch = 2
        elif "_red" in card_num:
            pitch = 1

        power = int(card.get("power", 0))
        if power == 0:
            if any(k in card_num for k in ["zipper", "throttle", "zero_to_sixty", "fast_and_furious", "out_pace", "expedite", "snatch"]):
                power = 4 if pitch == 1 else (3 if pitch == 2 else 2)
            elif "pounder" in card_num or "trebuchet" in card_num:
                power = 5
            elif "harpoon" in card_num or "command_and_conquer" in card_num:
                power = 6 if pitch == 1 else 4

        defense = int(card.get("defense", card.get("block", 0)))
        if defense == 0:
            if any(k in card_num for k in ["_red", "_yellow", "_blue"]) and not any(k in card_num for k in ["heart", "accelerator", "providence", "tunic"]):
                defense = 3 if pitch == 3 else 2

        cost = 0
        if any(k in card_num for k in ["throttle", "pounder", "trebuchet", "staunch", "spinal", "pulverize", "buckling"]):
            cost = 2 if "spinal" not in card_num and "pulverize" not in card_num else 4
        elif any(k in card_num for k in ["zipper", "fast_and_furious", "out_pace", "expedite", "harpoon", "spark_of_genius", "command_and_conquer"]):
            cost = 1
        elif any(k in card_num for k in ["zero_to_sixty", "bios_update", "convection", "boom_grenade", "snatch", "leg_tap", "rising_knee"]):
            cost = 0

        has_go_again = any(k in card_num for k in [
            "zero_to_sixty", "throttle", "zipper", "expedite", "out_pace", "fast_and_furious", "leg_tap", "snatch", "rising_knee", "fai"
        ])
        has_on_hit = any(oh in card_num for oh in DANGEROUS_ON_HITS)

        return {
            "name": card_num,
            "pitch": pitch,
            "power": power,
            "defense": defense,
            "cost": cost,
            "has_go_again": has_go_again,
            "has_on_hit": has_on_hit,
            "raw": card
        }

    @classmethod
    def simulate_attack(cls, state: dict, action: dict) -> dict:
        """
        Simula a execução de um ataque na fase principal (Phase M).
        Aplica desconto de pitch, AP, poder de combate vs bloqueio do oponente e vida.
        """
        sim_state = copy.deepcopy(state)
        
        # 1. Recursos e Pitch
        resources = sim_state.get("playerResources", [0, 0])
        floating = int(resources[0]) if isinstance(resources, list) and resources else 0
        cost = int(action.get("cost", 0))
        
        hand = sim_state.get("playerHand", [])
        pitch_zone = sim_state.get("playerPitch", [])
        discard_zone = sim_state.get("playerDiscard", [])

        # Se recursos flutuantes forem insuficientes, pitch automático de cartas azuis/amarelas da mão
        if floating < cost:
            needed = cost - floating
            rem_hand = []
            for c in hand:
                meta = cls.extract_card_meta(c)
                # Não pitchar a carta que está sendo jogada
                if meta["name"] == action.get("name") and c not in rem_hand:
                    rem_hand.append(c)
                    continue
                if needed > 0:
                    floating += meta["pitch"]
                    needed -= meta["pitch"]
                    pitch_zone.append(c)
                else:
                    rem_hand.append(c)
            hand = rem_hand

        floating = max(0, floating - cost)
        sim_state["playerResources"] = [floating, 0]

        # 2. Consumo de Action Points (AP) e Go Again
        ap = int(sim_state.get("playerAP", sim_state.get("actionPoints", 1)))
        has_go_again = bool(action.get("has_go_again", False))
        if has_go_again:
            new_ap = ap  # Gastou 1 e ganhou 1 com Go Again
        else:
            new_ap = max(0, ap - 1)
        sim_state["playerAP"] = new_ap
        sim_state["actionPoints"] = new_ap

        # 3. Remover carta jogada da zona de origem
        act_type = action.get("type", "hand").lower()
        act_name = action.get("name", "")
        if act_type == "hand":
            new_hand = []
            found = False
            for c in hand:
                if not found and cls.extract_card_meta(c)["name"] == act_name:
                    found = True
                    discard_zone.append(c)
                else:
                    new_hand.append(c)
            sim_state["playerHand"] = new_hand
        elif act_type == "arsenal":
            sim_state["playerArsenal"] = []
        elif act_type == "banish":
            banish = sim_state.get("playerBanish", [])
            sim_state["playerBanish"] = [c for c in banish if cls.extract_card_meta(c)["name"] != act_name]

        sim_state["playerPitch"] = pitch_zone
        sim_state["playerDiscard"] = discard_zone

        # 4. Resolução de Combate e Dano contra o Oponente
        atk_power = int(action.get("power", 4))
        opp_hp = int(sim_state.get("opponentHealth", sim_state.get("theirHealth", 40)))
        opp_hand_count = int(sim_state.get("opponentHandCount", sim_state.get("theirHandCount", 3)))

        # Estimativa de Bloqueio do Oponente baseada na contagem de mão dele
        # Cada carta na mão do oponente bloqueia em média 2.5 de dano se ele estiver defendendo
        if opp_hp <= 8:
            expected_block = min(atk_power, int(opp_hand_count * 2.8))  # Oponente bloqueia pesado com vida baixa
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
        
        # 5. On-Hit Effects
        if unblocked_damage > 0 and action.get("has_on_hit", False):
            # On-Hit aciona: penaliza mão ou recursos do oponente
            new_opp_hand = max(0, new_opp_hand - 1)

        sim_state["opponentHandCount"] = new_opp_hand
        sim_state["theirHandCount"] = new_opp_hand

        return sim_state

    @classmethod
    def simulate_defense(cls, state: dict, block_action: dict) -> dict:
        """
        Simula a decisão de bloqueio na fase defensiva (Phase B).
        Calcula redução de dano sofrido e preservação da mão.
        """
        sim_state = copy.deepcopy(state)
        
        my_hp = int(sim_state.get("playerHealth", sim_state.get("yourHealth", 20)))
        active_chain = sim_state.get("activeChainLink", {})
        if not isinstance(active_chain, dict):
            active_chain = {}
        incoming_power = int(active_chain.get("totalPower", sim_state.get("combatChainPower", 4)))

        block_val = int(block_action.get("block", block_action.get("defense", 0)))
        card_name = block_action.get("name", "")

        # Remover carta de bloqueio da mão e adicionar ao descarte
        hand = sim_state.get("playerHand", [])
        discard = sim_state.get("playerDiscard", [])
        new_hand = []
        found = False
        for c in hand:
            if not found and cls.extract_card_meta(c)["name"] == card_name:
                found = True
                discard.append(c)
            else:
                new_hand.append(c)

        sim_state["playerHand"] = new_hand
        sim_state["playerDiscard"] = discard

        # Dano líquido sofrido
        taken_damage = max(0, incoming_power - block_val)
        sim_state["playerHealth"] = max(0, my_hp - taken_damage)
        sim_state["yourHealth"] = max(0, my_hp - taken_damage)

        return sim_state

    @classmethod
    def simulate_pitch(cls, state: dict, pitch_action: dict) -> dict:
        """
        Simula a geração de recursos na fase de Pitch (Phase P / PDECK).
        """
        sim_state = copy.deepcopy(state)
        
        resources = sim_state.get("playerResources", [0, 0])
        floating = int(resources[0]) if isinstance(resources, list) and resources else 0
        
        card_name = pitch_action.get("name", "")
        pitch_val = int(pitch_action.get("pitch", 1))

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
