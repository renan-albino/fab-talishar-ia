import time
import json
import argparse
import os
import requests
from datetime import datetime

TALISHAR_API_URL = "http://localhost:8080/game"

class FabBotClient:
    def __init__(self, room_id: str, deck_url: str, role: str, player_name: str):
        self.room_id = room_id
        self.deck_url = deck_url
        self.role = role
        self.player_name = player_name
        self.session = requests.Session()
        self.game_id = None
        self.player_id = None
        self.auth_key = None
        self.log_file = f"logs/{self.room_id}_{self.player_name}_debug.log"
        self.metrics = {"health": 20, "opp_health": 20, "card_advantage": 0, "status": "Iniciando", "phase": "pre-game"}
        os.makedirs("logs", exist_ok=True)

    def log(self, message):
        t_str = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{t_str}] {message}"
        with open(self.log_file, "a") as f:
            f.write(formatted + "\n")
        print(formatted)

    def run_loop(self):
        self.log(f"[*] Iniciando Bot HTTP para a sala {self.room_id} (Role: {self.role})")
        
        # 1. Enviar requisição para criar ou entrar na sala
        if self.role == "host":
            deck_format = "blitz"
            target_deck = self.deck_url if self.deck_url else "deck.json"
            
            # Determine format if local file
            if os.path.exists(target_deck):
                try:
                    with open(target_deck, "r") as f:
                        d = json.load(f)
                        deck_format = d.get("format", "blitz")
                except Exception:
                    pass
            elif os.path.exists(f"decks/{target_deck}.json"):
                try:
                    with open(f"decks/{target_deck}.json", "r") as f:
                        d = json.load(f)
                        deck_format = d.get("format", "blitz")
                except Exception:
                    pass
            elif os.path.exists("Talishar/deck.json"):
                try:
                    with open("Talishar/deck.json", "r") as f:
                        d = json.load(f)
                        deck_format = d.get("format", "blitz")
                except Exception:
                    pass

            create_payload = {
                "format": deck_format,
                "fabdb": target_deck,
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
                
                # Salva o ID real da partida para o Bot2 ler
                with open(f"logs/{self.room_id}_game_id.txt", "w") as f:
                    f.write(self.game_id)
                self.log(f"[HOST SUCESSO] Partida ID #{self.game_id} criada ({deck_format.upper()}). AuthKey: {self.auth_key[:8]}...")
                
                # Host aguarda Bot 2 entrar no Lobby antes de definir First Player e Sideboard
                self.wait_for_opponent_and_start()
            except Exception as e:
                self.log(f"[ERRO DE CREATE] {e}")
                return
        else:
            # Espera o Host criar e escrever o ID da partida
            id_file = f"logs/{self.room_id}_game_id.txt"
            waited = 0
            while not os.path.exists(id_file) and waited < 20:
                time.sleep(1)
                waited += 1
            
            if not os.path.exists(id_file):
                self.log(f"[ERRO JOIN] Timeout esperando o Host criar a partida.")
                return

            with open(id_file, "r") as f:
                self.game_id = f.read().strip()

            target_deck = self.deck_url if self.deck_url else "deck.json"
            join_payload = {
                "gameName": self.game_id,
                "playerID": 2,
                "fabdb": target_deck
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
                self.log(f"[JOIN SUCESSO] Entrou na partida #{self.game_id} como Jogador {self.player_id}.")
                
                # Avisa o Host que o Jogador 2 entrou no Lobby
                with open(f"logs/{self.room_id}_p2_ready.txt", "w") as f:
                    f.write("ready")
                
                time.sleep(0.5)
                # Bot 2 submete Sideboard
                self.submit_sideboard()
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
                                    my_h = state.get("playerHealth", 40)
                                    opp_h = state.get("opponentHealth", 40)
                                    hero_name = state.get("initialLoad", {}).get("myHeroName", state.get("myCharacter", "Hero"))
                                    self.log(f"[TURNO {turn_num}] {hero_name} | Vida: {my_h} vs {opp_h} | Status: Em Partida")
                                    last_logged_turn = turn_num
                                self.handle_game_tick(state)
                                waiting_logged = False
                        except json.JSONDecodeError:
                            self.log(f"[ALERTA] Resposta inesperada do servidor: {res_state.text[:400]}")
                else:
                    self.log(f"[ALERTA] Servidor retornou HTTP {res_state.status_code}")
                
            except Exception as e:
                self.log(f"[ERRO DE CONEXÃO] {e}")

            time.sleep(0.1)

    def choose_first_player(self):
        try:
            res = self.session.post(
                f"{TALISHAR_API_URL}/APIs/ChooseFirstPlayer.php",
                json={"gameName": self.game_id, "playerID": self.player_id, "authKey": self.auth_key, "action": "Go First"}
            )
            self.log(f"[FIRST PLAYER] Escolha 'Go First' enviada para Jogador {self.player_id}.")
        except Exception as e:
            self.log(f"[ERRO FIRST PLAYER] {e}")

    def wait_for_opponent_and_start(self):
        self.log(f"[HOST] Aguardando Jogador 2 entrar na sala #{self.game_id}...")
        p2_flag = f"logs/{self.room_id}_p2_ready.txt"
        for _ in range(40):
            time.sleep(0.5)
            if os.path.exists(p2_flag):
                self.log(f"[HOST] Jogador 2 detectado no lobby. Avançando para sideboard...")
                time.sleep(0.5)
                self.choose_first_player()
                time.sleep(0.5)
                self.submit_sideboard()
                return
            try:
                lres = self.session.post(
                    f"{TALISHAR_API_URL}/APIs/GetLobbyRefresh.php",
                    json={"gameName": self.game_id, "playerID": 1, "authKey": self.auth_key}
                )
                if lres.status_code == 200:
                    ldata = lres.json()
                    # Se oponente entrou (gameStatus >= MGS_ChooseFirstPlayer)
                    if ldata.get("gameStatus", 0) >= 3 or ldata.get("opponentHero"):
                        self.log(f"[HOST] Jogador 2 detectado no lobby. Avançando para sideboard...")
                        time.sleep(0.5)
                        self.choose_first_player()
                        time.sleep(0.5)
                        self.submit_sideboard()
                        return
            except Exception:
                pass
        self.log(f"[TIMEOUT] Jogador 2 não entrou na sala a tempo.")

    def submit_sideboard(self):
        deck_file = self.deck_url if self.deck_url.endswith(".json") else f"decks/{self.deck_url}.json"
        if not os.path.exists(deck_file):
            if os.path.exists(f"Talishar/decks/{self.deck_url}.json"):
                deck_file = f"Talishar/decks/{self.deck_url}.json"
            elif os.path.exists(f"Talishar/decks/{self.deck_url}"):
                deck_file = f"Talishar/decks/{self.deck_url}"
            elif os.path.exists("Talishar/deck.json"):
                deck_file = "Talishar/deck.json"
            else:
                self.log(f"[ERRO] Arquivo de deck {deck_file} não encontrado.")
                return False

        try:
            with open(deck_file, "r") as f:
                deck_data = json.load(f)

            hero = deck_data.get("hero", "dash_io")
            head = deck_data.get("head", "crown_of_providence")
            chest = deck_data.get("chest", "teklo_foundry_heart")
            arms = deck_data.get("arms", "bracers_of_belief")
            legs = deck_data.get("legs", "achilles_accelerator")
            hands = deck_data.get("hands", ["symbiosis_shot"])
            
            raw_cards = deck_data.get("cards", [])
            flat_deck = []
            eq_set = {hero, head, chest, arms, legs}
            if isinstance(hands, list):
                eq_set.update(hands)
            else:
                eq_set.add(hands)
                
            for c in raw_cards:
                if isinstance(c, dict):
                    ident = c.get("identifier", "")
                    cnt = int(c.get("count", c.get("total", 1)))
                    if ident and ident not in eq_set:
                        flat_deck.extend([ident] * cnt)
                elif isinstance(c, str):
                    if c not in eq_set:
                        flat_deck.append(c)

            sub_obj = {
                "hero": hero,
                "head": head,
                "chest": chest,
                "arms": arms,
                "legs": legs,
                "hands": hands if isinstance(hands, list) else [hands],
                "deck": flat_deck,
                "inventory": []
            }

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
                
            self.log(f"[SIDEBOARD CONFIRMADO] Jogador {self.player_id}: Hero={hero} | Equip: [H:{head}, C:{chest}, A:{arms}, L:{legs}, W:{hands}] | Deck={len(flat_deck)} cartas | Inv=0 itens.")
            return True
        except Exception as e:
            self.log(f"[ERRO AO SUBMETER SIDEBOARD] {e}")
            return False

    def handle_game_tick(self, state: dict):
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
        
        # Checar se a partida terminou
        if tp_name == "OVER" or state.get("gameStatus") == 2 or my_h <= 0 or opp_h <= 0:
            self.metrics["status"] = "Finalizada"
            if not getattr(self, "game_recorded", False):
                self.game_recorded = True
                winner_id = 0
                if my_h > 0 and opp_h <= 0:
                    winner_id = self.player_id
                elif opp_h > 0 and my_h <= 0:
                    winner_id = 3 - self.player_id
                elif my_h > opp_h:
                    winner_id = self.player_id
                elif opp_h > my_h:
                    winner_id = 3 - self.player_id
                    
                try:
                    from stats_manager import update_match_result
                    update_match_result(
                        room_id=self.room_id,
                        p1_deck=self.deck_url,
                        p2_deck=self.deck_url,
                        p1_health=my_h if self.player_id == 1 else opp_h,
                        p2_health=opp_h if self.player_id == 1 else my_h,
                        total_turns=turn,
                        winner_id=winner_id
                    )
                    self.log(f"[FIM DE JOGO] Partida #{self.game_id} finalizada! Vencedor: Jogador {winner_id}. Placar: {my_h} vs {opp_h} em {turn} turnos.")
                except Exception as e:
                    self.log(f"[ERRO STATS] {e}")

        with open(f"logs/{self.room_id}_{self.player_name}.json", "w") as f:
            json.dump({"metrics": self.metrics}, f)
            
        # Se o bot tiver prioridade de ação, executa uma jogada
        if state.get("havePriority") and self.metrics["status"] != "Finalizada":
            self.decide_and_act(state)

    def send_action(self, mode=99, card_id="", button_input="", chk_count=0, chk_input=None, input_text=""):
        params = {
            "gameName": self.game_id,
            "playerID": self.player_id,
            "authKey": self.auth_key,
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
            res = self.session.get(f"{TALISHAR_API_URL}/ProcessInput.php", params=params)
            return res.status_code == 200
        except Exception as e:
            self.log(f"[ERRO AO ENVIAR AÇÃO] {e}")
            return False

    def decide_and_act(self, state: dict):
        tp_raw = state.get("turnPhase", "M")
        if isinstance(tp_raw, dict):
            turn_phase = str(tp_raw.get("turnPhase", "M"))
        else:
            turn_phase = str(tp_raw) if tp_raw else "M"
            
        turn_num = state.get("turnNo", state.get("currentTurn", 1))
        
        popup = state.get("popup", {})
        prompt_buttons = []
        if isinstance(state.get("playerPrompt"), dict):
            prompt_buttons = state.get("playerPrompt", {}).get("promptButtons", [])
        elif isinstance(state.get("promptButtons"), list):
            prompt_buttons = state.get("promptButtons", [])

        # Guarda Anti-Loop: Evita repetir a mesma ação em ciclo infinito
        if not hasattr(self, "loop_detector"):
            self.loop_detector = {}
        action_key = f"{turn_num}_{turn_phase}"
        self.loop_detector[action_key] = self.loop_detector.get(action_key, 0) + 1
        if self.loop_detector[action_key] > 10:
            if prompt_buttons:
                btn = prompt_buttons[0]
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ativado ({turn_phase} x{self.loop_detector[action_key]}) -> Botão {btn.get('caption')}")
                self.send_action(mode=btn.get("mode", 99), button_input=btn.get("buttonInput", ""))
            else:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ativado ({turn_phase} x{self.loop_detector[action_key]}) -> Passando (Mode 99)")
                self.send_action(mode=99, button_input="")
            self.loop_detector[action_key] = 0
            time.sleep(0.05)
            return True

        # 0. Tratar INPUTCARDNAME
        if turn_phase == "INPUTCARDNAME":
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Nomeou carta (INPUTCARDNAME) -> 'Sink Below'")
            self.send_action(mode=30, input_text="Sink Below")
            time.sleep(0.05)
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
                time.sleep(0.05)
                return True
            else:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Decisão {turn_phase} -> YES")
                self.send_action(mode=20, button_input="YES")
                time.sleep(0.05)
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
                time.sleep(0.05)
                return True
                
            p_buttons = p_data.get("buttons", [])
            if p_buttons:
                btn = p_buttons[0]
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Popup Botão -> {btn.get('caption', 'OK')}")
                self.send_action(mode=btn.get("mode", 17), button_input=btn.get("buttonInput", ""))
                time.sleep(0.05)
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
                    
                time.sleep(0.05)
                return True

        # 3. Tratar Escolhas de Zonas / Gatilhos (CHOOSECARD, CHOOSETRIGGERS, BUTTONINPUT, etc.)
        if turn_phase in ("BUTTONINPUT", "BUTTONINPUTNOPASS", "CHOOSEARCANE", "CHOOSEFIRSTPLAYER", "CHOOSETRIGGERS"):
            btn_input = prompt_buttons[0].get("buttonInput", "0") if prompt_buttons else "0"
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Gatilho/Escolha -> {turn_phase}")
            self.send_action(mode=17, button_input=str(btn_input))
            time.sleep(0.05)
            return True

        if turn_phase in ("CHOOSECARD", "CHOOSECARDID", "MAYCHOOSECARD", "CHOOSEZONE", "CHOOSEDECK", "MAYCHOOSEDECK"):
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Seleção de Alvo/Zona -> {turn_phase}")
            self.send_action(mode=16, card_id="0", button_input="0")
            time.sleep(0.05)
            return True

        if turn_phase in ("CHOOSEMULTIZONE", "MAYCHOOSEMULTIZONE", "MULTICHOOSE", "MULTICHOOSEHAND"):
            if prompt_buttons:
                btn = prompt_buttons[0]
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Confirmação MultiZona -> {btn.get('caption', 'Pass')}")
                self.send_action(mode=btn.get("mode", 19), button_input=btn.get("buttonInput", "0"), chk_count=1, chk_input=["0"])
            else:
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Multi-Seleção -> {turn_phase}")
                self.send_action(mode=19, chk_count=1, chk_input=["0"])
            time.sleep(0.05)
            return True

        if turn_phase in ("CHOOSENUMBER", "DYNPITCH", "NUMBERINPUT"):
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Entrada Numérica (Custo/Valor X) -> {turn_phase}")
            self.send_action(mode=7, button_input="0")
            time.sleep(0.05)
            return True

        if turn_phase in ("CHOOSETOP", "CHOOSEBOTTOM", "HANDTOPBOTTOM"):
            hand = state.get("playerHand", [])
            card_sel = hand[0].get("cardNumber", "") if hand else ""
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Reordenação -> {turn_phase}")
            self.send_action(mode=12 if turn_phase == "CHOOSETOP" else 13, button_input=card_sel)
            time.sleep(0.05)
            return True

        # 4. Se for Fase de Pitch (PDECK / P / PAYGOLDORPITCH / CHOOSEHANDCANCEL)
        if turn_phase in ("PDECK", "P", "PAYGOLDORPITCH", "CHOOSEHANDCANCEL"):
            if turn_phase == "PDECK":
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Bottom do Pitch (PDECK)")
                self.send_action(mode=6, card_id="0", button_input="0")
                time.sleep(0.05)
                return True

            hand = state.get("playerHand", [])
            for idx, c in enumerate(hand):
                c_action = c.get("action", 27)
                c_id = c.get("actionDataOverride", str(idx))
                c_name = c.get("cardNumber", "Card")
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Pitch de Carta -> {c_name} (Mode: {c_action})")
                self.send_action(mode=c_action if c_action > 0 else 27, card_id=c_id, button_input=c_id)
                time.sleep(0.05)
                return True

            if prompt_buttons:
                btn = prompt_buttons[0]
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Botão Pitch -> {btn.get('caption')}")
                self.send_action(mode=btn.get("mode", 99), button_input=btn.get("buttonInput", ""))
                time.sleep(0.05)
                return True

            self.send_action(mode=99, button_input="")
            time.sleep(0.05)
            return True

        # 5. Se for Fase de Defesa / Bloqueio (B)
        if turn_phase == "B":
            hand = state.get("playerHand", [])
            playable_blockers = [c for c in hand if c.get("action", 0) > 0 or c.get("borderColor", 0) > 0]
            if playable_blockers:
                c = playable_blockers[0]
                c_action = c.get("action", 27)
                c_id = c.get("actionDataOverride", c.get("cardNumber", ""))
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Declarou Bloqueio -> {c.get('cardNumber')}")
                self.send_action(mode=c_action, card_id=c_id, button_input=c_id)
                time.sleep(0.05)
                return True
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Passou Bloqueio")
            self.send_action(mode=99, button_input="")
            time.sleep(0.05)
            return True

        # 6. Se for Fase de Reação de Ataque (A) ou Defesa (D) ou Instantâneo
        if turn_phase in ("A", "D", "INSTANT"):
            hand = state.get("playerHand", [])
            for c in hand:
                c_action = c.get("action", 0)
                if c_action > 0:
                    c_id = c.get("actionDataOverride", c.get("cardNumber", ""))
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Jogou Reação/Instant -> {c.get('cardNumber')}")
                    self.send_action(mode=c_action, card_id=c_id, button_input=c_id)
                    time.sleep(0.05)
                    return True
            self.send_action(mode=99, button_input="")
            time.sleep(0.05)
            return True

        # 7. Se for Fase de Arsenal (ARS)
        if turn_phase == "ARS":
            hand = state.get("playerHand", [])
            if hand:
                c = hand[0]
                c_id = c.get("actionDataOverride", c.get("cardNumber", ""))
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Colocou no Arsenal -> {c.get('cardNumber')}")
                self.send_action(mode=4, card_id=c_id, button_input=c_id)
                time.sleep(0.05)
                return True
            self.send_action(mode=99, button_input="")
            time.sleep(0.05)
            return True

        # 8. Se for Fase Principal (M, STARTTURN, RESOLUTIONSTEP)
        if turn_phase in ("M", "STARTTURN", "RESOLUTIONSTEP"):
            # 8.1 Procurar carta jogável na mão (action > 0)
            hand = state.get("playerHand", [])
            for c in hand:
                action = c.get("action", 0)
                if action > 0:
                    c_id = c.get("actionDataOverride", c.get("cardNumber", ""))
                    c_name = c.get("cardNumber", "Card")
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Jogou Ataque/Ação -> {c_name} (Mode: {action})")
                    self.send_action(mode=action, card_id=c_id, button_input=c_id)
                    time.sleep(0.05)
                    return True

            # 8.2 Procurar ataque de arma / equipamento jogável (action > 0)
            equip = state.get("playerEquipment", [])
            for eq in equip:
                action = eq.get("action", 0)
                if action > 0:
                    eq_id = eq.get("actionDataOverride", eq.get("cardNumber", ""))
                    eq_name = eq.get("cardNumber", "Equip")
                    # Se já tentou esta habilidade de equipamento neste turno e não avançou, pular
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Atacou com Arma/Equip -> {eq_name} (Mode: {action})")
                    self.send_action(mode=action, card_id=eq_id, button_input=eq_id)
                    time.sleep(0.05)
                    return True

            # 8.3 Procurar cartas no Arsenal ou Banish jogáveis
            for zone_name, key in [("Arsenal", "playerArsenal"), ("Banish", "playerBanish")]:
                zone = state.get(key, [])
                for c in zone:
                    action = c.get("action", 0)
                    if action > 0:
                        c_id = c.get("actionDataOverride", c.get("cardNumber", ""))
                        self.log(f"[AÇÃO JOGADOR {self.player_id}] Jogou do {zone_name} -> {c.get('cardNumber')} (Mode: {action})")
                        self.send_action(mode=action, card_id=c_id, button_input=c_id)
                        time.sleep(0.05)
                        return True

        # 9. Se houver botões de prompt disponíveis ("Pass", "Pass Block and Reactions", "End Turn")
        if prompt_buttons:
            for btn in prompt_buttons:
                cap = str(btn.get("caption", "")).lower()
                if "pass" in cap or "done" in cap or "ok" in cap or "end" in cap:
                    self.log(f"[AÇÃO JOGADOR {self.player_id}] Clicou '{btn.get('caption')}'")
                    self.send_action(mode=btn.get("mode", 99), button_input=btn.get("buttonInput", ""))
                    time.sleep(0.05)
                    return True

        # 10. Passar prioridade padrão (Mode 99)
        self.log(f"[AÇÃO JOGADOR {self.player_id}] Passou prioridade / Fim de Ações (Fase: {turn_phase})")
        self.send_action(mode=99, button_input="")
        time.sleep(0.3)
        return True

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--room', required=True)
    parser.add_argument('--deck', required=True)
    parser.add_argument('--role', choices=['host', 'join'], required=True)
    parser.add_argument('--name', required=True)
    args = parser.parse_args()

    with open(f'logs/{args.room}_{args.name}_debug.log', 'w') as f:
        f.write('--- INICIO HTTP ---\n')
    
    client = FabBotClient(args.room, args.deck, args.role, args.name)
    client.run_loop()
