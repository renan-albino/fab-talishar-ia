"""
ai/training/headless_env.py
===========================
Headless, in-memory self-play loop for training the FaB AI.
Runs MCTS vs MCTS locally using GameSimulator and real canonical decks from decks/*.json,
bypassing Talishar API and Docker dependencies for maximum throughput.
"""

import os
import json
import random
import numpy as np
from typing import List, Dict, Any, Tuple, Optional
import torch

from ai.mcts.standard_mcts import MCTSEngine
from ai.game_simulator import GameSimulator
from ai.model import FaBPolicyValueNetwork
from config.settings import SETTINGS, DATA_DIR, PROJECT_ROOT
from ai.mcts.state import ImmutableGameState


_FAB_CARDS_DB: Optional[dict] = None
_DECKS_CACHE: Dict[str, dict] = {}


def _get_cards_db() -> dict:
    global _FAB_CARDS_DB
    if _FAB_CARDS_DB is None:
        db_path = DATA_DIR / "fab_cards_db.json"
        if db_path.exists():
            with open(db_path, "r", encoding="utf-8") as f:
                _FAB_CARDS_DB = json.load(f)
        else:
            _FAB_CARDS_DB = {}
    return _FAB_CARDS_DB


def _get_deck_data(deck_name: str) -> dict:
    global _DECKS_CACHE
    safe_name = os.path.splitext(os.path.basename(deck_name))[0].lower()
    if safe_name in _DECKS_CACHE:
        return _DECKS_CACHE[safe_name]

    decks_dir = os.path.join(str(PROJECT_ROOT), "decks")
    deck_path = os.path.join(decks_dir, f"{safe_name}.json")
    if not os.path.exists(deck_path):
        # Fallback para primeiro deck disponível
        available = [f for f in os.listdir(decks_dir) if f.endswith(".json")]
        if available:
            deck_path = os.path.join(decks_dir, available[0])
            safe_name = os.path.splitext(available[0])[0].lower()

    if os.path.exists(deck_path):
        with open(deck_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            _DECKS_CACHE[safe_name] = data
            return data
    return {"name": deck_name, "cards": []}


class HeadlessSelfPlayLoop:
    """
    Simula uma partida completa de Flesh and Blood em memória,
    utilizando baralhos reais de decks/*.json, dados de fab_cards_db.json
    e o GameSimulator determinístico para alta velocidade de self-play.
    """
    def __init__(self, model: FaBPolicyValueNetwork, mcts_sims: int = None, device: str = None):
        self.model = model
        self.device = device or SETTINGS.device
        self.mcts_sims = mcts_sims or SETTINGS.mcts_simulations
        self.cards_db = _get_cards_db()

    def _parse_deck(self, deck_name: str) -> Tuple[dict, List[dict], List[dict], List[dict]]:
        """
        Carrega o baralho e separa em:
        (hero_meta, equipment_cards, weapon_cards, main_deck_cards)
        """
        raw_deck = _get_deck_data(deck_name)
        hero_meta = None
        equipment = []
        weapons = []
        main_deck = []

        cards = raw_deck.get("cards", [])
        for entry in cards:
            cid = str(entry.get("identifier", "")).lower().strip()
            total = int(entry.get("total", 1))
            meta = dict(self.cards_db.get(cid, {}))
            if not meta:
                meta = {"id": cid, "name": cid.replace("_", " ").title(), "cost": 0, "power": 3, "defense": 2, "pitch": 1}
            else:
                meta = dict(meta)

            meta["cardNumber"] = cid
            meta["name"] = meta.get("name") or cid.replace("_", " ").title()

            # Enriquece com campos canônicos (pitch, cost, power, defense, has_go_again)
            sim_meta = GameSimulator.extract_card_meta(meta)
            for k in ("pitch", "cost", "power", "defense", "has_go_again", "has_on_hit", "dominate", "overpower"):
                if k in sim_meta and k not in meta:
                    meta[k] = sim_meta[k]

            slot = str(meta.get("slot", ""))
            ctype = str(meta.get("type", ""))

            if slot == "Hero" or ctype == "C":
                hero_meta = meta
            elif ctype == "W" or slot in ("Weapon", "Weapons"):
                weapons.append(meta)
            elif ctype == "E" or slot in ("Head", "Chest", "Arms", "Legs", "Off-Hand", "Quiver"):
                equipment.append(meta)
            else:
                for _ in range(total):
                    main_deck.append(dict(meta))

        # Fallback de herói se não detectado
        if hero_meta is None:
            hero_meta = {
                "id": raw_deck.get("name", "hero").lower(),
                "name": raw_deck.get("name", "Hero"),
                "is_young": False
            }

        # Fallback para main deck vazio
        if not main_deck:
            main_deck = [{
                "cardNumber": f"generic_attack_{i}",
                "name": f"Generic Strike {i}",
                "pitch": (i % 3) + 1,
                "cost": i % 3,
                "power": 4,
                "defense": 3
            } for i in range(40)]

        return hero_meta, equipment, weapons, main_deck

    def _init_state(self, deck1: str, deck2: str) -> ImmutableGameState:
        """Inicializa o estado com cartas, equipamentos e bibliotecas reais."""
        p1_hero, p1_eq, p1_wep, p1_deck = self._parse_deck(deck1)
        p2_hero, p2_eq, p2_wep, p2_deck = self._parse_deck(deck2)

        rng = random.Random()
        p1_deck_shuffled = list(p1_deck)
        p2_deck_shuffled = list(p2_deck)
        rng.shuffle(p1_deck_shuffled)
        rng.shuffle(p2_deck_shuffled)

        # Mão inicial de 4 cartas
        p1_hand = tuple(p1_deck_shuffled[:4])
        p1_draw_pile = tuple(p1_deck_shuffled[4:])

        p2_hand = tuple(p2_deck_shuffled[:4])
        p2_draw_pile = tuple(p2_deck_shuffled[4:])

        p1_is_young = "young" in str(p1_hero.get("subtype", "")).lower() or p1_hero.get("is_young", False)
        p2_is_young = "young" in str(p2_hero.get("subtype", "")).lower() or p2_hero.get("is_young", False)

        p1_hp = 20 if p1_is_young else 40
        p2_hp = 20 if p2_is_young else 40

        # Equipamentos ativos
        p1_equipment = tuple(p1_eq[:4])
        p2_equipment = tuple(p2_eq[:4])

        return ImmutableGameState({
            "playerHealth": p1_hp,
            "yourHealth": p1_hp,
            "opponentHealth": p2_hp,
            "theirHealth": p2_hp,
            "playerHand": p1_hand,
            "opponentHand": p2_hand,
            "playerDeck": p1_draw_pile,
            "opponentDeck": p2_draw_pile,
            "playerEquipment": p1_equipment,
            "opponentEquipment": p2_equipment,
            "playerWeapons": tuple(p1_wep),
            "opponentWeapons": tuple(p2_wep),
            "playerPitch": tuple(),
            "opponentPitch": tuple(),
            "playerDiscard": tuple(),
            "opponentDiscard": tuple(),
            "playerArsenal": tuple(),
            "opponentArsenal": tuple(),
            "turnPhase": "M",
            "phase": "M",
            "playerAP": 1,
            "actionPoints": 1,
            "playerResources": (0, 0),
            "opponentHandCount": len(p2_hand),
            "theirHandCount": len(p2_hand),
            "combatChainPower": 0,
            "activeChainLink": ImmutableGameState({}),
            "combatChain": tuple(),
            "currentChainLink": 0,
            "playerHero": p1_hero.get("id", "hero1"),
            "opponentHero": p2_hero.get("id", "hero2"),
        })

    def _get_legal_actions(self, state: ImmutableGameState) -> List[Dict[str, Any]]:
        """Gera ações legais respeitando a fase atual (M ou B)."""
        actions = []
        phase = str(state.get("turnPhase", state.get("phase", "M"))).upper()

        if phase in ("M", "MAIN"):
            ap = int(state.get("playerAP", 1))
            res = state.get("playerResources", (0, 0))
            floating = int(res[0]) if isinstance(res, (list, tuple)) else 0
            hand = list(state.get("playerHand", []))

            # Pitch disponível na mão
            available_pitch = sum(GameSimulator.extract_card_meta(c)["pitch"] for c in hand)
            total_purchasing_power = floating + available_pitch

            if ap > 0:
                # 1. Atacar com armas equipadas
                for wep in state.get("playerWeapons", []):
                    w_meta = GameSimulator.extract_card_meta(wep)
                    cost = int(w_meta.get("cost", 0))
                    if total_purchasing_power >= cost:
                        actions.append({
                            "type": "weapon",
                            "name": w_meta["name"],
                            "cardNumber": w_meta.get("name"),
                            "cost": cost,
                            "power": int(w_meta.get("power", 2)),
                            "has_go_again": bool(w_meta.get("has_go_again", False))
                        })

                # 2. Jogar cartas da mão
                for idx, card in enumerate(hand):
                    meta = GameSimulator.extract_card_meta(card)
                    cost = int(meta.get("cost", 0))
                    # A carta gasta a si mesma se for jogada, então os outros cards fornecem pitch
                    pitch_others = total_purchasing_power - meta["pitch"]
                    if pitch_others >= cost or floating >= cost:
                        actions.append({
                            "type": "hand",
                            "name": meta["name"],
                            "cardNumber": meta.get("name"),
                            "card_index": idx,
                            "cost": cost,
                            "power": int(meta.get("power", 3)),
                            "has_go_again": bool(meta.get("has_go_again", False)),
                            "raw": card
                        })

            # Sempre pode passar prioridade
            actions.append({"type": "pass_priority"})

        elif phase in ("B", "DEFENSE"):
            # Fase defensiva: pode passar (não bloquear) ou bloquear com cartas da mão
            actions.append({"type": "pass_priority"})
            hand = list(state.get("playerHand", []))
            for idx, card in enumerate(hand):
                meta = GameSimulator.extract_card_meta(card)
                def_val = int(meta.get("defense", 0))
                if def_val > 0:
                    actions.append({
                        "type": "block",
                        "name": meta["name"],
                        "cardNumber": meta.get("name"),
                        "defense": def_val,
                        "cards": [card]
                    })
        else:
            actions.append({"type": "pass_priority"})

        return actions

    def _upkeep_and_swap(self, state: ImmutableGameState) -> ImmutableGameState:
        """
        Executa a fase de fim de turno / upkeep:
        - Cartas de pitch vão para o fundo da biblioteca
        - Desenha até o intellect (4 cartas)
        - Inverte a perspectiva dos jogadores (troca atacante/defensor)
        """
        # Jogador 1 (que terminou o turno)
        p1_hand = list(state.get("playerHand", []))
        p1_deck = list(state.get("playerDeck", []))
        p1_pitch = list(state.get("playerPitch", []))

        # Pitch vai para o fundo do deck
        p1_deck.extend(p1_pitch)

        # Draw até 4 cartas
        intellect = 4
        needed = max(0, intellect - len(p1_hand))
        if needed > 0 and p1_deck:
            draw_n = min(needed, len(p1_deck))
            p1_hand.extend(p1_deck[:draw_n])
            p1_deck = p1_deck[draw_n:]

        # Jogador 2 (oponente)
        p2_hand = list(state.get("opponentHand", []))
        p2_deck = list(state.get("opponentDeck", []))
        p2_pitch = list(state.get("opponentPitch", []))
        p2_deck.extend(p2_pitch)

        needed_p2 = max(0, intellect - len(p2_hand))
        if needed_p2 > 0 and p2_deck:
            draw_n2 = min(needed_p2, len(p2_deck))
            p2_hand.extend(p2_deck[:draw_n2])
            p2_deck = p2_deck[draw_n2:]

        # Nova perspectiva invertida (o antigo P2 agora é o jogador ativo)
        updates = {
            "playerHealth": state.get("opponentHealth", 40),
            "yourHealth": state.get("opponentHealth", 40),
            "opponentHealth": state.get("playerHealth", 40),
            "theirHealth": state.get("playerHealth", 40),
            "playerHand": tuple(p2_hand),
            "opponentHand": tuple(p1_hand),
            "playerDeck": tuple(p2_deck),
            "opponentDeck": tuple(p1_deck),
            "playerEquipment": state.get("opponentEquipment", tuple()),
            "opponentEquipment": state.get("playerEquipment", tuple()),
            "playerWeapons": state.get("opponentWeapons", tuple()),
            "opponentWeapons": state.get("playerWeapons", tuple()),
            "playerPitch": tuple(),
            "opponentPitch": tuple(),
            "playerDiscard": state.get("opponentDiscard", tuple()),
            "opponentDiscard": state.get("playerDiscard", tuple()),
            "playerArsenal": state.get("opponentArsenal", tuple()),
            "opponentArsenal": state.get("playerArsenal", tuple()),
            "playerHero": state.get("opponentHero", "hero2"),
            "opponentHero": state.get("playerHero", "hero1"),
            "turnPhase": "M",
            "phase": "M",
            "playerAP": 1,
            "actionPoints": 1,
            "playerResources": (0, 0),
            "opponentHandCount": len(p1_hand),
            "theirHandCount": len(p1_hand),
            "combatChainPower": 0,
            "activeChainLink": ImmutableGameState({}),
            "combatChain": tuple(),
            "currentChainLink": 0,
        }
        return state.without("_simulated_projected_damage", "currentAttackBuff").replace(**updates)

    def _swap_perspective_for_defense(self, state: ImmutableGameState) -> ImmutableGameState:
        """Inverte a perspectiva temporariamente para o defensor escolher seus bloqueios."""
        updates = {
            "playerHealth": state.get("opponentHealth", 40),
            "yourHealth": state.get("opponentHealth", 40),
            "opponentHealth": state.get("playerHealth", 40),
            "theirHealth": state.get("playerHealth", 40),
            "playerHand": state.get("opponentHand", tuple()),
            "opponentHand": state.get("playerHand", tuple()),
            "playerDeck": state.get("opponentDeck", tuple()),
            "opponentDeck": state.get("playerDeck", tuple()),
            "playerEquipment": state.get("opponentEquipment", tuple()),
            "opponentEquipment": state.get("playerEquipment", tuple()),
            "playerWeapons": state.get("opponentWeapons", tuple()),
            "opponentWeapons": state.get("playerWeapons", tuple()),
            "playerPitch": state.get("opponentPitch", tuple()),
            "opponentPitch": state.get("playerPitch", tuple()),
            "playerDiscard": state.get("opponentDiscard", tuple()),
            "opponentDiscard": state.get("playerDiscard", tuple()),
            "playerArsenal": state.get("opponentArsenal", tuple()),
            "opponentArsenal": state.get("playerArsenal", tuple()),
            "playerHero": state.get("opponentHero", "hero2"),
            "opponentHero": state.get("playerHero", "hero1"),
            "turnPhase": "B",
            "phase": "B",
            "opponentHandCount": len(state.get("playerHand", tuple())),
            "theirHandCount": len(state.get("playerHand", tuple())),
        }
        return state.replace(**updates)

    def _swap_perspective_back_to_attacker(self, state: ImmutableGameState, has_go_again: bool) -> ImmutableGameState:
        """Retorna a perspectiva para o atacante após a resolução do combate."""
        updates = {
            "playerHealth": state.get("opponentHealth", 40),
            "yourHealth": state.get("opponentHealth", 40),
            "opponentHealth": state.get("playerHealth", 40),
            "theirHealth": state.get("playerHealth", 40),
            "playerHand": state.get("opponentHand", tuple()),
            "opponentHand": state.get("playerHand", tuple()),
            "playerDeck": state.get("opponentDeck", tuple()),
            "opponentDeck": state.get("playerDeck", tuple()),
            "playerEquipment": state.get("opponentEquipment", tuple()),
            "opponentEquipment": state.get("playerEquipment", tuple()),
            "playerWeapons": state.get("opponentWeapons", tuple()),
            "opponentWeapons": state.get("playerWeapons", tuple()),
            "playerPitch": state.get("opponentPitch", tuple()),
            "opponentPitch": state.get("playerPitch", tuple()),
            "playerDiscard": state.get("opponentDiscard", tuple()),
            "opponentDiscard": state.get("playerDiscard", tuple()),
            "playerArsenal": state.get("opponentArsenal", tuple()),
            "opponentArsenal": state.get("playerArsenal", tuple()),
            "playerHero": state.get("opponentHero", "hero2"),
            "opponentHero": state.get("playerHero", "hero1"),
            "turnPhase": "M",
            "phase": "M",
            "opponentHandCount": len(state.get("playerHand", tuple())),
            "theirHandCount": len(state.get("playerHand", tuple())),
            "combatChainPower": 0,
            "activeChainLink": ImmutableGameState({}),
        }
        return state.without("_simulated_projected_damage", "currentAttackBuff").replace(**updates)

    def play_game(self, deck1: str, deck2: str) -> Tuple[List[Any], int]:
        """
        Executa uma partida completa e retorna a trajetória e o vencedor:
        winner = 1 (P1 venceu), 2 (P2 venceu), ou 0 (empate/timeout).
        """
        state = self._init_state(deck1, deck2)

        mcts1 = MCTSEngine(self.model, device=self.device)
        mcts2 = MCTSEngine(self.model, device=self.device)

        trajectory = []
        turn = 0
        active_player = 1  # 1 ou 2

        # Loop de turnos (limite máximo de 120 iterações para segurança)
        while state.get("playerHealth", 40) > 0 and state.get("opponentHealth", 40) > 0 and turn < 120:
            turn += 1
            phase = str(state.get("turnPhase", state.get("phase", "M"))).upper()

            # ── 1. Fase Principal de Ataque (M) ──────────────────────
            if phase in ("M", "MAIN"):
                legal_actions = self._get_legal_actions(state)
                mcts = mcts1 if active_player == 1 else mcts2

                best_idx, policy_probs = mcts.search(state.to_dict(), legal_actions, num_simulations=self.mcts_sims)
                if not policy_probs.any() or sum(policy_probs) == 0:
                    policy_probs = np.ones(32, dtype=np.float32) / 32.0

                action_idx = best_idx if best_idx < len(legal_actions) else 0
                action = legal_actions[action_idx]

                # Vetor de estado em O(1) com card embeddings reais
                vec = FaBPolicyValueNetwork.extract_state_vector(state.to_dict())
                full_policy = np.zeros(32, dtype=np.float32)
                for i, p in enumerate(policy_probs[:32]):
                    full_policy[i] = p

                trajectory.append((vec, full_policy, active_player))

                if action.get("type") == "pass_priority":
                    # Fim do turno do jogador ativo: upkeep e passa a vez
                    state = self._upkeep_and_swap(state)
                    active_player = 2 if active_player == 1 else 1
                else:
                    # Executa o ataque via GameSimulator
                    has_go_again = bool(action.get("has_go_again", False))
                    state, _ = GameSimulator.simulate_step(state, action)

                    # Verifica letalidade imediata pós-ataque
                    if state.get("opponentHealth", 40) <= 0:
                        break

                    # Transição para a defesa do oponente (Phase B)
                    defending_player = 2 if active_player == 1 else 1
                    state = self._swap_perspective_for_defense(state)

                    def_actions = self._get_legal_actions(state)
                    def_mcts = mcts2 if defending_player == 2 else mcts1

                    def_best_idx, def_policy = def_mcts.search(state.to_dict(), def_actions, num_simulations=max(3, self.mcts_sims // 2))
                    if not def_policy.any() or sum(def_policy) == 0:
                        def_policy = np.ones(32, dtype=np.float32) / 32.0

                    def_idx = def_best_idx if def_best_idx < len(def_actions) else 0
                    def_action = def_actions[def_idx]

                    def_vec = FaBPolicyValueNetwork.extract_state_vector(state.to_dict())
                    def_full_policy = np.zeros(32, dtype=np.float32)
                    for i, p in enumerate(def_policy[:32]):
                        def_full_policy[i] = p

                    trajectory.append((def_vec, def_full_policy, defending_player))

                    # Resolução do bloqueio
                    if def_action.get("type") == "block":
                        state = GameSimulator.simulate_defense(state, def_action)

                    # Retorna perspectiva para o atacante
                    state = self._swap_perspective_back_to_attacker(state, has_go_again=has_go_again)

                    # Se o ataque não tinha go-again ou se os APs acabaram, passa a vez
                    if not has_go_again or state.get("playerAP", 0) <= 0:
                        state = self._upkeep_and_swap(state)
                        active_player = 2 if active_player == 1 else 1

            else:
                # Fallback para fases não mapeadas
                state = self._upkeep_and_swap(state)
                active_player = 2 if active_player == 1 else 1

        # Determinação do vencedor terminal
        # playerHealth refere-se a quem terminou com a perspectiva ativa
        p_active_hp = state.get("playerHealth", 40)
        p_inactive_hp = state.get("opponentHealth", 40)

        if active_player == 1:
            p1_hp = p_active_hp
            p2_hp = p_inactive_hp
        else:
            p1_hp = p_inactive_hp
            p2_hp = p_active_hp

        if p2_hp <= 0 and p1_hp > 0:
            winner = 1
        elif p1_hp <= 0 and p2_hp > 0:
            winner = 2
        elif p1_hp > p2_hp:
            winner = 1
        elif p2_hp > p1_hp:
            winner = 2
        else:
            winner = 0

        return trajectory, winner