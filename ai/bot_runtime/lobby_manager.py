import os
import time
import json
from ai.talishar_api import DEFAULT_BACKEND_URL
from ai.turn_order_learning import get_turn_order_learner

TALISHAR_API_URL = DEFAULT_BACKEND_URL

def choose_first_player(client):
    """Consulta o modelo de aprendizado de ordem de turno e envia a escolha."""
    learner = get_turn_order_learner()
    choice = learner.get_optimal_turn_order(client.player_name or client.deck_url)
    client.chosen_turn_order = choice
    ok = client.api.choose_first_player(client.game_id, client.player_id, client.auth_key, action=choice)
    if ok:
        client.log(f"[FIRST PLAYER] Escolha '{choice}' enviada para Jogador {client.player_id} (Hero: {client.player_name}).")
    else:
        client.log(f"[ERRO FIRST PLAYER] Falha ao enviar escolha '{choice}'")

def get_opponent_info(client) -> tuple[str, str]:
    """Consulta o endpoint GetLobbyRefresh.php e retorna (opp_hero, opp_class)."""
    try:
        res = client.session.post(
            f"{TALISHAR_API_URL}/APIs/GetLobbyRefresh.php",
            json={"gameName": client.game_id, "playerID": client.player_id, "authKey": client.auth_key},
            timeout=5.0
        )
        if res.status_code == 200:
            data = res.json()
            opp_hero = data.get("opponentHero", "")
            if not opp_hero:
                p1 = data.get("player1", {})
                p2 = data.get("player2", {})
                if client.player_id == 1:
                    opp_hero = p2.get("hero", "")
                else:
                    opp_hero = p1.get("hero", "")
            if opp_hero:
                meta = client.get_card_meta(opp_hero)
                return opp_hero, meta.get("class", "").lower()
    except Exception:
        pass
    return "", ""

def wait_in_lobby_and_start(client) -> bool:
    """
    Gerencia o ciclo de vida do bot como Jogador 2 (Join) no lobby do Talishar:
    1. Submete o sideboard do bot.
    2. Monitora o lobby via GetLobbyRefresh.php:
       - Se o bot venceu o dado e precisa escolher ordem de turno (amIChoosingFirstPlayer), escolhe 'Go First'.
       - Se o sideboard não foi aceito ainda, re-submete.
       - Aguarda o oponente confirmar e a partida iniciar (gamestate ativo ou isMainGameReady).
    """
    client.log(f"[LOBBY] Bot conectado ao lobby da sala #{client.game_id}. Submetendo sideboard...")
    client.submit_sideboard()

    first_player_chosen = False
    start_time = time.time()
    timeout_seconds = 600  # 10 minutos para o jogador humano preparar o deck no lobby

    client.log(f"[LOBBY] Aguardando confirmação no lobby da sala #{client.game_id}...")
    while time.time() - start_time < timeout_seconds:
        try:
            res = client.session.post(
                f"{TALISHAR_API_URL}/APIs/GetLobbyRefresh.php",
                json={"gameName": client.game_id, "playerID": client.player_id, "authKey": client.auth_key},
                timeout=5
            )
            if res.status_code == 200:
                data = res.json()

                # 1. Se o bot venceu o dado e precisa escolher quem começa
                am_i_choosing = data.get("amIChoosingFirstPlayer", False)
                if am_i_choosing and not first_player_chosen:
                    client.log(f"[LOBBY] Bot venceu o dado! Enviando escolha 'Go First'...")
                    client.choose_first_player()
                    first_player_chosen = True
                    time.sleep(0.2)
                    continue

                # 2. Se o bot ainda não submeteu sideboard ou o sideboard foi resetado
                if not data.get("mySideboardSubmitted", True):
                    client.submit_sideboard()
                    time.sleep(0.2)

                # 3. Verificar se a partida começou ou ambos os jogadores confirmaram
                if data.get("isMainGameReady") or data.get("gameStarted"):
                    client.log(f"[LOBBY] Ambos os jogadores confirmaram! Partida #{client.game_id} iniciando...")
                    return True

                # 4. Verificar se gamestate.txt já foi gerado no disco
                for gsp in [
                    f"Talishar/Games/{client.game_id}/gamestate.txt",
                    f"Games/{client.game_id}/gamestate.txt"
                ]:
                    if os.path.exists(gsp) and os.path.getsize(gsp) > 0:
                        client.log(f"[LOBBY] Gamestate detectado. Partida #{client.game_id} iniciada!")
                        return True
        except Exception as e:
            client.log(f"[LOBBY AVISO] {e}")

        time.sleep(0.3)

    client.log(f"[LOBBY TIMEOUT] Tempo limite excedido no lobby.")
    return False

def wait_for_opponent_and_start(client) -> bool:
    """Lado Host aguardando Jogador 2 no lobby, dado, sideboard e início da partida."""
    client.log(f"[HOST] Aguardando Jogador 2 entrar na sala #{client.game_id}...")
    p2_flag = f"logs/{client.room_id}_p2_ready.txt"
    first_player_chosen = False
    sideboard_sent = False
    start_time = time.time()

    while time.time() - start_time < 300:
        time.sleep(0.3)
        p2_present = os.path.exists(p2_flag)
        try:
            lres = client.session.post(
                f"{TALISHAR_API_URL}/APIs/GetLobbyRefresh.php",
                json={"gameName": client.game_id, "playerID": 1, "authKey": client.auth_key},
                timeout=5
            )
            if lres.status_code == 200:
                ldata = lres.json()
                status = ldata.get("gameStatus", 0)

                if p2_present or ldata.get("opponentHero") or status >= 2:
                    if ldata.get("amIChoosingFirstPlayer") and not first_player_chosen:
                        client.log(f"[HOST] Bot venceu o dado! Enviando escolha 'Go First'...")
                        client.choose_first_player()
                        first_player_chosen = True
                        time.sleep(0.2)

                    if not sideboard_sent:
                        client.submit_sideboard()
                        sideboard_sent = True

                    if ldata.get("isMainGameReady") or ldata.get("gameStarted"):
                        client.log(f"[HOST] Partida #{client.game_id} pronta para começar!")
                        return True

                    for gsp in [f"Talishar/Games/{client.game_id}/gamestate.txt", f"Games/{client.game_id}/gamestate.txt"]:
                        if os.path.exists(gsp) and os.path.getsize(gsp) > 0:
                            client.log(f"[HOST] Partida #{client.game_id} iniciada (gamestate detectado).")
                            return True
        except Exception:
            pass
    client.log(f"[TIMEOUT] Jogador 2 não entrou na sala a tempo.")
    return False

def setup_game_room(client) -> bool:
    """Configura e conecta a sala para o bot (seja como Host ou Join)."""
    if client.role == "host":
        target_deck = client.deck_url if client.deck_url else "deck.json"
        
        deck_data = None
        if os.path.exists(target_deck):
            try:
                with open(target_deck, "r") as f:
                    deck_data = json.load(f)
                    client.deck_format = deck_data.get("format", "blitz")
            except Exception:
                pass
        elif os.path.exists(f"decks/{target_deck}.json"):
            try:
                with open(f"decks/{target_deck}.json", "r") as f:
                    deck_data = json.load(f)
                    client.deck_format = deck_data.get("format", "blitz")
            except Exception:
                pass
        elif os.path.exists("Talishar/deck.json"):
            try:
                with open("Talishar/deck.json", "r") as f:
                    deck_data = json.load(f)
                    client.deck_format = deck_data.get("format", "blitz")
            except Exception:
                pass

        create_payload = {
            "format": client.deck_format,
            "fabdb": target_deck,
            "deck": deck_data,
            "visibility": "private",
            "gameDescription": client.room_id
        }
        try:
            res = client.session.post(f"{TALISHAR_API_URL}/APIs/CreateGame.php", json=create_payload, timeout=5.0)
            client.log(f"[CREATE RAW RESPONSE] HTTP {res.status_code}: {res.text[:120]}")
            try:
                data = res.json()
            except Exception:
                client.log(f"[ERRO DE JSON] Resposta do servidor não é JSON: {res.text[:180]}")
                return False
                
            if "error" in data:
                client.log(f"[ERRO AO CRIAR SALA] {data['error']}")
                return False
            client.game_id = str(data.get("gameName", ""))
            client.player_id = data.get("playerID", 1)
            client.auth_key = data.get("authKey", "")
            
            with open(f"logs/{client.room_id}_game_id.txt", "w") as f:
                f.write(client.game_id)
            client.log(f"[HOST SUCESSO] Partida ID #{client.game_id} criada ({client.deck_format.upper()}). AuthKey: {client.auth_key[:8]}...")
            
            return client.wait_for_opponent_and_start()
        except Exception as e:
            client.log(f"[ERRO DE CREATE] {e}")
            return False
    else:
        id_file = f"logs/{client.room_id}_game_id.txt"
        if os.path.exists(id_file):
            with open(id_file, "r") as f:
                client.game_id = f.read().strip()
        elif str(client.room_id).isdigit():
            client.game_id = str(client.room_id).strip()
        else:
            waited = 0
            while not os.path.exists(id_file) and waited < 20:
                time.sleep(1)
                waited += 1
            
            if os.path.exists(id_file):
                with open(id_file, "r") as f:
                    client.game_id = f.read().strip()
            else:
                client.log(f"[ERRO JOIN] Timeout esperando o Host criar a partida.")
                return False

        target_deck = client.deck_url if client.deck_url else "deck.json"
        deck_data = None
        if os.path.exists(target_deck):
            try:
                with open(target_deck, "r") as f:
                    deck_data = json.load(f)
                    client.deck_format = deck_data.get("format", client.deck_format)
            except Exception:
                pass
        elif os.path.exists(f"decks/{target_deck}.json"):
            try:
                with open(f"decks/{target_deck}.json", "r") as f:
                    deck_data = json.load(f)
                    client.deck_format = deck_data.get("format", client.deck_format)
            except Exception:
                pass
        elif os.path.exists("Talishar/deck.json"):
            try:
                with open("Talishar/deck.json", "r") as f:
                    deck_data = json.load(f)
                    client.deck_format = deck_data.get("format", client.deck_format)
            except Exception:
                pass

        join_payload = {
            "gameName": client.game_id,
            "playerID": 2,
            "fabdb": target_deck,
            "deck": deck_data
        }
        try:
            res = client.session.post(f"{TALISHAR_API_URL}/APIs/JoinGame.php", json=join_payload, timeout=5.0)
            client.log(f"[JOIN RAW RESPONSE] HTTP {res.status_code}: {res.text[:120]}")
            data = res.json()
            if "error" in data:
                client.log(f"[ERRO AO ENTRAR NA SALA] {data['error']}")
                return False
            client.player_id = data.get("playerID", 2)
            client.auth_key = data.get("authKey", "")
            if not client.auth_key:
                base_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                for gfp in [os.path.join("Talishar", "Games", str(client.game_id), "GameFile.txt"),
                            os.path.join(base_root, "Talishar", "Games", str(client.game_id), "GameFile.txt")]:
                    if os.path.exists(gfp):
                        try:
                            with open(gfp, "r") as gf:
                                lines = [l.strip() for l in gf.readlines()]
                                if len(lines) >= 9 and len(lines[8]) > 10:
                                    client.auth_key = lines[8]
                                    break
                        except Exception:
                            pass
            client.log(f"[JOIN SUCESSO] Entrou na partida #{client.game_id} como Jogador {client.player_id} (Auth: {str(client.auth_key)[:8]}...).")
            
            with open(f"logs/{client.room_id}_p2_ready.txt", "w") as f:
                f.write("ready")
            
            return client.wait_in_lobby_and_start()
        except Exception as e:
            client.log(f"[ERRO DE JOIN] {e}")
            return False
