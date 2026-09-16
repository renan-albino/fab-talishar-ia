# ADR-0001: Decomposição Modular dos Monólitos em Subpacotes Coesos com Fachadas Retrocompatíveis

- **Status**: Accepted
- **Date**: 2026-09-16
- **Deciders**: Equipe FaB Talishar AI (Architecture Review)

## Context

O motor de IA do FaB Talishar AI começou como um conjunto de scripts autônomos de grande porte (monólitos), com múltiplos módulos ultrapassando milhares de linhas de código (`bot_client.py`, `ai/policy_engine.py`, `ai/trainer.py`, `deck_parser.py`, `stats_manager.py`, `dashboard.py`). 

Essa arquitetura inicial concentrada apresentava problemas críticos:
1. **Acoplamento excessivo**: Módulos misturavam lógica de protocolo HTTP/WebSocket, regras de combate, heurísticas de heróis, treinamento de redes neurais e parsing de dados.
2. **Gargalo em desenvolvimento concorrente**: Diferentes frentes e agentes de IA geravam conflitos frequentes de merge ao editar as mesmas seções de arquivos gigantescos.
3. **Dificuldade de isolamento em testes**: Testes unitários para regras táticas (ex: poda de ataque ou bloqueio) exigiam instanciar dependências do cliente de rede ou da interface gráfica.
4. **Legado e dependências externas**: Dezenas de testes automatizados (`tests/`), scripts em `scripts/` e pipelines de CI já dependiam das assinaturas de importação raízes (ex: `from bot_client import BotClient` ou `from deck_parser import parse_deck`).

## Decision

Decompor os 9 monólitos em pacotes modulares de alta coesão e responsabilidade única (SRP), preservando fachadas retrocompatíveis na raiz do projeto:

1. **`ai/bot_runtime/`**: Runtime de execução e protocolo com o Talishar.
   - `client.py`: Loop principal de conexão e orquestração do bot.
   - `lobby_manager.py`: Criação, busca e entrada em partidas.
   - `match_tracker.py`: Métricas de turno, cálculo de dano, avaliação de tabuleiro e detecção de encerramento.
   - `choice_handler.py`: Resolução de janelas de decisão e modais do Talishar (anti-loop).
   - `phase_decider.py`: Máquina de estados das fases de decisão de Flesh and Blood.
   - **Fachada retrocompatível**: `bot_client.py` na raiz do projeto re-exporta as classes e funções principais.

2. **`ai/policy/`**: Motor de decisão tática e poda combinatória.
   - `engine.py`: Motor unificado de avaliação de jogadas.
   - `card_evaluator.py`: Avaliação intrínseca de valor e utilidade de cartas.
   - `attack_pruner.py`: Poda tática de ataques e geração de sequências de ataque.
   - `defense_pruner.py`: Poda combinatória de bloqueio e mitigação de ameaças on-hit.
   - `pitch_pruner.py`: Otimização de geração de recursos e sequenciamento de pitch.
   - `arsenal_pruner.py`: Poda e seleção de cartas para o Arsenal.
   - `constants.py`: Constantes e carregamento seguro do banco de cartas.
   - **Fachada retrocompatível**: `ai/policy_engine.py` re-exporta `PolicyEngine`, `ActionPruner` e funções auxiliares.

3. **`ai/mcts/`**: Motores de busca em árvore para informação perfeita e imperfeita.
   - `node.py`: Estrutura do nó MCTS com estatísticas de visita, prior e valor.
   - `standard_mcts.py`: Engine de MCTS clássico com batch leaf evaluation e virtual loss.
   - `world_generator.py`: Amostragem e determinização de mundos plausíveis baseados na classe do oponente.
   - `ismcts.py`: Information Set MCTS paralelo multithread.
   - **Fachada retrocompatível**: `ai/mcts/__init__.py` re-exporta `MCTSEngine` e `ISMCTSEngine`.

4. **`ai/training/`**: Infraestrutura de treinamento e supervisão de processos.
   - `orchestrator.py`: Orquestrador de treino GPU com FP16/AMP, PER e replay buffer.
   - `matchup_engine.py`: Rotação balanceada de confrontos (Round-Robin).
   - `process_supervisor.py`: Gestão de ciclo de vida e encerramento limpo de processos de bots.
   - **Fachada retrocompatível**: `ai/trainer.py` re-exporta `GPUTrainingOrchestrator`.

5. **`deck_manager/`**: Ciclo de vida e repositório de baralhos.
   - `parser.py`: Parsing de formatos FabDB, Fabrary e Talishar nativo.
   - `slugifier.py`: Normalização canônica de identificadores e nomes de baralhos.
   - `validator.py`: Validação de legalidade de formatos (Blitz, CC, Living Legend).
   - `repository.py`: Acesso e persistência atômica exclusivamente no diretório `decks/`.
   - **Fachada retrocompatível**: `deck_parser.py` re-exporta todas as rotinas de parsing e carregamento.

6. **`stats/`**: Métricas estatísticas e persistência de classificação.
   - `elo.py`: Algoritmo ELO com fator K dinâmico baseado em experiência.
   - `deck_names.py`: Dicionário e consolidação de nomes canônicos.
   - `storage.py`: Leitura e escrita atômica com lock interprocessos (`ratings.json`).
   - `sync.py`: Sincronização entre métricas locais e histórico de partidas.
   - **Fachada retrocompatível**: `stats_manager.py` re-exporta `StatsManager` e métodos estatísticos.

7. **`ui/`**: Interface visual Streamlit.
   - `helpers.py`: Utilitários de renderização, tailing assíncrono de logs e componentes.
   - `tabs/`: 7 abas desacopladas (`tab_training.py`, `tab_analytics.py`, `tab_arena.py`, `tab_decks.py`, `tab_ismcts.py`, `tab_play.py`, `tab_tournaments.py`).
   - **Ponto de entrada**: `dashboard.py` atua como agregador limpo delegando para os submódulos.

## Consequences

### Positive
- **Coesão e Manutenibilidade**: Cada arquivo tem escopo delimitado (<300 linhas em média), facilitando leitura, depuração e refatorações pontuais.
- **Zero Quebra de Compatibilidade (100% Retrocompatible)**: Todos os testes existentes (`pytest`), scripts de automação e CLIs continuam funcionando sem alteração de imports.
- **Concorrência Otimizada**: Múltiplos agentes ou desenvolvedores podem trabalhar em áreas distintas (ex: `defense_pruner.py` vs `lobby_manager.py`) sem risco de conflito de código.
- **Testabilidade Granular**: Possibilidade de criar suítes de testes unitários focadas exclusivamente em submódulos isolados sem mockar todo o ambiente.

### Negative / Trade-offs
- **Indireção de Arquivos**: Desenvolvedores precisam navegar por pacotes modulares em vez de abrir um único arquivo para buscar uma funcionalidade.
- **Manutenção de Fachadas**: Ao adicionar novos métodos públicos em submódulos, as fachadas correspondentes devem ser atualizadas caso precisem ser exportadas globalmente.

## Alternatives Considered

- **Manter Monólitos Originais**: Rejeitado devido ao acúmulo de débito técnico, lentidão de navegação e conflitos frequentes durante o trabalho concorrente de múltiplos agentes.
- **Quebra Rígida sem Fachadas**: Rejeitado porque invalidaria imediatamente mais de 50 testes existentes e exigiria refatoração simultânea de scripts de terceiros e templates legados.
