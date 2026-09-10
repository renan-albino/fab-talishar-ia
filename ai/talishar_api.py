"""
ai/talishar_api.py
==================
Cliente HTTP para comunicação com as APIs REST do motor de jogo Talishar (PHP / Apache).
Encapsula criação de partidas, lobby, sideboard, polling de turnos e envio de ações.
"""

import requests
from typing import Dict, Any, Optional, List
from ai.logger import get_logger

logger = get_logger("talishar_api")

try:
    from config.settings import SETTINGS
    DEFAULT_BACKEND_URL = SETTINGS.talishar_backend_url
except Exception:
    DEFAULT_BACKEND_URL = "http://localhost:8080/game"


class TalisharApiClient:
    """Cliente HTTP dedicado para interagir com o backend do Talishar."""

    def __init__(self, backend_url: str = None, session: Optional[requests.Session] = None):
        self.backend_url = (backend_url or DEFAULT_BACKEND_URL).rstrip("/")
        self.session = session or requests.Session()

    def create_game(self, game_name: str, deck_format: str = "blitz") -> Dict[str, Any]:
        """Cria uma nova sala de jogo no Talishar."""
        url = f"{self.backend_url}/APIs/CreateGame.php"
        payload = {
            "gameName": game_name,
            "format": deck_format,
            "isPrivate": 0,
            "gameType": 1,
            "aiDummy": 0
        }
        res = self.session.post(url, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()

    def join_game(self, game_name: str, deck_format: str = "blitz") -> Dict[str, Any]:
        """Entra como Jogador 2 em uma sala existente."""
        url = f"{self.backend_url}/APIs/JoinGame.php"
        payload = {
            "gameName": game_name,
            "format": deck_format,
            "passKey": ""
        }
        res = self.session.post(url, json=payload, timeout=10)
        res.raise_for_status()
        return res.json()

    def get_lobby_refresh(self, game_name: str, player_id: int, auth_key: str) -> Dict[str, Any]:
        """Consulta o estado do lobby para verificar se o oponente já entrou."""
        url = f"{self.backend_url}/APIs/GetLobbyRefresh.php"
        payload = {
            "gameName": game_name,
            "playerID": player_id,
            "authKey": auth_key
        }
        res = self.session.post(url, json=payload, timeout=5)
        if res.status_code == 200:
            return res.json()
        return {}

    def choose_first_player(self, game_name: str, player_id: int, auth_key: str, action: str = "Go First") -> bool:
        """Envia a decisão de ordem de turno ("Go First" / "Go Second")."""
        url = f"{self.backend_url}/APIs/ChooseFirstPlayer.php"
        payload = {
            "gameName": game_name,
            "playerID": player_id,
            "authKey": auth_key,
            "action": action
        }
        try:
            res = self.session.post(url, json=payload, timeout=5)
            if res.status_code == 200:
                try:
                    data = res.json()
                    return bool(data.get("success", False)) and not bool(data.get("error"))
                except Exception:
                    return True
            return False
        except Exception as e:
            logger.warning(f"Erro em choose_first_player: {e}")
            return False

    def submit_sideboard(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Submete herói, equipamentos, armas e deck configurados."""
        url = f"{self.backend_url}/APIs/SubmitSideboard.php"
        res = self.session.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            try:
                return res.json()
            except Exception:
                return {"status": "ok", "raw": res.text}
        return {"status": "error", "code": res.status_code}

    def get_next_turn(self, game_name: str, player_id: int, auth_key: str, last_action: int = 0) -> Dict[str, Any]:
        """Consulta o estado atual do jogo via polling rápido."""
        url = f"{self.backend_url}/GetNextTurn.php"
        params = {
            "gameName": game_name,
            "playerID": player_id,
            "authKey": auth_key,
            "lastAction": last_action
        }
        res = self.session.get(url, params=params, timeout=5)
        if res.status_code == 200:
            return res.json()
        return {}

    def process_input(
        self,
        game_name: str,
        player_id: int,
        auth_key: str,
        mode: int = 99,
        card_id: str = "",
        button_input: str = "",
        chk_count: int = 0,
        chk_input: Optional[List[Any]] = None,
        input_text: str = ""
    ) -> bool:
        """Executa uma ação de jogo via ProcessInput.php."""
        if not mode or mode <= 0:
            mode = 99

        params = {
            "gameName": game_name,
            "playerID": player_id,
            "authKey": auth_key,
            "mode": mode,
            "cardID": card_id,
            "buttonInput": button_input,
            "numMode": 0,
            "chkCount": chk_count,
            "inputText": input_text
        }
        if chk_input:
            for idx, item in enumerate(chk_input):
                params[f"chk{idx}"] = item

        try:
            url = f"{self.backend_url}/ProcessInput.php"
            res = self.session.get(url, params=params, timeout=5)
            if "Fatal error" in res.text or "Parse error" in res.text:
                logger.warning(f"Erro PHP no backend: {res.text[:200].strip()}")
                return False
            return res.status_code == 200
        except Exception as e:
            logger.warning(f"Erro ao enviar ação: {e}")
            return False

    def append_game_log(self, game_name: str, message: str) -> bool:
        """Injeta uma linha ou badge de avaliação no chat da partida."""
        url = f"{self.backend_url}/APIs/AppendGameLog.php"
        try:
            res = self.session.post(
                url,
                json={"gameName": game_name, "message": message},
                timeout=2
            )
            return res.status_code == 200
        except Exception:
            return False
