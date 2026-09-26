"""
ui/tabs/tab_training.py - Aba 3: Treinamento com GPU (Deep RL + Rotação de Decks).

Painel de controle para treinamento autônomo por Deep Reinforcement Learning com aceleração GPU,
seleção de perfis de hardware (Equilibrado vs Turbo Máximo) e telemetria em tempo real.
"""

import os
import numpy as np
import pandas as pd
import streamlit as st
from ui.helpers import (
    get_orchestrator,
    get_suggested_training_profile,
    get_stats_data,
    get_cached_saved_decks,
    get_gpu_info,
    get_replay_buffer_sample_count,
    clear_replay_buffer,
)


def render_tab_training(deck_options=None, gpu_available=None):
    """Renderiza a Aba 3: Treinamento com GPU (Deep RL)."""
    orchestrator = get_orchestrator()

    if gpu_available is None:
        gpu_available, _, _ = get_gpu_info()

    if deck_options is None:
        saved_decks = get_cached_saved_decks()
        deck_options = {
            f"{d.get('name', d.get('slug'))} ({str(d.get('format', 'blitz')).upper()} - {d.get('total_cards', 0)} cartas)": d.get("slug")
            for d in saved_decks
        }

    st.subheader("⚡ Painel de Treinamento Autônomo com GPU")
    st.markdown("Acelere o aprendizado da rede neural com **Self-Play em lote**, rotação dinâmica de decks e amostragem na GPU.")

    all_deck_keys = list(deck_options.keys())
    selected_training_decks = st.multiselect(
        "🎴 Selecione os Decks que a IA irá usar no Treinamento (Rotativo):",
        all_deck_keys,
        default=all_deck_keys[: min(3, len(all_deck_keys))],
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
                on_change=lambda: update_hardware_suggestions(),
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
                help="Quantidade de duelos simultâneos. No Modo Turbo, escala até 95% dos núcleos lógicos da máquina.",
            )
            batch_sz = st.select_slider(
                "Batch Size do Treinador:",
                options=[32, 64, 128, 256, 512, 1024, 2048, 4096],
                key="train_batch_size",
                help="Tamanho do lote para atualização de gradientes na GPU/CPU. No Turbo, ocupa até 95% da VRAM livre.",
            )
        with col_g2:
            lr_val = st.select_slider(
                "Learning Rate (Taxa de Aprendizado):",
                options=[0.0001, 0.0003, 0.001, 0.003],
                value=0.0003,
                key="train_lr",
            )
            mcts_sims = st.slider(
                "Simulações ISMCTS / MCTS por Jogada:",
                min_value=5,
                max_value=200,
                key="train_mcts_sims",
                help="Profundidade da busca na árvore. O motor utiliza ISMCTS (Information Set MCTS) simulando múltiplos mundos determinizados quando o oponente tem cartas ocultas na mão, e MCTS padrão quando a informação é completa.",
            )
            buffer_cap = st.select_slider(
                "Capacidade do Replay Buffer:",
                options=[10000, 50000, 100000, 250000, 500000],
                key="train_buffer_cap",
            )
        with col_g3:
            use_fp16 = st.toggle(
                "Aceleração Mixed Precision (FP16)",
                key="train_fp16",
                help="Acelera cálculos na GPU e economiza VRAM. Desativado automaticamente no modo CPU.",
            )
            auto_save = st.toggle("Auto-Save de Checkpoints (.pt)", value=True, key="train_auto_save")
            save_interval = st.number_input(
                "Salvar Checkpoint a cada N partidas:",
                min_value=5,
                max_value=100,
                key="train_save_interval",
                help="Frequência de gravação de novos checkpoints em disco.",
            )

        st.markdown("---")
        st.markdown("#### 🧠 Concorrência Híbrida ISMCTS & Telemetria Preditiva")
        col_ismcts_1, col_ismcts_2 = st.columns([2, 1])
        with col_ismcts_1:
            concurrency_options = ["threads", "multiprocessing", "direct_gpu", "sequential"]
            concurrency_labels = {
                "threads": "threads (Padrão/Estável - In-Process Multithread)",
                "multiprocessing": "multiprocessing (Actor-Evaluator IPC via Pipes)",
                "direct_gpu": "direct_gpu (Workers Spawnam Direto na GPU)",
                "sequential": "sequential (Determinizações Sequenciais in-process)",
            }
            selected_concurrency = st.selectbox(
                "Modo de Concorrência ISMCTS:",
                concurrency_options,
                index=0,
                format_func=lambda x: concurrency_labels.get(x, x),
                key="train_ismcts_concurrency",
                help="Estratégia de paralelização para os mundos determinizados do ISMCTS."
            )
        with col_ismcts_2:
            st.write("")
            force_direct_gpu = st.checkbox(
                "Forçar modo direct_gpu",
                key="train_force_direct_gpu",
                help="Força a execução de workers na GPU diretamente (alto consumo de VRAM por processo)."
            )
            if force_direct_gpu:
                selected_concurrency = "direct_gpu"

        # Nível de Log dos Bots de Treino
        st.markdown("---")
        st.markdown("#### 📝 Nível de Log dos Bots de Treino")
        log_level_options = {
            "0 - DEBUG (Tudo, incluindo scores de turno)": 0,
            "1 - INFO (Padrão - Fluxo de jogo, sideboard, ações)": 1,
            "2 - WARNING (Alertas, HTTP errors, respostas inesperadas)": 2,
            "3 - ERROR (Apenas erros - conexão, sideboard, decide_and_act)": 3,
        }
        current_log_level = os.environ.get("FAB_BOT_LOG_LEVEL", "1")
        try:
            current_log_level = int(current_log_level)
        except ValueError:
            current_log_level = 1
        
        log_level_labels = list(log_level_options.keys())
        log_level_values = list(log_level_options.values())
        default_index = log_level_values.index(current_log_level) if current_log_level in log_level_values else 1
        
        col_log_1, col_log_2 = st.columns([2, 1])
        with col_log_1:
            selected_log_label = st.selectbox(
                "Nível de Verbosidade dos Logs dos Bots:",
                log_level_labels,
                index=default_index,
                key="train_bot_log_level",
                help="Controla a verbosidade dos logs salvos em logs/Train_*_Bot*_debug.log. DEBUG=0 mostra scores de turno e espera; INFO=1 mostra fluxo normal; WARNING=2 mostra alertas; ERROR=3 mostra apenas erros críticos.",
            )
        with col_log_2:
            st.write("")
            st.write("")
            if st.button("Aplicar Nível de Log", use_container_width=True):
                os.environ["FAB_BOT_LOG_LEVEL"] = str(log_level_options[selected_log_label])
                st.success(f"Nível de log definido para: {selected_log_label}")
                st.toast(f"Log level: {selected_log_label}", icon="📝")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

        from config.settings import SETTINGS
        est_vram = SETTINGS.estimate_vram_usage(
            num_rooms=workers_count,
            ismcts_worlds=SETTINGS.ismcts_worlds,
            mode=selected_concurrency,
        )
        if gpu_available and SETTINGS.vram_gb > 0:
            if est_vram > SETTINGS.vram_gb:
                st.error(
                    f"⚠️ **Alerta de Sobrecarga de VRAM:** O setup selecionado (`{selected_concurrency}`) demandará "
                    f"~**{est_vram:.1f} GB** de VRAM, excedendo os **{SETTINGS.vram_gb:.1f} GB** físicos da GPU ({SETTINGS.gpu_name}). "
                    f"Risco iminente de CUDA Out of Memory (OOM)! Considere utilizar o modo `threads`."
                )
            elif est_vram > (SETTINGS.vram_gb * 0.85):
                st.warning(
                    f"⚡ **Atenção à VRAM:** Uso estimado de **{est_vram:.1f} GB** / **{SETTINGS.vram_gb:.1f} GB** disponíveis "
                    f"(`{selected_concurrency}` com {workers_count} salas). Operando próximo ao limite do hardware."
                )
            else:
                st.info(
                    f"📊 **Telemetria Preditiva de VRAM:** Uso estimado de **{est_vram:.1f} GB** / **{SETTINGS.vram_gb:.1f} GB** disponíveis "
                    f"(`{selected_concurrency}` com {workers_count} salas de treino)."
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
                    "training_decks": deck_slugs,
                    "ismcts_concurrency": selected_concurrency,
                })
                st.toast("⚡ Treinador de Deep RL iniciado com sucesso!", icon="🚀")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
        else:
            if st.button("🛑 Parar Treinamento com GPU", type="secondary", use_container_width=True):
                with st.spinner("Finalizando partidas ativas e liberando GPU/CPU..."):
                    orchestrator.stop()
                st.toast("Treinamento pausado com sucesso.", icon="🛑")
                st.warning("Treinador pausado com sucesso!")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    with col_t_btn2:
        if st.button("💾 Salvar Checkpoint Manual do Modelo", use_container_width=True):
            orchestrator.save_metrics()
            st.toast("Checkpoint manual e Replay Buffer salvos!", icon="💾")
            
        if st.button("🗑️ Limpar Replay Buffer", use_container_width=True):
            st.session_state.confirm_clear_buffer = True

        if st.session_state.get("confirm_clear_buffer", False):
            st.warning("⚠️ Tem certeza que deseja limpar o Replay Buffer? Isso não pode ser desfeito.")
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                if st.button("✔️ Sim, limpar", use_container_width=True):
                    if clear_replay_buffer():
                        st.success("Buffer limpo!")
                    else:
                        st.error("Falha ao limpar.")
                    st.session_state.confirm_clear_buffer = False
                    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
            with col_c2:
                if st.button("❌ Cancelar", use_container_width=True):
                    st.session_state.confirm_clear_buffer = False
                    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

    # Fragmento de Atualização em Tempo Real (a cada 4 segundos durante treino)
    @st.fragment(run_every="4s")
    def render_gpu_live_telemetry():
        if orchestrator.is_running:
            orchestrator.load_metrics()
        else:
            if not getattr(render_gpu_live_telemetry, "_loaded_once", False):
                orchestrator.load_metrics()
                render_gpu_live_telemetry._loaded_once = True
        st.divider()

        # Status Ativo da Sessão de Treino
        if orchestrator.is_running:
            cfg = orchestrator.config
            st.markdown(f"""
            <div style="background-color: #1e293b; padding: 15px; border-radius: 8px; border-left: 5px solid #22c55e; margin-bottom: 15px;">
                <h4 style="margin: 0; color: #22c55e;">🟢 Treinamento em Andamento (GPU Ativa)</h4>
                <p style="margin: 6px 0 0 0; color: #cbd5e1; font-size: 14px;">
                    <b>Dispositivo:</b> {cfg.get('device')} | <b>Batch:</b> {cfg.get('batch_size')} | <b>Concorrência:</b> {cfg.get('ismcts_concurrency', 'threads')} | <b>LR:</b> {cfg.get('learning_rate')} | <b>MCTS Sims:</b> {cfg.get('mcts_sims')} | <b>FP16:</b> {cfg.get('fp16')}<br>
                    <b>Confronto Atual em Execução:</b> <code>{orchestrator.stats.get('active_matchup', 'Rotativo')}</code>
                </p>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("### 📊 Telemetria de Treinamento em Tempo Real")
        st_m1, st_m2, st_m3, st_m4 = st.columns(4)
        st_m1.metric("Partidas Disputadas", orchestrator.stats.get("total_games", 0))
        max_cap = orchestrator.config.get("buffer_capacity", orchestrator.stats.get("buffer_capacity", 100000))
        real_samples = get_replay_buffer_sample_count()
        display_samples = max(real_samples, orchestrator.stats.get("samples_collected", 0))
        st_m2.metric("Amostras no Replay Buffer", f"{display_samples:,} / {max_cap:,}")
        st_m3.metric("Policy Loss (Ação)", orchestrator.stats.get("policy_loss", 0.0))
        st_m4.metric("Value Loss (Vitória MSE)", orchestrator.stats.get("value_loss", 0.0))

        # Histórico de Loss
        history = orchestrator.stats.get("history", [])
        if len(history) > 1:
            try:
                df_raw = pd.DataFrame(history)
                chart_cols = [c for c in ["epoch", "policy_loss", "value_loss", "total_loss"] if c in df_raw.columns]
                if len(chart_cols) >= 2 and "epoch" in chart_cols:
                    df_hist = df_raw[chart_cols].dropna(subset=["epoch"])
                    df_hist = df_hist.replace([np.inf, -np.inf], np.nan).fillna(0.0)
                    df_hist = df_hist.drop_duplicates(subset=["epoch"]).sort_values("epoch")
                    if len(df_hist) > 100:
                        step = max(1, len(df_hist) // 100)
                        df_hist = pd.concat([df_hist.iloc[::step], df_hist.iloc[[-1]]]).drop_duplicates(subset=["epoch"])
                    df_hist = df_hist.set_index("epoch")
                    col_map = {
                        "policy_loss": "Policy Loss",
                        "value_loss": "Value MSE Loss",
                        "total_loss": "Total Loss",
                    }
                    df_hist = df_hist.rename(columns=col_map)
                    if not df_hist.empty and df_hist.shape[0] > 1:
                        st.line_chart(df_hist)
            except Exception as e:
                st.caption(f"Aguardando dados numéricos para o gráfico de perda ({e}).")

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
