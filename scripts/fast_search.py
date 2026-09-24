#!/usr/bin/env python3
"""
scripts/fast_search.py
======================
Utilitário de busca rápida de texto que automaticamente ignora pastas gigantescas
(node_modules, venv, Talishar/Games, build, logs, data, .git, etc.) para evitar travamentos.

Uso:
  python scripts/fast_search.py "termo" [caminho] [--ext=.py,.tsx]
"""

import sys
import os
import re

EXCLUDE_DIRS = {
    "node_modules", "venv", ".venv", "env", ".git", "Talishar", "Talishar-FE",
    "logs", "data", "build", "dist", "__pycache__", ".pytest_cache", ".cache"
}

def fast_search(pattern: str, root: str = ".", extensions: list = None, max_results: int = 100):
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as e:
        print(f"[ERRO] Regex inválida: {e}")
        sys.exit(1)

    matches_found = 0
    print(f"[*] Buscando por '{pattern}' em '{root}' (excluindo diretórios pesados)...")

    for dirpath, dirnames, filenames in os.walk(root):
        # Poda em tempo real das pastas ignoradas
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith(".")]

        for fname in filenames:
            if extensions and not any(fname.endswith(ext) for ext in extensions):
                continue

            fpath = os.path.join(dirpath, fname)
            relpath = os.path.relpath(fpath, root)

            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as fp:
                    for line_no, line in enumerate(fp, 1):
                        if regex.search(line):
                            snippet = line.strip()
                            if len(snippet) > 120:
                                snippet = snippet[:117] + "..."
                            print(f"{relpath}:{line_no}: {snippet}")
                            matches_found += 1
                            if matches_found >= max_results:
                                print(f"\n[!] Limite de {max_results} resultados atingido. Refine a busca ou aponte para um subdiretório.")
                                return
            except Exception:
                continue

    if matches_found == 0:
        print(f"[-] Nenhuma ocorrência encontrada para '{pattern}'.")
    else:
        print(f"[OK] Total de {matches_found} ocorrência(s) encontrada(s).")

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
