# ADR-0014: Zero-Copy State Evaluation, Leaf Memoization e Dynamic Batched Inference

## Status
Aceito (Implementado e Validado)

## Contexto
Durante a auditoria de desempenho e vazão de treinamento do FaB Talishar AI Engine, o perfilamento empírico do loop headless revelou que o gargalo dominante **não era computação em GPU**, mas sim contenção massiva de CPU pelo interpretador Python:
1. **Serialização Recursiva Excessiva:** O ciclo contínuo de conversão entre `ImmutableGameState` e `dict` (`to_dict()`, `_freeze_value()` e `_unfreeze()`) consumia 84% do tempo de execução da CPU, totalizando mais de 204 milhões de chamadas de funções a cada duas partidas (~199.8 ms/decisão MCTS).
2. **Folhas Redundantes em Profundidade 1:** As 25 simulações do MCTS colapsavam nos mesmos 2 a 5 nós-filhos da raiz, recalculando e reavaliando deterministicamente a mesma ação múltiplas vezes por busca.
3. **Contenção de I/O de Disco no Replay Buffer:** A cada término de partida, bots clientes Sim2Real carregavam o buffer mestre inteiro (100k+ amostras) e regravavam o `.npz` compactado em disco de forma síncrona, além de o orquestrador gravar múltiplos checkpoints e recarregar o buffer a cada época, gerando pausas de 3.5 a 4.0 segundos por iteração.
4. **Desalinhamento do Alvo de Política:** No ambiente headless, a ausência da chave `"mode"` nas ações geradas causava compressão degenerada no índice 31 da política durante a gravação de trajetórias.

## Decisão

1. **Extração Zero-Copy em Mapeamentos (`ai/model.py` e `ai/game_simulator.py`):**
   - Refatoramos `extract_state_vector` para operar diretamente sobre qualquer `collections.abc.Mapping` e sequências `(list, tuple)`, tornando a conversão `.to_dict()` desnecessária.
   - Refatoramos `extract_card_meta` para aceitar `Mapping` e adicionamos um cache LRU de 32k entradas indexado por tupla determinística de campos sobrescritos.
   - Eliminamos sincronizações CPU-GPU ocultas (`if all_pad.any():`) na máscara de atenção, vetorizando a operação.

2. **Memoização de Folhas por Ação no MCTS (`ai/mcts/standard_mcts.py`):**
   - Implementamos cache determinístico por `action_id` em `_batch_evaluate_leaves()`. O estado imutável raiz é preparado uma única vez por busca e apenas transições com ações legais únicas são simuladas e passadas pela rede neural, redistribuindo os valores de volta às folhas.

3. **Arquitetura de Spooling Atômico e Checkpoint Assíncrono (Abordagem A):**
   - Removemos as chamadas de salvamento/carregamento síncrono do buffer mestre em `ai/bot_runtime/match_tracker.py`. Os bots clientes passam a emitir exclusivamente arquivos atômicos leves de trajetória em `data/trajectories/traj_*.npz`.
   - O orquestrador ingere essas trajetórias em memória sem I/O bloqueante no loop de treino.
   - `save_metrics(save_checkpoint=False)` passa a gravar atomicamente apenas o arquivo leve `training_metrics.json`.
   - Checkpoints pesados do PyTorch e do Replay Buffer são delegados a uma thread de background assíncrona (`threading.Thread`), executando apenas em intervalos configurados (`save_interval_games`) e no encerramento.

4. **Dynamic Thread-Batched Inference (`ai/mcts/batched_evaluator.py`):**
   - Criamos o `ThreadBatchedEvaluator`, uma fachada thread-safe compatível com a API de modelo (`predict_state`, `predict_states`, `__call__`).
   - Múltiplos workers MCTS concorrentes em threads submetem seus vetores de estado para uma fila compartilhada. Uma thread em background agrupa as requisições em lotes dinâmicos $[N, 832]$ com janela configurável (1.0 a 2.0 ms), dispara um forward pass conjunto na GPU com `torch.inference_mode()` e AMP FP16, e resolve as fatias via `concurrent.futures.Future`.
   - Suporte adicionado via flag `--batched-inference` ou variável de ambiente `FAB_BATCHED_INFERENCE=1`.

5. **Alinhamento do Índice de Política e Vetorização de SumTree:**
   - Atribuímos modos canônicos às ações do `headless_env.py` e unificamos a indexação no `standard_mcts.py`: `dist_idx = min(act_mode, 31) if act_mode < 32 else (act_mode % 32)`.
   - Vetorizamos a descida na `SumTree` (`get_leaves(v_arr)`) em `ai/experience_collector.py` usando máscara booleana dinâmica para suportar árvores com capacidades arbitrárias sem estouro de índices.

## Consequências

- **Positivas:**
  - **Aceleração de 30.5×:** O tempo total para duas partidas completas de headless self-play caiu de **79.70 s para 2.61 s**.
  - **Latência de MCTS reduzida em 15.5×:** De **199.8 ms para 12.9 ms por decisão**.
  - **Redução de 99.3% no churn de CPU:** Chamadas de função Python caíram de 204.5 milhões para 1.31 milhão. O forward pass PyTorch voltou a ser o componente dominante (>73% do tempo), desbloqueando escalabilidade real para GPU.
  - **ReplayBuffer 3.2× mais rápido:** `sample_batch(512)` PER caiu de 5.70 ms para 1.76 ms.
  - **Eliminação de contenção de disco:** Zero pausas de I/O síncronas por época no loop de treinamento.
  - **Robustez Matemática:** Distribuição de política agora consistente entre self-play, treinamento da policy head e ISMCTS.
- **Negativas:**
  - Checkpoints anteriores treinados com o bug de modo 31 tornam-se subótimos e devem ser descartados a favor de novas rodadas de auto-treinamento com a indexação canônica.
