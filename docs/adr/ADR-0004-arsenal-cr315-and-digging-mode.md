# ADR-0004: Poda Estrita de Arsenal conforme CR 3.1.5 e Heurística de Modo Cavar (CR 4.3.2)

- **Status**: Accepted
- **Date**: 2026-09-16
- **Deciders**: Equipe FaB Talishar AI (Architecture Review)

## Context

No jogo de cartas Flesh and Blood, a zona de **Arsenal** permite ao jogador guardar uma única carta da mão ao final de seu turno de ação para ser utilizada em turnos futuros.

Contudo, a regra oficial das *Comprehensive Rules* estipula:
> **CR 3.1.5:** *"Cards in the arsenal cannot be pitched."* (Cartas no Arsenal não podem ser colocadas na zona de pitch para pagar custos de recursos).

Cartas no Arsenal só podem ser jogadas se forem cartas de ação (Action cards), reações ou instantes válidos. Cartas puramente de recurso, gemas lendárias (como *Heart of Fyendal*, *Eye of Ophidia*, *Arknight Shard*) e cartas que servem unicamente para gerar pitch não possuem ações de jogo independentes. Quando um bot coloca uma carta dessas no Arsenal, o slot fica inutilizado e trancado permanentemente, eliminando a vantagem tática do Arsenal pelo resto da partida.

Paralelamente, surge o problema inverso de travamento de mão: se o bot finaliza o turno com uma mão saturada de recursos inúteis para ataque ($\ge 3$ cartas de recurso/suporte) e a heurística padrão descarta todas as opções por terem valor tático negativo ou nulo, o bot passaria a fase de Arsenal vazia. Pela regra de fim de turno (**CR 4.3.2 End of Turn Step**), o jogador compra cartas apenas até completar o **Intelecto** de seu herói ($4 - \text{cartas em mão}$). Se o bot mantiver 3 ou 4 cartas inúteis na mão, ele comprará 0 ou apenas 1 carta nova, ficando preso em um ciclo vicioso de estagnação (*hand deadlock*), passando turnos inteiros sem desferir dano.

## Decision

Implementar uma estratégia dual e cirúrgica de poda e seleção de cartas para o Arsenal em `ai/policy/arsenal_pruner.py`:

### 1. Poda Estrita Conforme CR 3.1.5
- Todas as cartas candidatas ao Arsenal são submetidas ao filtro universal `is_resource_or_gem_card(c_name, info, db_entry)` implementado em `ai/hero_strategies/`.
- Recursos puros, gemas de recurso e cartas sem ações jogáveis são sumariamente descartadas da lista de candidatos a Arsenal em condições normais de jogo.
- Avaliação polimórfica via `HeroStrategy.evaluate_arsenal_card`: apenas cartas com avaliação tática comprovadamente positiva (`score > 0`) para o próximo turno ofensivo/defensivo são elegíveis.

### 2. Heurística de Modo Cavar (Digging Mode, CR 4.3.2)
Quando nenhum candidato atinge `score > 0` e o jogador está com a mão travada com **3 ou mais cartas**:
- O algoritmo ativa o **Modo Cavar**: força o envio de uma carta da mão para o Arsenal deliberadamente, com o objetivo de esvaziar um slot da mão e forçar a compra de uma carta nova do deck no *End of Turn Step* até atingir o Intelecto.
- Critérios de pontuação do Modo Cavar:
  1. **Preferência por Cartas de Ação**: Cartas com tipo Ação (`"A"` ou `action > 0`) recebem bônus de $+10.0$, pois poderão ser jogadas no próximo turno para liberar o slot do Arsenal.
  2. **Maior Poder de Ataque**: Cartas com maior poder de ataque (`power * 3.0`) ganham prioridade para viabilizar ameaça ofensiva.
  3. **Menor Custo**: Cartas de custo 0 recebem bônus de $+2.0$ para facilitar sua desocupação no turno seguinte.
  4. **Penalidade Rígida para Gemas**: Gemas lendárias puras sofrem penalidade de $-100.0$, sendo o último recurso absoluto.
- **Caso $\le 2$ cartas restantes**: Se a mão possuir apenas 1 ou 2 recursos, o bot **NÃO** arsenala. Ele preserva os recursos na mão para pagar custos no turno subsequente e compra naturalmente 2 a 3 cartas novas do deck até atingir o Intelecto.

## Consequences

### Positive
- **Conformidade com as Regras Oficiais**: O bot nunca mais comete o erro crítico de trancar o Arsenal com cartas de recurso ou gemas que não podem ser dadas pitch nem jogadas.
- **Desobstrução Rápida de Mãos Travadas**: O Modo Cavar permite ao bot quebrar ciclos de estagnação de compras ruins, acelerando a rotação do baralho para encontrar finalizadores e ataques chave.
- **Otimização de Recursos**: Cartas de alto valor de pitch e custo de oportunidade são mantidas na mão quando a quantidade residual é pequena ($\le 2$), permitindo financiar ataques pesados no turno seguinte.

### Negative / Trade-offs
- Em situações excepcionais de baralho quase exausto (fim de deck por fadiga), cavar forçadamente consome 1 carta adicional do baralho, aproximando o bot do deck-out caso não consiga finalizar o jogo.

## Alternatives Considered

- **Nunca Arsenalar sem Score Positivo**: Rejeitado pois provocava empates técnicos e estagnações prolongadas (bots mantendo 4 azuis na mão por 5 turnos seguidos sem comprar nenhuma carta nova).
- **Arsenalar Qualquer Carta Aleatória**: Rejeitado pois gerava frequentemente o trancamento do Arsenal com gemas e recursos puros (violação tática direta da regra CR 3.1.5).
- **Descarte Voluntário**: Inviável pelas regras de FaB; o jogador não pode descartar cartas voluntariamente no fim do turno além das mecânicas do jogo.
