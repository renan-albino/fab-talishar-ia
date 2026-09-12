# CONTEXT.md — FaB Talishar AI Engine

Glossary of domain terms used in this project. AI agents and contributors must use these terms exactly as defined here.

## Domain: Flesh and Blood (FaB)

- **FaB**: Flesh and Blood, the trading card game by Legend Story Studios.
- **Herói (Hero)**: The character card that defines the class and abilities of a player's deck.
- **Arsenal**: A face-down zone where a player can store one card per turn for future use.
- **Pitch**: The act of placing a card from hand into the pitch zone to generate resource points for paying costs. Cards have pitch values of 1 (red), 2 (yellow), or 3 (blue).
- **Go Again**: A keyword that grants an additional action point after an attack resolves.
- **Combat Chain**: The sequence of attack and defense actions in a single engagement.
- **Action Point (AP)**: A resource that allows a player to play action cards or activate abilities.

## Domain: AI Engine

- **ISMCTS (Information Set Monte Carlo Tree Search)**: A variant of MCTS designed for imperfect-information games. It samples determinized worlds by filling the opponent's hidden hand from a class-filtered card pool.
- **World / Determinization**: A single hypothetical complete game state where all hidden information (opponent's hand) has been filled in with plausible cards.
- **Deck-Aware World Sampling**: The process of sampling determinized worlds using `fab_cards_db.json` to filter cards by the opponent's hero class, producing realistic hidden hands.
- **Policy Head**: The neural network output that produces a probability distribution over possible actions.
- **Value Head**: The neural network output that estimates the probability of winning from the current state, in the range [-1.0, 1.0].
- **Prior Shaping**: Using heuristic card evaluations (from `ai/hero_strategies/`) to bias the initial action probabilities in MCTS expansion.
- **Tempo Pivot**: A defensive strategy where the bot preserves cards in hand for a strong counter-attack next turn instead of over-blocking.
- **Overblocking**: Assigning more defense value than necessary to block an attack, wasting cards that could be used offensively.
- **GameSimulator**: The deterministic state-transition engine (`ai/game_simulator.py`) that projects future game states without randomness.
- **Replay Buffer**: Buffer circular (`ai/experience_collector.py`) que armazena experiências (estado, ação, recompensa) para treinamento off-policy da rede neural. Usa escrita atômica via `.tmp.npz`.
- **Batch Leaf Evaluation**: Técnica em `ai/mcts.py` que agrupa múltiplas folhas MCTS em um único forward pass da rede neural, reduzindo latência de O(N) para O(1).
- **Progressive Widening**: Restrição no MCTS que limita filhos expandidos a √N, focando a busca nos ramos mais promissores.
- **Prior Threshold Pruning**: Poda de ações com prior abaixo de −1.5σ da média, eliminando movimentos claramente inferiores durante a expansão MCTS.
- **Distilação Assimétrica (Asymmetric Distillation)**: Treinamento da rede neural usando a distribuição de visitas do MCTS (π_MCTS) como target via Cross-Entropy/KL-Divergence, em vez de vitória/derrota binária.
- **CR 3.1.5**: Regra oficial de Flesh and Blood que proíbe Resource/Gem cards de serem colocadas no Arsenal. Implementada em `ai/hero_strategies/` com score −9999.0.
- **Equipment Learning Engine (`ai/equipment_learning.py`)**: Motor de aprendizado empírico persistente que registra ativações e bloqueios por partida em `EquipmentTracker`, atualizando multiplicadores calibrados em `data/equipment_usage_stats.json` com base em vitórias.
- **Equipment Metadata (`data/equipment_metadata.json`)**: Metadados semânticos de 624 equipamentos extraídos automaticamente do Talishar, definindo bônus numéricos (`power_buff`, `cost_discount`, `grants_resource`, `min_attack_cost`, `req_counters`, `has_go_again`, `creates_token`) sem hardcoding nominal.
- **On-Hit Threat Quantification**: Escala hierárquica de ameaça (Catastrófico [8.5-10.0], Alto [5.0-7.0], Médio [3.5-4.5], Vanilla [0.0]) em `ai/policy_engine.py` para avaliar severidade de efeitos ao acertar.
- **Knapsack Breakpoint Defense**: Resolvedor de subconjunto ótimo em `select_defense_blocks` que combina o mínimo de cartas de mão e armaduras para neutralizar On-Hits ($\sum \text{block} \ge \text{opp\_power}$) poupando a mão para o contra-ataque.
- **Vanilla Armor Pruning**: Regra estrita de conservação que proíbe o bloqueio com armaduras em ataques comuns (ameaça 0.0) quando a vida é saudável ($HP > 12$), reservando-as para neutralizar On-Hits ou perigo letal.
- **Arsenal Threat Protection**: Heurística de proteção em `ai/policy_engine.py` e `bot_client.py` que detecta ataques de destruição/banimento de Arsenal (*Command and Conquer*, *Leave No Witnesses*, *Eradicate*, *Wreck Havoc*) e prioriza defender com `Crown of Providence` para colocar a carta ameaçada no fundo do deck, neutralizando a destruição pelo oponente e comprando uma nova carta.
- **Smart Sinking / Tuck Logic**: Heurística tática de seleção em `bot_client.py` (`_score_choice_candidate`) que inverte a pontuação de utilidade de cartas em janelas de "sink" (como *Crown of Providence* e *Sink Below*) para colocar a pior carta da mão no fundo do deck para ciclar, preservando o Arsenal quando seguro e peças nobres de ataque.
- **Void Equipment Pruning**: Poda estrita em `bot_client.py` que impede que equipamentos de prevenção ou reação (*Boots of Omniward*, *Ward*, *Barrier*, *Prevent*, *Spellvoid*) sejam ativados ou sacrificados no vazio quando não há dano físico ou arcano ativo na cadeia de combate.
- **Flexible Block Conversion**: Mecanismo em `ai/policy_engine.py` que avalia se a mão possui baixa eficiência defensiva (média de bloco $\le 2.0$) e se o plano de turno permite absorver dano (`can_absorb_damage`), evitando queimar 2 ou mais cartas da mão em bloqueios ineficientes quando é vantajoso pivotar ofensivamente.
- **Human ELO Feedback System**: Sistema de telemetria e pontuação ponderada em `stats_manager.py` e `dashboard.py` que identifica partidas de treino contra jogadores humanos, atribuindo peso diferenciado para aprendizado e exibindo métricas dedicadas para pós-análise e pruning de estratégias de heróis.

## Domain: Architecture

- **Bot Client (`bot_client.py`)**: The autonomous agent that connects to the Talishar backend, reads game state, and submits actions.
- **Dashboard (`dashboard.py`)**: The Streamlit web interface for training, analytics, arena combat, and ISMCTS telemetry. Otimizado com tailing dinâmico de logs para carregamento assíncrono e finalização limpa de subprocessos.
- **Setup Templates (`setup_templates/`)**: Patches and custom files that are injected into the cloned Talishar and Talishar-FE repositories to extend their functionality for AI integration. This is the only source of truth for project-specific modifications to the Talishar ecosystem.
- **Decks Directory (`decks/`)**: The single source of truth for all deck JSON files. No deck is ever duplicated into Talishar's internal folders.
- **Chess Advantage Tracker**: The frontend component (`ChessAdvantageTracker.tsx`) that displays a Stockfish/Chess.com-style advantage bar during games.
- **Elo Rating**: The rating system used in `stats_manager.py` to rank bot performance across training matches.
- **Environment Auto-Detection & Sanitizer (`scripts/prepare_environment.py`)**: Rotina de inspeção dinâmica de runtime (WSL2 vs Linux nativo) que atualiza o `AGENTS.md` local com instruções cirúrgicas de execução, prevenindo gasto de tokens de descoberta pelos agentes e garantindo que paths locais/privados nunca vazem para o Git.
- **Pre-Commit Verification & Privacy Guard (`scripts/sync_and_clean.sh`)**: Hook pré-commit que valida sincronização de templates, compilação de produção do frontend Vite (`npx vite build`), sintaxe Python e bloqueia commits que contenham caminhos pessoais de sistema de arquivos.
- **Frontend Ads Proxy / BannerUnit Mock (`setup_templates/frontend/bannerUnit`)**: Mock headless do módulo de anúncios do Talishar-FE para evitar dependências de terceiros e falhas de compilação em builds offline e de CI.

