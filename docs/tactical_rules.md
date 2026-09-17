# ⚔️ Arquitetura de Podas Táticas & Regras Oficiais FaB (CR)

Este documento descreve detalhadamente a engenharia de decisão, formalização matemática, regras oficiais do *Flesh and Blood* (**Comprehensive Rules - CR** e **Tournament Rules - TR**) e os algoritmos de poda tática implementados no motor de Inteligência Artificial do **FaB Talishar AI**.

---

## 📋 Índice
1. [Visão Geral e Propósito das Podas Táticas](#-visão-geral-e-propósito-das-podas-táticas)
2. [Poda 1: Ataque e Sequenciamento de Cadeia (Chain Sequencing)](#1-poda-de-ataque-e-sequenciamento-de-cadeia-chain-sequencing)
3. [Poda 2: Pitch Eficiente (Pitch Hierarchy: Blue > Yellow > Red)](#2-poda-de-pitch-eficiente-pitch-hierarchy-blue--yellow--red)
4. [Poda 3: Bloqueio Inteligente & Preservação de Pivot](#3-poda-de-bloqueio-inteligente--preservação-de-pivot)
5. [Poda 4: Global de Arsenal & Modo Cavar (CR 3.1.5 & CR 4.3.2)](#4-poda-global-de-arsenal--modo-cavar-cr-315--cr-432)
6. [Poda 5: Resolução Legal de Armas & Sideboard (CR 2.8.2 e CR 3.0)](#5-resolução-legal-de-armas--sideboard-cr-282-e-cr-30)
7. [Poda 6: Detecção de Stalemate / Empate Técnico & Anti-Loop (Tournament Rules)](#6-detecção-de-stalemate--empate-técnico--anti-loop-tournament-rules)
8. [Poda 7: Avaliação Dinâmica de Equipamentos & Aprendizado Empírico](#7-avaliação-dinâmica-de-equipamentos--aprendizado-empírico)
9. [Poda 8: Quantificação de Ameaça On-Hit & Defesa de Breakpoint Mínimo (Knapsack Breakpoint)](#8-quantificação-de-ameaça-on-hit--defesa-de-breakpoint-mínimo-knapsack-breakpoint)
10. [Poda 9: Prioritized Experience Replay (PER) & Auto-Tuning Dinâmico por Herói](#9-prioritized-experience-replay-per--auto-tuning-dinâmico-por-herói)
11. [Poda 10: Proteção Ativa de Arsenal & Otimização da Crown of Providence](#10-proteção-ativa-de-arsenal--otimização-da-crown-of-providence)
12. [Poda 11: Poda de Equipamentos de Prevenção e Reação no Vazio](#11-poda-de-equipamentos-de-prevenção-e-reação-no-vazio)
13. [Poda 12: Bloqueio Flexível com Validação de Conversão de Mão](#12-bloqueio-flexível-com-validação-de-conversão-de-mão)
14. [Poda 13: Treino Híbrido Humano vs Bot com Telemetria e Bônus ELO](#13-treino-híbrido-humano-vs-bot-com-telemetria-e-bônus-elo)
15. [Poda 14: Compreensão Semântica de Arena e Modificadores Dinâmicos de Combate](#14-compreensão-semântica-de-arena-e-modificadores-dinâmicos-de-combate)
16. [Mapeamento de Módulos e Referências](#-mapeamento-de-módulos-e-referências)

---

## 🎯 Visão Geral e Propósito das Podas Táticas

Em jogos com informação imperfeita e alta profundidade combinatória como Flesh and Blood, árvores de busca puras (**MCTS** ou **ISMCTS**) sofrem de explosão exponencial no espaço de estados:
- Cada turno envolve múltiplas micro-fases: *Action*, *Attack*, *Defend*, *Reaction Step* (Attack Reactions, Defense Reactions, Instants) e *End Phase* (Pitch bottoming e Arsenal).
- O número de subconjuntos de blocos a partir de uma mão de 4 cartas e 4 equipamentos ultrapassa $2^8 = 256$ combinações teóricas por elo de cadeia.
- Decisões ilegais segundo as regras do jogo (como pitchar cartas do Arsenal ou equipar simultaneamente armas 2H e escudos) inviabilizam o treinamento ou causam loops infinitos no motor de regras.

As **14 Podas Táticas** atuam como um filtro pré-MCTS e direcionador heurístico:
1. **Garantem conformidade estrita com o Comprehensive Rules (CR)** de Flesh and Blood.
2. **Eliminam ramos dominados ou ilegais** antes da amostragem de mundos no ISMCTS.
3. **Preservam recursos de longo prazo** (*tempo*, cartas reservadas para combos e integridade de armaduras de uso único).
4. **Respeitam restrições de zona e camadas (CR 3, CR 5 e CR 7)**, incluindo reação via Arsenal e Overpower restrito à mão.

---

## 1. Poda de Ataque e Sequenciamento de Cadeia (Chain Sequencing)

### Fundamentação Oficial e Conceito
No Flesh and Blood, um jogador só pode estender sua cadeia de combate se suas ações concederem a palavra-chave **Go Again** (ou se tiver múltiplos Pontos de Ação - AP via habilidades ou cartas como *Lead the Charge*). Iniciar um turno com um ataque sem *Go Again* quando se possui apenas 1 AP encerra o turno imediatamente, deixando o restante da mão inútil.

### Módulos do Código
- [`ai/policy/attack_pruner.py`](../ai/policy/attack_pruner.py)
- [`ai/hero_strategies/base.py`](../ai/hero_strategies/base.py)

### Regras Algorítmicas
1. **Starter Priority & Custo Zero**: Ataques com *Go Again* natural e custo $0$ recebem bonificação $+1.5$ no score base, sendo priorizados como iniciadores (*starters*).
2. **Penalidade de Quebra Prematura de Cadeia**:
   $$\text{Se } AP \le 1 \land \exists \text{ ataque com Go Again} \land \neg \text{atk.has\_go\_again} \land |\text{hand\_attacks}| > 1 \implies \text{score} \mathrel{-}= 4.0$$
   Isso impede que o bot jogue ataques sem Go Again no início do turno, preservando a capacidade de desferir múltiplos golpes.
3. **Flechas de Ranger (CR 2.1.2)**: Cartas com subtipo `Arrow` **nunca** podem ser jogadas diretamente da mão. O pruner filtra sumariamente qualquer flecha na mão (`subtype: Arrow`), forçando que sejam carregadas no Arsenal via Arco ou habilidades antes do disparo.
4. **Timing de Armas e Consumo de Flutuante**:
   - Armas pesadas (martelos de Guardião, custo 3) são priorizadas como finalizadores ou jogadas de turno único quando não há ataques na mão.
   - Armas ágeis de 1 mão (*Harmonized Kodachi*, adagas de Assassino) são ativadas no início para consumir recursos flutuantes residuais antes de fechar a cadeia.

---

## 2. Poda de Pitch Eficiente (Pitch Hierarchy: Blue > Yellow > Red)

### Fundamentação Oficial e Conceito
Gerar recursos no FaB requer colocar cartas da mão na zona de Pitch. Cartas Azuis concedem 3 recursos, Amarelas 2 e Vermelhas apenas 1. Como cartas vermelhas possuem o maior teto de dano e bloqueio, utilizá-las para gerar recursos representa uma perda severa de valor (*card disadvantage*).

### Módulos do Código
- [`ai/policy/pitch_pruner.py`](../ai/policy/pitch_pruner.py)
- [`ai/hero_strategies/base.py`](../ai/hero_strategies/base.py)

### Regras Algorítmicas
1. **Hierarquia de Pitch**:
   $$\text{score}_{\text{pitch}} = \text{base\_score} + \begin{cases} +4.0 & \text{se pitch} = 3 \text{ (Azul)} \\ +1.0 & \text{se pitch} = 2 \text{ (Amarelo)} \\ -3.0 & \text{se pitch} = 1 \land \text{power} \ge 4 \text{ (Vermelha Ofensiva)} \end{cases}$$
2. **Proteção de Peças Chave do Plano Ofensivo**:
   Se a carta estiver marcada como finalizador reservado no `TurnPlan` (`reserved_card_names`) e possuir `pitch == 1`, ela recebe penalidade extrema:
   $$\text{score}_{\text{pitch}} \mathrel{-}= 100.0$$
3. **Cartas Sem Pitch (Ex: *Gorganian Tome*)**:
   Cartas com `pitch <= 0` são sumariamente excluídas de candidatos de pitch para evitar rejeições e loops com o servidor.
4. **Refinamento ISMCTS de Pitch**:
   Quando há 2 ou mais opções válidas de pitch, o motor submete os candidatos à busca paralela ISMCTS para avaliar o impacto da carta oculta residual na mão.

---

## 3. Poda de Bloqueio Inteligente & Preservação de Pivot

### Fundamentação Oficial e Conceito
Bloquear além do estritamente necessário (*overblocking*) destrói a mão do defensor, impedindo que ele responda no seu próprio turno. O conceito de **Tempo Pivot** estabelece que heróis agressivos ou de alto custo (Brute, Guardian) devem aceitar dano residual não-letal para preservar cartas essenciais e virar a iniciativa no turno seguinte.

### Módulos do Código
- [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py)
- [`ai/hero_strategies/turn_planner.py`](../ai/hero_strategies/turn_planner.py)

### Regras Algorítmicas
1. **Anti-Overblocking Imediato**:
   $$\text{Se } \text{current\_blocked} \ge \text{opp\_power} \land \text{my\_hp} > 6 \implies \text{interrompe escolha de blocos}$$
2. **Preservação de Mão para Pivot**:
   - Se o herói está com vida saudável ($HP \ge 8$), não há ameaça On-Hit crítica, e a carta é uma bomba ofensiva (`pitch == 1` e `power >= 6`), aplica-se penalidade $\text{score} \mathrel{-}= 25.0$.
   - Cartas identificadas como recurso sagrado de pitch (`is_critical_pitch_resource`) sofrem penalidade $\text{score} \mathrel{-}= 30.0$.
   - Guardiões com 2 cartas azuis na mão poupam a 2ª azul ($\text{score} \mathrel{-}= 15.0$) para garantir ativações de custo 3 + arma no contra-ataque.
3. **Exceções Defensivas no Arsenal**:
   Cartas com `Ambush` e a carta *Down and Dirty* são autorizadas a defender diretamente do Arsenal:
   - *Down and Dirty* recebe bônus de $+1\{d\}$ (defende $4$ em vez de $3$).
   - Defender do Arsenal recebe bônus de score $\text{score} = \text{effective\_block} \times 2.5 + 5.0$, pois limpa o Arsenal e preserva cartas da mão.

---

## 4. Poda Global de Arsenal & Modo Cavar (CR 3.1.5 & CR 4.3.2)

### Fundamentação Oficial e Conceito
- **CR 3.1.5**: Cartas na zona de Arsenal **NÃO** podem ser usadas para gerar recursos (Pitch). Uma carta colocada no Arsenal só pode sair se for jogada (como ação, reação ou instant) ou se defender (apenas com keywords especiais como *Ambush*).
- **CR 4.3.2 (End of Turn)**: No final do turno, o jogador compra cartas até seu intelecto máximo. Se ele terminar o turno com a mão cheia de recursos inúteis e não arsenalar, ele não compra cartas novas e permanece travado.

### Módulos do Código
- [`ai/policy/arsenal_pruner.py`](../ai/policy/arsenal_pruner.py)
- [`ai/hero_strategies/base.py`](../ai/hero_strategies/base.py) (`is_resource_or_gem_card`)

### Regras Algorítmicas
1. **Rejeição Universal de Recursos e Gemas**:
   $$\text{Se } \text{type} = \text{'R'} \lor \text{subtype} \in \{\text{'Gem'}, \text{'Resource'}\} \lor \text{c\_name} \in \{\text{'heart\_of\_fyendal'}, \dots\} \implies \text{Exclusão Absoluta}$$
2. **Desvalorização de Bloco Não-DR**:
   Cartas de ação comuns com defesa 3 sem efeito de defesa no Arsenal perdem sua capacidade defensiva ao serem guardadas no Arsenal. O motor penaliza tais cartas para que permaneçam na mão como bloqueadores.
3. **Priorização de Reações de Defesa & Ranger**:
   Reações de Defesa (*Sink Below*, *Fate Foreseen*) e cartas com *Ambush* ganham alta prioridade de Arsenal, pois podem ser disparadas na janela de reação do oponente.
4. **Modo Cavar (Digging Mode - CR 4.3.2)**:
   Se nenhuma carta da mão obteve score positivo para Arsenal e o jogador possui $\ge 3$ cartas na mão (ex: múltiplos recursos):
   $$\text{dig\_score} = (\text{power} \times 3.0) + (10.0 \text{ se ação jogável}) + (2.0 \text{ se custo 0}) - (100.0 \text{ se gema pura})$$
   O bot escolhe a melhor ação para o Arsenal, permitindo que compre cartas novas até seu intelecto e destrave o baralho.

---

## 5. Resolução Legal de Armas & Sideboard (CR 2.8.2 e CR 3.0)

### Fundamentação Oficial e Conceito
- **CR 2.8.2**: Cada herói possui 2 mãos de equipamento (`main hand` e `off hand`).
- **CR 3.0**: Armas de duas mãos (2H) ocupam ambos os slots. Nenhuma off-hand, escudo ou segunda arma pode estar equipada junto com uma arma 2H.

### Módulos do Código
- [`ai/sideboard_manager.py`](../ai/sideboard_manager.py)
- [`tests/test_sideboard_and_stalemate.py`](../tests/test_sideboard_and_stalemate.py)

### Regras Algorítmicas
1. **Classificação Estrita de Armas**:
   - Armas 2H (*Sledge of Anvilheim*, *Anothos*, *Dawnblade*, *Raydn*, *Decimator Great Axe*): Custo de 2 mãos.
   - Armas 1H (*Titan's Fist*, *Harmonized Kodachi*, *Cintari Saber*, *Spider's Bite*): Custo de 1 mão.
   - Off-Hands e Escudos (*Stalagmite, Bastion of Isenloft*, *Rampart of the Ram's Head*): Custo de 1 mão.
2. **Resolução de Sideboard**:
   ```text
   Se w_2h e matchup de fadiga:
       equip(w_2h[0])
   Senão se w_1h e offhands:
       equip(w_1h[0], best_offhand)  # Ex: Titan's Fist + Stalagmite
   Senão se len(w_1h) >= 2:
       equip(w_1h[0], w_1h[1])       # Ex: Duas Kodachis
   Senão se w_2h:
       equip(w_2h[0])
   Armas e offhands excedentes -> Movidas para o Inventário (Sideboard)
   ```
3. **Mínimo de Baralho**: 40 cartas para Blitz, 60 para Classic Constructed (CC), e 65 cartas automáticas contra estratégias de fadiga (Guardian/Assassin).

---

## 6. Detecção de Stalemate / Empate Técnico & Anti-Loop (Tournament Rules)

### Fundamentação Oficial e Conceito
Em regras de torneio de FaB, uma partida pode atingir um estado em que nenhum jogador consegue vencer (ex: ambos com baralhos vazios e apenas cartas azuis sem ataque, ou repetição contínua de passes). Para evitar gasto infinito de CPU e congelamento em loops de prioridade, o motor implementa regras oficiais de encerramento por empate.

### Módulos do Código
- [`ai/bot_runtime/match_tracker.py`](../ai/bot_runtime/match_tracker.py)
- [`ai/bot_runtime/choice_handler.py`](../ai/bot_runtime/choice_handler.py)

### Regras Algorítmicas
1. **Critérios de Empate Técnico (Stalemate)**:
   - **Fadiga Estagnada**: Ambos os decks com 0 cartas e 3 turnos seguidos sem nenhuma alteração de vida.
   - **Deadlock Absoluto**: Decks com 0 cartas, mãos com 0 cartas e arsenais com 0 cartas (nenhuma ação possível).
   - **Estagnação Prolongada**: 12 turnos consecutivos sem dano com decks residuais $\le 5$ cartas.
2. **Hard Cap Anti-Loop por Formato**:
   $$\text{Limite de Turnos} = \begin{cases} 45 \text{ turnos} & \text{no Blitz / CompBlitz} \\ 55 \text{ turnos} & \text{no Classic Constructed (CC)} \end{cases}$$
3. **Ações Anti-Loop em Modais**:
   Rastreia assinaturas de estado $(\text{turn}, \text{phase}, |\text{hand}|, HP_1, HP_2)$. Se o bot passar pelo mesmo estado $> 4$ vezes seguidas ou cair em loop cíclico:
   - `DOCRANK` / `YESNO` $\to$ Força resposta `NO` (Mode 20).
   - `MAYCHOOSEMULTIZONE` $\to$ Força `PASS` (Mode 99).
   - `CHOOSEMULTIZONE` $\to$ Se travar consecutivamente, submete seleção do índice 0 (Mode 19).
4. **Finalização Limpa**: Registra `winner_id = 0` no ELO ($S = 0.5$) e desliga os subprocessos imediatamente.

---

## 7. Avaliação Dinâmica de Equipamentos & Aprendizado Empírico

### Fundamentação Oficial e Conceito
Substitui listas fixas de nomes de equipamentos por **metadados semânticos universais** e calibração por aprendizado por reforço empírico pós-partida, rastreando ativações de habilidades e bloqueios por herói.

### Módulos do Código
- [`ai/equipment_learning.py`](../ai/equipment_learning.py)
- [`data/equipment_metadata.json`](../data/equipment_metadata.json) (624 equipamentos)
- [`data/equipment_usage_stats.json`](../data/equipment_usage_stats.json)

### Regras e Fórmulas Matemáticas
1. **Atributos Semânticos Rastreaveis**:
   `power_buff`, `cost_discount`, `grants_resource`, `min_attack_cost`, `req_counters`, `has_go_again`, `creates_token`, `has_blade_break`, `has_battleworn`, `has_temper`.
2. **Calibração do Multiplicador Aprendido**:
   Para cada equipamento utilizado em jogo por determinado herói, ao fim da partida calcula-se:
   - Fator de Confiança Amostral:
     $$C = \min\left(1.0, \; \frac{N_{\text{total}}}{10.0}\right)$$
   - Bônus Posicional de Avaliação:
     $$\Delta_{\text{eval}} = \text{clamp}\left(\text{avg\_eval\_gain} \times 0.05, \; -0.2, \; 0.2\right)$$
   - Multiplicador Cru:
     $$M_{\text{raw}} = 1.0 + (WR - 0.5) \times 1.0 \times C + \Delta_{\text{eval}} \times C$$
   - Multiplicador Final Confinado:
     $$M_{\text{learned}} = \text{clamp}(M_{\text{raw}}, \; 0.5, \; 2.0)$$
3. **Ajuste Heurístico em Jogo**:
   O score de ativação de qualquer equipamento é ponderado por $M_{\text{learned}}$, priorizando armaduras comprovadamente eficientes para o herói em uso.

---

## 8. Quantificação de Ameaça On-Hit & Defesa de Breakpoint Mínimo (Knapsack Breakpoint)

### Fundamentação Oficial e Conceito
Efeitos *On-Hit* em Flesh and Blood são condicionados a causar pelo menos 1 de dano não bloqueado. Se todo o dano for bloqueado, o efeito não dispara. Ataques com efeitos catastróficos justificam gastar cartas adicionais ou armaduras para neutralizar totalmente o ataque no seu *breakpoint* exato.

### Módulos do Código
- [`ai/policy/constants.py`](../ai/policy/constants.py) (`ON_HIT_THREAT_VALUES`)
- [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py)

### Escala Numérica de Ameaça ($0.0$ a $10.0$)
| Categoria | Valor | Exemplos | Efeito em Jogo |
| :--- | :---: | :--- | :--- |
| **Catastrófico** | $8.0 - 10.0$ | *Command and Conquer*, *Red in the Ledger*, *Spinal Crush*, *Crippling Crush*, *Rightful King* | Destrói o Arsenal, congela ações a 1, remove Go Again ou descarta 2 cartas. |
| **Alto** | $5.0 - 7.5$ | *Snatch*, *Mask of Momentum*, *Herald of Erudition*, *Surgical Extraction*, *Leave no Witnesses* | Compras maciças, roubo de cartas ou banimento de arsenal. |
| **Médio** | $3.0 - 4.5$ | *Bloodrot Pox*, *Frailty*, *Inertia*, *Frostbite*, *Freeze* | Criação de aflições e penalidades de tempo. |
| **Vanilla** | $0.0$ | *Raging Onslaught*, *Wounded Bull*, ataques comuns sem gatilho | Dano puro sem efeitos colaterais. |

### Algoritmo Knapsack de Breakpoint Mínimo
Quando há um ataque com On-Hit perigoso ($\text{threat} \ge 3.0$) e vida segura ($HP > 6$):
1. Formula-se o problema da mochila: encontrar o subconjunto de candidatos $S$ (mão, arsenal com ambush, armaduras) tal que:
   $$\sum_{c \in S} \text{block}(c) \ge \text{opp\_power}$$
2. Minimiza-se a função de custo:
   $$\text{Custo}(S) = \sum_{c \in S} \text{cost}(c) + 0.7 \times (\text{total\_block} - \text{opp\_power})$$
   Onde cartas de mão possuem custo base $3.5 + \text{custo\_oportunidade}$, enquanto armaduras reutilizáveis (*Battleworn*) possuem custo $1.5$.
3. **Poda Estrita de Armaduras em Vanilla**:
   Se $\text{threat} == 0.0$ e $HP > 12$, armaduras descartáveis (*Blade Break*) são proibidas de entrar no bloqueio, reservando sua durabilidade para ataques que realmente ameacem a partida.

---

## 9. Prioritized Experience Replay (PER) & Auto-Tuning Dinâmico por Herói

### Fundamentação Oficial e Conceito
Nem todas as jogadas possuem a mesma relevância tática. Lances que causaram quedas abruptas de vantagem de mesa (*blunders*) ou jogadas brilhantes que viraram o jogo devem ser revisitadas com frequência muito maior pela rede neural. Em paralelo, heróis com dificuldades devem ter seus parâmetros heurísticos ajustados automaticamente.

### Módulos do Código
- [`ai/experience_collector.py`](../ai/experience_collector.py)
- [`ai/blunder_reviewer.py`](../ai/blunder_reviewer.py)
- [`ai/dynamic_rule_tuner.py`](../ai/dynamic_rule_tuner.py)

### Regras e Fórmulas Matemáticas
1. **Classificação e Pesos no Blunder Reviewer**:
   - **Blunder Severo** ($\Delta_{\text{eval}} \le -3.0$): Peso $3.5$ (máxima prioridade de re-amostragem).
   - **Imprecisão Tática** ($\Delta_{\text{eval}} \le -1.5$): Peso $2.0$.
   - **Lance Brilhante / Virada** ($\Delta_{\text{eval}} \ge +3.0$): Peso $2.0$.
   - **Lances Neutros**: Peso $1.0$.
   - **Últimos Passos em Derrota**: Peso mínimo $2.5$ para identificar o erro letal.
2. **Auto-Tuning Heurístico por Taxa de Vitória (`hero_rule_multipliers.json`)**:
   - **Taxa de Vitória $< 45\%$ (em $\ge 3$ jogos)**:
     $$\text{block\_weight} \mathrel{+}= 0.04, \quad \text{pivot\_bonus} \mathrel{+}= 0.03, \quad \text{attack\_weight} \mathrel{-}= 0.02$$
   - **Taxa de Vitória $> 60\%$ (em $\ge 3$ jogos)**:
     $$\text{attack\_weight} \mathrel{+}= 0.03, \quad \text{absorb\_tempo\_bonus} \mathrel{+}= 0.03$$
   - **Limites de Segurança**: Todos os pesos são estritamente mantidos em $[0.70, 1.40]$.

---

## 10. Proteção Ativa de Arsenal & Otimização da Crown of Providence

### Fundamentação Oficial e Conceito
A *Crown of Providence* é um dos equipamentos defensivos mais fortes de FaB. Ela concede 2 de defesa com *Blade Break* e permite, ao defender, colocar uma carta da mão ou do arsenal no fundo do deck para comprar uma nova.

### Módulos do Código
- [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py)
- [`ai/bot_runtime/choice_handler.py`](../ai/bot_runtime/choice_handler.py)

### Regras Algorítmicas
1. **Detecção de Destruidores de Arsenal**:
   Se o oponente ataca com *Command and Conquer*, *Leave No Witnesses*, *Wreck Havoc* ou *Eradicate* e o jogador possui carta no Arsenal:
   - A Crown of Providence recebe score $+35.0$ e custo mínimo $1.0$, entrando na cadeia de defesa com prioridade máxima.
2. **Sinking / Tuck Tático Inteligente (`score_choice_candidate`)**:
   - **Arsenal Sob Ameaça**: O bot seleciona a própria carta do Arsenal para afundar ($\text{score} = +150.0$), comprando 1 carta nova. A carta do Arsenal é salva no deck e o ataque do oponente não destrói nada.
   - **Arsenal Seguro**: O bot protege o Arsenal ($\text{score} = -200.0$) e inverte a pontuação das cartas da mão ($\text{score} = -\text{raw\_score}$), enviando para o fundo a **pior carta** da mão para buscar peças de ataque ou recursos.
3. **Ciclo de Mão Disfuncional**:
   Se a mão possuir $\ge 3$ cartas e não contiver nenhum pitch azul/amarelo ou nenhum ataque, a Crown bloqueia para destravar a mão.

---

## 11. Poda de Equipamentos de Prevenção e Reação no Vazio

### Fundamentação Oficial e Conceito
Equipamentos com janelas de reação instantânea ou de prevenção (*Boots of Omniward*, *Spellvoid*, *Ward*, *Arcane Barrier*, *Snapdragon Scalers*) muitas vezes ficam disponíveis para clique na interface mesmo sem benefício imediato. Ativá-los sem contexto desperdiça a peça permanentemente.

### Módulos do Código
- [`ai/bot_runtime/phase_decider.py`](../ai/bot_runtime/phase_decider.py) (`handle_reaction_phase`)

### Regras Algorítmicas
1. **Prevenção Sem Dano Ativo**:
   $$\text{Se } \text{is\_prevention\_eq} \land \text{opp\_power} \le 0 \land \text{arcane\_dmg} \le 0 \implies \text{Proibido Ativar}$$
2. **Preservação em Vida Alta contra Dano Vanilla**:
   Se a vida for saudável ($HP > 15$), o ataque não for fatal e não possuir ameaça On-Hit, itens de destruição única como *Boots of Omniward* são preservados para a reta final do jogo.
3. **Validação de Reações de Ataque (*Snapdragon Scalers*, *Flick Knives*)**:
   - Só podem ser ativadas durante o próprio turno de ataque (`is_attacking`).
   - Se o ataque em andamento já possui *Go Again*, proíbe o gasto da Snapdragon.
   - Se a mão está vazia (sem ataques subsequentes), proíbe o gasto da Snapdragon para não criar um Ponto de Ação inútil.

---

## 12. Bloqueio Flexível com Validação de Conversão de Mão

### Fundamentação Oficial e Conceito
Cartas com valor de defesa baixo ($\le 2\{d\}$) geram péssimo retorno se gastas no bloqueio. Se o herói tiver vida suficiente para absorver o impacto, manter 4 cartas na mão converte turnos com $14+$ de dano de retorno, sobrepujando o dano recebido.

### Módulos do Código
- [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py)
- [`ai/hero_strategies/turn_planner.py`](../ai/hero_strategies/turn_planner.py)

### Regras Algorítmicas
1. **Filtro de Conversão vs Absorção**:
   Se o plano tático determinou que é viável absorver dano (`turn_plan.can_absorb_damage`):
   - Subconjuntos de bloqueio com 2 ou mais cartas de mão cuja média de defesa seja $\le 2.0$ são sumariamente descartados.
   - O bot limita o bloqueio a no máximo 1 carta da mão se $HP > 15$ e o ataque for comum.
2. **Gatilho de Sobrevivência Estrita**:
   Se a vida atingir patamar crítico ($HP \le 6$) ou se o dano recebido for letal:
   - A política de preservação de pivot é desativada imediatamente.
   - O bot entra em bloqueio total, usando todas as cartas e armaduras necessárias para assegurar a permanência em jogo.

---

## 13. Treino Híbrido Humano vs Bot com Telemetria e Bônus ELO

### Fundamentação Oficial e Conceito
Partidas disputadas contra jogadores humanos oferecem amostras de treinamento de qualidade significativamente superior ao self-play puro, pois humanos exploram falhas táticas sutis e aplicam linhas de jogo criativas.

### Módulos do Código
- [`ai/bot_runtime/match_tracker.py`](../ai/bot_runtime/match_tracker.py)
- [`stats/elo.py`](../stats/elo.py)
- [`ai/experience_collector.py`](../ai/experience_collector.py)

### Regras Algorítmicas
1. **Identificação e Proteção de Partidas Humanas**:
   - Partidas com humanos são identificadas via `room_id` ou bot `AIMaster_Bot`.
   - **Imunidade a Punching Bag**: Partidas contra humanos nunca são descartadas sob a regra de bot inerte, respeitando o resultado real contra o jogador.
2. **Amplificação de Recompensa no Replay Buffer (3.0x)**:
   Se o bot vencer o jogador humano:
   $$\text{weights}_{\text{PER}} = [\text{weight} \times 3.0 \;\; \forall \;\; \text{passos da trajetória}]$$
   Isso faz com que a rede neural priorize fortemente as tomadas de decisão que superaram jogadores reais.
3. **Bônus de Prestígio no Dynamic Rule Tuner**:
   Vitórias contra humanos incrementam diretamente `human_wins` em `hero_rule_multipliers.json`, ajustando agressividade e absorção com bônus de prestígio.

---

## 14. Compreensão Semântica de Arena e Modificadores Dinâmicos de Combate

### Fundamentação Oficial e Conceito
Cartas de arena como Itens, Auras e Equipamentos ativos frequentemente concedem bônus de dano ou palavras-chave de evasão a ataques subsequentes sem que o texto esteja impresso na própria carta de ataque:
- **Dominate Concedido (CR 7.4.2a)**: Ex: *Convection Amplifier* concedendo Dominate ao próximo ataque, restringindo o bloqueio do defensor a no máximo 1 carta da mão.
- **Piercing Concedido (CR 8.5.21)**: Ex: *Penetration Script* concedendo Piercing (+1 de dano caso o defensor bloqueie com equipamento).
- **Dano On-Hit Concorrente**: Ex: Família *Boom Grenade* (+4, +3, +2 de dano se o ataque acertar).
- **Ameaça Arcana Concorrente**: Acúmulo de *Runechants* gerando dano arcano paralelo na mesma cadeia.

### Módulos do Código
- [`ai/policy/card_semantics.py`](../ai/policy/card_semantics.py)
- [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py)
- [`ai/policy/attack_pruner.py`](../ai/policy/attack_pruner.py)
- [`data/fab_card_semantics.json`](../data/fab_card_semantics.json)

### Regras Algorítmicas
1. **Síntese Dinâmica de Ameaça (`ArenaThreatContext`)**:
   A cada ciclo de decisão, o bot sintetiza `total_effective_physical_damage` somando o poder base aos bônus de itens da arena e computa `extra_on_hit_damage`.
2. **Defesa Adaptativa sob Dominate e Piercing de Arena**:
   - Se a arena adversária conceder Dominate, o podador restringe rigidamente a busca de subconjuntos de bloqueio a no máximo 1 carta da mão, prevenindo seleções de bloqueio ilegais no motor.
   - Se a arena adversária conceder Piercing, penaliza equipamentos com `block <= 1` (que gerariam mitigação líquida nula) e exige defesa estrita para cobrir o breakpoint.
3. **Poda de Ataque para Conversão de Itens Próprios**:
   Quando o bot possui itens próprios armados com gatilho de dano (ex: *Boom Grenade* própria), o `attack_pruner` eleva a prioridade de ataques com *Go Again* ou alto poder para forçar o acerto e disparar o dano extra.

---


---

## 15. Comportamento e Avaliação de Palavras-Chave de Combate

### Fundamentação Oficial e Conceito
A engine processa intrinsecamente os efeitos táticos de palavras-chave estruturais do Flesh and Blood, seja limitando matematicamente o domínio de cartas válidas para defesa, seja aplicando heurísticas de prioridade ou simulação de penalidades e efeitos estritos. O motor não apenas repassa a informação ao simulador de danos, mas ativamente avalia a semântica de cada keyword no podador de árvore de estados (MCTS) e na tomada de decisão em fases defensivas.

### Módulos do Código
- [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py)
- [`ai/game_simulator.py`](../ai/game_simulator.py)
- [`ai/policy/card_semantics.py`](../ai/policy/card_semantics.py)
- [`ai/hero_strategies/`](../ai/hero_strategies/) (especificamente `illusionist.py`, `guardian.py`, `brute.py`, `assassin.py`)

### Regras Algorítmicas
1. **Phantasm (CR 7.4.4)**:
   - **Mecânica:** Quando um ataque com Phantasm é bloqueado por uma carta não-Ilusionista com 6+ de Poder ("popper"), o ataque é destruído e a corrente de combate se encerra.
   - **Tática e Engine:** O `defense_pruner.py` procura ativamente por um *popper* na mão e atribui prioridade absoluta (custo `-200.0` no subset de defesa) se ele puder ser jogado, fechando a chain imediatamente sem perda de vida. A IA de Ilusionistas foca em usar e proteger cartas com Phantasm, sabendo deste risco calculável.
2. **Dominate (CR 7.4.2a) & Overpower (CR 7.4.2b, CR 8.3.22)**:
   - **Mecânica:** Restringem severamente a quantidade de cartas que podem defender vindas da mão do herói.
   - **Tática e Engine:** Em vez de depender do simulador para punir subconjuntos inválidos, o gerador em `defense_pruner.py` e a leitura de itens em `card_semantics.py` aplicam a poda preventivamente. Se há *Dominate*, nenhum subset de bloqueio gerado para o podador pode conter mais de 1 carta da mão. Se há *Overpower*, no máximo 1 carta de *Ação* da mão.
3. **Intimidate (CR 8.5.8)**:
   - **Mecânica:** Baniu aleatoriamente cartas da mão do oponente, reduzindo sua capacidade defensiva para a corrente de combate atual.
   - **Tática e Engine:** O `game_simulator.py` detecta cartas com o nome ou palavra-chave de *Intimidate* (ex: *Pack Hunt*). Ele contabiliza o `intimidate_count` acumulado e corta este número de cartas (`opp_hand[intimidate_count:]`) antes de calcular o bloqueio esperado do adversário. A estratégia de Brute usa ataques com mais de 6 de Poder para acionar esses gatilhos em massa.
4. **Piercing (CR 8.5.21)**:
   - **Mecânica:** Se o ataque for defendido por um equipamento, o atacante ganha +1 de dano para aquele elo.
   - **Tática e Engine:** Em `defense_pruner.py`, o motor soma +1 de poder ao ataque caso algum equipamento seja selecionado para o bloqueio. Equipamentos que defendem apenas 1 (`block <= 1`) geram mitigação líquida de `0` e são duramente penalizados heuristicamente (`-15.0`) e descartados no pós-processamento, já que a quebra ou uso deles seria em vão.

## 🔗 Mapeamento de Módulos e Referências

| Regra / Poda Tática | Arquivos Principais | Referência CR / TR |
| :--- | :--- | :--- |
| **1. Sequenciamento de Cadeia** | [`ai/policy/attack_pruner.py`](../ai/policy/attack_pruner.py) | CR 2.1.2, CR 2.3 |
| **2. Pitch Eficiente** | [`ai/policy/pitch_pruner.py`](../ai/policy/pitch_pruner.py) | CR 1.14 |
| **3. Bloqueio & Tempo Pivot** | [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py) | CR 2.4 |
| **4. Arsenal & Modo Cavar** | [`ai/policy/arsenal_pruner.py`](../ai/policy/arsenal_pruner.py) | CR 3.1.5, CR 4.3.2 |
| **5. Armas & Sideboard** | [`ai/sideboard_manager.py`](../ai/sideboard_manager.py) | CR 2.8.2, CR 3.0 |
| **6. Stalemate & Anti-Loop** | [`ai/bot_runtime/match_tracker.py`](../ai/bot_runtime/match_tracker.py) | FaB Tournament Rules 5.4 |
| **7. Aprendizado de Equipamentos** | [`ai/equipment_learning.py`](../ai/equipment_learning.py) | Heurística Empírica |
| **8. Knapsack Breakpoint** | [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py), [`ai/policy/constants.py`](../ai/policy/constants.py) | Teoria de Breakpoints FaB |
| **9. PER & Auto-Tuning** | [`ai/blunder_reviewer.py`](../ai/blunder_reviewer.py), [`ai/dynamic_rule_tuner.py`](../ai/dynamic_rule_tuner.py) | PER (Schaul et al.) |
| **10. Crown of Providence** | [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py), [`ai/bot_runtime/choice_handler.py`](../ai/bot_runtime/choice_handler.py) | CR 3.1.5 |
| **11. Prevenção no Vazio** | [`ai/bot_runtime/phase_decider.py`](../ai/bot_runtime/phase_decider.py) | CR 2.5, CR 2.6 |
| **12. Conversão de Mão** | [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py), [`ai/hero_strategies/turn_planner.py`](../ai/hero_strategies/turn_planner.py) | Teoria de Valor de Cartas FaB |
| **13. Treino Híbrido Humano** | [`ai/bot_runtime/match_tracker.py`](../ai/bot_runtime/match_tracker.py), [`stats/`](../stats/) | ELO Rating System |
| **14. Semântica de Arena** | [`ai/policy/card_semantics.py`](../ai/policy/card_semantics.py), [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py) | CR 7.4.2a, CR 8.5.21 |
| **15. Palavras-Chave de Combate** | [`ai/policy/defense_pruner.py`](../ai/policy/defense_pruner.py), [`ai/game_simulator.py`](../ai/game_simulator.py) | CR 7.4.2, 7.4.4, 8.5.8, 8.5.21 |
