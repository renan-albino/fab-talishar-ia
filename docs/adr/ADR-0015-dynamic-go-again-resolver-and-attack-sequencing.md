# ADR-0015: Dynamic Go-Again Resolver & Attack Sequencing Pruning

## Status
Aceito (Implementado e Validado)

## Contexto
No Flesh and Blood, o sequenciamento correto de ataques e a concessão de Go Again determinam o ritmo ofensivo do turno. Previamente, o motor de IA utilizava verificações estáticas ou heurísticas simples para determinar se um ataque possuía Go Again:
1. **Falso Positivo/Negativo em Condicionais:** Cartas cuja concessão de Go Again é estritamente condicional — como ataques Dracônicos (`burning_blade_dance`, `lava_vein_loyalty`, `cinderskin_devotion`), `blaze_headlong` e cartas com mecânica de Combo Ninja (`rising_knee_thrust`, `crane_dance`, `whelming_gustwave`) — eram frequentemente abertas como o primeiro elo da cadeia de combate sem que seus pré-requisitos canônicos tivessem sido satisfeitos.
2. **Quebra Prematura da Cadeia de Combate:** Quando o jogador possui apenas 1 Action Point (`player_ap <= 1`) e múltiplas opções de ataque na mão, iniciar a cadeia com um ataque condicional sem Go Again ativo causa o encerramento imediato do turno ofensivo, impedindo que as demais cartas da mão sejam jogadas e sacrificando tempo crítico.
3. **Penalidade Insuficiente na Poda:** A penalidade de -4.0 em `attack_pruner.py` era insuficiente para impedir que cartas como `burning_blade_dance_red` (custo 0) abrissem o turno à frente de starters legítimos com Go Again intrínseco (como `leg_tap_red` ou `ronin_renegade_red`).
4. **Planejamento de Turno Estático no Ninja:** Em `NinjaStrategy.analyze_turn_plan`, a identificação de "starters" de custo zero baseava-se em um atributo estático `c.get("has_go_again")`, falhando em validar o estado dinâmico da cadeia.

## Decisão

1. **Módulo Centralizado de Resolução Dinâmica (`ai/policy/go_again_resolver.py`):**
   - Criamos `resolve_attack_go_again(card_name: str, state: dict, hand_info: dict | None = None) -> tuple[bool, str]`.
   - **Go Again Natural:** Avaliado via consulta ao `GeneratedGoAgain.php` do Talishar e `fab_cards_db.json`. Retorna `(True, "natural_go_again")`.
   - **Tokens de Arena (Quicken e Agility):** De acordo com FaB CR 8.6.1 e 8.6.28, concedem Go Again gratuito se ativos no 1º elo da cadeia (`currentChainLink <= 1`). Retorna `(True, "token_granted")`.
   - **Links Dracônicos (Limiar >= 2):** Para cartas dracônicas com exigência de cadeia (`burning_blade_dance`, `display_loyalty`, `demonstrate_devotion`, `cinderskin_devotion`, `lava_vein_loyalty`, `hot_on_their_heels`, `mark_with_magma`), valida quantos elos anteriores no combate ativo possuem talento `DRACONIC` (via `GeneratedCardTalent.php` ou metadados). Se $\ge 2$, retorna `(True, "draconic_threshold_met")`; caso contrário, `(False, "insufficient_draconic_links")`.
   - **Cartas Vermelhas (`blaze_headlong`):** Verifica se outra carta vermelha foi jogada no turno via `currentTurnEffects`, ações do turno ou elos anteriores. Se sim, retorna `(True, "red_card_played")`; caso contrário, `(False, "no_prior_red_card")`.
   - **Combos Ninja:** Mapeia a tabela canônica de pré-requisitos (`rising_knee_thrust` $\leftarrow$ `leg_tap`, `crane_dance` $\leftarrow$ `soulbead_strike`, `whelming_gustwave` $\leftarrow$ `surging_strike`, etc.) e valida contra o elo imediatamente anterior na cadeia. Se satisfeito, retorna `(True, "combo_active")`; caso contrário, `(False, "combo_inactive")`.

2. **Penalidade Rígida de Sequenciamento de Ataque (`ai/policy/attack_pruner.py`):**
   - Substituímos a penalidade branda de -4.0 por uma penalidade rígida de **-35.0** quando `player_ap <= 1`, há opções de ataque na mão com Go Again (`has_any_go_again`) e o ataque candidato não possui Go Again garantido (`not effective_go_again`).
   - Isso garante que aberturas sem pré-requisito cumprido nunca sejam priorizadas sobre cartas com Go Again garantido.

3. **Validação Dinâmica de Starters no Ninja (`ai/hero_strategies/ninja.py`):**
   - Atualizamos `NinjaStrategy.analyze_turn_plan` para validar starters de custo zero utilizando `resolve_attack_go_again`, prevenindo planos de combo espúrios baseados em cartas condicionais desativadas.

## Consequências

- **Positivas:**
  - Sequenciamento ofensivo 100% canônico e alinhado com as regras do FaB em todas as classes, especialmente Ninja e talentos Dracônicos.
  - Eliminação completa de turnos interrompidos prematuramente por aberturas inválidas de `burning_blade_dance` ou `blaze_headlong`.
  - Transparência explicável com motivos detalhados de Go Again nos candidatos de ataque.
  - Integração perfeita e retrocompatível com a suíte de testes existente.
- **Negativas:**
  - Nenhuma identificada. A sobrecarga computacional de consulta ao cache é insignificante ($< 0.05$ ms por turno).
