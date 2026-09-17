# CONTEXT.md — FaB Talishar AI Engine

Glossário oficial de termos de domínio utilizados no projeto FaB Talishar AI. Agentes de IA, desenvolvedores e revisores devem utilizar estes termos com precisão estrita.

> [!IMPORTANT]
> **Convenção de Modelagem de Domínio (`_Avoid_`)**:
> Cada termo canônico possui uma lista de sinônimos informais ou termos imprecisos explicitamente proibidos sob a cláusula `- _Avoid_:`. Agentes de IA **NUNCA** devem utilizar os termos da lista `_Avoid_` em mensagens, documentações, testes, nomes de variáveis ou PRs, prevenindo a dispersão semântica (Term Drift).

---

## Domain: Flesh and Blood (FaB)

- **FaB**: Flesh and Blood, o trading card game competitivo desenhado pela Legend Story Studios.
  - _Avoid_: FABTCG informal, Jogo de cartas genérico, Card game sem sigla.
- **Herói (Hero)**: A carta de personagem central que define a classe, vida inicial, intelecto e conjunto de habilidades ativadas ou passivas de um jogador.
  - _Avoid_: Avatar, Campeão, Personagem principal, Monstro.
- **Arsenal**: Zona face-down onde o jogador pode armazenar exatamente uma carta ao final do seu turno de ação para jogá-la em turnos futuros. Cartas no Arsenal não podem ser colocadas na zona de pitch para pagar custos de recursos (CR 3.1.5).
  - _Avoid_: Zona de reserva, Mão secundária, Depósito, Backup zone.
- **Pitch**: Ato de colocar uma carta da mão na zona de pitch para gerar pontos de recurso para pagamento de custos. Possui valores de pitch 1 (vermelho), 2 (amarelo) ou 3 (azul).
  - _Avoid_: Descarte para mana, Geração de energia, Custo pago no cemitério.
- **Go Again**: Palavra-chave oficial de FaB que concede um ponto de ação (AP) adicional ao jogador imediatamente após a resolução bem-sucedida de um ataque ou ação.
  - _Avoid_: Ação extra, Ataque duplo, Segundo turno, Ação em cadeia.
- **Combat Chain (Cadeia de Combate)**: Estrutura contínua de resolução composta por elos de ataque (*chain links*), passos de defesa e passos de reação antes do fechamento formal da cadeia.
  - _Avoid_: Fila de combate, Sequência de batalha, Pilha de ataques.
- **Action Point (AP)**: Recurso fundamental consumido para jogar cartas do tipo Ação ou ativar habilidades de equipamentos/herói que exijam uma ação.
  - _Avoid_: Ponto de mana, Ponto de energia, Ponto de movimento, Turno adicional.
- **Intelecto (Intellect)**: Valor numérico impresso na carta do herói que define o tamanho máximo de cartas na mão até o qual o jogador compra durante o End of Turn Step (CR 4.3.2). Padrão 4 para heróis adultos e 3 para heróis Brute como Rhinar e Kayo.
  - _Avoid_: Tamanho da mão, Capacidade de compra, Hand Limit, Max Cards.
- **Reaction Step**: Etapa formal de combate que sucede o Defence Step, compreendendo o Attack Reaction Step (CR 7.5a) e o Defence Reaction Step (CR 7.5b), onde jogadores alternam prioridade para utilizar cartas de reação e cartas do tipo Instant antes da resolução de dano.
  - _Avoid_: Janela de resposta livre, Fast play step, Quick Action Phase, Janela de contra-ataque.
- **Prevenção Arcana (Arcane Prevention - Ward / Spellvoid / AB)**: Mecanismos e palavras-chave oficiais de FaB destinados a mitigar dano arcano:
  - **Arcane Barrier (AB)**: Efeito de equipamento ativado pagando pontos de recursos gerados por pitch para prevenir dano arcano na proporção 1:1.
  - **Spellvoid**: Habilidade de equipamento que permite destruí-lo voluntariamente para prevenir uma quantidade fixa de dano arcano.
  - **Ward**: Habilidade estática de substituição que destrói automaticamente o equipamento caso o herói fosse sofrer dano, prevenindo uma quantidade fixa de dano de qualquer tipo.
  - _Avoid_: Bloqueio arcano, Escudo mágico, Magic Defense, Armor Soak.

---

## Domain: AI Engine

- **FaBCardTransformerNetwork (`ai/model.py`)**: Rede Neural Transformer Dual-Head com Self-Attention (entre 16 slots de cartas ativas) e Cross-Attention (com token de contexto global), operando sobre vetor de estado flat-packed de 800 dimensões contínuas e cabeças auxiliares KataGo.
  - _Avoid_: MLP de cartas, Rede estática legada, ResNet v1 de 192 entradas, Rede de perceptron simples.
- **Matriz de Embeddings Tensoriais (`data/card_embeddings.pt` & `data/card_to_idx.json`)**: Matriz densa pré-compilada em PyTorch de dimensões `[5133, 48]` em FP32, indexada em $O(1)$ pelo identificador de carta. Codifica atributos canônicos, classes one-hot, keywords de combate e componentes semânticos textuais via decomposição SVD.
  - _Avoid_: Extração de embeddings em tempo de execução, Regex na inferência, One-hot gigante esparso.
- **Compreensão Semântica de Arena (`ai/policy/card_semantics.py` & `data/fab_card_semantics.json`)**: Sistema holístico de percepção que compila perfis funcionais (`CardSemanticProfile`) e sintetiza o contexto dinâmico de perigo (`ArenaThreatContext`), interpretando modificadores de combate concedidos por itens, auras e gatilhos de dano concorrentes sem dependência de hardcodes nominais.
  - _Avoid_: Hardcode nominal de itens, Lista estática de cartas de arena, Checagem cega por nome.
- **ISMCTS (Information Set Monte Carlo Tree Search)**: Variante de MCTS especializada em jogos de informação imperfeita. Amostra múltiplos mundos determinizados preenchendo as cartas ocultas do oponente a partir de um pool consistente com a classe do herói rival.
  - _Avoid_: MCTS determinístico simples, Alpha-Beta minimax, Monte Carlo cego, Árvore de decisão comum.
- **World / Determinization**: Uma instância hipotética e completa do estado da partida onde todas as variáveis ocultas (mão e arsenal do oponente) são simuladas com cartas plausíveis.
  - _Avoid_: Cenário simulado genérico, Universo paralelo, Hipótese de jogo.
- **Deck-Aware World Sampling**: Mecanismo de amostragem de mundos que utiliza `data/fab_cards_db.json` para filtrar cartas estritamente válidas para a classe, talentos e formato do herói oponente.
  - _Avoid_: Amostragem randômica cega, Deck guesser, Chute de cartas.
- **Multi-Threaded ISMCTS (`ai/mcts/ismcts.py`)**: Arquitetura concorrente que utiliza `concurrent.futures.ThreadPoolExecutor` para avaliar mundos determinizados paralelamente, agregando contadores de visitas de nós filhos da raiz de forma consolidada e thread-safe.
  - _Avoid_: MCTS sequencial, Multiprocessing com pickle pesado, Árvore global compartilhada com locks.
- **Distilação Assimétrica (Asymmetric Distillation)**: Paradigma de aprendizado onde a distribuição de contagem de visitas gerada pelo ISMCTS ($\pi_{\text{MCTS}}$) é utilizada diretamente como alvo de treino supervisionado (Cross-Entropy/KL) para a cabeça de política da rede neural $p_\theta(s)$.
  - _Avoid_: Treinamento supervisionado ingênuo, Policy Gradient puro com vitória binária, Imitação de heurística.
- **Alvos Auxiliares KataGo (Auxiliary Targets)**: Metodologia em `ai/model.py` e `ai/training/orchestrator.py` que treina cabeças auxiliares lineares para predição contínua da variação líquida de vida no turno ($\Delta\text{HP}$) e dano de ataque desferido (`turn_dmg`), adicionados com peso 0.2 na função de custo.
  - _Avoid_: Métricas secundárias, Multi-task não supervisionado, Preditor avulso.
- **PER (Prioritized Experience Replay)**: Sistema de amostragem em `ai/experience_collector.py` baseado em Schaul et al. (2016) que prioriza transições de jogo contendo blunders, viradas e momentos decisivos avaliados pelo `BlunderReviewer`, ponderado por Importance Sampling weights ($w_i$).
  - _Avoid_: Buffer prioritário simples, Replay balanceado por heurística, Amostragem sem peso de importância.
- **Blunder Reviewer (`ai/blunder_reviewer.py`)**: Módulo de análise pós-jogo que inspeciona a trajetória da partida recém-terminada, detectando oscilações severas de avaliação de tabuleiro ($\Delta\text{eval} \le -3.0$ para blunders, $\le -1.5$ para imprecisões) e gerando pesos proporcionais para o PER.
  - _Avoid_: Revisor de erros manual, Log de exceções táticas, Detector de derrotas.
- **Dynamic Rule Tuner (`ai/dynamic_rule_tuner.py`)**: Sistema de auto-calibração em runtime que ajusta dinamicamente os multiplicadores de regras táticas (ataque, bloqueio, pivot, arsenal) em `data/hero_rule_multipliers.json` com base no histórico de taxas de vitória empíricas de cada herói.
  - _Avoid_: Calibrador manual, Afinador de constantes estático, Script de balanceamento avulso.
- **Atomic File Lock (`ai/atomic_io.py`)**: Protocolo de persistência concorrente seguro para ambientes multiprocesso Linux que combina exclusão mútua interprocessos via `fcntl.flock` reentrante com substituição atômica de arquivos no nível POSIX (*write-to-tmp + rename* via `os.replace`).
  - _Avoid_: Lock de thread em memória, Trava de arquivo sem timeout, Gravação direta com open.
- **Modo Cavar (Digging Mode)**: Heurística tática ativada em `ai/policy/arsenal_pruner.py` quando o bot possui 3 ou mais cartas na mão no fim de turno e nenhuma opção alcança score positivo. Deposita deliberadamente a melhor carta de ação jogável no Arsenal para liberar a mão e forçar a compra de cartas novas do topo do baralho até o Intelecto no End of Turn Step (CR 4.3.2).
  - _Avoid_: Modo Escavação, Descarte voluntário, Arsenal forçado cego, Ciclo passivo.
- **Stalemate (Empate Técnico / Anti-Stall)**: Mecanismo de detecção em `ai/bot_runtime/match_tracker.py` que encerra partidas como empate técnico diante de esgotamento mútuo de baralhos sem dano por 3 turnos, estagnação de dano por 12 turnos com decks residuais $\le 5$ ou alcance do teto rígido de turnos (45 Blitz, 55 CC).
  - _Avoid_: Jogo travado genérico, Crash de engine, Partida pendurada, Abandono de conexão.
- **Resolução de Sideboard (`ai/sideboard_manager.py`)**: Algoritmo de conformidade pré-jogo que seleciona automaticamente herói, armas (estritamente até 2 mãos conforme CR 2.8.2 e CR 3.0), equipamentos e cartas do baralho principal vs inventário, adaptando o tamanho do baralho (40/60 ou 65 contra fadiga) e defesas arcanas.
  - _Avoid_: Troca manual de cartas, Seleção ingênua de sideboard, Ajuste de deck livre.
- **Knapsack Breakpoint Defense**: Resolvedor de subconjunto combinatório em `ai/policy/defense_pruner.py` focado exclusivamente em **defesa**. Calcula a combinação ótima mínima de cartas da mão e armaduras para cobrir *breakpoints* de ataque e mitigar ameaças *on-hit* ($\sum \text{block} \ge \text{opp\_power}$), poupando cartas para o próximo turno ofensivo.
  - _Avoid_: Knapsack ofensivo, Algoritmo de mochila único, Seleção ingênua de bloqueio.
- **Knapsack Turn Solver (`ai/hero_strategies/knapsack_solver.py`)**: Resolvedor baseado em Programação Dinâmica (0-1 Knapsack) focado exclusivamente no **planejamento ofensivo do turno**. Calcula a sequência ótima de cartas de ataque, pitches de recurso e ativações de herói para maximizar o dano e uso de Action Points, considerando custos de oportunidade.
  - _Avoid_: Knapsack defensivo, Turn planner simplificado, Calculador guloso de dano.
- **Tempo Pivot**: Decisão defensiva calculada onde o bot aceita sofrer dano moderado sem sobrebloquear para reter a mão inteira e desferir um contra-ataque massivo no turno seguinte.
  - _Avoid_: Não defender por negligência, Sacrifício passivo de vida, Ignorar ataque oponente.
- **Overblocking**: Erro tático de alocar mais pontos de defesa do que o dano recebido, desperdiçando cartas defensivas valiosas que poderiam ser convertidas em ataques ou pitches.
  - _Avoid_: Superdefesa, Bloqueio seguro excessivo, Bloco redundante.
- **GameSimulator (`ai/game_simulator.py`)**: Simulador determinístico de transições de regras e estados futuros de combate sem dependência do Talishar PHP.
  - _Avoid_: Mock de jogo, Emulador arbitrário, Test dummy.
- **Replay Buffer (`ai/experience_collector.py`)**: Buffer circular de experiências que armazena estados, políticas ISMCTS e recompensas de partidas para treino off-policy com salvamento atômico em disco.
  - _Avoid_: Histórico de logs, Banco de dados de partidas, Fila temporária.
- **Batch Leaf Evaluation**: Agrupamento simultâneo de múltiplos nós folhas gerados pelo MCTS em um único lote matricial de forward pass na GPU/PyTorch, reduzindo a latência de $O(N)$ para $O(1)$.
  - _Avoid_: Avaliação folha a folha, Inferência individual síncrona.
- **Progressive Widening**: Restrição no MCTS que limita a expansão de filhos a $\sqrt{N}$ simulações, direcionando o orçamento computacional para as variantes mais prováveis.
  - _Avoid_: Expansão completa da árvore, Poda fixa de nós.
- **Prior Threshold Pruning**: Poda estática que descarta ações legais com probabilidade de prior inferior a $-1.5\sigma$ em relação à média, eliminando movimentos manifestamente inferiores antes da árvore.
  - _Avoid_: Poda por limite arbitrário, Descarte de jogadas cego.
- **CR 3.1.5**: Regra oficial de Flesh and Blood que proíbe colocar cartas de recurso puro ou gemas no Arsenal devido à impossibilidade de pitch a partir dele.
  - _Avoid_: Regra geral de cartas, Bloqueio de arsenal facultativo.
- **Equipment Learning Engine (`ai/equipment_learning.py`)**: Módulo empírico que rastreia taxas de sucesso de bloqueio e ativação de armaduras, refinando multiplicadores salvos em `data/equipment_usage_stats.json`.
  - _Avoid_: Tabela fixa de armaduras, Avaliador estático de equipamentos.
- **Equipment Metadata (`data/equipment_metadata.json`)**: Banco de metadados semânticos extraído do Talishar para 624 equipamentos, definindo bônus numéricos sem hardcoding nominal.
  - _Avoid_: Dicionário manual de peças, Tabela improvisada de itens.
- **On-Hit Threat Quantification**: Escala hierárquica de severidade (Catastrófico [8.5-10.0], Alto [5.0-7.0], Médio [3.5-4.5], Vanilla [0.0]) para efeitos desencadeados ao acertar o golpe.
  - _Avoid_: Pontuação arbitrária de dano, Gravidade qualitativa.
- **Vanilla Armor Pruning**: Regra que proíbe gastar equipamentos defensivos contra ataques normais sem efeito on-hit quando o herói possui vida saudável ($HP > 12$).
  - _Avoid_: Proibição total de armaduras, Economia cega de equipamentos.
- **Arsenal Threat Protection**: Heurística de defesa que detecta ataques de destruição/banimento de Arsenal (*Command and Conquer*, *Leave No Witnesses*) e aciona peças como *Crown of Providence* para afundar a carta ameaçada.
  - _Avoid_: Proteção genérica de itens, Reação passiva a ataques pesados.
- **Smart Sinking / Tuck Logic**: Heurística que inverte o critério de pontuação em janelas de "sink" para colocar a pior carta da mão no fundo do baralho e recomprar cartas novas.
  - _Avoid_: Descarte no baralho, Ciclo aleatório, Sink ingênuo.
- **Void Equipment Pruning**: Poda que bloqueia a ativação ou sacrifício de equipamentos de prevenção no vazio quando não há dano físico ou arcano ativo na cadeia.
  - _Avoid_: Ativação preventiva livre, Descarte inútil de peças.
- **Flexible Block Conversion**: Mecanismo que identifica mãos com média defensiva ineficiente ($\le 2.0$) e autoriza absorção calculada de dano em prol de um turno ofensivo potente.
  - _Avoid_: Não defender por padrão, Bloqueio fraco arbitrário.
- **Human ELO Feedback System**: Telemetria em `stats_manager.py` que distingue partidas contra jogadores humanos, aplicando ponderação reforçada para calibração de estratégias.
  - _Avoid_: ELO unificado, Ranking sem separação de oponentes.
- **Invalid Match Filtering**: Algoritmo que invalida e expurga partidas espúrias (empates sem dano trocado $< 4$ HP ou bots inertes *Punching Bag*), mantendo a integridade dos dados de treino e rankings.
  - _Avoid_: Limpeza cega de partidas, Exclusão manual de dados.
- **Punching Bag / Inert Stall**: Anomalia técnica onde um bot perdedor passa $\ge 6$ turnos sem desferir ataques ou dano enquanto o adversário permanece intacto (100% HP), exigindo anulação da partida.
  - _Avoid_: Partida desbalanceada comum, Vitória rápida legítima.
- **Turn Planner & Survival Trigger (`ai/hero_strategies/turn_planner.py`)**: Módulo tático que formula o `TurnPlan` (modo ofensivo, pivot ou sobrevivência estrita quando dano letal é iminente).
  - _Avoid_: Planejador genérico de turno, Algoritmo ofensivo padrão.

---

## Domain: Architecture

- **Bot Client (`bot_client.py`)**: Ponto de entrada e fachada retrocompatível do agente autônomo que se conecta ao Talishar, consome o estado de jogo e envia ações.
  - _Avoid_: Script do bot, Talishar bot monólito.
- **Dashboard (`dashboard.py`)**: Interface visual Streamlit para monitoramento de treinamento GPU, telemetria de ISMCTS, visualização de ELO e arena de combate.
  - _Avoid_: UI de treino, Webapp genérico, Painel de controle solto.
- **Modular Subpackages**: A arquitetura decomposta em pacotes desacoplados e de responsabilidade única:
  - `ai/bot_runtime/`: Gestão de lobby, match tracker, modais anti-loop e decisões de fase.
  - `ai/policy/`: Poda combinatória, avaliação e motor de decisão tática.
  - `ai/mcts/`: Motores de busca MCTS/ISMCTS concorrentes multithread.
  - `ai/training/`: Supervisão de processos e orquestrador de GPU com FP16/AMP.
  - `deck_manager/`: Slugificação, parsing, validação de formatos e repositório atômico de baralhos.
  - `stats/`: Cálculo de ELO com K-factor dinâmico, nomes canônicos e persistência com lock.
  - `ui/`: Interface gráfica Streamlit decomposta (`helpers.py` e 7 abas em `tabs/`).
  - _Avoid_: Monólito dividido, Pastas arbitrárias de código, Módulos dispersos.
- **Retrocompatibility Facades**: Módulos raízes enxutos (`bot_client.py`, `dashboard.py`, `deck_parser.py`, `stats_manager.py`, `ai/trainer.py`, `ai/policy_engine.py`, `ai/mcts/__init__.py`) que re-exportam métodos e classes públicas dos subpacotes, preservando 100% de compatibilidade retroativa.
  - _Avoid_: Wrappers redundantes, Aliases soltos, Código duplicado.
- **Setup Templates (`setup_templates/`)**: Repositório central de patches e arquivos customizados que são injetados em clones limpos do Talishar e Talishar-FE para viabilizar integração com IA sem dependência de submódulos Git.
  - _Avoid_: Git Submodules, Forks do Talishar, Patches temporários.
- **Decks Directory (`decks/`)**: Diretório central e exclusivo para arquivos JSON de baralhos. Nenhum baralho é criado ou salvo dentro das pastas internas do Talishar.
  - _Avoid_: Pastas internas do Talishar, Decks temporários, Pastas avulsas.
- **Chess Advantage Tracker**: Componente visual do frontend (`ChessAdvantageTracker.tsx`) que exibe a barra de vantagem tática em tempo real no chat do Talishar.
  - _Avoid_: Barra de vida extra, Indicador genérico.
- **Elo Rating**: Sistema de ranqueamento ponderado em `stats_manager.py` para avaliação do nível competitivo dos decks e agentes.
  - _Avoid_: Pontuação simples, Leaderboard estático.
- **Environment Auto-Detection & Sanitizer (`scripts/prepare_environment.py`)**: Script de automação unificada que detecta o ambiente operacional (Linux vs WSL2), injeta templates e sanitiza permissões sem vazamento de dados privados.
  - _Avoid_: Instalador manual, Setup script disperso.
- **Pre-Commit Verification & Privacy Guard (`scripts/sync_and_clean.sh`)**: Hook pré-commit que valida sincronização de templates, compilação do frontend Vite (`npx vite build`) e sintaxe Python, bloqueando vazamento de caminhos pessoais.
  - _Avoid_: Script de git simples, Limpador de logs.
- **Frontend Ads Proxy / BannerUnit Mock (`setup_templates/frontend/bannerUnit`)**: Mock headless do módulo de anúncios do Talishar-FE para permitir compilações limpas e offline do frontend.
  - _Avoid_: Bloco de anúncio ativo, Bypass manual de dependências.
