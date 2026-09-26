import pytest
from unittest.mock import MagicMock, patch
import time

from ai.bot_runtime import choice_handler, phase_decider


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch):
    """Elimina esperas por sleep durante os testes para execução instantânea."""
    monkeypatch.setattr(time, "sleep", lambda x: None)


class MockClient:
    """Mock leve de FabBotClient para isolamento e testes unitários rápidos."""

    def __init__(self, player_id=1, hero_name="teklovossen"):
        self.player_id = player_id
        self.hero_name = hero_name
        self.last_attempted_play = None
        self.recent_phases = []
        self.consecutive_same_state = 0
        self.last_state_sig = None
        self._anti_loop_streak = 0
        self.attacks_made = 0
        self.opp_attacks_count = 0
        self.blocks_declared_count = 0
        self.declared_blocks_link = set()
        self.reaction_attempts = {}
        self.trajectory = []
        self.last_logged_combat_attack = None
        self.last_logged_def_plan = None
        self.last_logged_atk_plan = None
        self.teklo_ability_active_turn = -1

        self.sent_actions = []
        self.chat_logs = []
        self.logs = []

        # Policy Engine Mock
        self.policy_engine = MagicMock()
        self.policy_engine.num_mcts_sims = 32
        self.policy_engine.extract_card_info = MagicMock(return_value={
            "cardNumber": "",
            "power": 0,
            "cost": 1,
            "pitch": 3,
            "has_go_again": False,
        })
        self.policy_engine.calculate_available_resources.return_value = (1, 3)

        # Strategy Mock
        self.strategy = MagicMock()
        mock_plan = MagicMock()
        mock_plan.plan_type = "TEMPO_ATTACK"
        mock_plan.reason = "Maximizar Pressão"
        self.strategy.analyze_turn_plan.return_value = mock_plan
        self.strategy.evaluate_equipment_ability.return_value = 10.0
        self.policy_engine.strategy = self.strategy
        self.policy_engine.get_weapon_cost.return_value = 1

        # Equipment Tracker Mock
        self.equipment_tracker = MagicMock()

    def log(self, msg):
        self.logs.append(msg)

    def send_action(self, **kwargs):
        self.sent_actions.append(kwargs)
        return True

    def send_chat_log(self, text, **kwargs):
        self.chat_logs.append((text, kwargs))

    def evaluate_board_state(self, state):
        return 2.5

    def get_combat_chain_desc(self, state):
        return state.get("mock_chain_desc", "Command and Conquer (Power: 6)")


# ==============================================================================
# TESTES DE CHOICE_HANDLER
# ==============================================================================

class TestScoreChoiceCandidate:
    """Testes para score_choice_candidate em diferentes cenários e modais."""

    @pytest.fixture
    def client(self):
        return MockClient()

    @pytest.mark.parametrize("candidate", [
        {"buttonInput": "pass"},
        {"caption": "Pass Priority"},
        {"name": "cancel"},
        {"mode": 10000},
        "pass",
        "cancel",
    ])
    def test_pass_and_cancel_candidates(self, client, candidate):
        score = choice_handler.score_choice_candidate(client, candidate)
        assert score == -100.0

    def test_arsenal_threat_and_saving_arsenal_via_sink(self, client):
        state = {
            "playerArsenal": [{"cardNumber": "red_in_the_ledger"}],
            "activeChainLink": {"cardNumber": "command_and_conquer"},
            "promptText": "Choose a card to sink to bottom of deck",
        }
        popup = {"title": "Sink Below"}

        # Candidato vindo do arsenal: deve priorizar salvar o arsenal (+150.0)
        cand_arsenal = {"cardNumber": "red_in_the_ledger", "actionDataOverride": "ars"}
        score_ars = choice_handler.score_choice_candidate(
            client, cand_arsenal, turn_phase="B", state=state, popup=popup
        )
        assert score_ars == 150.0

        # Candidato da mão durante ameaça ao arsenal: pontuação negativa (-50.0)
        cand_hand = {"cardNumber": "sink_below", "actionDataOverride": "hand_0"}
        score_hand = choice_handler.score_choice_candidate(
            client, cand_hand, turn_phase="B", state=state, popup=popup
        )
        assert score_hand == -50.0

    @pytest.mark.parametrize("threat_card", [
        "command_and_conquer",
        "leave_no_witnesses",
        "wreck_havoc",
        "eradicate",
        "humble",
        "righteous_cleansing",
    ])
    def test_all_arsenal_threat_cards(self, client, threat_card):
        state = {
            "playerArse": ["codex_of_frailty"],
            "activeChainLink": {"cardNumber": threat_card},
        }
        popup = {"caption": "Crown of Providence: choose card to bottom"}
        cand_ars = {"name": "codex_of_frailty", "label": "arsenal"}
        score = choice_handler.score_choice_candidate(client, cand_ars, state=state, popup=popup)
        assert score == 150.0

    def test_normal_sink_preserves_arsenal(self, client):
        state = {
            "playerArsenal": [{"cardNumber": "codex_of_frailty"}],
            "activeChainLink": {"cardNumber": "snatch_red"},  # Ataque normal, sem perigo de destruir arsenal
            "promptText": "Sink Below trigger",
        }
        popup = {"title": "Sink Below"}

        # Nunca deve afundar o arsenal se não estiver sob ameaça direta (-200.0)
        cand_ars = {"cardNumber": "codex_of_frailty", "actionDataOverride": "ars"}
        score_ars = choice_handler.score_choice_candidate(client, cand_ars, state=state, popup=popup)
        assert score_ars == -200.0

        # Carta normal da mão: inverte o score para afundar a pior carta
        client.policy_engine.extract_card_info.return_value = {"power": 2, "pitch": 3, "has_go_again": False}
        cand_hand = {"cardNumber": "generic_block_blue"}
        score_hand = choice_handler.score_choice_candidate(client, cand_hand, state=state, popup=popup)
        assert score_hand == -2.0  # -score

    def test_self_discard_inverts_score(self, client):
        state = {"playerHand": [{"cardNumber": "strong_attack_red"}, {"cardNumber": "weak_pitch_blue"}]}
        popup = {"title": "Choose card to discard"}

        # Carta forte (power 4, synergy leave_no_witnesses +25 = 29)
        # Com inversão para descarte, pontuação fica -29.0
        client.policy_engine.extract_card_info.return_value = {"power": 4, "pitch": 1, "has_go_again": False}
        cand_strong = {"cardNumber": "leave_no_witnesses"}
        score_discard = choice_handler.score_choice_candidate(
            client, cand_strong, turn_phase="DISCARD_HAND", state=state, popup=popup
        )
        assert score_discard == -29.0  # -(4 + 25)

    def test_pitch_and_go_again_bonuses(self, client):
        # Carta sem sinergia especial, mas com pitch 1 (+6.0)
        client.policy_engine.extract_card_info.return_value = {"power": 3, "pitch": 1, "has_go_again": False}
        score_pitch = choice_handler.score_choice_candidate(client, "generic_red")
        assert score_pitch == 9.0  # 3 + 6

        # Carta sem sinergia especial, mas com go again (+5.0)
        client.policy_engine.extract_card_info.return_value = {"power": 2, "pitch": 3, "has_go_again": True}
        score_ga = choice_handler.score_choice_candidate(client, "generic_yellow")
        assert score_ga == 7.0  # 2 + 5

    @pytest.mark.parametrize("card_name,expected_bonus", [
        ("leave_no_witnesses", 25.0),
        ("codex_of_frailty", 25.0),
        ("pulsewave_harpoon", 25.0),  # Matches leave_no_witnesses/pulsewave
        ("arrow_red", 20.0),
        ("harpoon_blue", 20.0),
        ("boom_grenade", 18.0),
        ("convection_amplifier", 18.0),
        ("riggermortis", 15.0),
        ("sink_below", 15.0),
    ])
    def test_card_synergies(self, client, card_name, expected_bonus):
        client.policy_engine.extract_card_info.return_value = {"power": 0, "pitch": 2, "has_go_again": False}
        score = choice_handler.score_choice_candidate(client, card_name)
        assert score == expected_bonus

    def test_candidate_without_policy_engine(self):
        client = MockClient()
        del client.policy_engine  # Sem policy_engine
        cand = {"cardNumber": "sink_below"}
        score = choice_handler.score_choice_candidate(client, cand)
        assert score == 15.0  # Bonus de sink_below sem falhar


class TestRankChoiceCandidates:
    """Testes para ordenação de opções em rank_choice_candidates."""

    def test_rank_candidates_order(self):
        client = MockClient()
        client.policy_engine.extract_card_info.side_effect = lambda c: {
            "power": 4 if "strong" in c["cardNumber"] else 1,
            "pitch": 1 if "red" in c["cardNumber"] else 3,
            "has_go_again": False,
        }
        candidates = [
            {"cardNumber": "weak_card_blue"},
            {"cardNumber": "leave_no_witnesses_red"},  # 4 + 25 + 6 = 35
            {"cardNumber": "pass"},                     # -100
            {"cardNumber": "strong_card_red"},          # 4 + 6 = 10
        ]
        ranked = choice_handler.rank_choice_candidates(client, candidates)
        ranked_names = [c["cardNumber"] for c in ranked]
        assert ranked_names == [
            "leave_no_witnesses_red",
            "strong_card_red",
            "weak_card_blue",
            "pass",
        ]


class TestCheckAndHandleAntiLoop:
    """Testes para detecção de loop e forçamento de ações de escape."""

    @pytest.fixture
    def client(self):
        c = MockClient()
        c.last_attempted_play = "zero_to_sixty"
        return c

    def test_no_loop_on_first_turn(self, client):
        state = {"playerHand": [1, 2], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        escaped = choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=unpayable
        )
        assert escaped is False
        assert client.consecutive_same_state == 0
        assert len(client.recent_phases) == 1

    def test_recent_phases_history_capped_at_20(self, client):
        state = {"playerHand": [1], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        for i in range(25):
            choice_handler.check_and_handle_anti_loop(
                client, state, turn_num=i, turn_phase=f"PHASE_{i}", prompt_buttons=[], unpayable_set=unpayable
            )
        assert len(client.recent_phases) <= 20

    def test_anti_loop_doc_rank_and_yesno(self, client):
        state = {"playerHand": [1, 2], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        # Forçar loop com mais de 4 repetições do mesmo estado
        client.consecutive_same_state = 5
        client.last_state_sig = (1, "YESNO", 2, 20, 20)

        escaped = choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="YESNO", prompt_buttons=[], unpayable_set=unpayable
        )
        assert escaped is True
        assert "zero_to_sixty" in unpayable
        assert len(client.sent_actions) == 1
        assert client.sent_actions[0] == {"mode": 20, "button_input": "NO"}
        assert client.consecutive_same_state == 0
        assert len(client.recent_phases) == 0

    def test_anti_loop_may_choose_forces_pass(self, client):
        state = {"playerHand": [], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        client.consecutive_same_state = 5
        client.last_state_sig = (1, "MAYCHOOSEMULTIZONE", 0, 20, 20)

        escaped = choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="MAYCHOOSEMULTIZONE", prompt_buttons=[], unpayable_set=unpayable
        )
        assert escaped is True
        assert client.sent_actions[0] == {"mode": 99, "button_input": "PASS"}

    def test_anti_loop_multichoose_escalation_empty_then_index_zero(self, client):
        state = {"playerHand": [1], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        client.consecutive_same_state = 5
        client.last_state_sig = (1, "CHOOSEMULTIZONE", 1, 20, 20)

        # Streak < 3 -> submete vazio
        client._anti_loop_streak = 1
        choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="CHOOSEMULTIZONE", prompt_buttons=[], unpayable_set=unpayable
        )
        assert client.sent_actions[-1] == {"mode": 19, "chk_count": 0, "chk_input": []}

        # Streak >= 3 -> força seleção do índice 0
        client.consecutive_same_state = 5
        client.last_state_sig = (1, "CHOOSEMULTIZONE", 1, 20, 20)
        client._anti_loop_streak = 3
        choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="CHOOSEMULTIZONE", prompt_buttons=[], unpayable_set=unpayable
        )
        assert client.sent_actions[-1] == {"mode": 19, "chk_count": 1, "chk_input": ["0"]}
        assert client._anti_loop_streak == 0

    def test_anti_loop_multichoosetext_mandatory_index_zero(self, client):
        state = {"playerHand": [], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        client.consecutive_same_state = 5
        client.last_state_sig = (1, "MULTICHOOSETEXT", 0, 20, 20)

        escaped = choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="MULTICHOOSETEXT", prompt_buttons=[], unpayable_set=unpayable
        )
        assert escaped is True
        assert client.sent_actions[0] == {"mode": 19, "chk_count": 1, "chk_input": ["0"]}

    def test_anti_loop_pitch_with_cancel_button(self, client):
        state = {"playerHand": [], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        client.consecutive_same_state = 5
        client.last_state_sig = (1, "P", 0, 20, 20)
        prompt_buttons = [{"caption": "Cancel Pitch", "mode": 10000, "buttonInput": "cancel"}]

        escaped = choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="P", prompt_buttons=prompt_buttons, unpayable_set=unpayable
        )
        assert escaped is True
        assert client.sent_actions[0] == {"mode": 10000, "button_input": "cancel"}

    def test_anti_loop_pitch_fallback_mode_10000(self, client):
        state = {"playerHand": [], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        client.consecutive_same_state = 5
        client.last_state_sig = (1, "PAYGOLDORPITCH", 0, 20, 20)

        escaped = choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="PAYGOLDORPITCH", prompt_buttons=[], unpayable_set=unpayable
        )
        assert escaped is True
        assert client.sent_actions[0] == {"mode": 10000, "button_input": ""}

    def test_anti_loop_other_phase_with_pass_button(self, client):
        state = {"playerHand": [], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        client.consecutive_same_state = 5
        client.last_state_sig = (1, "M", 0, 20, 20)
        prompt_buttons = [{"caption": "Pass Priority", "mode": 101, "buttonInput": "pass"}]

        escaped = choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="M", prompt_buttons=prompt_buttons, unpayable_set=unpayable
        )
        assert escaped is True
        assert client.sent_actions[0] == {"mode": 101, "button_input": "pass"}

    def test_anti_loop_cyclic_loop_detection(self, client):
        state = {"playerHand": [1], "playerHealth": 20, "opponentHealth": 20}
        unpayable = set()
        client.recent_phases = ["M_zero_to_sixty", "M_zero_to_sixty"]

        escaped = choice_handler.check_and_handle_anti_loop(
            client, state, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=unpayable
        )
        assert escaped is True
        assert client.sent_actions[0] == {"mode": 99, "button_input": ""}

    def test_anti_loop_initializes_missing_client_attributes(self):
        bare_client = MagicMock()
        del bare_client.recent_phases
        del bare_client.last_state_sig
        state = {"playerHand": [], "playerHealth": 20, "opponentHealth": 20}
        choice_handler.check_and_handle_anti_loop(
            bare_client, state=state, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert hasattr(bare_client, "recent_phases")
        assert hasattr(bare_client, "last_state_sig")


class TestHandlePopupAndChoices:
    """Testes para modais, popups, seleção de cartas/zonas e multichoose."""

    @pytest.fixture
    def client(self):
        return MockClient()

    def test_input_card_name_sink_below(self, client):
        handled = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase="INPUTCARDNAME", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 30, "input_text": "Sink Below"}

    @pytest.mark.parametrize("is_my_turn,random_val,expected_choice", [
        (True, 0.5, "YES"),
        (True, 0.8, "NO"),
        (False, 0.5, "NO"),
        (False, 0.95, "YES"),
    ])
    def test_docrank_choices(self, client, monkeypatch, is_my_turn, random_val, expected_choice):
        import random
        monkeypatch.setattr(random, "random", lambda: random_val)
        state = {"amIActivePlayer": is_my_turn, "turnPlayer": client.player_id if is_my_turn else 2}

        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="DOCRANK", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[-1] == {"mode": 20, "button_input": expected_choice}

    def test_yesno_insufficient_resources(self, client):
        client.policy_engine.calculate_available_resources.return_value = (0, 1)  # total_res < 2
        state = {"playerHand": [{"cardNumber": "red_card"}]}  # hand <= 1

        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="YESNO", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 20, "button_input": "NO"}

    def test_yesno_blocked_card_anti_loop(self, client):
        client.last_attempted_play = "blocked_card"
        unpayable = {"blocked_card"}
        state = {"playerHand": [1, 2, 3]}

        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="YESNO", popup={}, prompt_buttons=[], unpayable_set=unpayable
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 20, "button_input": "NO"}

    def test_yesno_accepted(self, client):
        client.policy_engine.calculate_available_resources.return_value = (2, 5)
        state = {"playerHand": [1, 2, 3]}

        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="YESNO", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 20, "button_input": "YES"}

    def test_popup_modal_active_yesno(self, client, monkeypatch):
        import random
        monkeypatch.setattr(random, "random", lambda: 0.1)
        popup = {"active": True, "popup": {"type": "YESNO"}}
        state = {"amIActivePlayer": True}

        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="M", popup=popup, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 20, "button_input": "YES"}

    def test_popup_modal_active_button(self, client):
        popup = {
            "active": True,
            "popup": {
                "buttons": [{"mode": 18, "caption": "Confirm Search", "buttonInput": "confirm"}]
            }
        }
        handled = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase="M", popup=popup, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 18, "button_input": "confirm"}

    def test_popup_modal_active_cards_array_multizone_mode_19(self, client):
        popup = {
            "active": True,
            "formOptions": {"mode": 19},
            "popup": {
                "cardsArray": [
                    {"cardNumber": "generic_scrap"},
                    {"cardNumber": "convection_amplifier_red"},  # matches priority 'amplifier'
                ]
            }
        }
        handled = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase="M", popup=popup, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 19, "chk_count": 1, "chk_input": ["1"]}

    def test_popup_modal_active_cards_array_single_action(self, client):
        popup = {
            "active": True,
            "popup": {
                "cardsArray": [
                    {"cardNumber": "pounder_item", "action": 25, "actionDataOverride": "item_99"}
                ]
            }
        }
        handled = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase="M", popup=popup, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 25, "card_id": "item_99", "button_input": "item_99"}

    @pytest.mark.parametrize("phase", [
        "BUTTONINPUT", "BUTTONINPUTNOPASS", "CHOOSEARCANE", "CHOOSEFIRSTPLAYER", "CHOOSETRIGGERS"
    ])
    def test_button_input_and_trigger_phases(self, client, phase):
        prompt_buttons = [{"buttonInput": "trigger_1"}]
        handled = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase=phase, popup={}, prompt_buttons=prompt_buttons, unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 17, "button_input": "trigger_1"}

    def test_button_input_from_player_input_popup(self, client):
        state = {
            "playerInputPopUp": {
                "buttons": [
                    {"mode": 17, "buttonInput": "2", "caption": "2"}
                ]
            }
        }
        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="BUTTONINPUT", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 17, "button_input": "2"}

    def test_button_input_anti_loop_forces_button_not_pass(self, client):
        state = {
            "playerInputPopUp": {
                "buttons": [
                    {"mode": 17, "buttonInput": "1", "caption": "1"},
                    {"mode": 17, "buttonInput": "2", "caption": "2"}
                ]
            }
        }
        client.last_attempted_play = ""
        client.recent_phases = ["BUTTONINPUT_"] * 5
        handled = choice_handler.check_and_handle_anti_loop(
            client, state=state, turn_num=1, turn_phase="BUTTONINPUT", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        # Em vez de mode 99 (Pass inválido), envia o botão válido
        assert client.sent_actions[0]["mode"] == 17
        assert client.sent_actions[0]["button_input"] in ("1", "2")

    def test_choose_card_with_popup_data(self, client):
        popup = {
            "data": {
                "cardsArray": [
                    {"cardNumber": "weak_card", "actionDataOverride": "card_0"},
                    {"cardNumber": "sink_below", "actionDataOverride": "card_1"},  # Score +15
                ]
            }
        }
        handled = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase="CHOOSECARD", popup=popup, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 16, "card_id": "card_1", "button_input": "card_1"}

    def test_choose_discard_fallback_to_state(self, client):
        state = {
            "playerDiscard": [
                {"cardNumber": "generic_card", "actionDataOverride": "disc_0"},
                {"cardNumber": "leave_no_witnesses", "actionDataOverride": "disc_1"},
            ]
        }
        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="CHOOSEDISCARD", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 16, "card_id": "disc_1", "button_input": "disc_1"}

    def test_choose_hand_fallback_to_state(self, client):
        state = {
            "playerHand": [
                {"cardNumber": "generic_card", "actionDataOverride": "hand_0"},
                {"cardNumber": "sink_below", "actionDataOverride": "hand_1"},
            ]
        }
        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="CHOOSEHAND", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 16, "card_id": "hand_1", "button_input": "hand_1"}

    def test_multichoose_empty_may_vs_mandatory(self, client):
        # MAYCHOOSEMULTIZONE vazio -> Pass Mode 99
        handled_may = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase="MAYCHOOSEMULTIZONE", popup={"formOptions": {"maxCount": 0}},
            prompt_buttons=[], unpayable_set=set()
        )
        assert handled_may is True
        assert client.sent_actions[-1] == {"mode": 99, "button_input": "PASS"}

        # CHOOSEMULTIZONE vazio -> Confirma vazio Mode 19
        handled_mand = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase="CHOOSEMULTIZONE", popup={"formOptions": {"maxCount": 0}},
            prompt_buttons=[], unpayable_set=set()
        )
        assert handled_mand is True
        assert client.sent_actions[-1] == {"mode": 19, "chk_count": 0, "chk_input": []}

    def test_multichoose_selects_best_with_prompt_button(self, client):
        state = {
            "playerHand": [
                {"cardNumber": "weak_card"},
                {"cardNumber": "leave_no_witnesses"},
            ]
        }
        prompt_buttons = [{"mode": 19, "caption": "Submit", "buttonInput": "btn_submit"}]
        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="MULTICHOOSEHAND", popup={}, prompt_buttons=prompt_buttons, unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {
            "mode": 19,
            "button_input": "btn_submit",
            "chk_count": 1,
            "chk_input": ["1"],
        }

    def test_multichoosetext_optional_and_empty(self, client):
        popup = {"formOptions": {"minNo": 0, "maxNo": 1}}
        handled = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase="MAYMULTICHOOSETEXT", popup=popup, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 99, "button_input": "PASS"}

    def test_multichoosetext_semantic_options_selection(self, client):
        # Fabricate do Teklovossen: opções de texto semânticas
        state = {
            "multiChooseText": [
                {"text": "Search deck for generic card"},     # s = 5 (search)
                {"text": "Equip an Evo equipment from graveyard"},  # s = 15 (evo, equipment)
                {"text": "Gain 1 Action Point and Draw a card"},    # s = 12 (action point, draw)
            ]
        }
        popup = {"formOptions": {"minNo": 2, "maxNo": 2}}

        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="MULTICHOOSETEXT", popup=popup, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        # As melhores duas opções são índice 1 (score 15) e índice 2 (score 12)
        assert client.sent_actions[0] == {
            "mode": 19,
            "chk_count": 2,
            "chk_input": ["1", "2"],
        }

    def test_multichoosetext_all_semantic_categories(self, client):
        state = {
            "multiChooseText": [
                {"text": "Deal 4 damage with overpower and piercing"},  # s = 10 (damage, overpower, piercing)
                {"text": "Create a gold and treasure token"},           # s = 8 (gold, treasure, token)
                {"text": "Plain text with no keywords"},                # s = 0
            ]
        }
        popup = {"formOptions": {"minNo": 2, "maxNo": 2}}
        handled = choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="MULTICHOOSETEXT", popup=popup, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0]["chk_input"] == ["0", "1"]

    @pytest.mark.parametrize("phase", ["CHOOSENUMBER", "DYNPITCH", "NUMBERINPUT"])
    def test_number_input_phases(self, client, phase):
        handled = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase=phase, popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 7, "button_input": "0"}

    def test_choosetop_and_choosebottom(self, client):
        state = {"playerHand": [{"cardNumber": "red_card"}]}

        # CHOOSETOP -> Mode 12
        choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="CHOOSETOP", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert client.sent_actions[-1] == {"mode": 12, "button_input": "red_card"}

        # CHOOSEBOTTOM -> Mode 13
        choice_handler.handle_popup_and_choices(
            client, state=state, turn_phase="CHOOSEBOTTOM", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert client.sent_actions[-1] == {"mode": 13, "button_input": "red_card"}

    def test_unhandled_phase_returns_false(self, client):
        handled = choice_handler.handle_popup_and_choices(
            client, state={}, turn_phase="UNHANDLED_PHASE", popup={}, prompt_buttons=[], unpayable_set=set()
        )
        assert handled is False


# ==============================================================================
# TESTES DE PHASE_DECIDER
# ==============================================================================

class TestPhaseDeciderPitch:
    """Testes para handle_pitch_phase: PDECK, seleção ótima e cancelamento."""

    @pytest.fixture
    def client(self):
        return MockClient()

    def test_non_pitch_phase_ignored(self, client):
        handled = phase_decider.handle_pitch_phase(
            client, state={}, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is False

    def test_pdeck_with_pitch_card(self, client):
        state = {"playerPitch": [{"cardNumber": "blue_pitch_card"}]}
        handled = phase_decider.handle_pitch_phase(
            client, state=state, turn_phase="PDECK", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {
            "mode": 6,
            "card_id": "blue_pitch_card",
            "button_input": "blue_pitch_card",
        }

    def test_pdeck_empty(self, client):
        state = {"playerPitch": []}
        handled = phase_decider.handle_pitch_phase(
            client, state=state, turn_phase="PDECK", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 6, "card_id": "0", "button_input": "0"}

    def test_tactical_pitch_selected(self, client):
        client.policy_engine.select_best_pitch_card.return_value = (0, "blue_resource_card", 6, "123")
        handled = phase_decider.handle_pitch_phase(
            client, state={}, turn_phase="P", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {
            "mode": 6,
            "card_id": "123",
            "button_input": "blue_resource_card",
        }

    def test_no_pitch_available_with_cancel_button(self, client):
        client.policy_engine.select_best_pitch_card.return_value = None
        client.last_attempted_play = "costly_attack"
        prompt_buttons = [{"caption": "Cancel", "mode": 10000, "buttonInput": "cancel"}]
        unpayable = set()

        handled = phase_decider.handle_pitch_phase(
            client, state={}, turn_phase="P", prompt_buttons=prompt_buttons, unpayable_set=unpayable
        )
        assert handled is True
        assert "costly_attack" in unpayable
        assert client.sent_actions[0] == {"mode": 10000, "button_input": "cancel"}

    def test_no_pitch_available_fallback_mode_10000(self, client):
        client.policy_engine.select_best_pitch_card.return_value = None
        unpayable = set()
        handled = phase_decider.handle_pitch_phase(
            client, state={}, turn_phase="PAYGOLDORPITCH", prompt_buttons=[], unpayable_set=unpayable
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 10000, "button_input": ""}


class TestPhaseDeciderBlock:
    """Testes para handle_block_phase: integração com plano de turno, bloqueios e passagem."""

    @pytest.fixture
    def client(self):
        return MockClient()

    def test_non_block_phase_ignored(self, client):
        handled = phase_decider.handle_block_phase(
            client, state={"turnPhase": "M"}, turn_num=1, prompt_buttons=[]
        )
        assert handled is False

    def test_tactical_block_declared(self, client):
        state = {
            "turnPhase": "B",
            "playerEquipment": [{"cardNumber": "ironrot_legs"}],
            "mock_chain_desc": "Snatch (Power: 4)",
        }
        client.policy_engine.select_defense_blocks.return_value = [
            (0, "eq_0", "ironrot_legs", 1)
        ]

        handled = phase_decider.handle_block_phase(
            client, state=state, turn_num=1, prompt_buttons=[]
        )
        assert handled is True
        assert client.blocks_declared_count == 1
        assert client.equipment_tracker.track_block.called
        assert client.sent_actions[0] == {"mode": 1, "card_id": "eq_0", "button_input": "ironrot_legs"}

        # Chamada subsequente com o mesmo bloco já declarado deve passar
        client.sent_actions.clear()
        handled_second = phase_decider.handle_block_phase(
            client, state=state, turn_num=1, prompt_buttons=[]
        )
        assert handled_second is True
        assert client.sent_actions[0] == {"mode": 99, "button_input": ""}

    def test_pass_block_with_button(self, client):
        state = {"turnPhase": "B"}
        client.policy_engine.select_defense_blocks.return_value = []
        prompt_buttons = [{"caption": "Pass Block", "mode": 101, "buttonInput": "pass"}]

        handled = phase_decider.handle_block_phase(
            client, state=state, turn_num=1, prompt_buttons=prompt_buttons
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 101, "button_input": "pass"}

    def test_block_phase_initializes_declared_blocks_link(self):
        bare_client = MockClient()
        del bare_client.declared_blocks_link
        bare_client.policy_engine.select_defense_blocks.return_value = []
        phase_decider.handle_block_phase(
            bare_client, state={"turnPhase": "B"}, turn_num=1, prompt_buttons=[]
        )
        assert hasattr(bare_client, "declared_blocks_link")


class TestPhaseDeciderReaction:
    """Testes para handle_reaction_phase: podas defensivas/ofensivas e equipamentos."""

    @pytest.fixture
    def client(self):
        return MockClient()

    def test_reaction_phase_initializes_reaction_attempts(self):
        bare_client = MockClient()
        del bare_client.reaction_attempts
        phase_decider.handle_reaction_phase(
            bare_client, state={}, turn_num=1, turn_phase="D", prompt_buttons=[], unpayable_set=set()
        )
        assert hasattr(bare_client, "reaction_attempts")

    def test_non_reaction_phase_ignored(self, client):
        handled = phase_decider.handle_reaction_phase(
            client, state={}, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is False

    def test_offensive_instant_pruned_when_defending(self, client):
        state = {
            "turnPlayer": 2,  # Oponente atacando
            "playerHand": [
                {"cardNumber": "lightning_press_red", "action": 27, "cost": 0, "pitch": 1},
            ],
            "playerEquipment": [],
        }
        client.policy_engine.extract_card_info.return_value = {"cost": 0, "pitch": 1}

        # Lightning Press não deve ser jogada defendendo! Deve passar direto
        handled = phase_decider.handle_reaction_phase(
            client, state=state, turn_num=1, turn_phase="D", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        # Passou (Mode 99) em vez de gastar o instant ofensivo
        assert client.sent_actions[0] == {"mode": 99, "button_input": ""}

    def test_valid_hand_reaction_played(self, client):
        state = {
            "turnPlayer": 1,  # Nosso turno de ataque
            "playerHand": [
                {"cardNumber": "razor_reflex_red", "action": 27, "cost": 1, "pitch": 1},
            ],
            "playerEquipment": [],
        }
        client.policy_engine.extract_card_info.return_value = {"cost": 1, "pitch": 1}
        client.policy_engine.calculate_available_resources.return_value = (0, 3)

        handled = phase_decider.handle_reaction_phase(
            client, state=state, turn_num=1, turn_phase="A", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {"mode": 27, "card_id": "0", "button_input": "razor_reflex_red"}

    def test_reaction_attempts_limit_blocks_card(self, client):
        state = {
            "turnPlayer": 1,
            "playerHand": [{"cardNumber": "stuck_card", "action": 27}],
            "playerEquipment": [],
        }
        client.reaction_attempts = {"stuck_card": 2}
        unpayable = set()

        handled = phase_decider.handle_reaction_phase(
            client, state=state, turn_num=1, turn_phase="A", prompt_buttons=[], unpayable_set=unpayable
        )
        assert handled is True
        assert "stuck_card" in unpayable
        assert client.sent_actions[0] == {"mode": 99, "button_input": ""}

    def test_equipment_omniward_pruned_when_safe(self, client):
        # Omniward com vida alta e sem ameaça on-hit não deve ser queimada
        state = {
            "turnPlayer": 2,
            "playerHealth": 20,
            "playerEquipment": [
                {"cardNumber": "boots_of_omniward", "action": 15, "slot": "legs"}
            ],
            "activeChainLink": {"totalPower": 3, "cardNumber": "generic_attack"},
        }
        handled = phase_decider.handle_reaction_phase(
            client, state=state, turn_num=1, turn_phase="D", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        # Não ativou Omniward, passou
        assert client.sent_actions[0] == {"mode": 99, "button_input": ""}

    def test_equipment_prevention_activated_on_arcane_or_lethal(self, client):
        # Sofrendo 4 de dano arcano com pouco HP -> Ativa Omniward/Barrier
        state = {
            "turnPlayer": 2,
            "playerHealth": 5,
            "arcaneDamage": 4,
            "playerEquipment": [
                {"cardNumber": "boots_of_omniward", "action": 15, "slot": "legs", "actionDataOverride": "eq_legs"}
            ],
            "activeChainLink": {"totalPower": 0},
        }
        handled = phase_decider.handle_reaction_phase(
            client, state=state, turn_num=1, turn_phase="INSTANT", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[0] == {
            "mode": 15,
            "card_id": "eq_legs",
            "button_input": "boots_of_omniward",
        }

    def test_equipment_snapdragon_scalers_pruning_and_activation(self, client):
        # 1. Pruned se ataque já tem Go Again
        state_ga = {
            "turnPlayer": 1,
            "playerHand": [{"cardNumber": "next_attack"}],
            "playerEquipment": [{"cardNumber": "snapdragon_scalers", "action": 15, "slot": "legs"}],
            "activeChainLink": {"hasGoAgain": True},
        }
        phase_decider.handle_reaction_phase(
            client, state=state_ga, turn_num=1, turn_phase="A", prompt_buttons=[], unpayable_set=set()
        )
        assert client.sent_actions[-1] == {"mode": 99, "button_input": ""}

        # 2. Pruned se mão vazia
        client.sent_actions.clear()
        state_no_hand = {
            "turnPlayer": 1,
            "playerHand": [],
            "playerEquipment": [{"cardNumber": "snapdragon_scalers", "action": 15, "slot": "legs"}],
            "activeChainLink": {"hasGoAgain": False},
        }
        phase_decider.handle_reaction_phase(
            client, state=state_no_hand, turn_num=1, turn_phase="A", prompt_buttons=[], unpayable_set=set()
        )
        assert client.sent_actions[-1] == {"mode": 99, "button_input": ""}

        # 3. Ativado quando atacando, sem Go Again e com cartas na mão
        client.sent_actions.clear()
        state_valid = {
            "turnPlayer": 1,
            "playerHand": [{"cardNumber": "next_attack"}],
            "playerEquipment": [{"cardNumber": "snapdragon_scalers", "action": 15, "slot": "legs", "actionDataOverride": "eq_0"}],
            "activeChainLink": {"hasGoAgain": False},
        }
        phase_decider.handle_reaction_phase(
            client, state=state_valid, turn_num=1, turn_phase="A", prompt_buttons=[], unpayable_set=set()
        )
        assert client.sent_actions[-1] == {
            "mode": 15,
            "card_id": "eq_0",
            "button_input": "snapdragon_scalers",
        }

    def test_equipment_reactions_edge_cases(self, client):
        unpayable = set()
        client.reaction_attempts = {"broken_boots": 2}
        client.strategy.evaluate_equipment_ability.return_value = 0.0  # score <= 0
        state = {
            "turnPlayer": 2,  # defendendo
            "playerHealth": 20,
            "arcaneDamage": 0,
            "playerEquipment": [
                "string_item_not_dict",
                {"slot": "hero", "action": 15, "cardNumber": "hero_card"},
                {"isBroken": True, "action": 15, "cardNumber": "broken_card"},
                {"onChain": True, "action": 15, "cardNumber": "onchain_card"},
                {"cardNumber": "broken_boots", "action": 15, "slot": "legs"},
                {"cardNumber": "boots_of_omniward", "action": 15, "slot": "legs"},
                {"cardNumber": "snapdragon_scalers", "action": 15, "slot": "legs"},
                {"cardNumber": "flick_knives", "action": 15, "slot": "arms"},
                {"cardNumber": "generic_helm", "action": 15, "slot": "head"},
            ],
            "activeChainLink": {"totalPower": 0},
        }
        prompt_buttons = [{"caption": "Pass Reactions", "mode": 100, "buttonInput": "pass"}]
        handled = phase_decider.handle_reaction_phase(
            client, state=state, turn_num=1, turn_phase="D", prompt_buttons=prompt_buttons, unpayable_set=unpayable
        )
        assert handled is True
        assert "broken_boots" in unpayable
        assert client.sent_actions[0] == {"mode": 100, "button_input": "pass"}

    def test_prevention_eq_when_attacking_no_arcane_pruned(self, client):
        state = {
            "turnPlayer": 1,  # atacando
            "playerHealth": 20,
            "arcaneDamage": 0,
            "playerEquipment": [
                {"cardNumber": "barrier_belt", "action": 15, "slot": "chest"}
            ],
            "activeChainLink": {"totalPower": 4},
        }
        handled = phase_decider.handle_reaction_phase(
            client, state=state, turn_num=1, turn_phase="A", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.sent_actions[-1] == {"mode": 99, "button_input": ""}


class TestPhaseDeciderArsenal:
    """Testes para handle_arsenal_phase: seleção e colocação no Arsenal."""

    @pytest.fixture
    def client(self):
        return MockClient()

    def test_non_arsenal_phase_ignored(self, client):
        handled = phase_decider.handle_arsenal_phase(client, state={"turnPhase": "M"}, turn_num=1)
        assert handled is False

    def test_arsenal_card_selected(self, client):
        client.policy_engine.select_arsenal_card.return_value = ("sink_below", "hand_0")
        state = {"turnPhase": "ARS"}

        handled = phase_decider.handle_arsenal_phase(client, state=state, turn_num=1)
        assert handled is True
        assert client.sent_actions[0] == {"mode": 4, "card_id": "hand_0", "button_input": "hand_0"}

    def test_arsenal_none_passes(self, client):
        client.policy_engine.select_arsenal_card.return_value = None
        state = {"turnPhase": "ARS"}

        handled = phase_decider.handle_arsenal_phase(client, state=state, turn_num=1)
        assert handled is True
        assert client.sent_actions[0] == {"mode": 99, "button_input": ""}


class TestPhaseDeciderMainAction:
    """Testes para handle_main_action_phase: AP, ataques, telemetria e trajetórias."""

    @pytest.fixture
    def client(self):
        return MockClient()

    def test_opponent_turn_ignored(self, client):
        state = {"amIActivePlayer": False, "turnPlayer": 2, "playerAP": 1}
        handled = phase_decider.handle_main_action_phase(
            client, state=state, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is False

    def test_no_ap_and_no_teklo_ability_ignored(self, client):
        state = {"amIActivePlayer": True, "playerAP": 0}
        handled = phase_decider.handle_main_action_phase(
            client, state=state, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is False

    def test_attack_execution_and_trajectory(self, client):
        state = {"amIActivePlayer": True, "playerAP": 1}
        best_atk = {
            "name": "zero_to_sixty_red",
            "mode": 27,
            "card_id": "0",
            "score": 8.5,
            "power": 4,
            "cost": 0,
            "has_go_again": True,
            "type": "attack_action",
        }
        client.policy_engine.select_best_attack.return_value = best_atk

        handled = phase_decider.handle_main_action_phase(
            client, state=state, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.attacks_made == 1
        assert client.sent_actions[0] == {"mode": 27, "card_id": "0", "button_input": "zero_to_sixty_red"}
        assert len(client.trajectory) == 1

    def test_equipment_ability_tracked(self, client):
        state = {"amIActivePlayer": True, "playerAP": 1}
        best_atk = {
            "name": "goliath_gauntlet",
            "mode": 15,
            "card_id": "eq_arms",
            "type": "equipment_ability",
            "power": 0,
            "cost": 0,
        }
        client.policy_engine.select_best_attack.return_value = best_atk

        handled = phase_decider.handle_main_action_phase(
            client, state=state, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.equipment_tracker.track_activation.called

    def test_hero_ability_teklovossen_activation(self, client):
        state = {"amIActivePlayer": True, "playerAP": 1}
        best_atk = {
            "name": "teklovossen_ability",
            "mode": 16,
            "card_id": "hero_0",
            "type": "hero_ability",
            "power": 0,
            "cost": 1,
        }
        client.policy_engine.select_best_attack.return_value = best_atk

        handled = phase_decider.handle_main_action_phase(
            client, state=state, turn_num=3, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is True
        assert client.teklo_ability_active_turn == 3

    def test_main_action_corrupted_ap_fallback(self, client):
        state = {"amIActivePlayer": True, "playerAP": "invalid"}
        client.policy_engine.select_best_attack.return_value = None
        # Não lança exceção, faz fallback para player_ap = 1 e segue
        handled = phase_decider.handle_main_action_phase(
            client, state=state, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert handled is False

    def test_main_action_teklo_ability_active_sets_state(self, client):
        client.teklo_ability_active_turn = 2
        state = {"amIActivePlayer": True, "playerAP": 0}
        client.policy_engine.select_best_attack.return_value = None
        handled = phase_decider.handle_main_action_phase(
            client, state=state, turn_num=2, turn_phase="M", prompt_buttons=[], unpayable_set=set()
        )
        assert state.get("teklo_ability_active") is True
        assert handled is False

    def test_main_action_ismcts_logger_and_trajectory_exception(self, client):
        state = {"amIActivePlayer": True, "playerAP": 1}
        best_atk = {
            "name": "plasma_barrel_shot",
            "mode": 27,
            "card_id": "0",
            "score": 9.0,
            "power": 6,
            "cost": 2,
            "_ismcts_log": {"simulations": 100},
            "_policy_dist": None,
        }
        client.policy_engine.select_best_attack.return_value = best_atk
        client.policy_engine.ismcts_logger = MagicMock()
        client.policy_engine.ismcts_logger.log.side_effect = Exception("Disk error")

        # Simular erro na distilação de rede neural para exercitar o bloco except
        with patch("ai.model.FaBPolicyValueNetwork.extract_state_vector", side_effect=RuntimeError("GPU OOM")):
            handled = phase_decider.handle_main_action_phase(
                client, state=state, turn_num=1, turn_phase="M", prompt_buttons=[], unpayable_set=set()
            )
            assert handled is True
            assert client.policy_engine.ismcts_logger.log.called


class TestPhaseDeciderPassButtons:
    """Testes para handle_pass_buttons."""

    @pytest.fixture
    def client(self):
        return MockClient()

    def test_clicks_pass_button_when_available(self, client):
        prompt_buttons = [
            {"caption": "End Turn", "mode": 101, "buttonInput": "end"},
        ]
        handled = phase_decider.handle_pass_buttons(client, prompt_buttons=prompt_buttons, turn_phase="M")
        assert handled is True
        assert client.sent_actions[0] == {"mode": 101, "button_input": "end"}

    def test_sends_mode_99_when_no_prompt_button(self, client):
        handled = phase_decider.handle_pass_buttons(client, prompt_buttons=[], turn_phase="M")
        assert handled is True
        assert client.sent_actions[0] == {"mode": 99, "button_input": ""}
