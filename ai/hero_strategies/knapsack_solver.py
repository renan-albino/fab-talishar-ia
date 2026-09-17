"""
ai/hero_strategies/knapsack_solver.py
=====================================
Solucionador Combinatório Exato da Mochila 0-1 para Flesh and Blood (arXiv:2501.11683).
Calcula partição ótima de cartas entre Ataque, Pitch e Excedente (Surplus),
custo de oportunidade tático V*(H) - V*(H \\ {c}) e potencial de conversão de mão.
"""

import os
import json
import itertools
from typing import Optional, Dict, Any, Set, List, Tuple

def solve_knapsack_turn(
    hero_name: Any = "generic",
    hand: Optional[List[Dict[str, Any]]] = None,
    pitch_pool: Optional[List[Dict[str, Any]]] = None,
    available_resources: int = 0,
    floating_res: int = 0,
    base_ap: int = 1,
    arsenal: Optional[List[Dict[str, Any]]] = None,
    **kwargs
) -> Tuple[float, List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Solucionador Combinatório Exato da Mochila 0-1 para Turno de Flesh and Blood (arXiv:2501.11683).
    Avalia o espaço de partição (Ataque, Pitch, Excedente) sobre mão + arsenal (<= 5 cartas).
    Garante que restrições de custo, pitch e Action Points sejam rigorosamente satisfeitas,
    encontrando a sequência ótima global de dano e valor tático V*(H).

    Retorna:
      (max_value, best_attacks, best_pitches, surplus_cards)
    """
    # Importação local para evitar circular imports
    from ai.hero_strategies import get_hero_strategy
    from ai.policy.constants import _get_cards_db, DANGEROUS_ON_HITS

    # Resolução polimórfica para chamadas funcionais ou orientadas a objetos
    if isinstance(hero_name, (list, tuple)):
        actual_hand = list(hero_name)
        if isinstance(hand, int):
            floating_res = hand
        if isinstance(pitch_pool, int):
            base_ap = pitch_pool
        if isinstance(available_resources, list):
            arsenal = available_resources
        hero_str = "generic"
    else:
        actual_hand = list(hand or [])
        hero_str = str(hero_name)

    strategy = get_hero_strategy(hero_str)

    if available_resources > 0 and floating_res == 0:
        floating_res = available_resources

    all_cards = list(actual_hand)
    if pitch_pool and isinstance(pitch_pool, list):
        for pc in pitch_pool:
            if isinstance(pc, dict) and pc not in all_cards:
                all_cards.append({**pc, "from_pitch_pool": True})

    if arsenal:
        for ac in arsenal:
            if isinstance(ac, dict):
                all_cards.append({**ac, "from_arsenal": True})

    if not all_cards:
        return 0.0, [], [], []

    cards_db = _get_cards_db()
    parsed_cards = []
    for idx, c in enumerate(all_cards):
        c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
        c_meta = cards_db.get(c_name, {})
        c_power = int(c.get("power", c_meta.get("power", 0) or 0))
        c_cost = int(c.get("cost", c_meta.get("cost", 0) or 0))
        c_pitch = int(c.get("pitch", c_meta.get("pitch", 1) or 1))
        has_ga = bool(c.get("has_go_again", c_meta.get("has_go_again", False)))
        is_from_ars = bool(c.get("from_arsenal", False))
        is_from_pp = bool(c.get("from_pitch_pool", False))
        has_on_hit = any(oh in c_name for oh in DANGEROUS_ON_HITS)

        # Regra CR 3.1.5: Cartas no Arsenal não podem dar pitch
        can_pitch = not is_from_ars and c_pitch > 0

        # Valor ofensivo intrínseco (agora ciente da classe do herói)
        atk_val = strategy.evaluate_attack_card(
            card_name=c_name, 
            power=c_power, 
            cost=c_cost, 
            has_go_again=has_ga, 
            pitch=c_pitch
        )

        parsed_cards.append({
            "raw": c,
            "name": c_name,
            "power": c_power,
            "cost": c_cost,
            "pitch": c_pitch,
            "has_ga": has_ga,
            "can_pitch": can_pitch,
            "can_attack": not is_from_pp and (c_power > 0 or has_ga),
            "is_from_arsenal": is_from_ars,
            "value": atk_val,
            "idx": idx
        })

    n = len(parsed_cards)
    max_comb_value = 0.0
    best_attacks: List[Dict[str, Any]] = []
    best_pitches: List[Dict[str, Any]] = []
    best_surplus: List[Dict[str, Any]] = []

    # Para cada subconjunto de cartas atacantes (2^n combinações)
    for r_atk in range(1, n + 1):
        for atk_combo in itertools.combinations(range(n), r_atk):
            atks = [parsed_cards[i] for i in atk_combo]

            # 1. Validação de capacidade de ataque
            if any(not a["can_attack"] for a in atks):
                continue

            # 2. Validação de Action Points (AP):
            # Ataques sem Go Again consomem 1 AP cada.
            # O número de ataques sem Go Again não pode exceder base_ap.
            non_ga_count = sum(1 for a in atks if not a["has_ga"])
            if non_ga_count > base_ap:
                continue

            # Se houver múltiplos ataques, pelo menos (len - 1) devem ter Go Again
            if len(atks) > base_ap and non_ga_count > base_ap:
                continue

            total_cost = sum(a["cost"] for a in atks)
            cost_needed = max(0, total_cost - floating_res)

            # Cartas restantes candidatas a pitch
            rem_indices = [i for i in range(n) if i not in atk_combo]
            pitch_candidates = [parsed_cards[i] for i in rem_indices if parsed_cards[i]["can_pitch"]]

            # Encontrar subconjunto de pitch viável de menor custo (poupando cartas para surplus)
            viable_pitch_found = False
            chosen_pitches: List[Dict[str, Any]] = []

            if cost_needed == 0:
                viable_pitch_found = True
                chosen_pitches = []
            else:
                # Ordena do maior pitch para o menor para minimizar consumo de cartas
                pitch_candidates.sort(key=lambda x: x["pitch"], reverse=True)
                acc_pitch = 0
                cur_p = []
                for pc in pitch_candidates:
                    acc_pitch += pc["pitch"]
                    cur_p.append(pc)
                    if acc_pitch >= cost_needed:
                        viable_pitch_found = True
                        chosen_pitches = cur_p
                        break

            if not viable_pitch_found:
                continue

            comb_val = sum(a["value"] for a in atks)
            # Bônus para cadeias completas e conservação de cartas
            used_indices = set(atk_combo) | {p["idx"] for p in chosen_pitches}
            surplus = [parsed_cards[i] for i in range(n) if i not in used_indices]

            # Desempate favorece: maior valor de dano, mais cartas excedentes poupadas
            score_metric = comb_val + (len(surplus) * 0.1)
            if score_metric > max_comb_value or (max_comb_value == 0.0 and comb_val > 0.0):
                max_comb_value = score_metric
                best_attacks = atks
                best_pitches = chosen_pitches
                best_surplus = surplus

    real_val = sum(a["value"] for a in best_attacks)
    return real_val, best_attacks, best_pitches, best_surplus


def calculate_card_opportunity_cost(
    hero_name: Any = "generic",
    hand: Optional[List[Dict[str, Any]]] = None,
    card_candidate: Optional[Dict[str, Any]] = None,
    floating_res: int = 0,
    available_resources: int = 0,
    **kwargs
) -> float:
    """
    Calcula o Custo de Oportunidade Tático de uma carta (Felt Table & AI Unsheathed).
    Mede a perda de conversão ofensiva V*(H) - V*(H \\ {c}) se a carta for gasta em defesa.
    """
    if isinstance(hero_name, (list, tuple)):
        actual_hand = list(hero_name)
        actual_card = hand if isinstance(hand, dict) else card_candidate
        actual_hero = "generic"
    else:
        actual_hero = str(hero_name or "generic").lower().strip()
        actual_hand = list(hand or [])
        actual_card = card_candidate

    res = floating_res if floating_res > 0 else available_resources

    if not actual_hand or not actual_card:
        return 0.0

    v_full, _, _, _ = solve_knapsack_turn(actual_hero, hand=actual_hand, floating_res=res)
    if v_full <= 0.0:
        return 0.0

    # Remove apenas a primeira ocorrência da carta candidata
    c_target_id = str(actual_card.get("cardNumber") or actual_card.get("name", "")).lower()
    sub_hand = []
    removed = False
    for c in actual_hand:
        c_name = str(c.get("cardNumber") or c.get("name", "")).lower()
        if not removed and c_name == c_target_id:
            removed = True
        else:
            sub_hand.append(c)

    v_sub, _, _, _ = solve_knapsack_turn(actual_hero, hand=sub_hand, floating_res=res)
    return max(0.0, float(v_full - v_sub))


def calculate_hand_conversion_potential(
    hero_name: Any = "generic",
    hand: Optional[List[Dict[str, Any]]] = None,
    floating_res: int = 0,
    available_resources: int = 0,
    **kwargs
) -> Tuple[float, Set[str]]:
    """
    Calcula o potencial ofensivo de dano e sinergia que a mão atual consegue converter
    utilizando o Solucionador Combinatório Exato Knapsack (arXiv:2501.11683).
    Retorna (potencial_total, conjunto_de_cartas_chave_reservadas).
    """
    if isinstance(hero_name, (list, tuple)):
        actual_hand = list(hero_name)
        actual_hero = "generic"
        if isinstance(hand, int):
            floating_res = hand
    else:
        actual_hero = str(hero_name or "generic").lower().strip()
        actual_hand = list(hand or [])

    res = floating_res if floating_res > 0 else available_resources

    if not actual_hand:
        return 0.0, set()

    max_val, attacks, pitches, _ = solve_knapsack_turn(actual_hero, hand=actual_hand, floating_res=res)
    if max_val <= 0.0:
        return 0.0, set()

    reserved = {str(a["name"]) for a in attacks} | {str(p["name"]) for p in pitches}
    return max_val, reserved
