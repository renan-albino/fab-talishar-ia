#!/usr/bin/env python3
"""
scripts/prepare_environment.py
==============================
Script de automação unificada para preparar, sincronizar e validar 100% do ecossistema
FaB Talishar AI em qualquer máquina Linux ou WSL2.

Ações automatizadas:
  1. Cria e valida diretórios essenciais (`data/`, `logs/`, `decks/`).
  2. Sincroniza e aplica patches customizados de `setup_templates/` para `Talishar/` (PHP/APIs)
     e `Talishar-FE/` (React/Vite).
  3. Ajusta permissões de escrita em disco (`chmod 775` em `Talishar/Games/` e `logs/`).
  4. Extrai e indexa o banco oficial de 10.144 cartas em `data/fab_cards_db.json`.
  5. Valida o diretório central exclusivo de baralhos (`decks/`).
  6. Inspeciona os containers Docker do Talishar (Apache, MySQL, Redis) e sobe-os se necessário.
  7. Suporte a flag `--export-templates` para salvar o estado atual do código em `setup_templates/`.
"""

import os
import sys
import shutil
import subprocess
import json
import argparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DECKS_DIR = os.path.join(BASE_DIR, "decks")
TEMPLATES_DIR = os.path.join(BASE_DIR, "setup_templates")
TALISHAR_DIR = os.path.join(BASE_DIR, "Talishar")
TALISHAR_FE_DIR = os.path.join(BASE_DIR, "Talishar-FE")

BACKEND_MAPPINGS = [
    ("docker-compose.yml", "docker-compose.yml"),
    ("APIKeys/APIKeys.php.template", "APIKeys/APIKeys.php.template"),
    ("APIs/AppendGameLog.php", "APIs/AppendGameLog.php"),
    ("APIs/GetLobbyRefresh.php", "APIs/GetLobbyRefresh.php"),
    ("APIs/GetFavoriteDecks.php", "APIs/GetFavoriteDecks.php"),
    ("APIs/JoinGame.php", "APIs/JoinGame.php"),
    ("APIs/CreateGame.php", "APIs/CreateGame.php"),
    ("APIs/APIParseGamefile.php", "APIs/APIParseGamefile.php"),
    ("APIs/SubmitSideboard.php", "APIs/SubmitSideboard.php"),
    ("AI/CombatDummy.php", "AI/CombatDummy.php"),
    ("Libraries/HTTPLibraries.php", "Libraries/HTTPLibraries.php"),
    ("Libraries/PlayerSettings.php", "Libraries/PlayerSettings.php"),
    ("ProcessInput.php", "ProcessInput.php"),
    ("MenuFiles/WriteGamefile.php", "MenuFiles/WriteGamefile.php"),
]

FRONTEND_MAPPINGS = [
    ("chatBox/ChessAdvantageTracker.tsx", "src/routes/game/components/elements/chatBox/ChessAdvantageTracker.tsx"),
    ("chatBox/ChessAdvantageTracker.module.css", "src/routes/game/components/elements/chatBox/ChessAdvantageTracker.module.css"),
    ("chatBox/ChatBox.tsx", "src/routes/game/components/elements/chatBox/ChatBox.tsx"),
    ("features/GameSlice.ts", "src/features/game/GameSlice.ts"),
    ("lobby/StickyFooter.tsx", "src/routes/game/lobby/components/stickyFooter/StickyFooter.tsx"),
    ("lobby/LobbyChat.tsx", "src/routes/game/lobby/components/lobbyChat/LobbyChat.tsx"),
    ("components/Header.tsx", "src/components/header/Header.tsx"),
    ("routes.tsx", "src/routes.tsx"),
    ("bannerUnit/AdUnit.tsx", "src/components/bannerUnit/AdUnit.tsx"),
    ("bannerUnit/index.ts", "src/components/bannerUnit/index.ts"),
    ("vite.config.mts", "vite.config.mts"),
]

def log(msg):
    print(f"[*] {msg}")

def log_success(msg):
    print(f"[OK] {msg}")

def log_warn(msg):
    print(f"[!] {msg}")

def get_docker_compose_cmd():
    try:
        r = subprocess.run(["docker", "compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            return ["docker", "compose"]
    except Exception:
        pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return None
def ensure_system_idempotence():
    log("Inspecionando sistema operacional e camada de idempotência...")
    is_container = os.path.exists("/run/.containerenv") or os.path.exists("/.dockerenv")
    is_vanilla = False
    
    # 1. Detecção de Vanilla OS / Host Linux
    if os.path.exists("/etc/os-release"):
        try:
            with open("/etc/os-release") as f:
                content = f.read()
                if "vanilla" in content.lower():
                    is_vanilla = True
        except Exception:
            pass
    if os.path.exists("/run/host/usr/bin/podman") or os.path.exists("/run/host/abimage.abr"):
        is_vanilla = True

    # 2. Configuração do socket Podman / Docker
    uid = os.getuid()
    podman_sock = f"/run/user/{uid}/podman/podman.sock"
    if os.path.exists(podman_sock) or is_vanilla or is_container:
        if not os.path.exists(podman_sock):
            for cmd in [
                ["systemctl", "--user", "start", "podman.socket"],
                ["distrobox-host-exec", "systemctl", "--user", "start", "podman.socket"]
            ]:
                try:
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
        
        if os.path.exists(podman_sock):
            os.environ["DOCKER_HOST"] = f"unix://{podman_sock}"
            if not os.path.exists("/var/run/docker.sock"):
                try:
                    subprocess.run(["sudo", "-n", "ln", "-sfn", podman_sock, "/var/run/docker.sock"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception:
                    pass
            log_success(f"Podman API Socket ativo e compatível com Docker ({podman_sock}).")

    # 3. Configuração do Streamlit para evitar prompts interativos
    streamlit_config_dir = os.path.expanduser("~/.streamlit")
    streamlit_config_file = os.path.join(streamlit_config_dir, "config.toml")
    os.makedirs(streamlit_config_dir, exist_ok=True)
    if not os.path.exists(streamlit_config_file):
        with open(streamlit_config_file, "w", encoding="utf-8") as sf:
            sf.write("[browser]\ngatherUsageStats = false\n\n[server]\nheadless = true\n")
        log_success("Configuração do Streamlit gravada em ~/.streamlit/config.toml.")

    # 4. Arquivos obrigatórios do backend Talishar
    redirector_tpl = os.path.join(TALISHAR_DIR, "HostFiles", "RedirectorTemplate.php")
    redirector_php = os.path.join(TALISHAR_DIR, "HostFiles", "Redirector.php")
    if os.path.exists(redirector_tpl) and not os.path.exists(redirector_php):
        shutil.copy2(redirector_tpl, redirector_php)

    apikeys_tpl = os.path.join(TALISHAR_DIR, "APIKeys", "APIKeys.php.template")
    apikeys_php = os.path.join(TALISHAR_DIR, "APIKeys", "APIKeys.php")
    if os.path.exists(apikeys_tpl) and not os.path.exists(apikeys_php):
        shutil.copy2(apikeys_tpl, apikeys_php)

    game_counter = os.path.join(TALISHAR_DIR, "HostFiles", "GameIDCounter.txt")
    if not os.path.exists(game_counter):
        os.makedirs(os.path.dirname(game_counter), exist_ok=True)
        with open(game_counter, "w") as f:
            f.write("1\n")

    # 5. Garantir .env no frontend
    fe_env_tpl = os.path.join(TALISHAR_FE_DIR, ".env.template")
    fe_env = os.path.join(TALISHAR_FE_DIR, ".env")
    if os.path.exists(fe_env_tpl) and not os.path.exists(fe_env):
        shutil.copy2(fe_env_tpl, fe_env)

    log_success("Camada de idempotência do sistema validada.")

def ensure_talishar_backend():
    log("Verificando integridade do backend Talishar...")
    if not os.path.exists(os.path.join(TALISHAR_DIR, "docker-compose.yml")):
        log_warn("docker-compose.yml não encontrado em Talishar/.")
        workspace_backend = os.path.join(BASE_DIR, "talishar_workspace", "Talishar")
        if os.path.exists(os.path.join(workspace_backend, "docker-compose.yml")):
            log("Sincronizando Talishar a partir de talishar_workspace/...")
            shutil.copytree(workspace_backend, TALISHAR_DIR, dirs_exist_ok=True)
            log_success("Backend Talishar importado com sucesso.")
        else:
            log("Clonando repositório oficial do Talishar...")
            subprocess.run(["git", "clone", "--depth", "1", "https://github.com/Talishar/Talishar.git", TALISHAR_DIR], check=True)
            log_success("Repositório oficial Talishar clonado com sucesso.")

def ensure_talishar_frontend():
    log("Verificando integridade do frontend Talishar-FE...")
    if not os.path.exists(os.path.join(TALISHAR_FE_DIR, "package.json")):
        log_warn("package.json não encontrado em Talishar-FE/.")
        workspace_frontend = os.path.join(BASE_DIR, "talishar_workspace", "Talishar-FE")
        if os.path.exists(os.path.join(workspace_frontend, "package.json")):
            log("Sincronizando Talishar-FE a partir de talishar_workspace/...")
            shutil.copytree(workspace_frontend, TALISHAR_FE_DIR, dirs_exist_ok=True)
            log_success("Frontend Talishar-FE importado com sucesso.")
        else:
            log("Clonando repositório oficial do Talishar-FE...")
            subprocess.run(["git", "clone", "--depth", "1", "https://github.com/Talishar/Talishar-FE.git", TALISHAR_FE_DIR], check=True)
            log_success("Repositório oficial Talishar-FE clonado com sucesso.")

def ensure_talishar_repositories():
    log("Verificando integridade dos repositórios Talishar e Talishar-FE...")
    ensure_talishar_backend()
    ensure_talishar_frontend()

def ensure_directories():
    log("Verificando estrutura de diretórios do projeto...")
    for d in [DATA_DIR, LOGS_DIR, DECKS_DIR]:
        os.makedirs(d, exist_ok=True)
        try:
            os.chmod(d, 0o775)
        except Exception:
            pass
    log_success("Diretórios essenciais prontos (data/, logs/, decks/).")

def apply_backend_templates():
    backend_templates = os.path.join(TEMPLATES_DIR, "backend")
    if os.path.exists(backend_templates) and os.path.exists(TALISHAR_DIR):
        for src_rel, dst_rel in BACKEND_MAPPINGS:
            src_f = os.path.join(backend_templates, src_rel)
            dst_f = os.path.join(TALISHAR_DIR, dst_rel)
            if os.path.exists(src_f):
                os.makedirs(os.path.dirname(dst_f), exist_ok=True)
                shutil.copy2(src_f, dst_f)
                log(f"  -> Patch Backend aplicado: Talishar/{dst_rel}")
        log_success("Todos os patches do backend Talishar foram aplicados.")

def apply_frontend_templates():
    frontend_templates = os.path.join(TEMPLATES_DIR, "frontend")
    if os.path.exists(frontend_templates) and os.path.exists(TALISHAR_FE_DIR):
        for src_rel, dst_rel in FRONTEND_MAPPINGS:
            src_f = os.path.join(frontend_templates, src_rel)
            dst_f = os.path.join(TALISHAR_FE_DIR, dst_rel)
            if os.path.exists(src_f):
                os.makedirs(os.path.dirname(dst_f), exist_ok=True)
                shutil.copy2(src_f, dst_f)
                log(f"  -> Componente Frontend aplicado: Talishar-FE/{dst_rel}")
        log_success("Todos os componentes e patches do frontend foram sincronizados.")

def apply_custom_templates():
    log("Aplicando arquivos customizados e patches de setup_templates/...")
    apply_backend_templates()
    apply_frontend_templates()

def export_active_to_templates():
    log("Exportando arquivos ativos de Talishar/ e Talishar-FE/ para setup_templates/...")
    backend_templates = os.path.join(TEMPLATES_DIR, "backend")
    frontend_templates = os.path.join(TEMPLATES_DIR, "frontend")
    
    os.makedirs(backend_templates, exist_ok=True)
    os.makedirs(frontend_templates, exist_ok=True)

    for dst_rel, src_rel in BACKEND_MAPPINGS:
        src_f = os.path.join(TALISHAR_DIR, src_rel)
        dst_f = os.path.join(backend_templates, dst_rel)
        if os.path.exists(src_f):
            os.makedirs(os.path.dirname(dst_f), exist_ok=True)
            shutil.copy2(src_f, dst_f)
            log(f"  -> Template Backend exportado: setup_templates/backend/{dst_rel}")

    for dst_rel, src_rel in FRONTEND_MAPPINGS:
        src_f = os.path.join(TALISHAR_FE_DIR, src_rel)
        dst_f = os.path.join(frontend_templates, dst_rel)
        if os.path.exists(src_f):
            os.makedirs(os.path.dirname(dst_f), exist_ok=True)
            shutil.copy2(src_f, dst_f)
            log(f"  -> Template Frontend exportado: setup_templates/frontend/{dst_rel}")

    check_unmapped_changes()
    log_success("Exportação de templates concluída com sucesso.")

def check_unmapped_changes():
    """Detecta arquivos novos ou componentes críticos em Talishar/ e Talishar-FE/ que ainda não estão mapeados."""
    unmapped = []
    
    # 1. Backend (foco em APIs customizadas e lógica AI)
    if os.path.exists(os.path.join(TALISHAR_DIR, ".git")):
        try:
            res = subprocess.run(["git", "-C", TALISHAR_DIR, "status", "--porcelain"], capture_output=True, text=True)
            mapped_srcs = {src for _, src in BACKEND_MAPPINGS}
            for line in res.stdout.splitlines():
                status = line[:2]
                fpath = line[3:].strip()
                if fpath.startswith(("Games/", "HostFiles/", "logs/", "decks", "deck.json", "game/", "fix_and_start", "composer.lock", "data")):
                    continue
                if (status == "??" or fpath.startswith(("APIs/", "AI/"))) and fpath not in mapped_srcs and not any(src.startswith(fpath) for src in mapped_srcs):
                    unmapped.append(("Backend", fpath))
        except Exception:
            pass

    # 2. Frontend (foco em rotas, features e componentes customizados)
    if os.path.exists(os.path.join(TALISHAR_FE_DIR, ".git")):
        try:
            res = subprocess.run(["git", "-C", TALISHAR_FE_DIR, "status", "--porcelain"], capture_output=True, text=True)
            mapped_srcs = {src for _, src in FRONTEND_MAPPINGS}
            for line in res.stdout.splitlines():
                status = line[:2]
                fpath = line[3:].strip()
                if fpath.startswith(("build/", "dist/", "node_modules/", "package-lock.json")):
                    continue
                if (status == "??" or fpath.startswith("src/")) and fpath not in mapped_srcs and not any(src.startswith(fpath) for src in mapped_srcs):
                    unmapped.append(("Frontend", fpath))
        except Exception:
            pass

    if unmapped:
        log_warn(f"Detectados {len(unmapped)} arquivos customizados não mapeados em setup_templates/:")
        for kind, fpath in unmapped[:10]:
            print(f"    - [{kind}] {fpath}")
        if len(unmapped) > 10:
            print(f"    ... e mais {len(unmapped) - 10} arquivo(s).")
        print("    Para incluir novos arquivos permanentes, adicione-os a BACKEND_MAPPINGS ou FRONTEND_MAPPINGS em scripts/prepare_environment.py.")
    else:
        log_success("Todos os arquivos customizados em Talishar e Talishar-FE estão devidamente mapeados.")
    return unmapped

def fix_permissions():
    log("Ajustando permissões de arquivos e pastas no Talishar...")
    for sub in ["Games", "HostFiles", "AccountFiles", "APIKeys"]:
        p = os.path.join(TALISHAR_DIR, sub)
        if os.path.exists(p):
            try:
                # O container Docker roda Apache como www-data (UID 33) enquanto o host roda como usuário comum.
                # Permissões 777 nestas pastas específicas de I/O são necessárias para compartilhamento de volumes.
                subprocess.run(["chmod", "777", p], stderr=subprocess.DEVNULL, check=False)
                for f in os.listdir(p):
                    fp = os.path.join(p, f)
                    if os.path.isfile(fp):
                        subprocess.run(["chmod", "666", fp], stderr=subprocess.DEVNULL, check=False)
            except Exception:
                pass
    if os.path.exists(LOGS_DIR):
        try:
            subprocess.run(["chmod", "-R", "777", LOGS_DIR], stderr=subprocess.DEVNULL, check=False)
        except Exception:
            pass
    log_success("Permissões de I/O concedidas para Talishar (Games, HostFiles, AccountFiles, APIKeys) e logs/.")

def sync_card_database():
    log("Indexando banco de cartas em data/fab_cards_db.json...")
    extractor_script = os.path.join(BASE_DIR, "extract_card_db.py")
    if os.path.exists(extractor_script):
        try:
            subprocess.run([sys.executable, extractor_script], check=True)
            log_success("Banco de dados de cartas sincronizado com sucesso.")
        except Exception as e:
            log_warn(f"Falha ao rodar extract_card_db.py: {e}")

def verify_decks():
    log(f"Verificando decks em {DECKS_DIR} (Fonte única central)...")
    deck_files = [f for f in os.listdir(DECKS_DIR) if f.endswith(".json")]
    log_success(f"{len(deck_files)} decks disponíveis no diretório central: {', '.join(deck_files[:6])}...")

def check_docker():
    log("Verificando containers Docker (Apache / MySQL / Redis)...")
    try:
        res = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"], text=True)
        running = [name.strip() for name in res.strip().splitlines() if name.strip()]
        if any("talishar" in n.lower() and "web" in n.lower() for n in running):
            log_success(f"Containers ativos: {', '.join(running)}")
        else:
            log_warn("Containers Docker do Talishar não detectados. Subindo backend...")
            if os.path.exists(TALISHAR_DIR) and os.path.exists(os.path.join(TALISHAR_DIR, "docker-compose.yml")):
                dc_cmd = get_docker_compose_cmd()
                if dc_cmd:
                    subprocess.run(dc_cmd + ["up", "-d"], cwd=TALISHAR_DIR, check=False)
                    log_success("Comando de inicialização Docker disparado.")
                else:
                    log_warn("Comando docker compose ou docker-compose não encontrado.")
            else:
                log_warn("Talishar/docker-compose.yml não disponível.")
    except Exception as e:
        log_warn(f"Docker não disponível ou aviso de verificação: {e}")

def ensure_frontend_dependencies():
    log("Verificando dependências do Frontend (Talishar-FE)...")
    if not os.path.exists(TALISHAR_FE_DIR) or not os.path.exists(os.path.join(TALISHAR_FE_DIR, "package.json")):
        log_warn("Talishar-FE/package.json não encontrado. Ignorando setup do frontend.")
        return

    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        log_warn("npm/Node.js não encontrado no PATH. Instale Node.js >= 20 para compilar e rodar o frontend.")
        return

    node_modules = os.path.join(TALISHAR_FE_DIR, "node_modules")
    if not os.path.exists(node_modules):
        log("Instalando dependências npm do Frontend (pode levar alguns instantes)...")
        try:
            subprocess.run([npm_cmd, "install"], cwd=TALISHAR_FE_DIR, check=True)
            log_success("Dependências npm do Frontend instaladas com sucesso.")
        except Exception as e:
            log_warn(f"Erro durante npm install no frontend: {e}")

    build_dir = os.path.join(TALISHAR_FE_DIR, "build")
    if not os.path.exists(build_dir):
        log("Validando compilação do Frontend pela primeira vez (npx vite build)...")
        npx_cmd = shutil.which("npx") or "npx"
        try:
            subprocess.run([npx_cmd, "vite", "build"], cwd=TALISHAR_FE_DIR, check=False)
            log_success("Compilação inicial do Frontend concluída.")
        except Exception as e:
            log_warn(f"Aviso durante validação do build do frontend: {e}")
def ensure_git_hooks():
    log("Configurando hooks automáticos do Git (pre-commit e post-commit)...")
    git_dir = os.path.join(BASE_DIR, ".git")
    if not os.path.exists(git_dir):
        log_warn("Diretório .git não encontrado. Ignorando configuração de hooks.")
        return

    hooks_dir = os.path.join(git_dir, "hooks")
    os.makedirs(hooks_dir, exist_ok=True)

    # 1. Pre-commit hook -> scripts/sync_and_clean.sh
    pre_commit_file = os.path.join(hooks_dir, "pre-commit")
    pre_commit_content = """#!/usr/bin/env bash
# Git pre-commit hook gerado por scripts/prepare_environment.py
set -e
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
if [ -f "$ROOT_DIR/scripts/sync_and_clean.sh" ]; then
    bash "$ROOT_DIR/scripts/sync_and_clean.sh"
fi
"""
    with open(pre_commit_file, "w", encoding="utf-8") as f:
        f.write(pre_commit_content)
    try:
        os.chmod(pre_commit_file, 0o755)
    except Exception:
        pass

    # 2. Post-commit hook -> scripts/manage_state.py --auto-release
    post_commit_file = os.path.join(hooks_dir, "post-commit")
    post_commit_content = """#!/usr/bin/env bash
# Git post-commit hook gerado por scripts/prepare_environment.py
ROOT_DIR="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PY_BIN="$ROOT_DIR/venv/bin/python"
if [ ! -f "$PY_BIN" ]; then
    PY_BIN="python3"
fi

if [ -f "$ROOT_DIR/scripts/manage_state.py" ]; then
    "$PY_BIN" "$ROOT_DIR/scripts/manage_state.py" --auto-release
fi
"""
    with open(post_commit_file, "w", encoding="utf-8") as f:
        f.write(post_commit_content)
    try:
        os.chmod(post_commit_file, 0o755)
    except Exception:
        pass

    log_success("Git hooks configurados com sucesso (pre-commit e post-commit).")

def sync_agents_environment_rules():
    """
    Inspeciona dinamicamente o ambiente de execução (WSL2 vs Linux Nativo vs Container)
    e atualiza AGENTS.md garantindo que:
    1. Agentes IA saibam exatamente como executar comandos sem gastar tokens com testes.
    2. Nenhuma informação pessoal (nomes de usuário, paths absolutos privados) seja registrada.
    """
    log("Inspecionando ambiente para configuração de regras de agentes (AGENTS.md)...")
    is_wsl = False
    if os.path.exists("/proc/version"):
        try:
            with open("/proc/version", "r") as f:
                ver = f.read().lower()
                if "microsoft" in ver or "wsl" in ver:
                    is_wsl = True
        except Exception:
            pass

    distro_name = os.environ.get("WSL_DISTRO_NAME", "")
    if not distro_name and is_wsl:
        if os.path.exists("/etc/os-release"):
            try:
                with open("/etc/os-release") as f:
                    for line in f:
                        if line.startswith("ID="):
                            distro_name = line.strip().split("=")[1].strip('"')
            except Exception:
                pass
    if not distro_name:
        distro_name = "Ubuntu-22.04"

    linux_repo_path = BASE_DIR

    # Garante que AGENTS.md e .gemini/ estejam protegidos no .gitignore
    gitignore_path = os.path.join(BASE_DIR, ".gitignore")
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8") as f:
                gi_content = f.read()
            gi_modified = False
            if ".gemini/" not in gi_content:
                gi_content += "\n.gemini/\n"
                gi_modified = True
            if "AGENTS.md" not in gi_content:
                gi_content += "\nAGENTS.md\n!AGENTS.template.md\n"
                gi_modified = True
            if gi_modified:
                with open(gitignore_path, "w", encoding="utf-8") as f:
                    f.write(gi_content)
                log_success("Proteção de privacidade aplicada no .gitignore (.gemini/ e AGENTS.md).")
        except Exception as e:
            log_warn(f"Aviso ao verificar .gitignore: {e}")

    agents_file = os.path.join(BASE_DIR, "AGENTS.md")
    template_file = os.path.join(BASE_DIR, "AGENTS.template.md")

    source_file = template_file if os.path.exists(template_file) else agents_file
    if not os.path.exists(source_file):
        log_warn("AGENTS.template.md e AGENTS.md não encontrados para sincronização de regras.")
        return

    try:
        with open(source_file, "r", encoding="utf-8") as f:
            content = f.read()

        if is_wsl:
            section = f"""### Execução de Comandos (Ambiente Híbrido Windows / WSL2)

O agente executa em **Windows (PowerShell)**, porém todo o ecossistema (Python, PyTorch, Docker, Node) reside no **WSL2 ({distro_name})** no diretório `{linux_repo_path}`.

**NUNCA execute:**
- `git`, `python` ou `pytest` diretamente no PowerShell do Windows (as ferramentas e dependências não existem no host Windows).
- `./venv/bin/python` diretamente no PowerShell (é um binário ELF Linux e falhará no Windows).
- `wsl` sem `--cd {linux_repo_path}` (gera erro de tradução da unidade de rede).

**SEMPRE execute via WSL com `--cd {linux_repo_path}`:**
- **Git:** `wsl -d {distro_name} --cd {linux_repo_path} git <args>`
- **Python / Scripts:** `wsl -d {distro_name} --cd {linux_repo_path} ./venv/bin/python <script>`
- **Testes (Pytest):** `wsl -d {distro_name} --cd {linux_repo_path} ./venv/bin/python -m pytest <args>`
- **Docker:** `wsl -d {distro_name} --cd {linux_repo_path} docker <args>`
- **Frontend (Node/NPM):** `wsl -d {distro_name} --cd {linux_repo_path} npm <args>`
- **Comandos Linux/Bash:** `wsl -d {distro_name} --cd {linux_repo_path} <comando>`"""
        else:
            section = f"""### Execução de Comandos (Ambiente Linux Nativo)

O agente executa nativamente no Linux/Container no diretório `{linux_repo_path}`.

**SEMPRE execute no diretório do projeto:**
- **Git:** `git <args>`
- **Python / Scripts:** `./venv/bin/python <script>`
- **Testes (Pytest):** `./venv/bin/python -m pytest <args>`
- **Docker:** `docker <args>`
- **Frontend (Node/NPM):** `npm <args>`
- **Comandos Linux/Bash:** `<comando>`"""

        header = "### Execução de Comandos"
        if header in content:
            start_idx = content.find(header)
            next_header = content.find("\n### ", start_idx + len(header))
            if next_header == -1:
                next_header = content.find("\n## ", start_idx + len(header))
            if next_header != -1:
                new_content = content[:start_idx] + section + "\n\n" + content[next_header:].lstrip("\n")
            else:
                new_content = content[:start_idx] + section + "\n"
        else:
            if "### Architecture" in content:
                new_content = content.replace("### Architecture", f"{section}\n\n### Architecture")
            else:
                new_content = content.rstrip() + f"\n\n{section}\n"

        # Atualiza a regra 4 de sincronização de templates com o comando correto
        if is_wsl:
            export_cmd = f'wsl -d {distro_name} --cd {linux_repo_path} ./venv/bin/python scripts/prepare_environment.py --export-templates'
        else:
            export_cmd = './venv/bin/python scripts/prepare_environment.py --export-templates'

        import re
        new_content = re.sub(
            r'execute `[^`]*prepare_environment\.py --export-templates`',
            f'execute `{export_cmd}`',
            new_content
        )
        new_content = re.sub(
            r'execute \./venv/bin/python scripts/prepare_environment\.py --export-templates',
            f'execute `{export_cmd}`',
            new_content
        )
        new_content = re.sub(
            r'execute o script de exportação configurado no seu ambiente',
            f'execute `{export_cmd}`',
            new_content
        )

        with open(agents_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        log_success(f"AGENTS.md sincronizado com base no template para o ambiente ({linux_repo_path}).")
    except Exception as e:
        log_warn(f"Falha ao sincronizar AGENTS.md: {e}")

def main():
    parser = argparse.ArgumentParser(description="Automação de Preparação de Ambiente do FaB Talishar AI")
    parser.add_argument("--export-templates", action="store_true", help="Salva os arquivos modificados em setup_templates/")
    parser.add_argument("--frontend-only", action="store_true", help="Prepara apenas o repositório Talishar-FE e sincroniza templates")
    args = parser.parse_args()

    print("==================================================")
    print("   FAB TALISHAR AI - PREPARAÇÃO DE AMBIENTE       ")
    print("==================================================")

    if args.export_templates:
        export_active_to_templates()
        return

    if args.frontend_only:
        ensure_talishar_frontend()
        apply_frontend_templates()
        ensure_frontend_dependencies()
        log_success("Frontend Talishar-FE preparado e sincronizado com sucesso!")
        return

    # 1. Estrutura base de diretórios
    ensure_directories()

    # 2. Garantir repositórios do Talishar clonados/disponíveis
    ensure_talishar_repositories()

    # 3. Aplicar patches e templates customizados sobre os repositórios
    apply_custom_templates()

    # 4. Camada de idempotência do sistema e configs obrigatórios (executado APÓS repositórios e templates)
    ensure_system_idempotence()

    # 5. Permissões de escrita
    fix_permissions()

    # 6. Dependências do Frontend (npm install / validação de build)
    ensure_frontend_dependencies()

    # 7. Containers Docker (Apache, MySQL, Redis)
    check_docker()

    # 8. Extração e indexação do banco oficial de cartas
    sync_card_database()

    # 9. Verificação dos decks no diretório central
    verify_decks()

    # 10. Configurar Git Hooks automáticos (pre-commit e post-commit)
    ensure_git_hooks()

    # 11. Regras de agente dinâmicas para o runtime
    sync_agents_environment_rules()
    print("==================================================")
    log_success("Ambiente preparado com sucesso!")
    print("Para rodar o projeto:")
    print("  1. Iniciar tudo (Docker + Dashboard): ./start.sh")
    print("  2. Iniciar Frontend Web:              ./start_frontend.sh")
    print("  3. Parar serviços:                    ./stop.sh")
    print("==================================================")

if __name__ == "__main__":
    main()
