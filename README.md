# ⚔️ Talishar Flesh and Blood AI Engine & Dashboard

Ambiente de treinamento autônomo, simulação em alta velocidade e análise de desempenho com sistema Elo para partidas de Flesh and Blood utilizando o backend local do Talishar.

---

## 🚀 Pré-requisitos (Linux Mint / Ubuntu / Debian)

1. **Docker & Docker Compose** (para rodar o servidor PHP/MySQL do Talishar):
   ```bash
   sudo apt update
   sudo apt install -y docker.io docker-compose
   sudo usermod -aG docker $USER
   # Recomendado reiniciar a sessão caso precise rodar docker sem sudo
   ```

2. **Python 3.10+ & Virtualenv**:
   ```bash
   sudo apt install -y python3 python3-venv python3-pip git
   ```

---

## 🛠️ Passo a Passo de Instalação & Execução

### 1. Iniciar os Containers do Talishar
No diretório raiz do projeto:
```bash
cd Talishar
docker compose up -d
cd ..
```
*Verifique se os containers subiram:*
```bash
docker ps
```

### 2. Configurar o Ambiente Virtual Python
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Iniciar o Dashboard Interativo
```bash
./venv/bin/streamlit run dashboard.py
```
Acesse no seu navegador: **`http://localhost:8501`**

---

## 📊 Recursos do Dashboard

* **Gerenciamento de Decks:**
  * Importação direta de decks do Fabrary via URL ou formato JSON.
* **Execução em Lote & Auto-Battler:**
  * Disparo de partidas autônomas com execução ultra-rápida via HTTP keep-alive.
* **Monitoramento em Tempo Real (`@st.fragment`):**
  * Atualização dinâmica a cada 2s sem fade visual, sem duplicação de janelas e com visualização unificada da linha do tempo de combate.
* **Analytics & Sistema Elo:**
  * Cálculo de rating Elo ($K=32$) por deck/arquétipo, taxa de vitórias e histórico recente.

---

## 🧑‍💻 Comandos Úteis

* **Parar os containers do Talishar:**
  ```bash
  cd Talishar && docker compose down && cd ..
  ```
* **Limpar logs de partidas antigas:**
  ```bash
  rm -f logs/Treino_*
  ```
