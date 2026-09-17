"""
ui/tabs/tab_analytics.py - Aba 6: Analytics & ELO por Deck.

Exibe o leaderboard de ELO por deck e herói, panorama global projetado vs partidas
ranqueadas estritas, histórico de rating ao longo do tempo, e controles de sincronização e reset.
"""

import pandas as pd
import streamlit as st
from stats_manager import (
    delete_deck_stat,
    reset_all_elos,
    reset_stats,
    sync_training_matches,
)
from ui.helpers import get_cached_stats_data, get_total_training_games


@st.fragment()
def render_stats_leaderboard():
    """Fragmento que renderiza as tabelas, métricas e gráficos de ELO."""
    stats_data = get_cached_stats_data()
    deck_stats = stats_data.get("deck_stats", {})
    tot_m = stats_data.get("total_matches", 0)

    # Obtém o total de partidas globais do motor (ex: 1.217)
    total_training_games = get_total_training_games()
    total_training_games = max(total_training_games, tot_m)

    if deck_stats:
        col_hdr1, col_hdr2 = st.columns([2, 1])
        with col_hdr1:
            st.markdown("#### 🥇 Ranking de Competência por Deck / Herói")
        with col_hdr2:
            scope_options = [
                f"🌐 Todas as Partidas ({total_training_games:,})",
                f"🎯 Log ELO Verificado ({tot_m:,})",
            ]
            scope_mode = st.radio(
                "Escopo de Análise:",
                scope_options,
                index=0,
                key="elo_scope_radio",
                horizontal=True,
            )

        is_global_scope = scope_mode.startswith("🌐")
        scale_factor = (total_training_games / tot_m) if (tot_m > 0 and is_global_scope) else 1.0

        if is_global_scope and total_training_games > tot_m:
            st.caption(
                f"ℹ️ **Modo Panorama Global Ativo:** Exibindo a análise projetada sobre todas as **{total_training_games:,} partidas** "
                f"disputadas pelo motor de IA. O Win Rate % e o Rating ELO são calculados a partir da telemetria das **{tot_m} partidas ranqueadas**."
            )

        rows = []
        for d_name, d_info in deck_stats.items():
            matches = d_info.get("matches", 0)
            wins = d_info.get("wins", 0)
            elo = d_info.get("elo", 1200)
            wr = (wins / matches * 100) if matches > 0 else 0.0

            if is_global_scope and scale_factor > 1.0:
                disp_matches = round(matches * scale_factor)
                disp_wins = round(wins * scale_factor)
                disp_losses = max(0, disp_matches - disp_wins)
            else:
                disp_matches = matches
                disp_wins = wins
                disp_losses = d_info.get("losses", matches - wins)

            rows.append({
                "Deck / Bot": d_name,
                "Rating ELO": elo,
                "Partidas": disp_matches,
                "Vitórias": disp_wins,
                "Derrotas": disp_losses,
                "Win Rate %": round(wr, 1),
            })
        df_dstats = pd.DataFrame(rows).sort_values(by="Rating ELO", ascending=False)
        st.dataframe(
            df_dstats,
            use_container_width=True,
            column_config={
                "Win Rate %": st.column_config.NumberColumn(
                    "Win Rate %",
                    format="%.1f%%",
                    help="Percentual de vitórias (ordenável numericamente)",
                ),
            },
        )

        # Opção de Excluir / Apagar Deck Específico do Ranking
        col_del1, col_del2 = st.columns([3, 1])
        with col_del1:
            deck_to_del = st.selectbox("🗑️ Selecionar Deck para Limpar do Ranking:", list(deck_stats.keys()), key="del_deck_stat_sel")
        with col_del2:
            st.write("")
            if st.button("❌ Remover Deck do Ranking", use_container_width=True):
                if deck_to_del:
                    delete_deck_stat(deck_to_del)
                    get_cached_stats_data.clear()
                    st.toast(f"Estatísticas do deck '{deck_to_del}' removidas!", icon="🗑️")
                    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
    else:
        st.info("Nenhuma partida registrada ainda para compor o ranking de ELO por deck.")

    st.divider()
    b1_wins = stats_data.get("bot1_wins", 0)
    b2_wins = stats_data.get("bot2_wins", 0)
    b1_elo = stats_data.get("bot1_elo", 1200)
    b2_elo = stats_data.get("bot2_elo", 1200)
    b1_wr = (b1_wins / tot_m * 100) if tot_m > 0 else 50.0
    b2_wr = (b2_wins / tot_m * 100) if tot_m > 0 else 50.0

    col_m1, col_m2, col_m3, col_m4, col_m5, col_m6 = st.columns(6)
    col_m1.metric("Partidas Totais (Motor)", f"{total_training_games:,}", "Treino / Auto-Play")
    col_m2.metric("Partidas Ranqueadas (ELO)", f"{tot_m:,}", "Telemetria Estrita")

    human_info = deck_stats.get("👤 Humano (Você)", {})
    h_m = human_info.get("matches", 0)
    h_w = human_info.get("wins", 0)
    h_elo = human_info.get("elo", 1200)
    h_wr = (h_w / h_m * 100) if h_m > 0 else 0.0

    col_m3.metric("👤 Seu ELO (Humano)", h_elo, f"{h_wr:.1f}% WR ({h_m} jogos)")
    col_m4.metric("Rating Global (Host)", b1_elo, f"{b1_wr:.1f}% WR")
    col_m5.metric("Rating Global (Join)", b2_elo, f"{b2_wr:.1f}% WR")
    col_m6.metric("Empates", stats_data.get("draws", 0))

    st.markdown("#### 📉 Evolução do Rating ELO por Deck")
    deck_elo_hist = stats_data.get("deck_elo_history", [])
    if len(deck_elo_hist) > 1:
        if len(deck_elo_hist) > 150:
            step = len(deck_elo_hist) // 150
            sampled_deck_elo = deck_elo_hist[::step]
            if deck_elo_hist[-1] != sampled_deck_elo[-1]:
                sampled_deck_elo.append(deck_elo_hist[-1])
        else:
            sampled_deck_elo = deck_elo_hist
        df_deck_elo = pd.DataFrame(sampled_deck_elo).set_index("match")
        st.line_chart(df_deck_elo)
    else:
        elo_hist = stats_data.get("elo_history", [])
        if len(elo_hist) > 1:
            if len(elo_hist) > 150:
                step = len(elo_hist) // 150
                sampled_elo = elo_hist[::step]
                if elo_hist[-1] != sampled_elo[-1]:
                    sampled_elo.append(elo_hist[-1])
            else:
                sampled_elo = elo_hist
            df_elo = pd.DataFrame(sampled_elo)[["match", "bot1_elo", "bot2_elo"]].set_index("match")
            df_elo.columns = ["Bot 1 (Host)", "Bot 2 (Join)"]
            st.line_chart(df_elo)
        else:
            st.info("ℹ️ A curva de evolução de ELO será desenhada conforme novas partidas ranqueadas forem disputadas (iniciando em 1200).")


def render_tab_analytics():
    """Renderiza a Aba 6: Analytics & ELO por Deck."""
    col_st_hdr1, col_st_hdr2, col_st_hdr3 = st.columns([2.5, 1, 1.2])
    with col_st_hdr1:
        st.subheader("📈 Leaderboard de ELO & Desempenho por Deck")
    with col_st_hdr2:
        if st.button("🔄 Atualizar", key="btn_refresh_elo_data", use_container_width=True):
            get_cached_stats_data.clear()
            st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
    with col_st_hdr3:
        with st.popover("🎯 Resetar ELOs", use_container_width=True):
            st.markdown("##### 🎯 Resetar Ratings de ELO")
            st.caption(
                "Reinicia os ratings de todos os decks e bots para **1200** e zera o histórico de partidas "
                "para avaliar a progressão do novo modelo de rede neural."
            )
            if st.button(
                "⚠️ Confirmar Reset para 1200",
                key="btn_confirm_reset_elo_hdr",
                type="primary",
                use_container_width=True,
            ):
                reset_all_elos()
                get_cached_stats_data.clear()
                st.toast("Todos os ratings de ELO foram resetados para 1200!", icon="🎯")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    render_stats_leaderboard()

    col_btn1, col_btn2, col_btn3 = st.columns([1.5, 1.2, 1.2])
    with col_btn1:
        stats_data = get_cached_stats_data()
        tot_m = stats_data.get("total_matches", 0)
        total_training_games = get_total_training_games()
        if total_training_games > tot_m:
            if st.button(
                f"⚡ Sincronizar Base ELO com Treino ({total_training_games:,})",
                key="btn_sync_elo_matches",
                use_container_width=True,
            ):
                sync_training_matches(total_training_games)
                get_cached_stats_data.clear()
                st.toast(
                    f"Estatísticas de ELO sincronizadas com todas as {total_training_games:,} partidas!",
                    icon="🎉",
                )
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
    with col_btn2:
        with st.popover("🎯 Resetar ELOs para 1200", use_container_width=True):
            st.markdown("##### 🎯 Reiniciar Avaliação de ELO")
            st.write(
                "Todos os decks permanecerão na tabela com ELO 1200 e métricas zeradas, "
                "permitindo avaliar uma nova curva de progressão limpa."
            )
            if st.button(
                "Confirmar Reset de ELO",
                key="btn_confirm_reset_elo_btm",
                type="primary",
                use_container_width=True,
            ):
                reset_all_elos()
                get_cached_stats_data.clear()
                st.toast("Ratings de ELO reiniciados para 1200!", icon="🎯")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
    with col_btn3:
        with st.popover("🗑️ Limpar Banco de Dados", use_container_width=True):
            st.markdown("##### 🗑️ Reset Total da Telemetria")
            st.write("Apaga completamente o arquivo de estatísticas e rankings.")
            if st.button(
                "Confirmar Limpeza Total",
                key="btn_confirm_wipe_stats",
                type="secondary",
                use_container_width=True,
            ):
                reset_stats()
                get_cached_stats_data.clear()
                st.toast("Banco de dados de telemetria reiniciado!", icon="🗑️")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
