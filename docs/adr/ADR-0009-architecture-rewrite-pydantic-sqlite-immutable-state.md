# ADR-0009: Refatoração Arquitetural — Pydantic, Estados Imutáveis, Headless Self-Play e SQLite

- **Status**: Accepted (Deprecia o [ADR-0003](ADR-0003-concurrent-atomic-persistence-file-locks.md))
- **Data**: 2026-09-24
- **Autores**: FaB Talishar AI Team

## Contexto e Problema

Com a maturação do FaB Talishar AI Engine, a base de código começou a apresentar severos gargalos de performance e fragilidades de resiliência devido a escolhas arquiteturais precoces:
1. **Dados Não-Tipados na Borda**: O backend PHP do Talishar enviava valores como `""`, `"NaN"` e `null` aleatoriamente. Isso forçava o espalhamento de funções de coerção defensiva (`safe_int`, `safe_dict`) por todo o MCTS e módulos de decisão.
2. **Mutabilidade e Cópias de Dicionários**: O `GameSimulator` realizava transições de estado simuladas usando dicionários mutáveis de Python e `_shallow_clone_state`, vazando referências (como a lista de cartas da mão) entre simulações e causando gargalos no clone (Deepcopy).
3. **Self-Play Ineficiente via Rede**: O treinamento (Reinforcement Learning) via `orchestrator.py` subia clientes bot via `subprocess.Popen` que jogavam através de endpoints HTTP (mesmo rodando localmente). Isso sofria de timeouts, zumbis no Unix e gargalos severos de IO de disco para gravar trajetórias JSON.
4. **Race Conditions e Travamentos com `atomic_io`**: O uso de `fcntl` (lock de arquivos) para gravar arquivos JSON como `stats.json` ou `ratings.json` era frágil e incompatível em alguns ambientes WSL2, levando à corrupção e lentidão. O ADR-0003 tentou resolver isso, mas as limitações estruturais permaneceram.

## Decisão Arquitetural

Resolvemos refatorar massivamente o núcleo do motor de IA através das 4 fases a seguir:

### 1. Fronteira de Dados Tipada (Pydantic)
- Adoção da biblioteca **Pydantic** (`ai/common/schemas.py`). 
- A API agora converte e higieniza automaticamente a carga de entrada em modelos estritos (`GameState`, `Card`, `Player`). As validações defensivas manuais (`ai/common/converters.py`) foram completamente eliminadas, garantindo que a lógica central opere unicamente com tipos limpos (`int`, `bool`, `list`).

### 2. Imutabilidade no Simulador do MCTS (ImmutableGameState)
- Transição da representação do estado para estruturas baseadas em instâncias imutáveis recursivas (`Mapping`, `frozenset`, `tuple`).
- O `GameSimulator` (`ai/game_simulator.py`) agora retorna novas instâncias geradas através do método `replace()` (similar a `dataclasses.replace`). O tempo de clone do estado foi drasticamente otimizado, de $O(N)$ para operações nominais em $O(1)$, prevenindo o vazamento letal de informações entre mundos do ISMCTS.

### 3. Self-Play Headless e Profiling de GPU
- O *Self-Play* para RL local contorna completamente as restrições da rede e o PHP (`ai/training/headless_env.py`). Partidas de treino fluem usando diretamente o `GameSimulator` na RAM (`in-memory`).
- O `orchestrator.py` executa validações (Pre-flight Hardware Probe) que monitoram o $V_{RAM}$ e *Streaming Multiprocessors* ativos, interrompendo simulações exageradas antes que induzam travamentos na GPU (OOM).

### 4. Transição para Banco de Dados Nativo (SQLite)
- Abandono definitivo do `ai/atomic_io.py` e revogação do **ADR-0003**.
- Roteamento e consolidação de ranking ELO de heróis, histórico de partidas e tuning heurístico para um banco relacional transacional (SQLite3) estruturado em `data/talishar_stats.db`.

## Consequências

- **Impacto Positivo:** A suíte passou de 100% de confiabilidade; redução substancial no custo computacional de rollout MCTS; treino de RL ordens de magnitude mais veloz sem contenção TCP/IP; eliminação total de conflitos de concorrência em transações do dashboard e stats.
- **Impacto Negativo (Mitigado):** Acúmulo leve de complexidade em testes baseados em mocks, que agora requerem simulação na memória do SQLite (`sqlite3.connect(":memory:")`) em vez de arquivos textos simples de fixtures. Adicionou `pydantic` como dependência externa.
