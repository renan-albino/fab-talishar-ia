"""
ai/trainer.py
=============
Fachada retrocompatível para o subsistema de treinamento autônomo.
Decomposto e modularizado no pacote ai.training (orchestrator, matchup_engine, process_supervisor).
"""

from ai.training import GPUTrainingOrchestrator, RoundRobinMatchupEngine
from ai.training.orchestrator import DATA_DIR, METRICS_FILE

__all__ = [
    "GPUTrainingOrchestrator",
    "RoundRobinMatchupEngine",
    "DATA_DIR",
    "METRICS_FILE",
]
