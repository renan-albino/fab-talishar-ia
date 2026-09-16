"""
ai/policy/pitch_pruner.py
========================
Módulo de poda e seleção de cartas para pitch (Pitch Efficiency com ISMCTS).
"""

from typing import Optional, Tuple, Any


def select_best_pitch_card(engine: Any, state: dict) -> Optional[Tuple[int, str, int]]:
    """
    Seleciona a melhor carta da mão para dar pitch, priorizando eficiência de recursos
    (Azul 3 > Amarelo 2 > Vermelho 1) e penalizando estritamente peças reservadas do TurnPlan.
    """
    hand = state.get("playerHand", [])
    if not hand:
        return None

    turn_plan = engine.strategy.analyze_turn_plan(state)
    pitch_candidates = []
    for idx, c in enumerate(hand):
        info = engine.extract_card_info(c)
        c_clean_name = str(c.get("cardNumber") or info["name"]).lower()

        # Regra Oficial de FaB: Cartas sem pitch (pitch <= 0, ex: Gorganian Tome)
        # NUNCA podem ser dadas pitch! Ignora imediatamente para evitar loop no servidor.
        if int(info.get("pitch", 1)) <= 0 or "gorganian" in c_clean_name:
            continue

        c_action = info["action"] if info["action"] > 0 else 27
        score = engine.strategy.evaluate_pitch_card(
            info["name"], info["pitch"], info["cost"], info["power"], info["has_go_again"]
        )
        # Poda estrita de pitch: JAMAIS dar pitch em finalizador reservado do plano ofensivo
        is_reserved_finisher = (
            (info["name"] in turn_plan.reserved_card_names or c_clean_name in turn_plan.reserved_card_names)
            and info["pitch"] == 1
        )
        if is_reserved_finisher:
            score -= 100.0

        # Poda estrita: dar pitch em carta vermelha com alto poder (power >= 4)
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
    if len(pitch_candidates) > 1 and engine.num_mcts_sims > 0:
        opp_hand = state.get("opponentHand", [])
        opp_hand_count = len(opp_hand) if isinstance(opp_hand, list) and len(opp_hand) > 0 else int(
            state.get("opponentHandCount", state.get("theirHandCount", 0))
        )
        if opp_hand_count > 0:
            best_idx, _, ismcts_log = engine.ismcts.search_ismcts(
                state=state,
                legal_actions=pitch_candidates,
                num_simulations=engine.num_mcts_sims,
            )
            try:
                engine.ismcts_logger.log(
                    ismcts_log=ismcts_log,
                    turn=int(state.get("turnNo", state.get("turn", 0))),
                    phase="PITCH",
                )
            except Exception:
                pass
            chosen = pitch_candidates[best_idx]
            return chosen["idx"], chosen["name"], chosen["mode"]
        else:
            best_idx, _ = engine.mcts.search(
                state=state,
                legal_actions=pitch_candidates,
                num_simulations=engine.num_mcts_sims,
            )
            chosen = pitch_candidates[best_idx]
            return chosen["idx"], chosen["name"], chosen["mode"]

    pitch_candidates.sort(key=lambda x: x["score"], reverse=True)
    best = pitch_candidates[0]
    return best["idx"], best["name"], best["mode"]
