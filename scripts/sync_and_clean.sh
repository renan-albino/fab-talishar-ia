#!/usr/bin/env bash
# scripts/sync_and_clean.sh
# Automação de limpeza de testes temporários, sincronização de templates e validação pré-commit.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
HOOK_FILE="$ROOT_DIR/.git/hooks/pre-commit"

cd "$ROOT_DIR"

# Cores para terminal
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

function print_banner() {
    echo -e "${BLUE}======================================================${NC}"
    echo -e "${BLUE}   FaB Talishar AI - Sync & Clean Automation Tool     ${NC}"
    echo -e "${BLUE}======================================================${NC}"
}

function show_help() {
    print_banner
    echo "Uso: ./scripts/sync_and_clean.sh [OPÇÕES]"
    echo ""
    echo "Opções:"
    echo "  (sem argumentos)   Executa a limpeza de logs/testes, exporta templates e valida sintaxe"
    echo "  --install-hook     Instala este script como git pre-commit hook automático"
    echo "  --uninstall-hook   Remove o git pre-commit hook"
    echo "  --check-only       Verifica integridade sem apagar logs nem exportar arquivos"
    echo "  --help, -h         Exibe esta mensagem de ajuda"
    echo ""
}

function install_hook() {
    print_banner
    if [ ! -d "$ROOT_DIR/.git" ]; then
        echo -e "${RED}[ERRO] Diretório .git não encontrado. Não é um repositório git.${NC}"
        exit 1
    fi
    mkdir -p "$ROOT_DIR/.git/hooks"
    cat << 'HOOK_EOF' > "$HOOK_FILE"
#!/usr/bin/env bash
# Git pre-commit hook gerado por scripts/sync_and_clean.sh
set -e
ROOT_DIR="$(git rev-parse --show-toplevel)"
if [ -f "$ROOT_DIR/scripts/sync_and_clean.sh" ]; then
    bash "$ROOT_DIR/scripts/sync_and_clean.sh"
fi
HOOK_EOF
    chmod +x "$HOOK_FILE"
    echo -e "${GREEN}[OK] Git pre-commit hook instalado com sucesso em .git/hooks/pre-commit!${NC}"

    # Instala o hook post-commit para sincronização de checkpoints
    PY_BIN="$ROOT_DIR/venv/bin/python"
    [ ! -f "$PY_BIN" ] && PY_BIN="python3"
    $PY_BIN "$ROOT_DIR/scripts/manage_state.py" --install-hook

    echo -e "     Agora, a cada 'git commit':"
    echo -e "       1. Pre-commit: limpa logs, exporta templates e valida sintaxe."
    echo -e "       2. Post-commit: se houver novo checkpoint treinado, publica na GitHub Release automaticamente."
    exit 0
}

function uninstall_hook() {
    print_banner
    if [ -f "$HOOK_FILE" ]; then
        rm -f "$HOOK_FILE"
        echo -e "${GREEN}[OK] Git pre-commit hook removido com sucesso.${NC}"
    else
        echo -e "${YELLOW}[!] Nenhum hook pre-commit estava instalado.${NC}"
    fi

    PY_BIN="$ROOT_DIR/venv/bin/python"
    [ ! -f "$PY_BIN" ] && PY_BIN="python3"
    $PY_BIN "$ROOT_DIR/scripts/manage_state.py" --uninstall-hook
    exit 0
}

# Tratamento de argumentos
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    show_help
    exit 0
elif [ "$1" == "--install-hook" ]; then
    install_hook
elif [ "$1" == "--uninstall-hook" ]; then
    uninstall_hook
fi

print_banner

# 1. Encerrar processos de bots residuais
echo -e "${BLUE}[1/5] Encerrando processos de bots residuais...${NC}"
pkill -9 -f "bot_client.py" 2>/dev/null || true
echo -e "${GREEN}[OK] Processos de teste finalizados.${NC}"

# 2. Limpar logs temporários de partidas e testes
echo -e "${BLUE}[2/5] Limpando arquivos de logs e partidas de teste...${NC}"
if [ -d "logs" ]; then
    rm -f logs/*Test* logs/*Treino* logs/test_* logs/Human_vs_Bot_* 2>/dev/null || true
    rm -f logs/*_debug.log logs/*_terminal.log logs/*_match_feed.log logs/*_summary.log 2>/dev/null || true
    rm -f logs/*_game_id.txt logs/*_p2_ready.txt logs/*_host_deck.txt logs/*_join_deck.txt 2>/dev/null || true
    rm -f logs/*_Bot*.json 2>/dev/null || true
    echo -e "${GREEN}[OK] Diretório logs/ higienizado (preservando logs de sistema).${NC}"
fi

# 3. Exportar arquivos ativos do Backend e Frontend para setup_templates/
echo -e "${BLUE}[3/5] Sincronizando modificações com setup_templates/...${NC}"
PY_BIN="./venv/bin/python"
if [ ! -f "$PY_BIN" ]; then
    PY_BIN="python3"
fi

$PY_BIN scripts/prepare_environment.py --export-templates

# 4. Validar sintaxe Python de todos os scripts
echo -e "${BLUE}[4/5] Validando sintaxe do código Python...${NC}"
$PY_BIN -m py_compile *.py ai/*.py scripts/*.py
echo -e "${GREEN}[OK] Sintaxe de todos os módulos Python validada sem erros!${NC}"

# 5. Adicionar setup_templates/ ao stage do Git se dentro de repositório
echo -e "${BLUE}[5/5] Atualizando staging do Git com templates sincronizados...${NC}"
if command -v git &>/dev/null && [ -d ".git" ]; then
    git add setup_templates/
    echo -e "${GREEN}[OK] setup_templates/ adicionado ao stage do Git.${NC}"
fi

echo ""
echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}   ✓ Limpeza, Sincronização e Validação Concluídas!   ${NC}"
echo -e "${GREEN}======================================================${NC}"
echo -e "O repositório está pronto e limpo para novos commits ou testes."
echo -e "Dica: Execute ${YELLOW}./scripts/sync_and_clean.sh --install-hook${NC} para rodar isso automaticamente a cada 'git commit'."
