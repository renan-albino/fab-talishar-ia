"""
ui/tabs/tab_play.py - Aba 1: Jogar no Talishar (Humano vs Bot AI Master).

Permite criar e gerenciar duelos humanos contra a IA no navegador, iniciar/parar
servidores locais (Vite/PHP), monitorar logs da sala e inspecionar sumários de pruning.
"""

import os
import time
import pandas as pd
import streamlit as st
import frontend_manager
from ui.helpers import (
    get_cached_services_status,
    get_cached_saved_decks,
    read_text_tail,
)


def render_tab_play(saved_decks=None, deck_options=None, fe_running=None, be_running=None):
    """Renderiza a Aba 1: Duelo Humano vs Bot AI Master no Talishar."""
    if saved_decks is None:
        saved_decks = get_cached_saved_decks()

    if deck_options is None:
        deck_options = {
            f"{d.get('name', d.get('slug'))} ({str(d.get('format', 'blitz')).upper()} - {d.get('total_cards', 0)} cartas)": d.get("slug")
            for d in saved_decks
        }

    if fe_running is None or be_running is None:
        fe_running, be_running = get_cached_services_status()

    st.subheader("🎮 Duelo Humano vs Bot AI Master no Talishar")
    st.caption("Jogue diretamente no navegador contra a Rede Neural Treinada (MCTS + PyTorch). Seus decks do workspace são automaticamente listados como favoritos no Talishar!")

    col_fe1, col_fe2, col_fe3 = st.columns([2, 1, 1])
    with col_fe1:
        st.markdown(f"""
        **Status dos Servidores:**
        - **Backend (Engine/PHP):** {'🟢 Online (Porta 8080)' if be_running else '🔴 Offline'}
        - **Frontend (Vite/React):** {'🟢 Online (Porta 3000)' if fe_running else '🔴 Offline'}
        """)
    with col_fe2:
        if not fe_running:
            if st.button("🚀 Iniciar Frontend Talishar", type="primary", use_container_width=True):
                with st.spinner("Iniciando Frontend Vite..."):
                    if frontend_manager.start_frontend():
                        st.success("Frontend iniciado com sucesso!")
                        time.sleep(1)
                        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                    else:
                        st.error("Falha ao iniciar o Frontend.")
        else:
            st.link_button("🌐 Abrir Talishar no Navegador", "http://localhost:3000", use_container_width=True)
    with col_fe3:
        if fe_running:
            if st.button("🛑 Parar Frontend", use_container_width=True):
                frontend_manager.stop_frontend()
                st.warning("Frontend finalizado.")
                time.sleep(1)
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    st.markdown("---")
    st.subheader("⚔️ Lançador Rápido: Você vs Bot AI Master")

    # ── Status de Assimilação Neural Pós-Partida ──
    from ai.training.assimilation import get_assimilation_status
    from stats_manager import get_hero_training_recommendations, get_stats_data

    assim_info = get_assimilation_status()
    is_assimilating = (assim_info.get("status") == "assimilating")
    assim_room = assim_info.get("room_id", "")

    if is_assimilating:
        st.markdown(
            f"""
            <style>
            @keyframes hourglass-spin {{
                0% {{ transform: rotate(0deg); }}
                50% {{ transform: rotate(180deg); }}
                100% {{ transform: rotate(360deg); }}
            }}
            .hourglass-anim {{
                display: inline-block;
                animation: hourglass-spin 2s infinite ease-in-out;
                font-size: 32px;
            }}
            .assim-card {{
                background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%);
                border: 1px solid #4338ca;
                border-left: 6px solid #fbbf24;
                border-radius: 10px;
                padding: 16px 20px;
                margin-bottom: 18px;
                color: #e0e7ff;
            }}
            </style>
            <div class="assim-card">
                <div style="display: flex; align-items: center; gap: 16px;">
                    <div class="hourglass-anim">⏳</div>
                    <div style="flex: 1;">
                        <h4 style="margin: 0; color: #fbbf24; font-size: 17px;">
                            Assimilação Neural em Tempo Real... (Sala #{assim_room})
                        </h4>
                        <p style="margin: 5px 0 0 0; font-size: 13.5px; color: #c7d2fe;">
                            O motor de IA está executando um <b>mini-treinamento prioritário (PER) em GPU CUDA</b> com as jogadas da sua partida.<br/>
                            Aguarde alguns segundos enquanto os novos pesos de decisão são gravados em <code>model_latest.pt</code>...
                        </p>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        # Atualização em tempo real enquanto a assimilação estiver ativa
        time.sleep(1.2)
        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    elif assim_info.get("status") == "completed":
        finished_at = assim_info.get("finished_at", 0)
        if time.time() - finished_at < 180:
            loss_val = assim_info.get("final_loss", 0.0)
            loss_str = f" (Loss final: <b>{loss_val:.4f}</b>)" if loss_val > 0 else ""
            st.markdown(
                f"""
                <div style="background: #064e3b; border: 1px solid #059669; border-left: 6px solid #34d399; border-radius: 10px; padding: 14px 18px; margin-bottom: 16px; color: #d1fae5;">
                    <div style="display: flex; align-items: center; gap: 12px;">
                        <span style="font-size: 26px;">🎉</span>
                        <div>
                            <h4 style="margin: 0; color: #34d399; font-size: 16px;">Partida #{assim_room} Assimilada com Sucesso!</h4>
                            <p style="margin: 4px 0 0 0; font-size: 13px; color: #a7f3d0;">
                                {assim_info.get('message', '')}{loss_str} A rede neural já incorporou suas decisões e está pronta para o próximo duelo!
                            </p>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Dica de Heróis Recomendados para Treino ──
    stats_data = get_stats_data()
    recs = get_hero_training_recommendations(stats_data.get("deck_stats", {}), saved_decks)
    if recs.get("top_picks"):
        top_names = ", ".join([f"`{r['deck']}`" for r in recs["top_picks"][:3]])
        st.caption(
            f"💡 **Dica de Treino Acelerado:** A IA evoluirá mais rápido se você jogar com ou contra: {top_names} "
            f"(veja a análise completa na aba **Analytics & ELO**)."
        )

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        st.markdown("##### 👤 Seu Deck (Player 1 - Humano):")
        if deck_options:
            user_deck_label = st.selectbox("Escolha seu Deck:", list(deck_options.keys()), index=0, key="play_user_deck")
            user_deck_slug = deck_options[user_deck_label]
        else:
            user_deck_slug = st.text_input("Slug do seu Deck:", value="kassai", key="play_user_deck_txt")

    with col_p2:
        st.markdown("##### 🤖 Deck do Bot AI (Player 2 - MCTS / PyTorch):")
        if deck_options:
            bot_deck_label = st.selectbox("Escolha o Deck do Bot:", list(deck_options.keys()), index=min(1, len(deck_options) - 1), key="play_bot_deck")
            bot_deck_slug = deck_options[bot_deck_label]
        else:
            bot_deck_slug = st.text_input("Slug do Deck do Bot:", value="betsy", key="play_bot_deck_txt")

    col_fmt, col_btn = st.columns([1, 2])
    with col_fmt:
        match_format = st.selectbox("Formato da Partida:", ["CC", "Blitz", "Commoner", "Silver Age"], index=0, key="play_match_format")
    with col_btn:
        st.write("")
        st.write("")
        btn_create_duel = st.button(
            "⚔️ Criar Duelo & Conectar Bot AI",
            type="primary",
            use_container_width=True,
            disabled=is_assimilating,
            help="Aguarde a assimilação neural terminar antes de criar uma nova partida" if is_assimilating else None
        )

    if btn_create_duel:
        with st.spinner("Criando sala no Talishar e inicializando o Bot AI..."):
            fmt_code = "cc" if match_format == "CC" else ("blitz" if match_format == "Blitz" else "commoner")
            res = frontend_manager.create_human_vs_bot_match(user_deck_slug, bot_deck_slug, fmt_code)
            if res.get("success"):
                st.session_state["active_human_match"] = res
                st.success(f"🎉 Partida Criada! Sala #{res['game_name']} — Bot AI Conectado com sucesso!")
            else:
                st.error(f"Erro ao criar partida: {res.get('error')}")

    if "active_human_match" in st.session_state:
        match_info = st.session_state["active_human_match"]
        st.info(f"🎮 **Partida Ativa:** Sala #{match_info['game_name']} | Seu Deck: `{match_info['player_deck']}` | Bot Deck: `{match_info['bot_deck']}`")
        st.link_button("👉 ENTRAR NA PARTIDA (Abrir Lobby no Navegador)", match_info["lobby_url"], type="primary", use_container_width=True)

    st.markdown("---")
    st.subheader("🕹️ Monitor de Sala & Análise de Pruning (Humano vs Bot)")
    st.caption("Acompanhe os logs da sala em tempo real, revise decisões do bot e copie sumários para análise e poda de jogadas (pruning).")

    # Descobrir salas de partidas Humano vs Bot
    logs_dir = os.path.abspath("logs")
    human_log_files = []
    if os.path.exists(logs_dir):
        for f in os.listdir(logs_dir):
            if f.startswith("Human_vs_Bot_") and f.endswith(".log"):
                human_log_files.append(f)

    # Ordenar pelos mais recentes
    human_log_files.sort(key=lambda x: os.path.getmtime(os.path.join(logs_dir, x)) if os.path.exists(os.path.join(logs_dir, x)) else 0, reverse=True)

    available_rooms = []
    if "active_human_match" in st.session_state:
        cur_room = str(st.session_state["active_human_match"].get("game_name", ""))
        if cur_room:
            available_rooms.append(f"Sala #{cur_room} (Partida Atual)")

    for hf in human_log_files:
        room_cand = hf.replace("Human_vs_Bot_", "").replace(".log", "")
        label = f"Sala #{room_cand}"
        if label not in available_rooms and f"Sala #{room_cand} (Partida Atual)" not in available_rooms:
            available_rooms.append(label)

    if available_rooms:
        col_r1, col_r2 = st.columns([3, 1])
        with col_r1:
            selected_room_label = st.selectbox("Selecione a Sala para Inspeção:", available_rooms, index=0, key="inspect_human_room")
            sel_room_id = selected_room_label.split(" ")[1].replace("#", "")
        with col_r2:
            st.write("")
            st.write("")
            btn_refresh_log = st.button("🔄 Atualizar Log da Sala", key="btn_refresh_human_log")

        # Arquivos de log associados à sala
        bot_proc_log = os.path.join(logs_dir, f"Human_vs_Bot_{sel_room_id}.log")
        match_feed_log = os.path.join(logs_dir, f"{sel_room_id}_match_feed.log")
        bot_debug_log = os.path.join(logs_dir, f"{sel_room_id}_AIMaster_Bot_debug.log")
        summary_log = os.path.join(logs_dir, f"{sel_room_id}_summary.log")

        col_v1, col_v2 = st.columns([1, 1])

        with col_v1:
            st.markdown(f"##### 📜 Log de Ações & Decisões da Sala #{sel_room_id}")
            log_content = ""
            for lpath in [match_feed_log, bot_proc_log, bot_debug_log]:
                if os.path.exists(lpath):
                    log_content = read_text_tail(lpath, max_lines=80)
                    if log_content:
                        break
            if log_content:
                st.code(log_content, language="text", height=320)
            else:
                st.info("Aguardando as primeiras ações da partida...")

        with col_v2:
            st.markdown(f"##### 🎯 Sumário de Pruning do Herói (Sala #{sel_room_id})")
            summary_content = ""
            if os.path.exists(summary_log):
                try:
                    with open(summary_log, "r", encoding="utf-8", errors="replace") as sf:
                        summary_content = sf.read()
                except Exception:
                    pass

            if not summary_content and log_content:
                key_decisions = [line.strip() for line in log_content.split("\n") if any(k in line for k in ["AÇÃO", "PLANO", "Bloqueio", "Atacou", "Ativou", "COMBAT CHAIN", "VENCEU", "FIM DE JOGO"])]
                summary_content = f"### Partida #{sel_room_id}\n\n" + "\n".join(f"- {d}" for d in key_decisions[-25:])

            if summary_content:
                st.text_area("Copie o sumário abaixo para solicitar análise do assistente:", value=summary_content, height=260, key="pruning_summary_box")
                st.caption("💡 **Dica de Pruning:** Envie este log no chat dizendo: *'Analise esta partida da sala para me ajudar com o pruning das jogadas do herói.'*")
            else:
                st.info("O sumário de pruning será gerado assim que o primeiro turno for concluído.")
    else:
        st.info("Nenhuma partida contra bot registrada ainda. Crie um duelo acima para visualizar os logs da sala!")

    st.markdown("---")
    st.subheader("📋 Decks do Workspace Sincronizados com o Talishar")
    st.caption("Todos os decks criados no Dashboard são automaticamente injetados no menu de Favoritos do Talishar para qualquer usuário ou convidado.")
    if saved_decks:
        df_decks = pd.DataFrame([{
            "Deck": d.get("name", d.get("slug", "")),
            "Herói": d.get("hero", d.get("data", {}).get("hero", d.get("name", "Herói"))),
            "Formato": str(d.get("format", "blitz")).upper(),
            "Total Cartas": d.get("total_cards", 0),
            "Slug": d.get("slug", "")
        } for d in saved_decks])
        st.dataframe(df_decks, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum deck salvo no workspace.")
