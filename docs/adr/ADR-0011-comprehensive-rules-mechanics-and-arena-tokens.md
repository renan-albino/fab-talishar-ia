# ADR-0011: Integração Formal das Comprehensive Rules (CR) e Gestão Dinâmica de Tokens de Arena

## Status
**Aceito** (2026-09-27)

## Contexto
O Flesh and Blood possui um sistema de regras abrangente e estrito documentado nas *Comprehensive Rules (CR)*. Anteriormente, embora o motor de IA contivesse heurísticas avançadas de combate e suporte a 174 heróis, diversas regras canônicas de evasão, efeitos de substituição e penalidades impostas por marcadores e auras (*arena tokens*) não estavam unificadas em todos os subsistemas:

1. **Restrições de Bloqueio por Evasão (CR 7.3.2 & CR 8.3):**
   - *Dominate* (CR 7.3.2a, CR 8.3.4): O defensor não pode bloquear com mais de 1 carta da mão.
   - *Overpower* (CR 7.3.2b, CR 8.3.22): O defensor não pode bloquear com mais de 1 carta de ação de qualquer zona.
   - *Phantasm* (CR 7.4.4, CR 8.3.12): Ataques de Ilusionista com Phantasm são estourados (*popped*) e a cadeia é imediatamente fechada se defendidos por carta de ataque não-ilusionista com 6+ de poder.
   - *Piercing* (CR 8.5.21): Ataques ganham +1 de dano quando defendidos por equipamento.
2. **Tokens de Arena do Jogador (CR 8.6):**
   - *Quicken / Agility* (CR 8.6.1, CR 8.6.28): Concedem *Go Again* imediato no Elo 1 da cadeia, permitindo que ataques sem *Go Again* nativo abram turnos sem penalidade de quebra de cadeia antecipada.
   - *Frostbite* (CR 8.6.10): Taxa cada carta jogada ou habilidade ativada em +1 recurso por token, impactando a solvabilidade de custos na poda de ataque.
   - *Inertia* (CR 8.6.21): Envia toda a mão e arsenal para o fundo do deck na *End Phase*. O conceito de *Tempo Pivot* (reter cartas para contra-ataque futuro) torna-se fútil sob Inertia, exigindo que as cartas sejam usadas para defesa.
   - *Bloodrot Pox* (CR 8.6.20): Causa perda de 2 pontos de vida na *End Phase* a menos que o jogador pague {r}{r}{r} (3 recursos). Em vida crítica ($\le 2$ HP), preservar cartas de *pitch* (especialmente azuis) é mandatório para sobrevivência.
3. **Catálogo de Palavras-Chave de Efeito (CR 8.5):**
   - Palavras-chave formais como `clash`, `wager`, `amp`, `transcend`, `reload`, `freeze`, `intimidate`, `opt` e `charge` necessitavam de extração semântica canônica no pipeline `scripts/extract_cr_mechanics.py`.

## Decisão de Arquitetura

1. **Unificação da Lógica de Combate no `GameSimulator` (`ai/game_simulator.py`):**
   - `simulate_attack`:
     - Aplica o teto de 1 carta de mão quando `dominate=True`.
     - Aplica o teto de 1 carta de ação quando `overpower=True`.
     - Implementa *Phantasm Popping*: se o defensor não-ilusionista tiver carta com poder $\ge 6$, o ataque é destruído (`phantasm_popped = True`), `damage_dealt = 0` e `chain_closed = True`.
   - `simulate_defense`:
     - Aplica a regra de *Piercing* incrementando o poder efetivo de entrada em +1 quando qualquer equipamento bloqueia.
2. **Extração e Rastreamento em `ArenaThreatContext` (`ai/policy/card_semantics.py`):**
   - Adicionados campos para rastreamento de tokens próprios e adversários: `has_quicken`, `has_agility`, `has_might`, `has_frostbite`, `frostbite_count`, `has_inertia`, `has_bloodrot`.
   - `build_arena_threat_context`: Extrai dinamicamente auras, itens e tokens das chaves `playerAuras`, `playerTokens`, `playerItems`, `myAuras` e `myTokens`.
3. **Poda Ofensiva com Tokens de Arena (`ai/policy/attack_pruner.py`):**
   - Detecta `has_quicken` e `has_agility` no Elo 1, concedendo `effective_go_again` para evitar penalidade de quebra de cadeia (`-4.0`).
   - Aplica a taxa de recursos do *Frostbite* (`card_cost = base_cost + frostbite_count`), podando ataques impagáveis com base nos recursos totais disponíveis.
4. **Poda Defensiva e Sobrevivência a Aflições (`ai/policy/defense_pruner.py`):**
   - Sob `has_inertia`, define `turn_plan.can_absorb_damage = False` e desativa penalidades de retenção de bombas vermelhas, forçando seu uso como bloqueadores.
   - Sob `has_bloodrot` com $\text{HP projetado} \le 2$, preserva cartas de *pitch* necessárias para pagar {r}{r}{r} no fim do turno caso o dano de combate não seja letal.
5. **Catalogação Canônica em `scripts/extract_cr_mechanics.py`:**
   - Adicionadas as 9 palavras-chave de efeito principais da CR 8.5 ao mapeamento e geração de `data/fab_card_semantics.json`.

## Consequências

### Positivas
- **Fidelidade Rigorosa às Regras Oficiais:** Alinhamento de 100% com o livro de regras canônico de Flesh and Blood.
- **Prevenção de Falsos Pivots:** Elimina o suicídio tático de reter cartas sob *Inertia* ou bloquear com recursos vitais sob *Bloodrot Pox*.
- **Otimização Ofensiva:** Aproveitamento dinâmico de *Quicken* e *Agility* para sequenciamento ideal de cadeias de ataque.
- **Simulador de Alta Fidelidade:** `GameSimulator` agora simula com precisão Dominate, Overpower, Phantasm e Piercing tanto para o bot quanto para o oponente.

### Neutras / Compensações
- O `GameSimulator` consome alguns microssegundos a mais avaliando subtipos de cartas ao calcular combinações defensivas (impacto desprezível frente à precisão ganha).
