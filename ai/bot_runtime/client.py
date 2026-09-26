import os
import time
import json
import requests
import traceback
from typing import Optional
from datetime import datetime

from ai.policy_engine import PolicyEngine
from ai.equipment_learning import EquipmentTracker
from ai.talishar_api import TalisharApiClient, DEFAULT_BACKEND_URL
from ai.chat_badges import evaluate_board_state, format_html_line
from ai.bot_runtime import lobby_manager, match_tracker, choice_handler, phase_decider
from ai.common.schemas import GameState

def safe_int(val, default=0):
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

def safe_str(val, default=""):
    try:
        return str(val)
    except (ValueError, TypeError):
        return default

TALISHAR_API_URL = DEFAULT_BACKEND_URL

class FabBotClient:
    def __init__(
        self,
        room_id: str,
        deck_url: str,
        role: str,
        player_name: str,
        mcts_sims: int = None,
        device: str = None,
        buffer_capacity: int = None,
        epoch_ratio: float = 0.0,
        ismcts_concurrency: Optional[str] = None,
    ):
        self.room_id = room_id
        self.deck_url = deck_url
        self.role = role
        self.player_name = player_name
        self.name = player_name  # Garante self.name definido para evitar AttributeError
        self.epoch_ratio = epoch_ratio
        self.session = requests.Session()
        self.api = TalisharApiClient(backend_url=TALISHAR_API_URL, session=self.session)
        self.game_id = None
        self.player_id = None
        self._last_metrics_save_time = 0.0
        self._last_metrics_save_turn = None
        self.auth_key = None
        self.mcts_sims = mcts_sims
        self.device = device
        self.buffer_capacity = buffer_capacity
        self.ismcts_concurrency = ismcts_concurrency
        self.use_gpu = (self.device != "cpu") if self.device else True
        self.log_file = f"logs/{self.room_id}_{self.player_name}_debug.log"
        self.match_log_file = f"logs/{self.room_id}_match_feed.log"
        from ai.policy.opponent_tracker import OpponentTracker

        self.deck_format = "blitz"
        self.opponent_tracker = OpponentTracker()
        self.policy_engine = PolicyEngine(
            model_path="data/model_latest.pt" if os.path.exists("data/model_latest.pt") else None,
            num_mcts_sims=self.mcts_sims,
            use_gpu=self.use_gpu,
            ismcts_concurrency=self.ismcts_concurrency,
        )
        self.metrics = {"health": 20, "opp_health": 20, "card_advantage": 0, "status": "Iniciando", "phase": "pre-game"}
        self.trajectory = []
        self.attacks_made = 0
        self.damage_dealt = 0
        self.damage_taken = 0
        self.opp_attacks_count = 0
        self.blocks_declared_count = 0
        self.initial_my_health = None
        self.initial_opp_health = None
        self.execution_exceptions_count = 0
        self.clean_deck = os.path.basename(self.deck_url).replace(".json", "") if self.deck_url else "default_deck"
        
        # Log level: DEBUG=0, INFO=1, WARNING=2, ERROR=3
        # Control via FAB_BOT_LOG_LEVEL env var (0=DEBUG, 1=INFO, 2=WARNING, 3=ERROR)
        log_level_env = os.environ.get("FAB_BOT_LOG_LEVEL", "1")
        try:
            self.log_level = int(log_level_env)
        except ValueError:
            self.log_level = 1  # Default INFO
        
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

    def save_metrics_throttled(self, current_turn: int = None, force: bool = False):
        """Grava o arquivo JSON de métricas respeitando throttling de 1.5s ou mudança de turno."""
        now = time.time()
        last_turn = getattr(self, "_last_metrics_save_turn", None)
        last_time = getattr(self, "_last_metrics_save_time", 0.0)
        turn_changed = (current_turn is not None and current_turn != last_turn)
        time_elapsed = (now - last_time) >= 1.5

        if force or turn_changed or time_elapsed:
            try:
                metrics_path = f"logs/{self.room_id}_{self.player_name}.json"
                with open(metrics_path, "w", encoding="utf-8") as f:
                    json.dump({"metrics": self.metrics}, f)
                self._last_metrics_save_time = now
                if current_turn is not None:
                    self._last_metrics_save_turn = current_turn
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

    def dump_error_state(self, reason: str, state: dict, exception_trace: str = None):
        """Salva o estado do jogo e o contexto quando a IA realiza uma acao invalida."""
        try:
            os.makedirs("logs/exceptions", exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            turn = state.get("turnNo", state.get("currentTurn", "X"))
            dump_path = f"logs/exceptions/err_{self.room_id}_turn{turn}_{ts}.json"
            
            def json_default(obj):
                # Handle OpponentTracker specifically
                if obj.__class__.__name__ == "OpponentTracker":
                    return {"_type": "OpponentTracker", "data": obj.__dict__}
                if hasattr(obj, '__dict__'):
                    return obj.__dict__
                return str(obj)

            dump_data = {
                "reason": reason,
                "traceback": exception_trace,
                "turn_phase": state.get("turnPhase", ""),
                "player_name": self.player_name,
                "hero": getattr(self, "hero_name", ""),
                "state": state
            }
            with open(dump_path, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, indent=2, default=json_default)
            self.error(f"[ERRO GRAVADO] Dump de estado salvo em: {dump_path}")
        except Exception as e:
            self.error(f"[FALHA AO GRAVAR DUMP] {e}")

    def log(self, message, level: int = 1):
        """Log message with level filtering.
        level: 0=DEBUG, 1=INFO, 2=WARNING, 3=ERROR
        """
        if level < self.log_level:
            return
        t_str = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{t_str}] {message}"
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
        try:
            with open(self.match_log_file, "a", encoding="utf-8") as mf:
                mf.write(formatted + "\n")
        except Exception:
            pass
        # Only print to stdout for WARNING and ERROR to reduce console spam
        if level >= 2:
            print(formatted, flush=True)

    def debug(self, message):
        try:
            self.log(message, level=0)
        except TypeError:
            self.log(message)

    def info(self, message):
        try:
            self.log(message, level=1)
        except TypeError:
            self.log(message)

    def warning(self, message):
        try:
            self.log(message, level=2)
        except TypeError:
            self.log(message)

    def error(self, message):
        try:
            self.log(message, level=3)
        except TypeError:
            self.log(message)

    def run_loop(self):
        self.info(f"[*] Iniciando Bot HTTP para a sala {self.room_id} (Role: {self.role})")
        if not lobby_manager.setup_game_room(self):
            return

        # 2. Loop principal de Polling de estado da mesa (Adaptativo)
        waiting_logged = False
        last_logged_turn = -1
        backoff_delay = 0.25
        while True:
            has_priority = False
            try:
                res_state = self.session.get(
                    f"{TALISHAR_API_URL}/GetNextTurn.php",
                    params={"gameName": self.game_id, "playerID": self.player_id, "authKey": self.auth_key},
                    timeout=5.0
                )

                if res_state.status_code == 200:
                    text = res_state.text.strip()
                    if not text or text == "0":
                        if not waiting_logged:
                            self.debug(f"[AGUARDANDO] Aguardando início do Turno 1 na sala #{self.game_id}...")
                            waiting_logged = True
                        self.metrics["phase"] = "Aguardando Início"
                        self.metrics["status"] = "Aguardando"
                        self.save_metrics_throttled(current_turn=0, force=False)
                    else:
                        try:
                            state = res_state.json()
                            if "errorMessage" in state:
                                err_msg = state['errorMessage']
                                self.warning(f"[AVISO MESA] {err_msg}")
                                self.dump_error_state(f"Server Validation Error: {err_msg}", state)
                            else:
                                turn_num = safe_int(state.get("turnNo", state.get("currentTurn", 1)), default=1)
                                if turn_num != last_logged_turn:
                                    _fmt = getattr(self, "deck_format", "").lower()
                                    _def_hp = 20 if _fmt in ("blitz", "compblitz") else 40
                                    my_h = state.get("playerHealth", _def_hp)
                                    opp_h = state.get("opponentHealth", _def_hp)
                                    p1_hp = my_h if self.player_id == 1 else opp_h
                                    p2_hp = opp_h if self.player_id == 1 else my_h
                                    p1_lbl = self.get_player_label(1)
                                    p2_lbl = self.get_player_label(2)
                                    turn_active_id = state.get("turnPlayer", 1)
                                    active_lbl = p1_lbl if str(turn_active_id) == "1" else p2_lbl

                                    # O Host (Player 1) loga no feed compartilhado para evitar linhas duplicadas e invertidas
                                    if self.player_id == 1:
                                        self.debug(f"[TURNO {turn_num}] 📊 Placar: {p1_lbl} [{p1_hp} HP] vs {p2_lbl} [{p2_hp} HP] | Vez de: {active_lbl}")
                                    else:
                                        with open(self.log_file, "a", encoding="utf-8") as lf:
                                            lf.write(f"[{datetime.now().strftime('%H:%M:%S')}] [TURNO {turn_num}] 📊 Placar: {p1_lbl} [{p1_hp} HP] vs {p2_lbl} [{p2_hp} HP] | Vez de: {active_lbl}\n")
                                    last_logged_turn = turn_num
                                has_priority = bool(state.get("havePriority", False))
                                self.handle_game_tick(state)
                                waiting_logged = False
                                if self.metrics.get("status") == "Finalizada":
                                    self.info(f"[*] Bot {self.player_name} finalizou a partida #{self.game_id}.")
                                    break
                        except json.JSONDecodeError:
                            self.warning(f"[ALERTA] Resposta inesperada do servidor: {res_state.text[:400]}")
                else:
                    self.warning(f"[ALERTA] Servidor retornou HTTP {res_state.status_code}")
                
            except Exception as e:
                self.execution_exceptions_count += 1
                self.error(f"[ERRO DE CONEXÃO] {e}")

            # Polling adaptativo: 0.03s quando tem prioridade / ações pendentes, 0.25s com backoff quando aguarda oponente
            if has_priority:
                backoff_delay = 0.25
                time.sleep(0.03)
            else:
                time.sleep(backoff_delay)
                backoff_delay = min(backoff_delay * 1.25, 1.0)

    def choose_first_player(self):
        return lobby_manager.choose_first_player(self)

    def wait_in_lobby_and_start(self):
        return lobby_manager.wait_in_lobby_and_start(self)

    def wait_for_opponent_and_start(self):
        return lobby_manager.wait_for_opponent_and_start(self)

    def get_card_meta(self, card_id: str) -> dict:
        if not hasattr(self, "_card_db") or self._card_db is None:
            base_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
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
        return lobby_manager.get_opponent_info(self)

    def submit_sideboard(self):
        from ai.sideboard_manager import resolve_sideboard
        opp_hero, opp_class = self.get_opponent_info()
        sub_obj = resolve_sideboard(
            deck_url=self.deck_url,
            deck_format=self.deck_format,
            opp_hero=opp_hero,
            opp_class=opp_class,
            get_card_meta=self.get_card_meta,
            log_fn=self.log,
            game_id=self.game_id or "",
            player_id=self.player_id or 1,
        )

        hero = sub_obj["hero"]
        head = sub_obj["head"]
        chest = sub_obj["chest"]
        arms = sub_obj["arms"]
        legs = sub_obj["legs"]
        weapons = sub_obj["hands"]
        flat_deck = sub_obj["deck"]
        inv = sub_obj["inventory"]

        post_payload = {
            "gameName": self.game_id,
            "playerID": self.player_id,
            "authKey": self.auth_key,
            "submission": json.dumps(sub_obj)
        }

        try:
            res = self.session.post(f"{TALISHAR_API_URL}/APIs/SubmitSideboard.php", json=post_payload, timeout=5.0)
        except TypeError:
            res = self.session.post(f"{TALISHAR_API_URL}/APIs/SubmitSideboard.php", json=post_payload)
        try:
            data = res.json()
            if "error" in data or data.get("status") == "FAIL":
                self.error(f"[ERRO NO SIDEBOARD] {data.get('error') or data.get('deckError')}")
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
        self.save_metrics_throttled(force=True)

        self.policy_engine = PolicyEngine(
            hero_name=hero,
            model_path="data/model_latest.pt" if os.path.exists("data/model_latest.pt") else None,
            room_id=self.room_id,
            num_mcts_sims=self.mcts_sims,
            use_gpu=self.use_gpu
        )
        self.policy_engine.update_room_id(room_id=self.room_id, hero_name=hero)
        self.info(f"[SIDEBOARD CONFIRMADO] Jogador {self.player_id}: Hero={hero} | Equip: [H:{head}, C:{chest}, A:{arms}, L:{legs}, W:{weapons}] | Deck={len(flat_deck)} cartas | Inv={len(inv)} itens.")
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
        card_name = active_chain.get("cardNumber") or active_chain.get("name", "")
        if not card_name:
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
        if not isinstance(state, dict):
            return
            
        try:
            parsed_state = GameState(**state)
            state.update(parsed_state.model_dump())
        except Exception:
            pass

        opp_hand = state.get("opponentHand")
        if "opponentHand" in state and "opponentHandCount" not in state:
            state["opponentHandCount"] = len(opp_hand)

        # Compatibilidade com backend Talishar (playerArse -> playerArsenal, theirArse -> theirArsenal)
        if "playerArse" in state and "playerArsenal" not in state:
            state["playerArsenal"] = state.get("playerArse")
        if "theirArse" in state and "theirArsenal" not in state:
            state["theirArsenal"] = state.get("theirArse")
        if "theirArsenal" in state and "opponentArsenal" not in state:
            state["opponentArsenal"] = state.get("theirArsenal")

        # Normalização de zonas da arena adversária
        if "theirItems" in state and "opponentItems" not in state:
            state["opponentItems"] = state.get("theirItems")
        if "theirAuras" in state and "opponentAuras" not in state:
            state["opponentAuras"] = state.get("theirAuras")
        if "theirPermanents" in state and "opponentPermanents" not in state:
            state["opponentPermanents"] = state.get("theirPermanents")
        if "theirEquipment" in state and "opponentEquipment" not in state:
            state["opponentEquipment"] = state.get("theirEquipment")
        if "theirAllies" in state and "opponentAllies" not in state:
            state["opponentAllies"] = state.get("theirAllies")

        my_h = safe_int(state.get("playerHealth"), default=40)
        opp_h = safe_int(state.get("opponentHealth"), default=40)

        match_tracker.track_tick_health_and_damage(self, state, my_h, opp_h)

        turn_active_id = state.get("turnPlayer", 1)
        prev_active_id = getattr(self, "_prev_turn_active_id", None)
        if prev_active_id is not None and prev_active_id != self.player_id and turn_active_id == self.player_id:
            if hasattr(self, "opponent_tracker"):
                opp_cards_played = max(0, 4 - state.get("opponentHandCount", 4))
                opp_damage_dealt = self.damage_taken - getattr(self, "_prev_opp_damage_taken_track", 0)
                self._prev_opp_damage_taken_track = self.damage_taken
                self.opponent_tracker.update(cards_played=opp_cards_played, damage_dealt=opp_damage_dealt)
        self._prev_turn_active_id = turn_active_id

        turn = safe_int(state.get("turnNo", state.get("currentTurn", 1)), default=1)

        self.metrics["health"] = my_h
        self.metrics["opp_health"] = opp_h
        self.metrics["deck_url"] = self.deck_url
        self.metrics["player_id"] = self.player_id
            
        tp_raw = state.get("turnPhase", "")
        tp_name = tp_raw.get("turnPhase", "") if isinstance(tp_raw, dict) else tp_raw
        self.metrics["phase"] = f"Turno {turn} ({tp_name})" if tp_name else f"Turno {turn}"
        self.metrics["status"] = "Jogando"

        is_stalemate, stalemate_reason = match_tracker.check_stalemate_and_timeout(self, state, turn, my_h, opp_h)

        # Checar se a partida terminou (vitória, derrota ou empate técnico)
        is_game_over = (tp_name == "OVER" or state.get("gameStatus") == 2 or my_h <= 0 or opp_h <= 0 or is_stalemate)
        if is_game_over:
            self.metrics["status"] = "Finalizada"
            if not getattr(self, "game_recorded", False):
                self.game_recorded = True
                match_tracker.finalize_match(self, state, turn, my_h, opp_h, is_stalemate, stalemate_reason)

        self.save_metrics_throttled(current_turn=turn, force=is_game_over)
            
        if state.get("havePriority") and self.metrics["status"] != "Finalizada":
            try:
                self.decide_and_act(state)
            except Exception as e:
                self.execution_exceptions_count += 1
                tb = traceback.format_exc()
                self.error(f"[ERRO DECIDE_AND_ACT] {e}")
                self.dump_error_state("Exception in decide_and_act", state, tb)
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
        return choice_handler.score_choice_candidate(self, candidate, turn_phase=turn_phase, state=state, popup=popup)

    def _rank_choice_candidates(self, candidates: list, turn_phase: str = "", state: dict = None, popup: dict = None) -> list:
        """Ordena uma lista de candidatos do mais recomendado ao menos recomendado."""
        return choice_handler.rank_choice_candidates(self, candidates, turn_phase=turn_phase, state=state, popup=popup)

    def decide_and_act(self, state: dict):
        if not isinstance(state, dict):
            return False
            
        try:
            parsed_state = GameState(**state)
            state.update(parsed_state.model_dump())
        except Exception:
            pass

        state["opponent_tracker"] = getattr(self, "opponent_tracker", None)

        # Compatibilidade com backend Talishar (playerArse -> playerArsenal, theirArse -> theirArsenal)
        if "playerArse" in state and "playerArsenal" not in state:
            state["playerArsenal"] = state.get("playerArse")
        if "theirArse" in state and "theirArsenal" not in state:
            state["theirArsenal"] = state.get("theirArse")
        if "theirArsenal" in state and "opponentArsenal" not in state:
            state["opponentArsenal"] = state.get("theirArsenal")

        # Normalização de zonas da arena adversária
        if "theirItems" in state and "opponentItems" not in state:
            state["opponentItems"] = state.get("theirItems")
        if "theirAuras" in state and "opponentAuras" not in state:
            state["opponentAuras"] = state.get("theirAuras")
        if "theirPermanents" in state and "opponentPermanents" not in state:
            state["opponentPermanents"] = state.get("theirPermanents")
        if "theirEquipment" in state and "opponentEquipment" not in state:
            state["opponentEquipment"] = state.get("theirEquipment")
        if "theirAllies" in state and "opponentAllies" not in state:
            state["opponentAllies"] = state.get("theirAllies")

        tp_raw = state.get("turnPhase", "M")
        if isinstance(tp_raw, dict):
            turn_phase = safe_str(tp_raw.get("turnPhase", "M"), default="M")
        else:
            turn_phase = tp_raw if tp_raw else "M"
            
        turn_num = safe_int(state.get("turnNo", state.get("currentTurn", 1)), default=1)
        
        if not hasattr(self, "unpayable_cards_turn"):
            self.unpayable_cards_turn = {}
        turn_key = f"{turn_num}_{self.player_id}"
        if turn_key not in self.unpayable_cards_turn:
            self.unpayable_cards_turn = {turn_key: set()}
            self.reaction_attempts = {}
        unpayable_set = self.unpayable_cards_turn[turn_key]

        popup = state.get("popup")
        prompt_buttons = []
        player_prompt = state.get("playerPrompt")
        if isinstance(player_prompt, dict):
            prompt_buttons = player_prompt.get("buttons") or player_prompt.get("promptButtons")
        elif isinstance(state.get("promptButtons"), list):
            prompt_buttons = state.get("promptButtons")
        elif isinstance(state.get("buttons"), list):
            prompt_buttons = state.get("buttons")

        # 1. Anti-Loop
        if choice_handler.check_and_handle_anti_loop(self, state, turn_num, turn_phase, prompt_buttons, unpayable_set):
            return True

        # 2. Modais, popups e escolhas de zona/texto
        if choice_handler.handle_popup_and_choices(self, state, turn_phase, popup, prompt_buttons, unpayable_set):
            return True

        # 3. Fase de Pitch
        if phase_decider.handle_pitch_phase(self, state, turn_phase, prompt_buttons, unpayable_set):
            return True

        # 4. Fase de Bloqueio
        if phase_decider.handle_block_phase(self, state, turn_num, prompt_buttons):
            return True

        # 5. Fase de Reação
        if phase_decider.handle_reaction_phase(self, state, turn_num, turn_phase, prompt_buttons, unpayable_set):
            return True

        # 6. Fase de Arsenal
        if phase_decider.handle_arsenal_phase(self, state, turn_num):
            return True

        # 7. Fase Principal de Ataque / Ação
        if phase_decider.handle_main_action_phase(self, state, turn_num, turn_phase, prompt_buttons, unpayable_set):
            return True

        # 8. Pass padrão ou botões de prompt
        return phase_decider.handle_pass_buttons(self, prompt_buttons, turn_phase)
