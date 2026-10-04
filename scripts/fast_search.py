#!/usr/bin/env python3
"""
scripts/fast_search.py
======================
Utilitário de busca ultrarrápida usando git grep (nativo) e fallback para grep.
Ignora pastas gigantescas automaticamente.
"""

import sys
import os
import subprocess

EXCLUDE_DIRS = {
    "node_modules", "venv", ".venv", "env", ".git", "Talishar", "Talishar-FE",
    "logs", "data", "build", "dist", "__pycache__", ".pytest_cache", ".cache",
    "Games", "mysql-data", "AccountFiles", "HostFiles", "cache", ".turbo"
}

def fast_search(pattern: str, root: str = ".", extensions: list = None):
    print(f"[*] Buscando por '{pattern}' em '{root}' (ultrarrápido)...")
    
    # 1. Tentar git grep primeiro (instantâneo para arquivos versionados)
    try:
        cmd_git = ["git", "grep", "-n", "-I", "-i", "-e", pattern, "--", root]
        if extensions:
            pathspecs = [f"*{ext}" for ext in extensions]
            cmd_git.extend(pathspecs)
            
        result = subprocess.run(cmd_git, capture_output=True, text=True, cwd=root if root != "." else None)
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            count = 0
            for line in lines:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    snippet = parts[2].strip()
                    if len(snippet) > 120:
                        snippet = snippet[:117] + "..."
                    print(f"{parts[0]}:{parts[1]}: {snippet}")
                    count += 1
                if count >= 100:
                    break
            if len(lines) > 100:
                print(f"\n[!] Limite de 100 resultados atingido (total {len(lines)}). Refine a busca.")
            return
    except Exception:
        pass

    # 2. Fallback para o grep GNU nativo se git grep falhar (ex: arquivos não trackeados)
    try:
        excludes = [f"--exclude-dir={d}" for d in EXCLUDE_DIRS]
        cmd_grep = ["grep", "-rnI", "-i"] + excludes + [pattern, root]
        
        result = subprocess.run(cmd_grep, capture_output=True, text=True)
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")
            count = 0
            for line in lines:
                parts = line.split(":", 2)
                if len(parts) >= 3:
                    if extensions:
                        if not any(parts[0].endswith(e) for e in extensions):
                            continue
                    snippet = parts[2].strip()
                    if len(snippet) > 120:
                        snippet = snippet[:117] + "..."
                    print(f"{parts[0]}:{parts[1]}: {snippet}")
                    count += 1
                if count >= 100:
                    break
            if len(lines) > 100:
                print(f"\n[!] Limite de 100 resultados atingido. Refine a busca.")
            return
    except Exception:
        pass

    print(f"[-] Nenhuma ocorrência encontrada para '{pattern}'.")

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Uso: python scripts/fast_search.py <termo> [caminho] [--ext=.py,.tsx]")
        sys.exit(0)

    pat = sys.argv[1]
    target_path = "."
    exts = None

    for arg in sys.argv[2:]:
        if arg.startswith("--ext="):
            exts = [e.strip() for e in arg.split("=", 1)[1].split(",")]
        elif not arg.startswith("-"):
            target_path = arg

    fast_search(pat, target_path, exts)
