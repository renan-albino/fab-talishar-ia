"""
ai/training/process_supervisor.py
================================
Funções e utilitários para supervisão, monitoramento e encerramento de processos
de bots em treinamento paralelo.
"""

import subprocess
import threading
import time
from typing import List, Any, Optional, Callable


def kill_orphan_bots(pattern: str = "bot_client.py") -> None:
    """Varre e finaliza quaisquer processos órfãos de bots."""
    try:
        subprocess.run(
            ["pkill", "-9", "-f", pattern],
            timeout=2,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def kill_active_processes(active_procs: List[Any], proc_lock: Optional[threading.Lock] = None) -> None:
    """
    Encerra imediatamente todos os subprocessos ativos da lista fornecida.
    Suporta listas de tuplas (p1, p2) ou objetos Popen individuais.
    """
    if proc_lock is not None:
        with proc_lock:
            _terminate_procs_list(active_procs)
    else:
        _terminate_procs_list(active_procs)


def _terminate_procs_list(active_procs: List[Any]) -> None:
    for item in active_procs:
        if isinstance(item, (list, tuple)):
            for p in item:
                try:
                    if p is not None and hasattr(p, "poll") and p.poll() is None:
                        p.kill()
                except Exception:
                    pass
        elif hasattr(item, "poll"):
            try:
                if item.poll() is None:
                    item.kill()
            except Exception:
                pass
    active_procs.clear()


def is_process_alive(proc: Any) -> bool:
    """Verifica se um processo individual ainda está em execução."""
    if proc is None or not hasattr(proc, "poll"):
        return False
    try:
        return proc.poll() is None
    except Exception:
        return False


def get_active_pids(active_procs: List[Any], proc_lock: Optional[threading.Lock] = None) -> List[int]:
    """Retorna lista de PIDs de processos que continuam em execução."""
    if proc_lock is not None:
        with proc_lock:
            snapshot = list(active_procs)
    else:
        snapshot = list(active_procs)

    pids: List[int] = []
    for item in snapshot:
        if isinstance(item, (list, tuple)):
            for p in item:
                if p is not None and hasattr(p, "poll") and p.poll() is None:
                    if hasattr(p, "pid"):
                        pids.append(p.pid)
        elif hasattr(item, "poll") and item.poll() is None:
            if hasattr(item, "pid"):
                pids.append(item.pid)
    return pids


def wait_for_processes(
    active_procs: List[Any],
    timeout: float,
    is_running_check: Optional[Callable[[], bool]] = None,
    check_interval: float = 0.3,
    proc_lock: Optional[threading.Lock] = None,
) -> bool:
    """
    Aguarda o término de todos os processos monitorados ou até atingir timeout.
    Retorna True se todos terminaram normalmente, False se atingiu timeout ou cancelado.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_running_check is not None and not is_running_check():
            return False

        if proc_lock is not None:
            with proc_lock:
                procs_snapshot = list(active_procs)
        else:
            procs_snapshot = list(active_procs)

        if not procs_snapshot:
            return True

        all_done = True
        for item in procs_snapshot:
            if isinstance(item, (list, tuple)):
                if not all(p.poll() is not None for p in item if p is not None):
                    all_done = False
                    break
            elif hasattr(item, "poll"):
                if item.poll() is None:
                    all_done = False
                    break

        if all_done:
            return True

        time.sleep(check_interval)

    return False
