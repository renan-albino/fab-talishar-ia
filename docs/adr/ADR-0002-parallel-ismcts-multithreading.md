# ADR-0002: Paralelização do ISMCTS através de Determinizações Independentes de Mundos com ThreadPoolExecutor

- **Status**: Accepted
- **Date**: 2026-09-16
- **Deciders**: Equipe FaB Talishar AI (Architecture Review)

## Context

Flesh and Blood é um jogo de cartas colecionáveis com informação imperfeita: a mão e o arsenal oculto do oponente não são visíveis pelo bot durante a tomada de decisão. 

Para resolver o problema da incerteza sem cair no viés de onisciência, o motor adota o algoritmo **ISMCTS (Information Set Monte Carlo Tree Search)** (Cowling, Powley & Whitehouse, 2012). O algoritmo funciona gerando $W$ mundos determinizados plausíveis (amostrando cartas coerentes com a classe e herói do oponente a partir de `data/fab_cards_db.json`) e simulando buscas MCTS em cada mundo.

No entanto, a execução puramente sequencial de $W$ mundos com dezenas de simulações e inferências de rede neural (Forward pass PyTorch) gerava uma latência média de 3 a 5 segundos por jogada. Esse tempo de resposta degradava a experiência contra humanos no Talishar, arriscava timeouts de conexão HTTP e tornava o treinamento autônomo por Self-Play extremamente lento.

## Decision

Paralelizar a avaliação de mundos determinizados utilizando `concurrent.futures.ThreadPoolExecutor` em `ai/mcts/ismcts.py`:

1. **Determinizações Independentes**:
   - Para cada chamada de `search_ismcts`, são gerados $W$ mundos hipotéticos via `world_generator.generate_worlds(state, num_worlds)`.
   - O número de mundos $W$ é dimensionado no startup através de benchmark de hardware (`_probe_inference_latency_ms`) armazenado em `SETTINGS.ismcts_worlds` (padrão 4 mundos).

2. **Execução Concorrente com ThreadPoolExecutor**:
   - Cada mundo determinizado é submetido como uma tarefa independente ao pool de threads:
     ```python
     with concurrent.futures.ThreadPoolExecutor(max_workers=min(4, actual_worlds)) as executor:
         futures = [executor.submit(_evaluate_world, w) for w in worlds]
         for fut in concurrent.futures.as_completed(futures):
             world_children = fut.result()
             # Agregação de contadores de visitas
     ```
   - Em cada thread, o motor executa `_run_world_mcts`, aplicando MCTS padrão com *Batch Leaf Evaluation* (agrupando folhas de expansão em lote para minimizar o custo do forward pass na rede neural).

3. **Agregação Assíncrona de Votos**:
   - À medida que cada futuro é completado (`as_completed`), os nós filhos da raiz do mundo correspondente têm seus contadores de visitas (`child.visit_count`) somados no dicionário consolidado `vote_counts` para cada índice de ação legal.
   - A distribuição final da política $\pi_{\text{MCTS}}$ é calculada normalizando a contagem agregada de visitas:
     $$\pi(a_i) = \frac{\text{votes}[a_i]}{\sum_j \text{votes}[a_j]}$$
   - A ação com o maior volume global de visitas é selecionada como `best_idx`, com um nível de confiança dado por $\frac{\text{max\_votes}}{\text{total\_votes}}$.

4. **Thread-Safety e PyTorch**:
   - O modelo `FaBPolicyValueNetwork` opera exclusivamente em modo de avaliação (`model.eval()`) durante a inferência do ISMCTS, garantindo operações de leitura thread-safe nos tensores de pesos tanto em CPU quanto em GPU CUDA.

## Consequences

### Positive
- **Redução Acentuada de Latência**: O tempo de inferência e busca ISMCTS cai de ~3.5s para ~600ms em processadores modernos de 4+ núcleos, atendendo com folga a janela de resposta do Talishar.
- **Isolamento de Erros e Strategy Fusion**: Cada mundo possui sua própria subárvore e estado determinizado fechado, eliminando o clássico problema de fusão de estratégias (*strategy fusion*) inerente a árvores ISMCTS compartilhadas.
- **Escalabilidade Adaptativa**: Ambientes com mais threads de CPU ou GPUs velozes podem aumentar `SETTINGS.ismcts_worlds` proporcionalmente sem custo linear em latência de resposta.
- **Riqueza de Telemetria**: A agregação consolidada produz métricas detalhadas de concordância entre mundos, exportadas em `ismcts_log` para análise no dashboard.

### Negative / Trade-offs
- **Consumo de Memória de CPU**: Criar $W$ árvores e cópias parciais de estado de jogo simultâneas consome temporariamente mais memória RAM durante a fase de busca (geralmente ~50MB adicionais).
- **GIL do Python (CPython)**: Embora as chamadas tensoriais PyTorch liberem o GIL em C++/CUDA, operações pesadas de cópia de dicionário em Python puro podem sofrer alguma contenção entre threads se $W > 8$.

## Alternatives Considered

- **ProcessPoolExecutor (Multiprocessing)**: Rejeitado devido ao elevado custo de serialização (pickle/unpickle) dos tensores PyTorch, dicionários de estado de jogo e instâncias de regras a cada lance.
- **Árvore MCTS Única Global com Virtual Loss**: Rejeitado pois árvores globais em jogos de informação imperfeita sofrem severamente de *strategy fusion* e contenção destrutiva de locks em nós raízes concorrentes.
- **Determinização Sequencial Simples**: Rejeitada pela latência inaceitável para jogo em tempo real.
