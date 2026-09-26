import time
from ai.chat_badges import format_attack_chat_message

def handle_pitch_phase(client, state: dict, turn_phase: str, prompt_buttons: list, unpayable_set: set) -> bool:
    """Gerencia a fase de pitch: PDECK, seleção ótima via policy_engine ou cancelamento seguro (mode 10000)."""
    if turn_phase not in ("P", "PDECK", "PAYGOLDORPITCH", "CHOOSEHANDCANCEL"):
        return False

    if turn_phase == "PDECK":
        pitch = state.get("playerPitch", [])
        pitch_card = "0"
        if pitch:
            p0 = pitch[0]
            pitch_card = p0.get("cardNumber", p0.get("cardID", "0")) if isinstance(p0, dict) else str(p0)
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Bottom do Pitch (PDECK -> {pitch_card})")
        client.send_action(mode=6, card_id=str(pitch_card), button_input=str(pitch_card))
        time.sleep(0.002)
        return True

    target_cost = 1
    if hasattr(client, "last_attempted_play") and client.last_attempted_play:
        info = client.policy_engine.extract_card_info({"cardNumber": client.last_attempted_play})
        target_cost = info.get("cost", 1)

    pitch_choice = client.policy_engine.select_best_pitch_card(state, target_cost=target_cost)
    if pitch_choice:
        p_idx, p_name, p_mode, p_id = pitch_choice
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Pitch Tático -> {p_name} (Index: {p_idx})")
        client.send_action(mode=p_mode, card_id=p_id, button_input=p_name)
        time.sleep(0.002)
        return True

    if hasattr(client, "last_attempted_play") and client.last_attempted_play:
        unpayable_set.add(client.last_attempted_play)

    cancel_btn = None
    if prompt_buttons:
        for b in prompt_buttons:
            cap = str(b.get("caption", "")).lower()
            if "cancel" in cap or b.get("mode") == 10000:
                cancel_btn = b
                break

    if cancel_btn:
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Botão Pitch/Cancel -> {cancel_btn.get('caption')} (Mode {cancel_btn.get('mode')})")
        client.send_action(mode=cancel_btn.get("mode", 10000), button_input=str(cancel_btn.get("buttonInput", "")))
        time.sleep(0.002)
        return True

    client.log(f"[AÇÃO JOGADOR {client.player_id}] Sem cartas para pitch -> Cancelar (Mode 10000)")
    client.send_action(mode=10000, button_input="")
    time.sleep(0.002)
    return True

def handle_block_phase(client, state: dict, turn_num: int, prompt_buttons: list) -> bool:
    """Gerencia a fase de defesa / bloqueio (B), telemetria de plano, equipamentos e passagem."""
    tp_raw = state.get("turnPhase", "M")
    turn_phase = str(tp_raw.get("turnPhase", "M")) if isinstance(tp_raw, dict) else str(tp_raw or "M")
    if turn_phase != "B":
        return False

    chain_desc = client.get_combat_chain_desc(state)
    if chain_desc and getattr(client, "last_logged_combat_attack", None) != (turn_num, chain_desc):
        client.last_logged_combat_attack = (turn_num, chain_desc)
        client.opp_attacks_count += 1
        client.blocks_declared_count = 0
        client.log(f"[COMBAT CHAIN] ⚔️ Ataque em Andamento: {chain_desc}")

    if not hasattr(client, "declared_blocks_link"):
        client.declared_blocks_link = set()

    # ── Telemetria de Plano de Turno e Pivot ───────────────
    current_plan = client.policy_engine.strategy.analyze_turn_plan(state)
    if getattr(client, "last_logged_def_plan", None) != (turn_num, current_plan.plan_type):
        client.last_logged_def_plan = (turn_num, current_plan.plan_type)
        plan_badge = f"<b>[Turno {turn_num}] 🎯 Plano de Defesa</b> -> <b>{current_plan.plan_type}</b> ({current_plan.reason})"
        client.send_chat_log(plan_badge, highlight=True, bg_color="#0f172a", text_color="#38bdf8")
        client.log(f"[PLANO DE DEFESA] 🎯 Estratégia: {current_plan.plan_type} - {current_plan.reason}")

    from ai.common.schemas import clean_int_value
    active_chain = state.get("activeChainLink") or {}
    opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0))) if isinstance(active_chain, dict) else 0
    already_blocking = clean_int_value(active_chain.get("totalDefense", 0)) if isinstance(active_chain, dict) else 0
    eff_opp_power = max(0, opp_power - already_blocking)
    
    # Inject into state so defense_pruner sees the reduced power
    if isinstance(state.get("activeChainLink"), dict):
        state["activeChainLink"]["totalPower"] = eff_opp_power
    state["combatChainPower"] = eff_opp_power

    chosen_blocks = client.policy_engine.select_defense_blocks(state)
    unblocked = [b for b in chosen_blocks if (b[3], str(b[1])) not in client.declared_blocks_link]
    if unblocked:
        b_idx, b_id, b_name, b_action = unblocked[0]
        client.declared_blocks_link.add((b_action, str(b_id)))
        client.blocks_declared_count += 1
        if hasattr(client, "equipment_tracker"):
            equip_names = {str(eq.get("cardNumber", "")).lower() for eq in state.get("playerEquipment", []) if isinstance(eq, dict)}
            if str(b_name).lower() in equip_names:
                client.equipment_tracker.track_block(
                    hero=client.hero_name,
                    eq_name=b_name,
                    turn=turn_num,
                )
        chat_msg = f"<b>[Turno {turn_num}] 🛡️ Bloqueio Tático</b> -> <b>{b_name}</b> (Defesa Otimizada)"
        client.send_chat_log(chat_msg, highlight=True, bg_color="#1e1b4b", text_color="#c084fc")
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Bloqueio Tático -> {b_name} (ID: {b_id}, Mode: {b_action})")
        client.send_action(mode=b_action, card_id=str(b_id), button_input=b_name)
        time.sleep(0.002)
        return True

    client.declared_blocks_link = set()
    pass_btn = None
    if prompt_buttons:
        for b in prompt_buttons:
            cap = str(b.get("caption", "")).lower()
            if ("pass" in cap or b.get("mode") in (99, 101)) and "undo" not in cap:
                pass_btn = b
                break

    if pass_btn:
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Passou Bloqueio ({pass_btn.get('caption', 'Pass')})")
        client.send_action(mode=pass_btn.get("mode", 99), button_input=str(pass_btn.get("buttonInput", "")))
    else:
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Passou Bloqueio (Mode 99)")
        client.send_action(mode=99, button_input="")
    time.sleep(0.002)
    return True

def handle_reaction_phase(client, state: dict, turn_num: int, turn_phase: str, prompt_buttons: list, unpayable_set: set) -> bool:
    """Gerencia reações de ataque/defesa/instants da mão e equipamentos com podas heurísticas."""
    if turn_phase not in ("A", "D", "INSTANT"):
        return False

    chain_desc = client.get_combat_chain_desc(state)
    if chain_desc and getattr(client, "last_logged_combat_attack", None) != (turn_num, chain_desc):
        client.last_logged_combat_attack = (turn_num, chain_desc)
        client.log(f"[COMBAT CHAIN] ⚔️ Ataque em Andamento: {chain_desc}")

    hand = state.get("playerHand", [])
    active_chain = state.get("activeChainLink") or {}

    if not hasattr(client, "reaction_attempts"):
        client.reaction_attempts = {}

    # Reset reaction_attempts quando um novo chain link começa (novo ataque na cadeia)
    current_chain_id = str(active_chain.get("cardNumber", "")) + str(active_chain.get("uniqueID", ""))
    if not hasattr(client, "_last_chain_link_id"):
        client._last_chain_link_id = ""
    if current_chain_id and current_chain_id != client._last_chain_link_id:
        client.reaction_attempts = {}
        client._last_chain_link_id = current_chain_id

    turn_player = state.get("turnPlayer", 1)
    is_defending = (turn_player != client.player_id)
    is_attacking = (turn_player == client.player_id)
    incoming_text = str(active_chain.get("text", "")).lower()
    incoming_name = str(active_chain.get("cardNumber", "")).lower()

    # Dominate (CR 7.4.2a, CR 8.3.4b): Não pode ser defendido por mais de 1 carta da mão
    has_dominate = False
    if hasattr(client, "policy_engine") and hasattr(client.policy_engine, "arena_ctx"):
        has_dominate = getattr(client.policy_engine.arena_ctx, "has_active_dominate", False)
    if not has_dominate:
        has_dominate = bool(
            active_chain.get("dominate")
            or active_chain.get("hasDominate")
            or state.get("dominate")
            or state.get("hasDominate")
            or "dominate" in incoming_text
            or "dominate" in incoming_name
            or "dominate" in str(active_chain.get("keywords", [])).lower()
        )

    # Verifica se já houve defesa com carta da mão neste elo de combate (CR 7.4.2a, CR 8.3.4b)
    hand_defended = getattr(client, "blocks_declared_count", 0) >= 1
    if not hand_defended:
        combat_chain_cards = state.get("combatChain") or active_chain.get("reactions") or []
        equip_names = {str(eq.get("cardNumber", "")).lower() for eq in state.get("playerEquipment", []) if isinstance(eq, dict)}
        for ch_card in combat_chain_cards:
            if isinstance(ch_card, dict):
                ctrl = ch_card.get("controller", client.player_id)
                if str(ctrl) == str(client.player_id):
                    c_name_link = str(ch_card.get("cardNumber", "")).lower()
                    is_eq = c_name_link in equip_names or ch_card.get("slot") or ch_card.get("is_equipment")
                    is_ars = ch_card.get("from_arsenal") or ch_card.get("is_arsenal") or ch_card.get("zone") == "ARS"
                    if not is_eq and not is_ars:
                        hand_defended = True
                        break

    # 6a. Reações / Instantâneos via Mão
    for idx, c in enumerate(hand):
        c_action = c.get("action", 0)
        c_name = c.get("cardNumber", "")
        
        attempts = client.reaction_attempts.get(c_name, 0)
        if attempts >= 2:
            unpayable_set.add(c_name)
            
        if c_action > 0 and c_name not in unpayable_set:
            c_low = str(c_name).lower()
            cards_db = getattr(client.policy_engine, "cards_db", {}) or {}
            db_entry = cards_db.get(c_low, {})
            c_type = str(c.get("type") or db_entry.get("type", "")).upper()
            c_subtype = str(c.get("subtype") or db_entry.get("subtype", "")).lower()

            is_dr = (
                c_type in ("DR", "DEFENSE REACTION")
                or "defense reaction" in c_subtype
                or "defense reaction" in c_type.lower()
                or any(k in c_low for k in ["sink_below", "fate_foreseen", "staunch_response", "unmovable", "shelter", "take_cover"])
            )
            is_instant = (
                c_type in ("I", "INSTANT")
                or "instant" in c_subtype
                or "instant" in c_type.lower()
            )
            is_ar = (
                c_type in ("AR", "ATTACK REACTION")
                or "attack reaction" in c_subtype
                or "attack reaction" in c_type.lower()
                or any(k in c_low for k in ["razor_reflex", "ironsong_response", "pummel"])
            )

            if is_defending and not (is_dr or is_instant):
                continue
            if is_attacking and not (is_ar or is_instant):
                continue

            # ── Regra Dominate (CR 7.4.2a, CR 8.3.4b) ──
            # Se o ataque tem Dominate e já houve defesa com carta da mão, NÃO permite jogar Defense Reaction da mão!
            if is_defending and has_dominate and hand_defended and is_dr:
                client.log(f"[DOMINATE] ⚠️ Bloqueado jogar Defense Reaction da mão ({c_name}) sob Dominate.")
                continue

            # ── Poda Estrita de Instants Ofensivos na Defesa ──
            # Cartas de ataque puro, setup ou buffs ofensivos (ex: Astral Bridge, Thunderous Retort, Lightning Press)
            # NUNCA devem ser disparadas cegamente no turno do oponente enquanto ele ataca/ativa habilidades!
            if is_defending:
                is_offensive_instant = any(k in c_low for k in [
                    "astral_bridge", "thunderous_retort", "lightning_press",
                    "flowstate", "consign_to_cosmos", "comet_storm", "second_strike",
                    "razor_reflex", "ironsong_response", "pummel", "ancestral"
                ])
                if is_offensive_instant:
                    continue

            info = client.policy_engine.extract_card_info(c)
            floating_res, total_res = client.policy_engine.calculate_available_resources(state)
            remaining_pitch = total_res - info["pitch"]
            if remaining_pitch >= info["cost"]:
                c_id = c.get("actionDataOverride", str(idx))
                if c_action == 27:
                    c_id = str(idx)
                client.last_attempted_play = c_name
                client.reaction_attempts[c_name] = attempts + 1
                chat_msg = f"<b>[Turno {turn_num}] ⚡ Reação Tática</b> -> <b>{c_name}</b> (Modo {c_action})"
                client.send_chat_log(chat_msg, highlight=True, bg_color="#14532d", text_color="#4ade80")
                client.log(f"[AÇÃO JOGADOR {client.player_id}] Jogou Reação/Instant (Mão) -> {c_name}")
                client.send_action(mode=c_action, card_id=c_id, button_input=c_name)
                time.sleep(0.002)
                return True

    # 6b. Reações / Instantâneos via Arsenal (CR 7.4.2d, CR 7.5b)
    # Cartas de Defense Reaction e Instant no Arsenal podem ser jogadas legalmente, inclusive sob Dominate!
    arsenal = state.get("playerArsenal") or state.get("playerArse") or []
    for ars_idx, c in enumerate(arsenal):
        if not isinstance(c, dict):
            continue
        c_action = c.get("action")
        # Se action for explicitamente 0, carta não é jogável pelo Talishar
        if c_action == 0:
            continue
        effective_action = c_action if (c_action is not None and c_action > 0) else 5
        c_name = c.get("cardNumber", "")
        c_low = str(c_name).lower()

        attempts = client.reaction_attempts.get(c_name, 0)
        if attempts >= 2:
            unpayable_set.add(c_name)

        if c_name in unpayable_set:
            continue

        cards_db = getattr(client.policy_engine, "cards_db", {}) or {}
        db_entry = cards_db.get(c_low, {})
        c_type = str(c.get("type") or db_entry.get("type", "")).upper()
        c_subtype = str(c.get("subtype") or db_entry.get("subtype", "")).lower()

        is_dr = (
            c_type in ("DR", "DEFENSE REACTION")
            or "defense reaction" in c_subtype
            or "defense reaction" in c_type.lower()
            or any(k in c_low for k in ["sink_below", "fate_foreseen", "staunch_response", "unmovable", "shelter", "take_cover"])
        )
        is_instant = (
            c_type in ("I", "INSTANT")
            or "instant" in c_subtype
            or "instant" in c_type.lower()
        )
        is_ar = (
            c_type in ("AR", "ATTACK REACTION")
            or "attack reaction" in c_subtype
            or "attack reaction" in c_type.lower()
            or any(k in c_low for k in ["razor_reflex", "ironsong_response", "pummel"])
        )

        if is_defending:
            if not (is_dr or is_instant):
                continue
            is_offensive_instant = any(k in c_low for k in [
                "astral_bridge", "thunderous_retort", "lightning_press",
                "flowstate", "consign_to_cosmos", "comet_storm", "second_strike",
                "razor_reflex", "ironsong_response", "pummel", "ancestral"
            ])
            if is_offensive_instant:
                continue
        elif is_attacking:
            if not (is_ar or is_instant):
                continue

        info = client.policy_engine.extract_card_info(c)
        floating_res, total_res = client.policy_engine.calculate_available_resources(state)
        # Cartas do Arsenal não contam para pitch da mão; todos os recursos totais estão disponíveis
        if total_res >= info["cost"]:
            c_id = c.get("actionDataOverride") or str(c.get("uniqueID", ars_idx))
            if effective_action == 5:
                c_id = c.get("actionDataOverride") or str(ars_idx)
            client.last_attempted_play = c_name
            client.reaction_attempts[c_name] = attempts + 1
            chat_msg = f"<b>[Turno {turn_num}] ⚡ Reação de Arsenal</b> -> <b>{c_name}</b> (Modo {effective_action})"
            client.send_chat_log(chat_msg, highlight=True, bg_color="#14532d", text_color="#4ade80")
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Jogou Reação/Instant (Arsenal) -> {c_name} (ID: {c_id}, Modo: {effective_action})")
            client.send_action(mode=effective_action, card_id=str(c_id), button_input=c_name)
            time.sleep(0.002)
            return True

    # 6c. Reações / Instantâneos via Equipamentos (Snapdragon Scalers, Boots of Omniward, etc.)
    equip = state.get("playerEquipment", [])
    opp_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
    arcane_dmg = int(state.get("arcaneDamage", 0) or 0)
    my_hp = int(state.get("playerHealth", 20))

    for eq_idx, eq in enumerate(equip):
        if not isinstance(eq, dict):
            continue
        eq_action = int(eq.get("action", 0))
        eq_name = str(eq.get("cardNumber", "")).lower()
        slot = str(eq.get("slot", "")).lower()
        if slot == "hero" or eq.get("isBroken") or eq.get("onChain"):
            continue

        attempts = client.reaction_attempts.get(eq_name, 0)
        if attempts >= 2:
            unpayable_set.add(eq_name)

        if eq_action > 0 and eq_name not in unpayable_set:
            # ── Poda 1: Equipamentos de Prevenção / Defesa (Boots of Omniward, Ward, Barrier, Prevent) ──
            is_prevention_eq = any(k in eq_name for k in ["boots_of_omni", "omniward", "barrier", "ward", "prevent", "spellvoid"])
            if is_prevention_eq:
                # NUNCA ativar no vazio quando não há dano físico ou arcano sendo causado!
                if opp_power <= 0 and arcane_dmg <= 0:
                    continue
                # Se for nosso turno de ataque e não há dano arcano contra nós, não queima prevenção
                if is_attacking and arcane_dmg <= 0:
                    continue
                # Boots of Omniward é destruída ao ativar. Se HP alto e sem dano crítico/on-hit, poupar!
                if "omniward" in eq_name:
                    incoming_name = str(active_chain.get("cardNumber", "")).lower()
                    has_threat = any(oh in incoming_name for oh in ["command_and_conquer", "red_in_the_ledger", "snatch", "mask", "leave_no_witnesses", "crush"])
                    if my_hp > 15 and not has_threat and (my_hp - opp_power) > 10:
                        continue

            # ── Poda 2: Reações Ofensivas de Ataque (Snapdragon Scalers, Flick Knives) ──
            if "snapdragon_scalers" in eq_name:
                if not is_attacking:
                    continue
                # Se o ataque já possui go again, não gasta Snapdragon
                if active_chain.get("hasGoAgain") or active_chain.get("goAgain"):
                    continue
                # Se não há mais cartas ou ações em mãos, não desperdiça
                if not hand:
                    continue
            elif "flick_knives" in eq_name:
                if not is_attacking:
                    continue

            # ── Poda 3: Validação de Pontuação Semântica da Estratégia ──
            eq_score = client.policy_engine.strategy.evaluate_equipment_ability(state, eq)
            if eq_score <= 0.0 and not (is_prevention_eq and (opp_power > 0 or arcane_dmg > 0)):
                continue

            eq_cost = client.policy_engine.get_weapon_cost(eq_name, eq, state)
            floating_res, total_res = client.policy_engine.calculate_available_resources(state)
            if total_res >= eq_cost:
                eq_id = eq.get("actionDataOverride", str(eq_idx))
                client.last_attempted_play = eq_name
                client.reaction_attempts[eq_name] = attempts + 1
                chat_msg = f"<b>[Turno {turn_num}] ⚡ Reação de Equipamento</b> -> <b>{eq_name}</b> (Modo {eq_action})"
                client.send_chat_log(chat_msg, highlight=True, bg_color="#14532d", text_color="#4ade80")
                client.log(f"[AÇÃO JOGADOR {client.player_id}] Ativou Reação/Instant (Equipamento) -> {eq_name} (ID: {eq_id}, Custo: {eq_cost})")
                client.send_action(mode=eq_action, card_id=str(eq_id), button_input=eq_name)
                time.sleep(0.002)
                return True

    pass_btn = None
    for b in (prompt_buttons or []):
        cap = str(b.get("caption", "")).lower()
        if "pass" in cap or "ok" in cap or "done" in cap or b.get("mode") in (99, 100, 101):
            pass_btn = b
            break

    if pass_btn:
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Passou Reação ({pass_btn.get('caption', 'Pass')})")
        client.send_action(mode=pass_btn.get("mode", 99), button_input=str(pass_btn.get("buttonInput", "")))
    else:
        client.send_action(mode=99, button_input="")
    time.sleep(0.002)
    return True

def handle_arsenal_phase(client, state: dict, turn_num: int) -> bool:
    """Gerencia a fase de colocação estratégica no Arsenal (ARS)."""
    tp_raw = state.get("turnPhase", "M")
    turn_phase = str(tp_raw.get("turnPhase", "M")) if isinstance(tp_raw, dict) else str(tp_raw or "M")
    if turn_phase != "ARS":
        return False

    ars_choice = client.policy_engine.select_arsenal_card(state)
    if ars_choice:
        c_name, c_id = ars_choice
        chat_msg = f"<b>[Turno {turn_num}] 📥 Arsenal Estratégico</b> -> <b>{c_name}</b>"
        client.send_chat_log(chat_msg, highlight=True, bg_color="#312e81", text_color="#818cf8")
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Colocou no Arsenal -> {c_name}")
        client.send_action(mode=4, card_id=str(c_id), button_input=str(c_id))
        time.sleep(0.002)
        return True
    client.send_action(mode=99, button_input="")
    time.sleep(0.002)
    return True

def handle_main_action_phase(client, state: dict, turn_num: int, turn_phase: str, prompt_buttons: list, unpayable_set: set) -> bool:
    """Gerencia a fase principal de ação/ataque (M, STARTTURN, RESOLUTIONSTEP), AP, Teklovossen e seleção de ataque."""
    is_my_turn = bool(state.get("amIActivePlayer", False)) or (str(state.get("turnPlayer", "")) == str(client.player_id)) or (str(state.get("playerID", "")) == str(state.get("turnPlayer", "")))
    try:
        player_ap = int(state.get("playerAP", state.get("actionPoints", state.get("resources", {}).get("actionPoints", 1))))
    except Exception:
        player_ap = 1

    has_active_teklo = (getattr(client, "teklo_ability_active_turn", -1) == turn_num)
    if has_active_teklo:
        state["teklo_ability_active"] = True

    if is_my_turn and turn_phase in ("M", "STARTTURN", "RESOLUTIONSTEP"):
        if player_ap > 0 or has_active_teklo:
            # ── Telemetria de Plano de Turno e Ataque ──────────────
            current_plan = client.policy_engine.strategy.analyze_turn_plan(state)
            if getattr(client, "last_logged_atk_plan", None) != (turn_num, current_plan.plan_type):
                client.last_logged_atk_plan = (turn_num, current_plan.plan_type)
                plan_badge = f"<b>[Turno {turn_num}] 🎯 Plano de Ataque</b> -> <b>{current_plan.plan_type}</b> ({current_plan.reason})"
                client.send_chat_log(plan_badge, highlight=True, bg_color="#0f172a", text_color="#38bdf8")
                client.log(f"[PLANO DE ATAQUE] 🎯 Estratégia: {current_plan.plan_type} - {current_plan.reason}")

            best_attack = client.policy_engine.select_best_attack(state, unpayable_set)
            if best_attack:
                client.last_attempted_play = best_attack["name"]
                score_val = best_attack.get("score", 0.0)
                board_eval = client.evaluate_board_state(state)

                if best_attack.get("type") == "equipment_ability" and hasattr(client, "equipment_tracker"):
                    client.equipment_tracker.track_activation(
                        hero=client.hero_name,
                        eq_name=best_attack["name"],
                        turn=turn_num,
                        pre_eval=board_eval,
                    )

                # ── Capturar e registrar log ISMCTS (se presente) ────────
                ismcts_log = best_attack.pop("_ismcts_log", None)
                if ismcts_log:
                    try:
                        client.policy_engine.ismcts_logger.log(
                            ismcts_log=ismcts_log,
                            turn=turn_num,
                            phase=turn_phase,
                        )
                    except Exception:
                        pass

                # ── Classificação de Lance no Padrão de Xadrez ──────────
                chat_msg, badge_color = format_attack_chat_message(
                    turn_num=turn_num,
                    card_name=best_attack["name"],
                    score_val=score_val,
                    board_eval=board_eval,
                    mcts_sims=client.policy_engine.num_mcts_sims,
                    has_go_again=bool(best_attack.get("has_go_again")),
                    is_ismcts=bool(ismcts_log)
                )
                client.send_chat_log(chat_msg, highlight=True, bg_color="#0f172a", text_color=badge_color)

                # ── Gravação de Trajetória para Treinamento (Distilação MCTS) ──
                try:
                    from ai.model import FaBPolicyValueNetwork
                    import numpy as np
                    state_vec = FaBPolicyValueNetwork.extract_state_vector(state)
                    pol_dist = best_attack.get("_policy_dist", None)
                    if pol_dist is None:
                        pol_dist = np.zeros(32, dtype=np.float32)
                        m_idx = min(int(best_attack.get("mode", 27)), 31)
                        pol_dist[m_idx] = 1.0
                    client.trajectory.append((state_vec, pol_dist, client.player_id, board_eval))
                except Exception:
                    pass

                raw_type = str(best_attack.get("type", "ação")).lower()
                atk_type = raw_type.replace("_", " ").title()
                atk_name = best_attack["name"]
                atk_power = best_attack.get("power", 0)
                atk_cost = best_attack.get("cost", 0)
                if raw_type in ("hero_ability", "weapon_buff", "equipment_ability") and atk_power <= 0:
                    if raw_type == "hero_ability" and "teklo" in str(client.hero_name).lower():
                        client.teklo_ability_active_turn = turn_num
                    client.log(f"[AÇÃO JOGADOR {client.player_id}] Ativou -> {atk_name} (Tipo: {atk_type}, Custo: {atk_cost})")
                else:
                    client.attacks_made += 1
                    client.log(f"[AÇÃO JOGADOR {client.player_id}] Atacou com -> {atk_name} (Tipo: {atk_type}, Poder: {atk_power}, Custo: {atk_cost})")

                client.send_action(mode=best_attack["mode"], card_id=best_attack["card_id"], button_input=best_attack["name"])
                time.sleep(0.002)
                return True

    return False

def handle_pass_buttons(client, prompt_buttons: list, turn_phase: str) -> bool:
    """Passa prioridade acionando botões de prompt disponíveis ou enviando o modo padrão 99."""
    if prompt_buttons:
        for btn in prompt_buttons:
            cap = str(btn.get("caption", "")).lower()
            cap_words = set(cap.split())
            if "pass" in cap or cap_words & {"done", "ok", "end"} or cap in ("end turn", "pass priority", "end phase"):
                client.log(f"[AÇÃO JOGADOR {client.player_id}] Clicou '{btn.get('caption')}'")
                client.send_action(mode=btn.get("mode", 99), button_input=btn.get("buttonInput", ""))
                time.sleep(0.002)
                return True

    client.log(f"[AÇÃO JOGADOR {client.player_id}] Passou prioridade / Fim de Ações (Fase: {turn_phase})")
    client.send_action(mode=99, button_input="")
    time.sleep(0.01)
    return True
