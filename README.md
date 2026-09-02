# ⚔️ FaB Talishar AI Engine, Web App & Training Dashboard

Ambiente completo de simulação autônoma em alta velocidade, treinamento de Inteligência Artificial por **Deep Reinforcement Learning (GPU / PyTorch)** com **ISMCTS (Information Set MCTS)**, interface gráfica interativa para partidas humano vs bot com **Avaliação Tática Estilo Xadrez (Stockfish / Chess.com)**, perfis de treino dinâmicos (**Modo Equilibrado** e **Modo Turbo Máximo**), automação de releases no GitHub e dashboard com classificação **Elo Rating Compilado** para Flesh and Blood.

---

## 📋 Índice
1. [Visão Geral da Arquitetura](#-visão-geral-da-arquitetura)
2. [Principais Funcionalidades da Engine](#-principais-funcionalidades-da-engine)
3. [Módulos da Inteligência Artificial (Deep RL, ISMCTS & Podas Táticas)](#-módulos-da-inteligência-artificial)
4. [Gestão de Estado Essencial e Releases no GitHub (`manage_state.py`)](#-gestão-de-estado-essencial-e-releases-no-github)
5. [Perfis de Treinamento Dinâmico (Modo Equilibrado vs Modo Turbo Máximo)](#-perfis-de-treinamento-dinâmico)
6. [Resumo das Podas Táticas & Regras Oficiais FaB (CR)](#-resumo-das-podas-táticas--regras-oficiais-fab)
7. [Como Funciona o Preparo Automatizado do Ambiente](#-como-funciona-o-preparo-automatizado-do-ambiente)
8. [Instalação e Execução Rápida (1 Comando)](#-instalação-e-execução-rápida)
9. [Estrutura do Repositório](#-estrutura-do-repositório)
10. [Gerenciamento Central de Baralhos & Leaderboard Compilado](#-gerenciamento-central-de-baralhos)
11. [Protocolo e APIs do Talishar](#-protocolo-e-apis-do-talishar)
12. [CI & Testes Automatizados no GitHub Actions (Node 24)](#-ci--testes-automatizados)
13. [🚀 Roadmap e Próximos Passos](#-roadmap-e-próximos-passos)
14. [💡 Orientações para a Próxima IA](#-orientações-para-a-próxima-ia)

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

### 3. 📦 Gestão de Estado Essencial & Releases Automáticas
- **Pacotes Ultracompactos (`scripts/manage_state.py`)**: Empacotamento inteligente de checkpoints, replay buffer e métricas em pacotes `.tar.gz` de apenas **~6.5 MB** (ao invés de gigabytes de logs ou lixo temporário).
- **Git Hooks Integrados (`pre-commit` e `post-commit`)**:
  - `pre-commit`: Higieniza logs, exporta templates e valida sintaxe.
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
  - **Modo Cavar (Digging Mode - CR 4.3.2)**: Quando a mão possui $\ge 3$ cartas e todas são recursos, arsenala a melhor ação para permitir compras de cartas novas no *End of Turn* e destravar o bot.
  - **Resolução Legal de Armas & Mãos (CR 2.8.2 e CR 3.0)**: Gestão estrita do limite de 2 mãos no sideboard. Armas de duas mãos (2H) ocupam 2 mãos e nunca são combinadas com escudo/off-hand; armas 1H podem ser combinadas com escudo ou segunda arma 1H.
  - **Detecção de Stalemate / Empate Técnico & Anti-Loop**: Decks esgotados (0 cartas) sem dano por 3 turnos ou partidas que atingem o hard cap de turnos (45 em Blitz, 55 em CC) são imediatamente finalizadas como Empate Oficial, liberando os processos e economizando 100% da CPU.
- **Mapeamento Canônico de 139 Heróis (`HERO_CLASS_REGISTRY`)**: Cobertura de 100% de todos os heróis oficiais de Rathe catalogados no Talishar, associados às suas estratégias especializadas de classe.

---

## 🧠 Módulos da Inteligência Artificial (Deep RL, ISMCTS & Podas Táticas)

A arquitetura de IA em `ai/` é composta por módulos altamente desacoplados e especializados:

| Módulo | Responsabilidade Principal |
| :--- | :--- |
| [`ai/model.py`](ai/model.py) | Rede Neural ResNet Dual-Head (`FaBPolicyValueNetwork`) com LayerNorm e 192 entradas de estado. |
| [`ai/policy_engine.py`](ai/policy_engine.py) | Motor de decisão tática unificado. Alterna dinamicamente entre **ISMCTS** (quando o oponente tem cartas na mão) e **MCTS clássico** (quando a informação é completa), persiste telemetria direta em `logs/ismcts_decisions.jsonl` em todas as fases, e coordena podas táticas de ataque, pitch, bloqueio e arsenal. |
| [`ai/mcts.py`](ai/mcts.py) | Motores `MCTSEngine` e `ISMCTSEngine`. Amostragem de mundos (*Deck-Aware World Sampling* com leitura dinâmica de `opponentHand`) e agregação ponderada de votos. |
| [`ai/hero_strategies.py`](ai/hero_strategies.py) | Registro canônico de todos os 139 heróis oficiais e estratégias polimórficas por arquétipo/classe: `GuardianStrategy`, `JarlStrategy`, `BruteStrategy`, `WarriorStrategy`, `NinjaStrategy`, `RangerStrategy`, `MechanologistStrategy`, `RunebladeStrategy`, `WizardStrategy`, `IllusionistStrategy`, `AssassinStrategy` e `MerchantStrategy`. |
| [`ai/game_simulator.py`](ai/game_simulator.py) | Simulador determinístico de regras de FaB para expansão sintética nas folhas da árvore de busca. |
| [`ai/trainer.py`](ai/trainer.py) | Orquestrador de self-play e treino com Distilação Assimétrica contra $\pi_{\text{MCTS}}$, AMP FP16 e prioridade `nice 10`. |
| [`ai/experience_collector.py`](ai/experience_collector.py) | Replay Buffer circular em memória com serialização compacta em `.npz`. |
| [`ai/ismcts_logger.py`](ai/ismcts_logger.py) | Logger estruturado thread-safe que persiste diagnósticos de decisão ISMCTS (mundos amostrados, votos, confiança e $V_{root}$) em `logs/ismcts_decisions.jsonl`. |

---

## 📦 Gestão de Estado Essencial e Releases no GitHub (`manage_state.py`)

Checkpoints de redes neurais e buffers de treino são binários volumosos (`.pt`, `.npz`). Para manter o repositório Git leve, rápido e com histórico limpo, criamos o utilitário [`scripts/manage_state.py`](scripts/manage_state.py):

### O que o pacote essencial (`fab_ai_checkpoint_bundle.tar.gz`) inclui (~6.5 MB):
* `data/checkpoints/teacher_latest.pt` (Pesos da rede neural de professor)
* `data/model_latest.pt` (Rede neural ativa em produção)
* `data/replay_buffer.npz` (Buffer de experiências de self-play compactado)
* `data/training_metrics.json` (Métricas de loss e épocas concluídas)
* `data/training_stats.json` (Histórico de partidas, ELO compilado e leaderboard)
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

Para navegar a complexidade de regras do Flesh and Blood e garantir jogadas de nível competitivo sem sobrecarregar a árvore MCTS, o motor [`ai/policy_engine.py`](ai/policy_engine.py) opera com uma arquitetura de podas táticas e heurísticas estruturada em 6 pilares:

### 1. Poda de Ataque e Sequenciamento de Cadeia (Chain Sequencing)
* **Go Again & Starter Priority**: O motor prioriza ataques com *Go Again* e cartas de custo 0 como iniciadores (*starters*) quando o jogador possui Action Points limitados, evitando quebrar a cadeia de combate prematuramente.
* **Timing de Armas**: Armas de alto impacto e custo pesado de pitch (ex: martelos de Guardião) são pontuadas como finalizadores de turno ou pivots defensivos quando não há ataques jogáveis na mão; armas ágeis de 1 mão (Ninja Kodachis, adagas de Assassino) são ativadas no início da cadeia para aplicar pressão constante ou consumir recursos flutuantes residuais.

### 2. Poda de Pitch Eficiente (Pitch Hierarchy: Blue > Yellow > Red)
* **Eficiência de Recursos**: Cartas azuis (pitch 3) recebem prioridade máxima de pitch para pagar custos pesados com o menor consumo possível de cartas da mão.
* **Preservação de Linhas Ofensivas**: Ataques vermelhos de alto poder ofensivo sofrem penalidade severa de pitch (`score < 0`), garantindo que o bot não queime prematuramente suas principais cartas de dano na geração de recursos.

### 3. Poda de Bloqueio Inteligente & Preservação de Pivot
* **Anti-Overblocking**: O motor encerra imediatamente os bloqueios adicionais assim que o valor total de defesa acumulado iguala ou supera o ataque do oponente, preservando as cartas restantes da mão para o contra-ataque.
* **Preservação de Mão para Pivot**: Quando a vida do herói está em patamar seguro ($\ge 10$ HP), arquétipos pesados (Guardiões e Brutes) evitam bloquear com cartas chave para absorver pequenos danos e devolver turnos esmagadores de 6+ poder (*Oaken Old*, *Boulder Drop*, *Pack Hunt*).
* **Exceções Defensivas no Arsenal**: Detecção nativa de cartas com a keyword `Ambush` e a carta *Down and Dirty*, que possuem permissão de bloquear diretamente a partir da zona de Arsenal (*Down and Dirty* ganha bônus de $+1\{d\}$ se bloqueia do Arsenal).

### 4. Poda Global de Arsenal & Modo Cavar (CR 3.1.5 & CR 4.3.2)
* **Rejeição Universal de Recursos e Gemas (CR 3.1.5)**: Como cartas no Arsenal não podem ser dadas pitch e só saem dele se forem jogadas ou defenderem, cartas do tipo Recurso (`type: R`) ou Gemas (`subtype: Gem` como *Heart of Fyendal*, *Eye of Ophidia*, *Riches of Trōpal-Dhani*) são estritamente proibidas no Arsenal (`score: -9999.0`), prevenindo o travamento permanente do slot.
* **Desvalorização de Bloco Comum**: Cartas de ação comuns com defesa 3 que não possuem *Ambush* nem são reações de defesa perdem a capacidade de defender a partir do Arsenal. O motor penaliza essas cartas para que fiquem na mão como bloqueadores.
* **Priorização de Reações de Defesa e Ambush**: Cartas que extraem valor máximo ao serem acionadas do Arsenal (*Sink Below*, *Fate Foreseen*, cartas com *Ambush* e flechas de Ranger) recebem alta prioridade de carregamento.
* **Modo Cavar (Digging Mode - CR 4.3.2)**: Se a mão contiver $\ge 3$ cartas e todas forem recursos ou cartas não ofensivas, o bot seleciona a melhor ação para colocar no Arsenal, permitindo ao herói comprar novas cartas até seu intelecto máximo no *End of Turn* e destravar o fluxo do baralho.

### 5. Resolução Legal de Armas & Sideboard (CR 2.8.2 e CR 3.0)
* **Capacidade Estrita de 2 Mãos**:
  * **Armas de 2 Mãos (2H)** (*Sledge of Anvilheim*, *Anothos*, *Dawnblade*, *Raydn*): Ocupam ambas as mãos. É terminantemente proibido equipar qualquer escudo, off-hand ou segunda arma junto com elas.
  * **Armas de 1 Mão (1H)** (*Titan's Fist*, *Harmonized Kodachi*, *Cintari Saber*, *Spider's Bite*): Ocupam 1 mão, podendo ser combinadas com outra arma 1H ou com um escudo/off-hand.
  * **Off-Hands e Escudos** (*Stalagmite, Bastion of Isenloft*, *Rampart of the Ram's Head*): Ocupam 1 mão e só podem ser equipados com armas 1H ou desarmado.
* **Sideboard Dinâmico**: Ao processar listas de baralhos que possuem armas mistas (como Jarl com *Titan's Fist*, *Stalagmite* e *Sledge of Anvilheim*), o bot equipa o par legal ideal (`Titan's Fist` + `Stalagmite`) e envia o martelo 2H e o escudo reserva para o inventário, mantendo 100% de conformidade de regras.

### 6. Detecção de Stalemate / Empate Técnico & Anti-Loop (Tournament Rules)
* **Fadiga Estagnada (Decks em 0)**: Se ambos os baralhos esgotam e por 3 turnos seguidos a vida de nenhum jogador se altera (ou se mãos e arsenais estão 100% vazios), a IA detecta o impasse de ações e declara **Empate Técnico por Fadiga / Stalemate**.
* **Hard Cap Anti-Loop por Formato**: Limite estrito de 45 turnos (Blitz) e 55 turnos (CC) para interromper partidas em loop contínuo de prioridade.
* **Finalização Limpa**: Registra `winner_id = 0` ("Empate") no [`stats_manager.py`](stats_manager.py) (distribuindo $S=0.5$ no ELO e incrementando o total de empates), encerra os processos dos bots instantaneamente e libera 100% da CPU.

---

## 🛠️ Como Funciona o Preparo Automatizado do Ambiente

Para permitir que **qualquer pessoa ou IA replique o ambiente em 1 clique em qualquer computador**, o projeto utiliza uma pasta central de templates (`setup_templates/`) e um script de automação (`scripts/prepare_environment.py` / `scripts/prepare_environment.sh`).

### O que o script de preparação faz automaticamente:
1. **Verificação e Auto-reparo de Dependências Python:** Configura o `venv` e verifica a integridade de extensões binárias em C (como NumPy e PyTorch), reinstalando-as automaticamente se arquivos `.so` estiverem corrompidos.
2. **Garantia dos Repositórios Base (`Talishar` e `Talishar-FE`):** Detecta se as pastas base existem e estão completas (`docker-compose.yml` e `package.json`). Se ausentes, importa do diretório de workspace ou clona automaticamente dos repositórios oficiais do GitHub (`Talishar/Talishar` e `Talishar/Talishar-FE`).
3. **Criação de Diretórios:** Garante a existência de `data/`, `logs/` e `decks/` com permissões de I/O (`chmod 777`).
4. **Aplicação de Patches do Backend (`setup_templates/backend/` $\to$ `Talishar/`):**
   - Injeta `AppendGameLog.php` (API de chat em tempo real).
   - Injeta `JoinGame.php` (Handshake do bot e geração de `authKey`).
   - Injeta `CombatDummy.php` (Desativa o auto-pass legado do PHP para ceder prioridade à IA).
   - Injeta `ProcessInput.php` (Tratamento de ações com modo padrão `27`).
5. **Aplicação de Componentes do Frontend (`setup_templates/frontend/` $\to$ `Talishar-FE/`):**
   - Injeta `ChessAdvantageTracker.tsx` e `ChessAdvantageTracker.module.css` no topo do chat.
   - Sincroniza `GameSlice.ts` e `Header.tsx` para suporte a login livre e atalhos de duelo.
6. **Autoverificação e Compatibilidade Docker:**
   - Suporte transparente e automático a **Docker Compose v1 (`docker-compose`)** e **Docker Compose v2 (`docker compose`)**.
   - Resolução dinâmica de nomes de containers (`talishar_web-server_1` ou `talishar-web-server-1`).
7. **Indexação Oficial de Cartas:**
   - Executa `extract_card_db.py` conectando dinamicamente ao container web ativo e extrai 10.144 cartas do Talishar para `data/fab_cards_db.json`.
8. **Compilação e Validação do Frontend:**
   - Instala pacotes via `npm` (somente após confirmar a integridade de `package.json`) e valida a compilação com `npx vite build`.
9. **Exportação com 1 Comando (`--export-templates`):**
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

### 6. Automação Pré-Commit & Sincronização (`./scripts/sync_and_clean.sh`)
Para nunca se preocupar em esquecer de sincronizar templates com `setup_templates/` ou limpar logs de partidas antes de enviar commits para o repositório:
```bash
# Executa limpeza de logs, exportação de templates e teste de sintaxe:
./scripts/sync_and_clean.sh

# (Recomendado) Instalar como Git Pre-Commit Hook automático (1 vez só):
./scripts/sync_and_clean.sh --install-hook
```
> **O que o hook pré-commit faz:** A cada `git commit`, encerra processos de teste, higieniza `logs/`, exporta automaticamente alterações em `Talishar/` e `Talishar-FE/` para `setup_templates/`, adiciona-os ao commit (`git add setup_templates/`) e valida a sintaxe do código Python.

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
│   ├── sync_and_clean.sh     # Automação de limpeza, exportação de templates e pré-commit
│   ├── analyze_ismcts.py     # Analisador local ISMCTS (--dry-run sem servidor)
│   ├── prepare_environment.sh # Script shell de setup automático
│   ├── prepare_environment.py # Sincronização de templates, permissões e cartas
│   ├── manage_state.py       # Gestão de checkpoints compactos e releases no GitHub
│   └── sync_talishar_backend.py # Sincronização com containers Docker
├── tests/                    # Suíte de testes unitários automatizados
│   └── test_arsenal_pruning.py # Testes de poda de Arsenal (CR 3.1.5) e Ranger
├── decks/                    # Diretório central exclusivo de baralhos (JSON)
├── data/
│   ├── fab_cards_db.json     # Banco oficial de 10.144 cartas do Talishar
│   ├── training_stats.json   # Histórico de partidas e Leaderboard ELO compilado
│   └── training_metrics.json # Métricas de evolução, loss e épocas da rede neural
├── logs/                     # Logs detalhados de partidas e telemetria ISMCTS
├── bot_client.py             # Agente autônomo com emissão de badges no chat
├── dashboard.py              # Interface visual Streamlit com Telemetria ISMCTS ao vivo
├── frontend_manager.py       # Daemon de conexão automática do bot em novas salas
├── deck_parser.py            # Parser, normalizador e validador estrito de decks
└── stats_manager.py          # Gerenciador de resultados, fusão de duplicatas e rating Elo
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
* **Suíte de Testes Unitários de Regras:** Executa `python tests/test_arsenal_pruning.py` para validar a poda estrita de Arsenal (CR 3.1.5) e prioridades de Ranger.
* **Verificação de Templates:** Garante que `setup_templates/` está 100% sincronizado com modificações locais do frontend e backend.
* **Compilação do Frontend Vite:** Validação completa de compilação do React no Node 22 com `npx vite build`.

---

## 🚀 Roadmap

### ✅ Concluído

| Item | Descrição |
|------|-----------|
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

### 📋 Pendente

1. **Torneios Suíços Automatizados**: Orquestrador no Dashboard para ligas entre os decks em `decks/`.
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
- **1. Multi-Threading ISMCTS:** Paralelização da avaliação de mundos com `ThreadPoolExecutor` ou `torch.multiprocessing`.
- **2. Incerteza Bayesiana no Pitch:** Dropout no Value Head para calcular a variância do valor esperado antes de gastar recursos de pitch.
- **3. `num_sims` Adaptativo:** Dobrar simulações de MCTS em situações de dano letal (HP $\le 10$).
