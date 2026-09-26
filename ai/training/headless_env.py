"""
ai/training/headless_env.py
===========================
Headless, in-memory self-play loop for training the FaB AI.
Runs MCTS vs MCTS locally using GameSimulator, bypasses Talishar API.
"""

import time
import uuid
import numpy as np
from typing import List, Dict, Any, Tuple
import torch

from ai.mcts.standard_mcts import MCTSEngine
from ai.game_simulator import GameSimulator
from ai.model import FaBPolicyValueNetwork
from config.settings import SETTINGS
from ai.mcts.state import ImmutableGameState


class HeadlessSelfPlayLoop:
    """
    Simula uma partida completa de Flesh and Blood em memória,
    chamando o GameSimulator passo a passo, sem depender de subprocessos,
    rede ou Talishar.
    """
    def __init__(self, model: FaBPolicyValueNetwork, mcts_sims: int = None, device: str = None):
        self.model = model
        self.device = device or SETTINGS.device
        self.mcts_sims = mcts_sims or SETTINGS.mcts_simulations

    def _generate_dummy_deck(self, name: str) -> List[Dict[str, Any]]:
        # Deck fictício simplificado para manter o MCTS e o Simulador funcionando
        return [{
            "name": f"{name}_attack_{i}",
            "pitch": (i % 3) + 1,
            "cost": i % 3,
            "power": 4 + (i % 2),
            "defense": 3,
            "type": "action"
        } for i in range(40)]

    def _init_state(self, deck1: str, deck2: str) -> ImmutableGameState:
        return ImmutableGameState({
            "playerHealth": 40,
            "opponentHealth": 40,
            "theirHealth": 40,
            "yourHealth": 40,
            "playerHand": tuple(self._generate_dummy_deck(deck1)[:4]),
            "opponentHand": tuple(self._generate_dummy_deck(deck2)[:4]),
            "playerPitch": tuple(),
            "playerDiscard": tuple(),
            "turnPhase": "M",
            "phase": "M",
            "actionPoints": 1,
            "playerAP": 1,
            "playerResources": (0, 0),
            "opponentHandCount": 4,
            "theirHandCount": 4
        })

    def _get_legal_actions(self, state: ImmutableGameState, current_player: int) -> List[Dict[str, Any]]:
        actions = []
        phase = str(state.get("turnPhase", state.get("phase", "M")))
        if phase in ("M", "MAIN"):
            if state.get("playerAP", 1) > 0:
                for card in state.get("playerHand", []):
                    actions.append({
                        "type": "hand", 
                        "name": card["name"], 
                        "cost": card.get("cost", 0), 
                        "power": card.get("power", 4)
                    })
            actions.append({"type": "pass_priority"})
        elif phase in ("B", "DEFENSE"):
            actions.append({"type": "pass_priority"})
            for card in state.get("playerHand", []):
                actions.append({"type": "block", "cards": [card]})
        else:
            actions.append({"type": "pass_priority"})
        return actions

    def _swap_players(self, state: ImmutableGameState) -> ImmutableGameState:
        """Troca a perspectiva dos jogadores (para quando passa a prioridade)."""
        updates = {
            "playerHealth": state.get("opponentHealth", 40),
            "opponentHealth": state.get("playerHealth", 40),
            "yourHealth": state.get("opponentHealth", 40),
            "theirHealth": state.get("playerHealth", 40),
            "playerHand": state.get("opponentHand", tuple()),
            "opponentHand": state.get("playerHand", tuple()),
            "playerAP": 1,
            "actionPoints": 1,
            "turnPhase": "M",
            "phase": "M",
            "opponentHandCount": len(state.get("playerHand", tuple())),
            "theirHandCount": len(state.get("opponentHand", tuple())),
        }
        return state.replace(**updates)

    def play_game(self, deck1: str, deck2: str) -> Tuple[List[Any], int]:
        state = self._init_state(deck1, deck2)
        
        # MCTSEngine configurado
        mcts1 = MCTSEngine(self.model, device=self.device)
        mcts2 = MCTSEngine(self.model, device=self.device)
        
        trajectory = []
        turn = 0
        current_player = 1
        
        # Limite de turnos de segurança
        while state.get("playerHealth", 40) > 0 and state.get("opponentHealth", 40) > 0 and turn < 150:
            turn += 1
            legal_actions = self._get_legal_actions(state, current_player)
            mcts = mcts1 if current_player == 1 else mcts2
            
            best_idx, policy_probs = mcts.search(state.to_dict(), legal_actions, num_simulations=self.mcts_sims)
            
            if not policy_probs.any() or sum(policy_probs) == 0:
                policy_probs = np.ones(32, dtype=np.float32) / 32.0
                
            action_idx = best_idx if best_idx < len(legal_actions) else 0
            action = legal_actions[action_idx]
            
            vec = FaBPolicyValueNetwork.extract_state_vector(state.to_dict())
            
            full_policy = np.zeros(32, dtype=np.float32)
            for i, p in enumerate(policy_probs):
                if i < 32:
                    full_policy[i] = p
            
            # (state_vec, policy_vec, player_id)
            trajectory.append((vec, full_policy, current_player))
            
            # Avança o estado pelo Simulador
            state, _ = GameSimulator.simulate_step(state, action)
            
            # Se for pass, troca a perspectiva
            if action.get("type") == "pass_priority":
                state = self._swap_players(state)
                current_player = 2 if current_player == 1 else 1

        winner = 1 if state.get("opponentHealth", 40) <= 0 else (2 if state.get("playerHealth", 40) <= 0 else 0)
        return trajectory, winner