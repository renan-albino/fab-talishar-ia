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

from ..model import FaBPolicyValueNetwork
from .card_semantics import build_arena_threat_context


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
    base_chain_power = int(active_chain.get("totalPower", state.get("combatChainPower", 4)))
    incoming_name = str(active_chain.get("cardNumber", "")).lower()
    db_incoming = cards_db.get(incoming_name, {})
    incoming_text = str(db_incoming.get("text", "")).lower()

    # ── Contexto Holístico da Arena e Ameaças Semânticas ──────────────
    arena_ctx = build_arena_threat_context(state, my_hp=my_hp)
    opp_power = max(base_chain_power, arena_ctx.total_effective_physical_damage)
    
    from .on_hit_evaluator import estimate_on_hit_value
    on_hit_ev = estimate_on_hit_value(incoming_name, state)
    if on_hit_ev > 0:
        import math
        cards_needed = math.ceil(opp_power / 3.0)
        offensive_value_lost = cards_needed * 3.5
        if offensive_value_lost > on_hit_ev + opp_power:
            return []

    opp_hand_count_eval = int(state.get("opponentHandCount", state.get("theirHandCount", 0)))
    has_go_again = bool(active_chain.get("goAgain") or "go again" in incoming_text or "go again" in str(active_chain.get("keywords", [])).lower().replace("_", " "))
    is_early_chain_no_onhit = (
        int(state.get("currentChainLink", 1)) == 1
        and opp_hand_count_eval >= 1
        and has_go_again
        and on_hit_ev == 0
    )

    on_hit_threat = max(get_on_hit_threat(incoming_name, incoming_text), arena_ctx.composite_threat_score)
    has_dangerous_on_hit = (
        on_hit_threat >= 3.0
        or arena_ctx.extra_on_hit_damage > 0
        or any(oh in incoming_name for oh in DANGEROUS_ON_HITS)
    )

    # ── Palavras-chave Oficiais de Combate e Evasão da Arena ────────
    # Phantasm (CR 7.4.4): Ataque de Ilusionista destruído por defensor não-ilusionista com 6+ poder
    has_phantasm = arena_ctx.has_active_phantasm or bool(
        active_chain.get("phantasm")
        or active_chain.get("hasPhantasm")
        or state.get("phantasm")
        or "phantasm" in incoming_name
        or "phantasm" in incoming_text
        or "phantasm" in str(active_chain.get("keywords", [])).lower()
    )

    # Dominate (CR 7.4.2a): Não pode ser defendido por mais de 1 carta da mão
    has_dominate = arena_ctx.has_active_dominate or bool(
        active_chain.get("dominate")
        or active_chain.get("hasDominate")
        or state.get("dominate")
        or "dominate" in incoming_text
        or "dominate" in str(active_chain.get("keywords", [])).lower()
    )

    # Overpower (CR 7.4.2b): Não pode ser defendido por mais de 1 carta de ação
    has_overpower = arena_ctx.has_active_overpower or bool(
        active_chain.get("overpower")
        or active_chain.get("hasOverpower")
        or state.get("overpower")
        or "overpower" in incoming_text
        or "overpower" in str(active_chain.get("keywords", [])).lower()
    )

    # Piercing (CR 8.5.21): Ataques com Piercing ganham +1 de dano se bloqueados por equipamento
    has_piercing = arena_ctx.has_active_piercing or bool(
        active_chain.get("piercing")
        or active_chain.get("hasPiercing")
        or state.get("piercing")
        or "piercing" in incoming_name
        or "piercing" in incoming_text
        or "piercing" in str(active_chain.get("keywords", [])).lower()
    )

    # ── 3.1 Detecção Holística de Plano de Turno e Pivot ────────
    turn_plan = engine.strategy.analyze_turn_plan(state)
    is_heavy_hero = getattr(engine.strategy, "is_heavy_hero", False)
    current_turn = int(state.get("turnNo", state.get("currentTurn", 1)))

    # Contagem dinâmica de cartas Runegate na mão
    runegate_in_hand = sum(
        1 for hc in hand
        if "runegate" in str(hc.get("keywords", [])).lower()
        or any(rk in str(hc.get("cardNumber", "")).lower() for rk in [
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
        try:
            score = engine.strategy.evaluate_block_card(
                info["name"], info["block"], info["pitch"], info["power"], info["has_go_again"],
                runegate_in_hand=runegate_in_hand
            )
        except TypeError:
            score = engine.strategy.evaluate_block_card(
                info["name"], info["block"], info["pitch"], info["power"], info["has_go_again"]
            )

        # ── Identificação de Tipo e Classe para Regras Oficiais de Combate ──
        c_clean_name = str(c.get("cardNumber") or info["name"]).lower()
        c_db = cards_db.get(c_clean_name, {})
        c_type = str(c.get("type") or c_db.get("type", "")).upper()
        c_subtype = str(c.get("subtype") or c_db.get("subtype", "")).lower()
        c_class = str(c.get("class") or c_db.get("class", "")).upper()
        hero_class = str(getattr(engine, "hero_class", "") or state.get("playerClass", "") or state.get("heroClass", "")).upper()
        is_illusionist = "ILLUSIONIST" in c_class or "ILLUSIONIST" in hero_class
        effective_power = max(info.get("power", 0), int(c.get("power", 0)))

        is_dr = (
            c_type in ("DR", "DEFENSE REACTION")
            or "defense reaction" in c_subtype
            or any(k in c_clean_name for k in ["sink_below", "fate_foreseen", "staunch_response", "unmovable"])
        )
        is_action = not is_dr and (
            c_type in ("A", "AA", "ACTION", "ATTACK ACTION")
            or "action" in c_subtype
            or c_type == ""
        )

        # Phantasm Popping (CR 7.4.4): Defensor não-ilusionista com 6+ de poder estoura o ataque!
        is_phantasm_popper = has_phantasm and (not is_illusionist) and (effective_power >= 6)
        if is_phantasm_popper:
            score += 150.0  # Bonificação imensa para priorizar estourar o ataque e fechar cadeia com 0 dano

        # ── Poda Estrita de Peças Reservadas pelo TurnPlan ────────
        is_reserved = (
            info["name"] in turn_plan.reserved_card_names
            or c_clean_name in turn_plan.reserved_card_names
            or any(r.lower() == c_clean_name for r in turn_plan.reserved_card_names)
        )
        if is_reserved and turn_plan.can_absorb_damage and not is_phantasm_popper:
            # Se o plano determinou absorver dano para pivotar, peças reservadas
            # NUNCA bloqueiam a menos que estejamos sob risco letal iminente
            if my_hp > 6 and not (has_dangerous_on_hit and opp_power >= my_hp):
                score -= 150.0

        # ── Custo de Oportunidade Dinâmico de Bloqueio (Felt Table & AI Unsheathed)
        opp_cost = 0.0
        if hasattr(engine.strategy, "calculate_card_opportunity_cost"):
            avail_fl, _ = engine.calculate_available_resources(state)
            opp_cost = engine.strategy.calculate_card_opportunity_cost(hand, c, floating_res=avail_fl)

        if opp_cost > 0 and not is_phantasm_popper:
            absorb_mult = engine.strategy.get_dynamic_multiplier("absorb_tempo_bonus", 1.0)
            score -= opp_cost * 1.5 * absorb_mult
            is_catastrophic = on_hit_threat >= 8.0 or (my_hp - opp_power) <= 0
            if not is_catastrophic and my_hp > 8 and info["block"] < opp_cost:
                score -= 25.0

        # ── Poda de Preservação de Mão Ofensiva:
        # Se temos vida alta (> 20) e o ataque inimigo é fraco (<= 2 sem on-hit),
        # penaliza queimar cartas vermelhas de ataque chave (power >= 4 e pitch == 1)
        if my_hp > 20 and not has_dangerous_on_hit and opp_power <= 2 and not is_phantasm_popper:
            if info["power"] >= 4 and info["pitch"] == 1:
                score -= 5.0

        if is_early_chain_no_onhit:
            score -= 4.0

        # ── Poda de Tempo Pivot e Reserva Estrita de Pitch Crítico:
        if (is_heavy_hero or turn_plan.can_absorb_damage) and my_hp >= 8 and not has_dangerous_on_hit:
            if info["pitch"] == 1 and info["power"] >= 6 and not has_phantasm:
                score -= 25.0  # Nunca bloqueia com a bomba de ataque de Pivot (a menos que estoure Phantasm!)
            elif hasattr(engine.strategy, "is_critical_pitch_resource") and engine.strategy.is_critical_pitch_resource(info, hand, state) and not is_phantasm_popper:
                score -= 30.0  # Recurso de pitch sagrado preservado polimorficamente para o contra-ataque
            elif info["pitch"] == 3 and is_heavy_hero and not is_phantasm_popper:
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
                "pitch": info["pitch"], "power": effective_power,
                "is_equipment": False, "is_hand": True, "cost": hand_cost,
                "opp_cost": opp_cost,
                "is_action": is_action,
                "is_phantasm_popper": is_phantasm_popper,
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

            a_clean_name = str(c.get("cardNumber") or info["name"]).lower()
            a_db = cards_db.get(a_clean_name, {})
            a_type = str(c.get("type") or a_db.get("type", "")).upper()
            a_subtype = str(c.get("subtype") or a_db.get("subtype", "")).lower()
            a_class = str(c.get("class") or a_db.get("class", "")).upper()
            hero_class = str(getattr(engine, "hero_class", "") or state.get("playerClass", "") or state.get("heroClass", "")).upper()
            is_illusionist = "ILLUSIONIST" in a_class or "ILLUSIONIST" in hero_class
            effective_power = max(info.get("power", 0), int(c.get("power", 0)))
            is_popper = has_phantasm and (not is_illusionist) and (effective_power >= 6)
            if is_popper:
                score += 150.0

            is_dr = (
                a_type in ("DR", "DEFENSE REACTION")
                or "defense reaction" in a_subtype
                or any(k in a_clean_name for k in ["sink_below", "fate_foreseen", "staunch_response", "unmovable"])
            )
            is_action = not is_dr and (
                a_type in ("A", "AA", "ACTION", "ATTACK ACTION")
                or "action" in a_subtype
                or a_type == ""
            )

            c_id = info["actionDataOverride"] or str(a_idx)
            block_candidates.append({
                "type": "block", "score": score, "idx": a_idx, "card_id": c_id,
                "name": info["name"], "mode": c_action if c_action > 0 else 27,
                "block": effective_block, "pitch": info["pitch"], "power": effective_power,
                "from_arsenal": True, "is_arsenal": True, "is_equipment": False, "is_hand": False,
                "cost": 1.0,
                "is_action": is_action,
                "is_phantasm_popper": is_popper,
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

        # ── Cálculo da Defesa Efetiva com Marcadores de Penalidade (defCounters) ──
        # defCounters representam penalidades de defesa (ex: Battleworn, Blade Break).
        # Talishar nativo envia negativos (-1, -2); mocks/testes podem enviar positivos (+1).
        # Em ambos os casos, o valor absoluto é subtraído da defesa base.
        raw_def_counters = eq.get("defCounters")
        if raw_def_counters is None and isinstance(eq.get("countersMap"), dict):
            raw_def_counters = eq["countersMap"].get("defense")
        try:
            def_val = int(raw_def_counters) if raw_def_counters is not None and str(raw_def_counters).lstrip("-").isdigit() else 0
        except Exception:
            def_val = 0

        penalty = abs(def_val)
        effective_block = max(0, base_block - penalty)

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
        # Se o ataque NÃO possui efeito On-Hit (nem na carta e nem na arena) e nossa vida está saudável (HP > 12),
        # armaduras em geral não devem ser gastas para mitigar dano comum!
        is_safe_multiuse_temper = is_evo and has_temp and effective_block > 1
        if on_hit_threat == 0.0 and arena_ctx.extra_on_hit_damage == 0 and my_hp > 12 and not has_piercing:
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
            if is_early_chain_no_onhit:
                eq_score -= 8.0
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

        # ── Piercing (CR 8.5.21) Penalidade em Equipamentos ──
        if has_piercing:
            # Ataques com Piercing ganham +1 de dano ao serem bloqueados por equipamento.
            # Bloquear com armadura de block 1 resulta em 0 de mitigação líquida!
            if effective_block <= 1:
                eq_score -= 15.0
            else:
                eq_score -= 6.0

        if eq_score <= -20.0 and my_hp > 6:
            continue

        c_id = eq.get("actionDataOverride") or str(eq_idx)
        c_action = eq_action if eq_action > 0 else 3
        block_candidates.append({
            "type": "block", "score": eq_score, "idx": eq_idx, "card_id": str(c_id),
            "name": info["name"], "mode": c_action,
            "block": effective_block, "pitch": 0, "power": 0,
            "is_equipment": True, "is_hand": False, "cost": eq_cost,
            "is_action": False, "is_phantasm_popper": False,
        })

    if not block_candidates:
        return []

    # ── 3.2 Otimização de Subconjunto Mínimo de Defesa (Knapsack Breakpoint) ──
    from .knapsack_solver import solve_knapsack_defense
    knapsack_result = solve_knapsack_defense(
        block_candidates=block_candidates,
        opp_power=opp_power,
        my_hp=my_hp,
        has_dangerous_on_hit=has_dangerous_on_hit,
        has_phantasm=has_phantasm,
        has_dominate=has_dominate,
        has_overpower=has_overpower,
        has_piercing=has_piercing,
        turn_plan=turn_plan
    )
    if knapsack_result:
        return knapsack_result

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
    if my_hp <= 6 or arena_ctx.is_lethal_danger or (has_dangerous_on_hit and opp_power >= my_hp):
        max_hand_blocks = len(block_candidates)  # Modo Sobrevivência (Bloqueio total)
    elif turn_plan.plan_type in ("DEFENSIVE_TRAP", "FULL_DEFENSE", "DEFENSIVE"):
        max_hand_blocks = min(int(getattr(turn_plan, "max_block_cards", 2)), len(block_candidates))
    elif turn_plan.can_absorb_damage:
        max_hand_blocks = min(int(getattr(turn_plan, "max_block_cards", 2)), len(block_candidates))
    elif not has_dangerous_on_hit and my_hp > 15:
        # Em ataques comuns sem On-Hit com vida saudável (> 15), limita a no máximo 1 carta de mão para preservar a mão!
        max_hand_blocks = 1
    elif my_hp <= 12:
        max_hand_blocks = min(3, len(block_candidates))
    else:
        max_hand_blocks = min(2, len(block_candidates))

    # Regra Dominate (CR 7.4.2a): Limite estrito de no máximo 1 carta da mão
    if has_dominate:
        max_hand_blocks = min(max_hand_blocks, 1)

    hand_blocks_count = 0
    action_blocks_count = 0
    popped_phantasm = False

    for item in block_candidates:
        is_equip = item.get("is_equipment", False)
        is_hand = item.get("is_hand", not is_equip and not item.get("from_arsenal", False))
        is_action = item.get("is_action", False)
        is_popper = item.get("is_phantasm_popper", False)

        # Regra Dominate (CR 7.4.2a): Não mais de 1 carta da mão
        if is_hand and hand_blocks_count >= max_hand_blocks:
            continue

        # Regra Overpower (CR 7.4.2b, CR 8.3.22): Não mais de 1 carta de ação de qualquer zona
        if has_overpower and is_action and action_blocks_count >= 1:
            continue

        # Se já estouramos Phantasm neste elo, o ataque foi destruído: interrompe a defesa!
        if popped_phantasm:
            break

        # Regra Piercing (CR 8.5.21): Armadura com block <= 1 é inútil sozinha contra Piercing
        if has_piercing and is_equip and item["block"] <= 1 and my_hp > 2:
            continue

        # Poda de Bloqueio Ineficiente com Block <= 2 quando o plano é absorver dano:
        if turn_plan.can_absorb_damage and not is_equip and item["block"] <= 2 and my_hp > 12 and not is_popper:
            continue

        # Poda de Bloqueio Ineficiente: Não bloqueia se score for muito negativo com HP alto
        if my_hp > 15 and item["score"] < 0 and not has_dangerous_on_hit and not is_popper:
            continue

        chosen_blocks.append((item["idx"], item["card_id"], item["name"], item["mode"]))
        current_blocked += item["block"]
        if is_hand:
            hand_blocks_count += 1
        if is_action:
            action_blocks_count += 1

        # Phantasm Popping (CR 7.4.4):
        if is_popper:
            popped_phantasm = True
            current_blocked = max(current_blocked, opp_power)
            break  # Ataque destruído, elo fecha com 0 dano sofrido!

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

    # Pós-processamento Piercing (CR 8.5.21): Se apenas peças de equipamento foram selecionadas
    # e não evitam dano real (mitigação líquida <= 0), descarta o bloqueio de armadura inútil
    if has_piercing and chosen_blocks:
        chosen_items = [it for it in block_candidates if any(b[1] == it["card_id"] for b in chosen_blocks)]
        if chosen_items and all(it.get("is_equipment") for it in chosen_items):
            tot_eq_block = sum(it["block"] for it in chosen_items)
            net_mitigation = tot_eq_block - 1  # Piercing concede +1 de dano
            if net_mitigation <= 0 and my_hp > 2:
                chosen_blocks = []

    return chosen_blocks
