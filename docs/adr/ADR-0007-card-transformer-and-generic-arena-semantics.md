# ADR-0007: Arquitetura Card Transformer (800 Dimensões) e Compreensão Semântica Genérica de Arena

- **Status**: Accepted
- **Date**: 2026-09-17
- **Deciders**: Equipe FaB Talishar AI (Architecture Review)

## Context

Na versão 1 (v1) do motor de inteligência artificial, a rede neural (`FaBPolicyValueNetwork`) e o motor de poda dependiam de uma representação estática de 192 dimensões baseada em blocos residuais (MLP/ResNet). Essa arquitetura apresentava limitações conceituais severas:

1. **Incapacidade de Leitura Semântica de Cartas**: O vetor de 192 entradas codificava apenas contagens agregadas de zonas (ex: quantas cartas na mão ou no cemitério) e um número limitado de flags categóricas. A rede não "enxergava" quais cartas estavam presentes na mão, na cadeia de combate ou na arena do oponente.
2. **Dependência de Hardcodes Nominais para a Arena**: A presença de itens, auras ou ameaças com gatilhos de dano concorrente (como *Boom Grenade* armada na Dash, *Convection Amplifier* concedendo Dominate, *Penetration Script* concedendo Piercing ou *Runechants* acumulados) era invisível para o bot a menos que cada carta fosse tratada por regras manuais específicas (*hardcode* nominal).
3. **Sensibilidade à Ordem das Cartas (Falta de Invariância a Permutações)**: Em um MLP plano, trocar a posição da Carta A e da Carta B nos índices de entrada gerava ativações distintas, forçando a rede a tentar aprender todas as permutações possíveis por força bruta durante o treino.
4. **Esparsidade vs Generalização**: Representar cartas individuais via vetores one-hot tradicionais exigiria mais de 5.000 dimensões esparsas adicionais por slot, tornando inviável o treino com a VRAM disponível.

## Decision

Migrar integralmente o motor neural e a camada de percepção tática para uma arquitetura baseada em **Card Transformer (800 dimensões)** e **Compreensão Semântica Orientada a Dados**, com eliminação completa e sem suporte retroativo aos modelos e artefatos legados da v1:

### 1. Base Canônica de Conhecimento Semântico (`data/fab_card_semantics.json`)
- Desenvolvido o extrator offline [`scripts/extract_card_semantics.py`](../../scripts/extract_card_semantics.py), compilando os dicionários oficiais em PHP da engine do Talishar.
- Cataloga 5.087 cartas oficiais com atributos funcionais: palavras-chave de combate (Dominate, Piercing, Overpower, Phantasm, Go Again, etc.), bônus de dano extra em caso de acerto (*on-hit*), severidades numéricas de disrupção (0.0 a 10.0) e modificadores de arena concedidos a ataques.

### 2. Matriz Tensorial de Embeddings em $O(1)$ (`data/card_embeddings.pt` & `data/card_to_idx.json`)
- O script [`scripts/generate_card_embeddings.py`](../../scripts/generate_card_embeddings.py) gera uma matriz PyTorch densa de dimensões `[5133, 48]` em FP32 (0.94 MB) e um índice hash `card_to_idx.json`.
- Cada vetor de 48 floats codifica:
  - `[0:6]`: Custo, Pitch, Poder, Defesa, Vida e Tipo de Carta.
  - `[6:22]`: 16 classes canônicas de Rathe em one-hot.
  - `[22:38]`: 16 combat keywords ativas.
  - `[38:48]`: Decomposição SVD dos textos de regras e gatilhos da carta.
- A extração em `extract_state_vector` consulta a tabela via slicing direto na memória RAM em microssegundos ($O(1)$), eliminando expressões regulares e parsing de strings durante as partidas.

### 3. Rede Neural `FaBCardTransformerNetwork` ([`ai/model.py`](../../ai/model.py))
- **Vetor Flat-Packed de 800 Dimensões**:
  - `[0:32]`: Contexto global da partida (HP dos jogadores, AP, recursos, cadeia de combate, fases do turno, ciclo de pitch e densidades de cores).
  - `[32:800]`: 16 slots estruturados de cartas $\times$ 48 floats semânticos (8 mão, 4 equipamentos, 2 arsenal, 1 elo ativo da cadeia, 1 ameaça prioritária da arena adversária).
- **Mecanismo de Atenção Dual**:
  - **Self-Attention**: 2 camadas de Transformer Encoder com 4 cabeças de atenção e dimensão latente 384 operando sobre os slots de cartas ativas, garantindo invariância a permutações e aprendizado de sinergias.
  - **Cross-Attention Contextual**: Projeta o token de contexto global contra as representações refinadas das cartas, modulando o plano de ação de acordo com a vida e os recursos disponíveis.
- **Cabeçotes de Decisão e Alvos KataGo**:
  - Policy Head (distribuição sobre 32 modos de ação).
  - Value Head (predição escalar de vitória entre $[-1.0, 1.0]$).
  - Cabeças Auxiliares KataGo para $\Delta\text{HP}$ e dano do turno (`turn_dmg`), preservando a técnica de destilação assimétrica estabelecida no ADR-0006.

### 4. Percepção Holística de Arena (`ai/policy/card_semantics.py`)
- O módulo sintetiza dinamicamente o `ArenaThreatContext` a cada tick de jogo, integrando itens armados do oponente (ex: *Boom Grenade* adicionando +4 de dano efetivo no breakpoint, *Convection Amplifier* acionando a restrição de Dominate de no máximo 1 carta da mão para bloquear) e orientando tanto o [`ai/policy/defense_pruner.py`](../../ai/policy/defense_pruner.py) quanto o [`ai/policy/attack_pruner.py`](../../ai/policy/attack_pruner.py).

### 5. Exclusão Irrestrita da v1
- Todos os checkpoints e buffers legados de 192 entradas foram deletados. O `ReplayBuffer` em [`ai/experience_collector.py`](../../ai/experience_collector.py) opera com `state_dim = 800` nativo e o novo modelo foi inicializado em `data/model_latest.pt` com 3.482.723 parâmetros.

## Consequences

### Positive
- **Compreensão Generalista**: O bot avalia o perigo real de qualquer carta da arena adversária sem necessitar de novas regras nominais adicionadas manualmente a cada expansão lançada.
- **Invariância Relacional**: O Self-Attention permite que o bot reconheça o mesmo plano de turno independentemente da ordem em que as cartas foram compradas na mão.
- **Alta Eficiência de Inferência**: Tempo de inferência mantido abaixo de 2ms na GPU graças ao caching estático em memória da matriz de embeddings.
- **Higienização do Repositório**: A suíte de testes foi consolidada de arquivos redundantes em 28 suítes canônicas com 353 testes automatizados (100% de aprovação).

### Negative / Trade-offs
- **Maior Consumo de RAM no Buffer**: O aumento da dimensão do estado de 192 para 800 eleva o consumo de memória do Replay Buffer por amostra (ajustado de forma automática em `config/settings.py`).
- **Incompatibilidade com Checkpoints Anteriores**: Checkpoints da v1 não podem ser carregados no novo modelo (o treinamento reinicia a partir do modelo base inicializado da v2).

## Alternatives Considered
- **LLM Multimodal em Tempo Real**: Rejeitado pelo custo de latência proibitivo (>500ms por decisão) incompatível com as restrições de tempo de turno do Talishar.
- **Embeddings Esparsos One-Hot (5.000+ dimensões)**: Rejeitado devido ao volume massivo de parâmetros não convergentes e incapacidade de inferir similaridade funcional entre cartas correlatas.
