# ADR-0010: Alocação Adaptativa de Threads CPU e Supervisão de Liveness por Atividade Real

## Status
**Aceito** (2026-09-27)

## Contexto
Durante o treinamento concorrente com múltiplos workers (ex: 5 workers gerando 10 processos concorrentes de bots no WSL2), observou-se que as salas de jogo frequentemente paravam ou eram encerradas prematuramente no Turno 3 ou 4. A investigação aprofundada revelou duas causas arquiteturais críticas:

1. **Thread Thrashing do PyTorch em CPU:**
   Por padrão, o PyTorch aloca `torch.get_num_threads()` igual ao número de núcleos lógicos disponíveis (6 no WSL2). Com 10 processos concorrentes executando inferência Transformer de `batch_size = 1` no ISMCTS, eram geradas 60 threads disputando 6 núcleos físicos. O overhead de troca de contexto (*context switching*), invalidação de cache L1/L2 e *spinlocks* do OpenMP degradavam a latência por decisão de 0.1s para mais de 10s.
2. **Timeouts Cegos de Relógio de Parede:**
   O orquestrador e supervisor de processos utilizavam um prazo fixo estático (`deadline = time.time() + timeout`). Quando a disputa de CPU prolongava a duração de um lote, o supervisor executava `_kill_active_processes()`, assassinando partidas saudáveis e ativas no meio do combate.
3. **Inconsistência de Tipos em `turnPhase`:**
   O backend PHP do Talishar enviava `turnPhase` como array associativo em fases específicas (`CHOOSEHAND`, `M`), contaminando o modelo neural e simulador com strings malformadas (`"{'turnPhase': 'M'..."`).
4. **Loop Cego no Sideboard do Lobby:**
   Falhas de validação de deck entravam em loop infinito de 300 segundos no lobby sem abortar.

## Decisão de Arquitetura

1. **Fórmula de Alocação Adaptativa de Threads CPU:**
   Em vez de fixar valores estáticos ou podar simulações MCTS, cada bot client dimensiona dinamicamente suas threads intra-operação:
   $$\text{Threads por Bot} = \max\left(1, \left\lfloor \frac{\text{Total de Núcleos CPU}}{\text{Total de Bots Concorrentes}} \right\rfloor\right)$$
   - Se CUDA estiver ativo (`device == 'cuda'`), threads de CPU são fixadas em 1 para delegar todo o trabalho às GPUs.
   - Em CPU, as variáveis de ambiente `OMP_NUM_THREADS`, `MKL_NUM_THREADS` e `TORCH_NUM_THREADS` são injetadas no subprocesso, e `torch.set_num_threads()` é chamado antes da instanciação dos modelos.
2. **Supervisão de Liveness Baseada em Progresso Real:**
   - Em `ai/training/process_supervisor.py`, `wait_for_processes()` passa a rastrear a atividade individual de cada sala via `room_ids`.
   - O avanço é verificado pelo crescimento do arquivo de log (`logs/{room_id}_match_feed.log`) ou incremento de turnos.
   - Enquanto as salas estiverem ativas e avançando, o cronômetro estende dinamicamente.
   - **Encerramento Cirúrgico:** Uma sala só é terminada se permanecer estagnada por mais de 60 segundos consecutivos sem nenhuma ação (`stagnant_timeout=60.0`). Apenas a sala travada é finalizada, permitindo que todas as outras salas saudáveis continuem jogando até a conclusão natural.
3. **Normalização In-Place de `turnPhase`:**
   - Logo na entrada de `handle_game_tick(state)` e `decide_and_act(state)` no `client.py`, qualquer `turnPhase` do tipo `dict` é desempacotado:
     `state["turnPhaseCaption"] = tp_raw.get("caption", "")`
     `state["turnPhase"] = str(tp_raw.get("turnPhase", "M"))`
4. **Limite de 3 Retentativas no Lobby Sideboard:**
   - Em `ai/bot_runtime/lobby_manager.py`, se `client.submit_sideboard()` falhar 3 vezes consecutivas, o lobby é abortado com erro explícito.
5. **Watchdog de Prioridade Retida (>25s):**
   - No cliente HTTP, se `havePriority == True` persistir no mesmo estado por mais de 25 segundos, o bot força o envio de uma ação de escape (`mode=99`).

## Consequências

### Positivas
- **Velocidade e Vazão Máxima:** A eliminação do *thread thrashing* permite que 10 bots executem 25 simulações MCTS completas em paralelo com alta velocidade e sem travar a CPU.
- **Partidas Concluídas com Sucesso:** Zero partidas saudáveis mortas prematuramente por timeout de relógio.
- **Portabilidade Transparente:** Em máquinas com 32 ou 64 núcleos de CPU ou GPU dedicada, o sistema escala automaticamente sem necessidade de alteração manual de configurações.
- **Isolamento de Falhas:** Erros pontuais em uma sala não contaminam nem interrompem as outras salas do lote.

### Neutras / Compensações
- Requer monitoramento de I/O de disco para arquivos de log durante o loop de supervisão (custo desprezível de leitura de `os.path.getsize` a cada 0.3s).
