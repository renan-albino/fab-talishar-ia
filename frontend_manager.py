import os
import subprocess
import requests
import time
import json
import uuid
from typing import Dict, Any, Optional

BACKEND_URL = "http://localhost:8080/game"
FRONTEND_URL = "http://localhost:3000"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_BIN = os.path.join(BASE_DIR, "venv", "bin", "python")

def is_backend_running() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/APIs/GetGameList.php", timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def is_frontend_running() -> bool:
    try:
        r = requests.get(FRONTEND_URL, timeout=2)
        return r.status_code == 200
    except Exception:
        return False

def start_backend() -> bool:
    try:
        talishar_dir = os.path.join(BASE_DIR, "Talishar")
        cmd = "docker compose" if subprocess.run(["which", "docker-compose"], capture_output=True).returncode != 0 else "docker-compose"
        subprocess.run(["bash", "-c", f"cd {talishar_dir} && ln -sfn ../decks decks && {cmd} up -d"], check=True)
        time.sleep(3)
        return is_backend_running()
    except Exception as e:
        print(f"Erro ao iniciar backend: {e}")
        return False

def start_frontend() -> bool:
    if is_frontend_running():
        return True
    try:
        logs_dir = os.path.join(BASE_DIR, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        log_f = open(os.path.join(logs_dir, "frontend.log"), "a")
        subprocess.Popen(
            ["npx", "vite", "--port", "3000", "--host"],
            cwd=os.path.join(BASE_DIR, "Talishar-FE"),
            stdout=log_f,
            stderr=log_f,
            start_new_session=True
        )
        for _ in range(12):
            time.sleep(1)
            if is_frontend_running():
                return True
        return is_frontend_running()
    except Exception as e:
        print(f"Erro ao iniciar frontend: {e}")
import threading

_watcher_thread = None
_active_bot_procs = {}

def _ai_watcher_loop():
    games_dir = os.path.join(BASE_DIR, "Talishar", "Games")
    while True:
        try:
            if os.path.exists(games_dir):
                for g_id in os.listdir(games_dir):
                    g_path = os.path.join(games_dir, g_id)
                    if not os.path.isdir(g_path):
                        continue
                    flag_file = os.path.join(g_path, "p2_bot_needed.txt")
                    if os.path.exists(flag_file):
                        bot_deck = "betsy"
                        try:
                            with open(flag_file, "r") as ff:
                                bot_deck = ff.read().strip() or "betsy"
                            os.remove(flag_file)
                        except Exception:
                            continue

                        logs_dir = os.path.join(BASE_DIR, "logs")
                        os.makedirs(logs_dir, exist_ok=True)
                        bot_log_path = os.path.join(logs_dir, f"Human_vs_Bot_{g_id}.log")
                        out_f = open(bot_log_path, "a")
                        proc = subprocess.Popen(
                            [
                                PYTHON_BIN,
                                os.path.join(BASE_DIR, "bot_client.py"),
                                "--room", str(g_id),
                                "--deck", f"decks/{bot_deck}.json",
                                "--role", "join",
                                "--name", "AIMaster_Bot"
                            ],
                            cwd=BASE_DIR,
                            stdout=out_f,
                            stderr=out_f,
                            start_new_session=True
                        )
                        _active_bot_procs[str(g_id)] = proc
        except Exception:
            pass
        time.sleep(0.3)

def ensure_ai_watcher_running():
    global _watcher_thread
    if _watcher_thread is None or not _watcher_thread.is_alive():
        _watcher_thread = threading.Thread(target=_ai_watcher_loop, daemon=True)
        _watcher_thread.start()

ensure_ai_watcher_running()

def stop_frontend() -> bool:
    try:
        subprocess.run(["pkill", "-f", "vite.*3000"], check=False)
        time.sleep(1)
        return not is_frontend_running()
    except Exception:
        return False

def create_human_vs_bot_match(
    player_deck_slug: str,
    bot_deck_slug: str,
    format_code: str = "cc"
) -> Dict[str, Any]:
    """
    Cria uma partida no backend do Talishar para o jogador humano (Player 1)
    e inicializa o bot inteligente (bot_client.py) conectado como Player 2.
    """
    if not is_backend_running():
        start_backend()
    if not is_frontend_running():
        start_frontend()

    # 1. Cria a sala no Talishar para o Player 1
    create_payload = {
        "format": format_code.lower(),
        "visibility": "private",
        "fabdb": player_deck_slug,
        "gameDescription": "Humano vs AI Master"
    }

    try:
        resp = requests.post(
            f"{BACKEND_URL}/APIs/CreateGame.php",
            json=create_payload,
            headers={"Content-Type": "application/json"},
            timeout=5
        )
        data = resp.json()
    except Exception as e:
        return {"success": False, "error": f"Falha na comunicacao com o backend Talishar: {e}"}

    if "error" in data:
        return {"success": False, "error": data["error"]}

    game_name = str(data.get("gameName", ""))
    auth_key = str(data.get("authKey", ""))

    if not game_name:
        return {"success": False, "error": "Nome do jogo invalido retornado pelo Talishar."}

    # 2. Conecta o Bot como Player 2 na mesma sala em background
    logs_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    bot_log_path = os.path.join(logs_dir, f"Human_vs_Bot_{game_name}.log")
    out_f = open(bot_log_path, "w")

    bot_proc = subprocess.Popen(
        [
            PYTHON_BIN, os.path.join(BASE_DIR, "bot_client.py"),
            "--room", game_name,
            "--deck", f"decks/{bot_deck_slug}.json",
            "--role", "join",
            "--name", "AIMaster_Bot"
        ],
        cwd=BASE_DIR,
        stdout=out_f,
        stderr=out_f
    )

    # 3. Monta os links de redirecionamento para o frontend
    game_url = f"{FRONTEND_URL}/?gameName={game_name}&playerID=1"
    lobby_url = f"{FRONTEND_URL}/game/lobby?gameName={game_name}&playerID=1"

    return {
        "success": True,
        "game_name": game_name,
        "auth_key": auth_key,
        "player_id": 1,
        "game_url": game_url,
        "lobby_url": lobby_url,
        "bot_pid": bot_proc.pid,
        "bot_deck": bot_deck_slug,
        "player_deck": player_deck_slug
    }
