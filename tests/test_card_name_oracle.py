"""
tests/test_card_name_oracle.py
==============================
Testes unitários para o oráculo dinâmico de cartas (ai/bot_runtime/card_name_oracle.py).
"""

import os
import sqlite3
import pytest
from unittest.mock import MagicMock, patch

from ai.bot_runtime.card_name_oracle import (
    get_learned_card_name_target,
    compute_card_impact,
    _resolve_card_details,
    _clean_card_name,
)
from ai.bot_runtime import choice_handler


class MockClient:
    def __init__(self, player_id: int = 1):
        self.player_id = player_id
        self.sent_actions = []
        self.logs = []

    def send_action(self, mode: int, button_input: str = "", input_text: str = ""):
        self.sent_actions.append({"mode": mode, "input_text": input_text, "button_input": button_input})

    def log(self, msg: str):
        self.logs.append(msg)


def test_clean_card_name():
    assert _clean_card_name("crippling_crush_red") == "Crippling Crush"
    assert _clean_card_name("lumina_ascension_yellow") == "Lumina Ascension"
    assert _clean_card_name("Sink Below") == "Sink Below"
    assert _clean_card_name("command_and_conquer") == "Command And Conquer"


def test_resolve_card_details():
    name, meta, sem = _resolve_card_details("crippling_crush_red")
    assert name == "Crippling Crush"
    assert meta.get("power") == 11

    # Testando com objeto dict
    name2, meta2, _ = _resolve_card_details({"cardNumber": "snatch_red", "name": "Snatch"})
    assert name2 == "Snatch"
    assert meta2.get("power") == 4


def test_compute_card_impact_scoring():
    # 1. Carta com poder + on-hit (Crippling Crush: 11 power + 4 on-hit = 15)
    _, meta_cc, sem_cc = _resolve_card_details("crippling_crush_red")
    score_cc = compute_card_impact(meta_cc, sem_cc)
    assert score_cc >= 15.0

    # 2. Carta com go-again (Lumina Ascension: 0 power + 3 go-again = 3)
    _, meta_la, sem_la = _resolve_card_details("lumina_ascension_yellow")
    score_la = compute_card_impact(meta_la, sem_la)
    assert score_la >= 3.0

    # 3. Equipamento / Arma (deve retornar -1.0)
    score_equip = compute_card_impact({"slot": "Head", "type": "E"}, {})
    assert score_equip == -1.0


def test_level_1_opponent_graveyard_selection():
    """Identifica cartas de ataque no cemitério do oponente e escolhe a de maior impacto."""
    client = MockClient()
    state = {
        "opponentDiscard": ["sink_below_red", "crippling_crush_red", "wounding_blow_red"],
        "opponentHero": "Bravo",
    }
    chosen = get_learned_card_name_target(client, state)
    assert chosen == "Crippling Crush"


def test_level_1_opponent_pitch_selection():
    """Identifica cartas de ação perigosas no pitch do oponente."""
    client = MockClient()
    state = {
        "opponentPitch": ["lumina_ascension_yellow"],
        "opponentHero": "Dorinthea",
    }
    chosen = get_learned_card_name_target(client, state)
    assert chosen == "Lumina Ascension"


def test_level_1_opponent_banish_and_active_chain():
    """Identifica ameaça ativa na corrente de combate ou zona de banimento."""
    client = MockClient()
    # Ativo na corrente de combate
    state_chain = {
        "activeChainLink": {"cardNumber": "command_and_conquer_red", "totalPower": 6},
        "opponentHero": "Bravo",
    }
    chosen_chain = get_learned_card_name_target(client, state_chain)
    assert chosen_chain == "Command and Conquer"

    # Banimento
    state_banish = {
        "opponentBanish": [{"cardNumber": "snatch_red", "power": 4}],
        "opponentHero": "Katsu",
    }
    chosen_banish = get_learned_card_name_target(client, state_banish)
    assert chosen_banish == "Snatch"


def test_level_1_ignores_equipment():
    """Garante que equipamentos quebrados no cemitério sejam ignorados e não nomeados."""
    client = MockClient()
    state = {
        "opponentDiscard": [{"cardNumber": "ironrot_helm", "slot": "Head", "type": "E"}],
        "opponentHero": "Bravo",
        "opponentClass": "Guardian",
    }
    chosen = get_learned_card_name_target(client, state)
    # Não deve escolher o elmo; avança para o Nível 2 / Nível 3 (Guardian)
    assert chosen != "ironrot_helm"
    assert chosen in ("Crippling Crush", "Pulverize", "Command and Conquer")


def test_level_2_sqlite_history(tmp_path):
    """Consulta o histórico no SQLite quando a partida atual ainda não revelou cartas."""
    mock_db = str(tmp_path / "test_talishar_stats.db")
    conn = sqlite3.connect(mock_db)
    with conn:
        conn.execute('''
            CREATE TABLE opponent_card_history (
                hero TEXT,
                card_name TEXT,
                impact_score REAL,
                count INTEGER,
                last_seen REAL,
                PRIMARY KEY (hero, card_name)
            )
        ''')
        conn.execute(
            "INSERT INTO opponent_card_history VALUES (?, ?, ?, ?, ?)",
            ("CustomHero", "Star Struck", 14.0, 5, 1000.0)
        )
    conn.close()

    client = MockClient()
    state = {
        "opponentHero": "CustomHero",
        "opponentDiscard": [],
        "opponentPitch": [],
        "opponentBanish": [],
    }

    with patch("ai.bot_runtime.card_name_oracle.STATS_DB_PATH", mock_db):
        chosen = get_learned_card_name_target(client, state)
        assert chosen == "Star Struck"


def test_level_3_algorithmic_prediction_by_class(tmp_path):
    """Predição algorítmica pelo pool da classe quando cemitério e histórico estão vazios."""
    mock_empty_db = str(tmp_path / "empty_stats.db")
    client = MockClient()

    with patch("ai.bot_runtime.card_name_oracle.STATS_DB_PATH", mock_empty_db):
        # 1. Classe Guardian -> espera Crippling Crush (impacto 15: 11 atk + 4 on-hit)
        state_guardian = {
            "opponentHero": "Bravo, Showstopper",
            "opponentClass": "Guardian",
            "opponentDiscard": [],
        }
        chosen_guardian = get_learned_card_name_target(client, state_guardian)
        assert chosen_guardian == "Crippling Crush"

        # 2. Classe Ninja -> espera carta da classe Ninja (ex: Mauling Qi)
        state_ninja = {
            "opponentHero": "Katsu",
            "opponentClass": "Ninja",
            "opponentDiscard": [],
        }
        chosen_ninja = get_learned_card_name_target(client, state_ninja)
        assert chosen_ninja in ("Mauling Qi", "Surging Strike", "Rebellious Rush")


def test_fallback_safe_card():
    """Garante fallback seguro ('Sink Below') quando o estado é completamente vazio."""
    client = MockClient()
    chosen = get_learned_card_name_target(client, {})
    assert chosen in ("Sink Below", "Command and Conquer")


def test_choice_handler_input_card_name_integration():
    """Valida a integração completa com choice_handler.py na fase INPUTCARDNAME."""
    client = MockClient(player_id=1)
    state = {
        "opponentDiscard": ["crippling_crush_red"],
        "opponentHero": "Bravo",
    }
    handled = choice_handler.handle_popup_and_choices(
        client=client,
        state=state,
        turn_phase="INPUTCARDNAME",
        popup={},
        prompt_buttons=[],
        unpayable_set=set(),
    )
    assert handled is True
    assert len(client.sent_actions) == 1
    assert client.sent_actions[0]["mode"] == 30
    assert client.sent_actions[0]["input_text"] == "Crippling Crush"
    assert any("Nomeou carta (INPUTCARDNAME) -> 'Crippling Crush'" in log for log in client.logs)
