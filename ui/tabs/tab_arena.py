"""
ui/tabs/tab_arena.py - Aba 2: Arena de Bots & Simulação Visual.

Gerencia o lançamento de partidas rápidas entre bots IA, cancelamento e limpeza
de processos e logs, além de renderizar o tabuleiro visual com atualização a cada 3s.
"""

import os
import time
import json
import uuid
import html
import subprocess
import streamlit as st
from ui.helpers import get_cached_saved_decks, read_text_tail


@st.cache_data(ttl=2)
def get_available_rooms(session_rooms_key: str = ""):
    """Detecta salas ativas ou arquivadas na pasta logs/."""
    discovered = set()
    if os.path.exists("logs"):
        suffixes = (
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
            "_join_deck.txt",
        )
        for fname in os.listdir("logs"):
            for s in suffixes:
                if fname.endswith(s):
                    room_id = fname[: -len(s)]
                    if room_id:
                        discovered.add(room_id)
                    break
    for r in st.session_state.get("rooms", []):
        if r:
            discovered.add(r)
    return sorted(list(discovered), reverse=True)


@st.fragment(run_every="3s")
def render_arena_board():
    """Fragmento que atualiza a cada 3 segundos o tabuleiro visual e feed de ações da arena."""
    available_rooms = get_available_rooms(str(st.session_state.get("rooms", [])))
    if not available_rooms:
        st.info("ℹ️ Nenhuma partida ativa no momento. Escolha os decks e clique em **'🚀 Iniciar Partidas Rápidas'**.")
        return

    room = st.selectbox("Inspecionar Sala:", available_rooms, key="arena_selected_room")
    file_b1 = f"logs/{room}_Bot1.json"
    file_b2 = f"logs/{room}_Bot2.json"
    m1 = {}
    m2 = {}
    h1 = 40
    h2 = 40
    phase1 = "Em Combate"
    deck1_name = "Bot 1 (Host)"
    deck2_name = "Bot 2 (Joiner)"

    if os.path.exists(file_b1):
        try:
            with open(file_b1, "r", encoding="utf-8") as f:
                data1 = json.load(f)
            m1 = data1.get("metrics", {})
            h1 = int(m1.get("health", 40))
            phase1 = m1.get("phase", "Em Combate")
            deck1_name = m1.get("deck_url", "Bot 1")
        except Exception:
            pass

    if os.path.exists(file_b2):
        try:
            with open(file_b2, "r", encoding="utf-8") as f:
                data2 = json.load(f)
            m2 = data2.get("metrics", {})
            h2 = int(m2.get("health", 40))
            deck2_name = m2.get("deck_url", "Bot 2")
        except Exception:
            pass

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
        feed_text = read_text_tail(match_feed_log, max_lines=60)
        combined = [l.strip() for l in feed_text.splitlines() if l.strip() and not l.startswith("---")]
    else:
        for lp in [log1, log2]:
            if os.path.exists(lp):
                lp_text = read_text_tail(lp, max_lines=40)
                for l in lp_text.splitlines():
                    line = l.strip()
                    if line and not line.startswith("---"):
                        combined.append(line)
        combined.sort(key=lambda x: x[:10] if x.startswith("[") else "")

    if combined:
        formatted_logs = html.escape("\n".join(combined))
        st.markdown(f"""
        <div style="background-color: #0b1120; color: #38bdf8; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; padding: 12px; border-radius: 8px; max-height: 280px; height: 280px; overflow-y: auto; border: 1px solid #1e293b; white-space: pre-wrap; line-height: 1.45;">{formatted_logs}</div>
        """, unsafe_allow_html=True)
    else:
        st.info("Aguardando primeiras ações dos bots...")

    st.write("")
    st.markdown("#### 🎴 Configuração de Decks & Equipamentos na Match")

    _FALLBACK_DECK_CACHE = getattr(render_arena_board, "_deck_cache", {})
    render_arena_board._deck_cache = _FALLBACK_DECK_CACHE

    def get_fallback_deck_info(d_name):
        if not d_name:
            return {}
        clean = os.path.basename(str(d_name)).replace(".json", "").lower()
        if clean in _FALLBACK_DECK_CACHE:
            return _FALLBACK_DECK_CACHE[clean]
        paths = [f"decks/{clean}.json", f"Talishar/decks/{clean}.json", f"{clean}.json", "deck.json"]
        for p in paths:
            if os.path.exists(p):
                try:
                    with open(p, "r", encoding="utf-8") as df_file:
                        d_obj = json.load(df_file)
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
                    deck_info = {
                        "hero": hero if hero else (cards[0].get("identifier", "Herói") if cards else "Herói"),
                        "equipment": {
                            "head": next((e for e in eq if any(h in e for h in ["crown", "helm", "hood", "mask", "kabuto", "head", "fold", "respirator"])), "-"),
                            "chest": next((e for e in eq if any(h in e for h in ["chest", "tunic", "carapace", "threads", "robe", "heart", "vest", "grains", "bloodspill"])), "-"),
                            "arms": next((e for e in eq if any(h in e for h in ["gloves", "arms", "rerebrace", "quillhand", "hook", "gauntlet", "knives", "shuko"])), "-"),
                            "legs": next((e for e in eq if any(h in e for h in ["boots", "legs", "steps", "creepers", "dynamo", "mountain", "whisperers"])), "-"),
                            "weapons": [e for e in eq if any(h in e for h in ["blade", "sword", "shot", "hammer", "flail", "weapon", "klaive", "harpoon", "compass", "fellingsong", "grimoire"])],
                        },
                        "main_deck_count": len(main),
                        "sideboard_count": max(0, len(main) - 60) if len(main) > 60 else 0,
                        "sideboard_cards": main[60:] if len(main) > 60 else [],
                    }
                    _FALLBACK_DECK_CACHE[clean] = deck_info
                    return deck_info
                except Exception:
                    pass
        res = {}
        _FALLBACK_DECK_CACHE[clean] = res
        return res

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


def render_tab_arena(deck_options=None):
    """Renderiza a Aba 2: Arena de Bots & Simulação."""
    if deck_options is None:
        saved_decks = get_cached_saved_decks()
        deck_options = {
            f"{d.get('name', d.get('slug'))} ({str(d.get('format', 'blitz')).upper()} - {d.get('total_cards', 0)} cartas)": d.get("slug")
            for d in saved_decks
        }

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
            bot2_choice = st.selectbox("Deck Bot 2 (Join):", list(deck_options.keys()), index=min(1, len(deck_options) - 1), key="arena_bot2")
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
                if f == "ismcts_decisions.jsonl":
                    continue
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
            subprocess.Popen(
                ["./venv/bin/python", "-u", "bot_client.py", "--room", room_id, "--deck", f"decks/{bot1_deck_slug}.json", "--role", "host", "--name", "Bot1"],
                stdout=out1,
                stderr=out1,
                start_new_session=True,
            )
            time.sleep(0.1)
            out2 = open(f"logs/{room_id}_Bot2_terminal.log", "w")
            subprocess.Popen(
                ["./venv/bin/python", "-u", "bot_client.py", "--room", room_id, "--deck", f"decks/{bot2_deck_slug}.json", "--role", "join", "--name", "Bot2"],
                stdout=out2,
                stderr=out2,
                start_new_session=True,
            )
        st.success(f"{num_matches} partida(s) de alta velocidade iniciada(s)!")

    st.divider()
    render_arena_board()
