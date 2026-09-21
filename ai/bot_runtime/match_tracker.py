import os
import json
from ai.equipment_learning import get_equipment_learning_engine
from ai.turn_order_learning import get_turn_order_learner
from ai.common import safe_int, safe_list

def track_tick_health_and_damage(client, state: dict, my_h: int, opp_h: int):
    """Atualiza métricas de dano causado e recebido e dispara badge de avaliação no chat."""
    if client.initial_my_health is None:
        client.initial_my_health = my_h
    if client.initial_opp_health is None:
        client.initial_opp_health = opp_h

    prev_opp_h = getattr(client, "_prev_tracked_opp_h", None)
    prev_my_h = getattr(client, "_prev_tracked_my_h", None)
    if not isinstance(prev_opp_h, (int, float)) or not isinstance(prev_my_h, (int, float)):
        client._prev_tracked_opp_h = opp_h
        client._prev_tracked_my_h = my_h
    else:
        if opp_h < prev_opp_h:
            client.damage_dealt += (prev_opp_h - opp_h)
        if my_h < prev_my_h:
            client.damage_taken += (prev_my_h - my_h)
        client._prev_tracked_opp_h = opp_h
        client._prev_tracked_my_h = my_h

    turn = safe_int(state.get("turnNo", state.get("currentTurn", 1)), default=1)
    
    # Disparar banner de avaliação de turno no chat (estilo Chess Engine)
    if turn != getattr(client, "last_chat_turn", -1):
        client.last_chat_turn = turn
        board_eval = client.evaluate_board_state(state)
        eval_str = f"+{board_eval}" if board_eval > 0 else str(board_eval)
        chat_turn_summary = f"<b>[Turno {turn}]</b> 📊 <b>AI Eval:</b> <code>{eval_str}</code> | <b>Vida:</b> {my_h} vs {opp_h} | <b>Mão:</b> {len(safe_list(state.get('playerHand')))} cartas"
        client.send_chat_log(chat_turn_summary, highlight=True, bg_color="#1e293b", text_color="#94a3b8")

def check_stalemate_and_timeout(client, state: dict, turn: int, my_h: int, opp_h: int) -> tuple[bool, str]:
    """
    Verifica condições de empate técnico (stalemate), fadiga estagnada ou estouro de turnos:
    1. Ambos os decks esgotados (0 cartas) sem dano por 3 turnos seguidos, ou deadlock de mãos e arsenais.
    2. Hard Cap de Turnos Anti-Loop (45 turnos no Blitz, 55 no CC).
    3. Estagnação prolongada (12 turnos sem dano com decks residuais <= 5).
    """
    my_deck_cnt = safe_int(state.get("playerDeckCount"), default=len(safe_list(state.get("playerDeck"))))
    opp_deck_cnt = safe_int(state.get("opponentDeckCount"), default=len(safe_list(state.get("opponentDeck"))))
    my_hand_cnt = len(safe_list(state.get("playerHand")))
    opp_hand_cnt = len(safe_list(state.get("opponentHand")))
    my_ars_cnt = len(safe_list(state.get("playerArsenal")))
    opp_ars_cnt = len(safe_list(state.get("opponentArsenal")))

    # Inicializa variáveis de controle de estagnação no bot se não existirem
    if not hasattr(client, "_last_state_health"):
        client._last_state_health = (my_h, opp_h)
        client._last_state_turn = turn
        client._stagnant_turns_count = 0

    # Atualiza a contagem a cada avanço de turno
    if turn != client._last_state_turn:
        prev_my_h, prev_opp_h = client._last_state_health
        if my_h == prev_my_h and opp_h == prev_opp_h:
            client._stagnant_turns_count += 1
        else:
            client._stagnant_turns_count = 0
        client._last_state_health = (my_h, opp_h)
        client._last_state_turn = turn

    is_stalemate = False
    stalemate_reason = ""

    # 1. Ambos os decks esgotados (0 cartas) sem dano por 3 turnos seguidos
    if my_deck_cnt == 0 and opp_deck_cnt == 0:
        if client._stagnant_turns_count >= 3:
            is_stalemate = True
            stalemate_reason = f"Decks esgotados (0 cartas) e sem alteração de vida por {client._stagnant_turns_count} turnos consecutivos"
        # Se decks em 0 e mãos e arsenais vazios (impossível jogar ações ou gerar recursos):
        elif my_hand_cnt == 0 and opp_hand_cnt == 0 and my_ars_cnt == 0 and opp_ars_cnt == 0:
            is_stalemate = True
            stalemate_reason = "Decks, mãos e arsenais completamente esgotados (deadlock de ações)"

    # 2. Hard Cap de Turnos Anti-Loop (CR/TR Tournament Round Timeout)
    max_turn_limit = 45 if client.deck_format.lower() in ("blitz", "compblitz") else 55
    if turn >= max_turn_limit:
        is_stalemate = True
        stalemate_reason = f"Limite máximo de {max_turn_limit} turnos atingido (Hard Cap Anti-Loop)"

    # 3. Estagnação prolongada (12 turnos consecutivos sem dano com decks residuais <= 5)
    if client._stagnant_turns_count >= 12 and (my_deck_cnt <= 5 or opp_deck_cnt <= 5):
        is_stalemate = True
        stalemate_reason = "Estagnação prolongada (12 turnos sem dano com decks residuais esgotando)"

    return is_stalemate, stalemate_reason

def finalize_match(client, state: dict, turn: int, my_h: int, opp_h: int, is_stalemate: bool, stalemate_reason: str):
    """Determina o vencedor, audita validade da partida, revisa blunders, salva dados de treino e atualiza estatísticas."""
    winner_id = 0
    if is_stalemate:
        client.log(f"⚠️ [FIM DE JOGO - EMPATE TÉCNICO] {stalemate_reason}!")
        client.send_chat_log(
            f"<b>[FIM DE JOGO - EMPATE TÉCNICO]</b> {stalemate_reason}. "
            f"Partida finalizada como <b>EMPATE</b> para evitar desperdício de processamento.",
            highlight=True, bg_color="#451a03", text_color="#fbbf24"
        )
        winner_id = 0
    elif my_h > 0 and opp_h <= 0:
        winner_id = client.player_id
    elif opp_h > 0 and my_h <= 0:
        winner_id = 3 - client.player_id
    elif my_h > opp_h:
        winner_id = client.player_id
    elif opp_h > my_h:
        winner_id = 3 - client.player_id

    p1_hp = my_h if client.player_id == 1 else opp_h
    p2_hp = opp_h if client.player_id == 1 else my_h
    p1_lbl = client.get_player_label(1)
    p2_lbl = client.get_player_label(2)

    # ── Identificação do tipo de partida (Humano vs Bot ou Bot vs Bot) ──
    is_vs_human = (getattr(client, "name", "") == "AIMaster_Bot" or "Human_vs_Bot" in str(client.room_id) or str(client.room_id).isdigit())
    is_human_victory = is_vs_human and (winner_id == client.player_id)

    # ── Avaliação de Partida Inválida (Empate 0 Dano ou Bot Inerte / Punching Bag) ──
    p1_init_hp = client.initial_my_health if client.player_id == 1 else (client.initial_opp_health or 40)
    p2_init_hp = client.initial_opp_health if client.player_id == 1 else (client.initial_my_health or 40)
    p1_dmg_dealt = max(0, p2_init_hp - p2_hp)
    p2_dmg_dealt = max(0, p1_init_hp - p1_hp)
    total_dmg_exchanged = p1_dmg_dealt + p2_dmg_dealt

    is_invalid_match = False
    invalid_reason = ""

    # 1. Empate com zero ou desprezível dano trocado (< 4 de dano trocado no total)
    if winner_id == 0:
        if total_dmg_exchanged < 4:
            is_invalid_match = True
            invalid_reason = "Empate 0 Dano (Mutual Stall)"
    # 2. Bot travou só apanhando (Punching Bag / Bot Inerte)
    # IMPORTANTE: Partidas contra jogadores humanos NUNCA são consideradas Punching Bag!
    elif not is_vs_human and winner_id in (1, 2):
        winner_hp = p1_hp if winner_id == 1 else p2_hp
        winner_init_hp = p1_init_hp if winner_id == 1 else p2_init_hp
        loser_hp = p2_hp if winner_id == 1 else p1_hp
        loser_id = 3 - winner_id

        # Vencedor terminou com vida intacta (sofreu zero de dano líquido)
        winner_undamaged = (winner_hp >= winner_init_hp)

        if winner_undamaged and loser_hp <= 0:
            if client.player_id == loser_id:
                if (client.attacks_made == 0 and client.damage_dealt == 0) or client.execution_exceptions_count >= 2:
                    if turn >= 5 or client.execution_exceptions_count >= 2:
                        is_invalid_match = True
                        invalid_reason = "Bot Inerte (Travou sem atacar / Punching Bag)"
            else:
                if (5 <= turn <= 8) and getattr(client, "opp_attacks_count", 0) == 0:
                    is_invalid_match = True
                    invalid_reason = "Bot Oponente Inerte (Punching Bag)"

    if is_invalid_match:
        client.log(f"⚠️ [PARTIDA ANULADA] {invalid_reason}! Trajetória descartada do ReplayBuffer e ELO protegido.")
        client.send_chat_log(
            f"⚠️ <b>[PARTIDA ANULADA]</b> {invalid_reason}. "
            f"Partida descartada do ReplayBuffer e sem alteração de ELO.",
            highlight=True, bg_color="#451a03", text_color="#fbbf24"
        )

    trajectory_samples_count = len(client.trajectory) if hasattr(client, "trajectory") and isinstance(client.trajectory, list) else 0

    if is_invalid_match and hasattr(client, "trajectory") and isinstance(client.trajectory, list):
        client.trajectory.clear()

    if not is_invalid_match and hasattr(client, "trajectory") and client.trajectory:
        try:
            from ai.experience_collector import get_global_buffer, save_trajectory_file
            from ai.blunder_reviewer import review_trajectory_for_blunders
            weights, b_stats = review_trajectory_for_blunders(
                client.trajectory,
                winner_player_id=winner_id,
                bot_player_id=client.player_id
            )
            if is_vs_human:
                from config.settings import SETTINGS
                human_mult = SETTINGS.human_loss_sample_weight if winner_id != client.player_id else SETTINGS.human_win_sample_weight
                weights = [float(w) * human_mult for w in weights]
                outcome_desc = "Vitória do Bot" if winner_id == client.player_id else "Vitória do Humano (Aprendizado de Erros e Linhas Superiores)"
                client.log(
                    f"🧠 [APRENDIZADO ACELERADO COM HUMANO] Peso amostral amplificado {human_mult:.1f}x no Replay Buffer! ({outcome_desc})"
                )
                client.send_chat_log(
                    f"🧠 <b>[APRENDIZADO ACELERADO]</b> Partida contra Humano concluída! "
                    f"Prioridade de {human_mult:.1f}x aplicada no Replay Buffer. A IA iniciou a assimilação pós-partida.",
                    highlight=True, bg_color="#1e1b4b", text_color="#a5b4fc"
                )
            if b_stats.get("blunders", 0) > 0 or b_stats.get("brilliants", 0) > 0:
                client.log(
                    f"[PER / BLUNDER REVIEW] Trajetória avaliada: {b_stats.get('blunders', 0)} blunders, "
                    f"{b_stats.get('inaccuracies', 0)} imprecisões, {b_stats.get('brilliants', 0)} viradas. "
                    f"Peso médio amostral: {b_stats.get('avg_weight', 1.0):.2f}"
                )
            save_trajectory_file(
                client.trajectory,
                winner_player_id=winner_id,
                weights=weights,
                room_id=str(client.room_id),
                player_id=client.player_id,
                epoch_ratio=getattr(client, "epoch_ratio", 0.0),
            )
            buf = get_global_buffer(client.buffer_capacity)
            buf.add_trajectory(
                client.trajectory,
                winner_player_id=winner_id,
                weights=weights,
                epoch_ratio=getattr(client, "epoch_ratio", 0.0)
            )
            buf.save()

            if is_vs_human:
                from ai.training.assimilation import trigger_human_match_assimilation
                trigger_human_match_assimilation(
                    room_id=str(client.room_id),
                    bot_player_id=client.player_id,
                    winner_id=winner_id,
                )

            client.trajectory.clear()
        except Exception as e:
            client.log(f"[ERRO BUFFER] {e}")
            if hasattr(client, "trajectory") and isinstance(client.trajectory, list):
                client.trajectory.clear()

    if hasattr(client, "equipment_tracker") and client.equipment_tracker.get_events():
        try:
            if not is_invalid_match:
                won = (winner_id == client.player_id)
                get_equipment_learning_engine().record_match_result(
                    hero_name=client.hero_name,
                    events=client.equipment_tracker.get_events(),
                    won=won,
                )
            client.equipment_tracker.clear()
        except Exception as e:
            client.log(f"[ERRO EQ STATS] {e}")

    if is_invalid_match:
        winner_str = f"Anulada ({invalid_reason})"
    elif winner_id == 1:
        winner_str = p1_lbl
    elif winner_id == 2:
        winner_str = p2_lbl
    else:
        winner_str = "Empate"

    if client.role == "host" or is_vs_human or client.player_id == 1:
        try:
            p1_d_file = f"logs/{client.room_id}_host_deck.txt"
            p2_d_file = f"logs/{client.room_id}_join_deck.txt"
            p1_d = "Humano (Você)" if is_vs_human else getattr(client, "deck_name", client.clean_deck)
            if not is_vs_human and os.path.exists(p1_d_file):
                with open(p1_d_file, encoding="utf-8") as f1:
                    p1_d = f1.read().strip()
            p2_d = getattr(client, "deck_name", client.clean_deck)
            if os.path.exists(p2_d_file):
                with open(p2_d_file, encoding="utf-8") as f2:
                    p2_d = f2.read().strip()
            
            from stats_manager import update_match_result
            update_match_result(
                room_id=client.room_id,
                p1_deck=p1_d,
                p2_deck=p2_d,
                p1_health=p1_hp,
                p2_health=p2_hp,
                total_turns=turn,
                winner_id=winner_id,
                is_human_p1=is_vs_human,
                is_invalid_match=is_invalid_match,
                invalid_reason=invalid_reason
            )
            if hasattr(client, "chosen_turn_order") and client.chosen_turn_order and not is_invalid_match:
                won = (winner_id == client.player_id)
                get_turn_order_learner().record_match_result(client.player_name or client.deck_url, client.chosen_turn_order, won)
        except Exception as e:
            client.log(f"[ERRO STATS] {e}")

        # LOG DE DESTAQUE DO VENCEDOR (Claro e Visível):
        client.log("════════════════════════════════════════════════════════════")
        client.log(f"🏆 [FIM DE JOGO] VENCEDOR: {winner_str.upper()}!")
        client.log(f"📊 [PLACAR FINAL] {p1_lbl}: {p1_hp} HP  x  {p2_lbl}: {p2_hp} HP  (Total: {turn} turnos)")
        client.log("════════════════════════════════════════════════════════════")

        try:
            summary_text = (
                f"═══════════════════════════════════════════════\n"
                f"🏆 RESULTADO DA PARTIDA: {client.room_id}\n"
                f"═══════════════════════════════════════════════\n"
                f"• Vencedor: {winner_str} (Jogador {winner_id})\n"
                f"• {p1_lbl}: {p1_hp} HP\n"
                f"• {p2_lbl}: {p2_hp} HP\n"
                f"• Duração: {turn} turnos\n"
                f"• Decisões Coletadas para Treino: {trajectory_samples_count} amostras\n"
                f"═══════════════════════════════════════════════\n"
            )
            with open(f"logs/{client.room_id}_summary.log", "w", encoding="utf-8") as f:
                f.write(summary_text)
        except Exception as e:
            client.log(f"[ERRO SUMMARY] {e}")
