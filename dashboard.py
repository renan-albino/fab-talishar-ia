import streamlit as st
import subprocess
import uuid
import json
import os
import time
import pandas as pd
from deck_parser import parse_deck_text, save_deck_to_workspace, list_saved_decks, set_active_deck, load_current_deck

st.set_page_config(page_title="FaB AI Master", layout="wide")
st.title("🤖 Fábrica de Treinamento - Flesh and Blood AI")

# Carrega decks salvos
saved_decks = list_saved_decks()
deck_options = {f"{d['name']} ({d['format'].upper()} - {d['total_cards']} cartas)": d['slug'] for d in saved_decks}

# --- SEÇÃO 1: GERENCIADOR E EDITOR DE DECKS ---
with st.expander("📦 Gerenciador e Editor de Decks (FaBrary / Texto Puro)", expanded=False):
    tab_import, tab_edit = st.tabs(["📥 Importar do FaBrary (Texto)", "✏️ Visualizar & Editar Decks Salvos"])
    
    with tab_import:
        st.markdown("Cole abaixo o texto exportado diretamente do **FaBrary** (ou FabDB):")
        col_imp1, col_imp2 = st.columns([3, 2])
        with col_imp1:
            deck_text_input = st.text_area(
                "Texto do Deck:",
                height=240,
                placeholder="""Name: Calling: Hamburg 1st 🇩🇪
Hero: Dash I/O
Format: Classic Constructed

Arena cards
1x Achilles Accelerator
1x Symbiosis Shot
...
Deck cards
3x Backup Protocol: RED (red)
3x Zero to Sixty (red)
..."""
            )
            col_b1, col_b2 = st.columns([2, 1])
            with col_b1:
                custom_name = st.text_input("Nome do Deck (opcional):", placeholder="Deixe em branco para usar o nome do FaBrary")
            with col_b2:
                st.write("")
                st.write("")
                btn_save = st.button("💾 Salvar Deck", use_container_width=True)

            if btn_save:
                if deck_text_input.strip():
                    parsed = parse_deck_text(deck_text_input, default_name=custom_name if custom_name else "Meu Deck")
                    res = save_deck_to_workspace(parsed)
                    st.success(f"Deck **{parsed['name']}** salvo com sucesso! Formato: {parsed['format'].upper()} com {sum(c['total'] for c in parsed['cards'])} cartas.")
                    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                else:
                    st.warning("Cole o texto do deck antes de clicar em salvar.")

        with col_imp2:
            st.info("""💡 **Dica:** O importador reconhece automaticamente:
- `Hero:` e formato (`Classic Constructed` ou `Blitz`)
- Equipamentos e armas em `Arena cards`
- Cartas e pitches `(red)`, `(yellow)`, `(blue)`, `(1)`, `(2)`, `(3)`""")

    with tab_edit:
        if saved_decks:
            selected_deck_name = st.selectbox("Selecione o Deck para Visualizar / Editar:", list(deck_options.keys()))
            selected_slug = deck_options[selected_deck_name]
            deck_info = next((d for d in saved_decks if d["slug"] == selected_slug), None)
            
            if deck_info:
                d_data = deck_info["data"]
                col_e1, col_e2 = st.columns([1, 1])
                col_e1.text_input("Nome:", value=d_data.get("name", ""), key=f"name_{selected_slug}", disabled=True)
                col_e2.selectbox("Formato:", ["cc", "blitz"], index=0 if d_data.get("format") == "cc" else 1, key=f"fmt_{selected_slug}", disabled=True)
                
                cards_list = d_data.get("cards", [])
                df_cards = pd.DataFrame(cards_list)
                if not df_cards.empty:
                    df_cards.columns = ["Identificador (ID)", "Quantidade"]
                    st.dataframe(df_cards, height=260, use_container_width=True)
                    
                if st.button("🌟 Definir como Deck Ativo Padrão do Talishar"):
                    set_active_deck(d_data)
                    st.success(f"Deck **{d_data.get('name')}** definido como padrão!")
        else:
            st.info("Nenhum deck salvo ainda. Importe um deck na aba ao lado.")

st.divider()

# --- SEÇÃO 2: LANÇADOR DE PARTIDAS (COM DROPDOWN) ---
st.subheader("⚔️ Lançar Partida de Treinamento")

col1, col2, col3 = st.columns([2, 2, 1])
with col1:
    if deck_options:
        bot1_choice = st.selectbox("Deck Bot 1 (Host):", list(deck_options.keys()), index=0)
        bot1_deck_slug = deck_options[bot1_choice]
    else:
        bot1_deck_slug = st.text_input("Deck Bot 1:", value="ira_blitz_padr_o")

with col2:
    if deck_options:
        bot2_choice = st.selectbox("Deck Bot 2 (Join):", list(deck_options.keys()), index=0)
        bot2_deck_slug = deck_options[bot2_choice]
    else:
        bot2_deck_slug = st.text_input("Deck Bot 2:", value="ira_blitz_padr_o")

with col3:
    num_matches = st.number_input("Partidas Simultâneas", min_value=1, max_value=10, value=1)

def count_active_bot_processes():
    try:
        res = subprocess.run(["pgrep", "-c", "-f", "bot_client.py"], capture_output=True, text=True)
        return int(res.stdout.strip()) if res.stdout.strip().isdigit() else 0
    except Exception:
        return 0

active_bots = count_active_bot_processes()
if active_bots > 0:
    st.success(f"🟢 **{active_bots}** processos de bots em execução.")
else:
    st.info("⚪ Nenhum processo de bot em execução.")

col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
with col_btn1:
    btn_start = st.button("🚀 Iniciar Lote de Treinamento", type="primary", use_container_width=True)
with col_btn2:
    btn_kill = st.button("🛑 Parar / Matar Partidas", type="secondary", use_container_width=True)
with col_btn3:
    btn_clean = st.button("🧹 Limpar Histórico / Logs", use_container_width=True)

if btn_kill or btn_clean:
    subprocess.run(["pkill", "-9", "-f", "bot_client.py"])
    if os.path.exists("logs"):
        for f in os.listdir("logs"):
            try:
                os.remove(os.path.join("logs", f))
            except Exception:
                pass
    st.session_state["rooms"] = []
    st.warning("Processos finalizados e histórico de salas limpo com sucesso!")
    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

if btn_start:
    st.session_state["rooms"] = []
    
    for i in range(num_matches):
        room_id = f"Treino_{uuid.uuid4().hex[:4]}_{i}"
        st.session_state["rooms"].append(room_id)
        
        out1 = open(f"logs/{room_id}_Bot1_terminal.log", "w")
        subprocess.Popen(["./venv/bin/python", "bot_client.py", "--room", room_id, "--deck", bot1_deck_slug, "--role", "host", "--name", "Bot1"], stdout=out1, stderr=out1)
        
        time.sleep(2) # Tempo pro backend registrar o host e gerar o ID da partida
        
        out2 = open(f"logs/{room_id}_Bot2_terminal.log", "w")
        subprocess.Popen(["./venv/bin/python", "bot_client.py", "--room", room_id, "--deck", bot2_deck_slug, "--role", "join", "--name", "Bot2"], stdout=out2, stderr=out2)
        
    st.success(f"{num_matches} partida(s) iniciada(s) em background!")

st.divider()

# --- SEÇÃO 3: MONITORAMENTO DA PARTIDA ---
def get_available_rooms():
    discovered = set()
    if os.path.exists("logs"):
        for fname in os.listdir("logs"):
            if fname.startswith("Treino_") and (fname.endswith(".json") or fname.endswith(".log")):
                parts = fname.split("_")
                if len(parts) >= 3:
                    room_name = f"{parts[0]}_{parts[1]}_{parts[2].split('.')[0]}"
                    discovered.add(room_name)
    for r in st.session_state.get("rooms", []):
        discovered.add(r)
    return sorted(list(discovered), reverse=True)

@st.fragment(run_every="2s")
def render_live_monitoring_fragment():
    available_rooms = get_available_rooms()
    if not available_rooms:
        st.info("ℹ️ Nenhuma partida ativa ou inspecionada no momento. Selecione os decks e clique em **'🚀 Iniciar Lote de Treinamento'** acima.")
        return

    st.subheader("📊 Monitoramento em Tempo Real")
    room = st.selectbox("Inspecionar Partida:", available_rooms, key="selected_room_inspect")
    
    c1, c2 = st.columns(2)
    file_b1 = f"logs/{room}_Bot1.json"
    file_b2 = f"logs/{room}_Bot2.json"
    
    with c1:
        st.markdown("### 🔴 Bot 1 (Host)")
        if os.path.exists(file_b1):
            try:
                data1 = json.load(open(file_b1))
                m1 = data1.get("metrics", {})
                st.metric("Vida (Host)", m1.get("health", 40))
                st.write(f"**Fase/Turno:** {m1.get('phase', 'Iniciando')}")
                st.write(f"**Deck:** `{m1.get('deck_url', 'Padrão')}`")
            except Exception:
                st.info("Carregando métricas do Bot 1...")
        else:
            st.info("Aguardando inicialização do Bot 1...")

    with c2:
        st.markdown("### 🔵 Bot 2 (Join)")
        if os.path.exists(file_b2):
            try:
                data2 = json.load(open(file_b2))
                m2 = data2.get("metrics", {})
                st.metric("Vida (Join)", m2.get("health", 40))
                st.write(f"**Fase/Turno:** {m2.get('phase', 'Iniciando')}")
                st.write(f"**Deck:** `{m2.get('deck_url', 'Padrão')}`")
            except Exception:
                st.info("Carregando métricas do Bot 2...")
        else:
            st.info("Aguardando inicialização do Bot 2...")
        
    st.subheader("🕵️ Logs Dinâmicos da Partida (Últimas 20 Linhas)")
    tab_uni, tab1, tab2 = st.tabs(["⚔️ Combate Unificado", "Bot 1 (Host)", "Bot 2 (Join)"])
    
    with tab_uni:
        log1 = f"logs/{room}_Bot1_debug.log"
        log2 = f"logs/{room}_Bot2_debug.log"
        combined_lines = []
        if os.path.exists(log1):
            with open(log1, "r") as f:
                for l in f.readlines():
                    if l.strip() and not l.startswith("---"):
                        combined_lines.append(l.strip())
        if os.path.exists(log2):
            with open(log2, "r") as f:
                for l in f.readlines():
                    if l.strip() and not l.startswith("---"):
                        combined_lines.append(l.strip())
        combined_lines.sort()
        if combined_lines:
            st.code("\n".join(combined_lines[-20:]))
        else:
            st.info("Aguardando ações dos bots...")

    with tab1:
        log1 = f"logs/{room}_Bot1_debug.log"
        if os.path.exists(log1):
            with open(log1, "r") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                st.code("\n".join(lines[-20:]))
        else:
            st.info("Log do Bot 1 ainda não disponível.")
            
    with tab2:
        log2 = f"logs/{room}_Bot2_debug.log"
        if os.path.exists(log2):
            with open(log2, "r") as f:
                lines = [l.strip() for l in f.readlines() if l.strip()]
                st.code("\n".join(lines[-20:]))
        else:
            st.info("Log do Bot 2 ainda não disponível.")

render_live_monitoring_fragment()

st.divider()

# --- SEÇÃO 4: COEFICIENTE DE APRENDIZADO & DESEMPENHO (ELO & ANALYTICS) ---
from stats_manager import get_stats_data, reset_stats

st.subheader("📈 Coeficiente de Aprendizado & Desempenho dos Bots (Elo & Analytics)")
stats_data = get_stats_data()

tot_m = stats_data.get("total_matches", 0)
b1_wins = stats_data.get("bot1_wins", 0)
b2_wins = stats_data.get("bot2_wins", 0)
b1_elo = stats_data.get("bot1_elo", 1200)
b2_elo = stats_data.get("bot2_elo", 1200)

b1_wr = (b1_wins / tot_m * 100) if tot_m > 0 else 50.0
b2_wr = (b2_wins / tot_m * 100) if tot_m > 0 else 50.0

col_m1, col_m2, col_m3, col_m4 = st.columns(4)
col_m1.metric("Partidas Concluídas", tot_m)
col_m2.metric("Rating Elo (Bot 1)", b1_elo, f"{b1_wr:.1f}% WR")
col_m3.metric("Rating Elo (Bot 2)", b2_elo, f"{b2_wr:.1f}% WR")
col_m4.metric("Empates", stats_data.get("draws", 0))

# Gráfico de Evolução de Elo
elo_hist = stats_data.get("elo_history", [])
if len(elo_hist) > 1:
    st.markdown("#### 📉 Evolução do Rating Elo")
    df_elo = pd.DataFrame(elo_hist)[["match", "bot1_elo", "bot2_elo"]].set_index("match")
    df_elo.columns = ["Bot 1 (Host)", "Bot 2 (Join)"]
    st.line_chart(df_elo)

# Tabela de Partidas Recentes
recent = stats_data.get("recent_matches", [])
if recent:
    st.markdown("#### 📜 Histórico Recente de Partidas")
    df_recent = pd.DataFrame(recent)
    df_recent.columns = ["Sala", "Data/Hora", "Vencedor", "Deck Bot 1", "Deck Bot 2", "Vida B1", "Vida B2", "Turnos"]
    st.dataframe(df_recent, use_container_width=True)

if st.button("🗑️ Resetar Estatísticas de Aprendizado"):
    reset_stats()
    st.success("Estatísticas resetadas com sucesso!")
    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
