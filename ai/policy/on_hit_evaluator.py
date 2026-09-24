def estimate_on_hit_value(attack_name: str, state: dict) -> float:
    """
    Estimates the value of an attack's on-hit effect.
    """
    on_hit_values = {
        "Command and Conquer": 5.0,
        "Snatch": 4.0,
        "Leave No Witnesses": 4.0,
        "Erase Face": 4.0,
        "Spinal Crush": 6.0
    }
    for name, val in on_hit_values.items():
        if name.lower() == attack_name.lower():
            return val
    return 0.0
