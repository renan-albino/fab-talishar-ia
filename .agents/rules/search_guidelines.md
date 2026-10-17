---
trigger: always_on
description: Fast surgical search rules using WSL2 git grep and fast_search.py; forbids blind grep -r on root and unquoted pipes in PowerShell.
---

# Fast Search & Anti-Blind-Grep Rule

Rule:
- **PROIBIDO GREP CEGO NA RAIZ (`grep -r .`)**: O repositório contém diretórios massivos (`node_modules/`, `venv/`, `Talishar/Games/`, `Talishar-FE/build/`, `logs/`, `data/`) que possuem centenas de milhares de arquivos brutos. Executar `grep -r .` ou `grep -rn "termo" .` sem exclusão de diretórios causa travamento total (hang/timeout), estouro de buffer e gasto massivo de tokens.
- **PROIBIDO `|` DESPROTEGIDO NO POWERSHELL**: Como o host é Windows PowerShell invocando `wsl`, caracteres `|` fora de aspas simples são interpretados como pipe do PowerShell e quebram regexes. Para múltiplos padrões no `git grep`, use múltiplos `-e` (`git grep -n -e "termo1" -e "termo2"`).
- **SEMPRE UTILIZE BUSCA CIRÚRGICA E EFICIENTE VIA WSL2**:
  1. **Nativo do Git (Preferencial)**: `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia git grep -n "termo"` (ou múltiplos `-e "A" -e "B"`) — busca instantânea e restrita exclusivamente aos arquivos versionados, ignorando automaticamente `venv`, `node_modules`, logs e bancos locais.
  2. **Script Especializado**: `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia ./venv/bin/python scripts/fast_search.py "termo" [caminho] [--ext=.py,.tsx]` — busca com poda automática de pastas pesadas.
  3. **Grep Restrito a Subpacotes**: Aponte diretamente para o módulo relevante: `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia grep -rn "termo" ai/ tests/ scripts/ deck_manager/ stats/ ui/`.
  4. **Grep com Exclusão Obrigatória**: Se for indispensável usar `grep -r`, utilize sempre:
     `wsl -d Ubuntu-22.04 --cd /home/renan/fab-talishar-ia grep -rn --exclude-dir={node_modules,venv,Talishar,Talishar-FE,logs,data,build,dist,.git,__pycache__} "termo" .`
