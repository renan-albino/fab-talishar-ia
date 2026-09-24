"""
ai/turn_order_learning.py
=========================
Sistema de Aprendizado e Otimização da Escolha de Quem Começa (First Player).
Permite que os bots aprendam dinamicamente se é melhor escolher 'Go First' ou 'Go Second'
com base no histórico de partidas e priors específicos de cada herói / arquétipo.

Priors de FaB:
- Heróis de Setup (Dash IO, Vynnset, Teklovossen) preferem fortemente "Go First" para
  estabelecer itens com Crank, banir ataques de Runegate e montar Evos sem sofrer pressão.
- Heróis de Tempo / Agressivos aprendem a escolha que maximiza seu winrate no matchup.
"""

import os
import json
import random
from typing import Dict, Any, Tuple
from .logger import get_logger

logger = get_logger("turn_order_learning")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TURN_ORDER_FILE = os.path.join(BASE_DIR, "data", "turn_order_stats.json")

# Heróis que se beneficiam fortemente de começar primeiro (Setup / Engine)
SETUP_HEROES_GO_FIRST = {
    "dash_io",
    "dash_i/o",
    "vynnset",
    "vynsett",
    "vynnset_iron_maiden",
    "teklovossen",
    "professor_teklovossen",
    "teklovossen_esteemed_magnate"
}


class TurnOrderLearner:
    """Gerencia estatísticas de vitórias/partidas de 'Go First' vs 'Go Second' por herói."""

    def __init__(self, stats_file: str = TURN_ORDER_FILE):
        self.stats_file = stats_file
        self.stats: Dict[str, Any] = self._load_stats()

    def _normalize_hero(self, hero_name: str) -> str:
        return str(hero_name or "").lower().strip().replace("-", "_").replace(" ", "_")

    def _load_stats(self) -> Dict[str, Any]:
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Erro ao carregar turn_order_stats.json: {e}")
        return {}

    def _save_stats(self) -> None:
        try:
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=4)
        except Exception as e:
            logger.warning(f"Erro ao salvar turn_order_stats.json: {e}")

    def get_optimal_turn_order(self, hero_name: str, opponent_hero: str = None, epsilon: float = 0.05) -> str:
        """
        Retorna 'Go First' ou 'Go Second' com base no modelo aprendido e priors de FaB.
        Utiliza epsilon-greedy para permitir exploração ocasional.
        """
        clean_hero = self._normalize_hero(hero_name)
        
        # Exploração aleatória para testar a opção alternativa ocasionalmente
        if random.random() < epsilon:
            return random.choice(["Go First", "Go Second"])

        hero_data = self.stats.get(clean_hero, {})
        first_stats = hero_data.get("go_first", {"wins": 0, "matches": 0})
        second_stats = hero_data.get("go_second", {"wins": 0, "matches": 0})

        first_matches = first_stats.get("matches", 0)
        second_matches = second_stats.get("matches", 0)

        # Priors fortes para heróis de setup com menos de 10 partidas registradas em cada lado
        if clean_hero in SETUP_HEROES_GO_FIRST or any(sh in clean_hero for sh in SETUP_HEROES_GO_FIRST):
            if first_matches < 10 or second_matches < 10:
                return "Go First"

        # Se houver histórico estatístico suficiente, escolhe a opção com maior winrate
        if first_matches >= 3 and second_matches >= 3:
            first_wr = first_stats["wins"] / max(1, first_matches)
            second_wr = second_stats["wins"] / max(1, second_matches)
            if first_wr > second_wr + 0.05:
                return "Go First"
            elif second_wr > first_wr + 0.05:
                return "Go Second"

        # Fallback padrão: heróis de setup vão primeiro, demais vão segundo
        if clean_hero in SETUP_HEROES_GO_FIRST or any(sh in clean_hero for sh in SETUP_HEROES_GO_FIRST):
            return "Go First"
        
        return "Go Second"

    def record_match_result(self, hero_name: str, chosen_order: str, won: bool) -> None:
        """Registra o resultado da partida para calibrar o aprendizado."""
        clean_hero = self._normalize_hero(hero_name)
        clean_order = "go_first" if "first" in chosen_order.lower() else "go_second"

        if clean_hero not in self.stats:
            self.stats[clean_hero] = {
                "go_first": {"wins": 0, "matches": 0},
                "go_second": {"wins": 0, "matches": 0}
            }

        slot = self.stats[clean_hero][clean_order]
        slot["matches"] += 1
        if won:
            slot["wins"] += 1

        self._save_stats()
        logger.info(f"[TurnOrderLearner] Registrado para {clean_hero} ({clean_order}): Wins={slot['wins']}/{slot['matches']}")


_GLOBAL_TURN_ORDER_LEARNER = None

def get_turn_order_learner() -> TurnOrderLearner:
    global _GLOBAL_TURN_ORDER_LEARNER
    if _GLOBAL_TURN_ORDER_LEARNER is None:
        _GLOBAL_TURN_ORDER_LEARNER = TurnOrderLearner()
    return _GLOBAL_TURN_ORDER_LEARNER
