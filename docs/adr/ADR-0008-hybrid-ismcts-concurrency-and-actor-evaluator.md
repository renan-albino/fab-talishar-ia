# ADR-0008: Concorrência Híbrida no ISMCTS e Avaliação Preguiçosa de Hardware (Lazy Probing)

- **Status**: Accepted (Amends [ADR-0002](ADR-0002-parallel-ismcts-multithreading.md))
- **Date**: 2026-09-18
- **Deciders**: Equipe FaB Talishar AI (Architecture Review)

---

## Context

Na [ADR-0002](ADR-0002-parallel-ismcts-multithreading.md), a equipe optou pelo `concurrent.futures.ThreadPoolExecutor` para paralelizar a avaliação de mundos determinizados do ISMCTS, rejeitando o uso de `multiprocessing` devido ao custo de serialização (pickle) e complexidade de IPC.

No entanto, o crescimento da complexidade de busca e a tentativa de contornar o Global Interpreter Lock (GIL) do CPython via `multiprocessing.spawn` dentro de cada bot revelou um problema crítico durante o treinamento autônomo por Self-Play:
1. **Multiplicação Destrutiva de Processos**: O `orchestrator.py` já paraleliza o treino criando $N$ salas concorrentes e $2N$ processos de bots. Quando cada bot ativava $W=6$ subprocessos via `spawn`, o sistema gerava até 24 a 48 processos Python pesados competindo pelos mesmos 12 núcleos lógicos e saturando a memória da máquina virtual WSL2 (9.7 GB de RAM + Swap), culminando no acionamento do Linux Kernel OOM Killer e encerramento do `/init` (PID 2) do Hyper-V.
2. **Storm de Probes de Hardware**: Na inicialização de cada processo worker no modo `spawn`, a importação de `config/settings.py` disparava chamadas síncronas a `nvidia-smi` (`_probe_gpu()`), gerando 24 execuções simultâneas de checagem de hardware e sobrecarregando o driver `/dev/dxg`.
3. **Contenção de VRAM por Contextos CUDA**: No PyTorch para Linux/WSL2, cada processo independente que inicializa o CUDA aloca entre 400 MB e 600 MB de VRAM fixa para o runtime da GPU. Em placas de entrada (ex: 6 GB VRAM), múltiplos processos executando CUDA simultaneamente provocam *CUDA Out of Memory* instantâneo.

---

## Decision

Evoluir a estratégia de paralelização do ISMCTS para uma **Arquitetura Híbrida Configurável** governada pelo parâmetro `concurrency_mode` e introduzir o **Lazy Hardware Probing**:

### 1. Quatro Modos de Concorrência (`concurrency_mode`)

1. **`threads` (Padrão e Recomendado para Self-Play)**:
   - Mantém o `ThreadPoolExecutor(max_workers=min(4, worlds))` in-process conforme a ADR-0002.
   - **Custo de Processo**: 0 MB adicionais.
   - **Uso de Multicore**: O paralelismo de múltiplos núcleos é aproveitado naturalmente pelo `orchestrator.py`, que já executa 2 a 4 salas de duelo simultâneas em processos separados.
   - **Estabilidade**: 100% resiliente contra OOM no WSL2 e ideal para hardware com memória limitada.

2. **`multiprocessing` (Opção Avançada: Actor-Evaluator)**:
   - Implementa a arquitetura Actor-Evaluator via `ai/mcts/inference_server.py`.
   - **Workers (Actors)**: Processos `mp.get_context("spawn").Process` rodando estritamente em CPU, desacoplados de CUDA, navegando em suas próprias árvores com GIL isolado e usando o `RemoteModelProxy`.
   - **Servidor Central (Evaluator)**: O processo pai detém o modelo PyTorch na GPU e executa o `BatchedInferenceServer`, escutando requisições via `multiprocessing.Pipe`, agrupando estados em batches dinâmicos `[N, 832]` e devolvendo predições fatiadas.
   - **Resumo de Nível 1**: Ao final da busca, os workers transmitem apenas as estatísticas da raiz e dos filhos imediatos (`children_stats`), reduzindo o payload de IPC para poucos kilobytes.

3. **`direct_gpu` (Opção Avançada: GPU de Alta Capacidade)**:
   - Cada worker MCTS instancia o modelo diretamente no dispositivo CUDA (sem IPC Pipes).
   - Para evitar o erro fatal de CUDA IPC (`RuntimeError: CUDA error: invalid resource handle` no pickle de tensores CUDA entre processos), o processo pai passa o modelo com tensores na CPU (`_get_worker_model_for_direct_gpu`), e o worker invoca `.to(device)` dentro de seu próprio contexto CUDA.
   - Destinado a partidas individuais ou servidores com GPUs de alta capacidade (16 GB, 24 GB+ de VRAM).

4. **`sequential`**:
   - Loop sequencial simples mundo a mundo. Útil para depuração e testes unitários.

### 2. Orçamento Preditivo de VRAM (`SETTINGS.estimate_vram_usage`)

Em vez de bloquear rigidamente a execução de múltiplos mundos no modo `direct_gpu`, o sistema calcula dinamicamente a demanda estimada de memória:
$$\text{VRAM Estimada} = (\text{Salas} \times \text{Mundos}) \times 0.45\text{ GB} + 1.2\text{ GB (Base do Treinador)}$$

- No `dashboard.py` (Streamlit), um card de telemetria preditiva exibe alertas visuais (Verde, Amarelo e Vermelho) comparando a demanda estimada com a VRAM física detectada (`SETTINGS.vram_gb`).
- O usuário possui controle total via checkbox para forçar a execução caso disponha de VRAM suficiente.

### 3. Lazy Hardware Probing no `config/settings.py`

- A função `_probe_gpu()` foi encapsulada com `@functools.lru_cache(maxsize=1)`.
- Adicionada a salvaguarda de ambiente `os.environ["TALISHAR_SKIP_GPU_PROBE"] = "1"`, injetada nos processos de bots pelo orquestrador.
- Quando a variável está ativa, o hardware scan não invoca `nvidia-smi` e retorna valores cacheados/seguros instantaneamente.

---

## Consequences

### Positive
- **Eliminação de Crashes por OOM no WSL2**: O modo `threads` garante que o auto-treinamento com múltiplas salas simultâneas permaneça leve (< 4 GB de RAM) e com 0% de uso de swap.
- **Escalabilidade para Hardware Avançado**: Usuários com placas de vídeo de alta capacidade (RTX 3090, 4090, A100) podem habilitar `direct_gpu` ou `multiprocessing` diretamente pela interface gráfica ou CLI (`--ismcts-concurrency`).
- **Eliminação de Storms de Processos**: A flag de ambiente e o cache LRU eliminaram a execução repetida de dezenas de instâncias de `nvidia-smi` no boot de subprocessos.
- **Transparência e Telemetria**: O `ismcts_log` registra formalmente o modo de concorrência utilizado e a flag `fallback: bool`, garantindo auditabilidade no dashboard.

### Negative / Trade-offs
- **Complexidade de Código**: O `ai/mcts/ismcts.py` passa a gerenciar quatro fluxos de execução distintos, com testes unitários dedicados a cada rota.
- **Sobrecarga de Contexto CUDA no modo `direct_gpu`**: Se ativado inadvertidamente em GPUs com $\le 6$ GB de VRAM com muitas salas, o modo direto ainda causará CUDA OOM (mitigado pelos alertas visuais preditivos no dashboard).
