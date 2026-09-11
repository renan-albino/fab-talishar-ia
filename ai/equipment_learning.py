"""
ai/equipment_learning.py
========================
Motor de Aprendizado e Calibração Dinâmica de Uso de Equipamentos por Experiência.

Registra o histórico de ativações e bloqueios de equipamentos por partida,
avalia a contribuição empírica para a taxa de vitória e ajuste de valor posicional,
e fornece multiplicadores dinâmicos para guiar a escolha de ações sem hardcoding.
"""

import os
import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from ai.atomic_io import atomic_json_save

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATS_FILE = os.path.join(DATA_DIR, "equipment_usage_stats.json")
METADATA_FILE = os.path.join(DATA_DIR, "equipment_metadata.json")

_METADATA_CACHE: Optional[Dict[str, Any]] = None


def load_equipment_metadata() -> Dict[str, Any]:
    """Carrega os metadados mecânicos dos equipamentos com cache em memória."""
    global _METADATA_CACHE
    if _METADATA_CACHE is not None:
        return _METADATA_CACHE

    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                _METADATA_CACHE = json.load(f)
                return _METADATA_CACHE
        except Exception:
            pass
    _METADATA_CACHE = {}
    return _METADATA_CACHE


@dataclass
class EquipmentEvent:
    """Evento individual de uso de equipamento (ativação de habilidade ou bloqueio)."""
    hero: str
    eq_name: str
    slot: str = "equipment"
    action_type: str = "ability"  # "ability" ou "block"
    turn: int = 1
    pre_eval: float = 0.0
    post_eval: float = 0.0


class EquipmentTracker:
    """Rastreador volátil em memória para uso de equipamentos durante uma única partida."""

    def __init__(self, hero_name: str = "generic"):
        self.hero_name = str(hero_name).lower().strip()
        self.events: List[EquipmentEvent] = []

    def track_activation(
        self,
        hero: str,
        eq_name: str,
        slot: str = "equipment",
        turn: int = 1,
        pre_eval: float = 0.0,
        post_eval: float = 0.0,
    ) -> None:
        """Registra a ativação de uma habilidade de equipamento."""
        if not eq_name:
            return
        self.events.append(
            EquipmentEvent(
                hero=str(hero or self.hero_name).lower().strip(),
                eq_name=str(eq_name).lower().strip(),
                slot=str(slot).lower().strip(),
                action_type="ability",
                turn=turn,
                pre_eval=pre_eval,
                post_eval=post_eval,
            )
        )

    def track_block(
        self,
        hero: str,
        eq_name: str,
        slot: str = "equipment",
        turn: int = 1,
        pre_eval: float = 0.0,
        post_eval: float = 0.0,
    ) -> None:
        """Registra o uso de um equipamento para bloqueio."""
        if not eq_name:
            return
        self.events.append(
            EquipmentEvent(
                hero=str(hero or self.hero_name).lower().strip(),
                eq_name=str(eq_name).lower().strip(),
                slot=str(slot).lower().strip(),
                action_type="block",
                turn=turn,
                pre_eval=pre_eval,
                post_eval=post_eval,
            )
        )

    def get_events(self) -> List[EquipmentEvent]:
        return list(self.events)

    def clear(self) -> None:
        self.events.clear()


class EquipmentLearningEngine:
    """
    Motor persistente de aprendizado de equipamentos.
    Consolida métricas em data/equipment_usage_stats.json e calcula multiplicadores táticos.
    """

    def __init__(self, stats_path: str = STATS_FILE):
        self.stats_path = stats_path
        self._cache_mtime = 0.0
        self._stats_cache: Dict[str, Any] = {}

    def load_stats(self) -> Dict[str, Any]:
        """Carrega estatísticas com invalidação baseada no mtime do arquivo."""
        if not os.path.exists(self.stats_path):
            return {}
        try:
            mtime = os.path.getmtime(self.stats_path)
            if mtime != self._cache_mtime:
                with open(self.stats_path, "r", encoding="utf-8") as f:
                    self._stats_cache = json.load(f)
                self._cache_mtime = mtime
            return self._stats_cache
        except Exception:
            return self._stats_cache or {}

    def get_equipment_multiplier(self, hero_name: str, eq_name: str, default: float = 1.0) -> float:
        """
        Retorna o multiplicador aprendido para determinado herói e equipamento.
        Varia de [0.5, 2.0], onde 1.0 indica baseline neutro.
        """
        if not eq_name:
            return default

        eq_clean = str(eq_name).lower().strip()
        h_clean = str(hero_name or "generic").lower().strip().replace(" ", "_")
        root_hero = h_clean.split("_")[0] if "_" in h_clean else h_clean

        stats = self.load_stats()

        # 1. Procura por herói específico exato
        hero_dict = stats.get(h_clean, {})
        if eq_clean in hero_dict:
            return float(hero_dict[eq_clean].get("learned_multiplier", default))

        # 2. Fallback para root hero (ex: 'kassai' para 'kassai_of_the_golden_sand')
        if root_hero in stats and eq_clean in stats[root_hero]:
            return float(stats[root_hero][eq_clean].get("learned_multiplier", default))

        # 3. Fallback genérico global
        if "generic" in stats and eq_clean in stats["generic"]:
            return float(stats["generic"][eq_clean].get("learned_multiplier", default))

        return default

    def record_match_result(
        self,
        hero_name: str,
        events: List[EquipmentEvent],
        won: bool,
    ) -> Dict[str, Any]:
        """
        Atualiza as estatísticas com os eventos da partida terminada e salva atomicamente.
        """
        if not events:
            return self.load_stats()

        stats = dict(self.load_stats())
        h_clean = str(hero_name or "generic").lower().strip().replace(" ", "_")
        hero_stats = stats.setdefault(h_clean, {})

        # Agrupa eventos únicos por equipamento por partida para não inflar wins/losses
        seen_eqs = {}
        for ev in events:
            eq_clean = str(ev.eq_name).lower().strip()
            if eq_clean not in seen_eqs:
                seen_eqs[eq_clean] = {"activations": 0, "blocks": 0, "eval_deltas": []}
            if ev.action_type == "ability":
                seen_eqs[eq_clean]["activations"] += 1
            elif ev.action_type == "block":
                seen_eqs[eq_clean]["blocks"] += 1
            delta = ev.post_eval - ev.pre_eval
            if delta != 0.0:
                seen_eqs[eq_clean]["eval_deltas"].append(delta)

        for eq_clean, data in seen_eqs.items():
            eq_stat = hero_stats.setdefault(
                eq_clean,
                {
                    "times_activated": 0,
                    "times_blocked": 0,
                    "wins": 0,
                    "losses": 0,
                    "win_rate": 0.5,
                    "learned_multiplier": 1.0,
                    "avg_eval_gain": 0.0,
                    "total_matches": 0,
                },
            )

            eq_stat["times_activated"] += data["activations"]
            eq_stat["times_blocked"] += data["blocks"]
            eq_stat["total_matches"] += 1
            if won:
                eq_stat["wins"] += 1
            else:
                eq_stat["losses"] += 1

            total_m = eq_stat["wins"] + eq_stat["losses"]
            if total_m > 0:
                wr = float(eq_stat["wins"]) / float(total_m)
                eq_stat["win_rate"] = round(wr, 4)

                # Avaliação de delta posicional
                if data["eval_deltas"]:
                    new_avg = sum(data["eval_deltas"]) / len(data["eval_deltas"])
                    prev_avg = float(eq_stat.get("avg_eval_gain", 0.0))
                    eq_stat["avg_eval_gain"] = round((prev_avg * 0.7) + (new_avg * 0.3), 4)

                # Calibração do multiplicador aprendido:
                # Com poucas partidas, converge suavemente para baseline.
                confidence = min(1.0, total_m / 10.0)
                eval_bonus = max(-0.2, min(0.2, eq_stat.get("avg_eval_gain", 0.0) * 0.05))
                raw_mult = 1.0 + ((wr - 0.5) * 1.0 * confidence) + (eval_bonus * confidence)
                eq_stat["learned_multiplier"] = round(max(0.5, min(2.0, raw_mult)), 4)

        try:
            atomic_json_save(stats, self.stats_path)
            self._stats_cache = stats
            self._cache_mtime = time.time()
        except Exception:
            pass

        return stats


_ENGINE_SINGLETON: Optional[EquipmentLearningEngine] = None


def get_equipment_learning_engine() -> EquipmentLearningEngine:
    """Retorna o singleton do motor de aprendizado de equipamentos."""
    global _ENGINE_SINGLETON
    if _ENGINE_SINGLETON is None:
        _ENGINE_SINGLETON = EquipmentLearningEngine()
    return _ENGINE_SINGLETON
