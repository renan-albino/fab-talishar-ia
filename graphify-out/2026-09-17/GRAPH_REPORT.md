# Graph Report - fab-talishar-ia  (2026-09-17)

## Corpus Check
- Large corpus: 229 files · ~639,238 words. Semantic extraction will be expensive (many Claude tokens). Consider running on a subfolder.

## Summary
- 2256 nodes · 4276 edges · 155 communities (104 shown, 51 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 195 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Equipment Learning & Evaluation
- Bot Client & Runtime
- Deck Parsing & Validation
- Bot Client & Runtime
- Bot Client & Runtime
- Policy Decision Engine
- Neural Network Training Pipeline
- Card Transformer Architecture
- Tactical Action Pruners
- Tactical Action Pruners
- MCTS Tree & Search Nodes
- Game State Transition Simulator
- MCTS Tree & Search Nodes
- ISMCTS & World Sampling
- Bot Client & Runtime
- Neural Network Training Pipeline
- Hero Specific Strategies
- Hero Specific Strategies
- Policy Decision Engine
- ISMCTS & World Sampling
- Agent Skills & Automation
- Tactical Action Pruners
- Deck Parsing & Validation
- Bot Client & Runtime
- Tactical Action Pruners
- Hero Specific Strategies
- Card Transformer Architecture
- Policy Decision Engine
- Deck Parsing & Validation
- Deck Parsing & Validation
- Bot Client & Runtime
- Hero Specific Strategies
- Automated Test Suites
- Deck Parsing & Validation
- Hero Specific Strategies
- Neural Network Training Pipeline
- Bot Client & Runtime
- Hero Specific Strategies
- Hero Specific Strategies
- Hero Specific Strategies
- ISMCTS & World Sampling
- Neural Network Training Pipeline
- ELO Ranking & Tournaments
- Automated Test Suites
- ISMCTS & World Sampling
- Agent Skills & Automation
- Streamlit Telemetry Dashboard
- ELO Ranking & Tournaments
- Equipment Learning & Evaluation
- Hero Specific Strategies
- Hero Specific Strategies
- Hero Specific Strategies
- State Commit Release
- Agent Skills & Automation
- Hero Specific Strategies
- Hero Specific Strategies
- Infrastructure & Templates
- Hero Specific Strategies
- Hero Specific Strategies
- Policy Decision Engine
- Policy Decision Engine
- Neural Network Training Pipeline
- Semantics Disruption Semantics
- Deck Parsing & Validation
- Agent Skills & Automation
- Hero Specific Strategies
- Automated Test Suites
- Automated Test Suites
- Deck Parsing & Validation
- ISMCTS & World Sampling
- ISMCTS & World Sampling
- Deck Parsing & Validation
- Tactical Action Pruners
- Neural Network Training Pipeline
- Tactical Action Pruners
- ISMCTS & World Sampling
- ISMCTS & World Sampling
- Agent Skills & Automation
- Agent Skills & Automation
- Hero Specific Strategies
- Agent Skills & Automation
- Bot Client & Runtime
- ISMCTS & World Sampling
- Policy Decision Engine
- Infrastructure & Templates
- Deck Parsing & Validation
- Automated Test Suites
- Policy Decision Engine
- Card Transformer Architecture
- Card Transformer Architecture
- Automated Test Suites
- Automated Test Suites
- Hero Specific Strategies
- Hero Specific Strategies
- Context Constraint Chain
- Game State Transition Simulator
- Infrastructure & Templates
- Clean Hook Banner
- Automated Test Suites
- ELO Ranking & Tournaments
- Hero Specific Strategies
- Card Transformer Architecture
- Tactical Action Pruners
- Basehttprequesthandler Server Fabrary
- Infrastructure & Templates
- Mechanics Profile Main
- Automated Test Suites
- Agent Skills & Automation
- Bot Client & Runtime
- Start Status Entry
- Stop Status Entry
- Agent Skills & Automation
- Card Transformer Architecture
- Policy Decision Engine
- Deck Parsing & Validation
- Agent Skills & Automation
- Policy Decision Engine
- Policy Decision Engine
- Policy Decision Engine
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Bot Client & Runtime
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Infrastructure & Templates
- Entry Environment
- Frontend Entry
- Deck Parsing & Validation
- Streamlit Telemetry Dashboard
- Bot Client & Runtime

## God Nodes (most connected - your core abstractions)
1. `PolicyEngine` - 74 edges
2. `HeroStrategy` - 71 edges
3. `DummyBotClient` - 46 edges
4. `TalisharApiClient` - 44 edges
5. `get_hero_strategy()` - 42 edges
6. `FabBotClient` - 40 edges
7. `TurnPlan` - 36 edges
8. `MCTSEngine` - 28 edges
9. `TestTalisharApiClient` - 28 edges
10. `GameSimulator` - 25 edges

## Surprising Connections (you probably didn't know these)
- `__init__()` --calls--> `PolicyEngine`  [INFERRED]
  tests/test_cr_comprehensive_rules.py → ai/policy/engine.py
- `test_generic_pivot()` --calls--> `PolicyEngine`  [INFERRED]
  tests/test_jarl_marlinn_pruning.py → ai/policy/engine.py
- `test_jarl()` --calls--> `PolicyEngine`  [INFERRED]
  tests/test_jarl_marlinn_pruning.py → ai/policy/engine.py
- `test_marlinn()` --calls--> `PolicyEngine`  [INFERRED]
  tests/test_jarl_marlinn_pruning.py → ai/policy/engine.py
- `test_canonicalize_deck_name()` --calls--> `canonicalize_deck_name()`  [INFERRED]
  tests/test_stats_manager.py → stats/deck_names.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Issue Tracker Backend Adapters** — agents_skills_setup_matt_pocock_skills_issue_tracker_github, agents_skills_setup_matt_pocock_skills_issue_tracker_gitlab, agents_skills_setup_matt_pocock_skills_issue_tracker_local [EXTRACTED 1.00]
- **Ponytail Over-Engineering Elimination Suite** — agents_skills_ponytail_skill, agents_skills_ponytail_review_skill, agents_skills_ponytail_audit_skill, agents_skills_ponytail_debt_skill, agents_skills_ponytail_gain_skill, agents_skills_ponytail_help_skill [EXTRACTED 1.00]
- **Repo Engineering Skills Scaffolding** — agents_skills_setup_matt_pocock_skills_skill, agents_skills_setup_matt_pocock_skills_domain, agents_skills_setup_matt_pocock_skills_issue_tracker_github, agents_skills_setup_matt_pocock_skills_issue_tracker_gitlab, agents_skills_setup_matt_pocock_skills_issue_tracker_local, agents_skills_setup_matt_pocock_skills_triage_labels [EXTRACTED 1.00]
- **Architectural Decision Records Governance Suite** — docs_adr_adr_0001_modular_package_decomposition, docs_adr_adr_0002_parallel_ismcts_multithreading, docs_adr_adr_0003_concurrent_atomic_persistence_file_locks, docs_adr_adr_0004_arsenal_cr315_and_digging_mode, docs_adr_adr_0005_setup_templates_vs_git_submodules, docs_adr_adr_0006_asymmetric_distillation_mcts_visit_targets, docs_adr_adr_0007_card_transformer_and_generic_arena_semantics [EXTRACTED 1.00]
- **Tactical Decision Pruning Engine Framework** — docs_tactical_rules_attack_chain_sequencing, docs_tactical_rules_pitch_hierarchy, docs_tactical_rules_smart_blocking_pivot, docs_tactical_rules_strict_arsenal_pruning, context_tactical_pruning [EXTRACTED 1.00]
- **Neural MCTS Training & Inference Pipeline** — docs_adr_adr_0002_parallel_ismcts_multithreading, docs_adr_adr_0006_asymmetric_distillation_mcts_visit_targets, docs_adr_adr_0007_card_transformer_and_generic_arena_semantics, readme_hybrid_decision_engine [EXTRACTED 1.00]

## Communities (155 total, 51 thin omitted)

### Community 0 - "Equipment Learning & Evaluation"
Cohesion: 0.06
Nodes (63): fix_deck_obj(), main(), Any, Valida um único arquivo de deck JSON e opcionalmente aplica correções., validate_decks.py ================= Script utilitário para validar e corrigir…, Tenta corrigir inconformidades comuns em um deck JSON. Ações de autocorreção:…, validate_single_deck(), deck_manager (+55 more)

### Community 1 - "Bot Client & Runtime"
Cohesion: 0.06
Nodes (20): ai/talishar_api.py ================== Cliente HTTP para comunicação com as APIs…, requests, DummyBotClient, patch, tests/test_lobby_and_api_mock.py ================================ Testes…, Testa fallback de DEFAULT_BACKEND_URL quando config.settings falha., Mock completo do cliente de bot para testar lobby_manager isoladamente., Testes para resolução de ordem de turno e integração com o learner. (+12 more)

### Community 2 - "Deck Parsing & Validation"
Cohesion: 0.05
Nodes (27): IsPlayerAI(), ExitJsonResponse(), InitializeAuthenticatedJsonApi(), IsReplay(), ReadJsonBody(), ReadPostData(), WriteJsonResponse(), ApplyDeckAltArtOverride() (+19 more)

### Community 3 - "Bot Client & Runtime"
Cohesion: 0.07
Nodes (14): Any, Consulta o estado atual do jogo via polling rápido., Executa uma ação de jogo via ProcessInput.php., Injeta uma linha ou badge de avaliação no chat da partida., Cliente HTTP dedicado para interagir com o backend do Talishar., Cria uma nova sala de jogo no Talishar., Entra como Jogador 2 em uma sala existente., Consulta o estado do lobby para verificar se o oponente já entrou. (+6 more)

### Community 4 - "Bot Client & Runtime"
Cohesion: 0.06
Nodes (42): ref_appconstants, ref_button, ref_card, ref_gamestate, ref_gamestaticinfo, ref_initialgamestate, ref_interface_api_getlobbyrefresh_php, ref_player (+34 more)

### Community 5 - "Policy Decision Engine"
Cohesion: 0.05
Nodes (43): ai_policy_engine, pytest, Durante pivot com max_block_cards == 0, cartas da mão não bloqueiam, mas…, Testa ativação de habilidade de equipamento na Fase Principal (M)., Se houver carta no Arsenal e o oponente atacar com Command and Conquer, Crown…, Se a mão estiver disfuncional (3+ cartas sem nenhum pitch azul/amarelo para…, Garante que Boots of Omniward NUNCA é ativada no vazio quando opp_power <= 0 e…, Testa modificador dinâmico de custo de espada com a habilidade de compra da… (+35 more)

### Community 6 - "Neural Network Training Pipeline"
Cohesion: 0.08
Nodes (35): ai/trainer.py ============= Fachada retrocompatível para o subsistema de…, ai_training, ai/training =========== Pacote modular de orquestração e balanceamento de…, Any, ai/training/matchup_engine.py ============================= Gerenciador de…, Gerenciador de pareamento balanceado para treinamento autônomo. Gera ciclos…, RoundRobinMatchupEngine, ai/training/orchestrator.py ===========================… (+27 more)

### Community 7 - "Card Transformer Architecture"
Cohesion: 0.07
Nodes (32): ai/atomic_io.py =============== Utilitários de I/O atômico para evitar…, ai/blunder_reviewer.py ====================== Módulo de Revisão Automática de…, ai/dynamic_rule_tuner.py ======================== Auto-Tuning Dinâmico de…, ExperienceCollector / ReplayBuffer: Armazena trajetórias de partidas em memória…, ai_mcts, ai/model.py =========== FaBCardTransformerNetwork: Rede Neural com Atenção…, fcntl, numpy (+24 more)

### Community 8 - "Tactical Action Pruners"
Cohesion: 0.07
Nodes (31): EquipmentEvent, EquipmentLearningEngine, EquipmentTracker, get_equipment_learning_engine(), load_equipment_metadata(), Any, ai/equipment_learning.py ======================== Motor de Aprendizado e…, Motor persistente de aprendizado de equipamentos. Consolida métricas em… (+23 more)

### Community 9 - "Tactical Action Pruners"
Cohesion: 0.07
Nodes (21): FabBotClient, Retorna uma identificação legível e clara para o Jogador 1 ou 2., Calcula o índice de avaliação da posição (estilo Chess Eval +/-)., Extrai descrição detalhada da carta/arma atacante e status da Combat Chain., Pontua um candidato para escolha múltipla ou alvo de primeira tentativa., Ordena uma lista de candidatos do mais recomendado ao menos recomendado., Grava o arquivo JSON de métricas respeitando throttling de 1.5s ou mudança de…, __getattr__() (+13 more)

### Community 10 - "MCTS Tree & Search Nodes"
Cohesion: 0.09
Nodes (32): get_logger(), ai/logger.py ============ Logger centralizado do FAB AI Engine. Todos os…, Retorna um logger configurado com formato padronizado., ai/mcts ======= Módulo MCTS e ISMCTS para o FaB Talishar AI., _get_ismcts_worlds(), ai/mcts/ismcts.py ================= ISMCTSEngine: Information Set MCTS para…, Retorna número de mundos ISMCTS calculado por hardware scan no startup., ai/mcts/node.py =============== Nó da árvore MCTS para busca AlphaZero / PUCT. (+24 more)

### Community 11 - "Game State Transition Simulator"
Cohesion: 0.10
Nodes (32): GameSimulator, _get_card_semantics(), _get_cards_db(), Any, ndarray, ai/game_simulator.py ==================== Simulador determinístico de regras e…, Motor de transição determinística para rollouts e expansão de folhas do MCTS., Extrai metadados táticos e semânticos de uma carta consultando… (+24 more)

### Community 12 - "MCTS Tree & Search Nodes"
Cohesion: 0.09
Nodes (21): MCTSNode, Nó da árvore MCTS. Atributos: prior (float) : Probabilidade da POLICY HEAD para…, PUCT(s,a) = Q(s,a) + c_puct × P(s,a) × √N(s) / (1 + N(s,a)), MCTSEngine, Any, FaBPolicyValueNetwork, ndarray, Avalia estado raiz. Retorna priors uniformes e value=0 sem modelo. (+13 more)

### Community 13 - "ISMCTS & World Sampling"
Cohesion: 0.06
Nodes (32): PolicyEngine, Extrai e normaliza atributos de cartas a partir do snapshot e banco de dados., Regra oficial FaB: Evos do Banish só ganham a opção de serem jogados como…, Seleciona a melhor combinação de bloqueadores otimizando breakpoints e…, Seleciona a melhor carta para o Arsenal respeitando a proibição de pitch e modo…, Motor de Decisão Híbrido (ISMCTS / MCTS + Rede Neural Policy-Value +…, test_policy_engine_integration(), Testa se a IA decide absorver dano de ataque quando possui cartas de block 2 e… (+24 more)

### Community 14 - "Bot Client & Runtime"
Cohesion: 0.06
Nodes (6): ref_components_loadingscreen_loadingscreen, ref_errorpage, ref_hooks_useknownsearchparams, Index, ./routes/index/Index, router

### Community 15 - "Neural Network Training Pipeline"
Cohesion: 0.09
Nodes (18): get_global_buffer(), GPUTrainingOrchestrator, Any, device, FaBPolicyValueNetwork, Carrega métricas persistidas em disco., Substitui NaN e inf por 0.0 recursivamente para garantir conformidade JSON., Salva métricas e checkpoints em disco. (+10 more)

### Community 16 - "Hero Specific Strategies"
Cohesion: 0.13
Nodes (19): ai/hero_strategies/assassin.py ============================== Estratégia para a…, is_resource_or_gem_card(), ai/hero_strategies/base.py ========================== Definição base de…, CR 3.1.5: Recursos e Gemas NUNCA podem ser colocados no Arsenal., ai/hero_strategies/brute.py =========================== Estratégia para a…, ai/hero_strategies/guardian.py ============================== Estratégia para…, ai/hero_strategies/illusionist.py ================================= Estratégia…, ai/hero_strategies/__init__.py ============================== Pacote modular de… (+11 more)

### Community 17 - "Hero Specific Strategies"
Cohesion: 0.07
Nodes (11): HeroStrategy, Any, Pontuação tática para ativar habilidades de equipamento delegada ao…, Calcula score de utilidade para colocar carta no Arsenal no fim do turno (CR…, Delega para knapsack_solver.solve_knapsack_turn., Delega para knapsack_solver.calculate_card_opportunity_cost., Delega para knapsack_solver.calculate_hand_conversion_potential., Delega para turn_planner.should_trigger_survival_block. (+3 more)

### Community 18 - "Policy Decision Engine"
Cohesion: 0.12
Nodes (24): Any, ai/policy/arsenal_pruner.py =========================== Módulo de poda e…, Seleciona a melhor carta para colocar no Arsenal no fim do turno. Regra Oficial…, select_arsenal_card(), calculate_available_resources(), extract_card_info(), get_all_known_zone_cards(), get_weapon_cost() (+16 more)

### Community 19 - "ISMCTS & World Sampling"
Cohesion: 0.10
Nodes (30): _bar(), _build_settings(), _compute_batch_size(), _compute_buffer_capacity(), _compute_hidden_dim(), _compute_ismcts_worlds_from_latency(), _compute_mcts_sims(), _compute_num_res_blocks() (+22 more)

### Community 20 - "Agent Skills & Automation"
Cohesion: 0.11
Nodes (27): check_port(), check_writable(), get_container_runtime(), main(), print_report(), probe_http_service(), Any, Executa todas as verificações de saúde do ecossistema FaB Talishar AI. (+19 more)

### Community 21 - "Tactical Action Pruners"
Cohesion: 0.12
Nodes (27): Any, ai/policy/attack_pruner.py ========================== Módulo de poda de…, Seleciona o melhor candidato de ataque (da mão, equipamento, arma, arsenal,…, select_best_attack(), ArenaThreatContext, build_arena_threat_context(), CardSemanticProfile, _load_semantics_db() (+19 more)

### Community 22 - "Deck Parsing & Validation"
Cohesion: 0.11
Nodes (18): Any, Gera pareamento para a rodada suíça ordenando por pontuação., Executa uma partida de torneio lançando os bots em subprocessos., Atualiza a tabela de classificação com base no resultado da partida., Executa todas as partidas pendentes do torneio em sequência., Salva a tabela de classificação e histórico de confrontos em JSON., Gera uma matriz de vitórias/derrotas entre todos os decks., Lê todos os decks JSON disponíveis no diretório. (+10 more)

### Community 23 - "Bot Client & Runtime"
Cohesion: 0.09
Nodes (23): ai_bot_runtime, check_and_handle_anti_loop(), handle_popup_and_choices(), rank_choice_candidates(), Trata modais, popups, inputs de nome, multichoose e escolhas de zona/texto., Pontua um candidato para escolha múltipla ou alvo de primeira tentativa., Ordena uma lista de candidatos do mais recomendado ao menos recomendado., Rastreia histórico de fases e estados repetidos, aplicando ações forçadas de… (+15 more)

### Community 24 - "Tactical Action Pruners"
Cohesion: 0.09
Nodes (22): handle_reaction_phase(), Gerencia reações de ataque/defesa/instants da mão e equipamentos com podas…, MockReactionClient, tests/test_combat_rules_pruning.py ================================== Testes…, Overpower (CR 7.4.2b): Se o ataque possuir Overpower, nenhuma combinação de…, Piercing (CR 8.5.21): Ataques com Piercing ganham +1 de dano se forem…, Overpower (CR 7.4.2b, CR 8.3.22): "This can't be defended by more than one…, Phantasm (CR 7.4.4): Se o ataque oponente possui Phantasm (ex: Illusionist… (+14 more)

### Community 25 - "Hero Specific Strategies"
Cohesion: 0.10
Nodes (22): AssassinStrategy, Estratégia especializada para a classe Assassin (Arakni, Uzuri, Nuu, Dr.…, get_hero_strategy(), Fábrica canônica de estratégias de herói de Flesh and Blood. Hierarquia em 3…, RangerStrategy, Estratégia especializada para a classe Ranger. Prioriza disparo de flechas a…, __getattr__(), Módulo de Inteligência Artificial para Flesh and Blood (FaB Talishar). Inclui… (+14 more)

### Community 26 - "Card Transformer Architecture"
Cohesion: 0.08
Nodes (19): Any, device, ndarray, Amostra um batch balanceado com suporte opcional a Importance Sampling (Schaul…, Redimensiona a capacidade máxima do buffer preservando os dados já coletados., Carrega e remove arquivos compactos de trajetória gerados concorrentemente por…, Adiciona trajetória completa ao buffer calculando Recompensa Densa (Reward…, ReplayBuffer (+11 more)

### Community 27 - "Policy Decision Engine"
Cohesion: 0.07
Nodes (25): Retorna um mapa consolidado de todas as cartas em todas as zonas do jogo., fixture, Garante que Hammerhead não é ativado sem flecha no Arsenal para evitar…, Valida a exceção tática: Hammerhead PODE e DEVE ser ativado sem flecha no…, Valida que o policy_engine gera candidatos de ataque para Aliados em jogo…, Garante que a lógica do canhão reside em…, Valida a regra oficial de Teklo Leveler (EVO009) para 0, 1, 2, 3 e 4 Evos…, Valida que Oscilio prioriza Astral Bridge no ataque e não bloqueia com peças… (+17 more)

### Community 28 - "Deck Parsing & Validation"
Cohesion: 0.26
Nodes (25): apply_backend_templates(), apply_custom_templates(), apply_frontend_templates(), check_docker(), check_unmapped_changes(), ensure_directories(), ensure_frontend_dependencies(), ensure_git_hooks() (+17 more)

### Community 29 - "Deck Parsing & Validation"
Cohesion: 0.09
Nodes (25): Registra resultado de partida com exclusão mútua estrita (file_lock) para…, update_match_result(), Testa o cálculo de ELO acelerado (K=48) e registro de vitórias contra humanos…, test_human_elo_bonus_and_stats(), Valida que vitórias com vida intacta (40 HP) em 22 e 25 turnos são registradas…, test_gravy_bones_shutout_win_preservation(), fixture, Configura um arquivo temporário de stats para isolar os testes. (+17 more)

### Community 30 - "Bot Client & Runtime"
Cohesion: 0.12
Nodes (21): check_stalemate_and_timeout(), Verifica condições de empate técnico (stalemate), fadiga estagnada ou estouro…, Atualiza métricas de dano causado e recebido e dispara badge de avaliação no…, track_tick_health_and_damage(), classify_chess_move(), evaluate_board_state(), format_attack_chat_message(), format_html_line() (+13 more)

### Community 31 - "Hero Specific Strategies"
Cohesion: 0.09
Nodes (10): Any, Habilidade ativada de Teklovossen: {r}{r}: Bane um card Evo da mão. Se o fizer,…, Estratégia de jogo para Professor Teklovossen e Teklovossen, Esteemed Magnate.…, Avaliação de Arsenal especializada para Teklovossen: Permite e prioriza cartas…, Verifica se a habilidade de Teklovossen ({r}{r}: Bane Evo da mão, compra carta)…, Regra oficial Teklovossen: equipar Evo da zona banida é jogado como Instant se…, Preservação Sagrada dos Evos com TEMPER: não queimar a última defesa de 1 que…, TeklovossenStrategy (+2 more)

### Community 32 - "Automated Test Suites"
Cohesion: 0.10
Nodes (9): fast_sleep(), MockClient, fixture, Elimina esperas por sleep durante os testes para execução instantânea., Mock leve de FabBotClient para isolamento e testes unitários rápidos., Testes para ordenação de opções em rank_choice_candidates., Testes para handle_block_phase: integração com plano de turno, bloqueios e…, TestPhaseDeciderBlock (+1 more)

### Community 33 - "Deck Parsing & Validation"
Cohesion: 0.20
Nodes (20): atomic_json_save(), Salva dados JSON de forma atômica usando write-to-tmp + rename., canonicalize_deck_name(), consolidate_deck_stats(), get_expected_starting_health(), stats/deck_names.py =================== Normalização de nomes de decks,…, Compila e unifica entradas duplicadas (ex: Marlinn e marlinn, dash_io e Dash…, Retorna o total de vida inicial esperado para o deck (40 para CC, 20 para… (+12 more)

### Community 34 - "Hero Specific Strategies"
Cohesion: 0.10
Nodes (11): HalaStrategy, KassaiStrategy, Estratégia especializada para Kassai (Cintari Sellsword / Golden Sand). Foco em…, Habilidade ativada de Kassai of the Golden Sand: Concede o efeito de que o…, Estratégia especializada para a classe Warrior. Prioriza o ataque de arma como…, Estratégia especializada para Hala, Bladesaint of the Vow. Foco absoluto em…, WarriorStrategy, Testa que os heróis identificados resolvem para suas classes específicas com… (+3 more)

### Community 35 - "Neural Network Training Pipeline"
Cohesion: 0.13
Nodes (17): FaBCardTransformerNetwork, Any, Converte o estado do Talishar em um vetor contíguo de 800 dimensões (Flat-…, Rede Neural Dual-Head com Atenção Carta-a-Carta e Contexto Global. Utiliza…, tests/test_model.py =================== Testes unitários canônicos para o motor…, Testa que a ordem das cartas da mão (slots 0 a 7 que pertencem à Zone 0) é…, Testa que se o checkpoint for inválido ou corrompido, create_model JAMAIS o…, Testa predição vetorizada em batch para múltiplos estados simultâneos. (+9 more)

### Community 36 - "Bot Client & Runtime"
Cohesion: 0.10
Nodes (20): Any, Analisa os passos de uma trajetória e calcula pesos de prioridade para PER.…, review_trajectory_for_blunders(), choose_first_player(), get_opponent_info(), Consulta o modelo de aprendizado de ordem de turno e envia a escolha., Lado Host aguardando Jogador 2 no lobby, dado, sideboard e início da partida., Configura e conecta a sala para o bot (seja como Host ou Join). (+12 more)

### Community 37 - "Hero Specific Strategies"
Cohesion: 0.17
Nodes (19): get_multipliers_for_hero(), Retorna os multiplicadores calibrados para o herói ou arquétipo especificado.…, calculate_card_opportunity_cost(), calculate_hand_conversion_potential(), Any, ai/hero_strategies/knapsack_solver.py =====================================…, Calcula o Custo de Oportunidade Tático de uma carta (Felt Table & AI…, Calcula o potencial ofensivo de dano e sinergia que a mão atual consegue… (+11 more)

### Community 38 - "Hero Specific Strategies"
Cohesion: 0.11
Nodes (6): GuardianStrategy, JarlStrategy, Estratégia especializada para a classe Guardian. Prioriza ataques pesados de…, Preservação de pitch azul para Guardião/Jarl quando há apenas 1 azul na mão., Estratégia especializada para Jarl Vetreiði (Guardião Elemental de Terra e…, test_turn_plan_systems()

### Community 39 - "Hero Specific Strategies"
Cohesion: 0.11
Nodes (5): MarlynnStrategy, Any, Habilidade ativada de Marlynn, Treasure Hunter: Destrói 1 Gold para carregar…, Validação e pontuação especializada para Hammerhead, Harpoon Cannon. Regra FaB…, Estratégia especializada para Marlynn, Treasure Hunter (Ranger / Pirata).…

### Community 40 - "ISMCTS & World Sampling"
Cohesion: 0.13
Nodes (11): ai/ismcts_logger.py =================== Logger estruturado para decisões do…, ai/sideboard_manager.py ======================= Gerenciador de resolução e…, datetime, extract_from_local(), json, extract_ability_costs(), main(), scripts/extract_ability_costs.py ================================ Extrai os… (+3 more)

### Community 41 - "Neural Network Training Pipeline"
Cohesion: 0.17
Nodes (16): dashboard.py - Orquestrador Principal da Interface Gráfica Streamlit do FaB…, streamlit, get_cached_stats_data(), get_total_training_games(), cache_data, ui/helpers.py - Funções de Cache de Alta Performance e Utilitários…, Lê rapidamente o total de partidas do arquivo de métricas sem instanciar o…, Retorna dados de estatísticas e ELO com cache TTL. (+8 more)

### Community 43 - "Automated Test Suites"
Cohesion: 0.16
Nodes (10): Any, ai/common/converters.py ======================= Utilitários universais de…, Converte com segurança strings, None, floats ou valores anômalos ('NaN',…, Garante que se val for None ou não for dicionário retorne `{}`., Garante retorno de string limpa sem lançar exceções., safe_dict(), safe_int(), safe_str() (+2 more)

### Community 44 - "ISMCTS & World Sampling"
Cohesion: 0.14
Nodes (17): pandas, tests/test_ui_modules.py - Testes unitários para a arquitetura modular da UI…, Valida a importação de todos os submódulos e funções exportadas do pacote ui., Valida funções de leitura otimizada de cauda (tail) e contagem de linhas., Valida os perfis sugeridos de treinamento em modo equilibrado e turbo., test_ui_helpers_tail_and_count(), test_ui_helpers_training_profile(), test_ui_imports() (+9 more)

### Community 45 - "Agent Skills & Automation"
Cohesion: 0.16
Nodes (16): main(), print_summary(), Any, Etapa 2: Sanidade de importação das fachadas do sistema e símbolos fundamentais., Etapa 3: Execução rápida da suíte essencial de testes automatizados com pytest., run_smoke_tests.py ================== Bateria rápida de Smoke Tests para o…, Renderiza painel terminal com sumário executivo e colorido dos smoke tests., Etapa 1: Validação de sintaxe com py_compile em todos os arquivos Python. (+8 more)

### Community 46 - "Streamlit Telemetry Dashboard"
Cohesion: 0.22
Nodes (16): _ai_watcher_loop(), create_human_vs_bot_match(), ensure_ai_watcher_running(), is_backend_running(), is_frontend_running(), _is_port_open(), Any, Cria uma partida no backend do Talishar para o jogador humano (Player 1) e… (+8 more)

### Community 47 - "ELO Ranking & Tournaments"
Cohesion: 0.14
Nodes (13): ref_app_hooks, ref_app_store, ref_chatbox_module_css, ref_chatinput_chatinput, ref_features_options_constants, ref_gamelogmessages, ref_hooks_usesetting, ref_react (+5 more)

### Community 48 - "Equipment Learning & Evaluation"
Cohesion: 0.18
Nodes (11): DelimStringContains(), isBannedInFormat(), IsCardBanned(), isClashLegal(), isSpecialUsePromo(), isUnimplemented(), ProcessCard(), ProcessEquipment() (+3 more)

### Community 49 - "Hero Specific Strategies"
Cohesion: 0.13
Nodes (6): Delega para turn_planner.analyze_turn_plan., Avalia taticamente jogar cartas de zonas específicas (Arsenal, Banish,…, IllusionistStrategy, Estratégia especializada para a classe Illusionist (Prism, Dromai, Enigma,…, Plano tático de ação para o turno atual. Coordena decisões ofensivas e…, TurnPlan

### Community 50 - "Hero Specific Strategies"
Cohesion: 0.12
Nodes (10): DashIOStrategy, MechanologistStrategy, Any, Habilidade de Dash IO: olhar o topo do deck para jogar itens como Instant., Estratégia especializada para a classe Mechanologist (Dash, Maxx, Teklovossen,…, Estratégia especializada para Dash I/O. Foco absoluto em itens com Crank (Boom…, Garante que DashIOStrategy, Arakni e Gravy aceitam hand_attacks sem erro de…, Testa heurísticas de Dash I/O (Mechanologist / Items com Crank). (+2 more)

### Community 51 - "Hero Specific Strategies"
Cohesion: 0.12
Nodes (8): GravyBonesStrategy, MerchantStrategy, Any, Estratégia especializada para a classe Merchant / Bard / Misc (Genis, Kavdaen,…, Estratégia especializada para Gravy Bones, Shipwrecked Looter (Pirata /…, Rastreia detalhadamente as 15 cópias de aliados do baralho do Gravy Bones.…, Testa heurísticas de Gravy Bones e Mario (Assassin / Pirate)., test_gravy_bones_and_mario_heuristics()

### Community 52 - "State Commit Release"
Cohesion: 0.26
Nodes (16): auto_release_on_commit(), download_release(), export_state(), format_size(), get_release_notes(), import_state(), init_checkpoint(), install_git_hook() (+8 more)

### Community 53 - "Agent Skills & Automation"
Cohesion: 0.16
Nodes (12): main(), print_table(), Any, Executa o benchmark para um motor específico (MCTS ou ISMCTS)., benchmark_mcts.py ================= Benchmark de vazão e latência para os…, Imprime tabela formatada de resultados do benchmark., run_benchmark_for_engine(), _execute_search() (+4 more)

### Community 54 - "Hero Specific Strategies"
Cohesion: 0.15
Nodes (16): Setup Matt Pocock Skills Agent Config, Domain Documentation Convention, Domain Context Layout Strategy, GitHub Issue Tracker Adapter, GitHub CLI Operations, GitHub Wayfinding Operations, GitLab Issue Tracker Adapter, GitLab CLI Operations (+8 more)

### Community 55 - "Hero Specific Strategies"
Cohesion: 0.13
Nodes (7): Habilidade de início da fase de ação de Vynnset: Bane uma carta da mão para…, Estratégia especializada para a classe Runeblade (Viserai, Chane, Briar,…, Estratégia especializada para Vynnset, Iron Maiden. Sinergia com Shadow e…, RunebladeStrategy, VynnsetStrategy, Testa heurísticas de Vynnset (Shadow Runeblade / Rune Gate)., test_vynnset_heuristics()

### Community 56 - "Infrastructure & Templates"
Cohesion: 0.12
Nodes (14): ref_components_adblockingrecovery, ref_components_cookieconsent, ref_components_footer_footer, ref_components_header_languageselector, ref_components_sessionrecovery, ref_features_api_apislice, ref_header_module_scss, ref_hooks_useauth (+6 more)

### Community 57 - "Hero Specific Strategies"
Cohesion: 0.14
Nodes (15): load_multipliers(), Any, Carrega o mapa de multiplicadores com cache em memória baseado em mtime., Lê o histórico de partidas do stats_manager e atualiza gradualmente os…, sync_multipliers_with_stats(), get_stats_data(), Lê os dados de estatísticas protegendo contra concorrência com file_lock., Reinicializa todos os ratings de ELO para 1200 e zera as métricas de partidas,… (+7 more)

### Community 58 - "Hero Specific Strategies"
Cohesion: 0.14
Nodes (5): OscilioStrategy, Estratégia especializada para a classe Wizard (Kano, Iyslander, Verdance,…, Habilidade de Oscilio: Bane uma carta de ação da mão para jogar cartas do…, Estratégia especializada para Oscilio, Constella Intelligence / Forked…, WizardStrategy

### Community 59 - "Policy Decision Engine"
Cohesion: 0.15
Nodes (3): parametrize, Testes para score_choice_candidate em diferentes cenários e modais., TestScoreChoiceCandidate

### Community 60 - "Policy Decision Engine"
Cohesion: 0.15
Nodes (12): ai_hero_strategies, Valida retrocompatibilidade com o backend Talishar enviando arsenal como…, Valida que para heróis Brute (Intellect 3), o Modo Cavar ativa com len(hand) >=…, Valida que para heróis com Intellect 5, o Modo Cavar ativa com len(hand) >= 4., run_tests(), test_arsenal_pruning(), test_digging_mode_dynamic_intellect_brute(), test_digging_mode_dynamic_intellect_high() (+4 more)

### Community 61 - "Neural Network Training Pipeline"
Cohesion: 0.22
Nodes (13): cache_resource, get_cached_saved_decks(), get_gpu_info(), get_orchestrator(), get_suggested_training_profile(), Calcula parâmetros de treinamento sugeridos: - mode='balanced': ~75-80% de…, Detecta GPU via nvidia-smi em ~50ms sem importar torch. Fallback para torch se…, Carrega o GPUTrainingOrchestrator de forma lazy apenas quando a aba de treino… (+5 more)

### Community 62 - "Semantics Disruption Semantics"
Cohesion: 0.21
Nodes (13): classify_on_hit_disruption(), extract_card_semantics(), identify_arena_item_aura_effects(), main(), parse_on_hit_damage_from_php(), parse_php_match_dictionaries(), Any, Identifica dano adicional On-Hit a partir de ItemAbilities.php, CardLogic.php e… (+5 more)

### Community 63 - "Deck Parsing & Validation"
Cohesion: 0.24
Nodes (11): calculate_elo_ratings(), calculate_k_factor(), expected_score(), stats/elo.py ============ Funções matemáticas puras para cálculo de rating ELO:…, Calcula a probabilidade esperada de vitória do jogador A contra B. Formula: 1 /…, Calcula o K-factor dinâmico para atualização de ELO. - Recompensa acelerada de…, Calcula novos ratings ELO para P1 e P2 a partir do resultado da partida:…, stats_manager.py ================ Fachada retrocompatível para o pacote modular… (+3 more)

### Community 64 - "Agent Skills & Automation"
Cohesion: 0.19
Nodes (13): Ponytail Audit Skill, Whole-Repo Over-Engineering Audit, Ponytail Debt Skill, Shortcut Debt Ledger Harvesting, Ponytail Gain Skill, Ponytail Impact Scoreboard, Ponytail Help Skill, Ponytail Modes Reference Card (+5 more)

### Community 65 - "Hero Specific Strategies"
Cohesion: 0.21
Nodes (7): Any, Registra o resultado da partida para calibrar o aprendizado., Gerencia estatísticas de vitórias/partidas de 'Go First' vs 'Go Second' por…, Retorna 'Go First' ou 'Go Second' com base no modelo aprendido e priors de FaB.…, TurnOrderLearner, Verifica se heróis de setup (Dash IO, Vynnset, Teklovossen) escolhem 'Go First'…, test_turn_order_learner_priors()

### Community 67 - "Automated Test Suites"
Cohesion: 0.15
Nodes (8): tests/test_cr_comprehensive_rules.py ==================================== Suíte…, CR 7.4.2b: 'An attack with overpower cannot be defended by more than 1 action…, CR 4.3.2 / 4.4.3f: Para heróis com Intelecto 3 (Rhinar, Kayo), o Modo Cavar…, CR 7.4.2a / 7.4.2d / 8.3.4b: Sob ataque com Dominate onde uma carta da mão já…, test_cr_arsenal_reaction_allowed_under_dominate(), __init__(), test_cr_digging_mode_dynamic_intellect(), test_cr_overpower_allows_arsenal_action_block()

### Community 68 - "Deck Parsing & Validation"
Cohesion: 0.15
Nodes (6): Valida que quando ambos os decks esgotam e não há mudança de vida por 3 turnos,…, Valida encerramento imediato se ambos os decks e mãos estão totalmente vazios…, Valida o Hard Cap de turnos para evitar loops infinitos., Valida que Jarl NUNCA equipa uma arma 2H junto com um escudo (CR 2.8.2 e CR…, Se o deck tiver apenas uma arma 2H e um escudo (sem arma 1H), o escudo não pode…, TestSideboardAndStalemate

### Community 69 - "ISMCTS & World Sampling"
Cohesion: 0.18
Nodes (7): ISMCTSLogger, Any, Carrega todas as entradas do arquivo JSONL. Retorna lista de dicts (vazia se…, Retorna as últimas `n` entradas do log., Logger thread-safe (append-only) para decisões do ISMCTS. Uso: from…, Escreve uma entrada de decisão ISMCTS no arquivo JSONL. Args: ismcts_log : Dict…, Atualiza room_id e hero do logger (chamado após o sideboard).

### Community 70 - "ISMCTS & World Sampling"
Cohesion: 0.23
Nodes (8): ISMCTSEngine, _evaluate_world(), Any, FaBPolicyValueNetwork, ndarray, Executa MCTSEngine em um mundo determinizado com batch leaf evaluation. Retorna…, Information Set MCTS para Flesh and Blood (informação imperfeita). Estratégia:…, Executa ISMCTS e retorna (best_idx, policy_dist, ismcts_log). Fluxo por mundo:…

### Community 71 - "Deck Parsing & Validation"
Cohesion: 0.20
Nodes (10): html, get_available_rooms(), cache_data, fragment, ui/tabs/tab_arena.py - Aba 2: Arena de Bots & Simulação Visual. Gerencia o…, Detecta salas ativas ou arquivadas na pasta logs/., Renderiza a Aba 2: Arena de Bots & Simulação., Fragmento que atualiza a cada 3 segundos o tabuleiro visual e feed de ações da… (+2 more)

### Community 73 - "Neural Network Training Pipeline"
Cohesion: 0.20
Nodes (10): file_lock(), Context manager para exclusão mútua entre processos via fcntl.flock., Context manager de file_lock reentrante para o mesmo thread/processo. Evita…, Limpa e reinicializa os dados de estatísticas com proteção de lock., Resolve dinamicamente o caminho do arquivo de estatísticas considerando…, reset_stats(), _resolve_stats_file(), stats_file_lock() (+2 more)

### Community 74 - "Tactical Action Pruners"
Cohesion: 0.22
Nodes (11): Arsenal Zone, Pitch Mechanism & Resource Generation, Tactical Decision Pruning, ADR-0004: Strict Arsenal Pruning CR 3.1.5 & Digging Mode, Digging Mode Heuristic CR 4.3.2, Strict CR 3.1.5 Arsenal Pruning, tactical_rules.md: Tactical Decision Pruning Architecture, Attack Chain Sequencing & Go Again Heuristics (+3 more)

### Community 75 - "ISMCTS & World Sampling"
Cohesion: 0.20
Nodes (11): Information Set Monte Carlo Tree Search (ISMCTS), ADR-0002: Parallel ISMCTS Multithreading, Independent World Determinization with ThreadPoolExecutor, ADR-0006: Asymmetric Policy Distillation, Dense Auxiliary Targets KataGo Methodology, MCTS Visit Distribution Policy Distillation, README.md: FaB Talishar AI Engine & Dashboard, Dynamic Training Profiles (Balanced vs Turbo) (+3 more)

### Community 76 - "ISMCTS & World Sampling"
Cohesion: 0.31
Nodes (10): analyze(), _bar_h(), _divider(), _histogram(), main(), scripts/analyze_ismcts.py ========================== Analisador local de…, Barra horizontal ASCII proporcional., Histograma ASCII horizontal para uma lista de floats [0, 1]. (+2 more)

### Community 77 - "Agent Skills & Automation"
Cohesion: 0.20
Nodes (10): Ask Matt Agent Configuration, Phase Boundaries Guide, Phase Boundary Decision Principle, Five Phase Boundary Options, Ask Matt Skill, Idea to Ship Flow, Engineering Skills Router, Grill Me Agent Configuration (+2 more)

### Community 78 - "Agent Skills & Automation"
Cohesion: 0.20
Nodes (10): SKILL.md: spec-audit, Spec Decomposition Axis, Standards Audit Axis, Two-Axis Audit Pattern, AGENTS.template.md: Agent Rules Template, Multi-Agent Parallelism Guidelines, Ponytail Protocol Rules, Workspace Editing Conventions (+2 more)

### Community 79 - "Hero Specific Strategies"
Cohesion: 0.22
Nodes (3): BruteStrategy, Estratégia especializada para a classe Brute. Foco em manter cartas de poder 6+…, Retorna o Intelecto do herói Brute (CR 4.3.2), padrão 3 para heróis Brute…

### Community 80 - "Agent Skills & Automation"
Cohesion: 0.20
Nodes (10): ADR-0003: Concurrent Atomic Persistence & File Locks, Write-to-Temp and Atomic Rename Pattern, Reentrant Interprocess Mutex via fcntl.flock, ADR-0005: Setup Templates vs Git Submodules, Declarative Patch Injection via setup_templates SSOT, domain.md: Agent Domain Guide, Canonical Glossary Rule, Setup Templates Synchronization Check (+2 more)

### Community 81 - "Bot Client & Runtime"
Cohesion: 0.20
Nodes (8): ref_classnames, ref_formik, ref_interface_api_getlobbyinfo_php, ref_react_icons_fa, ref_react_icons_hi, ref_react_icons_md, ref_stickyfooter_module_css, DeckSize

### Community 83 - "Policy Decision Engine"
Cohesion: 0.28
Nodes (7): Any, Seleciona a melhor combinação de bloqueadores (mão, arsenal com ambush, e…, select_defense_blocks(), MockEngine, test_defense_pruner_accounts_for_arena_boom_grenade(), test_defense_pruner_piercing_avoids_vanilla_equipment_overuse(), test_defense_pruner_respects_arena_dominate()

### Community 84 - "Infrastructure & Templates"
Cohesion: 0.25
Nodes (9): CONTRIBUTING.md: Contribution Guide, Automated Environment Setup, Automated Testing Suite, ci.yml: CI Pipeline, Talishar Frontend Vite Build Job, Python AI Validation Job, requirements.txt: Project Dependencies, PyTorch Deep Learning Engine (+1 more)

### Community 86 - "Automated Test Suites"
Cohesion: 0.22
Nodes (5): Processo que finaliza normalmente ao receber SIGTERM., Processo teimoso que ignora SIGTERM deve ser finalizado com SIGKILL e wait()., Processo já terminado deve chamar wait() para liberar recurso sem falhar., Objetos inválidos ou None não devem lançar exceções., TestProcessCleanup

### Community 87 - "Policy Decision Engine"
Cohesion: 0.38
Nodes (6): create_model(), get_device(), device, Cria ou carrega um modelo FaBCardTransformerNetwork (v2). Se nenhum checkpoint…, Verifica que, se um checkpoint estiver corrompido, o carregador cria um backup…, test_cr_checkpoint_corruption_protection()

### Community 88 - "Card Transformer Architecture"
Cohesion: 0.29
Nodes (6): _get_card_embeddings_table(), Recebe x no formato [batch, 800] (ou [batch, state_dim]). Sintetiza features…, Tensor, Verifica se a matriz densa data/card_embeddings.pt foi compilada com as CR…, test_cr_embeddings_matrix_integrity(), test_card_embeddings_table_integrity()

### Community 89 - "Card Transformer Architecture"
Cohesion: 0.29
Nodes (7): ADR-0007: Card Transformer & Arena Semantics, 800-Dimension Card Transformer Network, Generic Data-Driven Arena Semantics, data_pipeline.md: Data Pipeline, Ability Costs Extraction (extract_ability_costs.py), Card Database Extraction (extract_card_db.py), Equipment Metadata Extraction (extract_equipment_metadata.py)

### Community 90 - "Automated Test Suites"
Cohesion: 0.29
Nodes (4): Verifica que check_stalemate_and_timeout tolera chaves None / NaN., Verifica que track_tick_health_and_damage tolera estados nulos e sem cartas., Valida que handle_game_tick em FabBotClient não explode com payload corrompido., TestPayloadResilience

### Community 91 - "Automated Test Suites"
Cohesion: 0.29
Nodes (4): Verifica que a gravação em disco respeita o throttling de 1.5s ou mudança de…, Garante que client.trajectory.clear() é chamado em finalize_match liberando…, Garante que decide_and_act não insere o vetor dummy arbitrário p_dist[0] = 1.0., TestMetricsThrottlingAndReplayBuffer

### Community 93 - "Hero Specific Strategies"
Cohesion: 0.33
Nodes (3): ArakniMarionetteStrategy, Any, Estratégia especializada para Arakni, Marionette ("Mario"). Combina contratos…

### Community 94 - "Context Constraint Chain"
Cohesion: 0.33
Nodes (6): CONTEXT.md: Canonical Domain Glossary, Domain Modeling Avoid Constraints, Combat Chain & Attack Link, Hidden State Determinization, Flesh and Blood (FaB) Domain, Dual Policy-Value Network

### Community 95 - "Game State Transition Simulator"
Cohesion: 0.33
Nodes (6): ADR-0001: Modular Package Decomposition, Backward-Compatible Facades Pattern, ROADMAP.md: Technical Roadmap & Milestones, Hero & Class Strategic Specialization, Deterministic Game Simulator, Global Code Coverage Progression

### Community 96 - "Infrastructure & Templates"
Cohesion: 0.33
Nodes (5): ref_path, ref_vite, ref_vite_plugin_svgr, ref_vite_tsconfig_paths, ref_vitejs_plugin_react

### Community 97 - "Clean Hook Banner"
Cohesion: 0.80
Nodes (5): install_hook(), print_banner(), sync_and_clean.sh script, show_help(), uninstall_hook()

### Community 99 - "ELO Ranking & Tournaments"
Cohesion: 0.40
Nodes (4): ui/tabs/__init__.py - Exportação das funções de renderização das abas do…, ui/tabs/tab_tournaments.py - Aba 4: Organizador de Torneios Customizados.…, Renderiza a Aba 4: Torneios Customizados., render_tab_tournaments()

### Community 101 - "Card Transformer Architecture"
Cohesion: 0.40
Nodes (3): ndarray, Avalia um estado único e retorna probabilidades e value escalar., Avalia múltiplos vetores de estado simultaneamente em batch. Retorna (probs,…

### Community 102 - "Tactical Action Pruners"
Cohesion: 0.40
Nodes (4): Any, ai/policy/pitch_pruner.py ======================== Módulo de poda e seleção de…, Seleciona a melhor carta da mão para dar pitch, priorizando eficiência de…, select_best_pitch_card()

### Community 103 - "Basehttprequesthandler Server Fabrary"
Cohesion: 0.40
Nodes (3): BaseHTTPRequestHandler, http_server, MockFaBrary

### Community 104 - "Infrastructure & Templates"
Cohesion: 0.40
Nodes (5): ref_routes_user_login, ForgottenPasswordForm, LoginForm, LoginPage, ResetPasswordForm

### Community 105 - "Mechanics Profile Main"
Cohesion: 0.50
Nodes (4): extract_cr_profile(), main(), Any, scripts/extract_cr_mechanics.py =============================== Extrai e…

### Community 107 - "Agent Skills & Automation"
Cohesion: 0.50
Nodes (4): Automate Repetitive Tasks Skill, Repetitive Task Detection Pipeline, Automated Tasks Catalog Skill, FaB Talishar Automation Scripts

### Community 109 - "Start Status Entry"
Cohesion: 0.83
Nodes (3): check_status(), start.sh script, show_help()

### Community 110 - "Stop Status Entry"
Cohesion: 0.83
Nodes (3): check_status(), stop.sh script, show_help()

### Community 111 - "Agent Skills & Automation"
Cohesion: 0.67
Nodes (3): Graphify Rule, Graphify AST Lazy Update, Graphify Query Workflow

### Community 112 - "Card Transformer Architecture"
Cohesion: 0.67
Nodes (3): Fill Skill Gaps Skill, Family Skill Architecture Model, Name Verification Gate

### Community 114 - "Deck Parsing & Validation"
Cohesion: 0.67
Nodes (3): ref_routes_user, DecksPage, ProfilePage

## Knowledge Gaps
- **65 isolated node(s):** `prepare_environment.sh script`, `AdUnitProps`, `LobbyRefreshError`, `STICKY_PLAYER_FIELDS`, `FALLBACK_GAME_INFO_FIELDS` (+60 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1049 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **51 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HeroStrategy` connect `Hero Specific Strategies` to `Hero Specific Strategies`, `Automated Test Suites`, `Hero Specific Strategies`, `Hero Specific Strategies`, `Card Transformer Architecture`, `Tactical Action Pruners`, `ISMCTS & World Sampling`, `Policy Decision Engine`, `Hero Specific Strategies`, `Hero Specific Strategies`, `Hero Specific Strategies`, `Hero Specific Strategies`, `Hero Specific Strategies`, `Hero Specific Strategies`, `Hero Specific Strategies`, `Hero Specific Strategies`, `Hero Specific Strategies`, `Hero Specific Strategies`?**
  _High betweenness centrality (0.056) - this node is a cross-community bridge._
- **Why does `PolicyEngine` connect `ISMCTS & World Sampling` to `Automated Test Suites`, `ISMCTS & World Sampling`, `Policy Decision Engine`, `Tactical Action Pruners`, `Tactical Action Pruners`, `MCTS Tree & Search Nodes`, `Policy Decision Engine`, `Policy Decision Engine`, `Policy Decision Engine`, `Policy Decision Engine`, `Policy Decision Engine`, `Policy Decision Engine`, `Tactical Action Pruners`, `Policy Decision Engine`, `Policy Decision Engine`?**
  _High betweenness centrality (0.050) - this node is a cross-community bridge._
- **Why does `FabBotClient` connect `Tactical Action Pruners` to `Bot Client & Runtime`, `Deck Parsing & Validation`, `Policy Decision Engine`, `Tactical Action Pruners`, `Agent Skills & Automation`, `Bot Client & Runtime`, `Automated Test Suites`, `Automated Test Suites`, `Bot Client & Runtime`?**
  _High betweenness centrality (0.029) - this node is a cross-community bridge._
- **Are the 58 inferred relationships involving `PolicyEngine` (e.g. with `.__init__()` and `.submit_sideboard()`) actually correct?**
  _`PolicyEngine` has 58 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `HeroStrategy` (e.g. with `TurnPlan` and `get_hero_strategy()`) actually correct?**
  _`HeroStrategy` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `prepare_environment.sh script`, `AdUnitProps`, `LobbyRefreshError` to the rest of the system?**
  _65 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Equipment Learning & Evaluation` be split into smaller, more focused modules?**
  _Cohesion score 0.058596491228070174 - nodes in this community are weakly interconnected._