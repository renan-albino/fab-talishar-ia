"""
ai/policy/defense_pruner.py
===========================
Módulo de poda e seleção de defesa, otimização de breakpoints e preservação de mão ofensiva.
"""

import itertools
from typing import List, Tuple, Any

from .constants import (
    _get_cards_db,
    get_on_hit_threat,
    DANGEROUS_ON_HITS,
)
from ..hero_strategies import VynnsetStrategy
from ..model import FaBPolicyValueNetwork


def select_defense_blocks(engine: Any, state: dict) -> List[Tuple[int, str, str, int]]:
    """
    Seleciona a melhor combinação de bloqueadores (mão, arsenal com ambush, e equipamentos),
    otimizando breakpoints contra On-Hit perigosos, evitando overblocking e preservando
    recursos de contra-ataque.
    """
    hand = state.get("playerHand", [])
    my_hp = int(state.get("playerHealth", 20))
    opp_hp = int(state.get("opponentHealth", 20))
    cards_db = _get_cards_db()

    active_chain = state.get("activeChainLink", {})
    if not isinstance(active_chain, dict):
        active_chain = {}
    opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 4)))
    incoming_name = str(active_chain.get("cardNumber", "")).lower()
    db_incoming = cards_db.get(incoming_name, {})
    incoming_text = str(db_incoming.get("text", "")).lower()

    on_hit_threat = get_on_hit_threat(incoming_name, incoming_text)
    has_dangerous_on_hit = on_hit_threat >= 3.0 or any(oh in incoming_name for oh in DANGEROUS_ON_HITS)

    # ── 3.1 Detecção Holística de Plano de Turno e Pivot ────────
    turn_plan = engine.strategy.analyze_turn_plan(state)
    is_heavy_hero = getattr(engine.strategy, "is_heavy_hero", False)
    current_turn = int(state.get("turnNo", state.get("currentTurn", 1)))

    # Contagem de cartas de ataque Runegate na mão para Vynnset
    runegate_in_hand = 0
    if "vynnset" in str(engine.hero_name).lower():
        runegate_in_hand = sum(
            1 for hc in hand
            if any(rk in str(hc.get("cardNumber", "")).lower() for rk in [
                "cull", "deathly_delight", "deathly_wail", "widespread_ruin",
                "widespread_destruction", "widespread_annihilation", "oblivion", "eloquent_eulogy"
            ])
        )

    block_candidates = []
    for idx, c in enumerate(hand):
        info = engine.extract_card_info(c)
        if info["block"] <= 0:
            continue

        c_id = info["actionDataOverride"] or str(idx)
        c_action = info["action"] if info["action"] > 0 else 27
        if isinstance(engine.strategy, VynnsetStrategy):
            score = engine.strategy.evaluate_block_card(
                info["name"], info["block"], info["pitch"], info["power"], info["has_go_again"],
                runegate_in_hand=runegate_in_hand
            )
        else:
            score = engine.strategy.evaluate_block_card(
                info["name"], info["block"], info["pitch"], info["power"], info["has_go_again"]
            )

        # ── Poda Estrita de Peças Reservadas pelo TurnPlan ────────
        c_clean_name = str(c.get("cardNumber") or info["name"]).lower()
        is_reserved = (
            info["name"] in turn_plan.reserved_card_names
            or c_clean_name in turn_plan.reserved_card_names
            or any(r.lower() == c_clean_name for r in turn_plan.reserved_card_names)
        )
        if is_reserved and turn_plan.can_absorb_damage:
            # Se o plano determinou absorver dano para pivotar, peças reservadas
            # NUNCA bloqueiam a menos que estejamos sob risco letal iminente
            if my_hp > 6 and not (has_dangerous_on_hit and opp_power >= my_hp):
                score -= 150.0

        # ── Custo de Oportunidade Dinâmico de Bloqueio (Felt Table & AI Unsheathed)
        opp_cost = 0.0
        if hasattr(engine.strategy, "calculate_card_opportunity_cost"):
            avail_fl, _ = engine.calculate_available_resources(state)
            opp_cost = engine.strategy.calculate_card_opportunity_cost(hand, c, floating_res=avail_fl)

        if opp_cost > 0:
            absorb_mult = engine.strategy.get_dynamic_multiplier("absorb_tempo_bonus", 1.0)
            score -= opp_cost * 1.5 * absorb_mult
            is_catastrophic = on_hit_threat >= 8.0 or (my_hp - opp_power) <= 0
            if not is_catastrophic and my_hp > 8 and info["block"] < opp_cost:
                score -= 25.0

        # ── Poda de Preservação de Mão Ofensiva:
        # Se temos vida alta (> 20) e o ataque inimigo é fraco (<= 2 sem on-hit),
        # penaliza queimar cartas vermelhas de ataque chave (power >= 4 e pitch == 1)
        if my_hp > 20 and not has_dangerous_on_hit and opp_power <= 2:
            if info["power"] >= 4 and info["pitch"] == 1:
                score -= 5.0

        # ── Poda de Tempo Pivot e Reserva Estrita de Pitch Crítico:
        if (is_heavy_hero or turn_plan.can_absorb_damage) and my_hp >= 8 and not has_dangerous_on_hit:
            if info["pitch"] == 1 and info["power"] >= 6:
                score -= 25.0  # Nunca bloqueia com a bomba de ataque de Pivot
            elif engine.strategy.is_critical_pitch_resource(info, hand, state):
                score -= 30.0  # Recurso de pitch sagrado preservado polimorficamente para o contra-ataque
            elif info["pitch"] == 3 and is_heavy_hero:
                blue_count = len([x for x in hand if engine.extract_card_info(x)["pitch"] == 3])
                if blue_count == 2:
                    score -= 15.0  # Preserva a 2ª azul para fusão elemental / custo 3 + arma

        # Bônus para reações de defesa dedicadas (Sink, Fate, Staunch)
        if info["block"] >= 3 and any(k in info["name"] for k in ["sink", "fate", "staunch", "unmovable"]):
            score += 3.0

        hand_cost = 3.5 + opp_cost
        if is_reserved:
            hand_cost = 25.0
        elif info["power"] >= 5 or (info["pitch"] == 1 and info["power"] >= 4):
            hand_cost = 5.0 + opp_cost

        if score > -100.0 and info["block"] > 0:
            block_candidates.append({
                "type": "block", "score": score, "idx": idx, "card_id": c_id,
                "name": info["name"], "mode": c_action, "block": info["block"],
                "pitch": info["pitch"], "power": info["power"],
                "is_equipment": False, "is_hand": True, "cost": hand_cost,
                "opp_cost": opp_cost
            })

    # ── 3.1b Cartas no Arsenal que podem defender (Ambush e Down and Dirty) ──
    arsenal = state.get("playerArsenal") or state.get("playerArse") or []
    for a_idx, c in enumerate(arsenal):
        info = engine.extract_card_info(c)
        c_name_low = info["name"].lower()
        c_action = info.get("action", 0)
        db_entry = cards_db.get(c_name_low, {})
        card_text = (db_entry.get("text", "") if db_entry else "").lower()
        subtype = (db_entry.get("subtype", "") if db_entry else "").lower()
        is_down_and_dirty = "down_and_dirty" in c_name_low or "down and dirty" in c_name_low
        has_ambush = (
            "ambush" in subtype
            or "ambush" in card_text
            or "defend with this from your arsenal" in card_text
            or "ambush" in c_name_low
            or is_down_and_dirty
        )
        if has_ambush and info["block"] > 0:
            # Down and Dirty ganha +1 de defesa defendendo do arsenal (defende 4 em vez de 3!)
            effective_block = info["block"] + (1 if is_down_and_dirty else 0)
            # Defender do arsenal é altamente vantajoso: preserva a mão ofensiva e limpa o arsenal!
            score = float(effective_block) * 2.5 + 5.0
            c_id = info["actionDataOverride"] or str(a_idx)
            block_candidates.append({
                "type": "block", "score": score, "idx": a_idx, "card_id": c_id,
                "name": info["name"], "mode": c_action if c_action > 0 else 27,
                "block": effective_block, "pitch": info["pitch"], "power": info["power"],
                "from_arsenal": True, "is_equipment": False, "is_hand": False,
                "cost": 1.0
            })

    # ── 3.1c Bloqueio com Equipamentos (Defesa Otimizada e Anti-Queima) ────────
    equip = state.get("playerEquipment", [])
    for eq_idx, eq in enumerate(equip):
        if not isinstance(eq, dict):
            continue
        eq_name = str(eq.get("cardNumber", "")).lower()
        slot = str(eq.get("slot", "")).lower()
        if slot == "hero":
            continue
        # Armas só podem bloquear se forem especificamente do tipo equipamento/escudo
        db_entry = cards_db.get(eq_name, {})
        eq_type = str(eq.get("type") or db_entry.get("type", "")).upper()
        if slot == "weapon" and eq_type != "E":
            continue

        eq_action = int(eq.get("action", 0))
        if eq.get("isBroken") or eq.get("onChain"):
            continue

        info = engine.extract_card_info(eq)
        base_block = info["block"]

        # ── Cálculo da Defesa Efetiva com Marcadores (-1 counters / defCounters) ──
        # No Talishar nativo, marcadores de perda de defesa são números negativos (-1, -2).
        # Em mocks/testes, podem vir como positivos (+1 para indicar 1 marcador de -1).
        raw_def_counters = eq.get("defCounters")
        if raw_def_counters is None and isinstance(eq.get("countersMap"), dict):
            raw_def_counters = eq["countersMap"].get("defense")
        try:
            def_val = int(raw_def_counters) if raw_def_counters is not None and str(raw_def_counters).lstrip("-").isdigit() else 0
        except Exception:
            def_val = 0

        if def_val < 0:
            effective_block = max(0, base_block + def_val)  # Talishar nativo: 1 + (-1) = 0
        elif def_val > 0:
            effective_block = max(0, base_block - def_val)  # Mocks/testes: 1 - 1 = 0
        else:
            effective_block = base_block

        # Se a engine do Talishar enviou explicitamente action <= 0, o equipamento não pode defender agora
        if eq_action <= 0 and "action" in eq:
            continue

        is_crown = "crown_of_providence" in eq_name
        is_ironhide = "ironhide" in eq_name
        is_rampart = "rampart" in eq_name

        # Equipamentos com ativações defensivas que pagam recursos (Ironhide +2d, Rampart +1d)
        avail_floating, avail_pitch = engine.calculate_available_resources(state)
        has_defense_resource = (avail_floating + avail_pitch) >= 1

        if is_ironhide and has_defense_resource:
            effective_block = max(effective_block, max(0, 2 + def_val))
        elif is_rampart and has_defense_resource:
            effective_block = max(effective_block, max(0, 1 + def_val))

        is_evo = "evo" in eq_name or "cogwerx_base" in eq_name or "evo" in str(db_entry.get("subtype", "")).lower()

        has_bw = bool(db_entry.get("has_battleworn") or "battleworn" in str(db_entry.get("subtype", "")).lower())
        has_bb = bool(db_entry.get("has_blade_break") or "blade break" in str(db_entry.get("subtype", "")).lower() or "ironrot" in eq_name or eq.get("has_blade_break"))
        has_temp = bool(db_entry.get("has_temper") or "temper" in str(db_entry.get("subtype", "")).lower() or is_evo or eq.get("has_temper"))

        has_defend_trigger = (
            is_crown
            or (is_ironhide and has_defense_resource)
            or (is_rampart and has_defense_resource)
            or "defend" in str(db_entry.get("text", "")).lower()
            or any(k in eq_name for k in ["providence", "ironhide", "rampart", "constellas", "carrion_husk"])
        )

        # Equipamentos cuja defesa foi zerada (ou base 0):
        # Se NÃO possui efeito ao defender, descarta para não bloquear inutilmente por 0 de dano!
        if effective_block <= 0 and not has_defend_trigger:
            continue

        arsenal = state.get("playerArsenal") or state.get("playerArse") or []
        has_arsenal = len(arsenal) > 0
        is_arsenal_threat = has_arsenal and (
            any(k in incoming_name for k in ["command_and_conquer", "leave_no_witnesses", "wreck_havoc", "eradicate", "humble", "righteous_cleansing"])
            or ("arsenal" in incoming_text and any(w in incoming_text for w in ["destroy", "banish", "put"]))
        )
        # Avaliação de mão para Crown of Providence ciclar cartas
        hand_cards = state.get("playerHand", [])
        hand_info = [engine.extract_card_info(c) for c in hand_cards]
        num_attacks = sum(1 for c in hand_info if c["power"] > 0)
        num_pitches = sum(1 for c in hand_info if c["pitch"] >= 2)
        is_awkward_hand = (len(hand_cards) >= 3 and (num_pitches == 0 or num_attacks == 0))

        will_break = has_bb or (has_temp and effective_block <= 1)

        # ── Poda Estrita de Armadura em Ataques Vanilla ──
        # Se o ataque NÃO possui efeito On-Hit e nossa vida está saudável (HP > 12),
        # armaduras em geral não devem ser gastas para mitigar dano comum!
        is_safe_multiuse_temper = is_evo and has_temp and effective_block > 1
        if on_hit_threat == 0.0 and my_hp > 12:
            if not ((is_crown and is_awkward_hand) or is_safe_multiuse_temper):
                continue

        # Preservação polimórfica de equipamentos vitais (ex: Evos com Temper de Teklovossen)
        is_fatal = (my_hp - opp_power) <= 0
        if engine.strategy.should_preserve_equipment_on_block(eq_name, eq, state, opp_power, is_fatal):
            continue

        has_active_ability = bool(db_entry.get("ability_cost") is not None or any(k in eq_name for k in [
            "goliath_gauntlet", "heartened_cross_strap", "snapdragon_scalers",
            "fyendals_spring_tunic", "scabskin_leathers", "barkbone_strapping", "tunic"
        ]))

        eq_cost = 3.5
        eq_score = float(effective_block) * 3.0

        if is_crown:
            if is_arsenal_threat:
                eq_score += 35.0  # Prioridade máxima: salva o Arsenal de destruição/on-hit e puxa carta nova
                eq_cost = 1.0
            elif my_hp <= 6 or (has_dangerous_on_hit and opp_power >= my_hp):
                eq_score += 20.0  # Modo sobrevivência: salva vida crítica
                eq_cost = 1.5
            elif has_dangerous_on_hit and not (any(k in incoming_name for k in ["command_and_conquer", "leave_no_witnesses", "wreck_havoc", "eradicate"]) and not has_arsenal):
                eq_score += 16.0  # Parar on-hit perigoso ativo
                eq_cost = 2.0
            elif my_hp <= 12 or is_awkward_hand:
                eq_score += 10.0  # Pressão ou ciclo de mão disfuncional
                eq_cost = 2.5
            else:
                eq_score -= 25.0  # Poupar Crown (Blade Break valioso)
                eq_cost = 25.0
        elif is_ironhide and has_defense_resource:
            eq_score += 6.0
            eq_cost = 2.0
        elif is_rampart and has_defense_resource:
            eq_score += 4.0
            eq_cost = 2.0
        elif has_defend_trigger:
            eq_score += 8.0
            eq_cost = 2.0
        elif effective_block <= 0:
            eq_score = 0.0
            eq_cost = 5.0
        elif has_bw:
            eq_score += 8.0  # Battleworn é prioridade máxima: bloqueia de graça e sobrevive
            eq_cost = 1.5
        elif has_temp:
            eq_score += 5.0  # Temper sobrevive se defCounters < base_block - 1
            eq_cost = 2.5
        elif has_bb:
            if has_active_ability:
                if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= my_hp):
                    eq_score += 2.0  # Modo Sobrevivência: salva vida a qualquer custo
                    eq_cost = 6.0
                else:
                    eq_score -= 25.0  # Preserva equipamento com habilidade ativa
                    eq_cost = 25.0
            else:
                if opp_power <= 2 and my_hp > 20 and not has_dangerous_on_hit:
                    eq_score -= 3.0  # Economiza armadura descartável se dano for irrelevante
                    eq_cost = 5.0
                else:
                    eq_score += 3.0  # Ironrot / armadura pura bloqueia para mitigar dano e economizar mão
                    eq_cost = 3.5

        if eq_score <= -20.0 and my_hp > 6:
            continue

        c_id = eq.get("actionDataOverride") or str(eq_idx)
        c_action = eq_action if eq_action > 0 else 3
        block_candidates.append({
            "type": "block", "score": eq_score, "idx": eq_idx, "card_id": str(c_id),
            "name": info["name"], "mode": c_action,
            "block": effective_block, "pitch": 0, "power": 0,
            "is_equipment": True, "is_hand": False, "cost": eq_cost
        })

    if not block_candidates:
        return []

    # ── 3.2 Otimização de Subconjunto Mínimo de Defesa (Knapsack Breakpoint) ──
    # Quando há On-Hit perigoso e não estamos em modo sobrevivência de desespero:
    # Encontra o subconjunto de menor custo total (poupando cartas da mão para o pivot)
    # que neutraliza completamente o dano (total_block >= opp_power).
    if has_dangerous_on_hit and opp_power > 0 and my_hp > 6:
        valid_subsets = []
        max_hand_in_subset = turn_plan.max_block_cards if turn_plan.can_absorb_damage else (
            2 if my_hp > 12 else 3
        )
        for r in range(1, min(len(block_candidates) + 1, 5)):
            for subset in itertools.combinations(block_candidates, r):
                tot_block = sum(item["block"] for item in subset)
                if tot_block >= opp_power:
                    hand_count = sum(1 for item in subset if item.get("is_hand"))
                    if hand_count > max_hand_in_subset:
                        continue
                    # Poda de Bloqueio Ineficiente: Se o plano permite absorver dano para pivotar
                    # ou vida saudável (> 12), rejeitar subconjuntos com 2+ cartas de mão com média <= 2.0 block
                    if turn_plan.can_absorb_damage and hand_count >= 2:
                        avg_hand_block = sum(item["block"] for item in subset if item.get("is_hand")) / hand_count
                        if avg_hand_block <= 2.0:
                            continue
                    overblock = tot_block - opp_power
                    sub_cost = sum(item["cost"] for item in subset) + (overblock * 0.7)
                    valid_subsets.append((sub_cost, subset))

        if valid_subsets:
            valid_subsets.sort(key=lambda x: x[0])
            best_subset = valid_subsets[0][1]
            return [(item["idx"], item["card_id"], item["name"], item["mode"]) for item in best_subset]

    # ── 3.3 Avaliação da Rede Neural Policy-Value e Refinamento ISMCTS ──
    if engine.model is not None and block_candidates:
        try:
            state_vec = FaBPolicyValueNetwork.extract_state_vector(state, getattr(engine, "player_id", 1))
            probs, _ = engine.model.predict_state(state_vec, str(engine.device))
            for item in block_candidates:
                action_id = int(item.get("mode", 3)) % 32
                prior_prob = float(probs[action_id]) if action_id < len(probs) else 0.0
                item["score"] += prior_prob * 10.0
        except Exception:
            pass

    if len(block_candidates) > 1 and engine.num_mcts_sims > 0:
        opp_hand = state.get("opponentHand", [])
        opp_hand_count = len(opp_hand) if isinstance(opp_hand, list) and len(opp_hand) > 0 else int(
            state.get("opponentHandCount", state.get("theirHandCount", 0))
        )
        if opp_hand_count > 0:
            best_idx, _, ismcts_log = engine.ismcts.search_ismcts(
                state=state,
                legal_actions=block_candidates,
                num_simulations=engine.num_mcts_sims,
            )
            try:
                engine.ismcts_logger.log(
                    ismcts_log=ismcts_log,
                    turn=int(state.get("turnNo", state.get("turn", 0))),
                    phase="BLOCK",
                )
            except Exception:
                pass
            best_item = block_candidates[best_idx]
            best_item["score"] += 10.0

    # Ordenar melhores cartas defensivas primeiro
    block_candidates.sort(key=lambda x: x["score"], reverse=True)

    chosen_blocks = []
    current_blocked = 0

    # Limite máximo de cartas da MÃO para bloquear
    if my_hp <= 6 or (has_dangerous_on_hit and opp_power >= my_hp):
        max_hand_blocks = len(block_candidates)  # Modo Sobrevivência (Bloqueio total)
    elif turn_plan.plan_type in ("DEFENSIVE_TRAP", "FULL_DEFENSE", "DEFENSIVE"):
        max_hand_blocks = min(turn_plan.max_block_cards, len(block_candidates))
    elif turn_plan.can_absorb_damage:
        max_hand_blocks = min(turn_plan.max_block_cards, len(block_candidates))
    elif not has_dangerous_on_hit and my_hp > 15:
        # Em ataques comuns sem On-Hit com vida saudável (> 15), limita a no máximo 1 carta de mão para preservar a mão!
        max_hand_blocks = 1
    elif my_hp <= 12:
        max_hand_blocks = min(3, len(block_candidates))
    else:
        max_hand_blocks = min(2, len(block_candidates))

    hand_blocks_count = 0
    for item in block_candidates:
        is_equip = item.get("is_equipment", False)
        if not is_equip and hand_blocks_count >= max_hand_blocks:
            continue

        # Poda de Bloqueio Ineficiente com Block <= 2 quando o plano é absorver dano:
        if turn_plan.can_absorb_damage and not is_equip and item["block"] <= 2 and my_hp > 12:
            continue

        # Poda de Bloqueio Ineficiente: Não bloqueia se score for muito negativo com HP alto
        if my_hp > 15 and item["score"] < 0 and not has_dangerous_on_hit:
            continue

        chosen_blocks.append((item["idx"], item["card_id"], item["name"], item["mode"]))
        current_blocked += item["block"]
        if not is_equip:
            hand_blocks_count += 1

        # ── Defesa Mínima Viável (FaB Minimum Viable Defense / Preservação de Contra-Ataque) ──
        remaining_dmg = max(0, opp_power - current_blocked)
        projected_hp = my_hp - remaining_dmg
        if current_blocked > 0 and turn_plan.plan_type not in ("DEFENSIVE_TRAP", "FULL_DEFENSE"):
            remaining_hand = len(hand) - hand_blocks_count
            # Se o ataque ameaça destruir Arsenal mas não temos cartas no Arsenal, o on-hit é inócuo
            arsenal_cards = state.get("playerArsenal") or state.get("playerArse") or []
            is_real_on_hit = has_dangerous_on_hit and not (
                any(k in incoming_name for k in ["command_and_conquer", "leave_no_witnesses", "wreck_havoc", "eradicate"])
                and len(arsenal_cards) == 0
            )
            if projected_hp >= 2 and remaining_hand <= 1 and not is_real_on_hit:
                # Preserva a última carta da mão para poder dar pitch / jogar ação ofensiva
                break
            elif projected_hp >= 1 and opp_hp <= 4 and remaining_hand <= 1:
                # Risco tático de vitória: aceita dano residual seguro para garantir o swing letal!
                break

        # ── Poda de Overblocking Exato:
        if current_blocked >= opp_power and my_hp > 6:
            break

    return chosen_blocks
