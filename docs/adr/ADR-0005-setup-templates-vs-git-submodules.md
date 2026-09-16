# ADR-0005: Desacoplamento do Ecossistema Talishar via setup_templates e Injeção de Patches

- **Status**: Accepted
- **Date**: 2026-09-16
- **Deciders**: Equipe FaB Talishar AI (Architecture Review)

## Context

O projeto FaB Talishar AI estende e opera sobre dois repositórios abertos da comunidade:
1. **Talishar** (Backend em PHP/Apache/Docker): Motor de execução de regras de Flesh and Blood e estado de jogo em arquivos de log.
2. **Talishar-FE** (Frontend em React, TypeScript e Vite): Interface visual web para interação dos jogadores.

Para permitir que agentes autônomos de IA interajam perfeitamente com a plataforma, foram necessárias dezenas de modificações estruturais:
- Criação de novos endpoints de API REST no PHP (`APIs/APIParseGamefile.php`, `APIs/SubmitSideboard.php`, `APIs/AppendGameLog.php`, `AI/CombatDummy.php`).
- Configurações estendidas de Docker Compose (`docker-compose.yml`), parâmetros de ambiente e bibliotecas de HTTP.
- Componentes visuais personalizados no React (`ChessAdvantageTracker.tsx`, barra de vantagem tática estilo Stockfish, integração do chat do bot em `ChatBox.tsx`).
- Mock headless de anúncios (`bannerUnit/`) para impedir que dependências externas bloqueiem a compilação offline do Vite.

O uso de abordagens tradicionais como **Git Submodules** ou **Forks Permanentes** trazia sérios problemas:
- Submódulos Git frequentemente entravam em estado de ponteiro desincronizado (*detached HEAD*), quebrando o pipeline de CI e a inicialização de novos ambientes.
- Atualizações frequentes de regras de cartas vindas do repositório original do Talishar geravam conflitos intrincados de merge.
- Risco contínuo de commits acidentais de logs, arquivos de partidas (`Talishar/Games/`) ou credenciais privadas dentro de subárvores Git.

## Decision

Desacoplar totalmente a base de código do motor de IA dos repositórios upstream através da estratégia de **Setup Templates com Injeção Declarativa**:

### 1. `setup_templates/` como Única Fonte da Verdade (SSOT)
- O diretório central `setup_templates/` armazena exclusivamente os arquivos modificados ou novos criados para o backend e frontend:
  - `setup_templates/backend/`: Endpoints PHP, docker-compose e bibliotecas.
  - `setup_templates/frontend/`: Componentes React, estilos CSS, slices do Redux e mock de anúncios.
- Nenhum subrepositório Git interno é versionado como submódulo dentro do projeto raiz.

### 2. Sincronização e Provisionamento Automatizado via `scripts/prepare_environment.py`
- O script unificado mapeia declarativamente cada arquivo de template para sua localização de destino em `Talishar/` e `Talishar-FE/` (`BACKEND_MAPPINGS` e `FRONTEND_MAPPINGS`).
- Ao provisionar uma nova máquina ou container Docker, basta clonar os repositórios limpos do Talishar e executar:
  ```bash
  python scripts/prepare_environment.py
  ```
- O script aplica todos os templates, ajusta permissões de escrita (`chmod 775` em `Talishar/Games/` e `logs/`), valida o banco de dados oficial de cartas e inicializa os containers.

### 3. Sincronização Reversa via `--export-templates`
- Caso um desenvolvedor ou agente realize melhorias ou correções diretamente dentro de `Talishar/` ou `Talishar-FE/`, o comando:
  ```bash
  python scripts/prepare_environment.py --export-templates
  ```
  copia cirurgicamente as alterações de volta para `setup_templates/`.

### 4. Salvaguarda no Pré-Commit (`scripts/sync_and_clean.sh`)
- O hook pré-commit do projeto valida a integridade dos templates, compila o frontend Vite (`npx vite build`) e impede o commit caso existam divergências não sincronizadas entre `Talishar(-FE)` e `setup_templates/`.

## Consequences

### Positive
- **Imunidade a Quebras de Upstream**: As atualizações do Talishar original podem ser testadas e integradas sem risco de corromper o repositório principal de IA.
- **Portabilidade Rápida e Determinística**: O ambiente de desenvolvimento pode ser completamente destruído e reconstruído em minutos em qualquer distribuição Linux ou WSL2.
- **Repositório Central Limpo**: O Git versiona apenas o código do motor de IA, testes e os templates específicos de integração, mantendo o histórico conciso e focado.

### Negative / Trade-offs
- **Disciplina Operacional**: Exige dos desenvolvedores e agentes o hábito estrito de exportar os templates (`--export-templates`) antes de commitar mudanças no frontend ou backend (garantido pela Regra 4 de `AGENTS.md`).

## Alternatives Considered

- **Git Submodules**: Rejeitado por seu histórico crônico de desincronização de branches, dificuldades de checkout em pipelines automatizados e poluição de histórico.
- **Git Subtree**: Rejeitado pelo aumento excessivo do tamanho do repositório principal e complexidade de comandos para desenvolvedores e agentes de IA.
- **Unified Diff Patches (`git apply`)**: Rejeitado porque mudanças insignificantes no código do Talishar original quebravam a aplicação de linhas de contexto dos patches (`patch rejected: hunks failed`).
