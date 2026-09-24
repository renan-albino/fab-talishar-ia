"""
ai/mcts/world_generator.py
==========================
Geração de mundos determinizados para ISMCTS com amostragem Deck-Aware.
"""

import os
import random
from typing import Dict, Any, List, Optional

from ai.logger import get_logger

logger = get_logger("mcts")

_CARD_DB_CACHE: Optional[Dict[str, Any]] = None


def _get_card_db() -> Dict[str, Any]:
    """Retorna o banco de dados oficial de cartas em cache."""
    global _CARD_DB_CACHE
    if _CARD_DB_CACHE is None:
        possible_paths = [
            "data/fab_cards_db.json",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "fab_cards_db.json"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "fab_cards_db.json"),
        ]
        db_path = None
        for p in possible_paths:
            if os.path.exists(p):
                db_path = p
                break

        if db_path and os.path.exists(db_path):
            try:
                import json
                with open(db_path, "r", encoding="utf-8") as f:
                    _CARD_DB_CACHE = json.load(f)
            except Exception as e:
                logger.warning(f"Erro ao carregar card_db de {db_path}: {e}")
                _CARD_DB_CACHE = {}
        else:
            _CARD_DB_CACHE = {}
    return _CARD_DB_CACHE


def generate_worlds(
    state: Dict[str, Any],
    opp_hand_count: Optional[int] = None,
    num_worlds: int = 4,
    player_id: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """
    Gera `num_worlds` mundos determinizados com amostragem Deck-Aware.

    Prioridade do pool de amostragem da mão oculta:
      1. Cartas reais vistas no opponentDiscard (proxy de alta fidelidade).
      2. Cartas do banco de dados oficial (fab_cards_db.json) compatíveis
         com a classe do herói oponente (ex: Guardian/Generic para Bravo).
      3. Cartas genéricas Red/Yellow/Blue como fallback.
    """
    if opp_hand_count is None:
        opp_hand = state.get("opponentHand", [])
        if isinstance(opp_hand, list) and len(opp_hand) > 0:
            opp_hand_count = len(opp_hand)
        else:
            raw_count = state.get("opponentHandCount")
            if raw_count is None:
                raw_count = state.get("theirHandCount", 4)
            opp_hand_count = int(raw_count) if raw_count is not None else 4

    if opp_hand_count == 0:
        return [dict(state)]

    opp_discard = state.get("opponentDiscard", state.get("theirDiscard", []))
    opp_deck_pool = list(opp_discard) if isinstance(opp_discard, list) and opp_discard else []

    # ── Identificar classe do herói adversário para amostragem Deck-Aware ──
    opp_hero = str(
        state.get("opponentHero",
        state.get("theirCharacter",
        state.get("initialLoad", {}).get("theirHeroName", "")))
    ).lower()

    card_db = _get_card_db()
    class_cards = []
    if card_db and opp_hero:
        for c_slug, meta in card_db.items():
            if not isinstance(meta, dict):
                continue
            c_class = str(meta.get("class", "")).lower()
            c_slot = str(meta.get("slot", "")).lower()
            if c_slot == "deck" or not c_slot:
                if any(ch in opp_hero for ch in ["bravo", "betsy", "victor", "valda", "guardian"]) and "guardian" in c_class:
                    class_cards.append({"cardNumber": c_slug, "pitch": int(meta.get("pitch", 1)), "power": int(meta.get("power", 4)), "defense": int(meta.get("defense", 3)), "action": 27})
                elif any(ch in opp_hero for ch in ["katsu", "fai", "ira", "zen", "ninja"]) and "ninja" in c_class:
                    class_cards.append({"cardNumber": c_slug, "pitch": int(meta.get("pitch", 1)), "power": int(meta.get("power", 3)), "defense": int(meta.get("defense", 2)), "action": 27})
                elif any(ch in opp_hero for ch in ["dash", "maxx", "mechanologist"]) and "mechanologist" in c_class:
                    class_cards.append({"cardNumber": c_slug, "pitch": int(meta.get("pitch", 1)), "power": int(meta.get("power", 4)), "defense": int(meta.get("defense", 2)), "action": 27})
                elif "generic" in c_class:
                    class_cards.append({"cardNumber": c_slug, "pitch": int(meta.get("pitch", 1)), "power": int(meta.get("power", 3)), "defense": int(meta.get("defense", 2)), "action": 27})

    if class_cards:
        opp_deck_pool.extend(random.sample(class_cards, min(len(class_cards), 20)))

    generic_cards = [
        {"cardNumber": "generic_red",    "pitch": 1, "power": 4, "defense": 2, "action": 27},
        {"cardNumber": "generic_yellow", "pitch": 2, "power": 3, "defense": 3, "action": 27},
        {"cardNumber": "generic_blue",   "pitch": 3, "power": 2, "defense": 3, "action": 27},
    ]
    target_pool_size = max(opp_hand_count, 9)
    while len(opp_deck_pool) < target_pool_size:
        opp_deck_pool.extend(generic_cards)

    from ai.mcts.state import ImmutableGameState
    worlds = []
    for _ in range(num_worlds):
        sampled = random.sample(opp_deck_pool, min(opp_hand_count, len(opp_deck_pool)))
        
        updates = {
            "opponentHand": tuple(sampled),
            "opponentHandCount": len(sampled)
        }
        
        if isinstance(state, ImmutableGameState):
            world = state.replace(**updates)
        else:
            world = ImmutableGameState(state).replace(**updates)
        worlds.append(world)

    return worlds
