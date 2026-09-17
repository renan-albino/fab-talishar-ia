# Guia de Contribuição - FaB Talishar AI Engine

Bem-vindo(a)! Ficamos felizes com o seu interesse em contribuir com o **FaB Talishar AI Engine**. Este documento serve como um guia completo de onboarding para ajudar você a configurar o ambiente de desenvolvimento, entender a arquitetura do projeto e executar os testes automatizados.

## 🛠️ Configurando o Ambiente

Para garantir que o ambiente seja configurado de forma fácil e padronizada (e imune a diferenças entre sistemas operacionais), utilizamos um script automatizado de preparação.

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/renan-albino/fab-talishar-ia.git
   cd fab-talishar-ia
   ```

2. **Execute o script de setup automatizado:**
   ```bash
   ./scripts/prepare_environment.sh
   ```
   > Esse script é **idempotente**, o que significa que pode ser executado várias vezes sem quebrar o ambiente. Ele se encarrega de criar o virtualenv Python (`venv/`), baixar as dependências (Python, Node/npm), aplicar patches no backend/frontend, preparar o banco de cartas e configurar o Docker local.

3. **Inicie os serviços:**
   ```bash
   ./start.sh
   ```

## 🏗️ Arquitetura do Projeto

O projeto é altamente modularizado. Ao navegar pelo código, você trabalhará principalmente nos seguintes diretórios chave:

- **`ai/`**: O "Cérebro" do projeto. Contém todos os módulos de Inteligência Artificial e Deep RL. Aqui dentro, você encontrará motores de decisão (ISMCTS), o simulador determinístico do jogo (`ai/game_simulator.py`), a rede neural em PyTorch (`ai/model.py`), lógicas de podas táticas, runtime do bot e estratégias específicas para os heróis do jogo (`ai/hero_strategies/`).
- **`ui/`**: Interface do usuário para o Dashboard Analítico. Construído utilizando o framework Streamlit, os arquivos estão organizados de forma modular, delegando a responsabilidade de visualização para `ui/helpers.py` e separando as telas em `ui/tabs/` (com 7 abas dedicadas, incluindo Play, Arena, Treino, etc).
- **`deck_manager/`**: Módulo desacoplado responsável pela gestão centralizada de baralhos. Trata de tudo relacionado aos decks: o parseamento (leitura dos arquivos de configuração), validação de formatos rigorosos (Blitz, Classic Constructed), verificação do limite de cópias das cartas, inventário de equipamentos e persistência atômica.
- **`stats/`**: Sistema de rankeamento e métricas de desempenho. Aqui ocorrem os cálculos do rating **ELO dinâmico**, consolidação de vitórias/derrotas de forma canônica (evitando duplicatas de decks), sincronização com proteção de escrita (locks atômicos) e gerenciamento dos históricos de partidas no formato de leaderboards.

## 🧪 Rodando os Testes Automatizados

Garantir que as regras e podas táticas da IA não quebrem a cada alteração é essencial. O projeto conta com uma extensa suíte de centenas de testes automatizados unitários e de integração utilizando o framework `pytest`.

Para rodar todos os testes localizados na pasta `tests/` e verificar a integridade da aplicação, utilize o executável do ambiente virtual previamente criado:

```bash
./venv/bin/pytest tests/
```

Caso você tenha ativado o `venv` manualmente na sua sessão do terminal (ou se ele estiver no `PATH`), também é possível rodar usando o comando clássico:
```bash
pytest tests/
```

*Os testes isolam as lógicas nativamente e executam rapidamente, validando desde o motor híbrido MCTS/ISMCTS, estratégias de classes (Guardiões, Guerreiros, Ninjas, etc.) até os parsers de deck.*

## 📝 Regras Gerais para Commits

- **Não versione lixo:** Nunca realize o commit de logs brutos (`logs/*.log`) ou binários de rede neural não filtrados. Nosso projeto utiliza hooks de Git (`pre-commit` e `post-commit`), já configurados via `prepare_environment.sh`, que limpam resíduos, verificam tipagem, e compilam o frontend automaticamente antes de qualquer envio.
- **Use as ferramentas de automação:** Se fizer qualquer alteração no frontend (`Talishar-FE/`) ou backend (`Talishar/`) original, lembre-se de sincronizar os templates rodando: `./venv/bin/python scripts/prepare_environment.py --export-templates`.
- **Dúvidas Adicionais?** Consulte o arquivo principal `README.md` e também os documentos técnicos na pasta `docs/` (como `docs/tactical_rules.md`) para entender mais a fundo o funcionamento dos algoritmos antes de propor grandes refatorações na lógica de avaliação da engine.

Obrigado por ajudar a aprimorar o FaB Talishar AI Engine!
