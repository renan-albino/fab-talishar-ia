# Fast Search & Anti-Blind-Grep Rule

Rule:
- **PROIBIDO GREP CEGO NA RAIZ (`grep -r .`)**: O repositório contém diretórios massivos (`node_modules/`, `venv/`, `Talishar/Games/`, `Talishar-FE/build/`, `logs/`, `data/`) que possuem centenas de milhares de arquivos brutos. Executar `grep -r .` ou `grep -rn "termo" .` sem exclusão de diretórios causa travamento total (hang/timeout), estouro de buffer e gasto massivo de tokens.
- **SEMPRE UTILIZE BUSCA CIRÚRGICA E EFICIENTE**:
  1. **Nativo do Git (Preferencial)**: `git grep -n "termo"` — busca instantânea e restrita exclusivamente aos arquivos versionados, ignorando automaticamente `venv`, `node_modules`, logs e bancos locais.
  2. **Script Especializado**: `./venv/bin/python scripts/fast_search.py "termo" [caminho] [--ext=.py,.tsx]` — busca com poda automática de pastas pesadas.
  3. **Grep Restrito a Subpacotes**: Aponte diretamente para o módulo relevante: `grep -rn "termo" ai/ tests/ scripts/ deck_manager/ stats/ ui/`.
  4. **Grep com Exclusão Obrigatória**: Se for indispensável usar `grep -r`, utilize sempre:
     `grep -rn --exclude-dir={node_modules,venv,Talishar,Talishar-FE,logs,data,build,dist,.git,__pycache__} "termo" .`
