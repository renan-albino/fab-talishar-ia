import time
import random

def score_choice_candidate(client, candidate, turn_phase: str = "", state: dict = None, popup: dict = None) -> float:
    """Pontua um candidato para escolha múltipla ou alvo de primeira tentativa."""
    c_name = ""
    c_mode = 0
    c_override = ""
    c_label = ""
    if isinstance(candidate, dict):
        c_name = str(
            candidate.get("cardNumber")
            or candidate.get("name")
            or candidate.get("caption")
            or candidate.get("buttonInput")
            or ""
        ).lower()
        c_mode = int(candidate.get("mode", 0) or 0)
        c_override = str(candidate.get("actionDataOverride", "")).lower()
        c_label = str(candidate.get("label", "")).lower()
    else:
        c_name = str(candidate).lower()

    # Pass tem prioridade mínima a menos que seja forçado
    if c_name in ("pass", "pass priority", "cancel") or c_mode == 10000:
        return -100.0

    state = state or {}
    popup_obj = popup if isinstance(popup, dict) else {}
    p_title = str(popup_obj.get("title") or popup_obj.get("caption") or popup_obj.get("text") or "").lower()
    p_prompt = str(state.get("promptText") or "").lower()

    # Contexto de Sinking / Bottom / Discard
    is_sink = any(k in p_title or k in p_prompt for k in ["sink", "bottom", "providence"])
    is_self_discard = ("DISCARD" in turn_phase and "HAND" in turn_phase) or "discard" in p_title or "discard" in p_prompt

    # Identificar se o candidato é do Arsenal
    arsenal = state.get("playerArsenal") or state.get("playerArse") or []
    arsenal_names = [str(a.get("cardNumber", a.get("name", "")) if isinstance(a, dict) else a).lower() for a in arsenal]
    is_from_arsenal = (
        "ars" in c_override
        or "arsenal" in c_label
        or (c_name in arsenal_names and len(arsenal_names) > 0)
    )

    # Checagem de ameaça ao Arsenal (ex: Command and Conquer, Leave No Witnesses)
    active_chain = state.get("activeChainLink") or {}
    incoming_name = str(active_chain.get("cardNumber", "")).lower()
    is_arsenal_threat = len(arsenal) > 0 and any(k in incoming_name for k in [
        "command_and_conquer", "leave_no_witnesses", "wreck_havoc", "eradicate", "humble", "righteous_cleansing"
    ])

    # Se for escolha de afundar (Crown of Providence / Sink Below) e o Arsenal está em perigo iminente:
    # A carta do Arsenal DEVE ser afundada imediatamente para salvá-la e comprar uma nova carta!
    if is_sink and is_arsenal_threat:
        if is_from_arsenal:
            return 150.0  # Protege o Arsenal salvando a carta no deck e comprando 1 nova
        else:
            return -50.0  # Não afunda da mão se precisa salvar o Arsenal

    score = 0.0
    c_info = client.policy_engine.extract_card_info({"cardNumber": c_name}) if hasattr(client, "policy_engine") else {}
    score += float(c_info.get("power", 0))

    # Prioridades específicas por sinergia e valor
    if any(k in c_name for k in ["leave_no_witnesses", "codex_of_frailty", "pulsewave", "conqueror_of_the_high_seas"]):
        score += 25.0
    elif any(k in c_name for k in ["arrow", "harpoon", "bolt", "trophy"]):
        score += 20.0
    elif any(k in c_name for k in ["boom_grenade", "convection_amplifier", "penetration_script", "foundry_heart"]):
        score += 18.0
    elif any(k in c_name for k in ["riggermortis", "zenith_blade", "edict_of_steel", "sink_below"]):
        score += 15.0
    elif c_info.get("pitch") == 1:
        score += 6.0
    elif c_info.get("has_go_again"):
        score += 5.0

    # Se for para descartar ou afundar (e não era para salvar o Arsenal):
    # Inverte o score para descartar/afundar a PIOR carta (ciclando e preservando peças nobres)
    if is_self_discard or is_sink:
        # Nunca afundar o Arsenal se ele não estava sob ameaça
        if is_from_arsenal and is_sink:
            return -200.0
        return -score

    return score

def rank_choice_candidates(client, candidates: list, turn_phase: str = "", state: dict = None, popup: dict = None) -> list:
    """Ordena uma lista de candidatos do mais recomendado ao menos recomendado."""
    return sorted(candidates, key=lambda c: score_choice_candidate(client, c, turn_phase=turn_phase, state=state, popup=popup), reverse=True)

def check_and_handle_anti_loop(client, state: dict, turn_num: int, turn_phase: str, prompt_buttons: list, unpayable_set: set) -> bool:
    """Rastreia histórico de fases e estados repetidos, aplicando ações forçadas de escape de loop."""
    if not hasattr(client, "recent_phases"):
        client.recent_phases = []
        
    phase_sig = f"{turn_phase}_{getattr(client, 'last_attempted_play', '')}"
    client.recent_phases.append(phase_sig)
    if len(client.recent_phases) > 20:
        client.recent_phases.pop(0)

    # Guarda Anti-Loop: Evita ficar preso no mesmo estado
    state_sig = (turn_num, turn_phase, len(state.get("playerHand", [])), state.get("playerHealth"), state.get("opponentHealth"))
    if not hasattr(client, "last_state_sig"):
        client.last_state_sig = None
        client.consecutive_same_state = 0
        
    if client.last_state_sig == state_sig:
        client.consecutive_same_state += 1
    else:
        client.last_state_sig = state_sig
        client.consecutive_same_state = 0

    is_cyclic_loop = client.recent_phases.count(phase_sig) >= 3
    is_stuck_state = client.consecutive_same_state > 4

    if is_stuck_state or is_cyclic_loop:
        if hasattr(client, "last_attempted_play") and client.last_attempted_play:
            unpayable_set.add(client.last_attempted_play)

        # Acumula contador para evitar loop eterno de anti-loop
        client._anti_loop_streak = getattr(client, "_anti_loop_streak", 0) + 1

        if turn_phase in ("DOCRANK", "YESNO"):
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Anti-Loop ({turn_phase}) -> Forçando NO (Mode 20)")
            client.send_action(mode=20, button_input="NO")
            client.recent_phases.clear()
            client.consecutive_same_state = 0
            time.sleep(0.15)
            return True

        if turn_phase in ("MAYCHOOSEMULTIZONE", "MAYMULTICHOOSETEXT"):
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Anti-Loop ({turn_phase}) -> Pass (Mode 99)")
            client.send_action(mode=99, button_input="PASS")
            client.recent_phases.clear()
            client.consecutive_same_state = 0
            time.sleep(0.15)
            return True

        if turn_phase in ("CHOOSEMULTIZONE", "MULTICHOOSE", "MULTICHOOSEHAND"):
            # Se já falhou submeter vazio consecutivamente, força seleção do índice 0
            if client._anti_loop_streak >= 3:
                client.log(f"[AÇÃO JOGADOR {client.player_id}] Anti-Loop ({turn_phase}) -> Forçando índice 0 (Mode 19)")
                client.send_action(mode=19, chk_count=1, chk_input=["0"])
                client._anti_loop_streak = 0
            else:
                client.log(f"[AÇÃO JOGADOR {client.player_id}] Anti-Loop ({turn_phase}) -> Submetendo vazio (Mode 19)")
                client.send_action(mode=19, chk_count=0, chk_input=[])
            client.recent_phases.clear()
            client.consecutive_same_state = 0
            time.sleep(0.15)
            return True

        # MULTICHOOSETEXT: fase de seleção de texto obrigatória (ex: Fabricate do Teklovossen).
        # O servidor NÃO aceita PASS (mode=99); deve-se enviar mode=19 selecionando pelo menos 1 item.
        if turn_phase == "MULTICHOOSETEXT":
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Anti-Loop (MULTICHOOSETEXT) -> Selecionando índice 0 (Mode 19)")
            client.send_action(mode=19, chk_count=1, chk_input=["0"])
            client.recent_phases.clear()
            client.consecutive_same_state = 0
            time.sleep(0.15)
            return True

        fallback_mode = 10000 if turn_phase in ("P", "PAYGOLDORPITCH") else 99
        chosen_btn = None
        if turn_phase in ("P", "PAYGOLDORPITCH"):
            for b in prompt_buttons:
                if "cancel" in str(b.get("caption", "")).lower() or b.get("mode") == 10000:
                    chosen_btn = b
                    break
        else:
            for b in prompt_buttons:
                cap = str(b.get("caption", "")).lower()
                if ("pass" in cap or "done" in cap or "ok" in cap or b.get("mode") in (99, 101)) and "undo" not in cap:
                    chosen_btn = b
                    break

        if chosen_btn:
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Anti-Loop ({turn_phase}) -> {chosen_btn.get('caption', 'Pass')}")
            client.send_action(mode=chosen_btn.get("mode", fallback_mode), button_input=str(chosen_btn.get("buttonInput", "")))
        else:
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Anti-Loop ({turn_phase}) -> Passando/Cancelando (Mode {fallback_mode})")
            client.send_action(mode=fallback_mode, button_input="")
        client.recent_phases.clear()
        client.consecutive_same_state = 0
        time.sleep(0.15)
        return True

    return False

def handle_popup_and_choices(client, state: dict, turn_phase: str, popup: dict, prompt_buttons: list, unpayable_set: set) -> bool:
    """Trata modais, popups, inputs de nome, multichoose e escolhas de zona/texto."""
    # 0. Tratar INPUTCARDNAME
    if turn_phase == "INPUTCARDNAME":
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Nomeou carta (INPUTCARDNAME) -> 'Sink Below'")
        client.send_action(mode=30, input_text="Sink Below")
        time.sleep(0.002)
        return True

    # 1. Tratar Decisões de Crank e YESNO / Modal Triggers
    if turn_phase in ("DOCRANK", "YESNO"):
        if turn_phase == "DOCRANK":
            is_my_turn = state.get("amIActivePlayer", False) or (str(state.get("turnPlayer", "")) == str(client.player_id))
            if is_my_turn:
                choice = "YES" if random.random() < 0.75 else "NO"
                reason = "Exploração de Tempo (+1 AP)" if choice == "YES" else "Estratégia de Setup (Manter Item)"
            else:
                choice = "NO" if random.random() < 0.90 else "YES"
                reason = "Turno Oponente (Preservar Item)" if choice == "NO" else "Exploração"
                
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Decisão Crank ({reason}) -> {choice}")
            client.send_action(mode=20, button_input=choice)
            time.sleep(0.002)
            return True
        else:
            floating_res, total_res = client.policy_engine.calculate_available_resources(state)
            hand = state.get("playerHand", [])
            
            # Se não temos recursos ou cartas de pitch suficientes para custos adicionais, responder NO
            if total_res < 2 and len(hand) <= 1:
                choice = "NO"
                reason = "Recursos Insuficientes"
            elif hasattr(client, "last_attempted_play") and client.last_attempted_play in unpayable_set:
                choice = "NO"
                reason = "Carta Bloqueada Anti-Loop"
            else:
                choice = "YES"
                reason = "Aceito"
                
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Decisão YESNO ({reason}) -> {choice}")
            client.send_action(mode=20, button_input=choice)
            time.sleep(0.002)
            return True

    # 2. Tratar Popups Modais e Buscas no Deck / Zonas
    if isinstance(popup, dict) and popup.get("active"):
        p_data = popup.get("popup", {})
        p_type = p_data.get("type", "")
        
        if p_type in ("YESNO", "DOCRANK"):
            is_my_turn = state.get("amIActivePlayer", False) or (str(state.get("turnPlayer", "")) == str(client.player_id))
            choice = "YES" if (is_my_turn and random.random() < 0.75) else "NO"
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Popup {p_type} -> Respondeu {choice}")
            client.send_action(mode=20, button_input=choice)
            time.sleep(0.002)
            return True
            
        p_buttons = p_data.get("buttons", [])
        if p_buttons:
            btn = p_buttons[0]
            client.log(f"[AÇÃO JOGADOR {client.player_id}] Popup Botão -> {btn.get('caption', 'OK')}")
            client.send_action(mode=btn.get("mode", 17), button_input=btn.get("buttonInput", ""))
            time.sleep(0.002)
            return True
            
        cards_arr = p_data.get("cardsArray", [])
        if cards_arr:
            best_card = cards_arr[0]
            best_idx = 0
            for idx, c in enumerate(cards_arr):
                cid = str(c.get("cardNumber", "")).lower()
                if any(w in cid for w in ["pounder", "core", "amplifier", "grenade", "processor", "mainline", "item"]):
                    best_card = c
                    best_idx = idx
                    break
                    
            c_action = best_card.get("action", 16)
            c_id = best_card.get("actionDataOverride", best_card.get("cardNumber", str(best_idx)))
            
            form_opts = popup.get("formOptions", {})
            if form_opts.get("mode") == 19 or p_type in ("CHOOSEMULTIZONE", "MAYCHOOSEMULTIZONE"):
                client.log(f"[AÇÃO JOGADOR {client.player_id}] Escolheu {best_card.get('cardNumber')} no Deck (Mode 19 / Index {best_idx})")
                client.send_action(mode=19, chk_count=1, chk_input=[str(best_idx)])
            else:
                client.log(f"[AÇÃO JOGADOR {client.player_id}] Escolheu {best_card.get('cardNumber')} no Deck (Mode {c_action} / ID {c_id})")
                client.send_action(mode=c_action, card_id=c_id, button_input=str(c_id))
                
            time.sleep(0.002)
            return True

    # 3. Tratar Escolhas de Zonas / Gatilhos (CHOOSECARD, CHOOSETRIGGERS, BUTTONINPUT, etc.)
    if turn_phase in ("BUTTONINPUT", "BUTTONINPUTNOPASS", "CHOOSEARCANE", "CHOOSEFIRSTPLAYER", "CHOOSETRIGGERS"):
        btn_input = prompt_buttons[0].get("buttonInput", "0") if prompt_buttons else "0"
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Gatilho/Escolha -> {turn_phase}")
        client.send_action(mode=17, button_input=str(btn_input))
        time.sleep(0.002)
        return True

    if turn_phase in ("CHOOSECARD", "CHOOSECARDID", "MAYCHOOSECARD", "CHOOSEZONE", "CHOOSEDECK", "MAYCHOOSEDECK", "CHOOSEHAND", "MAYCHOOSEHAND", "CHOOSEDISCARD", "MAYCHOOSEDISCARD", "CHOOSEPERMANENT", "MAYCHOOSEPERMANENT", "CHOOSEMYSOUL", "MAYCHOOSEMYSOUL", "CHOOSETARGET"):
        p_data = popup.get("data", popup) if isinstance(popup, dict) else {}
        cards_arr = p_data.get("cardsArray", []) if isinstance(p_data, dict) else []
        if not cards_arr and "DISCARD" in turn_phase:
            cards_arr = state.get("playerDiscard", [])
        elif not cards_arr and "HAND" in turn_phase:
            cards_arr = state.get("playerHand", [])

        best_card_id = "0"
        best_btn_inp = "0"
        if cards_arr:
            best_score = -9999.0
            for idx, c_item in enumerate(cards_arr):
                score = score_choice_candidate(client, c_item, turn_phase=turn_phase, state=state, popup=popup)
                if score > best_score:
                    best_score = score
                    best_card_id = str(c_item.get("actionDataOverride", c_item.get("cardNumber", str(idx)))) if isinstance(c_item, dict) else str(idx)
                    best_btn_inp = best_card_id

        client.log(f"[AÇÃO JOGADOR {client.player_id}] Seleção Inteligente de Alvo/Zona -> {turn_phase} (CardID: {best_card_id})")
        client.send_action(mode=16, card_id=best_card_id, button_input=best_btn_inp)
        time.sleep(0.002)
        return True

    if turn_phase in ("MAYCHOOSEMULTIZONE", "CHOOSEMULTIZONE", "MULTICHOOSE", "MULTICHOOSEHAND"):
        p_data = popup.get("data", popup) if isinstance(popup, dict) else {}
        cards_arr = p_data.get("cardsArray", []) if isinstance(p_data, dict) else []
        hand = state.get("playerHand", [])
        
        form_opts = popup.get("formOptions", {}) if isinstance(popup, dict) else {}
        max_cnt = form_opts.get("maxCount", len(cards_arr) if cards_arr else len(hand))
        
        if max_cnt == 0 or (not cards_arr and not hand):
            if turn_phase == "MAYCHOOSEMULTIZONE":
                client.log(f"[AÇÃO JOGADOR {client.player_id}] Escolha Opcional ({turn_phase}) Sem opções -> Pass (Mode 99)")
                client.send_action(mode=99, button_input="PASS")
            else:
                client.log(f"[AÇÃO JOGADOR {client.player_id}] Multi-Seleção (Sem opções / Max 0) -> Confirmar vazio (Mode 19)")
                client.send_action(mode=19, chk_count=0, chk_input=[])
            time.sleep(0.002)
            return True

        # Heurística Tática: Selecionar a melhor carta de primeira tentativa
        best_idx = 0
        target_list = cards_arr if cards_arr else hand
        if len(target_list) > 1:
            best_score = -9999.0
            for c_idx, c_item in enumerate(target_list):
                score = score_choice_candidate(client, c_item, turn_phase=turn_phase, state=state, popup=popup)
                if score > best_score:
                    best_score = score
                    best_idx = c_idx

        chk_cnt = 1
        chk_inp = [str(best_idx)]

        btn_inp = "0"
        if prompt_buttons:
            for b in prompt_buttons:
                if b.get("mode") == 19 or "submit" in str(b.get("caption", "")).lower() or "ok" in str(b.get("caption", "")).lower():
                    btn_inp = str(b.get("buttonInput", "0"))
                    break
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Multi-Seleção -> {turn_phase} (Mode: 19, Count: {chk_cnt}, Pick: {chk_inp})")
        client.send_action(mode=19, button_input=btn_inp, chk_count=chk_cnt, chk_input=chk_inp)
        time.sleep(0.002)
        return True

    # Handler dedicado para MULTICHOOSETEXT / MAYMULTICHOOSETEXT
    # Usado por cartas com efeito de Fabricate (Teklovossen, Dash IO), escolhas de efeitos de texto, etc.
    if turn_phase in ("MULTICHOOSETEXT", "MAYMULTICHOOSETEXT"):
        popup_obj = popup if isinstance(popup, dict) else {}
        form_opts = popup_obj.get("formOptions", {}) if isinstance(popup_obj, dict) else {}
        min_no = int(form_opts.get("minNo", 0))
        max_no = int(form_opts.get("maxNo", form_opts.get("maxCount", 1)))

        multi_text = (
            state.get("multiChooseText")
            or popup_obj.get("multiChooseText")
            or (popup_obj.get("popup", {}) or {}).get("multiChooseText")
            or []
        )

        is_optional = (turn_phase == "MAYMULTICHOOSETEXT") or (min_no == 0)
        if is_optional and not multi_text:
            client.log(f"[AÇÃO JOGADOR {client.player_id}] {turn_phase} Opcional/Sem itens -> Pass (Mode 99)")
            client.send_action(mode=99, button_input="PASS")
            time.sleep(0.002)
            return True

        n_select = max(1, min_no) if not is_optional else min(1, max_no)
        n_available = len(multi_text) if multi_text else max(1, n_select)
        n_select = min(n_select, n_available)

        # Avaliação semântica e inteligente das opções de texto na PRIMEIRA tentativa
        def _score_text_option(opt_obj) -> float:
            raw_text = str(opt_obj.get("text", opt_obj.get("caption", opt_obj.get("label", opt_obj))) if isinstance(opt_obj, dict) else opt_obj).lower()
            s = 0.0
            if any(w in raw_text for w in ["evo", "equipment", "item", "pounder", "crank"]):
                s += 15.0
            if any(w in raw_text for w in ["draw", "action point", "resource", "steam", "counter"]):
                s += 12.0
            if any(w in raw_text for w in ["damage", "attack", "overpower", "dominate", "piercing"]):
                s += 10.0
            if any(w in raw_text for w in ["gold", "silver", "treasure", "token"]):
                s += 8.0
            if any(w in raw_text for w in ["opt", "look", "search"]):
                s += 5.0
            return s

        scored_indices = sorted(range(len(multi_text)), key=lambda i: _score_text_option(multi_text[i]), reverse=True) if multi_text else list(range(n_select))
        chk = [str(i) for i in scored_indices[:n_select]]
        client.log(f"[AÇÃO JOGADOR {client.player_id}] {turn_phase} -> Selecionando opções inteligentes {chk} (Mode 19, minNo={min_no})")
        client.send_action(mode=19, chk_count=n_select, chk_input=chk)
        time.sleep(0.002)
        return True

    if turn_phase in ("CHOOSENUMBER", "DYNPITCH", "NUMBERINPUT"):
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Entrada Numérica (Custo/Valor X) -> {turn_phase}")
        client.send_action(mode=7, button_input="0")
        time.sleep(0.002)
        return True

    if turn_phase in ("CHOOSETOP", "CHOOSEBOTTOM", "HANDTOPBOTTOM"):
        opt_cards = popup.get("cardsArray", popup.get("cards", state.get("deckTop", [])))
        if opt_cards:
            best_score = -9999.0
            card_sel = ""
            for c in opt_cards:
                sc = score_choice_candidate(client, c, turn_phase=turn_phase, state=state, popup=popup)
                if sc > best_score:
                    best_score = sc
                    card_sel = str(c.get("actionDataOverride", c.get("cardNumber", "")))
        else:
            hand = state.get("playerHand", [])
            card_sel = str(hand[0].get("cardNumber", "")) if hand else ""
        client.log(f"[AÇÃO JOGADOR {client.player_id}] Reordenação -> {turn_phase}")
        client.send_action(mode=12 if turn_phase == "CHOOSETOP" else 13, button_input=card_sel)
        time.sleep(0.002)
        return True

    return False
