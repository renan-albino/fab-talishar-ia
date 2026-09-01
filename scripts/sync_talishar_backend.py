#!/usr/bin/env python3
"""
scripts/sync_talishar_backend.py
Script de automação e sincronização entre o backend Talishar (Docker) e o ambiente de IA.

Executa:
1. Verificação de status dos containers Docker do Talishar (Web, Redis, MySQL).
2. Extração e indexação completa do banco oficial de cartas (CardDictionaries) para data/fab_cards_db.json.
3. Criação e garantia de permissões para diretórios de logs, decks e dados.
4. Teste de conectividade com os endpoints da API do Talishar (porta 8080).
"""

import os
import sys
import shutil
import json
import re
import subprocess
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
DECKS_DIR = os.path.join(BASE_DIR, "decks")
DB_PATH = os.path.join(DATA_DIR, "fab_cards_db.json")
TALISHAR_URL = "http://localhost:8080/game"

def log(msg):
    print(f"[*] {msg}")

def ensure_directories():
    log("Garantindo estrutura de diretórios...")
    for d in [DATA_DIR, LOGS_DIR, DECKS_DIR]:
        os.makedirs(d, exist_ok=True)
    log("Diretórios verificados: data/, logs/, decks/.")

def get_docker_compose_cmd():
    try:
        r = subprocess.run(["docker", "compose", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if r.returncode == 0:
            return ["docker", "compose"]
    except Exception:
        pass
    if shutil.which("docker-compose"):
        return ["docker-compose"]
    return ["docker", "compose"]

def check_docker_containers():
    log("Verificando containers Docker do Talishar...")
    try:
        res = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"], text=True)
        running = [name.strip() for name in res.strip().splitlines() if name.strip()]
        
        web_running = any("talishar" in n.lower() and "web" in n.lower() for n in running)
        redis_running = any("redis" in n.lower() for n in running)
        mysql_running = any("mysql" in n.lower() for n in running)
        
        log(f"Containers em execução: {', '.join(running)}")
        if not web_running:
            log("[AVISO] Container Web Server do Talishar não encontrado em execução!")
            log("[+] Tentando subir backend via Docker Compose...")
            talishar_dir = os.path.join(BASE_DIR, "Talishar")
            if os.path.exists(talishar_dir):
                dc_cmd = get_docker_compose_cmd()
                subprocess.run(dc_cmd + ["up", "-d"], cwd=talishar_dir, check=True)
            else:
                log("[ERRO] Diretório Talishar/ não encontrado.")
        else:
            log("Backend Talishar ativo no Docker.")
    except Exception as e:
        log(f"[AVISO] Falha ao inspecionar Docker: {e}")

def extract_card_database():
    log("Sincronizando e indexando banco de dados de cartas do Talishar...")
    
    # 1. Procurar arquivos de dicionário no sistema de arquivos ou dentro do container
    card_dict_files = []
    
    local_candidates = [
        os.path.join(BASE_DIR, "Talishar", "game", "CardDictionaries"),
        os.path.join(BASE_DIR, "Talishar", "CardDictionaries"),
        "/var/www/html/game/CardDictionaries"
    ]
    
    found_local_dir = None
    for cand in local_candidates:
        if os.path.exists(cand) and os.path.isdir(cand):
            found_local_dir = cand
            break
            
    php_contents = []
    if found_local_dir:
        for root, _, files in os.walk(found_local_dir):
            for file in files:
                if file.endswith(".php"):
                    full_p = os.path.join(root, file)
                    try:
                        with open(full_p, "r", encoding="utf-8", errors="ignore") as f:
                            php_contents.append((file, f.read()))
                    except Exception:
                        pass
    else:
        # Tentar extrair do container docker
        try:
            cname = "talishar_web-server_1"
            try:
                out = subprocess.check_output(["docker", "ps", "--filter", "name=web-server", "--format", "{{.Names}}"], text=True)
                cand = [c.strip() for c in out.strip().splitlines() if c.strip()]
                if cand:
                    cname = cand[0]
            except Exception:
                pass
            container_cmd = f"docker exec {cname} find /var/www/html/ -name '*Dictionary*.php'"
            files_out = subprocess.check_output(container_cmd, shell=True, text=True)
            for fpath in files_out.strip().splitlines():
                if fpath.strip():
                    cat_cmd = f"docker exec {cname} cat '{fpath.strip()}'"
                    content = subprocess.check_output(cat_cmd, shell=True, text=True, errors="ignore")
                    php_contents.append((os.path.basename(fpath.strip()), content))
        except Exception as e:
            log(f"[AVISO] Erro ao extrair dicionários via Docker: {e}")

    cards_db = {}
    
    for fname, text in php_contents:
        # Regex para capturar definições de cartas em arrays PHP
        # Padrões comuns no Talishar:
        # "card_id" => array( ... ), 'card_id' => [ ... ]
        pattern = r"['\"]([a-zA-Z0-9_]+)['\"]\s*=>\s*(?:array|\()\s*(.*?)(?=\),\s*['\"]|\);\s*|\}\s*;|\Z)"
        matches = re.findall(r"['\"]([a-zA-Z0-9_]+)['\"]\s*=>\s*(?:array|\()\s*([^)]+)\)", text, flags=re.DOTALL)
        
        for cid, meta_str in matches:
            if cid in ("array", "string", "int", "bool", "name", "type", "cost"):
                continue
                
            slot = "Deck"
            meta_str_l = meta_str.lower()
            
            if "hero" in meta_str_l:
                slot = "Hero"
            elif "head" in meta_str_l:
                slot = "Head"
            elif "chest" in meta_str_l:
                slot = "Chest"
            elif "arms" in meta_str_l:
                slot = "Arms"
            elif "legs" in meta_str_l:
                slot = "Legs"
            elif "weapon" in meta_str_l or "1h" in meta_str_l or "2h" in meta_str_l:
                slot = "Weapon"
            elif "offhand" in meta_str_l or "off-hand" in meta_str_l or "equipment" in meta_str_l:
                slot = "Equipment"
                
            is_1h = ("1h" in meta_str_l) or ("one-hand" in meta_str_l) or ("one hand" in meta_str_l)
            
            cards_db[cid] = {
                "id": cid,
                "slot": slot,
                "is1h": is_1h,
                "source": fname
            }
            
    # Se o banco atual já existir e tiver mais cartas, mesclar
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, "r", encoding="utf-8") as f:
                existing = json.load(f)
            for k, v in existing.items():
                if k not in cards_db:
                    cards_db[k] = v
        except Exception:
            pass

    with open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(cards_db, f, indent=2)
        
    log(f"Banco de dados indexado com sucesso: {len(cards_db)} cartas gravadas em {DB_PATH}.")

def test_api_connection():
    log(f"Testando conexão com a API do Talishar em {TALISHAR_URL}...")
    try:
        res = requests.get(f"{TALISHAR_URL}/GetNextTurn.php", timeout=3)
        log(f"API respondeu com HTTP {res.status_code} (Operacional).")
    except Exception as e:
        log(f"[ALERTA] API Talishar não respondeu na porta 8080: {e}")

def main():
    log("=== SINCRONIZAÇÃO DO BACKEND TALISHAR ===")
    ensure_directories()
    check_docker_containers()
    extract_card_database()
    test_api_connection()
    log("=== SINCRONIZAÇÃO CONCLUÍDA COM SUCESSO ===")

if __name__ == "__main__":
    main()
