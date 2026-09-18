import pytest
import os
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
