import os
import json
import re
from .slugifier import load_fab_cards_db, BASE_DIR
from .parser import enrich_deck_metadata, extract_hero_from_deck

def save_deck_to_workspace(deck_obj: dict, base_dir: str = None) -> dict:
    """Salva um deck no diretório decks/ e define como deck ativo do Talishar."""
    if base_dir is None:
        base_dir = BASE_DIR
    deck_obj = enrich_deck_metadata(deck_obj)
    deck_name = deck_obj.get("name", "Custom_Deck")
    safe_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", deck_name).strip("_").lower()
    if not safe_slug:
        safe_slug = "custom_deck"
        
    deck_str = json.dumps(deck_obj, indent=2, ensure_ascii=False)
    saved_files = []
    
    # Salva na pasta decks/
    for root in [base_dir, "."]:
        for folder in [os.path.join(root, "Talishar", "decks"), os.path.join(root, "decks")]:
            try:
                os.makedirs(folder, exist_ok=True)
                file_path = os.path.join(folder, f"{safe_slug}.json")
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(deck_str)
                saved_files.append(file_path)
            except Exception:
                pass
        
    # Também define como deck ativo atual
    for root in [base_dir, "."]:
        for main_file in [os.path.join(root, "Talishar", "deck.json"), os.path.join(root, "deck.json")]:
            try:
                with open(main_file, "w", encoding="utf-8") as f:
                    f.write(deck_str)
                saved_files.append(main_file)
            except Exception:
                pass
        
    return {
        "slug": safe_slug,
        "saved_files": saved_files,
        "deck": deck_obj
    }

def update_saved_deck(slug: str, new_name: str, new_format: str, cards_list: list, base_dir: str = None) -> dict:
    """Atualiza as propriedades e cartas de um deck salvo existente."""
    if base_dir is None:
        base_dir = BASE_DIR
    deck_obj = {
        "name": new_name,
        "format": new_format.lower(),
        "cards": cards_list
    }
    new_slug = re.sub(r"[^a-zA-Z0-9_]+", "_", new_name).strip("_").lower()
    if new_slug and new_slug != slug:
        delete_saved_deck(slug, base_dir=base_dir)
    return save_deck_to_workspace(deck_obj, base_dir=base_dir)

def list_saved_decks(base_dir: str = None) -> list:
    """Lista todos os decks salvos disponíveis no diretório decks/."""
    if base_dir is None:
        base_dir = BASE_DIR
    db = load_fab_cards_db()
    decks_dir = os.path.join(base_dir, "decks")
    if not os.path.exists(decks_dir):
        decks_dir = "decks"
    os.makedirs(decks_dir, exist_ok=True)
    deck_files = [f for f in os.listdir(decks_dir) if f.endswith(".json")]
    decks = []
    for df in sorted(deck_files):
        path = os.path.join(decks_dir, df)
        try:
            with open(path, "r", encoding="utf-8") as f:
                d = json.load(f)
                hero = extract_hero_from_deck(d, db)
                decks.append({
                    "filename": df,
                    "slug": df[:-5],
                    "name": d.get("name", df[:-5]),
                    "hero": hero,
                    "class": d.get("class", "GENERIC"),
                    "talents": d.get("talents", []),
                    "format": d.get("format", "blitz"),
                    "total_cards": sum(c.get("total", 1) for c in d.get("cards", [])),
                    "data": d
                })
        except Exception:
            pass
    return decks

def delete_saved_deck(slug: str, base_dir: str = None) -> bool:
    """Remove o arquivo JSON do deck do diretório decks/."""
    if base_dir is None:
        base_dir = BASE_DIR
    for root in [base_dir, "."]:
        deck_path = os.path.join(root, "decks", f"{slug}.json")
        if os.path.exists(deck_path):
            try:
                os.remove(deck_path)
                return True
            except Exception as e:
                print(f"Erro ao remover {deck_path}: {e}")
    return False

def set_active_deck(deck_data: dict, base_dir: str = None):
    """Define o deck ativo no Talishar (deck.json)."""
    if base_dir is None:
        base_dir = BASE_DIR
    deck_str = json.dumps(deck_data, indent=2)
    for root in [base_dir, "."]:
        for main_file in [os.path.join(root, "Talishar", "deck.json"), os.path.join(root, "deck.json")]:
            try:
                with open(main_file, "w", encoding="utf-8") as f:
                    f.write(deck_str)
            except Exception:
                pass

def load_current_deck(base_dir: str = None) -> dict:
    """Carrega o deck atualmente ativo do arquivo deck.json."""
    if base_dir is None:
        base_dir = BASE_DIR
    for root in [base_dir, "."]:
        for main_file in [os.path.join(root, "Talishar", "deck.json"), os.path.join(root, "deck.json")]:
            if os.path.exists(main_file):
                try:
                    with open(main_file, "r", encoding="utf-8") as f:
                        return json.load(f)
                except Exception:
                    pass
    return {}

def normalize_all_saved_decks(base_dir: str = None) -> list[str]:
    """Reavalia e normaliza todos os arquivos JSON em decks/ com metadados canônicos."""
    if base_dir is None:
        base_dir = BASE_DIR
    db = load_fab_cards_db()
    decks_dir = os.path.join(base_dir, "decks")
    if not os.path.exists(decks_dir):
        decks_dir = "decks"
    normalized = []
    if os.path.exists(decks_dir):
        for df in sorted(os.listdir(decks_dir)):
            if df.endswith(".json"):
                fpath = os.path.join(decks_dir, df)
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    enriched = enrich_deck_metadata(d, db=db)
                    with open(fpath, "w", encoding="utf-8") as f:
                        json.dump(enriched, f, indent=2, ensure_ascii=False)
                    normalized.append(df)
                except Exception as e:
                    print(f"Erro ao normalizar deck {df}: {e}")
    return normalized
