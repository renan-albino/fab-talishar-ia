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
- **Chain Links (Elos da Cadeia de Combate - CR 7.0 / CR 7.1)**: Unidades discretas sequenciais dentro de uma Combat Chain, cada qual iniciada pela declaração de um ataque no Layer Step e processada através de Attack Step, Defend Step, Reaction Step, Damage Step e Link Step. Contabilizados em `numChainLinks` para habilitar sinergias condicionais como Rupture (elo $\ge 4$) e limiares Dracônicos ($\ge 2$ elos).
  - _Avoid_: Rodada de ataque, Sub-turno de combate, Ataque isolado fora de elo.
- **Layer Priority (Prioridade de Camada - CR 1.10 / CR 7.1)**: Janela de prioridade onde cartas de ação jogadas, habilidades ativadas ou gatilhos (*triggers*) residem na pilha da camada (*Layer*) aguardando resolução em ordem LIFO (Last-In, First-Out) antes de se tornarem o ataque ativo do elo da cadeia.
  - _Avoid_: Pilha mágica genérica, Fila FIFO de efeitos, Resolução imediata sem resposta.
- **Action Point (AP)**: Recurso fundamental consumido para jogar cartas do tipo Ação ou ativar habilidades de equipamentos/herói que exijam uma ação.
  - _Avoid_: Ponto de mana, Ponto de energia, Ponto de movimento, Turno adicional.
- **Intelecto (Intellect)**: Valor numérico impresso na carta do herói que define o tamanho máximo de cartas na mão até o qual o jogador compra durante o End of Turn Step (CR 4.3.2). Padrão 4 para heróis adultos e 3 para heróis Brute como Rhinar e Kayo.
  - _Avoid_: Tamanho da mão, Capacidade de compra, Hand Limit, Max Cards.
- **Reaction Step (CR 7.5a & CR 7.5b)**: Etapa formal de combate que sucede o Defend Step, compreendendo o Attack Reaction Step (CR 7.5a) e o Defense Reaction Step (CR 7.5b), onde jogadores alternam prioridade para utilizar cartas de reação e Instant antes da resolução de dano. Impõe restrições estritas sob Dominate (CR 7.4.2a: proíbe adicionar Defense Reactions da mão se o elo já é defendido por uma carta, permitindo apenas Defense Reactions jogadas a partir do Arsenal via Mode 5) e exige a exclusão mandatória de Defense Reactions da declaração inicial de bloqueio na Phase B (CR 7.3.2).
  - _Avoid_: Janela de resposta livre, Fast play step, Quick Action Phase, Janela de contra-ataque, Bloqueio com Defense Reaction na Phase B.
- **Choose Multi-Zone (`CHOOSEMULTIZONE`) & May Choose Multi-Zone (`MAYCHOOSEMULTIZONE`)**: Modais interativos de seleção multi-zona emitidos pelo motor para escolha obrigatória (`CHOOSEMULTIZONE`) ou facultativa (`MAYCHOOSEMULTIZONE`, permitindo Mode 99 `PASS`) de alvos em equipamentos, mão, arsenal, cemitério ou banimento (`ai/bot_runtime/choice_handler.py`), blindados contra alvos quebrados (`isBroken=True`) ou desabilitados (`overlay=1`).
  - _Avoid_: Popup genérico de clique, Modal sem validação de overlay, Escolha cega de índice.
- **Mechanologist Boost (CR 8.3.19)**: Palavra-chave opcional de classe Mechanologist que permite banir a carta do topo do próprio baralho ao jogar um ataque; se a carta banida também for uma carta Mechanologist, o ataque adquire **Go Again** (modelado em `ai/hero_strategies/mechanologist.py` e `ai/game_simulator.py`).
  - _Avoid_: Compra extra de Mechanologist, Descarte do topo para go again, Mill sem verificação de classe.
- **Illusionist Phantasm (CR 7.4.4 / CR 8.3.13)**: Palavra-chave estática de ataques Illusionist que destrói imediatamente o ataque e fecha a Combat Chain caso seja defendido por uma carta de Ação não-Illusionist com poder base ou modificado $\ge 6$ (*Phantasm Pop*, avaliado em `ai/policy/defense_pruner.py`, `ai/hero_strategies/illusionist.py` e ADR-0011).
  - _Avoid_: Destruição mágica de ataque, Cancelamento por qualquer bloqueio 6+, Fechamento de cadeia por equipamento 6+.
- **Runeblade Runechants (CR 8.6.13)**: Tokens de aura que acumulam na arena e são destruídos automaticamente ao declarar um ataque (ou ativar condições específicas), disparando instâncias individuais de 1 ponto de dano arcano contra o alvo antes do impacto físico (`ai/hero_strategies/runeblade.py`).
  - _Avoid_: Contadores de dano físico extra, Auras permanentes de poder, Buff estático de espada.
- **Shadow Blood Debt (CR 8.3.11)**: Palavra-chave em cartas de talento Shadow que, enquanto permanecem na zona de banimento face-up, infligem 1 ponto de perda de vida por carta ao controlador durante sua End Phase, salvo se desativadas pela condição do herói (como banir/atacar com poder $\ge 6$ em Levia via `LEVIA_BLOOD_DEBT_PREVENTION` em `ai/hero_strategies/brute.py`).
  - _Avoid_: Dano de fadiga, Veneno de cemitério, Custo de sangue ao jogar.
- **Elemental Fusion (CR 8.3.18)**: Palavra-chave adicional que permite revelar uma ou mais cartas da mão com os talentos elementais requeridos (*Earth*, *Ice* ou *Lightning*) no momento em que a carta é jogada para desbloquear efeitos bônus poderosos, exigindo retenção coordenada de peças elementais na mão (`ai/policy/pitch_pruner.py` e `ai/hero_strategies/`).
  - _Avoid_: Descarte elemental para fundir, Sacrifício de carta da mão, Pitch elemental como fusão.
- **Prevenção Arcana (Arcane Prevention - Ward / Spellvoid / AB)**: Mecanismos e palavras-chave oficiais de FaB destinados a mitigar dano arcano:
  - **Arcane Barrier (AB)**: Efeito de equipamento ativado pagando pontos de recursos gerados por pitch para prevenir dano arcano na proporção 1:1.
  - **Spellvoid**: Habilidade de equipamento que permite destruí-lo voluntariamente para prevenir uma quantidade fixa de dano arcano.
  - **Ward**: Habilidade estática de substituição que destrói automaticamente o equipamento caso o herói fosse sofrer dano, prevenindo uma quantidade fixa de dano de qualquer tipo.
  - _Avoid_: Bloqueio arcano, Escudo mágico, Magic Defense, Armor Soak.

---

## Domain: Simulador Talishar & Idiossincrasias Sim2Real

- **Normalização Bidirecional `playerArse` vs `playerArsenal` (`ai/game_simulator.py`, `ai/shadow_mode.py`, `ai/mcts/state.py` & ADR-0020)**: Tratamento unificado e bidirecional das chaves de estado do Arsenal entre a nomenclatura truncada histórica do payload PHP do Talishar (`playerArse` / `opponentArse`) e a chave canônica da engine (`playerArsenal` / `opponentArsenal`), garantindo que jogadas de Mode 5 e contagens de `arsenal_count` nunca gerem divergências fantasmas.
  - _Avoid_: Leitura exclusiva de `playerArsenal`, Descarte silencioso de `playerArse`, Duplicação dessincronizada de listas de arsenal.
- **Ciclo de Fases `turnPhase` (`M`, `P`, `A`, `B`, `D`, `E`/`ARS`) (`ai/bot_runtime/client.py`, `ai/bot_runtime/phase_decider.py` & `ai/game_simulator.py`)**: Máquina de estados finita das fases de turno exportadas pelo Talishar: `M` (Main Phase / Action Phase), `P` (Pitch Step para pagamento de custos pendentes), `A` (Attack / Layer Step), `B` (Block / Defend Step, onde apenas equipamentos e cartas não-DR bloqueiam conforme CR 7.3.2), `D` (Reaction Step para Attack e Defense Reactions) e `E`/`ARS` (End of Turn / Arsenal Step).
  - _Avoid_: Fase única de combate, Mistura de Phase B com Phase D, String livre de fase sem normalização in-place.
- **Identificadores de Ação `actionDataOverride` (`MYCHAR-X`, `EQ-0`) (`ai/bot_runtime/choice_handler.py`, `ai/bot_runtime/phase_decider.py` & `ai/game_simulator.py`)**: Convenção de endereçamento de alvos e fontes de ativação no protocolo do Talishar e no simulador local, onde `MYCHAR-X` referencia o índice exato `X` na matriz de personagem/equipamentos/armas (ex: targeting cirúrgico de adagas com Mode 16) e `EQ-0` / `EQ-X` identifica ativações diretas de habilidades de equipamento sem consumo indevido de Action Point quando instantâneas.
  - _Avoid_: Índices mágicos sem prefixo de zona, Ativação de equipamento descontando AP incondicionalmente, Clique cego sem `actionDataOverride`.
- **Transições Multi-Tick Assíncronas & Estados Transitórios (`confounded`) (`ai/shadow_mode.py` & ADR-0020)**: Fenômeno do motor PHP do Talishar onde uma única declaração de carta com custo > recursos disponíveis transita primeiro por estados intermediários de pagamento (`M` $\to$ `P` ou modais `CHOOSEMULTIZONE` / `BUTTONINPUT`) antes de liquidar atomicamente o custo, deduzir recursos e consumir o AP. Tais passos são sinalizados com `confounded=True` no `Shadow Mode` para isolar a métrica de Fidelidade do Simulador contra ruído assíncrono de multi-tick.
  - _Avoid_: Comparação direta de diff em transição `M` $\to$ `P`, Contabilização de modais intermediários como erro do simulador, Penalização de fidelidade em estados transitórios.

---

## Domain: AI Engine

- **FaBCardTransformerNetwork (`ai/model.py`)**: Rede Neural Transformer Dual-Head com Self-Attention (entre 16 slots de cartas ativas) e Cross-Attention (com 64 tokens de contexto global), operando sobre vetor de estado flat-packed de 832 dimensões contínuas e cabeças auxiliares KataGo.
  - _Avoid_: MLP de cartas, Rede estática legada, ResNet v1 de 192 entradas, Rede de perceptron simples, Vetor legado de 800 dimensões.
- **Matriz de Embeddings Tensoriais (`data/card_embeddings.pt` & `data/card_to_idx.json`)**: Matriz densa pré-compilada em PyTorch de dimensões `[5145, 48]` em FP32, indexada em $O(1)$ pelo identificador de carta. Codifica atributos canônicos, classes one-hot, keywords de combate e componentes semânticos textuais via decomposição SVD.
  - _Avoid_: Extração de embeddings em tempo de execução, Regex na inferência, One-hot gigante esparso.
- **Compreensão Semântica de Arena (`ai/policy/card_semantics.py` & `data/fab_card_semantics.json`)**: Sistema holístico de percepção que compila perfis funcionais (`CardSemanticProfile`) e sintetiza o contexto dinâmico de perigo (`ArenaThreatContext`), interpretando modificadores de combate concedidos por itens, auras e gatilhos de dano concorrentes sem dependência de hardcodes nominais.
  - _Avoid_: Hardcode nominal de itens, Lista estática de cartas de arena, Checagem cega por nome.
- **Resolvedor Dinâmico de Go Again (`ai/policy/go_again_resolver.py`)**: Mecanismo canônico que avalia a concessão dinâmica de Go Again para ataques em tempo real, integrando verificações intrínsecas (`GeneratedGoAgain.php`), tokens (Quicken/Agility no elo inicial da cadeia conforme CR 8.6.1/8.6.28), requisitos Dracônicos ($\ge 2$ elos com talento DRACONIC), ativação de cartas vermelhas (`blaze_headlong`) e combos de Ninja (`rising_knee_thrust`, `crane_dance`, `whelming_gustwave`), aplicando penalidade rígida de $-35.0$ em `attack_pruner.py` contra aberturas ilegítimas sem Go Again garantido quando `player_ap \le 1`.
  - _Avoid_: Flag estática de go again, Checagem ingênua de starter, Suposição cega de go again condicional.
- **Caixa Preta de Erros / Error Dump (`logs/exceptions/`)**: Dicionário serializado JSON salvo instantaneamente contendo o *Traceback*, *Turn Phase* e *Game State* cru sempre que a AI submete seletores (`MULTICHOOSE`) inválidos ou crasha na simulação, usado para podas manuais da rede.
  - _Avoid_: Log de texto de erro, print de console, crash log genérico.
- **ISMCTS (Information Set Monte Carlo Tree Search)**: Variante de MCTS especializada em jogos de informação imperfeita. Amostra múltiplos mundos determinizados preenchendo as cartas ocultas do oponente a partir de um pool consistente com a classe do herói rival.
  - _Avoid_: MCTS determinístico simples, Alpha-Beta minimax, Monte Carlo cego, Árvore de decisão comum.
- **World / Determinization**: Uma instância hipotética e completa do estado da partida onde todas as variáveis ocultas (mão e arsenal do oponente) são simuladas com cartas plausíveis.
  - _Avoid_: Cenário simulado genérico, Universo paralelo, Hipótese de jogo.
- **Deck-Aware World Sampling**: Mecanismo de amostragem de mundos que utiliza `data/fab_cards_db.json` para filtrar cartas estritamente válidas para a classe, talentos e formato do herói oponente.
  - _Avoid_: Amostragem randômica cega, Deck guesser, Chute de cartas.
- **Concorrência Híbrida ISMCTS (`ai/mcts/ismcts.py`)**: Arquitetura adaptativa de execução que suporta 4 modos de concorrência (`threads`, `multiprocessing`, `direct_gpu` e `sequential`). O modo `threads` (ThreadPoolExecutor in-process) atua como padrão estável de zero-overhead de processos para treino multi-salas (ADR-0002 / ADR-0008).
  - _Avoid_: Concorrência rígida de processo único, Multiprocessing cego para self-play, Paralelismo não configurável.
- **Actor-Evaluator ISMCTS (`ai/mcts/inference_server.py`)**: Arquitetura de concorrência avançada onde múltiplos processos MCTS em CPU (Actors com `RemoteModelProxy`) enviam requisições de inferência via IPC Pipes para um servidor centralizado na GPU (`BatchedInferenceServer`), que processa lotes dinâmicos e devolve resumos de Nível 1.
  - _Avoid_: Réplicas completas de modelo em subprocessos, Pickle de árvores recursivas profundas, Contextos CUDA aninhados sem servidor.
- **Lazy Hardware Probe (`config/settings.py`)**: Mecanismo de avaliação sob demanda e cacheada (`@lru_cache`) para detecção de GPU (`nvidia-smi`) e benchmark de latência, com bypass seguro via flag `TALISHAR_SKIP_GPU_PROBE` para evitar storms de processos em subprocessos paralelos.
  - _Avoid_: Hardware probe síncrono na importação, Subprocesso repetido de nvidia-smi, Checagem pesada em boot de worker.
- **Orçamento Preditivo de VRAM (`SETTINGS.estimate_vram_usage`)**: Função de dimensionamento analítico que calcula a memória de vídeo necessária para o conjunto de salas, mundos e modo de concorrência antes da inicialização do treino, alertando contra riscos de CUDA OOM.
  - _Avoid_: Trava arbitrária de hardware, Dimensionamento empírico cego, Alocação sem checagem de VRAM.
- **Orçamento Adaptativo de MCTS (Adaptive MCTS Budget - `ai/mcts/ismcts.py`)**: Mecanismo de alocação dinâmica de simulações MCTS/ISMCTS (`calculate_adaptive_mcts_budget`) que preserva o valor base configurado (`base_sims`) como piso/referência, reduzindo simulações em escolhas triviais/forçadas e escalonando o orçamento computacional em até $1.5\times$ ou $2.0\times$ sob alta incerteza da rede neural (entropia nos priors $\ge 0.85$, $\Delta\text{eval} \ge 1.5$, letalidade crítica ou incerteza Bayesiana no Value Head com $\sigma_V \ge 0.20 / 0.35$ conforme ADR-0019).
  - _Avoid_: Simulações fixas cegas, MCTS estático, Throttle manual de turnos.
- **Amostragem por Incerteza Bayesiana (Monte Carlo Dropout - `ai/model.py` & ADR-0019 / ADR-0020)**: Estimação de incerteza epistêmica ($\mu_V, \sigma_V$) na cabeça de valor da `FaBCardTransformerNetwork` (`predict_value_with_uncertainty`) que executa um único forward pass determinístico pelo backbone Transformer (Self-Attention e Cross-Attention) e replica apenas o tensor de features latentes fundidas (`fused.repeat(num_samples, 1)`) através de `value_dropout` e `value_head`, modulando o orçamento MCTS adaptativo e blindando contra apostas especulativas de `TEMPO_COUNTER_ATTACK` quando $\sigma_V \ge 0.25$ (`UNCERTAINTY_SAFETY_BLOCK`).
  - _Avoid_: Múltiplos forward passes completos no Transformer, Predição escalar cega sem incerteza, Loop sequencial de dropout em Python.
- **Distilação Assimétrica (Asymmetric Distillation)**: Paradigma de aprendizado onde a distribuição de contagem de visitas gerada pelo ISMCTS ($\pi_{\text{MCTS}}$) é utilizada diretamente como alvo de treino supervisionado (Cross-Entropy/KL) para a cabeça de política da rede neural $p_\theta(s)$.
  - _Avoid_: Treinamento supervisionado ingênuo, Policy Gradient puro com vitória binária, Imitação de heurística.
- **Alvos Auxiliares KataGo (Auxiliary Targets - `ai/model.py`, `ai/training/headless_env.py`, `ai/training/orchestrator.py` & ADR-0020)**: Metodologia multi-tarefa inspirada no KataGo que treina cabeças lineares auxiliares para predição contínua da variação líquida de vida no turno ($\Delta\text{HP} / \text{board\_eval}$) e dano de ataque desferido (`turn_dmg`), supervisionadas tanto em trajetórias Sim2Real quanto no `HeadlessSelfPlayLoop` com peso $0.2$ na função de perda composta.
  - _Avoid_: Métricas secundárias não supervisionadas, Multi-task sem target no headless, Preditor avulso fora da loss.
- **1-Ply Memoization (Memoização de Folhas 1-Ply - ADR-0014 & ADR-0016)**: Otimização de busca em `ai/mcts/ismcts.py` e `ai/mcts/standard_mcts.py` onde todos os nós filhos candidatos únicos (`action_id`) são avaliados em lote único antes do loop de simulações PUCT, armazenando os priors e avaliações em tabela de dispersão em memória e reutilizando a raiz entre mundos determinizados. Elimina 96.7% dos forward passes repetidos na rede neural e reduz a latência p50 em 94.9% sem alterar a distribuição de visitas.
  - _Avoid_: MCTS profundo de rollouts cegos, Forward pass individual por simulação, Busca com recálculo redundante de folhas idênticas.
- **Fast Immutability (`ImmutableGameState._from_frozen` - ADR-0016)**: Construtor otimizado de representação de estado em `ai/mcts/state.py` que congela exclusivamente os campos modificados em chamadas de `replace()` e `without()`, reutilizando referências já imutáveis sem reprocessamento recursivo de tipos.
  - _Avoid_: Re-congelamento recursivo total, Deepcopy de estado, Cópia ingênua de dicionário em loop.
- **Decay Annealing (`epoch_ratio` - ADR-0012, ADR-0016, ADR-0017)**: Esquema unificado de recozimento progressivo parametrizado pela razão de evolução do treinamento ($\text{epoch\_ratio} \in [0.0, 1.0]$) que governa simultaneamente o annealing triplo do motor: (1) transição de pesos da recompensa canônica $w_{\text{term}} = 1.0 - 0.4(1 - \text{epoch\_ratio})$ e $w_{\text{eval}} = 0.4(1 - \text{epoch\_ratio})$; (2) decaimento da temperatura de fusão heurística Knapsack-NN em direção à política neural pura; e (3) incremento de $\beta \to 1.0$ para correção de viés de Importance Sampling no PER.
  - _Avoid_: Pesos fixos de reward sem annealing, Temperatura estática Knapsack-NN, Beta constante no PER.
- **Recompensa Canônica Unificada (Canonical Shaped Reward - ADR-0017)**: Função unificada `compute_shaped_reward` em `ai/experience_collector.py` que calcula a recompensa de treino com decaimento temporal $w_{\text{term}} = 1.0 - 0.4(1 - \text{epoch\_ratio})$ e $w_{\text{eval}} = 0.4(1 - \text{epoch\_ratio})$, garantindo paridade matemática estrita entre partidas Sim2Real do Talishar e partidas em memória do Headless.
  - _Avoid_: Fórmulas divergentes de recompensa, Reward estático sem annealing, Pesos de vitória assimétricos entre simulação e produção.
- **SumTree Vetorizada em C/NumPy (`SumTree.set_all`, `get_leaves` & `update_batch` - `ai/experience_collector.py` & ADR-0017 / ADR-0020)**: Estrutura de árvore de soma segmentada inteiramente vetorizada em NumPy que reconstrói níveis internos em $O(N)$ via `set_all` (233.8× mais rápida), extrai folhas por indexação contígua (`get_leaves`) e atualiza prioridades de TD-error $|V_{\text{pred}} - V_{\text{target}}|$ em lote (`update_batch`) propagando apenas os nós pais únicos afetados nível a nível sem loops Python por amostra.
  - _Avoid_: Rebuild de SumTree com loop Python $O(N \log N)$, Propagação sequencial amostra por amostra em `update_priorities`, Árvore de prioridades em listas Python.

- **PER (Prioritized Experience Replay)**: Sistema de amostragem em `ai/experience_collector.py` baseado em Schaul et al. (2016) que prioriza transições de jogo contendo blunders, viradas e momentos decisivos avaliados pelo `BlunderReviewer`, ponderado por Importance Sampling weights ($w_i$).
  - _Avoid_: Buffer prioritário simples, Replay balanceado por heurística, Amostragem sem peso de importância.
- **Blunder Reviewer (`ai/blunder_reviewer.py`)**: Módulo de análise pós-jogo que inspeciona a trajetória da partida recém-terminada, detectando oscilações severas de avaliação de tabuleiro ($\Delta\text{eval} \le -3.0$ para blunders, $\le -1.5$ para imprecisões) e gerando pesos proporcionais para o PER.
  - _Avoid_: Revisor de erros manual, Log de exceções táticas, Detector de derrotas.
- **Dynamic Rule Tuner (`ai/dynamic_rule_tuner.py`)**: Sistema de auto-calibração em runtime que ajusta dinamicamente os multiplicadores de regras táticas (ataque, bloqueio, pivot, arsenal) em `banco SQLite talishar_stats.db` com base no histórico de taxas de vitória empíricas de cada herói.
  - _Avoid_: Calibrador manual, Afinador de constantes estático, Script de balanceamento avulso.
- **Banco de Dados Relacional (SQLite3)**: Persistência nativa, segura e transacional configurada em `stats/db.py`, substituindo os antigos locks atômicos no sistema de arquivos para lidar simultaneamente com ELOs (`hero_elo`), históricos (`match_history`) e hiperparâmetros de poda.
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
- **HeadlessSelfPlayLoop (`ai/training/headless_env.py`)**: Motor determinístico de auto-jogo em memória de alta performance que simula partidas completas de Flesh and Blood usando baralhos canônicos reais de `decks/*.json`, dados de `fab_cards_db.json` e `GameSimulator`, alimentando o Replay Buffer em $O(1)$ sem depender do Talishar, Docker ou chamadas de rede.
  - _Avoid_: Mock de self-play, Simulador falso de treino, Dummy loop.
- **Card Name Oracle (`ai/bot_runtime/card_name_oracle.py`)**: Oráculo dinâmico em 3 níveis (Memória da Partida Atual, Histórico no SQLite e Avaliador Algorítmico do Cards DB com fallback seguro) para predição e escolha inteligente de alvos no prompt `INPUTCARDNAME` sem listas estáticas.
  - _Avoid_: Hardcoded card names, Lista fixa de nomes, Chute cego em INPUTCARDNAME.
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
- **Human Replay Boost (`ai/bot_runtime/match_tracker.py`)**: Multiplicação de peso amostral no Replay Buffer (4.0x para vitórias do bot, 7.0x para derrotas contra humanos) para priorizar a correção de blunders e a assimilação de linhas humanas no Prioritized Experience Replay.
  - _Avoid_: Peso arbitrário de replay, Boost genérico de amostras.
- **Assimilação Pós-Partida (`ai/training/assimilation.py`)**: Ciclo leve de treinamento supervisionado/PER (10 passos de gradiente) disparado em segundo plano logo após o encerramento de duelos contra jogadores humanos, atualizando imediatamente `data/model_latest.pt` com bloqueio concorrente via `file_lock`.
  - _Avoid_: Treinamento síncrono bloqueante, Retreino completo do modelo, Auto-treino infinito.
- **Recomendação de Heróis para Treino (`stats/recommendations.py`)**: Motor heurístico de diagnóstico que inspeciona `deck_stats` e cataloga os heróis mais valiosos para duelos humanos (Gargalos de ELO com Win Rate < 45%, Alta Incerteza com < 6 partidas e Inéditos contra Humanos).
  - _Avoid_: Chute de herói, Sugestão randômica de deck, Matchup aleatório.
- **Sincronização de Telemetria do Replay Buffer (`ui/helpers.py`, `ui/tabs/tab_training.py`, `ai/training/assimilation.py`)**: Mecanismo de leitura direta e cacheada (`get_replay_buffer_sample_count`, TTL=3s) das amostras físicas de `data/replay_buffer.npz` para o Dashboard e atualização contínua do campo `samples_collected` em `training_metrics.json` pela assimilação pós-partida, evitando descompassos visuais entre duelos humanos e o orquestrador GPU.
  - _Avoid_: Leitura cega estática de métricas, Polling bloqueante de disco, Descompasso de amostras.
- **Reconexão Resiliente de Partidas (`ai/bot_runtime/lobby_manager.py`, `frontend_manager.py`)**: Capacidade do bot cliente recuperar credenciais de autenticação (`auth_key`, `player_id`) diretamente de `GameFile.txt` no disco caso a requisição de entrada (`JoinGame.php`) reporte que o oponente já se conectou ou que a partida já foi iniciada, retomando o loop de polling e decisões MCTS sem abortar a sala.
  - _Avoid_: Reconexão cega sem credenciais, Reinício destrutivo de sala, Abandono de partida em andamento.
- **Notificação e Ampulheta em Tempo Real da Assimilação (`ui/tabs/tab_play.py`, `Talishar/Games/.../gamelog.txt`)**: Indicador visual dinâmico com ampulheta animada CSS na aba de Duelo e injeção de balões de status no chat oficial do Talishar avisando o progresso da assimilação em background e prevenindo o início precipitado de novas partidas enquanto os pesos neurais estão sendo sincronizados.
  - _Avoid_: Trava cega de tela, Pop-up modal intrusivo.
- **Invalid Match Filtering**: Algoritmo que invalida e expurga partidas espúrias (empates sem dano trocado $< 4$ HP, bots inertes *Punching Bag*, timeouts de treino com turnos $\ge 2$ ou interrupções manuais na Arena com turnos $\ge 1$), preservando o histórico com placar de vida real no SQLite sem alterar o ELO nem poluir o ReplayBuffer.
  - _Avoid_: Limpeza cega de partidas, Exclusão manual de dados, Timeout desconsiderado.
- **Punching Bag / Inert Stall**: Anomalia técnica onde um bot perdedor passa $\ge 6$ turnos sem desferir ataques ou dano enquanto o adversário permanece intacto (100% HP), exigindo anulação da partida.
  - _Avoid_: Partida desbalanceada comum, Vitória rápida legítima.
- **Turn Planner & Survival Trigger (`ai/hero_strategies/turn_planner.py`)**: Módulo tático que formula o `TurnPlan` (modo ofensivo, pivot ou sobrevivência estrita quando dano letal é iminente).
  - _Avoid_: Planejador genérico de turno, Algoritmo ofensivo padrão.
- **Opponent Tracking (`ai/policy/opponent_tracker.py`)**: Rastreamento da média ponderada de cartas jogadas e dano por turno do adversário para exploração tática de ineficiência de mão.
  - _Avoid_: Leitura de mente do oponente, Rastreamento cego de cartas.
- **Risk Profile PUCT Scaling (`ai/policy/risk_profile.py`)**: Escalonamento adaptativo do parâmetro $c_{\text{puct}}$ do ISMCTS baseado na avaliação do tabuleiro $Q(s)$ (amplia exploração quando atrás e consolida linhas sólidas quando à frente).
  - _Avoid_: PUCT constante rígido, Exploração estática, Desespero aleatório.
- **On-Hit Quantitative Valuation (`ai/policy/on_hit_evaluator.py`)**: Quantificação numérica dinâmica do impacto de efeitos *on-hit* no grafo de ações (compra de cartas com taxa de conversão do arquétipo, descarte/banimento forçado, destruição de arsenal e aflições) escalados exponencialmente pela alavancagem de HP do herói.
  - _Avoid_: Bloqueio de pânico, Avaliação qualitativa de on-hit.
- **Turn 0 Selective Block (`ai/policy/defense_pruner.py` - CR 4.4.3f)**: Regra de bloqueio seletivo no primeiro turno da partida onde o bot defende. Cartas normais da mão possuem custo de oportunidade 0 (ambos os jogadores recompram até o Intelecto no fim do turno 0); absorção cega é desativada e cartas normais cobrem o dano preservando apenas peças de combo insubstituíveis e proibindo ativação de armadura no vazio.
  - _Avoid_: Absorção cega no Turno 0, Sacrifício de armadura no vazio no Turno 0.
- **Hand Conversion Potential (`calculate_hand_conversion` in `turn_planner.py`)**: Avaliação matemática comparativa do valor ofensivo total da mão versus seu valor defensivo acumulado para determinar a viabilidade de absorção de dano.
  - _Avoid_: Estimativa empírica de mão, Julgamento subjetivo de ataque.
- **Dynamic Sideboard Fatigue Detection (`stats/db.py`, `ai/sideboard_manager.py`)**: Detecção dinâmica de partidas propensas a fadiga consultando a média real de turnos do oponente no SQLite (`get_average_match_length`), substituindo listas estáticas de classes.
  - _Avoid_: Tuplas fixas de classe, Suposição cega de arquétipo.
- **Dynamic World Pool Sampling (`ai/mcts/world_generator.py`)**: Amostragem de cartas no determinizador do ISMCTS orientada pelo banco oficial `fab_cards_db.json` e correspondência de classe/talentos, sem listas nominais hardcoded de heróis.
  - _Avoid_: Listas de nomes de heróis em if/else, Simulação restrita a heróis conhecidos.

- **Shadow Mode (Modo Sombra) (`ai/shadow_mode.py` - ADR-0013)**: Subsistema de interceptação passiva que compara predições locais do `simulate_step` com o estado real validado pelo backend, registrando as divergências em SQLite (`shadow_steps`) para quantificar a % de Fidelidade do Simulador.
  - _Avoid_: Modo espião, Teste cego online, Verificação manual de diff.
- **Golden Puzzles (Puzzles Dourados) (`tests/puzzles/` & `scripts/extract_puzzle.py`)**: Snapshots estáticos JSON extraídos do histórico do Shadow Mode contra humanos, usados como testes de regressão ("benchmark humano") para garantir que o bot descubra a mesma jogada ótima.
  - _Avoid_: Desafios randômicos, Mocks manuais sem extração de DB.

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
  - `stats/`: Cálculo de ELO com K-factor dinâmico, nomes canônicos e persistência transacional em SQLite3 WAL.
  - `ui/`: Interface gráfica Streamlit decomposta (`helpers.py` e 7 abas em `tabs/`).
  - _Avoid_: Monólito dividido, Pastas arbitrárias de código, Módulos dispersos.
- **Retrocompatibility Facades**: Módulos raízes enxutos (`bot_client.py`, `dashboard.py`, `deck_parser.py`, `stats_manager.py`, `ai/policy_engine.py`, `ai/mcts/__init__.py`) que re-exportam métodos e classes públicas dos subpacotes, preservando 100% de compatibilidade retroativa.
  - _Avoid_: Wrappers redundantes, Aliases soltos, Código duplicado.
- **Setup Templates (`setup_templates/`)**: Repositório central de patches e arquivos customizados que são injetados em clones limpos do Talishar e Talishar-FE para viabilizar integração com IA sem dependência de submódulos Git.
  - _Avoid_: Git Submodules, Forks do Talishar, Patches temporários.
- **Decks Directory (`decks/`)**: Diretório central e exclusivo para arquivos JSON de baralhos. Nenhum baralho é criado ou salvo dentro das pastas internas do Talishar.
  - _Avoid_: Pastas internas do Talishar, Decks temporários, Pastas avulsas.
- **Chess Advantage Tracker**: Componente visual do frontend (`ChessAdvantageTracker.tsx`) que exibe a barra de vantagem tática em tempo real no chat do Talishar.
  - _Avoid_: Barra de vida extra, Indicador genérico.
- **Elo Rating**: Sistema de ranqueamento ponderado em `stats_manager.py` para avaliação do nível competitivo dos decks e agentes.
  - _Avoid_: Pontuação simples, Leaderboard estático.
- **Environment Auto-Detection & Sanitizer (`scripts/prepare_environment.py`)**: Script de automação unificada que detecta o ambiente operacional (Linux vs WSL2), injeta templates, sincroniza upstream (`--update-upstream`) e sanitiza permissões sem vazamento de dados privados.
  - _Avoid_: Instalador manual, Setup script disperso.
- **Pre-Commit Verification & Privacy Guard (`scripts/sync_and_clean.sh`)**: Hook pré-commit que valida sincronização de templates, compilação do frontend Vite (`npx vite build`) e sintaxe Python, bloqueando vazamento de caminhos pessoais.
  - _Avoid_: Script de git simples, Limpador de logs.
- **Pré-Push CI Validator (`scripts/verify_ci.sh` & `.git/hooks/pre-push`)**: Validador executado automaticamente antes de cada `git push` que replica 100% da esteira do GitHub Actions (581 testes no Pytest, dry-run do ISMCTS, diff de templates e Vite build). Opera em modo incremental inteligente por padrão, pulando compilação de frontend e testes de código quando arquivos correspondentes não foram alterados, com suporte a `--force`.
  - _Avoid_: Validação manual remota, Bypass cego de testes, Push sem verificação, Recompilação desnecessária do Vite.
- **Training State Cleaner (`scripts/clean_training_state.py` & `scripts/manage_state.py --clean-training`)**: Utilitário de limpeza atômica e reset seguro de treinamento com backup automático comprimido (`data/backups/`). Elimina o Replay Buffer (`data/replay_buffer.npz`), trajetórias transitórias, métricas/épocas (`data/training_metrics.json`) e anomalias de divergência Sim2Real (`logs/sim2real_anomalies.jsonl` e tabela SQLite), prevenindo envenenamento de política (*Policy Poisoning*) após grandes atualizações de regras.
  - _Avoid_: Deleção manual avulsa de arquivos, Perda de histórico sem backup, Treino com buffer contaminado.
- **Tokens de Arena (Arena Tokens - Quicken / Frostbite / Inertia / Bloodrot Pox - CR 8.6)**: Objetos e auras criados na arena que modificam a economia de turnos (Quicken/Agility concedem Go Again gratuito), penalizam custos (Frostbite adiciona {r} por token), forçam descarte ao fundo do deck (Inertia anula Tempo Pivot) ou ameaçam dano terminal no fim do turno (Bloodrot Pox exige {r}{r}{r} para evitar perda de 2 HP).
  - _Avoid_: Marcadores soltos, Fichas genéricas, Auras não tipadas.
- **Supervisor de Liveness & Watchdog de Atividade Real (`ai/training/process_supervisor.py`)**: Monitor de integridade de processos de treinamento e arena que acompanha o avanço individual de cada partida (via incremento de logs e turnos de jogo). Substitui timeouts cegos de relógio de parede por encerramento cirúrgico exclusivo de salas estagnadas (>60s sem ação), permitindo que partidas saudáveis progridam naturalmente até a vitória/derrota.
  - _Avoid_: Timeout cego de relógio, Aborto prematuro de lote, Assassinato de partidas ativas.
- **Alocador Adaptativo de Threads CPU (`ai/training/orchestrator.py` & `bot_client.py`)**: Dimensionamento dinâmico de threads intra-operação do PyTorch (`torch.set_num_threads`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`) baseado no quociente de núcleos de CPU disponíveis dividido pelo total de bots concorrentes (`max(1, cpu_cores // total_active_bots)`). Erradica o *thread thrashing* e saturação de cache L1/L2 em WSL2 ao rodar múltiplos workers sem exigir poda de simulações MCTS.
  - _Avoid_: Thread thrashing, Saturação estática de threads, Poda arbitrária de simulações MCTS.
- **Fast Search & Anti-Blind-Grep (`scripts/fast_search.py` & `.agents/rules/search_guidelines.md`)**: Ferramenta e diretiva obrigatória para agentes de IA para busca de padrões com poda automática de diretórios pesados (`node_modules/`, `venv/`, `Talishar/Games/`, `build/`, `logs/`, `data/`), priorizando `git grep -n` e prevenindo travamentos de processo.
  - _Avoid_: Grep cego na raiz (`grep -r .`), Busca sem exclusão, Varredura recursiva de node_modules/venv.
- **Upstream Sincronizador & Changelog (`scripts/prepare_environment.py --update-upstream` & `docs/talishar_upstream_changelog.md`)**: Sistema de atualização automatizada que sincroniza Talishar e Talishar-FE com o upstream oficial, reaplica patches customizados de IA, reindexa o banco de cartas e registra a transição de versões e commits em markdown para os agentes.
  - _Avoid_: Git pull manual cego, Sobrescrita acidental de patches, Upstream drift.
- **Frontend Ads Proxy / BannerUnit Mock (`setup_templates/frontend/bannerUnit`)**: Mock headless do módulo de anúncios do Talishar-FE (`AdUnit.tsx` e `AdRailLayout.tsx`) para permitir compilações limpas e offline do frontend.
  - _Avoid_: Bloco de anúncio ativo, Bypass manual de dependências.
- **Palavras-Chave de Efeito CR 8.5 (CR Effect Keywords - `scripts/extract_cr_mechanics.py`)**: As 9 palavras-chave estruturais de efeito do Flesh and Blood (`clash`, `wager`, `amp`, `transcend`, `reload`, `freeze`, `intimidate`, `opt`, `charge`) mapeadas deterministamente na base semântica para consulta direta do MCTS e simulador.
  - _Avoid_: Efeitos de texto livre, Keywords não estruturadas, Parsing dinâmico em tempo de execução.
- **Combate contra Aliados & Anti-Gravy Bones (`ai/bot_runtime/choice_handler.py` & `ai/policy/defense_pruner.py`)**: Heurística de prioridade absoluta para destruição de aliados adversários recorrentes (+30.0 em modais de target para Riggermortis/Sawbones) e defesa estrita que impede ignorar ataques de aliados mesmo com On-Hit nulo.
  - _Avoid_: Ignorar dano de aliado, Alvo cego de herói em presença de aliados letais.
- **Plano de Prevenção de Blood Debt de Levia (`ai/hero_strategies/brute.py`)**: Modo tático (`LEVIA_BLOOD_DEBT_PREVENTION`) ativado sob acúmulo de cartas com Blood Debt na zona banida, reservando ataque de poder 6+ e pitch para desligar o dano no fim do turno e penalizando severamente seu uso em bloqueio (-40.0).
  - _Avoid_: Morte passiva por Blood Debt, Bloqueio com finalizador 6+ de Brute.
- **Análise de Anomalias de Partida (`scripts/analyze_match_anomalies.py`)**: Ferramenta analítica sobre `data/talishar_stats.db` para quantificação de vitórias bilaterais, overkills, empates, timeouts, partidas ultracurtas e calibração de multiplicadores dinâmicos.
  - _Avoid_: Diagnóstico manual cego, Telemetria não compilada.
- **Auto-Tuning Causal & Hand Value Conversion Rate (HVCR) (`ai/dynamic_rule_tuner.py` - ADR-0012)**: Mecânica de auto-tuning que diagnostica a causa real das derrotas com base na taxa de conversão de valor de mão (HVCR), separando perda por corrida de tempo de incapacidade de converter a mão, aplicando clamp estrito [0.85, 1.15] para eliminar o efeito espiral.
  - _Avoid_: Efeito espiral, Ajuste unidirecional de bloqueio, Punição cumulativa de derrotas.
- **Pitch Stacking & Stratified PER (`ai/mcts/world_generator.py` & `ai/experience_collector.py` - ADR-0012)**: Preservação da ordem exata de cartas pitchadas no fundo do deck simulado (`playerDeckBottom`) no ISMCTS e amostragem estratificada por herói no buffer de treino com atenuação de falsos blunders por reversão temporal de valor.
  - _Avoid_: Embaralhamento do pitch, Perda de ordem do fundo do deck, Buffer PER não estratificado.
- **Extração Zero-Copy de Vetor de Estado (`ai/model.py` & ADR-0014)**: Extração determinística do vetor de 832 dimensões diretamente sobre qualquer `collections.abc.Mapping` e tuplas (incluindo `ImmutableGameState`), eliminando por completo o ciclo de conversão `to_dict()` e o churn de freeze/unfreeze no MCTS.
  - _Avoid_: Freeze/unfreeze recursivo, Conversão to_dict em folha, Serialização em rollout.
- **Memoização de Folhas MCTS (`ai/mcts/standard_mcts.py` & ADR-0014)**: Cache determinístico indexado por `action_id` em `_batch_evaluate_leaves()` na profundidade 1 da árvore MCTS, colapsando simulações idênticas e executando um único forward pass somente para ações legais únicas.
  - _Avoid_: Reavaliação de folha idêntica, Forward repetido da mesma ação, Simulação redundante de nó.
- **Spooling Atômico de Trajetórias & Checkpoint Assíncrono (`ai/bot_runtime/match_tracker.py` & `ai/training/orchestrator.py` - ADR-0014)**: Arquitetura desacoplada de persistência (Abordagem A) onde bots clientes salvam apenas pequenos arquivos atômicos em `data/trajectories/traj_*.npz`, enquanto a gravação pesada de checkpoints mestre (`.pt` e `.npz`) é delegada para threads assíncronas no orquestrador a cada `save_interval_games`, eliminando contenção de disco e I/O bloqueante por época.
  - _Avoid_: buffer.save() em bot client, Releitura síncrona de buffer na época, Concorrência sobre replay_buffer.npz.
- **Thread-Batched Evaluator (`ai/mcts/batched_evaluator.py` & ADR-0014)**: Fachada multithread dinâmica que agrupa vetores de estado de múltiplos workers MCTS concorrentes em batches dinâmicos $[N, 832]$ para um único forward pass em GPU/PyTorch sob `torch.inference_mode()` e AMP FP16, despachando fatias resolvidas via `concurrent.futures.Future`.
  - _Avoid_: Forward individual por thread, Forward síncrono concorrente sem batching, Concorrência de GPU fragmentada.
- **Adaptive Mini-Batched MCTS (`ai/mcts/standard_mcts.py`)**: Divisão da busca MCTS em mini-batches dinâmicos (até 8 simulações) com backpropagação intermediária, preservando a aceleração de batching matricial e ao mesmo tempo garantindo que o PUCT adapte suas seleções com base em $Q(s, a)$ atualizados.
  - _Avoid_: Batch cego de todas as simulações sem atualização de Q, Simulação puramente estática.
- **Puzzles Táticos & Invariantes de Simulação (`tests/test_ismcts_tactical_puzzles.py` & `tests/test_game_simulator_invariants.py`)**: Suíte de integração e oráculos determinísticos que validam a convergência do MCTS (Mate em 1 / Sobrevivência letal) e invariantes matemáticas de conservação de zonas, pitch e combate sem necessidade de carregar a rede neural.
  - _Avoid_: Teste dependente de pesos aleatórios da rede, Avaliação não-determinística de árvore.
- **Poda Preventiva de Flick Knives (`ai/bot_runtime/phase_decider.py` & `ai/hero_strategies/assassin.py`)**: Validação a montante em conformidade estrita com CR 245 e `REMOVEINDICESIFACTIVECHAINLINK` do Talishar, exigindo adaga funcional não arremessada (`overlay=0`, `status != 0`, `isBroken=False`) que não seja o elo ativo de ataque na cadeia de combate, podando o equipamento com antecedência e prevenindo ativações inválidas e falhas de layers no motor.
  - _Avoid_: Ativação de Flick Knives sem adaga, Arremesso da adaga atacante atual.
- **Blindagem de Popups Multizone (`ai/bot_runtime/choice_handler.py`)**: Mecanismo que atribui penalidade severa (-500.0) a opções desabilitadas/arremessadas (`overlay=1`, `isBroken=True`) em popups `CHOOSEMULTIZONE` e emite `PASS` (Mode 99) em seleções facultativas (`MAYCHOOSEMULTIZONE`) quando todos os alvos potenciais foram destruídos.
  - _Avoid_: Seleção cega de adaga quebrada, Clique em overlay desabilitado.
- **Sincronização Sim2Real de Go-Again & Arsenal (`ai/game_simulator.py` & `ai/shadow_mode.py`)**: Integração de validação dinâmica contextual de Go-Again (`resolve_attack_go_again`) no `GameSimulator` para cartas condicionais (links dracônicos, combos, vermelhas) e suporte formal a jogadas a partir do Arsenal (Mode 5) e temporização de dano em Phase B no `Shadow Mode`, eliminando falsas divergências de estado.
  - _Avoid_: Go-Again estático incondicional, Tratamento de jogada de Arsenal como mão.
- **Telemetria Sim2Real em Tempo Real (`ai/training/process_supervisor.py` & `ai/training/orchestrator.py`)**: Monitoramento contínuo e não-bloqueante na CLI durante lotes de treino Sim2Real e Headless, exibindo a cada 8 segundos o progresso por sala (número da sala no Talishar, turno atual, HP relativo dos jogadores, indicador de pensamento MCTS) e notificação imediata de conclusão de partidas com placar e vencedor, eliminando cegueira operacional em partidas longas (como mirrors de Guardião).
  - _Avoid_: Execução silenciosa sem ticker, Polling bloqueante de logs na CLI, Espera cega até fim do lote.
- **Sincronização e Resolução de Fidelidade Sim2Real (`ai/policy/defense_pruner.py`, `ai/shadow_mode.py`, `ai/game_simulator.py`)**: Alinhamento estrito entre o simulador in-process e a engine PHP do Talishar: exclusão mandatória de cartas de reação de defesa (DR) da declaração de blocos em Phase B (CR 7.3.2), preservando-as exclusivamente para a etapa de reações em Phase D; unificação de chaves de arsenal (`playerArsenal` e `playerArse`); temporização correta de dano intermediário de ataque (`opponentHealth`); e modelagem precisa de satisfação de custos pendentes e consumo de AP na fase de pitch (`simulate_pitch`) e neutralização de AP indevido para equipamentos ativados (`simulate_attack`).
  - _Avoid_: Bloqueio com reações de defesa em Phase B, Divergência falsa de arsenal, Consumo prematuro de HP em ataque aberto.
- **1-Ply Memoized MCTS & Fast Immutability (`ai/mcts/ismcts.py`, `ai/mcts/state.py` & ADR-0016)**: Avaliação de candidatos legais em lote único antes do loop PUCT, reaproveitamento determinístico da raiz através de mundos de determinização e imutabilidade seletiva (`_from_frozen`), reduzindo latência do ISMCTS em 94.9% (de 534ms para 28.9ms p50) e forward passes por decisão de 154 para 5.
  - _Avoid_: Avaliação redundante de folha MCTS, Forward por simulação, Re-congelamento recursivo de tuplas.
- **Vetorização da SumTree (PER) & Dynamic Training Throughput (`ai/experience_collector.py`, `ai/training/orchestrator.py` & ADR-0017)**: Reconstrução em $O(N)$ nível a nível de SumTree com `set_all` (233x mais rápido), atualização de prioridades com erro temporal $|V_{pred} - V_{target}|$ e annealing de $\beta \to 1.0$, passos dinâmicos de gradiente e cache de templates de baralhos pré-compilados em `HeadlessSelfPlayLoop` (throughput elevado para 42.19 jogos/min).
  - _Avoid_: Rebuild de SumTree com loop Python O(N log N), Pesos PER sem atualização de TD-error, Gradient starvation no self-play.
- **Headless Arena, Suíço Oficial & Self-Play League (`stats/tournament_manager.py`, `ai/training/orchestrator.py`, `ui/tabs/tab_tournaments.py` & ADR-0018)**: Sistema completo de validação competitiva e pareamento suíço com desempates oficiais (Buchholz e Sonneborn-Berger), prevenção estrita de rematches, sistema de Byes (+3 pts), atualização de ELO em SQLite (`data/talishar_stats.db`), suporte a auto-jogo em memória (`execution_mode="headless"`) com rede oponente carregada (`opp_model`) e liga de self-play contra checkpoints históricos amostrados probabilisticamente.
  - _Avoid_: Pareamento aleatório sem desempate, Torneio restrito a subprocessos Talishar, Auto-jogo estritamente espelhado (self-play ingênuo sem oponentes históricos).
- **Sideboard Data-Driven & Incerteza Bayesiana / MC Dropout (`ai/model.py`, `ai/sideboard_manager.py`, `ai/policy/defense_pruner.py` & ADR-0019)**: Resolução de sideboard com detecção semântica dinâmica de arquétipos arcanos via metadados de herói (classes, tipos, texto), pontuação de equipamentos e armas por durabilidade (`battleworn`, `temper`) e conformidade com CR 2.8.2 e CR 3.0; e quantificação de incerteza Bayesiana no Value Head via Monte Carlo Dropout em lote único (`predict_value_with_uncertainty`), escalonando o orçamento MCTS adaptativo (até 2.0x) e reforçando a cautela defensiva contra apostas especulativas de Tempo Pivot.
  - _Avoid_: Listas nominais fixas de heróis arcanos, Checks nominais rígidos de equipamentos, Predição escalar cega sem incerteza.

---

## Domain: Torneios & Liga

- **Emparelhamento Suíço Oficial (`TournamentManager._generate_swiss_round` - ADR-0018)**: Algoritmo de geração de rodadas em `stats/tournament_manager.py` que ordena os competidores por pontuação acumulada, Buchholz, Sonneborn-Berger e vitórias antes de formar pares de força equivalente em modo `talishar` ou `headless` (com suporte a `opp_model` para ligas entre checkpoints).
  - _Avoid_: Chaveamento mata-mata simples, Pareamento aleatório por rodada, Round-robin disfarçado de suíço.
- **Desempate Buchholz e Sonneborn-Berger (`TournamentManager._calculate_tie_breakers` - ADR-0018)**: Critérios oficiais de desempate FIDE/LSS recalculados dinamicamente ao fim de cada rodada suíça: **Buchholz** soma a pontuação total de todos os oponentes enfrentados (*Strength of Schedule*), enquanto **Sonneborn-Berger (SB)** soma a pontuação integral dos oponentes derrotados mais 50% da pontuação dos oponentes com quem houve empate.
  - _Avoid_: Desempate por saldo de HP, Ordem alfabética em igualdade de pontos, Sorteio de posição na tabela.
- **Algoritmo Anti-Rematch (`stats/tournament_manager.py` - ADR-0018)**: Heurística gulosa com *lookahead* em `_generate_swiss_round` que consulta o grafo histórico `played_pairs` do torneio para proibir repetição de confrontos já disputados em rodadas anteriores, realizando fallback controlado apenas caso todos os candidatos restantes já tenham se enfrentado.
  - _Avoid_: Repetição livre de confrontos na mesma chave suíça, Pareamento sem verificação de histórico.
- **Byes de 3 Pontos (`stats/tournament_manager.py` - ADR-0018)**: Regra oficial para chaves com número ímpar de participantes que seleciona o competidor de menor pontuação que ainda não recebeu Bye (`had_bye`) e concede avanço automático na rodada com $+3$ pontos e $+1$ vitória oficial registrada no banco.
  - _Avoid_: Bye sem pontuação, Concessão repetida de Bye ao mesmo participante, Exclusão de jogador ímpar.



