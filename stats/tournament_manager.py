"""
TournamentManager: Gerenciador de Torneios Automatizados para Flesh and Blood (Talishar).
Suporta formatos Round-Robin (Todos contra Todos) e Sistema Suíço (Swiss).
Executa partidas automatizadas entre múltiplos decks, registrando ELO e matriz de matchups.
"""

import os
import json
import time
import uuid
import math
import subprocess
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

import stats_manager

DATA_DIR = "data"
STATS_FILE = os.path.join(DATA_DIR, "training_stats.json")
TOURNAMENT_RESULTS_FILE = os.path.join(DATA_DIR, "tournament_results.json")

class TournamentManager:
    def __init__(
        self,
        tournament_name: str = "FaB Championship",
        format_type: str = "round_robin",
        execution_mode: str = "talishar",
        mcts_sims: int = 3,
        num_rounds: Optional[int] = None,
    ):
        self.tournament_name = tournament_name
        self.format_type = format_type.lower()  # "round_robin" ou "swiss"
        self.execution_mode = execution_mode.lower()  # "headless" ou "talishar"
        self.mcts_sims = mcts_sims
        self.num_rounds = num_rounds
        self.id = str(uuid.uuid4())[:8]
        self.participants: List[Dict[str, Any]] = []
        self.matches: List[Dict[str, Any]] = []
        self.current_round = 0
        self.is_running = False
        self.completed = False
        self.logs: List[str] = []
        self._headless_model = None
        os.makedirs(DATA_DIR, exist_ok=True)

    def log(self, message: str):
        t_str = datetime.now().strftime("%H:%M:%S")
        entry = f"[{t_str}] [TORNEIO] {message}"
        self.logs.append(entry)
        print(entry)

    def load_available_decks(self, decks_dir: str = "decks") -> List[Dict[str, Any]]:
        """Lê todos os decks JSON disponíveis no diretório."""
        decks = []
        if not os.path.exists(decks_dir):
            return decks

        for fname in os.listdir(decks_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(decks_dir, fname)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        hero = data.get("hero", data.get("name", fname.replace(".json", "")))
                        deck_format = data.get("format", "cc" if len(data.get("cards", [])) > 50 else "blitz")
                        decks.append({
                            "id": fname.replace(".json", ""),
                            "name": data.get("name", fname),
                            "hero": hero,
                            "format": deck_format,
                            "file": fpath,
                            "points": 0,
                            "wins": 0,
                            "losses": 0,
                            "draws": 0,
                            "byes": 0,
                            "elo": 1200,
                            "opponents": [],
                            "buchholz": 0.0,
                            "sonneborn_berger": 0.0,
                        })
                except Exception as e:
                    self.log(f"Erro ao carregar deck {fname}: {e}")
        return decks

    def setup_tournament(self, deck_ids: List[str]):
        """Configura os participantes do torneio com base nos decks selecionados."""
        all_decks = self.load_available_decks()
        self.participants = [d for d in all_decks if d["id"] in deck_ids or d["name"] in deck_ids]
        for p in self.participants:
            p.setdefault("opponents", [])
            p.setdefault("byes", 0)
            p.setdefault("buchholz", 0.0)
            p.setdefault("sonneborn_berger", 0.0)
        self.log(f"Torneio '{self.tournament_name}' configurado com {len(self.participants)} decks.")

        if self.format_type == "round_robin":
            self._generate_round_robin_schedule()
        elif self.format_type == "swiss":
            self._generate_swiss_round(1)

    def _generate_round_robin_schedule(self):
        """Gera todos os confrontos (todos contra todos)."""
        self.matches = []
        n = len(self.participants)
        match_id = 1
        for i in range(n):
            for j in range(i + 1, n):
                p1 = self.participants[i]
                p2 = self.participants[j]
                self.matches.append({
                    "id": match_id,
                    "round": 1,
                    "deck1": p1["id"],
                    "deck2": p2["id"],
                    "deck1_name": p1["name"],
                    "deck2_name": p2["name"],
                    "winner": None,
                    "p1_health": None,
                    "p2_health": None,
                    "turns": None,
                    "status": "Pendente"
                })
                match_id += 1
        self.log(f"Total de {len(self.matches)} partidas geradas para o formato Round-Robin.")

    def _calculate_tie_breakers(self):
        """Calcula pontuação de desempate oficial Buchholz e Sonneborn-Berger."""
        id_to_points = {p["id"]: p["points"] for p in self.participants}
        for p in self.participants:
            opps = p.get("opponents", [])
            p["buchholz"] = float(sum(id_to_points.get(opp_id, 0) for opp_id in opps))

            sb = 0.0
            for opp_id in opps:
                opp_pts = id_to_points.get(opp_id, 0)
                for m in self.matches:
                    if m.get("status") == "Concluída" and not m.get("is_bye"):
                        if (m["deck1"] == p["id"] and m["deck2"] == opp_id) or (m["deck2"] == p["id"] and m["deck1"] == opp_id):
                            if m.get("winner") == p["name"]:
                                sb += opp_pts
                            elif m.get("winner") == "Empate":
                                sb += 0.5 * opp_pts
            p["sonneborn_berger"] = float(sb)

    def _generate_swiss_round(self, round_num: int):
        """
        Gera pareamento para a rodada suíça sem rematches e com suporte a Bye oficial.
        Critérios de ordenação: (pontos, Buchholz, Sonneborn-Berger, ELO).
        """
        self.current_round = round_num
        self._calculate_tie_breakers()

        sorted_participants = sorted(
            self.participants,
            key=lambda x: (x["points"], x.get("buchholz", 0.0), x.get("sonneborn_berger", 0.0), x.get("elo", 1200)),
            reverse=True,
        )

        round_matches = []
        match_id_offset = len(self.matches) + 1
        unpaired = list(sorted_participants)

        # Tratar número ímpar: atribui Bye ao jogador de menor ranking sem Bye prévio
        if len(unpaired) % 2 != 0:
            bye_idx = None
            for idx in reversed(range(len(unpaired))):
                if unpaired[idx].get("byes", 0) == 0:
                    bye_idx = idx
                    break
            if bye_idx is None:
                bye_idx = len(unpaired) - 1

            bye_player = unpaired.pop(bye_idx)
            round_matches.append({
                "id": match_id_offset,
                "round": round_num,
                "deck1": bye_player["id"],
                "deck2": "BYE",
                "deck1_name": bye_player["name"],
                "deck2_name": "BYE",
                "winner": bye_player["name"],
                "p1_health": 20,
                "p2_health": 0,
                "turns": 0,
                "status": "Concluída",
                "is_bye": True,
            })
            match_id_offset += 1
            self.log(f"[Rodada {round_num}] Bye concedido a {bye_player['name']} (+3 pontos).")

        # Parear jogadores restantes evitando rematches passados
        while len(unpaired) >= 2:
            p1 = unpaired.pop(0)
            p1_opps = set(p1.get("opponents", []))

            chosen_idx = None
            for idx, candidate in enumerate(unpaired):
                if candidate["id"] not in p1_opps:
                    chosen_idx = idx
                    break

            if chosen_idx is None:
                chosen_idx = 0

            p2 = unpaired.pop(chosen_idx)
            round_matches.append({
                "id": match_id_offset,
                "round": round_num,
                "deck1": p1["id"],
                "deck2": p2["id"],
                "deck1_name": p1["name"],
                "deck2_name": p2["name"],
                "winner": None,
                "p1_health": None,
                "p2_health": None,
                "turns": None,
                "status": "Pendente",
                "is_bye": False,
            })
            match_id_offset += 1

        self.matches.extend(round_matches)
        self.log(f"Rodada {round_num} gerada com {len(round_matches)} partidas.")

    def run_single_match(self, match: Dict[str, Any]) -> bool:
        """Executa uma partida única (via Headless em memória ou Talishar bots)."""
        if match.get("is_bye"):
            match["status"] = "Concluída"
            self._update_standings(match)
            self.log(f"Partida #{match['id']} Concluída por Bye para {match['deck1_name']}!")
            return True

        if self.execution_mode == "headless":
            return self._run_single_match_headless(match)
        return self._run_single_match_talishar(match)

    def _run_single_match_headless(self, match: Dict[str, Any]) -> bool:
        """Execução ultrarrápida da partida em memória via GameSimulator e HeadlessSelfPlayLoop."""
        match_id = match["id"]
        deck1_id = match["deck1"]
        deck2_id = match["deck2"]

        match["status"] = "Em Progresso"
        self.log(f"Iniciando Partida Headless #{match_id}: {match['deck1_name']} vs {match['deck2_name']}")

        try:
            from ai.training.headless_env import HeadlessSelfPlayLoop
            from ai.model import FaBPolicyValueNetwork

            if self._headless_model is None:
                self._headless_model = FaBPolicyValueNetwork()
                self._headless_model.eval()

            env = HeadlessSelfPlayLoop(self._headless_model, mcts_sims=self.mcts_sims, device="cpu")
            trajectory, winner_id = env.play_game(deck1_id, deck2_id)

            if winner_id == 1:
                match["winner"] = match["deck1_name"]
            elif winner_id == 2:
                match["winner"] = match["deck2_name"]
            else:
                match["winner"] = "Empate"

            match["p1_health"] = 20 if winner_id == 1 else (0 if winner_id == 2 else 10)
            match["p2_health"] = 20 if winner_id == 2 else (0 if winner_id == 1 else 10)
            match["turns"] = max(1, len(trajectory) // 2)
            match["status"] = "Concluída"

            try:
                stats_manager.update_match_result(
                    room_id=f"Tourney_{self.id}_{match_id}",
                    p1_deck=deck1_id,
                    p2_deck=deck2_id,
                    p1_health=match["p1_health"],
                    p2_health=match["p2_health"],
                    total_turns=match["turns"],
                    winner_id=winner_id,
                )
            except Exception as e:
                self.log(f"Aviso ao registrar stats no banco: {e}")

        except Exception as e:
            self.log(f"Erro na simulação headless: {e}")
            match["winner"] = "Empate"
            match["status"] = "Concluída"
            match["p1_health"] = 0
            match["p2_health"] = 0
            match["turns"] = 0

        self._update_standings(match)
        self.log(f"Partida #{match_id} Concluída! Vencedor: {match['winner']}")
        return True

    def _run_single_match_talishar(self, match: Dict[str, Any]) -> bool:
        """Executa uma partida de torneio lançando os bots em subprocessos contra o servidor Talishar."""
        match_id = match["id"]
        deck1_id = match["deck1"]
        deck2_id = match["deck2"]

        room_name = f"Tourney_{self.id}_{match_id}"
        deck1_path = f"decks/{deck1_id}.json"
        deck2_path = f"decks/{deck2_id}.json"

        match["status"] = "Em Progresso"
        self.log(f"Iniciando Partida #{match_id}: {match['deck1_name']} vs {match['deck2_name']} (Sala: {room_name})")

        # 1. Iniciar Host
        cmd1 = ["python3", "bot_client.py", "--room", room_name, "--role", "host", "--name", f"Bot_{deck1_id}", "--deck", deck1_path]
        p1 = subprocess.Popen(cmd1, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.0)

        # 2. Iniciar Joiner
        cmd2 = ["python3", "bot_client.py", "--room", room_name, "--role", "join", "--name", f"Bot_{deck2_id}", "--deck", deck2_path]
        p2 = subprocess.Popen(cmd2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Monitorar conclusão (Timeout de 120s por partida)
        start_t = time.time()
        winner = None
        while time.time() - start_t < 120:
            if p1.poll() is not None and p2.poll() is not None:
                break
            time.sleep(1.0)

        # Terminar se ainda estiverem rodando após o timeout
        if p1.poll() is None: p1.terminate()
        if p2.poll() is None: p2.terminate()

        # 4. Ler estatísticas da partida gravada em training_stats.json
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, "r", encoding="utf-8") as f:
                    stats = json.load(f)
                    recent = stats.get("recent_matches", [])
                    for r in recent:
                        if r.get("room") == room_name:
                            winner = r.get("winner")
                            if str(winner) == "0" or "Empate" in str(winner) or "Draw" in str(winner):
                                match["winner"] = "Empate"
                            else:
                                match["winner"] = match["deck1_name"] if "Host" in str(winner) or "1" in str(winner) else match["deck2_name"]
                            match["p1_health"] = r.get("p1_health")
                            match["p2_health"] = r.get("p2_health")
                            match["turns"] = r.get("turns")
                            match["status"] = "Concluída"
                            break
            except Exception as e:
                self.log(f"Erro ao ler estatísticas da partida: {e}")

        if not match.get("winner"):
            match["winner"] = "Empate"
            match["status"] = "Concluída"
            match["p1_health"] = 0
            match["p2_health"] = 0
            match["turns"] = 0

            # Atualização do banco de dados/stat_manager para empate/timeout
            stats_manager.update_match_result(
                room_id=room_name,
                p1_deck=deck1_id,
                p2_deck=deck2_id,
                p1_health=0,
                p2_health=0,
                total_turns=0,
                winner_id=0,
                is_invalid_match=True,
                invalid_reason="Timeout do Torneio"
            )

        # 5. Atualizar pontuação e ELO dos participantes
        self._update_standings(match)
        self.log(f"Partida #{match_id} Concluída! Vencedor: {match['winner']}")
        return True

    def _update_standings(self, match: Dict[str, Any]):
        """Atualiza a tabela de classificação e ratings ELO oficiais."""
        if match.get("is_bye"):
            for p in self.participants:
                if p["id"] == match["deck1"] or p["name"] == match["deck1_name"]:
                    p["wins"] += 1
                    p["points"] += 3
                    p["byes"] = p.get("byes", 0) + 1
            return

        winner_name = match.get("winner")
        p1 = next((p for p in self.participants if p["name"] == match.get("deck1_name") or p["id"] == match.get("deck1")), None)
        p2 = next((p for p in self.participants if p["name"] == match.get("deck2_name") or p["id"] == match.get("deck2")), None)

        if p1 is not None and p2 is not None:
            p1.setdefault("opponents", []).append(p2["id"])
            p2.setdefault("opponents", []).append(p1["id"])

        if winner_name == "Empate":
            winner_code = 0
            for p in self.participants:
                if p["name"] in (match.get("deck1_name"), match.get("deck2_name")):
                    p["draws"] += 1
                    p["points"] += 1
        elif p1 is not None and winner_name == p1["name"]:
            winner_code = 1
            p1["wins"] += 1
            p1["points"] += 3
            if p2 is not None:
                p2["losses"] += 1
        else:
            winner_code = 2
            if p2 is not None:
                p2["wins"] += 1
                p2["points"] += 3
            if p1 is not None:
                p1["losses"] += 1

        if p1 is not None and p2 is not None:
            try:
                from stats.elo import calculate_elo_ratings
                p1["elo"], p2["elo"] = calculate_elo_ratings(p1["elo"], p2["elo"], winner_code, k=32)
            except Exception:
                if winner_code == 1:
                    p1["elo"] += 16
                    p2["elo"] = max(1000, p2["elo"] - 16)
                elif winner_code == 2:
                    p2["elo"] += 16
                    p1["elo"] = max(1000, p1["elo"] - 16)

    def run_all_matches(self):
        """Executa todas as partidas pendentes do torneio em sequência."""
        self.is_running = True
        self.log(f"Iniciando execução do torneio '{self.tournament_name}' ({self.format_type}, {self.execution_mode})...")

        if self.format_type == "round_robin":
            for m in self.matches:
                if m["status"] == "Pendente":
                    self.run_single_match(m)
                    if self.execution_mode == "talishar":
                        time.sleep(0.5)
        elif self.format_type == "swiss":
            n = len(self.participants)
            total_rounds = self.num_rounds or max(1, int(math.ceil(math.log2(max(2, n)))))
            # Roda rodada 1
            for m in list(self.matches):
                if m["status"] == "Pendente":
                    self.run_single_match(m)
                    if self.execution_mode == "talishar":
                        time.sleep(0.5)

            # Roda rodadas subsequentes
            for r in range(2, total_rounds + 1):
                self._generate_swiss_round(r)
                round_matches = [m for m in self.matches if m.get("round") == r and m["status"] == "Pendente"]
                for m in round_matches:
                    self.run_single_match(m)
                    if self.execution_mode == "talishar":
                        time.sleep(0.5)

        self._calculate_tie_breakers()
        self.participants.sort(
            key=lambda x: (x["points"], x.get("buchholz", 0.0), x.get("sonneborn_berger", 0.0), x["elo"]),
            reverse=True,
        )
        self.is_running = False
        self.completed = True
        self.save_results()
        self.log(f"Torneio '{self.tournament_name}' finalizado com sucesso!")

    def save_results(self):
        """Salva a tabela de classificação e histórico de confrontos em JSON."""
        self._calculate_tie_breakers()
        standings = sorted(
            self.participants,
            key=lambda x: (x["points"], x.get("buchholz", 0.0), x.get("sonneborn_berger", 0.0), x["elo"]),
            reverse=True,
        )
        results = {
            "id": self.id,
            "tournament_name": self.tournament_name,
            "format": self.format_type,
            "execution_mode": self.execution_mode,
            "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "standings": standings,
            "matches": self.matches,
        }
        with open(TOURNAMENT_RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        self.log(f"Resultados salvos em {TOURNAMENT_RESULTS_FILE}.")

    def get_matchup_matrix(self) -> Dict[str, Dict[str, str]]:
        """Gera uma matriz de vitórias/derrotas entre todos os decks."""
        matrix = {p["name"]: {p2["name"]: "-" for p2 in self.participants} for p in self.participants}
        for m in self.matches:
            if m["status"] == "Concluída" and m["winner"]:
                d1 = m["deck1_name"]
                d2 = m["deck2_name"]
                if m["winner"] == d1:
                    matrix[d1][d2] = "V"
                    matrix[d2][d1] = "D"
                else:
                    matrix[d2][d1] = "V"
                    matrix[d1][d2] = "D"
        return matrix
