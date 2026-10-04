"""
ai/sim2real_detector.py
======================
Módulo de detecção e registro de anomalias Sim2Real (divergências de regras,
falhas de resolução de layers no Talishar, rejeições de ação e watchdog stalls).
"""

import os
import re
import json
import time
from typing import Dict, Any, List, Optional
from stats.db import get_connection

LOG_FILE = "logs/sim2real_anomalies.jsonl"

ENGINE_ERROR_PATTERNS = [
    (re.compile(r"the targeted .* is no longer there.*layer fails to resolve", re.I), "LAYER_TARGET_LOST"),
    (re.compile(r"fails to resolve", re.I), "LAYER_FAILED_TO_RESOLVE"),
    (re.compile(r"invalid target", re.I), "INVALID_TARGET"),
    (re.compile(r"illegal action", re.I), "ILLEGAL_ACTION"),
    (re.compile(r"does not have sufficient resources", re.I), "INSUFFICIENT_RESOURCES"),
    (re.compile(r"action cannot be played", re.I), "ACTION_CANNOT_BE_PLAYED"),
    (re.compile(r"fatal error|parse error", re.I), "PHP_ENGINE_FATAL"),
    (re.compile(r"warning:|notice:", re.I), "PHP_ENGINE_WARNING"),
]


def scan_log_for_anomalies(text: str) -> List[Dict[str, str]]:
    """Analisa um trecho de log/chat e retorna anomalias encontradas."""
    if not text:
        return []
    anomalies = []
    # Remove tags HTML simples
    for line in text.splitlines():
        clean = re.sub(r"<[^>]+>", " ", line).strip()
        clean = re.sub(r"\s+", " ", clean)
        if not clean:
            continue
        for pattern, code in ENGINE_ERROR_PATTERNS:
            if pattern.search(clean):
                anomalies.append({"code": code, "raw_message": clean})
                break
    return anomalies


def record_anomaly(
    room_id: str,
    hero: str,
    turn: int,
    phase: str,
    anomaly_type: str,
    message: str,
    opponent_hero: str = "",
    last_action: Optional[Dict[str, Any]] = None,
    extra_context: Optional[Dict[str, Any]] = None,
):
    """
    Grava a anomalia Sim2Real atomicamente no SQLite e no arquivo JSONL logs/sim2real_anomalies.jsonl.
    """
    now = time.time()
    payload = {
        "timestamp": now,
        "room_id": str(room_id),
        "hero": str(hero or "Unknown"),
        "opponent_hero": str(opponent_hero or "Unknown"),
        "turn": int(turn or 0),
        "phase": str(phase or ""),
        "anomaly_type": str(anomaly_type),
        "message": str(message),
        "last_action": last_action or {},
        "extra_context": extra_context or {},
    }

    # 1. Gravar em arquivo JSONL
    try:
        os.makedirs("logs", exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[Sim2Real] Falha ao gravar JSONL: {e}")

    # 2. Gravar no SQLite
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sim2real_anomalies (
                    room_id, hero, opponent_hero, turn, phase, anomaly_type, raw_message, last_action_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(room_id),
                    str(hero or "Unknown"),
                    str(opponent_hero or "Unknown"),
                    int(turn or 0),
                    str(phase or ""),
                    str(anomaly_type),
                    str(message),
                    json.dumps(last_action or {}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
    except Exception as e:
        print(f"[Sim2Real] Falha ao gravar SQLite: {e}")
