import pytest
from ai.chat_badges import evaluate_board_state, classify_chess_move, format_attack_chat_message, format_html_line
from ai.talishar_api import TalisharApiClient

def test_evaluate_board_state():
    state_ahead = {
        "playerHealth": 35,
        "opponentHealth": 15,
        "playerHand": [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}],
        "opponentHandCount": 1
    }
    # (35 - 15)*0.4 + (3 - 1)*0.8 = 8.0 + 1.6 = 9.6
    eval_ahead = evaluate_board_state(state_ahead)
    assert eval_ahead > 0
    assert eval_ahead == 9.6

    state_behind = {
        "playerHealth": 10,
        "opponentHealth": 30,
        "playerHand": [],
        "opponentHandCount": 4
    }
    eval_behind = evaluate_board_state(state_behind)
    assert eval_behind < 0

def test_classify_chess_move():
    badge, color = classify_chess_move(9.5)
    assert "Brilhante" in badge
    assert color == "#22c55e"

    badge_best, _ = classify_chess_move(6.0)
    assert "Melhor Jogada" in badge_best

    badge_ga, _ = classify_chess_move(3.0, has_go_again=True)
    assert "Excelente" in badge_ga

    badge_good, _ = classify_chess_move(2.0, has_go_again=False)
    assert "Bom" in badge_good

def test_format_attack_chat_message():
    msg, color = format_attack_chat_message(
        turn_num=3,
        card_name="zero_to_sixty_red",
        score_val=9.5,
        board_eval=5.2,
        mcts_sims=32,
        has_go_again=True,
        is_ismcts=True
    )
    assert "Turno 3" in msg
    assert "Brilhante" in msg
    assert "zero_to_sixty_red" in msg
    assert "ISMCTS: 32 sims" in msg

def test_talishar_api_client_init():
    client = TalisharApiClient(backend_url="http://custom:8080/game")
    assert client.backend_url == "http://custom:8080/game"
    assert client.session is not None
