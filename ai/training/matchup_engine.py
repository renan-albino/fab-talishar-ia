"""
ai/training/matchup_engine.py
=============================
Gerenciador de pareamento balanceado para treinamento autônomo.
Gera ciclos completos de confrontos (todos contra todos, em ambas as orientações host/joiner)
embaralhados aleatoriamente, garantindo que nenhum matchup fique repetindo em loop
e que todos os heróis/decks do pool tenham representação estatística uniforme.
"""

import random
from collections import defaultdict
from typing import Dict, Any, List, Optional, Tuple


class RoundRobinMatchupEngine:
    """
    Gerenciador de pareamento balanceado para treinamento autônomo.
    Gera ciclos completos de confrontos (todos contra todos, em ambas as orientações host/joiner)
    embaralhados aleatoriamente, garantindo que nenhum matchup fique repetindo em loop
    e que todos os heróis/decks do pool tenham representação estatística uniforme.
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = random.Random(seed)
        self._current_pool: List[str] = []
        self._cycle_queue: List[Tuple[str, str]] = []
        self.pair_counts: Dict[Tuple[str, str], int] = defaultdict(int)

    def _generate_cycle(self, pool: List[str]) -> List[Tuple[str, str]]:
        if not pool:
            return [("calling_hamburg_1st", "calling_hamburg_1st")]
        if len(pool) == 1:
            return [(pool[0], pool[0])]

        pairs: List[Tuple[str, str]] = []
        for i in range(len(pool)):
            for j in range(len(pool)):
                if i != j:
                    pairs.append((pool[i], pool[j]))

        self.rng.shuffle(pairs)
        return pairs

    def next_pair(self, pool: List[str]) -> Tuple[str, str]:
        if not pool:
            return ("calling_hamburg_1st", "calling_hamburg_1st")
        if len(pool) == 1:
            return (pool[0], pool[0])

        normalized_pool = sorted(list(pool))
        if normalized_pool != self._current_pool or not self._cycle_queue:
            self._current_pool = normalized_pool
            self._cycle_queue = self._generate_cycle(self._current_pool)

        pair = self._cycle_queue.pop(0)
        self.pair_counts[pair] += 1
        return pair

    def get_stats(self) -> Dict[str, Any]:
        return {
            "total_pairs_dispatched": sum(self.pair_counts.values()),
            "unique_matchups": len(self.pair_counts),
            "queue_remaining": len(self._cycle_queue),
            "pair_counts": {f"{k[0]} vs {k[1]}": v for k, v in self.pair_counts.items()},
        }
