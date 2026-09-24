def get_risk_profile(v_root: float) -> dict:
    if v_root > 0.5:
        return {"c_puct_scale": 0.7, "block_aggression": 1.3}
    elif v_root > -0.3:
        return {"c_puct_scale": 1.0, "block_aggression": 1.0}
    elif v_root > -0.7:
        return {"c_puct_scale": 1.5, "block_aggression": 0.6}
    else:
        return {"c_puct_scale": 2.5, "block_aggression": 0.3}
