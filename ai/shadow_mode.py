"""
ai/shadow_mode.py
Modo Sombra: intercepta ações enviadas ao Talishar, simula localmente e compara os estados
para medir a fidelidade do simulador.
"""

import json
import time
from typing import Tuple, Dict, Any, Optional

from config.settings import SETTINGS
from ai.game_simulator import GameSimulator
from stats.db import get_connection

def predict(pre_state: dict, card_id: str) -> Optional[dict]:
    """
    Constrói a ação a partir do estado e pede para o simulador prever os campos próprios.
    """
    if not card_id:
        return None
        
    turn_phase = str(pre_state.get("turnPhase", "")).upper()
    if isinstance(pre_state.get("turnPhase"), dict):
        turn_phase = str(pre_state.get("turnPhase").get("turnPhase", "")).upper()

    # Mapeamento grosseiro de fase para tipo de ação
    if turn_phase in ("P", "PDECK"):
        act_type = "pitch"
    elif turn_phase in ("B", "DEFENSE"):
        act_type = "block"
    elif turn_phase in ("M", ""):
        act_type = "hand" # Pode ser arsenal etc, mas hand serve para testes básicos
    else:
        return None

    action = {"type": act_type, "cardNumber": card_id}
    
    try:
        next_state, _ = GameSimulator.simulate_step(pre_state, action)
        ns_dict = next_state.to_dict() if hasattr(next_state, "to_dict") else next_state
        return {
            "hand_count": len(ns_dict.get("playerHand", [])),
            "resources": int(ns_dict.get("playerResources", [0, 0])[0]),
            "action_points": int(ns_dict.get("playerAP", ns_dict.get("actionPoints", 0))),
            "arsenal_count": len(ns_dict.get("playerArsenal", []))
        }
    except Exception:
        return None

def compare(expected: dict, pre_state: dict, post_state: dict) -> Tuple[Dict[str, Any], bool]:
    """
    Compara o esperado com o post_state e indica se o tick foi contaminado (confounded).
    """
    confounded = False
    if pre_state.get("turnNo") != post_state.get("turnNo"):
        confounded = True
    if pre_state.get("turnPlayer") != post_state.get("turnPlayer"):
        confounded = True

    actual = {
        "hand_count": len(post_state.get("playerHand", [])),
        "resources": int(post_state.get("playerResources", [0, 0])[0]),
        "action_points": int(post_state.get("playerAP", post_state.get("actionPoints", 0))),
        "arsenal_count": len(post_state.get("playerArsenal", []))
    }

    diffs = {}
    for k, v in expected.items():
        if actual[k] != v:
            diffs[k] = {"expected": v, "actual": actual[k]}

    return diffs, confounded

def record(room_id: str, hero: str, turn: int, phase: str, mode: int, card_id: str, 
           diffs: dict, confounded: bool, pre_state: dict, is_human: bool):
    """Grava o registro no SQLite."""
    pre_state_json = json.dumps(pre_state) if is_human else None
    diffs_json = json.dumps(diffs)
    
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO shadow_steps (room_id, hero, turn, phase, mode, card_id, diffs_json, confounded, pre_state_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (room_id, hero, turn, phase, mode, card_id, diffs_json, 1 if confounded else 0, pre_state_json, time.time()))
            conn.commit()
    except Exception as e:
        print(f"Shadow mode record error: {e}")

def flush(client, pending_shadow: tuple, post_state: dict):
    """Callback do client quando recebe novo estado."""
    expected, pre_state, mode, card_id = pending_shadow
    diffs, confounded = compare(expected, pre_state, post_state)
    
    turn = int(pre_state.get("turnNo", 1))
    tp = pre_state.get("turnPhase", "")
    phase = str(tp.get("turnPhase", "") if isinstance(tp, dict) else tp)
    hero = getattr(client, "deck_name", "unknown")
    
    # Identifica is_human a partir do próprio client state ou log
    is_vs_human = (getattr(client, "name", "") == "AIMaster_Bot" or "Human_vs_Bot" in str(client.room_id) or str(client.room_id).isdigit())
    
    record(client.room_id, hero, turn, phase, mode, card_id, diffs, confounded, pre_state, is_vs_human)
