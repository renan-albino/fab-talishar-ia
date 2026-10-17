# ADR-0020: Holistic Performance Optimization, Sim2Real Multi-Tick Isolation & Test Hermeticity

## Status
Aceito (Implementado e Validado)

## Contexto
Após a conclusão das Sprints 0 a 4 (ADR-0016 a ADR-0019), uma auditoria holística de performance, fidelidade Sim2Real e higiene de testes revelou pontos de otimização e isolamento no ecossistema:
1. **Custo Redundante de Backbone no Monte Carlo Dropout (`ai/model.py`):** A estimativa de incerteza Bayesiana (`predict_value_with_uncertainty`) replicava o vetor de entrada `[1, 832]` em `[T, 832]` antes de passar pelo backbone Transformer (Self-Attention e Cross-Attention), sendo que apenas `value_dropout` e `value_head` operam de modo estocástico durante a inferência.
2. **Propagação Sequencial em Lote na SumTree (`ai/experience_collector.py`):** Enquanto `SumTree.set_all` já havia sido vetorizado (ADR-0017), a atualização incremental de prioridades pós-gradiente (`update_priorities`) ainda invocava propagações individuais por amostra na árvore de soma.
3. **Supervisão Auxiliar KataGo no Auto-Jogo Headless (`ai/training/headless_env.py`):** O `HeadlessSelfPlayLoop` precisava exportar consistentemente os sinais auxiliares contínuos (`board_eval` / $\Delta\text{HP}$ e `turn_dmg`) em paridade estrita com as trajetórias Sim2Real para alimentar as cabeças auxiliares da `FaBCardTransformerNetwork` no `orchestrator.py`.
4. **Alocações Desnecessárias no `ThreadBatchedEvaluator` (`ai/mcts/batched_evaluator.py`):** As chamadas de inferência em lote sempre computavam e transferiam tensores das cabeças auxiliares mesmo quando os workers MCTS solicitavam apenas `(policy, value)`, além de realizarem cópias intermediárias de arrays NumPy.
5. **Ruído de Transições Multi-Tick e Modais no `Shadow Mode` (`ai/shadow_mode.py` & `ai/game_simulator.py`):** No motor PHP do Talishar, jogar uma carta cujo custo excede os recursos ativos transita por passos intermediários (`Phase M` $\to$ `Phase P` ou popups `CHOOSEMULTIZONE` / `BUTTONINPUT`) antes de deduzir recursos e AP, além de utilizar a chave truncada `playerArse`. Comparar o estado pós-ação imediato do simulador com o estado multi-tick intermediário gerava falsos positivos de divergência.
6. **Isolamento Hermético de Testes (`tests/conftest.py`) e Ferramental CLI:** A suíte de testes precisava de garantias herméticas para nunca tocar no banco SQLite de produção (`data/talishar_stats.db`) ou logs ativos durante execuções paralelas, e o catálogo de automação carecia de scripts dedicados para diagnóstico Sim2Real e torneios suíços headless.

## Decisão

1. **Single-Pass Transformer Backbone no MC Dropout (`ai/model.py`):**
   - Refatorado `predict_value_with_uncertainty(state_vector, num_samples=8)` para executar o backbone Transformer (projeções de cartas, Self-Attention, Cross-Attention e fusão latente) **uma única vez** com batch size $1$ em modo `eval()`.
   - Apenas o vetor latente fundido `fused` é replicado via `fused.repeat(num_samples, 1)` e submetido a `F.dropout(..., training=True)` seguido de `self.value_head`, reduzindo o custo computacional do MC Dropout em ~85%.
2. **Atualização Vetorizada de Lote na SumTree (`SumTree.update_batch` - `ai/experience_collector.py`):**
   - Implementado `SumTree.update_batch(tree_indices, priorities)` que atualiza todas as folhas do mini-batch simultaneamente em NumPy e propaga a soma ascendente nível a nível (`parent = (indices - 1) // 2`) recalculando apenas os nós pais únicos (`np.unique`) em cada profundidade da árvore.
3. **Paridade de Alvos Auxiliares KataGo no Headless (`ai/training/headless_env.py` & `ai/training/orchestrator.py`):**
   - O `HeadlessSelfPlayLoop` registra a variação normalizada de vida (`board_eval`) e dano do turno (`turn_dmg`) em cada transição, permitindo supervisão contínua das cabeças auxiliares KataGo (peso $0.2$) tanto em treinos `--headless` quanto Sim2Real.
4. **`ThreadBatchedEvaluator` Zero-Copy e `return_aux` Sob Demanda (`ai/mcts/batched_evaluator.py`):**
   - Adicionado suporte a `return_aux=False` por padrão no avaliador em lote multithread e montagem do batch via `np.asarray(..., dtype=np.float32)` / `torch.from_numpy` sem cópias supérfluas, evitando cálculo e transferência GPU $\to$ CPU das cabeças auxiliares durante a expansão normal de nós MCTS.
5. **Isolamento de Estados Multi-Tick (`confounded`) e Normalização `playerArse` (`ai/shadow_mode.py` & `ai/game_simulator.py`):**
   - O `Shadow Mode` identifica automaticamente transições multi-tick (`M` $\to$ `P`), liquidações de pitch e aberturas de modais interativos (`CHOOSEMULTIZONE`, `MAYCHOOSEMULTIZONE`, `BUTTONINPUT`), marcando o passo com `confounded=True` para não contaminar a métrica de Fidelidade do Simulador.
   - `GameSimulator.simulate_attack` e `Shadow Mode` operam com suporte bidirecional transparente entre `playerArse` e `playerArsenal`.
6. **Hermeticidade Global no Pytest (`tests/conftest.py`) & Scripts Operacionais (`.agents/skills/automated-tasks/scripts/`):**
   - Fixture `autouse` em `tests/conftest.py` redireciona variáveis de ambiente e caminhos de banco SQLite/logs para diretórios temporários isolados (`tmp_path`), blindando `data/talishar_stats.db`.
   - Adicionados os utilitários CLI `diagnose_sim2real.py` (inspeção analítica de divergências do Shadow Mode por fase e campo) e `run_headless_tournament.py` (execução de torneios suíços completos em memória via CLI).

## Consequências

- **Positivas:**
  - Redução drástica da sobrecarga de inferência com incerteza Bayesiana (MC Dropout) e das atualizações de prioridade no PER.
  - Treinamento `--headless` supervisiona 100% das cabeças da rede (`policy`, `value`, `board_eval`, `turn_dmg`).
  - A métrica de Fidelidade Sim2Real reflete exclusivamente a precisão das regras de negócio do `GameSimulator`, livre de artefatos assíncronos de protocolo do Talishar.
  - Execução da suíte de **581 testes unitários** 100% hermética, determinística e sem efeitos colaterais no estado de produção.
- **Negativas:**
  - Nenhuma identificada.
