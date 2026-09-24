#!/usr/bin/env bash
# scripts/verify_ci.sh
# Validador local pré-push que replica a esteira de CI do GitHub Actions:
# 1. Validação de Sintaxe Python (compileall)
# 2. Dry-run da engine de ISMCTS
# 3. Execução da suíte completa de testes unitários (pytest) [Incremental]
# 4. Sincronização de setup_templates/
# 5. Build de produção do Talishar Frontend (Vite) [Incremental]
#
# Uso:
#   ./scripts/verify_ci.sh          # Execução inteligente (pula builds/testes não afetados)
#   ./scripts/verify_ci.sh --force  # Força execução de todas as etapas

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

FORCE_ALL=false
for arg in "$@"; do
    case "$arg" in
        --force|-f)
            FORCE_ALL=true
            ;;
        --help|-h)
            echo "Uso: ./scripts/verify_ci.sh [--force|-f]"
            echo "  --force, -f  Executa todas as 5 etapas sem pular nenhuma verificação."
            exit 0
            ;;
    esac
done

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}   🛡️  FaB Talishar AI - Pré-Push CI Validator        ${NC}"
echo -e "${BLUE}======================================================${NC}"

# Detecção incremental de arquivos alterados
UPSTREAM_REF=""
if [ "$FORCE_ALL" = false ]; then
    if git rev-parse --verify @{upstream} &>/dev/null; then
        UPSTREAM_REF="@{upstream}"
    elif git rev-parse --verify origin/main &>/dev/null; then
        UPSTREAM_REF="origin/main"
    fi
fi

if [ "$FORCE_ALL" = false ] && [ -n "$UPSTREAM_REF" ]; then
    COMMITTED_CHANGES=$(git diff --name-only "$UPSTREAM_REF"...HEAD 2>/dev/null || true)
    STAGED_CHANGES=$(git diff --name-only --cached 2>/dev/null || true)
    UNSTAGED_CHANGES=$(git diff --name-only 2>/dev/null || true)
    UNTRACKED_CHANGES=$(git ls-files --others --exclude-standard 2>/dev/null || true)
    ALL_CHANGED=$(echo -e "${COMMITTED_CHANGES}\n${STAGED_CHANGES}\n${UNSTAGED_CHANGES}\n${UNTRACKED_CHANGES}" | sort -u | sed '/^$/d')
    
    # Se não houver nada alterado, forçamos execução completa para segurança
    if [ -z "$ALL_CHANGED" ]; then
        FORCE_ALL=true
    fi
else
    FORCE_ALL=true
fi

if [ "$FORCE_ALL" = true ]; then
    echo -e "${YELLOW}[MODO COMPLETO] Executando todas as validações sem pular etapas.${NC}"
    HAS_CODE_CHANGES="1"
    HAS_FRONTEND_CHANGES="1"
else
    HAS_CODE_CHANGES=$(echo "$ALL_CHANGED" | grep -E '\.(py|json|ya?ml|sh)$|pytest\.ini|requirements' || true)
    HAS_FRONTEND_CHANGES=$(echo "$ALL_CHANGED" | grep -E '^(Talishar-FE/|setup_templates/frontend/)' || true)
    echo -e "${BLUE}[MODO INCREMENTAL] Analisando arquivos alterados frente a ${UPSTREAM_REF}...${NC}"
fi

PY_BIN="$ROOT_DIR/venv/bin/python"
if [ ! -f "$PY_BIN" ]; then
    PY_BIN="python3"
fi

# 1. Sintaxe Python
echo -e "${BLUE}[1/5] Validando sintaxe Python de todos os módulos...${NC}"
$PY_BIN -m compileall -q .
echo -e "${GREEN}[OK] Sintaxe Python 100% válida!${NC}"

# 2. ISMCTS Dry-Run
if [ -n "$HAS_CODE_CHANGES" ]; then
    echo -e "${BLUE}[2/5] Executando Dry-Run do motor ISMCTS...${NC}"
    $PY_BIN scripts/analyze_ismcts.py --dry-run
    echo -e "${GREEN}[OK] ISMCTS Dry-Run concluído com sucesso!${NC}"
else
    echo -e "${YELLOW}[2/5] [PULADO] Apenas documentação alterada. Pulando Dry-Run.${NC}"
fi

# 3. Testes Unitários com Pytest
if [ -n "$HAS_CODE_CHANGES" ]; then
    echo -e "${BLUE}[3/5] Executando suíte de testes unitários (Pytest)...${NC}"
    $PY_BIN -m pytest tests/ -q --tb=short
    echo -e "${GREEN}[OK] Todos os testes passaram com sucesso!${NC}"
else
    echo -e "${YELLOW}[3/5] [PULADO] Nenhuma alteração em código/testes/configs. Pulando Pytest.${NC}"
fi

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
if [ -n "$HAS_FRONTEND_CHANGES" ]; then
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
else
    echo -e "${YELLOW}[5/5] [PULADO] Nenhuma alteração no Frontend (Talishar-FE/). Pulando build Vite.${NC}"
fi

echo ""
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}   ✓ Validação Pré-Push Aprovada! Push Autorizado.    ${NC}"
echo -e "${GREEN}======================================================${NC}"
