# Pipeline de Dados (Data Pipeline)

Este documento detalha os scripts de extração de dados do projeto, responsáveis por gerar as bases de dados semânticas que alimentam a IA (como `data/fab_cards_db.json`, `data/ability_costs.json` e `data/equipment_metadata.json`). Esses scripts eliminam a necessidade de *hardcodes* nas lógicas e estratégias da IA, buscando as informações de regras diretamente do código-fonte e dos mapeamentos originais do Talishar.

## Visão Geral dos Scripts

### 1. `extract_card_db.py`
* **Localização:** Raiz do projeto (`/extract_card_db.py`)
* **Saída:** `data/fab_cards_db.json`

Este script é responsável por extrair a base de dados central das cartas do jogo.

* **Fonte dos dados:** Ele prioriza a leitura direta dos dicionários modulares do repositório local (especificamente `Talishar/GeneratedCode/GeneratedFunctions/*.php`, com fallback para `GeneratedCardDictionaries.php`). Caso os arquivos locais não estejam disponíveis, possui fallback para acessar o container Docker em execução do servidor web do Talishar, injetando e rodando um script PHP para exportar os dados via JSON.
* **Extração:** Quando executa localmente, utiliza expressões regulares (Regex) de alta performance para varrer e processar diretamente os arquivos individuais de funções geradas pelo Talishar (`GeneratedCardType`, `GeneratedCardCost`, `GeneratedPowerValue`, `GeneratedBlockValue`, `GeneratedPitchValue`, `GeneratedGoAgain`, `GeneratedCardClass`, entre outras), catalogando mais de 5.270 cartas em menos de 1 segundo de forma 100% offline.
* **Função e Uso na IA:** O artefato gerado, `fab_cards_db.json`, atua como o dicionário central de cartas para o Bot. Ele mapeia IDs para atributos base: custo, tipo, subtipo, slot de equipamento, poder, defesa, *pitch*, se possui *go again* inato, além de metadados como *Blade Break*, *Temper* e *Battleworn*. Além disso, o script importa e executa internamente o extraidor de custos de habilidades para injetar a propriedade `ability_cost` diretamente neste dicionário.

### 2. `extract_ability_costs.py`
* **Localização:** `scripts/extract_ability_costs.py`
* **Saída:** `data/ability_costs.json` (e também injetado em `fab_cards_db.json`)

Focado exclusivamente em descobrir o custo de ativação das habilidades das cartas (especialmente armas e equipamentos).

* **Fonte dos dados:** Lê diretamente do sistema de arquivos local nos diretórios `Talishar/CardDictionaries/` e do arquivo central `Talishar/CardDictionary.php`.
* **Extração:** Procura por funções PHP no formato `...AbilityCost($cardID)`. O script interpreta e entende as estruturas de código PHP como `switch ($cardID)` ou a sintaxe `match ($cardID)` para mapear os IDs das cartas aos seus custos de ativação em formato de inteiro.
* **Função e Uso na IA:** Gera o `ability_costs.json`. Esta extração permite que o motor de políticas (*PolicyEngine*) e o planejador de turno calculem exatamente quantos recursos a IA precisará para atacar com armas como *Romping Club* ou ativar itens que custam recursos. O objetivo é evitar que o agente dependa de adivinhações baseadas em texto ou configurações manuais.

### 3. `extract_equipment_metadata.py`
* **Localização:** `scripts/extract_equipment_metadata.py`
* **Saída:** `data/equipment_metadata.json`

Este é o script mais avançado e semântico do pipeline, focado em destrinchar como cada equipamento específico interage e altera as regras do jogo.

* **Fonte dos dados:** Puxa os arquivos extraídos primários (`data/fab_cards_db.json` e `data/ability_costs.json`) e inspeciona os códigos-fonte locais de efeitos ativos e mapeamentos em `Talishar/CardDictionaries/*.php` e `Talishar/CurrentEffectAbilities.php`.
* **Extração:** Além de Regex, ele compreende lógicas PHP completas (*switch/match*). Ele extrai metadados finos, como:
  * `AbilityType` (Ação, Reação de Ataque, Instantânea);
  * `AbilityHasGoAgain`;
  * Modificadores de combate (ex: `EffectPowerModifier`);
  * Checagem de condições como custo mínimo de ataque para ativação (`CombatEffectActive`);
  * Descontos concedidos em custos (`$costModifier -= N`);
  * Recursos gerados (`GainResources(N)`) e criação de *tokens* ou auras (`PlayAura`).
  * Mescla essas lógicas com a interpretação simplificada do texto descritivo da carta (identificando palavras-chave ausentes nas variáveis isoladas).
* **Função e Uso na IA:** Emite o `equipment_metadata.json`. Sem isso, o bot de IA não saberia usar seu inventário de maneira ótima. Esse mapeamento alimenta o `equipment_evaluator.py`, provendo dados tabulares sobre as capacidades de *buff*, desconto, concessão de *go again*, e *token generation* para cada equipamento. Isso viabiliza um mecanismo dinâmico e flexível para que a IA integre esses itens no seu cálculo de otimização de táticas durante as partidas, independentemente de estarem *hardcoded* ou não.

### 4. `extract_card_semantics.py`
* **Localização:** `scripts/extract_card_semantics.py`
* **Saída:** `data/fab_card_semantics.json`

Gera a base de conhecimento semântico e modificadores de combate para 5.144 cartas catalogadas.

* **Fonte dos dados:** Lê o banco bruto `data/fab_cards_db.json` e os dicionários PHP do Talishar (`Talishar/CardDictionaries/`).
* **Extração:** Processa textos e metadados para catalogar:
  * Papel tático (`aggro`, `control`, `combo`, `disruption`, `setup`);
  * Palavras-chave de combate (Phantasm, Dominate, Overpower, Piercing, Stealth, Contract, Boost);
  * Gatilhos On-Hit (dano, descarte, banimento, tokens de Frostbite/Bloodrot/Frailty/Inertia);
  * Modificadores de arena concedidos a outros ataques (ex: buffs de poder contínuos, concessão de Dominate ou Piercing por itens/auras).
* **Função e Uso na IA:** Alimenta o sistema de percepção holística de ameaças de arena (`ai/policy/card_semantics.py`), permitindo que a IA compreenda efeitos complexos de itens em campo (como *Boom Grenade* ou *Convection Amplifier*) sem depender de nomes hardcoded.

### 5. `extract_cr_mechanics.py`
* **Localização:** `scripts/extract_cr_mechanics.py`
* **Saída:** Atualização incremental em `data/fab_card_semantics.json`

Cruza as regras formais do *Comprehensive Rules* (CR) com o dicionário de cartas para garantir conformidade estrita.

* **Fonte dos dados:** Cruzamento de `data/fab_cards_db.json` com regras canônicas de CR (CR 7.4.4 Phantasm, CR 7.4.2a Dominate, CR 7.4.2b Overpower, CR 8.5.8 Intimidate, CR 8.5.21 Piercing, CR 8.6 Arena Tokens e CR 8.5 Effect Keywords).
* **Extração:** 
  * Identifica cartas categorizadas como "Poppers" de Phantasm (Poder $\ge 6$), ataques com evasão inerente e cartas com efeitos instantâneos defensivos;
  * Cataloga as 9 palavras-chave de efeito da CR 8.5 (`clash`, `wager`, `amp`, `transcend`, `reload`, `freeze`, `intimidate`, `opt`, `charge`);
  * Mapeia os 38 tokens oficiais da CR 8.6 (*Quicken*, *Agility*, *Frostbite*, *Inertia*, *Bloodrot Pox*, *Frailty*, *Might*, *Vigor*, etc.) com suas propriedades táticas.
* **Função e Uso na IA:** Garante que o `defense_pruner.py`, `attack_pruner.py` e o `game_simulator.py` tenham flags booleanas pré-compiladas de conformidade de regras oficiais, acelerando o tempo de resposta do podador.

### 6. `generate_card_embeddings.py`
* **Localização:** `scripts/generate_card_embeddings.py`
* **Saída:** `data/card_embeddings.pt` e `data/card_to_idx.json`

Compila a representação vetorial densa de todas as cartas para inferência em $O(1)$ na rede neural Transformer.

* **Fonte dos dados:** Combina `data/fab_card_semantics.json` e `data/fab_cards_db.json`.
* **Extração:** Codifica cada carta em um vetor de 48 floats:
  * 16 floats estruturais normalizados (custo, poder, defesa, pitch, vida, slots de equipamento);
  * 16 floats de atributos categóricos e keywords (one-hot de classes de herói e talentos);
  * 16 floats de componentes semânticos textuais gerados via decomposição SVD (*TruncatedSVD*) sobre a matriz TF-IDF de textos e efeitos.
* **Função e Uso na IA:** Gera a matriz densa PyTorch `[5145, 48]` em FP32. Durante a partida, o `ai/model.py` recupera embeddings dos 16 slots ativos instantaneamente via indexação tensorial, alimentando o mecanismo de Cross/Self-Attention do Transformer sem latência de parsing.

### 7. `analyze_match_anomalies.py`
* **Localização:** `scripts/analyze_match_anomalies.py`
* **Saída:** Relatório analítico de telemetria no terminal

Audita a base transacional SQLite3 para diagnosticar anomalias de balanceamento e integridade de partidas.

* **Fonte dos dados:** Consulta tabelas `match_history`, `hero_elo` e `dynamic_rules` em `data/talishar_stats.db`.
* **Extração:** Identifica e quantifica:
  * Partidas anuladas e timeouts técnicos (desconexões e deadlocks);
  * Partidas ultracurtas ($\le 6$ turnos) e vitórias unilaterais (*Punching Bags*);
  * Overkills extremos ($\text{HP final} \le -5$);
  * Win Rate consolidado por baralho/herói, rankings de ELO e multiplicadores dinâmicos ativos (`dynamic_rules`).
* **Função e Uso na IA:** Fornece visibilidade estatística para desenvolvedores e calibradores de heurísticas, permitindo identificar desequilíbrios no meta (como dominância de aliados) e disparar intervenções orientadas a dados.
