# ADR-0013: Modo Sombra (Shadow Mode) para Medição de Fidelidade do Simulador

## Status
Aceito (Fase 0)

## Contexto
O projeto FaB Talishar AI baseia suas decisões em árvores de busca de Monte Carlo (MCTS). Para que o MCTS seja eficaz, o simulador local (`GameSimulator`) precisa prever com precisão as consequências de uma ação antes de enviá-la para o Talishar. Se o simulador prevê que uma carta gasta 1 recurso, mas o servidor cobra 2, a IA tomará decisões baseadas em falsas premissas, causando blunders ou descarte subótimo.

Precisamos de uma forma contínua e passiva de medir a taxa de acerto do nosso simulador em relação ao servidor oficial (Talishar), construindo confiança gradual para o produto e fornecendo dados de debug para os desenvolvedores.

## Decisão
Implementamos um "Modo Sombra" (`shadow_mode`) acoplado ao envio de ações (`send_action`) do bot:
1. Ao decidir uma ação, o bot gera uma predição local do próximo estado usando `simulate_step`.
2. Essa predição e o estado original são cacheados temporariamente.
3. Quando o próximo estado real (`handle_game_tick`) chega do backend via WebSocket/HTTP, comparamos a predição local com o estado real.
4. As diferenças (diffs) de métricas-chave (tamanho da mão, recursos, pontos de ação, arsenal) são gravadas em uma tabela SQLite dedicada (`shadow_steps`).

Adicionalmente, introduzimos suporte à extração de "Puzzles Dourados" (`extract_puzzle.py`) a partir dos `pre_state_json` salvos no banco para permitir regressão contínua em momentos cruciais, onde humanos experientes tomam ações específicas.

## Consequências
- **Positivas:** Permite quantificar exatamente a "% de Fidelidade" do simulador. Cria um pipeline para encontrar e consertar regras faltantes. Facilita muito a construção de testes unitários reais sem criar JSONs na mão.
- **Negativas:** Leve overhead de CPU no cliente por simular ações que já vão ser validadas pelo backend; pequeno aumento no tamanho do DB (mitigado por limite de expurgo se necessário no futuro).
