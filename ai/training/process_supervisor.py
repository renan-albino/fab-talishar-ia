"""
ai/training/process_supervisor.py
================================
Funções e utilitários para supervisão, monitoramento e encerramento de processos
de bots em treinamento paralelo.
"""

import os
import subprocess
import threading
import time
import json
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


def terminate_process_cleanly(proc: Any, timeout: float = 2.0) -> None:
    """
    Implementa o ciclo correto de finalização de subprocessos para erradicar zumbis Unix <defunct>:
    1. Envia proc.terminate().
    2. Aguarda até `timeout` segundos via proc.wait(timeout=...).
    3. Se não terminar (TimeoutExpired) ou continuar vivo, envia proc.kill() e
       obrigatoriamente chama proc.wait() para limpar o processo da tabela do kernel.
    """
    if proc is None or not hasattr(proc, "poll"):
        return
    try:
        if proc.poll() is None:
            if hasattr(proc, "terminate"):
                proc.terminate()
                import sys, os, signal
                if sys.platform != "win32":
                    try:
                        pid = getattr(proc, "pid", None)
                        if isinstance(pid, int) and not isinstance(pid, bool) and pid > 1:
                            pgid = os.getpgid(pid)
                            # Só mata o grupo se o filho está em grupo diferente do processo atual
                            # e nunca sinaliza o grupo 1 (init / container host)
                            if pgid > 1 and pgid != os.getpgid(0):
                                os.killpg(pgid, signal.SIGTERM)
                    except (ProcessLookupError, PermissionError, OSError, AttributeError):
                        pass
            is_alive = True
            try:
                if hasattr(proc, "wait"):
                    proc.wait(timeout=timeout)
                is_alive = (proc.poll() is None)
            except (subprocess.TimeoutExpired, Exception):
                is_alive = True
            
            if is_alive:
                if hasattr(proc, "kill"):
                    proc.kill()
                try:
                    if hasattr(proc, "wait"):
                        proc.wait(timeout=2.0)
                except Exception:
                    pass
        else:
            try:
                if hasattr(proc, "wait"):
                    proc.wait(timeout=0.1)
            except Exception:
                pass
    except Exception:
        pass


def _terminate_procs_list(active_procs: List[Any]) -> None:
    for item in active_procs:
        if isinstance(item, (list, tuple)):
            for p in item:
                terminate_process_cleanly(p, timeout=2.0)
        else:
            terminate_process_cleanly(item, timeout=2.0)
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
                    pid = getattr(p, "pid", None)
                    if isinstance(pid, int) and not isinstance(pid, bool):
                        pids.append(pid)
        elif hasattr(item, "poll") and item.poll() is None:
            pid = getattr(item, "pid", None)
            if isinstance(pid, int) and not isinstance(pid, bool):
                pids.append(pid)
    return pids


def get_room_telemetry(room_id: str, base_dir: str = ".") -> dict:
    """
    Lê a telemetria atual da sala (Game ID do Talishar, turno, HPs dos jogadores e status).
    Retorna dicionário com:
        room_id: str
        game_id: Optional[str]
        turn: Optional[int]
        p1_hp: Optional[int]
        p2_hp: Optional[int]
        status: str
        phase: str
    """
    game_id = None
    gid_path = os.path.join(base_dir, "logs", f"{room_id}_game_id.txt")
    if os.path.exists(gid_path):
        try:
            with open(gid_path, "r", encoding="utf-8") as f:
                val = f.read().strip()
                if val:
                    game_id = val
        except Exception:
            pass

    turn = None
    p1_hp = None
    p2_hp = None
    status = "Iniciando"
    phase = ""

    # Tenta ler do metrics do Bot1
    b1_path = os.path.join(base_dir, "logs", f"{room_id}_Bot1.json")
    if os.path.exists(b1_path):
        try:
            with open(b1_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                m = data.get("metrics", {})
                turn = m.get("turn")
                p1_hp = m.get("health")
                p2_hp = m.get("opp_health")
                status = m.get("status", "Jogando")
                phase = m.get("phase", "")
        except Exception:
            pass

    # Se não achou no Bot1, tenta Bot2
    if turn is None:
        b2_path = os.path.join(base_dir, "logs", f"{room_id}_Bot2.json")
        if os.path.exists(b2_path):
            try:
                with open(b2_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    m = data.get("metrics", {})
                    turn = m.get("turn")
                    p2_hp = m.get("health")
                    p1_hp = m.get("opp_health")
                    status = m.get("status", "Jogando")
                    phase = m.get("phase", "")
            except Exception:
                pass

    return {
        "room_id": room_id,
        "game_id": game_id,
        "turn": turn,
        "p1_hp": p1_hp,
        "p2_hp": p2_hp,
        "status": status,
        "phase": phase,
    }


def get_room_summary_info(room_id: str, base_dir: str = ".") -> dict:
    """
    Lê os dados consolidados de uma sala a partir de seu summary.log (quando concluída).
    """
    summary_file = os.path.join(base_dir, "logs", f"{room_id}_summary.log")
    winner = None
    duration = None
    p1_hp = None
    p2_hp = None
    samples = None
    if os.path.exists(summary_file):
        try:
            with open(summary_file, "r", encoding="utf-8") as f:
                for line in f:
                    line_str = line.strip()
                    if "• Vencedor:" in line_str:
                        winner = line_str.split("• Vencedor:")[-1].strip()
                    elif "• Duração:" in line_str:
                        duration = line_str.split("• Duração:")[-1].strip()
                    elif "• Decisões Coletadas" in line_str:
                        samples = line_str.split(":")[-1].strip()
                    elif "• Jogador 1" in line_str:
                        p1_hp = line_str.split(":")[-1].strip()
                    elif "• Jogador 2" in line_str:
                        p2_hp = line_str.split(":")[-1].strip()
        except Exception:
            pass
    return {
        "winner": winner,
        "duration": duration,
        "p1_hp": p1_hp,
        "p2_hp": p2_hp,
        "samples": samples,
    }


def wait_for_processes(
    active_procs: List[Any],
    timeout: float,
    is_running_check: Optional[Callable[[], bool]] = None,
    check_interval: float = 0.3,
    proc_lock: Optional[threading.Lock] = None,
    on_item_finished: Optional[Callable[[int, Any], None]] = None,
    room_ids: Optional[List[str]] = None,
    stagnant_timeout: float = 60.0,
    progress_interval: float = 8.0,
    show_progress: bool = True,
    on_progress: Optional[Callable[[float, int, int, List[dict]], None]] = None,
) -> bool:
    """
    Aguarda o término de todos os processos monitorados ou até atingir timeout.
    Rastreia atividade de logs por sala e encerra individualmente processos estagnados.
    Exibe telemetria periódica na CLI com turno, HP e tempo decorrido.
    Retorna True se todos terminaram normalmente, False se atingiu timeout ou cancelado.
    """
    finished_indices = set()
    last_activity_time = {idx: time.time() for idx in range(len(active_procs))}
    last_log_sizes = {idx: 0 for idx in range(len(active_procs))}
    max_overall_timeout = max(timeout, 1800.0) if room_ids else timeout
    deadline = time.time() + max_overall_timeout
    start_time = time.time()
    last_progress_time = start_time

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

        now = time.time()
        for idx in range(len(procs_snapshot)):
            if idx not in last_activity_time:
                last_activity_time[idx] = now
                last_log_sizes[idx] = 0

        all_done = True
        for idx, item in enumerate(procs_snapshot):
            if idx in finished_indices:
                continue

            if isinstance(item, (list, tuple)):
                item_done = all(p.poll() is not None for p in item if p is not None)
            elif hasattr(item, "poll"):
                item_done = (item.poll() is not None)
            else:
                item_done = True

            if item_done:
                finished_indices.add(idx)
                if on_item_finished:
                    on_item_finished(idx, item)
                continue

            # Processo ainda ativo: verificar atividade por logs se room_ids informado
            if room_ids and idx < len(room_ids):
                r_id = room_ids[idx]
                curr_size = 0
                for log_file in (
                    f"logs/{r_id}_match_feed.log",
                    f"logs/{r_id}_Bot1_debug.log",
                    f"logs/{r_id}_Bot2_debug.log",
                    f"logs/{r_id}_Bot1.json",
                    f"logs/{r_id}_Bot2.json",
                ):
                    if os.path.exists(log_file):
                        try:
                            curr_size += os.path.getsize(log_file) + int(os.path.getmtime(log_file))
                        except OSError:
                            pass
                if curr_size > last_log_sizes.get(idx, 0):
                    last_activity_time[idx] = now
                    last_log_sizes[idx] = curr_size

                if now - last_activity_time[idx] > stagnant_timeout:
                    # Esta sala específica travou! Encerrar cirurgicamente apenas os processos desta sala
                    if isinstance(item, (list, tuple)):
                        for p in item:
                            terminate_process_cleanly(p)
                    else:
                        terminate_process_cleanly(item)
                    finished_indices.add(idx)
                    if on_item_finished:
                        on_item_finished(idx, item)
                    continue

            all_done = False

        if all_done:
            return True

        # Telemetria periódica em tempo real para o usuário
        if show_progress and room_ids and (now - last_progress_time >= progress_interval):
            last_progress_time = now
            elapsed = now - start_time
            total_rooms = len(room_ids)
            finished_count = len(finished_indices)
            telemetries = []
            active_entries = []

            for idx, r_id in enumerate(room_ids):
                if idx in finished_indices:
                    continue
                telem = get_room_telemetry(r_id)
                telemetries.append(telem)

                gid = f"#{telem['game_id']}" if telem.get("game_id") else r_id[:10]
                turn = telem.get("turn")
                p1_hp = telem.get("p1_hp")
                p2_hp = telem.get("p2_hp")

                thinking_time = now - last_activity_time.get(idx, now)
                think_warn = f" [pensando {int(thinking_time)}s]" if thinking_time >= 25 else ""

                if turn is not None:
                    hp_str = f", {p1_hp}v{p2_hp} HP" if (p1_hp is not None and p2_hp is not None) else ""
                    active_entries.append(f"{gid} (T{turn}{hp_str}{think_warn})")
                else:
                    active_entries.append(f"{gid} ({telem.get('status', 'Iniciando')}{think_warn})")

            if on_progress:
                on_progress(elapsed, total_rooms, finished_count, telemetries)
            elif active_entries:
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                print(
                    f"[Treinador] ⏳ [{mins:02d}m{secs:02d}s] Salas ({len(active_entries)}/{total_rooms} ativas): "
                    + " | ".join(active_entries),
                    flush=True,
                )

        time.sleep(check_interval)

    return False

