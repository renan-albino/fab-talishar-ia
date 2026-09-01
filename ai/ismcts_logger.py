"""
ai/ismcts_logger.py
===================
Logger estruturado para decisões do ISMCTS.

Escreve em `logs/ismcts_decisions.jsonl` (JSON Lines) uma entrada por decisão:

{
  "timestamp"       : "2026-08-30T21:30:00",
  "room_id"         : "sala_xyz",
  "turn"            : 5,
  "phase"           : "M",
  "worlds_sampled"  : 4,
  "num_simulations" : 25,
  "candidates"      : ["zero_to_sixty_red", "throttle_red", "anothos"],
  "votes"           : {"zero_to_sixty_red": 42, "throttle_red": 31, "anothos": 11},
  "chosen"          : "zero_to_sixty_red",
  "chosen_idx"      : 0,
  "confidence"      : 0.494,
  "mcts_value_root" : 0.23,
  "total_votes"     : 84,
  "hero"            : "dorinthea_ironsong"
}

O arquivo pode ser analisado com `scripts/analyze_ismcts.py` sem nenhuma
dependência de servidor ou banco de dados.
"""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional


_DEFAULT_LOG_PATH = os.path.join("logs", "ismcts_decisions.jsonl")


class ISMCTSLogger:
    """
    Logger thread-safe (append-only) para decisões do ISMCTS.

    Uso:
        from ai.ismcts_logger import ISMCTSLogger
        logger = ISMCTSLogger(room_id="sala_xyz", hero="dorinthea")

        # Dentro da decisão:
        logger.log(
            ismcts_log=ismcts_log,   # dict retornado por ISMCTSEngine.search_ismcts
            turn=5,
            phase="M",
        )
    """

    def __init__(
        self,
        room_id: str = "unknown",
        hero: str = "generic",
        log_path: str = _DEFAULT_LOG_PATH,
    ):
        self.room_id  = room_id
        self.hero     = hero
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path) if os.path.dirname(log_path) else ".", exist_ok=True)

    def log(
        self,
        ismcts_log: Dict[str, Any],
        turn: int = 0,
        phase: str = "",
    ) -> None:
        """
        Escreve uma entrada de decisão ISMCTS no arquivo JSONL.

        Args:
            ismcts_log : Dict retornado por ISMCTSEngine.search_ismcts.
            turn       : Número do turno atual.
            phase      : Fase do turno (ex: "M", "B", "A").
        """
        if not ismcts_log:
            return

        entry = {
            "timestamp"      : datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "room_id"        : self.room_id,
            "hero"           : self.hero,
            "turn"           : turn,
            "phase"          : phase,
            **ismcts_log,
        }

        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            # Logging não deve nunca travar o bot — falha silenciosa
            print(f"[ISMCTSLogger] Aviso: falha ao escrever log — {e}")

    # ── Conveniência: ler de volta para análise ───────────────────

    @staticmethod
    def load_all(log_path: str = _DEFAULT_LOG_PATH) -> list:
        """
        Carrega todas as entradas do arquivo JSONL.
        Retorna lista de dicts (vazia se arquivo não existir).
        """
        if not os.path.exists(log_path):
            return []
        entries = []
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return entries

    @staticmethod
    def tail(log_path: str = _DEFAULT_LOG_PATH, n: int = 10) -> list:
        """Retorna as últimas `n` entradas do log."""
        entries = ISMCTSLogger.load_all(log_path)
        return entries[-n:]
