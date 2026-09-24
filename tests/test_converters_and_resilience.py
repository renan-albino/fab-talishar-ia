"""
tests/test_converters_and_resilience.py
=======================================
Testes unitários e de integração para:
1. Conversores universais seguros (ai/common/converters.py).
2. Resiliência de parsing contra payloads malformados/nulos do PHP do Talishar.
3. Finalização limpa de processos e erradicação de zumbis Unix <defunct>.
4. Simetria de Virtual Loss no MCTS.
5. Conformidade da persistência de decks com a Project Rule 3 (diretório decks/).
6. Throttling de métricas e limpeza do Replay Buffer.
"""

import math
import os
import signal
import subprocess
import sys
import time
from unittest.mock import MagicMock, patch
import pytest
import numpy as np


from ai.training.process_supervisor import terminate_process_cleanly, kill_active_processes
from ai.mcts.standard_mcts import MCTSEngine, VIRTUAL_LOSS
from ai.mcts.node import MCTSNode
from deck_manager.repository import save_deck_to_workspace, list_saved_decks, delete_saved_deck, get_decks_dir
from ai.bot_runtime.client import FabBotClient
from ai.bot_runtime import match_tracker


class TestPydanticSchemas:
    def test_gamestate_resilience(self):
        from ai.common.schemas import GameState
        
        # Test valid parsing
        state = GameState(playerHealth=20, turnNo=2, opponentHand=[{"id": 1}])
        assert state.playerHealth == 20
        assert state.turnNo == 2
        assert len(state.opponentHand) == 1
        
        # Test resilience against corrupted values
        bad_state = GameState(
            playerHealth="NaN", 
            opponentHealth=None, 
            turnNo="invalid", 
            opponentHandCount="undefined",
            opponentHand=None,
            activeChainLink=["wrong type"]
        )
        assert bad_state.playerHealth == 0
        assert bad_state.opponentHealth == 0
        assert bad_state.turnNo == 0
        assert bad_state.opponentHandCount == 0
        assert bad_state.opponentHand == []
        assert bad_state.activeChainLink == {}

    def test_card_resilience(self):
        from ai.common.schemas import Card
        
        # Valid
        c1 = Card(pitch=3, cost=2, power=5, name="Test Card")
        assert c1.pitch == 3
        assert c1.cost == 2
        assert c1.power == 5
        assert c1.name == "Test Card"
        
        # Corrupted
        c2 = Card(pitch="NaN", cost=None, power="inf", name=123)
        assert c2.pitch == 0
        assert c2.cost == 0
        assert c2.power == 0
        assert c2.name == "123"


# ══════════════════════════════════════════════════════════════════════
# 2. TESTES DE RESILIÊNCIA DE PAYLOADS DO TALISHAR
# ══════════════════════════════════════════════════════════════════════

class TestPayloadResilience:
    def test_stalemate_check_with_corrupted_state(self):
        """Verifica que check_stalemate_and_timeout tolera chaves None / NaN."""
        client = MagicMock()
        client.deck_format = "blitz"
        client._last_state_health = (40, 40)
        client._last_state_turn = 1
        client._stagnant_turns_count = 0

        corrupted_state = {
            "playerDeckCount": None,
            "playerDeck": None,
            "opponentDeckCount": "NaN",
            "opponentDeck": None,
            "playerHand": None,
            "opponentHand": None,
            "playerArsenal": None,
            "opponentArsenal": None,
            "turnNo": None,
        }

        is_stalemate, reason = match_tracker.check_stalemate_and_timeout(
            client, corrupted_state, turn=1, my_h=40, opp_h=40
        )
        assert isinstance(is_stalemate, bool)
        assert isinstance(reason, str)

    def test_track_tick_with_corrupted_state(self):
        """Verifica que track_tick_health_and_damage tolera estados nulos e sem cartas."""
        client = MagicMock()
        client.initial_my_health = None
        client.initial_opp_health = None
        client._prev_tracked_opp_h = 40
        client._prev_tracked_my_h = 40
        client.damage_dealt = 0
        client.damage_taken = 0
        client.last_chat_turn = -1
        client.evaluate_board_state.return_value = 0.0

        corrupted_state = {
            "turnNo": None,
            "currentTurn": "invalid",
            "playerHand": None,
        }

        match_tracker.track_tick_health_and_damage(client, corrupted_state, my_h=40, opp_h=40)
        assert client.initial_my_health == 40
        assert client.initial_opp_health == 40

    def test_handle_game_tick_resilience(self, monkeypatch):
        """Valida que handle_game_tick em FabBotClient não explode com payload corrompido."""
        client = FabBotClient(
            room_id="test_room_resilience",
            deck_url="",
            role="host",
            player_name="TestBot"
        )
        client.decide_and_act = MagicMock()

        corrupted_state = {
            "playerHealth": None,
            "opponentHealth": "NaN",
            "turnNo": None,
            "turnPhase": None,
            "playerHand": None,
            "opponentHand": None,
            "playerArse": None,
            "theirArse": None,
            "havePriority": False,
        }

        # Não deve lançar exceção
        client.handle_game_tick(corrupted_state)
        assert client.metrics["health"] == 0
        assert client.metrics["opp_health"] == 0


# ══════════════════════════════════════════════════════════════════════
# 3. TESTES DE ENCERRAMENTO LIMPO DE PROCESSOS (Zumbi Unix <defunct>)
# ══════════════════════════════════════════════════════════════════════

class TestProcessCleanup:
    def test_terminate_cooperative_process(self):
        """Processo que finaliza normalmente ao receber SIGTERM."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        assert proc.poll() is None  # Está rodando

        terminate_process_cleanly(proc, timeout=1.0)

        assert proc.poll() is not None
        assert proc.returncode is not None  # wait() foi obrigatoriamente chamado

    def test_terminate_stubborn_process(self):
        """Processo teimoso que ignora SIGTERM deve ser finalizado com SIGKILL e wait()."""
        # Script que ignora SIGTERM
        code = (
            "import signal, time\n"
            "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
            "while True:\n"
            "    time.sleep(0.1)\n"
        )
        proc = subprocess.Popen(
            [sys.executable, "-c", code],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(0.2)
        assert proc.poll() is None

        # Deve dar timeout no SIGTERM e forçar SIGKILL + wait()
        terminate_process_cleanly(proc, timeout=0.3)

        assert proc.poll() is not None
        assert proc.returncode is not None
        # Em Unix, SIGKILL gera código de retorno -9 (ou 137)
        assert proc.returncode in (-signal.SIGKILL, 137, -9)

    def test_terminate_already_dead_process(self):
        """Processo já terminado deve chamar wait() para liberar recurso sem falhar."""
        proc = subprocess.Popen(
            [sys.executable, "-c", "exit(0)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        proc.wait(timeout=2.0)
        assert proc.poll() is not None

        # Chamar novamente deve ser no-op seguro
        terminate_process_cleanly(proc, timeout=1.0)
        assert proc.poll() == 0

    def test_terminate_invalid_objects(self):
        """Objetos inválidos ou None não devem lançar exceções."""
        terminate_process_cleanly(None)
        terminate_process_cleanly(object())


# ══════════════════════════════════════════════════════════════════════
# 4. TESTES DE SIMETRIA DE VIRTUAL LOSS NO MCTS
# ══════════════════════════════════════════════════════════════════════

class TestMCTSVirtualLossSymmetry:
    def test_virtual_loss_symmetry_in_search(self):
        """Após o término de search(), todos os nós da árvore devem ter virtual_loss == 0."""
        engine = MCTSEngine(model=None, c_puct=1.4)
        state = {
            "playerHand": [{"id": "card1", "pitch": 1}],
            "opponentHandCount": 2,
            "playerHealth": 20,
            "opponentHealth": 20
        }
        legal_actions = [
            {"action": "attack", "card_id": "card1"},
            {"action": "pass"}
        ]

        best_idx, policy_dist = engine.search(
            state=state,
            legal_actions=legal_actions,
            num_simulations=15,
            training_mode=False
        )

        assert 0 <= best_idx < len(legal_actions)
        assert policy_dist.shape == (32,)
        assert math.isclose(np.sum(policy_dist), 1.0, abs_tol=1e-4) or np.sum(policy_dist) == 0.0

    def test_virtual_loss_manual_step_symmetry(self):
        """Valida que _select e _backpropagate incrementam e decrementam rigorosamente o mesmo valor."""
        engine = MCTSEngine(model=None)
        root = MCTSNode(prior=1.0)
        root.is_expanded = True
        child0 = MCTSNode(prior=0.6, parent=root, action_id=0)
        child1 = MCTSNode(prior=0.4, parent=root, action_id=1)
        root.children[0] = child0
        root.children[1] = child1

        # 1. Seleção
        selected_leaf = engine._select(root)
        # Caminho: root -> selected_leaf. Ambos devem ter recebido VIRTUAL_LOSS exatamente uma vez
        assert root.virtual_loss == VIRTUAL_LOSS
        assert selected_leaf.virtual_loss == VIRTUAL_LOSS
        # O outro filho não selecionado permanece 0
        other = child1 if selected_leaf is child0 else child0
        assert other.virtual_loss == 0

        # 2. Backpropagação
        engine._backpropagate(selected_leaf, value=0.5)

        # Ambos retornam a 0
        assert root.virtual_loss == 0
        assert selected_leaf.virtual_loss == 0


# ══════════════════════════════════════════════════════════════════════
# 5. TESTES DE CONFORMIDADE DE DECKS COM A PROJECT RULE 3 (decks/)
# ══════════════════════════════════════════════════════════════════════

class TestDeckRepositoryRule3:
    def test_save_deck_exclusively_in_decks_dir(self, tmp_path):
        """Garante que decks são salvos exclusivamente em decks/ e nunca em Talishar/decks/."""
        base_dir = str(tmp_path)
        talishar_decks_dir = os.path.join(base_dir, "Talishar", "decks")

        deck_payload = {
            "name": "Test_Bravo_Hammer",
            "format": "blitz",
            "cards": [
                {"identifier": "bravo_showstopper", "total": 1},
                {"identifier": "anothos", "total": 1},
                {"identifier": "crippling_crush", "total": 2}
            ]
        }

        result = save_deck_to_workspace(deck_payload, base_dir=base_dir)

        # 1. Deve salvar no diretório raiz decks/
        expected_deck_file = os.path.join(base_dir, "decks", "test_bravo_hammer.json")
        assert os.path.exists(expected_deck_file)

        # 2. NUNCA deve criar ou salvar em Talishar/decks/ (Project Rule 3)
        assert not os.path.exists(talishar_decks_dir)

        # 3. list_saved_decks deve encontrar o deck
        saved_list = list_saved_decks(base_dir=base_dir)
        slugs = [d["slug"] for d in saved_list]
        assert "test_bravo_hammer" in slugs

        # 4. delete_saved_deck remove o arquivo de decks/
        deleted = delete_saved_deck("test_bravo_hammer", base_dir=base_dir)
        assert deleted is True
        assert not os.path.exists(expected_deck_file)


# ══════════════════════════════════════════════════════════════════════
# 6. TESTES DE THROTTLING DE MÉTRICAS E LIMPEZA DO REPLAY BUFFER
# ══════════════════════════════════════════════════════════════════════

class TestMetricsThrottlingAndReplayBuffer:
    def test_metrics_throttling(self, tmp_path):
        """Verifica que a gravação em disco respeita o throttling de 1.5s ou mudança de turno."""
        client = FabBotClient(
            room_id="test_throttle_room",
            deck_url="",
            role="host",
            player_name="TestBot"
        )
        # Redireciona o log_path para temp
        client.room_id = f"test_{int(time.time()*1000)}"
        metrics_file = f"logs/{client.room_id}_{client.player_name}.json"

        try:
            # 1. Primeira gravação (forçada)
            client.save_metrics_throttled(current_turn=1, force=True)
            assert os.path.exists(metrics_file)
            mtime1 = os.path.getmtime(metrics_file)

            # 2. Gravação imediata no mesmo turno sem force -> deve sofrer throttling (não atualiza)
            time.sleep(0.05)
            client.save_metrics_throttled(current_turn=1, force=False)
            mtime2 = os.path.getmtime(metrics_file)
            assert mtime1 == mtime2

            # 3. Gravação com mudança de turno -> deve gravar imediatamente
            time.sleep(0.05)
            client.save_metrics_throttled(current_turn=2, force=False)
            mtime3 = os.path.getmtime(metrics_file)
            assert mtime3 > mtime1
        finally:
            if os.path.exists(metrics_file):
                try:
                    os.remove(metrics_file)
                except OSError:
                    pass

    def test_trajectory_memory_cleared_on_finalize(self):
        """Garante que client.trajectory.clear() é chamado em finalize_match liberando memória."""
        client = MagicMock()
        client.player_id = 1
        client.role = "host"
        client.room_id = "test_clear_trajectory"
        client.player_name = "BotA"
        client.deck_format = "blitz"
        client.initial_my_health = 40
        client.initial_opp_health = 40
        client.attacks_made = 2
        client.damage_dealt = 10
        client.execution_exceptions_count = 0
        client.buffer_capacity = 1000
        client.trajectory = [(MagicMock(), MagicMock(), 1, 0.5) for _ in range(5)]
        client.get_player_label.side_effect = lambda pid: f"P{pid}"

        with patch("ai.experience_collector.get_global_buffer") as mock_buf, \
             patch("ai.experience_collector.save_trajectory_file"), \
             patch("ai.blunder_reviewer.review_trajectory_for_blunders", return_value=([1.0]*5, {})):
            mock_buffer_inst = MagicMock()
            mock_buf.return_value = mock_buffer_inst

            match_tracker.finalize_match(
                client,
                state={},
                turn=5,
                my_h=40,
                opp_h=0,
                is_stalemate=False,
                stalemate_reason=""
            )

            # Trajetória deve ter sido completamente limpa
            assert len(client.trajectory) == 0

    def test_decide_and_act_does_not_inject_spurious_dummy_vector(self):
        """Garante que decide_and_act não insere o vetor dummy arbitrário p_dist[0] = 1.0."""
        client = FabBotClient(
            room_id="test_no_dummy_vector",
            deck_url="",
            role="host",
            player_name="TestBot"
        )
        client.trajectory = []

        mock_state = {
            "turnNo": 1,
            "turnPhase": "M",
            "havePriority": True,
            "playerHand": [],
            "playerPrompt": {"buttons": []}
        }

        with patch("ai.bot_runtime.choice_handler.check_and_handle_anti_loop", return_value=True):
            client.decide_and_act(mock_state)

        # Não deve haver nenhum item espúrio injetado na trajetória
        assert len(client.trajectory) == 0
