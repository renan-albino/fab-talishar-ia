"""
ui/tabs/tab_tournaments.py - Aba 4: Organizador de Torneios Customizados.

Permite selecionar decks do workspace, configurar o formato da competição
(Round-Robin ou Suíço), executar todos os confrontos via TournamentManager
e exibir tabela de classificação e matriz de matchups.
"""

import os
import json
import pandas as pd
import streamlit as st
from stats.tournament_manager import TournamentManager
from ui.helpers import get_cached_saved_decks


def render_tab_tournaments(deck_options=None):
    """Renderiza a Aba 4: Torneios Customizados."""
    if deck_options is None:
        saved_decks = get_cached_saved_decks()
        deck_options = {
            f"{d.get('name', d.get('slug'))} ({str(d.get('format', 'blitz')).upper()} - {d.get('total_cards', 0)} cartas)": d.get("slug")
            for d in saved_decks
        }

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
            st.write("")
            st.write("")
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
            with open(res_path, "r", encoding="utf-8") as f:
                t_data = json.load(f)
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
                        d1 = m["deck1_name"]
                        d2 = m["deck2_name"]
                        if d1 in matrix and d2 in matrix:
                            if m["winner"] == d1:
                                matrix[d1][d2] = "🟢 Vit"
                                matrix[d2][d1] = "🔴 Der"
                            else:
                                matrix[d2][d1] = "🟢 Vit"
                                matrix[d1][d2] = "🔴 Der"
                st.dataframe(pd.DataFrame(matrix), use_container_width=True)
        except Exception:
            pass
