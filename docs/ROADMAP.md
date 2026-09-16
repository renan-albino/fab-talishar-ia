# 🗺️ Roadmap Técnico & Próximos Marcos — FaB Talishar AI

Este documento estabelece o direcionamento estratégico e o planejamento de evolução do motor **FaB Talishar AI**, consolidando melhorias arquiteturais, aprofundamento em regras oficiais (CR) de Flesh and Blood e expansão de cobertura de testes.

---

## 📌 Status dos Marcos de Testes e Cobertura

- [x] **Modularização dos 9 Monólitos**: Todos os arquivos de lógica de negócio decompostos em pacotes coesos abaixo de 500 linhas.
- [x] **Governança & ADRs**: ADR-0001 a ADR-0006 documentados em `docs/adr/`, `CONTEXT.md` com diretivas de vocabulário e domínio.
- [x] **Regras Oficiais de Combate (CR)**: Phantasm Popping (CR 7.4.4), Dominate (CR 7.4.2a), Overpower (CR 7.4.2b), Piercing (CR 8.5.21) e Intimidate (CR 8.5.8).
- [x] **Resiliência & Concorrência**: Conversores universais `safe_*`, polling adaptativo, eliminação de zumbis Unix e virtual loss simétrico.
- [x] **Ferramentas CLI de Automação**: `validate_decks.py`, `benchmark_mcts.py`, `healthcheck_talishar.py` e `run_smoke_tests.py`.
- [🔄] **Passo 1 (Em Execução)**: Cobertura de rede e ciclo de lobby (`lobby_manager.py` e `talishar_api.py`) via mocks abrangentes de endpoints PHP.
- [🔄] **Passo 2 (Em Execução)**: Testes parametrizados de modais complexos e tratamento de escolhas (`choice_handler.py` e `phase_decider.py`).

---

## 🎯 Próximo Marco Prioritário: Passo 3 (Especialização de Classes & Estados Complexos)

### 🗡️ Escopo do Passo 3: Expansão de Testes para Classes de Alta Complexidade Tática

O objetivo do **Passo 3** é elevar a cobertura e o rigor das estratégias de heróis que operam com mecânicas não-lineares, auras, contratos ou recursos acumulativos:

#### 1. Classe Ilusionista (`ai/hero_strategies/illusionist.py`)
- **Gestão de Auras e Miragens**:
  - Simulação de criação e sacrifício de *Spectral Shields* (Prism / Enigma).
  - Sequenciamento de ataques com *Phantasm* contra defensores com Poder $< 6$ vs defensores pesados com Poder $\ge 6$.
  - Preservação e proteção de dragões / auras contínuas (Dromai / Enigma) contra ataques com Go Again.

#### 2. Classe Assassino (`ai/hero_strategies/assassin.py`)
- **Contratos e Mecânicas de Furtividade (Stealth & Banish)**:
  - Resolução de gatilhos de *Contract* (banimento de cartas vermelhas/ataques do topo do baralho oponente).
  - Sequenciamento de ataques *Stealth* com reações de ataque especializadas (*Cut to the Chase*, *Spike with Bloodrot*).
  - Poda tática de interceptação de cartas banidas para maximizar disrupção da mão adversária.

#### 3. Classe Runeblade (`ai/hero_strategies/runeblade.py`)
- **Sequenciamento de Dano Híbrido (Arcano + Físico)**:
  - Acúmulo e detonação ideal de *Runechants* em cadeia com cartas de ação não-ataque (*Non-Attack Actions*) e ataques de custo reduzido.
  - Sinergia de *Blood Debt* e mitigação de auto-dano com Vynnset.

---

## 🚀 Marcos Futuros de Evolução

### Marco 4: Reforço de Testes de Interface Streamlit (`ui/tabs/`)
- Mocks modulares de sessão do Streamlit para exercitar os callbacks das abas de Arena, Torneios e Treinamento sem necessidade de navegador ativo.

### Marco 5: Self-Play Distribuído & Asymmetric Distillation
- Pipeline contínuo de treinamento GPU utilizando visitas ISMCTS ($\pi_{\text{MCTS}}$) para acelerar convergência do modelo neural `model_latest.pt`.
- Avaliação automatizada de ELO em torneios Round-Robin de 1.000 partidas entre checkpoints de redes neurais.
