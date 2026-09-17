"""
ai/policy/arsenal_pruner.py
===========================
Módulo de poda e seleção de cartas para o Arsenal (Regra Oficial: Proibido Pitch do Arsenal).
"""

from typing import Optional, Tuple, Any

from .constants import _get_cards_db



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

    # ── 0. Verificação de Ocupação do Arsenal ──
    # Se o arsenal já estiver cheio (geralmente 1 carta, ou 2 se equipado com New Horizon), não podemos arsenalar mais.
    arsenal = state.get("playerArsenal") or state.get("playerArse") or []
    arsenal_capacity = 1
    equip = state.get("playerEquipment", [])
    for eq in equip:
        if isinstance(eq, dict):
            eq_name = str(eq.get("name") or eq.get("cardNumber") or "").lower()
            if "new_horizon" in eq_name:
                arsenal_capacity = 2
                break

    # Cada entrada no array que é um dicionário real de carta conta como ocupado
    occupied_slots = sum(1 for c in arsenal if isinstance(c, dict) and (c.get("name") or c.get("cardNumber")))
    if occupied_slots >= arsenal_capacity:
        return None

    cards_db = _get_cards_db()
    valid_candidates = []

    for c in hand:
        info = engine.extract_card_info(c)
        c_name = info["name"].lower()
        c_id = info["actionDataOverride"] or info["name"]
        db_entry = cards_db.get(c_name, {})

        # 1. Filtro Global Universal: Recursos e Gemas são ESTRITAMENTE PROIBIDOS no Arsenal para qualquer herói!
        from ai.hero_strategies import is_resource_or_gem_card
        if is_resource_or_gem_card(c_name, info, db_entry):
            continue

        # 2. Avaliação polimórfica via HeroStrategy (com desvalorização estrita de cartas de bloco não-DR)
        score = engine.strategy.evaluate_arsenal_card(info, db_entry)

        # Só considera cartas com score positivo (vantajosas de verdade para o próximo turno)
        if score > 0:
            valid_candidates.append((score, info["name"], c_id))

    if not valid_candidates:
        # ── 2. Modo Cavar (Digging Mode) Dinâmico pelo Intelecto (CR 4.3.2, CR 4.4.3f) ───
        # Se nenhuma carta atingiu score > 0 e a mão atingiu o limiar de cavar:
        # Se não colocarmos nada no Arsenal, o jogador compra poucas ou nenhuma carta no End of Turn
        # e continua travado com recursos. Então, deve-se arsenalar 1 carta para cavar!
        hero_intellect = 4
        if hasattr(engine, "strategy") and hasattr(engine.strategy, "get_intellect"):
            try:
                hero_intellect = int(engine.strategy.get_intellect(state))
            except Exception:
                hero_intellect = 4
        elif hasattr(engine, "strategy") and hasattr(engine.strategy, "intellect"):
            hero_intellect = int(getattr(engine.strategy, "intellect", 4))
        else:
            hero_intellect = int(state.get("playerIntellect", state.get("intellect", 4)))

        if "playerIntellect" in state:
            hero_intellect = int(state["playerIntellect"])
        elif "intellect" in state:
            hero_intellect = int(state["intellect"])

        digging_min_cards = max(2, hero_intellect - 1)
        if len(hand) >= digging_min_cards:
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
