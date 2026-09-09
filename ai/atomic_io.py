"""
ai/atomic_io.py
===============
Utilitários de I/O atômico para evitar corrupção de dados
em ambientes com múltiplos processos concorrentes.

Padrão: escreve em arquivo temporário (.tmp) e renomeia atomicamente.
"""

import json
import os
import tempfile


def atomic_json_save(data: dict | list, filepath: str, indent: int = 2) -> None:
    """Salva dados JSON de forma atômica usando write-to-tmp + rename."""
    dir_name = os.path.dirname(filepath) or "."
    os.makedirs(dir_name, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=dir_name, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        os.replace(tmp_path, filepath)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
