"""Fixtures compartilhadas para a suíte de testes do FaB Talishar AI."""

import os
import tempfile
import pytest
import atexit
import shutil
import platform

if platform.system() == "Windows":
    pytest.skip("Testes requerem ambiente Linux/WSL2 para fcntl/atomic IO", allow_module_level=True)

_SESSION_TMP_DIR = tempfile.mkdtemp(prefix="fab_pytest_session_")
atexit.register(shutil.rmtree, _SESSION_TMP_DIR, ignore_errors=True)
os.environ["FAB_STATS_DB_PATH"] = os.path.join(_SESSION_TMP_DIR, "session_talishar_stats.db")
os.environ["FAB_SIM2REAL_LOG_FILE"] = os.path.join(_SESSION_TMP_DIR, "session_sim2real_anomalies.jsonl")

try:
    import ai.bot_runtime.card_name_oracle as _oracle_mod
    _oracle_mod.STATS_DB_PATH = os.environ["FAB_STATS_DB_PATH"]
except Exception:
    pass

try:
    import ai.training.assimilation as _assim_mod
    _assim_mod.DATA_DIR = _SESSION_TMP_DIR
except Exception:
    pass

from ai.policy.engine import PolicyEngine


def make_policy_engine(hero_name="generic", num_mcts_sims=0, use_gpu=False, **kwargs):
    """Factory para PolicyEngine com defaults seguros para testes unitários.

    Uso:
        pe = make_policy_engine()                           # genérico, sem MCTS
        pe = make_policy_engine("rhinar")                   # herói específico
        pe = make_policy_engine("marlinn", num_mcts_sims=5) # com MCTS
    """
    return PolicyEngine(hero_name=hero_name, num_mcts_sims=num_mcts_sims, use_gpu=use_gpu, **kwargs)


@pytest.fixture(autouse=True)
def _isolate_production_db_and_logs(tmp_path, monkeypatch):
    """Isola SQLite (stats.db), logs Sim2Real e métricas em tmp_path durante todos os testes."""
    import stats.db
    import ai.sim2real_detector

    test_db = str(tmp_path / "test_talishar_stats.db")
    test_log = str(tmp_path / "test_sim2real_anomalies.jsonl")
    monkeypatch.setenv("FAB_STATS_DB_PATH", test_db)
    monkeypatch.setenv("FAB_SIM2REAL_LOG_FILE", test_log)
    monkeypatch.setattr(stats.db, "_DEFAULT_DB_FILE", test_db)
    monkeypatch.setattr(stats.db, "DB_FILE", test_db)
    monkeypatch.setattr(ai.sim2real_detector, "_DEFAULT_LOG_FILE", test_log)
    monkeypatch.setattr(ai.sim2real_detector, "LOG_FILE", test_log)
    try:
        import ai.bot_runtime.card_name_oracle as oracle_mod
        monkeypatch.setattr(oracle_mod, "STATS_DB_PATH", test_db)
    except Exception:
        pass
    try:
        import ai.training.orchestrator as orch_mod
        monkeypatch.setattr(orch_mod, "METRICS_FILE", str(tmp_path / "test_training_metrics.json"))
    except Exception:
        pass


@pytest.fixture
def policy_engine():
    """PolicyEngine genérico sem MCTS para testes rápidos."""
    return make_policy_engine()
