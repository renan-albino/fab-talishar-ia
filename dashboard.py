import streamlit as st
import subprocess
import uuid
import json
import os
import time
import pandas as pd
import torch
from deck_parser import parse_deck_text, save_deck_to_workspace, list_saved_decks, set_active_deck, delete_saved_deck, update_saved_deck, validate_deck_against_db
from stats_manager import get_stats_data, reset_stats, delete_deck_stat
from tournament_manager import TournamentManager
from ai.trainer import GPUTrainingOrchestrator
from config.settings import SETTINGS
import frontend_manager

st.set_page_config(page_title="FaB AI Master - GPU Deep RL", layout="wide", initial_sidebar_state="expanded")
orchestrator = GPUTrainingOrchestrator()

# Título Principal com Badge de GPU e Status do Frontend
gpu_available = torch.cuda.is_available()
gpu_name = torch.cuda.get_device_name(0) if gpu_available else "CPU"

fe_running = frontend_manager.is_frontend_running()
be_running = frontend_manager.is_backend_running()

col_title1, col_title2, col_title3 = st.columns([3, 1, 1])
with col_title1:
    st.title("🤖 FaB AI Master: Deep RL & Arena")
with col_title2:
    st.write("")
    if gpu_available:
        st.success(f"🟢 GPU: **{gpu_name}**")
    else:
        st.warning("🟡 Modo CPU (CUDA não detectado)")
with col_title3:
    st.write("")
    if fe_running:
        st.success("🌐 Frontend: **Online (3000)**")
    else:
        st.info("🌐 Frontend: **Offline**")

# Carrega decks salvos
saved_decks = list_saved_decks()
deck_options = {f"{d.get('name', d.get('slug'))} ({str(d.get('format', 'blitz')).upper()} - {d.get('total_cards', 0)} cartas)": d.get('slug') for d in saved_decks}

# Abas Principais da Aplicação
tab_play, tab_arena, tab_gpu, tab_tourney, tab_decks, tab_stats, tab_ismcts = st.tabs([
    "🎮 Jogar no Talishar (Humano vs Bot)",
    "⚔️ Arena de Bots & Simulação",
    "⚡ Treinamento com GPU (Deep RL)",
    "🏆 Torneios Customizados",
    "📦 Gerenciador & Editor de Decks",
    "📈 Analytics & ELO por Deck",
    "🌐 Telemetria ISMCTS"
])

# ==============================================================================
# ABA 1: JOGAR NO TALISHAR (HUMANO VS BOT AI)
# ==============================================================================
with tab_play:
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
            bot_deck_label = st.selectbox("Escolha o Deck do Bot:", list(deck_options.keys()), index=min(1, len(deck_options)-1), key="play_bot_deck")
            bot_deck_slug = deck_options[bot_deck_label]
        else:
            bot_deck_slug = st.text_input("Slug do Deck do Bot:", value="betsy", key="play_bot_deck_txt")

    col_fmt, col_btn = st.columns([1, 2])
    with col_fmt:
        match_format = st.selectbox("Formato da Partida:", ["CC", "Blitz", "Commoner", "Silver Age"], index=0, key="play_match_format")
    with col_btn:
        st.write("")
        st.write("")
        btn_create_duel = st.button("⚔️ Criar Duelo & Conectar Bot AI", type="primary", use_container_width=True)

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
        col_enter1, col_enter2 = st.columns([2, 1])
        with col_enter1:
            st.link_button("👉 ENTRAR NA PARTIDA (Abrir no Navegador)", match_info['game_url'], type="primary", use_container_width=True)
        with col_enter2:
            st.link_button("📋 Ver Lobby da Sala", match_info['lobby_url'], use_container_width=True)

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

# ==============================================================================
# ABA 1: ARENA DE COMBATE & TABULEIRO VISUAL
# ==============================================================================
with tab_arena:
    st.subheader("⚔️ Lançador de Partidas de Alta Velocidade")
    st.caption("A Arena utiliza a IA com Rede Neural PyTorch / MCTS para guiar as decisões táticas de combate.")
    col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 2, 1])
    with col_ctrl1:
        if deck_options:
            bot1_choice = st.selectbox("Deck Bot 1 (Host):", list(deck_options.keys()), index=0, key="arena_bot1")
            bot1_deck_slug = deck_options[bot1_choice]
        else:
            bot1_deck_slug = st.text_input("Deck Bot 1:", value="calling_hamburg_1st", key="arena_bot1_txt")

    with col_ctrl2:
        if deck_options:
            bot2_choice = st.selectbox("Deck Bot 2 (Join):", list(deck_options.keys()), index=min(1, len(deck_options)-1), key="arena_bot2")
            bot2_deck_slug = deck_options[bot2_choice]
        else:
            bot2_deck_slug = st.text_input("Deck Bot 2:", value="ira_blitz_padr_o", key="arena_bot2_txt")

    with col_ctrl3:
        num_matches = st.number_input("Partidas Simultâneas:", min_value=1, max_value=100, value=1, key="arena_num_m")

    col_b1, col_b2, col_b3 = st.columns([2, 1, 1])
    with col_b1:
        btn_start = st.button("🚀 Iniciar Partidas Rápidas", type="primary", use_container_width=True)
    with col_b2:
        btn_kill = st.button("🛑 Parar / Cancelar Partidas", type="secondary", use_container_width=True)
    with col_b3:
        btn_clean = st.button("🧹 Limpar Histórico de Logs", use_container_width=True)

    if btn_kill:
        subprocess.run(["pkill", "-9", "-f", "bot_client.py"])
        st.warning("Processos de bots finalizados. Os logs e histórico foram preservados para análise!")
        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    if btn_clean:
        subprocess.run(["pkill", "-9", "-f", "bot_client.py"])
        if os.path.exists("logs"):
            for f in os.listdir("logs"):
                try:
                    os.remove(os.path.join("logs", f))
                except Exception:
                    pass
        st.session_state["rooms"] = []
        st.success("Histórico e arquivos de logs limpos com sucesso!")
        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    if btn_start:
        if "rooms" not in st.session_state:
            st.session_state["rooms"] = []
        for i in range(num_matches):
            room_id = f"Treino_{uuid.uuid4().hex[:4]}_{i}"
            st.session_state["rooms"].append(room_id)
            out1 = open(f"logs/{room_id}_Bot1_terminal.log", "w")
            subprocess.Popen(["./venv/bin/python", "bot_client.py", "--room", room_id, "--deck", f"decks/{bot1_deck_slug}.json", "--role", "host", "--name", "Bot1"], stdout=out1, stderr=out1)
            time.sleep(0.1)
            out2 = open(f"logs/{room_id}_Bot2_terminal.log", "w")
            subprocess.Popen(["./venv/bin/python", "bot_client.py", "--room", room_id, "--deck", f"decks/{bot2_deck_slug}.json", "--role", "join", "--name", "Bot2"], stdout=out2, stderr=out2)
        st.success(f"{num_matches} partida(s) de alta velocidade iniciada(s)!")

    st.divider()

    def get_available_rooms():
        discovered = set()
        if os.path.exists("logs"):
            for fname in os.listdir("logs"):
                for suffix in [
                    "_match_feed.log",
                    "_summary.log",
                    "_Bot1_debug.log",
                    "_Bot2_debug.log",
                    "_Bot1_terminal.log",
                    "_Bot2_terminal.log",
                    "_Bot1.json",
                    "_Bot2.json",
                    "_p2_ready.txt",
                    "_host_deck.txt",
                    "_join_deck.txt"
                ]:
                    if fname.endswith(suffix):
                        room_id = fname[:-len(suffix)]
                        if room_id:
                            discovered.add(room_id)
                        break
        for r in st.session_state.get("rooms", []):
            if r:
                discovered.add(r)
        return sorted(list(discovered), reverse=True)

    @st.fragment(run_every="2s")
    def render_arena_board():
        available_rooms = get_available_rooms()
        if not available_rooms:
            st.info("ℹ️ Nenhuma partida ativa no momento. Escolha os decks e clique em **'🚀 Iniciar Partidas Rápidas'**.")
            return

        room = st.selectbox("Inspecionar Sala:", available_rooms, key="arena_selected_room")
        file_b1 = f"logs/{room}_Bot1.json"
        file_b2 = f"logs/{room}_Bot2.json"
        m1 = {}
        m2 = {}
        h1 = 40; h2 = 40; phase1 = "Em Combate"
        deck1_name = "Bot 1 (Host)"; deck2_name = "Bot 2 (Joiner)"

        if os.path.exists(file_b1):
            try:
                data1 = json.load(open(file_b1))
                m1 = data1.get("metrics", {})
                h1 = int(m1.get("health", 40))
                phase1 = m1.get("phase", "Em Combate")
                deck1_name = m1.get("deck_url", "Bot 1")
            except Exception: pass

        if os.path.exists(file_b2):
            try:
                data2 = json.load(open(file_b2))
                m2 = data2.get("metrics", {})
                h2 = int(m2.get("health", 40))
                deck2_name = m2.get("deck_url", "Bot 2")
            except Exception: pass

        st.markdown("### 🏟️ Tabuleiro Visual da Partida")
        col_p1, col_vs, col_p2 = st.columns([4, 2, 4])
        with col_p1:
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 15px; border-radius: 10px; border-left: 6px solid #ef4444;">
                <h4 style="margin: 0; color: #ef4444;">🔴 {deck1_name}</h4>
                <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold;">❤️ Vida: {h1} HP</p>
                <div style="background-color: #334155; border-radius: 5px; height: 10px; margin-top: 8px;">
                    <div style="background-color: #ef4444; width: {max(0, min(100, (h1/40)*100))}%; height: 10px; border-radius: 5px;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        with col_vs:
            st.markdown(f"""
            <div style="text-align: center; padding: 15px;">
                <h2 style="margin: 0; color: #fbbf24;">VS</h2>
                <span style="font-size: 12px; color: #94a3b8;">Fase: {phase1}</span>
            </div>
            """, unsafe_allow_html=True)
        with col_p2:
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 15px; border-radius: 10px; border-right: 6px solid #3b82f6;">
                <h4 style="margin: 0; color: #3b82f6; text-align: right;">🔵 {deck2_name}</h4>
                <p style="margin: 5px 0 0 0; font-size: 24px; font-weight: bold; text-align: right;">❤️ Vida: {h2} HP</p>
                <div style="background-color: #334155; border-radius: 5px; height: 10px; margin-top: 8px;">
                    <div style="background-color: #3b82f6; width: {max(0, min(100, (h2/40)*100))}%; height: 10px; border-radius: 5px; margin-left: auto;"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.write("")
        st.markdown("#### 📜 Feed de Ações em Tempo Real (Rolável)")
        match_feed_log = f"logs/{room}_match_feed.log"
        log1 = f"logs/{room}_Bot1_debug.log"
        log2 = f"logs/{room}_Bot2_debug.log"
        combined = []
        if os.path.exists(match_feed_log):
            with open(match_feed_log, "r", encoding="utf-8", errors="ignore") as f:
                for l in f.readlines():
                    line = l.strip()
                    if line and not line.startswith("---"):
                        combined.append(line)
        else:
            for lp in [log1, log2]:
                if os.path.exists(lp):
                    with open(lp, "r", encoding="utf-8", errors="ignore") as f:
                        for l in f.readlines():
                            line = l.strip()
                            if line and not line.startswith("---"):
                                combined.append(line)
            combined.sort(key=lambda x: x[:10] if x.startswith("[") else "")

        if combined:
            import html
            formatted_logs = html.escape("\n".join(combined))
            st.markdown(f"""
            <div style="background-color: #0b1120; color: #38bdf8; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; padding: 12px; border-radius: 8px; max-height: 280px; height: 280px; overflow-y: auto; border: 1px solid #1e293b; white-space: pre-wrap; line-height: 1.45;">{formatted_logs}</div>
            """, unsafe_allow_html=True)
        else:
            st.info("Aguardando primeiras ações dos bots...")

        st.write("")
        st.markdown("#### 🎴 Configuração de Decks & Equipamentos na Match")

        def get_fallback_deck_info(d_name):
            if not d_name:
                return {}
            clean = os.path.basename(str(d_name)).replace(".json", "").lower()
            paths = [f"decks/{clean}.json", f"Talishar/decks/{clean}.json", f"{clean}.json", "deck.json"]
            for p in paths:
                if os.path.exists(p):
                    try:
                        d_obj = json.load(open(p, encoding="utf-8"))
                        cards = d_obj.get("cards", [])
                        eq = []
                        main = []
                        hero = ""
                        for c in cards:
                            cid = c.get("identifier", "") if isinstance(c, dict) else str(c)
                            tot = int(c.get("count", c.get("total", 1))) if isinstance(c, dict) else 1
                            cid_l = cid.lower()
                            if not hero and (any(h in cid_l for h in ["vynnset", "hala", "dash", "mario", "arakni", "jarl", "oscilio", "dorinthea", "katsu", "rhinar", "bravo", "fai", "briar", "zen", "nuu", "enigma", "aurora", "florian", "verdance", "gravy"]) or "hero" in cid_l):
                                hero = cid
                            elif any(k in cid_l for k in ["boots", "crown", "helm", "hood", "gloves", "arms", "chest", "tunic", "blade", "sword", "shot", "hammer", "flail", "weapon", "quillhand", "carapace", "fold", "steps", "mask", "dynamo", "respirator", "whisperers", "fellingsong", "grimoire"]):
                                eq.append(cid)
                            elif cid != hero:
                                main.extend([cid] * tot)
                        return {
                            "hero": hero if hero else (cards[0].get("identifier", "Herói") if cards else "Herói"),
                            "equipment": {
                                "head": next((e for e in eq if any(h in e for h in ["crown", "helm", "hood", "mask", "kabuto", "head", "fold", "respirator"])), "-"),
                                "chest": next((e for e in eq if any(h in e for h in ["chest", "tunic", "carapace", "threads", "robe", "heart", "vest", "grains", "bloodspill"])), "-"),
                                "arms": next((e for e in eq if any(h in e for h in ["gloves", "arms", "rerebrace", "quillhand", "hook", "gauntlet", "knives", "shuko"])), "-"),
                                "legs": next((e for e in eq if any(h in e for h in ["boots", "legs", "steps", "creepers", "dynamo", "mountain", "whisperers"])), "-"),
                                "weapons": [e for e in eq if any(h in e for h in ["blade", "sword", "shot", "hammer", "flail", "weapon", "klaive", "harpoon", "compass", "fellingsong", "grimoire"])]
                            },
                            "main_deck_count": len(main),
                            "sideboard_count": max(0, len(main) - 60) if len(main) > 60 else 0,
                            "sideboard_cards": main[60:] if len(main) > 60 else []
                        }
                    except Exception:
                        pass
            return {}

        sb1 = m1.get("sideboard_info", {})
        sb2 = m2.get("sideboard_info", {})
        if not sb1 or not sb1.get("main_deck_count"):
            sb1 = get_fallback_deck_info(deck1_name)
        if not sb2 or not sb2.get("main_deck_count"):
            sb2 = get_fallback_deck_info(deck2_name)
        
        col_sb1, col_sb2 = st.columns(2)
        with col_sb1:
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 14px; border-radius: 8px; border-left: 4px solid #ef4444;">
                <h5 style="margin: 0 0 10px 0; color: #f87171;">🔴 {deck1_name} ({sb1.get('hero', 'Herói')})</h5>
                <p style="margin: 4px 0; font-size: 13px;"><b>🗃️ Deck Principal Subido:</b> <span style="color: #4ade80; font-weight: bold;">{sb1.get('main_deck_count', '-')} cartas</span></p>
                <p style="margin: 4px 0; font-size: 13px;"><b>📦 Cartas de Fora (Sideboard):</b> <span style="color: #fbbf24; font-weight: bold;">{sb1.get('sideboard_count', '-')} cartas</span></p>
                <div style="margin-top: 8px; font-size: 12px; color: #cbd5e1;">
                    <b>🛡️ Equipamentos Selecionados:</b>
                    <ul style="margin: 4px 0 0 15px; padding: 0;">
                        <li>👑 <b>Cabeça:</b> <code>{sb1.get('equipment', {}).get('head', '-')}</code></li>
                        <li>🦺 <b>Peitoral:</b> <code>{sb1.get('equipment', {}).get('chest', '-')}</code></li>
                        <li>🧤 <b>Braços:</b> <code>{sb1.get('equipment', {}).get('arms', '-')}</code></li>
                        <li>👢 <b>Pernas:</b> <code>{sb1.get('equipment', {}).get('legs', '-')}</code></li>
                        <li>⚔️ <b>Arma(s):</b> <code>{', '.join(sb1.get('equipment', {}).get('weapons', [])) if sb1.get('equipment', {}).get('weapons') else '-'}</code></li>
                    </ul>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if sb1.get("sideboard_cards"):
                with st.expander(f"📦 Ver {sb1.get('sideboard_count')} Cartas de Fora (P1)"):
                    st.caption(", ".join(sb1.get("sideboard_cards", [])))

        with col_sb2:
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 14px; border-radius: 8px; border-left: 4px solid #3b82f6;">
                <h5 style="margin: 0 0 10px 0; color: #60a5fa;">🔵 {deck2_name} ({sb2.get('hero', 'Herói')})</h5>
                <p style="margin: 4px 0; font-size: 13px;"><b>🗃️ Deck Principal Subido:</b> <span style="color: #4ade80; font-weight: bold;">{sb2.get('main_deck_count', '-')} cartas</span></p>
                <p style="margin: 4px 0; font-size: 13px;"><b>📦 Cartas de Fora (Sideboard):</b> <span style="color: #fbbf24; font-weight: bold;">{sb2.get('sideboard_count', '-')} cartas</span></p>
                <div style="margin-top: 8px; font-size: 12px; color: #cbd5e1;">
                    <b>🛡️ Equipamentos Selecionados:</b>
                    <ul style="margin: 4px 0 0 15px; padding: 0;">
                        <li>👑 <b>Cabeça:</b> <code>{sb2.get('equipment', {}).get('head', '-')}</code></li>
                        <li>🦺 <b>Peitoral:</b> <code>{sb2.get('equipment', {}).get('chest', '-')}</code></li>
                        <li>🧤 <b>Braços:</b> <code>{sb2.get('equipment', {}).get('arms', '-')}</code></li>
                        <li>👢 <b>Pernas:</b> <code>{sb2.get('equipment', {}).get('legs', '-')}</code></li>
                        <li>⚔️ <b>Arma(s):</b> <code>{', '.join(sb2.get('equipment', {}).get('weapons', [])) if sb2.get('equipment', {}).get('weapons') else '-'}</code></li>
                    </ul>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if sb2.get("sideboard_cards"):
                with st.expander(f"📦 Ver {sb2.get('sideboard_count')} Cartas de Fora (P2)"):
                    st.caption(", ".join(sb2.get("sideboard_cards", [])))

    render_arena_board()

# ==============================================================================
# ABA 2: TREINAMENTO COM GPU (DEEP RL + ROTAÇÃO DE DECKS)
# ==============================================================================
def get_suggested_training_profile(device_str: str, mode: str = "balanced") -> dict:
    """
    Calcula parâmetros de treinamento sugeridos:
      - mode='balanced': ~75-80% de carga segura (permite uso normal do PC, navegador, vídeos, sem engasgos).
      - mode='turbo': ~95% de carga máxima (ideal para treino noturno, ausente ou remoto, extraindo todo o potencial do hardware).
    """
    is_gpu = "cuda" in device_str.lower() and torch.cuda.is_available()
    try:
        from config.settings import SETTINGS
        vram_gb = getattr(SETTINGS, "vram_gb", 0.0)
        cpu_cores = getattr(SETTINGS, "cpu_logical", 4)
        gpu_name = getattr(SETTINGS, "gpu_name", "GPU")
    except Exception:
        vram_gb = 6.0 if torch.cuda.is_available() else 0.0
        cpu_cores = os.cpu_count() or 4
        gpu_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "GPU"

    is_turbo = (mode == "turbo")

    if not is_gpu:
        if is_turbo:
            turbo_workers = max(1, cpu_cores - 1)
            return {
                "device_label": f"CPU ({cpu_cores} threads)",
                "mode_name": "🔥 Modo Turbo CPU (~95% Carga)",
                "workers": turbo_workers,
                "batch_size": 256,
                "mcts_sims": 25,
                "save_interval": 25,
                "use_fp16": False,
                "buffer_capacity": 100000,
                "description": f"🔥 Modo Turbo CPU (~95% carga) • {turbo_workers} workers em paralelo • MCTS 25 • Rendimento máximo sem uso interativo do PC."
            }
        else:
            safe_workers = max(1, min(3, (cpu_cores - 2) // 3))
            return {
                "device_label": f"CPU ({cpu_cores} threads)",
                "mode_name": "⚖️ Modo Equilibrado CPU (~60% Carga)",
                "workers": safe_workers,
                "batch_size": 128,
                "mcts_sims": 15,
                "save_interval": 15,
                "use_fp16": False,
                "buffer_capacity": 50000,
                "description": f"⚖️ Modo CPU Seguro (~60% carga) • {safe_workers} workers • 15 MCTS sims • Sistema 100% livre para uso normal do PC."
            }

    # Perfil para GPU calibrado por faixa de VRAM:
    if vram_gb <= 6.5:
        # Ex: GTX 1660 Super (6.4 GB VRAM)
        if is_turbo:
            turbo_workers = max(2, min(10, cpu_cores - 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "🔥 Modo Turbo GPU (~95% Carga)",
                "workers": turbo_workers,
                "batch_size": 512,
                "mcts_sims": 50,
                "save_interval": 30,
                "use_fp16": True,
                "buffer_capacity": 250000,
                "description": f"🔥 Turbo Máximo (~95% GPU) • {turbo_workers} workers simultâneos • Batch 512 (~5.0 GB VRAM) • MCTS 50 • Máximo throughput para treino noturno ou remoto."
            }
        else:
            safe_workers = max(1, min(4, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~75% Carga)",
                "workers": safe_workers,
                "batch_size": 256,
                "mcts_sims": 30,
                "save_interval": 20,
                "use_fp16": True,
                "buffer_capacity": 100000,
                "description": f"⚖️ {gpu_name} (~75% VRAM) • {safe_workers} workers • Batch 256 • ~4 GB VRAM livres para uso geral do PC."
            }
    elif vram_gb <= 12.5:
        # Ex: RTX 3060, RTX 4060 Ti, RTX 4070
        if is_turbo:
            turbo_workers = max(4, min(14, cpu_cores - 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "🔥 Modo Turbo GPU (~95% Carga)",
                "workers": turbo_workers,
                "batch_size": 1024,
                "mcts_sims": 75,
                "save_interval": 35,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"🔥 Turbo Máximo (~95% carga) • {turbo_workers} workers • Batch 1024 • MCTS 75 • Treinamento de alta densidade sem travas."
            }
        else:
            safe_workers = max(2, min(6, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~80% Carga)",
                "workers": safe_workers,
                "batch_size": 512,
                "mcts_sims": 45,
                "save_interval": 25,
                "use_fp16": True,
                "buffer_capacity": 250000,
                "description": f"⚖️ {gpu_name} (~80% carga) • {safe_workers} workers • Batch 512 • Excelente velocidade com folga de sistema."
            }
    elif vram_gb <= 20.0:
        # Ex: RX 9070 XT 16GB, RTX 4080 16GB
        if is_turbo:
            turbo_workers = max(6, min(18, cpu_cores - 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "🔥 Modo Turbo GPU (~95% Carga)",
                "workers": turbo_workers,
                "batch_size": 2048,
                "mcts_sims": 100,
                "save_interval": 40,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"🔥 Turbo Máximo (~95% carga) • {turbo_workers} workers • Batch 2048 • MCTS 100 • Rendimento industrial para 16 GB de VRAM."
            }
        else:
            safe_workers = max(2, min(8, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~80% Carga)",
                "workers": safe_workers,
                "batch_size": 1024,
                "mcts_sims": 60,
                "save_interval": 30,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"⚖️ {gpu_name} (~80% carga) • {safe_workers} workers • Batch 1024 • Alto rendimento com folga para multitarefa."
            }
    else:
        # Ex: RTX 5090 32GB, RTX 4090 24GB
        if is_turbo:
            turbo_workers = max(8, min(24, cpu_cores - 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "🔥 Modo Turbo GPU (~95% Carga)",
                "workers": turbo_workers,
                "batch_size": 4096,
                "mcts_sims": 150,
                "save_interval": 50,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"🔥 Turbo Máximo (~95% carga) • {turbo_workers} workers • Batch 4096 • MCTS 150 • Supercomputação para Alpha-Level AI."
            }
        else:
            safe_workers = max(4, min(12, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~80% Carga)",
                "workers": safe_workers,
                "batch_size": 2048,
                "mcts_sims": 100,
                "save_interval": 40,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"⚖️ {gpu_name} (~80% carga) • {safe_workers} workers • Batch 2048 • Capacidade extrema sem travar o desktop."
            }

with tab_gpu:
    st.subheader("⚡ Painel de Treinamento Autônomo com GPU")
    st.markdown("Acelere o aprendizado da rede neural com **Self-Play em lote**, rotação dinâmica de decks e amostragem na GPU.")

    all_deck_keys = list(deck_options.keys())
    selected_training_decks = st.multiselect(
        "🎴 Selecione os Decks que a IA irá usar no Treinamento (Rotativo):",
        all_deck_keys,
        default=all_deck_keys[:min(3, len(all_deck_keys))]
    )

    device_options = ["cuda:0 (GPU)", "cpu"] if gpu_available else ["cpu"]

    if "training_preset_mode" not in st.session_state:
        st.session_state["training_preset_mode"] = "balanced"

    def update_hardware_suggestions(mode: str = None):
        if mode is None:
            mode = st.session_state.get("training_preset_mode", "balanced")
        chosen = st.session_state.get("train_dev_select", device_options[0])
        prof = get_suggested_training_profile(chosen, mode=mode)
        st.session_state["train_workers"] = prof["workers"]
        st.session_state["train_batch_size"] = prof["batch_size"]
        st.session_state["train_mcts_sims"] = prof["mcts_sims"]
        st.session_state["train_save_interval"] = prof["save_interval"]
        st.session_state["train_fp16"] = prof["use_fp16"]
        st.session_state["train_buffer_cap"] = prof["buffer_capacity"]

    if "train_workers" not in st.session_state:
        update_hardware_suggestions("balanced")

    with st.expander("⚙️ Configurações Avançadas de Hardware e Treinador", expanded=not orchestrator.is_running):
        col_dev_sel, col_mode_status = st.columns([2, 2])
        with col_dev_sel:
            train_dev = st.selectbox(
                "Dispositivo de Treino:",
                device_options,
                index=0 if gpu_available else 0,
                key="train_dev_select",
                on_change=lambda: update_hardware_suggestions()
            )
        with col_mode_status:
            current_mode = st.session_state.get("training_preset_mode", "balanced")
            st.write("")
            if current_mode == "turbo":
                st.markdown("**Modo de Carga Ativo:** 🚀 `🔥 TURBO MÁXIMO (~95%)`")
            else:
                st.markdown("**Modo de Carga Ativo:** 🛡️ `⚖️ EQUILIBRADO (~80%)`")

        # Botões de Seleção de Perfil (Equilibrado vs Turbo Máximo)
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            if st.button("⚖️ Ativar Perfil Equilibrado (~80% Carga - Uso Normal do PC)", use_container_width=True):
                st.session_state["training_preset_mode"] = "balanced"
                update_hardware_suggestions("balanced")
                st.toast("Modo Equilibrado ativado (~80% de carga segura).", icon="⚖️")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
        with col_p2:
            if st.button("🔥 Ativar Perfil Turbo Máximo (~95% Carga - Noturno / Remoto)", use_container_width=True, type="primary"):
                st.session_state["training_preset_mode"] = "turbo"
                update_hardware_suggestions("turbo")
                st.toast("🔥 Modo Turbo Máximo ativado (~95% de poder bruto)! Otimizado para treino noturno ou remoto.", icon="🔥")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

        active_prof = get_suggested_training_profile(train_dev, mode=st.session_state.get("training_preset_mode", "balanced"))
        if st.session_state.get("training_preset_mode", "balanced") == "turbo":
            st.warning(f"🔥 **{active_prof['mode_name']} ({active_prof['device_label']}):** {active_prof['description']}")
        else:
            st.info(f"💡 **{active_prof['mode_name']} ({active_prof['device_label']}):** {active_prof['description']}")

        col_g1, col_g2, col_g3 = st.columns(3)
        with col_g1:
            workers_count = st.slider(
                "Partidas Simultâneas de Self-Play:",
                min_value=1,
                max_value=24,
                key="train_workers",
                help="Quantidade de duelos simultâneos. No Modo Turbo, escala até 95% dos núcleos lógicos da máquina."
            )
            batch_sz = st.select_slider(
                "Batch Size do Treinador:",
                options=[32, 64, 128, 256, 512, 1024, 2048, 4096],
                key="train_batch_size",
                help="Tamanho do lote para atualização de gradientes na GPU/CPU. No Turbo, ocupa até 95% da VRAM livre."
            )
        with col_g2:
            lr_val = st.select_slider(
                "Learning Rate (Taxa de Aprendizado):",
                options=[0.0001, 0.0003, 0.001, 0.003],
                value=0.0003,
                key="train_lr"
            )
            mcts_sims = st.slider(
                "Simulações MCTS por Jogada:",
                min_value=5,
                max_value=200,
                key="train_mcts_sims",
                help="Profundidade da busca ISMCTS. Mais simulações aumentam a qualidade tática das partidas."
            )
            buffer_cap = st.select_slider(
                "Capacidade do Replay Buffer:",
                options=[10000, 50000, 100000, 250000, 500000],
                key="train_buffer_cap"
            )
        with col_g3:
            use_fp16 = st.toggle(
                "Aceleração Mixed Precision (FP16)",
                key="train_fp16",
                help="Acelera cálculos na GPU e economiza VRAM. Desativado automaticamente no modo CPU."
            )
            auto_save = st.toggle("Auto-Save de Checkpoints (.pt)", value=True, key="train_auto_save")
            save_interval = st.number_input(
                "Salvar Checkpoint a cada N partidas:",
                min_value=5,
                max_value=100,
                key="train_save_interval",
                help="Frequência de gravação de novos checkpoints em disco."
            )

    col_t_btn1, col_t_btn2 = st.columns([1, 1])
    with col_t_btn1:
        if not orchestrator.is_running:
            if st.button("🚀 Iniciar Treinamento Contínuo com GPU", type="primary", use_container_width=True):
                dev_str = "cuda:0" if "cuda" in train_dev else "cpu"
                deck_slugs = [deck_options[k] for k in selected_training_decks] if selected_training_decks else list(deck_options.values())
                orchestrator.start({
                    "device": dev_str,
                    "num_workers": workers_count,
                    "batch_size": batch_sz,
                    "learning_rate": lr_val,
                    "mcts_sims": mcts_sims,
                    "buffer_capacity": buffer_cap,
                    "fp16": use_fp16,
                    "save_interval_games": save_interval,
                    "training_decks": deck_slugs
                })
                st.toast("⚡ Treinador de Deep RL iniciado com sucesso!", icon="🚀")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
        else:
            if st.button("🛑 Parar Treinamento com GPU", type="secondary", use_container_width=True):
                orchestrator.stop()
                st.toast("Treinamento finalizado.", icon="🛑")
                st.warning("Treinador pausado com sucesso!")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    with col_t_btn2:
        if st.button("💾 Salvar Checkpoint Manual do Modelo", use_container_width=True):
            orchestrator.save_metrics()
            st.toast("Checkpoint manual e Replay Buffer salvos!", icon="💾")

    # Fragmento de Atualização em Tempo Real (a cada 2 segundos)
    @st.fragment(run_every="2s")
    def render_gpu_live_telemetry():
        orchestrator.load_metrics()
        st.divider()
        
        # Status Ativo da Sessão de Treino
        if orchestrator.is_running:
            cfg = orchestrator.config
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid #22c55e; margin-bottom: 15px;">
                <h4 style="margin: 0; color: #22c55e;">🟢 Treinamento em Andamento (GPU Ativa)</h4>
                <p style="margin: 6px 0 0 0; color: #cbd5e1; font-size: 14px;">
                    <b>Dispositivo:</b> {cfg.get('device')} | <b>Batch:</b> {cfg.get('batch_size')} | <b>LR:</b> {cfg.get('learning_rate')} | <b>MCTS Sims:</b> {cfg.get('mcts_sims')} | <b>FP16:</b> {cfg.get('fp16')}<br>
                    <b>Confronto Atual em Execução:</b> <code>{orchestrator.stats.get('active_matchup', 'Rotativo')}</code>
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("### 📊 Telemetria de Treinamento em Tempo Real")
        st_m1, st_m2, st_m3, st_m4 = st.columns(4)
        st_m1.metric("Partidas Disputadas", orchestrator.stats.get("total_games", 0))
        st_m2.metric("Amostras no Replay Buffer", orchestrator.stats.get("samples_collected", 0))
        st_m3.metric("Policy Loss (Ação)", orchestrator.stats.get("policy_loss", 0.0))
        st_m4.metric("Value Loss (Vitória MSE)", orchestrator.stats.get("value_loss", 0.0))

        # Histórico de Loss
        history = orchestrator.stats.get("history", [])
        if len(history) > 1:
            df_hist = pd.DataFrame(history)[["epoch", "policy_loss", "value_loss", "total_loss"]].set_index("epoch")
            df_hist.columns = ["Policy Loss", "Value MSE Loss", "Total Loss"]
            st.line_chart(df_hist)

        # Resumo da Última Partida Concluída
        st.markdown("#### 📜 Resumo da Última Partida de Treino")
        last_sum = orchestrator.stats.get("last_summary", "Nenhuma partida registrada ainda.")
        st.code(last_sum)

        # Histórico Recente de Confrontos (movido para aba GPU)
        stats_data = get_stats_data()
        recent = stats_data.get("recent_matches", [])
        if recent:
            st.markdown("#### 📜 Histórico Recente de Confrontos (Treino)")
            df_recent = pd.DataFrame(recent)
            df_recent.columns = ["Sala", "Data/Hora", "Vencedor", "Deck Bot 1", "Deck Bot 2", "Vida B1", "Vida B2", "Turnos"]
            st.dataframe(df_recent, use_container_width=True)

    render_gpu_live_telemetry()

# ==============================================================================
# ABA 3: TORNEIOS CUSTOMIZADOS
# ==============================================================================
with tab_tourney:
    st.subheader("🏆 Organizador de Torneios Customizados")
    st.markdown("Selecione os decks aprovados que você deseja incluir no torneio.")

    if not deck_options:
        st.warning("Nenhum deck cadastrado ainda. Importe seus decks na aba **'📦 Gerenciador & Editor de Decks'**.")
    else:
        col_t1, col_t2 = st.columns([2, 1])
        with col_t1:
            tourney_name = st.text_input("Nome do Torneio:", value="Torneio Personalizado 2026")
            all_deck_keys = list(deck_options.keys())
            selected_tourney_decks = st.multiselect("Selecione os Decks Participantes:", all_deck_keys, default=[])
            st.caption(f"Decks selecionados: **{len(selected_tourney_decks)}**")
        with col_t2:
            tourney_format = st.selectbox("Formato do Torneio:", ["Round-Robin (Todos contra Todos)", "Sistema Suíço (Swiss)"])
            st.write(""); st.write("")
            btn_start_tourney = st.button("🏁 Iniciar Torneio", type="primary", use_container_width=True)

        if btn_start_tourney:
            if len(selected_tourney_decks) < 2:
                st.warning("Selecione pelo menos 2 decks para iniciar o torneio.")
            else:
                deck_slugs = [deck_options[k] for k in selected_tourney_decks]
                fmt = "round_robin" if "Round-Robin" in tourney_format else "swiss"
                tm = TournamentManager(tournament_name=tourney_name, format_type=fmt)
                tm.setup_tournament(deck_slugs)
                with st.spinner(f"Executando confrontos do torneio ({len(tm.matches)} partidas)..."):
                    tm.run_all_matches()
                st.success(f"Torneio **{tourney_name}** concluído com sucesso!")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    res_path = "data/tournament_results.json"
    if os.path.exists(res_path):
        st.divider()
        try:
            with open(res_path, "r", encoding="utf-8") as f: t_data = json.load(f)
            st.markdown(f"### 📊 Resultados do Torneio: **{t_data.get('tournament_name')}** ({t_data.get('date')})")
            col_res1, col_res2 = st.columns([3, 2])
            with col_res1:
                st.markdown("#### 🥇 Tabela de Classificação")
                standings = t_data.get("standings", [])
                if standings:
                    df_std = pd.DataFrame(standings)[["name", "hero", "points", "wins", "losses", "elo"]]
                    df_std.columns = ["Deck / Jogador", "Herói", "Pontos", "Vitórias", "Derrotas", "Rating ELO"]
                    st.dataframe(df_std, use_container_width=True)
            with col_res2:
                st.markdown("#### ⚔️ Matriz de Matchups")
                matches = t_data.get("matches", [])
                participants = [s["name"] for s in standings]
                matrix = {p1: {p2: "-" for p2 in participants} for p1 in participants}
                for m in matches:
                    if m.get("status") == "Concluída" and m.get("winner"):
                        d1 = m["deck1_name"]; d2 = m["deck2_name"]
                        if d1 in matrix and d2 in matrix:
                            if m["winner"] == d1:
                                matrix[d1][d2] = "🟢 Vit"; matrix[d2][d1] = "🔴 Der"
                            else:
                                matrix[d2][d1] = "🟢 Vit"; matrix[d1][d2] = "🔴 Der"
                st.dataframe(pd.DataFrame(matrix), use_container_width=True)
        except Exception: pass

# ==============================================================================
# ABA 4: GERENCIADOR & EDITOR DE DECKS
# ==============================================================================
with tab_decks:
    st.subheader("📦 Gerenciador & Editor de Decks (FaBrary / Workspace)")
    tab_list, tab_edit_deck, tab_import = st.tabs(["📚 Decks Salvos & Exclusão", "✏️ Editor de Deck", "📥 Importar do FaBrary"])

    with tab_list:
        if saved_decks:
            st.markdown("### 📋 Decks Disponíveis no Workspace")
            for d in saved_decks:
                with st.container():
                    c_d1, c_d2, c_d3, c_d4 = st.columns([3, 2, 2, 2])
                    with c_d1:
                        st.markdown(f"**{d['name']}**")
                        st.caption(f"Slug: `{d['slug']}`")
                    with c_d2:
                        st.write(f"🏷️ **Formato:** {d['format'].upper()}")
                    with c_d3:
                        st.write(f"🃏 **Total:** {d['total_cards']} cartas")
                    with c_d4:
                        if st.button(f"🗑️ Deletar", key=f"del_{d['slug']}", type="secondary"):
                            delete_saved_deck(d["slug"])
                            st.toast(f"Deck '{d['name']}' deletado!", icon="🗑️")
                            st.success(f"Deck **{d['name']}** deletado com sucesso!")
                            st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                    st.divider()
        else:
            st.info("Nenhum deck cadastrado ainda. Use a aba ao lado para importar seu primeiro deck.")

    with tab_edit_deck:
        if saved_decks:
            edit_choice = st.selectbox("Selecione o Deck para Editar:", list(deck_options.keys()), key="deck_editor_select")
            edit_slug = deck_options[edit_choice]
            deck_target = next((d for d in saved_decks if d["slug"] == edit_slug), None)
            if deck_target:
                d_curr = deck_target["data"]
                c_ed1, c_ed2 = st.columns([2, 1])
                with c_ed1:
                    new_name_val = st.text_input("Nome do Deck:", value=d_curr.get("name", ""), key=f"ed_name_{edit_slug}")
                with c_ed2:
                    new_fmt_val = st.selectbox("Formato:", ["cc", "blitz"], index=0 if d_curr.get("format") == "cc" else 1, key=f"ed_fmt_{edit_slug}")
                
                st.markdown("#### 🃏 Lista de Cartas do Deck (JSON / Quantidades):")
                cards_raw_str = json.dumps(d_curr.get("cards", []), indent=2)
                edited_cards_text = st.text_area("Estrutura das Cartas:", value=cards_raw_str, height=260, key=f"ed_cards_{edit_slug}")
                
                c_save_b1, c_save_b2 = st.columns([1, 1])
                with c_save_b1:
                    if st.button("💾 Salvar Alterações no Deck", type="primary", use_container_width=True):
                        try:
                            parsed_cards = json.loads(edited_cards_text)
                            update_saved_deck(edit_slug, new_name_val, new_fmt_val, parsed_cards)
                            st.toast(f"Deck '{new_name_val}' atualizado com sucesso!", icon="💾")
                            st.success(f"Alterações salvas no deck **{new_name_val}**!")
                            st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                        except Exception as e:
                            st.error(f"Erro ao salvar alterações no JSON das cartas: {e}")
                with c_save_b2:
                    if st.button("🌟 Definir como Deck Ativo Padrão", use_container_width=True):
                        set_active_deck(d_curr)
                        st.toast(f"Deck '{d_curr.get('name')}' definido como padrão!", icon="🌟")
        else:
            st.info("Nenhum deck para editar.")

    with tab_import:
        st.markdown("Cole abaixo o texto exportado diretamente do **FaBrary** (ou FabDB):")
        col_imp1, col_imp2 = st.columns([3, 2])
        
        # Manter texto em session_state caso ocorra erro de validação
        if "import_text_val" not in st.session_state:
            st.session_state["import_text_val"] = ""
        if "import_name_val" not in st.session_state:
            st.session_state["import_name_val"] = ""
        if "import_errors" not in st.session_state:
            st.session_state["import_errors"] = []

        with col_imp1:
            deck_text_input = st.text_area(
                "Texto do Deck (FaBrary / FabDB):", height=230,
                value=st.session_state["import_text_val"],
                placeholder="""Name: Calling: Hamburg 1st 🇩🇪\nHero: Dash I/O\nFormat: Classic Constructed\n\nArena cards\n1x Achilles Accelerator\n1x Symbiosis Shot\n\nDeck cards\n3x Backup Protocol: RED (red)\n3x Zero to Sixty (red)"""
            )
            col_b1, col_b2 = st.columns([2, 1])
            with col_b1:
                custom_name = st.text_input("Nome Customizado do Deck (opcional):", value=st.session_state["import_name_val"], placeholder="Ex: Dash CC Pro")
            with col_b2:
                st.write(""); st.write("")
                btn_save = st.button("💾 Importar e Validar Deck", type="primary", use_container_width=True)

            if btn_save:
                if deck_text_input and deck_text_input.strip():
                    parsed = parse_deck_text(deck_text_input, default_name=custom_name if custom_name else "Meu Deck")
                    if custom_name and custom_name.strip():
                        parsed["name"] = custom_name.strip()
                        
                    is_valid, errors, meta_info = validate_deck_against_db(parsed)
                    if not is_valid:
                        st.session_state["import_text_val"] = deck_text_input
                        st.session_state["import_name_val"] = custom_name
                        st.session_state["import_errors"] = errors
                        st.toast("⚠️ Inconsistências encontradas no Deck!", icon="⚠️")
                    else:
                        res = save_deck_to_workspace(parsed)
                        st.session_state["import_text_val"] = ""
                        st.session_state["import_name_val"] = ""
                        st.session_state["import_errors"] = []
                        st.session_state["last_imported_deck"] = parsed
                        st.toast(f"✅ Deck '{parsed['name']}' ({parsed['format'].upper()}) importado com sucesso!", icon="🎉")
                        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                else:
                    st.warning("Cole o texto do deck antes de clicar em salvar.")

            if "last_imported_deck" in st.session_state:
                p = st.session_state.pop("last_imported_deck")
                st.success(f"🎉 **Deck Validado e Importado com Sucesso!**\n- **Nome:** {p['name']}\n- **Formato:** {p['format'].upper()}\n- **Total de Cartas:** {sum(c.get('total', 1) for c in p['cards'])}")

        with col_imp2:
            if st.session_state.get("import_errors"):
                st.error("### ⚠️ Erros de Validação do Deck\n" + "\n".join(f"• **{e}**" for e in st.session_state["import_errors"]))
                st.info("💡 Corrija as inconsistências na caixa de texto ao lado e clique novamente em 'Importar e Validar Deck'.")
            else:
                st.info("""💡 **Validador Estrito do Talishar:**\n- Validação automática de 10.000+ cartas suportadas no motor\n- Reconhecimento de Hero e slots de equipamentos (Head, Chest, Arms, Legs, Weapons)\n- Trava de importação se houver cartas não suportadas\n- Preservação do texto para correção imediata""")

# ==============================================================================
# ABA 5: ANALYTICS & ELO POR DECK
# ==============================================================================
with tab_stats:
    st.subheader("📈 Leaderboard de ELO & Desempenho por Deck")
    
    @st.fragment(run_every="2s")
    def render_stats_leaderboard():
        stats_data = get_stats_data()
        deck_stats = stats_data.get("deck_stats", {})
        if deck_stats:
            st.markdown("#### 🥇 Ranking de Competência por Deck / Herói")
            rows = []
            for d_name, d_info in deck_stats.items():
                matches = d_info.get("matches", 0)
                wins = d_info.get("wins", 0)
                losses = d_info.get("losses", matches - wins)
                elo = d_info.get("elo", 1200)
                wr = (wins / matches * 100) if matches > 0 else 0.0
                rows.append({
                    "Deck / Bot": d_name,
                    "Rating ELO": elo,
                    "Partidas": matches,
                    "Vitórias": wins,
                    "Derrotas": losses,
                    "Win Rate %": f"{wr:.1f}%"
                })
            df_dstats = pd.DataFrame(rows).sort_values(by="Rating ELO", ascending=False)
            st.dataframe(df_dstats, use_container_width=True)

            # Opção de Excluir / Apagar Deck Específico do Ranking
            col_del1, col_del2 = st.columns([3, 1])
            with col_del1:
                deck_to_del = st.selectbox("🗑️ Selecionar Deck para Limpar do Ranking:", list(deck_stats.keys()), key="del_deck_stat_sel")
            with col_del2:
                st.write("")
                if st.button("❌ Remover Deck do Ranking", use_container_width=True):
                    if deck_to_del:
                        delete_deck_stat(deck_to_del)
                        st.toast(f"Estatísticas do deck '{deck_to_del}' removidas!", icon="🗑️")
                        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
        else:
            st.info("Nenhuma partida registrada ainda para compor o ranking de ELO por deck.")

        st.divider()
        tot_m = stats_data.get("total_matches", 0)
        b1_wins = stats_data.get("bot1_wins", 0)
        b2_wins = stats_data.get("bot2_wins", 0)
        b1_elo = stats_data.get("bot1_elo", 1200)
        b2_elo = stats_data.get("bot2_elo", 1200)
        b1_wr = (b1_wins / tot_m * 100) if tot_m > 0 else 50.0
        b2_wr = (b2_wins / tot_m * 100) if tot_m > 0 else 50.0

        col_m1, col_m2, col_m3, col_m4, col_m5 = st.columns(5)
        col_m1.metric("Total de Partidas", tot_m)

        human_info = deck_stats.get("👤 Humano (Você)", {})
        h_m = human_info.get("matches", 0)
        h_w = human_info.get("wins", 0)
        h_elo = human_info.get("elo", 1200)
        h_wr = (h_w / h_m * 100) if h_m > 0 else 0.0

        col_m2.metric("👤 Seu ELO (Humano)", h_elo, f"{h_wr:.1f}% WR ({h_m} jogos)")
        col_m3.metric("Rating Global (Host)", b1_elo, f"{b1_wr:.1f}% WR")
        col_m4.metric("Rating Global (Join)", b2_elo, f"{b2_wr:.1f}% WR")
        col_m5.metric("Empates", stats_data.get("draws", 0))

        st.markdown("#### 📉 Evolução do Rating ELO por Deck")
        deck_elo_hist = stats_data.get("deck_elo_history", [])
        if len(deck_elo_hist) > 1:
            df_deck_elo = pd.DataFrame(deck_elo_hist).set_index("match")
            st.line_chart(df_deck_elo)
        else:
            elo_hist = stats_data.get("elo_history", [])
            if len(elo_hist) > 1:
                df_elo = pd.DataFrame(elo_hist)[["match", "bot1_elo", "bot2_elo"]].set_index("match")
                df_elo.columns = ["Bot 1 (Host)", "Bot 2 (Join)"]
                st.line_chart(df_elo)

    render_stats_leaderboard()

    if st.button("🗑️ Resetar Todas as Estatísticas de ELO"):
        reset_stats()
        st.toast("Estatísticas resetadas!", icon="🗑️")
        st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

# ==============================================================================
# ABA 7: TELEMETRIA ISMCTS EM TEMPO REAL
# ==============================================================================
with tab_ismcts:
    st.subheader("🌐 Telemetria e Diagnóstico ISMCTS (Information Set MCTS)")
    st.caption("Acompanhe em tempo real os mundos determinizados amostrados pela IA, distribuição de confiança e votos de visitas por fase.")

    ismcts_log_path = "logs/ismcts_decisions.jsonl"
    if os.path.exists(ismcts_log_path):
        records = []
        try:
            with open(ismcts_log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            pass
        except Exception as e:
            st.error(f"Erro ao ler logs ISMCTS: {e}")

        if records:
            df_ismcts = pd.DataFrame(records)
            
            # Métricas Top-Level
            tot_decisions = len(df_ismcts)
            avg_conf = df_ismcts["confidence"].mean() * 100 if "confidence" in df_ismcts else 0.0
            avg_worlds = df_ismcts["worlds_sampled"].mean() if "worlds_sampled" in df_ismcts else 0.0
            
            col_is1, col_is2, col_is3, col_is4 = st.columns(4)
            col_is1.metric("Decisões Registradas", tot_decisions)
            col_is2.metric("Confiança Média", f"{avg_conf:.1f}%")
            col_is3.metric("Mundos Médios / Decisão", f"{avg_worlds:.1f}")
            col_is4.metric("Última Fase Analisada", df_ismcts.iloc[-1].get("phase", "M") if "phase" in df_ismcts else "-")

            st.divider()

            col_ch1, col_ch2 = st.columns(2)
            with col_ch1:
                st.markdown("#### 🎯 Distribuição de Confiança por Decisão")
                if "confidence" in df_ismcts:
                    st.bar_chart(df_ismcts["confidence"].tail(50))

            with col_ch2:
                st.markdown("#### 📈 Evolução do Value da Raiz ($V_{root}$)")
                if "mcts_value_root" in df_ismcts:
                    st.line_chart(df_ismcts["mcts_value_root"].tail(50))

            st.markdown("#### 📋 Histórico das Últimas Decisões da IA")
            display_cols = ["timestamp", "turn", "phase", "chosen", "confidence", "worlds_sampled", "total_votes"]
            available_cols = [c for c in display_cols if c in df_ismcts.columns]
            st.dataframe(df_ismcts[available_cols].tail(25).iloc[::-1], use_container_width=True)

            if st.button("🗑️ Limpar Histórico de Telemetria ISMCTS"):
                try:
                    os.remove(ismcts_log_path)
                    st.toast("Histórico ISMCTS limpo com sucesso!", icon="🗑️")
                    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                except Exception as e:
                    st.error(f"Erro ao limpar log: {e}")
        else:
            st.info("Nenhuma decisão ISMCTS registrada no arquivo de log ainda.")
    else:
        st.info("O arquivo de telemetria `logs/ismcts_decisions.jsonl` ainda não foi criado. Inicie uma partida para gerar dados de decisão!")
