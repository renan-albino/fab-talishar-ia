"""
ai/policy/card_evaluator.py
===========================
Módulo de avaliação, normalização de cartas, cálculo de recursos e custos de equipamentos/armas.
"""

from typing import Dict, List, Optional, Tuple, Any

from .constants import (
    _load_cards_db,
    _load_ability_costs,
    DANGEROUS_ON_HITS,
    KNOWN_WEAPON_COSTS,
)


def extract_card_info(card: dict) -> dict:
    """Extrai e normaliza atributos de cartas a partir do snapshot e do banco oficial."""
    card_number = str(card.get("cardNumber", "")).lower()
    pitch = 1
    if "_blue" in card_number:
        pitch = 3
    elif "_yellow" in card_number:
        pitch = 2
    elif "_red" in card_number:
        pitch = 1

    power = int(card.get("power", 0))
    block = int(card.get("defense", card.get("block", 0)))
    cost = 0
    has_go_again = False

    # Consulta banco de dados oficial (fab_cards_db.json)
    db_entry = _load_cards_db().get(card_number)
    if db_entry:
        if "cost" in db_entry:
            cost = max(0, int(db_entry["cost"]))
        if "pitch" in db_entry:
            pitch = int(db_entry["pitch"])
        if power == 0 and "power" in db_entry:
            power = int(db_entry["power"])
        if block == 0 and "defense" in db_entry:
            block = int(db_entry["defense"])
        if "has_go_again" in db_entry:
            has_go_again = bool(db_entry["has_go_again"])

    is_equip_or_weapon = (
        "hammerhead" in card_number
        or (db_entry and db_entry.get("type") in ("W", "E", "C"))
        or str(card.get("slot", "")).lower() in ("weapon", "head", "chest", "arms", "legs", "off-hand", "hero")
    )

    # Inferência de poder por heurística quando ausente no snapshot e banco (somente cartas jogáveis do deck)
    if power == 0 and not is_equip_or_weapon:
        if any(k in card_number for k in ["zipper", "throttle", "zero_to_sixty", "fast_and_furious", "out_pace", "expedite", "snatch"]):
            power = 4 if pitch == 1 else (3 if pitch == 2 else 2)
        elif "pounder" in card_number or "trebuchet" in card_number:
            power = 5
        elif ("harpoon" in card_number and "hammerhead" not in card_number) or "command_and_conquer" in card_number:
            power = 6 if pitch == 1 else 4

    # Exceção especial FaB: Goldfin Harpoon não defende (block = 0) e não gera recurso (pitch = 0)
    if "goldfin" in card_number:
        pitch = 0
        block = 0

    # Inferência de bloqueio padrão (FaB: maioria das cartas de ação e flechas defende 2 ou 3)
    # Regra Oficial FaB: Itens (Item), Aliados (Ally) e certas Auras NÃO possuem defesa (defense: None)
    # e NUNCA podem ser usados para defender. Flechas (Arrows) POSSUEM defesa legítima (exceto Goldfin Harpoon).
    subtype_str = str((db_entry.get("subtype") if db_entry else "") or card.get("subtype", "")).lower()
    is_non_blocking_type = (
        any(nb in subtype_str for nb in ["item", "ally", "landmark"])
        or "goldfin" in card_number
        or any(k in card_number for k in [
            "boom_grenade", "convection_amplifier", "penetration_script",
            "teklo_core", "cerebellum_processor", "null_time_zone",
            "teklo_pounder", "teklo_trebuchet", "plasma_mainline",
            "dissolving_shield", "hyper_driver", "payload", "quiver"
        ])
    )
    if is_non_blocking_type:
        block = 0
    elif block == 0 and not is_equip_or_weapon:
        # Para cartas de ação convencionais (AA ou A) e Flechas onde a defesa não veio catalogada no banco,
        # infere a defesa padrão do Flesh and Blood (3 para azul, 2 para amarelo/vermelho)
        if any(k in card_number for k in ["_red", "_yellow", "_blue"]) and not any(k in card_number for k in ["heart", "accelerator", "providence", "tunic"]):
            block = 3 if pitch == 3 else (2 if pitch == 2 else 2)

    # Custo de recurso heurístico se não estiver catalogado no banco
    if cost == 0 and not db_entry:
        if any(k in card_number for k in ["throttle", "pounder", "trebuchet", "staunch", "spinal", "mangle", "felling"]):
            cost = 2 if "throttle" in card_number else (4 if "mangle" in card_number else 3)
        elif any(k in card_number for k in ["zipper", "fast_and_furious", "out_pace", "expedite", "harpoon", "spark_of_genius", "command_and_conquer"]):
            cost = 1

    # Go Again heurístico se não estiver catalogado no banco
    if not has_go_again and not db_entry:
        if any(k in card_number for k in ["zero_to_sixty", "throttle", "zipper", "expedite", "out_pace", "fast_and_furious", "leg_tap", "snatch", "rising_knee", "fai"]):
            has_go_again = True

    # On-Hit Perigoso
    has_dangerous_on_hit = any(oh in card_number for oh in DANGEROUS_ON_HITS)

    return {
        "name": card_number,
        "raw": card,
        "pitch": pitch,
        "power": power,
        "block": block,
        "cost": cost,
        "has_go_again": has_go_again,
        "has_dangerous_on_hit": has_dangerous_on_hit,
        "action": card.get("action", 0),
        "actionDataOverride": card.get("actionDataOverride", ""),
        "borderColor": card.get("borderColor", 0),
        "subtype": card.get("subtype", ""),
        "text": card.get("text", ""),
        "type": card.get("type", ""),
    }


def calculate_available_resources(state: dict) -> Tuple[int, int]:
    """Calcula recursos flutuantes atuais e potencial total de pitch da mão."""
    current_floating = int(state.get("playerPitchCount", 0))
    if current_floating == 0:
        resources = state.get("playerResources", [0, 0])
        current_floating = int(resources[0]) if isinstance(resources, list) and resources else 0
    hand = state.get("playerHand", [])
    total_potential_pitch = sum(extract_card_info(c)["pitch"] for c in hand)
    return current_floating, current_floating + total_potential_pitch


def get_weapon_cost(
    weapon_name: str,
    eq: Optional[dict] = None,
    state: Optional[dict] = None,
    hero_name: str = "",
    strategy: Any = None,
    equip_dict: Optional[dict] = None,
) -> int:
    """Retorna o custo em recursos para ativar a arma ou habilidade de equipamento."""
    if eq is None and equip_dict is not None:
        eq = equip_dict
    clean = str(weapon_name).lower()

    # Regra Oficial Teklo Leveler (Joseph Qiu - EVO009):
    # • Com 0 ou 1 Evo equipado: Custo {r}{r}{r} (3 recursos), Poder 2, sem Go Again (arma é igual com 0 e 1 Evos).
    # • Com 2+ Evos equipados: Custa {r}{r} a menos -> Custa apenas {r} (1 recurso)!
    if "leveler" in clean or "teklo_leveler" in clean:
        equip_list = state.get("playerEquipment", []) if state else []
        evos_equipped = sum(1 for e in equip_list if isinstance(e, dict) and ("evo" in str(e.get("cardNumber", "")).lower() or "evo" in str(e.get("subtype", "")).lower()))
        if evos_equipped <= 1:
            return 3
        else:
            return 1

    # 1. Consulta banco dinâmico de custos de habilidades extraídos do Talishar
    ability_costs = _load_ability_costs()
    cost = None
    if clean in ability_costs:
        cost = ability_costs[clean]
    elif clean in _load_cards_db() and "ability_cost" in _load_cards_db()[clean]:
        cost = int(_load_cards_db()[clean]["ability_cost"])
    elif clean in KNOWN_WEAPON_COSTS:
        cost = KNOWN_WEAPON_COSTS[clean]
    else:
        for kw, kw_cost in [
            ("hammer", 3), ("anvilheim", 3), ("titans_fist", 3), ("pile_driver", 4), ("anothos", 3), ("rok", 3), ("club", 2),
            ("flail", 2), ("scythe", 2), ("staff", 2), ("meteor", 2), ("symbiosis", 2), ("zenith", 2),
            ("saber", 1), ("sword", 1), ("dagger", 1), ("blade", 1), ("claw", 1), ("kodachi", 1), ("pistol", 1), ("bow", 1)
        ]:
            if kw in clean:
                cost = kw_cost
                break
        if cost is None:
            cost = 2

    # 2. Modificadores Dinâmicos de Custo Baseados em Estado
    if state:
        num_drawn = int(state.get("cardsDrawnThisTurn", state.get("numCardsDrawn", state.get("num_drawn", state.get("numDrawn", 0)))))
        h_name = str(hero_name or state.get("playerHero", "")).lower()
        has_draw_discount = "kassai" in h_name or bool(state.get("weaponCostReductionOnDraw"))
        if has_draw_discount and num_drawn >= 1 and any(s in clean for s in ["saber", "sword", "blade", "cintari"]):
            cost = max(0, cost - 1)

    return cost


def get_all_known_zone_cards(state: dict) -> Dict[str, List[dict]]:
    """
    Retorna um mapa consolidado de todas as cartas em todas as zonas do jogo:
    Mão, Equipamentos, Arsenal, Banish, Cemitério (Discard), Alma (Soul), Pitch e Combat Chain.
    Permite que qualquer herói ou módulo de IA faça contagem de cartas (card counting),
    verificação de recursão e rastreamento de peças do deck em todas as zonas.
    """
    if not isinstance(state, dict):
        return {}
    return {
        "hand": [c for c in state.get("playerHand", []) if isinstance(c, dict)],
        "equipment": [c for c in state.get("playerEquipment", []) if isinstance(c, dict)],
        "arsenal": [c for c in (state.get("playerArsenal") or state.get("playerArse") or []) if isinstance(c, dict)],
        "banish": [c for c in state.get("playerBanish", []) if isinstance(c, dict)],
        "graveyard": [c for c in (state.get("playerGraveyard") or state.get("playerDiscard") or []) if isinstance(c, dict)],
        "soul": [c for c in state.get("playerSoul", []) if isinstance(c, dict)],
        "pitch": [c for c in state.get("playerPitch", []) if isinstance(c, dict)],
        "combat_chain": [c for c in state.get("combatChain", []) if isinstance(c, dict)],
        "opponent_graveyard": [c for c in (state.get("opponentGraveyard") or state.get("opponentDiscard") or []) if isinstance(c, dict)],
        "opponent_banish": [c for c in state.get("opponentBanish", []) if isinstance(c, dict)],
    }
