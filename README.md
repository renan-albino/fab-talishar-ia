# ⚔️ Talishar Flesh and Blood AI Engine & Dashboard

Ambiente completo de treinamento autônomo, simulação em alta velocidade e análise de desempenho com sistema de rating Elo para partidas de Flesh and Blood utilizando o backend local do Talishar.

---

## 📋 Índice
1. [Visão Geral do Projeto](#-visão-geral-do-projeto)
2. [Configuração do SSH Automático no ZSH](#-configuração-do-ssh-automático-no-zsh)
3. [Pré-requisitos no Linux Mint / Ubuntu](#-pré-requisitos-no-linux-mint--ubuntu)
4. [Instalação e Execução](#-instalação-e-execução)
5. [Estrutura da Codebase](#-estrutura-da-codebase)
6. [Mecânicas do Bot e Protocolo Talishar](#-mecânicas-do-bot-e-protocolo-talishar)
7. [🤖 Guia de Contexto para Agentes de IA & Roadmap de Tarefas](#-guia-de-contexto-para-agentes-de-ia--roadmap-de-tarefas)

---

## 🌟 Visão Geral do Projeto

Este projeto permite executar simulações de partidas de Flesh and Blood em ambiente local entre dois agentes autônomos (bots). Ele integra:
* **Backend Talishar Local**: Motor oficial de regras em PHP/MySQL/Redis rodando via Docker.
* **Cliente de Bot Assíncrono (`bot_client.py`)**: Cliente ultrarrápido com conexões HTTP persistentes (`requests.Session`), sistema de anti-loop e suporte a múltiplas fases do jogo (Ataques, Bloqueios, Reações, Crank, Busca no Deck, Input de nomes de cartas e Pitch).
* **Dashboard Interativo Streamlit (`dashboard.py`)**: Interface visual com monitoramento em tempo real sem fade-out ou duplicações (`@st.fragment`), importação de decks do Fabrary e gráficos de desempenho Elo.
* **Métricas & Rating Elo (`stats_manager.py`)**: Classificação dinâmica ($K=32$) por deck/herói com persistência automática.

---

## 🔑 Configuração do SSH Automático no ZSH

Se você utiliza **Zsh** (como Oh My Zsh) no Linux Mint / Ubuntu e possui uma chave SSH personalizada (`~/.ssh/chavegit`), configure para carregar automaticamente em qualquer nova aba ou sessão do terminal:

### Opção 1: Configuração Universal via `~/.ssh/config` (Recomendada)
```bash
mkdir -p ~/.ssh
cat << 'CONFIG_EOF' >> ~/.ssh/config
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/chavegit
    IdentitiesOnly yes
CONFIG_EOF
chmod 600 ~/.ssh/config
```

### Opção 2: Carregamento Automático no `~/.zshrc`
Abra o `~/.zshrc` ou adicione as linhas ao final:
```bash
cat << 'ZSH_EOF' >> ~/.zshrc

# Iniciar ssh-agent e carregar chave do GitHub automaticamente
if [ -z "$SSH_AUTH_SOCK" ]; then
   eval "$(ssh-agent -s)" > /dev/null
fi
if [ -f ~/.ssh/chavegit ]; then
   ssh-add -q ~/.ssh/chavegit 2>/dev/null
fi
ZSH_EOF

source ~/.zshrc
```

Para testar a autenticação:
```bash
ssh -T git@github.com
```

---

## 🚀 Pré-requisitos no Linux Mint / Ubuntu

Instale os pacotes básicos do sistema operacional:
```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip docker.io docker-compose git
sudo usermod -aG docker $USER
```

---

## 🛠️ Instalação e Execução

### 1. Clonar o Repositório via SSH
```bash
git clone git@github.com:renan-albino/fab-talishar-ia.git
cd fab-talishar-ia
```

### 2. Iniciar o Backend Docker do Talishar
```bash
cd Talishar
docker compose up -d
cd ..
```
*Confira se os containers subiram:*
```bash
docker ps
```

### 3. Configurar o Ambiente Virtual Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Executar o Dashboard
```bash
./venv/bin/streamlit run dashboard.py
```
Acesse no navegador: **`http://localhost:8501`**

---

## 📁 Estrutura da Codebase

```text
├── Talishar/                 # Backend PHP / Docker do motor de regras do FaB
├── Talishar-FE/              # Frontend web original do Talishar (opcional)
├── decks/                    # Decks salvos em formato JSON compatível
├── data/
│   └── training_stats.json   # Histórico de partidas e ratings Elo
├── logs/                     # Logs de comunicação e métricas em tempo real
├── bot_client.py             # Agente de tomada de decisão e automação HTTP
├── dashboard.py              # Interface Streamlit com fragmentos em tempo real
├── deck_parser.py            # Parser de decks do Fabrary e formatador JSON
├── stats_manager.py          # Gerenciador de partidas e cálculo de Elo Rating
├── mock_fabrary.py           # Mock local para testes offline do Fabrary
├── requirements.txt          # Dependências Python
└── README.md                 # Documentação e guia do projeto
```

---

## ⚙️ Mecânicas do Bot e Protocolo Talishar

### Endpoints da API do Talishar
* **`POST /game/APIs/CreateGame.php`**: Cria a sala de jogo (Host).
* **`POST /game/APIs/JoinGame.php`**: Conecta o Jogador 2 à sala.
* **`POST /game/APIs/ChooseFirstPlayer.php`**: Define a ordem de início (`action: "Go First"`).
* **`POST /game/APIs/SubmitSideboard.php`**: Envia a lista expandida de cartas e equipamentos no campo `"submission": json.dumps(sub_obj)`.
* **`GET /game/GetNextTurn.php`**: Obtém o estado atual da mesa em JSON com polling de alta velocidade (`havePriority`, `playerHealth`, `playerHand`, `playerEquipment`, `popup`, etc.).
* **`GET /game/ProcessInput.php`**: Executa uma ação de jogo.

### Mapeamento de Modos de Ação (`ProcessInput.php`)
* **`Mode 3`**: Habilidade de Equipamento ou Arma (ex: *Symbiosis Shot*, *Teklo Foundry Heart*).
* **`Mode 4`**: Colocar carta no Arsenal a partir da mão (Fase `ARS`).
* **`Mode 6`**: Enviar carta do Pitch para o fundo do Deck (Fase `PDECK`).
* **`Mode 7`**: Entrada Numérica / Custo X (Fases `CHOOSENUMBER`, `DYNPITCH`, `NUMBERINPUT`).
* **`Mode 12 / 13`**: Reordenação de cartas (Fases `CHOOSETOP` / `CHOOSEBOTTOM`).
* **`Mode 16`**: Seleção de alvo em Popup / Busca no Deck (`CHOOSECARD`, `MAYCHOOSEDECK`).
* **`Mode 17`**: Gatilhos e botões modais (`BUTTONINPUT`, `CHOOSETRIGGERS`).
* **`Mode 19`**: Seleção múltipla via checkboxes (`CHOOSEMULTIZONE`).
* **`Mode 20`**: Decisão Booleana (Fases `YESNO` ou `DOCRANK`).
* **`Mode 27`**: Jogar carta de Ação, Ataque, Bloqueio (`B`) ou Pitch (`P`).
* **`Mode 30`**: Nomear carta via texto com `inputText` (Fase `INPUTCARDNAME`).
* **`Mode 99`**: Passar prioridade / Finalizar ações da fase atual.

---

## 🤖 Guia de Contexto para Agentes de IA & Roadmap de Tarefas

> **Para a próxima IA trabalhando nesta Codebase**: Utilize as diretrizes abaixo para continuar o desenvolvimento, refatoração ou expansão das capacidades dos bots.

### Regras Críticas da Codebase
1. **Sideboard Payload**: No endpoint `SubmitSideboard.php`, o campo `deck` deve ser uma **lista plana de strings** com cada carta repetida pelo seu `total` (ex: 75 cartas no formato Classic Constructed). Não passe objetos ou dicionários diretamente no array `deck`.
2. **Dashboard sem Flickering**: O monitoramento de partidas no `dashboard.py` utiliza `@st.fragment(run_every="2s")`. Nunca adicione `st.rerun()` dentro de loops com `time.sleep()` no escopo principal do script para não reintroduzir problemas de esmaecimento (fade-out) e componentes duplicados.
3. **Anti-Loop**: Em `bot_client.py`, ações repetidas na mesma fase de turno são protegidas pelo `loop_detector`. Se o bot atingir mais de 10 ticks na mesma fase sem progresso, force o clique em botões de prompt disponíveis ou envie `Mode 99` e resete o contador.

---

### 🎯 Roadmap de Tarefas para IAs

#### 1. Implementação de Algoritmo de Decisão Avançado (MCTS / Redes Neurais)
* **Objetivo**: Substituir a heurística linear de `decide_and_act()` por uma árvore de busca Monte Carlo (MCTS) ou uma rede de política treinada com PyTorch para otimizar sequências de combo, sequenciamento de recursos e bloqueios eficientes.
* **Arquivos-alvo**: `bot_client.py`, criar novo módulo `ai/policy_engine.py`.

#### 2. Suporte Abrangente a Novas Classes de Heróis
* **Objetivo**: Adicionar regras específicas para classes como:
  * **Runeblade**: Gerenciamento de marcadores de *Runechant* e sequenciamento de dano arcano vs físico.
  * **Wizard**: Tomada de ações na fase de reação do oponente (instants em alta velocidade).
  * **Brute / Guardian**: Mecânicas de *Roll* de dados (*Scramble*), esmagamento (*Crush*) e custo de pitch alto.
* **Arquivos-alvo**: `bot_client.py` (métodos `decide_and_act`).

#### 3. Visualizador Gráfico de Tabuleiro no Streamlit
* **Objetivo**: Renderizar graficamente no Dashboard a mesa completa (Combat Chain, Arsenal, Equipamentos com contadores de vida útil/vapor e cartas na mão) consumindo os links de imagens oficiais do Talishar ou Fabrary.
* **Arquivos-alvo**: `dashboard.py`.

#### 4. Execução de Torneios Automatizados (Round-Robin & Swiss System)
* **Objetivo**: Adicionar ao `dashboard.py` um organizador de torneios com 4 a 16 decks disputando chaves Suíças ou todos contra todos, gerando relatórios de matchup e matriz de winrate por matchup.
* **Arquivos-alvo**: `dashboard.py`, `stats_manager.py`.
