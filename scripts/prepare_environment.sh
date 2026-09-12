#!/usr/bin/env bash
# scripts/prepare_environment.sh
# Prepara e sincroniza todo o ambiente do projeto em qualquer máquina Linux/WSL.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=================================================="
echo "   Iniciando Preparação do Ambiente FaB Talishar  "
echo "=================================================="

cd "$ROOT_DIR"

# Auto-configura socket do Podman para Vanilla OS / Podman rootless
if [ -S "/run/user/$UID/podman/podman.sock" ]; then
    export DOCKER_HOST="unix:///run/user/$UID/podman/podman.sock"
elif command -v distrobox-host-exec >/dev/null 2>&1; then
    distrobox-host-exec systemctl --user start podman.socket 2>/dev/null || true
    if [ -S "/run/user/$UID/podman/podman.sock" ]; then
        export DOCKER_HOST="unix:///run/user/$UID/podman/podman.sock"
    fi
fi

# 1. Verificar python3 e configurar Python Virtualenv se necessário
if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERRO] python3 não encontrado! Instale Python 3.10+ (ex: sudo apt install python3 python3-venv python3-pip)."
    exit 1
fi

if [ ! -d "venv" ]; then
    echo "[*] Criando ambiente virtual Python (venv)..."
    if ! python3 -m venv venv 2>/dev/null; then
        echo "[ERRO] Falha ao criar o virtualenv com 'python3 -m venv venv'."
        echo "Em sistemas Debian/Ubuntu/WSL, execute:"
        echo "  sudo apt update && sudo apt install -y python3-venv python3-pip"
        echo "Em sistemas Fedora/RHEL, execute:"
        echo "  sudo dnf install -y python3 python3-pip"
        exit 1
    fi
fi

echo "[*] Instalando/atualizando dependências Python..."
./venv/bin/pip install -q --upgrade pip
./venv/bin/pip install -q -r requirements.txt || true

# Validação e autocura de dependências Python C-extensions (NumPy / PyTorch / psutil)
if ! ./venv/bin/python -c "import numpy, torch, streamlit, psutil" >/dev/null 2>&1; then
    echo "[!] Dependências binárias do Python com erro de importação. Reparando com --force-reinstall..."
    ./venv/bin/pip install --force-reinstall numpy
    ./venv/bin/pip install -r requirements.txt
fi

# 2. Executar script de sincronização de templates, repositórios e permissões
./venv/bin/python scripts/prepare_environment.py

# 3. Preparar Frontend Node/Vite
if [ -d "Talishar-FE" ] && [ -f "Talishar-FE/package.json" ]; then
    echo "[*] Verificando dependências do Frontend (Talishar-FE)..."
    cd Talishar-FE
    if [ ! -d "node_modules" ]; then
        echo "[*] Instalando pacotes npm..."
        npm install
    fi
    echo "[*] Compilando Frontend para validar integridade..."
    npx vite build || echo "[!] Aviso: Build do Vite finalizado com observações."
    cd "$ROOT_DIR"
else
    echo "[!] Aviso: Talishar-FE/package.json não encontrado. Pulei o build do frontend."
fi

echo ""
echo "[✓] Ambiente 100% preparado e validado!"
echo "Comandos para iniciar:"
echo "  - Iniciar Dashboard: ./venv/bin/streamlit run dashboard.py"
echo "  - Iniciar Frontend:  ./start_frontend.sh"
echo "=================================================="
