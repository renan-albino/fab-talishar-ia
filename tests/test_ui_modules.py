"""
tests/test_ui_modules.py - Testes unitários para a arquitetura modular da UI (ui/ e ui/tabs/).
"""

import os
import json
import tempfile
import pytest


def test_ui_imports():
    """Valida a importação de todos os submódulos e funções exportadas do pacote ui."""
    import ui
    import ui.helpers as helpers
    import ui.tabs as tabs

    # Verifica helpers
    expected_helpers = [
        "get_gpu_info",
        "get_orchestrator",
        "get_total_training_games",
        "get_cached_services_status",
        "get_cached_saved_decks",
        "get_cached_stats_data",
        "read_text_tail",
        "read_jsonl_tail",
        "get_fast_line_count",
        "get_suggested_training_profile",
    ]
    for h in expected_helpers:
        assert hasattr(helpers, h), f"Função {h} ausente em ui.helpers"
        assert callable(getattr(helpers, h)), f"{h} não é chamável em ui.helpers"

    # Verifica tabs
    expected_tabs = [
        "render_tab_play",
        "render_tab_arena",
        "render_tab_training",
        "render_tab_tournaments",
        "render_tab_decks",
        "render_tab_analytics",
        "render_tab_ismcts",
    ]
    for t in expected_tabs:
        assert hasattr(tabs, t), f"Função {t} ausente em ui.tabs"
        assert callable(getattr(tabs, t)), f"{t} não é chamável em ui.tabs"


def test_ui_helpers_tail_and_count():
    """Valida funções de leitura otimizada de cauda (tail) e contagem de linhas."""
    from ui.helpers import read_text_tail, read_jsonl_tail, get_fast_line_count

    with tempfile.TemporaryDirectory() as tmpdir:
        # Teste com arquivo inexistente
        assert read_text_tail(os.path.join(tmpdir, "nonexistent.txt")) == ""
        assert read_jsonl_tail(os.path.join(tmpdir, "nonexistent.jsonl")) == []
        assert get_fast_line_count(os.path.join(tmpdir, "nonexistent.txt")) == 0

        # Teste com arquivo vazio
        empty_file = os.path.join(tmpdir, "empty.txt")
        with open(empty_file, "w") as f:
            pass
        assert read_text_tail(empty_file) == ""
        assert read_jsonl_tail(empty_file) == []
        assert get_fast_line_count(empty_file) == 0

        # Teste com arquivo de texto
        text_file = os.path.join(tmpdir, "sample.txt")
        lines = [f"Linha {i}" for i in range(100)]
        with open(text_file, "w") as f:
            f.write("\n".join(lines) + "\n")

        tail_res = read_text_tail(text_file, max_lines=5)
        tail_lines = tail_res.splitlines()
        assert len(tail_lines) == 5
        assert tail_lines[-1] == "Linha 99"
        assert tail_lines[0] == "Linha 95"
        assert get_fast_line_count(text_file) == 100

        # Teste com arquivo JSONL
        jsonl_file = os.path.join(tmpdir, "sample.jsonl")
        json_records = [{"id": i, "val": f"item_{i}"} for i in range(50)]
        with open(jsonl_file, "w") as f:
            for rec in json_records:
                f.write(json.dumps(rec) + "\n")

        records_tail = read_jsonl_tail(jsonl_file, max_lines=10)
        assert len(records_tail) == 10
        assert records_tail[-1]["id"] == 49
        assert records_tail[0]["id"] == 40


def test_ui_helpers_training_profile():
    """Valida os perfis sugeridos de treinamento em modo equilibrado e turbo."""
    from ui.helpers import get_suggested_training_profile

    # Modo CPU
    prof_cpu_bal = get_suggested_training_profile("cpu", mode="balanced")
    assert "workers" in prof_cpu_bal
    assert "batch_size" in prof_cpu_bal
    assert prof_cpu_bal["use_fp16"] is False
    assert prof_cpu_bal["workers"] >= 1

    prof_cpu_turbo = get_suggested_training_profile("cpu", mode="turbo")
    assert "workers" in prof_cpu_turbo
    assert prof_cpu_turbo["batch_size"] >= prof_cpu_bal["batch_size"]

    # Modo CUDA
    prof_cuda_bal = get_suggested_training_profile("cuda:0", mode="balanced")
    assert "workers" in prof_cuda_bal
    assert "mcts_sims" in prof_cuda_bal

    prof_cuda_turbo = get_suggested_training_profile("cuda:0", mode="turbo")
    assert "workers" in prof_cuda_turbo
