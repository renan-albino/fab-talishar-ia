# Revisão da Análise do Projeto FaB Talishar AI Engine

> Revisão ponto a ponto da análise anterior, com verificação no código real.
> Data: 2026-09-19. Cada veredito cita evidência `arquivo:linha`.

Legenda: ✅ Confirmado · ❌ Falso / mitigado · ⚠️ Parcial (premissa ou severidade ajustada)

---

## A. Segurança

| # | Ponto original | Veredito | Evidência / Correção |
|---|---|---|---|
| 1 | `chmod -R 777` é risco grave | ✅ Confirmado (ampliado) | `scripts/prepare_environment.py:308,313`, `start.sh:142`, `setup_templates/backend/APIs/CreateGame.php:82,253`, `.agents/skills/automated-tasks/scripts/healthcheck_talishar.py:227,235`. Contexto: containers rootless com `www-data` exigem escrita, mas o correto é `775` + grupo ou ACL, nunca `777`. Prioridade mantém 🔴. |
| 2 | Git hooks inline sem validação | ⚠️ Parcial, severidade baixa | `scripts/prepare_environment.py:395-429`, `scripts/manage_state.py:304-315`. Confirmado que são strings inline, mas **sem interpolação de input de usuário** — risco de injection é teórico. Recomendação rebaixada: extrair para arquivos em `scripts/hooks/` por manutenibilidade, não por segurança. |
| 3 | `APIKeys.php` a partir de template sem credenciais reais | ❌ Mitigado por design | `.gitignore:18` ignora `Talishar/` inteiro; `.gitignore:53-55` ignora `.env`. O arquivo com credenciais de fallback nunca é versionado. Nenhuma ação necessária além de manter o ignore. |
| 4 | `weights_only=True` causa incompatibilidade | ⚠️ Inversão: é boa prática | `ai/model.py:41,472`. `weights_only=True` **previne execução arbitrária via pickle** — deve ser mantido. O que falta é fallback de versão (mensagem atual já cria `.corrupted.bak`, o que é bom). Ação: adicionar log de `torch.__version__` no erro, não remover o flag. |
| 5 | Caminhos pessoais em `AGENTS.md` | ❌ Mitigado por design | `.gitignore:60-61` ignora `AGENTS.md` e versiona só `AGENTS.template.md`. `sync_agents_environment_rules` gera o arquivo local. Vazamento via commit é impossível salvo `git add -f`. Nenhuma ação. |

## B. Código & Manutenibilidade

| # | Ponto original | Veredito | Evidência / Correção |
|---|---|---|---|
| 6 | `conftest.py` mínimo | ✅ Confirmado | `conftest.py:1-4` — só `sys.path.insert`. Sem fixtures. Recomendação mantém: adicionar `mock_state()`, `mock_game()`. |
| 7 | `asyncio` nunca usado; `__future__` + threads | ⚠️ Fato ok, implicação errada | `grep asyncio`: zero ocorrências. `from __future__`: só `config/settings.py:26`, não "espalhado". Threads são a escolha correta aqui (MCTS CPU-bound + contexto CUDA compartilhado + polling HTTP bloqueante; `asyncio` não ajudaria). Retirar sugestão de migrar para `asyncio`. |
| 8 | Falta type hints em funções públicas | ❌ Exagerado | `ai/policy/card_evaluator.py:17`, `attack_pruner.py:18`, `defense_pruner.py:20`, `ai/mcts/ismcts.py:336-344`, `ai/bot_runtime/client.py:18-29` — todos com hints. Rebaixar para "completar hints em módulos legados pontuais", prioridade 🟢. |
| 9 | `model_info()` diz "800-dim" mas `STATE_DIM` é 832 | ✅ Confirmado | `ai/model.py:19` (`STATE_DIM = 832`) vs `ai/model.py:299` (`f"800-dim→..."`). Erro real de string hardcoded. Fix de 1 linha, prioridade 🔴 (polui logs/telemetria). |
| 10 | Mistura f-strings com `.format()` | ❌ Falso | `grep \.format\(` em `*.py`: zero ocorrências. Projeto já padronizado em f-strings. Remover item. |
| 11 | Falta docstrings nos pacotes filhos | ⚠️ Parcial | `ai/policy/__init__.py:1-5` e `ai/mcts/__init__.py:1-5` **têm** docstrings. Gap pode existir em submódulos individuais — auditar caso a caso em vez de afirmação genérica. |
| 12 | `sync_and_clean.sh` com limpeza hardcoded | ✅ Confirmado | `scripts/sync_and_clean.sh:104-107` — padrões `rm -f` fixos. Sugestão mantém: mover para variável/config no topo do script. |

## C. Testes

| # | Ponto original | Veredito | Evidência / Correção |
|---|---|---|---|
| 13 | `pytest.ini` com `-q` suprime detalhe | ⚠️ Parcial | `pytest.ini:3` (`-ra -q`). `-q` reduz verbosidade mas `-ra` preserva sumário. Sugestão válida (adicionar `--tb=short --strict-markers`), mas não é "supressão crítica". |
| 14 | Falta teste para `atomic_io` | ⚠️ Parcial | `test_atomic_json_save` **existe** em `tests/test_stats_manager.py:32`. O que falta: arquivo dedicado `test_atomic_io.py` com `file_lock` timeout + concorrência. Nenhum `test_atomic*` em `tests/` (glob confirma). |
| 15 | Falta teste para `config/settings` | ⚠️ Parcial | `test_settings_default_ismcts_concurrency` **existe** em `tests/test_ismcts_concurrency_modes.py:70`. Falta: `test_settings.py` dedicado às fórmulas (`_compute_batch_size`, `_compute_mcts_sims`, `_compute_workers`). |
| 16 | Falta teste para `manage_state` | ✅ Confirmado | Nenhum `test_manage_state*` em `tests/` (33 arquivos listados, nenhum cobre). Export/import/release merecem cobertura. |
| 17 | `conftest.py` sem fixtures | ✅ Confirmado | Decorrente do item 6. |
| 18 | Falta teste de integração e2e | ⚠️ Parcial | `test_policy_engine_integration` **existe** em `tests/test_all_hero_strategies.py:160`. O que falta é o ciclo completo sala→bot→resultado. Reescrever como "e2e completo ausente; integração parcial existe". |

## D. Performance

| # | Ponto original | Veredito | Evidência / Correção |
|---|---|---|---|
| 19 | Embeddings recarregados a cada import | ❌ Já otimizado | `ai/model.py:32-51` usa global `_CARD_EMBEDDINGS_TABLE` + early return — equivalente a `lru_cache`. Remover item. |
| 20 | `np.zeros` por chamada em `extract_state_vector` | ⚠️ Fato ok, severidade nula | `ai/model.py:313`: 832 floats ≈ 3,3 KB vs forward do Transformer em ms. Pooling adiciona risco de bug por economia irrelevante. Marcar como YAGNI — **não fazer** (Ponytail). |
| 21 | Fallback de latência impreciso | ⚠️ Design intencional | `config/settings.py:290-291`: fallback só quando `torch` ainda não importado (evita ~2 s de import no startup). Comportamento documentado no docstring. Manter; opcionalmente calibrar constantes. |
| 22 | `isinstance(state, dict)` repetidos | ⚠️ Baixa prioridade | Fato confirmado em `ai/model.py`, mas helper `_get()` economiza microssegundos. Prioridade 🟢 ou won't-fix. |

## E. Documentação

| # | Ponto original | Veredito | Evidência / Correção |
|---|---|---|---|
| 23 | `ROADMAP.md` desatualizado | ✅ Confirmado com evidência nova | `docs/ROADMAP.md:36` dizia **336 testes / 67,1%**; `README.md:306,519` dizia **377 testes**; contagem real atual expandida para **424 testes** (`pytest --collect-only`). `README` cita "ADR-0001 a ADR-0007" mas `docs/adr/` contém **ADR-0001..ADR-0008**. Sincronizar os três para 424 testes e ADRs 0001–0008. |
| 24 | `CONTRIBUTING.md` genérico | ⚠️ Parcial | `CONTRIBUTING.md` **existe** (58 linhas, onboarding + testes + regras de commit). Falta só: Conventional Commits, template de PR/issue. Complemento, não criação. |
| 25 | `AGENTS.template.md` dessincronizado | ✅ Confirmado, divergência real | Template (64 linhas) contém seções **Ponytail Protocol + Multi-Agent Workflow**; `AGENTS.md` gerado (47 linhas) **não** as contém. `sync_agents_environment_rules` só reescreve a seção de Execução — o restante nunca propaga. Decidir fonte da verdade e corrigir o sync. |
| 26 | Faltam ADRs para mudanças recentes | ⚠️ Parcial | `ADR-0001` (decomposição modular), `ADR-0005` (templates vs submódulos) e `ADR-0008` (concorrência híbrida) **existem**. O erro real é a contagem no README/ROADMAP ("0001–0007"). Corrigir contagem; avaliar ADR só para o que for genuinamente novo. |

## F. CI/CD

| # | Ponto original | Veredito | Evidência / Correção |
|---|---|---|---|
| 27 | CI só Python 3.10 | ✅ Confirmado | `.github/workflows/ci.yml:26` (`python-version: '3.10'`). Sugestão mantém: matriz 3.10/3.11/3.12. |
| 28 | CI sem `--cov` | ❌ Falso na premissa | `.github/workflows/ci.yml:43`: `pytest tests/ -v --cov=ai/ --timeout=30` **já tem** `--cov`. O que falta: threshold (`--cov-fail-under=...`) e upload (Codecov). Corrigir a recomendação. |
| 29 | CI sem `mypy` | ✅ Confirmado | Nenhuma etapa de tipos no `ci.yml`. Adicionar `mypy ai/`. |
| 30 | CI sem pre-commit | ✅ Confirmado | Sem `.pre-commit-config.yaml` no repo (glob confirma). |
| 31 | Frontend sem testes headless | ✅ Confirmado | `ci.yml:76-80` só faz `npm ci` + `npx vite build`. Sem `npm test`/`vitest`. |

## G. Funcionalidades / DevOps

| # | Ponto original | Veredito | Evidência / Correção |
|---|---|---|---|
| 32 | Falta `docker-compose.yml` na raiz | ⚠️ By design | Compose vive em `setup_templates/backend/docker-compose.yml` + `Talishar/` (gitignored, clonado). Wrapper na raiz é conveniência, não ausência. Prioridade 🟢. |
| 33 | Falta `.env.example` | ✅ Confirmado | Glob `.env*` na raiz: nada. Criar `.env.example` documentando `FAB_*`, `TALISHAR_SKIP_GPU_PROBE`, `GITHUB_TOKEN`. |
| 34 | Falta `docker-compose.override.yml` | ✅ Confirmado | Não existe. Útil para dev local sem tocar no compose base. |
| 35 | Falta `Makefile`/`justfile` | ✅ Confirmado | Glob `Makefile`: nada. Targets sugeridos: `setup test train start stop clean lint format`. |
| 36 | Falta `pyproject.toml`/`setup.py` | ✅ Confirmado | Glob `**/pyproject.toml`: nada. Centralizaria `ruff`, `mypy`, `pytest`. |
| 37 | Falta healthchecks Docker | ✅ Confirmado | `setup_templates/backend/docker-compose.yml:13-78`: nenhum bloco `healthcheck:`, `depends_on` sem condição. Adicionar `healthcheck` em `web-server`, `mysql-server`, `redis`. Nota: contém `MYSQL_ROOT_PASSWORD: "secret"` e `PMA_PASSWORD` hardcoded (linhas 39,56,69) — mover para `.env` junto do item 33. |

---

## Plano de ação corrigido

### 🔴 Fazer primeiro
1. **Permissões** (item 1): trocar `777` → `775` + grupo/`setgid` ou ACL; documentar o motivo rootless no README. Inclui `CreateGame.php` e `healthcheck_talishar.py`.
2. **`model_info()`** (item 9): usar `{self.state_dim}` em vez de `"800-dim"`.
3. **Sincronia de docs** (itens 23, 26, 28): unificar contagem de testes (fixar 424 testes reais via `pytest --collect-only`), contagem de ADRs (0001–0008) e descrição do `--cov`.
4. **Divergência AGENTS** (item 25): decidir se Ponytail/Multi-Agent valem para o `AGENTS.md` gerado; se sim, incluir no sync.
5. **Testes ausentes reais** (itens 6, 16, 17): fixtures em `conftest.py` + `test_manage_state.py` + `test_atomic_io.py` (lock/timeout).

### 🟡 Em seguida
- `test_settings.py` para as fórmulas (item 15), threshold de cobertura no CI (item 28 corrigido), `mypy` no CI (29), matriz Python (27), `.env.example` + segredos do compose via `.env` (33, 37), `healthcheck:` no compose (37), `sync_and_clean.sh` com padrões configuráveis (12), `pytest.ini` com `--tb=short --strict-markers` (13), CONTRIBUTING com Conventional Commits (24).

### 🟢 Se / quando sobrar tempo
- `Makefile`, `pyproject.toml` (`ruff` + `mypy` + `pytest` centralizados), `docker-compose.override.yml`, wrapper de compose na raiz (32), completar hints/docstrings pontuais (8, 11), calibrar fallback de latência (21).

### ❌ Não fazer (itens refutados)
- **10** (`.format` — já é f-string), **19** (cache de embeddings — já existe), **20** (pool de `np.zeros` — YAGNI), **7-asyncio** (threads são adequadas), **3/5** (protegidos pelo `.gitignore`), **4-remover-`weights_only`** (é proteção; só melhorar a mensagem de erro).
