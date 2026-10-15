"""
tests/test_sim2real_corrections.py
==================================
Validação estrita de resolução de anomalias Sim2Real:
1. Poda preventiva de Flick Knives a montante (CR 245 & REMOVEINDICESIFACTIVECHAINLINK).
2. Seleção segura em popups CHOOSEMULTIZONE/MAYCHOOSEMULTIZONE (rejeição de overlay=1 e Pass se tudo quebrado).
3. Resolução condicional de Go-Again no GameSimulator (AP 0 vs AP 1 com elos dracônicos).
4. Suporte a Mode 5 (Arsenal) e temporização de HP na Phase B no Shadow Mode.
"""

from unittest.mock import MagicMock
import pytest

from ai.bot_runtime.choice_handler import (
    score_choice_candidate,
    rank_choice_candidates,
    handle_popup_and_choices,
)
from ai.bot_runtime.phase_decider import handle_reaction_phase
from ai.game_simulator import GameSimulator
import ai.shadow_mode as shadow_mode


# ─── 1. Poda Preventiva de Flick Knives a Montante ───────────────────────────

def test_flick_knives_pruned_when_sole_dagger_is_attacking_on_chain():
    """Valida que Flick Knives NÃO é ativado se a única adaga estiver atacando na cadeia ativa (CR 245)."""
    client = MagicMock()
    client.player_id = 1
    client.last_attempted_play = None
    client.reaction_attempts = {}
    client.log = MagicMock()
    client.send_chat_log = MagicMock()
    client.get_combat_chain_desc = MagicMock(return_value="Claw of Vynserakai Attack")
    client.blocks_declared_count = 0
    client.policy_engine = MagicMock()
    client.policy_engine.calculate_available_resources.return_value = (2, 2)
    client.policy_engine.get_weapon_cost.return_value = 0
    client.policy_engine.strategy.evaluate_equipment_ability.return_value = 18.0

    # Estado onde o bot está atacando com Claw of Vynserakai (ela está na cadeia ativa)
    state = {
        "turnPhase": "A",
        "turnPlayer": 1,
        "amIActivePlayer": True,
        "activeChainLink": {
            "attackingPlayer": 1,
            "isDefending": False,
            "attackingCard": {"cardNumber": "claw_of_vynserakai"},
            "cardNumber": "claw_of_vynserakai",
        },
        "playerEquipment": [
            {"cardNumber": "flick_knives", "action": 1, "actionDataOverride": "EQ-0", "status": 1},
            {"cardNumber": "claw_of_vynserakai", "subtype": "Dagger", "isBroken": False, "overlay": 0, "onChain": True},
        ],
    }

    handle_reaction_phase(client, state, 1, "A", [], unpayable_set=set())
    # O bot NÃO deve acionar Flick Knives (mode 1 / EQ-0), mas sim passar a reação (mode 99)
    client.send_action.assert_called_once()
    assert client.send_action.call_args[1].get("mode") == 99


def test_flick_knives_pruned_when_all_daggers_broken_or_no_dagger():
    """Valida que Flick Knives passa (mode 99) se todas as adagas estiverem quebradas ou se não houver adagas."""
    client = MagicMock()
    client.player_id = 1
    client.last_attempted_play = None
    client.reaction_attempts = {}
    client.blocks_declared_count = 0
    client.policy_engine = MagicMock()
    client.policy_engine.calculate_available_resources.return_value = (2, 2)
    client.policy_engine.get_weapon_cost.return_value = 0
    client.policy_engine.strategy.evaluate_equipment_ability.return_value = 18.0

    # Caso 1: Todas as adagas quebradas/arremessadas
    state_broken = {
        "turnPhase": "A",
        "turnPlayer": 1,
        "amIActivePlayer": True,
        "activeChainLink": {"attackingPlayer": 1, "isDefending": False, "cardNumber": "snatch_red"},
        "playerEquipment": [
            {"cardNumber": "flick_knives", "action": 1, "actionDataOverride": "EQ-0", "status": 1},
            {"cardNumber": "claw_of_vynserakai", "subtype": "Dagger", "isBroken": True, "overlay": 1},
        ],
    }
    handle_reaction_phase(client, state_broken, 1, "A", [], unpayable_set=set())
    assert client.send_action.call_args[1].get("mode") == 99

    client.send_action.reset_mock()

    # Caso 2: Sem nenhuma adaga
    state_no_daggers = {
        "turnPhase": "A",
        "turnPlayer": 1,
        "amIActivePlayer": True,
        "activeChainLink": {"attackingPlayer": 1, "isDefending": False, "cardNumber": "snatch_red"},
        "playerEquipment": [
            {"cardNumber": "flick_knives", "action": 1, "actionDataOverride": "EQ-0", "status": 1},
            {"cardNumber": "cintari_saber", "subtype": "Sword", "isBroken": False, "overlay": 0},
        ],
    }
    handle_reaction_phase(client, state_no_daggers, 1, "A", [], unpayable_set=set())
    assert client.send_action.call_args[1].get("mode") == 99


def test_flick_knives_activated_when_eligible_second_dagger_exists():
    """Valida que Flick Knives ativa com sucesso quando há adaga sobressalente pronta fora da cadeia."""
    client = MagicMock()
    client.player_id = 1
    client.last_attempted_play = None
    client.reaction_attempts = {}
    client.blocks_declared_count = 0
    client.policy_engine = MagicMock()
    client.policy_engine.calculate_available_resources.return_value = (2, 2)
    client.policy_engine.get_weapon_cost.return_value = 0
    client.policy_engine.strategy.evaluate_equipment_ability.return_value = 18.0

    state_valid = {
        "turnPhase": "A",
        "turnPlayer": 1,
        "amIActivePlayer": True,
        "activeChainLink": {
            "attackingPlayer": 1,
            "isDefending": False,
            "attackingCard": {"cardNumber": "claw_of_vynserakai"},
            "cardNumber": "claw_of_vynserakai",
        },
        "playerEquipment": [
            {"cardNumber": "flick_knives", "action": 1, "actionDataOverride": "EQ-0", "status": 1},
            {"cardNumber": "claw_of_vynserakai", "subtype": "Dagger", "isBroken": False, "overlay": 0, "onChain": True},
            {"cardNumber": "kunai_of_retribution", "subtype": "Dagger", "isBroken": False, "overlay": 0, "onChain": False},
        ],
    }

    handle_reaction_phase(client, state_valid, 1, "A", [], unpayable_set=set())
    assert client.send_action.call_args[1].get("mode") == 1
    assert client.send_action.call_args[1].get("card_id") == "EQ-0"


# ─── 2. Blindagem de Popups de Adagas (CHOOSEMULTIZONE / MAYCHOOSEMULTIZONE) ───

def test_dagger_popup_selection_with_mixed_overlay():
    """Valida que no popup de adagas mistas o bot rejeita adaga arremessada (overlay=1) e escolhe a adaga ativa (overlay=0)."""
    client = MagicMock()
    client.player_id = 1

    popup = {
        "title": "Choose a dagger to poke with",
        "cardsMultiZone": [
            {
                "cardNumber": "claw_of_vynserakai",
                "action": 16,
                "actionDataOverride": "MYCHAR-1",
                "overlay": 1,
                "status": 0,
            },
            {
                "cardNumber": "kunai_of_retribution",
                "action": 16,
                "actionDataOverride": "MYCHAR-2",
                "overlay": 0,
                "status": 2,
            },
        ],
    }
    state = {"turnPhase": "CHOOSEMULTIZONE", "popup": popup}

    # Pontuação deve penalizar severamente a arremessada
    score_thrown = score_choice_candidate(client, popup["cardsMultiZone"][0], turn_phase="CHOOSEMULTIZONE", state=state)
    score_ready = score_choice_candidate(client, popup["cardsMultiZone"][1], turn_phase="CHOOSEMULTIZONE", state=state)
    assert score_thrown <= -500.0
    assert score_ready > 0.0

    # Ordenação deve priorizar a pronta
    ranked = rank_choice_candidates(client, popup["cardsMultiZone"], turn_phase="CHOOSEMULTIZONE", state=state)
    assert ranked[0]["actionDataOverride"] == "MYCHAR-2"

    # Execução do manipulador de escolha
    res = handle_popup_and_choices(client, state, "CHOOSEMULTIZONE", popup, [], set())
    assert res is True
    client.send_action.assert_called_once_with(mode=16, card_id="MYCHAR-2", button_input="MYCHAR-2")


def test_dagger_popup_all_broken_sends_pass_on_maychoosemultizone():
    """Valida que em MAYCHOOSEMULTIZONE, se todas as opções estiverem indisponíveis/arremessadas, o bot emite Pass (Mode 99)."""
    client = MagicMock()
    client.player_id = 1

    popup = {
        "title": "Choose a dagger to flick",
        "cardsMultiZone": [
            {
                "cardNumber": "claw_of_vynserakai",
                "action": 16,
                "actionDataOverride": "MYCHAR-1",
                "overlay": 1,
                "isBroken": True,
            },
            {
                "cardNumber": "kunai_of_retribution",
                "action": 16,
                "actionDataOverride": "MYCHAR-2",
                "overlay": 1,
                "status": "destroyed",
            },
        ],
    }
    state = {"turnPhase": "MAYCHOOSEMULTIZONE", "popup": popup}

    res = handle_popup_and_choices(client, state, "MAYCHOOSEMULTIZONE", popup, [], set())
    assert res is True
    client.send_action.assert_called_once_with(mode=99, button_input="PASS")


# ─── 3. Resolução Condicional de Go-Again no GameSimulator ──────────────────

def test_conditional_draconic_go_again_simulator():
    """Valida que Burning Blade Dance sem 2 links dracônicos anteriores reduz AP para 0, e com 2 links preserva AP 1."""
    # Cenário A: Sem links dracônicos anteriores
    state_no_links = {
        "playerAP": 1,
        "actionPoints": 1,
        "playerHand": [{"cardNumber": "burning_blade_dance_red", "cost": 0, "power": 3}],
        "combatChain": [],
        "combatChainLinks": [],
        "draconicLinksCount": 0,
    }
    next_state_no_links, _ = GameSimulator.simulate_step(
        state_no_links,
        {"type": "hand", "cardNumber": "burning_blade_dance_red", "name": "burning_blade_dance_red", "cost": 0}
    )
    assert next_state_no_links.get("playerAP") == 0

    # Cenário B: Com 2 links dracônicos anteriores
    state_with_links = {
        "playerAP": 1,
        "actionPoints": 1,
        "playerHand": [{"cardNumber": "burning_blade_dance_red", "cost": 0, "power": 3}],
        "draconicLinksCount": 2,
    }
    next_state_with_links, _ = GameSimulator.simulate_step(
        state_with_links,
        {"type": "hand", "cardNumber": "burning_blade_dance_red", "name": "burning_blade_dance_red", "cost": 0}
    )
    assert next_state_with_links.get("playerAP") == 1


# ─── 4. Modo 5 (Arsenal) e Temporização de HP em Phase B no Shadow Mode ──────

def test_shadow_mode_handles_mode_5_arsenal():
    """Valida que jogada via Mode 5 reduz playerArsenal em vez de playerHand e não acusa card_unconsumed."""
    pre_state = {
        "turnNo": 2,
        "turnPlayer": 1,
        "turnPhase": "M",
        "playerAP": 1,
        "playerHand": [{"cardNumber": "snatch_red", "cost": 0}],
        "playerArsenal": [{"cardNumber": "command_and_conquer", "cost": 2}],
        "playerResources": [2, 0],
        "playerHealth": 40,
        "opponentHealth": 40,
    }

    pred = shadow_mode.predict(pre_state, card_id="0", mode=5)
    assert pred is not None
    assert pred["zone"] == "arsenal"
    assert pred["arsenal_count"] == 0
    assert pred["hand_count"] == 1

    post_state = {
        "turnNo": 2,
        "turnPlayer": 1,
        "playerAP": 0,
        "playerHand": [{"cardNumber": "snatch_red", "cost": 0}],
        "playerArsenal": [],
        "playerResources": [0, 0],
        "playerHealth": 40,
        "opponentHealth": 40,
    }

    diffs, confounded = shadow_mode.compare(pred, pre_state, post_state)
    assert not confounded
    assert "card_unconsumed" not in diffs
    assert "hand_count" not in diffs


def test_shadow_mode_phase_b_health_timing():
    """Valida que declaração de bloco em Phase B não prediz perda antecipada de HP antes do damage step."""
    pre_state = {
        "turnNo": 1,
        "turnPlayer": 2,
        "turnPhase": "B",
        "playerHealth": 35,
        "opponentHealth": 40,
        "activeChainLink": {"totalPower": 4, "totalDefense": 0},
        "playerHand": [{"cardNumber": "sink_below_red", "defense": 4}],
    }

    pred = shadow_mode.predict(pre_state, card_id="0", mode=0)
    assert pred is not None
    # No tick intermediário após o bloco, HP esperado é o HP atual (35), pois dano só resolve após reações
    assert pred["player_health"] == 35


def test_dr_cards_excluded_from_declare_block():
    """Valida que Defense Reactions (Sink Below, Rootbound Carapace) são excluídas da declaração de bloco na Phase B (CR 7.3.2)."""
    from ai.policy.defense_pruner import select_defense_blocks

    engine = MagicMock()
    engine.hero_class = "GUARDIAN"
    engine.calculate_available_resources.return_value = (0, 0)
    engine.extract_card_info.side_effect = lambda c: {
        "name": c.get("name", c.get("cardNumber", "")),
        "block": c.get("defense", c.get("block", 0)),
        "pitch": c.get("pitch", 1),
        "power": c.get("power", 0),
        "cost": c.get("cost", 0),
        "has_go_again": False,
        "action": 27,
        "actionDataOverride": None,
    }
    engine.strategy.analyze_turn_plan.return_value = MagicMock(
        reserved_card_names=set(),
        can_absorb_damage=False,
        plan_type="FULL_DEFENSE",
    )
    engine.strategy.calculate_card_opportunity_cost.return_value = 0.0
    engine.strategy.evaluate_block_card.return_value = 10.0

    state = {
        "turnNo": 2,
        "turnPhase": "B",
        "activeChainLink": {"power": 4, "totalPower": 4},
        "playerHealth": 5,
        "playerEquipment": [],
        "playerHand": [
            {"cardNumber": "sink_below_red", "name": "Sink Below", "defense": 4, "type": "DR"},
            {"cardNumber": "rootbound_carapace_red", "name": "Rootbound Carapace", "defense": 4, "type": "DR"},
            {"cardNumber": "staunch_defense_red", "name": "Staunch Defense", "defense": 3, "type": "A"},
        ],
    }

    blocks = select_defense_blocks(engine, state)
    # Apenas a carta do tipo Action (Staunch Defense) pode ser candidata a bloco na Phase B;
    # As DRs (Sink Below e Rootbound Carapace) DEVEM ser excluídas da fase B
    blocked_names = [b[2] for b in blocks]
    assert "Sink Below" not in blocked_names
    assert "Rootbound Carapace" not in blocked_names
    assert "Staunch Defense" in blocked_names


def test_shadow_mode_player_arse_key_and_opponent_health():
    """Valida que playerArse não acusa falso positivo de arsenal e que ataque não assume dano prematuro."""
    pre_state = {
        "turnNo": 1,
        "turnPlayer": 1,
        "turnPhase": "M",
        "playerAP": 1,
        "playerHand": [{"cardNumber": "snatch_red", "cost": 0, "power": 4}],
        "playerArse": [{"cardNumber": "sink_below_red", "cost": 0}],
        "playerResources": [0, 0],
        "playerHealth": 40,
        "opponentHealth": 40,
    }

    pred = shadow_mode.predict(pre_state, card_id="0", mode=27)
    assert pred is not None
    # playerArse deve refletir arsenal_count = 1
    assert pred["arsenal_count"] == 1
    # Ao declarar ataque no tick intermediário, dano ainda não resolveu, opp HP é 40
    assert pred["opponent_health"] == 40

    post_state = {
        "turnNo": 1,
        "turnPlayer": 1,
        "playerAP": 0,
        "playerHand": [],
        "playerArse": [{"cardNumber": "sink_below_red", "cost": 0}],
        "playerResources": [0, 0],
        "playerHealth": 40,
        "opponentHealth": 40,
    }

    diffs, confounded = shadow_mode.compare(pred, pre_state, post_state)
    assert not confounded
    assert "arsenal_count" not in diffs
    assert "opponent_health" not in diffs


def test_simulate_pitch_pending_costs_and_ap_consumption():
    """Valida que simulate_pitch consome custos pendentes [0, cost] e consome AP ao quitar o custo da ação."""
    # Estado com custo pendente de 3 recursos exigido por uma ação declarada
    state = {
        "playerAP": 1,
        "playerResources": [0, 3],
        "playerHand": [
            {"cardNumber": "blue_pitch_card", "name": "Blue Pitch Card", "pitch": 3},
            {"cardNumber": "other_card", "name": "Other Card", "pitch": 1},
        ],
        "playerPitch": [],
    }

    next_state = GameSimulator.simulate_pitch(state, {"cardNumber": "blue_pitch_card", "pitch": 3, "card_idx": 0})
    # O pitch de 3 quitou o custo exigido de 3: sobra de floating = 0, custo pendente remanescente = 0
    assert next_state.get("playerResources") == (0, 0)
    # Ação processada consumiu 1 AP
    assert next_state.get("playerAP") == 0
    assert len(next_state.get("playerHand")) == 1


def test_simulate_attack_equipment_ability_does_not_spend_ap():
    """Valida que ativar habilidade de equipamento (Instant) não gasta Action Point."""
    state = {
        "playerAP": 1,
        "currentAttackBuff": 0,
    }

    action = {
        "type": "equipment_ability",
        "cardNumber": "crown_of_providence",
        "name": "crown_of_providence",
    }
    next_state = GameSimulator.simulate_attack(state, action)
    assert next_state.get("playerAP") == 1


def test_shadow_mode_phase_m_to_p_multi_tick_transition_confounded():
    """Valida que transição multi-tick M -> P (esperando pitch) é marcada como transicional (confounded)."""
    pre_state = {
        "turnNo": 1,
        "turnPlayer": 1,
        "turnPhase": "M",
        "playerAP": 1,
        "playerHand": [{"cardNumber": "attack_cost_3", "cost": 3}],
        "playerResources": [0, 0],
    }
    pred = {"hand_count": 0, "resources": 0, "action_points": 0, "card_consumed": "attack_cost_3", "zone": "hand"}
    post_state = {
        "turnNo": 1,
        "turnPlayer": 1,
        "turnPhase": "P",
        "playerAP": 1,
        "playerHand": [{"cardNumber": "attack_cost_3", "cost": 3}],
        "playerResources": [0, 0],
    }
    diffs, confounded = shadow_mode.compare(pred, pre_state, post_state)
    assert confounded is True


def test_shadow_mode_phase_p_pending_cost_settlement_no_divergence():
    """Valida que liquidação de pitch na Phase P não acusa divergência de resources/AP consumidos pela ação."""
    pre_state = {
        "turnNo": 1,
        "turnPlayer": 1,
        "turnPhase": "P",
        "playerAP": 1,
        "playerHand": [{"cardNumber": "blue_pitch", "pitch": 3}],
        "playerResources": [0, 0],
    }
    pred = {"hand_count": 0, "resources": 3, "action_points": 1, "card_consumed": "blue_pitch", "zone": "hand"}
    # Talishar quitou a ação com os 3 recursos e consumiu o AP
    post_state = {
        "turnNo": 1,
        "turnPlayer": 1,
        "turnPhase": "M",
        "playerAP": 0,
        "playerHand": [],
        "playerResources": [0, 0],
    }
    diffs, confounded = shadow_mode.compare(pred, pre_state, post_state)
    assert not diffs
    assert "resources" not in diffs
    assert "action_points" not in diffs


def test_game_simulator_simulate_attack_player_arse_support():
    """Valida que simulate_attack consome corretamente cartas sob a chave playerArse."""
    state = {
        "turnPhase": "M",
        "playerAP": 1,
        "playerHand": [],
        "playerArse": [{"cardNumber": "enlightened_strike_red", "name": "enlightened_strike_red", "cost": 0}],
        "playerResources": [0, 0],
    }
    action = {"type": "arsenal", "cardNumber": "enlightened_strike_red", "name": "enlightened_strike_red"}
    next_state = GameSimulator.simulate_attack(state, action)
    assert len(next_state.get("playerArsenal", [])) == 0
    assert len(next_state.get("playerArse", [])) == 0

