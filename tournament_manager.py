"""
TournamentManager: Gerenciador de Torneios Automatizados para Flesh and Blood (Talishar).
Suporta formatos Round-Robin (Todos contra Todos) e Sistema Suíço (Swiss).
Executa partidas automatizadas entre múltiplos decks, registrando ELO e matriz de matchups.
"""

import os
import json
import time
import uuid
import subprocess
import threading
from datetime import datetime
from typing import List, Dict, Any, Optional

DATA_DIR = "data"
STATS_FILE = os.path.join(DATA_DIR, "training_stats.json")
TOURNAMENT_RESULTS_FILE = os.path.join(DATA_DIR, "tournament_results.json")

class TournamentManager:
    def __init__(self, tournament_name: str = "FaB Championship", format_type: str = "round_robin"):
        self.tournament_name = tournament_name
        self.format_type = format_type.lower()  # "round_robin" ou "swiss"
        self.id = str(uuid.uuid4())[:8]
        self.participants: List[Dict[str, Any]] = []
        self.matches: List[Dict[str, Any]] = []
        self.current_round = 0
        self.is_running = False
        self.completed = False
        self.logs: List[str] = []
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
                            "elo": 1200
                        })
                except Exception as e:
                    self.log(f"Erro ao carregar deck {fname}: {e}")
        return decks

    def setup_tournament(self, deck_ids: List[str]):
        """Configura os participantes do torneio com base nos decks selecionados."""
        all_decks = self.load_available_decks()
        self.participants = [d for d in all_decks if d["id"] in deck_ids or d["name"] in deck_ids]
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

    def _generate_swiss_round(self, round_num: int):
        """Gera pareamento para a rodada suíça ordenando por pontuação."""
        self.current_round = round_num
        sorted_participants = sorted(self.participants, key=lambda x: x["points"], reverse=True)
        
        round_matches = []
        match_id_offset = len(self.matches) + 1
        
        for i in range(0, len(sorted_participants) - 1, 2):
            p1 = sorted_participants[i]
            p2 = sorted_participants[i + 1]
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
                "status": "Pendente"
            })
            match_id_offset += 1
            
        self.matches.extend(round_matches)
        self.log(f"Rodada {round_num} gerada com {len(round_matches)} partidas.")

    def run_single_match(self, match: Dict[str, Any]) -> bool:
        """Executa uma partida de torneio lançando os bots em subprocessos."""
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
                            match["winner"] = match["deck1_name"] if "Host" in str(winner) or "1" in str(winner) else match["deck2_name"]
                            match["p1_health"] = r.get("p1_health")
                            match["p2_health"] = r.get("p2_health")
                            match["turns"] = r.get("turns")
                            match["status"] = "Concluída"
                            break
            except Exception as e:
                self.log(f"Erro ao ler estatísticas da partida: {e}")

        if not match["winner"]:
            match["winner"] = match["deck1_name"]  # Fallback default
            match["status"] = "Concluída"

        # 5. Atualizar pontuação e ELO dos participantes
        self._update_standings(match)
        self.log(f"Partida #{match_id} Concluída! Vencedor: {match['winner']}")
        return True

    def _update_standings(self, match: Dict[str, Any]):
        """Atualiza a tabela de classificação com base no resultado da partida."""
        winner_name = match["winner"]
        for p in self.participants:
            if p["name"] == winner_name:
                p["wins"] += 1
                p["points"] += 3
                p["elo"] += 16
            elif p["name"] in (match["deck1_name"], match["deck2_name"]):
                p["losses"] += 1
                p["elo"] = max(1000, p["elo"] - 16)

    def run_all_matches(self):
        """Executa todas as partidas pendentes do torneio em sequência."""
        self.is_running = True
        self.log(f"Iniciando execução do torneio '{self.tournament_name}'...")
        
        for m in self.matches:
            if m["status"] == "Pendente":
                self.run_single_match(m)
                time.sleep(0.5)

        self.is_running = False
        self.completed = True
        self.save_results()
        self.log(f"Torneio '{self.tournament_name}' finalizado com sucesso!")

    def save_results(self):
        """Salva a tabela de classificação e histórico de confrontos em JSON."""
        results = {
            "id": self.id,
            "tournament_name": self.tournament_name,
            "format": self.format_type,
            "date": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "standings": sorted(self.participants, key=lambda x: x["points"], reverse=True),
            "matches": self.matches
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
