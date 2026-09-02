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

MTIME_MARKER_FILE = os.path.join(DATA_DIR, ".last_release_mtime")
HOOK_PATH = os.path.join(BASE_DIR, ".git", "hooks", "post-commit")

def publish_release(tag: str = "checkpoint-latest", force: bool = False):
    print("==================================================")
    print(f"   PUBLICANDO GITHUB RELEASE ({tag})              ")
    print("==================================================")

    # 1. Garante que o pacote .tar.gz existe e está atualizado
    export_state(DEFAULT_EXPORT_PATH)

    notes = get_release_notes(tag)
    title = f"FaB AI Engine Checkpoint ({tag})"

    # 2. Testa autenticação do gh CLI
    import subprocess
    import shutil
    gh_cmd = shutil.which("gh")

    is_authenticated = False
    if gh_cmd:
        r = subprocess.run([gh_cmd, "auth", "status"], capture_output=True, text=True)
        is_authenticated = (r.returncode == 0)

    if gh_cmd and is_authenticated:
        print(f"[*] gh CLI autenticado. Verificando release '{tag}'...")
        
        # Verifica se a release já existe
        check = subprocess.run([gh_cmd, "release", "view", tag], capture_output=True, text=True)
        if check.returncode == 0:
            print(f"[*] Release '{tag}' existente detectada. Atualizando arquivo e notas...")
            up_res = subprocess.run([gh_cmd, "release", "upload", tag, DEFAULT_EXPORT_PATH, "--clobber"], capture_output=True, text=True)
            edit_res = subprocess.run([gh_cmd, "release", "edit", tag, "--title", title, "--notes", notes], capture_output=True, text=True)
            if up_res.returncode == 0:
                print(f"[OK] Release '{tag}' atualizada com sucesso no GitHub!")
                record_release_mtime()
                return
        else:
            print(f"[*] Criando nova release '{tag}'...")
            cmd = [
                gh_cmd, "release", "create", tag,
                DEFAULT_EXPORT_PATH,
                "--title", title,
                "--notes", notes,
            ]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                print(f"[OK] Release '{tag}' publicada com sucesso no GitHub!")
                print(res.stdout.strip())
                record_release_mtime()
                return
            else:
                print(f"[!] Erro ao criar release: {res.stderr.strip()}")

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

def record_release_mtime():
    teacher_path = os.path.join(DATA_DIR, "checkpoints", "teacher_latest.pt")
    if os.path.exists(teacher_path):
        mtime = os.path.getmtime(teacher_path)
        try:
            with open(MTIME_MARKER_FILE, "w") as f:
                f.write(str(mtime))
        except Exception:
            pass

def auto_release_on_commit():
    teacher_path = os.path.join(DATA_DIR, "checkpoints", "teacher_latest.pt")
    if not os.path.exists(teacher_path):
        return

    curr_mtime = os.path.getmtime(teacher_path)
    last_mtime = 0.0
    if os.path.exists(MTIME_MARKER_FILE):
        try:
            with open(MTIME_MARKER_FILE, "r") as f:
                last_mtime = float(f.read().strip())
        except Exception:
            last_mtime = 0.0

    # Se o checkpoint não mudou desde a última publicação, não faz nada
    if curr_mtime <= last_mtime:
        print("[*] [Post-Commit Hook] Checkpoint de IA inalterado desde o último upload. Pulando release.")
        return

    print("\n==================================================")
    print("   [Post-Commit Hook] NOVO CHECKPOINT DETECTADO!  ")
    print("==================================================")
    print("Atualizando release 'checkpoint-latest' no GitHub...")
    publish_release("checkpoint-latest")

def install_git_hook():
    print("==================================================")
    print("   INSTALANDO GIT POST-COMMIT HOOK               ")
    print("==================================================")
    hook_dir = os.path.dirname(HOOK_PATH)
    if not os.path.exists(hook_dir):
        print(f"[ERRO] Diretório .git/hooks não encontrado.")
        sys.exit(1)

    hook_content = """#!/usr/bin/env bash
# Git post-commit hook gerado por scripts/manage_state.py
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PY_BIN="$ROOT_DIR/venv/bin/python"
if [ ! -f "$PY_BIN" ]; then
    PY_BIN="python3"
fi

if [ -f "$ROOT_DIR/scripts/manage_state.py" ]; then
    "$PY_BIN" "$ROOT_DIR/scripts/manage_state.py" --auto-release
fi
"""
    with open(HOOK_PATH, "w") as f:
        f.write(hook_content)

    os.chmod(HOOK_PATH, 0o755)
    print(f"[OK] Hook post-commit instalado com sucesso em: {HOOK_PATH}")
    print("     A cada 'git commit', se houver um novo checkpoint treinado,")
    print("     ele será empacotado e enviado automaticamente para o GitHub Releases!")
    print("==================================================")

def uninstall_git_hook():
    if os.path.exists(HOOK_PATH):
        os.remove(HOOK_PATH)
        print(f"[OK] Hook post-commit removido: {HOOK_PATH}")
    else:
        print(f"[!] Nenhum hook post-commit estava instalado.")

def init_checkpoint():
    """Gera um checkpoint inicial com pesos da rede neural caso ainda não exista."""
    teacher_path = os.path.join(DATA_DIR, "checkpoints", "teacher_latest.pt")
    if os.path.exists(teacher_path):
        print(f"[*] Checkpoint já existente em: {teacher_path} ({format_size(os.path.getsize(teacher_path))})")
        return

    os.makedirs(os.path.dirname(teacher_path), exist_ok=True)
    try:
        from ai.model import create_model
        import torch
        model, dev = create_model()
        torch.save(model.state_dict(), teacher_path)
        print(f"[OK] Checkpoint inicial criado com sucesso: {teacher_path} ({format_size(os.path.getsize(teacher_path))})")
    except ImportError:
        venv_py = os.path.join(BASE_DIR, "venv", "bin", "python")
        if os.path.exists(venv_py) and sys.executable != venv_py:
            import subprocess
            subprocess.run([venv_py, __file__, "--init-checkpoint"])
            return
        print("[!] Erro: PyTorch não está instalado no ambiente Python atual.")
    except Exception as e:
        print(f"[!] Erro ao criar checkpoint: {e}")

def download_release(tag: str = "latest"):
    print("==================================================")
    print(f"   BAIXANDO GITHUB RELEASE ({tag})                ")
    print("==================================================")

    import subprocess
    import shutil
    gh_cmd = shutil.which("gh")

    downloaded = False
    dest_tar = DEFAULT_EXPORT_PATH

    actual_tag = "checkpoint-latest" if tag in ("latest", "checkpoint-latest") else tag

    if gh_cmd:
        print("[*] Tentando download via GitHub CLI (gh)...")
        # Remove arquivo local existente antes do download para garantir compatibilidade
        # com versões do gh CLI que não suportam a flag --clobber no download
        if os.path.exists(dest_tar):
            try:
                os.remove(dest_tar)
            except Exception:
                pass

        cmd = [gh_cmd, "release", "download", actual_tag, "--pattern", "fab_ai_checkpoint_bundle.tar.gz", "--dir", BASE_DIR]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0 and os.path.exists(dest_tar) and os.path.getsize(dest_tar) > 1000:
            downloaded = True
        elif res.returncode != 0:
            print(f"[!] gh release download retornou: {res.stderr.strip() or res.stdout.strip()}")

    if not downloaded:
        print("[*] Tentando download direto via curl...")
        url = f"https://github.com/renan-albino/fab-talishar-ia/releases/download/{actual_tag}/fab_ai_checkpoint_bundle.tar.gz"
        curl_cmd = ["curl", "-sL", "-f", url, "-o", dest_tar]

        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        if token:
            curl_cmd = ["curl", "-sL", "-f", "-H", f"Authorization: Bearer {token}", url, "-o", dest_tar]

        r = subprocess.run(curl_cmd)
        if r.returncode == 0 and os.path.exists(dest_tar) and os.path.getsize(dest_tar) > 1000:
            downloaded = True
        else:
            if os.path.exists(dest_tar) and os.path.getsize(dest_tar) <= 1000:
                try:
                    os.remove(dest_tar)
                except Exception:
                    pass

    if downloaded:
        print(f"[OK] Pacote baixado com sucesso: {dest_tar} ({format_size(os.path.getsize(dest_tar))})")
        import_state(dest_tar)
    else:
        print(f"\n[ERRO] Não foi possível baixar a release '{tag}'.")
        print("Possíveis causas e soluções:")
        print(f"  1. A release '{actual_tag}' ainda não foi publicada no GitHub com o arquivo anexado.")
        print(f"     Verifique em: https://github.com/renan-albino/fab-talishar-ia/releases")
        print("  2. O repositório é PRIVADO: o GitHub bloqueia downloads públicos via curl (retorna 404).")
        print("     -> Para resolver com GitHub CLI (Recomendado):")
        print("        sudo apt install gh")
        print("        gh auth login")
        print(f"        python3 scripts/manage_state.py --download-release {tag}")
        print("  3. Transferência Manual sem GitHub:")
        print("     -> Na máquina de origem com o modelo:")
        print("        python3 scripts/manage_state.py --export")
        print("     -> Copie 'fab_ai_checkpoint_bundle.tar.gz' para esta máquina e execute:")
        print("        python3 scripts/manage_state.py --import fab_ai_checkpoint_bundle.tar.gz")

def main():
    parser = argparse.ArgumentParser(description="Gerenciador de Estado e Checkpoints do FaB Talishar AI")
    parser.add_argument("--info", action="store_true", help="Exibe informações do estado e checkpoints atuais")
    parser.add_argument("--export", nargs="?", const=DEFAULT_EXPORT_PATH, help="Gera um pacote .tar.gz com o estado essencial")
    parser.add_argument("--import-state", "--import", dest="import_path", help="Restaura um pacote .tar.gz gerado previamente")
    parser.add_argument("--init-checkpoint", action="store_true", help="Gera um checkpoint inicial caso ainda não exista")
    parser.add_argument("--publish-release", nargs="?", const="checkpoint-latest", help="Publica uma release no GitHub com o pacote de checkpoints (default: checkpoint-latest)")
    parser.add_argument("--download-release", nargs="?", const="latest", help="Baixa uma release do GitHub e restaura automaticamente (default: latest)")
    parser.add_argument("--auto-release", action="store_true", help="Chamado pelo hook post-commit: publica se o checkpoint foi alterado")
    parser.add_argument("--install-hook", action="store_true", help="Instala o hook post-commit para upload automático em git commit")
    parser.add_argument("--uninstall-hook", action="store_true", help="Remove o hook post-commit")
    args = parser.parse_args()

    if args.init_checkpoint:
        init_checkpoint()
    elif args.install_hook:
        install_git_hook()
    elif args.uninstall_hook:
        uninstall_git_hook()
    elif args.auto_release:
        auto_release_on_commit()
    elif args.publish_release:
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
