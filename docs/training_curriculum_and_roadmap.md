# Roadmap e Currículo de Treinamento Deep RL — FaB 174 Heróis

## 1. Visão Geral e Desafio Dimensional

O Flesh and Blood possui mais de 174 heróis cadastrados entre formatos Blitz, Classic Constructed e formatos casuais. Treinar uma rede neural Policy-Value Dual Head diretamente a partir de pesos aleatórios em todos os heróis simultaneamente gera uma matriz combinatória de mais de $174 \times 174 \approx 30.000$ matchups com dispersão extrema de políticas e colapso de valor.

Este documento define a estratégia de treinamento em currículo (Curriculum Learning) com 4 fases graduais, a calibração de hiperparâmetros em precisão mista (FP16) e os indicadores de telemetria para prevenção de overfitting contra o solucionador heurístico (`knapsack_solver.py`).

---

## 2. Estrutura em 4 Fases do Currículo de Treinamento

### Fase 1: Bootstrap Fundacional em Partidas Espelhadas (Mirror Matches)
- **Objetivo:** Treinar a rede em jogos simétricos de arquétipos elementares para estabilizar a estimativa de valor $V(s) \in [-1, 1]$ sem viés de desbalanceamento de classe.
- **Heróis Selecionados:**
  1. `Bravo, Showstopper` (Guardião: turnos de 1-2 cartas, pitch alto, valor linear, crush effects).
  2. `Katsu, the Wanderer` (Ninja: sequenciamento de combos, go-again, turnos amplos de 4 cartas).
  3. `Dorinthea Ironsong` (Guerreira: combat chain focada em arma, timing de attack reactions e defesa precisa).
- **Matchups Executados:** Apenas `Bravo vs Bravo`, `Katsu vs Katsu` e `Dorinthea vs Dorinthea`.
- **Temperatura MCTS:** $\tau = 1.0$ nos primeiros 10 turnos, decaindo para $\tau = 0.2$ no endgame.
- **Duração Recomendada:** 50 a 100 épocas (atingir estabilidade de loss com Value MSE $\le 0.25$).

### Fase 2: Cross-Matchups Triangulares (Pedra-Papel-Tesoura Fundamental)
- **Objetivo:** Ensinar a rede a ponderar estratégias assimétricas (Aggro vs Midrange vs Tempo/Fatigue).
- **Matchups:** `Bravo vs Katsu`, `Bravo vs Dorinthea`, `Dorinthea vs Katsu`.
- **Mecanismo:** Ativação do `RoundRobinMatchupEngine` restrito aos 3 heróis.
- **Foco Técnico:** Calibração da cabeça de políticas com poda tática (`Prior Threshold Pruning` do ISMCTS).

### Fase 3: Expansão por Classes Principais (Clusterização Arquetípica)
- **Classes Integradas:**
  - **Bruto:** `Rhinar`, `Levia`, `Kayo` (Intimidate, Phantasm-popping, aleatoriedade controlada).
  - **Runeblade:** `Viserai`, `Briar`, `Vynnset` (Dano híbrido físico + arcano, runechants).
  - **Mago:** `Kano`, `Iyslander`, `Oscilio` (Dano arcano instantâneo fora do turno).
  - **Mecanólogo:** `Dash`, `Teklovossen`, `Maxx Nitro` (Boost, montagem de itens de arena).
  - **Ilusionista:** `Prism`, `Dromai`, `Enigma` (Auras, dragões, mecânica de Phantasm).
  - **Assassino:** `Arakni`, `Uzuri`, `Nuu` (Stealth, banimento de deck, interrupção de recursos).
  - **Ranger:** `Lexi`, `Azalea`, `Riptide` (Arsenal carregado de flechas, armadilhas).
- **Duração:** 100 a 250 épocas com checkpoint assíncrono habilitado.

### Fase 4: Full Pool (174 Heróis com Round-Robin Balanceado)
- **Objetivo:** Generalização total para todos os 174 heróis suportados em `ai/hero_strategies/`.
- **Modo:** Auto-play headless paralelo multithread (`--headless --batched-inference`).
- **Geração de Dados:** Spooling atômico com priorização por Prioritized Experience Replay (PER via `SumTree`).

---

## 3. Calibração de Hiperparâmetros em FP16 (AMP)

### Função de Perda Multi-Tarefa
A perda total é formulada como:
$$\mathcal{L}_{total} = \mathcal{L}_{policy}(\mathbf{p}, \boldsymbol{\pi}) + c_v \cdot \mathcal{L}_{value}(v, z) + c_{aux} \cdot \mathcal{L}_{aux} + c_{reg} \|\theta\|^2$$

1. **Perda da Política ($\mathcal{L}_{policy}$):**
   - Entropia cruzada ponderada por pesos de Importance Sampling (IS weights do replay buffer):
     $$\mathcal{L}_{policy} = - \frac{1}{B} \sum_{i=1}^B w_i \sum_{a=1}^{32} \pi_i(a) \log p_i(a)$$
2. **Perda de Valor ($\mathcal{L}_{value}$):**
   - **Smooth L1 Loss (Huber Loss, $\beta = 1.0$)**: Substitui o MSE clássico para garantir robustez contra outliers em partidas longas e evitar estouro de gradiente em precisão de meia precisão (FP16).
   - **Peso da Perda de Valor ($c_v$):** Calibrado em $0.5$ (em vez de $1.0$).
3. **Alvos Auxiliares KataGo ($c_{aux} = 0.2$):**
   - Predição de dano do turno e variação delta de HP ($\Delta \text{HP}$).
4. **Otimizador e Learning Rate:**
   - **Otimizador:** AdamW com $\beta_1 = 0.9, \beta_2 = 0.999$, Weight Decay $= 10^{-4}$.
   - **LR Inicial:** $3 \times 10^{-4}$ com decaimento suave por Cosseno.
   - **Warmup:** 500 steps lineares partindo de $1 \times 10^{-5}$.
   - **Gradient Clipping:** Norma máxima de gradiente fixada em $1.0$ após `scaler.unscale_(optimizer)`.

---

## 4. Telemetria Anti-Overfitting (`ismcts_logger.py` e `orchestrator.py`)

Para assegurar que o modelo não está apenas decorando as linhas do `knapsack_solver.py` e sim descobrindo jogadas não-triviais de valor no ISMCTS, acompanhe as seguintes métricas no dashboard (`dashboard.py`):

1. **Entropia da Política MCTS ($\mathcal{H}(\boldsymbol{\pi})$):**
   - $\mathcal{H} \ge 0.22$ bits por decisão indica exploração saudável e diversidade de linhas.
   - Se a entropia desabar para $\le 0.10$ nas fases iniciais, há colapso prematuro da política na primeira ação gulosa recomendada pela heurística.
2. **Divergência entre Heurística e Visitas Finais ($D_{KL}(\mathbf{p}_{heur} \parallel \boldsymbol{\pi}_{mcts})$):**
   - O ISMCTSLogger registra o ganho de busca ($N$ simulações com avaliação de folhas).
   - Se a taxa de concordância for $>98\%$, o ISMCTS está apenas repetindo a heurística sem avaliar o impacto terminal de vida e recursos. O ponto ideal é $75\% \sim 88\%$ de convergência com $\ge 12\%$ de desvios estratégicos vitoriosos.
3. **Correlação de Pearson entre Value Head e Resultado Terminal ($z$):**
   - Acompanha se o valor estimado no meio da partida realmente prediz vitória terminal. Valores de correlação $\ge 0.65$ indicam que a rede aprendeu noções profundas de tempo e card advantage.
