#!/usr/bin/env bash
# ==============================================================================
# Script de Inicializacao Completa do Frontend e Backend do Talishar
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR"
TALISHAR_DIR="$PROJECT_DIR/Talishar"
FRONTEND_DIR="$PROJECT_DIR/Talishar-FE"

# Detect docker-compose command
if docker compose version >/dev/null 2>&1; then
    DC_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    DC_CMD="docker-compose"
else
    DC_CMD="docker compose"
fi

mkdir -p "$PROJECT_DIR/logs"

echo "=== [1/3] Verificando Backend Docker (Apache / MySQL / Redis) ==="
if [ -d "$TALISHAR_DIR" ]; then
    cd "$TALISHAR_DIR"
    ln -sfn ../decks decks || true
    if $DC_CMD ps 2>/dev/null | grep -q "web-server"; then
        echo "Backend Docker ja esta em execucao (Porta 8080)."
    else
        echo "Iniciando containers do backend via $DC_CMD..."
        $DC_CMD up -d
        echo "Backend Docker iniciado com sucesso!"
    fi
fi

echo "=== [2/3] Verificando Frontend Talishar (Vite / React) ==="
cd "$FRONTEND_DIR"

if [ ! -f ".env" ]; then
    echo "Criando .env a partir de .env.template..."
    cp .env.template .env
fi

echo "=== [3/3] Iniciando Servidor Vite na Porta 3000 ==="
if pgrep -f "vite.*3000" > /dev/null; then
    echo "Frontend Vite ja esta rodando em http://localhost:3000"
else
    nohup npx vite --port 3000 --host > "$PROJECT_DIR/logs/frontend.log" 2>&1 &
    sleep 2
    echo "Frontend Vite iniciado com sucesso em http://localhost:3000!"
fi

echo "================================================================="
echo "Talishar Pronto para Jogar!"
echo "Frontend URL: http://localhost:3000"
echo "Backend API:  http://localhost:8080/game"
echo "================================================================="
