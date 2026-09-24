#!/usr/bin/env bash
# scripts/verify_ci.sh
# Validador local pré-push que replica a esteira de CI do GitHub Actions:
# 1. Validação de Sintaxe Python (compileall)
# 2. Dry-run da engine de ISMCTS
# 3. Execução da suíte completa de testes unitários (pytest)
# 4. Sincronização de setup_templates/
# 5. Build de produção do Talishar Frontend (Vite)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}   🛡️  FaB Talishar AI - Pré-Push CI Validator        ${NC}"
echo -e "${BLUE}======================================================${NC}"

PY_BIN="$ROOT_DIR/venv/bin/python"
if [ ! -f "$PY_BIN" ]; then
    PY_BIN="python3"
fi

# 1. Sintaxe Python
echo -e "${BLUE}[1/5] Validando sintaxe Python de todos os módulos...${NC}"
$PY_BIN -m compileall -q .
echo -e "${GREEN}[OK] Sintaxe Python 100% válida!${NC}"

# 2. ISMCTS Dry-Run
echo -e "${BLUE}[2/5] Executando Dry-Run do motor ISMCTS...${NC}"
$PY_BIN scripts/analyze_ismcts.py --dry-run
echo -e "${GREEN}[OK] ISMCTS Dry-Run concluído com sucesso!${NC}"

# 3. Testes Unitários com Pytest
echo -e "${BLUE}[3/5] Executando suíte de testes unitários (Pytest)...${NC}"
$PY_BIN -m pytest tests/ -q --tb=short
echo -e "${GREEN}[OK] Todos os testes passaram com sucesso!${NC}"

# 4. Sincronização de Templates
echo -e "${BLUE}[4/5] Verificando integridade e sincronização de setup_templates/...${NC}"
$PY_BIN scripts/prepare_environment.py --export-templates
if ! git diff --exit-code setup_templates/ >/dev/null 2>&1; then
    echo -e "${RED}[ERRO] setup_templates/ possui alterações não sincronizadas!${NC}"
    echo -e "${RED}Execute: git add setup_templates/ e faça commit antes de enviar.${NC}"
    exit 1
fi
echo -e "${GREEN}[OK] setup_templates/ perfeitamente sincronizado!${NC}"

# 5. Build de Produção do Frontend Vite
echo -e "${BLUE}[5/5] Validando compilação do Frontend Talishar-FE (Vite)...${NC}"
if [ -d "Talishar-FE" ] && [ -f "Talishar-FE/package.json" ]; then
    if command -v npx &>/dev/null; then
        (cd Talishar-FE && npx vite build)
        echo -e "${GREEN}[OK] Frontend compilado sem erros!${NC}"
    else
        echo -e "${YELLOW}[!] npx não encontrado. Pulando build do frontend.${NC}"
    fi
else
    echo -e "${YELLOW}[!] Talishar-FE não encontrado. Pulando build do frontend.${NC}"
fi

echo ""
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}   ✓ Validação Pré-Push Aprovada! Push Autorizado.    ${NC}"
echo -e "${GREEN}======================================================${NC}"
