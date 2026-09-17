"""
dashboard.py - Orquestrador Principal da Interface Gráfica Streamlit do FaB Talishar AI.

Arquitetura modular: delega a renderização de cada aba para seus respectivos módulos em ui/tabs/.
"""

import streamlit as st
from ui.helpers import (
    get_gpu_info,
    get_cached_services_status,
    get_cached_saved_decks,
)
import importlib
import ui.tabs.tab_analytics
importlib.reload(ui.tabs.tab_analytics)
from ui.tabs import (
    render_tab_play,
    render_tab_arena,
    render_tab_training,
    render_tab_tournaments,
    render_tab_decks,
    render_tab_ismcts,
)
from ui.tabs.tab_analytics import render_tab_analytics


# Configuração da Página
st.set_page_config(
    page_title="FaB AI Master - GPU Deep RL",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Detecção de GPU e Serviços (via helpers com cache)
gpu_available, gpu_name, gpu_vram = get_gpu_info()
fe_running, be_running = get_cached_services_status()

# Cabeçalho Superior e Badges
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

# Carrega decks salvos (com cache)
saved_decks = get_cached_saved_decks()
deck_options = {
    f"{d.get('name', d.get('slug'))} ({str(d.get('format', 'blitz')).upper()} - {d.get('total_cards', 0)} cartas)": d.get("slug")
    for d in saved_decks
}

# Menu Principal de Navegação (Carregamento Lazy Instantâneo)
MENU_OPTIONS = [
    "🎮 Jogar no Talishar (Humano vs Bot)",
    "⚔️ Arena de Bots & Simulação",
    "⚡ Treinamento com GPU (Deep RL)",
    "🏆 Torneios Customizados",
    "📦 Gerenciador & Editor de Decks",
    "📈 Analytics & ELO por Deck",
    "🌐 Telemetria ISMCTS",
]

active_tab = st.segmented_control(
    "Navegação Principal",
    MENU_OPTIONS,
    default=MENU_OPTIONS[0],
    label_visibility="collapsed",
    width="stretch",
    key="dashboard_active_tab",
) or MENU_OPTIONS[0]

# Delegação de Renderização para as Abas Modulares
if active_tab == MENU_OPTIONS[0]:
    render_tab_play(saved_decks=saved_decks, deck_options=deck_options, fe_running=fe_running, be_running=be_running)
elif active_tab == MENU_OPTIONS[1]:
    render_tab_arena(deck_options=deck_options)
elif active_tab == MENU_OPTIONS[2]:
    render_tab_training(deck_options=deck_options, gpu_available=gpu_available)
elif active_tab == MENU_OPTIONS[3]:
    render_tab_tournaments(deck_options=deck_options)
elif active_tab == MENU_OPTIONS[4]:
    render_tab_decks(saved_decks=saved_decks, deck_options=deck_options)
elif active_tab == MENU_OPTIONS[5]:
    render_tab_analytics()
elif active_tab == MENU_OPTIONS[6]:
    render_tab_ismcts()
