import streamlit as st
import subprocess
import uuid
import json
import os
import time
import pandas as pd
from deck_parser import parse_deck_text, save_deck_to_workspace, list_saved_decks, set_active_deck, delete_saved_deck, update_saved_deck, validate_deck_against_db
from stats_manager import get_stats_data, reset_stats, delete_deck_stat, sync_training_matches
from tournament_manager import TournamentManager
from config.settings import SETTINGS
import frontend_manager

st.set_page_config(page_title="FaB AI Master - GPU Deep RL", layout="wide", initial_sidebar_state="expanded")

@st.cache_resource
def get_gpu_info():
    """Detecta GPU via nvidia-smi em ~50ms sem importar torch. Fallback para torch se necessário."""
    import shutil
    if shutil.which("nvidia-smi"):
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=0.8
            )
            if res.returncode == 0 and res.stdout.strip():
                line = res.stdout.strip().splitlines()[0]
                parts = [p.strip() for p in line.split(",")]
                name = parts[0]
                vram_mb = float(parts[1]) if len(parts) > 1 else 0.0
                return True, name, round(vram_mb / 1024.0, 1)
        except Exception:
            pass
    try:
        import torch
        if torch.cuda.is_available():
            vram = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 1)
            return True, torch.cuda.get_device_name(0), vram
    except Exception:
        pass
    return False, "CPU", 0.0

@st.cache_resource
def get_orchestrator():
    """Carrega o GPUTrainingOrchestrator de forma lazy apenas quando a aba de treino for acessada."""
    from ai.trainer import GPUTrainingOrchestrator
    return GPUTrainingOrchestrator()

@st.cache_data(ttl=2)
def get_total_training_games() -> int:
    """Lê rapidamente o total de partidas do arquivo de métricas sem instanciar o orquestrador."""
    metrics_file = os.path.join("data", "training_metrics.json")
    if os.path.exists(metrics_file):
        try:
            with open(metrics_file, "r") as mf:
                return json.load(mf).get("total_games", 0)
        except Exception:
            pass
    return 0

# Título Principal com Badge de GPU e Status do Frontend
gpu_available, gpu_name, gpu_vram = get_gpu_info()

# Helpers de Cache de Alta Performance (Eliminam gargalos de I/O em reruns)
@st.cache_data(ttl=4)
def get_cached_services_status():
    return frontend_manager.is_frontend_running(deep=False), frontend_manager.is_backend_running(deep=False)

@st.cache_data(ttl=5)
def get_cached_saved_decks():
    return list_saved_decks()

@st.cache_data(ttl=3)
def get_cached_stats_data():
    return get_stats_data()

def read_text_tail(filepath: str, max_lines: int = 80, chunk_size: int = 32768) -> str:
    """Lê as últimas N linhas de um arquivo de texto sem carregar o arquivo inteiro na memória."""
    if not os.path.exists(filepath):
        return ""
    try:
        fsize = os.path.getsize(filepath)
        if fsize == 0:
            return ""
        with open(filepath, "rb") as f:
            if fsize <= chunk_size:
                lines = f.read().decode("utf-8", errors="replace").splitlines()
                return "\n".join(lines[-max_lines:])
            f.seek(max(0, fsize - chunk_size))
            chunk = f.read().decode("utf-8", errors="replace")
            lines = chunk.splitlines()
            return "\n".join(lines[-max_lines:])
    except Exception:
        return ""

def read_jsonl_tail(filepath: str, max_lines: int = 100, chunk_size: int = 65536) -> list:
    """Lê eficientemente apenas as últimas N linhas de um arquivo jsonl grande sem carregar tudo na memória."""
    if not os.path.exists(filepath):
        return []
    lines = []
    try:
        file_size = os.path.getsize(filepath)
        if file_size == 0:
            return []
        with open(filepath, "rb") as f:
            if file_size <= chunk_size:
                raw_lines = f.read().decode("utf-8", errors="replace").splitlines()
                for l in reversed(raw_lines):
                    l_s = l.strip()
                    if l_s:
                        lines.append(l_s)
                        if len(lines) >= max_lines:
                            break
            else:
                buffer = b""
                f.seek(0, os.SEEK_END)
                pos = f.tell()
                while pos > 0 and len(lines) < max_lines:
                    read_size = min(chunk_size, pos)
                    pos -= read_size
                    f.seek(pos)
                    chunk = f.read(read_size)
                    buffer = chunk + buffer
                    parts = buffer.split(b"\n")
                    buffer = parts[0]
                    for p in reversed(parts[1:]):
                        p_s = p.strip().decode("utf-8", errors="replace")
                        if p_s:
                            lines.append(p_s)
                            if len(lines) >= max_lines:
                                break
                if buffer and len(lines) < max_lines:
                    p_s = buffer.strip().decode("utf-8", errors="replace")
                    if p_s:
                        lines.append(p_s)

        records = []
        for l in reversed(lines):
            try:
                records.append(json.loads(l))
            except Exception:
                pass
        return records
    except Exception:
        return []

@st.cache_data(ttl=15)
def get_fast_line_count(filepath: str) -> int:
    """Conta rapidamente as linhas de um arquivo grande lendo blocos binários de 1MB com cache de 15s."""
    if not os.path.exists(filepath):
        return 0
    try:
        with open(filepath, "rb") as f:
            return sum(chunk.count(b"\n") for chunk in iter(lambda: f.read(1024 * 1024), b""))
    except Exception:
        return 0

def get_suggested_training_profile(device_str: str, mode: str = "balanced") -> dict:
    """
    Calcula parâmetros de treinamento sugeridos:
      - mode='balanced': ~75-80% de carga segura (permite uso normal do PC, navegador, vídeos, sem engasgos).
      - mode='turbo': ~95% de carga máxima (ideal para treino noturno, ausente ou remoto, extraindo todo o potencial do hardware).
    """
    is_gpu = "cuda" in device_str.lower() and gpu_available
    try:
        from config.settings import SETTINGS
        vram_gb = gpu_vram if gpu_vram > 0 else getattr(SETTINGS, "vram_gb", 0.0)
        cpu_cores = getattr(SETTINGS, "cpu_logical", 4)
        gpu_name_str = gpu_name
    except Exception:
        vram_gb = gpu_vram if gpu_available else 0.0
        cpu_cores = os.cpu_count() or 4
        gpu_name_str = gpu_name

    is_turbo = (mode == "turbo")

    if not is_gpu:
        if is_turbo:
            turbo_workers = max(2, min(5, (cpu_cores - 2) // 2))
            return {
                "device_label": f"CPU ({cpu_cores} threads)",
                "mode_name": "🔥 Modo Turbo CPU (~90% Carga)",
                "workers": turbo_workers,
                "batch_size": 256,
                "mcts_sims": 25,
                "save_interval": 25,
                "use_fp16": False,
                "buffer_capacity": 100000,
                "description": f"🔥 Modo Turbo CPU (~90% carga) • {turbo_workers} workers ({turbo_workers*2} bots) • MCTS 25 • Rendimento máximo sem travar o sistema."
            }
        else:
            safe_workers = max(1, min(2, (cpu_cores - 2) // 4))
            return {
                "device_label": f"CPU ({cpu_cores} threads)",
                "mode_name": "⚖️ Modo Equilibrado CPU (~50% Carga)",
                "workers": safe_workers,
                "batch_size": 128,
                "mcts_sims": 15,
                "save_interval": 15,
                "use_fp16": False,
                "buffer_capacity": 50000,
                "description": f"⚖️ Modo CPU Seguro (~50% carga) • {safe_workers} workers ({safe_workers*2} bots) • MCTS 15 • Sistema 100% livre para uso normal do PC."
            }

    # Perfil para GPU calibrado por faixa de VRAM:
    if vram_gb <= 6.5:
        if is_turbo:
            turbo_workers = max(2, min(5, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "🔥 Modo Turbo GPU (~90% Carga)",
                "workers": turbo_workers,
                "batch_size": 512,
                "mcts_sims": 45,
                "save_interval": 30,
                "use_fp16": True,
                "buffer_capacity": 250000,
                "description": f"🔥 Turbo Máximo (~90% GPU/CPU) • {turbo_workers} workers ({turbo_workers*2} bots) • Batch 512 (~5.0 GB VRAM) • MCTS 45 • Máxima velocidade para treino noturno ou remoto sem travar o webserver."
            }
        else:
            safe_workers = max(1, min(3, (cpu_cores - 2) // 3))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~65% Carga)",
                "workers": safe_workers,
                "batch_size": 256,
                "mcts_sims": 25,
                "save_interval": 20,
                "use_fp16": True,
                "buffer_capacity": 100000,
                "description": f"⚖️ {gpu_name} (~65% carga) • {safe_workers} workers ({safe_workers*2} bots) • Batch 256 • ~4 GB VRAM e 6+ threads livres para uso geral do PC."
            }
    elif vram_gb <= 12.5:
        if is_turbo:
            turbo_workers = max(3, min(7, (cpu_cores - 2) // 2))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "🔥 Modo Turbo GPU (~90% Carga)",
                "workers": turbo_workers,
                "batch_size": 1024,
                "mcts_sims": 60,
                "save_interval": 35,
                "use_fp16": True,
                "buffer_capacity": 500000,
                "description": f"🔥 Turbo Máximo (~90% carga) • {turbo_workers} workers ({turbo_workers*2} bots) • Batch 1024 • MCTS 60 • Treinamento de alta densidade sem travas."
            }
        else:
            safe_workers = max(2, min(4, (cpu_cores - 2) // 3))
            return {
                "device_label": f"{gpu_name} ({vram_gb:.1f} GB VRAM)",
                "mode_name": "⚖️ Modo Equilibrado GPU (~70% Carga)",
                "workers": safe_workers,
                "batch_size": 512,
                "mcts_sims": 35,
                "save_interval": 25,
                "use_fp16": True,
                "buffer_capacity": 250000,
                "description": f"⚖️ {gpu_name} (~70% carga) • {safe_workers} workers ({safe_workers*2} bots) • Batch 512 • Excelente velocidade com folga de sistema."
            }
    elif vram_gb <= 20.0:
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

fe_running, be_running = get_cached_services_status()

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
deck_options = {f"{d.get('name', d.get('slug'))} ({str(d.get('format', 'blitz')).upper()} - {d.get('total_cards', 0)} cartas)": d.get('slug') for d in saved_decks}

# Menu Principal de Navegação (Carregamento Lazy Instantâneo)
MENU_OPTIONS = [
    "🎮 Jogar no Talishar (Humano vs Bot)",
    "⚔️ Arena de Bots & Simulação",
    "⚡ Treinamento com GPU (Deep RL)",
    "🏆 Torneios Customizados",
    "📦 Gerenciador & Editor de Decks",
    "📈 Analytics & ELO por Deck",
    "🌐 Telemetria ISMCTS"
]

active_tab = st.segmented_control(
    "Navegação Principal",
    MENU_OPTIONS,
    default=MENU_OPTIONS[0],
    label_visibility="collapsed",
    width="stretch",
    key="dashboard_active_tab"
) or MENU_OPTIONS[0]

# ==============================================================================
# ABA 1: JOGAR NO TALISHAR (HUMANO VS BOT AI)
# ==============================================================================
if active_tab == MENU_OPTIONS[0]:
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
        st.link_button("👉 ENTRAR NA PARTIDA (Abrir Lobby no Navegador)", match_info['lobby_url'], type="primary", use_container_width=True)

    st.markdown("---")
    st.subheader("🕹️ Monitor de Sala & Análise de Pruning (Humano vs Bot)")
    st.caption("Acompanhe os logs da sala em tempo real, revise decisões do bot e copie sumários para análise e poda de jogadas (pruning).")

    # Descobrir salas de partidas Humano vs Bot
    logs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
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

# ==============================================================================
# ABA 2: ARENA DE COMBATE & TABULEIRO VISUAL
# ==============================================================================
elif active_tab == MENU_OPTIONS[1]:
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
            subprocess.Popen(["./venv/bin/python", "-u", "bot_client.py", "--room", room_id, "--deck", f"decks/{bot1_deck_slug}.json", "--role", "host", "--name", "Bot1"], stdout=out1, stderr=out1, start_new_session=True)
            time.sleep(0.1)
            out2 = open(f"logs/{room_id}_Bot2_terminal.log", "w")
            subprocess.Popen(["./venv/bin/python", "-u", "bot_client.py", "--room", room_id, "--deck", f"decks/{bot2_deck_slug}.json", "--role", "join", "--name", "Bot2"], stdout=out2, stderr=out2, start_new_session=True)
        st.success(f"{num_matches} partida(s) de alta velocidade iniciada(s)!")

    st.divider()

    @st.cache_data(ttl=2)
    def get_available_rooms(session_rooms_key: str = ""):
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
                "_join_deck.txt"
            )
            for fname in os.listdir("logs"):
                if fname.endswith(suffixes):
                    for s in suffixes:
                        if fname.endswith(s):
                            room_id = fname[:-len(s)]
                            if room_id:
                                discovered.add(room_id)
                            break
        for r in st.session_state.get("rooms", []):
            if r:
                discovered.add(r)
        return sorted(list(discovered), reverse=True)

    @st.fragment(run_every="3s")
    def render_arena_board():
        available_rooms = get_available_rooms(str(st.session_state.get("rooms", [])))
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
            import html
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
                        _FALLBACK_DECK_CACHE[clean] = res
                        return res
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

    render_arena_board()

# ==============================================================================
# ABA 3: TREINAMENTO COM GPU (DEEP RL + ROTAÇÃO DE DECKS)
# ==============================================================================
elif active_tab == MENU_OPTIONS[2]:
    orchestrator = get_orchestrator()
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
                "Simulações ISMCTS / MCTS por Jogada:",
                min_value=5,
                max_value=200,
                key="train_mcts_sims",
                help="Profundidade da busca na árvore. O motor utiliza ISMCTS (Information Set MCTS) simulando múltiplos mundos determinizados quando o oponente tem cartas ocultas na mão, e MCTS padrão quando a informação é completa."
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
                    <b>Dispositivo:</b> {cfg.get('device')} | <b>Batch:</b> {cfg.get('batch_size')} | <b>LR:</b> {cfg.get('learning_rate')} | <b>MCTS Sims:</b> {cfg.get('mcts_sims')} | <b>FP16:</b> {cfg.get('fp16')}<br>
                    <b>Confronto Atual em Execução:</b> <code>{orchestrator.stats.get('active_matchup', 'Rotativo')}</code>
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("### 📊 Telemetria de Treinamento em Tempo Real")
        st_m1, st_m2, st_m3, st_m4 = st.columns(4)
        st_m1.metric("Partidas Disputadas", orchestrator.stats.get("total_games", 0))
        max_cap = orchestrator.config.get("buffer_capacity", orchestrator.stats.get("buffer_capacity", 100000))
        st_m2.metric("Amostras no Replay Buffer", f"{orchestrator.stats.get('samples_collected', 0):,} / {max_cap:,}")
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
# ABA 4: TORNEIOS CUSTOMIZADOS
# ==============================================================================
elif active_tab == MENU_OPTIONS[3]:
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
# ABA 5: GERENCIADOR & EDITOR DE DECKS
# ==============================================================================
elif active_tab == MENU_OPTIONS[4]:
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
                            get_cached_saved_decks.clear()
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
                            get_cached_saved_decks.clear()
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
        
        # Controle de versão do formulário para garantir limpeza confiável dos campos após importação
        if "import_form_id" not in st.session_state:
            st.session_state["import_form_id"] = 0
        if "import_errors" not in st.session_state:
            st.session_state["import_errors"] = []

        form_id = st.session_state["import_form_id"]

        with col_imp1:
            deck_text_input = st.text_area(
                "Texto do Deck (FaBrary / FabDB):", height=230,
                key=f"deck_import_text_{form_id}",
                placeholder="""Name: Calling: Hamburg 1st 🇩🇪\nHero: Dash I/O\nFormat: Classic Constructed\n\nArena cards\n1x Achilles Accelerator\n1x Symbiosis Shot\n\nDeck cards\n3x Backup Protocol: RED (red)\n3x Zero to Sixty (red)"""
            )
            col_b1, col_b2, col_b3 = st.columns([3, 2, 1])
            with col_b1:
                custom_name = st.text_input(
                    "Nome Customizado do Deck (opcional):",
                    key=f"deck_import_name_{form_id}",
                    placeholder="Ex: Dash CC Pro"
                )
            with col_b2:
                st.write(""); st.write("")
                btn_save = st.button("💾 Importar e Validar Deck", type="primary", use_container_width=True)
            with col_b3:
                st.write(""); st.write("")
                if st.button("🧹 Limpar", use_container_width=True, help="Limpa o texto e erros do formulário"):
                    st.session_state["import_form_id"] = form_id + 1
                    st.session_state["import_errors"] = []
                    st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

            if btn_save:
                if deck_text_input and deck_text_input.strip():
                    parsed = parse_deck_text(deck_text_input, default_name=custom_name if custom_name else "Meu Deck")
                    if custom_name and custom_name.strip():
                        parsed["name"] = custom_name.strip()
                        
                    is_valid, errors, meta_info = validate_deck_against_db(parsed)
                    if not is_valid:
                        st.session_state["import_errors"] = errors
                        st.toast("⚠️ Inconsistências encontradas no Deck!", icon="⚠️")
                    else:
                        res = save_deck_to_workspace(parsed)
                        get_cached_saved_decks.clear()
                        # Incrementa form_id para resetar os campos de texto no Streamlit
                        st.session_state["import_form_id"] = form_id + 1
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
# ABA 6: ANALYTICS & ELO POR DECK
# ==============================================================================
elif active_tab == MENU_OPTIONS[5]:
    col_st_hdr1, col_st_hdr2 = st.columns([3, 1])
    with col_st_hdr1:
        st.subheader("📈 Leaderboard de ELO & Desempenho por Deck")
    with col_st_hdr2:
        if st.button("🔄 Atualizar Leaderboard", key="btn_refresh_elo_data", use_container_width=True):
            get_cached_stats_data.clear()
            st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
    
    @st.fragment()
    def render_stats_leaderboard():
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
                    f"🎯 Log ELO Verificado ({tot_m:,})"
                ]
                scope_mode = st.radio(
                    "Escopo de Análise:",
                    scope_options,
                    index=0,
                    key="elo_scope_radio",
                    horizontal=True
                )

            is_global_scope = scope_mode.startswith("🌐")
            scale_factor = (total_training_games / tot_m) if (tot_m > 0 and is_global_scope) else 1.0

            if is_global_scope and total_training_games > tot_m:
                st.caption(f"ℹ️ **Modo Panorama Global Ativo:** Exibindo a análise projetada sobre todas as **{total_training_games:,} partidas** disputadas pelo motor de IA. O Win Rate % e o Rating ELO são calculados a partir da telemetria das **{tot_m} partidas ranqueadas**.")

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

    render_stats_leaderboard()

    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        stats_data = get_cached_stats_data()
        tot_m = stats_data.get("total_matches", 0)
        total_training_games = get_total_training_games()
        if total_training_games > tot_m:
            if st.button(f"⚡ Sincronizar Base ELO com Todas as Partidas do Treino ({total_training_games:,})", use_container_width=True):
                sync_training_matches(total_training_games)
                get_cached_stats_data.clear()
                st.toast(f"Estatísticas de ELO sincronizadas com todas as {total_training_games:,} partidas!", icon="🎉")
                st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()
    with col_btn2:
        if st.button("🗑️ Resetar Todas as Estatísticas de ELO", use_container_width=True):
            reset_stats()
            get_cached_stats_data.clear()
            st.toast("Estatísticas resetadas!", icon="🗑️")
            st.rerun() if hasattr(st, "rerun") else st.experimental_rerun()

# ==============================================================================
# ABA 7: TELEMETRIA ISMCTS EM TEMPO REAL
# ==============================================================================
elif active_tab == MENU_OPTIONS[6]:
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
