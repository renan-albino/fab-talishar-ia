import time
import json
import argparse
import os
import requests
from datetime import datetime
from ai.policy_engine import PolicyEngine
from ai.equipment_learning import EquipmentTracker, get_equipment_learning_engine
from ai.talishar_api import TalisharApiClient, DEFAULT_BACKEND_URL
from ai.chat_badges import evaluate_board_state, format_html_line, format_attack_chat_message
from ai.turn_order_learning import get_turn_order_learner

TALISHAR_API_URL = DEFAULT_BACKEND_URL

class FabBotClient:
    def __init__(self, room_id: str, deck_url: str, role: str, player_name: str, mcts_sims: int = None, device: str = None, buffer_capacity: int = None):
        self.room_id = room_id
        self.deck_url = deck_url
        self.role = role
        self.player_name = player_name
        self.name = player_name  # Garante self.name definido para evitar AttributeError
        self.session = requests.Session()
        self.api = TalisharApiClient(backend_url=TALISHAR_API_URL, session=self.session)
        self.game_id = None
        self.player_id = None
        self.auth_key = None
        self.mcts_sims = mcts_sims
        self.device = device
        self.buffer_capacity = buffer_capacity
        self.use_gpu = (self.device != "cpu") if self.device else True
        self.log_file = f"logs/{self.room_id}_{self.player_name}_debug.log"
        self.match_log_file = f"logs/{self.room_id}_match_feed.log"
        self.deck_format = "blitz"
        self.policy_engine = PolicyEngine(
            model_path="data/model_latest.pt" if os.path.exists("data/model_latest.pt") else None,
            num_mcts_sims=self.mcts_sims,
            use_gpu=self.use_gpu
        )
        self.metrics = {"health": 20, "opp_health": 20, "card_advantage": 0, "status": "Iniciando", "phase": "pre-game"}
        self.trajectory = []
        self.attacks_made = 0
        self.damage_dealt = 0
        self.damage_taken = 0
        self.initial_my_health = None
        self.initial_opp_health = None
        self.execution_exceptions_count = 0
        self.clean_deck = os.path.basename(self.deck_url).replace(".json", "") if self.deck_url else "default_deck"
        
        # Identificar nome do Herói e Nome do Deck
        self.hero_name = ""
        self.deck_name = ""
        target_path = self.deck_url if (self.deck_url and os.path.exists(self.deck_url)) else f"decks/{self.clean_deck}.json"
        if os.path.exists(target_path):
            try:
                with open(target_path, "r", encoding="utf-8") as f:
                    d_data = json.load(f)
                    self.deck_name = d_data.get("name", "")
                    self.hero_name = d_data.get("hero", "")
                    if not self.hero_name and isinstance(d_data.get("cards"), list):
                        for c_entry in d_data["cards"]:
                            cid = c_entry.get("identifier", "") if isinstance(c_entry, dict) else str(c_entry)
                            meta = self.get_card_meta(cid)
                            if meta.get("slot") == "Hero":
                                self.hero_name = cid
                                break
            except Exception:
                pass
        if not self.deck_name:
            self.deck_name = self.clean_deck.replace("_", " ").title()
        if not self.hero_name:
            self.hero_name = self.deck_name
        self.equipment_tracker = EquipmentTracker(hero_name=self.hero_name)

        os.makedirs("logs", exist_ok=True)
        try:
            with open(f"logs/{self.room_id}_{self.role}_deck.txt", "w", encoding="utf-8") as f:
                f.write(self.deck_name or self.clean_deck)
        except Exception:
            pass

    def get_player_label(self, target_player_id: int) -> str:
        """Retorna uma identificação legível e clara para o Jogador 1 ou 2."""
        is_vs_human = (getattr(self, "name", "") == "AIMaster_Bot" or "Human_vs_Bot" in str(self.room_id) or str(self.room_id).isdigit())
        if is_vs_human:
            if target_player_id == 1:
                return "Humano (Você)"
            else:
                bot_deck = getattr(self, "deck_name", "") or self.clean_deck.replace("_", " ").title()
                return f"Bot AI ({bot_deck})"

        # Partida de Treino / Arena entre Bots
        p1_deck_file = f"logs/{self.room_id}_host_deck.txt"
        p2_deck_file = f"logs/{self.room_id}_join_deck.txt"
        p1_deck = getattr(self, "deck_name", self.clean_deck) if self.player_id == 1 else "Host"
        p2_deck = getattr(self, "deck_name", self.clean_deck) if self.player_id == 2 else "Join"

        if os.path.exists(p1_deck_file):
            try:
                with open(p1_deck_file, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                    if val:
                        p1_deck = val
            except Exception:
                pass
        if os.path.exists(p2_deck_file):
            try:
                with open(p2_deck_file, "r", encoding="utf-8") as f:
                    val = f.read().strip()
                    if val:
                        p2_deck = val
            except Exception:
                pass

        if target_player_id == 1:
            return f"Jogador 1 ({p1_deck})"
        else:
            return f"Jogador 2 ({p2_deck})"

    def log(self, message):
        t_str = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{t_str}] {message}"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
        try:
            with open(self.match_log_file, "a", encoding="utf-8") as mf:
                mf.write(formatted + "\n")
        except Exception:
            pass
        print(formatted, flush=True)

    def run_loop(self):
        self.log(f"[*] Iniciando Bot HTTP para a sala {self.room_id} (Role: {self.role})")
        
        # 1. Enviar requisição para criar ou entrar na sala
        if self.role == "host":
            target_deck = self.deck_url if self.deck_url else "deck.json"
            
            deck_data = None
            if os.path.exists(target_deck):
                try:
                    with open(target_deck, "r") as f:
                        deck_data = json.load(f)
                        self.deck_format = deck_data.get("format", "blitz")
                except Exception:
                    pass
            elif os.path.exists(f"decks/{target_deck}.json"):
                try:
                    with open(f"decks/{target_deck}.json", "r") as f:
                        deck_data = json.load(f)
                        self.deck_format = deck_data.get("format", "blitz")
                except Exception:
                    pass
            elif os.path.exists("Talishar/deck.json"):
                try:
                    with open("Talishar/deck.json", "r") as f:
                        deck_data = json.load(f)
                        self.deck_format = deck_data.get("format", "blitz")
                except Exception:
                    pass

            create_payload = {
                "format": self.deck_format,
                "fabdb": target_deck,
                "deck": deck_data,
                "visibility": "private",
                "gameDescription": self.room_id
            }
            try:
                res = self.session.post(f"{TALISHAR_API_URL}/APIs/CreateGame.php", json=create_payload)
                self.log(f"[CREATE RAW RESPONSE] HTTP {res.status_code}: {res.text[:120]}")
                try:
                    data = res.json()
                except Exception as je:
                    self.log(f"[ERRO DE JSON] Resposta do servidor não é JSON: {res.text[:180]}")
                    return
                    
                if "error" in data:
                    self.log(f"[ERRO AO CRIAR SALA] {data['error']}")
                    return
                self.game_id = str(data.get("gameName", ""))
                self.player_id = data.get("playerID", 1)
                self.auth_key = data.get("authKey", "")
                
                with open(f"logs/{self.room_id}_game_id.txt", "w") as f:
                    f.write(self.game_id)
                self.log(f"[HOST SUCESSO] Partida ID #{self.game_id} criada ({self.deck_format.upper()}). AuthKey: {self.auth_key[:8]}...")
                
                self.wait_for_opponent_and_start()
            except Exception as e:
                self.log(f"[ERRO DE CREATE] {e}")
                return
        else:
            id_file = f"logs/{self.room_id}_game_id.txt"
            if os.path.exists(id_file):
                with open(id_file, "r") as f:
                    self.game_id = f.read().strip()
            elif str(self.room_id).isdigit():
                self.game_id = str(self.room_id).strip()
            else:
                waited = 0
                while not os.path.exists(id_file) and waited < 20:
                    time.sleep(1)
                    waited += 1
                
                if os.path.exists(id_file):
                    with open(id_file, "r") as f:
                        self.game_id = f.read().strip()
                else:
                    self.log(f"[ERRO JOIN] Timeout esperando o Host criar a partida.")
                    return

            target_deck = self.deck_url if self.deck_url else "deck.json"
            deck_data = None
            if os.path.exists(target_deck):
                try:
                    with open(target_deck, "r") as f:
                        deck_data = json.load(f)
                        self.deck_format = deck_data.get("format", self.deck_format)
                except Exception:
                    pass
            elif os.path.exists(f"decks/{target_deck}.json"):
                try:
                    with open(f"decks/{target_deck}.json", "r") as f:
                        deck_data = json.load(f)
                        self.deck_format = deck_data.get("format", self.deck_format)
                except Exception:
                    pass
            elif os.path.exists("Talishar/deck.json"):
                try:
                    with open("Talishar/deck.json", "r") as f:
                        deck_data = json.load(f)
                        self.deck_format = deck_data.get("format", self.deck_format)
                except Exception:
                    pass

            join_payload = {
                "gameName": self.game_id,
                "playerID": 2,
                "fabdb": target_deck,
                "deck": deck_data
            }
            try:
                res = self.session.post(f"{TALISHAR_API_URL}/APIs/JoinGame.php", json=join_payload)
                self.log(f"[JOIN RAW RESPONSE] HTTP {res.status_code}: {res.text[:120]}")
                data = res.json()
                if "error" in data:
                    self.log(f"[ERRO AO ENTRAR NA SALA] {data['error']}")
                    return
                self.player_id = data.get("playerID", 2)
                self.auth_key = data.get("authKey", "")
                if not self.auth_key:
                    base_root = os.path.dirname(os.path.abspath(__file__))
                    for gfp in [os.path.join("Talishar", "Games", str(self.game_id), "GameFile.txt"),
                                os.path.join(base_root, "Talishar", "Games", str(self.game_id), "GameFile.txt")]:
                        if os.path.exists(gfp):
                            try:
                                with open(gfp, "r") as gf:
                                    lines = [l.strip() for l in gf.readlines()]
                                    if len(lines) >= 9 and len(lines[8]) > 10:
                                        self.auth_key = lines[8]
                                        break
                            except Exception:
                                pass
                self.log(f"[JOIN SUCESSO] Entrou na partida #{self.game_id} como Jogador {self.player_id} (Auth: {str(self.auth_key)[:8]}...).")
                
                with open(f"logs/{self.room_id}_p2_ready.txt", "w") as f:
                    f.write("ready")
                
                self.wait_in_lobby_and_start()
            except Exception as e:
                self.log(f"[ERRO DE JOIN] {e}")
                return

        # 2. Loop principal de Polling de estado da mesa
        waiting_logged = False
        last_logged_turn = -1
        while True:
            try:
                res_state = self.session.get(
                    f"{TALISHAR_API_URL}/GetNextTurn.php",
                    params={"gameName": self.game_id, "playerID": self.player_id, "authKey": self.auth_key}
                )

                if res_state.status_code == 200:
                    text = res_state.text.strip()
                    if not text or text == "0":
                        if not waiting_logged:
                            self.log(f"[AGUARDANDO] Aguardando início do Turno 1 na sala #{self.game_id}...")
                            waiting_logged = True
                        self.metrics["phase"] = "Aguardando Início"
                        self.metrics["status"] = "Aguardando"
                        with open(f"logs/{self.room_id}_{self.player_name}.json", "w") as f:
                            json.dump({"metrics": self.metrics}, f)
                    else:
                        try:
                            state = res_state.json()
                            if "errorMessage" in state:
                                self.log(f"[AVISO MESA] {state['errorMessage']}")
                            else:
                                turn_num = state.get("turnNo", state.get("currentTurn", 1))
                                if turn_num != last_logged_turn:
                                    try:
                                        my_h = int(state.get("playerHealth", 40))
                                    except Exception:
                                        my_h = 40
                                    try:
                                        opp_h = int(state.get("opponentHealth", 40))
                                    except Exception:
                                        opp_h = 40
                                    p1_hp = my_h if self.player_id == 1 else opp_h
                                    p2_hp = opp_h if self.player_id == 1 else my_h
                                    p1_lbl = self.get_player_label(1)
                                    p2_lbl = self.get_player_label(2)
                                    turn_active_id = state.get("turnPlayer", 1)
                                    active_lbl = p1_lbl if str(turn_active_id) == "1" else p2_lbl

                                    # O Host (Player 1) loga no feed compartilhado para evitar linhas duplicadas e invertidas
                                    if self.player_id == 1:
                                        self.log(f"[TURNO {turn_num}] 📊 Placar: {p1_lbl} [{p1_hp} HP] vs {p2_lbl} [{p2_hp} HP] | Vez de: {active_lbl}")
                                    else:
                                        with open(self.log_file, "a", encoding="utf-8") as lf:
                                            lf.write(f"[{datetime.now().strftime('%H:%M:%S')}] [TURNO {turn_num}] 📊 Placar: {p1_lbl} [{p1_hp} HP] vs {p2_lbl} [{p2_hp} HP] | Vez de: {active_lbl}\n")
                                    last_logged_turn = turn_num
                                self.handle_game_tick(state)
                                waiting_logged = False
                                if self.metrics.get("status") == "Finalizada":
                                    self.log(f"[*] Bot {self.player_name} finalizou a partida #{self.game_id}.")
                                    break
                        except json.JSONDecodeError:
                            self.log(f"[ALERTA] Resposta inesperada do servidor: {res_state.text[:400]}")
                else:
                    self.log(f"[ALERTA] Servidor retornou HTTP {res_state.status_code}")
                
            except Exception as e:
                self.execution_exceptions_count += 1
                self.log(f"[ERRO DE CONEXÃO] {e}")

            time.sleep(0.005)

    def choose_first_player(self):
        learner = get_turn_order_learner()
        choice = learner.get_optimal_turn_order(self.player_name or self.deck_url)
        self.chosen_turn_order = choice
        ok = self.api.choose_first_player(self.game_id, self.player_id, self.auth_key, action=choice)
        if ok:
            self.log(f"[FIRST PLAYER] Escolha '{choice}' enviada para Jogador {self.player_id} (Hero: {self.player_name}).")
        else:
            self.log(f"[ERRO FIRST PLAYER] Falha ao enviar escolha '{choice}'")

    def wait_in_lobby_and_start(self):
        """
        Gerencia o ciclo de vida do bot como Jogador 2 (Join) no lobby do Talishar:
        1. Submete o sideboard do bot.
        2. Monitora o lobby via GetLobbyRefresh.php:
           - Se o bot venceu o dado e precisa escolher ordem de turno (amIChoosingFirstPlayer), escolhe 'Go First'.
           - Se o sideboard não foi aceito ainda, re-submete.
           - Aguarda o oponente confirmar e a partida iniciar (gamestate ativo ou isMainGameReady).
        """
        self.log(f"[LOBBY] Bot conectado ao lobby da sala #{self.game_id}. Submetendo sideboard...")
        self.submit_sideboard()

        first_player_chosen = False
        start_time = time.time()
        timeout_seconds = 600  # 10 minutos para o jogador humano preparar o deck no lobby

        self.log(f"[LOBBY] Aguardando confirmação no lobby da sala #{self.game_id}...")
        while time.time() - start_time < timeout_seconds:
            try:
                res = self.session.post(
                    f"{TALISHAR_API_URL}/APIs/GetLobbyRefresh.php",
                    json={"gameName": self.game_id, "playerID": self.player_id, "authKey": self.auth_key},
                    timeout=5
                )
                if res.status_code == 200:
                    data = res.json()

                    # 1. Se o bot venceu o dado e precisa escolher quem começa
                    am_i_choosing = data.get("amIChoosingFirstPlayer", False)
                    if am_i_choosing and not first_player_chosen:
                        self.log(f"[LOBBY] Bot venceu o dado! Enviando escolha 'Go First'...")
                        self.choose_first_player()
                        first_player_chosen = True
                        time.sleep(0.2)
                        continue

                    # 2. Se o bot ainda não submeteu sideboard ou o sideboard foi resetado
                    if not data.get("mySideboardSubmitted", True):
                        self.submit_sideboard()
                        time.sleep(0.2)

                    # 3. Verificar se a partida começou ou ambos os jogadores confirmaram
                    if data.get("isMainGameReady") or data.get("gameStarted"):
                        self.log(f"[LOBBY] Ambos os jogadores confirmaram! Partida #{self.game_id} iniciando...")
                        return True

                    # 4. Verificar se gamestate.txt já foi gerado no disco
                    for gsp in [
                        f"Talishar/Games/{self.game_id}/gamestate.txt",
                        f"Games/{self.game_id}/gamestate.txt"
                    ]:
                        if os.path.exists(gsp) and os.path.getsize(gsp) > 0:
                            self.log(f"[LOBBY] Gamestate detectado. Partida #{self.game_id} iniciada!")
                            return True
            except Exception as e:
                self.log(f"[LOBBY AVISO] {e}")

            time.sleep(0.3)

        self.log(f"[LOBBY TIMEOUT] Tempo limite excedido no lobby.")
        return False

    def wait_for_opponent_and_start(self):
        self.log(f"[HOST] Aguardando Jogador 2 entrar na sala #{self.game_id}...")
        p2_flag = f"logs/{self.room_id}_p2_ready.txt"
        first_player_chosen = False
        sideboard_sent = False
        start_time = time.time()

        while time.time() - start_time < 300:
            time.sleep(0.3)
            p2_present = os.path.exists(p2_flag)
            try:
                lres = self.session.post(
                    f"{TALISHAR_API_URL}/APIs/GetLobbyRefresh.php",
                    json={"gameName": self.game_id, "playerID": 1, "authKey": self.auth_key},
                    timeout=5
                )
                if lres.status_code == 200:
                    ldata = lres.json()
                    status = ldata.get("gameStatus", 0)

                    if p2_present or ldata.get("opponentHero") or status >= 2:
                        if ldata.get("amIChoosingFirstPlayer") and not first_player_chosen:
                            self.log(f"[HOST] Bot venceu o dado! Enviando escolha 'Go First'...")
                            self.choose_first_player()
                            first_player_chosen = True
                            time.sleep(0.2)

                        if not sideboard_sent:
                            self.submit_sideboard()
                            sideboard_sent = True

                        if ldata.get("isMainGameReady") or ldata.get("gameStarted"):
                            self.log(f"[HOST] Partida #{self.game_id} pronta para começar!")
                            return True

                        for gsp in [f"Talishar/Games/{self.game_id}/gamestate.txt", f"Games/{self.game_id}/gamestate.txt"]:
                            if os.path.exists(gsp) and os.path.getsize(gsp) > 0:
                                self.log(f"[HOST] Partida #{self.game_id} iniciada (gamestate detectado).")
                                return True
            except Exception:
                pass
        self.log(f"[TIMEOUT] Jogador 2 não entrou na sala a tempo.")
        return False

    def get_card_meta(self, card_id: str) -> dict:
        if not hasattr(self, "_card_db") or self._card_db is None:
            base_root = os.path.dirname(os.path.abspath(__file__))
            for p in ["data/fab_cards_db.json", os.path.join(base_root, "data", "fab_cards_db.json")]:
                if os.path.exists(p):
                    try:
                        with open(p, "r", encoding="utf-8") as f:
                            self._card_db = json.load(f)
                            break
                    except Exception:
                        pass
            if not hasattr(self, "_card_db") or self._card_db is None:
                self._card_db = {}
        return self._card_db.get(card_id, {})

    def get_opponent_info(self):
        try:
            res = self.session.post(
                f"{TALISHAR_API_URL}/APIs/GetLobbyRefresh.php",
                json={"gameName": self.game_id, "playerID": self.player_id, "authKey": self.auth_key}
            )
            if res.status_code == 200:
                data = res.json()
                opp_hero = data.get("opponentHero", "")
                if not opp_hero:
                    p1 = data.get("player1", {})
                    p2 = data.get("player2", {})
                    if self.player_id == 1:
                        opp_hero = p2.get("hero", "")
                    else:
                        opp_hero = p1.get("hero", "")
                if opp_hero:
                    meta = self.get_card_meta(opp_hero)
                    return opp_hero, meta.get("class", "").lower()
        except Exception:
            pass
        return "", ""

    def submit_sideboard(self):
        is_cc = self.deck_format.lower() in ("cc", "compcc", "llcc", "compllcc", "futurecc", "futurell", "gage")
        
        opp_hero, opp_class = self.get_opponent_info()
        is_arcane = opp_class in ("wizard", "runeblade")
        is_fatigue = opp_class in ("guardian", "assassin", "mechanologist")
        
        min_main = 60 if is_cc else 40
        if is_fatigue and is_cc:
            min_main = 65

        deck_file = self.deck_url if self.deck_url.endswith(".json") else f"decks/{self.deck_url}.json"
        if not os.path.exists(deck_file):
            for p in [f"Talishar/decks/{self.deck_url}.json", f"Talishar/decks/{self.deck_url}", "deck.json", "Talishar/deck.json"]:
                if os.path.exists(p):
                    deck_file = p
                    break

        raw_cards = []
        if os.path.exists(deck_file):
            try:
                with open(deck_file, "r", encoding="utf-8") as f:
                    deck_data = json.load(f)
                    raw_cards = deck_data.get("cards", [])
            except Exception as e:
                self.log(f"[AVISO] Erro ao ler deck_file {deck_file}: {e}")

        if not raw_cards:
            pdeck_path = f"Talishar/Games/{self.game_id}/p{self.player_id}Deck.txt"
            if not os.path.exists(pdeck_path):
                pdeck_path = f"Games/{self.game_id}/p{self.player_id}Deck.txt"
            if os.path.exists(pdeck_path):
                try:
                    with open(pdeck_path, "r", encoding="utf-8") as f:
                        lines = [l.strip() for l in f if l.strip()]
                    if len(lines) >= 2:
                        for cid in lines[0].split() + lines[1].split():
                            raw_cards.append({"identifier": cid, "total": 1})
                except Exception:
                    pass

        hero = ""
        head = ""
        chest = ""
        arms = ""
        legs = ""
        quiver = ""
        weapons = []
        raw_weapon_candidates = []
        raw_quivers = []
        main_cards = []
        inv = []

        base_head_cands = []
        base_chest_cands = []
        base_arms_cands = []
        base_legs_cands = []

        for c in raw_cards:
            cid = c.get("identifier", "") if isinstance(c, dict) else str(c)
            tot = int(c.get("count", c.get("total", 1))) if isinstance(c, dict) else 1
            if not cid:
                continue
            meta = self.get_card_meta(cid)
            slot = meta.get("slot", "Deck")
            subtype = str(meta.get("subtype", "")).lower()

            if slot == "Hero":
                if not hero:
                    hero = cid
            elif slot == "Head":
                if not head:
                    head = cid
                else:
                    inv.append(cid)
            elif slot == "Chest":
                if not chest:
                    chest = cid
                else:
                    inv.append(cid)
            elif slot == "Arms":
                if not arms:
                    arms = cid
                else:
                    inv.append(cid)
            elif slot == "Legs":
                if not legs:
                    legs = cid
                else:
                    inv.append(cid)
            elif "quiver" in subtype or "quiver" in cid.lower():
                raw_quivers.append(cid)
            elif slot in ("Weapon", "Off-Hand") or meta.get("type") == "W":
                raw_weapon_candidates.append(cid)
            else:
                if "base" in subtype:
                    if "head" in subtype:
                        base_head_cands.append(cid)
                    elif "chest" in subtype:
                        base_chest_cands.append(cid)
                    elif "arms" in subtype:
                        base_arms_cands.append(cid)
                    elif "legs" in subtype:
                        base_legs_cands.append(cid)
                main_cards.extend([cid] * tot)

        # ── Resolução de Equipamentos Base / Evo Base (ex: Teklovossen) para slots vagos ──
        if not head and base_head_cands:
            head = base_head_cands[0]
            if head in main_cards:
                main_cards.remove(head)
        if not chest and base_chest_cands:
            chest = base_chest_cands[0]
            if chest in main_cards:
                main_cards.remove(chest)
        if not arms and base_arms_cands:
            if is_arcane and any("arcbane" in x for x in base_arms_cands):
                arms = next(x for x in base_arms_cands if "arcbane" in x)
            else:
                arms = base_arms_cands[0]
            if arms in main_cards:
                main_cards.remove(arms)
        if not legs and base_legs_cands:
            legs = base_legs_cands[0]
            if legs in main_cards:
                main_cards.remove(legs)

        # ── Resolução de Quivers (Aljavas de Ranger) ──
        if raw_quivers:
            quiver = raw_quivers[0]
            inv.extend(raw_quivers[1:])

        if not hero:
            hero = "ira_crimson_haze"

        # ── Resolução Legal de Armas e Mãos (Flesh and Blood CR 2.8.2 e CR 3.0) ──
        # Um herói possui exatamente 2 slots de mãos.
        # - Arma de 2 Mãos (2H): ocupa 2 mãos. NUNCA pode ter escudo, off-hand ou 2ª arma!
        # - Arma de 1 Mão (1H): ocupa 1 mão. Permite 2ª arma 1H ou 1 Off-Hand/Escudo.
        # - Off-Hand (Escudo, Orbe, Aljava): ocupa 1 mão. Só pode ser equipada com arma 1H ou desarmado.
        w_2h = []
        w_1h = []
        offhands = []

        for cid in raw_weapon_candidates:
            meta = self.get_card_meta(cid)
            slot = meta.get("slot", "")
            subtype = str(meta.get("subtype", "")).lower()
            is_1h = bool(meta.get("is1h", False))
            is_off = (slot == "Off-Hand" or "off-hand" in subtype or "shield" in subtype)
            if is_off:
                offhands.append(cid)
            elif is_1h:
                w_1h.append(cid)
            else:
                w_2h.append(cid)

        chosen_weapons = []
        # Cenário 0: Se contra fadiga e temos arma 2H pesada (ex: Sledge of Anvilheim vs Bravo), priorizar a arma 2H
        if w_2h and is_fatigue and not is_arcane:
            chosen_weapons = [w_2h[0]]
        # Cenário 1: Temos arma 1H e Off-Hand/Escudo (ex: Titan's Fist + Stalagmite/Rampart para Jarl/Guardião)
        elif w_1h and offhands:
            # Para Jarl / Guardiões de Gelo, Stalagmite é o escudo prioritário (Frostbite)
            best_off = offhands[0]
            for off in offhands:
                if "stalagmite" in off:
                    best_off = off
                    break
            chosen_weapons = [w_1h[0], best_off]
        # Cenário 2: Múltiplas armas 1H (ex: 2 Kodachis para Ninja, 2 Sabres para Warrior, 2 Adagas para Assassin)
        elif len(w_1h) >= 2:
            chosen_weapons = [w_1h[0], w_1h[1]]
        # Cenário 3: Arma de 2 Mãos (ex: Sledge of Anvilheim, Anothos, Dawnblade, Raydn, Dread Scythe)
        # Atenção estrita: ocupa AMBAS as mãos. Nenhum outro item de mão pode ser equipado!
        elif w_2h:
            chosen_weapons = [w_2h[0]]
        # Cenário 4: Apenas uma arma 1H (sem par)
        elif w_1h:
            chosen_weapons = [w_1h[0]]
        # Cenário 5: Apenas Off-Hand sem arma (caso raro/incomum)
        elif offhands:
            chosen_weapons = [offhands[0]]

        weapons = chosen_weapons
        # Todos os itens de arma/off-hand não equipados vão obrigatoriamente para o inventário (sideboard)
        for cid in raw_weapon_candidates:
            if cid not in weapons:
                inv.append(cid)

        equipped_arcane_count = 0
        if is_arcane:
            equip_slots = {"Head": head, "Chest": chest, "Arms": arms, "Legs": legs}
            new_inv = []
            for item in inv:
                meta = self.get_card_meta(item)
                slot = meta.get("slot", "")
                text = meta.get("text", "").lower()
                name = meta.get("name", "").lower()
                keywords = [k.lower() for k in meta.get("keywords", [])]
                is_arcane_item = (
                    "arcane barrier" in text
                    or "nullrune" in name
                    or "quelling" in text
                    or "spellvoid" in text
                    or "spellvoid" in name
                    or any("spellvoid" in k or "arcane" in k for k in keywords)
                )
                if slot in equip_slots and is_arcane_item:
                    old_item = equip_slots[slot]
                    if old_item:
                        new_inv.append(old_item)
                    equip_slots[slot] = item
                else:
                    new_inv.append(item)
            head, chest, arms, legs = equip_slots.get("Head", ""), equip_slots.get("Chest", ""), equip_slots.get("Arms", ""), equip_slots.get("Legs", "")
            inv = new_inv

            # Contabilizar quantos equipamentos com Arcane Barrier / Spellvoid / Quelling temos equipados
            for eq in [head, chest, arms, legs] + weapons:
                if not eq:
                    continue
                meta = self.get_card_meta(eq)
                text = meta.get("text", "").lower()
                name = meta.get("name", "").lower()
                keywords = [k.lower() for k in meta.get("keywords", [])]
                if (
                    "arcane barrier" in text
                    or "nullrune" in name
                    or "quelling" in text
                    or "spellvoid" in text
                    or "spellvoid" in name
                    or any("spellvoid" in k or "arcane" in k for k in keywords)
                ):
                    equipped_arcane_count += 1

        flat_deck = main_cards
        if len(flat_deck) > min_main:
            def card_score(cid):
                meta = self.get_card_meta(cid)
                pitch = int(meta.get("pitch", 0)) if str(meta.get("pitch", 0)).isdigit() else 0
                defense = int(meta.get("defense", 0)) if str(meta.get("defense", 0)).isdigit() else 0
                power = int(meta.get("power", 0)) if str(meta.get("power", 0)).isdigit() else 0
                
                # Se o oponente causar dano arcano:
                if is_arcane:
                    if equipped_arcane_count >= 2:
                        if pitch == 3:
                            return 100 + power + defense
                    else:
                        if pitch == 3:
                            return (defense * 2) + power - 10

                return power + defense + (3 - pitch)
            
            flat_deck.sort(key=card_score, reverse=True)
            inv.extend(flat_deck[min_main:])
            flat_deck = flat_deck[:min_main]
        elif len(flat_deck) < min_main:
            # Puxar do inventario se faltar cartas para atingir o minimo de 60/40
            needed = min_main - len(flat_deck)
            deck_inv = [i for i in inv if self.get_card_meta(i).get("slot", "Deck") == "Deck"]
            if len(deck_inv) >= needed:
                flat_deck.extend(deck_inv[:needed])
                for c in deck_inv[:needed]:
                    inv.remove(c)

        sub_obj = {
            "hero": hero,
            "head": head,
            "chest": chest,
            "arms": arms,
            "legs": legs,
            "hands": weapons,
            "deck": flat_deck,
            "inventory": inv
        }
        if quiver:
            sub_obj["quiver"] = quiver

        post_payload = {
            "gameName": self.game_id,
            "playerID": self.player_id,
            "authKey": self.auth_key,
            "submission": json.dumps(sub_obj)
        }

        res = self.session.post(f"{TALISHAR_API_URL}/APIs/SubmitSideboard.php", json=post_payload)
        try:
            data = res.json()
            if "error" in data or data.get("status") == "FAIL":
                self.log(f"[ERRO NO SIDEBOARD] {data.get('error') or data.get('deckError')}")
                return False
        except Exception:
            pass

        self.metrics["sideboard_info"] = {
            "hero": hero,
            "equipment": {
                "head": head,
                "chest": chest,
                "arms": arms,
                "legs": legs,
                "weapons": weapons
            },
            "main_deck_count": len(flat_deck),
            "main_deck_cards": flat_deck,
            "sideboard_count": len(inv),
            "sideboard_cards": inv
        }
        with open(f"logs/{self.room_id}_{self.player_name}.json", "w") as f:
            json.dump({"metrics": self.metrics}, f)

        self.policy_engine = PolicyEngine(
            hero_name=hero,
            model_path="data/model_latest.pt" if os.path.exists("data/model_latest.pt") else None,
            room_id=self.room_id,
            num_mcts_sims=self.mcts_sims,
            use_gpu=self.use_gpu
        )
        self.policy_engine.update_room_id(room_id=self.room_id, hero_name=hero)
        self.log(f"[SIDEBOARD CONFIRMADO] Jogador {self.player_id}: Hero={hero} | Equip: [H:{head}, C:{chest}, A:{arms}, L:{legs}, W:{weapons}] | Deck={len(flat_deck)} cartas | Inv={len(inv)} itens.")
        return True

    def send_chat_log(self, text: str, highlight: bool = False, bg_color: str = "#1e293b", text_color: str = "#38bdf8"):
        target_id = getattr(self, "game_id", None) or getattr(self, "room_id", "")
        if not target_id:
            return
        html_line = format_html_line(text, highlight=highlight, bg_color=bg_color, text_color=text_color)
        self.api.append_game_log(target_id, html_line)

    def evaluate_board_state(self, state: dict) -> float:
        """Calcula o índice de avaliação da posição (estilo Chess Eval +/-)."""
        return evaluate_board_state(state)

    def get_combat_chain_desc(self, state: dict) -> str:
        """Extrai descrição detalhada da carta/arma atacante e status da Combat Chain."""
        active_chain = state.get("activeChainLink")
        if not isinstance(active_chain, dict):
            return ""
        reactions = active_chain.get("reactions", [])
        if not reactions:
            return ""
        first_card = reactions[0] if isinstance(reactions, list) and reactions else {}
        card_name = first_card.get("cardNumber", "")
        if not card_name:
            return ""
        pow_val = active_chain.get("totalPower", 0)
        def_val = active_chain.get("totalDefense", 0)
        extras = []
        if active_chain.get("goAgain"):
            extras.append("Go Again")
        if active_chain.get("dominate"):
            extras.append("Dominate")
        extra_str = f" | {', '.join(extras)}" if extras else ""
        return f"{card_name} [Poder: {pow_val} | Bloqueio: {def_val}{extra_str}]"

    def handle_game_tick(self, state: dict):
        if "opponentHand" in state and "opponentHandCount" not in state:
            state["opponentHandCount"] = len(state.get("opponentHand", []))

        # Compatibilidade com backend Talishar (playerArse -> playerArsenal, theirArse -> theirArsenal)
        if "playerArse" in state and "playerArsenal" not in state:
            state["playerArsenal"] = state.get("playerArse") or []
        if "theirArse" in state and "theirArsenal" not in state:
            state["theirArsenal"] = state.get("theirArse") or []
        if "theirArsenal" in state and "opponentArsenal" not in state:
            state["opponentArsenal"] = state.get("theirArsenal") or []

        raw_my_h = state.get("playerHealth")
        raw_opp_h = state.get("opponentHealth")
        
        try:
            my_h = int(raw_my_h) if raw_my_h is not None else 40
        except (ValueError, TypeError):
            my_h = 40
            
        try:
            opp_h = int(raw_opp_h) if raw_opp_h is not None else 40
        except (ValueError, TypeError):
            opp_h = 40
            
        if self.initial_my_health is None:
            self.initial_my_health = my_h
        if self.initial_opp_health is None:
            self.initial_opp_health = opp_h

        if not hasattr(self, "_prev_tracked_opp_h"):
            self._prev_tracked_opp_h = opp_h
            self._prev_tracked_my_h = my_h
        else:
            if opp_h < self._prev_tracked_opp_h:
                self.damage_dealt += (self._prev_tracked_opp_h - opp_h)
            if my_h < self._prev_tracked_my_h:
                self.damage_taken += (self._prev_tracked_my_h - my_h)
            self._prev_tracked_opp_h = opp_h
            self._prev_tracked_my_h = my_h

        turn = int(state.get("turnNo", state.get("currentTurn", 1))) if str(state.get("turnNo", state.get("currentTurn", 1))).isdigit() else 1
        
        # Disparar banner de avaliação de turno no chat (estilo Chess Engine)
        if turn != getattr(self, "last_chat_turn", -1):
            self.last_chat_turn = turn
            board_eval = self.evaluate_board_state(state)
            eval_str = f"+{board_eval}" if board_eval > 0 else str(board_eval)
            chat_turn_summary = f"<b>[Turno {turn}]</b> 📊 <b>AI Eval:</b> <code>{eval_str}</code> | <b>Vida:</b> {my_h} vs {opp_h} | <b>Mão:</b> {len(state.get('playerHand', []))} cartas"
            self.send_chat_log(chat_turn_summary, highlight=True, bg_color="#1e293b", text_color="#94a3b8")

        self.metrics["health"] = my_h
        self.metrics["opp_health"] = opp_h
        self.metrics["deck_url"] = self.deck_url
        self.metrics["player_id"] = self.player_id
        
        try:
            turn = int(state.get("turnNo", state.get("currentTurn", 1)))
        except (ValueError, TypeError):
            turn = 1
            
        tp_raw = state.get("turnPhase", "")
        tp_name = tp_raw.get("turnPhase", "") if isinstance(tp_raw, dict) else str(tp_raw)
        self.metrics["phase"] = f"Turno {turn} ({tp_name})" if tp_name else f"Turno {turn}"
        self.metrics["status"] = "Jogando"
        
        # ── Detecção de Stalemate / Empate Técnico (Fadiga sem Mudança de Estado) ──
        my_deck_cnt = int(state.get("playerDeckCount", len(state.get("playerDeck", []))))
        opp_deck_cnt = int(state.get("opponentDeckCount", len(state.get("opponentDeck", []))))
        my_hand_cnt = len(state.get("playerHand", []))
        opp_hand_cnt = len(state.get("opponentHand", []))
        my_ars_cnt = len(state.get("playerArsenal", []))
        opp_ars_cnt = len(state.get("opponentArsenal", []))

        # Inicializa variáveis de controle de estagnação no bot se não existirem
        if not hasattr(self, "_last_state_health"):
            self._last_state_health = (my_h, opp_h)
            self._last_state_turn = turn
            self._stagnant_turns_count = 0

        # Atualiza a contagem a cada avanço de turno
        if turn != self._last_state_turn:
            prev_my_h, prev_opp_h = self._last_state_health
            if my_h == prev_my_h and opp_h == prev_opp_h:
                self._stagnant_turns_count += 1
            else:
                self._stagnant_turns_count = 0
            self._last_state_health = (my_h, opp_h)
            self._last_state_turn = turn

        is_stalemate = False
        stalemate_reason = ""

        # 1. Ambos os decks esgotados (0 cartas) sem dano por 3 turnos seguidos
        if my_deck_cnt == 0 and opp_deck_cnt == 0:
            if self._stagnant_turns_count >= 3:
                is_stalemate = True
                stalemate_reason = f"Decks esgotados (0 cartas) e sem alteração de vida por {self._stagnant_turns_count} turnos consecutivos"
            # Se decks em 0 e mãos e arsenais vazios (impossível jogar ações ou gerar recursos):
            elif my_hand_cnt == 0 and opp_hand_cnt == 0 and my_ars_cnt == 0 and opp_ars_cnt == 0:
                is_stalemate = True
                stalemate_reason = "Decks, mãos e arsenais completamente esgotados (deadlock de ações)"

        # 2. Hard Cap de Turnos Anti-Loop (CR/TR Tournament Round Timeout)
        # Partidas de FaB duram 8-15 turnos (Blitz) e 15-25 turnos (CC). Acima de 45/55 é loop garantido.
        max_turn_limit = 45 if self.deck_format.lower() in ("blitz", "compblitz") else 55
        if turn >= max_turn_limit:
            is_stalemate = True
            stalemate_reason = f"Limite máximo de {max_turn_limit} turnos atingido (Hard Cap Anti-Loop)"

        # 3. Estagnação prolongada (12 turnos consecutivos sem dano com decks residuais <= 5)
        if self._stagnant_turns_count >= 12 and (my_deck_cnt <= 5 or opp_deck_cnt <= 5):
            is_stalemate = True
            stalemate_reason = "Estagnação prolongada (12 turnos sem dano com decks residuais esgotando)"

        # Checar se a partida terminou (vitória, derrota ou empate técnico)
        if tp_name == "OVER" or state.get("gameStatus") == 2 or my_h <= 0 or opp_h <= 0 or is_stalemate:
            self.metrics["status"] = "Finalizada"
            if not getattr(self, "game_recorded", False):
                self.game_recorded = True
                winner_id = 0
                if is_stalemate:
                    self.log(f"⚠️ [FIM DE JOGO - EMPATE TÉCNICO] {stalemate_reason}!")
                    self.send_chat_log(
                        f"<b>[FIM DE JOGO - EMPATE TÉCNICO]</b> {stalemate_reason}. "
                        f"Partida finalizada como <b>EMPATE</b> para evitar desperdício de processamento.",
                        highlight=True, bg_color="#451a03", text_color="#fbbf24"
                    )
                    winner_id = 0
                elif my_h > 0 and opp_h <= 0:
                    winner_id = self.player_id
                elif opp_h > 0 and my_h <= 0:
                    winner_id = 3 - self.player_id
                elif my_h > opp_h:
                    winner_id = self.player_id
                elif opp_h > my_h:
                    winner_id = 3 - self.player_id

                p1_hp = my_h if self.player_id == 1 else opp_h
                p2_hp = opp_h if self.player_id == 1 else my_h
                p1_lbl = self.get_player_label(1)
                p2_lbl = self.get_player_label(2)

                # ── Avaliação de Partida Inválida (Empate 0 Dano ou Bot Inerte / Punching Bag) ──
                p1_init_hp = self.initial_my_health if self.player_id == 1 else (self.initial_opp_health or 40)
                p2_init_hp = self.initial_opp_health if self.player_id == 1 else (self.initial_my_health or 40)
                p1_dmg_dealt = max(0, p2_init_hp - p2_hp)
                p2_dmg_dealt = max(0, p1_init_hp - p1_hp)
                total_dmg_exchanged = p1_dmg_dealt + p2_dmg_dealt

                is_invalid_match = False
                invalid_reason = ""

                # 1. Empate com zero ou desprezível dano trocado (< 4 de dano trocado no total)
                if winner_id == 0:
                    if total_dmg_exchanged < 4:
                        is_invalid_match = True
                        invalid_reason = "Empate 0 Dano (Mutual Stall)"
                # 2. Bot travou só apanhando (Punching Bag / Bot Inerte)
                elif winner_id in (1, 2):
                    winner_hp = p1_hp if winner_id == 1 else p2_hp
                    winner_init_hp = p1_init_hp if winner_id == 1 else p2_init_hp
                    loser_hp = p2_hp if winner_id == 1 else p1_hp
                    loser_id = 3 - winner_id

                    # Vencedor terminou com vida intacta (sofreu zero de dano)
                    winner_undamaged = (winner_hp >= winner_init_hp)

                    if winner_undamaged and loser_hp <= 0:
                        # Se este bot é o perdedor:
                        if self.player_id == loser_id:
                            if self.attacks_made == 0 or self.damage_dealt == 0 or self.execution_exceptions_count >= 2:
                                if turn >= 5 or self.execution_exceptions_count >= 2:
                                    is_invalid_match = True
                                    invalid_reason = "Bot Inerte (Travou sem atacar / Punching Bag)"
                        # Se este bot é o vencedor:
                        else:
                            # Partida durou múltiplos turnos (>= 6) com oponente sem desferir dano
                            if turn >= 6:
                                is_invalid_match = True
                                invalid_reason = "Bot Oponente Inerte (Punching Bag)"

                if is_invalid_match:
                    self.log(f"⚠️ [PARTIDA ANULADA] {invalid_reason}! Trajetória descartada do ReplayBuffer e ELO protegido.")
                    self.send_chat_log(
                        f"⚠️ <b>[PARTIDA ANULADA]</b> {invalid_reason}. "
                        f"Partida descartada do ReplayBuffer e sem alteração de ELO.",
                        highlight=True, bg_color="#451a03", text_color="#fbbf24"
                    )

                is_vs_human = (getattr(self, "name", "") == "AIMaster_Bot" or "Human_vs_Bot" in str(self.room_id) or str(self.room_id).isdigit())
                is_human_victory = is_vs_human and (winner_id == self.player_id)

                if not is_invalid_match and hasattr(self, "trajectory") and self.trajectory:
                    try:
                        from ai.experience_collector import get_global_buffer
                        from ai.blunder_reviewer import review_trajectory_for_blunders
                        weights, b_stats = review_trajectory_for_blunders(
                            self.trajectory,
                            winner_player_id=winner_id,
                            bot_player_id=self.player_id
                        )
                        if is_human_victory:
                            weights = [float(w) * 3.0 for w in weights]
                            self.log(
                                "🏆 [VITÓRIA CONTRA HUMANO] O Bot AI Master superou o jogador Humano! "
                                "Recompensando todas as decisões da partida com peso amostral amplificado 3.0x no Replay Buffer!"
                            )
                        if b_stats.get("blunders", 0) > 0 or b_stats.get("brilliants", 0) > 0:
                            self.log(
                                f"[PER / BLUNDER REVIEW] Trajetória avaliada: {b_stats.get('blunders', 0)} blunders, "
                                f"{b_stats.get('inaccuracies', 0)} imprecisões, {b_stats.get('brilliants', 0)} viradas. "
                                f"Peso médio amostral: {b_stats.get('avg_weight', 1.0):.2f}"
                            )
                        buf = get_global_buffer(self.buffer_capacity)
                        buf.add_trajectory(self.trajectory, winner_player_id=winner_id, weights=weights)
                        buf.save()
                    except Exception as e:
                        self.log(f"[ERRO BUFFER] {e}")

                if hasattr(self, "equipment_tracker") and self.equipment_tracker.get_events():
                    try:
                        if not is_invalid_match:
                            won = (winner_id == self.player_id)
                            get_equipment_learning_engine().record_match_result(
                                hero_name=self.hero_name,
                                events=self.equipment_tracker.get_events(),
                                won=won,
                            )
                        self.equipment_tracker.clear()
                    except Exception as e:
                        self.log(f"[ERRO EQ STATS] {e}")

                if is_invalid_match:
                    winner_str = f"Anulada ({invalid_reason})"
                elif winner_id == 1:
                    winner_str = p1_lbl
                elif winner_id == 2:
                    winner_str = p2_lbl
                else:
                    winner_str = "Empate"

                if self.role == "host" or is_vs_human or self.player_id == 1:
                    try:
                        p1_d_file = f"logs/{self.room_id}_host_deck.txt"
                        p2_d_file = f"logs/{self.room_id}_join_deck.txt"
                        p1_d = "Humano (Você)" if is_vs_human else getattr(self, "deck_name", self.clean_deck)
                        if not is_vs_human and os.path.exists(p1_d_file):
                            with open(p1_d_file, encoding="utf-8") as f1:
                                p1_d = f1.read().strip()
                        p2_d = getattr(self, "deck_name", self.clean_deck)
                        if os.path.exists(p2_d_file):
                            with open(p2_d_file, encoding="utf-8") as f2:
                                p2_d = f2.read().strip()
                        
                        from stats_manager import update_match_result
                        update_match_result(
                            room_id=self.room_id,
                            p1_deck=p1_d,
                            p2_deck=p2_d,
                            p1_health=p1_hp,
                            p2_health=p2_hp,
                            total_turns=turn,
                            winner_id=winner_id,
                            is_human_p1=is_vs_human,
                            is_invalid_match=is_invalid_match,
                            invalid_reason=invalid_reason
                        )
                        if hasattr(self, "chosen_turn_order") and self.chosen_turn_order and not is_invalid_match:
                            won = (winner_id == self.player_id)
                            get_turn_order_learner().record_match_result(self.player_name or self.deck_url, self.chosen_turn_order, won)
                    except Exception as e:
                        self.log(f"[ERRO STATS] {e}")

                    # LOG DE DESTAQUE DO VENCEDOR (Claro e Visível):
                    self.log("════════════════════════════════════════════════════════════")
                    self.log(f"🏆 [FIM DE JOGO] VENCEDOR: {winner_str.upper()}!")
                    self.log(f"📊 [PLACAR FINAL] {p1_lbl}: {p1_hp} HP  x  {p2_lbl}: {p2_hp} HP  (Total: {turn} turnos)")
                    self.log("════════════════════════════════════════════════════════════")

                    try:
                        summary_text = (
                            f"═══════════════════════════════════════════════\n"
                            f"🏆 RESULTADO DA PARTIDA: {self.room_id}\n"
                            f"═══════════════════════════════════════════════\n"
                            f"• Vencedor: {winner_str} (Jogador {winner_id})\n"
                            f"• {p1_lbl}: {p1_hp} HP\n"
                            f"• {p2_lbl}: {p2_hp} HP\n"
                            f"• Duração: {turn} turnos\n"
                            f"• Decisões Coletadas para Treino: {len(self.trajectory)} amostras\n"
                            f"═══════════════════════════════════════════════\n"
                        )
                        with open(f"logs/{self.room_id}_summary.log", "w", encoding="utf-8") as f:
                            f.write(summary_text)
                    except Exception as e:
                        self.log(f"[ERRO SUMMARY] {e}")

        with open(f"logs/{self.room_id}_{self.player_name}.json", "w") as f:
            json.dump({"metrics": self.metrics}, f)
            
        if state.get("havePriority") and self.metrics["status"] != "Finalizada":
            try:
                self.decide_and_act(state)
            except Exception as e:
                self.execution_exceptions_count += 1
                self.log(f"[ERRO DECIDE_AND_ACT] {e}")
                try:
                    self.send_action(mode=99, button_input="")
                except Exception:
                    pass

    def send_action(self, mode=99, card_id="", button_input="", chk_count=0, chk_input=None, input_text=""):
        return self.api.process_input(
            game_name=self.game_id,
            player_id=self.player_id,
            auth_key=self.auth_key,
            mode=mode,
            card_id=card_id,
            button_input=button_input,
            chk_count=chk_count,
            chk_input=chk_input,
            input_text=input_text
        )

    def _score_choice_candidate(self, candidate, turn_phase: str = "", state: dict = None, popup: dict = None) -> float:
        """Pontua um candidato para escolha múltipla ou alvo de primeira tentativa."""
        c_name = ""
        c_mode = 0
        c_override = ""
        c_label = ""
        if isinstance(candidate, dict):
            c_name = str(candidate.get("buttonInput") or candidate.get("caption") or candidate.get("cardNumber") or candidate.get("name") or "").lower()
            c_mode = int(candidate.get("mode", 0) or 0)
            c_override = str(candidate.get("actionDataOverride", "")).lower()
            c_label = str(candidate.get("label", "")).lower()
        else:
            c_name = str(candidate).lower()

        # Pass tem prioridade mínima a menos que seja forçado
        if c_name in ("pass", "pass priority", "cancel") or c_mode == 10000:
            return -100.0

        state = state or {}
        popup_obj = popup if isinstance(popup, dict) else {}
        p_title = str(popup_obj.get("title") or popup_obj.get("caption") or popup_obj.get("text") or "").lower()
        p_prompt = str(state.get("promptText") or "").lower()

        # Contexto de Sinking / Bottom / Discard
        is_sink = any(k in p_title or k in p_prompt for k in ["sink", "bottom", "providence"])
        is_self_discard = ("DISCARD" in turn_phase and "HAND" in turn_phase) or "discard" in p_title or "discard" in p_prompt

        # Identificar se o candidato é do Arsenal
        arsenal = state.get("playerArsenal") or state.get("playerArse") or []
        arsenal_names = [str(a.get("cardNumber", a.get("name", "")) if isinstance(a, dict) else a).lower() for a in arsenal]
        is_from_arsenal = (
            "ars" in c_override
            or "arsenal" in c_label
            or (c_name in arsenal_names and len(arsenal_names) > 0)
        )

        # Checagem de ameaça ao Arsenal (ex: Command and Conquer, Leave No Witnesses)
        active_chain = state.get("activeChainLink") or {}
        incoming_name = str(active_chain.get("cardNumber", "")).lower()
        is_arsenal_threat = len(arsenal) > 0 and any(k in incoming_name for k in [
            "command_and_conquer", "leave_no_witnesses", "wreck_havoc", "eradicate", "humble", "righteous_cleansing"
        ])

        # Se for escolha de afundar (Crown of Providence / Sink Below) e o Arsenal está em perigo iminente:
        # A carta do Arsenal DEVE ser afundada imediatamente para salvá-la e comprar uma nova carta!
        if is_sink and is_arsenal_threat:
            if is_from_arsenal:
                return 150.0  # Protege o Arsenal salvando a carta no deck e comprando 1 nova
            else:
                return -50.0  # Não afunda da mão se precisa salvar o Arsenal

        score = 0.0
        c_info = self.policy_engine.extract_card_info({"cardNumber": c_name}) if hasattr(self, "policy_engine") else {}
        score += float(c_info.get("power", 0))

        # Prioridades específicas por sinergia e valor
        if any(k in c_name for k in ["leave_no_witnesses", "codex_of_frailty", "pulsewave", "conqueror_of_the_high_seas"]):
            score += 25.0
        elif any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy"]):
            score += 20.0
        elif any(k in c_name for k in ["boom_grenade", "convection_amplifier", "penetration_script", "foundry_heart"]):
            score += 18.0
        elif any(k in c_name for k in ["riggermortis", "zenith_blade", "edict_of_steel", "sink_below"]):
            score += 15.0
        elif c_info.get("pitch") == 1:
            score += 6.0
        elif c_info.get("has_go_again"):
            score += 5.0

        # Se for para descartar ou afundar (e não era para salvar o Arsenal):
        # Inverte o score para descartar/afundar a PIOR carta (ciclando e preservando peças nobres)
        if is_self_discard or is_sink:
            # Nunca afundar o Arsenal se ele não estava sob ameaça
            if is_from_arsenal and is_sink:
                return -200.0
            return -score

        return score

    def _rank_choice_candidates(self, candidates: list, turn_phase: str = "", state: dict = None, popup: dict = None) -> list:
        """Ordena uma lista de candidatos do mais recomendado ao menos recomendado."""
        return sorted(candidates, key=lambda c: self._score_choice_candidate(c, turn_phase=turn_phase, state=state, popup=popup), reverse=True)

    def decide_and_act(self, state: dict):
        # Compatibilidade com backend Talishar (playerArse -> playerArsenal, theirArse -> theirArsenal)
        if "playerArse" in state and "playerArsenal" not in state:
            state["playerArsenal"] = state.get("playerArse") or []
        if "theirArse" in state and "theirArsenal" not in state:
            state["theirArsenal"] = state.get("theirArse") or []
        if "theirArsenal" in state and "opponentArsenal" not in state:
            state["opponentArsenal"] = state.get("theirArsenal") or []

        tp_raw = state.get("turnPhase", "M")
        if isinstance(tp_raw, dict):
            turn_phase = str(tp_raw.get("turnPhase", "M"))
        else:
            turn_phase = str(tp_raw) if tp_raw else "M"
            
        turn_num = state.get("turnNo", state.get("currentTurn", 1))
        
        if not hasattr(self, "unpayable_cards_turn"):
            self.unpayable_cards_turn = {}
        turn_key = f"{turn_num}_{self.player_id}"
        if turn_key not in self.unpayable_cards_turn:
            self.unpayable_cards_turn = {turn_key: set()}
            self.reaction_attempts = {}
        unpayable_set = self.unpayable_cards_turn[turn_key]

        # Gravar estado no Replay Buffer para aprendizado por reforço
        try:
            import numpy as np
            from ai.model import FaBPolicyValueNetwork
            s_vec = FaBPolicyValueNetwork.extract_state_vector(state, self.player_id)
            p_dist = np.zeros(32, dtype=np.float32)
            p_dist[0] = 1.0
            b_eval = self.evaluate_board_state(state)
            self.trajectory.append((s_vec, p_dist, self.player_id, b_eval))
        except Exception:
            pass
        
        popup = state.get("popup", {})
        prompt_buttons = []
        if isinstance(state.get("playerPrompt"), dict):
            prompt_buttons = state.get("playerPrompt", {}).get("buttons", []) or state.get("playerPrompt", {}).get("promptButtons", [])
        elif isinstance(state.get("promptButtons"), list):
            prompt_buttons = state.get("promptButtons", [])
        elif isinstance(state.get("buttons"), list):
            prompt_buttons = state.get("buttons", [])

        # Rastrear histórico recente de fases e ações para detectar ciclos oscilantes (ex: D -> YESNO -> P -> D)
        if not hasattr(self, "recent_phases"):
            self.recent_phases = []
            
        phase_sig = f"{turn_phase}_{getattr(self, 'last_attempted_play', '')}"
        self.recent_phases.append(phase_sig)
        if len(self.recent_phases) > 20:
            self.recent_phases.pop(0)

        # Guarda Anti-Loop: Evita ficar preso no mesmo estado
        state_sig = (turn_num, turn_phase, len(state.get("playerHand", [])), state.get("playerHealth"), state.get("opponentHealth"))
        if not hasattr(self, "last_state_sig"):
            self.last_state_sig = None
            self.consecutive_same_state = 0
            
        if self.last_state_sig == state_sig:
            self.consecutive_same_state += 1
        else:
            self.last_state_sig = state_sig
            self.consecutive_same_state = 0

        is_cyclic_loop = self.recent_phases.count(phase_sig) >= 3
        is_stuck_state = self.consecutive_same_state > 4

        if is_stuck_state or is_cyclic_loop:
            if hasattr(self, "last_attempted_play") and self.last_attempted_play:
                unpayable_set.add(self.last_attempted_play)

            # Acumula contador para evitar loop eterno de anti-loop
            self._anti_loop_streak = getattr(self, "_anti_loop_streak", 0) + 1

            if turn_phase in ("DOCRANK", "YESNO"):
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ({turn_phase}) -> Forçando NO (Mode 20)")
                self.send_action(mode=20, button_input="NO")
                self.recent_phases.clear()
                self.consecutive_same_state = 0
                time.sleep(0.15)
                return True

            if turn_phase in ("MAYCHOOSEMULTIZONE", "MAYMULTICHOOSETEXT"):
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ({turn_phase}) -> Pass (Mode 99)")
                self.send_action(mode=99, button_input="PASS")
                self.recent_phases.clear()
                self.consecutive_same_state = 0
                time.sleep(0.15)
                return True

            if turn_phase in ("CHOOSEMULTIZONE", "MULTICHOOSE", "MULTICHOOSEHAND"):
                # Se já falhou submeter vazio consecutivamente, força seleção do índice 0
                if self._anti_loop_streak >= 3:
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ({turn_phase}) -> Forçando índice 0 (Mode 19)")
                    self.send_action(mode=19, chk_count=1, chk_input=["0"])
                    self._anti_loop_streak = 0
                else:
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ({turn_phase}) -> Submetendo vazio (Mode 19)")
                    self.send_action(mode=19, chk_count=0, chk_input=[])
                self.recent_phases.clear()
                self.consecutive_same_state = 0
                time.sleep(0.15)
                return True

            # MULTICHOOSETEXT: fase de seleção de texto obrigatória (ex: Fabricate do Teklovossen).
            # O servidor NÃO aceita PASS (mode=99); deve-se enviar mode=19 selecionando pelo menos 1 item.
            if turn_phase == "MULTICHOOSETEXT":
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop (MULTICHOOSETEXT) -> Selecionando índice 0 (Mode 19)")
                self.send_action(mode=19, chk_count=1, chk_input=["0"])
                self.recent_phases.clear()
                self.consecutive_same_state = 0
                time.sleep(0.15)
                return True

            fallback_mode = 10000 if turn_phase in ("P", "PAYGOLDORPITCH") else 99
            chosen_btn = None
            if turn_phase in ("P", "PAYGOLDORPITCH"):
                for b in prompt_buttons:
                    if "cancel" in str(b.get("caption", "")).lower() or b.get("mode") == 10000:
                        chosen_btn = b
                        break
            else:
                for b in prompt_buttons:
                    cap = str(b.get("caption", "")).lower()
                    if ("pass" in cap or "done" in cap or "ok" in cap or b.get("mode") in (99, 101)) and "undo" not in cap:
                        chosen_btn = b
                        break

            if chosen_btn:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ({turn_phase}) -> {chosen_btn.get('caption', 'Pass')}")
                self.send_action(mode=chosen_btn.get("mode", fallback_mode), button_input=str(chosen_btn.get("buttonInput", "")))
            else:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ({turn_phase}) -> Passando/Cancelando (Mode {fallback_mode})")
                self.send_action(mode=fallback_mode, button_input="")
            self.recent_phases.clear()
            self.consecutive_same_state = 0
            time.sleep(0.15)
            return True

        # 0. Tratar INPUTCARDNAME
        if turn_phase == "INPUTCARDNAME":
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Nomeou carta (INPUTCARDNAME) -> 'Sink Below'")
            self.send_action(mode=30, input_text="Sink Below")
            time.sleep(0.002)
            return True

        # 1. Tratar Decisões de Crank e YESNO / Modal Triggers
        if turn_phase in ("DOCRANK", "YESNO"):
            if turn_phase == "DOCRANK":
                import random
                is_my_turn = state.get("amIActivePlayer", False) or (state.get("turnPlayer") == self.player_id)
                if is_my_turn:
                    choice = "YES" if random.random() < 0.75 else "NO"
                    reason = "Exploração de Tempo (+1 AP)" if choice == "YES" else "Estratégia de Setup (Manter Item)"
                else:
                    choice = "NO" if random.random() < 0.90 else "YES"
                    reason = "Turno Oponente (Preservar Item)" if choice == "NO" else "Exploração"
                    
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Decisão Crank ({reason}) -> {choice}")
                self.send_action(mode=20, button_input=choice)
                time.sleep(0.002)
                return True
            else:
                floating_res, total_res = self.policy_engine.calculate_available_resources(state)
                hand = state.get("playerHand", [])
                
                # Se não temos recursos ou cartas de pitch suficientes para custos adicionais, responder NO
                if total_res < 2 and len(hand) <= 1:
                    choice = "NO"
                    reason = "Recursos Insuficientes"
                elif hasattr(self, "last_attempted_play") and self.last_attempted_play in unpayable_set:
                    choice = "NO"
                    reason = "Carta Bloqueada Anti-Loop"
                else:
                    choice = "YES"
                    reason = "Aceito"
                    
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Decisão YESNO ({reason}) -> {choice}")
                self.send_action(mode=20, button_input=choice)
                time.sleep(0.002)
                return True

        # 2. Tratar Popups Modais e Buscas no Deck / Zonas
        if isinstance(popup, dict) and popup.get("active"):
            p_data = popup.get("popup", {})
            p_type = p_data.get("type", "")
            
            if p_type in ("YESNO", "DOCRANK"):
                import random
                is_my_turn = state.get("amIActivePlayer", False) or (state.get("turnPlayer") == self.player_id)
                choice = "YES" if (is_my_turn and random.random() < 0.75) else "NO"
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Popup {p_type} -> Respondeu {choice}")
                self.send_action(mode=20, button_input=choice)
                time.sleep(0.002)
                return True
                
            p_buttons = p_data.get("buttons", [])
            if p_buttons:
                btn = p_buttons[0]
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Popup Botão -> {btn.get('caption', 'OK')}")
                self.send_action(mode=btn.get("mode", 17), button_input=btn.get("buttonInput", ""))
                time.sleep(0.002)
                return True
                
            cards_arr = p_data.get("cardsArray", [])
            if cards_arr:
                best_card = cards_arr[0]
                best_idx = 0
                for idx, c in enumerate(cards_arr):
                    cid = str(c.get("cardNumber", "")).lower()
                    if any(w in cid for w in ["pounder", "core", "amplifier", "grenade", "processor", "mainline", "item"]):
                        best_card = c
                        best_idx = idx
                        break
                        
                c_action = best_card.get("action", 16)
                c_id = best_card.get("actionDataOverride", best_card.get("cardNumber", str(best_idx)))
                
                form_opts = popup.get("formOptions", {})
                if form_opts.get("mode") == 19 or p_type in ("CHOOSEMULTIZONE", "MAYCHOOSEMULTIZONE"):
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Escolheu {best_card.get('cardNumber')} no Deck (Mode 19 / Index {best_idx})")
                    self.send_action(mode=19, chk_count=1, chk_input=[str(best_idx)])
                else:
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Escolheu {best_card.get('cardNumber')} no Deck (Mode {c_action} / ID {c_id})")
                    self.send_action(mode=c_action, card_id=c_id, button_input=str(c_id))
                    
                time.sleep(0.002)
                return True

        # 3. Tratar Escolhas de Zonas / Gatilhos (CHOOSECARD, CHOOSETRIGGERS, BUTTONINPUT, etc.)
        if turn_phase in ("BUTTONINPUT", "BUTTONINPUTNOPASS", "CHOOSEARCANE", "CHOOSEFIRSTPLAYER", "CHOOSETRIGGERS"):
            btn_input = prompt_buttons[0].get("buttonInput", "0") if prompt_buttons else "0"
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Gatilho/Escolha -> {turn_phase}")
            self.send_action(mode=17, button_input=str(btn_input))
            time.sleep(0.002)
            return True

        if turn_phase in ("CHOOSECARD", "CHOOSECARDID", "MAYCHOOSECARD", "CHOOSEZONE", "CHOOSEDECK", "MAYCHOOSEDECK", "CHOOSEHAND", "MAYCHOOSEHAND", "CHOOSEDISCARD", "MAYCHOOSEDISCARD", "CHOOSEPERMANENT", "MAYCHOOSEPERMANENT", "CHOOSEMYSOUL", "MAYCHOOSEMYSOUL", "CHOOSETARGET"):
            p_data = popup.get("data", popup) if isinstance(popup, dict) else {}
            cards_arr = p_data.get("cardsArray", []) if isinstance(p_data, dict) else []
            if not cards_arr and "DISCARD" in turn_phase:
                cards_arr = state.get("playerDiscard", [])
            elif not cards_arr and "HAND" in turn_phase:
                cards_arr = state.get("playerHand", [])

            best_card_id = "0"
            best_btn_inp = "0"
            if cards_arr:
                best_score = -9999.0
                for idx, c_item in enumerate(cards_arr):
                    score = self._score_choice_candidate(c_item, turn_phase=turn_phase, state=state, popup=popup)
                    if score > best_score:
                        best_score = score
                        best_card_id = str(c_item.get("actionDataOverride", c_item.get("cardNumber", str(idx)))) if isinstance(c_item, dict) else str(idx)
                        best_btn_inp = best_card_id

            self.log(f"[AÇÃO JOGADOR {self.player_id}] Seleção Inteligente de Alvo/Zona -> {turn_phase} (CardID: {best_card_id})")
            self.send_action(mode=16, card_id=best_card_id, button_input=best_btn_inp)
            time.sleep(0.002)
            return True

        if turn_phase in ("MAYCHOOSEMULTIZONE", "CHOOSEMULTIZONE", "MULTICHOOSE", "MULTICHOOSEHAND"):
            p_data = popup.get("data", popup) if isinstance(popup, dict) else {}
            cards_arr = p_data.get("cardsArray", []) if isinstance(p_data, dict) else []
            hand = state.get("playerHand", [])
            
            form_opts = popup.get("formOptions", {}) if isinstance(popup, dict) else {}
            max_cnt = form_opts.get("maxCount", len(cards_arr) if cards_arr else len(hand))
            
            if max_cnt == 0 or (not cards_arr and not hand):
                if turn_phase == "MAYCHOOSEMULTIZONE":
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Escolha Opcional ({turn_phase}) Sem opções -> Pass (Mode 99)")
                    self.send_action(mode=99, button_input="PASS")
                else:
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Multi-Seleção (Sem opções / Max 0) -> Confirmar vazio (Mode 19)")
                    self.send_action(mode=19, chk_count=0, chk_input=[])
                time.sleep(0.002)
                return True

            # Heurística Tática: Selecionar a melhor carta de primeira tentativa
            best_idx = 0
            target_list = cards_arr if cards_arr else hand
            if len(target_list) > 1:
                best_score = -9999.0
                for c_idx, c_item in enumerate(target_list):
                    score = self._score_choice_candidate(c_item, turn_phase=turn_phase, state=state, popup=popup)
                    if score > best_score:
                        best_score = score
                        best_idx = c_idx

            chk_cnt = 1
            chk_inp = [str(best_idx)]

            btn_inp = "0"
            if prompt_buttons:
                for b in prompt_buttons:
                    if b.get("mode") == 19 or "submit" in str(b.get("caption", "")).lower() or "ok" in str(b.get("caption", "")).lower():
                        btn_inp = str(b.get("buttonInput", "0"))
                        break
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Multi-Seleção -> {turn_phase} (Mode: 19, Count: {chk_cnt}, Pick: {chk_inp})")
            self.send_action(mode=19, button_input=btn_inp, chk_count=chk_cnt, chk_input=chk_inp)
            time.sleep(0.002)
            return True

        # Handler dedicado para MULTICHOOSETEXT / MAYMULTICHOOSETEXT
        # Usado por cartas com efeito de Fabricate (Teklovossen, Dash IO), escolhas de efeitos de texto, etc.
        if turn_phase in ("MULTICHOOSETEXT", "MAYMULTICHOOSETEXT"):
            popup_obj = popup if isinstance(popup, dict) else {}
            form_opts = popup_obj.get("formOptions", {}) if isinstance(popup_obj, dict) else {}
            min_no = int(form_opts.get("minNo", 0))
            max_no = int(form_opts.get("maxNo", form_opts.get("maxCount", 1)))

            multi_text = (
                state.get("multiChooseText")
                or popup_obj.get("multiChooseText")
                or (popup_obj.get("popup", {}) or {}).get("multiChooseText")
                or []
            )

            is_optional = (turn_phase == "MAYMULTICHOOSETEXT") or (min_no == 0)
            if is_optional and not multi_text:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] {turn_phase} Opcional/Sem itens -> Pass (Mode 99)")
                self.send_action(mode=99, button_input="PASS")
                time.sleep(0.002)
                return True

            n_select = max(1, min_no) if not is_optional else min(1, max_no)
            n_available = len(multi_text) if multi_text else max(1, n_select)
            n_select = min(n_select, n_available)

            # Avaliação semântica e inteligente das opções de texto na PRIMEIRA tentativa
            def _score_text_option(opt_obj) -> float:
                raw_text = str(opt_obj.get("text", opt_obj.get("caption", opt_obj.get("label", opt_obj))) if isinstance(opt_obj, dict) else opt_obj).lower()
                s = 0.0
                if any(w in raw_text for w in ["evo", "equipment", "item", "pounder", "crank"]):
                    s += 15.0
                if any(w in raw_text for w in ["draw", "action point", "resource", "steam", "counter"]):
                    s += 12.0
                if any(w in raw_text for w in ["damage", "attack", "overpower", "dominate", "piercing"]):
                    s += 10.0
                if any(w in raw_text for w in ["gold", "silver", "treasure", "token"]):
                    s += 8.0
                if any(w in raw_text for w in ["opt", "look", "search"]):
                    s += 5.0
                return s

            scored_indices = sorted(range(len(multi_text)), key=lambda i: _score_text_option(multi_text[i]), reverse=True) if multi_text else list(range(n_select))
            chk = [str(i) for i in scored_indices[:n_select]]
            self.log(f"[AÇÃO JOGADOR {self.player_id}] {turn_phase} -> Selecionando opções inteligentes {chk} (Mode 19, minNo={min_no})")
            self.send_action(mode=19, chk_count=n_select, chk_input=chk)
            time.sleep(0.002)
            return True


        if turn_phase in ("CHOOSENUMBER", "DYNPITCH", "NUMBERINPUT"):
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Entrada Numérica (Custo/Valor X) -> {turn_phase}")
            self.send_action(mode=7, button_input="0")
            time.sleep(0.002)
            return True

        if turn_phase in ("CHOOSETOP", "CHOOSEBOTTOM", "HANDTOPBOTTOM"):
            hand = state.get("playerHand", [])
            card_sel = hand[0].get("cardNumber", "") if hand else ""
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Reordenação -> {turn_phase}")
            self.send_action(mode=12 if turn_phase == "CHOOSETOP" else 13, button_input=card_sel)
            time.sleep(0.002)
            return True

        # 4. Se for Fase de Pitch (P / PDECK / PAYGOLDORPITCH / CHOOSEHANDCANCEL)
        if turn_phase in ("P", "PDECK", "PAYGOLDORPITCH", "CHOOSEHANDCANCEL"):
            if turn_phase == "PDECK":
                pitch = state.get("playerPitch", [])
                pitch_card = "0"
                if pitch:
                    p0 = pitch[0]
                    pitch_card = p0.get("cardNumber", p0.get("cardID", "0")) if isinstance(p0, dict) else str(p0)
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Bottom do Pitch (PDECK -> {pitch_card})")
                self.send_action(mode=6, card_id=str(pitch_card), button_input=str(pitch_card))
                time.sleep(0.002)
                return True

            pitch_choice = self.policy_engine.select_best_pitch_card(state)
            if pitch_choice:
                p_idx, p_name, p_mode = pitch_choice
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Pitch Tático -> {p_name} (Index: {p_idx})")
                self.send_action(mode=p_mode, card_id=str(p_idx), button_input=p_name)
                time.sleep(0.002)
                return True

            if hasattr(self, "last_attempted_play") and self.last_attempted_play:
                unpayable_set.add(self.last_attempted_play)

            cancel_btn = None
            for b in prompt_buttons:
                cap = str(b.get("caption", "")).lower()
                if "cancel" in cap or b.get("mode") == 10000:
                    cancel_btn = b
                    break

            if cancel_btn:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Botão Pitch/Cancel -> {cancel_btn.get('caption')} (Mode {cancel_btn.get('mode')})")
                self.send_action(mode=cancel_btn.get("mode", 10000), button_input=str(cancel_btn.get("buttonInput", "")))
                time.sleep(0.002)
                return True

            self.log(f"[AÇÃO JOGADOR {self.player_id}] Sem cartas para pitch -> Cancelar (Mode 10000)")
            self.send_action(mode=10000, button_input="")
            time.sleep(0.002)
            return True

        # 5. Se for Fase de Defesa / Bloqueio (B)
        if turn_phase == "B":
            chain_desc = self.get_combat_chain_desc(state)
            if chain_desc and getattr(self, "last_logged_combat_attack", None) != (turn_num, chain_desc):
                self.last_logged_combat_attack = (turn_num, chain_desc)
                self.log(f"[COMBAT CHAIN] ⚔️ Ataque em Andamento: {chain_desc}")

            if not hasattr(self, "declared_blocks_link"):
                self.declared_blocks_link = set()

            # ── Telemetria de Plano de Turno e Pivot ───────────────
            current_plan = self.policy_engine.strategy.analyze_turn_plan(state)
            if getattr(self, "last_logged_def_plan", None) != (turn_num, current_plan.plan_type):
                self.last_logged_def_plan = (turn_num, current_plan.plan_type)
                plan_badge = f"<b>[Turno {turn_num}] 🎯 Plano de Defesa</b> -> <b>{current_plan.plan_type}</b> ({current_plan.reason})"
                self.send_chat_log(plan_badge, highlight=True, bg_color="#0f172a", text_color="#38bdf8")
                self.log(f"[PLANO DE DEFESA] 🎯 Estratégia: {current_plan.plan_type} - {current_plan.reason}")

            chosen_blocks = self.policy_engine.select_defense_blocks(state)
            unblocked = [b for b in chosen_blocks if (b[3], str(b[1])) not in self.declared_blocks_link]
            if unblocked:
                b_idx, b_id, b_name, b_action = unblocked[0]
                self.declared_blocks_link.add((b_action, str(b_id)))
                if hasattr(self, "equipment_tracker"):
                    equip_names = {str(eq.get("cardNumber", "")).lower() for eq in state.get("playerEquipment", []) if isinstance(eq, dict)}
                    if str(b_name).lower() in equip_names:
                        self.equipment_tracker.track_block(
                            hero=self.hero_name,
                            eq_name=b_name,
                            turn=turn_num,
                        )
                chat_msg = f"<b>[Turno {turn_num}] 🛡️ Bloqueio Tático</b> -> <b>{b_name}</b> (Defesa Otimizada)"
                self.send_chat_log(chat_msg, highlight=True, bg_color="#1e1b4b", text_color="#c084fc")
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Bloqueio Tático -> {b_name} (ID: {b_id}, Mode: {b_action})")
                self.send_action(mode=b_action, card_id=str(b_id), button_input=b_name)
                time.sleep(0.002)
                return True

            self.declared_blocks_link = set()
            pass_btn = None
            for b in prompt_buttons:
                cap = str(b.get("caption", "")).lower()
                if ("pass" in cap or b.get("mode") in (99, 101)) and "undo" not in cap:
                    pass_btn = b
                    break

            if pass_btn:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Passou Bloqueio ({pass_btn.get('caption', 'Pass')})")
                self.send_action(mode=pass_btn.get("mode", 99), button_input=str(pass_btn.get("buttonInput", "")))
            else:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Passou Bloqueio (Mode 99)")
                self.send_action(mode=99, button_input="")
            time.sleep(0.002)
            return True

        # 6. Se for Fase de Reação de Ataque (A) ou Defesa (D) ou Instantâneo
        if turn_phase in ("A", "D", "INSTANT"):
            chain_desc = self.get_combat_chain_desc(state)
            if chain_desc and getattr(self, "last_logged_combat_attack", None) != (turn_num, chain_desc):
                self.last_logged_combat_attack = (turn_num, chain_desc)
                self.log(f"[COMBAT CHAIN] ⚔️ Ataque em Andamento: {chain_desc}")

            hand = state.get("playerHand", [])
            
            if not hasattr(self, "reaction_attempts"):
                self.reaction_attempts = {}

            # 6a. Reações / Instantâneos via Mão
            turn_player = state.get("turnPlayer", 1)
            is_defending = (turn_player != self.player_id)
            is_attacking = (turn_player == self.player_id)

            for idx, c in enumerate(hand):
                c_action = c.get("action", 0)
                c_name = c.get("cardNumber", "")
                
                attempts = self.reaction_attempts.get(c_name, 0)
                if attempts >= 2:
                    unpayable_set.add(c_name)
                    
                if c_action > 0 and c_name not in unpayable_set:
                    c_low = str(c_name).lower()
                    # ── Poda Estrita de Instants Ofensivos na Defesa ──
                    # Cartas de ataque puro, setup ou buffs ofensivos (ex: Astral Bridge, Thunderous Retort, Lightning Press)
                    # NUNCA devem ser disparadas cegamente no turno do oponente enquanto ele ataca/ativa habilidades!
                    if is_defending:
                        is_offensive_instant = any(k in c_low for k in [
                            "astral_bridge", "thunderous_retort", "lightning_press",
                            "flowstate", "consign_to_cosmos", "comet_storm", "second_strike",
                            "razor_reflex", "ironsong_response", "pummel", " ancestral"
                        ])
                        if is_offensive_instant:
                            continue

                    info = self.policy_engine.extract_card_info(c)
                    floating_res, total_res = self.policy_engine.calculate_available_resources(state)
                    remaining_pitch = total_res - info["pitch"]
                    if remaining_pitch >= info["cost"]:
                        c_id = c.get("actionDataOverride", str(idx))
                        if c_action == 27:
                            c_id = str(idx)
                        self.last_attempted_play = c_name
                        self.reaction_attempts[c_name] = attempts + 1
                        chat_msg = f"<b>[Turno {turn_num}] ⚡ Reação Tática</b> -> <b>{c_name}</b> (Modo {c_action})"
                        self.send_chat_log(chat_msg, highlight=True, bg_color="#14532d", text_color="#4ade80")
                        self.log(f"[AÇÃO JOGADOR {self.player_id}] Jogou Reação/Instant (Mão) -> {c_name}")
                        self.send_action(mode=c_action, card_id=c_id, button_input=c_name)
                        time.sleep(0.002)
                        return True

            # 6b. Reações / Instantâneos via Equipamentos (Snapdragon Scalers, Boots of Omniward, etc.)
            equip = state.get("playerEquipment", [])
            active_chain = state.get("activeChainLink") or {}
            opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
            arcane_dmg = int(state.get("arcaneDamage", 0) or 0)
            my_hp = int(state.get("playerHealth", 20))

            for eq_idx, eq in enumerate(equip):
                if not isinstance(eq, dict):
                    continue
                eq_action = int(eq.get("action", 0))
                eq_name = str(eq.get("cardNumber", "")).lower()
                slot = str(eq.get("slot", "")).lower()
                if slot == "hero" or eq.get("isBroken") or eq.get("onChain"):
                    continue

                attempts = self.reaction_attempts.get(eq_name, 0)
                if attempts >= 2:
                    unpayable_set.add(eq_name)

                if eq_action > 0 and eq_name not in unpayable_set:
                    # ── Poda 1: Equipamentos de Prevenção / Defesa (Boots of Omniward, Ward, Barrier, Prevent) ──
                    is_prevention_eq = any(k in eq_name for k in ["boots_of_omni", "omniward", "barrier", "ward", "prevent", "spellvoid"])
                    if is_prevention_eq:
                        # NUNCA ativar no vazio quando não há dano físico ou arcano sendo causado!
                        if opp_power <= 0 and arcane_dmg <= 0:
                            continue
                        # Se for nosso turno de ataque e não há dano arcano contra nós, não queima prevenção
                        if is_attacking and arcane_dmg <= 0:
                            continue
                        # Boots of Omniward é destruída ao ativar. Se HP alto e sem dano crítico/on-hit, poupar!
                        if "omniward" in eq_name:
                            incoming_name = str(active_chain.get("cardNumber", "")).lower()
                            has_threat = any(oh in incoming_name for oh in ["command_and_conquer", "red_in_the_ledger", "snatch", "mask", "leave_no_witnesses", "crush"])
                            if my_hp > 15 and not has_threat and (my_hp - opp_power) > 10:
                                continue

                    # ── Poda 2: Reações Ofensivas de Ataque (Snapdragon Scalers, Flick Knives) ──
                    if "snapdragon_scalers" in eq_name:
                        if not is_attacking:
                            continue
                        # Se o ataque já possui go again, não gasta Snapdragon
                        if active_chain.get("hasGoAgain") or active_chain.get("goAgain"):
                            continue
                        # Se não há mais cartas ou ações em mãos, não desperdiça
                        if not hand:
                            continue
                    elif "flick_knives" in eq_name:
                        if not is_attacking:
                            continue

                    # ── Poda 3: Validação de Pontuação Semântica da Estratégia ──
                    eq_score = self.policy_engine.strategy.evaluate_equipment_ability(state, eq)
                    if eq_score <= 0.0 and not (is_prevention_eq and (opp_power > 0 or arcane_dmg > 0)):
                        continue

                    eq_cost = self.policy_engine.get_weapon_cost(eq_name, eq, state)
                    floating_res, total_res = self.policy_engine.calculate_available_resources(state)
                    if total_res >= eq_cost:
                        eq_id = eq.get("actionDataOverride", str(eq_idx))
                        self.last_attempted_play = eq_name
                        self.reaction_attempts[eq_name] = attempts + 1
                        chat_msg = f"<b>[Turno {turn_num}] ⚡ Reação de Equipamento</b> -> <b>{eq_name}</b> (Modo {eq_action})"
                        self.send_chat_log(chat_msg, highlight=True, bg_color="#14532d", text_color="#4ade80")
                        self.log(f"[AÇÃO JOGADOR {self.player_id}] Ativou Reação/Instant (Equipamento) -> {eq_name} (ID: {eq_id}, Custo: {eq_cost})")
                        self.send_action(mode=eq_action, card_id=str(eq_id), button_input=eq_name)
                        time.sleep(0.002)
                        return True

            pass_btn = None
            for b in prompt_buttons:
                cap = str(b.get("caption", "")).lower()
                if "pass" in cap or "ok" in cap or "done" in cap or b.get("mode") in (99, 100, 101):
                    pass_btn = b
                    break

            if pass_btn:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Passou Reação ({pass_btn.get('caption', 'Pass')})")
                self.send_action(mode=pass_btn.get("mode", 99), button_input=str(pass_btn.get("buttonInput", "")))
            else:
                self.send_action(mode=99, button_input="")
            time.sleep(0.002)
            return True

        # 7. Se for Fase de Arsenal (ARS)
        if turn_phase == "ARS":
            ars_choice = self.policy_engine.select_arsenal_card(state)
            if ars_choice:
                c_name, c_id = ars_choice
                chat_msg = f"<b>[Turno {turn_num}] 📥 Arsenal Estratégico</b> -> <b>{c_name}</b>"
                self.send_chat_log(chat_msg, highlight=True, bg_color="#312e81", text_color="#818cf8")
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Colocou no Arsenal -> {c_name}")
                self.send_action(mode=4, card_id=str(c_id), button_input=str(c_id))
                time.sleep(0.002)
                return True
            self.send_action(mode=99, button_input="")
            time.sleep(0.002)
            return True

        # 8. Se for Fase Principal (M, STARTTURN, RESOLUTIONSTEP)
        is_my_turn = bool(state.get("amIActivePlayer", False)) or (str(state.get("turnPlayer", "")) == str(self.player_id)) or (str(state.get("playerID", "")) == str(state.get("turnPlayer", "")))
        try:
            player_ap = int(state.get("playerAP", state.get("actionPoints", state.get("resources", {}).get("actionPoints", 1))))
        except Exception:
            player_ap = 1

        has_active_teklo = (getattr(self, "teklo_ability_active_turn", -1) == turn_num)
        if has_active_teklo:
            state["teklo_ability_active"] = True

        if is_my_turn and turn_phase in ("M", "STARTTURN", "RESOLUTIONSTEP"):
            if player_ap > 0 or has_active_teklo:
                # ── Telemetria de Plano de Turno e Ataque ──────────────
                current_plan = self.policy_engine.strategy.analyze_turn_plan(state)
                if getattr(self, "last_logged_atk_plan", None) != (turn_num, current_plan.plan_type):
                    self.last_logged_atk_plan = (turn_num, current_plan.plan_type)
                    plan_badge = f"<b>[Turno {turn_num}] 🎯 Plano de Ataque</b> -> <b>{current_plan.plan_type}</b> ({current_plan.reason})"
                    self.send_chat_log(plan_badge, highlight=True, bg_color="#0f172a", text_color="#38bdf8")
                    self.log(f"[PLANO DE ATAQUE] 🎯 Estratégia: {current_plan.plan_type} - {current_plan.reason}")

                best_attack = self.policy_engine.select_best_attack(state, unpayable_set)
                if best_attack:
                    self.last_attempted_play = best_attack["name"]
                    score_val  = best_attack.get("score", 0.0)
                    board_eval = self.evaluate_board_state(state)

                    if best_attack.get("type") == "equipment_ability" and hasattr(self, "equipment_tracker"):
                        self.equipment_tracker.track_activation(
                            hero=self.hero_name,
                            eq_name=best_attack["name"],
                            turn=turn_num,
                            pre_eval=board_eval,
                        )

                    # ── Capturar e registrar log ISMCTS (se presente) ────────
                    ismcts_log = best_attack.pop("_ismcts_log", None)
                    if ismcts_log:
                        try:
                            self.policy_engine.ismcts_logger.log(
                                ismcts_log=ismcts_log,
                                turn=turn_num,
                                phase=turn_phase,
                            )
                        except Exception:
                            pass

                    # ── Classificação de Lance no Padrão de Xadrez ──────────
                    chat_msg, badge_color = format_attack_chat_message(
                        turn_num=turn_num,
                        card_name=best_attack["name"],
                        score_val=score_val,
                        board_eval=board_eval,
                        mcts_sims=self.policy_engine.num_mcts_sims,
                        has_go_again=bool(best_attack.get("has_go_again")),
                        is_ismcts=bool(ismcts_log)
                    )
                    self.send_chat_log(chat_msg, highlight=True, bg_color="#0f172a", text_color=badge_color)

                    # ── Gravação de Trajetória para Treinamento (Distilação MCTS) ──
                    try:
                        from ai.model import FaBPolicyValueNetwork
                        import numpy as np
                        state_vec = FaBPolicyValueNetwork.extract_state_vector(state)
                        pol_dist = best_attack.get("_policy_dist", None)
                        if pol_dist is None:
                            pol_dist = np.zeros(32, dtype=np.float32)
                            m_idx = min(int(best_attack.get("mode", 27)), 31)
                            pol_dist[m_idx] = 1.0
                        self.trajectory.append((state_vec, pol_dist, self.player_id, board_eval))
                    except Exception:
                        pass

                    raw_type = str(best_attack.get("type", "ação")).lower()
                    atk_type = raw_type.replace("_", " ").title()
                    atk_name = best_attack["name"]
                    atk_power = best_attack.get("power", 0)
                    atk_cost = best_attack.get("cost", 0)
                    if raw_type in ("hero_ability", "weapon_buff", "equipment_ability") and atk_power <= 0:
                        if raw_type == "hero_ability" and "teklo" in str(self.hero_name).lower():
                            self.teklo_ability_active_turn = turn_num
                        self.log(f"[AÇÃO JOGADOR {self.player_id}] Ativou -> {atk_name} (Tipo: {atk_type}, Custo: {atk_cost})")
                    else:
                        self.attacks_made += 1
                        self.log(f"[AÇÃO JOGADOR {self.player_id}] Atacou com -> {atk_name} (Tipo: {atk_type}, Poder: {atk_power}, Custo: {atk_cost})")

                    self.send_action(mode=best_attack["mode"], card_id=best_attack["card_id"], button_input=best_attack["name"])
                    time.sleep(0.002)
                    return True


        # 9. Se houver botões de prompt disponíveis ("Pass", "Pass Block and Reactions", "End Turn")
        if prompt_buttons:
            for btn in prompt_buttons:
                cap = str(btn.get("caption", "")).lower()
                if "pass" in cap or "done" in cap or "ok" in cap or "end" in cap:
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Clicou '{btn.get('caption')}'")
                    self.send_action(mode=btn.get("mode", 99), button_input=btn.get("buttonInput", ""))
                    time.sleep(0.002)
                    return True

        # 10. Passar prioridade padrão (Mode 99)
        self.log(f"[AÇÃO JOGADOR {self.player_id}] Passou prioridade / Fim de Ações (Fase: {turn_phase})")
        self.send_action(mode=99, button_input="")
        time.sleep(0.01)
        return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--room', required=True)
    parser.add_argument('--deck', required=True)
    parser.add_argument('--role', choices=['host', 'join'], required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--mcts-sims', type=int, default=None)
    parser.add_argument('--device', type=str, default=None)
    parser.add_argument('--buffer-capacity', type=int, default=None)
    args = parser.parse_args()

    with open(f'logs/{args.room}_{args.name}_debug.log', 'w') as f:
        f.write('--- INICIO HTTP ---\n')
    
    client = FabBotClient(
        args.room, args.deck, args.role, args.name,
        mcts_sims=args.mcts_sims, device=args.device,
        buffer_capacity=args.buffer_capacity
    )
    client.run_loop()
