"""
stats/elo.py
============
Funções matemáticas puras para cálculo de rating ELO:
- Score esperado (probabilidade de vitória)
- K-factor dinâmico (com base em número de partidas disputadas e bônus humano)
- Cálculo de novos ratings para P1, P2 e Empate
"""

from typing import Tuple


def expected_score(rating_a: float, rating_b: float) -> float:
    """
    Calcula a probabilidade esperada de vitória do jogador A contra B.
    Formula: 1 / (1 + 10 ** ((rating_b - rating_a) / 400))
    """
    return 1.0 / (1.0 + 10.0 ** ((float(rating_b) - float(rating_a)) / 400.0))


calculate_expected_score = expected_score


def calculate_k_factor(
    matches_played: int = 0,
    is_human_p1: bool = False,
    winner_id: int = 0,
    base_k: int = 32,
) -> int:
    """
    Calcula o K-factor dinâmico para atualização de ELO.
    - Recompensa acelerada de ELO (K=48) quando o bot vence um jogador humano.
    - K dinâmico baseado no volume de partidas para estabilização de rating.
    """
    if is_human_p1 and winner_id == 2:
        return 48
    if matches_played < 30:
        return base_k
    elif matches_played < 100:
        return max(16, int(base_k * 0.75))
    return max(16, int(base_k * 0.5))


get_k_factor = calculate_k_factor


def calculate_elo_ratings(
    r1: float,
    r2: float,
    winner_id: int,
    k: float = 32,
) -> Tuple[int, int]:
    """
    Calcula novos ratings ELO para P1 e P2 a partir do resultado da partida:
      winner_id == 1: Vitória de P1 (s1=1.0, s2=0.0)
      winner_id == 2: Vitória de P2 (s1=0.0, s2=1.0)
      winner_id == 0 (ou outro): Empate (s1=0.5, s2=0.5)

    Retorna tupla (new_r1, new_r2) com valores inteiros arredondados.
    """
    e1 = expected_score(r1, r2)
    e2 = expected_score(r2, r1)

    if winner_id == 1:
        s1, s2 = 1.0, 0.0
    elif winner_id == 2:
        s1, s2 = 0.0, 1.0
    else:
        s1, s2 = 0.5, 0.5

    new_r1 = round(float(r1) + k * (s1 - e1))
    new_r2 = round(float(r2) + k * (s2 - e2))
    return new_r1, new_r2


calculate_new_ratings = calculate_elo_ratings
