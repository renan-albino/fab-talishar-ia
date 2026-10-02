# ADR-0012: Causal Dynamic Tuning, Anti-Spiral Clamp, MCTS Enhancements, and Stratified PER

- **Status**: Aceito
- **Data**: 2026-10-01
- **Decisores**: Renan Albino & Antigravity AI Engine Specialist

---

## 1. Contexto

Durante o treinamento concorrente e auto-tuning de heróis, dois problemas arquiteturais críticos foram identificados:
1. **Efeito Espiral do Auto-Tuner Heurístico**:
   O `DynamicRuleTuner` tratava derrotas de forma cega com `win_rate < 0.45` aumentando `block_weight` para até `1.40` e reduzindo `attack_weight` para `0.80` em heróis não-aggro. Isso forçava baralhos perdedores a uma postura excessivamente passiva (bloquear com a mão inteira), acelerando mortes por fadiga e impedindo qualquer recuperação de tempo.
2. **Desconexão de Rate e Desperdício de Informação**:
   - O gerador de mundos ISMCTS (`world_generator.py`) descartava a informação pública de que cartas na zona de pitch vão ordenadas para o fundo do baralho (pitch stacking).
   - O ruído de Dirichlet no MCTS utilizava parâmetros de Go ($N \approx 362$) gerando ruído quase uniforme em espaços reduzidos do FaB ($N \in [2, 6]$).
   - A fusão Heurística-NN na raiz usava divisor constante $2.5$, perpetuando o viés do knapsack mesmo em redes neurais avançadas.
   - O Prioritized Experience Replay (PER) era monolítico e cego a heróis, sub-representando heróis raros (Gravy Bones, Teklovossen).
   - O `BlunderReviewer` classificava blefes e decisões baseadas em assimetria de informação como "blunders severos", inflando prioridades espúrias.

---

## 2. Decisão Arquitetural

Implementou-se um conjunto coordenado de 6 melhorias estruturais:

### 2.1 Diagnóstico Causal e Clamp Anti-Espiral (`ai/dynamic_rule_tuner.py`)
- **Limites Rígidos**: Clamp estrito em $[0.85, 1.15]$ ($\pm 15\%$ de desvio máximo do neutro).
- **Diagnóstico Causal via Taxa de Valor por Turno (HVCR)**:
  - `tempo_race`: Oponente terminou com $\le 15\%$ do HP inicial ($\le 6$ em CC, $\le 3$ em Blitz). Refina `pivot_bonus` (+0.02) e `arsenal_bonus` (+0.015) sem alterar `block_weight`.
  - `overblocking`: Turnos longos com DPS do bot abaixo do esperado. Reduz `block_weight` (-0.02) e eleva `absorb_tempo_bonus` (+0.02).
  - `low_hand_conversion`: Turnos normais com ineficiência líquida. Eleva `attack_weight` (+0.02) e `pivot_bonus` (+0.02).
  - `fast_bleed`: Jogo encerrado precocemente por explosão de dano. Eleva sutilmente `block_weight` (+0.015, teto 1.08).
  - `generic_loss` / Equilíbrio: Decaimento exponencial suave rumo ao neutro ($0.96$).

### 2.2 Pitch Stacking no MCTS (`ai/mcts/world_generator.py`)
- As cartas de `playerPitch` são preservadas como `playerDeckBottom` nos mundos simulados `ImmutableGameState`, permitindo ao MCTS prever com precisão compras do segundo ciclo.

### 2.3 Dirichlet Calibrado para o Espaço de Ações do FaB (`ai/mcts/standard_mcts.py`)
- Fórmula calibrada:
  $$\alpha = \min\left(1.5, \frac{3.0}{\max(1, N)}\right), \quad \epsilon = 0.15$$
  Gera $\alpha = 1.0$ para 3 candidatos e $\alpha = 0.5$ para 6 candidatos (exploração assimétrica e concentrada).

### 2.4 Decaimento da Temperatura de Fusão Knapsack-NN (`ai/mcts/standard_mcts.py`)
- Fórmula dinâmica:
  $$\text{shaping\_temp} = 2.5 + 7.5 \cdot \text{epoch\_ratio} \quad (2.5 \to 10.0)$$
  O knapsack orienta a exploração inicial; a rede neural domina conforme o treinamento converge.

### 2.5 Consistência Temporal no TD Error (`ai/blunder_reviewer.py`)
- Se um swing negativo ($\le -3.0$) for seguido imediatamente por uma reversão favorável no próximo passo ($\ge +2.0$), o peso de prioridade é atenuado de $3.5$ para $1.5$, isolando blunders reais de variâncias transitórias.

### 2.6 Stratified PER com Rastreamento de `hero_ids` (`ai/experience_collector.py`)
- Adição do array `hero_ids: np.ndarray(max_capacity, dtype=int32)`.
- Opção `stratified=True` no `sample_batch`: garante pelo menos 1 amostra de cada herói ativo no lote antes de preencher a cota com amostragem SumTree.
- Serialização atualizada para `schema_version = 3` com retrocompatibilidade automática para buffers legados (`hero_ids = 0`).

---

## 3. Consequências

- **Positivas**:
  - Impossibilidade matemática de heróis entrarem em espiral de passividade (bloco travado em 1.40 eliminado).
  - Heróis raros têm garantia de presença e aprendizado contínuo nos batches de treino GPU.
  - Eliminação de falsos blunders provocados por blefes ou viradas táticas imediatas.
  - O MCTS agora aproveita o pitch stacking que o próprio bot construiu.
  - Suíte completa de 462 testes unitários passando com 100% de sucesso.
- **Neutras**:
  - `ReplayBuffer` consome alguns kilobytes adicionais em RAM para armazenar `int32` por slot de experiência.
