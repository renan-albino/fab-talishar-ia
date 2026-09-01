import torch
import os

print("=== HARDWARE PROBE ===")
print(f"CUDA available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    for i in range(torch.cuda.device_count()):
        props = torch.cuda.get_device_properties(i)
        print(f"GPU {i}: {props.name} | VRAM: {round(props.total_memory / 1e9, 2)} GB | SMs: {props.multi_processor_count}")

try:
    import psutil
    mem = psutil.virtual_memory()
    print(f"RAM total: {round(mem.total / 1e9, 1)} GB | Available: {round(mem.available / 1e9, 1)} GB")
    print(f"CPU physical cores: {psutil.cpu_count(logical=False)}")
    print(f"CPU logical cores: {psutil.cpu_count(logical=True)}")
except ImportError:
    print(f"CPU logical cores: {os.cpu_count()}")
    print("psutil not installed — RAM info unavailable")
