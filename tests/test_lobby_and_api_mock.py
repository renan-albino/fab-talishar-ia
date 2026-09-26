"""
tests/test_lobby_and_api_mock.py
================================
Testes unitários abrangentes para TalisharApiClient (ai/talishar_api.py)
e lobby_manager (ai/bot_runtime/lobby_manager.py), utilizando unittest.mock
e pytest para isolamento total de rede, filesystem e processos.
"""

import os
import json
import pytest
from unittest.mock import patch, MagicMock
import requests

from ai.talishar_api import TalisharApiClient, DEFAULT_BACKEND_URL
from ai.bot_runtime import lobby_manager


class DummyBotClient:
    """Mock completo do cliente de bot para testar lobby_manager isoladamente."""

    def __init__(
        self,
        role: str = "host",
        room_id: str = "room_test_100",
        game_id: str = "9999",
        player_id: int = 1,
        auth_key: str = "auth_token_initial",
        player_name: str = "Kayo",
        deck_url: str = "kayo_blitz",
        deck_format: str = "blitz",
    ):
        self.role = role
        self.room_id = room_id
        self.game_id = game_id
        self.player_id = player_id
        self.auth_key = auth_key
        self.player_name = player_name
        self.deck_url = deck_url
        self.deck_format = deck_format
        self.chosen_turn_order = None

        self.session = MagicMock(spec=requests.Session)
        self.api = MagicMock(spec=TalisharApiClient)
        self.logs = []

        self.submit_sideboard = MagicMock(return_value={"status": "ok"})
        self.choose_first_player = MagicMock()
        self.wait_for_opponent_and_start = MagicMock(return_value=True)
        self.wait_in_lobby_and_start = MagicMock(return_value=True)
        self.get_card_meta = MagicMock(return_value={"class": "Brute"})

    def log(self, message: str):
        self.logs.append(str(message))


# ==============================================================================
# PARTE 1: TESTES PARA TalisharApiClient (ai/talishar_api.py)
# ==============================================================================

class TestTalisharApiClient:
    """Testes unitários para TalisharApiClient com mocks de rede."""

    def test_init_defaults_and_custom(self):
        # Default initialization
        client_default = TalisharApiClient()
        assert client_default.backend_url == DEFAULT_BACKEND_URL.rstrip("/")
        assert isinstance(client_default.session, requests.Session)

        # Custom backend URL com barra no final e sessão injetada
        mock_session = MagicMock(spec=requests.Session)
        client_custom = TalisharApiClient(backend_url="http://custom-host:9090/game/", session=mock_session)
        assert client_custom.backend_url == "http://custom-host:9090/game"
        assert client_custom.session is mock_session

    def test_create_game_success(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"gameName": "1001", "playerID": 1, "authKey": "host_key_abc"}
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(backend_url="http://test-server/game", session=mock_session)
        result = client.create_game("game_blitz_1", deck_format="blitz")

        assert result["gameName"] == "1001"
        assert result["playerID"] == 1
        assert result["authKey"] == "host_key_abc"
        mock_session.post.assert_called_once_with(
            "http://test-server/game/APIs/CreateGame.php",
            json={
                "gameName": "game_blitz_1",
                "format": "blitz",
                "isPrivate": 0,
                "gameType": 1,
                "aiDummy": 0
            },
            timeout=5.0
        )
        mock_response.raise_for_status.assert_called_once()

    def test_create_game_http_error(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        with pytest.raises(requests.HTTPError):
            client.create_game("broken_game")

    def test_join_game_success(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"gameName": "1001", "playerID": 2, "authKey": "guest_key_xyz"}
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(backend_url="http://test-server/game", session=mock_session)
        result = client.join_game("1001", deck_format="classic")

        assert result["playerID"] == 2
        assert result["authKey"] == "guest_key_xyz"
        mock_session.post.assert_called_once_with(
            "http://test-server/game/APIs/JoinGame.php",
            json={
                "gameName": "1001",
                "format": "classic",
                "passKey": ""
            },
            timeout=5.0
        )
        mock_response.raise_for_status.assert_called_once()

    def test_join_game_password_or_occupied_error(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden - Room Full")
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        with pytest.raises(requests.HTTPError):
            client.join_game("1001")

    def test_join_game_request_exception_timeout(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_session.post.side_effect = requests.Timeout("Connection timed out")

        client = TalisharApiClient(session=mock_session)
        with pytest.raises(requests.RequestException):
            client.join_game("1001")

    def test_get_lobby_refresh_success(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "opponentHero": "Dash, Inventor Extraordinary",
            "gameStatus": 2,
            "amIChoosingFirstPlayer": True
        }
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(backend_url="http://test-server/game", session=mock_session)
        data = client.get_lobby_refresh("1001", player_id=1, auth_key="auth_key_1")

        assert data["opponentHero"] == "Dash, Inventor Extraordinary"
        assert data["amIChoosingFirstPlayer"] is True
        mock_session.post.assert_called_once_with(
            "http://test-server/game/APIs/GetLobbyRefresh.php",
            json={"gameName": "1001", "playerID": 1, "authKey": "auth_key_1"},
            timeout=5
        )

    def test_get_lobby_refresh_non_200(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 502
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        data = client.get_lobby_refresh("1001", player_id=1, auth_key="auth_key_1")
        assert data == {}

    def test_choose_first_player_success(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(backend_url="http://test-server/game", session=mock_session)
        ok = client.choose_first_player("1001", player_id=1, auth_key="k1", action="Go First")

        assert ok is True
        mock_session.post.assert_called_once_with(
            "http://test-server/game/APIs/ChooseFirstPlayer.php",
            json={"gameName": "1001", "playerID": 1, "authKey": "k1", "action": "Go First"},
            timeout=5
        )

    def test_choose_first_player_server_error_flag(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "error": "Already decided"}
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        ok = client.choose_first_player("1001", player_id=1, auth_key="k1", action="Go Second")
        assert ok is False

    def test_choose_first_player_success_false(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False}
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        ok = client.choose_first_player("1001", player_id=1, auth_key="k1")
        assert ok is False

    def test_choose_first_player_non_json_fallback_true(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Not JSON")
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        ok = client.choose_first_player("1001", player_id=1, auth_key="k1")
        assert ok is True

    def test_choose_first_player_non_200_status(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 500
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        ok = client.choose_first_player("1001", player_id=1, auth_key="k1")
        assert ok is False

    def test_choose_first_player_exception_handled(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_session.post.side_effect = requests.RequestException("Network is down")

        client = TalisharApiClient(session=mock_session)
        ok = client.choose_first_player("1001", player_id=1, auth_key="k1")
        assert ok is False

    def test_submit_sideboard_success_json(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok", "hero": "Bravo"}
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(backend_url="http://test-server/game", session=mock_session)
        payload = {"gameName": "1001", "deck": ["card_1", "card_2"]}
        res = client.submit_sideboard(payload)

        assert res["status"] == "ok"
        assert res["hero"] == "Bravo"
        mock_session.post.assert_called_once_with(
            "http://test-server/game/APIs/SubmitSideboard.php",
            json=payload,
            timeout=5.0
        )

    def test_submit_sideboard_success_non_json_fallback(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Plain text response")
        mock_response.text = "Sideboard submitted successfully"
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        res = client.submit_sideboard({"gameName": "1001"})
        assert res == {"status": "ok", "raw": "Sideboard submitted successfully"}

    def test_submit_sideboard_error_status(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 400
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        res = client.submit_sideboard({"gameName": "1001"})
        assert res == {"status": "error", "code": 400}

    def test_get_next_turn_success(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = {"turn": 2, "activePlayer": 1, "actions": []}
        mock_session.get.return_value = mock_response

        client = TalisharApiClient(backend_url="http://test-server/game", session=mock_session)
        data = client.get_next_turn("1001", player_id=1, auth_key="auth_key_1", last_action=3)

        assert data["turn"] == 2
        mock_session.get.assert_called_once_with(
            "http://test-server/game/GetNextTurn.php",
            params={"gameName": "1001", "playerID": 1, "authKey": "auth_key_1", "lastAction": 3},
            timeout=5.0
        )

    def test_get_next_turn_non_200(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 503
        mock_session.get.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        data = client.get_next_turn("1001", player_id=1, auth_key="auth_key_1")
        assert data == {}

    def test_process_input_success(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_session.get.return_value = mock_response

        client = TalisharApiClient(backend_url="http://test-server/game", session=mock_session)
        ok = client.process_input(
            game_name="1001",
            player_id=1,
            auth_key="key",
            mode=1,
            card_id="c123",
            button_input="Play",
            chk_count=2,
            chk_input=["pitch_1", "pitch_2"],
            input_text="Pass"
        )
        assert ok is True
        mock_session.get.assert_called_once_with(
            "http://test-server/game/ProcessInput.php",
            params={
                "gameName": "1001",
                "playerID": 1,
                "authKey": "key",
                "mode": 1,
                "cardID": "c123",
                "buttonInput": "Play",
                "numMode": 0,
                "chkCount": 2,
                "inputText": "Pass",
                "chk0": "pitch_1",
                "chk1": "pitch_2"
            },
            timeout=5.0
        )

    def test_process_input_default_mode_when_zero_or_negative(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = "OK"
        mock_session.get.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        ok = client.process_input("1001", 1, "k", mode=0)
        assert ok is True
        assert mock_session.get.call_args[1]["params"]["mode"] == 99

        client.process_input("1001", 1, "k", mode=-5)
        assert mock_session.get.call_args[1]["params"]["mode"] == 99

    def test_process_input_php_errors_handled(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.text = "Fatal error: Uncaught Error: Call to a member function on null"
        mock_session.get.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        assert client.process_input("1001", 1, "k") is False

        mock_response.text = "Parse error: syntax error, unexpected token"
        assert client.process_input("1001", 1, "k") is False

    def test_process_input_exception_handled(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_session.get.side_effect = requests.RequestException("Timeout")

        client = TalisharApiClient(session=mock_session)
        assert client.process_input("1001", 1, "k") is False

    def test_append_game_log_success(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 200
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(backend_url="http://test-server/game", session=mock_session)
        ok = client.append_game_log("1001", "Turno 1: Ataque Brilhante")

        assert ok is True
        mock_session.post.assert_called_once_with(
            "http://test-server/game/APIs/AppendGameLog.php",
            json={"gameName": "1001", "message": "Turno 1: Ataque Brilhante"},
            timeout=5.0
        )

    def test_append_game_log_non_200_and_exception(self):
        mock_session = MagicMock(spec=requests.Session)
        mock_response = MagicMock(spec=requests.Response)
        mock_response.status_code = 500
        mock_session.post.return_value = mock_response

        client = TalisharApiClient(session=mock_session)
        assert client.append_game_log("1001", "badge") is False

        mock_session.post.side_effect = requests.RequestException("Connection broken")
        assert client.append_game_log("1001", "badge") is False


# ==============================================================================
# PARTE 2: TESTES PARA choose_first_player (ai/bot_runtime/lobby_manager.py)
# ==============================================================================

class TestLobbyManagerChooseFirstPlayer:
    """Testes para resolução de ordem de turno e integração com o learner."""

    @patch("ai.bot_runtime.lobby_manager.get_turn_order_learner")
    def test_choose_first_player_success(self, mock_get_learner):
        mock_learner = MagicMock()
        mock_learner.get_optimal_turn_order.return_value = "Go Second"
        mock_get_learner.return_value = mock_learner

        client = DummyBotClient(player_name="Kayo", game_id="2020", player_id=1, auth_key="auth_p1")
        client.api.choose_first_player.return_value = True

        lobby_manager.choose_first_player(client)

        assert client.chosen_turn_order == "Go Second"
        mock_learner.get_optimal_turn_order.assert_called_once_with("Kayo")
        client.api.choose_first_player.assert_called_once_with("2020", 1, "auth_p1", action="Go Second")
        assert any("[FIRST PLAYER]" in msg for msg in client.logs)

    @patch("ai.bot_runtime.lobby_manager.get_turn_order_learner")
    def test_choose_first_player_fallback_to_deck_url(self, mock_get_learner):
        mock_learner = MagicMock()
        mock_learner.get_optimal_turn_order.return_value = "Go First"
        mock_get_learner.return_value = mock_learner

        client = DummyBotClient(player_name="", deck_url="decks/rhinar.json")
        client.api.choose_first_player.return_value = True

        lobby_manager.choose_first_player(client)

        mock_learner.get_optimal_turn_order.assert_called_once_with("decks/rhinar.json")
        assert client.chosen_turn_order == "Go First"

    @patch("ai.bot_runtime.lobby_manager.get_turn_order_learner")
    def test_choose_first_player_api_failure(self, mock_get_learner):
        mock_learner = MagicMock()
        mock_learner.get_optimal_turn_order.return_value = "Go First"
        mock_get_learner.return_value = mock_learner

        client = DummyBotClient(player_name="Kayo")
        client.api.choose_first_player.return_value = False

        lobby_manager.choose_first_player(client)

        assert any("[ERRO FIRST PLAYER]" in msg for msg in client.logs)


# ==============================================================================
# PARTE 3: TESTES PARA get_opponent_info (ai/bot_runtime/lobby_manager.py)
# ==============================================================================

class TestLobbyManagerGetOpponentInfo:
    """Testes para consulta segura do herói e classe do oponente via GetLobbyRefresh."""

    def test_get_opponent_info_direct_opponent_hero(self):
        client = DummyBotClient(game_id="3030", player_id=1, auth_key="auth_key")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"opponentHero": "Bravo, Showstopper"}
        client.session.post.return_value = mock_resp
        client.get_card_meta.return_value = {"class": "Guardian"}

        hero, hero_class = lobby_manager.get_opponent_info(client)

        assert hero == "Bravo, Showstopper"
        assert hero_class == "guardian"
        client.get_card_meta.assert_called_once_with("Bravo, Showstopper")

    def test_get_opponent_info_from_player2_when_client_is_p1(self):
        client = DummyBotClient(game_id="3030", player_id=1, auth_key="auth_key")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "opponentHero": "",
            "player1": {"hero": "Kayo"},
            "player2": {"hero": "Dash, Inventor Extraordinary"}
        }
        client.session.post.return_value = mock_resp
        client.get_card_meta.return_value = {"class": "Mechanologist"}

        hero, hero_class = lobby_manager.get_opponent_info(client)

        assert hero == "Dash, Inventor Extraordinary"
        assert hero_class == "mechanologist"
        client.get_card_meta.assert_called_once_with("Dash, Inventor Extraordinary")

    def test_get_opponent_info_from_player1_when_client_is_p2(self):
        client = DummyBotClient(game_id="3030", player_id=2, auth_key="auth_key")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "opponentHero": "",
            "player1": {"hero": "Katsu, the Wanderer"},
            "player2": {"hero": "Iyslander"}
        }
        client.session.post.return_value = mock_resp
        client.get_card_meta.return_value = {"class": "Ninja"}

        hero, hero_class = lobby_manager.get_opponent_info(client)

        assert hero == "Katsu, the Wanderer"
        assert hero_class == "ninja"
        client.get_card_meta.assert_called_once_with("Katsu, the Wanderer")

    def test_get_opponent_info_no_hero_in_response(self):
        client = DummyBotClient()
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"opponentHero": "", "player1": {}, "player2": {}}
        client.session.post.return_value = mock_resp

        hero, hero_class = lobby_manager.get_opponent_info(client)
        assert hero == ""
        assert hero_class == ""

    def test_get_opponent_info_non_200_and_exception(self):
        client = DummyBotClient()
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 500
        client.session.post.return_value = mock_resp

        assert lobby_manager.get_opponent_info(client) == ("", "")

        client.session.post.side_effect = requests.RequestException("HTTP Failure")
        assert lobby_manager.get_opponent_info(client) == ("", "")


# ==============================================================================
# PARTE 4: TESTES PARA wait_in_lobby_and_start (ai/bot_runtime/lobby_manager.py)
# ==============================================================================

class TestLobbyManagerWaitInLobbyAndStart:
    """Testes para o fluxo de espera do Jogador 2 no lobby."""

    @patch("time.sleep", return_value=None)
    def test_wait_in_lobby_immediate_main_game_ready(self, _mock_sleep):
        client = DummyBotClient(game_id="4040", player_id=2)
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"isMainGameReady": True, "mySideboardSubmitted": True}
        client.session.post.return_value = mock_resp

        result = lobby_manager.wait_in_lobby_and_start(client)

        assert result is True
        client.submit_sideboard.assert_called_once()
        assert any("Partida #4040 iniciando..." in m for m in client.logs)

    @patch("time.sleep", return_value=None)
    def test_wait_in_lobby_game_started_flag(self, _mock_sleep):
        client = DummyBotClient(game_id="4041", player_id=2)
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"gameStarted": True, "mySideboardSubmitted": True}
        client.session.post.return_value = mock_resp

        result = lobby_manager.wait_in_lobby_and_start(client)
        assert result is True

    @patch("time.sleep", return_value=None)
    def test_wait_in_lobby_chooses_first_player_and_resubmits_sideboard(self, _mock_sleep):
        client = DummyBotClient(game_id="4042", player_id=2)

        resp1 = MagicMock(spec=requests.Response)
        resp1.status_code = 200
        resp1.json.return_value = {
            "amIChoosingFirstPlayer": True,
            "mySideboardSubmitted": True,
            "isMainGameReady": False
        }

        resp2 = MagicMock(spec=requests.Response)
        resp2.status_code = 200
        resp2.json.return_value = {
            "amIChoosingFirstPlayer": False,
            "mySideboardSubmitted": False,
            "isMainGameReady": False
        }

        resp3 = MagicMock(spec=requests.Response)
        resp3.status_code = 200
        resp3.json.return_value = {
            "amIChoosingFirstPlayer": False,
            "mySideboardSubmitted": True,
            "isMainGameReady": True
        }

        client.session.post.side_effect = [resp1, resp2, resp3]

        result = lobby_manager.wait_in_lobby_and_start(client)

        assert result is True
        client.choose_first_player.assert_called_once()
        # submit_sideboard chamado 1 vez no início + 1 vez no resp2 porque mySideboardSubmitted foi False
        assert client.submit_sideboard.call_count == 2

    @patch("time.sleep", return_value=None)
    def test_wait_in_lobby_gamestate_detected_on_disk(self, _mock_sleep, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        client = DummyBotClient(game_id="5050", player_id=2)

        # Cria gamestate.txt no caminho esperado Talishar/Games/5050/gamestate.txt
        gs_dir = tmp_path / "Talishar" / "Games" / "5050"
        gs_dir.mkdir(parents=True, exist_ok=True)
        gs_file = gs_dir / "gamestate.txt"
        gs_file.write_text("turn=1&active=1\n" + "x" * 250)

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"isMainGameReady": False, "gameStarted": False, "mySideboardSubmitted": True}
        client.session.post.return_value = mock_resp

        result = lobby_manager.wait_in_lobby_and_start(client)

        assert result is True
        assert any("Gamestate detectado" in m for m in client.logs)

    @patch("time.sleep", return_value=None)
    def test_wait_in_lobby_alt_gamestate_path(self, _mock_sleep, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        client = DummyBotClient(game_id="5051", player_id=2)

        # Cria gamestate.txt no caminho alternativo Games/5051/gamestate.txt
        gs_dir = tmp_path / "Games" / "5051"
        gs_dir.mkdir(parents=True, exist_ok=True)
        gs_file = gs_dir / "gamestate.txt"
        gs_file.write_text("turn=1\n" + "x" * 250)

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"isMainGameReady": False, "gameStarted": False}
        client.session.post.return_value = mock_resp

        result = lobby_manager.wait_in_lobby_and_start(client)
        assert result is True

    @patch("time.sleep", return_value=None)
    def test_wait_in_lobby_exception_in_loop_recovers(self, _mock_sleep):
        client = DummyBotClient(game_id="4043", player_id=2)

        resp_ok = MagicMock(spec=requests.Response)
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"isMainGameReady": True}

        client.session.post.side_effect = [requests.RequestException("Temporary glitch"), resp_ok]

        result = lobby_manager.wait_in_lobby_and_start(client)

        assert result is True
        assert any("[LOBBY AVISO]" in m for m in client.logs)

    @patch("time.sleep", return_value=None)
    @patch("time.time")
    def test_wait_in_lobby_timeout(self, mock_time, _mock_sleep):
        # Simula tempo inicial 0.0 e depois ultrapassando os 600 segundos
        mock_time.side_effect = [0.0, 605.0]

        client = DummyBotClient(game_id="4044", player_id=2)
        result = lobby_manager.wait_in_lobby_and_start(client)

        assert result is False
        assert any("[LOBBY TIMEOUT]" in m for m in client.logs)


# ==============================================================================
# PARTE 5: TESTES PARA wait_for_opponent_and_start (ai/bot_runtime/lobby_manager.py)
# ==============================================================================

class TestLobbyManagerWaitForOpponentAndStart:
    """Testes para o fluxo do Host aguardando Jogador 2."""

    @patch("time.sleep", return_value=None)
    def test_wait_for_opponent_p2_ready_file_and_game_ready(self, _mock_sleep, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        ready_flag = tmp_path / "logs" / "test_room_p2_ready.txt"
        ready_flag.write_text("ready")

        client = DummyBotClient(room_id="test_room", game_id="6060", player_id=1)
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"isMainGameReady": True}
        client.session.post.return_value = mock_resp

        result = lobby_manager.wait_for_opponent_and_start(client)

        assert result is True
        client.submit_sideboard.assert_called_once()
        assert any("Partida #6060 pronta para começar!" in m for m in client.logs)

    @patch("time.sleep", return_value=None)
    def test_wait_for_opponent_hero_present_and_choose_first_player(self, _mock_sleep):
        client = DummyBotClient(room_id="room_hero", game_id="6061", player_id=1)

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "opponentHero": "Dorinthea",
            "amIChoosingFirstPlayer": True,
            "gameStarted": True
        }
        client.session.post.return_value = mock_resp

        result = lobby_manager.wait_for_opponent_and_start(client)

        assert result is True
        client.choose_first_player.assert_called_once()
        client.submit_sideboard.assert_called_once()
        assert any("Bot venceu o dado!" in m for m in client.logs)

    @patch("time.sleep", return_value=None)
    def test_wait_for_opponent_game_status_gte_2_and_gamestate_on_disk(self, _mock_sleep, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        gs_dir = tmp_path / "Talishar" / "Games" / "6062"
        gs_dir.mkdir(parents=True, exist_ok=True)
        (gs_dir / "gamestate.txt").write_text("state=active\n" + "x" * 250)

        client = DummyBotClient(room_id="room_status", game_id="6062", player_id=1)
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"gameStatus": 2, "isMainGameReady": False, "gameStarted": False}
        client.session.post.return_value = mock_resp

        result = lobby_manager.wait_for_opponent_and_start(client)

        assert result is True
        assert any("Partida #6062 iniciada (gamestate detectado)." in m for m in client.logs)

    @patch("time.sleep", return_value=None)
    def test_wait_for_opponent_alt_gamestate_path(self, _mock_sleep, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        gs_dir = tmp_path / "Games" / "6063"
        gs_dir.mkdir(parents=True, exist_ok=True)
        (gs_dir / "gamestate.txt").write_text("state=active\n" + "x" * 250)

        client = DummyBotClient(room_id="room_status2", game_id="6063", player_id=1)
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"gameStatus": 3}
        client.session.post.return_value = mock_resp

        result = lobby_manager.wait_for_opponent_and_start(client)
        assert result is True

    @patch("time.sleep", return_value=None)
    def test_wait_for_opponent_exception_ignored_and_recovers(self, _mock_sleep):
        client = DummyBotClient(room_id="room_exc", game_id="6064", player_id=1)

        resp_ok = MagicMock(spec=requests.Response)
        resp_ok.status_code = 200
        resp_ok.json.return_value = {"opponentHero": "Rhinar", "isMainGameReady": True}

        client.session.post.side_effect = [requests.RequestException("Socket drop"), resp_ok]

        result = lobby_manager.wait_for_opponent_and_start(client)
        assert result is True

    @patch("time.sleep", return_value=None)
    @patch("time.time")
    def test_wait_for_opponent_timeout(self, mock_time, _mock_sleep):
        mock_time.side_effect = [0.0, 305.0]

        client = DummyBotClient(room_id="room_timeout", game_id="6065", player_id=1)
        result = lobby_manager.wait_for_opponent_and_start(client)

        assert result is False
        assert any("[TIMEOUT]" in m for m in client.logs)


# ==============================================================================
# PARTE 6: TESTES PARA setup_game_room (HOST)
# ==============================================================================

class TestLobbyManagerSetupGameRoomHost:
    """Testes para setup_game_room quando o bot atua como Host (P1)."""

    def test_setup_host_success_direct_deck_url(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)

        # Cria arquivo de deck direto
        deck_file = tmp_path / "my_deck.json"
        deck_file.write_text(json.dumps({"format": "cc", "hero": "Bravo"}))

        client = DummyBotClient(role="host", room_id="host_room_1", deck_url=str(deck_file))
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"gameName": "7001", "playerID": 1, "authKey": "secret_key_123"}'
        mock_resp.json.return_value = {"gameName": "7001", "playerID": 1, "authKey": "secret_key_123"}
        client.session.post.return_value = mock_resp
        client.wait_for_opponent_and_start.return_value = True

        result = lobby_manager.setup_game_room(client)

        assert result is True
        assert client.game_id == "7001"
        assert client.player_id == 1
        assert client.auth_key == "secret_key_123"
        assert client.deck_format == "cc"

        # Verifica criação do arquivo de controle em logs/
        game_id_file = tmp_path / "logs" / "host_room_1_game_id.txt"
        assert game_id_file.exists()
        assert game_id_file.read_text() == "7001"
        client.wait_for_opponent_and_start.assert_called_once()

    def test_setup_host_success_from_decks_folder(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "decks").mkdir(exist_ok=True)

        deck_file = tmp_path / "decks" / "dash_blitz.json"
        deck_file.write_text(json.dumps({"format": "blitz", "hero": "Dash"}))

        client = DummyBotClient(role="host", room_id="host_room_2", deck_url="dash_blitz")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"gameName": "7002", "playerID": 1, "authKey": "key_7002"}'
        mock_resp.json.return_value = {"gameName": "7002", "playerID": 1, "authKey": "key_7002"}
        client.session.post.return_value = mock_resp

        result = lobby_manager.setup_game_room(client)

        assert result is True
        assert client.game_id == "7002"
        assert client.deck_format == "blitz"

    def test_setup_host_success_from_talishar_deck(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "Talishar").mkdir(exist_ok=True)

        deck_file = tmp_path / "Talishar" / "deck.json"
        deck_file.write_text(json.dumps({"format": "commoner", "hero": "Iyslander"}))

        client = DummyBotClient(role="host", room_id="host_room_3", deck_url="")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"gameName": "7003", "playerID": 1, "authKey": "key_7003"}'
        mock_resp.json.return_value = {"gameName": "7003", "playerID": 1, "authKey": "key_7003"}
        client.session.post.return_value = mock_resp

        result = lobby_manager.setup_game_room(client)

        assert result is True
        assert client.game_id == "7003"
        assert client.deck_format == "commoner"

    def test_setup_host_corrupted_deck_file_fallback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)

        broken_file = tmp_path / "corrupted_deck.json"
        broken_file.write_text("{invalid json file...")

        client = DummyBotClient(role="host", room_id="host_room_4", deck_url=str(broken_file))
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"gameName": "7004", "playerID": 1, "authKey": "key_7004"}'
        mock_resp.json.return_value = {"gameName": "7004", "playerID": 1, "authKey": "key_7004"}
        client.session.post.return_value = mock_resp

        result = lobby_manager.setup_game_room(client)

        assert result is True
        # Verifica que enviou payload com deck=None sem crashar
        sent_payload = client.session.post.call_args[1]["json"]
        assert sent_payload["deck"] is None

    def test_setup_host_server_non_json_response(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)

        client = DummyBotClient(role="host", room_id="host_bad_json")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = "<html>502 Bad Gateway</html>"
        mock_resp.json.side_effect = ValueError("Not JSON")
        client.session.post.return_value = mock_resp

        result = lobby_manager.setup_game_room(client)

        assert result is False
        assert any("[ERRO DE JSON]" in m for m in client.logs)

    def test_setup_host_server_error_field(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)

        client = DummyBotClient(role="host", room_id="host_err")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"error": "Too many open rooms"}'
        mock_resp.json.return_value = {"error": "Too many open rooms"}
        client.session.post.return_value = mock_resp

        result = lobby_manager.setup_game_room(client)

        assert result is False
        assert any("[ERRO AO CRIAR SALA] Too many open rooms" in m for m in client.logs)

    def test_setup_host_request_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)

        client = DummyBotClient(role="host", room_id="host_exc")
        client.session.post.side_effect = requests.RequestException("Connection timeout")

        result = lobby_manager.setup_game_room(client)

        assert result is False
        assert any("[ERRO DE CREATE]" in m for m in client.logs)


# ==============================================================================
# PARTE 7: TESTES PARA setup_game_room (GUEST / JOIN)
# ==============================================================================

class TestLobbyManagerSetupGameRoomJoin:
    """Testes para setup_game_room quando o bot entra como Jogador 2 (Join)."""

    def test_setup_join_existing_game_id_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(exist_ok=True)
        (logs_dir / "guest_room_1_game_id.txt").write_text("8001")

        client = DummyBotClient(role="join", room_id="guest_room_1")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"playerID": 2, "authKey": "guest_auth_8001"}'
        mock_resp.json.return_value = {"playerID": 2, "authKey": "guest_auth_8001"}
        client.session.post.return_value = mock_resp
        client.wait_in_lobby_and_start.return_value = True

        result = lobby_manager.setup_game_room(client)

        assert result is True
        assert client.game_id == "8001"
        assert client.player_id == 2
        assert client.auth_key == "guest_auth_8001"

        # Verifica criação do arquivo _p2_ready.txt
        ready_file = logs_dir / "guest_room_1_p2_ready.txt"
        assert ready_file.exists()
        assert ready_file.read_text() == "ready"
        client.wait_in_lobby_and_start.assert_called_once()

    def test_setup_join_numeric_room_id(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)

        client = DummyBotClient(role="join", room_id="8002")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"playerID": 2, "authKey": "guest_auth_8002"}'
        mock_resp.json.return_value = {"playerID": 2, "authKey": "guest_auth_8002"}
        client.session.post.return_value = mock_resp

        result = lobby_manager.setup_game_room(client)

        assert result is True
        assert client.game_id == "8002"

    def test_setup_join_waits_for_host_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(exist_ok=True)

        client = DummyBotClient(role="join", room_id="delayed_room")

        # Mock time.sleep para criar o arquivo durante a espera
        def mock_sleep_action(seconds):
            (logs_dir / "delayed_room_game_id.txt").write_text("8003")

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"playerID": 2, "authKey": "auth_8003"}'
        mock_resp.json.return_value = {"playerID": 2, "authKey": "auth_8003"}
        client.session.post.return_value = mock_resp

        with patch("time.sleep", side_effect=mock_sleep_action):
            result = lobby_manager.setup_game_room(client)

        assert result is True
        assert client.game_id == "8003"

    @patch("time.sleep", return_value=None)
    def test_setup_join_timeout_waiting_for_host_file(self, _mock_sleep, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)

        client = DummyBotClient(role="join", room_id="never_created_room")
        result = lobby_manager.setup_game_room(client)

        assert result is False
        assert any("[ERRO JOIN] Timeout" in m for m in client.logs)

    def test_setup_join_deck_loading_variations(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir(exist_ok=True)
        (logs_dir / "deck_var_room_game_id.txt").write_text("8004")

        # 1. Deck direto
        deck1 = tmp_path / "direct.json"
        deck1.write_text(json.dumps({"format": "silver"}))
        client1 = DummyBotClient(role="join", room_id="deck_var_room", deck_url=str(deck1))

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"playerID": 2, "authKey": "k"}'
        mock_resp.json.return_value = {"playerID": 2, "authKey": "k"}
        client1.session.post.return_value = mock_resp

        assert lobby_manager.setup_game_room(client1) is True
        assert client1.deck_format == "silver"

        # 2. Deck em decks/<name>.json
        (tmp_path / "decks").mkdir(exist_ok=True)
        (tmp_path / "decks" / "in_decks.json").write_text(json.dumps({"format": "ll"}))
        client2 = DummyBotClient(role="join", room_id="deck_var_room", deck_url="in_decks")
        client2.session.post.return_value = mock_resp
        assert lobby_manager.setup_game_room(client2) is True
        assert client2.deck_format == "ll"

        # 3. Deck em Talishar/deck.json
        (tmp_path / "Talishar").mkdir(exist_ok=True)
        (tmp_path / "Talishar" / "deck.json").write_text(json.dumps({"format": "custom_format"}))
        client3 = DummyBotClient(role="join", room_id="deck_var_room", deck_url="")
        client3.session.post.return_value = mock_resp
        assert lobby_manager.setup_game_room(client3) is True
        assert client3.deck_format == "custom_format"

    def test_setup_join_corrupted_deck_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "logs" / "corrupt_room_game_id.txt").write_text("8005")

        bad_deck = tmp_path / "bad.json"
        bad_deck.write_text("bad json content")

        client = DummyBotClient(role="join", room_id="corrupt_room", deck_url=str(bad_deck))
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"playerID": 2, "authKey": "k"}'
        mock_resp.json.return_value = {"playerID": 2, "authKey": "k"}
        client.session.post.return_value = mock_resp

        assert lobby_manager.setup_game_room(client) is True

    def test_setup_join_server_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "logs" / "err_room_game_id.txt").write_text("8006")

        client = DummyBotClient(role="join", room_id="err_room")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"error": "Game password incorrect"}'
        mock_resp.json.return_value = {"error": "Game password incorrect"}
        client.session.post.return_value = mock_resp

        result = lobby_manager.setup_game_room(client)

        assert result is False
        assert any("[ERRO AO ENTRAR NA SALA] Game password incorrect" in m for m in client.logs)

    def test_setup_join_recovers_auth_key_from_game_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "logs" / "gamefile_room_game_id.txt").write_text("8007")

        # Cria Talishar/Games/8007/GameFile.txt com token na linha 9 (índice 8)
        gf_dir = tmp_path / "Talishar" / "Games" / "8007"
        gf_dir.mkdir(parents=True, exist_ok=True)
        lines = [
            "line0", "line1", "line2", "line3", "line4",
            "line5", "line6", "line7", "recovered_secret_auth_token_999", "line9"
        ]
        (gf_dir / "GameFile.txt").write_text("\n".join(lines))

        client = DummyBotClient(role="join", room_id="gamefile_room")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        # authKey vazia na resposta para forçar busca no GameFile.txt
        mock_resp.text = '{"playerID": 2, "authKey": ""}'
        mock_resp.json.return_value = {"playerID": 2, "authKey": ""}
        client.session.post.return_value = mock_resp

        result = lobby_manager.setup_game_room(client)

        assert result is True
        assert client.auth_key == "recovered_secret_auth_token_999"

    def test_setup_join_game_file_too_short(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "logs" / "short_gf_room_game_id.txt").write_text("999988")

        gf_dir = tmp_path / "Talishar" / "Games" / "999988"
        gf_dir.mkdir(parents=True, exist_ok=True)
        (gf_dir / "GameFile.txt").write_text("line0\nline1")

        client = DummyBotClient(role="join", room_id="short_gf_room")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"playerID": 2, "authKey": ""}'
        mock_resp.json.return_value = {"playerID": 2, "authKey": ""}
        client.session.post.return_value = mock_resp

        result = lobby_manager.setup_game_room(client)

        assert result is True
        assert client.auth_key == ""

    def test_setup_join_request_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "logs" / "exc_room_game_id.txt").write_text("8009")

        client = DummyBotClient(role="join", room_id="exc_room")
        client.session.post.side_effect = requests.RequestException("Join dropped")

        result = lobby_manager.setup_game_room(client)

        assert result is False
        assert any("[ERRO DE JOIN]" in m for m in client.logs)

    def test_setup_join_corrupted_json_in_decks_and_talishar(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "decks").mkdir(exist_ok=True)
        (tmp_path / "Talishar").mkdir(exist_ok=True)

        # Corrompe decks/bad_sub.json
        (tmp_path / "decks" / "bad_sub.json").write_text("not-json")
        (tmp_path / "logs" / "bad_deck_room_game_id.txt").write_text("8010")

        client = DummyBotClient(role="join", room_id="bad_deck_room", deck_url="bad_sub")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"playerID": 2, "authKey": "k"}'
        mock_resp.json.return_value = {"playerID": 2, "authKey": "k"}
        client.session.post.return_value = mock_resp

        assert lobby_manager.setup_game_room(client) is True

        # Corrompe Talishar/deck.json
        (tmp_path / "Talishar" / "deck.json").write_text("not-json")
        client2 = DummyBotClient(role="join", room_id="bad_deck_room", deck_url="")
        client2.session.post.return_value = mock_resp

        assert lobby_manager.setup_game_room(client2) is True

    def test_setup_host_corrupted_json_in_decks_and_talishar(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "decks").mkdir(exist_ok=True)
        (tmp_path / "Talishar").mkdir(exist_ok=True)

        # Corrompe decks/bad_host.json
        (tmp_path / "decks" / "bad_host.json").write_text("not-json")
        client = DummyBotClient(role="host", room_id="host_bad_decks", deck_url="bad_host")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"gameName": "7010", "playerID": 1, "authKey": "k"}'
        mock_resp.json.return_value = {"gameName": "7010", "playerID": 1, "authKey": "k"}
        client.session.post.return_value = mock_resp

        assert lobby_manager.setup_game_room(client) is True

        # Corrompe Talishar/deck.json
        (tmp_path / "Talishar" / "deck.json").write_text("not-json")
        client2 = DummyBotClient(role="host", room_id="host_bad_talishar", deck_url="")
        client2.session.post.return_value = mock_resp

        assert lobby_manager.setup_game_room(client2) is True

    def test_setup_join_game_file_read_exception(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        (tmp_path / "logs").mkdir(exist_ok=True)
        (tmp_path / "logs" / "err_gf_room_game_id.txt").write_text("8011")

        gf_dir = tmp_path / "Talishar" / "Games" / "8011"
        gf_dir.mkdir(parents=True, exist_ok=True)
        gf_file = gf_dir / "GameFile.txt"
        gf_file.write_text("something")

        client = DummyBotClient(role="join", room_id="err_gf_room")
        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = '{"playerID": 2, "authKey": ""}'
        mock_resp.json.return_value = {"playerID": 2, "authKey": ""}
        client.session.post.return_value = mock_resp

        # Simula erro de leitura ao abrir o arquivo
        real_open = open
        def mock_broken_open(path, *args, **kwargs):
            if "GameFile.txt" in str(path):
                raise OSError("Disk I/O Error")
            return real_open(path, *args, **kwargs)

        with patch("builtins.open", side_effect=mock_broken_open):
            result = lobby_manager.setup_game_room(client)

        assert result is True
        assert client.auth_key == ""


# ==============================================================================
# PARTE 8: TESTE DE FALLBACK DE IMPORT EM ai/talishar_api.py
# ==============================================================================

def test_default_backend_url_import_fallback():
    """Testa fallback de DEFAULT_BACKEND_URL quando config.settings falha."""
    import sys
    import importlib
    import ai.talishar_api as api_module

    with patch.dict(sys.modules, {"config.settings": None}):
        importlib.reload(api_module)
        assert api_module.DEFAULT_BACKEND_URL == "http://localhost:8080/game"

    # Restaura módulo com reload
    importlib.reload(api_module)

