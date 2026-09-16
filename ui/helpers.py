"""
ui/helpers.py - Funções de Cache de Alta Performance e Utilitários Compartilhados do Dashboard.

Eliminam gargalos de I/O em reruns do Streamlit e abstraem tarefas de detecção de hardware,
monitoramento de serviços e leitura eficiente de logs tail/jsonl.
"""

import os
import json
import shutil
import subprocess
import streamlit as st
import frontend_manager
from deck_parser import list_saved_decks
from stats_manager import get_stats_data


@st.cache_resource
def get_gpu_info():
    """Detecta GPU via nvidia-smi em ~50ms sem importar torch. Fallback para torch se necessário."""
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=0.8,
            )
            if res.returncode == 0 and res.stdout.strip():
                line = res.stdout.strip().splitlines()[0]
                parts = [p.strip() for p in line.split(",")]
                name = parts[0]
                vram_mb = float(parts[1]) if len(parts) > 1 else 0.0
                return True, name, round(vram_mb / 1024.0, 1)
        except Exception:
            pass
    try:
        import torch

        if torch.cuda.is_available():
            vram = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
            return True, torch.cuda.get_device_name(0), vram
    except Exception:
        pass
    return False, "CPU", 0.0


@st.cache_resource
def get_orchestrator():
    """Carrega o GPUTrainingOrchestrator de forma lazy apenas quando a aba de treino for acessada."""
    from ai.trainer import GPUTrainingOrchestrator

    return GPUTrainingOrchestrator()


@st.cache_data(ttl=2)
def get_total_training_games() -> int:
    """Lê rapidamente o total de partidas do arquivo de métricas sem instanciar o orquestrador."""
    metrics_file = os.path.join("data", "training_metrics.json")
    if os.path.exists(metrics_file):
        try:
            with open(metrics_file, "r") as mf:
                return json.load(mf).get("total_games", 0)
        except Exception:
            pass
    return 0


@st.cache_data(ttl=4)
def get_cached_services_status():
    """Retorna o status de execução do frontend e backend com cache TTL."""
    return frontend_manager.is_frontend_running(deep=False), frontend_manager.is_backend_running(deep=False)


@st.cache_data(ttl=5)
def get_cached_saved_decks():
    """Retorna lista de decks salvos com cache TTL."""
    return list_saved_decks()


@st.cache_data(ttl=3)
def get_cached_stats_data():
    """Retorna dados de estatísticas e ELO com cache TTL."""
    return get_stats_data()


def read_text_tail(filepath: str, max_lines: int = 80, chunk_size: int = 32768) -> str:
    """Lê as últimas N linhas de um arquivo de texto sem carregar o arquivo inteiro na memória."""
    if not os.path.exists(filepath):
        return ""
    try:
        fsize = os.path.getsize(filepath)
        if fsize == 0:
            return ""
        with open(filepath, "rb") as f:
            if fsize <= chunk_size:
                lines = f.read().decode("utf-8", errors="replace").splitlines()
                return "\n".join(lines[-max_lines:])
            f.seek(max(0, fsize - chunk_size))
            chunk = f.read().decode("utf-8", errors="replace")
            lines = chunk.splitlines()
            return "\n".join(lines[-max_lines:])
    except Exception:
        return ""


def read_jsonl_tail(filepath: str, max_lines: int = 100, chunk_size: int = 65536) -> list:
    """Lê eficientemente apenas as últimas N linhas de um arquivo jsonl grande sem carregar tudo na memória."""
    if not os.path.exists(filepath):
        return []
    lines = []
    try:
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            return []
        with open(filepath, "rb") as f:
            if file_size <= chunk_size:
                raw_lines = f.read().decode("utf-8", errors="replace").splitlines()
                for l in reversed(raw_lines):
                    l_s = l.strip()
                    if l_s:
                        lines.append(l_s)
                        if len(lines) >= max_lines:
                            break
            else:
                buffer = b""
                f.seek(0, os.SEEK_END)
                pos = f.tell()
                while pos > 0 and len(lines) < max_lines:
                    read_size = min(chunk_size, pos)
                    pos -= read_size
                    f.seek(pos)
                    chunk = f.read(read_size)
                    buffer = chunk + buffer
                    parts = buffer.split(b"\n")
                    buffer = parts[0]
                    for p in reversed(parts[1:]):
                        p_s = p.strip().decode("utf-8", errors="replace")
                        if p_s:
                            lines.append(p_s)
                            if len(lines) >= max_lines:
                                break
                if buffer and len(lines) < max_lines:
                    p_s = buffer.strip().decode("utf-8", errors="replace")
                    if p_s:
                        lines.append(p_s)

        records = []
        for l in reversed(lines):
            try:
                records.append(json.loads(l))
            except Exception:
                pass
        return records
    except Exception:
        return []


@st.cache_data(ttl=15)
def get_fast_line_count(filepath: str) -> int:
    """Conta rapidamente as linhas de um arquivo grande lendo blocos binários de 1MB com cache de 15s."""
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, "rb") as f:
            return sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1024 * 1024), b""))
    except Exception:
        return 0


def get_suggested_training_profile(device_str: str, mode: str = "balanced") -> dict:
    """
    Calcula parâmetros de treinamento sugeridos:
      - mode='balanced': ~75-80% de carga segura (permite uso normal do PC, navegador, vídeos, sem engasgos).
      - mode='turbo': ~95% de carga máxima (ideal para treino noturno, ausente ou remoto, extraindo todo o potencial do hardware).
    """
    gpu_available, gpu_name, gpu_vram = get_gpu_info()
    is_gpu = "cuda" in device_str.lower() and gpu_available
    try:
        from config.settings import SETTINGS

        vram_gb = gpu_vram if gpu_vram > 0 else getattr(SETTINGS, "vram_gb", 0.0)
        cpu_cores = getattr(SETTINGS, "cpu_logical", 4)
        gpu_name_str = gpu_name
    except Exception:
        vram_gb = gpu_vram if gpu_available else 0.0
        cpu_cores = os.cpu_count() or 4
        gpu_name_str = gpu_name

    try:
        import psutil

        ram_gb = psutil.virtual_memory().total / (1024**3)
    except Exception:
        ram_gb = 8.0

    # Cada worker = 2 bots simultâneos. Cada bot em Python com PyTorch consome ~0.65 GB de RAM.
    # Reservamos pelo menos 3.2 GB de RAM para o SO Linux, Docker (Apache, MySQL, Redis) e Dashboard Streamlit.
    avail_ram_for_bots = max(1.0, ram_gb - 3.2)
    safe_workers_by_ram = max(1, int((avail_ram_for_bots / 0.65) // 2))

    is_turbo = mode == "turbo"

    if not is_gpu:
        if is_turbo:
            turbo_workers = max(1, min(3, safe_workers_by_ram, (cpu_cores - 2) // 2))
            return {
                "device_label": f"CPU ({cpu_cores} threads, {ram_gb:.1f} GB RAM)",
                "mode_name": "🔥 Modo Turbo CPU (~85% Carga)",
                "workers": turbo_workers,
                "batch_size": 256,
                "mcts_sims": 25,
                "save_interval": 25,
                "use_fp16": False,
                "buffer_capacity": 100000,
                "description": f"🔥 Modo Turbo CPU (~85% carga) • {turbo_workers} workers ({turbo_workers*2} bots) • MCTS 25 • Rendimento máximo estável sem travar o sistema.",
            }
        else:
            safe_workers = max(1, min(2, safe_workers_by_ram, (cpu_cores - 2) // 4))
            return {
                "device_label": f"CPU ({cpu_cores} threads, {ram_gb:.1f} GB RAM)",
                "mode_name": "⚖️ Modo Equilibrado CPU (~50% Carga)",
                "workers": safe_workers,
                "batch_size": 128,
                "mcts_sims": 15,
                "save_interval": 15,
                "use_fp16": False,
                "buffer_capacity": 50000,
                "description": f"⚖️ Modo CPU Seguro (~50% carga) • {safe_workers} workers ({safe_workers*2} bots) • MCTS 15 • Sistema 100% livre para uso normal do PC.",
            }

    # Perfil para GPU calibrado por faixa de VRAM e RAM real:
    if vram_gb <= 6.5:
        if is_turbo:
            turbo_workers = max(1, min(3, safe_workers_by_ram, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name_str} ({vram_gb:.1f} GB VRAM, {ram_gb:.1f} GB RAM)",
                "mode_name": "🔥 Modo Turbo GPU (~85% Carga)",
                "workers": turbo_workers,
                "batch_size": 512,
                "mcts_sims": 35,
                "save_interval": 30,
                "use_fp16": True,
                "buffer_capacity": 250000,
                "description": f"🔥 Turbo Máximo Seguro (~85% GPU/CPU) • {turbo_workers} workers ({turbo_workers*2} bots) • Batch 512 • MCTS 35 • Máxima velocidade para treino noturno ou remoto sem risco de OOM.",
            }
        else:
            safe_workers = max(1, min(2, safe_workers_by_ram, (cpu_cores - 2) // 3))
            return {
                "device_label": f"{gpu_name_str} ({vram_gb:.1f} GB VRAM, {ram_gb:.1f} GB RAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~65% Carga)",
                "workers": safe_workers,
                "batch_size": 256,
                "mcts_sims": 25,
                "save_interval": 20,
                "use_fp16": True,
                "buffer_capacity": 100000,
                "description": f"⚖️ {gpu_name_str} (~65% carga) • {safe_workers} workers ({safe_workers*2} bots) • Batch 256 • Memória e threads livres para uso geral do PC.",
            }
    elif vram_gb <= 12.5:
        if is_turbo:
            turbo_workers = max(2, min(5, safe_workers_by_ram, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name_str} ({vram_gb:.1f} GB VRAM, {ram_gb:.1f} GB RAM)",
                "mode_name": "🔥 Modo Turbo GPU (~90% Carga)",
                "workers": turbo_workers,
                "batch_size": 1024,
                "mcts_sims": 50,
                "save_interval": 35,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"🔥 Turbo Máximo (~90% carga) • {turbo_workers} workers ({turbo_workers*2} bots) • Batch 1024 • MCTS 50 • Treinamento de alta densidade sem travas.",
            }
        else:
            safe_workers = max(1, min(3, safe_workers_by_ram, (cpu_cores - 2) // 3))
            return {
                "device_label": f"{gpu_name_str} ({vram_gb:.1f} GB VRAM, {ram_gb:.1f} GB RAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~70% Carga)",
                "workers": safe_workers,
                "batch_size": 512,
                "mcts_sims": 35,
                "save_interval": 25,
                "use_fp16": True,
                "buffer_capacity": 250000,
                "description": f"⚖️ {gpu_name_str} (~70% carga) • {safe_workers} workers ({safe_workers*2} bots) • Batch 512 • Excelente velocidade com folga de sistema.",
            }
    elif vram_gb <= 20.0:
        if is_turbo:
            turbo_workers = max(3, min(8, safe_workers_by_ram, cpu_cores - 2))
            return {
                "device_label": f"{gpu_name_str} ({vram_gb:.1f} GB VRAM, {ram_gb:.1f} GB RAM)",
                "mode_name": "🔥 Modo Turbo GPU (~95% Carga)",
                "workers": turbo_workers,
                "batch_size": 2048,
                "mcts_sims": 80,
                "save_interval": 40,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"🔥 Turbo Máximo (~95% carga) • {turbo_workers} workers • Batch 2048 • MCTS 80 • Rendimento industrial para 16 GB de VRAM.",
            }
        else:
            safe_workers = max(2, min(5, safe_workers_by_ram, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name_str} ({vram_gb:.1f} GB VRAM, {ram_gb:.1f} GB RAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~80% Carga)",
                "workers": safe_workers,
                "batch_size": 1024,
                "mcts_sims": 50,
                "save_interval": 30,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"⚖️ {gpu_name_str} (~80% carga) • {safe_workers} workers • Batch 1024 • Alto rendimento com folga para multitarefa.",
            }
    else:
        if is_turbo:
            turbo_workers = max(4, min(12, safe_workers_by_ram, cpu_cores - 2))
            return {
                "device_label": f"{gpu_name_str} ({vram_gb:.1f} GB VRAM, {ram_gb:.1f} GB RAM)",
                "mode_name": "🔥 Modo Turbo GPU (~95% Carga)",
                "workers": turbo_workers,
                "batch_size": 4096,
                "mcts_sims": 120,
                "save_interval": 50,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"🔥 Turbo Máximo (~95% carga) • {turbo_workers} workers • Batch 4096 • MCTS 120 • Supercomputação para Alpha-Level AI.",
            }
        else:
            safe_workers = max(2, min(6, safe_workers_by_ram, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name_str} ({vram_gb:.1f} GB VRAM, {ram_gb:.1f} GB RAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~80% Carga)",
                "workers": safe_workers,
                "batch_size": 2048,
                "mcts_sims": 80,
                "save_interval": 40,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"⚖️ {gpu_name_str} (~80% carga) • {safe_workers} workers • Batch 2048 • Capacidade extrema sem travar o desktop.",
            }
