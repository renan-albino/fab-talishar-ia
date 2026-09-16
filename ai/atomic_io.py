"""
ai/atomic_io.py
===============
Utilitários de I/O atômico para evitar corrupção de dados
em ambientes com múltiplos processos concorrentes.

Padrão: escreve em arquivo temporário (.tmp) e renomeia atomicamente.
"""

import fcntl
import json
import os
import tempfile
import time
from contextlib import contextmanager


@contextmanager
def file_lock(filepath: str, timeout: float = 10.0):
    """Context manager para exclusão mútua entre processos via fcntl.flock."""
    lock_file = f"{filepath}.lock"
    os.makedirs(os.path.dirname(lock_file) or ".", exist_ok=True)
    with open(lock_file, "a") as f:
        if timeout is None or timeout <= 0:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        else:
            start_time = time.time()
            while True:
                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except (BlockingIOError, OSError):
                    if (time.time() - start_time) >= timeout:
                        raise TimeoutError(f"Timeout de {timeout}s aguardando lock em {lock_file}")
                    time.sleep(0.01)
        try:
            yield
        finally:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass



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
