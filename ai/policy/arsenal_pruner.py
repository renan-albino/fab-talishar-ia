"""
ai/policy/arsenal_pruner.py
===========================
Módulo de poda e seleção de cartas para o Arsenal (Regra Oficial: Proibido Pitch do Arsenal).
"""

from typing import Optional, Tuple, Any

from .constants import _get_cards_db
from ..hero_strategies import is_resource_or_gem_card


def select_arsenal_card(engine: Any, state: dict) -> Optional[Tuple[str, str]]:
    """
    Seleciona a melhor carta para colocar no Arsenal no fim do turno.

    Regra Oficial de FaB (CR 3.1.5): Cartas no Arsenal NÃO podem ser dadas pitch.
    Portanto, colocar cartas de recurso (R), gemas ou pitch puro no Arsenal tranca o slot.
    Se nenhuma carta for taticamente vantajosa ou todas forem recursos, retorna None (passar).
    """
    hand = state.get("playerHand", [])
    if not hand:
        return None

    cards_db = _get_cards_db()
    valid_candidates = []

    for c in hand:
        info = engine.extract_card_info(c)
        c_name = info["name"].lower()
        c_id = info["actionDataOverride"] or info["name"]
        db_entry = cards_db.get(c_name, {})

        # 1. Filtro Global Universal: Recursos e Gemas são ESTRITAMENTE PROIBIDOS no Arsenal para qualquer herói!
        if is_resource_or_gem_card(c_name, info, db_entry):
            continue

        # 2. Avaliação polimórfica via HeroStrategy (com desvalorização estrita de cartas de bloco não-DR)
        score = engine.strategy.evaluate_arsenal_card(info, db_entry)

        # Só considera cartas com score positivo (vantajosas de verdade para o próximo turno)
        if score > 0:
            valid_candidates.append((score, info["name"], c_id))

    if not valid_candidates:
        # ── 2. Modo Cavar (Digging Mode) para Mão Travada de Recursos (len(hand) >= 3) ───
        # Se nenhuma carta atingiu score > 0 e a mão possui 3 ou mais cartas:
        # Se não colocarmos nada no Arsenal, o jogador compra 0 ou 1 carta no End of Turn
        # e continua travado com recursos. Então, deve-se arsenalar 1 carta para cavar!
        if len(hand) >= 3:
            dig_candidates = []
            for c in hand:
                info = engine.extract_card_info(c)
                c_name = info["name"].lower()
                c_id = info["actionDataOverride"] or info["name"]
                db_entry = cards_db.get(c_name, {})

                # Gemas puras lendárias são a última opção possível (pois não têm ação jogável)
                is_pure_gem = "gem" in (db_entry.get("subtype", "")).lower() or any(
                    k in c_name for k in ["heart_of_fyendal", "eye_of_ophidia", "grandeur_of_valahai", "arknight_shard"]
                )

                # Priorização para Cavar:
                # 1. Prefere cartas de ação que possam ser jogadas no próximo turno para limpar o Arsenal
                # 2. Cartas com poder de ataque maior ganham preferência
                # 3. Cartas de menor custo ganham preferência
                # 4. Gemas puras sofrem forte penalidade (-100.0)
                dig_score = float(info.get("power", 0)) * 3.0
                card_type = (db_entry.get("type", "") or info.get("type", "")).upper()
                if "A" in card_type or info.get("action", 0) > 0:
                    dig_score += 10.0
                if info.get("cost", 0) == 0:
                    dig_score += 2.0
                if is_pure_gem:
                    dig_score -= 100.0

                dig_candidates.append((dig_score, info["name"], c_id))

            if dig_candidates:
                dig_candidates.sort(key=lambda x: x[0], reverse=True)
                best_dig = dig_candidates[0]
                return best_dig[1], best_dig[2]

        # Se tem 1 ou 2 recursos na mão, NÃO ARSENALA:
        # Mantém para pitch no próximo turno e compra cartas até o intelecto normalmente
        return None

    valid_candidates.sort(key=lambda x: x[0], reverse=True)
    best = valid_candidates[0]
    return best[1], best[2]
