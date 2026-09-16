"""
stats/deck_names.py
===================
Normalização de nomes de decks, resolução canônica e estimativa de vida inicial.
"""

import glob
import json
import os
from typing import Dict, Tuple

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DECKS_DIR = os.path.join(BASE_DIR, "decks")

CANONICAL_DECK_NAMES: Dict[str, str] = {
    # Dash IO
    "dash_io": "Dash IO",
    "dash io": "Dash IO",
    "dash_i/o": "Dash IO",
    "dash i/o": "Dash IO",
    # Oscilio GIAF
    "oscilio_giaf": "Oscilio GIAF",
    "oscilio giaf": "Oscilio GIAF",
    "oscilio_constella_intelligence": "Oscilio GIAF",
    "oscilio constella intelligence": "Oscilio GIAF",
    # Gravy Bones
    "gravy_bones": "Gravy Bones",
    "gravy bones": "Gravy Bones",
    "gravy_bones_shipwrecked_looter": "Gravy Bones",
    "gravy bones shipwrecked looter": "Gravy Bones",
    # Marlinn
    "marlynn": "Marlinn",
    "marlinn": "Marlinn",
    "marlynn_treasure_hunter": "Marlinn",
    "marlynn treasure hunter": "Marlinn",
    "marlinn_treasure_hunter": "Marlinn",
    "marlinn treasure hunter": "Marlinn",
    # Teklovossen
    "teklovossen": "Teklovossen",
    "teklovossen_esteemed_magnate": "Teklovossen",
    "teklovossen esteemed magnate": "Teklovossen",
    "professor_teklovossen": "Teklovossen",
    "professor teklovossen": "Teklovossen",
    # Betsy
    "betsy": "Betsy",
    "betsy_skin_in_the_game": "Betsy",
    "betsy skin in the game": "Betsy",
    # Kassai
    "kassai": "Kassai",
    "kassai_of_the_golden_sand": "Kassai",
    "kassai of the golden sand": "Kassai",
    # Cindra
    "cindra": "Cindra",
    "cindra_dracai_of_retribution": "Cindra",
    "cindra dracai of retribution": "Cindra",
    # Jarl
    "jarl": "Jarl",
    "jarl_vetreidi": "Jarl",
    "jarl vetreidi": "Jarl",
    "jarl_vetreiði": "Jarl",
    "jarl vetreiði": "Jarl",
    # Vynsett
    "vynsett": "Vynsett",
    "vynnset": "Vynsett",
    "vynnset_iron_maiden": "Vynsett",
    "vynnset iron maiden": "Vynsett",
    # Mario (Arakni)
    "mario": "Mario",
    "arakni_marionette": "Mario",
    "arakni marionette": "Mario",
    # Hala
    "hala": "Hala",
    "hala_bladesaint_of_the_vow": "Hala",
    "hala bladesaint of the vow": "Hala",
}


def canonicalize_deck_name(name: str) -> str:
    """Normaliza o nome do deck para um nome canônico legível e consistente."""
    if not name or name.strip() == "👤 Humano (Você)":
        return name
    clean = str(name).strip()
    low = clean.lower().replace("-", "_").replace(",", "")
    while "  " in low:
        low = low.replace("  ", " ")
    if low in CANONICAL_DECK_NAMES:
        return CANONICAL_DECK_NAMES[low]
    # Fallback dinâmico: verificar decks salvos no workspace
    try:
        from deck_parser import list_saved_decks

        for d in list_saved_decks():
            d_name = d.get("name", "")
            d_slug = d.get("slug", "").lower()
            d_hero = d.get("hero", "").lower().replace("-", "_").replace(",", "")
            if low in (d_slug, d_name.lower(), d_hero):
                return d_name
    except Exception:
        pass
    if "_" in clean:
        clean = clean.replace("_", " ")
    return clean.title()


def consolidate_deck_stats(deck_stats: dict) -> Tuple[dict, bool]:
    """Compila e unifica entradas duplicadas (ex: Marlinn e marlinn, dash_io e Dash IO)."""
    consolidated = {}
    had_duplicates = False

    for d_name, d_info in deck_stats.items():
        c_name = canonicalize_deck_name(d_name)
        if c_name != d_name:
            had_duplicates = True

        matches = d_info.get("matches", 0)
        wins = d_info.get("wins", 0)
        losses = d_info.get("losses", matches - wins)
        elo = d_info.get("elo", 1200)

        if c_name not in consolidated:
            consolidated[c_name] = {
                "matches": matches,
                "wins": wins,
                "losses": losses,
                "elo": elo,
            }
        else:
            had_duplicates = True
            prev = consolidated[c_name]
            tot_matches = prev["matches"] + matches
            tot_wins = prev["wins"] + wins
            tot_losses = prev["losses"] + losses

            # ELO ponderado pelo número de partidas disputadas
            if tot_matches > 0:
                weighted_elo = round(
                    (prev["elo"] * prev["matches"] + elo * matches) / tot_matches
                )
            else:
                weighted_elo = prev["elo"]

            consolidated[c_name] = {
                "matches": tot_matches,
                "wins": tot_wins,
                "losses": tot_losses,
                "elo": weighted_elo,
            }

    return consolidated, had_duplicates


def get_expected_starting_health(deck_name: str) -> int:
    """Retorna o total de vida inicial esperado para o deck (40 para CC, 20 para Blitz)."""
    clean = canonicalize_deck_name(deck_name).lower()
    for d_path in glob.glob(os.path.join(DECKS_DIR, "*.json")):
        try:
            with open(d_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            name = (d.get("name") or "").lower()
            hero = (d.get("hero") or "").lower()
            if clean in name or clean in hero or name in clean or hero in clean:
                fmt = str(d.get("format", "")).lower()
                if "blitz" in fmt:
                    return 20
                if "cc" in fmt or "classic" in fmt:
                    return 40
        except Exception:
            pass
    return 40
