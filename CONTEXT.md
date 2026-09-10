# CONTEXT.md — FaB Talishar AI Engine

Glossary of domain terms used in this project. AI agents and contributors must use these terms exactly as defined here.

## Domain: Flesh and Blood (FaB)

- **FaB**: Flesh and Blood, the trading card game by Legend Story Studios.
- **Herói (Hero)**: The character card that defines the class and abilities of a player's deck.
- **Arsenal**: A face-down zone where a player can store one card per turn for future use.
- **Pitch**: The act of placing a card from hand into the pitch zone to generate resource points for paying costs. Cards have pitch values of 1 (red), 2 (yellow), or 3 (blue).
- **Go Again**: A keyword that grants an additional action point after an attack resolves.
- **Combat Chain**: The sequence of attack and defense actions in a single engagement.
- **Action Point (AP)**: A resource that allows a player to play action cards or activate abilities.

## Domain: AI Engine

- **ISMCTS (Information Set Monte Carlo Tree Search)**: A variant of MCTS designed for imperfect-information games. It samples determinized worlds by filling the opponent's hidden hand from a class-filtered card pool.
- **World / Determinization**: A single hypothetical complete game state where all hidden information (opponent's hand) has been filled in with plausible cards.
- **Deck-Aware World Sampling**: The process of sampling determinized worlds using `fab_cards_db.json` to filter cards by the opponent's hero class, producing realistic hidden hands.
- **Policy Head**: The neural network output that produces a probability distribution over possible actions.
- **Value Head**: The neural network output that estimates the probability of winning from the current state, in the range [-1.0, 1.0].
- **Prior Shaping**: Using heuristic card evaluations (from `ai/hero_strategies/`) to bias the initial action probabilities in MCTS expansion.
- **Tempo Pivot**: A defensive strategy where the bot preserves cards in hand for a strong counter-attack next turn instead of over-blocking.
- **Overblocking**: Assigning more defense value than necessary to block an attack, wasting cards that could be used offensively.
- **GameSimulator**: The deterministic state-transition engine (`ai/game_simulator.py`) that projects future game states without randomness.
- **Replay Buffer**: Buffer circular (`ai/experience_collector.py`) que armazena experiências (estado, ação, recompensa) para treinamento off-policy da rede neural. Usa escrita atômica via `.tmp.npz`.
- **Batch Leaf Evaluation**: Técnica em `ai/mcts.py` que agrupa múltiplas folhas MCTS em um único forward pass da rede neural, reduzindo latência de O(N) para O(1).
- **Progressive Widening**: Restrição no MCTS que limita filhos expandidos a √N, focando a busca nos ramos mais promissores.
- **Prior Threshold Pruning**: Poda de ações com prior abaixo de −1.5σ da média, eliminando movimentos claramente inferiores durante a expansão MCTS.
- **Distilação Assimétrica (Asymmetric Distillation)**: Treinamento da rede neural usando a distribuição de visitas do MCTS (π_MCTS) como target via Cross-Entropy/KL-Divergence, em vez de vitória/derrota binária.
- **CR 3.1.5**: Regra oficial de Flesh and Blood que proíbe Resource/Gem cards de serem colocadas no Arsenal. Implementada em `ai/hero_strategies/` com score −9999.0.

## Domain: Architecture

- **Bot Client (`bot_client.py`)**: The autonomous agent that connects to the Talishar backend, reads game state, and submits actions.
- **Dashboard (`dashboard.py`)**: The Streamlit web interface for training, analytics, arena combat, and ISMCTS telemetry.
- **Setup Templates (`setup_templates/`)**: Patches and custom files that are injected into the cloned Talishar and Talishar-FE repositories to extend their functionality for AI integration. This is the only source of truth for project-specific modifications to the Talishar ecosystem.
- **Decks Directory (`decks/`)**: The single source of truth for all deck JSON files. No deck is ever duplicated into Talishar's internal folders.
- **Chess Advantage Tracker**: The frontend component (`ChessAdvantageTracker.tsx`) that displays a Stockfish/Chess.com-style advantage bar during games.
- **Elo Rating**: The rating system used in `stats_manager.py` to rank bot performance across training matches.
