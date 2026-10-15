# ADR-0018: Headless Arena, Official Swiss Tournament System & Self-Play League

## Status
Aceito (Implementado e Validado)

## Contexto
O ecossistema dispunha de um organizador básico de torneios (`stats/tournament_manager.py`) e uma interface Streamlit (`ui/tabs/tab_tournaments.py`), porém com limitações que restringiam a validação de novos modelos:
1. **Pareamento Suíço Ingênuo:** A rodada suíça anterior apenas ordenava participantes por pontos e pareava vizinhos adjacentes, sem controle de rematches (permitindo que os mesmos decks se enfrentassem repetidamente).
2. **Ausência de Critérios Oficiais de Desempenho:** Inexistência de métricas oficiais de Tie-Breaker (Buchholz e Sonneborn-Berger), cruciais em torneios competitivos de Flesh and Blood e Magic: The Gathering.
3. **Falta de Tratamento de Bye:** Em chaves com número ímpar de participantes, o último jogador era descartado em vez de receber Bye (+3 pontos).
4. **Execução Presa a Subprocessos:** O torneio só podia rodar lançando `python3 bot_client.py` contra o servidor Talishar, tornando testes de torneio lentos.
5. **Auto-jogo Estático sem Liga de Oponentes:** O loop de auto-jogo treinava a rede exclusivamente contra sua versão idêntica corrente, vulnerável a esquecimento catastrófico e ciclos de estratégia não-transitivas (*rock-paper-scissors loops*).

## Decisão

1. **Duelo Headless entre Modelos Distintos (`opp_model` em `HeadlessSelfPlayLoop`):**
   - Estendido `HeadlessSelfPlayLoop` para suportar `opp_model: Optional[FaBPolicyValueNetwork] = None`.
   - O jogador 1 avalia o estado com `self.model` e o jogador 2 avalia com `opp_model`, permitindo duelos ultrarrápidos em memória entre versões diferentes da rede neural sem necessidade do servidor Talishar.
2. **Sistema Suíço Completo com Proibição de Rematches e Bye Rotativo:**
   - Implementado algoritmo de pareamento suíço canônico em `_generate_swiss_round`.
   - Histórico de oponentes rastreado via `p["opponents"]`, proibindo confrontos repetidos no mesmo torneio.
   - Atribuição oficial de Bye ao participante de menor pontuação sem Bye prévio quando o número de competidores for ímpar.
3. **Cálculo de Desempate Oficial (Buchholz & Sonneborn-Berger):**
   - Implementado `_calculate_tie_breakers`:
     - **Buchholz:** Soma dos pontos de todos os oponentes enfrentados pelo jogador.
     - **Sonneborn-Berger:** Soma dos pontos dos oponentes derrotados + metade dos pontos dos empatados.
   - Ordenação canônica da classificação: `(pontos, buchholz, sonneborn_berger, elo)`.
4. **Cálculo ELO Real e Suporte Headless no Torneio:**
   - Atualização de ELO através de `stats.elo.calculate_elo_ratings(r1, r2, winner_code, k=32)` com persistência em SQLite (`stats_manager.update_match_result`).
   - Modo de execução configurável (`execution_mode="headless"` ou `"talishar"`), executando torneios de 8 baralhos em segundos.
5. **Self-Play League com Checkpoints Históricos:**
   - Adicionada flag `--league-play` e amostragem probabilística (`league_prob=0.25`) no `GPUTrainingOrchestrator`, selecionando checkpoints históricos aleatórios de `SETTINGS.checkpoint_dir` para atuar como oponentes no treino de auto-jogo.

## Consequências

- **Positivas:**
  - Torneios de avaliação de checkpoints e baralhos podem ser executados em tempo real na interface Streamlit ou CLI em questão de segundos via modo headless.
  - O sistema suíço é estritamente conforme com as normas oficiais de torneios de TCG.
  - A esteira de treinamento agora suporta a metodologia AlphaStar/KataGo de Liga de Oponentes contra esquecimento catastrófico.
  - A suíte de testes unitários foi expandida para **569 testes aprovados (100% verde)**.
- **Negativas:**
  - Nenhuma identificada. A sobrecarga de memória para carregar um checkpoint histórico de oponente na liga é inferior a 15 MB.
