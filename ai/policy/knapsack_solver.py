from typing import List, Tuple, Any, Dict
import itertools

def solve_knapsack_defense(
    block_candidates: List[Dict[str, Any]],
    opp_power: int,
    my_hp: int,
    has_dangerous_on_hit: bool,
    has_phantasm: bool,
    has_dominate: bool,
    has_overpower: bool,
    has_piercing: bool,
    turn_plan: Any
) -> List[Tuple[int, str, str, int]]:
    """
    Encontra o subconjunto de menor custo total que neutraliza completamente o dano.
    """
    if not ((has_dangerous_on_hit or has_phantasm) and opp_power > 0 and my_hp > 6):
        return []

    valid_subsets = []
    max_hand_in_subset = int(getattr(turn_plan, "max_block_cards", 2)) if getattr(turn_plan, "can_absorb_damage", False) else (
        2 if my_hp > 12 else 3
    )
    if has_dominate:
        max_hand_in_subset = min(max_hand_in_subset, 1)

    for r in range(1, min(len(block_candidates) + 1, 5)):
        for subset in itertools.combinations(block_candidates, r):
            tot_block = sum(item["block"] for item in subset)
            hand_count = sum(1 for item in subset if item.get("is_hand"))
            action_count = sum(1 for item in subset if item.get("is_action", False))
            has_eq = any(item.get("is_equipment") for item in subset)
            req_power = (opp_power + 1) if (has_piercing and has_eq) else opp_power

            if has_dominate and hand_count > 1:
                continue

            if has_overpower and action_count > 1:
                continue

            if has_piercing and has_eq and all(item.get("is_equipment") for item in subset):
                if (tot_block - 1) <= 0 or tot_block < req_power:
                    continue

            pops_phantasm = any(item.get("is_phantasm_popper") for item in subset)
            if pops_phantasm:
                tot_block = max(tot_block, req_power)

            if tot_block >= req_power:
                if hand_count > max_hand_in_subset and not pops_phantasm:
                    continue
                if getattr(turn_plan, "can_absorb_damage", False) and hand_count >= 2 and not pops_phantasm:
                    avg_hand_block = sum(item["block"] for item in subset if item.get("is_hand")) / hand_count
                    if avg_hand_block <= 2.0:
                        continue
                overblock = tot_block - req_power
                sub_cost = sum(item["cost"] for item in subset) + (overblock * 0.7)
                if pops_phantasm:
                    sub_cost -= 200.0
                valid_subsets.append((sub_cost, subset))

    if valid_subsets:
        valid_subsets.sort(key=lambda x: x[0])
        best_subset = valid_subsets[0][1]
        return [(item["idx"], item["card_id"], item["name"], item["mode"]) for item in best_subset]
    return []
