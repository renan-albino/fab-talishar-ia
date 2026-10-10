#!/usr/bin/env python3
"""
scripts/clean_training_state.py
===============================
Script direto para limpar e resetar o estado de treinamento:
- Replay Buffer (data/replay_buffer.npz) e trajetórias transitórias (data/trajectories/)
- Épocas e Histórico de Treinamento (data/training_metrics.json, training_stats.json)
- Divergências e Anomalias Sim2Real (logs/sim2real_anomalies.jsonl e SQLite)

Gera backup automático em .tar.gz antes de limpar, salvo se --no-backup for informado.
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from manage_state import clean_training_state

def main():
    parser = argparse.ArgumentParser(description="Limpa e reseta o estado de treinamento (Buffer, Épocas, Sim2Real)")
    parser.add_argument("--no-backup", action="store_true", help="Não gerar backup antes de limpar")
    parser.add_argument("--backup-path", help="Caminho específico para o arquivo de backup .tar.gz")
    parser.add_argument("--skip-sim2real", action="store_true", help="Não limpar anomalias Sim2Real")
    parser.add_argument("--skip-metrics", action="store_true", help="Não resetar épocas e métricas")
    parser.add_argument("--skip-buffer", action="store_true", help="Não remover o replay buffer")
    args = parser.parse_args()

    clean_training_state(
        backup=not args.no_backup,
        include_buffer=not args.skip_buffer,
        include_metrics=not args.skip_metrics,
        include_sim2real=not args.skip_sim2real,
        backup_path=args.backup_path,
    )

if __name__ == "__main__":
    main()
