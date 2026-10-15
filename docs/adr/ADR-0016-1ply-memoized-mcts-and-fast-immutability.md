# ADR-0016: 1-Ply Memoized MCTS, Single Root Forward & Fast Immutability

## Status
Aceito (Implementado e Validado)

## Contexto
Durante a auditoria de desempenho do motor de IA (`fab-talishar-ia`), foram identificados gargalos estruturais no loop de simulação e busca:
1. **Avaliações Redundantes de Folhas no MCTS:** A árvore do MCTS em Flesh and Blood opera com profundidade 1 (apenas a raiz é expandida via `_expand`). A transição de estado via `GameSimulator.simulate_step(state, action)` e os ruídos de fallback são estritamente determinísticos para cada tupla `(mundo, action_id)`. Entretanto, a cada simulação, o método `_batch_evaluate_leaves` era chamado com `nodes=[node]`, alocando um dicionário de cache vazio por chamada e disparando um forward pass unitário na rede neural para ações já calculadas. Em um estado com 4 ações legais, 4 mundos e 25 simulações, o motor realizava **154 forward passes por decisão**.
2. **Avaliações Múltiplas da Raiz:** Os mundos determinizados diferem exclusivamente na mão oculta do oponente (`opponentHand`), a qual não é inspecionada pelo extrator de features do modelo (`FaBCardTransformerNetwork.extract_state_vector`). Logo, o vetor raiz é idêntico para todos os $W$ mundos, mas era reavaliado repetidamente nos mundos e nos logs de telemetria.
3. **Re-congelamento Recursivo em `ImmutableGameState`:** Os métodos `replace` e `without` recriavam o estado chamando `__init__`, que re-executava `_freeze_value` sobre dezenas de chaves e tuplas que já estavam previamente imutáveis.
4. **Extração Eager de Vetores de 832 Dimensões:** `GameSimulator.simulate_step` sempre calculava `extract_state_vector`, mesmo em chamadas de `headless_env.py` e `shadow_mode.py` que descartavam o vetor com `state, _ = ...`.

## Decisão

1. **Memoização de Folhas de 1-Ply em Lote Único:**
   - Em `ISMCTSEngine._run_world_mcts` e `MCTSEngine.search`, todos os nós candidatos da raiz (`root.children.values()`) são avaliados em um **único forward pass em lote** antes do loop de simulações.
   - Os valores retornados são armazenados em um mapeamento `{action_id: value}`.
   - O loop de $S$ simulações executa em microssegundos na memória RAM, aplicando a fórmula PUCT, progressive widening e retropropagação com lookup instantâneo.
2. **Reaproveitamento da Raiz em `search_ismcts`:**
   - O vetor de estado e as predições de raiz (`root_priors, root_base_value`) são calculados uma única vez na entrada de `search_ismcts` e repassados a todos os mundos e ao log de telemetria.
   - Para $W$ mundos, o número total de forward passes por decisão torna-se estritamente $W + 1$ (1 raiz + $W$ lotes de folhas).
3. **Fast Immutability via `_from_frozen`:**
   - Criamos o método de classe `ImmutableGameState._from_frozen(frozen_data)`.
   - `replace` agora aplica `_freeze_value` exclusivamente sobre os novos pares chave-valor passados em `kwargs`, preservando sem reprocessamento as estruturas já congeladas.
4. **Extração Opcional de Vetor:**
   - Adicionamos o argumento `with_vector: bool = True` em `GameSimulator.simulate_step`. Em `headless_env` e `shadow_mode`, passa-se `with_vector=False`.

## Consequências

- **Positivas (Métricas Reais Medidas):**
  - **Latência do ISMCTS:** Redução de **94.9%** (de 534.25 ms para **27.20 ms** p50).
  - **Taxa de Decisões do ISMCTS:** Aumento de **18.7x** (de 1.89 dec/s para **35.43 dec/s**).
  - **Forward Passes:** Queda de **96.7%** (de 154.0 para **5.0** forwards por decisão).
  - **Throughput Headless:** Aumento de 25.9 para **34.1 partidas/min** (de 59.4 para **102.3 passos/s**).
  - **Preservação Algorítmica:** A distribuição de visitas do PUCT permanece matematicamente fiel ao comportamento anterior.
- **Negativas:**
  - Nenhuma identificada. A memória para armazenar o mapa de valores por ação legal é desprezível ($\le 32$ floats por mundo).
