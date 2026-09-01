import time
import json
import argparse
import os
import requests
from datetime import datetime
from ai.policy_engine import PolicyEngine

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
        self.log_file = f"logs/{self.room_id}_{self.player_name}_debug.log"
        self.match_log_file = f"logs/{self.room_id}_match_feed.log"
        self.deck_format = "blitz"
        self.policy_engine = PolicyEngine(model_path="data/model_latest.pt" if os.path.exists("data/model_latest.pt") else None)
        self.metrics = {"health": 20, "opp_health": 20, "card_advantage": 0, "status": "Iniciando", "phase": "pre-game"}
        self.trajectory = []
        self.clean_deck = os.path.basename(self.deck_url).replace(".json", "") if self.deck_url else "default_deck"
        os.makedirs("logs", exist_ok=True)
        try:
            with open(f"logs/{self.room_id}_{self.role}_deck.txt", "w") as f:
                f.write(self.clean_deck)
        except Exception:
            pass

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
        print(formatted)

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
                    for gfp in [f"Talishar/Games/{self.game_id}/GameFile.txt", f"/home/renan/fab-talishar-ia/Talishar/Games/{self.game_id}/GameFile.txt"]:
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
                
                time.sleep(0.05)
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
                                if self.metrics.get("status") == "Finalizada":
                                    self.log(f"[*] Bot {self.player_name} finalizou a partida #{self.game_id}.")
                                    break
                        except json.JSONDecodeError:
                            self.log(f"[ALERTA] Resposta inesperada do servidor: {res_state.text[:400]}")
                else:
                    self.log(f"[ALERTA] Servidor retornou HTTP {res_state.status_code}")
                
            except Exception as e:
                self.log(f"[ERRO DE CONEXÃO] {e}")

            time.sleep(0.005)

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
            time.sleep(0.05)
            if os.path.exists(p2_flag):
                self.log(f"[HOST] Jogador 2 detectado no lobby. Avançando para sideboard...")
                time.sleep(0.05)
                self.choose_first_player()
                time.sleep(0.05)
                self.submit_sideboard()
                return
            try:
                lres = self.session.post(
                    f"{TALISHAR_API_URL}/APIs/GetLobbyRefresh.php",
                    json={"gameName": self.game_id, "playerID": 1, "authKey": self.auth_key}
                )
                if lres.status_code == 200:
                    ldata = lres.json()
                    if ldata.get("gameStatus", 0) >= 3 or ldata.get("opponentHero"):
                        self.log(f"[HOST] Jogador 2 detectado no lobby. Avançando para sideboard...")
                        time.sleep(0.05)
                        self.choose_first_player()
                        time.sleep(0.05)
                        self.submit_sideboard()
                        return
            except Exception:
                pass
        self.log(f"[TIMEOUT] Jogador 2 não entrou na sala a tempo.")

    def get_card_meta(self, card_id: str) -> dict:
        if not hasattr(self, "_card_db") or self._card_db is None:
            for p in ["data/fab_cards_db.json", "/home/renan/fab-talishar-ia/data/fab_cards_db.json"]:
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
        weapons = []
        main_cards = []
        inv = []

        for c in raw_cards:
            cid = c.get("identifier", "") if isinstance(c, dict) else str(c)
            tot = int(c.get("count", c.get("total", 1))) if isinstance(c, dict) else 1
            if not cid:
                continue
            meta = self.get_card_meta(cid)
            slot = meta.get("slot", "Deck")

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
            elif slot in ("Weapon", "Off-Hand"):
                if len(weapons) < 2:
                    weapons.append(cid)
                else:
                    inv.append(cid)
            else:
                main_cards.extend([cid] * tot)

        if not hero:
            hero = "ira_crimson_haze"

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
            "offhand": weapons[1] if len(weapons) > 1 else "",
            "deck": flat_deck,
            "inventory": inv
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

        self.policy_engine = PolicyEngine(hero_name=hero, room_id=self.room_id)
        self.policy_engine.update_room_id(room_id=self.room_id, hero_name=hero)
        self.log(f"[SIDEBOARD CONFIRMADO] Jogador {self.player_id}: Hero={hero} | Equip: [H:{head}, C:{chest}, A:{arms}, L:{legs}, W:{weapons}] | Deck={len(flat_deck)} cartas | Inv={len(inv)} itens.")
        return True

    def send_chat_log(self, text: str, highlight: bool = False, bg_color: str = "#1e293b", text_color: str = "#38bdf8"):
        target_id = getattr(self, "game_id", None) or getattr(self, "room_id", "")
        if not target_id:
            return
        if highlight:
            html_line = f"<div style='background:{bg_color};border-left:4px solid {text_color};padding:3px 6px;margin:2px 0;border-radius:4px;color:{text_color};font-size:12px;'>{text}</div>"
        else:
            html_line = f"<span style='color:{text_color};font-weight:600;'>{text}</span>"
        try:
            self.session.post(
                f"{TALISHAR_API_URL}/APIs/AppendGameLog.php",
                json={"gameName": target_id, "message": html_line},
                timeout=1
            )
        except Exception:
            pass

    def evaluate_board_state(self, state: dict) -> float:
        """Calcula o índice de avaliação da posição (estilo Chess Eval +/-)."""
        my_h = int(state.get("playerHealth", 40))
        opp_h = int(state.get("opponentHealth", 40))
        my_hand_cnt = len(state.get("playerHand", []))
        opp_hand_cnt = int(state.get("opponentHandCount", 4))
        
        # Diferencial de Vida e Vantagem de Cartas
        eval_score = ((my_h - opp_h) * 0.4) + ((my_hand_cnt - opp_hand_cnt) * 0.8)
        return round(eval_score, 1)

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

                if hasattr(self, "trajectory") and self.trajectory:
                    try:
                        from ai.experience_collector import get_global_buffer
                        buf = get_global_buffer()
                        buf.add_trajectory(self.trajectory, winner_player_id=winner_id)
                        buf.save()
                    except Exception as e:
                        self.log(f"[ERRO BUFFER] {e}")

                is_vs_human = (self.name == "AIMaster_Bot" or "Human_vs_Bot" in str(self.room_id) or str(self.room_id).isdigit())
                if self.role == "host" or is_vs_human:
                    try:
                        p1_d_file = f"logs/{self.room_id}_host_deck.txt"
                        p2_d_file = f"logs/{self.room_id}_join_deck.txt"
                        p1_d = open(p1_d_file).read().strip() if os.path.exists(p1_d_file) else ("Humano (Você)" if is_vs_human else self.clean_deck)
                        p2_d = open(p2_d_file).read().strip() if os.path.exists(p2_d_file) else self.clean_deck
                        
                        from stats_manager import update_match_result
                        update_match_result(
                            room_id=self.room_id,
                            p1_deck=p1_d,
                            p2_deck=p2_d,
                            p1_health=my_h if self.player_id == 1 else opp_h,
                            p2_health=opp_h if self.player_id == 1 else my_h,
                            total_turns=turn,
                            winner_id=winner_id,
                            is_human_p1=is_vs_human
                        )
                        winner_str = p1_d if winner_id == 1 else (p2_d if winner_id == 2 else "Empate")
                        self.log(f"[FIM DE JOGO] Partida #{self.game_id} finalizada! Vencedor: {winner_str}. Placar: {my_h} vs {opp_h} em {turn} turnos.")

                        summary_text = (
                            f"═══════════════════════════════════════════════\n"
                            f"🏆 RESULTADO DA PARTIDA: {self.room_id}\n"
                            f"═══════════════════════════════════════════════\n"
                            f"• Vencedor: {winner_str} (Jogador {winner_id})\n"
                            f"• Host ({p1_d}): {my_h if self.player_id == 1 else opp_h} HP\n"
                            f"• Join ({p2_d}): {opp_h if self.player_id == 1 else my_h} HP\n"
                            f"• Duração: {turn} turnos\n"
                            f"• Decisões Coletadas para Treino: {len(self.trajectory)} amostras\n"
                            f"═══════════════════════════════════════════════\n"
                        )
                        with open(f"logs/{self.room_id}_summary.log", "w", encoding="utf-8") as f:
                            f.write(summary_text)
                    except Exception as e:
                        self.log(f"[ERRO STATS] {e}")

        with open(f"logs/{self.room_id}_{self.player_name}.json", "w") as f:
            json.dump({"metrics": self.metrics}, f)
            
        if state.get("havePriority") and self.metrics["status"] != "Finalizada":
            self.decide_and_act(state)

    def send_action(self, mode=99, card_id="", button_input="", chk_count=0, chk_input=None, input_text=""):
        if not mode or mode <= 0:
            mode = 99
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
            self.trajectory.append((s_vec, p_dist, self.player_id))
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

            if turn_phase in ("DOCRANK", "YESNO"):
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ({turn_phase}) -> Forçando NO (Mode 20)")
                self.send_action(mode=20, button_input="NO")
                self.recent_phases.clear()
                self.consecutive_same_state = 0
                time.sleep(0.005)
                return True

            if turn_phase == "MAYCHOOSEMULTIZONE":
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ({turn_phase}) -> Pass (Mode 99)")
                self.send_action(mode=99, button_input="PASS")
                self.recent_phases.clear()
                self.consecutive_same_state = 0
                time.sleep(0.005)
                return True

            if turn_phase in ("CHOOSEMULTIZONE", "MULTICHOOSE", "MULTICHOOSEHAND"):
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Anti-Loop ({turn_phase}) -> Submetendo vazio (Mode 19)")
                self.send_action(mode=19, chk_count=0, chk_input=[])
                self.recent_phases.clear()
                self.consecutive_same_state = 0
                time.sleep(0.005)
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
            time.sleep(0.005)
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
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Seleção de Alvo/Zona -> {turn_phase}")
            self.send_action(mode=16, card_id="0", button_input="0")
            time.sleep(0.002)
            return True

        if turn_phase == "MAYCHOOSEMULTIZONE":
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Escolha Opcional ({turn_phase}) -> Pass (Mode 99)")
            self.send_action(mode=99, button_input="PASS")
            time.sleep(0.002)
            return True

        if turn_phase in ("CHOOSEMULTIZONE", "MULTICHOOSE", "MULTICHOOSEHAND"):
            p_data = popup.get("data", popup) if isinstance(popup, dict) else {}
            cards_arr = p_data.get("cardsArray", []) if isinstance(p_data, dict) else []
            hand = state.get("playerHand", [])
            
            form_opts = popup.get("formOptions", {}) if isinstance(popup, dict) else {}
            max_cnt = form_opts.get("maxCount", len(cards_arr) if cards_arr else len(hand))
            
            if max_cnt == 0 or (not cards_arr and not hand):
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Multi-Seleção (Sem opções / Max 0) -> Confirmar vazio (Mode 19)")
                self.send_action(mode=19, chk_count=0, chk_input=[])
                time.sleep(0.002)
                return True

            chk_cnt = 1 if len(cards_arr) > 0 else (1 if len(hand) > 0 else 0)
            chk_inp = ["0"] if chk_cnt > 0 else []

            btn_inp = "0"
            if prompt_buttons:
                for b in prompt_buttons:
                    if b.get("mode") == 19 or "submit" in str(b.get("caption", "")).lower() or "ok" in str(b.get("caption", "")).lower():
                        btn_inp = str(b.get("buttonInput", "0"))
                        break
            self.log(f"[AÇÃO JOGADOR {self.player_id}] Multi-Seleção -> {turn_phase} (Mode: 19, Count: {chk_cnt})")
            self.send_action(mode=19, button_input=btn_inp, chk_count=chk_cnt, chk_input=chk_inp)
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
            if not hasattr(self, "declared_blocks_link"):
                self.declared_blocks_link = set()

            chosen_blocks = self.policy_engine.select_defense_blocks(state)
            unblocked = [b for b in chosen_blocks if str(b[1]) not in self.declared_blocks_link]
            if unblocked:
                b_idx, b_id, b_name, b_action = unblocked[0]
                self.declared_blocks_link.add(str(b_id))
                chat_msg = f"<b>[Turno {turn_num}] 🛡️ Bloqueio Tático</b> -> <b>{b_name}</b> (Defesa Otimizada)"
                self.send_chat_log(chat_msg, highlight=True, bg_color="#1e1b4b", text_color="#c084fc")
                self.log(f"[AÇÃO JOGADOR {self.player_id}] Bloqueio Tático -> {b_name} (ID: {b_id})")
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
            hand = state.get("playerHand", [])
            
            if not hasattr(self, "reaction_attempts"):
                self.reaction_attempts = {}

            for idx, c in enumerate(hand):
                c_action = c.get("action", 0)
                c_name = c.get("cardNumber", "")
                
                attempts = self.reaction_attempts.get(c_name, 0)
                if attempts >= 2:
                    unpayable_set.add(c_name)
                    
                if c_action > 0 and c_name not in unpayable_set:
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
                        self.log(f"[AÇÃO JOGADOR {self.player_id}] Jogou Reação/Instant -> {c_name}")
                        self.send_action(mode=c_action, card_id=c_id, button_input=c_name)
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

        if is_my_turn and turn_phase in ("M", "STARTTURN", "RESOLUTIONSTEP"):
            if player_ap > 0:
                best_attack = self.policy_engine.select_best_attack(state, unpayable_set)
                if best_attack:
                    self.last_attempted_play = best_attack["name"]
                    score_val  = best_attack.get("score", 0.0)
                    board_eval = self.evaluate_board_state(state)

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
                    if score_val >= 9.0:
                        tier_badge  = "🟢 Brilhante (!!)"
                        badge_color = "#22c55e"
                    elif score_val >= 5.0:
                        tier_badge  = "🎯 Melhor Jogada (!)"
                        badge_color = "#38bdf8"
                    elif best_attack.get("has_go_again"):
                        tier_badge  = "⚡ Excelente"
                        badge_color = "#a855f7"
                    else:
                        tier_badge  = "🔵 Bom"
                        badge_color = "#60a5fa"

                    eval_str = f"+{board_eval}" if board_eval > 0 else str(board_eval)
                    engine_tag = "ISMCTS" if ismcts_log else "MCTS"
                    chat_msg = (
                        f"<b>[Turno {turn_num}] {tier_badge}</b> → <b>{best_attack['name']}</b> "
                        f"(Score: {score_val:.1f} | Eval: {eval_str} | {engine_tag}: {self.policy_engine.num_mcts_sims} sims)"
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
                        self.trajectory.append((state_vec, pol_dist, self.player_id))
                    except Exception:
                        pass

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
    args = parser.parse_args()

    with open(f'logs/{args.room}_{args.name}_debug.log', 'w') as f:
        f.write('--- INICIO HTTP ---\n')
    
    client = FabBotClient(args.room, args.deck, args.role, args.name)
    client.run_loop()
