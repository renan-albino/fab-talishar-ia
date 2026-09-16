# ADR-0006: Distilação Assimétrica da Política com Alvos de Visitas MCTS e Objetivos Auxiliares KataGo

- **Status**: Accepted
- **Date**: 2026-09-16
- **Deciders**: Equipe FaB Talishar AI (Architecture Review)

## Context

Flesh and Blood possui um espaço de estados e ações combinatórias de altíssima complexidade: turnos típicos envolvem sequenciamento fino de geração de recursos (pitch), priorização de ataques com e sem *Go Again*, cálculo de *breakpoints* de defesa e ativações de equipamentos.

Treinar a rede neural de política ($p_\theta$) e valor ($v_\theta$) exclusivamente com métodos de Reinforcement Learning baseados em recompensas binárias de fim de jogo ($z \in \{+1, -1\}$ para vitória ou derrota) apresenta sérias limitações:
1. **Esparsidade extrema de recompensa**: Em partidas com dezenas de turnos e centenas de decisões, um único erro tático no meio do combate (ex: defender com a carta errada ou não colocar uma carta no Arsenal) fica oculto no sinal tardio de vitória/derrota.
2. **Alta variância amostral**: Decisões brilhantes podem resultar em derrota por pura desvantagem estatística de compras futuras de baralho, desestabilizando a convergência da rede neural.
3. **Lentidão de aprendizado**: Milhares de partidas seriam necessárias apenas para aprender a lógica básica de que bloquear 4 de dano evita perder 4 de vida.

## Decision

Adotar a arquitetura de **Distilação Assimétrica** (*Asymmetric Distillation* / AlphaZero-style Policy Distillation) combinada com **Alvos Auxiliares KataGo** em `ai/training/orchestrator.py` e `ai/model.py`:

### 1. Distilação da Distribuição de Visitas MCTS ($\pi_{\text{MCTS}}$)
- Durante a busca em árvore, o motor ISMCTS realiza simulações em múltiplos mundos determinizados, avaliando centenas de nós e refinando as probabilidades de jogada.
- A distribuição de contagens de visitas normalizada da raiz ($\pi_{\text{MCTS}}$) representa um estimador de política muito mais refinado e forte do que a distribuição inicial da rede neural.
- O treinamento supervisiona a cabeça de política minimizando a perda de Cross-Entropy / Kullback-Leibler Divergence:
  $$\mathcal{L}_{\text{policy}} = -\sum_{a} \pi_{\text{MCTS}}(a \mid s) \log p_\theta(a \mid s)$$
- Esse processo destila a capacidade deliberativa de longo prazo do MCTS diretamente para os pesos da rede neural $p_\theta(s)$.

### 2. Cabeça de Valor e Prioritized Experience Replay (PER)
- A cabeça de valor prediz a probabilidade de vitória esperada $v_\theta(s) \in [-1, 1]$, treinada via Mean Squared Error (MSE) contra o resultado final da partida $z$:
  $$\mathcal{L}_{\text{value}} = \big( v_\theta(s) - z \big)^2$$
- Amostras de partidas são armazenadas no `ReplayBuffer` (`ai/experience_collector.py`) com pesos de prioridade gerados pelo `BlunderReviewer` (`ai/blunder_reviewer.py`).
- Durante o treinamento em lote na GPU, os gradientes são ponderados por pesos de amostragem de importância (*Importance Sampling weights* $w_i$, Schaul et al. 2016) para corrigir o viés de priorização.

### 3. Alvos Auxiliares Densos (Metodologia KataGo)
Inspirado na técnica proposta por David J. Wu (KataGo, 2019), a arquitetura `FaBPolicyValueNetwork` incorpora cabeças auxiliares lineares para estimar propriedades de curto prazo do jogo:
- **$\Delta\text{HP}$**: Variação líquida de pontos de vida ocorrida no turno (dano causado menos dano sofrido).
- **`turn_dmg`**: Dano total de ataque desferido ao longo do turno ativo.
- A perda auxiliar combinada é adicionada à função de custo total:
  $$\mathcal{L}_{\text{aux}} = 0.2 \times \Big( \text{MSE}(\hat{\Delta\text{HP}}, \Delta\text{HP}^*) + \text{MSE}(\hat{\text{turn\_dmg}}, \text{turn\_dmg}^*) \Big)$$
  $$\mathcal{L}_{\text{total}} = w_i \cdot \mathcal{L}_{\text{policy}} + w_i \cdot \mathcal{L}_{\text{value}} + \mathcal{L}_{\text{aux}}$$

## Consequences

### Positive
- **Aceleração da Convergência**: A rede aprende táticas sofisticadas de combate e sequenciamento com uma fração das partidas requeridas por algoritmos como PPO ou REINFORCE.
- **Riqueza de Representações Latentes**: As tarefas auxiliares forçam o *backbone* convolucional/denso a extrair características essenciais de dinâmica de combate (poder de ataque, blocos eficientes e corrida de pontos de vida).
- **Inferência Rápida e Eficaz**: A política destilada $p_\theta(s)$ atua como um excelente *prior* para podar e orientar futuras buscas MCTS (Prior Shaping), fechando um ciclo virtuoso de auto-aperfeiçoamento.
- **Treinamento Estável com FP16/AMP**: A formulação com Cross-Entropy e perdas auxiliares é numericamente estável com Automatic Mixed Precision (AMP) da PyTorch em GPU.

### Negative / Trade-offs
- **Dependência da Qualidade do MCTS**: Se a simulação do MCTS for subótima (ex: mundos mal determinizados ou número insuficiente de iterações), a rede neural aprenderá as imperfeições da busca.
- **Armazenamento no Replay Buffer**: O buffer precisa armazenar não apenas os estados e ações, mas também o vetor contínuo de visitas (32 dimensões) e as metas auxiliares por passo de jogo.

## Alternatives Considered

- **Algoritmos de Policy Gradient Direto (PPO / SAC)**: Rejeitados devido à incapacidade prática de convergir em ambientes estocásticos com turnos longos e regras combinatórias sem um oráculo de busca.
- **Supervisão Exclusiva por Heurísticas Estáticas**: Rejeitada porque a rede neural ficaria estritamente limitada ao teto de habilidade das heurísticas codificadas manualmente, sem capacidade de superá-las.
- **Treinamento sem Alvos Auxiliares (Apenas Policy + Value)**: Avaliado nos primeiros experimentos; a inclusão das perdas auxiliares KataGo reduziu a perda de valor em mais de 35% nas primeiras 20 épocas de treinamento.
