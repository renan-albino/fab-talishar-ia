"""
Benchmark de diagnóstico do gargalo Sim2Real: CPU vs GPU para múltiplos bots.
Mede latência de inferência, overhead de contexto CUDA e throughput concorrente.
"""
import os
import sys
import time
import multiprocessing as mp
import torch
import numpy as np

# Configurar caminhos do projeto
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai.model import FaBCardTransformerNetwork

def single_process_eval(device_str: str, num_evals: int = 20, batch_size: int = 50):
    """Executa avaliações sequenciais em um único processo."""
    device = torch.device(device_str)
    model = FaBCardTransformerNetwork().to(device)
    model.eval()

    # Warmup
    dummy = torch.randn(batch_size, 832, device=device)
    with torch.no_grad():
        for _ in range(3):
            _ = model(dummy)
    if "cuda" in device_str:
        torch.cuda.synchronize()

    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(num_evals):
            x = torch.randn(batch_size, 832, device=device)
            _ = model(x)
            if "cuda" in device_str:
                torch.cuda.synchronize()
    elapsed = time.perf_counter() - t0
    return elapsed / num_evals

def worker_bench(proc_id: int, device_str: str, num_evals: int, batch_size: int, queue: mp.Queue):
    """Worker que simula um bot fazendo decisões."""
    os.environ["TALISHAR_SKIP_GPU_PROBE"] = "1"
    t_start = time.perf_counter()
    device = torch.device(device_str)
    
    # Se for CPU, limita threads por worker para simular concorrência
    if device_str == "cpu":
        torch.set_num_threads(2)
        
    model = FaBCardTransformerNetwork().to(device)
    model.eval()
    
    t_init = time.perf_counter() - t_start

    # Loop de simulação de turnos
    t0 = time.perf_counter()
    with torch.no_grad():
        for _ in range(num_evals):
            x = torch.randn(batch_size, 832, device=device)
            _ = model(x)
            if "cuda" in device_str:
                torch.cuda.synchronize()
            time.sleep(0.01) # Simula pequeno intervalo de I/O do bot
            
    t_work = time.perf_counter() - t0
    queue.put((proc_id, t_init, t_work))

def run_concurrent_bench(num_workers: int, device_str: str, num_evals: int = 30, batch_size: int = 50):
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    procs = []

    t_total_start = time.perf_counter()
    for i in range(num_workers):
        p = ctx.Process(target=worker_bench, args=(i, device_str, num_evals, batch_size, queue))
        procs.append(p)
        p.start()

    results = []
    for _ in range(num_workers):
        results.append(queue.get())

    for p in procs:
        p.join()
        
    total_time = time.perf_counter() - t_total_start
    avg_init = sum(r[1] for r in results) / len(results)
    avg_work = sum(r[2] for r in results) / len(results)
    return total_time, avg_init, avg_work

def main():
    print("=" * 65)
    print("🔬 DIAGNÓSTICO DE PERFORMANCE: CPU vs GPU (GTX 1660 SUPER)")
    print("=" * 65)

    has_cuda = torch.cuda.is_available()
    print(f"CUDA Disponível: {has_cuda}")
    if has_cuda:
        prop = torch.cuda.get_device_properties(0)
        print(f"GPU: {prop.name} | VRAM: {prop.total_memory / 1e9:.2f} GB | SMs: {prop.multi_processor_count}")
    print(f"CPU Cores: {os.cpu_count()}")
    print("-" * 65)

    # Teste 1: Inferência isolada (Single process)
    print("\n[Teste 1] Inferência Isolada (Single Process - Batch=50):")
    cpu_lat = single_process_eval("cpu", num_evals=25, batch_size=50) * 1000
    print(f"  • CPU (1 processo, batch 50): {cpu_lat:.2f} ms por passo")

    if has_cuda:
        gpu_lat = single_process_eval("cuda:0", num_evals=25, batch_size=50) * 1000
        print(f"  • GPU (1 processo, batch 50): {gpu_lat:.2f} ms por passo")
        
        # Teste com batch grande (treinamento real)
        gpu_train_lat = single_process_eval("cuda:0", num_evals=10, batch_size=2048) * 1000
        print(f"  • GPU no Treinamento (batch 2048): {gpu_train_lat:.2f} ms por passo ({2048 / (gpu_train_lat/1000):.0f} amostras/s)")

    # Teste 2: Concorrência multi-bot (Simulação de 4 workers = 8 bots)
    num_bots = 8
    print(f"\n[Teste 2] Concorrência Multiprocesso ({num_bots} bots simultâneos):")
    
    print(f"  Rodando {num_bots} bots em CPU (torch threads=2)...")
    cpu_total, cpu_init, cpu_work = run_concurrent_bench(num_bots, "cpu", num_evals=25, batch_size=50)
    print(f"  ✓ CPU: Tempo Total: {cpu_total:.2f}s | Init Médio: {cpu_init:.3f}s | Trabalho Médio: {cpu_work:.2f}s")

    if has_cuda:
        print(f"  Rodando {num_bots} bots em GPU (cuda:0)...")
        gpu_total, gpu_init, gpu_work = run_concurrent_bench(num_bots, "cuda:0", num_evals=25, batch_size=50)
        print(f"  ✓ GPU: Tempo Total: {gpu_total:.2f}s | Init Médio: {gpu_init:.3f}s | Trabalho Médio: {gpu_work:.2f}s")
        
        print("\n" + "=" * 65)
        print("📊 COMPARAÇÃO E ANÁLISE:")
        print(f"  • Tempo de Inicialização do Processo: GPU é {gpu_init / max(cpu_init, 1e-4):.1f}x MAIS LENTA que CPU")
        print(f"  • Tempo Total dos 8 bots: GPU={gpu_total:.2f}s vs CPU={cpu_total:.2f}s")
        if gpu_total > cpu_total:
            print(f"  ⚠️ Gargalo Detectado: Rodar 8 bots na GPU é {(gpu_total / cpu_total - 1)*100:.1f}% MAIS LENTO do que na CPU!")
        else:
            print(f"  Speedup GPU: {cpu_total / gpu_total:.2f}x")
    print("=" * 65)

if __name__ == "__main__":
    main()
