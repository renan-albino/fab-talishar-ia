"""
ai/training
===========
Pacote modular de orquestração e balanceamento de treinamento autônomo na GPU.
"""

from ai.training.matchup_engine import RoundRobinMatchupEngine
from ai.training.process_supervisor import (
    kill_active_processes,
    kill_orphan_bots,
    is_process_alive,
    get_active_pids,
    wait_for_processes,
    terminate_process_cleanly,
)
from ai.training.orchestrator import GPUTrainingOrchestrator

__all__ = [
    "GPUTrainingOrchestrator",
    "RoundRobinMatchupEngine",
    "kill_active_processes",
    "kill_orphan_bots",
    "is_process_alive",
    "get_active_pids",
    "wait_for_processes",
    "terminate_process_cleanly",
]
