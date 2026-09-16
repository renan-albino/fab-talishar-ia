# GEMINI.md — FaB Talishar AI Engine

Diretrizes e regras operacionais para agentes de IA (Google Antigravity / Gemini CLI).

## Project Rules

### Workspace Conventions

1. **Respeite o `.geminiignore`:** Nunca leia arquivos de logs brutos (`logs/*.log`), backups de partidas ou checkpoints binários de rede neural (`*.pt`).
2. **Foco Cirúrgico:** Realize edições pontuais no arquivo exato alvo usando substituições de bloco. Não reescreva arquivos inteiros.
3. **Decks em `decks/`:** Nunca crie baralhos dentro das pastas do Talishar; use sempre o diretório central `decks/`.
4. **Sincronização de Templates:** Se alterar componentes no frontend (`Talishar-FE/`) ou backend (`Talishar/`), execute o script de exportação configurado no seu ambiente para manter `setup_templates/` atualizado.
5. **Vocabulário:** Use os termos definidos em `CONTEXT.md`. Não invente sinônimos.
6. **Multiagentes & Paralelismo com Subagentes:** Sempre que uma tarefa envolver múltiplas etapas independentes, refatorações em mais de um arquivo/módulo, pesquisas extensas de código, análises comparativas ou testes concorrentes, **SEMPRE distribua a execução utilizando subagentes (`invoke_subagent`)**.
   - Priorize disparar subagentes em paralelo para maximizar a velocidade de entrega e economizar a janela de contexto do agente principal.
   - Atribua papéis especializados e instruções cirúrgicas (ex: `Tooling Specialist`, `Refactor Specialist`, `Test Runner`, `Codebase Researcher`).
   - O agente principal atua como orquestrador: planeja a divisão de trabalho, dispara os subagentes em paralelo, aguarda reativamente as notificações de término (sem polling ativo), valida os resultados e consolida a entrega final.

### Multi-Agent Workflow

- **Distribuição Proativa:** Não execute tarefas sequenciais longas no processo principal se elas puderem ser paralelizadas. Delegue cada frente independente a um subagente dedicado.
- **Concorrência:** Se houver múltiplos arquivos para refatorar, múltiplos testes para analisar ou múltiplos tópicos de pesquisa, invoque subagentes simultaneamente em uma única chamada de `invoke_subagent`.
- **Especialização:** Use o campo `Role` com título claro de trabalho e `Prompt` com escopo estrito, arquivos-alvo e critérios de aceitação.
- **Reatividade:** Não faça loops ou polling de status; a plataforma acorda o agente automaticamente via mensagens quando o subagente finaliza.

### Execução de Comandos (Ambiente Linux Nativo)

**SEMPRE execute no diretório do projeto:**
- **Git:** `git <args>`
- **Python / Scripts:** `./venv/bin/python <script>`
- **Testes (Pytest):** `./venv/bin/python -m pytest <args>`
- **Docker:** `docker <args>`
- **Frontend (Node/NPM):** `npm <args>`
- **Comandos Linux/Bash:** `<comando>`

### Architecture

- O motor de IA é organizado em pacotes modulares em `ai/`:
  - `ai/bot_runtime/`: Runtime do bot (lobby, match tracker, choices, fases de decisão). Fachada raiz: `bot_client.py`.
  - `ai/policy/`: Poda tática (ataque, defesa, pitch, arsenal) e motor de decisão unificado. Fachada: `ai/policy_engine.py`.
  - `ai/mcts/`: Motores MCTS e ISMCTS paralelo multithread (`ThreadPoolExecutor`). Fachada: `ai/mcts/`.
  - `ai/training/`: Orquestrador de treino GPU FP16 e supervisor de processos. Fachada: `ai/trainer.py`.
  - `ai/hero_strategies/`: 139 heróis oficiais, `knapsack_solver.py`, `turn_planner.py`, `equipment_evaluator.py` e submódulos por classe.
  - `ai/model.py`, `ai/game_simulator.py`, `ai/experience_collector.py`, `ai/equipment_learning.py`.
- O gerenciamento de decks vive no pacote `deck_manager/` (fachada raiz: `deck_parser.py`).
- O sistema de ranking e estatísticas vive no pacote `stats/` (fachada raiz: `stats_manager.py`).
- O dashboard Streamlit é orquestrado por `dashboard.py` delegando para `ui/helpers.py` e `ui/tabs/` (7 abas).
- Patches do Talishar e Talishar-FE ficam em `setup_templates/` e são aplicados por `scripts/prepare_environment.py`.
- Banco de cartas oficial fica em `data/fab_cards_db.json` (extraído por `extract_card_db.py`).
- Testes automatizados usam `./venv/bin/pytest` isolados via `pytest.ini`.
