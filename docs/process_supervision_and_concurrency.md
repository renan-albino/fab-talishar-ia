# Guia Técnico: Supervisão de Processos, Liveness e Concorrência Adaptativa

## 1. Visão Geral da Arquitetura de Processos

O ecossistema do **FaB Talishar AI** suporta múltiplos níveis de paralelismo para auto-treinamento (*self-play*) e confrontos na Arena. Cada partida ativa é orquestrada por dois subprocessos independentes de bots:

- **Host (Bot 1):** Cria a sala no backend Talishar (`CreateGame.php`), submete o baralho/sideboard e gerencia a criação de turnos.
- **Join (Bot 2):** Conecta-se à sala criada (`JoinGame.php`), submete o baralho/sideboard e interage na partida.

No modo de treinamento concorrente (`num_workers`), o `ai/training/orchestrator.py` gera múltiplos pares de bots:
$$\text{Total de Processos Concorrentes} = 2 \times \text{num\_workers}$$

---

## 2. Dimensionamento Dinâmico de Threads (Anti-Thrashing)

### O Problema do *Thread Thrashing*
Em ambientes Linux/WSL2, o PyTorch aloca por padrão tantas threads intra-operação quanto núcleos lógicos detectados no sistema. Se cada processo de bot criar 6 threads e 5 workers estiverem rodando simultaneamente (10 bots), são geradas **60 threads concorrentes de inferência** disputando 6 núcleos físicos. 

Para inferência com `batch_size = 1` no MCTS, isso gera:
1. Overhead severo de troca de contexto (*context switching*).
2. Perda contínua de linhas de cache L1/L2.
3. *Spinlocks* do OpenMP saturando a CPU em 100% com baixo rendimento útil.

### Fórmula Adaptativa no `orchestrator.py`
Para garantir máxima velocidade em qualquer máquina (notebooks, estações de trabalho ou servidores multinúcleo), a alocação de threads é calculada dinamicamente:

```python
cpu_cores = os.cpu_count() or 4
total_active_bots = max(1, num_workers * 2)

if torch.cuda.is_available() and (bot_device == "cuda" or str(bot_device).startswith("cuda")):
    torch_threads = 1
else:
    torch_threads = max(1, cpu_cores // total_active_bots)
```

As variáveis de ambiente de baixo nível do runtime C++ são configuradas diretamente no ambiente de execução do processo filho:
```python
bot_env["OMP_NUM_THREADS"] = str(torch_threads)
bot_env["MKL_NUM_THREADS"] = str(torch_threads)
bot_env["TORCH_NUM_THREADS"] = str(torch_threads)
```
E no `bot_client.py`:
```python
torch.set_num_threads(torch_threads)
```

---

## 3. Supervisor de *Liveness* por Atividade Real (`process_supervisor.py`)

Em vez de depender de cronômetros cegos de relógio de parede que abortavam partidas ativas de forma indiscriminada, o supervisor monitora a integridade de cada sala individualmente.

### Algoritmo de Verificação de Atividade
A função `wait_for_processes()` monitora:
1. **Atividade Individual:** Acompanha o arquivo `logs/{room_id}_match_feed.log`. Qualquer escrita ou incremento no tamanho do arquivo atualiza `last_activity_time[idx] = time.time()`.
2. **Estagnação Isolada:** Se uma sala ficar sem qualquer atividade por mais de 60 segundos consecutivos (`stagnant_timeout=60.0`), apenas os processos dessa sala estagnada são finalizados com `terminate_process_cleanly()`.
3. **Isolamento de Falhas:** Salas ativas continuam operando normalmente até a finalização natural (vitória, derrota ou empate técnico).
4. **Teto de Segurança Global:** O loop geral continua enquanto houver salas progredindo, com um teto de segurança global elástico (`max_overall_timeout = max(timeout, 1800.0)`).

---

## 4. Watchdogs de Runtime no Cliente (`client.py`)

Para evitar que anomalias em modais ou respostas HTTP retenham o fluxo de jogo:

1. **Watchdog de Prioridade Retida (>25s):**
   - Rastreia uma assinatura digital da mesa (`f"{turnNo}_{turnPhase}_{len(playerHand)}_{playerHealth}_{opponentHealth}"`).
   - Se a assinatura permanecer idêntica sob `havePriority == True` por mais de 25 segundos, o bot força o envio de uma ação de escape (`Mode 99`), destravando a rodada.
2. **Normalização In-Place de `turnPhase`:**
   - Arrays associativos retornados pelo Talishar (`{'turnPhase': 'CHOOSEHAND', 'caption': '...'}`) são automaticamente desempacotados para string canônica no dicionário `state`, prevenindo contaminação da rede neural.
3. **Limite de Retentativas de Sideboard no Lobby:**
   - Caso `client.submit_sideboard()` falhe repetidamente por 3 vezes consecutivas (ex: baralho com cartas a menos), o lobby é cancelado graciosamente com log explícito, erradicando o antigo travamento de 300 segundos.

---

## 5. Inferência em Lote Dinâmica Multi-Thread (`ThreadBatchedEvaluator` - ADR-0014)

No auto-treinamento headless (`HeadlessSelfPlayLoop`), múltiplos workers concorrentes simulam partidas simultaneamente via `concurrent.futures.ThreadPoolExecutor`. 

Sem inferência agrupada, cada thread realiza chamadas individuais e fragmentadas ao modelo PyTorch, gerando múltiplos lançamentos de kernel CUDA com overhead de sincronização host-device.

### Arquitetura de Dynamic Batching
O [`ai/mcts/batched_evaluator.py`](file:///home/renan-albino/Documents/fab-talishar-ia/ai/mcts/batched_evaluator.py) resolve isso através de uma fila central assíncrona:
1. **Enfileiramento Thread-Safe:** Cada worker de MCTS envia requisições `(batch_numpy, Future)` para uma fila em memória (`queue.Queue`).
2. **Janela Temporal Adaptativa:** Uma thread dedicada em background agrupa requisições subsequentes até atingir `max_batch_size` (ex: 128) ou o deadline temporal (`batch_timeout_ms = 1.0` a `2.0 ms`).
3. **Forward Pass Conjunto em GPU:** Executa uma única chamada `model(x_tensor)` na GPU utilizando `torch.inference_mode()` e Mixed Precision (`torch.amp.autocast("cuda")`).
4. **Despacho Assíncrono:** As fatias de tensores (políticas, valores e saídas KataGo) são devolvidas diretamente aos `Futures` de cada worker sem bloqueio mútuo.

Pode ser ativado no orquestrador via CLI com a flag `--batched-inference` ou pela variável de ambiente `FAB_BATCHED_INFERENCE=1`.

