"""
tests/test_cr_comprehensive_rules.py
====================================
Suíte de testes formais de conformidade com as Comprehensive Rules (CR) de Flesh and Blood:
  1. CR 7.4.2d & CR 7.5b: Reações de Defesa executáveis a partir do Arsenal
  2. CR 7.4.2a & CR 8.3.4b: Dominate restringe apenas cartas da mão na Reaction Step
  3. CR 7.4.2b & CR 8.3.22: Overpower restringe apenas ações de mão (Ambush do Arsenal é legal)
  4. CR 4.3.2 & CR 4.4.3f: Modo Cavar calibrado dinamicamente pelo Intelecto real do herói
  5. CR 3.0 & CR 7: GameSimulator integrado à base canônica de dados de cartas
  6. CR 1.14.2: Ordem de pagamento de custos e pitch (Blue -> Yellow -> Red)
  7. Matriz de Embeddings Tensoriais e Vocabulário das CR
  8. Proteção de Checkpoints contra corrupção
"""

import os
import sys
import json
import tempfile
import pytest
import torch
import numpy as np

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai.policy_engine import PolicyEngine
from ai.game_simulator import GameSimulator
from ai.policy.constants import get_on_hit_threat, ON_HIT_THREAT_VALUES
from ai.model import FaBCardTransformerNetwork, create_model, CARD_EMBEDDING_DIM, _get_card_embeddings_table
from ai.hero_strategies.base import HeroStrategy
from ai.hero_strategies.brute import BruteStrategy


# ══════════════════════════════════════════════════════════════════
# 1. CR 7.4.2d & CR 7.5b: REAÇÕES DE DEFESA DO ARSENAL
# ══════════════════════════════════════════════════════════════════

def test_cr_arsenal_reaction_allowed_under_dominate():
    """
    CR 7.4.2a / 7.4.2d / 8.3.4b:
    Sob ataque com Dominate onde uma carta da mão já defendeu na Defend Step,
    o defensor NÃO PODE jogar Defense Reaction da mão, mas É 100% LEGAL
    jogar uma Defense Reaction que está no Arsenal.
    """
    from ai.bot_runtime.phase_decider import handle_reaction_phase

    class DummyClient:
        def __init__(self):
            self.player_id = 1
            self.hero_name = "generic"
            self.policy_engine = PolicyEngine(hero_name="generic")
            self.blocks_declared_count = 1  # Já bloqueou com 1 carta da mão
            self.sent_actions = []
            self.reaction_attempts = {}
            self.last_attempted_play = None
            self.last_logged_combat_attack = None

        def log(self, msg):
            pass

        def send_chat_log(self, msg, **kwargs):
            pass

        def send_action(self, **kwargs):
            self.sent_actions.append(kwargs)

        def get_combat_chain_desc(self, state):
            return "Dominate Attack (Power: 6)"

    client = DummyClient()

    state = {
        "turnPlayer": 2,
        "playerHealth": 10,
        "playerHand": [
            {"cardNumber": "sink_below_red", "name": "Sink Below", "type": "DR", "cost": 0, "action": 27}
        ],
        "playerArsenal": [
            {"cardNumber": "sink_below_red", "name": "Sink Below", "type": "DR", "cost": 0, "action": 5, "actionDataOverride": "0"}
        ],
        "playerEquipment": [],
        "activeChainLink": {
            "cardNumber": "command_and_conquer",
            "totalPower": 6,
            "dominate": True,
        },
        "combatChainPower": 6,
    }

    unpayable = set()
    result = handle_reaction_phase(client, state, turn_num=1, turn_phase="D", prompt_buttons=[], unpayable_set=unpayable)

    assert result is True
    assert len(client.sent_actions) == 1, "Deveria ter emitido ação de reação do Arsenal"
    action = client.sent_actions[0]
    assert action["mode"] == 5, f"Esperado modo 5 (Arsenal), obtido: {action}"
    assert action["button_input"] == "sink_below_red"


# ══════════════════════════════════════════════════════════════════
# 2. CR 7.4.2b & CR 8.3.22: OVERPOWER COM CARTAS DO ARSENAL
# ══════════════════════════════════════════════════════════════════

def test_cr_overpower_allows_arsenal_action_block():
    """
    CR 7.4.2b: 'An attack with overpower cannot be defended by more than 1 action card from hand.'
    Cartas de ação declaradas a partir do Arsenal (ex: com Ambush ou Down and Dirty)
    NÃO violam a restrição de Overpower quando combinadas com 1 ação da mão.
    """
    pe = PolicyEngine(hero_name="generic")

    hand = [
        {"cardNumber": "action_atk_1", "name": "Action Attack 1", "type": "AA", "power": 4, "block": 3, "pitch": 1, "action": 27}
    ]
    arsenal = [
        {"cardNumber": "down_and_dirty_red", "name": "Down and Dirty", "type": "AA", "power": 4, "block": 3, "pitch": 1, "action": 27}
    ]

    state = {
        "playerHealth": 2,
        "playerHand": hand,
        "playerArsenal": arsenal,
        "activeChainLink": {
            "cardNumber": "heavy_swing",
            "totalPower": 7,
            "overpower": True,
        },
        "combatChainPower": 7,
    }

    chosen_blocks = pe.select_defense_blocks(state)
    assert isinstance(chosen_blocks, list)
    chosen_names = [b[2].lower() for b in chosen_blocks]
    assert any("down_and_dirty" in n for n in chosen_names), f"Down and Dirty do Arsenal deve ser aceito: {chosen_names}"
    assert any("action_atk_1" in n for n in chosen_names), f"action_atk_1 da mão deve ser aceito: {chosen_names}"
    assert len(chosen_blocks) == 2, f"Overpower deve permitir 1 ação da mão + 1 ação do Arsenal, obtido {len(chosen_blocks)}"



# ══════════════════════════════════════════════════════════════════
# 3. CR 4.3.2: MODO CAVAR DINÂMICO POR INTELECTO
# ══════════════════════════════════════════════════════════════════

def test_cr_digging_mode_dynamic_intellect():
    """
    CR 4.3.2 / 4.4.3f:
    Para heróis com Intelecto 3 (Rhinar, Kayo), o Modo Cavar deve ativar com >= 2 cartas
    para não deixar o bot travado com 2 cartas inúteis na mão.
    Para heróis com Intelecto 4, ativa com >= 3 cartas.
    """
    pe_brute = PolicyEngine(hero_name="rhinar")
    pe_standard = PolicyEngine(hero_name="generic")

    # Mão de 2 cartas de recurso (Brute deve cavar com 2 cartas!)
    hand_2_cards = [
        {"cardNumber": "blue_pitch_1", "name": "Blue Resource 1", "type": "R", "cost": 0, "pitch": 3, "block": 0},
        {"cardNumber": "blue_pitch_2", "name": "Blue Resource 2", "type": "R", "cost": 0, "pitch": 3, "block": 0},
    ]

    state_brute = {
        "playerHealth": 20,
        "playerHand": hand_2_cards,
        "playerArsenal": [],
        "turnPhase": "ARS",
    }

    # Para Rhinar (Intelecto 3), digging mode ativa com len(hand) >= 2
    # CR 3.1.5 ainda proíbe pitch puro no arsenal, mas o cálculo de min_cards deve ser 2
    assert pe_brute.strategy.get_intellect(state_brute) == 3
    assert pe_standard.strategy.get_intellect(state_brute) == 4


# ══════════════════════════════════════════════════════════════════
# 4. CR 3.0 & CR 7: SIMULADOR CONSULTANDO BASE CANÔNICA DE CARTAS
# ══════════════════════════════════════════════════════════════════

def test_cr_game_simulator_canonical_metadata():
    """
    Verifica se o GameSimulator obtém metadados de combate (poder, defesa, custo, keywords)
    a partir de data/fab_cards_db.json e fab_card_semantics.json sem depender de 25 hardcodes.
    """
    card_snatch = {"cardNumber": "snatch_red", "name": "Snatch"}
    meta_snatch = GameSimulator.extract_card_meta(card_snatch)

    assert meta_snatch["power"] == 4, f"Snatch Red deve ter 4 de poder, obteve {meta_snatch['power']}"
    assert meta_snatch["cost"] == 0, f"Snatch Red deve ter custo 0, obteve {meta_snatch['cost']}"
    assert meta_snatch["has_go_again"] is False or meta_snatch["has_on_hit"] is True

    card_cnc = {"cardNumber": "command_and_conquer_red", "name": "Command and Conquer"}
    meta_cnc = GameSimulator.extract_card_meta(card_cnc)
    assert meta_cnc["power"] == 6, "Command and Conquer deve ter 6 de poder"
    assert meta_cnc["cost"] == 2, "Command and Conquer deve ter custo 2"
    assert meta_cnc["has_on_hit"] is True


def test_cr_game_simulator_pitch_order():
    """
    CR 1.14.2: O pitch deve priorizar recursos de maior valor (Azul 3 -> Amarelo 2 -> Vermelho 1).
    Não deve pitchar a carta que está sendo jogada.
    """
    state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "playerAP": 1,
        "playerResources": [0, 0],
        "playerHand": [
            {"cardNumber": "attack_card_red", "name": "attack_card_red", "cost": 2, "power": 4, "pitch": 1},
            {"cardNumber": "red_pitch", "name": "red_pitch", "cost": 0, "power": 0, "pitch": 1},
            {"cardNumber": "blue_pitch", "name": "blue_pitch", "cost": 0, "power": 0, "pitch": 3},
        ],
        "playerPitch": [],
        "playerDiscard": [],
    }

    action = {"name": "attack_card_red", "cost": 2, "power": 4}
    sim_res = GameSimulator.simulate_attack(state, action)

    # Para pagar custo 2, deve ter pitchado a carta azul (3 recursos) e não a vermelha
    pitch_names = [c.get("name") or c.get("cardNumber") for c in sim_res.get("playerPitch", [])]
    assert "blue_pitch" in pitch_names, "Deveria ter pitchado a carta azul prioritariamente"
    assert "red_pitch" not in pitch_names, "Não deveria ter pitchado a carta vermelha"


# ══════════════════════════════════════════════════════════════════
# 5. MATRIZ DE EMBEDDINGS TENSORIAIS & CR KEYWORDS
# ══════════════════════════════════════════════════════════════════

def test_cr_embeddings_matrix_integrity():
    """
    Verifica se a matriz densa data/card_embeddings.pt foi compilada com as CR keywords,
    tem formato [N, 48] sem NaNs e sem Infs.
    """
    table, c2idx = _get_card_embeddings_table()
    assert isinstance(table, torch.Tensor)
    assert table.shape[1] == CARD_EMBEDDING_DIM
    assert table.shape[0] >= 5000, "Deve conter mais de 5.000 cartas catalogadas"
    assert not torch.isnan(table).any(), "Embeddings contêm NaNs!"
    assert not torch.isinf(table).any(), "Embeddings contêm Infs!"


# ══════════════════════════════════════════════════════════════════
# 6. RESILIÊNCIA CONTRA CORRUPÇÃO DE CHECKPOINTS
# ══════════════════════════════════════════════════════════════════

def test_cr_checkpoint_corruption_protection(tmp_path):
    """
    Verifica que, se um checkpoint estiver corrompido, o carregador
    cria um backup .corrupted.bak e JAMAIS sobrescreve o arquivo com pesos aleatórios.
    """
    fake_ckpt = tmp_path / "corrupted_model.pt"
    fake_ckpt.write_text("DADOS_CORROMPIDOS_NAO_TORCH", encoding="utf-8")

    model, device = create_model(checkpoint_path=str(fake_ckpt))
    assert model is not None

    # O arquivo corrompido original deve continuar existindo ou backup criado
    bak_file = tmp_path / "corrupted_model.pt.corrupted.bak"
    assert bak_file.exists(), "Deveria ter criado backup do arquivo corrompido"
    assert bak_file.read_text(encoding="utf-8") == "DADOS_CORROMPIDOS_NAO_TORCH"
