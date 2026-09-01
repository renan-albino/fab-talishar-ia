# ⚔️ FaB Talishar AI Engine, Web App & Training Dashboard

Ambiente completo de simulação autônoma em alta velocidade, treinamento de Inteligência Artificial por **Deep Reinforcement Learning (GPU / PyTorch)**, interface gráfica interativa para partidas humano vs bot com **Avaliação Tática Estilo Xadrez (Stockfish / Chess.com)** e dashboard completo com classificação **Elo Rating** e **Telemetria ISMCTS** para Flesh and Blood.

---

## 📋 Índice
1. [Visão Geral da Arquitetura](#-visão-geral-da-arquitetura)
2. [Principais Funcionalidades da Engine](#-principais-funcionalidades-da-engine)
3. [Como Funciona o Preparo Automatizado do Ambiente](#-como-funciona-o-preparo-automatizado-do-ambiente)
4. [Instalação e Execução Rápida (1 Comando)](#-instalação-e-execução-rápida)
5. [Estrutura do Repositório](#-estrutura-do-repositório)
6. [Módulos da Inteligência Artificial (Deep RL & MCTS)](#-módulos-da-inteligência-artificial)
7. [Gerenciamento Central de Baralhos](#-gerenciamento-central-de-baralhos)
8. [Protocolo e APIs do Talishar](#-protocolo-e-apis-do-talishar)
9. [🚀 Roadmap e Próximos Passos](#-roadmap-e-próximos-passos)
10. [💡 Orientações para a Próxima IA](#-orientações-para-a-próxima-ia)

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
│   Talishar-FE (React / Vite)    │     │   Treinador GPU (ai/trainer.py) │
│  - Tracker de Vantagem (Xadrez) │     │  - PyTorch Policy-Value ResNet  │
│  - Lobby & Sideboard Instantâneo│     │  - FP16 Mixed Precision (AMP)   │
│  - Chat com Métricas In-Game    │     │  - Replay Buffer Multithread    │
└────────────────┬────────────────┘     └────────────────┬────────────────┘
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     │
┌────────────────────────────────────▼───────────────────────────────────┐
│                    Bot Client (bot_client.py)                          │
│  - Motor Híbrido: Rede Neural + ISMCTS + GameSimulator + Heurísticas   │
│  - ISMCTS: Information Set MCTS para decisões com mão oculta           │
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
- **Rede Neural `FaBPolicyValueNetwork` (`ai/model.py`)**:
  - Arquitetura com blocos residuais (ResNet) e normalização por camada (`LayerNorm`).
  - Vetor de entrada de 192 dimensões (Vida, Pontos de Ação, Recursos, Contagem de Mão/Arsenal/Pitch/Banish/Descarte, Equipamentos e Fases).
  - Dual-Head: **Policy Head** (distribuição sobre 32 modos de ação) e **Value Head** (estimativa de vitória entre $[-1.0, 1.0]$).
- **Simulador Determinístico (`ai/game_simulator.py`)**:
  - Projeta estados futuros exatos pós-ação (desconto de custos, pitch automático, cálculo de ataque vs bloqueio, dano não bloqueado, *Go Again*, AP e vida).
  - Substitui ruído sintético por avaliações determinísticas nas folhas da árvore MCTS.
- **ISMCTS em Ataque, Defesa e Pitch (`ai/mcts.py` & `ai/policy_engine.py`)**:
  - *Information Set MCTS*: Amostra mundos determinizados preenchendo a mão oculta do adversário com filtro por classe do herói oponente (*Deck-Aware World Sampling* via `fab_cards_db.json`).
  - Avalia a melhor linha defensiva prevenindo *overblocking* e preservando a mão de contra-ataque (*Tempo Pivot*).
- **Cache LRU de Heurísticas (`ai/hero_strategies.py`)**:
  - Memoização de alta velocidade para scores estáticos de cartas em Dorinthea, Bravo, Dash, Katsu e Guardiões.

### 2. ♟️ Avaliação Tática Estilo Xadrez (Stockfish / Chess.com)
- **Barra de Vantagem Dinâmica no Frontend (`ChessAdvantageTracker.tsx`)**:
  - Barra dividida acima do chat calculando probabilidade de vitória em tempo real por função sigmoide baseada em diferencial de vida, vantagem de cartas na mão e arsenal.
  - Badges: `+X.X` (Vantagem Humana), `-X.X` (Vantagem IA), `0.0` (Equilíbrio) e `1-0`/`0-1` ao finalizar.
- **Classificação de Lances no Chat**:
  - `🟢 Brilhante (!!)`: Ataques letais ou sequenciamento de alto impacto (Score $\ge 9.0$).
  - `🎯 Melhor Jogada (!)`: Escolha ótima da busca ISMCTS.
  - `⚡ Excelente`: Starters de cadeia com custo 0 e *Go Again*.
  - `🛡️ Bloqueio Tático`: Defesa calculada sem quebrar a mão ofensiva do turno seguinte.

---

## 🛠️ Como Funciona o Preparo Automatizado do Ambiente

Para permitir que **qualquer pessoa ou IA replique o ambiente em 1 clique em qualquer computador**, o projeto utiliza uma pasta central de templates (`setup_templates/`) e um script de automação (`scripts/prepare_environment.py` / `scripts/prepare_environment.sh`).

### O que o script de preparação faz automaticamente:
1. **Criação de Diretórios:** Garante a existência de `data/`, `logs/` e `decks/` com permissões de I/O (`chmod 777`).
2. **Aplicação de Patches do Backend (`setup_templates/backend/` $\to$ `Talishar/`):**
   - Injeta `AppendGameLog.php` (API de chat em tempo real).
   - Injeta `JoinGame.php` (Handshake do bot e geração de `authKey`).
   - Injeta `CombatDummy.php` (Desativa o auto-pass legado do PHP para ceder prioridade à IA).
   - Injeta `ProcessInput.php` (Tratamento de ações com modo padrão `27`).
3. **Aplicação de Componentes do Frontend (`setup_templates/frontend/` $\to$ `Talishar-FE/`):**
   - Injeta `ChessAdvantageTracker.tsx` e `ChessAdvantageTracker.module.css` no topo do chat.
   - Sincroniza `GameSlice.ts` e `Header.tsx` para suporte a login livre e atalhos de duelo.
4. **Indexação Oficial de Cartas:**
   - Executa `extract_card_db.py` e extrai 10.144 cartas do Talishar para `data/fab_cards_db.json`.
5. **Autoverificação Docker:**
   - Detecta se os containers `talishar-web-server`, `talishar-mysql-server` e `app_redis` estão ativos e sobe-os automaticamente se necessário.
6. **Exportação com 1 Comando (`--export-templates`):**
   - Caso você ou uma nova IA faça modificações no frontend ou backend, basta rodar `./venv/bin/python scripts/prepare_environment.py --export-templates` para salvar as alterações em `setup_templates/`.

---

## 🚀 Instalação e Execução Rápida

### 1. Clonar o Repositório
```bash
git clone git@github.com:renan-albino/fab-talishar-ia.git
cd fab-talishar-ia
```

### 2. Executar o Script de Preparação Unificado
```bash
./scripts/prepare_environment.sh
```
*(Ou execute diretamente via Python: `./venv/bin/python scripts/prepare_environment.py`)*

### 3. Iniciar Todos os Serviços via Script Orquestrador (`./start.sh`)
Para subir o backend Docker e o Dashboard Streamlit automaticamente em segundo plano:
```bash
./start.sh
```

**Opções úteis do `./start.sh`:**
* `./start.sh -v` : Exibe logs detalhados durante a inicialização.
* `./start.sh --status` : Verifica se o backend Docker, Dashboard e processos de bots estão rodando.
* `./start.sh --no-docker` : Inicia apenas o Streamlit Dashboard (se o Docker já estiver ativo).
* `./start.sh --no-dashboard` : Inicia apenas o backend Docker do Talishar.
* `./start.sh --port 8502` : Altera a porta do Streamlit Dashboard.

### 4. Iniciar o Frontend do Talishar (Partidas contra o Bot)
Em outro terminal (ou via botão na aba *"🎮 Jogar no Talishar"* do Dashboard):
```bash
./start_frontend.sh
```
* **Frontend Web:** `http://localhost:3000`
* **Dashboard Streamlit:** `http://localhost:8501`
* **Backend Talishar:** `http://localhost:8080`

### 5. Parar Todos os Serviços (`./stop.sh`)
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

## 📁 Estrutura do Repositório

```text
├── Talishar/                 # Backend PHP / Docker do motor de regras do FaB
├── Talishar-FE/              # Frontend React / Vite com Tracker de Xadrez
├── setup_templates/          # Templates e patches para replicação em outras máquinas
│   ├── backend/              # APIs customizadas (AppendGameLog, JoinGame, CombatDummy...)
│   └── frontend/             # Componentes React (ChessAdvantageTracker, ChatBox...)
├── ai/                       # Módulos de Inteligência Artificial e Deep RL
│   ├── model.py              # Rede Neural PyTorch (Policy-Value Network Dual-Head)
│   ├── game_simulator.py     # Simulador determinístico de transição de regras de FaB
│   ├── mcts.py               # MCTSEngine + ISMCTSEngine com Deck-Aware World Sampling
│   ├── ismcts_logger.py      # Logger JSONL de decisões para telemetria em tempo real
│   ├── trainer.py            # Orquestrador de Treino GPU com Distilação Assimétrica
│   ├── policy_engine.py      # Motor de Decisão Tático com ISMCTS em Ataque, Defesa e Pitch
│   ├── experience_collector.py # Replay Buffer com suporte a distribuições suaves de visitas
│   └── hero_strategies.py    # Estratégias por Herói com Cache LRU de alta performance
├── scripts/
│   ├── analyze_ismcts.py     # Analisador local ISMCTS (--dry-run sem servidor)
│   ├── prepare_environment.sh # Script shell de setup automático
│   ├── prepare_environment.py # Sincronização de templates, permissões e cartas
│   └── sync_talishar_backend.py # Sincronização com containers Docker
├── decks/                    # Diretório central exclusivo de baralhos (JSON)
├── data/
│   ├── fab_cards_db.json     # Banco oficial de 10.144 cartas do Talishar
│   ├── training_stats.json   # Histórico de partidas e ratings Elo
│   └── training_metrics.json # Métricas de evolução e loss da rede neural
├── logs/                     # Logs detalhados de partidas e telemetria ISMCTS
├── bot_client.py             # Agente autônomo com emissão de badges no chat
├── dashboard.py              # Interface visual Streamlit com Telemetria ISMCTS ao vivo
├── frontend_manager.py       # Daemon de conexão automática do bot em novas salas
├── deck_parser.py            # Parser, normalizador e validador estrito de decks
└── stats_manager.py          # Gerenciador de resultados e cálculo de rating Elo
```

---

## 📂 Gerenciamento Central de Baralhos

Todos os baralhos do ecossistema residem exclusivamente em:
```text
/home/renan/fab-talishar-ia/decks/
```
- **Fonte Única da Verdade:** Nenhum baralho é duplicado para pastas internas do Talishar. O backend PHP (`CreateGame.php`, `JoinGame.php`), o Dashboard Streamlit e o `bot_client.py` lêem diretamente deste diretório.
- **Controle pelo Dashboard:** Novos baralhos subidos ou editados pela aba *Gerenciador de Decks* ficam disponíveis instantaneamente para partidas no Frontend e treinos da IA.

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

## 🚀 Roadmap

### ✅ Concluído

| Item | Descrição |
|------|-----------|
| **Dashboard ISMCTS em Tempo Real** | Aba *"🌐 Telemetria ISMCTS"* no Streamlit (`dashboard.py`) com gráficos de confiança por fase, evolução de $V_{\text{root}}$ e histórico de votos |
| **Deck-Aware World Sampling** | Amostragem de mundos determinizados no ISMCTS com filtro de classe via `fab_cards_db.json` para preenchimento realista da mão oculta |
| **Cache LRU de Prior Shaping** | Memoização de avaliações estáticas de cartas em `hero_strategies.py` com `functools.lru_cache`, acelerando a expansão da árvore MCTS |
| **Simulador de Transição (`ai/game_simulator.py`)** | Motor determinístico de transição de estado para FaB (custos, pitch, poder vs bloco, dano não bloqueado, AP, Go Again e vida) integrado à avaliação de folhas no MCTS |
| **ISMCTS em Defesa e Pitch** | `select_defense_blocks()` e `select_best_pitch_card()` utilizam mundos determinizados do ISMCTS para calcular a melhor linha defensiva e preservação de mão (*Tempo Pivot*) |
| **Distilação Assimétrica (MCTS Target)** | Treinamento com Cross-Entropy / KL-Divergence contra a distribuição real de visitas do MCTS ($\pi_{\text{MCTS}}$), acelerando o aprendizado da rede neural |
| **MCTS Pruning v2** | Prior Threshold Pruning (−1.5σ), Progressive Widening (√N), Single-Player Backprop, Batch Leaf Evaluation com Value Head real em 1 forward pass |
| **ISMCTS** | Information Set MCTS: gera mundos determinizados preenchendo a mão oculta do oponente; agrega votos por visit_count entre mundos |
| **Hardware Scan de Latência** | `_probe_inference_latency_ms` mede a latência real do hardware no startup e calibra dinamicamente `SETTINGS.ismcts_worlds` |
| **Análise Local** | `scripts/analyze_ismcts.py --dry-run` verifica todo o fluxo ISMCTS sem servidor Talishar |
| **Logger JSONL** | `ai/ismcts_logger.py` persiste cada decisão em `logs/ismcts_decisions.jsonl` |

### 📋 Pendente

1. **Torneios Suíços Automatizados**: Orquestrador no Dashboard para ligas entre os decks em `decks/`.
2. **Modelagem de Matchups**: Fine-tuning da rede para arquétipos específicos do meta competitivo.

---

## 💡 Orientações para a Próxima IA

> [!NOTE]
> Esta seção orienta IAs e desenvolvedores que forem assumir o projeto.

### Diretrizes de Trabalho e Economia de Contexto:
1. **Respeite o `.geminiignore`:** Nunca leia arquivos de logs brutos (`logs/*.log`), backups de partidas ou checkpoints binários de rede neural (`*.pt`).
2. **Foco Cirúrgico:** Realize edições pontuais no arquivo exato alvo usando substituições de bloco.
3. **Decks em `decks/`:** Nunca crie baralhos dentro das pastas do Talishar; use sempre o diretório central `decks/`.
4. **Sincronização de Templates:** Se alterar componentes no frontend (`Talishar-FE/`) ou backend (`Talishar/`), execute `./venv/bin/python scripts/prepare_environment.py --export-templates` para manter `setup_templates/` atualizado.

### Próximos Passos Recomendados (Baixa Prioridade / Pesquisa):
- **1. Multi-Threading ISMCTS:** Paralelização da avaliação de mundos com `ThreadPoolExecutor` ou `torch.multiprocessing`.
- **2. Incerteza Bayesiana no Pitch:** Dropout no Value Head para calcular a variância do valor esperado antes de gastar recursos de pitch.
- **3. `num_sims` Adaptativo:** Dobrar simulações de MCTS em situações de dano letal (HP $\le 10$).
