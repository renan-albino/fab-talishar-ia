import pytest
import torch
import numpy as np
from ai.model import FaBPolicyValueNetwork, STATE_DIM, ACTION_DIM

def test_model_forward_pass_shapes():
    model = FaBPolicyValueNetwork(state_dim=192, action_dim=32, hidden_dim=128, num_res_blocks=2)
    model.eval()
    
    batch_size = 4
    x = torch.randn(batch_size, 192)
    with torch.no_grad():
        policy_logits, value = model(x)
        
    assert policy_logits.shape == (batch_size, 32)
    assert value.shape == (batch_size, 1)
    # Tanh bounds value between -1.0 and 1.0
    assert torch.all(value >= -1.0) and torch.all(value <= 1.0)

def test_extract_state_vector_shape_and_fallback():
    # Fallback with None or non-dict
    vec_none = FaBPolicyValueNetwork.extract_state_vector(None)
    assert isinstance(vec_none, np.ndarray)
    assert vec_none.shape == (192,)
    assert np.all(vec_none == 0.0)

    # Valid state
    state = {
        "playerHealth": 30,
        "opponentHealth": 20,
        "playerResources": [3, 0],
        "playerAP": 2,
        "turnPhase": "M"
    }
    vec = FaBPolicyValueNetwork.extract_state_vector(state)
    assert vec.shape == (192,)
    assert np.isclose(vec[0], 30.0 / 40.0)
    assert np.isclose(vec[1], 20.0 / 40.0)
    assert np.isclose(vec[2], 3.0 / 10.0)
    assert np.isclose(vec[3], 2.0 / 5.0)
    # Phase "M" should set index 4
    assert vec[4] == 1.0
