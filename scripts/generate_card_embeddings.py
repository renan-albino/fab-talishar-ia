"""
scripts/generate_card_embeddings.py
===================================
Compila a base de conhecimento semântico (data/fab_card_semantics.json e data/fab_cards_db.json)
em uma matriz contínua de Embeddings Tensoriais (data/card_embeddings.pt) de dimensão [N, 48]
e um mapeamento rápido (data/card_to_idx.json) para lookup em O(1) na GPU/CPU.
"""

import os
import sys
import json
import torch
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SEMANTICS_PATH = os.path.join(DATA_DIR, "fab_card_semantics.json")
CARDS_DB_PATH = os.path.join(DATA_DIR, "fab_cards_db.json")
OUTPUT_PT_PATH = os.path.join(DATA_DIR, "card_embeddings.pt")
OUTPUT_IDX_PATH = os.path.join(DATA_DIR, "card_to_idx.json")

CARD_EMBEDDING_DIM = 48


def build_card_vector(card_id: str, sem: dict, db_entry: dict) -> np.ndarray:
    """Extrai exatamente 48 features numéricas/normalizadas de uma carta."""
    vec = np.zeros(CARD_EMBEDDING_DIM, dtype=np.float32)

    # 1. Atributos Numéricos Básicos (Índices 0-7)
    cost = float(db_entry.get("cost", sem.get("cost", 0)) or 0)
    power = float(db_entry.get("power", sem.get("power", 0)) or 0)
    defense = float(db_entry.get("defense", sem.get("defense", 0)) or 0)
    pitch = int(db_entry.get("pitch", sem.get("pitch", 0)) or 0)

    vec[0] = min(cost / 5.0, 2.0)
    vec[1] = min(power / 10.0, 2.0)
    vec[2] = min(defense / 5.0, 2.0)
    vec[3] = 1.0 if pitch == 1 else (1.0 if "_red" in card_id else 0.0)
    vec[4] = 1.0 if pitch == 2 else (1.0 if "_yellow" in card_id else 0.0)
    vec[5] = 1.0 if pitch == 3 else (1.0 if "_blue" in card_id else 0.0)

    extra_dmg = float(sem.get("extra_on_hit_damage", 0) or 0)
    severity = float(sem.get("on_hit_severity", 0.0) or 0.0)
    vec[6] = min(extra_dmg / 4.0, 2.0)
    vec[7] = min(severity / 10.0, 1.0)

    # 2. Economia de Ações e Recursos (Índices 8-11)
    kws = [k.lower() for k in sem.get("keywords", [])]
    has_ga = bool(db_entry.get("has_go_again") or "goagain" in kws or "go_again" in kws)
    vec[8] = 1.0 if has_ga else 0.0
    vec[9] = float(sem.get("generates_ap", 0) or 0)
    vec[10] = min(float(sem.get("generates_resource", 0) or 0) / 3.0, 1.0)
    vec[11] = min(float(sem.get("arcane_threat", 0) or 0) / 2.0, 1.0)

    # 3. Tipagem Canônica (Índices 12-19)
    c_type = str(sem.get("type", db_entry.get("type", "AA"))).upper()
    sub = str(sem.get("subtype", db_entry.get("subtype", ""))).lower()

    vec[12] = 1.0 if c_type == "AA" else 0.0
    vec[13] = 1.0 if c_type == "A" else 0.0
    vec[14] = 1.0 if c_type in ("DR", "DEFENSE REACTION") else 0.0
    vec[15] = 1.0 if c_type in ("AR", "ATTACK REACTION") else 0.0
    vec[16] = 1.0 if c_type == "W" or "dagger" in sub or "weapon" in sub else 0.0
    vec[17] = 1.0 if c_type == "E" or any(s in sub for s in ["head", "chest", "arms", "legs"]) else 0.0
    vec[18] = 1.0 if c_type in ("I", "B", "C", "T") else 0.0
    vec[19] = 1.0 if ("item" in sub or "aura" in sub or "item" in card_id) else 0.0

    # 4. Evasão e Modificadores de Combate (Índices 20-29)
    evasion = sem.get("evasion", {})
    vec[20] = 1.0 if evasion.get("dominate") or "dominate" in kws else 0.0
    vec[21] = 1.0 if evasion.get("overpower") or "overpower" in kws else 0.0
    vec[22] = 1.0 if evasion.get("piercing", 0) > 0 or "piercing" in kws else 0.0
    vec[23] = 1.0 if evasion.get("phantasm") or "phantasm" in kws else 0.0
    vec[24] = 1.0 if evasion.get("stealth") or "stealth" in kws else 0.0
    vec[25] = 1.0 if "crush" in kws else 0.0
    vec[26] = 1.0 if "reprise" in kws else 0.0
    vec[27] = 1.0 if "rupture" in kws else 0.0
    vec[28] = 1.0 if "boost" in kws else 0.0
    vec[29] = 1.0 if "combo" in kws else 0.0

    # 5. Categorias de Disrupção On-Hit (Índices 30-35)
    disruption = sem.get("on_hit_disruption")
    vec[30] = 1.0 if disruption == "destroy_arsenal" else 0.0
    vec[31] = 1.0 if disruption == "discard_hand" else 0.0
    vec[32] = 1.0 if disruption == "turn_lock" else 0.0
    vec[33] = 1.0 if disruption == "affliction" else 0.0
    vec[34] = 1.0 if disruption == "draw_cards" else 0.0
    vec[35] = 1.0 if (disruption is not None and disruption not in [
        "destroy_arsenal", "discard_hand", "turn_lock", "affliction", "draw_cards"
    ]) else 0.0

    # 6. Prevenção e Palavras-chave Defensivas (Índices 36-43)
    prev = sem.get("prevention", {})
    vec[36] = min(float(prev.get("arcane_barrier", 0)) / 3.0, 1.0)
    vec[37] = min(float(prev.get("spellvoid", 0)) / 2.0, 1.0)
    vec[38] = min(float(prev.get("ward", 0)) / 4.0, 1.0)
    vec[39] = min(float(prev.get("quell", 0)) / 2.0, 1.0)
    vec[40] = 1.0 if "battleworn" in kws else 0.0
    vec[41] = 1.0 if "bladebreak" in kws or "blade_break" in kws else 0.0
    vec[42] = 1.0 if "temper" in kws else 0.0
    vec[43] = 1.0 if "ambush" in kws else 0.0

    # 7. Concessões de Arena e Efeitos Especiais (Índices 44-47)
    grants_ev = sem.get("grants_evasion", [])
    vec[44] = 1.0 if "dominate" in grants_ev else 0.0
    vec[45] = 1.0 if sem.get("grants_piercing", 0) > 0 else 0.0
    vec[46] = 1.0 if "crank" in kws else 0.0
    vec[47] = 1.0 if ("blooddebt" in kws or "runegate" in kws or "blood_debt" in kws or "rune_gate" in kws) else 0.0

    return vec


def main():
    print(f"[Embeddings] Carregando semântica de {SEMANTICS_PATH}...")
    with open(SEMANTICS_PATH, "r", encoding="utf-8") as f:
        semantics_db = json.load(f)

    cards_db = {}
    if os.path.exists(CARDS_DB_PATH):
        with open(CARDS_DB_PATH, "r", encoding="utf-8") as f:
            cards_db = json.load(f)

    # Coleta todos os card_ids únicos
    all_card_ids = sorted(list(set(semantics_db.keys()) | set(cards_db.keys())))
    print(f"[Embeddings] Total de cartas únicas identificadas: {len(all_card_ids)}")

    # Index 0 é reservado para UNKNOWN / PAD CARD (vetor nulo)
    card_to_idx = {"<PAD>": 0}
    matrix = [np.zeros(CARD_EMBEDDING_DIM, dtype=np.float32)]

    for idx, card_id in enumerate(all_card_ids, start=1):
        c_clean = card_id.lower().strip()
        sem = semantics_db.get(c_clean, {})
        db_e = cards_db.get(c_clean, {})
        v = build_card_vector(c_clean, sem, db_e)

        card_to_idx[c_clean] = idx
        matrix.append(v)

    tensor_mat = torch.from_numpy(np.stack(matrix, axis=0)).float()

    print(f"[Embeddings] Tensor gerado com formato: {tensor_mat.shape} (Cards x {CARD_EMBEDDING_DIM} features)")
    assert not torch.isnan(tensor_mat).any(), "ERRO: NaNs encontrados no tensor de embeddings!"
    assert not torch.isinf(tensor_mat).any(), "ERRO: Infs encontrados no tensor de embeddings!"

    # Salva os artefatos
    torch.save(tensor_mat, OUTPUT_PT_PATH)
    with open(OUTPUT_IDX_PATH, "w", encoding="utf-8") as f:
        json.dump(card_to_idx, f)

    file_size_mb = os.path.getsize(OUTPUT_PT_PATH) / (1024 * 1024)
    print(f"[Embeddings] ✓ Salvo em {OUTPUT_PT_PATH} ({file_size_mb:.2f} MB)")
    print(f"[Embeddings] ✓ Salvo mapeamento em {OUTPUT_IDX_PATH} ({len(card_to_idx)} entradas)")


if __name__ == "__main__":
    main()
