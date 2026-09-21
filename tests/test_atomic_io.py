"""
tests/test_atomic_io.py
=======================
Testes unitários dedicados para as funções de I/O atômico e lock de arquivos em ai/atomic_io.py.
"""

import json
import os
import tempfile
import pytest
from ai.atomic_io import atomic_json_save, file_lock


def test_atomic_json_save_dict(tmp_path):
    target = str(tmp_path / "test_data.json")
    data = {"hero": "dorinthea", "wins": 42, "rating": 1250.5}

    atomic_json_save(data, target)

    assert os.path.exists(target)
    with open(target, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data


def test_atomic_json_save_list(tmp_path):
    target = str(tmp_path / "test_list.json")
    data = ["card_1", "card_2", "card_3"]

    atomic_json_save(data, target)

    assert os.path.exists(target)
    with open(target, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data


def test_atomic_json_save_creates_nested_directories(tmp_path):
    target = str(tmp_path / "nested" / "deep" / "dir" / "state.json")
    data = {"nested": True}

    atomic_json_save(data, target)

    assert os.path.exists(target)
    with open(target, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded == data


def test_atomic_json_save_cleanup_on_error(tmp_path):
    target = str(tmp_path / "invalid.json")

    class Unserializable:
        pass

    data = {"bad": Unserializable()}

    with pytest.raises(TypeError):
        atomic_json_save(data, target)

    # Garante que nenhum arquivo temporário (.tmp) restou
    tmp_files = [f for f in os.listdir(str(tmp_path)) if f.endswith(".tmp")]
    assert len(tmp_files) == 0
    assert not os.path.exists(target)


def test_file_lock_acquisition_and_release(tmp_path):
    target = str(tmp_path / "locked_resource.json")
    lock_file = f"{target}.lock"

    with file_lock(target, timeout=2.0):
        assert os.path.exists(lock_file)

    # Deve ser possível readquirir o lock sequencialmente
    with file_lock(target, timeout=2.0):
        pass


def test_file_lock_timeout_when_held(tmp_path):
    import fcntl
    target = str(tmp_path / "resource.json")
    lock_file = f"{target}.lock"

    # Simula um lock externo ativo no arquivo
    with open(lock_file, "a") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            with pytest.raises(TimeoutError):
                with file_lock(target, timeout=0.1):
                    pass
        finally:
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
