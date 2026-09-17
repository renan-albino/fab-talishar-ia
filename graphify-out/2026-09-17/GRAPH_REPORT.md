# Graph Report - fab-talishar-ia  (2026-09-17)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 1985 nodes · 3954 edges · 125 communities (105 shown, 20 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 184 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `a2ac6f21`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- storage.py
- helpers.py
- deck_manager/__init__.py
- DummyBotClient
- TalisharApiClient
- test_generic_arena_semantics.py
- typing
- engine.py
- analyze_ismcts.py
- test_equipment_learning_and_defense_optimization.py
- HeroStrategy
- MCTSEngine
- settings.py
- pytest
- healthcheck_talishar.py
- TournamentManager
- FabBotClient
- test_combat_rules_pruning.py
- ReplayBuffer
- client.py
- test_model.py
- prepare_environment.py
- test_dynamic_learning_and_per.py
- knapsack_solver.py
- GameSimulator
- TeklovossenStrategy
- get_hero_strategy
- os
- GPUTrainingOrchestrator
- PolicyEngine
- process_supervisor.py
- MockClient
- TestHandlePopupAndChoices
- test_sub50_hero_strategies.py
- safe_int
- GuardianStrategy
- test_training_modules.py
- standard_mcts.py
- generate_worlds
- run_smoke_tests.py
- MarlynnStrategy
- CONTEXT.md: Canonical Domain Glossary
- manage_state.py
- test_teklovossen_and_deck_normalization.py
- Setup Matt Pocock Skills
- TurnPlan
- ISMCTSEngine
- test_unpayable_pruning.py
- TestScoreChoiceCandidate
- sys
- model.py
- extract_card_semantics.py
- Ponytail Help Skill
- TurnOrderLearner
- TestCheckAndHandleAntiLoop
- test_hero_hierarchical_strategies.py
- TestSideboardAndStalemate
- frontend_manager.py
- TestPhaseDeciderReaction
- phase_decider.py
- DashIOStrategy
- GravyBonesStrategy
- README.md: FaB Talishar AI Engine & Dashboard
- test_choice_handler_and_modals.py
- Ask Matt Skill
- SKILL.md: spec-audit
- finalize_match
- AssassinStrategy
- BruteStrategy
- VynnsetStrategy
- WarriorStrategy
- OscilioStrategy
- TestPhaseDeciderMainAction
- test_cr_comprehensive_rules.py
- run_benchmark_for_engine
- lobby_manager.py
- test_hammerhead_tome_and_hero.py
- ci.yml: CI Pipeline
- subprocess
- test_arsenal_pruning.py
- TestPhaseDeciderPitch
- TestProcessCleanup
- domain.md: Agent Domain Guide
- load_equipment_metadata
- game_simulator.py
- HalaStrategy
- turn_order_learning.py
- ADR-0007: Card Transformer & Arena Semantics
- extract_equipment_metadata.py
- TestPayloadResilience
- TestMetricsThrottlingAndReplayBuffer
- test_cr_arsenal_reaction_allowed_under_dominate
- resolve_sideboard
- RangerStrategy
- MechanologistStrategy
- NinjaStrategy
- ._train_step
- ROADMAP.md: Technical Roadmap & Milestones
- test_converters_and_resilience.py
- generate_card_embeddings.py
- sync_and_clean.sh
- TestPhaseDeciderArsenal
- .simulate_step
- IllusionistStrategy
- WizardStrategy
- .predict_state
- .config
- mock_fabrary.py
- Automate Repetitive Tasks Skill
- KassaiStrategy
- .get_all_known_zone_cards
- start.sh
- stop.sh
- Graphify Rule
- Fill Skill Gaps Skill
- .select_best_attack
- Workflow: graphify
- .evaluate_equipment_ability
- .calculate_available_resources
- .select_arsenal_card
- prepare_environment.sh script
- start_frontend.sh
- ui/__init__.py

## God Nodes (most connected - your core abstractions)
1. `HeroStrategy` - 70 edges
2. `PolicyEngine` - 69 edges
3. `DummyBotClient` - 46 edges
4. `TalisharApiClient` - 44 edges
5. `get_hero_strategy()` - 42 edges
6. `FabBotClient` - 40 edges
7. `TurnPlan` - 36 edges
8. `MCTSEngine` - 28 edges
9. `TestTalisharApiClient` - 28 edges
10. `GameSimulator` - 25 edges

## Surprising Connections (you probably didn't know these)
- `test_combat_chain_desc()` --calls--> `FabBotClient`  [INFERRED]
  tests/test_unpayable_pruning.py → ai/bot_runtime/client.py
- `test_policy_engine_integration()` --calls--> `PolicyEngine`  [INFERRED]
  tests/test_all_hero_strategies.py → ai/policy/engine.py
- `__init__()` --calls--> `PolicyEngine`  [INFERRED]
  tests/test_cr_comprehensive_rules.py → ai/policy/engine.py
- `TestMetricsThrottlingAndReplayBuffer` --uses--> `FabBotClient`  [INFERRED]
  tests/test_converters_and_resilience.py → ai/bot_runtime/client.py
- `TestPayloadResilience` --uses--> `FabBotClient`  [INFERRED]
  tests/test_converters_and_resilience.py → ai/bot_runtime/client.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Architectural Decision Records Governance Suite** — docs_adr_adr_0001_modular_package_decomposition, docs_adr_adr_0002_parallel_ismcts_multithreading, docs_adr_adr_0003_concurrent_atomic_persistence_file_locks, docs_adr_adr_0004_arsenal_cr315_and_digging_mode, docs_adr_adr_0005_setup_templates_vs_git_submodules, docs_adr_adr_0006_asymmetric_distillation_mcts_visit_targets, docs_adr_adr_0007_card_transformer_and_generic_arena_semantics [EXTRACTED 1.00]
- **Neural MCTS Training & Inference Pipeline** — docs_adr_adr_0002_parallel_ismcts_multithreading, docs_adr_adr_0006_asymmetric_distillation_mcts_visit_targets, docs_adr_adr_0007_card_transformer_and_generic_arena_semantics, readme_hybrid_decision_engine [EXTRACTED 1.00]
- **Issue Tracker Backend Adapters** — agents_skills_setup_matt_pocock_skills_issue_tracker_github, agents_skills_setup_matt_pocock_skills_issue_tracker_gitlab, agents_skills_setup_matt_pocock_skills_issue_tracker_local [EXTRACTED 1.00]
- **Ponytail Over-Engineering Elimination Suite** — agents_skills_ponytail_skill, agents_skills_ponytail_review_skill, agents_skills_ponytail_audit_skill, agents_skills_ponytail_debt_skill, agents_skills_ponytail_gain_skill, agents_skills_ponytail_help_skill [EXTRACTED 1.00]
- **Repo Engineering Skills Scaffolding** — agents_skills_setup_matt_pocock_skills_skill, agents_skills_setup_matt_pocock_skills_domain, agents_skills_setup_matt_pocock_skills_issue_tracker_github, agents_skills_setup_matt_pocock_skills_issue_tracker_gitlab, agents_skills_setup_matt_pocock_skills_issue_tracker_local, agents_skills_setup_matt_pocock_skills_triage_labels [EXTRACTED 1.00]
- **Tactical Decision Pruning Engine Framework** — docs_tactical_rules_attack_chain_sequencing, docs_tactical_rules_pitch_hierarchy, docs_tactical_rules_smart_blocking_pivot, docs_tactical_rules_strict_arsenal_pruning, context_tactical_pruning [EXTRACTED 1.00]

## Communities (125 total, 20 thin omitted)

### Community 0 - "storage.py"
Cohesion: 0.06
Nodes (72): atomic_json_save(), file_lock(), Context manager para exclusão mútua entre processos via fcntl.flock., Salva dados JSON de forma atômica usando write-to-tmp + rename., Any, Lê o histórico de partidas do stats_manager e atualiza gradualmente os…, sync_multipliers_with_stats(), canonicalize_deck_name() (+64 more)

### Community 1 - "helpers.py"
Cohesion: 0.05
Nodes (65): cache_resource, dashboard.py - Orquestrador Principal da Interface Gráfica Streamlit do FaB…, html, pandas, streamlit, tests/test_ui_modules.py - Testes unitários para a arquitetura modular da UI…, Valida a importação de todos os submódulos e funções exportadas do pacote ui., Valida funções de leitura otimizada de cauda (tail) e contagem de linhas. (+57 more)

### Community 2 - "deck_manager/__init__.py"
Cohesion: 0.07
Nodes (56): fix_deck_obj(), main(), Any, Valida um único arquivo de deck JSON e opcionalmente aplica correções., validate_decks.py ================= Script utilitário para validar e corrigir…, Tenta corrigir inconformidades comuns em um deck JSON. Ações de autocorreção:…, validate_single_deck(), deck_manager (+48 more)

### Community 3 - "DummyBotClient"
Cohesion: 0.06
Nodes (20): ai/talishar_api.py ================== Cliente HTTP para comunicação com as APIs…, requests, DummyBotClient, patch, tests/test_lobby_and_api_mock.py ================================ Testes…, Testa fallback de DEFAULT_BACKEND_URL quando config.settings falha., Mock completo do cliente de bot para testar lobby_manager isoladamente., Testes para resolução de ordem de turno e integração com o learner. (+12 more)

### Community 4 - "TalisharApiClient"
Cohesion: 0.07
Nodes (14): Any, Consulta o estado atual do jogo via polling rápido., Executa uma ação de jogo via ProcessInput.php., Injeta uma linha ou badge de avaliação no chat da partida., Cliente HTTP dedicado para interagir com o backend do Talishar., Cria uma nova sala de jogo no Talishar., Entra como Jogador 2 em uma sala existente., Consulta o estado do lobby para verificar se o oponente já entrou. (+6 more)

### Community 5 - "test_generic_arena_semantics.py"
Cohesion: 0.08
Nodes (31): Any, Seleciona o melhor candidato de ataque (da mão, equipamento, arma, arsenal,…, select_best_attack(), ArenaThreatContext, build_arena_threat_context(), CardSemanticProfile, _load_semantics_db(), parse_card_semantics() (+23 more)

### Community 6 - "typing"
Cohesion: 0.11
Nodes (21): ai/hero_strategies/assassin.py ============================== Estratégia para a…, ai/hero_strategies/base.py ========================== Definição base de…, ai/hero_strategies/brute.py =========================== Estratégia para a…, ai/hero_strategies/guardian.py ============================== Estratégia para…, ai/hero_strategies/illusionist.py ================================= Estratégia…, ai/hero_strategies/__init__.py ============================== Pacote modular de…, ai/hero_strategies/mechanologist.py ===================================…, MerchantStrategy (+13 more)

### Community 7 - "engine.py"
Cohesion: 0.10
Nodes (31): Any, ai/policy/arsenal_pruner.py =========================== Módulo de poda e…, Seleciona a melhor carta para colocar no Arsenal no fim do turno. Regra Oficial…, select_arsenal_card(), ai/policy/attack_pruner.py ========================== Módulo de poda de…, calculate_available_resources(), extract_card_info(), get_all_known_zone_cards() (+23 more)

### Community 8 - "analyze_ismcts.py"
Cohesion: 0.07
Nodes (28): check_and_handle_anti_loop(), handle_popup_and_choices(), rank_choice_candidates(), Trata modais, popups, inputs de nome, multichoose e escolhas de zona/texto., Pontua um candidato para escolha múltipla ou alvo de primeira tentativa., Ordena uma lista de candidatos do mais recomendado ao menos recomendado., Rastreia histórico de fases e estados repetidos, aplicando ações forçadas de…, score_choice_candidate() (+20 more)

### Community 9 - "test_equipment_learning_and_defense_optimization.py"
Cohesion: 0.07
Nodes (25): EquipmentEvent, EquipmentLearningEngine, EquipmentTracker, Any, ai/equipment_learning.py ======================== Motor de Aprendizado e…, Motor persistente de aprendizado de equipamentos. Consolida métricas em…, Carrega estatísticas com invalidação baseada no mtime do arquivo., Retorna o multiplicador aprendido para determinado herói e equipamento. Varia… (+17 more)

### Community 10 - "HeroStrategy"
Cohesion: 0.07
Nodes (12): HeroStrategy, Any, Pontuação tática para ativar habilidades de equipamento delegada ao…, Calcula score de utilidade para colocar carta no Arsenal no fim do turno (CR…, Delega para knapsack_solver.solve_knapsack_turn., Delega para knapsack_solver.calculate_card_opportunity_cost., Delega para knapsack_solver.calculate_hand_conversion_potential., Delega para turn_planner.should_trigger_survival_block. (+4 more)

### Community 11 - "MCTSEngine"
Cohesion: 0.11
Nodes (17): MCTSNode, Nó da árvore MCTS. Atributos: prior (float) : Probabilidade da POLICY HEAD para…, PUCT(s,a) = Q(s,a) + c_puct × P(s,a) × √N(s) / (1 + N(s,a)), MCTSEngine, Any, ndarray, Avalia estado raiz. Retorna priors uniformes e value=0 sem modelo., Avalia todas as folhas selecionadas em UM ÚNICO forward pass batch. Usa o… (+9 more)

### Community 12 - "settings.py"
Cohesion: 0.09
Nodes (31): _bar(), _build_settings(), _compute_batch_size(), _compute_buffer_capacity(), _compute_hidden_dim(), _compute_ismcts_worlds_from_latency(), _compute_mcts_sims(), _compute_num_res_blocks() (+23 more)

### Community 13 - "pytest"
Cohesion: 0.07
Nodes (27): ai_policy_engine, pytest, Fixtures compartilhadas para a suíte de testes do FaB Talishar AI., Durante pivot com max_block_cards == 0, cartas da mão não bloqueiam, mas…, Testa ativação de habilidade de equipamento na Fase Principal (M)., Se houver carta no Arsenal e o oponente atacar com Command and Conquer, Crown…, Se a mão estiver disfuncional (3+ cartas sem nenhum pitch azul/amarelo para…, Testa modificador dinâmico de custo de espada com a habilidade de compra da… (+19 more)

### Community 14 - "healthcheck_talishar.py"
Cohesion: 0.11
Nodes (27): check_port(), check_writable(), get_container_runtime(), main(), print_report(), probe_http_service(), Any, Executa todas as verificações de saúde do ecossistema FaB Talishar AI. (+19 more)

### Community 15 - "TournamentManager"
Cohesion: 0.11
Nodes (18): Any, Gera pareamento para a rodada suíça ordenando por pontuação., Executa uma partida de torneio lançando os bots em subprocessos., Atualiza a tabela de classificação com base no resultado da partida., Executa todas as partidas pendentes do torneio em sequência., Salva a tabela de classificação e histórico de confrontos em JSON., Gera uma matriz de vitórias/derrotas entre todos os decks., Lê todos os decks JSON disponíveis no diretório. (+10 more)

### Community 16 - "FabBotClient"
Cohesion: 0.10
Nodes (11): FabBotClient, Retorna uma identificação legível e clara para o Jogador 1 ou 2., Calcula o índice de avaliação da posição (estilo Chess Eval +/-)., Extrai descrição detalhada da carta/arma atacante e status da Combat Chain., Pontua um candidato para escolha múltipla ou alvo de primeira tentativa., Ordena uma lista de candidatos do mais recomendado ao menos recomendado., Grava o arquivo JSON de métricas respeitando throttling de 1.5s ou mudança de…, __getattr__() (+3 more)

### Community 17 - "test_combat_rules_pruning.py"
Cohesion: 0.09
Nodes (22): handle_reaction_phase(), Gerencia reações de ataque/defesa/instants da mão e equipamentos com podas…, MockReactionClient, tests/test_combat_rules_pruning.py ================================== Testes…, Overpower (CR 7.4.2b): Se o ataque possuir Overpower, nenhuma combinação de…, Piercing (CR 8.5.21): Ataques com Piercing ganham +1 de dano se forem…, Overpower (CR 7.4.2b, CR 8.3.22): "This can't be defended by more than one…, Phantasm (CR 7.4.4): Se o ataque oponente possui Phantasm (ex: Illusionist… (+14 more)

### Community 18 - "ReplayBuffer"
Cohesion: 0.08
Nodes (19): Any, device, ndarray, Amostra um batch balanceado com suporte opcional a Importance Sampling (Schaul…, Redimensiona a capacidade máxima do buffer preservando os dados já coletados., Carrega e remove arquivos compactos de trajetória gerados concorrentemente por…, Adiciona trajetória completa ao buffer calculando Recompensa Densa (Reward…, ReplayBuffer (+11 more)

### Community 19 - "client.py"
Cohesion: 0.13
Nodes (21): check_stalemate_and_timeout(), Verifica condições de empate técnico (stalemate), fadiga estagnada ou estouro…, Atualiza métricas de dano causado e recebido e dispara badge de avaliação no…, track_tick_health_and_damage(), classify_chess_move(), evaluate_board_state(), format_attack_chat_message(), format_html_line() (+13 more)

### Community 20 - "test_model.py"
Cohesion: 0.12
Nodes (19): FaBCardTransformerNetwork, _get_card_embeddings_table(), Any, Recebe x no formato [batch, 800] (ou [batch, state_dim]). Sintetiza features…, Converte o estado do Talishar em um vetor contíguo de 800 dimensões (Flat-…, Rede Neural Dual-Head com Atenção Carta-a-Carta e Contexto Global. Utiliza…, Tensor, tests/test_model.py =================== Testes unitários canônicos para o motor… (+11 more)

### Community 21 - "prepare_environment.py"
Cohesion: 0.26
Nodes (25): apply_backend_templates(), apply_custom_templates(), apply_frontend_templates(), check_docker(), check_unmapped_changes(), ensure_directories(), ensure_frontend_dependencies(), ensure_git_hooks() (+17 more)

### Community 22 - "test_dynamic_learning_and_per.py"
Cohesion: 0.10
Nodes (20): Any, ai/blunder_reviewer.py ====================== Módulo de Revisão Automática de…, Analisa os passos de uma trajetória e calcula pesos de prioridade para PER.…, review_trajectory_for_blunders(), ExperienceCollector / ReplayBuffer: Armazena trajetórias de partidas em memória…, ai_mcts, numpy, psutil (+12 more)

### Community 23 - "knapsack_solver.py"
Cohesion: 0.12
Nodes (23): get_multipliers_for_hero(), load_multipliers(), Carrega o mapa de multiplicadores com cache em memória baseado em mtime., Retorna os multiplicadores calibrados para o herói ou arquétipo especificado.…, calculate_card_opportunity_cost(), calculate_hand_conversion_potential(), Any, ai/hero_strategies/knapsack_solver.py =====================================… (+15 more)

### Community 24 - "GameSimulator"
Cohesion: 0.16
Nodes (22): GameSimulator, Motor de transição determinística para rollouts e expansão de folhas do MCTS., Simula a execução de um ataque na fase principal (Phase M). Aplica desconto de…, Simula a decisão de bloqueio na fase defensiva (Phase B). Soma a defesa total…, Faz uma cópia rápida do estado, garantindo isolamento de estruturas mutáveis e…, _shallow_clone_state(), Intimidate (CR 8.5.8): Quando o ataque possui Intimidate, desconta da mão do…, test_intimidate_reduces_opponent_hand_in_simulator() (+14 more)

### Community 25 - "TeklovossenStrategy"
Cohesion: 0.09
Nodes (10): Any, Habilidade ativada de Teklovossen: {r}{r}: Bane um card Evo da mão. Se o fizer,…, Estratégia de jogo para Professor Teklovossen e Teklovossen, Esteemed Magnate.…, Avaliação de Arsenal especializada para Teklovossen: Permite e prioriza cartas…, Verifica se a habilidade de Teklovossen ({r}{r}: Bane Evo da mão, compra carta)…, Regra oficial Teklovossen: equipar Evo da zona banida é jogado como Instant se…, Preservação Sagrada dos Evos com TEMPER: não queimar a última defesa de 1 que…, TeklovossenStrategy (+2 more)

### Community 26 - "get_hero_strategy"
Cohesion: 0.09
Nodes (23): get_hero_strategy(), Fábrica canônica de estratégias de herói de Flesh and Blood. Hierarquia em 3…, __getattr__(), test_all_139_official_heroes_resolution(), test_archetype_specific_heuristics(), test_dynamic_fallback(), test_policy_engine_integration(), Kassai reconhece sua estratégia, ativa habilidade e valoriza compras para… (+15 more)

### Community 27 - "os"
Cohesion: 0.13
Nodes (15): ai/atomic_io.py =============== Utilitários de I/O atômico para evitar…, ai/dynamic_rule_tuner.py ======================== Auto-Tuning Dinâmico de…, ai/sideboard_manager.py ======================= Gerenciador de resolução e…, ai/training/orchestrator.py ===========================…, contextlib, fcntl, json, os (+7 more)

### Community 28 - "GPUTrainingOrchestrator"
Cohesion: 0.13
Nodes (10): GPUTrainingOrchestrator, Carrega métricas persistidas em disco., Substitui NaN e inf por 0.0 recursivamente para garantir conformidade JSON., Salva métricas e checkpoints em disco., Encerra imediatamente todos os subprocessos ativos de bots., Varre e finaliza quaisquer processos órfãos de bot_client.py., Sinaliza parada e encerra imediatamente todos os subprocessos ativos., Singleton que gerencia o loop de treinamento autônomo. (+2 more)

### Community 29 - "PolicyEngine"
Cohesion: 0.10
Nodes (16): PolicyEngine, Retorna o custo em recursos para ativar a arma ou habilidade de equipamento., Extrai e normaliza atributos de cartas a partir do snapshot e banco de dados., Regra oficial FaB: Evos do Banish só ganham a opção de serem jogados como…, Seleciona a melhor combinação de bloqueadores otimizando breakpoints e…, Delega a escolha de pitch para o pruner especializado., Motor de Decisão Híbrido (ISMCTS / MCTS + Rede Neural Policy-Value +…, Em risco letal (HP <= 6), até equipamentos Blade Break com habilidades ativas… (+8 more)

### Community 30 - "process_supervisor.py"
Cohesion: 0.19
Nodes (19): ai/training =========== Pacote modular de orquestração e balanceamento de…, get_active_pids(), is_process_alive(), kill_active_processes(), kill_orphan_bots(), Any, ai/training/process_supervisor.py ================================ Funções e…, Retorna lista de PIDs de processos que continuam em execução. (+11 more)

### Community 31 - "MockClient"
Cohesion: 0.13
Nodes (5): MockClient, fixture, Mock leve de FabBotClient para isolamento e testes unitários rápidos., Testes para handle_block_phase: integração com plano de turno, bloqueios e…, TestPhaseDeciderBlock

### Community 33 - "test_sub50_hero_strategies.py"
Cohesion: 0.10
Nodes (19): tests/test_sub50_hero_strategies.py =================================== Testes…, Garante que equipar Evo do Banish só seja possível se a habilidade do…, Garante que cartas NAA de buff de Guerreiro (Hala e Kassai) sejam jogadas antes…, Garante que itens Mechanologist e Goldfin Harpoon tenham 0 de defesa, enquanto…, Garante que em cenários de final de jogo, o bot execute a Defesa Mínima Viável:…, Garante que defCounters negativos nativos do Talishar (-1, -2) reduzam a defesa…, Garante a regra oficial de TEMPER para os Evos do Teklovossen: 1. Enquanto…, Garante que equipamentos com efeitos ao defender ou ativações com recursos… (+11 more)

### Community 34 - "safe_int"
Cohesion: 0.16
Nodes (10): Any, ai/common/converters.py ======================= Utilitários universais de…, Converte com segurança strings, None, floats ou valores anômalos ('NaN',…, Garante que se val for None ou não for dicionário retorne `{}`., Garante retorno de string limpa sem lançar exceções., safe_dict(), safe_int(), safe_str() (+2 more)

### Community 35 - "GuardianStrategy"
Cohesion: 0.12
Nodes (5): GuardianStrategy, JarlStrategy, Estratégia especializada para a classe Guardian. Prioriza ataques pesados de…, Preservação de pitch azul para Guardião/Jarl quando há apenas 1 azul na mão., Estratégia especializada para Jarl Vetreiði (Guardião Elemental de Terra e…

### Community 36 - "test_training_modules.py"
Cohesion: 0.13
Nodes (12): ai/trainer.py ============= Fachada retrocompatível para o subsistema de…, ai_training, Any, ai/training/matchup_engine.py ============================= Gerenciador de…, Gerenciador de pareamento balanceado para treinamento autônomo. Gera ciclos…, RoundRobinMatchupEngine, collections, tests/test_training_modules.py - Testes unitários para a decomposição modular… (+4 more)

### Community 37 - "standard_mcts.py"
Cohesion: 0.16
Nodes (11): benchmark_mcts.py ================= Benchmark de vazão e latência para os…, ai/mcts ======= Módulo MCTS e ISMCTS para o FaB Talishar AI., _get_ismcts_worlds(), ai/mcts/ismcts.py ================= ISMCTSEngine: Information Set MCTS para…, Retorna número de mundos ISMCTS calculado por hardware scan no startup., ai/mcts/node.py =============== Nó da árvore MCTS para busca AlphaZero / PUCT., _get_c_puct(), FaBPolicyValueNetwork (+3 more)

### Community 38 - "generate_worlds"
Cohesion: 0.18
Nodes (16): generate_worlds(), _get_card_db(), Any, ai/mcts/world_generator.py ========================== Geração de mundos…, Retorna o banco de dados oficial de cartas em cache., Gera `num_worlds` mundos determinizados com amostragem Deck-Aware. Prioridade…, mock_card_db(), fixture (+8 more)

### Community 39 - "run_smoke_tests.py"
Cohesion: 0.17
Nodes (15): main(), print_summary(), Any, Etapa 2: Sanidade de importação das fachadas do sistema e símbolos fundamentais., Etapa 3: Execução rápida da suíte essencial de testes automatizados com pytest., run_smoke_tests.py ================== Bateria rápida de Smoke Tests para o…, Renderiza painel terminal com sumário executivo e colorido dos smoke tests., Etapa 1: Validação de sintaxe com py_compile em todos os arquivos Python. (+7 more)

### Community 40 - "MarlynnStrategy"
Cohesion: 0.12
Nodes (7): MarlynnStrategy, Any, Habilidade ativada de Marlynn, Treasure Hunter: Destrói 1 Gold para carregar…, Validação e pontuação especializada para Hammerhead, Harpoon Cannon. Regra FaB…, Estratégia especializada para Marlynn, Treasure Hunter (Ranger / Pirata).…, Garante que a lógica do canhão reside em…, test_marlynn_strategy_direct_weapon_ability()

### Community 41 - "CONTEXT.md: Canonical Domain Glossary"
Cohesion: 0.15
Nodes (17): CONTEXT.md: Canonical Domain Glossary, Arsenal Zone, Domain Modeling Avoid Constraints, Combat Chain & Attack Link, Hidden State Determinization, Flesh and Blood (FaB) Domain, Pitch Mechanism & Resource Generation, Dual Policy-Value Network (+9 more)

### Community 42 - "manage_state.py"
Cohesion: 0.26
Nodes (16): auto_release_on_commit(), download_release(), export_state(), format_size(), get_release_notes(), import_state(), init_checkpoint(), install_git_hook() (+8 more)

### Community 43 - "test_teklovossen_and_deck_normalization.py"
Cohesion: 0.12
Nodes (16): fixture, Garante que Hammerhead não é ativado sem flecha no Arsenal para evitar…, Valida a exceção tática: Hammerhead PODE e DEVE ser ativado sem flecha no…, Valida que o policy_engine gera candidatos de ataque para Aliados em jogo…, Valida a regra oficial de Teklo Leveler (EVO009) para 0, 1, 2, 3 e 4 Evos…, Valida que cartas jogáveis no cemitério (ex: Instant liberada por Astral…, Valida o modo de Execução Letal, cálculo por não-conversão da mão, Blood in the…, Valida que o bot equipa os 4 slots de armadura usando Base Evos quando… (+8 more)

### Community 44 - "Setup Matt Pocock Skills"
Cohesion: 0.15
Nodes (16): Setup Matt Pocock Skills Agent Config, Domain Documentation Convention, Domain Context Layout Strategy, GitHub Issue Tracker Adapter, GitHub CLI Operations, GitHub Wayfinding Operations, GitLab Issue Tracker Adapter, GitLab CLI Operations (+8 more)

### Community 45 - "TurnPlan"
Cohesion: 0.16
Nodes (4): Delega para turn_planner.analyze_turn_plan., Avalia taticamente jogar cartas de zonas específicas (Arsenal, Banish,…, Plano tático de ação para o turno atual. Coordena decisões ofensivas e…, TurnPlan

### Community 46 - "ISMCTSEngine"
Cohesion: 0.16
Nodes (11): ISMCTSEngine, _evaluate_world(), Any, FaBPolicyValueNetwork, ndarray, Executa MCTSEngine em um mundo determinizado com batch leaf evaluation. Retorna…, Information Set MCTS para Flesh and Blood (informação imperfeita). Estratégia:…, Executa ISMCTS e retorna (best_idx, policy_dist, ismcts_log). Fluxo por mundo:… (+3 more)

### Community 47 - "test_unpayable_pruning.py"
Cohesion: 0.16
Nodes (14): fixture, make_policy_engine(), policy_engine(), PolicyEngine genérico sem MCTS para testes rápidos., Factory para PolicyEngine com defaults seguros para testes unitários. Uso: pe =…, Testa se a IA decide absorver dano de ataque quando possui cartas de block 2 e…, test_flexible_blocking_low_efficiency_hand_conversion(), test_combat_chain_desc() (+6 more)

### Community 48 - "TestScoreChoiceCandidate"
Cohesion: 0.15
Nodes (3): parametrize, Testes para score_choice_candidate em diferentes cenários e modais., TestScoreChoiceCandidate

### Community 49 - "sys"
Cohesion: 0.15
Nodes (10): ai_bot_runtime, argparse, FaB Talishar AI - Bot Client Ponto de entrada do cliente HTTP de execução do…, extract_cr_profile(), main(), Any, scripts/extract_cr_mechanics.py =============================== Extrai e…, sys (+2 more)

### Community 50 - "model.py"
Cohesion: 0.18
Nodes (12): create_model(), get_device(), device, ai/model.py =========== FaBCardTransformerNetwork: Rede Neural com Atenção…, Cria ou carrega um modelo FaBCardTransformerNetwork (v2). Se nenhum checkpoint…, logging, Verifica que, se um checkpoint estiver corrompido, o carregador cria um backup…, test_cr_checkpoint_corruption_protection() (+4 more)

### Community 51 - "extract_card_semantics.py"
Cohesion: 0.21
Nodes (13): classify_on_hit_disruption(), extract_card_semantics(), identify_arena_item_aura_effects(), main(), parse_on_hit_damage_from_php(), parse_php_match_dictionaries(), Any, Identifica dano adicional On-Hit a partir de ItemAbilities.php, CardLogic.php e… (+5 more)

### Community 52 - "Ponytail Help Skill"
Cohesion: 0.19
Nodes (13): Ponytail Audit Skill, Whole-Repo Over-Engineering Audit, Ponytail Debt Skill, Shortcut Debt Ledger Harvesting, Ponytail Gain Skill, Ponytail Impact Scoreboard, Ponytail Help Skill, Ponytail Modes Reference Card (+5 more)

### Community 53 - "TurnOrderLearner"
Cohesion: 0.21
Nodes (7): Any, Registra o resultado da partida para calibrar o aprendizado., Gerencia estatísticas de vitórias/partidas de 'Go First' vs 'Go Second' por…, Retorna 'Go First' ou 'Go Second' com base no modelo aprendido e priors de FaB.…, TurnOrderLearner, Verifica se heróis de setup (Dash IO, Vynnset, Teklovossen) escolhem 'Go First'…, test_turn_order_learner_priors()

### Community 55 - "test_hero_hierarchical_strategies.py"
Cohesion: 0.15
Nodes (12): Testa heurísticas de Gravy Bones e Mario (Assassin / Pirate)., Testa que o RoundRobinMatchupEngine distribui todos os pares uniformemente sem…, Testa o scoring semântico de candidatos para botões de escolha única e múltipla., Ao afundar carta com Crown of Providence sob ameaça de Command and Conquer, a…, Ao afundar carta sem ameaça ao Arsenal, a pior carta da mão é afundada para…, Testa que os heróis identificados resolvem para suas classes específicas com…, test_gravy_bones_and_mario_heuristics(), test_hero_strategies_resolution() (+4 more)

### Community 56 - "TestSideboardAndStalemate"
Cohesion: 0.15
Nodes (6): Valida que quando ambos os decks esgotam e não há mudança de vida por 3 turnos,…, Valida encerramento imediato se ambos os decks e mãos estão totalmente vazios…, Valida o Hard Cap de turnos para evitar loops infinitos., Valida que Jarl NUNCA equipa uma arma 2H junto com um escudo (CR 2.8.2 e CR…, Se o deck tiver apenas uma arma 2H e um escudo (sem arma 1H), o escudo não pode…, TestSideboardAndStalemate

### Community 57 - "frontend_manager.py"
Cohesion: 0.32
Nodes (11): _ai_watcher_loop(), create_human_vs_bot_match(), ensure_ai_watcher_running(), is_backend_running(), is_frontend_running(), _is_port_open(), Any, Cria uma partida no backend do Talishar para o jogador humano (Player 1) e… (+3 more)

### Community 59 - "phase_decider.py"
Cohesion: 0.18
Nodes (10): handle_arsenal_phase(), handle_block_phase(), handle_main_action_phase(), handle_pass_buttons(), handle_pitch_phase(), Gerencia a fase de colocação estratégica no Arsenal (ARS)., Gerencia a fase principal de ação/ataque (M, STARTTURN, RESOLUTIONSTEP), AP,…, Gerencia a fase de pitch: PDECK, seleção ótima via policy_engine ou… (+2 more)

### Community 60 - "DashIOStrategy"
Cohesion: 0.18
Nodes (8): DashIOStrategy, Any, Habilidade de Dash IO: olhar o topo do deck para jogar itens como Instant., Estratégia especializada para Dash I/O. Foco absoluto em itens com Crank (Boom…, Garante que DashIOStrategy, Arakni e Gravy aceitam hand_attacks sem erro de…, Testa heurísticas de Dash I/O (Mechanologist / Items com Crank)., test_dash_io_heuristics(), test_dash_io_strategy_accepts_hand_attacks_kwarg()

### Community 61 - "GravyBonesStrategy"
Cohesion: 0.20
Nodes (5): GravyBonesStrategy, Estratégia especializada para Gravy Bones, Shipwrecked Looter (Pirata /…, Rastreia detalhadamente as 15 cópias de aliados do baralho do Gravy Bones.…, Valida que o Ally Stock Tracker cataloga com precisão aliados na mesa, mão,…, test_gravy_bones_ally_stock_tracking()

### Community 62 - "README.md: FaB Talishar AI Engine & Dashboard"
Cohesion: 0.20
Nodes (11): Information Set Monte Carlo Tree Search (ISMCTS), ADR-0002: Parallel ISMCTS Multithreading, Independent World Determinization with ThreadPoolExecutor, ADR-0006: Asymmetric Policy Distillation, Dense Auxiliary Targets KataGo Methodology, MCTS Visit Distribution Policy Distillation, README.md: FaB Talishar AI Engine & Dashboard, Dynamic Training Profiles (Balanced vs Turbo) (+3 more)

### Community 63 - "test_choice_handler_and_modals.py"
Cohesion: 0.18
Nodes (6): fast_sleep(), Elimina esperas por sleep durante os testes para execução instantânea., Testes para handle_pass_buttons., Testes para ordenação de opções em rank_choice_candidates., TestPhaseDeciderPassButtons, TestRankChoiceCandidates

### Community 64 - "Ask Matt Skill"
Cohesion: 0.20
Nodes (10): Ask Matt Agent Configuration, Phase Boundaries Guide, Phase Boundary Decision Principle, Five Phase Boundary Options, Ask Matt Skill, Idea to Ship Flow, Engineering Skills Router, Grill Me Agent Configuration (+2 more)

### Community 65 - "SKILL.md: spec-audit"
Cohesion: 0.20
Nodes (10): SKILL.md: spec-audit, Spec Decomposition Axis, Standards Audit Axis, Two-Axis Audit Pattern, AGENTS.template.md: Agent Rules Template, Multi-Agent Parallelism Guidelines, Ponytail Protocol Rules, Workspace Editing Conventions (+2 more)

### Community 66 - "finalize_match"
Cohesion: 0.20
Nodes (10): choose_first_player(), Consulta o modelo de aprendizado de ordem de turno e envia a escolha., finalize_match(), Determina o vencedor, audita validade da partida, revisa blunders, salva dados…, get_equipment_learning_engine(), Retorna o singleton do motor de aprendizado de equipamentos., get_global_buffer(), Salva uma trajetória individual de forma atômica e ultrarrápida sem contenção… (+2 more)

### Community 67 - "AssassinStrategy"
Cohesion: 0.20
Nodes (5): ArakniMarionetteStrategy, AssassinStrategy, Any, Estratégia especializada para a classe Assassin (Arakni, Uzuri, Nuu, Dr.…, Estratégia especializada para Arakni, Marionette ("Mario"). Combina contratos…

### Community 68 - "BruteStrategy"
Cohesion: 0.22
Nodes (3): BruteStrategy, Estratégia especializada para a classe Brute. Foco em manter cartas de poder 6+…, Retorna o Intelecto do herói Brute (CR 4.3.2), padrão 3 para heróis Brute…

### Community 69 - "VynnsetStrategy"
Cohesion: 0.20
Nodes (5): Habilidade de início da fase de ação de Vynnset: Bane uma carta da mão para…, Estratégia especializada para Vynnset, Iron Maiden. Sinergia com Shadow e…, VynnsetStrategy, Testa heurísticas de Vynnset (Shadow Runeblade / Rune Gate)., test_vynnset_heuristics()

### Community 71 - "OscilioStrategy"
Cohesion: 0.20
Nodes (5): OscilioStrategy, Habilidade de Oscilio: Bane uma carta de ação da mão para jogar cartas do…, Estratégia especializada para Oscilio, Constella Intelligence / Forked…, Valida que Oscilio prioriza Astral Bridge no ataque e não bloqueia com peças…, test_oscilio_astral_bridge_and_overblocking()

### Community 73 - "test_cr_comprehensive_rules.py"
Cohesion: 0.20
Nodes (9): tests/test_cr_comprehensive_rules.py ==================================== Suíte…, CR 7.4.2b: 'An attack with overpower cannot be defended by more than 1 action…, CR 4.3.2 / 4.4.3f: Para heróis com Intelecto 3 (Rhinar, Kayo), o Modo Cavar…, Verifica se o GameSimulator obtém metadados de combate (poder, defesa, custo,…, Verifica se a matriz densa data/card_embeddings.pt foi compilada com as CR…, test_cr_digging_mode_dynamic_intellect(), test_cr_embeddings_matrix_integrity(), test_cr_game_simulator_canonical_metadata() (+1 more)

### Community 74 - "run_benchmark_for_engine"
Cohesion: 0.28
Nodes (8): main(), print_table(), Any, Executa o benchmark para um motor específico (MCTS ou ISMCTS)., Imprime tabela formatada de resultados do benchmark., run_benchmark_for_engine(), _execute_search(), _worker_task()

### Community 75 - "lobby_manager.py"
Cohesion: 0.22
Nodes (8): get_opponent_info(), Lado Host aguardando Jogador 2 no lobby, dado, sideboard e início da partida., Configura e conecta a sala para o bot (seja como Host ou Join)., Consulta o endpoint GetLobbyRefresh.php e retorna (opp_hero, opp_class)., Gerencia o ciclo de vida do bot como Jogador 2 (Join) no lobby do Talishar: 1.…, setup_game_room(), wait_for_opponent_and_start(), wait_in_lobby_and_start()

### Community 76 - "test_hammerhead_tome_and_hero.py"
Cohesion: 0.22
Nodes (8): ai_hero_strategies, tests/test_hammerhead_tome_and_hero.py =======================================…, Marlynn ativa habilidade destruindo Gold para carregar Arsenal quando vazio., Gorganian Tome tem pitch 0 e NUNCA pode ser selecionado como pitch., Hammerhead Harpoon Cannon deve ter poder 0 (não 6), custo 4 e ser podado quando…, test_gorganian_tome_pitch_zero(), test_hammerhead_harpoon_cannon_attributes_and_pruning(), test_marlynn_hero_ability()

### Community 77 - "ci.yml: CI Pipeline"
Cohesion: 0.25
Nodes (9): CONTRIBUTING.md: Contribution Guide, Automated Environment Setup, Automated Testing Suite, ci.yml: CI Pipeline, Talishar Frontend Vite Build Job, Python AI Validation Job, requirements.txt: Project Dependencies, PyTorch Deep Learning Engine (+1 more)

### Community 78 - "subprocess"
Cohesion: 0.28
Nodes (5): extract_from_local(), extract_ability_costs(), main(), scripts/extract_ability_costs.py ================================ Extrai os…, subprocess

### Community 79 - "test_arsenal_pruning.py"
Cohesion: 0.25
Nodes (8): Valida retrocompatibilidade com o backend Talishar enviando arsenal como…, Valida que para heróis Brute (Intellect 3), o Modo Cavar ativa com len(hand) >=…, Valida que para heróis com Intellect 5, o Modo Cavar ativa com len(hand) >= 4., run_tests(), test_arsenal_pruning(), test_digging_mode_dynamic_intellect_brute(), test_digging_mode_dynamic_intellect_high(), test_player_arse_support_in_policy_engine()

### Community 81 - "TestProcessCleanup"
Cohesion: 0.22
Nodes (5): Processo que finaliza normalmente ao receber SIGTERM., Processo teimoso que ignora SIGTERM deve ser finalizado com SIGKILL e wait()., Processo já terminado deve chamar wait() para liberar recurso sem falhar., Objetos inválidos ou None não devem lançar exceções., TestProcessCleanup

### Community 82 - "domain.md: Agent Domain Guide"
Cohesion: 0.25
Nodes (8): ADR-0003: Concurrent Atomic Persistence & File Locks, Write-to-Temp and Atomic Rename Pattern, Reentrant Interprocess Mutex via fcntl.flock, ADR-0005: Setup Templates vs Git Submodules, Declarative Patch Injection via setup_templates SSOT, domain.md: Agent Domain Guide, Canonical Glossary Rule, Setup Templates Synchronization Check

### Community 83 - "load_equipment_metadata"
Cohesion: 0.33
Nodes (6): load_equipment_metadata(), Carrega os metadados mecânicos dos equipamentos com cache em memória., evaluate_equipment_ability(), Any, ai/hero_strategies/equipment_evaluator.py…, Pontuação tática para ativar habilidades de equipamento (Head, Chest, Arms,…

### Community 84 - "game_simulator.py"
Cohesion: 0.33
Nodes (5): _get_card_semantics(), _get_cards_db(), Any, ai/game_simulator.py ==================== Simulador determinístico de regras e…, Extrai metadados táticos e semânticos de uma carta consultando…

### Community 85 - "HalaStrategy"
Cohesion: 0.29
Nodes (4): HalaStrategy, Estratégia especializada para Hala, Bladesaint of the Vow. Foco absoluto em…, Testa heurísticas de Hala Bladesaint (Warrior / Zenith Blade)., test_hala_heuristics()

### Community 86 - "turn_order_learning.py"
Cohesion: 0.33
Nodes (5): get_logger(), ai/logger.py ============ Logger centralizado do FAB AI Engine. Todos os…, Retorna um logger configurado com formato padronizado., ai/turn_order_learning.py ========================= Sistema de Aprendizado e…, Logger

### Community 87 - "ADR-0007: Card Transformer & Arena Semantics"
Cohesion: 0.29
Nodes (7): ADR-0007: Card Transformer & Arena Semantics, 800-Dimension Card Transformer Network, Generic Data-Driven Arena Semantics, data_pipeline.md: Data Pipeline, Ability Costs Extraction (extract_ability_costs.py), Card Database Extraction (extract_card_db.py), Equipment Metadata Extraction (extract_equipment_metadata.py)

### Community 88 - "extract_equipment_metadata.py"
Cohesion: 0.43
Nodes (6): extract_equipment_metadata(), extract_php_switch_map(), main(), Any, scripts/extract_equipment_metadata.py =====================================…, Extrai mapeamento de funções PHP estilo switch($cardID) ou match($cardID).

### Community 89 - "TestPayloadResilience"
Cohesion: 0.29
Nodes (4): Verifica que check_stalemate_and_timeout tolera chaves None / NaN., Verifica que track_tick_health_and_damage tolera estados nulos e sem cartas., Valida que handle_game_tick em FabBotClient não explode com payload corrompido., TestPayloadResilience

### Community 90 - "TestMetricsThrottlingAndReplayBuffer"
Cohesion: 0.29
Nodes (4): Verifica que a gravação em disco respeita o throttling de 1.5s ou mudança de…, Garante que client.trajectory.clear() é chamado em finalize_match liberando…, Garante que decide_and_act não insere o vetor dummy arbitrário p_dist[0] = 1.0., TestMetricsThrottlingAndReplayBuffer

### Community 91 - "test_cr_arsenal_reaction_allowed_under_dominate"
Cohesion: 0.29
Nodes (3): CR 7.4.2a / 7.4.2d / 8.3.4b: Sob ataque com Dominate onde uma carta da mão já…, test_cr_arsenal_reaction_allowed_under_dominate(), __init__()

### Community 92 - "resolve_sideboard"
Cohesion: 0.33
Nodes (4): Any, Resolve a configuração ótima e estritamente legal de Herói, Equipamentos, Armas…, resolve_sideboard(), card_score()

### Community 93 - "RangerStrategy"
Cohesion: 0.33
Nodes (4): is_resource_or_gem_card(), CR 3.1.5: Recursos e Gemas NUNCA podem ser colocados no Arsenal., RangerStrategy, Estratégia especializada para a classe Ranger. Prioriza disparo de flechas a…

### Community 95 - "NinjaStrategy"
Cohesion: 0.33
Nodes (3): NinjaStrategy, Estratégia especializada para a classe Ninja. Prioriza ataques rápidos de baixo…, test_turn_plan_systems()

### Community 96 - "._train_step"
Cohesion: 0.33
Nodes (4): device, FaBPolicyValueNetwork, GradScaler, Optimizer

### Community 97 - "ROADMAP.md: Technical Roadmap & Milestones"
Cohesion: 0.33
Nodes (6): ADR-0001: Modular Package Decomposition, Backward-Compatible Facades Pattern, ROADMAP.md: Technical Roadmap & Milestones, Hero & Class Strategic Specialization, Deterministic Game Simulator, Global Code Coverage Progression

### Community 98 - "test_converters_and_resilience.py"
Cohesion: 0.33
Nodes (5): math, signal, tests/test_converters_and_resilience.py =======================================…, TestDeckRepositoryRule3, unittest_mock

### Community 99 - "generate_card_embeddings.py"
Cohesion: 0.40
Nodes (5): build_card_vector(), main(), ndarray, scripts/generate_card_embeddings.py =================================== Compila…, Extrai exatamente 48 features numéricas/normalizadas de uma carta.

### Community 100 - "sync_and_clean.sh"
Cohesion: 0.80
Nodes (5): install_hook(), print_banner(), sync_and_clean.sh script, show_help(), uninstall_hook()

### Community 102 - ".simulate_step"
Cohesion: 0.40
Nodes (3): ndarray, Simula a geração de recursos na fase de Pitch (Phase P / PDECK)., Ponto de entrada unificado para simulação de passo: Identifica a fase e tipo de…

### Community 106 - ".predict_state"
Cohesion: 0.40
Nodes (3): ndarray, Avalia um estado único e retorna probabilidades e value escalar., Avalia múltiplos vetores de estado simultaneamente em batch. Retorna (probs,…

### Community 107 - ".config"
Cohesion: 0.40
Nodes (3): Any, Inicia o loop de treinamento numa thread daemon., Retorna o dicionário de configurações ativas mesclando SETTINGS e overrides.

### Community 108 - "mock_fabrary.py"
Cohesion: 0.40
Nodes (3): BaseHTTPRequestHandler, http_server, MockFaBrary

### Community 109 - "Automate Repetitive Tasks Skill"
Cohesion: 0.50
Nodes (4): Automate Repetitive Tasks Skill, Repetitive Task Detection Pipeline, Automated Tasks Catalog Skill, FaB Talishar Automation Scripts

### Community 110 - "KassaiStrategy"
Cohesion: 0.50
Nodes (3): KassaiStrategy, Estratégia especializada para Kassai (Cintari Sellsword / Golden Sand). Foco em…, Habilidade ativada de Kassai of the Golden Sand: Concede o efeito de que o…

### Community 111 - ".get_all_known_zone_cards"
Cohesion: 0.50
Nodes (3): Retorna um mapa consolidado de todas as cartas em todas as zonas do jogo., Valida que get_all_known_zone_cards consolida todas as zonas e…, test_all_known_zone_cards_and_state_vector()

### Community 112 - "start.sh"
Cohesion: 0.83
Nodes (3): check_status(), start.sh script, show_help()

### Community 113 - "stop.sh"
Cohesion: 0.83
Nodes (3): check_status(), stop.sh script, show_help()

### Community 114 - "Graphify Rule"
Cohesion: 0.67
Nodes (3): Graphify Rule, Graphify AST Lazy Update, Graphify Query Workflow

### Community 115 - "Fill Skill Gaps Skill"
Cohesion: 0.67
Nodes (3): Fill Skill Gaps Skill, Family Skill Architecture Model, Name Verification Gate

## Knowledge Gaps
- **50 isolated node(s):** `prepare_environment.sh script`, `start_frontend.sh script`, `Repetitive Task Detection Pipeline`, `FaB Talishar Automation Scripts`, `Family Skill Architecture Model` (+45 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 887 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **20 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PolicyEngine` connect `PolicyEngine` to `engine.py`, `analyze_ismcts.py`, `test_equipment_learning_and_defense_optimization.py`, `pytest`, `FabBotClient`, `test_combat_rules_pruning.py`, `get_hero_strategy`, `test_sub50_hero_strategies.py`, `test_teklovossen_and_deck_normalization.py`, `ISMCTSEngine`, `test_unpayable_pruning.py`, `model.py`, `test_cr_comprehensive_rules.py`, `test_hammerhead_tome_and_hero.py`, `test_arsenal_pruning.py`, `test_cr_arsenal_reaction_allowed_under_dominate`, `resolve_sideboard`, `.get_all_known_zone_cards`, `.select_best_attack`, `.calculate_available_resources`, `.select_arsenal_card`?**
  _High betweenness centrality (0.069) - this node is a cross-community bridge._
- **Why does `HeroStrategy` connect `HeroStrategy` to `typing`, `test_equipment_learning_and_defense_optimization.py`, `pytest`, `test_dynamic_learning_and_per.py`, `knapsack_solver.py`, `TeklovossenStrategy`, `get_hero_strategy`, `PolicyEngine`, `GuardianStrategy`, `TurnPlan`, `test_unpayable_pruning.py`, `AssassinStrategy`, `BruteStrategy`, `WarriorStrategy`, `test_cr_comprehensive_rules.py`, `RangerStrategy`, `MechanologistStrategy`, `NinjaStrategy`, `IllusionistStrategy`, `WizardStrategy`?**
  _High betweenness centrality (0.055) - this node is a cross-community bridge._
- **Why does `get_hero_strategy()` connect `get_hero_strategy` to `typing`, `engine.py`, `analyze_ismcts.py`, `HeroStrategy`, `knapsack_solver.py`, `test_sub50_hero_strategies.py`, `GuardianStrategy`, `MarlynnStrategy`, `test_teklovossen_and_deck_normalization.py`, `model.py`, `test_hero_hierarchical_strategies.py`, `AssassinStrategy`, `BruteStrategy`, `WarriorStrategy`, `OscilioStrategy`, `test_hammerhead_tome_and_hero.py`, `RangerStrategy`, `MechanologistStrategy`, `NinjaStrategy`, `IllusionistStrategy`, `WizardStrategy`?**
  _High betweenness centrality (0.040) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `HeroStrategy` (e.g. with `TurnPlan` and `get_hero_strategy()`) actually correct?**
  _`HeroStrategy` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 53 inferred relationships involving `PolicyEngine` (e.g. with `.__init__()` and `.submit_sideboard()`) actually correct?**
  _`PolicyEngine` has 53 INFERRED edges - model-reasoned connections that need verification._
- **What connects `prepare_environment.sh script`, `start_frontend.sh script`, `Repetitive Task Detection Pipeline` to the rest of the system?**
  _50 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `storage.py` be split into smaller, more focused modules?**
  _Cohesion score 0.056962025316455694 - nodes in this community are weakly interconnected._