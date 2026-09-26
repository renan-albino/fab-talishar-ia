# ⚔️ FaB Talishar AI Engine, Web App & Training Dashboard

Ambiente completo de simulação autônoma em alta velocidade, treinamento de Inteligência Artificial por **Deep Reinforcement Learning (GPU / PyTorch)** com **ISMCTS (Information Set MCTS)**, interface gráfica interativa para partidas humano vs bot com **Avaliação Tática Estilo Xadrez (Stockfish / Chess.com)**, perfis de treino dinâmicos (**Modo Equilibrado** e **Modo Turbo Máximo**), automação de releases no GitHub e dashboard com classificação **Elo Rating Compilado** para Flesh and Blood.

---

## 📋 Índice
1. [Visão Geral da Arquitetura](#-visão-geral-da-arquitetura)
2. [Principais Funcionalidades da Engine](#-principais-funcionalidades-da-engine)
3. [Módulos da Inteligência Artificial](#-módulos-da-inteligência-artificial-deep-rl-ismcts--podas-táticas)
4. [Gestão de Estado Essencial e Releases no GitHub](#-gestão-de-estado-essencial-e-releases-no-github-manage_statepy)
5. [Perfis de Treinamento Dinâmico](#-perfis-de-treinamento-dinâmico)
6. [Resumo das Podas Táticas & Regras Oficiais FaB (CR)](#-resumo-das-podas-táticas--regras-oficiais-fab-cr) — *(Detalhado em [docs/tactical_rules.md](docs/tactical_rules.md))*
7. [Como Funciona o Preparo Automatizado do Ambiente](#-como-funciona-o-preparo-automatizado-do-ambiente)
8. [Instalação e Execução Rápida](#-instalação-e-execução-rápida)
9. [Estrutura do Repositório](#-estrutura-do-repositório)
10. [Gerenciamento Central de Baralhos & Leaderboard Compilado](#-gerenciamento-central-de-baralhos--leaderboard-compilado)
11. [Protocolo e APIs do Talishar](#-protocolo-e-apis-do-talishar)
12. [CI & Testes Automatizados no GitHub Actions (Node 24)](#-ci--testes-automatizados-no-github-actions-node-24)
13. [Roadmap e Próximos Passos](#-roadmap-e-próximos-passos)
14. [Orientações para a Próxima IA](#-orientações-para-a-próxima-ia)

---

## 🌟 Visão Geral da Arquitetura

O ecossistema integra 6 camadas interconectadas em tempo real:

```text
┌────────────────────────────────────────────────────────────────────────┐
│                   Streamlit Dashboard (dashboard.py)                   │
│  [Arena de Combate]  [Treino GPU]  [Analytics Elo]  [Decks]  [ISMCTS] │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
                 ┌───────────────────┴───────────────────┐
                 │                                       │
┌────────────────▼────────────────┐     ┌────────────────▼────────────────┐
│   Talishar-FE (React / Vite)    │     │Treinador GPU (ai/training/orchestrator.py)│
│  - Tracker de Vantagem (Xadrez) │     │  - FaBCardTransformerNetwork (Transformer Encoder)  │
│  - Lobby & Sideboard Instantâneo│     │  - FP16 Mixed Precision (AMP)   │
│  - Chat com Métricas In-Game    │     │  - Replay Buffer Multithread    │
└────────────────┬────────────────┘     └────────────────┬────────────────┘
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│                    Bot Client (bot_client.py)                          │
│  - Motor Híbrido: Rede Neural + ISMCTS + GameSimulator + Heurísticas   │
│  - ISMCTS: Concorrência Híbrida (Threads, Actor-Evaluator, Direct GPU) │
│  - Simulador de Transição Local (ai/game_simulator.py)                 │
│  - Emissão de Badges no Chat (Brilhante, Melhor Lance, Bloqueio)       │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│              Backend Talishar Local (Docker Compose)                   │
│   - talishar-web-server (PHP 8.x / APIs de Jogo / Games / Logs)        │
│   - app_redis (Gerenciamento de Estados de Memória SHMOP)              │
│   - talishar-mysql-server (Persistência e Contas de Usuário)           │
└────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ Principais Funcionalidades da Engine

### 1. 🧠 Motor de Decisão Híbrido (PyTorch + ISMCTS + GameSimulator)
- **Rede Neural `FaBCardTransformerNetwork` (`ai/model.py`)**:
  - Arquitetura Transformer Encoder Dual-Head com Self-Attention para sinergia entre cartas e Cross-Attention contextual com o estado global.
  - Vetor de entrada de 832 dimensões (64 dimensões globais de contexto + 16 slots de cartas × 48 floats semânticos de embeddings densos gerados via NLP/SVD).
  - Dual-Head: **Policy Head** (distribuição sobre 32 modos de ação) e **Value Head** (estimativa de vitória entre $[-1.0, 1.0]$), além de **Cabeças Auxiliares KataGo** (diferencial de vida $\Delta\text{HP}$ e estimativa de dano do turno).
- **Simulador Determinístico (`ai/game_simulator.py`)**:
  - Projeta estados futuros exatos pós-ação (desconto de custos, pitch automático, cálculo de ataque vs bloqueio, dano não bloqueado, *Go Again*, AP e vida).
  - Substitui ruído sintético por avaliações determinísticas nas folhas da árvore MCTS.
- **Concorrência Híbrida no ISMCTS (`ai/mcts/ismcts.py` & ADR-0008)**:
  - *Information Set MCTS*: Amostra mundos determinizados preenchendo a mão oculta do adversário com filtro por classe do herói oponente (*Deck-Aware World Sampling* via `fab_cards_db.json`).
  - **4 Modos de Execução**: `threads` (ThreadPool in-process leve, padrão para auto-treinamento com zero risco de OOM), `multiprocessing` (Actor-Evaluator em CPU com GPU centralizada em batch via Pipes), `direct_gpu` (CUDA nativo para GPUs de alta VRAM) e `sequential`.
  - **Telemetria Preditiva & Lazy Probe**: Cálculo de VRAM em tempo real no dashboard e cache de GPU probe (`@lru_cache`) para evitar sobrecarga no driver.
  - Avalia a melhor linha defensiva prevenindo *overblocking* e preservando a mão de contra-ataque (*Tempo Pivot*).
- **Cache LRU de Heurísticas e Sistema de TurnPlan (`ai/hero_strategies/`)**:
  - Memoização de alta velocidade para scores estáticos de cartas e planos táticos unificados (`TurnPlan`).
- **Caixa Preta de Rastreamento de Erros (Error Dumps)**:
  - Hooks nativos no client para interceptação de `Exception` da IA ou falhas de `errorMessage` do backend (ex: erro de `MULTICHOOSE`).
  - Dumps completos de estado injetados em `logs/exceptions/` registrando *Turn Phase* e *Traceback* exatos para guiar podas de treinamento na rede neural.

### 2. ♟️ Avaliação Tática Estilo Xadrez (Stockfish / Chess.com)
- **Barra de Vantagem Dinâmica no Frontend (`ChessAdvantageTracker.tsx`)**:
  - Barra dividida acima do chat calculando probabilidade de vitória em tempo real por função sigmoide baseada em diferencial de vida, vantagem de cartas na mão e arsenal.
  - Badges: `+X.X` (Vantagem Humana), `-X.X` (Vantagem IA), `0.0` (Equilíbrio) e `1-0`/`0-1` ao finalizar.
- **Classificação de Lances no Chat**:
  - `🟢 Brilhante (!!)`: Ataques letais ou sequenciamento de alto impacto (Score $\ge 9.0$).
  - `🎯 Melhor Jogada (!)`: Escolha ótima da busca ISMCTS.
  - `⚡ Excelente`: Starters de cadeia com custo 0 e *Go Again*.
  - `🛡️ Bloqueio Tático`: Defesa calculada sem quebrar a mão ofensiva do turno seguinte.

### 3. 📦 Gestão de Estado Essencial & Releases Automáticas
- **Pacotes Ultracompactos (`scripts/manage_state.py`)**: Empacotamento inteligente de checkpoints, replay buffer e métricas em pacotes `.tar.gz` de apenas **~6.5 MB** (ao invés de gigabytes de logs ou lixo temporário).
- **Git Hooks Integrados (`pre-commit` e `post-commit`)**:
  - `pre-commit`: Higieniza logs, exporta templates, valida sintaxe Python, testa a compilação do Frontend Vite (`npx vite build`) e audita contra vazamentos de caminhos pessoais (`/home/<user>`).
  - `post-commit`: Detecta quando novos modelos foram treinados e atualiza instantaneamente a release **`checkpoint-latest`** no GitHub usando o `gh release upload --clobber`.
- **Portabilidade Total**: Clone o repositório em uma máquina remota ou VPS, baixe o checkpoint mais recente com `python scripts/manage_state.py --download-release` e continue o treino de onde parou em segundos.

### 4. 🎛️ Perfis Dinâmicos de Treino: Modo Equilibrado vs Turbo Máximo
- **Calibração Inteligente por Hardware**:
  - Detecta VRAM da GPU e threads de CPU para dimensionar automaticamente partidas simultâneas (*workers*), *batch size*, simulações ISMCTS e intervalos de salvamento.
- **⚖️ Modo Equilibrado (~65-75% Carga)**:
  - 3 a 4 partidas simultâneas, batch 256, 25-30 simulações ISMCTS. Mantém a máquina responsiva para trabalho normal, vídeos e navegação.
- **🔥 Modo Turbo Máximo (~90% Carga)**:
  - 5 a 6 partidas simultâneas (10 a 12 bots), batch 512 (~5.0 GB de VRAM na GTX 1660 Super) e 45-50 simulações ISMCTS.
  - **Prioridade de CPU no Linux (`nice 10`)**: Os processos dos bots rodam em prioridade de segundo plano, garantindo que o servidor web Streamlit nunca congele e sempre abra de forma instantânea no navegador.

### 5. ⚔️ Podas Táticas Globais & Conformidade com Regras Oficiais (CR)
- **Conformidade Estrita com as Regras de Flesh and Blood**:
  - **Poda Global de Arsenal (CR 3.1.5)**: Bloqueio universal de recursos/gemas, desvalorização de blocos comuns que perdem defesa no arsenal e priorização de reações de defesa e cartas com *Ambush* / *Down and Dirty*.
  - **Modo Cavar (Digging Mode - CR 4.3.2)**: Quando a mão possui dinamicamente `max(2, intellect - 1)` cartas e todas são recursos, arsenala a melhor ação para permitir compras de cartas novas no *End of Turn* e destravar o bot.
  - **Resolução Legal de Armas & Mãos (CR 2.8.2 e CR 3.0)**: Gestão estrita do limite de 2 mãos no sideboard. Armas de duas mãos (2H) ocupam 2 mãos e nunca são combinadas com escudo/off-hand; armas 1H podem ser combinadas com escudo ou segunda arma 1H.
  - **Detecção de Stalemate / Empate Técnico & Anti-Loop**: Decks esgotados (0 cartas) sem dano por 3 turnos ou partidas que atingem o hard cap de turnos (45 em Blitz, 55 em CC) são imediatamente finalizadas como Empate Oficial, liberando os processos e economizando 100% da CPU.
- **Mapeamento Canônico de 139 Heróis (`HERO_CLASS_REGISTRY`)**: Cobertura de 100% de todos os heróis oficiais de Rathe catalogados no Talishar, associados às suas estratégias especializadas de classe.

---

## 🧠 Módulos da Inteligência Artificial (Deep RL, ISMCTS & Podas Táticas)

A arquitetura de IA em `ai/` é composta por módulos altamente desacoplados e especializados:

| Módulo | Responsabilidade Principal |
| :--- | :--- |
| [`ai/model.py`](ai/model.py) | Rede Neural Transformer Dual-Head (`FaBCardTransformerNetwork`) com Self/Cross-Attention e 832 dimensões de estado. |
| [`ai/policy/`](ai/policy/) & [`ai/policy_engine.py`](ai/policy_engine.py) | Motor de decisão tático unificado modular (`constants`, `card_evaluator`, `attack_pruner`, `defense_pruner`, `pitch_pruner`, `arsenal_pruner`, `engine`). Alterna dinamicamente entre **ISMCTS** (mão oculta) e **MCTS clássico** (informação completa), persiste telemetria direta em `logs/ismcts_decisions.jsonl`, quantifica ameaças On-Hit e resolve defesa por knapsack de breakpoint com fachada raiz retrocompatível. |
| [`ai/mcts/`](ai/mcts/) | Motores `MCTSEngine` e `ISMCTSEngine` decompostos (`node`, `standard_mcts`, `world_generator`, `ismcts`). Amostragem de mundos (*Deck-Aware World Sampling*) e busca paralela multithread com `ThreadPoolExecutor`. |
| [`ai/bot_runtime/`](ai/bot_runtime/) & [`bot_client.py`](bot_client.py) | Runtime modular do bot (`lobby_manager`, `match_tracker`, `choice_handler`, `phase_decider`, `client`). Gerencia ciclo de vida de salas, anti-loop heurístico, tratamento de modais e modulação de fases de combate. |
| [`ai/training/`](ai/training/) | Orquestrador de self-play e treino GPU decomposto (`matchup_engine`, `process_supervisor`, `orchestrator`). Distilação Assimétrica contra $\pi_{\text{MCTS}}$, Prioritized Experience Replay (PER), AMP FP16 e prioridade `nice 10`. |
| [`deck_manager/`](deck_manager/) & [`deck_parser.py`](deck_parser.py) | Pacote desacoplado de baralhos (`slugifier`, `parser`, `validator`, `repository`). Validação estrita de formatos (Blitz/CC), limites de cópias, inventário de equipamentos e persistência atômica. |
| [`stats/`](stats/) & [`stats_manager.py`](stats_manager.py) | Sistema de métricas e ranking (`elo`, `deck_names`, `storage`, `sync`). Cálculo dinâmico de K-factor, consolidação canônica de decks e sincronização com proteção de locks atômicos. |
| [`ui/`](ui/) & [`dashboard.py`](dashboard.py) | Interface web Streamlit modular (`ui/helpers.py` e `ui/tabs/` com 7 abas dedicadas: Play, Arena, Treino, Torneios, Decks, Analytics e ISMCTS). |
| [`ai/equipment_learning.py`](ai/equipment_learning.py) | Motor de aprendizado empírico de equipamentos por experiência pós-partida. Rastreia ativações e bloqueios por herói (`EquipmentTracker`), monitora taxas de vitória e calibra multiplicadores aprendidos dinâmicos $\in [0.5, 2.0]$ em `data/equipment_usage_stats.json`. |
| [`ai/dynamic_rule_tuner.py`](ai/dynamic_rule_tuner.py) | Auto-tuner dinâmico de pesos heurísticos (ataque, bloqueio, pivot e arsenal) ajustados em tempo real com base nas taxas de vitória empíricas de cada herói em `data/hero_rule_multipliers.json`. |
| [`ai/blunder_reviewer.py`](ai/blunder_reviewer.py) | Analisador automático de trajetórias para Prioritized Experience Replay (PER). Identifica e pondera blunders (-3.0), imprecisões e viradas brilhantes (+3.0) para acelerar o treinamento neural. |
| [`ai/hero_strategies/`](ai/hero_strategies/) | Registro canônico de todos os 174 heróis oficiais e estratégias polimórficas por arquétipo/classe. Algoritmos pesados isolados em `knapsack_solver.py`, `turn_planner.py` e `equipment_evaluator.py`, com submódulos dedicados por classe (`guardian`, `warrior`, `brute`, `ninja`, `ranger`, `mechanologist`, `runeblade`, `wizard`, `illusionist`, `assassin`, `merchant`, `teklovossen`). |
| [`ai/game_simulator.py`](ai/game_simulator.py) | Simulador determinístico de regras de FaB para expansão sintética nas folhas da árvore de busca. |
| [`ai/experience_collector.py`](ai/experience_collector.py) | Replay Buffer circular em memória com amostragem priorizada por importância (PER), dense reward shaping e serialização compacta em `.npz`. |
| [`ai/ismcts_logger.py`](ai/ismcts_logger.py) | Logger estruturado thread-safe que persiste diagnósticos de decisão ISMCTS (mundos amostrados, votos, confiança e $V_{root}$) em `logs/ismcts_decisions.jsonl`. |
| [`scripts/extract_equipment_metadata.py`](scripts/extract_equipment_metadata.py) | Extrator de metadados semânticos de 624 equipamentos oficiais do Talishar gerando `data/equipment_metadata.json` (buffs de poder, descontos, contadores, geração de recursos, Go Again e tokens). |
| [`scripts/extract_ability_costs.py`](scripts/extract_ability_costs.py) | Extrator automático de custos de ativação de habilidades e armas a partir dos arquivos PHP do Talishar gerando `data/ability_costs.json`. |

---

## 📦 Gestão de Estado Essencial e Releases no GitHub (`manage_state.py`)

Checkpoints de redes neurais e buffers de treino são binários volumosos (`.pt`, `.npz`). Para manter o repositório Git leve, rápido e com histórico limpo, criamos o utilitário [`scripts/manage_state.py`](scripts/manage_state.py):

### O que o pacote essencial (`fab_ai_checkpoint_bundle.tar.gz`) inclui (~6.5 MB):
* `data/checkpoints/teacher_latest.pt` (Pesos da rede neural de professor)
* `data/model_latest.pt` (Rede neural ativa em produção)
* `data/replay_buffer.npz` (Buffer de experiências de self-play compactado)
* `data/training_metrics.json` (Métricas de loss e épocas concluídas)
* `data/talishar_stats.db` (Histórico de partidas, ELO compilado e leaderboard)
* `data/fab_cards_db.json` (Banco de cartas oficial do Talishar)

### Comandos da CLI:
```bash
# Inspecionar o estado atual do treino local:
python scripts/manage_state.py --info

# Exportar o bundle compactado para transferência:
python scripts/manage_state.py --export

# Importar um bundle recebido em outra máquina:
python scripts/manage_state.py --import fab_ai_checkpoint_bundle.tar.gz

# Publicar o checkpoint atual na aba Releases do GitHub:
python scripts/manage_state.py --publish-release checkpoint-latest

# Baixar o checkpoint mais recente publicado no GitHub:
python scripts/manage_state.py --download-release checkpoint-latest
```

### 🔄 Automação Completa via Hook Git `post-commit`
Ao instalar os hooks via `./scripts/sync_and_clean.sh --install-hook`:
1. Você treina a IA normalmente pelo Dashboard.
2. Ao realizar qualquer `git commit`:
   - O hook `post-commit` roda em segundo plano em menos de 5 segundos.
   - Detecta se o arquivo `teacher_latest.pt` foi alterado por novas partidas.
   - Gera o bundle e faz o upload automático para a release **`checkpoint-latest`** no GitHub via `gh release upload --clobber`.
   - Se o modelo não mudou (ex: commits de código ou documentação), ele ignora instantaneamente (3 ms).

---

## 🎛️ Perfis de Treinamento Dinâmico

Na aba **"⚡ Treinamento com GPU (Deep RL)"** do Dashboard, a IA adapta automaticamente os sliders e parâmetros de treino com base no hardware identificado e no objetivo do usuário:

| Parâmetro | ⚖️ Modo Equilibrado (~65-75% Carga) | 🔥 Modo Turbo Máximo (~90% Carga) | Função e Comportamento |
| :--- | :---: | :---: | :--- |
| **Uso Recomendado** | Durante o dia (Uso Normal do PC) | Noturno / Remoto / Ausente | Permite usar o computador sem engasgos vs Maximização de rendimento. |
| **Partidas Simultâneas** | 3 a 4 partidas (6 a 8 bots) | 5 a 6 partidas (10 a 12 bots) | Ocupa até 90% das threads lógicas da CPU sem travar o scheduler. |
| **Batch Size na GPU** | 256 (~2.0 GB VRAM) | 512 (~5.0 GB VRAM) | Ocupa a memória da GPU para acelerar os passos de gradiente. |
| **Simulações ISMCTS/MCTS** | 25 a 30 sims / jogada | 45 a 50 sims / jogada | Aumenta a profundidade tática das partidas geradas. |
| **Salvamento de Checkpoint** | A cada 20 partidas | A cada 30 partidas | Reduz escrita em disco durante treino intensivo. |
| **Prioridade de CPU** | `nice 10` (Background) | `nice 10` (Background) | O Streamlit Dashboard mantém prioridade máxima e nunca congela. |

---

## ⚔️ Resumo das Podas Táticas & Regras Oficiais FaB (CR)

Para navegar a alta complexidade tática de Flesh and Blood e eliminar a explosão combinatória na busca MCTS/ISMCTS sem violar as regras oficiais (**Comprehensive Rules - CR** e **Tournament Rules - TR**), o motor [`ai/policy/`](ai/policy/) implementa **14 Podas Táticas e Regras Oficiais**.

> [!TIP]
> 📖 **Documentação Técnica Completa**: Consulte o guia aprofundado em [**`docs/tactical_rules.md`**](docs/tactical_rules.md) para a formulação matemática rigorosa, regras oficiais CR/TR, algoritmos de breakpoint (knapsack) e exemplos práticos de cada poda.

| # | Poda Tática / Regra Oficial | Fundamento (CR / Heurística) | Impacto no Motor de IA |
| :-: | :--- | :--- | :--- |
| **1** | **Ataque e Sequenciamento de Cadeia** | CR 2.1.2 & CR 2.3 | Prioriza *starters* de custo 0 e *Go Again*; penaliza quebrar cadeia sem *Go Again*; proíbe flechas na mão. |
| **2** | **Pitch Eficiente (Blue > Yellow > Red)** | CR 1.14 | Hierarquia de pitch (Azul $+4.0$, Vermelha $-3.0$); protege finalizadores reservados do plano ofensivo. |
| **3** | **Bloqueio Inteligente & Tempo Pivot** | CR 2.4 | Anti-overblocking imediato; preserva cartas nobres para contra-ataque; autoriza bloqueio de *Ambush* e *Down and Dirty*. |
| **4** | **Poda Global de Arsenal & Modo Cavar** | CR 3.1.5 & CR 4.3.2 | Proíbe recursos/gemas no Arsenal; desvaloriza blocos comuns; ativa Modo Cavar com $\ge 3$ recursos para destravar compras no EOT. |
| **5** | **Resolução Legal de Armas & Sideboard** | CR 2.8.2 & CR 3.0 | Limite estrito de 2 mãos: armas 2H ocupam 2 mãos (sem escudo); armas 1H aceitam escudo ou 2ª arma; decks com 40 (Blitz) ou 60/65 (CC). |
| **6** | **Stalemate / Empate Técnico & Anti-Loop** | Tournament Rules 5.4 | Declara empate oficial em decks a 0 sem dano (3 turnos) ou hard cap (45 turnos Blitz, 55 CC), liberando 100% da CPU. |
| **7** | **Aprendizado Empírico de Equipamentos** | [`ai/equipment_learning.py`](ai/equipment_learning.py) | Substitui nomes fixos por metadados de 624 equipamentos e calibra multiplicadores aprendidos $\in [0.5, 2.0]$ por vitórias empíricas. |
| **8** | **Ameaça On-Hit & Knapsack Breakpoint** | [`ai/policy/constants.py`](ai/policy/constants.py) | Quantifica ameaça ($0.0$ a $10.0$); resolve subconjunto mínimo de defesa (knapsack); veta queimar armadura em ataques vanilla. |
| **9** | **PER & Auto-Tuning Dinâmico por Herói** | [`ai/blunder_reviewer.py`](ai/blunder_reviewer.py) | Superamostra blunders (peso 3.5) e viradas (peso 2.0); ajusta multiplicadores de ataque/defesa por herói em tempo real. |
| **10** | **Proteção de Arsenal & Crown of Providence** | [`ai/bot_runtime/choice_handler.py`](ai/bot_runtime/choice_handler.py) | Crown entra no bloco sob ameaça a Arsenal; afunda a carta ameaçada do Arsenal ($+150.0$) ou a pior da mão para ciclar. |
| **11** | **Poda de Prevenção e Reação no Vazio** | [`ai/bot_runtime/phase_decider.py`](ai/bot_runtime/phase_decider.py) | Veta Boots of Omniward, Ward e Spellvoid sem dano ativo; restringe Snapdragon Scalers ao turno de ataque sem Go Again. |
| **12** | **Bloqueio Flexível & Conversão de Mão** | [`ai/hero_strategies/turn_planner.py`](ai/hero_strategies/turn_planner.py) | Rejeita blocos ineficientes ($\le 2.0$) para absorver dano e contra-atacar com 4 cartas; modo sobrevivência estrito se $HP \le 6$. |
| **13** | **Treino Híbrido Humano vs Bot & Bônus ELO** | [`ai/bot_runtime/match_tracker.py`](ai/bot_runtime/match_tracker.py) | Isola salas humanas; imune a punching bag; bonifica trajetórias vitoriosas contra humanos com peso 3.0x no buffer. |

---

## 🛠️ Como Funciona o Preparo Automatizado do Ambiente

Para permitir que **qualquer pessoa ou IA replique o ambiente em 1 clique em qualquer computador**, o projeto utiliza uma pasta central de templates (`setup_templates/`) e um script de automação unificado e idempotente (`scripts/prepare_environment.sh` / `scripts/prepare_environment.py`).

### O que o script de preparação faz automaticamente e de forma idempotente:
1. **Garantia dos Repositórios Base (`Talishar` e `Talishar-FE`):** Detecta se as pastas base existem e estão completas (`docker-compose.yml` e `package.json`). Se ausentes (como em um clone limpo), importa do workspace ou clona automaticamente dos repositórios oficiais (`Talishar/Talishar` e `Talishar/Talishar-FE`).
2. **Aplicação de Patches e Arquivos Críticos do Backend (`setup_templates/backend/` $\to$ `Talishar/`):**
   - **`docker-compose.yml` Customizado:** Injeta os pontos de montagem essenciais dos volumes compartilhados (`../decks` $\to$ `/var/www/html/game/decks` e `../data` $\to$ `/var/www/html/game/data`) e configura `MYSQL_ROOT_HOST: "%"` para permitir conexões de rede locais.
   - **`APIs/GetFavoriteDecks.php`:** Integra dinamicamente todos os baralhos presentes no diretório central `decks/` para o menu do frontend web.
   - **`APIs/AppendGameLog.php`:** API de chat e telemetria de lances da IA em tempo real.
   - **`APIs/JoinGame.php` & `APIs/CreateGame.php`:** Handshake do bot e geração de `authKey`.
   - **`AI/CombatDummy.php`:** Desativa o auto-pass legado do PHP para ceder prioridade de decisão ao motor de IA.
   - **`Libraries/HTTPLibraries.php` & `Libraries/PlayerSettings.php`:** Suprime warnings PHP (`ini_set('display_errors', '0')`) para evitar que quebrem as respostas JSON das APIs, além de tratar preferências de sessão de bots locais sem erro.
   - **`ProcessInput.php`:** Tratamento de ações com modo padrão `27`.
3. **Aplicação de Componentes do Frontend (`setup_templates/frontend/` $\to$ `Talishar-FE/`):**
   - Injeta `ChessAdvantageTracker.tsx` e `ChessAdvantageTracker.module.css` no topo do chat.
   - Sincroniza `GameSlice.ts`, `Header.tsx` e rotas para suporte a login livre e atalhos de duelo.
   - **Imunidade a Adblockers (BannerUnit):** Cria o componente `bannerUnit/AdUnit.tsx` e configura o alias `components/ads` $\to$ `bannerUnit` no `vite.config.mts`, impedindo que extensões como uBlock Origin, Firefox Tracking Protection e Brave Shields bloqueiem o carregamento de rotas e scripts React.
4. **Camada de Idempotência do Sistema e Configurações Essenciais (`ensure_system_idempotence`):**
   - Detecta dinamicamente a distribuição hospedeira (Vanilla OS, Fedora, Debian/Ubuntu, WSL2).
   - Se estiver sob Podman rootless, verifica e ativa automaticamente o socket do usuário (`systemctl --user enable --now podman.socket`).
   - Garante que a variável `DOCKER_HOST` aponte para o socket ativo do Podman/Docker.
   - Configura o arquivo de ambiente do Streamlit (`~/.streamlit/config.toml`) para execução limpa (`headless = true`, `gatherUsageStats = false`).
   - Garante a existência de `HostFiles/Redirector.php` (a partir do template), `APIKeys/APIKeys.php` (com credenciais locais de fallback sem 1Password), `HostFiles/GameIDCounter.txt` (iniciado em 1) e `Talishar-FE/.env` (a partir do `.env.template`).
5. **Criação de Diretórios e Permissões:** Garante a existência de `data/`, `logs/`, `decks/` e pastas de escrita do Talishar (`Talishar/Games/`, `Talishar/HostFiles/`, `Talishar/AccountFiles/`, `Talishar/APIKeys/`) com permissões completas de I/O (`chmod 777`), assegurando que o Apache (`www-data`) em containers rootless possa criar salas e salvar partidas sem erro de permissão.
6. **Dependências do Frontend (Node / npm):** Detecta se `Talishar-FE/node_modules` existe; caso não exista, executa `npm install` automaticamente e valida a compilação inicial com `npx vite build`. Se já instalado, avança instantaneamente.
7. **Verificação de Containers Docker:** Inspeciona containers ativos e inicia o compose em segundo plano caso estejam desligados.
8. **Indexação Oficial de Cartas:** Executa `extract_card_db.py` lendo os dicionários de cartas do Talishar para compilar `data/fab_cards_db.json`.
9. **Exportação com 1 Comando (`--export-templates`):** Caso faça alterações em arquivos do frontend ou backend, basta rodar `./venv/bin/python scripts/prepare_environment.py --export-templates` para salvar as modificações em `setup_templates/`.

---

## 🚀 Instalação e Execução Rápida

### 0. Pré-requisitos Mínimos do Sistema

O projeto é projetado para configurar virtualenvs, repositórios, patches e dependências automaticamente. Você só precisa ter instalado no seu sistema hospedeiro (Linux nativo ou WSL2) as ferramentas básicas:

#### 🐧 No Ubuntu / Debian / WSL2:
```bash
sudo apt update && sudo apt install -y git python3 python3-venv python3-pip curl nodejs npm docker.io docker-compose-v2

# (Opcional, mas recomendado) Permitir rodar docker sem sudo:
sudo usermod -aG docker $USER && newgrp docker
```
> *Nota: Recomenda-se Node.js >= 20 para compilação otimizada do frontend Vite.*

#### 🎩 No Fedora / Vanilla OS / RHEL (com Podman):
```bash
sudo dnf install -y git python3 python3-pip nodejs npm podman podman-docker

# Ativar o socket da API Docker via Podman:
systemctl --user enable --now podman.socket
```

---

### 1. Clonar o Repositório
```bash
git clone https://github.com/renan-albino/fab-talishar-ia.git
cd fab-talishar-ia
```

---

### 2. Executar o Script de Preparação Unificado (1 Comando)
Execute o script orquestrador:
```bash
./scripts/prepare_environment.sh
```
*(Ou execute diretamente pelo Python caso já possua virtualenv ativo: `python scripts/prepare_environment.py`)*

Esse script é **totalmente idempotente**: ele pode ser executado quantas vezes você desejar. Ele criará o virtualenv `venv/`, instalará as dependências Python (`torch`, `streamlit`, `numpy`, `psutil`, etc.), clonará `Talishar` e `Talishar-FE`, aplicará todos os templates e patches, configurará os arquivos locais, instalará os pacotes npm, compilará o frontend e indexará a base de dados de cartas.

---

### 3. Validar a Instalação com os Testes Automatizados (Pytest)
Para garantir que todos os módulos de IA, simulador, ISMCTS, podas táticas e estratégias de heróis estão operando perfeitamente:
```bash
./venv/bin/pytest
```
*(Todos os 414 testes automatizados executam e passam em ~3 segundos, isolados nativamente via `pytest.ini`).*

---

### 4. Iniciar Todos os Serviços via Script Orquestrador (`./start.sh`)
Para subir o backend Docker (Talishar PHP, MySQL, Redis) e o Dashboard Streamlit automaticamente em segundo plano:
```bash
./start.sh
```

**Opções úteis do `./start.sh`:**
* `./start.sh -v` : Exibe logs detalhados durante a inicialização.
* `./start.sh --status` : Verifica se o backend Docker, Dashboard e processos de bots estão rodando.
* `./start.sh --update` : Força a verificação e atualização dos repositórios oficiais upstream do Talishar antes de iniciar.
* `./start.sh --no-update` : Pula a checagem remota e inicia instantaneamente offline.
* `./start.sh --no-docker` : Inicia apenas o Streamlit Dashboard (se o Docker já estiver ativo).
* `./start.sh --no-dashboard` : Inicia apenas o backend Docker do Talishar.
* `./start.sh --port 8502` : Altera a porta do Streamlit Dashboard.

---

### 5. Iniciar o Frontend do Talishar (Partidas Humano vs Bot)
Em outro terminal (ou clicando no botão na aba *"🎮 Jogar no Talishar"* do Dashboard):
```bash
./start_frontend.sh
```
* **Frontend Web (Interface do Jogo):** `http://localhost:3000`
* **Dashboard Streamlit (Treino e Métricas):** `http://localhost:8501`
* **Backend Talishar (APIs de Jogo):** `http://localhost:8080`

---

### 6. Parar Todos os Serviços (`./stop.sh`)
Para desligar com segurança todos os containers Docker, processos do Dashboard e bots em execução:
```bash
./stop.sh
```

**Opções úteis do `./stop.sh`:**
* `./stop.sh --all` : Para tudo (Dashboard, Bots e Docker) [Padrão].
* `./stop.sh --dashboard-only` : Finaliza apenas o Dashboard e processos de bots.
* `./stop.sh --docker-only` : Desliga apenas os containers Docker.
* `./stop.sh --clean-logs` : Finaliza os serviços e limpa arquivos de logs temporários.
* `./stop.sh --status` : Consulta o status atual dos processos.

---

### 7. Automação Pré-Commit & Higienização (`./scripts/sync_and_clean.sh`)

Os Git Hooks (`pre-commit` e `post-commit`) são **instalados automaticamente** durante a execução do `./scripts/prepare_environment.sh`.

#### Qual o papel do `sync_and_clean.sh`?
O `sync_and_clean.sh` é o motor de auditoria e higienização invocado automaticamente pelo Git antes de cada `git commit`:
1. **Encerra bots residuais** para não travar arquivos de log.
2. **Higieniza `logs/`**, limpando logs temporários de partidas e testes para manter o repositório leve.
3. **Exporta templates modificados** (`prepare_environment.py --export-templates`), garantindo que alterações no frontend ou backend sejam salvas em `setup_templates/`.
4. **Valida sintaxe Python** de todos os módulos (`py_compile`).
5. **Valida a compilação do Frontend Vite** (`npx vite build`) para garantir que o TypeScript não quebre no CI do GitHub Actions.
6. **Audita privacidade contra vazamentos**, bloqueando commits se caminhos pessoais/absolutos (`/home/<user>`) forem adicionados.
7. **Adiciona automaticamente os templates ao commit** (`git add setup_templates/`).

Você também pode executar o script manualmente a qualquer momento quando quiser limpar o ambiente ou testar a integridade antes de commitar:
```bash
# Executa limpeza de logs, exportação de templates e auditoria manualmente:
./scripts/sync_and_clean.sh

# Apenas verificar integridade sem modificar arquivos:
./scripts/sync_and_clean.sh --check-only
```

---

### 8. Validador Pré-Push & CI Local Incremental (`./scripts/verify_ci.sh`)

O Git Hook `pre-push` é executado automaticamente a cada `git push` para garantir que falhas nunca cheguem ao repositório remoto ou quebrem o GitHub Actions. Ele executa:
1. **Sintaxe Completa Python** (`compileall`).
2. **Dry-Run do ISMCTS** (`scripts/analyze_ismcts.py --dry-run`).
3. **Execução da Suíte de Testes** (`pytest tests/`, 414 testes) [Incremental: pula se apenas documentação foi alterada].
4. **Verificação de Sincronização dos Templates** (`prepare_environment.py --export-templates` & diff).
5. **Build de Produção do Frontend Vite** (`npx vite build`) [Incremental: pula se não houve alterações no frontend].

A validação inteligente detecta os arquivos modificados frente ao upstream remoto, economizando ~18 segundos ao evitar compilações desnecessárias do frontend Vite quando nenhum arquivo de frontend foi tocado.

Você pode rodar a validação manualmente ou forçar todas as etapas:
```bash
# Modo incremental inteligente (padrão)
./scripts/verify_ci.sh

# Modo completo forçado (executa todas as 5 etapas)
./scripts/verify_ci.sh --force
```

---

### 9. Sincronização Upstream do Talishar & Changelog Automatizado

Para manter a compatibilidade quando os repositórios oficiais do Talishar (Backend PHP e Frontend React) recebem novas cartas, correções de regras ou mudanças de UI:
```bash
# Verifica se há novidades no upstream oficial (retorna código 0 se houver, 1 se não):
./venv/bin/python scripts/prepare_environment.py --check-upstream

# Atualiza os repositórios, reaplica os patches da IA, reindexa o banco de cartas e registra o changelog:
./venv/bin/python scripts/prepare_environment.py --update-upstream
```
Toda transição de versão é registrada automaticamente com os hashes de commit (`from_commit` ➔ `to_commit`), contagem de novos commits, diffs e arquivos principais alterados no documento [**`docs/talishar_upstream_changelog.md`**](docs/talishar_upstream_changelog.md).

---

### 10. Busca Rápida no Repositório & Anti-Grep Cego (`scripts/fast_search.py`)

Para evitar travamento de processos e estouro de buffer causados por buscas recursivas cegas na raiz (`grep -r .`) sobre diretórios gigantescos (`node_modules/`, `venv/`, `Talishar/Games/`, `build/`, `logs/`, `data/`):
- **1ª Escolha (Instantâneo):** `git grep -n "termo"` (pesquisa apenas arquivos versionados).
- **2ª Escolha (Com poda de pastas pesadas):** `./venv/bin/python scripts/fast_search.py "termo" [pasta]` (ignora automaticamente pastas pesadas e arquivos binários).
- **3ª Escolha (Direcionado):** `grep -rn "termo" ai/ tests/ scripts/ deck_manager/ stats/ ui/`.

---

## 📁 Estrutura do Repositório

```text
├── Talishar/                 # Backend PHP / Docker do motor de regras do FaB
├── Talishar-FE/              # Frontend React / Vite com Tracker de Xadrez
├── setup_templates/          # Templates e patches para replicação em outras máquinas
│   ├── backend/              # APIs customizadas (AppendGameLog, JoinGame, CombatDummy...)
│   └── frontend/             # Componentes React (ChessAdvantageTracker, ChatBox...)
├── docs/                     # Documentação técnica, ADRs e Roadmap
│   ├── ROADMAP.md            # Planejamento estratégico e expansão de cobertura
│   ├── tactical_rules.md     # Detalhamento técnico das 13 Podas Táticas & Regras FaB (CR)
│   ├── adr/                  # Architecture Decision Records formais (ADR-0001 a ADR-0008)
│   └── agents/               # Guias para agentes (domain.md, issue-tracker.md)
├── ai/                       # Módulos de Inteligência Artificial e Deep RL
│   ├── bot_runtime/          # Runtime modular do bot (lobby, tracker, choices, fases, client)
│   ├── policy/               # Poda tática, avaliação de cartas e motor de decisão unificado
│   ├── mcts/                 # MCTS e ISMCTS paralelo multithread (ThreadPoolExecutor)
│   ├── training/             # Orquestrador de treino GPU FP16 e supervisor de processos
│   ├── hero_strategies/      # 174 heróis oficiais, knapsack solver, turn planner e classes
│   │   ├── base.py           # Classe base HeroStrategy e interfaces polimórficas
│   │   ├── knapsack_solver.py # Solver DP 0-1 knapsack de turno e custo de oportunidade
│   │   ├── turn_planner.py   # Dataclass TurnPlan, planos de ataque/defesa e survival trigger
│   │   ├── equipment_evaluator.py # Avaliação semântica orientada a dados de equipamentos
│   │   └── *.py              # Módulos dedicados por classe (guardian, warrior, mechanologist...)
│   ├── model.py              # Rede Neural PyTorch (Policy-Value Network Dual-Head)
│   ├── game_simulator.py     # Simulador determinístico de transição de regras de FaB
│   ├── ismcts_logger.py      # Logger JSONL de decisões para telemetria em tempo real
│   ├── equipment_learning.py # Rastreamento empírico e calibração de multiplicadores de equipamentos
│   ├── dynamic_rule_tuner.py # Auto-tuning dinâmico de pesos heurísticos por herói baseado em vitórias
│   ├── blunder_reviewer.py   # Avaliador de blunders, imprecisões e viradas brilhantes para PER
│   ├── experience_collector.py # Replay Buffer PER com amostragem priorizada e reward shaping
│   ├── policy_engine.py      # Fachada retrocompatível para ai.policy
│   └── trainer.py            # Fachada retrocompatível para ai.training
├── deck_manager/             # Gerenciamento de baralhos (slugifier, parser, validator, repo)
├── stats/                    # Métricas de ELO, agregação de nomes, armazenamento e sync
├── ui/                       # Interface gráfica desacoplada (ui.helpers e ui.tabs com 7 abas)
│   ├── helpers.py            # Cache Streamlit, tail assíncrono de logs e telemetria de GPU
│   └── tabs/                 # Módulos individuais de cada aba do Dashboard
├── scripts/
│   ├── sync_and_clean.sh     # Automação de limpeza, exportação de templates e pré-commit
│   ├── extract_equipment_metadata.py # Extração semântica de equipamentos
│   ├── extract_ability_costs.py # Extração de custos de ativação
│   ├── analyze_ismcts.py     # Analisador local ISMCTS (--dry-run sem servidor)
│   ├── prepare_environment.sh # Script shell de setup automático
│   ├── prepare_environment.py # Sincronização de templates, permissões e cartas
│   ├── manage_state.py       # Gestão de checkpoints compactos e releases no GitHub
│   └── sync_talishar_backend.py # Sincronização com containers Docker
├── tests/                    # Suíte completa de 414 testes automatizados (pytest)
│   ├── test_all_hero_strategies.py # Cobertura de todas as estratégias de heróis
│   ├── test_hero_hierarchical_strategies.py # Testes de planos de turno e decisões
│   ├── test_equipment_defense_and_abilities.py # Testes de ativação e bloqueio
│   ├── test_unpayable_and_ismcts.py # Testes de ISMCTS paralelo e unpayable handling
│   ├── test_teklovossen_and_deck_normalization.py # Testes de regras de Teklovossen e decks
│   ├── test_deck_parser.py   # Testes do deck_manager e validação de formatos
│   ├── test_stats_manager.py # Testes de ELO dinâmico e persistência atômica
│   ├── test_training_modules.py # Testes de orquestração de treino GPU
│   ├── test_ui_modules.py    # Testes unitários das abas do Dashboard
│   └── ...                   # Testes de modelo, simulador, sideboard e anti-loop
├── decks/                    # Diretório central exclusivo de baralhos (JSON)
├── data/
│   ├── equipment_metadata.json # Metadados semânticos de 624 equipamentos (custos, buffs, tokens)
│   ├── ability_costs.json    # Custos dinâmicos de habilidades e armas extraídos do Talishar
│   ├── fab_cards_db.json     # Banco oficial de 5.132 cartas do Talishar
│   ├── training_stats.json   # Histórico de partidas e Leaderboard ELO compilado
│   └── training_metrics.json # Métricas de evolução, loss e épocas da rede neural
├── logs/                     # Logs detalhados de partidas e telemetria ISMCTS
├── pytest.ini                # Configuração do pytest isolando pastas do Talishar e venv
├── extract_card_db.py        # Extração de banco de dados de cartas
├── bot_client.py             # Fachada retrocompatível para ai.bot_runtime.client
├── dashboard.py              # Orquestrador enxuto da interface Streamlit
├── frontend_manager.py       # Daemon de conexão automática do bot em novas salas
├── deck_parser.py            # Fachada retrocompatível para deck_manager
└── stats_manager.py          # Fachada retrocompatível para stats
```

---

## 📂 Gerenciamento Central de Baralhos & Leaderboard Compilado

### 1. Diretório Central de Decks (`decks/`):
Todos os baralhos do ecossistema residem exclusivamente na raiz do projeto:
```text
<raiz-do-projeto>/decks/
```
- **Fonte Única da Verdade:** Nenhum baralho é duplicado para pastas internas do Talishar. O backend PHP (`CreateGame.php`, `JoinGame.php`), o Dashboard Streamlit e o `bot_client.py` lêem diretamente deste diretório.
- **Importador com Limpeza Automática:** O formulário de importação de decks no Dashboard possui controle de versão de estado (`import_form_id`) que limpa automaticamente os campos de texto após validação e salvamento bem-sucedidos, além de contar com o botão manual `🧹 Limpar`.

### 2. Leaderboard de ELO Compilado (`stats_manager.py`):
- **Normalização Canônica:** A função `canonicalize_deck_name()` unifica variações de caixa alta/baixa e slugs (ex: `marlinn` e `Marlinn` ➔ `Marlinn`; `dash_io` e `Dash IO` ➔ `Dash IO`).
- **Fusão Automática de Estatísticas:** Se decks duplicados existirem no histórico, o sistema consolida as entradas somando partidas, vitórias, derrotas e calculando o rating ELO médio ponderado pelo volume de jogos disputados.

---

## ⚙️ Protocolo e APIs do Talishar

* **`POST /game/APIs/CreateGame.php`**: Cria a sala de jogo e gera chaves de autenticação.
* **`POST /game/APIs/JoinGame.php`**: Conecta o Jogador 2 (Humano ou Bot) à sala.
* **`POST /game/APIs/ChooseFirstPlayer.php`**: Define a ordem de início (`action: "Go First"`).
* **`POST /game/APIs/SubmitSideboard.php`**: Submete a seleção de herói, equipamentos e baralho.
* **`POST /game/APIs/AppendGameLog.php`**: Injeta avaliações táticas e badges diretamente no chat da partida.
* **`GET /game/GetNextTurn.php`**: Consulta o estado atual da mesa (Polling de alta velocidade).
* **`GET /game/ProcessInput.php`**: Executa uma ação de jogo com tratamento de modo padrão (`27`).

---

## 🧪 CI & Testes Automatizados no GitHub Actions (Node 24)

O repositório conta com pipeline de Integração Contínua automatizado em `.github/workflows/ci.yml`:
* **Node 24 Moderno:** Forçado via `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: 'true'`, eliminando avisos de depreciação.
* **Validação Sintática Total:** `python -m py_compile *.py ai/*.py scripts/*.py tests/*.py`.
* **Simulação Dry-Run de ISMCTS:** Executa `python scripts/analyze_ismcts.py --dry-run` sem necessidade de servidor externo.
* **Suíte de Testes Unitários de Regras:** Executa `pytest tests/ -v --cov=ai/` para validar a poda estrita de Arsenal (CR 3.1.5) e prioridades de Ranger.
* **Verificação de Templates:** Garante que `setup_templates/` está 100% sincronizado com modificações locais do frontend e backend.
* **Compilação do Frontend Vite:** Validação completa de compilação do React no Node 22 com `npx vite build`.

---

## 🚀 Roadmap e Próximos Passos

### ✅ Concluído

| Item | Descrição |
|------|-----------|
| **Fundamentos Competitivos de FaB** | Implementação das heurísticas estratégicas do meta de alto nível: OpponentTracker de ritmo de jogo, escalonamento dinâmico de risco ($c_{\text{puct}}$ via $V_{\text{root}}$), cálculo de conversão ofensiva/defensiva de mão, timing de cadeia de combate, preservação de Blade Break e bônus multi-ciclo de *Deck Damage* |
| **Remoção de Hardcodes & Generalização Dinâmica** | Eliminação de amarras nominais e listas estáticas em favor de detecção por metadados de cartas (`fab_cards_db.json`), histórico em SQLite para sideboard (`get_average_match_length`) e mundos determinizados agnósticos à classe |
| **Fronteira de Dados com Pydantic** | Transição completa da API para objetos Python estritamente tipados via `pydantic` em `ai/common/schemas.py`, eliminando a necessidade de conversores defensivos no runtime contra payloads nulos/caóticos do Talishar |
| **Imutabilidade O(1) no Simulador MCTS** | Motor de combate transita estados via `ImmutableGameState` com operações `.replace()` ao invés de clones de dicionário na memória, garantindo integridade de árvore e aceleração massiva da simulação |
| **Self-Play Headless & Hardware Probe** | Treinamento da IA agora usa ambiente Gymnasium-like local, ignorando tráfego de rede; o orquestrador analisa hardware (CUDA/CPU) e restringe VRAM ativamente antes das execuções |
| **SQLite3 Transacional Local** | Eliminação completa das gravações atômicas em JSONs (e locks baseados em `fcntl`). Toda a telemetria, histórico de duelo e ELO de Heróis agora é gravada e consultada rapidamente do arquivo `talishar_stats.db` |
| **Documentação Técnica de Podas Táticas & CR** | Criação de [`docs/tactical_rules.md`](docs/tactical_rules.md) com detalhamento matemático e regras oficiais (CR/TR) das 14 podas táticas e heurísticas da engine |
| **Gestão de Checkpoints & GitHub Releases** | Utilitário `scripts/manage_state.py` com empacotamento compacto (~6.5 MB), comandos CLI de export/import e Git Hook `post-commit` automático que publica novos modelos treinados na release `checkpoint-latest` do GitHub |
| **Perfis Dinâmicos de Treino (Equilibrado / Turbo)** | Calibração por hardware (GTX 1660 Super, CPUs, GPUs high-end), botão Turbo Máximo (~90% carga) com escalonamento de CPU em segundo plano (`nice 10`) garantindo estabilidade absoluta da interface web |
| **Poda de Arsenal (CR 3.1.5) & RangerStrategy** | Poda estrita que proíbe recursos (`type: R`) e gemas no Arsenal (evitando travar o slot), priorização de flechas (`Arrow`) como condição essencial de ataque no Ranger e capacidade de passar sem arsenalar para preservar recursos |
| **Leaderboard ELO Compilado & Sem Duplicatas** | `stats_manager.py` com normalização canônica (`canonicalize_deck_name`) e consolidação automática de entradas duplicadas (ex: `Marlinn` + `marlinn`, `Dash IO` + `dash_io`) com ELO ponderado |
| **Propagação Dinâmica de Parâmetros MCTS** | Repasse em tempo real de `--mcts-sims` e `--device` do Dashboard para os subprocessos de self-play em `trainer.py` e `bot_client.py` |
| **Limpeza Confiável no Editor de Decks** | Versionamento de formulário (`import_form_id`) e botão `🧹 Limpar` que higienizam os campos de importação do Dashboard após validação de novos decks |
| **Pipeline CI com Node 24 & Testes Unitários** | GitHub Actions atualizado para Node 24 nativo, com compilação do frontend Vite e testes unitários de regras em `tests/test_arsenal_pruning.py` |
| **Resiliência e Autocura de Ambiente** | `prepare_environment.sh` e `prepare_environment.py` com detecção automática de Docker Compose v1/v2, resolução dinâmica de containers e autocura de extensões C |
| **Correção de Ações & Backend Engine** | Remoção de lock indefinido em `ProcessInput.php`; tratamento e validação de respostas HTTP |
| **Telemetria de Partidas e Identificação Clara** | Turn-by-turn logs com identificação legível de decks, heróis e HP exato por jogador, banner de destaque para o vencedor e gravação de resumo |
| **Extração Canônica de Heróis & Decks** | `deck_parser.py` com extração automática do Herói oficial via `fab_cards_db.json`, proteção contra `KeyError: 'hero'` no Dashboard |
| **Dashboard ISMCTS em Tempo Real** | Aba *"🌐 Telemetria ISMCTS"* no Streamlit (`dashboard.py`) com gráficos de confiança por fase, evolução de $V_{\text{root}}$ e histórico de votos |
| **Deck-Aware World Sampling** | Amostragem de mundos determinizados no ISMCTS com filtro de classe via `fab_cards_db.json` para preenchimento realista da mão oculta |
| **Simulador de Transição (`ai/game_simulator.py`)** | Motor determinístico de transição de estado para FaB (custos, pitch, poder vs bloco, dano não bloqueado, AP, Go Again e vida) integrado ao MCTS |
| **Distilação Assimétrica (MCTS Target)** | Treinamento com Cross-Entropy / KL-Divergence contra a distribuição real de visitas do MCTS ($\pi_{\text{MCTS}}$), acelerando o aprendizado da rede neural |
| **Camada de Idempotência & Vanilla OS / Podman** | Detecção dinâmica de distros imutáveis (Vanilla OS 3 / Apx / Fedora), auto-ativação do socket de usuário Podman, garantia de diretórios com permissão `775` para `www-data` no host e configuração `headless` do Streamlit |
| **Imunidade a Adblockers (BannerUnit)** | Criação do módulo `bannerUnit` e alias Vite substituindo importações dinâmicas `/components/ads/`, eliminando quebras causadas por extensões de bloqueio de anúncios (uBlock Origin, Brave Shields) |
| **Decomposição Modular Completa (9 Monólitos)** | Refatoração estrutural completa de 9 arquivos monolíticos (`dashboard.py`, `bot_client.py`, `policy_engine.py`, `mcts.py`, `trainer.py`, `deck_parser.py`, `stats_manager.py`, `hero_strategies/base.py`, `hero_strategies/other_classes.py`) em pacotes limpos e coesos (`ai/bot_runtime/`, `ai/policy/`, `ai/mcts/`, `ai/training/`, `deck_manager/`, `stats/`, `ui/tabs/`), preservando 100% de retrocompatibilidade em todas as fachadas raízes |
| **Paralelização Multi-Thread do ISMCTS** | Busca paralela e thread-safe em mundos determinizados com `concurrent.futures.ThreadPoolExecutor` em `ai/mcts/ismcts.py`, acelerando a amostragem e a agregação ponderada de votos na árvore de decisão |
| **Suíte de Testes Expandida (427 Testes Automatizados)** | Ampliação da cobertura de testes para 414 testes (`pytest`) cobrindo todas as classes de heróis, estratégias hierárquicas, poda de arsenal (CR 3.1.5), persistência atômica, normalização de decks e orquestração de GPU, com isolamento via `pytest.ini` |
| **Torneios Suíços Automatizados** | Implementado em `stats/tournament_manager.py` com ligas entre decks e persistência no `stats/`. |
| **Aprendizado Acelerado com Humanos & Assimilação Pós-Partida** | Ponderação amplificada (4.0x a 7.0x no PER) para partidas contra humanos, assimilação imediata pós-jogo em background via `ai/training/assimilation.py` com atualização segura do modelo (`model_latest.pt`) e alertas visuais com bloqueio protetor no Dashboard (`tab_play.py`) |
| **Recomendação Inteligente de Heróis (Analytics & ELO)** | Motor de diagnóstico tático em `stats/recommendations.py` que analisa a telemetria e sugere os heróis prioritários para treino humano (gargalos de ELO < 45% WR, alta incerteza amostral e matchups inéditos contra humanos) integrado nas abas 1 e 6 do Dashboard |
| **Sincronização de Telemetria do Replay Buffer** | Leitura direta com cache leve (TTL=3s) das amostras físicas do `replay_buffer.npz` no Dashboard (`ui/helpers.py`, `ui/tabs/tab_training.py`) e sincronização imediata de `samples_collected` pós-assimilação |
| **Notificações Visuais de Assimilação em Tempo Real** | Ampulheta animada CSS e aviso de status na aba de Duelo Humano (`tab_play.py`) com injeção de logs estilizados no chat do Talishar durante a assimilação |

### 📋 Pendente
 
1. **Suporte a Torneios Suíços Completos**: Integração de chaves suíças automatizadas com persistência no `stats/`.
2. **Modelagem de Matchups**: Fine-tuning da rede para arquétipos específicos do meta competitivo.

---

## 💡 Orientações para a Próxima IA

> [!NOTE]
> Esta seção orienta IAs e desenvolvedores que forem assumir o projeto.

### Diretrizes de Trabalho e Economia de Contexto:
1. **Respeite o `.geminiignore` e `.gitignore`:** Nunca leia arquivos de logs brutos (`logs/*.log`), backups de partidas ou checkpoints binários de rede neural (`*.pt`). O estado essencial é gerenciado por `scripts/manage_state.py`.
2. **Foco Cirúrgico:** Realize edições pontuais no arquivo exato alvo usando substituições de bloco.
3. **Decks em `decks/`:** Nunca crie baralhos dentro das pastas do Talishar; use sempre o diretório central `decks/`.
4. **Sincronização de Templates:** Se alterar componentes no frontend (`Talishar-FE/`) ou backend (`Talishar/`), execute `./venv/bin/python scripts/prepare_environment.py --export-templates` para manter `setup_templates/` atualizado.

### Próximos Passos Recomendados (Baixa Prioridade / Pesquisa):
- **1. Incerteza Bayesiana no Pitch:** Dropout no Value Head para calcular a variância do valor esperado antes de gastar recursos de pitch.
- **2. `num_sims` Adaptativo:** Dobrar simulações de MCTS em situações de dano letal (HP $\le 10$).
- **3. Suporte a Torneios Suíços Completos:** Integração de chaves suíças automatizadas com persistência no `stats/`.

