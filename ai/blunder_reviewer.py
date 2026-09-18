"""
ai/blunder_reviewer.py
======================
Módulo de Revisão Automática de Blunders e Análise Pós-Jogo de Trajetórias.

Examina a sequência de lances executados em uma partida e identifica momentos críticos
onde a vantagem da mesa oscilou drasticamente (blunders, imprecisões e viradas).
Gera pesos de prioridade para o Prioritized Experience Replay (PER), permitindo que a
Rede Neural foque o aprendizado nos erros mais graves e nas jogadas decisivas.
"""

from typing import List, Any, Tuple, Dict
import numpy as np


def review_trajectory_for_blunders(
    trajectory: List[Any],
    winner_player_id: int,
    bot_player_id: int = 1,
) -> Tuple[List[float], Dict[str, Any]]:
    """
    Analisa os passos de uma trajetória e calcula pesos de prioridade para PER.

    Critérios:
      - Blunder severo (delta eval <= -3.0): peso 3.5 (foco máximo de correção).
      - Imprecisão / Erro tático (delta eval <= -1.5): peso 2.0.
      - Lance brilhante / Virada (delta eval >= +3.0): peso 2.0.
      - Lances normais / estáveis: peso 1.0.
      - Lances finais de derrota (últimos 2 passos): peso mínimo 2.5 para isolar o erro final.

    Retorna:
      (weights, stats_summary)
    """
    n_steps = len(trajectory)
    if n_steps == 0:
        return [], {"blunders": 0, "inaccuracies": 0, "brilliants": 0, "total_steps": 0}

    weights = [1.0] * n_steps
    evals = []

    # Extrai o board_eval registrado em cada passo (se disponível)
    for step in trajectory:
        b_eval = step[3] if len(step) > 3 and step[3] is not None else 0.0
        try:
            evals.append(float(b_eval))
        except (ValueError, TypeError):
            evals.append(0.0)

    blunder_count = 0
    inaccuracy_count = 0
    brilliant_count = 0

    # Calcula deltas de avaliação entre passos sucessivos
    for i in range(n_steps - 1):
        step_pid = trajectory[i][2] if len(trajectory[i]) > 2 else bot_player_id
        is_my_step = (step_pid == bot_player_id)

        delta = evals[i + 1] - evals[i]
        # Se for o próprio bot jogando, queda no eval indica lance subótimo dele
        # Se for o oponente, aumento indica ganho do oponente (ponto de atenção)
        step_swing = delta if is_my_step else -delta

        from config.settings import SETTINGS
        blunder_thresh = getattr(SETTINGS, "blunder_threshold", -3.0)
        inacc_thresh = getattr(SETTINGS, "inaccuracy_threshold", -1.5)
        brill_thresh = getattr(SETTINGS, "brilliant_threshold", 3.0)

        if step_swing <= blunder_thresh:
            weights[i] = 3.5
            blunder_count += 1
        elif step_swing <= inacc_thresh:
            weights[i] = 2.0
            inaccuracy_count += 1
        elif step_swing >= brill_thresh:
            weights[i] = 2.0
            brilliant_count += 1

    # Se o bot perdeu a partida, os últimos passos contêm o erro letal
    if winner_player_id in (1, 2) and winner_player_id != bot_player_id:
        for idx in range(max(0, n_steps - 2), n_steps):
            weights[idx] = max(weights[idx], 2.5)

    stats = {
        "blunders": blunder_count,
        "inaccuracies": inaccuracy_count,
        "brilliants": brilliant_count,
        "total_steps": n_steps,
        "avg_weight": float(np.mean(weights)) if weights else 1.0,
    }

    return weights, stats
