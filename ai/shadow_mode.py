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


def _is_layer_card(card_name: str, card_obj: Optional[dict] = None) -> bool:
    """Retorna True se a carta é Instant, Reaction ou habilidade retida em camada no Talishar."""
    if not card_name:
        return False
    name_clean = str(card_name).lower().strip()
    if any(k in name_clean for k in (
        "blizzard", "sigil_of_solace", "oasis_respite", "take_the_lead", "sink_below",
        "fate_foreseen", "pummel", "razor_reflex", "ironsong_response", "whisper_of_the_oracle"
    )):
        return True
    if isinstance(card_obj, dict):
        c_type = str(card_obj.get("type") or card_obj.get("cardType", "")).upper()
        if any(t in c_type for t in ("I", "INSTANT", "AR", "DR", "REACTION")):
            return True
    try:
        from ai.game_simulator import _get_cards_db
        db = _get_cards_db()
        entry = db.get(name_clean)
        if entry:
            t = str(entry.get("type", "")).upper()
            if t in ("I", "INSTANT") or "REACTION" in str(entry.get("subtype", "")).upper():
                return True
    except Exception:
        pass
    return False


def _is_draw_or_cantrip(card_name: str) -> bool:
    """Retorna True se a carta compra, repõe ou substitui cartas na mão."""
    if not card_name:
        return False
    name = str(card_name).lower().strip()
    if any(kw in name for kw in (
        "draw", "glint", "tome", "spoils", "cash", "lead", "snatch",
        "plunder", "rouse", "belittle", "sink", "fate", "blood_on_her_hands"
    )):
        return True
    try:
        from ai.game_simulator import _get_cards_db
        db = _get_cards_db()
        entry = db.get(name) or {}
        if "draw" in str(entry).lower():
            return True
    except Exception:
        pass
    return False


def predict(pre_state: dict, card_id: str, mode: Optional[int] = None) -> Optional[dict]:
    """
    Constrói a ação a partir do estado e pede para o simulador prever os campos próprios.
    Resolve índices brutos (ex: mode 27 card_id='0') para cartas reais de playerHand/playerEquipment.
    """
    if not card_id or mode in (16, 18, 23, 24, 99, 100) or str(card_id).upper() == "PASS":
        return None

    turn_phase = str(pre_state.get("turnPhase", "")).upper()
    if isinstance(pre_state.get("turnPhase"), dict):
        turn_phase = str(pre_state.get("turnPhase").get("turnPhase", "")).upper()

    # Mapeamento de fase para tipo de ação
    zone = "hand"
    card_id_str = str(card_id)
    if turn_phase in ("P", "PDECK"):
        act_type = "pitch"
    elif turn_phase in ("B", "DEFENSE"):
        act_type = "block"
    elif turn_phase in ("M", ""):
        if mode == 5:
            act_type = "arsenal"
            zone = "arsenal"
        elif mode == 3:
            act_type = "weapon"
            zone = "equipment"
        elif mode == 1 or card_id_str.startswith(("EQ-", "MYCHAR-")):
            act_type = "equipment_ability"
            zone = "equipment"
        else:
            act_type = "hand"
    else:
        return None

    actual_card_name = card_id_str.lower().strip()
    card_obj = None
    if mode == 5:
        zone = "arsenal"
        act_type = "arsenal"
        ars = pre_state.get("playerArsenal", []) or pre_state.get("playerArse", [])
        if card_id_str.isdigit():
            idx = int(card_id_str)
            if 0 <= idx < len(ars) and isinstance(ars[idx], dict):
                card_obj = ars[idx]
                actual_card_name = str(card_obj.get("cardNumber", card_obj.get("name", ""))).lower().strip()
        elif ars:
            for item in ars:
                if isinstance(item, dict) and str(item.get("cardNumber", item.get("name", ""))).lower().strip() == actual_card_name:
                    card_obj = item
                    break
    elif card_id_str.isdigit():
        idx = int(card_id_str)
        if mode in (1, 3):
            zone = "equipment"
            equips = pre_state.get("playerEquipment", [])
            for eq in equips:
                if isinstance(eq, dict) and str(eq.get("actionDataOverride", "") or eq.get("uniqueID", "") or eq.get("id", "")) == card_id_str:
                    card_obj = eq
                    actual_card_name = str(card_obj.get("cardNumber", card_obj.get("name", ""))).lower().strip()
                    break
            if card_obj is None and 0 <= idx < len(equips) and isinstance(equips[idx], dict):
                card_obj = equips[idx]
                actual_card_name = str(card_obj.get("cardNumber", card_obj.get("name", ""))).lower().strip()
            if card_obj:
                eq_type = str(card_obj.get("type", "")).upper()
                eq_slot = str(card_obj.get("slot", "")).lower()
                if mode == 3 or eq_type in ("W", "WEAPON") or eq_slot in ("weapon", "1h", "2h"):
                    act_type = "weapon"
        else:
            hand = pre_state.get("playerHand", [])
            for c in hand:
                if isinstance(c, dict) and str(c.get("actionDataOverride", "") or c.get("uniqueID", "")) == card_id_str:
                    card_obj = c
                    actual_card_name = str(card_obj.get("cardNumber", card_obj.get("name", ""))).lower().strip()
                    break
            if card_obj is None and 0 <= idx < len(hand) and isinstance(hand[idx], dict):
                card_obj = hand[idx]
                actual_card_name = str(card_obj.get("cardNumber", card_obj.get("name", ""))).lower().strip()

    action = {"type": act_type, "cardNumber": actual_card_name, "name": actual_card_name}
    if card_id_str.isdigit():
        action["card_idx"] = int(card_id_str)
    if card_obj:
        action["raw"] = card_obj

    try:
        next_state, _ = GameSimulator.simulate_step(pre_state, action, with_vector=False)
        ns_dict = next_state.to_dict() if hasattr(next_state, "to_dict") else next_state

        # Em Phase B (declaração de bloco), o dano no Talishar só é deduzido no Damage Step (após reactions).
        # No tick intermediário após o bloco, o HP permanece o mesmo do pre_state.
        expected_hp = int(pre_state.get("playerHealth", 40)) if act_type == "block" else int(ns_dict.get("playerHealth", pre_state.get("playerHealth", 40)))

        # Ao declarar ataque, o dano no Talishar só é deduzido no Damage Step (após defesa e reações).
        # No tick intermediário após o ataque, opponentHealth permanece o mesmo do pre_state.
        expected_opp_hp = int(pre_state.get("opponentHealth", 40)) if act_type in ("hand", "arsenal", "attack") else int(ns_dict.get("opponentHealth", pre_state.get("opponentHealth", 40)))

        return {
            "hand_count": len(ns_dict.get("playerHand", [])),
            "resources": int(ns_dict.get("playerResources", [0, 0])[0]),
            "action_points": int(ns_dict.get("playerAP", ns_dict.get("actionPoints", 0))),
            "arsenal_count": len(ns_dict.get("playerArsenal", []) or ns_dict.get("playerArse", [])),
            "player_health": expected_hp,
            "opponent_health": expected_opp_hp,
            "card_consumed": actual_card_name,
            "zone": zone,
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
    if bool(pre_state.get("amIActivePlayer")) != bool(post_state.get("amIActivePlayer")):
        confounded = True

    pre_tp = str(pre_state.get("turnPhase", "")).upper()
    if isinstance(pre_state.get("turnPhase"), dict):
        pre_tp = str(pre_state.get("turnPhase").get("turnPhase", "")).upper()

    post_tp = str(post_state.get("turnPhase", "")).upper()
    if isinstance(post_state.get("turnPhase"), dict):
        post_tp = str(post_state.get("turnPhase").get("turnPhase", "")).upper()

    # Transições intermediárias de pagamento de custos ou janelas de escolha/resolução no Talishar:
    if pre_tp in ("M", "B", "") and post_tp in ("P", "PDECK", "PAYGOLDORPITCH"):
        confounded = True
    # Abertura de combate (M/A -> B/DEFENSE): prioridade passa ao defensor; mão e AP do atacante ficam em espera
    if pre_tp in ("M", "A") and post_tp in ("B", "DEFENSE"):
        confounded = True
    if post_tp in (
        "CHOOSECARD", "MAYCHOOSECARD", "CHOOSEMULTIZONE", "MAYCHOOSEMULTIZONE",
        "CHOOSEHAND", "MAYCHOOSEHAND", "OPT", "BUTTONINPUT", "YESNO",
        "INSTANT", "RESOLUTIONSTEP", "ARS", "ENDTURN", "OVER"
    ) or bool((post_state.get("playerInputPopUp") or {}).get("active")):
        confounded = True

    actual = {
        "hand_count": len(post_state.get("playerHand", [])),
        "resources": int(post_state.get("playerResources", [0, 0])[0]),
        "action_points": int(post_state.get("playerAP", post_state.get("actionPoints", 0))),
        "arsenal_count": len(post_state.get("playerArsenal", []) or post_state.get("playerArse", [])),
        "player_health": int(post_state.get("playerHealth", 40)),
        "opponent_health": int(post_state.get("opponentHealth", 40)),
    }

    diffs = {}
    card_consumed = str(expected.get("card_consumed", "")).lower()
    for k in ("hand_count", "resources", "action_points", "arsenal_count", "player_health", "opponent_health"):
        if k in expected and actual[k] != expected[k]:
            # Em Phase P (pitch para pagar custo pendente):
            # O Talishar consome imediatamente os recursos do pitch e o AP da ação engatilhada.
            # Se os recursos gerados ou AP foram consumidos pela ação pendente (actual <= expected),
            # trata-se da liquidação legítima do custo no Talishar.
            if pre_tp in ("P", "PDECK", "PAYGOLDORPITCH") and k in ("resources", "action_points"):
                if actual[k] <= expected[k]:
                    continue
            if k == "player_health" and pre_tp in ("B", "DEFENSE") and post_tp not in ("B", "DEFENSE"):
                if actual["player_health"] <= expected["player_health"]:
                    continue
            # Cartas com custo adicional / modais (ex: Enlightened Strike): retidas na mão/arsenal pelo Talishar até a resolução do modal
            if "enlightened_strike" in card_consumed and k in ("hand_count", "arsenal_count", "action_points"):
                continue
            # Cartas que compram/substituem cartas na mão (cantrips/draws):
            if k == "hand_count" and actual["hand_count"] > expected["hand_count"] and _is_draw_or_cantrip(card_consumed):
                continue
            # Instants/Reactions retidos na camada até a passagem de prioridade / resolução:
            if k == "hand_count" and _is_layer_card(card_consumed):
                continue
            # Timing de cura em resolução de Instants (ex: Sigil of Solace cura 3 HP após resolução de camada):
            if k in ("player_health", "opponent_health") and "sigil_of_solace" in card_consumed and abs(actual[k] - expected[k]) <= 3:
                continue
            diffs[k] = {"expected": expected[k], "actual": actual[k]}

    # Checar se a carta foi consumida (não deve permanecer na zona de origem após ser jogada/bloqueada/pitch)
    card_id = expected.get("card_consumed")
    zone = expected.get("zone", "hand")
    if card_id and not confounded:
        # Cartas com modais de custo adicional ou Instants/Reactions retidas em camada não disparam falso positivo de card_unconsumed
        if "enlightened_strike" in str(card_id).lower() or _is_layer_card(str(card_id)):
            pass
        elif zone == "arsenal":
            post_ars = [
                str(c.get("cardNumber", c.get("name", "")) if isinstance(c, dict) else c).lower()
                for c in (post_state.get("playerArsenal", []) or post_state.get("playerArse", []))
            ]
            pre_ars = [
                str(c.get("cardNumber", c.get("name", "")) if isinstance(c, dict) else c).lower()
                for c in (pre_state.get("playerArsenal", []) or pre_state.get("playerArse", []))
            ]
            if pre_ars.count(card_id.lower()) > 0 and post_ars.count(card_id.lower()) == pre_ars.count(card_id.lower()):
                diffs["card_unconsumed"] = {"expected": f"consumed {card_id} from arsenal", "actual": "still_in_arsenal"}
        elif zone == "hand":
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
