#!/usr/bin/env bash

# ==============================================================================
# 🛑 FaB AI Engine & Dashboard - Stop Script
# ==============================================================================

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

STOP_DOCKER=true
STOP_DASHBOARD=true
STOP_BOTS=true
CLEAN_LOGS=false
VERBOSE=false
PID_FILE="$PROJECT_ROOT/.dashboard.pid"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Detect docker-compose vs docker compose
if docker compose version >/dev/null 2>&1; then
    DC_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC_CMD="docker-compose"
else
    DC_CMD="docker compose"
fi

show_help() {
    cat << EOF
Uso: ./stop.sh [OPÇÕES]

Opções:
  -a, --all             Para todos os serviços (Dashboard, Bots e Docker) [padrão]
  --dashboard-only      Para apenas o Dashboard e processos de Bots
  --docker-only         Para apenas os containers Docker do Talishar
  --bots-only           Para apenas os processos de bots em execução
  --clean-logs          Limpa os logs temporários após parar os serviços
  -v, --verbose         Exibe detalhes durante a parada
  --status              Exibe o status atual dos serviços
  -h, --help            Exibe esta mensagem de ajuda

Exemplos:
  ./stop.sh                    # Para todos os serviços
  ./stop.sh --dashboard-only   # Para apenas o dashboard
  ./stop.sh --clean-logs       # Para tudo e remove logs
EOF
}

check_status() {
    echo -e "${BLUE}=== Status dos Serviços FaB AI ===${NC}"
    
    if $DC_CMD -f "$PROJECT_ROOT/Talishar/docker-compose.yml" ps 2>/dev/null | grep -q "web-server"; then
        echo -e "🐳 Docker Talishar:       ${GREEN}RODANDO${NC}"
    else
        echo -e "🐳 Docker Talishar:       ${RED}PARADO${NC}"
    fi

    if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
        echo -e "📊 Streamlit Dashboard:    ${GREEN}RODANDO${NC} (PID $(cat "$PID_FILE"))"
    elif pgrep -f "streamlit run dashboard.py" > /dev/null 2>&1; then
        echo -e "📊 Streamlit Dashboard:    ${GREEN}RODANDO${NC}"
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
        -a|--all)
            STOP_DOCKER=true
            STOP_DASHBOARD=true
            STOP_BOTS=true
            shift
            ;;
        --dashboard-only)
            STOP_DOCKER=false
            STOP_DASHBOARD=true
            STOP_BOTS=true
            shift
            ;;
        --docker-only)
            STOP_DOCKER=true
            STOP_DASHBOARD=false
            STOP_BOTS=false
            shift
            ;;
        --bots-only)
            STOP_DOCKER=false
            STOP_DASHBOARD=false
            STOP_BOTS=true
            shift
            ;;
        --clean-logs)
            CLEAN_LOGS=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
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

if [ "$STOP_BOTS" = true ]; then
    echo -ne "${BLUE}[-] Finalizando processos de bots... ${NC}"
    pkill -9 -f "bot_client.py" 2>/dev/null || true
    echo -e "${GREEN}OK${NC}"
fi

if [ "$STOP_DASHBOARD" = true ]; then
    echo -ne "${BLUE}[-] Finalizando Streamlit Dashboard... ${NC}"
    if [ -f "$PID_FILE" ]; then
        DASH_PID=$(cat "$PID_FILE")
        kill "$DASH_PID" 2>/dev/null || true
        rm -f "$PID_FILE"
    fi
    pkill -f "streamlit run dashboard.py" 2>/dev/null || true
    echo -e "${GREEN}OK${NC}"
fi

if [ "$STOP_DOCKER" = true ]; then
    if [ -d "$PROJECT_ROOT/Talishar" ] && [ -f "$PROJECT_ROOT/Talishar/docker-compose.yml" ]; then
        if [ "$VERBOSE" = true ]; then
            echo -e "${BLUE}[-] Parando containers Docker do Talishar via $DC_CMD...${NC}"
            $DC_CMD -f "$PROJECT_ROOT/Talishar/docker-compose.yml" down
        else
            echo -ne "${BLUE}[-] Parando backend Talishar (Docker)... ${NC}"
            $DC_CMD -f "$PROJECT_ROOT/Talishar/docker-compose.yml" down > /dev/null 2>&1
            echo -e "${GREEN}OK${NC}"
        fi
    fi
fi

if [ "$CLEAN_LOGS" = true ]; then
    echo -ne "${BLUE}[-] Limpando logs temporários... ${NC}"
    if [ -d "$PROJECT_ROOT/logs" ]; then
        find "$PROJECT_ROOT/logs" -type f ! -name '.gitkeep' -delete 2>/dev/null || true
    fi
    echo -e "${GREEN}OK${NC}"
fi

echo ""
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}🛑 Serviços parados com sucesso!${NC}"
echo -e "${GREEN}======================================================${NC}"
