"""
tests/test_match_13229_corrections.py
=====================================
Testes unitários dedicados a validar as correções táticas derivadas da partida #13229:
1. Poda de abertura de Arsenal sem Go-Again quando AP <= 1 e a mão tem ataques/iniciadores.
2. Checagem e penalização de condicionais prematuros:
   - Hunt the Hunter (exige carta vermelha prévia para Mark).
   - Rupture / Lava Burst (exige elo de cadeia >= 4).
   - Mark with Magma (exige links dracônicos >= 2).
3. Defesa de sobrevivência em HP crítico (<= 10) contra ataques com Go-Again e oponente com mão ativa.
"""

import pytest
from unittest.mock import MagicMock

from ai.policy.attack_pruner import (
    select_best_attack,
    evaluate_conditional_attack_penalty,
)
from ai.policy.defense_pruner import select_defense_blocks
from ai.policy.go_again_resolver import (
    has_prior_red_card_played,
    resolve_attack_go_again,
)
from ai.hero_strategies.turn_planner import should_trigger_survival_block, TurnPlan
from ai.hero_strategies.ninja import NinjaStrategy


class MockEngine:
    def __init__(self, hero_name="cindra"):
        self.strategy = NinjaStrategy(hero_name)
        self.num_mcts_sims = 0
        self.model = None

    def calculate_available_resources(self, state):
        res = 0
        for c in state.get("playerHand", []):
            res += int(c.get("pitch", 1))
        return 0, res

    def extract_card_info(self, card):
        if not isinstance(card, dict):
            return {"name": str(card), "cost": 0, "power": 3, "block": 3, "pitch": 1, "has_go_again": False}
        return {
            "name": str(card.get("cardNumber") or card.get("name", "attack")).lower(),
            "cost": int(card.get("cost", 0)),
            "power": int(card.get("power", 3)),
            "block": int(card.get("block", 3)),
            "pitch": int(card.get("pitch", 1)),
            "has_go_again": bool(card.get("has_go_again", False)),
            "action": int(card.get("action", 27)),
            "actionDataOverride": card.get("actionDataOverride"),
        }


# ── 1. Testes de Condicionais de Ataque (Hunt the Hunter, Rupture, Draconic) ──

def test_has_prior_red_card_played_detection():
    """Valida detecção de cartas vermelhas jogadas através de múltiplos campos de telemetria."""
    assert not has_prior_red_card_played({})
    assert has_prior_red_card_played({"redCardsPlayed": 1})
    assert has_prior_red_card_played({"numRedPlayed": 2})
    assert has_prior_red_card_played({"currentTurnActions": [{"cardNumber": "snatch_red", "pitch": 1}]})
    assert has_prior_red_card_played({"combatChainLinks": [{"cardNumber": "blaze_headlong_red", "pitch": 1}]})


def test_hunt_the_hunter_penalized_without_prior_red():
    """Hunt the Hunter deve sofrer penalidade de -25.0 se nenhuma carta vermelha foi jogada e há outras opções."""
    candidate_attacks = [
        {"name": "hunt_the_hunter_red", "pitch": 1},
        {"name": "blaze_headlong_red", "pitch": 1},
    ]
    state_no_red = {"redCardsPlayed": 0}
    penalty = evaluate_conditional_attack_penalty("hunt_the_hunter_red", state_no_red, candidate_attacks)
    assert penalty == -25.0

    state_with_red = {"redCardsPlayed": 1}
    penalty_met = evaluate_conditional_attack_penalty("hunt_the_hunter_red", state_with_red, candidate_attacks)
    assert penalty_met == 0.0


def test_rupture_lava_burst_penalized_before_link_4():
    """Lava Burst / Rupture deve sofrer penalidade de -30.0 nos elos 1, 2 e 3 quando há outros ataques."""
    candidate_attacks = [
        {"name": "lava_burst_red", "pitch": 1},
        {"name": "ronin_renegade_red", "pitch": 1},
    ]
    state_link_1 = {"currentChainLink": 1}
    assert evaluate_conditional_attack_penalty("lava_burst_red", state_link_1, candidate_attacks) == -30.0

    state_link_3 = {"currentChainLink": 3}
    assert evaluate_conditional_attack_penalty("lava_burst_red", state_link_3, candidate_attacks) == -30.0

    state_link_4 = {"currentChainLink": 4}
    assert evaluate_conditional_attack_penalty("lava_burst_red", state_link_4, candidate_attacks) == 0.0


# ── 2. Testes de Universalização da Poda de Go-Again para o Arsenal ──────────

def test_arsenal_non_go_again_penalized_as_opener():
    """
    Ataque no Arsenal sem Go-Again (ex: art_of_the_dragon_fire_red) com AP <= 1
    NÃO deve abrir o turno se a mão possui ataques jogáveis e a cadeia está vazia.
    """
    engine = MockEngine("cindra")
    state = {
        "playerAP": 1,
        "playerHand": [
            {"cardNumber": "ronin_renegade_red", "name": "ronin_renegade_red", "cost": 0, "power": 3, "has_go_again": True, "pitch": 1, "action": 27},
            {"cardNumber": "sink_below_red", "name": "sink_below_red", "cost": 0, "power": 0, "block": 4, "pitch": 1, "action": 0},
            {"cardNumber": "blue_pitch_card", "name": "blue_pitch_card", "cost": 0, "power": 1, "pitch": 3, "action": 27},
        ],
        "playerArsenal": [
            {"cardNumber": "art_of_the_dragon_fire_red", "name": "art_of_the_dragon_fire_red", "cost": 0, "power": 4, "has_go_again": False, "pitch": 1, "action": 27}
        ],
        "combatChain": [],
        "combatChainLinks": [],
    }

    best = select_best_attack(engine, state)
    assert best is not None
    # Deve selecionar o starter com Go-Again da mão (ronin_renegade_red) em vez da carta sem Go-Again do Arsenal
    assert best["name"] == "ronin_renegade_red"
    assert best["type"] == "hand"


def test_arsenal_non_go_again_allowed_as_chain_finisher():
    """
    Se a cadeia de combate já está ativa (ex: link 2), a carta sem Go-Again do Arsenal
    pode ser jogada como finisher legítimo sem sofrer a penalidade de abertura.
    """
    engine = MockEngine("cindra")
    state = {
        "playerAP": 1,
        "playerHand": [
            {"cardNumber": "blue_pitch_card", "name": "blue_pitch_card", "cost": 0, "power": 0, "pitch": 3, "action": 0},
        ],
        "playerArsenal": [
            {"cardNumber": "art_of_the_dragon_fire_red", "name": "art_of_the_dragon_fire_red", "cost": 0, "power": 4, "has_go_again": False, "pitch": 1, "action": 27}
        ],
        "combatChain": [{"cardNumber": "ronin_renegade_red"}],
        "combatChainLinks": [{"cardNumber": "ronin_renegade_red"}],
        "activeChainLink": {"cardNumber": "ronin_renegade_red"},
    }

    best = select_best_attack(engine, state)
    assert best is not None
    assert best["name"] == "art_of_the_dragon_fire_red"
    assert best["type"] == "arsenal"


# ── 3. Testes de Defesa de Sobrevivência contra Cadeias Oponentes ─────────────

def test_survival_block_triggered_at_low_hp_against_chain():
    """Em HP <= 10, ataque oponente com Go-Again e cartas na mão deve ativar SURVIVAL_BLOCK."""
    state = {
        "playerHealth": 8,
        "activeChainLink": {
            "cardNumber": "hot_on_their_heels_red",
            "totalPower": 3,
            "goAgain": True,
        },
        "opponentHandCount": 2,
    }
    assert should_trigger_survival_block(state) is True


def test_defense_pruner_blocks_go_again_attack_at_8_hp():
    """
    Cenário real do Turno 6 da partida #13229:
    Bot com 8 HP enfrentando hot_on_their_heels_red (3 de dano com Go-Again)
    com o oponente tendo 2 cartas na mão. O bot NÃO pode desistir do bloqueio (retornar [])
    para 'preservar mão', devendo bloquear com as cartas da mão.
    """
    engine = MockEngine("cindra")
    state = {
        "playerHealth": 8,
        "playerID": 2,
        "turnPlayer": 1,
        "activeChainLink": {
            "cardNumber": "hot_on_their_heels_red",
            "totalPower": 3,
            "goAgain": True,
            "keywords": ["go_again"],
        },
        "combatChainPower": 3,
        "opponentHandCount": 2,
        "playerHand": [
            {"cardNumber": "blaze_headlong_red", "name": "blaze_headlong_red", "block": 3, "power": 4, "pitch": 1, "cost": 0, "action": 27},
            {"cardNumber": "ignite_red", "name": "ignite_red", "block": 3, "power": 3, "pitch": 1, "cost": 0, "action": 27},
            {"cardNumber": "rising_resentment_red", "name": "rising_resentment_red", "block": 2, "power": 3, "pitch": 1, "cost": 0, "action": 27},
        ],
    }

    blocks = select_defense_blocks(engine, state)
    assert len(blocks) > 0, "O bot não deve retornar bloqueio vazio em HP 8 contra ataque com Go-Again!"
    # Bloqueou com sucesso cobrindo os 3 de dano
    blocked_cards = [b[2] for b in blocks]
    assert any("blaze_headlong_red" in c or "ignite_red" in c for c in blocked_cards)
