# ADR-0019: Data-Driven Sideboard & Monte Carlo Dropout Uncertainty

## Status
Aceito (Implementado e Validado)

## Contexto
O ecossistema contava com uma resolução de sideboard (`ai/sideboard_manager.py`) e uma estimativa de valor escalar no modelo neural (`ai/model.py`), porém com limitações arquiteturais:
1. **Acoplamento Nominal no Sideboard:** A identificação de oponentes arcanos dependia de listas estáticas de heróis (`arcane_heroes`), falhando em detectar novos heróis, variações de cartas promocionais ou heróis híbridos extraídos de `fab_cards_db.json`.
2. **Seleção Heurística Rígida de Equipamentos e Armas:** Equipamentos e off-hands eram pontuados com checks hardcoded (ex: `"stalagmite"`), sem considerar atributos semânticos completos de durabilidade (`battleworn`, `temper`), proteção (`ward`, `spellvoid`) ou conformidade estrita com CR 2.8.2 e CR 3.0.
3. **Ponto Cego de Incerteza Epistêmica no Value Head:** A rede Transformer fornecia uma predição escalar pontual $V(s) \in [-1.0, +1.0]$ sem estimativa de incerteza Bayesiana. Diante de estados novos, taticamente ambíguos ou de alta tensão, a engine corria o risco de tomar decisões arriscadas (como pular bloqueio via Tempo Pivot) por excesso de confiança em previsões ruidosas.

## Decisão

1. **Monte Carlo Dropout na Cabeça de Valor (`ai/model.py`):**
   - Introduzida camada `self.value_dropout = nn.Dropout(p=dropout or 0.15)` projetando sobre o vetor fundido antes de `self.value_head`.
   - Implementado método `predict_value_with_uncertainty(state_vector, num_samples=8)` que avalia $T$ amostras estocásticas em um único forward pass paralelizado (`x.repeat(num_samples, 1)`), mantendo o restante da rede em modo `eval()` determinístico.
   - Retorna média $\mu_V$ e desvio padrão $\sigma_V$ (incerteza epistêmica), preservando 100% da compatibilidade de chaves de estado de checkpoints existentes sem alterar `state_dict`.
2. **Orçamento Adaptativo MCTS Guiado por Incerteza Bayesiana (`ai/mcts/ismcts.py` e `ai/policy/engine.py`):**
   - Parâmetro `value_uncertainty` integrado em `calculate_adaptive_mcts_budget`.
   - Se $\sigma_V \ge 0.20$, o orçamento de simulações é escalonado em $1.5\times$; se $\sigma_V \ge 0.35$ (incerteza extrema), o orçamento dobra ($2.0\times$), direcionando capacidade computacional para cenários indecisos.
3. **Poda Defensiva Resiliente sob Incerteza (`ai/policy/defense_pruner.py`):**
   - Quando `value_uncertainty >= 0.25`, anula a presunção otimista de absorção de dano livre (`can_absorb_damage = False`) em planos de `TEMPO_COUNTER_ATTACK`, convertendo o plano em `UNCERTAINTY_SAFETY_BLOCK` e bloqueando dano para proteger a integridade do bot.
4. **Sideboard Totalmente Data-Driven (`ai/sideboard_manager.py`):**
   - Detecção dinâmica de dano arcano via inspeção de classes (`classes`, `types`), palavras-chave (`keywords`) e texto da carta de herói adversário.
   - Pontuação semântica enriquecida para durabilidade (`battleworn` +5.0, `temper` +4.0) e proteção (`ward`, `spellvoid`, `arcane barrier`).
   - Resolução de armas e escudos baseada em defesa e sinergia em conformidade com CR 2.8.2 e CR 3.0.
   - Poda de baralho principal considerando retenção de cartas de prevenção arcana (Oasis Respite, Peace of Mind) e estabilidade de pitch/defesa contra fadiga.

## Consequências

- **Positivas:**
  - O bot agora quantifica matematicamente sua própria incerteza sobre o estado do jogo e adapta sua cautela defensiva e profundidade de busca no MCTS.
  - A seleção de equipamentos e armas adapta-se automaticamente a qualquer novo herói ou carta adicionada ao banco oficial sem necessidade de intervenção de código.
  - O throughput de inferência permanece ultra-rápido: as $T$ amostras de dropout rodam em um único lote matricial sem loop sequencial em Python.
  - A suíte de testes unitários foi expandida para **574 testes aprovados (100% verde)**.
- **Negativas:**
  - Nenhuma identificada. A computação adicional de incerteza ocorre apenas quando requisitada pelo MCTS adaptativo ou resolvedor de defesa.
