"""
ai/shadow_mode.py
Modo Sombra: intercepta ações enviadas ao Talishar, simula localmente e compara os estados
para medir a fidelidade do simulador e detectar divergências Sim2Real.
"""

import json
import time
from typing import Tuple, Dict, Any, Optional

from config.settings import SETTINGS
from ai.game_simulator import GameSimulator
from stats.db import get_connection


def predict(pre_state: dict, card_id: str, mode: Optional[int] = None) -> Optional[dict]:
    """
    Constrói a ação a partir do estado e pede para o simulador prever os campos próprios.
    Resolve índices brutos (ex: mode 27 card_id='0') para cartas reais de playerHand/playerEquipment.
    """
    if not card_id:
        return None

    turn_phase = str(pre_state.get("turnPhase", "")).upper()
    if isinstance(pre_state.get("turnPhase"), dict):
        turn_phase = str(pre_state.get("turnPhase").get("turnPhase", "")).upper()

    # Mapeamento de fase para tipo de ação
    if turn_phase in ("P", "PDECK"):
        act_type = "pitch"
    elif turn_phase in ("B", "DEFENSE"):
        act_type = "block"
    elif turn_phase in ("M", ""):
        act_type = "hand"
    else:
        return None

    actual_card_name = str(card_id).lower().strip()
    card_obj = None
    if str(card_id).isdigit():
        idx = int(card_id)
        if mode == 3:
            equips = pre_state.get("playerEquipment", [])
            if 0 <= idx < len(equips) and isinstance(equips[idx], dict):
                card_obj = equips[idx]
                actual_card_name = str(card_obj.get("cardNumber", "")).lower().strip()
        else:
            hand = pre_state.get("playerHand", [])
            if 0 <= idx < len(hand) and isinstance(hand[idx], dict):
                card_obj = hand[idx]
                actual_card_name = str(card_obj.get("cardNumber", "")).lower().strip()

    action = {"type": act_type, "cardNumber": actual_card_name, "name": actual_card_name}
    if card_obj:
        action["raw"] = card_obj

    try:
        next_state, _ = GameSimulator.simulate_step(pre_state, action)
        ns_dict = next_state.to_dict() if hasattr(next_state, "to_dict") else next_state
        return {
            "hand_count": len(ns_dict.get("playerHand", [])),
            "resources": int(ns_dict.get("playerResources", [0, 0])[0]),
            "action_points": int(ns_dict.get("playerAP", ns_dict.get("actionPoints", 0))),
            "arsenal_count": len(ns_dict.get("playerArsenal", [])),
            "player_health": int(ns_dict.get("playerHealth", pre_state.get("playerHealth", 40))),
            "opponent_health": int(ns_dict.get("opponentHealth", pre_state.get("opponentHealth", 40))),
            "card_consumed": actual_card_name,
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
        "arsenal_count": len(post_state.get("playerArsenal", [])),
        "player_health": int(post_state.get("playerHealth", 40)),
        "opponent_health": int(post_state.get("opponentHealth", 40)),
    }

    diffs = {}
    for k in ("hand_count", "resources", "action_points", "arsenal_count", "player_health", "opponent_health"):
        if k in expected and actual[k] != expected[k]:
            diffs[k] = {"expected": expected[k], "actual": actual[k]}

    # Checar se a carta foi consumida (não deve permanecer na mão após ser jogada/bloqueada/pitch)
    card_id = expected.get("card_consumed")
    if card_id and not confounded:
        post_hand = [
            str(c.get("cardNumber", c.get("name", "")) if isinstance(c, dict) else c).lower()
            for c in post_state.get("playerHand", [])
        ]
        pre_hand = [
            str(c.get("cardNumber", c.get("name", "")) if isinstance(c, dict) else c).lower()
            for c in pre_state.get("playerHand", [])
        ]
        # Se a contagem da carta não diminuiu na mão
        if pre_hand.count(card_id.lower()) > 0 and post_hand.count(card_id.lower()) == pre_hand.count(card_id.lower()):
            diffs["card_unconsumed"] = {"expected": f"consumed {card_id}", "actual": "still_in_hand"}

    return diffs, confounded


def record(
    room_id: str,
    hero: str,
    turn: int,
    phase: str,
    mode: int,
    card_id: str,
    diffs: dict,
    confounded: bool,
    pre_state: dict,
    is_human: bool,
):
    """Grava o registro no SQLite."""
    pre_state_json = json.dumps(pre_state) if is_human else None
    diffs_json = json.dumps(diffs)

    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO shadow_steps (room_id, hero, turn, phase, mode, card_id, diffs_json, confounded, pre_state_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    room_id,
                    hero,
                    turn,
                    phase,
                    mode,
                    card_id,
                    diffs_json,
                    1 if confounded else 0,
                    pre_state_json,
                    time.time(),
                ),
            )
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
    hero = getattr(client, "deck_name", getattr(client, "hero_name", "unknown"))

    # Identifica is_human a partir do próprio client state ou log
    is_vs_human = (
        getattr(client, "name", "") == "AIMaster_Bot"
        or "Human_vs_Bot" in str(client.room_id)
        or str(client.room_id).isdigit()
    )

    record(client.room_id, hero, turn, phase, mode, card_id, diffs, confounded, pre_state, is_vs_human)

    # Se houve divergência não contaminada por mudança de turno, notificar Sim2Real Detector
    if diffs and not confounded:
        try:
            from ai import sim2real_detector

            opp_hero_str = str(post_state.get("theirHero", post_state.get("opponentHero", "Unknown")))
            sim2real_detector.record_anomaly(
                room_id=client.room_id,
                hero=hero,
                turn=turn,
                phase=phase,
                anomaly_type="SIMULATOR_DIVERGENCE",
                message=f"Divergência GameSimulator vs Talishar em {card_id}: {diffs}",
                opponent_hero=opp_hero_str,
                last_action={"mode": mode, "card_id": card_id},
                extra_context={"diffs": diffs},
            )
            if hasattr(client, "warning"):
                client.warning(f"[SIM2REAL DIVERGÊNCIA] Turno {turn}: {card_id} -> {diffs}")
        except Exception:
            pass
