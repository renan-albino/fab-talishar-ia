---
name: automated-tasks
description: Ready-made scripts for tasks that repeat in this workspace. Use before doing a routine server, service, or data task by hand.
---

# Automated Tasks

Scripts utilitários prontos e robustos para automação de tarefas rotineiras do ecossistema FaB Talishar AI. Cada script reside em `.agents/skills/automated-tasks/scripts/` e pode ser executado a partir da raiz do repositório utilizando `./venv/bin/python` ou diretamente como executável.

| Script | O que faz |
| --- | --- |
| `validate_decks.py` | Valida baralhos JSON em `decks/` contra o banco oficial `data/fab_cards_db.json` e regras de torneio (Classic Constructed e Blitz). Suporta `--fix` para autocorreção. |
| `benchmark_mcts.py` | Executa benchmarks de vazão e latência do MCTS e ISMCTS (`rollouts/s`, decisões/s, percentis p50/p90/p95/p99) com suporte a multi-threading e inferência neural. |
| `healthcheck_talishar.py` | Diagnóstico de saúde do ecossistema: portas ativas (8080 Apache/PHP, 3000 Vite FE, 8501 Streamlit), status de Podman/Docker, permissões de disco e integridade do banco de cartas. Suporta `--fix`. |
| `run_smoke_tests.py` | Bateria rápida de validação em 3 etapas (sub-3s): sintaxe `py_compile`, sanidade de imports de todas as fachadas e execução de suíte de testes essencial do pytest. |

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
./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py

# Validar um deck específico com slots detalhados
./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py --deck decks/jarl.json --verbose

# Validar e corrigir inconformidades automaticamente
./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py --fix

# Saída em formato JSON para automações
./venv/bin/python .agents/skills/automated-tasks/scripts/validate_decks.py --json
```

### Códigos de Saída (Exit Codes)

- `0`: Todos os baralhos avaliados são válidos (ou foram corrigidos com sucesso).
- `1`: Um ou mais baralhos permanecem inválidos ou com inconsistências de regras.
- `2`: Erro crítico (ex: `data/fab_cards_db.json` não encontrado).

---

## 2. `benchmark_mcts.py`

Mede throughput e latência dos algoritmos de busca determinizada do bot (MCTS e Information Set MCTS).

### Parâmetros CLI

- `--engine {both,mcts,ismcts}`: Define qual motor avaliar (padrão: `both`).
- `--sims <int>`: Número de simulações MCTS por decisão (padrão: `25`).
- `--worlds <int>`: Quantidade de mundos determinizados ISMCTS (padrão: `4`).
- `--threads <int>`: Número de threads simultâneas para despacho de buscas (padrão: `1`).
- `--decisions, --iterations <int>`: Quantidade de decisões avaliadas no teste (padrão: `10`).
- `--no-nn`: Desativa inferência da rede neural para medir apenas vazão estrutural da árvore.
- `--device <str>`: Dispositivo PyTorch (`cpu` ou `cuda`, padrão: `cpu`).
- `--json`: Retorna resultados em formato JSON estruturado.
- `-h, --help`: Exibe mensagem de ajuda.

### Exemplos de Uso

```bash
# Benchmark padrão de ambos os motores (MCTS e ISMCTS)
./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py

# Teste de alta carga concorrente (4 threads, 50 simulações, 20 decisões)
./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py --threads 4 --sims 50 --decisions 20

# Avaliar apenas ISMCTS sem rede neural (pura árvore)
./venv/bin/python .agents/skills/automated-tasks/scripts/benchmark_mcts.py --engine ismcts --no-nn
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
./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py

# Diagnóstico com remediação automática de permissões e templates
./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py --fix

# Exportar telemetria de saúde para JSON
./venv/bin/python .agents/skills/automated-tasks/scripts/healthcheck_talishar.py --json
```

### Códigos de Saída (Exit Codes)

- `0`: Sistema saudável (ou apenas avisos normais de serviços offline que ainda não foram iniciados).
- `2`: Erros críticos detectados (ex: banco de dados de cartas corrompido ou pastas sem permissão de escrita).

---

## 4. `run_smoke_tests.py`

Bateria de validação rápida para execução pré-commit ou em pipelines de CI, rodando em sub-3s:
1. **Sintaxe (`py_compile`)**: Verifica compilação de todos os arquivos `.py` do projeto.
2. **Imports de Fachadas**: Importa e valida símbolos fundamentais das 11 principais fachadas do sistema.
3. **Pytest Essencial**: Executa suíte de 26 testes unitários rápidos cobrindo modelos, simulação, parsers e regras.

### Parâmetros CLI

- `--skip-compile`: Pula a etapa de validação sintática (`py_compile`).
- `--skip-imports`: Pula o teste de sanidade de imports das fachadas.
- `--skip-tests`: Pula a execução dos testes automatizados via `pytest`.
- `--test-suite {essential,all}`: Seleciona suíte rápida (`essential`, sub-3s) ou completa (`all`).
- `--json`: Retorna relatório dos testes em formato JSON.
- `-v, --verbose`: Exibe saída detalhada de compilação e imports.
- `-h, --help`: Exibe mensagem de ajuda.

### Exemplos de Uso

```bash
# Executar smoke tests completos (sintaxe + imports + pytest essencial)
./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py

# Executar validação de sintaxe e imports ignorando testes pytest
./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py --skip-tests

# Exibir detalhes verbosos de cada módulo
./venv/bin/python .agents/skills/automated-tasks/scripts/run_smoke_tests.py -v
```

### Códigos de Saída (Exit Codes)

- `0`: Todas as 3 etapas foram aprovadas com sucesso.
- `1`: Falha em qualquer uma das etapas (erro sintático, falha de importação ou teste falhado).
