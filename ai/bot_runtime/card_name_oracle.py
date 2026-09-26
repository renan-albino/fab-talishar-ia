"""
ai/bot_runtime/card_name_oracle.py
==================================
Oráculo dinâmico e inteligente para predição e escolha de nomes de cartas
em prompts de INPUTCARDNAME (ex: Amnesia, cartas de disrupção, etc.).

Opera em 3 níveis hierárquicos:
  1. Memória da Partida Atual: cartas reveladas em opponentDiscard, opponentPitch,
     opponentBanish e activeChainLink, ranqueadas por score de impacto
     (poder + 3 se go again + 4 se on-hit).
  2. Histórico no Banco SQLite (data/talishar_stats.db): cartas mais perigosas
     enfrentadas anteriormente contra o herói do oponente.
  3. Avaliador Algorítmico do Cards DB (data/fab_cards_db.json): análise dinâmica
     do pool da classe do oponente pontuando ataques/ações de maior impacto.
  4. Fallback Seguro: "Command and Conquer" ou "Sink Below".
"""

import os
import json
import time
import re
import sqlite3
from typing import Dict, Any, List, Optional, Tuple

from ai.logger import get_logger
from ai.policy.constants import ON_HIT_THREAT_VALUES

logger = get_logger("oracle")

_CARD_DB_CACHE: Optional[Dict[str, Any]] = None
_SEMANTICS_DB_CACHE: Optional[Dict[str, Any]] = None
_NAME_TO_META_CACHE: Optional[Dict[str, Dict[str, Any]]] = None

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CARDS_DB_PATH = os.path.join(BASE_DIR, "data", "fab_cards_db.json")
SEMANTICS_DB_PATH = os.path.join(BASE_DIR, "data", "fab_card_semantics.json")
STATS_DB_PATH = os.path.join(BASE_DIR, "data", "talishar_stats.db")


def _get_card_db() -> Dict[str, Any]:
    """Carrega o banco de cartas oficial com cache."""
    global _CARD_DB_CACHE
    if _CARD_DB_CACHE is None:
        for p in [CARDS_DB_PATH, "data/fab_cards_db.json"]:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        _CARD_DB_CACHE = json.load(f)
                        break
                except Exception as e:
                    logger.warning(f"Erro ao carregar card_db: {e}")
        if _CARD_DB_CACHE is None:
            _CARD_DB_CACHE = {}
    return _CARD_DB_CACHE


def _get_semantics_db() -> Dict[str, Any]:
    """Carrega o banco semântico de mecânicas com cache."""
    global _SEMANTICS_DB_CACHE
    if _SEMANTICS_DB_CACHE is None:
        for p in [SEMANTICS_DB_PATH, "data/fab_card_semantics.json"]:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        _SEMANTICS_DB_CACHE = json.load(f)
                        break
                except Exception as e:
                    logger.warning(f"Erro ao carregar semantics_db: {e}")
        if _SEMANTICS_DB_CACHE is None:
            _SEMANTICS_DB_CACHE = {}
    return _SEMANTICS_DB_CACHE


def _get_name_index() -> Dict[str, Dict[str, Any]]:
    """Gera índice de busca rápida nome_normalizado -> metadados."""
    global _NAME_TO_META_CACHE
    if _NAME_TO_META_CACHE is None:
        db = _get_card_db()
        idx: Dict[str, Dict[str, Any]] = {}
        for k, v in db.items():
            if not isinstance(v, dict):
                continue
            name = v.get("name")
            if name:
                idx[name.lower().strip()] = v
            idx[k.lower().strip()] = v
        _NAME_TO_META_CACHE = idx
    return _NAME_TO_META_CACHE


def _clean_card_name(raw_name: str) -> str:
    """Formata um nome bruto ou slug de carta para exibição adequada."""
    if not raw_name:
        return ""
    # Se o nome já tiver espaços e maiúsculas, preserva
    s = raw_name.strip()
    # Remove sufixos de tom (_red, _yellow, _blue) se estiver em formato slug
    s_no_pitch = re.sub(r'_(red|yellow|blue)$', '', s, flags=re.IGNORECASE)
    # Se continha underscores, converte em Title Case
    if "_" in s_no_pitch:
        return s_no_pitch.replace("_", " ").title()
    return s


def _resolve_card_details(card_item: Any) -> Tuple[str, dict, dict]:
    """
    Resolve nome formatado, metadados do card_db e metadados de semântica.
    Suporta strings (slugs ou nomes) e dicts do estado do Talishar.
    """
    card_db = _get_card_db()
    sem_db = _get_semantics_db()
    name_idx = _get_name_index()

    meta = {}
    sem = {}
    raw_id = ""
    display_name = ""

    if isinstance(card_item, dict):
        raw_id = str(card_item.get("cardNumber") or card_item.get("id") or card_item.get("name") or "")
        display_name = card_item.get("name") or ""
    elif isinstance(card_item, str):
        raw_id = card_item
    else:
        return "", {}, {}

    raw_clean = raw_id.strip()
    low = raw_clean.lower()
    low_slug = low.replace(" ", "_")

    # 1. Busca exata no card_db
    if low in card_db:
        meta = card_db[low]
    elif low_slug in card_db:
        meta = card_db[low_slug]
    elif low in name_idx:
        meta = name_idx[low]
    else:
        # Tenta variantes com pitch (_red, _yellow, _blue)
        for suffix in ["_red", "_yellow", "_blue"]:
            candidate = f"{low_slug}{suffix}"
            if candidate in card_db:
                meta = card_db[candidate]
                break

    # 2. Busca no semantics_db
    meta_id = meta.get("id", low_slug)
    if meta_id in sem_db:
        sem = sem_db[meta_id]
    elif low_slug in sem_db:
        sem = sem_db[low_slug]
    elif f"{low_slug}_red" in sem_db:
        sem = sem_db[f"{low_slug}_red"]

    final_name = display_name or meta.get("name") or _clean_card_name(raw_clean)
    return final_name, meta, sem


def compute_card_impact(meta: dict, sem: dict, card_dict: Optional[dict] = None) -> float:
    """
    Calcula o score de impacto de uma carta:
    score = poder + 3 (se tiver go again) + 4 (se tiver on-hit)
    Retorna -1.0 se a carta não for ação/ataque de deck (ex: equipamento/arma).
    """
    slot = str(meta.get("slot", "")).lower()
    if slot in ("head", "chest", "arms", "legs", "weapon", "hero"):
        return -1.0

    c_type = str(meta.get("type", "")).upper()
    if c_type in ("E", "W", "H", "T"):
        return -1.0

    card_dict = card_dict or {}

    # Determinar poder base
    power = 0
    if "totalPower" in card_dict and card_dict["totalPower"] is not None:
        power = int(card_dict["totalPower"])
    elif "power" in card_dict and card_dict["power"] is not None:
        power = int(card_dict["power"])
    elif meta.get("power") is not None:
        try:
            power = int(meta["power"])
        except (ValueError, TypeError):
            power = 0

    # Go again (+3)
    has_go_again = False
    if card_dict.get("hasGoAgain") is True or card_dict.get("has_go_again") is True:
        has_go_again = True
    elif meta.get("has_go_again") is True:
        has_go_again = True
    elif "go_again" in sem.get("keywords", []):
        has_go_again = True

    # On-hit (+4)
    has_on_hit = False
    if card_dict.get("has_on_hit") is True or card_dict.get("onHit") is True:
        has_on_hit = True
    elif sem.get("on_hit_disruption") is not None:
        has_on_hit = True
    elif float(sem.get("on_hit_severity", 0) or 0) > 0:
        has_on_hit = True
    elif int(sem.get("extra_on_hit_damage", 0) or 0) > 0:
        has_on_hit = True
    elif any(k in sem.get("keywords", []) for k in ("crush", "on_hit", "on-hit", "hit")):
        has_on_hit = True
    else:
        # Checar ameaça conhecida na lista tática
        name_or_id = (meta.get("name") or card_dict.get("name") or "").lower().replace(" ", "_")
        if any(threat_k in name_or_id for threat_k in ON_HIT_THREAT_VALUES):
            has_on_hit = True

    # Verificar se é ação / ataque (ou se possui poder > 0 ou go again)
    is_action_or_attack = c_type in ("AA", "A", "AR") or power > 0 or has_go_again or has_on_hit

    if not is_action_or_attack and slot != "deck":
        return -1.0

    score = float(power) + (3.0 if has_go_again else 0.0) + (4.0 if has_on_hit else 0.0)
    return score


def _record_opponent_card_to_db(hero: str, card_name: str, impact_score: float) -> None:
    """Registra carta observada no banco SQLite para aprendizado contínuo."""
    if not hero or not card_name:
        return
    try:
        os.makedirs(os.path.dirname(STATS_DB_PATH), exist_ok=True)
        conn = sqlite3.connect(STATS_DB_PATH, timeout=2.0)
        with conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS opponent_card_history (
                    hero TEXT,
                    card_name TEXT,
                    impact_score REAL DEFAULT 0,
                    count INTEGER DEFAULT 1,
                    last_seen REAL DEFAULT 0.0,
                    PRIMARY KEY (hero, card_name)
                )
            ''')
            now = time.time()
            conn.execute('''
                INSERT INTO opponent_card_history (hero, card_name, impact_score, count, last_seen)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(hero, card_name) DO UPDATE SET
                    count = count + 1,
                    impact_score = MAX(impact_score, excluded.impact_score),
                    last_seen = excluded.last_seen
            ''', (hero.strip(), card_name.strip(), float(impact_score), now))
        conn.close()
    except Exception as e:
        logger.debug(f"Falha ao registrar carta no sqlite: {e}")


def _extract_opponent_hero_and_class(client: Any, state: dict) -> Tuple[str, str]:
    """Extrai nome do herói e classe do oponente a partir do state ou client."""
    card_db = _get_card_db()
    opp_hero = str(
        state.get("opponentHero")
        or state.get("theirCharacter")
        or state.get("initialLoad", {}).get("theirHeroName")
        or ""
    ).strip()

    opp_class = str(
        state.get("opponentClass")
        or state.get("theirClass")
        or ""
    ).strip()

    if (not opp_hero or not opp_class) and client and hasattr(client, "get_opponent_info"):
        try:
            h_info, c_info = client.get_opponent_info()
            if not opp_hero and h_info:
                opp_hero = str(h_info).strip()
            if not opp_class and c_info:
                opp_class = str(c_info).strip()
        except Exception:
            pass

    # Se ainda não temos a classe, descobre pelo herói no card_db
    if opp_hero and not opp_class:
        h_low = opp_hero.lower()
        for k, v in card_db.items():
            if not isinstance(v, dict):
                continue
            if v.get("type") == "C" and (h_low in k.lower() or h_low in str(v.get("name", "")).lower()):
                opp_class = str(v.get("class", ""))
                break

    return opp_hero, opp_class


def get_learned_card_name_target(client: Any, state: dict) -> str:
    """
    Retorna o nome da carta mais relevante e de maior impacto para nomear
    em INPUTCARDNAME, navegando pelos 3 níveis de inteligência e fallback seguro.
    """
    state = state or {}
    card_db = _get_card_db()
    sem_db = _get_semantics_db()
    opp_hero, opp_class = _extract_opponent_hero_and_class(client, state)

    # =========================================================================
    # NÍVEL 1: Memória da Partida Atual
    # =========================================================================
    revealed_sources = []
    # Cemitério
    discard_cards = state.get("opponentDiscard") or state.get("theirDiscard") or state.get("opponentGraveyard") or []
    if isinstance(discard_cards, list):
        revealed_sources.extend(discard_cards)

    # Pitch
    pitch_cards = state.get("opponentPitch") or state.get("theirPitch") or []
    if isinstance(pitch_cards, list):
        revealed_sources.extend(pitch_cards)

    # Banish
    banish_cards = state.get("opponentBanish") or state.get("theirBanish") or state.get("opponentBanishZone") or []
    if isinstance(banish_cards, list):
        revealed_sources.extend(banish_cards)

    # Cadeia de combate ativa
    active_chain = state.get("activeChainLink")
    if isinstance(active_chain, dict) and (active_chain.get("cardNumber") or active_chain.get("name")):
        revealed_sources.append(active_chain)

    combat_chain = state.get("combatChain") or []
    if isinstance(combat_chain, list):
        revealed_sources.extend(combat_chain)

    scored_revealed: List[Tuple[float, int, str]] = []
    seen_names = set()

    for item in revealed_sources:
        card_dict = item if isinstance(item, dict) else None
        name, meta, sem = _resolve_card_details(item)
        if not name or name in seen_names:
            continue
        seen_names.add(name)

        impact = compute_card_impact(meta, sem, card_dict)
        if impact > 0:
            power = int(meta.get("power", 0) or (card_dict.get("totalPower") if card_dict else 0) or 0)
            scored_revealed.append((impact, power, name))

    if scored_revealed:
        scored_revealed.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best_score, _, best_name = scored_revealed[0]
        logger.info(f"Oráculo Nível 1 (Memória de Jogo): {best_name} (Score {best_score})")

        # Salva as cartas observadas no histórico SQLite para partidas futuras
        if opp_hero:
            for sc, _, c_name in scored_revealed[:3]:
                _record_opponent_card_to_db(opp_hero, c_name, sc)

        return best_name

    # =========================================================================
    # NÍVEL 2: Histórico no Banco SQLite (data/talishar_stats.db)
    # =========================================================================
    if opp_hero and os.path.exists(STATS_DB_PATH):
        try:
            conn = sqlite3.connect(STATS_DB_PATH, timeout=2.0)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT card_name, impact_score FROM opponent_card_history
                WHERE LOWER(hero) = LOWER(?) OR LOWER(?) LIKE ('%' || LOWER(hero) || '%')
                   OR LOWER(hero) LIKE ('%' || LOWER(?) || '%')
                ORDER BY impact_score DESC, count DESC LIMIT 1
            ''', (opp_hero, opp_hero, opp_hero))
            row = cursor.fetchone()
            conn.close()
            if row and row[0]:
                hist_card = _clean_card_name(row[0])
                logger.info(f"Oráculo Nível 2 (Histórico SQLite): {hist_card} (Score {row[1]}) contra {opp_hero}")
                return hist_card
        except Exception as e:
            logger.debug(f"Erro ao consultar Nível 2 no SQLite: {e}")

    # =========================================================================
    # NÍVEL 3: Avaliador Algorítmico do Cards DB (data/fab_cards_db.json)
    # =========================================================================
    if card_db and (opp_class or opp_hero):
        cls_target = (opp_class or "").upper()
        pool_scored: List[Tuple[float, int, str]] = []

        for cid, meta in card_db.items():
            if not isinstance(meta, dict):
                continue
            slot = meta.get("slot", "Deck")
            if slot not in ("Deck", "", None):
                continue
            c_type = meta.get("type")
            if c_type not in ("AA", "A", "AR"):
                continue

            card_class = str(meta.get("class", "")).upper()
            is_class_match = bool(cls_target and cls_target in card_class)
            is_hero_match = bool(opp_hero and opp_hero.upper() in card_class)

            if is_class_match or is_hero_match:
                sem = sem_db.get(cid, {})
                score = compute_card_impact(meta, sem)
                if score > 0:
                    power = int(meta.get("power", 0) or 0)
                    pool_scored.append((score, power, meta.get("name", cid)))

        if pool_scored:
            pool_scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
            top_score, _, top_name = pool_scored[0]
            clean_top = _clean_card_name(top_name)
            logger.info(f"Oráculo Nível 3 (Avaliador Algorítmico): {clean_top} (Score {top_score}) para classe {opp_class}")
            return clean_top

    # =========================================================================
    # FALLBACK SEGURO
    # =========================================================================
    logger.info("Oráculo Fallback Seguro: Sink Below")
    return "Sink Below"
