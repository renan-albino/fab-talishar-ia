"""
ai/hero_strategies/equipment_evaluator.py
=========================================
Módulo de avaliação heurística e orientada a dados de habilidades de equipamentos
(Head, Chest, Arms, Legs, Off-Hand) para Flesh and Blood.
"""

from typing import Optional, Dict, Any, List
from .knapsack_solver import _get_cards_db


def evaluate_equipment_ability(
    hero_name: Any = "generic",
    state: Optional[Dict[str, Any]] = None,
    eq_item: Any = None,
    floating_resources: int = 0,
    total_resources: int = 0,
    hand_attacks: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> float:
    """
    Pontuação tática para ativar habilidades de equipamento (Head, Chest, Arms, Legs, Off-Hand).
    Abordagem 100% orientada a dados e semântica de regras, sem hardcoding de nomes de cartas,
    calibrada dinamicamente pelo motor de aprendizado persistente EquipmentLearningEngine.
    Suporta chamadas polimórficas (hero_name, state, eq_item), (state, eq_info) ou legadas (eq_name, floating_res, total_res).
    """
    actual_hero = "generic"
    actual_state: Dict[str, Any] = {}
    actual_eq_info: Dict[str, Any] = {}

    if isinstance(hero_name, dict):
        # Chamada direta: evaluate_equipment_ability(state, eq_item, ...)
        actual_state = hero_name
        actual_hero = kwargs.get("hero_name", "generic")
        if isinstance(state, dict):
            actual_eq_info = state
        elif isinstance(state, str):
            actual_eq_info = {"cardNumber": state}
        else:
            actual_eq_info = kwargs.get("eq_info", {})
        if hand_attacks is None and isinstance(eq_item, list):
            hand_attacks = eq_item

    elif isinstance(hero_name, str) and isinstance(state, dict):
        # Chamada padrão: evaluate_equipment_ability(hero_name, state, eq_item, ...)
        actual_hero = hero_name
        actual_state = state
        if isinstance(eq_item, dict):
            actual_eq_info = eq_item
        elif isinstance(eq_item, str):
            actual_eq_info = {"cardNumber": eq_item}
        else:
            actual_eq_info = kwargs.get("eq_info", {})

    elif isinstance(hero_name, str) and isinstance(state, str):
        # Chamada com hero_name e eq_name: (hero_name, "card_name", ...)
        actual_hero = hero_name
        actual_state = kwargs.get("state", {})
        actual_eq_info = {"cardNumber": state}
        if isinstance(eq_item, (int, float)):
            floating_resources = int(eq_item)
        if isinstance(hand_attacks, (int, float)):
            total_resources = int(hand_attacks)
            hand_attacks = None

    elif isinstance(hero_name, str) and (state is None or isinstance(state, (int, float))):
        # Chamada legada: (eq_name, floating_res, total_res)
        actual_hero = kwargs.get("hero_name", "generic")
        actual_state = kwargs.get("state", {})
        actual_eq_info = {"cardNumber": hero_name}
        if isinstance(state, (int, float)):
            floating_resources = int(state)
        if isinstance(eq_item, (int, float)):
            total_resources = int(eq_item)
    else:
        actual_hero = str(getattr(hero_name, "hero_name", hero_name) or "generic")
        actual_state = state if isinstance(state, dict) else {}
        actual_eq_info = eq_item if isinstance(eq_item, dict) else kwargs.get("eq_info", {})

    eq_name = str(actual_eq_info.get("cardNumber") or actual_eq_info.get("name", "")).lower().strip()
    if not eq_name:
        return 0.0

    from ai.equipment_learning import load_equipment_metadata, get_equipment_learning_engine
    eq_meta = load_equipment_metadata().get(eq_name, {})
    cards_db = _get_cards_db()
    hand = actual_state.get("playerHand", [])
    arsenal = actual_state.get("playerArsenal", [])

    # Se for equipamento puramente defensivo ou de prevenção (ex: ward, barrier, prevent):
    # Na fase principal, sem dano ativo na cadeia, nunca deve pontuar para ativação no vazio!
    is_defensive_instant = bool(
        "ward" in eq_name
        or "barrier" in eq_name
        or "prevent" in eq_name
        or eq_meta.get("is_defense_reaction")
    )
    if is_defensive_instant:
        active_chain = actual_state.get("activeChainLink") or {}
        opp_pow = int(active_chain.get("totalPower", actual_state.get("combatChainPower", 0)))
        if opp_pow <= 0 and int(actual_state.get("arcaneDamage", 0)) <= 0:
            return 0.0

    # 1. Validação de requisitos de contadores (ex: contadores mínimos exigidos)
    req_counters = int(eq_meta.get("req_counters", 0))
    if req_counters > 0:
        current_counters = int(actual_eq_info.get("counters", 0) or 0)
        if current_counters < req_counters:
            return 0.0

    # 2. Avaliação semântica da habilidade
    power_buff = int(eq_meta.get("power_buff", 0))
    min_atk_cost = int(eq_meta.get("min_attack_cost", 0))
    cost_discount = int(eq_meta.get("cost_discount", 0))
    grants_res = int(eq_meta.get("grants_resource", 0))
    creates_token = str(eq_meta.get("creates_token", ""))
    grants_ga = bool(eq_meta.get("grants_go_again", False))
    has_ga = bool(eq_meta.get("has_go_again", False))
    ab_cost = int(eq_meta.get("ability_cost", 0))

    base_score = 0.0

    # Caso A: Buff de poder para ataques
    if power_buff > 0:
        if hand_attacks:
            heavy = [a for a in hand_attacks if int(a.get("cost", 0)) >= min_atk_cost]
            if heavy:
                base_score = max(float(a.get("score", 0.0)) for a in heavy) + float(power_buff) * 3.0
            else:
                return 0.0
        else:
            heavy_attacks = [
                c for c in list(hand) + list(arsenal)
                if int(c.get("cost", cards_db.get(str(c.get("cardNumber", c.get("name", ""))).lower(), {}).get("cost", 0))) >= min_atk_cost
            ]
            if not heavy_attacks:
                return 0.0
            base_score = 20.0 + float(power_buff) * 2.5

    # Caso B: Desconto de custo de recurso
    elif cost_discount > 0:
        target_min_cost = 2 if cost_discount >= 2 else 1
        if hand_attacks:
            cost_targets = [a for a in hand_attacks if int(a.get("cost", 0)) >= target_min_cost]
            if cost_targets:
                base_score = max(float(a.get("score", 0.0)) for a in cost_targets) + float(cost_discount) * 2.5
            else:
                return 0.0
        else:
            cost_targets = [
                c for c in list(hand) + list(arsenal)
                if int(c.get("cost", cards_db.get(str(c.get("cardNumber", c.get("name", ""))).lower(), {}).get("cost", 0))) >= target_min_cost
            ]
            if not cost_targets:
                return 0.0
            base_score = 20.0 + float(cost_discount) * 2.0

    # Caso C: Geração de recursos
    elif grants_res > 0:
        base_score = 12.0 + float(grants_res) * 2.0

    # Caso D: Criação de Tokens (ex: Seismic Surge)
    elif creates_token:
        base_score = 14.0

    # Caso E: Concessão de Go Again
    elif grants_ga:
        base_score = 16.0

    # Caso F: Outras habilidades ativas
    else:
        ab_type = str(eq_meta.get("ability_type", "")).upper()
        if ab_type in ("A", "AR", "I", "AA"):
            base_score = 10.0
        else:
            base_score = 0.0

    if base_score <= 0.0:
        return 0.0

    if has_ga:
        base_score += 4.0
    if ab_cost > 0:
        base_score -= float(ab_cost) * 1.5

    # 3. Calibração empírica aprendida por herói / arquétipo
    learned_mult = get_equipment_learning_engine().get_equipment_multiplier(actual_hero, eq_name)
    return max(0.0, base_score * learned_mult)
