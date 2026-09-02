#!/usr/bin/env python3
"""
scripts/manage_state.py
=======================
Gerenciador de Estado Essencial e Checkpoints do FaB Talishar AI.

Permite exportar, importar e inspecionar os arquivos essenciais de treinamento
(modelos, replay buffer, métricas e stats) para transferência rápida entre máquinas (~9.5 MB).

Comandos:
  python scripts/manage_state.py --export [caminho.tar.gz]
  python scripts/manage_state.py --import [caminho.tar.gz]
  python scripts/manage_state.py --info
"""

import os
import sys
import json
import tarfile
import argparse
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DEFAULT_EXPORT_PATH = os.path.join(BASE_DIR, "fab_ai_checkpoint_bundle.tar.gz")

ESSENTIAL_FILES = [
    ("checkpoints/teacher_latest.pt", True),
    ("model_latest.pt", False),
    ("replay_buffer.npz", False),
    ("training_metrics.json", False),
    ("training_stats.json", False),
    ("fab_cards_db.json", False),
]

def format_size(bytes_val: int) -> str:
    if bytes_val < 1024:
        return f"{bytes_val} B"
    elif bytes_val < 1024 * 1024:
        return f"{bytes_val / 1024:.1f} KB"
    else:
        return f"{bytes_val / (1024 * 1024):.2f} MB"

def show_info():
    print("==================================================")
    print("   FAB TALISHAR AI — INFORMAÇÕES DE ESTADO ATUAL  ")
    print("==================================================")
    
    total_size = 0
    found_count = 0
    for rel_path, required in ESSENTIAL_FILES:
        full_path = os.path.join(DATA_DIR, rel_path)
        if os.path.exists(full_path):
            size = os.path.getsize(full_path)
            total_size += size
            found_count += 1
            mtime = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime("%Y-%m-%d %H:%M:%S")
            print(f"  ✓ data/{rel_path:<32} {format_size(size):>10}  ({mtime})")
        else:
            tag = "[OBRIGATÓRIO]" if required else "[OPCIONAL]"
            print(f"  ✗ data/{rel_path:<32}   AUSENTE {tag}")

    metrics_file = os.path.join(DATA_DIR, "training_metrics.json")
    if os.path.exists(metrics_file):
        try:
            with open(metrics_file, "r") as f:
                m = json.load(f)
                print("\n  [Resumo do Treino]")
                print(f"    - Épocas Concluídas: {m.get('epochs_completed', 0):,}")
                print(f"    - Partidas Jogadas:  {m.get('total_games', 0):,}")
                print(f"    - Amostras no Buffer:{m.get('samples_collected', 0):,}")
                print(f"    - Loss Total Atual:  {m.get('total_loss', 0.0):.4f}")
        except Exception:
            pass

    stats_file = os.path.join(DATA_DIR, "training_stats.json")
    if os.path.exists(stats_file):
        try:
            with open(stats_file, "r") as f:
                s = json.load(f)
                print("  [Rating Elo Atual]")
                print(f"    - Bot 1 Elo: {s.get('bot1_elo', 1200)} | Bot 2 Elo: {s.get('bot2_elo', 1200)}")
                print(f"    - Total Partidas Registradas: {s.get('total_matches', 0):,}")
        except Exception:
            pass

    print("--------------------------------------------------")
    print(f"  Total de Arquivos: {found_count}/{len(ESSENTIAL_FILES)} ({format_size(total_size)})")
    print("==================================================")

def export_state(dest_path: str = None):
    print("==================================================")
    print("   EXPORTANDO PACOTE DE ESTADO ESSENCIAL         ")
    print("==================================================")

    target_tar = dest_path or DEFAULT_EXPORT_PATH
    added_files = []

    with tarfile.open(target_tar, "w:gz") as tar:
        for rel_path, required in ESSENTIAL_FILES:
            full_path = os.path.join(DATA_DIR, rel_path)
            if os.path.exists(full_path):
                arcname = os.path.join("data", rel_path)
                tar.add(full_path, arcname=arcname)
                added_files.append((rel_path, os.path.getsize(full_path)))
                print(f"  + Adicionado: data/{rel_path} ({format_size(os.path.getsize(full_path))})")
            elif required:
                print(f"  [!] AVISO: Arquivo crítico ausente: data/{rel_path}")

    tar_size = os.path.getsize(target_tar)
    print("--------------------------------------------------")
    print(f"[OK] Pacote gerado com sucesso: {target_tar}")
    print(f"[OK] Tamanho compactado: {format_size(tar_size)} ({len(added_files)} arquivos)")
    print("==================================================")
    print("Para transferir para outra máquina:")
    print(f"  scp {target_tar} usuario@outra-maquina:~/fab-talishar-ia/")
    print("E na outra máquina execute:")
    print(f"  python scripts/manage_state.py --import {os.path.basename(target_tar)}")
    print("==================================================")

def import_state(src_path: str):
    print("==================================================")
    print("   IMPORTANDO PACOTE DE ESTADO ESSENCIAL         ")
    print("==================================================")

    if not os.path.exists(src_path):
        print(f"[ERRO] Arquivo não encontrado: {src_path}")
        sys.exit(1)

    os.makedirs(DATA_DIR, exist_ok=True)

    with tarfile.open(src_path, "r:gz") as tar:
        members = tar.getmembers()
        print(f"Extraindo {len(members)} arquivos para {BASE_DIR}...")
        tar.extractall(path=BASE_DIR)
        for m in members:
            print(f"  ✓ Restaurado: {m.name} ({format_size(m.size)})")

    print("--------------------------------------------------")
    print("[OK] Estado essencial importado com sucesso!")
    print("==================================================")
    show_info()

def main():
    parser = argparse.ArgumentParser(description="Gerenciador de Estado e Checkpoints do FaB Talishar AI")
    parser.add_argument("--info", action="store_true", help="Exibe informações do estado e checkpoints atuais")
    parser.add_argument("--export", nargs="?", const=DEFAULT_EXPORT_PATH, help="Gera um pacote .tar.gz com o estado essencial")
    parser.add_argument("--import-state", "--import", dest="import_path", help="Restaura um pacote .tar.gz gerado previamente")
    args = parser.parse_args()

    if args.export:
        export_state(args.export)
    elif args.import_path:
        import_state(args.import_path)
    else:
        show_info()

if __name__ == "__main__":
    main()
