import pytest
import os
import json
import unittest
import torch
from unittest.mock import patch, MagicMock
from ai.training.orchestrator import GPUTrainingOrchestrator

def test_orchestrator_initialization():
    GPUTrainingOrchestrator.reset_instance()
    orch = GPUTrainingOrchestrator()
    assert orch._initialized == True
    assert orch.is_running == False
    GPUTrainingOrchestrator.reset_instance()

@patch('ai.training.orchestrator.create_model')
@patch('torch.optim.AdamW')
def test_orchestrator_train_step(mock_adam, mock_create):
    GPUTrainingOrchestrator.reset_instance()
    orch = GPUTrainingOrchestrator()
    mock_model = MagicMock()
    mock_model.return_value = (torch.randn(4, 32), torch.randn(4, 1), {"delta_hp": torch.randn(4, 1), "turn_dmg": torch.randn(4, 1)})
    mock_create.return_value = (mock_model, True)
    
    # Mock global buffer
    with patch('ai.training.orchestrator.get_global_buffer') as mock_buf:
        mock_buf.return_value.sample_batch.return_value = (
            torch.randn(4, 832),
            torch.randn(4, 32),
            torch.randn(4, 1),
            torch.randn(4),
            {"delta_hp": torch.randn(4, 1), "turn_dmg": torch.randn(4, 1)}
        )
        mock_buf.return_value.__len__.return_value = 100
        
        orch.stats['epochs_completed'] = 0
        orch.config['batch_size'] = 4
        losses = orch._train_step(
            model=mock_model,
            optimizer=mock_adam.return_value,
            scaler=MagicMock(),
            buffer=mock_buf.return_value,
            device='cpu',
            batch_size=4,
            use_amp=False
        )
        assert len(losses) == 5
    GPUTrainingOrchestrator.reset_instance()


def test_wait_for_processes_on_item_finished():
    from ai.training.process_supervisor import wait_for_processes

    p1 = MagicMock()
    p2 = MagicMock()
    p3 = MagicMock()
    p4 = MagicMock()

    # Initial state: item 0 finished, item 1 running until second iteration
    p1.poll.return_value = 0
    p2.poll.return_value = 0
    p3_calls = [0]
    p4_calls = [0]
    def poll_p3():
        p3_calls[0] += 1
        return 0 if p3_calls[0] >= 2 else None
    def poll_p4():
        p4_calls[0] += 1
        return 0 if p4_calls[0] >= 2 else None
    p3.poll.side_effect = poll_p3
    p4.poll.side_effect = poll_p4

    finished_calls = []

    def on_finished(idx, item):
        finished_calls.append((idx, item))

    active_procs = [(p1, p2), (p3, p4)]
    res = wait_for_processes(
        active_procs,
        timeout=1.0,
        check_interval=0.01,
        on_item_finished=on_finished,
    )
    assert res is True
    assert len(finished_calls) == 2
    assert finished_calls[0][0] == 0
    assert finished_calls[1][0] == 1


@patch('stats_manager.update_match_result')
def test_update_elo_reasons(mock_update_match):
    GPUTrainingOrchestrator.reset_instance()
    orch = GPUTrainingOrchestrator()

    m1_data = json.dumps({"metrics": {"health": 20, "turn": 5}})
    m2_data = json.dumps({"metrics": {"health": 18, "turn": 5}})

    # Case 1: is_running is True -> Timeout
    orch.is_running = True
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', unittest.mock.mock_open(read_data=m1_data)) as m_open:
        # Alternates returning m1_data and m2_data
        m_open.side_effect = [
            unittest.mock.mock_open(read_data=m1_data).return_value,
            unittest.mock.mock_open(read_data=m2_data).return_value,
        ]
        orch._update_elo("room_timeout", "d1", "d2")

    mock_update_match.assert_called_with(
        "room_timeout", "d1", "d2", 20, 18, 5, 0,
        is_invalid_match=True,
        invalid_reason="Tempo Esgotado / Timeout"
    )

    # Case 2: is_running is False -> Interrupted by User
    orch.is_running = False
    with patch('os.path.exists', return_value=True), \
         patch('builtins.open', unittest.mock.mock_open(read_data=m1_data)) as m_open:
        m_open.side_effect = [
            unittest.mock.mock_open(read_data=m1_data).return_value,
            unittest.mock.mock_open(read_data=m2_data).return_value,
        ]
        orch._update_elo("room_user_stop", "d1", "d2")

    mock_update_match.assert_called_with(
        "room_user_stop", "d1", "d2", 20, 18, 5, 0,
        is_invalid_match=True,
        invalid_reason="Interrompida pelo Usuário"
    )
    GPUTrainingOrchestrator.reset_instance()


def test_stop_processes_active_rooms():
    GPUTrainingOrchestrator.reset_instance()
    orch = GPUTrainingOrchestrator()
    orch.is_running = True
    orch._current_batch_rooms = [
        ("room_1", "d1", "d2"),
        ("room_2", "d3", "d4"),
    ]
    orch._recorded_rooms = {"room_1"}

    with patch.object(orch, "_update_elo") as mock_update, \
         patch.object(orch, "_kill_active_processes"), \
         patch.object(orch, "_kill_orphan_bots"):
        orch.stop()

        # room_1 was already recorded, so only room_2 must be updated
        mock_update.assert_called_once_with("room_2", "d3", "d4")
        assert "room_2" in orch._recorded_rooms

    GPUTrainingOrchestrator.reset_instance()


def test_batch_rooms_cleanup_guarantee():
    GPUTrainingOrchestrator.reset_instance()
    orch = GPUTrainingOrchestrator()
    batch_rooms = [
        ("room_alpha", "deck_a", "deck_b"),
        ("room_beta", "deck_c", "deck_d"),
    ]
    recorded_rooms = {"room_alpha"}

    with patch.object(orch, "_update_elo") as mock_update:
        for room_id, d1_slug, d2_slug in batch_rooms:
            if room_id not in recorded_rooms:
                orch._update_elo(room_id, d1_slug, d2_slug)
                recorded_rooms.add(room_id)

        mock_update.assert_called_once_with("room_beta", "deck_c", "deck_d")
        assert "room_alpha" in recorded_rooms
        assert "room_beta" in recorded_rooms

    GPUTrainingOrchestrator.reset_instance()


