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
