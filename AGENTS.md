# AGENTS.md — FaB Talishar AI Engine

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
4. **Sincronização de Templates:** Se alterar componentes no frontend (`Talishar-FE/`) ou backend (`Talishar/`), execute `./venv/bin/python scripts/prepare_environment.py --export-templates` para manter `setup_templates/` atualizado.
5. **Vocabulário:** Use os termos definidos em `CONTEXT.md`. Não invente sinônimos.

### Architecture

- O motor de IA vive em `ai/` (model, mcts, policy_engine, game_simulator, trainer, hero_strategies).
- O agente autônomo é `bot_client.py` na raiz.
- O dashboard Streamlit é `dashboard.py` na raiz.
- Patches do Talishar e Talishar-FE ficam em `setup_templates/` e são aplicados por `scripts/prepare_environment.py`.
- Banco de cartas oficial fica em `data/fab_cards_db.json` (extraído por `extract_card_db.py`).
