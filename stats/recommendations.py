"""
stats/recommendations.py
========================
Motor de recomendação tática para partidas de treino humano.
Identifica quais heróis e decks o usuário deve jogar para acelerar
o aprendizado da rede neural, priorizando:
1. Gargalos de ELO (decks onde o bot tem pior Win Rate).
2. Alta Incerteza (pouca ou nenhuma amostragem de partidas).
3. Inéditos contra Humanos (decks nunca pilotados por humanos contra o bot).
"""

from typing import Dict, Any, List, Optional


def get_hero_training_recommendations(
    deck_stats: Dict[str, Any],
    saved_decks: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """
    Analisa os dados de telemetria e retorna uma lista priorizada de heróis
    recomendados para o jogador humano escolher.
    """
    deck_stats = deck_stats or {}
    saved_decks = saved_decks or []

    # Mapeia slugs/nomes conhecidos
    all_known_decks = {}
    for d in saved_decks:
        slug = d.get("slug", "")
        name = d.get("name", slug)
        hero = d.get("hero", d.get("data", {}).get("hero", name))
        all_known_decks[name] = {"slug": slug, "hero": hero, "deck_obj": d}

    bottlenecks = []
    under_sampled = []
    untested_human = []

    # 1. Analisa os decks já registrados em deck_stats
    for d_name, info in deck_stats.items():
        if "Humano" in d_name:
            continue

        matches = info.get("matches", 0)
        wins = info.get("wins", 0)
        wr = (wins / matches * 100) if matches > 0 else 50.0
        h_matches = info.get("human_matches", 0)

        hero_name = all_known_decks.get(d_name, {}).get("hero", d_name)
        slug = all_known_decks.get(d_name, {}).get("slug", d_name.lower().replace(" ", "_"))

        # A. Gargalo de ELO (Bot perde muito com este deck)
        if matches >= 3 and wr < 45.0:
            bottlenecks.append({
                "deck": d_name,
                "hero": hero_name,
                "slug": slug,
                "matches": matches,
                "win_rate": round(wr, 1),
                "priority": "alta",
                "badge": "🔴 Gargalo de ELO",
                "reason": f"O bot vence apenas {wr:.1f}% das partidas com este deck. Jogar com ele ensina à rede neural linhas vencedoras de pilotagem para dominar este arquétipo.",
            })

        # B. Baixa amostragem (Menos de 6 partidas)
        if matches < 6:
            under_sampled.append({
                "deck": d_name,
                "hero": hero_name,
                "slug": slug,
                "matches": matches,
                "win_rate": round(wr, 1),
                "priority": "média",
                "badge": "🟡 Pouca Amostragem",
                "reason": f"Apenas {matches} partida(s) registradas. A rede neural possui alta incerteza sobre as linhas de jogada deste herói.",
            })

        # C. Nunca jogou contra humano
        if h_matches == 0:
            untested_human.append({
                "deck": d_name,
                "hero": hero_name,
                "slug": slug,
                "matches": matches,
                "priority": "alta",
                "badge": "👤 Inédito contra Humano",
                "reason": "O bot nunca disputou partidas humanas com este deck. Seu feedback fornecerá novos padrões táticos para a IA.",
            })

    # 2. Decks salvos no workspace que nem sequer entraram no ranking de partidas
    for d in saved_decks:
        d_name = d.get("name", d.get("slug", ""))
        if d_name not in deck_stats and d.get("slug") not in deck_stats:
            hero = d.get("hero", d.get("data", {}).get("hero", d_name))
            slug = d.get("slug", "")
            under_sampled.append({
                "deck": d_name,
                "hero": hero,
                "slug": slug,
                "matches": 0,
                "win_rate": 0.0,
                "priority": "alta",
                "badge": "⚡ Novo / Sem Partidas",
                "reason": "Deck salvo no workspace que ainda não possui partidas registradas no histórico da IA.",
            })

    # Ordenações por relevância
    bottlenecks.sort(key=lambda x: x["win_rate"])
    under_sampled.sort(key=lambda x: x["matches"])

    # Seleção dos Top 4 destaques consolidados
    top_picks = []
    seen = set()

    for item in bottlenecks[:2]:
        if item["deck"] not in seen:
            top_picks.append(item)
            seen.add(item["deck"])

    for item in untested_human[:2]:
        if item["deck"] not in seen:
            top_picks.append(item)
            seen.add(item["deck"])

    for item in under_sampled:
        if len(top_picks) >= 4:
            break
        if item["deck"] not in seen:
            top_picks.append(item)
            seen.add(item["deck"])

    return {
        "bottlenecks": bottlenecks,
        "under_sampled": under_sampled,
        "untested_human": untested_human,
        "top_picks": top_picks,
    }
