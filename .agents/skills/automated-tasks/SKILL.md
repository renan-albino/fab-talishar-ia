---
name: automated-tasks
description: Ready-made scripts for tasks that repeat in this workspace. Use before doing a routine server, service, or data task by hand.
---

# Automated Tasks

Scripts utilitários prontos e robustos para automação de tarefas rotineiras do ecossistema FaB Talishar AI. Cada script reside em `.agents/skills/automated-tasks/scripts/` e deve ser executado a partir do host Windows invocando explicitamente o runtime WSL2: `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/<script>.py`.

| Script | O que faz |
| --- | --- |
| `validate_decks.py` | Valida baralhos JSON em `decks/` contra o banco oficial `data/fab_cards_db.json` e regras de torneio (Classic Constructed e Blitz). Suporta `--fix` para autocorreção. |
| `benchmark_mcts.py` | Executa benchmarks de vazão e latência do MCTS e ISMCTS (`rollouts/s`, decisões/s, percentis p50/p90/p95/p99), `HeadlessSelfPlayLoop` (`--include-headless`) e `ReplayBuffer` PER (`--include-per`). |
| `healthcheck_talishar.py` | Diagnóstico de saúde do ecossistema: portas ativas (8080 Apache/PHP, 3000 Vite FE, 8501 Streamlit), status de Podman/Docker, permissões de disco e integridade do banco de cartas. Suporta `--fix`. |
| `run_smoke_tests.py` | Bateria rápida de validação em 3 etapas (sub-3s): sintaxe `py_compile`, sanidade de imports de todas as 13 fachadas e execução de suíte de testes essencial do pytest. |
| `diagnose_sim2real.py` | Inspeciona anomalias Sim2Real (`sim2real_anomalies` + fallback JSONL) e telemetria do Modo Sombra (`shadow_steps`: % fidelidade exata, % ticks transitórios e ranking de divergências). |
| `run_headless_tournament.py` | Executa torneios competitivos (`swiss` ou `round_robin`) 100% em memória via `TournamentManager(execution_mode="headless")` com desempates Buchholz, Sonneborn-Berger e ELO. |

---

## 1. `validate_decks.py`

Valida baralhos no formato JSON contra o banco oficial de 10.144 cartas (`data/fab_cards_db.json`) e regras competitivas de Flesh and Blood.

### Parâmetros CLI

- `--deck <path>`: Caminho para validar um arquivo de deck específico (ex: `decks/jarl.json`).
- `--decks-dir <dir>`: Diretório para varredura de múltiplos baralhos (padrão: `decks`).
- `--fix`: Aplica correções automáticas de metadados, normalização de chaves de cartas (`count` -> `total`) e sincronização de formato coerente com o Herói.
- `--json`: Retorna o relatório em formato JSON estruturado.
- `-v, --verbose`: Exibe detalhamento de slots de equipamentos e armas.
- `-h, --help`: Exibe mensagem de ajuda.

### Exemplos de Uso

```bash
# Validar todos os baralhos de decks/
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py

# Validar um deck específico com slots detalhados
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py --deck decks/jarl.json --verbose

# Validar e corrigir inconformidades automaticamente
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py --fix

# Saída em formato JSON para automações
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py --json
```

### Códigos de Saída (Exit Codes)

- `0`: Todos os baralhos avaliados são válidos (ou foram corrigidos com sucesso).
- `1`: Um ou mais baralhos permanecem inválidos ou com inconsistências de regras.
- `2`: Erro crítico (ex: `data/fab_cards_db.json` não encontrado).

---

## 2. `benchmark_mcts.py`

Mede throughput e latência dos algoritmos de busca determinizada do bot (MCTS e Information Set MCTS), além da vazão de partidas completas em memória (`HeadlessSelfPlayLoop`) e operações vetorizadas de Prioritized Experience Replay (`ReplayBuffer`).

### Parâmetros CLI

- `--engine {both,mcts,ismcts}`: Define qual motor avaliar (padrão: `both`).
- `--sims <int>`: Número de simulações MCTS por decisão (padrão: `25`).
- `--worlds <int>`: Quantidade de mundos determinizados ISMCTS (padrão: `4`).
- `--threads <int>`: Número de threads simultâneas para despacho de buscas (padrão: `1`).
- `--decisions, --iterations, --states <int>`: Quantidade de decisões avaliadas no teste (padrão: `10`).
- `--no-nn`: Desativa inferência da rede neural para medir apenas vazão estrutural da árvore.
- `--device <str>`: Dispositivo PyTorch (`cpu` ou `cuda`, padrão: `cpu`).
- `--include-headless`: Mede `HeadlessSelfPlayLoop` (`ai/training/headless_env.py`): jogos/min e steps/s.
- `--headless-games <int>`: Quantidade de partidas completas para `--include-headless` (padrão: `4`).
- `--include-per`: Mede `ReplayBuffer` (`ai/experience_collector.py`): latência de `set_all`, `sample_batch` e `update_priorities`.
- `--json`: Retorna resultados em formato JSON estruturado.
- `-h, --help`: Exibe mensagem de ajuda.

### Exemplos de Uso

```bash
# Benchmark completo (MCTS, ISMCTS, Headless Self-Play e ReplayBuffer PER)
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py --include-headless --include-per

# Teste rápido com saída JSON
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py --sims 4 --states 2 --include-per --json

# Avaliar apenas ISMCTS sem rede neural (pura árvore)
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py --engine ismcts --no-nn
```

### Códigos de Saída (Exit Codes)

- `0`: Benchmark executado com sucesso e relatório gerado.
- `1`: Falha na execução ou argumentos inválidos.

---

## 3. `healthcheck_talishar.py`

Verifica a conectividade de rede, o container runtime e a integridade de disco do ecossistema de simulação.

### Parâmetros CLI

- `--fix`: Tenta corrigir automaticamente permissões de pastas (`Talishar/Games/`, `logs/`, etc.), subir containers via Docker/Podman e reconstruir o banco de cartas ausente via `extract_card_db.py`.
- `--host <ip>`: Endereço IP/host para testes de portas de rede (padrão: `127.0.0.1`).
- `--timeout <float>`: Timeout em segundos para testes de conexão de rede (padrão: `0.5s`).
- `--json`: Retorna o relatório de saúde em formato JSON estruturado.
- `-v, --verbose`: Exibe detalhes completos de cada componente avaliado.
- `-h, --help`: Exibe mensagem de ajuda.

### Exemplos de Uso

```bash
# Executar diagnóstico de saúde
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py

# Diagnóstico com remediação automática de permissões e templates
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py --fix

# Exportar telemetria de saúde para JSON
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py --json
```

### Códigos de Saída (Exit Codes)

- `0`: Sistema saudável (ou apenas avisos normais de serviços offline que ainda não foram iniciados).
- `2`: Erros críticos detectados (ex: banco de dados de cartas corrompido ou pastas sem permissão de escrita).

---

## 4. `run_smoke_tests.py`

Bateria de validação rápida para execução pré-commit ou em pipelines de CI, rodando em sub-3s:
1. **Sintaxe (`py_compile`)**: Verifica compilação de todos os arquivos `.py` do projeto.
2. **Imports de Fachadas**: Importa e valida símbolos fundamentais das 13 principais fachadas do sistema (incluindo `stats.tournament_manager` e `ai.shadow_mode`).
3. **Pytest Essencial**: Executa suíte de testes unitários rápidos cobrindo modelos, simulação, parsers e regras.

### Parâmetros CLI

- `--skip-compile`: Pula a etapa de validação sintática (`py_compile`).
- `--skip-imports`: Pula o teste de sanidade de imports das fachadas.
- `--skip-tests, --skip-pytest`: Pula a execução dos testes automatizados via `pytest`.
- `--test-suite {essential,all}`: Seleciona suíte rápida (`essential`, sub-3s) ou completa (`all`).
- `--json`: Retorna relatório dos testes em formato JSON.
- `-v, --verbose`: Exibe saída detalhada de compilação e imports.
- `-h, --help`: Exibe mensagem de ajuda.

### Exemplos de Uso

```bash
# Executar smoke tests completos (sintaxe + imports + pytest essencial)
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py

# Executar validação de sintaxe e imports ignorando testes pytest
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py --skip-pytest --json

# Exibir detalhes verbosos de cada módulo
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py -v
```

### Códigos de Saída (Exit Codes)

- `0`: Todas as 3 etapas foram aprovadas com sucesso.
- `1`: Falha em qualquer uma das etapas (erro sintático, falha de importação ou teste falhado).

---

## 5. `diagnose_sim2real.py`

Inspeciona anomalias Sim2Real (`stats.db.get_recent_sim2real_anomalies` + fallback `logs/sim2real_anomalies.jsonl`) e métricas de fidelidade da tabela `shadow_steps` no SQLite (`data/talishar_stats.db`).

### Parâmetros CLI

- `--limit <int>`: Limite de anomalias recentes retornadas (padrão: `25`).
- `--hero <str>`: Filtra anomalias e passos do Modo Sombra por herói/slug.
- `--type <str>`: Filtra anomalias por `anomaly_type` (ex: `SHADOW_DIFF`, `ILLEGAL_ACTION`, `STATE_STUCK`).
- `--json`: Retorna diagnóstico completo em formato JSON estruturado.

### Exemplos de Uso

```bash
# Resumo geral de fidelidade do Modo Sombra e anomalias Sim2Real
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/diagnose_sim2real.py

# Filtrar por herói e exportar JSON
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/diagnose_sim2real.py --hero jarl --json
```

---

## 6. `run_headless_tournament.py`

Instancia `TournamentManager` (`stats/tournament_manager.py`) com `execution_mode="headless"` e executa torneios Swiss ou Round-Robin em memória, exibindo tabela final com Pontos, W-L-D, Buchholz, Sonneborn-Berger e ELO.

### Parâmetros CLI

- `--format {swiss,round_robin}`: Formato do torneio (padrão: `swiss`).
- `--rounds <int>`: Número de rodadas para formato Swiss (padrão: `ceil(log2(N))`).
- `--sims <int>`: Simulações MCTS por decisão no modo headless (padrão: `2`).
- `--decks <slug1,slug2,...>`: Slugs específicos separados por vírgula.
- `--max-decks <int>`: Quantidade máxima de decks se `--decks` for omitido (padrão: `4`).
- `--json`: Retorna a tabela final e partidas em JSON.

### Exemplos de Uso

```bash
# Executar torneio Swiss Headless rápido com 4 decks
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/run_headless_tournament.py --format swiss --max-decks 4 --sims 2

# Executar Round-Robin entre decks específicos com saída JSON
wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python .agents/skills/automated-tasks/scripts/run_headless_tournament.py --format round_robin --decks jarl,dash_io,kayo --json
```

