"""
tests/test_kassai_tactics_and_survival.py
=========================================
Validações de inteligência tática:
1. Sequenciamento de buffs e ataques de arma da Kassai (Warrior).
2. Defesa mandatória de sobrevivência sob dano letal.
3. Repasse de parâmetros de performance MCTS no duelo 1v1.
"""

import pytest
from unittest.mock import MagicMock, patch
from ai.hero_strategies.warrior import WarriorStrategy, KassaiStrategy
from ai.hero_strategies.base import TurnPlan
from ai.policy.engine import PolicyEngine
from ai.policy.defense_pruner import select_defense_blocks
import frontend_manager


def test_kassai_buff_resource_sequencing():
    """Valida que Kassai penaliza buffs de arma quando faltam recursos para atacar com a arma."""
    strat = KassaiStrategy("kassai_cintari_sellsword")
    plan = TurnPlan(plan_type="WARRIOR_REPRISE_STRIKE")
    card_info = {"cost": 2, "pitch": 1}

    # Cenário A: Sem recursos suficientes (apenas 1 carta red na mão, 0 floating pitch)
    state_poor = {
        "playerHand": [{"cardNumber": "spoils_of_war", "cost": 2, "pitch": 1}],
        "playerPitchCount": 0,
        "playerEquipment": [{"cardNumber": "cintari_saber", "slot": "weapon", "action": 1}],
    }
    score_poor = strat.modify_attack_candidate_score("spoils_of_war", card_info, plan, 20.0, state_poor)
    # Deve ser severamente penalizado por falta de pitch para a arma (-35)
    assert score_poor < 0.0

    # Cenário B: Recursos fartos (1 carta azul na mão para dar pitch de 3 recursos)
    state_rich = {
        "playerHand": [
            {"cardNumber": "spoils_of_war", "cost": 2, "pitch": 1},
            {"cardNumber": "blue_pitch", "pitch": 3},
        ],
        "playerPitchCount": 0,
        "playerEquipment": [{"cardNumber": "cintari_saber", "slot": "weapon", "action": 1}],
    }
    score_rich = strat.modify_attack_candidate_score("spoils_of_war", card_info, plan, 20.0, state_rich)
    assert score_rich >= 40.0


def test_kassai_weapon_swing_boosted_after_buff():
    """Valida que o ataque com arma recebe bônus massivo (+30) quando há buff de arma ativo no estado."""
    strat = KassaiStrategy("kassai_cintari_sellsword")

    # Sem buff
    state_no_buff = {"playerEquipment": [{"cardNumber": "cintari_saber", "slot": "weapon"}]}
    score_base = strat.evaluate_weapon_attack("cintari_saber", 1, 3, True, state=state_no_buff)

    # Com buff ativo na pilha/estado (ex: spoils_of_war recente no descarte)
    state_with_buff = {
        "playerEquipment": [{"cardNumber": "cintari_saber", "slot": "weapon"}],
        "playerDiscard": [{"cardNumber": "spoils_of_war"}],
    }
    score_buffed = strat.evaluate_weapon_attack("cintari_saber", 1, 3, True, state=state_with_buff)

    assert score_buffed >= score_base + 30.0


def test_fatal_damage_never_returns_empty_blocks():
    """Valida que dano letal iminente força o bot a bloquear com as cartas da mão em vez de abortar."""
    pe = PolicyEngine(hero_name="kassai_cintari_sellsword", num_mcts_sims=0)

    # Estado de dano letal: Vida = 3, Ataque recebido = 5
    state_fatal = {
        "playerHealth": 3,
        "opponentHealth": 20,
        "playerHand": [
            {"cardNumber": "ironsong_response", "block": 3, "pitch": 1, "action": 27},
            {"cardNumber": "strike_card", "block": 2, "pitch": 2, "action": 27},
        ],
        "activeChainLink": {
            "cardNumber": "snatch",
            "totalPower": 5,
            "text": "If this hits, draw a card.",
        },
        "combatChainPower": 5,
        "playerEquipment": [],
    }

    blocks = select_defense_blocks(pe, state_fatal)
    # O bot NUNCA pode retornar lista vazia e aceitar a morte de mão cheia!
    assert len(blocks) > 0
    total_blocked = sum(
        int(c.get("block", 0))
        for idx, cid, name, mode in blocks
        for c in state_fatal["playerHand"]
        if str(c.get("cardNumber", "")).lower() == name.lower()
    )
    assert total_blocked >= 3


def test_warrior_block_card_does_not_penalize_reactions_on_fatal():
    """Valida que reações de ataque bloqueiam normalmente sem penalidade sob risco letal."""
    strat = WarriorStrategy("dorinthea")
    # Em vida saudável, ironsong tem penalidade de -15 para guardar na mão
    score_healthy = strat.evaluate_block_card("ironsong_response", 3, 1, 0, False, my_hp=20, is_fatal=False)
    assert score_healthy < 0

    # Sob dano letal, ironsong não recebe penalidade e bloqueia com prioridade
    score_fatal = strat.evaluate_block_card("ironsong_response", 3, 1, 0, False, my_hp=2, is_fatal=True)
    assert score_fatal > 0
    assert score_fatal == 6.0


def test_create_human_vs_bot_match_parameters():
    """Valida que create_human_vs_bot_match repassa os argumentos CLI de MCTS e concorrência para o bot."""
    with patch("frontend_manager.is_backend_running", return_value=True), \
         patch("frontend_manager.is_frontend_running", return_value=True), \
         patch("frontend_manager.requests.post") as mock_post, \
         patch("frontend_manager.subprocess.Popen") as mock_popen:

        mock_post.return_value.status_code = 200
        mock_post.return_value.json.return_value = {
            "gameName": "TestRoom123",
            "authKey": "key_abc",
        }
        mock_popen.return_value.pid = 9999

        res = frontend_manager.create_human_vs_bot_match(
            player_deck_slug="kassai",
            bot_deck_slug="mario",
            format_code="cc",
            mcts_sims=0,
            ismcts_concurrency="threads",
            device="cpu",
            torch_threads=2,
        )

        assert res["success"] is True
        assert res["game_name"] == "TestRoom123"

        # Verifica se o comando passado ao subprocess.Popen inclui as flags
        args, kwargs = mock_popen.call_args
        cmd_list = args[0]
        assert "--mcts-sims" in cmd_list
        idx_sims = cmd_list.index("--mcts-sims")
        assert cmd_list[idx_sims + 1] == "0"

        assert "--ismcts-concurrency" in cmd_list
        idx_conc = cmd_list.index("--ismcts-concurrency")
        assert cmd_list[idx_conc + 1] == "threads"

        assert "--device" in cmd_list
        idx_dev = cmd_list.index("--device")
        assert cmd_list[idx_dev + 1] == "cpu"
