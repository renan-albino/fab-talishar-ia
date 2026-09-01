#!/usr/bin/env bash

# ==============================================================================
# ⚔️ FaB AI Engine & Dashboard - Start Script
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

START_DOCKER=true
START_DASHBOARD=true
VERBOSE=false
DASHBOARD_PORT=8501
PID_FILE="$PROJECT_ROOT/.dashboard.pid"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

show_help() {
    cat << EOF
Uso: ./start.sh [OPÇÕES]

Opções:
  -s, --silent          Executa de modo silencioso (padrão)
  -v, --verbose         Mostra logs detalhados durante a inicialização
  --no-docker           Não inicia os containers Docker (inicia apenas o Dashboard)
  --no-dashboard        Não inicia o Dashboard (inicia apenas o Docker Talishar)
  --port <PORT>         Porta para o Streamlit Dashboard (padrão: 8501)
  --status              Exibe o status atual dos serviços sem iniciá-los
  -h, --help            Exibe esta mensagem de ajuda

Exemplos:
  ./start.sh                    # Inicia tudo em modo silencioso
  ./start.sh -v                 # Inicia com saída detalhada
  ./start.sh --no-dashboard     # Inicia apenas o backend Talishar
  ./start.sh --status           # Verifica se os serviços estão rodando
EOF
}

check_status() {
    echo -e "${BLUE}=== Status dos Serviços FaB AI ===${NC}"
    
    if docker compose -f "$PROJECT_ROOT/Talishar/docker-compose.yml" ps 2>/dev/null | grep -q "web-server"; then
        echo -e "🐳 Docker Talishar:       ${GREEN}RODANDO${NC} (http://localhost:8080)"
    else
        echo -e "🐳 Docker Talishar:       ${RED}PARADO${NC}"
    fi

    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "📊 Streamlit Dashboard:    ${GREEN}RODANDO${NC} (PID $(cat "$PID_FILE") - http://localhost:$DASHBOARD_PORT)"
    elif pgrep -f "streamlit run dashboard.py" > /dev/null 2>&1; then
        echo -e "📊 Streamlit Dashboard:    ${GREEN}RODANDO${NC} (http://localhost:$DASHBOARD_PORT)"
    else
        echo -e "📊 Streamlit Dashboard:    ${RED}PARADO${NC}"
    fi

    ACTIVE_BOTS=$(pgrep -f "bot_client.py" 2>/dev/null | wc -l || echo "0")
    ACTIVE_BOTS=$(echo "$ACTIVE_BOTS" | tr -d '[:space:]')
    if [ "$ACTIVE_BOTS" -gt 0 ]; then
        echo -e "🤖 Bots em Partida:        ${GREEN}$ACTIVE_BOTS processo(s) ativo(s)${NC}"
    else
        echo -e "🤖 Bots em Partida:        ${YELLOW}Nenhum ativo${NC}"
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            show_help
            exit 0
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -s|--silent)
            VERBOSE=false
            shift
            ;;
        --no-docker)
            START_DOCKER=false
            shift
            ;;
        --no-dashboard)
            START_DASHBOARD=false
            shift
            ;;
        --port)
            DASHBOARD_PORT="$2"
            shift 2
            ;;
        --status)
            check_status
            exit 0
            ;;
        *)
            echo -e "${RED}Opção desconhecida: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

mkdir -p "$PROJECT_ROOT/logs" "$PROJECT_ROOT/data"

if [ "$START_DOCKER" = true ]; then
    if [ ! -d "$PROJECT_ROOT/Talishar" ] || [ ! -f "$PROJECT_ROOT/Talishar/docker-compose.yml" ]; then
        echo -e "${RED}[ERRO] Diretório Talishar ou docker-compose.yml não encontrado!${NC}"
        exit 1
    fi

    cp -n "$PROJECT_ROOT/Talishar/HostFiles/RedirectorTemplate.php" "$PROJECT_ROOT/Talishar/HostFiles/Redirector.php" 2>/dev/null || true
    cp -n "$PROJECT_ROOT/Talishar/APIKeys/APIKeys.php.template" "$PROJECT_ROOT/Talishar/APIKeys/APIKeys.php" 2>/dev/null || true
    if [ ! -f "$PROJECT_ROOT/Talishar/HostFiles/GameIDCounter.txt" ]; then
        echo "1" > "$PROJECT_ROOT/Talishar/HostFiles/GameIDCounter.txt"
    fi
    mkdir -p "$PROJECT_ROOT/Talishar/Games" "$PROJECT_ROOT/Talishar/AccountFiles"
    chmod -R 777 "$PROJECT_ROOT/Talishar/HostFiles" "$PROJECT_ROOT/Talishar/Games" "$PROJECT_ROOT/Talishar/AccountFiles" "$PROJECT_ROOT/Talishar/APIKeys" 2>/dev/null || true

    if [ "$VERBOSE" = true ]; then
        echo -e "${BLUE}[+] Subindo containers Docker do Talishar...${NC}"
        docker compose -f "$PROJECT_ROOT/Talishar/docker-compose.yml" up -d
    else
        echo -ne "${BLUE}[+] Subindo backend Talishar (Docker)... ${NC}"
        docker compose -f "$PROJECT_ROOT/Talishar/docker-compose.yml" up -d > /dev/null 2>&1
        echo -e "${GREEN}OK${NC}"
    fi

    echo -ne "${BLUE}[+] Aguardando inicialização do backend Talishar (porta 8080)... ${NC}"
    MAX_RETRIES=30
    COUNT=0
    SERVER_READY=false
    while [ $COUNT -lt $MAX_RETRIES ]; do
        if curl -s -o /dev/null "http://localhost:8080/game/APIs/CreateGame.php" 2>/dev/null || curl -s -o /dev/null "http://localhost:8080" 2>/dev/null; then
            SERVER_READY=true
            break
        fi
        sleep 1
        COUNT=$((COUNT + 1))
    done

    if [ "$SERVER_READY" = true ]; then
        echo -e "${GREEN}PRONTO${NC}"
    else
        echo -e "${YELLOW}AVISO: Servidor ainda iniciando em segundo plano.${NC}"
    fi
fi

if [ "$START_DASHBOARD" = true ]; then
    VENV_PYTHON="$PROJECT_ROOT/venv/bin/python"
    VENV_STREAMLIT="$PROJECT_ROOT/venv/bin/streamlit"

    if [ ! -f "$VENV_STREAMLIT" ]; then
        echo -e "${RED}[ERRO] Ambiente virtual Python não encontrado em ./venv!${NC}"
        exit 1
    fi

    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "${YELLOW}[!] Dashboard já está em execução com PID $(cat "$PID_FILE").${NC}"
    elif pgrep -f "streamlit run dashboard.py" > /dev/null 2>&1; then
        echo -e "${YELLOW}[!] Dashboard já está em execução.${NC}"
    else
        echo -ne "${BLUE}[+] Iniciando Streamlit Dashboard na porta $DASHBOARD_PORT... ${NC}"
        nohup "$VENV_STREAMLIT" run dashboard.py \
            --server.port "$DASHBOARD_PORT" \
            --server.headless true \
            --browser.serverAddress "localhost" \
            --server.enableCORS false \
            --server.enableXsrfProtection false \
            > "$PROJECT_ROOT/logs/dashboard.log" 2>&1 &
        
        DASH_PID=$!
        echo "$DASH_PID" > "$PID_FILE"
        sleep 2

        if kill -0 "$DASH_PID" 2>/dev/null; then
            echo -e "${GREEN}OK (PID: $DASH_PID)${NC}"
        else
            echo -e "${RED}FALHA! Verifique logs/dashboard.log${NC}"
            exit 1
        fi
    fi
fi

echo ""
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}🚀 Serviços iniciados com sucesso!${NC}"
echo -e "   🌐 Talishar Backend:   ${BLUE}http://localhost:8080${NC}"
echo -e "   📊 AI Dashboard:       ${BLUE}http://localhost:$DASHBOARD_PORT${NC}"
echo -e "   📜 Logs do Dashboard:  ${YELLOW}logs/dashboard.log${NC}"
echo -e "   🛑 Para parar tudo:    ${YELLOW}./stop.sh${NC}"
echo -e "${GREEN}======================================================${NC}"
