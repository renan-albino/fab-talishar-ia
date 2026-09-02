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

def get_release_notes(tag: str) -> str:
    epochs, games, samples, loss = 0, 0, 0, 0.0
    b1_elo, b2_elo = 1200, 1200
    
    metrics_file = os.path.join(DATA_DIR, "training_metrics.json")
    if os.path.exists(metrics_file):
        try:
            with open(metrics_file, "r") as f:
                m = json.load(f)
                epochs = m.get("epochs_completed", 0)
                games = m.get("total_games", 0)
                samples = m.get("samples_collected", 0)
                loss = m.get("total_loss", 0.0)
        except Exception:
            pass

    stats_file = os.path.join(DATA_DIR, "training_stats.json")
    if os.path.exists(stats_file):
        try:
            with open(stats_file, "r") as f:
                s = json.load(f)
                b1_elo = s.get("bot1_elo", 1200)
                b2_elo = s.get("bot2_elo", 1200)
        except Exception:
            pass

    return f"""## ⚔️ FaB Talishar AI — Checkpoint `{tag}`

Snapshot do estado essencial de treinamento: pesos da rede neural (PyTorch Policy-Value ResNet), replay buffer e métricas de auto-treinamento.

### 📊 Métricas do Checkpoint:
* **Épocas Concluídas:** {epochs:,}
* **Partidas de Treino:** {games:,}
* **Amostras no Replay Buffer:** {samples:,}
* **Loss Total Atual:** {loss:.4f}
* **Rating Elo Atual:** Bot 1 ({b1_elo}) | Bot 2 ({b2_elo})

### 📦 Como Usar em Qualquer Máquina:
```bash
# 1. Baixar o checkpoint bundle
python scripts/manage_state.py --download-release {tag}

# 2. Iniciar o sistema (compatível com GPU ou CPU)
./start.sh
```
"""

def publish_release(tag: str = "v1.0"):
    print("==================================================")
    print(f"   PUBLICANDO GITHUB RELEASE ({tag})              ")
    print("==================================================")

    # 1. Garante que o pacote .tar.gz existe
    if not os.path.exists(DEFAULT_EXPORT_PATH):
        export_state(DEFAULT_EXPORT_PATH)
    else:
        print(f"  ✓ Pacote existente detectado: {DEFAULT_EXPORT_PATH} ({format_size(os.path.getsize(DEFAULT_EXPORT_PATH))})")

    notes = get_release_notes(tag)
    title = f"FaB AI Engine Checkpoint {tag}"

    # 2. Testa autenticação do gh CLI
    import subprocess
    gh_cmd = shutil.which("gh") if "shutil" in globals() else None
    if not gh_cmd:
        import shutil
        gh_cmd = shutil.which("gh")

    is_authenticated = False
    if gh_cmd:
        r = subprocess.run([gh_cmd, "auth", "status"], capture_output=True, text=True)
        is_authenticated = (r.returncode == 0)

    if gh_cmd and is_authenticated:
        print(f"[*] gh CLI autenticado detectado. Enviando release...")
        cmd = [
            gh_cmd, "release", "create", tag,
            DEFAULT_EXPORT_PATH,
            "--title", title,
            "--notes", notes,
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print("[OK] Release publicada com sucesso no GitHub!")
            print(res.stdout)
            return
        else:
            print(f"[!] Erro ao criar release via gh: {res.stderr.strip()}")

    # 3. Fallback com orientações passo a passo
    print("\n[!] O GitHub CLI precisa de autenticação rápida ou você pode criar via Web:")
    print("--------------------------------------------------")
    print("OPÇÃO A (Automática via Terminal):")
    print("  1. Execute: gh auth login")
    print("  2. Em seguida execute:")
    print(f"     gh release create {tag} fab_ai_checkpoint_bundle.tar.gz --title \"{title}\" --notes \"{notes.splitlines()[0]}\"")
    print("\nOPÇÃO B (Interface Web em 1 Clique):")
    print("  1. Acesse: https://github.com/renan-albino/fab-talishar-ia/releases/new")
    print(f"  2. Tag version: {tag}")
    print(f"  3. Release title: {title}")
    print(f"  4. Arraste e solte o arquivo: {DEFAULT_EXPORT_PATH}")
    print("  5. Clique em 'Publish release'!")
    print("==================================================")

def download_release(tag: str = "latest"):
    print("==================================================")
    print(f"   BAIXANDO GITHUB RELEASE ({tag})                ")
    print("==================================================")

    import subprocess
    import shutil
    gh_cmd = shutil.which("gh")

    downloaded = False
    dest_tar = DEFAULT_EXPORT_PATH

    if gh_cmd:
        cmd = [gh_cmd, "release", "download", tag, "--pattern", "fab_ai_checkpoint_bundle.tar.gz", "--dir", BASE_DIR, "--clobber"]
        res = subprocess.run(cmd)
        if res.returncode == 0 and os.path.exists(dest_tar):
            downloaded = True

    if not downloaded:
        print("[*] Tentando download via curl...")
        url = (
            f"https://github.com/renan-albino/fab-talishar-ia/releases/latest/download/fab_ai_checkpoint_bundle.tar.gz"
            if tag == "latest"
            else f"https://github.com/renan-albino/fab-talishar-ia/releases/download/{tag}/fab_ai_checkpoint_bundle.tar.gz"
        )
        r = subprocess.run(["curl", "-sL", url, "-o", dest_tar])
        if r.returncode == 0 and os.path.exists(dest_tar) and os.path.getsize(dest_tar) > 1000:
            downloaded = True

    if downloaded:
        print(f"[OK] Pacote baixado com sucesso: {dest_tar} ({format_size(os.path.getsize(dest_tar))})")
        import_state(dest_tar)
    else:
        print(f"[ERRO] Não foi possível baixar a release {tag}.")
        print("Verifique se a release existe em https://github.com/renan-albino/fab-talishar-ia/releases")

def main():
    parser = argparse.ArgumentParser(description="Gerenciador de Estado e Checkpoints do FaB Talishar AI")
    parser.add_argument("--info", action="store_true", help="Exibe informações do estado e checkpoints atuais")
    parser.add_argument("--export", nargs="?", const=DEFAULT_EXPORT_PATH, help="Gera um pacote .tar.gz com o estado essencial")
    parser.add_argument("--import-state", "--import", dest="import_path", help="Restaura um pacote .tar.gz gerado previamente")
    parser.add_argument("--publish-release", nargs="?", const="v1.0", help="Publica uma release no GitHub com o pacote de checkpoints (default: v1.0)")
    parser.add_argument("--download-release", nargs="?", const="latest", help="Baixa uma release do GitHub e restaura automaticamente (default: latest)")
    args = parser.parse_args()

    if args.publish_release:
        publish_release(args.publish_release)
    elif args.download_release:
        download_release(args.download_release)
    elif args.export:
        export_state(args.export)
    elif args.import_path:
        import_state(args.import_path)
    else:
        show_info()

if __name__ == "__main__":
    main()
