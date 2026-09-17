# Pipeline de Dados (Data Pipeline)

Este documento detalha os scripts de extração de dados do projeto, responsáveis por gerar as bases de dados semânticas que alimentam a IA (como `data/fab_cards_db.json`, `data/ability_costs.json` e `data/equipment_metadata.json`). Esses scripts eliminam a necessidade de *hardcodes* nas lógicas e estratégias da IA, buscando as informações de regras diretamente do código-fonte e dos mapeamentos originais do Talishar.

## Visão Geral dos Scripts

### 1. `extract_card_db.py`
* **Localização:** Raiz do projeto (`/extract_card_db.py`)
* **Saída:** `data/fab_cards_db.json`

Este script é responsável por extrair a base de dados central das cartas do jogo.

* **Fonte dos dados:** Ele prioriza a leitura direta do repositório local (especificamente `Talishar/GeneratedCode/GeneratedCardDictionaries.php`). Caso o arquivo local não esteja disponível, ele possui um *fallback* (plano B) para acessar o container Docker em execução do servidor web do Talishar, injetando e rodando um script PHP para exportar os dados via JSON.
* **Extração:** Quando executa localmente, utiliza expressões regulares (Regex) para varrer e processar (fazer *parse*) as funções geradas pelo Talishar, como `GeneratedCardType`, `GeneratedCardCost`, `GeneratedPowerValue`, `GeneratedBlockValue`, entre várias outras (como detecção de bloqueio condicional e *keywords* defensivas).
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
