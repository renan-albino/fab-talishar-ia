"""
ui/tabs/tab_ismcts.py - Aba 7: Telemetria ISMCTS em Tempo Real.

Diagnóstico profundo do algoritmo ISMCTS (Information Set MCTS): mundos determinizados
amostrados pela IA sob informação oculta, distribuição de confiança, valor da raiz (V_root)
e log de decisões recentes.
"""

import os
import pandas as pd
import streamlit as st
from ui.helpers import read_jsonl_tail, get_fast_line_count


def render_tab_ismcts():
    """Renderiza a Aba 7: Telemetria ISMCTS em Tempo Real."""
    st.subheader("🌐 Telemetria e Diagnóstico ISMCTS (Information Set MCTS)")
    st.caption("Acompanhe em tempo real os mundos determinizados amostrados pela IA, distribuição de confiança e votos de visitas por fase.")

    ismcts_log_path = "logs/ismcts_decisions.jsonl"
    if os.path.exists(ismcts_log_path):
        records = read_jsonl_tail(ismcts_log_path, max_lines=150)
        tot_decisions = get_fast_line_count(ismcts_log_path)

        if records:
            df_ismcts = pd.DataFrame(records)
            for col in ["turn", "total_votes", "worlds_sampled"]:
                if col in df_ismcts.columns:
                    df_ismcts[col] = pd.to_numeric(df_ismcts[col], errors="coerce").fillna(0).astype(int)
            for col in ["confidence", "mcts_value_root"]:
                if col in df_ismcts.columns:
                    df_ismcts[col] = pd.to_numeric(df_ismcts[col], errors="coerce").fillna(0.0)
            for col in ["timestamp", "phase", "chosen"]:
                if col in df_ismcts.columns:
                    df_ismcts[col] = df_ismcts[col].astype(str)

            # Métricas Top-Level calculadas sobre o histórico recente
            avg_conf = df_ismcts["confidence"].tail(50).mean() * 100 if "confidence" in df_ismcts else 0.0
            avg_worlds = df_ismcts["worlds_sampled"].tail(50).mean() if "worlds_sampled" in df_ismcts else 0.0

            col_is1, col_is2, col_is3, col_is4 = st.columns(4)
            col_is1.metric("Decisões Registradas", f"{tot_decisions:,}")
            col_is2.metric("Confiança Média (Recente)", f"{avg_conf:.1f}%")
            col_is3.metric("Mundos Médios / Decisão", f"{avg_worlds:.1f}")
            col_is4.metric("Última Fase Analisada", df_ismcts.iloc[-1].get("phase", "M") if "phase" in df_ismcts else "-")

            st.divider()

            col_ch1, col_ch2 = st.columns(2)
            with col_ch1:
                st.markdown("#### 🎯 Distribuição de Confiança por Decisão (Últimas 50)")
                if "confidence" in df_ismcts:
                    st.bar_chart(df_ismcts["confidence"].tail(50))

            with col_ch2:
                st.markdown("#### 📈 Evolução do Value da Raiz ($V_{root}$ - Últimas 50)")
                if "mcts_value_root" in df_ismcts:
                    st.line_chart(df_ismcts["mcts_value_root"].tail(50))

            st.markdown("#### 📋 Histórico das Últimas Decisões da IA")
            display_cols = ["timestamp", "turn", "phase", "chosen", "confidence", "worlds_sampled", "total_votes"]
            available_cols = [c for c in display_cols if c in df_ismcts.columns]
            st.dataframe(df_ismcts[available_cols].tail(25).iloc[::-1], use_container_width=True)

            if st.button("🗑️ Limpar Histórico de Telemetria ISMCTS"):
                try:
                    os.remove(ismcts_log_path)
                    get_fast_line_count.clear()
                    st.toast("Histórico ISMCTS limpo com sucesso!", icon="🗑️")
                    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
                except Exception as e:
                    st.error(f"Erro ao limpar log: {e}")
        else:
            st.info("Nenhuma decisão ISMCTS registrada no arquivo de log ainda.")
    else:
        st.info("O arquivo de telemetria `logs/ismcts_decisions.jsonl` ainda não foi criado. Inicie uma partida para gerar dados de decisão!")
