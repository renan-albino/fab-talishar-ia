"""
config/settings.py
==================
Configuração Dinâmica do FAB AI Engine.

Calcula automaticamente batch_size, simulações MCTS e workers de self-play
a partir das especificações reais do hardware — sem tabelas hardcoded.

Fórmulas derivadas de:
  - batch_size   : VRAM disponível para ativações após reserva do modelo e buffer
  - mcts_sims    : Throughput estimado de forward passes / decisão em 80ms
  - num_workers  : Min(CPU_bound, RAM_bound, Talishar_bound) de partidas paralelas

Variáveis de Ambiente para Override (útil em scripts cloud/spot):
  FAB_MAX_RESOURCES = 1 | 0                     (ativa modo de potência máxima para GPU/CPU alugada)
  FAB_PHASE         = "teacher" | "student"     (padrão: teacher)
  FAB_BATCH_SIZE    = int                        (force override)
  FAB_WORKERS       = int                        (force override)
  FAB_MCTS_SIMS     = int                        (force override)
  FAB_LR            = float                      (force override)
  FAB_C_PUCT        = float                      (padrão: 1.4)
  FAB_STATE_DIM     = int                        (padrão: 192)
  FAB_ACTION_DIM    = int                        (padrão: 32)
"""

from __future__ import annotations

import os
import math
from dataclasses import dataclass
from typing import Tuple


# ══════════════════════════════════════════════════════════════════
# 1. DETECÇÃO DE HARDWARE
# ══════════════════════════════════════════════════════════════════

def _probe_gpu() -> Tuple[bool, float, int, str]:
    """Retorna (cuda_ok, vram_gb, sm_count, gpu_name)."""
    try:
        import torch
        if not torch.cuda.is_available():
            return False, 0.0, 0, "cpu"
        p = torch.cuda.get_device_properties(0)
        return True, p.total_memory / 1e9, p.multi_processor_count, p.name
    except Exception:
        return False, 0.0, 0, "cpu"


def _probe_ram_gb() -> float:
    """RAM total do sistema em GB (lê /proc/meminfo no Linux)."""
    try:
        import psutil
        return psutil.virtual_memory().total / 1e9
    except ImportError:
        pass
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) / 1_000_000
    except Exception:
        pass
    return 8.0


def _probe_cpu() -> Tuple[int, int]:
    """(physical_cores, logical_cores)."""
    try:
        import psutil
        return psutil.cpu_count(logical=False) or 1, psutil.cpu_count(logical=True) or 1
    except ImportError:
        logical = os.cpu_count() or 1
        return max(1, logical // 2), logical


# ══════════════════════════════════════════════════════════════════
# 2. FÓRMULAS DE DIMENSIONAMENTO DINÂMICO
# ══════════════════════════════════════════════════════════════════

def _nearest_power_of_2(x: float) -> int:
    """Arredonda para a potência de 2 mais próxima."""
    if x <= 1:
        return 1
    return 2 ** round(math.log2(x))


def _compute_batch_size(
    vram_gb: float,
    cuda: bool,
    state_dim: int,
    hidden_dim: int,
    num_res_blocks: int,
    fp16: bool,
    max_resources: bool = False,
) -> int:
    """
    Calcula o batch_size máximo seguro baseado na VRAM disponível.

    Orçamento de VRAM durante o passo de treino (backward pass):
      - Pesos do modelo (FP32 + cópia FP16 com AMP):
            params = (state_dim*hidden + hidden*hidden*2*num_blocks + hidden*action_dim)
            bytes_model  = params * 4          (FP32 master copy)
            bytes_model += params * 2          (FP16 working copy com AMP)
      - Estados AdamW (momentum + variância): 2 × bytes_model FP32
      - Ativações durante backward:
            bytes_per_sample ≈ hidden_dim * (num_res_blocks * 4) * bytes_per_element
      - Buffer de segurança: 0.5 GB (modo max_resources) ou 1.5 GB (padrão)
    """
    if not cuda:
        return 128 if max_resources else 64

    bytes_per_elem = 2 if fp16 else 4  # AMP usa FP16 para ativações

    params = (
        state_dim * hidden_dim
        + hidden_dim
        + (hidden_dim * hidden_dim * 2 + hidden_dim * 2) * num_res_blocks
        + hidden_dim * 128
        + 128
        + 128 * 32
        + hidden_dim * 64
        + 64
        + 64 * 1
    )

    bytes_model = params * 4
    bytes_model_fp16 = params * 2
    bytes_adam = params * 4 * 2
    bytes_grads = params * 4
    bytes_overhead = (bytes_model + bytes_model_fp16 + bytes_adam + bytes_grads)

    safety_gb = 0.5 if max_resources else 1.5
    available_bytes = max(0, (vram_gb - safety_gb) * 1e9 - bytes_overhead)

    bytes_per_sample = (
        hidden_dim * 4
        + hidden_dim * 4 * num_res_blocks
        + 128 * 4
        + 64 * 4
    ) * bytes_per_elem

    fraction = 0.90 if max_resources else 0.75
    raw = available_bytes / max(bytes_per_sample, 1)
    batch = _nearest_power_of_2(raw * fraction)

    upper_limit = 65_536 if max_resources else 32_768
    return max(64, min(batch, upper_limit))


def _compute_mcts_sims(
    vram_gb: float,
    sm_count: int,
    cuda: bool,
    hidden_dim: int,
    state_dim: int,
    max_resources: bool = False,
) -> int:
    """
    Calcula o número de simulações MCTS por decisão dado o throughput da GPU.
    """
    if not cuda:
        return 20 if max_resources else 10

    flops_per_sample = 2 * (
        state_dim * hidden_dim * 2
        + hidden_dim * hidden_dim * 4 * 3
        + hidden_dim * 128 * 2
        + 128 * 32 * 2
        + hidden_dim * 64 * 2
        + 64 * 1 * 2
    )

    tflops = sm_count * 230e9
    latency_single_s = flops_per_sample / tflops

    batch_eval = 16 if max_resources else 8
    latency_batched_s = latency_single_s * batch_eval * 1.5

    target_time_s = 0.120 if max_resources else 0.080
    sims_raw = target_time_s / max(latency_batched_s, 1e-9)

    sims = _nearest_power_of_2(sims_raw)
    max_sims = 3_200 if max_resources else 1_600
    return max(10, min(sims, max_sims))


def _compute_workers(
    cpu_logical: int,
    ram_gb: float,
    cuda: bool,
    max_resources: bool = False,
) -> int:
    """
    Calcula o número de partidas de self-play em paralelo.
    """
    if max_resources:
        max_cpu = max(1, (cpu_logical - 1) // 2)
        max_ram = max(1, int((ram_gb - 1.0) / 0.20))
        max_talishar = 24
    else:
        max_cpu = max(1, (cpu_logical - 2) // 2)
        max_ram = max(1, int((ram_gb - 2.0) / 0.25))
        max_talishar = 12

    workers = min(max_cpu, max_ram, max_talishar)
    upper_bound = 32 if max_resources else 16
    return max(1, min(workers, upper_bound))


def _compute_buffer_capacity(ram_gb: float, max_resources: bool = False) -> int:
    """Capacidade do replay buffer em amostras."""
    pct = 0.40 if max_resources else 0.20
    budget_bytes = ram_gb * 1e9 * pct
    bytes_per_sample = (192 + 32 + 1) * 4
    capacity = int(budget_bytes / bytes_per_sample)
    max_cap = 20_000_000 if max_resources else 10_000_000
    return max(10_000, min(capacity, max_cap))


def _compute_hidden_dim(vram_gb: float, cuda: bool, max_resources: bool = False) -> int:
    """Dimensiona a largura da rede Teacher."""
    if not cuda:
        return 128
    multiplier = 96 if max_resources else 64
    raw = vram_gb * multiplier
    rounded = int(round(raw / 64) * 64)
    max_h = 1024 if max_resources or vram_gb >= 24 else 512
    return max(128, min(rounded, max_h))


def _compute_num_res_blocks(vram_gb: float, cuda: bool, max_resources: bool = False) -> int:
    """Blocos residuais."""
    if not cuda:
        return 2
    divisor = 1.5 if max_resources else 2.0
    max_blocks = 16 if max_resources else 12
    return max(2, min(int(vram_gb / divisor), max_blocks))


# ══════════════════════════════════════════════════════════════════
# 3. HARDWARE SCAN DE LATÊNCIA DE INFERÊNCIA
# ══════════════════════════════════════════════════════════════════

def _probe_inference_latency_ms(
    hidden_dim: int,
    state_dim: int,
    cuda: bool,
    n_warmup: int = 3,
    n_measure: int = 20,
) -> float:
    """
    Mede a latência real de um forward pass da rede Policy-Value em milissegundos.

    Usa uma rede proxy com a mesma escala do Teacher para medição realista.
    Executado uma única vez no startup (não afeta o hot-path de inferência).

    Fluxo:
      1. Instancia proxy nn.Sequential com mesmo hidden_dim e state_dim.
      2. Aquece JIT/alocador com n_warmup passes (descartados).
      3. Mede n_measure passes com perf_counter (alta resolução).
      4. Retorna média em ms.

    Fallback em caso de erro: 5 ms (GPU) ou 2 ms (CPU) — conservadores.
    """
    import time
    try:
        import torch
        import torch.nn as nn

        device = torch.device("cuda:0" if cuda else "cpu")

        # Proxy com mesma escala do Teacher: Input → Hidden → LayerNorm → Out (policy+value)
        proxy = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.LeakyReLU(0.1),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.LayerNorm(hidden_dim // 2),
            nn.LeakyReLU(0.1),
            nn.Linear(hidden_dim // 2, 33),   # 32 policy logits + 1 value
        ).to(device)
        proxy.eval()

        x = torch.zeros(1, state_dim, device=device)

        # Warmup — garante que o JIT e o alocador de VRAM já estejam prontos
        with torch.no_grad():
            for _ in range(n_warmup):
                proxy(x)
        if cuda:
            try:
                torch.cuda.synchronize()
            except Exception:
                pass

        # Medição real
        t0 = time.perf_counter()
        with torch.no_grad():
            for _ in range(n_measure):
                proxy(x)
        if cuda:
            try:
                torch.cuda.synchronize()
            except Exception:
                pass
        t1 = time.perf_counter()

        latency_ms = ((t1 - t0) / n_measure) * 1000.0
        return max(0.01, latency_ms)

    except Exception:
        return 5.0 if cuda else 2.0  # Fallback conservador


def _compute_ismcts_worlds_from_latency(
    latency_ms: float,
    mcts_sims: int,
    cuda: bool,
    decision_budget_ms: float = 80.0,
    max_resources: bool = False,
) -> int:
    """
    Calcula o número máximo de mundos ISMCTS a partir da latência real medida.

    Com batch leaf evaluation ativado (v2):
      - Cada mundo executa 1 batch forward pass de tamanho `mcts_sims` no lugar
        de `mcts_sims` passes sequenciais.
      - GPU: latência do batch ≈ latência_single × 1.5 (overhead de kernels)
      - CPU: latência do batch ≈ latência_single × min(mcts_sims, cpu_threads)^0.4
             (paralelismo vetorial limitado pela memória)

    Fórmula:
      latency_per_world_ms = latency_batch_ms + overhead_ms (seleção + backprop)
      max_worlds = floor(decision_budget / latency_per_world_ms)

    Hard cap para garantir responsividade do polling loop do bot:
      CPU: 8  mundos | GPU: 24 mundos (modo padrão)
      CPU: 12 mundos | GPU: 48 mundos (max_resources)
    """
    overhead_ms = 2.0  # Overhead de seleção PUCT + backprop por mundo

    if cuda:
        # GPU: um batch de qualquer tamanho razoável ≈ mesmo tempo que single pass
        latency_batch_ms = latency_ms * 1.5
    else:
        # CPU: lote de N tende a ser sublinear por vetorização BLAS
        batch_speedup = max(1.0, float(mcts_sims) ** 0.4)
        latency_batch_ms = latency_ms * batch_speedup

    latency_per_world_ms = max(0.1, latency_batch_ms + overhead_ms)

    budget = decision_budget_ms * (1.5 if max_resources else 1.0)
    raw_worlds = int(budget / latency_per_world_ms)

    hard_cap = (48 if max_resources else 24) if cuda else (12 if max_resources else 8)
    return max(1, min(raw_worlds, hard_cap))


# ══════════════════════════════════════════════════════════════════
# 3. DATACLASS PRINCIPAL (imutável após construção)
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class FaBSettings:
    """Configuração completa do projeto, derivada do hardware."""

    # Hardware detectado
    machine_profile: str
    device: str
    gpu_name: str
    vram_gb: float
    ram_gb: float
    cpu_physical: int
    cpu_logical: int
    sm_count: int

    # Flags de operação
    max_resources_mode: bool    # True se FAB_MAX_RESOURCES=1 (Cloud Beast Mode)
    current_phase: str          # "teacher" | "student"

    # Dimensões do modelo Teacher
    state_dim: int
    action_dim: int
    hidden_dim: int
    num_res_blocks: int
    dropout: float

    # Dimensões do modelo Student (NNUE)
    nnue_input_dim: int
    nnue_hidden_dims: tuple

    # Hiperparâmetros de treino — todos CALCULADOS
    batch_size: int
    learning_rate: float
    weight_decay: float
    lr_scheduler_step: int
    lr_scheduler_gamma: float
    grad_clip_norm: float
    fp16: bool

    # Replay Buffer — CALCULADO
    buffer_capacity: int
    min_buffer_to_train: int

    # Self-play — CALCULADO
    num_workers: int
    game_timeout_seconds: int
    save_interval_games: int

    # MCTS — CALCULADO + MEDIDO
    mcts_simulations: int
    ismcts_worlds: int        # Calculado a partir da latência real medida em hardware
    ismcts_c_puct: float
    inference_latency_ms: float  # Latência real de 1 forward pass da rede proxy (ms)


    # Destilação (Fase 2)
    distillation_temperature: float
    distillation_alpha: float

    # Caminhos de artefatos
    checkpoint_dir: str
    teacher_checkpoint: str
    student_checkpoint: str
    parquet_export_dir: str


# ══════════════════════════════════════════════════════════════════
# 4. FACTORY — Constrói a instância calculando tudo
# ══════════════════════════════════════════════════════════════════

def _build_settings() -> FaBSettings:
    # ── 4.1 Detecção de hardware ──────────────────────────────────
    cuda, vram_gb, sm_count, gpu_name = _probe_gpu()
    ram_gb   = _probe_ram_gb()
    cpu_p, cpu_l = _probe_cpu()

    # ── 4.2 Flags de Ambiente ────────────────────────────────────
    max_resources = os.environ.get("FAB_MAX_RESOURCES", "0").lower() in ("1", "true", "yes")

    current_phase = os.environ.get("FAB_PHASE", "teacher").lower()
    if current_phase not in ("teacher", "student"):
        current_phase = "teacher"

    state_dim  = int(os.environ.get("FAB_STATE_DIM",  192))
    action_dim = int(os.environ.get("FAB_ACTION_DIM",  32))
    c_puct     = float(os.environ.get("FAB_C_PUCT",   1.4))
    lr         = float(os.environ.get("FAB_LR", 3e-4))

    # ── 4.3 Calcular dimensões da rede ────────────────────────────
    hidden_dim     = _compute_hidden_dim(vram_gb, cuda, max_resources)
    num_res_blocks = _compute_num_res_blocks(vram_gb, cuda, max_resources)
    fp16           = cuda

    # ── 4.4 Calcular batch_size a partir da VRAM ─────────────────
    if os.environ.get("FAB_BATCH_SIZE"):
        batch_size = int(os.environ["FAB_BATCH_SIZE"])
    else:
        batch_size = _compute_batch_size(
            vram_gb, cuda, state_dim, hidden_dim, num_res_blocks, fp16, max_resources
        )

    # ── 4.5 Calcular simulações MCTS a partir do throughput GPU ───
    if os.environ.get("FAB_MCTS_SIMS"):
        mcts_sims = int(os.environ["FAB_MCTS_SIMS"])
    else:
        mcts_sims = _compute_mcts_sims(vram_gb, sm_count, cuda, hidden_dim, state_dim, max_resources)

    # ── 4.6 Calcular workers a partir de CPU + RAM ────────────────
    if os.environ.get("FAB_WORKERS"):
        num_workers = int(os.environ["FAB_WORKERS"])
    else:
        num_workers = _compute_workers(cpu_l, ram_gb, cuda, max_resources)

    # ── 4.7 Calcular capacidade do buffer ────────────────────────
    buffer_cap = _compute_buffer_capacity(ram_gb, max_resources)
    min_to_train = max(batch_size, 512)

    # ── 4.8 Parâmetros derivados de batch e workers ───────────────
    game_timeout   = 120
    save_interval  = max(5, num_workers * 3)

    lr_step  = 50
    lr_gamma = 0.97
    if vram_gb >= 40:
        lr_step  = 200
        lr_gamma = 0.99

    ismcts_worlds_legacy = max(2, min(num_workers * 2, 24 if max_resources else 16))

    # ── 4.8b Hardware Scan: medir latência real de inferência ────────
    # Executado uma única vez no startup para calibrar o número de mundos ISMCTS.
    # Usa rede proxy com mesma escala do Teacher (não carrega pesos — apenas arquitetura).
    inference_latency_ms = _probe_inference_latency_ms(hidden_dim, state_dim, cuda)

    # ── 4.8c Calcular mundos ISMCTS a partir da latência medida ──────
    ismcts_worlds_by_latency = _compute_ismcts_worlds_from_latency(
        latency_ms=inference_latency_ms,
        mcts_sims=mcts_sims,
        cuda=cuda,
        decision_budget_ms=120.0 if max_resources else 80.0,
        max_resources=max_resources,
    )
    # Usa o menor entre o limite por latência e o limite por workers (mais conservador)
    ismcts_worlds = min(ismcts_worlds_by_latency, ismcts_worlds_legacy)

    nnue_hidden = (256, 32)


    # ── 4.9 Perfil descritivo ─────────────────────────────────────
    if not cuda:
        profile = "cpu_only"
    elif vram_gb >= 40:
        profile = "cloud_h100"
    elif vram_gb >= 12:
        profile = "cloud_a10"
    elif vram_gb >= 9:
        profile = "local_16gb"
    else:
        profile = "local_6gb"

    # ── 4.10 Caminhos ─────────────────────────────────────────────
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ckpt_dir    = os.path.join(base_dir, "data", "checkpoints")
    parquet_dir = os.path.join(base_dir, "data", "parquet_export")

    return FaBSettings(
        # Hardware
        machine_profile=profile,
        device="cuda:0" if cuda else "cpu",
        gpu_name=gpu_name,
        vram_gb=round(vram_gb, 2),
        ram_gb=round(ram_gb, 1),
        cpu_physical=cpu_p,
        cpu_logical=cpu_l,
        sm_count=sm_count,

        # Flags
        max_resources_mode=max_resources,
        current_phase=current_phase,

        # Arquitetura Teacher
        state_dim=state_dim,
        action_dim=action_dim,
        hidden_dim=hidden_dim,
        num_res_blocks=num_res_blocks,
        dropout=0.1,

        # Arquitetura NNUE
        nnue_input_dim=state_dim,
        nnue_hidden_dims=nnue_hidden,

        # Treino — calculados
        batch_size=batch_size,
        learning_rate=lr,
        weight_decay=1e-4,
        lr_scheduler_step=lr_step,
        lr_scheduler_gamma=lr_gamma,
        grad_clip_norm=1.0,
        fp16=fp16,

        # Buffer — calculado
        buffer_capacity=buffer_cap,
        min_buffer_to_train=min_to_train,

        # Self-play — calculado
        num_workers=num_workers,
        game_timeout_seconds=game_timeout,
        save_interval_games=save_interval,

        # MCTS — calculado + medido por hardware scan
        mcts_simulations=mcts_sims,
        ismcts_worlds=ismcts_worlds,
        ismcts_c_puct=c_puct,
        inference_latency_ms=round(inference_latency_ms, 4),


        # Destilação
        distillation_temperature=3.0,
        distillation_alpha=0.5,

        # Caminhos
        checkpoint_dir=ckpt_dir,
        teacher_checkpoint=os.path.join(ckpt_dir, "teacher_latest.pt"),
        student_checkpoint=os.path.join(ckpt_dir, "nnue_latest.pt"),
        parquet_export_dir=parquet_dir,
    )


# ══════════════════════════════════════════════════════════════════
# 5. INSTÂNCIA GLOBAL (Singleton — importada por todos os módulos)
# ══════════════════════════════════════════════════════════════════

SETTINGS: FaBSettings = _build_settings()


# ══════════════════════════════════════════════════════════════════
# 6. RELATÓRIO DE DIAGNÓSTICO (CLI: python config/settings.py)
# ══════════════════════════════════════════════════════════════════

def _bar(label: str, value: float, max_val: float, width: int = 30) -> str:
    """Barra de progresso ASCII proporcional."""
    numeric_val = float(value)
    numeric_max = float(max_val)
    if numeric_max <= 0:
        filled = 0
    else:
        filled = int(width * min(numeric_val, numeric_max) / numeric_max)
    bar = "█" * filled + "░" * (width - filled)
    return f"  {label:<18} [{bar}]  {numeric_val:.1f} GB"


def print_settings_report():
    s = SETTINGS
    W = 60
    print(f"\n{'═' * W}")
    print(f"  ⚔  FAB AI Engine — Configuração Auto-Detectada")
    print(f"{'═' * W}")
    print(f"  Perfil         : {s.machine_profile.upper()}")
    print(f"  Max Resources  : {'⚡ ATIVADO (Cloud Max Performance)' if s.max_resources_mode else 'DESATIVADO (Padrão Seguro)'}")
    print(f"  GPU            : {s.gpu_name}")
    print(f"  VRAM           : {s.vram_gb} GB  ({s.sm_count} SMs)")
    print(f"  RAM Sistema    : {s.ram_gb} GB")
    print(f"  CPU Cores      : {s.cpu_physical}p / {s.cpu_logical}t")
    print(f"  Dispositivo    : {s.device}")
    print(f"  Fase Ativa     : {s.current_phase.upper()}")
    print(f"{'─' * W}")
    print(f"  {'HIPERPARÂMETRO':<26}  {'VALOR CALCULADO':<14}  FÓRMULA BASE")
    print(f"{'─' * W}")
    print(f"  {'Batch Size':<26}  {s.batch_size:<14,}  VRAM livre ÷ ativações/amostra")
    print(f"  {'MCTS Sims/decisão':<26}  {s.mcts_simulations:<14}  80-120ms ÷ latência forward pass")
    print(f"  {'Partidas paralelas':<26}  {s.num_workers:<14}  min(CPU, RAM, Talishar)")
    print(f"  {'Buffer de Replay':<26}  {s.buffer_capacity:<14,}  RAM ÷ 900 bytes/amostra")
    print(f"  {'ISMCTS Mundos':<26}  {s.ismcts_worlds:<14}  Hardware scan: {s.inference_latency_ms:.3f} ms/pass")
    print(f"  {'Latência Inferência':<26}  {s.inference_latency_ms:<10.3f} ms  Medido em startup (rede proxy)")
    print(f"  {'Min p/ treinar':<26}  {s.min_buffer_to_train:<14,}  max(batch_size, 512)")

    print(f"{'─' * W}")
    print(f"  {'Rede Teacher':<26}  {s.state_dim}→{s.hidden_dim}×{s.num_res_blocks} blocos→{s.action_dim}|1")
    print(f"  {'Rede NNUE':<26}  {s.nnue_input_dim}→{s.nnue_hidden_dims}")
    print(f"  {'FP16 AMP':<26}  {s.fp16}")
    print(f"  {'Learning Rate':<26}  {s.learning_rate}")
    print(f"  {'LR Scheduler':<26}  step={s.lr_scheduler_step}  γ={s.lr_scheduler_gamma}")
    print(f"  {'Grad Clip Norm':<26}  {s.grad_clip_norm}")
    print(f"{'─' * W}")
    print(_bar("VRAM uso modelo",   s.vram_gb * 0.15,  s.vram_gb))
    print(_bar("VRAM ativações",    s.vram_gb * 0.60,  s.vram_gb))
    print(_bar("RAM buffer",        s.ram_gb  * (0.40 if s.max_resources_mode else 0.20),  s.ram_gb))
    print(f"{'─' * W}")
    print(f"  Teacher ckpt   : {s.teacher_checkpoint}")
    print(f"  NNUE ckpt      : {s.student_checkpoint}")
    print(f"  Parquet export : {s.parquet_export_dir}")
    print(f"  Temp. Distil.  : {s.distillation_temperature}")
    print(f"  c_puct         : {s.ismcts_c_puct}")
    print(f"{'═' * W}\n")


if __name__ == "__main__":
    print_settings_report()
