#!/usr/bin/env python3
"""
healthcheck_talishar.py
=======================
Diagnóstico e validação de saúde do ecossistema FaB Talishar AI.

Verifica:
  1. Portas de rede ativas:
     - 8080: Talishar Apache / PHP Backend
     - 3000: Talishar-FE Vite Frontend
     - 8501: Streamlit AI Dashboard
  2. Status do Container Runtime (Docker / Podman) e containers ativos;
  3. Permissões de escrita e estrutura de diretórios (`Talishar/Games`, `logs/`, `decks/`);
  4. Integridade do banco de dados oficial de cartas `data/fab_cards_db.json`;
  5. Arquivos críticos e templates de inicialização (`Redirector.php`, `APIKeys.php`, `GameIDCounter.txt`).

Suporta `--fix` para remediação automática de permissões, geração de banco e templates.
"""

import os
import sys
import json
import socket
import shutil
import urllib.request
import urllib.error
import subprocess
import argparse
from typing import Dict, Any, List, Tuple, Optional

# ── Resolução de Caminho Raiz do Repositório ──────────────────────────────
def _find_repo_root() -> str:
    curr = os.path.abspath(os.path.dirname(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, "bot_client.py")) or os.path.exists(os.path.join(curr, ".git")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.."))

ROOT_DIR = _find_repo_root()
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

# Cores ANSI
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[0;32m"
COLOR_YELLOW = "\033[1;33m"
COLOR_RED = "\033[0;31m"
COLOR_CYAN = "\033[0;36m"
COLOR_BOLD = "\033[1m"


def check_port(host: str, port: int, timeout: float = 0.5) -> Tuple[bool, Optional[float]]:
    """Testa se uma porta TCP está ouvindo conexões."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = socket.getdefaulttimeout()
    try:
        start_time = socket.getdefaulttimeout()
        res = s.connect_ex((host, port))
        if res == 0:
            return True, None
        return False, None
    except Exception:
        return False, None
    finally:
        s.close()


def probe_http_service(url: str, timeout: float = 1.0) -> Tuple[bool, Optional[int], Optional[str]]:
    """Tenta uma requisição HTTP básica e retorna status code."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "FaB-Talishar-Healthcheck"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return True, response.status, "OK"
    except urllib.error.HTTPError as e:
        return True, e.code, str(e.reason)
    except Exception as e:
        return False, None, str(e)


def check_writable(path: str) -> bool:
    """Verifica se um caminho existe e possui permissão de escrita real."""
    if not os.path.exists(path):
        return False
    try:
        test_file = os.path.join(path, ".healthcheck_write_test")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return True
    except Exception:
        return False


def get_container_runtime() -> Tuple[Optional[str], Optional[str], List[str]]:
    """Detecta o container runtime disponível (Docker ou Podman) e lista containers ativos."""
    runtime = None
    version_str = None
    containers: List[str] = []

    # 1. Tentar Docker
    if shutil.which("docker"):
        try:
            r = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                runtime = "Docker"
                version_str = r.stdout.strip()
                # Lista containers ativos
                cr = subprocess.run(["docker", "ps", "--format", "{{.Names}} ({{.Status}})"], capture_output=True, text=True, timeout=3)
                if cr.returncode == 0:
                    containers = [line.strip() for line in cr.stdout.splitlines() if line.strip()]
        except Exception:
            pass

    # 2. Se Docker não responder ou não estiver disponível, tentar Podman
    if not runtime and shutil.which("podman"):
        try:
            r = subprocess.run(["podman", "--version"], capture_output=True, text=True, timeout=2)
            if r.returncode == 0:
                runtime = "Podman"
                version_str = r.stdout.strip()
                cr = subprocess.run(["podman", "ps", "--format", "{{.Names}} ({{.Status}})"], capture_output=True, text=True, timeout=3)
                if cr.returncode == 0:
                    containers = [line.strip() for line in cr.stdout.splitlines() if line.strip()]
        except Exception:
            pass

    return runtime, version_str, containers


def run_healthcheck(auto_fix: bool = False, host: str = "127.0.0.1", timeout: float = 0.5) -> Dict[str, Any]:
    """Executa todas as verificações de saúde do ecossistema FaB Talishar AI."""
    report: Dict[str, Any] = {
        "ports": {},
        "containers": {},
        "filesystem": {},
        "database": {},
        "critical_files": {},
        "fixed_items": [],
        "summary": {"ok": True, "warnings": 0, "errors": 0}
    }

    # ══════════════════════════════════════════════════════════════
    # 1. Portas de Rede e Serviços
    # ══════════════════════════════════════════════════════════════
    ports_to_check = [
        {"port": 8080, "name": "Talishar Apache/PHP Backend", "url": f"http://{host}:8080/", "critical": False},
        {"port": 3000, "name": "Talishar-FE Vite Frontend", "url": f"http://{host}:3000/", "critical": False},
        {"port": 8501, "name": "Streamlit AI Dashboard", "url": f"http://{host}:8501/", "critical": False},
        {"port": 3306, "name": "Talishar MySQL Database", "url": None, "critical": False},
    ]

    for p in ports_to_check:
        port_num = p["port"]
        is_open, _ = check_port(host, port_num, timeout=timeout)
        http_ok, code, reason = (False, None, None)
        if is_open and p["url"]:
            http_ok, code, reason = probe_http_service(p["url"], timeout=timeout)

        report["ports"][str(port_num)] = {
            "name": p["name"],
            "open": is_open,
            "http_responsive": http_ok,
            "http_status": code,
        }

        if not is_open:
            report["summary"]["warnings"] += 1

    # ══════════════════════════════════════════════════════════════
    # 2. Container Runtime e Serviços Docker / Podman
    # ══════════════════════════════════════════════════════════════
    runtime, version_str, running_containers = get_container_runtime()
    talishar_containers = [c for c in running_containers if "talishar" in c.lower()]

    report["containers"] = {
        "runtime": runtime or "Não instalado",
        "version": version_str,
        "active_containers": running_containers,
        "talishar_containers_active": talishar_containers,
    }

    if not runtime:
        report["summary"]["warnings"] += 1
    elif len(talishar_containers) == 0:
        report["summary"]["warnings"] += 1
        if auto_fix:
            # Tenta subir docker compose em Talishar/
            talishar_dir = os.path.join(ROOT_DIR, "Talishar")
            compose_file = os.path.join(talishar_dir, "docker-compose.yml")
            if os.path.exists(compose_file):
                cmd = None
                if runtime == "Docker":
                    cmd = ["docker", "compose", "up", "-d"]
                elif runtime == "Podman":
                    cmd = ["podman", "compose", "up", "-d"] if shutil.which("podman-compose") else None
                if cmd:
                    try:
                        res = subprocess.run(cmd, cwd=talishar_dir, capture_output=True, timeout=10)
                        if res.returncode == 0:
                            report["fixed_items"].append("Inicialização de containers Talishar disparada com sucesso.")
                    except Exception:
                        pass

    # ══════════════════════════════════════════════════════════════
    # 3. Permissões de Pastas Críticas
    # ══════════════════════════════════════════════════════════════
    paths_to_check = [
        {"path": os.path.join(ROOT_DIR, "Talishar", "Games"), "name": "Talishar/Games", "critical": True},
        {"path": os.path.join(ROOT_DIR, "Talishar", "HostFiles"), "name": "Talishar/HostFiles", "critical": True},
        {"path": os.path.join(ROOT_DIR, "Talishar", "AccountFiles"), "name": "Talishar/AccountFiles", "critical": False},
        {"path": os.path.join(ROOT_DIR, "Talishar", "APIKeys"), "name": "Talishar/APIKeys", "critical": False},
        {"path": os.path.join(ROOT_DIR, "logs"), "name": "logs/", "critical": True},
        {"path": os.path.join(ROOT_DIR, "decks"), "name": "decks/", "critical": True},
        {"path": os.path.join(ROOT_DIR, "data"), "name": "data/", "critical": True},
    ]

    for item in paths_to_check:
        p = item["path"]
        exists = os.path.exists(p)
        writable = check_writable(p) if exists else False

        if not exists and auto_fix:
            try:
                os.makedirs(p, exist_ok=True)
                os.chmod(p, 0o775)
                exists = True
                writable = check_writable(p)
                report["fixed_items"].append(f"Criado diretório '{item['name']}' com permissão 775.")
            except Exception:
                pass
        elif exists and not writable and auto_fix:
            try:
                os.chmod(p, 0o775)
                writable = check_writable(p)
                if writable:
                    report["fixed_items"].append(f"Ajustada permissão de escrita em '{item['name']}'.")
            except Exception:
                pass

        report["filesystem"][item["name"]] = {
            "exists": exists,
            "writable": writable,
            "critical": item["critical"]
        }

        if not exists or not writable:
            if item["critical"]:
                report["summary"]["errors"] += 1
            else:
                report["summary"]["warnings"] += 1

    # ══════════════════════════════════════════════════════════════
    # 4. Banco Oficial de Cartas (data/fab_cards_db.json)
    # ══════════════════════════════════════════════════════════════
    card_db_path = os.path.join(ROOT_DIR, "data", "fab_cards_db.json")
    card_db_exists = os.path.exists(card_db_path)
    card_count = 0
    valid_json = False

    if card_db_exists:
        try:
            with open(card_db_path, "r", encoding="utf-8") as f:
                card_data = json.load(f)
            if isinstance(card_data, dict):
                card_count = len(card_data)
                valid_json = True
        except Exception:
            valid_json = False

    if (not card_db_exists or not valid_json or card_count < 1000) and auto_fix:
        extractor = os.path.join(ROOT_DIR, "extract_card_db.py")
        if os.path.exists(extractor):
            try:
                subprocess.run([sys.executable, extractor], check=True, capture_output=True, timeout=30)
                if os.path.exists(card_db_path):
                    with open(card_db_path, "r", encoding="utf-8") as f:
                        card_data = json.load(f)
                    card_count = len(card_data)
                    card_db_exists = True
                    valid_json = True
                    report["fixed_items"].append(f"Banco de cartas reconstruído com sucesso ({card_count} cartas).")
            except Exception as e:
                report["fixed_items"].append(f"Falha ao reconstruir banco de cartas: {e}")

    report["database"]["fab_cards_db"] = {
        "path": card_db_path,
        "exists": card_db_exists,
        "valid_json": valid_json,
        "card_count": card_count,
    }

    if not card_db_exists or not valid_json or card_count < 1000:
        report["summary"]["errors"] += 1

    # ══════════════════════════════════════════════════════════════
    # 5. Arquivos Críticos de Inicialização e Templates
    # ══════════════════════════════════════════════════════════════
    critical_files = [
        {
            "dst": os.path.join(ROOT_DIR, "Talishar", "HostFiles", "Redirector.php"),
            "tpl": os.path.join(ROOT_DIR, "Talishar", "HostFiles", "RedirectorTemplate.php"),
            "name": "Redirector.php"
        },
        {
            "dst": os.path.join(ROOT_DIR, "Talishar", "APIKeys", "APIKeys.php"),
            "tpl": os.path.join(ROOT_DIR, "Talishar", "APIKeys", "APIKeys.php.template"),
            "name": "APIKeys.php"
        },
        {
            "dst": os.path.join(ROOT_DIR, "Talishar", "HostFiles", "GameIDCounter.txt"),
            "content": "1\n",
            "name": "GameIDCounter.txt"
        },
        {
            "dst": os.path.join(ROOT_DIR, "Talishar-FE", ".env"),
            "tpl": os.path.join(ROOT_DIR, "Talishar-FE", ".env.template"),
            "name": "Talishar-FE/.env"
        }
    ]

    for cf in critical_files:
        exists = os.path.exists(cf["dst"])
        if not exists and auto_fix:
            try:
                os.makedirs(os.path.dirname(cf["dst"]), exist_ok=True)
                if "tpl" in cf and os.path.exists(cf["tpl"]):
                    shutil.copy2(cf["tpl"], cf["dst"])
                    exists = True
                    report["fixed_items"].append(f"Gerado {cf['name']} a partir do template.")
                elif "content" in cf:
                    with open(cf["dst"], "w") as f:
                        f.write(cf["content"])
                    exists = True
                    report["fixed_items"].append(f"Criado arquivo inicial {cf['name']}.")
            except Exception:
                pass

        report["critical_files"][cf["name"]] = exists
        if not exists:
            report["summary"]["warnings"] += 1

    report["summary"]["ok"] = (report["summary"]["errors"] == 0)
    return report


def print_report(report: Dict[str, Any], verbose: bool = False) -> None:
    """Exibe o relatório formatado de saúde do sistema no terminal."""
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════════════════════════════{COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}   FaB Talishar AI — Diagnóstico e Healthcheck do Ecossistema                                           {COLOR_RESET}")
    print(f"{COLOR_BOLD}{COLOR_CYAN}══════════════════════════════════════════════════════════════════════════════════════════════════════{COLOR_RESET}\n")

    # 1. Portas
    print(f"{COLOR_BOLD}[1] Portas de Rede e Conectividade de Serviços:{COLOR_RESET}")
    for port_str, info in report["ports"].items():
        if info["open"]:
            status = f"{COLOR_GREEN}✓ ATIVA (Porta {port_str}){COLOR_RESET}"
            if info.get("http_responsive"):
                status += f" — HTTP {info['http_status']}"
        else:
            status = f"{COLOR_YELLOW}○ INATIVA (Porta {port_str} offline){COLOR_RESET}"
        print(f"    - {info['name']:<35}: {status}")

    # 2. Container Runtime
    print(f"\n{COLOR_BOLD}[2] Runtime de Containers e Serviços Talishar:{COLOR_RESET}")
    cinfo = report["containers"]
    runtime_str = cinfo["runtime"]
    if runtime_str in ("Docker", "Podman"):
        rt_badge = f"{COLOR_GREEN}✓ {runtime_str}{COLOR_RESET}"
        if cinfo.get("version"):
            rt_badge += f" ({cinfo['version'].splitlines()[0]})"
    else:
        rt_badge = f"{COLOR_YELLOW}○ Não detectado no PATH{COLOR_RESET}"
    print(f"    - Container Runtime: {rt_badge}")

    talishar_cnts = cinfo.get("talishar_containers_active", [])
    if talishar_cnts:
        print(f"    - Containers ativos : {COLOR_GREEN}{', '.join(talishar_cnts)}{COLOR_RESET}")
    else:
        print(f"    - Containers ativos : {COLOR_YELLOW}Nenhum container do Talishar em execução no momento.{COLOR_RESET}")

    # 3. Permissões de Diretórios
    print(f"\n{COLOR_BOLD}[3] Estrutura e Permissões de Pastas:{COLOR_RESET}")
    for name, finfo in report["filesystem"].items():
        if finfo["exists"] and finfo["writable"]:
            st = f"{COLOR_GREEN}✓ OK (Leitura e Escrita){COLOR_RESET}"
        elif finfo["exists"] and not finfo["writable"]:
            st = f"{COLOR_RED}✗ SEM PERMISSÃO DE ESCRITA{COLOR_RESET}"
        else:
            st = f"{COLOR_RED}✗ NÃO ENCONTRADO{COLOR_RESET}"
        print(f"    - {name:<25}: {st}")

    # 4. Banco de Cartas
    print(f"\n{COLOR_BOLD}[4] Banco Oficial de Cartas (fab_cards_db.json):{COLOR_RESET}")
    db_info = report["database"]["fab_cards_db"]
    if db_info["exists"] and db_info["valid_json"] and db_info["card_count"] > 1000:
        db_st = f"{COLOR_GREEN}✓ Integridade verificada ({db_info['card_count']} cartas catalogadas){COLOR_RESET}"
    else:
        db_st = f"{COLOR_RED}✗ Ausente ou corrompido! Execute com --fix ou execute extract_card_db.py{COLOR_RESET}"
    print(f"    - data/fab_cards_db.json  : {db_st}")

    # 5. Arquivos Críticos de Configuração
    print(f"\n{COLOR_BOLD}[5] Templates e Arquivos Críticos de Configuração:{COLOR_RESET}")
    for fname, ok in report["critical_files"].items():
        c_st = f"{COLOR_GREEN}✓ Presente{COLOR_RESET}" if ok else f"{COLOR_YELLOW}○ Ausente (use --fix){COLOR_RESET}"
        print(f"    - {fname:<25}: {c_st}")

    # Correções aplicadas
    if report.get("fixed_items"):
        print(f"\n{COLOR_BOLD}{COLOR_YELLOW}[Ações de Remediação Automática (--fix):]{COLOR_RESET}")
        for fix in report["fixed_items"]:
            print(f"    ↳ {COLOR_YELLOW}[FIX]{COLOR_RESET} {fix}")

    # Resumo Geral
    errs = report["summary"]["errors"]
    warns = report["summary"]["warnings"]
    print(f"\n--------------------------------------------------------------------------------------------------")
    if errs == 0:
        print(f"{COLOR_BOLD}Resultado Geral:{COLOR_RESET} {COLOR_GREEN}✓ SISTEMA SAUDÁVEL{COLOR_RESET} (Erros críticos: 0 | Avisos de serviços offline: {warns})")
        print(f"Observação: Portas inativas são normais quando o servidor Talishar/Vite/Streamlit ainda não foi disparado.")
    else:
        print(f"{COLOR_BOLD}Resultado Geral:{COLOR_RESET} {COLOR_RED}✗ INCONSISTÊNCIAS CRÍTICAS DETECTADAS ({errs} erro(s)){COLOR_RESET}")
        print(f"Dica: Execute {COLOR_YELLOW}./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py --fix{COLOR_RESET} para remediação.")
    print("--------------------------------------------------------------------------------------------------\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnóstico de Saúde do Ecossistema FaB Talishar AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  ./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py
  ./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py --fix
  ./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py --json
        """
    )
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Executa autocorreção automática de permissões de disco, arquivos de configuração e banco de cartas."
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host para verificação de portas (padrão: 127.0.0.1)."
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=0.5,
        help="Timeout em segundos para testes de conexão de rede (padrão: 0.5s)."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Retorna relatório em JSON estruturado para automação."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Modo detalhado com telemetria completa."
    )

    args = parser.parse_args()

    report = run_healthcheck(auto_fix=args.fix, host=args.host, timeout=args.timeout)

    if args.output_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print_report(report, verbose=args.verbose)

    if report["summary"]["errors"] > 0:
        return 2
    if report["summary"]["warnings"] > 0:
        return 0  # Avisos de servidores offline não são erros fatais de build/smoke
    return 0


if __name__ == "__main__":
    sys.exit(main())
