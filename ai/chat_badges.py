"""
ai/chat_badges.py
=================
Formatação e emissão de avaliações táticas e badges estilo Xadrez (Stockfish / Chess.com)
para o chat in-game do Talishar.
"""

from typing import Tuple, Dict, Any
from ai.common import safe_int, safe_list

def evaluate_board_state(state: Dict[str, Any]) -> float:
    """
    Calcula o índice de avaliação da posição em tempo real (estilo Chess Eval +/-).
    Baseado no diferencial de pontos de vida e vantagem de cartas na mão.
    """
    if not isinstance(state, dict):
        return 0.0

    my_h = safe_int(state.get("playerHealth", state.get("yourHealth")), default=40)
    opp_h = safe_int(state.get("opponentHealth", state.get("theirHealth")), default=40)
    my_hand_cnt = len(safe_list(state.get("playerHand")))
    opp_hand_cnt = safe_int(state.get("opponentHandCount", state.get("theirHandCount")), default=4)

    # Diferencial de Vida (peso 0.4) e Vantagem de Cartas (peso 0.8)
    eval_score = ((my_h - opp_h) * 0.4) + ((my_hand_cnt - opp_hand_cnt) * 0.8)
    return round(eval_score, 1)

def classify_chess_move(score_val: float, has_go_again: bool = False, is_lethal: bool = False) -> Tuple[str, str]:
    """
    Classifica o lance de acordo com o score tático ou MCTS.
    Retorna (badge_text, hex_color).
    """
    if is_lethal or score_val >= 9.0:
        return "🟢 Brilhante (!!)", "#22c55e"
    elif score_val >= 5.0:
        return "🎯 Melhor Jogada (!)", "#38bdf8"
    elif has_go_again:
        return "⚡ Excelente", "#a855f7"
    else:
        return "🔵 Bom", "#60a5fa"

def format_attack_chat_message(
    turn_num: int,
    card_name: str,
    score_val: float,
    board_eval: float,
    mcts_sims: int,
    has_go_again: bool = False,
    is_ismcts: bool = False,
    is_lethal: bool = False
) -> Tuple[str, str]:
    """
    Gera a mensagem formatada para envio ao chat do Talishar com classificação de xadrez.
    Retorna (html_text, badge_color).
    """
    tier_badge, badge_color = classify_chess_move(score_val, has_go_again=has_go_again, is_lethal=is_lethal)
    eval_str = f"+{board_eval}" if board_eval > 0 else str(board_eval)
    engine_tag = "ISMCTS" if is_ismcts else "MCTS"
    
    msg = (
        f"<b>[Turno {turn_num}] {tier_badge}</b> → <b>{card_name}</b> "
        f"(Score: {score_val:.1f} | Eval: {eval_str} | {engine_tag}: {mcts_sims} sims)"
    )
    return msg, badge_color

def format_html_line(text: str, highlight: bool = False, bg_color: str = "#1e293b", text_color: str = "#38bdf8") -> str:
    """Gera a linha HTML para injeção no log de chat do Talishar."""
    if highlight:
        return f"<div style='background:{bg_color};border-left:4px solid {text_color};padding:3px 6px;margin:2px 0;border-radius:4px;color:{text_color};font-size:12px;'>{text}</div>"
    else:
        return f"<span style='color:{text_color};font-weight:600;'>{text}</span>"
