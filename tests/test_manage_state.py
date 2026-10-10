"""
tests/test_manage_state.py
==========================
Testes unitários para o gerenciador de estado scripts/manage_state.py.
Valida exportação, importação e formatação do pacote de checkpoints.
"""

import os
import sys
import tarfile
import pytest
from unittest.mock import patch

# Importa o módulo manage_state a partir do diretório scripts/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts")))
import manage_state


def test_format_size():
    assert manage_state.format_size(500) == "500 B"
    assert manage_state.format_size(2048) == "2.0 KB"
    assert manage_state.format_size(5 * 1024 * 1024) == "5.00 MB"


def test_get_release_notes():
    notes = manage_state.get_release_notes("v1.0.0-test")
    assert "v1.0.0-test" in notes
    assert "FaB Talishar AI" in notes
    assert "Métricas do Checkpoint" in notes


def test_export_and_import_state(tmp_path):
    # Cria uma estrutura simulada de DATA_DIR e BASE_DIR
    mock_base = tmp_path / "project"
    mock_data = mock_base / "data"
    mock_checkpoints = mock_data / "checkpoints"
    mock_checkpoints.mkdir(parents=True)

    # Cria alguns arquivos essenciais falsos
    teacher_pt = mock_checkpoints / "teacher_latest.pt"
    teacher_pt.write_bytes(b"mock_teacher_weights")

    metrics_json = mock_data / "training_metrics.json"
    metrics_json.write_text('{"epochs_completed": 10, "total_games": 100, "samples_collected": 500, "total_loss": 0.25}')

    bundle_path = str(tmp_path / "test_bundle.tar.gz")

    with patch.object(manage_state, "BASE_DIR", str(mock_base)), \
         patch.object(manage_state, "DATA_DIR", str(mock_data)):

        # 1. Exporta o estado
        manage_state.export_state(bundle_path)
        assert os.path.exists(bundle_path)

        # Valida que o tar.gz contém os arquivos esperados
        with tarfile.open(bundle_path, "r:gz") as tar:
            names = tar.getnames()
            assert any("teacher_latest.pt" in n for n in names)
            assert any("training_metrics.json" in n for n in names)

        # 2. Deleta os arquivos originais
        teacher_pt.unlink()
        metrics_json.unlink()
        assert not teacher_pt.exists()
        assert not metrics_json.exists()

        # 3. Importa o estado de volta
        manage_state.import_state(bundle_path)
        assert teacher_pt.exists()
        assert teacher_pt.read_bytes() == b"mock_teacher_weights"
        assert metrics_json.exists()


def test_show_info_executes_cleanly(tmp_path, capsys):
    mock_data = tmp_path / "data"
    mock_data.mkdir()

    with patch.object(manage_state, "DATA_DIR", str(mock_data)):
        manage_state.show_info()

    captured = capsys.readouterr()
    assert "INFORMAÇÕES DE ESTADO ATUAL" in captured.out


def test_clean_training_state_with_backup(tmp_path):
    mock_base = tmp_path / "project"
    mock_data = mock_base / "data"
    mock_logs = mock_base / "logs"
    mock_data.mkdir(parents=True)
    mock_logs.mkdir(parents=True)

    # Cria arquivos simulados de buffer, métricas e anomalias
    buf = mock_data / "replay_buffer.npz"
    buf.write_bytes(b"mock_buffer_content")

    metrics = mock_data / "training_metrics.json"
    metrics.write_text('{"epochs_completed": 100, "samples_collected": 5000, "total_games": 200}')

    stats = mock_data / "training_stats.json"
    stats.write_text('{"total_matches": 50, "bot1_elo": 1400}')

    sim2real = mock_logs / "sim2real_anomalies.jsonl"
    sim2real.write_text('{"anomaly_type": "MOCK_ANOMALY"}\n')

    backup_bundle = str(tmp_path / "custom_backup.tar.gz")

    with patch.object(manage_state, "BASE_DIR", str(mock_base)), \
         patch.object(manage_state, "DATA_DIR", str(mock_data)), \
         patch("stats.db.clear_sim2real_anomalies", return_value=5):

        summary = manage_state.clean_training_state(
            backup=True,
            include_buffer=True,
            include_metrics=True,
            include_sim2real=True,
            backup_path=backup_bundle,
        )

        # 1. Verifica backup
        assert summary["backup_created"] == backup_bundle
        assert os.path.exists(backup_bundle)
        with tarfile.open(backup_bundle, "r:gz") as tar:
            names = tar.getnames()
            assert any("replay_buffer.npz" in n for n in names)
            assert any("training_metrics.json" in n for n in names)
            assert any("sim2real_anomalies.jsonl" in n for n in names)

        # 2. Verifica remoção do buffer
        assert not buf.exists()
        assert summary["buffer_cleared"] is True

        # 3. Verifica reset de métricas para 0
        import json
        with open(metrics, "r") as f:
            m = json.load(f)
            assert m["epochs_completed"] == 0
            assert m["samples_collected"] == 0
            assert m["total_games"] == 0

        # 4. Verifica limpeza de anomalias
        assert not sim2real.exists()
        assert summary["sim2real_db_records_cleared"] == 5
