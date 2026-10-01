import pytest
from ai.dynamic_rule_tuner import (
    MIN_WEIGHT,
    MAX_WEIGHT,
    DEFAULT_MULTIPLIERS,
    is_aggro_or_combo_hero,
    diagnose_deck_losses,
    apply_causal_tuning,
    _fetch_deck_match_metrics,
    sync_multipliers_with_stats,
    load_multipliers,
    get_multipliers_for_hero,
)
import stats.db


@pytest.fixture(autouse=True)
def setup_isolated_db(monkeypatch, tmp_path):
    test_db = str(tmp_path / "test_tuner.db")
    monkeypatch.setattr("stats.db.DB_FILE", test_db)
    monkeypatch.setattr("stats.storage.STATS_FILE", test_db)
    monkeypatch.setattr("stats_manager.STATS_FILE", test_db)
    stats.db.init_db()
    yield


def test_tuner_anti_spiral_bounds():
    """Valida que MIN_WEIGHT é 0.85 e MAX_WEIGHT é 1.15 conforme especificação."""
    assert MIN_WEIGHT == 0.85
    assert MAX_WEIGHT == 1.15
    for k, v in DEFAULT_MULTIPLIERS.items():
        assert v == 1.0


def test_diagnose_deck_losses_causes():
    """Valida os diagnósticos causais de Flesh and Blood."""
    # 1. Tempo Race: Oponente sobreviveu com <= 15% de HP (ex: CC 40 HP -> opp <= 6 HP)
    metrics_close = {"avg_turns": 14.0, "avg_opp_hp": 4.0}
    assert diagnose_deck_losses(metrics_close, "bravo") == "tempo_race"

    # 2. Overblocking Passivo: muitos turnos e DPS muito baixo
    metrics_overblock = {"avg_turns": 22.0, "avg_opp_hp": 30.0}
    assert diagnose_deck_losses(metrics_overblock, "bravo") == "overblocking"

    # 3. Baixa Conversão de Mão: turnos normais, mas DPS ineficiente
    metrics_low_conv = {"avg_turns": 14.0, "avg_opp_hp": 32.0}
    assert diagnose_deck_losses(metrics_low_conv, "bravo") == "low_hand_conversion"

    # 4. Fast Bleed: jogo acabou rápido demais
    metrics_bleed = {"avg_turns": 7.0, "avg_opp_hp": 25.0}
    assert diagnose_deck_losses(metrics_bleed, "bravo") == "fast_bleed"

    # 5. Generic Loss
    metrics_generic = {"avg_turns": 14.0, "avg_opp_hp": 16.0}
    assert diagnose_deck_losses(metrics_generic, "bravo") == "generic_loss"


def test_tuner_50_consecutive_losses_strict_clamp():
    """
    Simula 50 derrotas consecutivas com causas variadas (incluindo overblocking)
    e garante matematicamente que nenhum peso ultrapassa [0.85, 1.15].
    """
    mults = dict(DEFAULT_MULTIPLIERS)
    causes = ["overblocking", "low_hand_conversion", "fast_bleed", "tempo_race", "generic_loss"]

    for i in range(50):
        c = causes[i % len(causes)]
        mults = apply_causal_tuning(mults, c)
        for k, v in mults.items():
            assert MIN_WEIGHT <= v <= MAX_WEIGHT, f"Peso {k}={v} violou os limites [{MIN_WEIGHT}, {MAX_WEIGHT}]!"

    # Caso extremo: 50 derrotas consecutivas de puro overblocking
    mults_overblock = dict(DEFAULT_MULTIPLIERS)
    for _ in range(50):
        mults_overblock = apply_causal_tuning(mults_overblock, "overblocking")
        for k, v in mults_overblock.items():
            assert MIN_WEIGHT <= v <= MAX_WEIGHT

    # block_weight deve estar cravado no piso 0.85 e NÃO cair mais
    assert mults_overblock["block_weight"] == 0.85
    assert mults_overblock["absorb_tempo_bonus"] == 1.15


def test_sync_multipliers_with_stats_causal_flow():
    """Valida o ciclo completo de sincronização e persistência no SQLite."""
    with stats.db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO hero_elo (deck_name, matches, wins, losses, elo, human_matches, human_wins)
            VALUES ('Rhinar', 10, 2, 8, 1100, 1, 1)
        ''')
        # Inserir partidas com muitos turnos e opp com vida alta (overblocking)
        for i in range(5):
            cursor.execute('''
                INSERT INTO match_history (room_id, date, winner, p1_deck, p2_deck, p1_health, p2_health, turns)
                VALUES (?, '01/10/2026', 'Bot 2 (Katsu)', 'Rhinar', 'Katsu', 0, 32, 24)
            ''', (f"room_test_{i}",))
        conn.commit()

    summary = sync_multipliers_with_stats()
    assert "rhinar" in summary
    r_rules = summary["rhinar"]
    assert MIN_WEIGHT <= r_rules["block_weight"] <= MAX_WEIGHT
    assert MIN_WEIGHT <= r_rules["attack_weight"] <= MAX_WEIGHT
    assert r_rules["block_weight"] < 1.0, "Overblocking deve reduzir block_weight!"
    assert r_rules["absorb_tempo_bonus"] > 1.0, "Overblocking deve aumentar absorb_tempo_bonus!"

    # Leitura e resolução por herói
    loaded = load_multipliers()
    assert "rhinar" in loaded
    hero_mults = get_multipliers_for_hero("rhinar")
    assert hero_mults["block_weight"] == r_rules["block_weight"]

    # Backward compatibility
    assert is_aggro_or_combo_hero("rhinar") is True
