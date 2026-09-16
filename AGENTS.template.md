# AGENTS.template.md — FaB Talishar AI Engine

Template de diretrizes e regras para agentes de IA. Execute `python scripts/prepare_environment.py` para gerar o `AGENTS.md` local customizado para sua máquina e runtime específico.

## Agent skills

### Issue tracker

Issues are tracked in GitHub Issues on `renan-albino/fab-talishar-ia`. See `docs/agents/issue-tracker.md`.

### Domain docs

Single-context layout: one `CONTEXT.md` at the repo root, ADRs in `docs/adr/`. See `docs/agents/domain.md`.

## Project Rules

### Workspace Conventions

1. **Respeite o `.geminiignore`:** Nunca leia arquivos de logs brutos (`logs/*.log`), backups de partidas ou checkpoints binários de rede neural (`*.pt`).
2. **Foco Cirúrgico:** Realize edições pontuais no arquivo exato alvo usando substituições de bloco. Não reescreva arquivos inteiros.
3. **Decks em `decks/`:** Nunca crie baralhos dentro das pastas do Talishar; use sempre o diretório central `decks/`.
4. **Sincronização de Templates:** Se alterar componentes no frontend (`Talishar-FE/`) ou backend (`Talishar/`), execute o script de exportação configurado no seu ambiente para manter `setup_templates/` atualizado.
5. **Vocabulário:** Use os termos definidos em `CONTEXT.md`. Não invente sinônimos.

### Execução de Comandos (Configurado por scripts/prepare_environment.py)

O script `scripts/prepare_environment.py` detecta automaticamente se seu ambiente é WSL2 ou Linux Nativo e preenche esta seção no seu `AGENTS.md` local com os caminhos corretos:

- **WSL2 (Windows Host):** Comandos executados via `wsl -d <distro> --cd <caminho_linux> ...`
- **Linux Nativo:** Comandos executados diretamente no shell `./venv/bin/python ...`

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

