"""
tests/test_combat_rules_pruning.py
==================================
Testes unitários das regras e palavras-chave oficiais de combate do Flesh and Blood (Frente B):
  1. Phantasm Popping (CR 7.4.4)
  2. Dominate (CR 7.4.2a)
  3. Overpower (CR 7.4.2b)
  4. Piercing (CR 8.5.21)
  5. Intimidate (CR 8.5.8)
"""

import os
import sys
import pytest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ai.policy_engine import PolicyEngine
from ai.game_simulator import GameSimulator


# =====================================================================
# 1. Phantasm Popping (CR 7.4.4)
# =====================================================================

def test_phantasm_popping():
    """
    Phantasm (CR 7.4.4):
    Se o ataque oponente possui Phantasm (ex: Illusionist Herald),
    uma carta defensora não-ilusionista com 6+ de ataque (ex: Command & Conquer)
    estoura o ataque e fecha a cadeia com 0 dano sofrido.
    A IA deve priorizar essa carta e não queimar outros recursos.
    """
    pe = PolicyEngine(hero_name="generic")

    # Mão do jogador:
    # - Command & Conquer (Poder 6, Block 2) -> Popper perfeito de Phantasm
    # - Duas cartas defensivas comuns (Poder 0, Block 3)
    hand = [
        {"cardNumber": "command_and_conquer", "name": "Command and Conquer", "power": 6, "cost": 2, "pitch": 1, "block": 2},
        {"cardNumber": "blue_blocker_1", "name": "Blue Blocker 1", "power": 0, "cost": 0, "pitch": 3, "block": 3},
        {"cardNumber": "blue_blocker_2", "name": "Blue Blocker 2", "power": 0, "cost": 0, "pitch": 3, "block": 3},
    ]

    # Ataque de Ilusionista com Phantasm de 6 de poder
    state = {
        "playerHealth": 20,
        "playerHand": hand,
        "activeChainLink": {
            "cardNumber": "herald_of_protection",
            "totalPower": 6,
            "phantasm": True,
        },
        "combatChainPower": 6,
    }

    chosen_blocks = pe.select_defense_blocks(state)
    assert len(chosen_blocks) >= 1, "Deveria selecionar bloqueador para Phantasm"

    chosen_names = [b[2] for b in chosen_blocks]
    assert any("Command and Conquer" in n or "command_and_conquer" in n for n in chosen_names), (
        f"Esperava que Command & Conquer (6+ poder) estourasse Phantasm, obtido: {chosen_names}"
    )
    # Como o popper destrói o ataque e fecha a cadeia com 0 de dano, apenas ele deve ser usado
    assert len(chosen_blocks) == 1, f"Apenas 1 carta popper deveria defender, obtido: {len(chosen_blocks)}"


# =====================================================================
# 2. Dominate (CR 7.4.2a)
# =====================================================================

def test_dominate_restricts_hand_blocks_to_max_one():
    """
    Dominate (CR 7.4.2a):
    Se o ataque possuir Dominate, nenhuma combinação gerada pode conter mais de 1 carta da mão.
    Equipamentos não contam para este limite.
    """
    pe = PolicyEngine(hero_name="generic")

    # Mão com 3 cartas de block 3 e 1 equipamento
    hand = [
        {"cardNumber": "card1", "name": "Card 1", "power": 3, "cost": 1, "pitch": 1, "block": 3, "action": 27},
        {"cardNumber": "card2", "name": "Card 2", "power": 3, "cost": 1, "pitch": 2, "block": 3, "action": 27},
        {"cardNumber": "card3", "name": "Card 3", "power": 3, "cost": 1, "pitch": 3, "block": 3, "action": 27},
    ]
    equipment = [
        {"cardNumber": "ironrot_helm", "name": "Ironrot Helm", "slot": "head", "block": 1, "action": 3},
    ]

    # Ataque de 8 de dano com Dominate em vida crítica (4 HP)
    # Mesmo em modo sobrevivência, Dominate restringe estritamente a no máximo 1 da mão.
    state = {
        "playerHealth": 4,
        "playerHand": hand,
        "playerEquipment": equipment,
        "activeChainLink": {
            "cardNumber": "dominate_attack",
            "totalPower": 8,
            "dominate": True,
        },
        "combatChainPower": 8,
    }

    chosen_blocks = pe.select_defense_blocks(state)
    # Contar cartas de mão escolhidas (não-equipamento)
    hand_blocks = [b for b in chosen_blocks if b[3] != 3 and "ironrot" not in b[2].lower()]
    assert len(hand_blocks) <= 1, f"Dominate permite no máximo 1 carta da mão, obtido: {len(hand_blocks)}"


# =====================================================================
# 3. Overpower (CR 7.4.2b)
# =====================================================================

def test_overpower_restricts_action_cards_to_max_one():
    """
    Overpower (CR 7.4.2b):
    Se o ataque possuir Overpower, nenhuma combinação de bloqueadores gerada pode
    conter mais de 1 carta de ação (Action card).
    Cartas como Defense Reactions e Equipamentos não contam para essa restrição.
    """
    pe = PolicyEngine(hero_name="generic")

    # Mão com 2 cartas Attack Action e 1 Defense Reaction
    hand = [
        {"cardNumber": "action_atk_1", "name": "Action Attack 1", "type": "AA", "power": 4, "block": 3, "pitch": 1, "action": 27},
        {"cardNumber": "action_atk_2", "name": "Action Attack 2", "type": "AA", "power": 4, "block": 3, "pitch": 1, "action": 27},
        {"cardNumber": "sink_below_red", "name": "Sink Below", "type": "DR", "power": 0, "block": 4, "pitch": 1, "action": 27},
    ]
    equipment = [
        {"cardNumber": "ironrot_legs", "name": "Ironrot Legs", "slot": "legs", "block": 1, "action": 3},
    ]

    state = {
        "playerHealth": 6,
        "playerHand": hand,
        "playerEquipment": equipment,
        "activeChainLink": {
            "cardNumber": "overpower_slam",
            "totalPower": 9,
            "overpower": True,
        },
        "combatChainPower": 9,
    }

    chosen_blocks = pe.select_defense_blocks(state)
    # Identificar quantas cartas de ação foram escolhidas
    action_blocks = [b for b in chosen_blocks if "action_atk" in b[2].lower()]
    assert len(action_blocks) <= 1, f"Overpower permite no máximo 1 carta de ação, obtido: {len(action_blocks)}"


# =====================================================================
# 4. Piercing (CR 8.5.21)
# =====================================================================

def test_piercing_penalizes_pure_ineffective_armor():
    """
    Piercing (CR 8.5.21):
    Ataques com Piercing ganham +1 de dano se forem bloqueados por equipamento.
    Penalizar e rejeitar bloqueios puramente com armaduras em ataques com Piercing que não evitem dano real
    (ex: armadura com block 1 concede +1 de poder ao oponente, gerando 0 mitigação líquida).
    """
    pe = PolicyEngine(hero_name="generic")

    equipment = [
        {"cardNumber": "ironrot_helm", "name": "Ironrot Helm", "slot": "head", "block": 1, "action": 3},
    ]
    hand = [
        {"cardNumber": "red_attack_keep", "name": "Red Attack Keep", "power": 5, "block": 2, "pitch": 1},
    ]

    # Ataque com Piercing de 4 de dano
    state = {
        "playerHealth": 20,
        "playerHand": hand,
        "playerEquipment": equipment,
        "activeChainLink": {
            "cardNumber": "piercing_shadow_vise_red",
            "totalPower": 4,
            "piercing": True,
        },
        "combatChainPower": 4,
    }

    chosen_blocks = pe.select_defense_blocks(state)
    # Não deve queimar armadura inutilmente contra Piercing quando a mitigação líquida é zero
    armor_chosen = [b for b in chosen_blocks if "ironrot" in b[2].lower() or b[3] == 3]
    assert len(armor_chosen) == 0, f"Armadura ineficaz contra Piercing não deve ser gasta, obtido: {armor_chosen}"


# =====================================================================
# 5. Intimidate (CR 8.5.8) no GameSimulator
# =====================================================================

def test_intimidate_reduces_opponent_hand_in_simulator():
    """
    Intimidate (CR 8.5.8):
    Quando o ataque possui Intimidate, desconta da mão do defensor (opp_hand_count)
    o número de cartas intimidadas (min 0) ao calcular probabilidades de bloqueio.
    """
    state = {
        "playerHealth": 20,
        "opponentHealth": 20,
        "opponentHandCount": 4,
        "playerResources": [2, 0],
        "playerAP": 1,
        "playerHand": [],
    }

    # Ataque comum de 6 sem intimidate
    normal_action = {"name": "heavy_swing", "power": 6, "cost": 0, "has_go_again": False}
    st_normal = GameSimulator.simulate_attack(state, normal_action)

    # Ataque de 6 COM intimidate: 2 (ex: Pack Hunt / Barraging Beatdown)
    intimidate_action = {"name": "pack_hunt", "power": 6, "cost": 0, "has_go_again": False, "intimidate": 2}
    st_intimidate = GameSimulator.simulate_attack(state, intimidate_action)

    # Sob intimidate, o oponente tem 2 cartas a menos para defender,
    # gerando bloqueio esperado menor e mais dano não bloqueado (vida final menor)!
    assert st_intimidate["opponentHealth"] < st_normal["opponentHealth"], (
        f"Ataque com Intimidate deveria causar mais dano: "
        f"Intimidate HP={st_intimidate['opponentHealth']} vs Normal HP={st_normal['opponentHealth']}"
    )
    # Mão restante do oponente deve ser menor após o combate
    assert st_intimidate["opponentHandCount"] < st_normal["opponentHandCount"]


# =====================================================================
# 6. Overpower com Ação no Arsenal (CR 7.4.2b, CR 8.3.22)
# =====================================================================

def test_overpower_allows_action_from_arsenal_with_action_from_hand():
    """
    Overpower (CR 7.4.2b, CR 8.3.22):
    "This can't be defended by more than one action card from hand".
    Cartas defendidas do Arsenal (com Ambush / Down and Dirty) são cartas de ação,
    mas NÃO vêm da mão (is_hand=False, is_arsenal=True).
    Portanto, defender com 1 ação da mão + 1 ação do Arsenal é 100% legal sob Overpower!
    """
    pe = PolicyEngine(hero_name="generic")

    # Mão com 1 Attack Action e Arsenal com 1 Attack Action com Ambush (Down and Dirty)
    hand = [
        {"cardNumber": "action_atk_1", "name": "Action Attack 1", "type": "AA", "power": 4, "block": 3, "pitch": 1, "action": 27},
    ]
    arsenal = [
        {"cardNumber": "down_and_dirty_red", "name": "Down and Dirty", "type": "AA", "power": 4, "block": 3, "pitch": 1, "action": 27},
    ]

    state = {
        "playerHealth": 2,
        "playerHand": hand,
        "playerArsenal": arsenal,
        "activeChainLink": {
            "cardNumber": "overpower_slam",
            "totalPower": 7,
            "overpower": True,
        },
        "combatChainPower": 7,
    }

    chosen_blocks = pe.select_defense_blocks(state)
    chosen_names = [b[2].lower() for b in chosen_blocks]
    assert any("down_and_dirty" in n for n in chosen_names), f"Esperado Down and Dirty do Arsenal, obtido: {chosen_names}"
    assert any("action_atk_1" in n for n in chosen_names), f"Esperado action_atk_1 da mão, obtido: {chosen_names}"
    assert len(chosen_blocks) == 2, f"Overpower deve permitir 1 ação da mão + 1 ação do Arsenal, obtido {len(chosen_blocks)}"


# =====================================================================
# 7. Arsenal em Fase de Reação e Dominate (CR 7.4.2a, CR 7.4.2d, CR 7.5b, CR 8.3.4b)
# =====================================================================

from ai.bot_runtime.phase_decider import handle_reaction_phase

class MockReactionClient:
    def __init__(self, player_id=1, hero_name="generic"):
        self.player_id = player_id
        self.hero_name = hero_name
        self.policy_engine = PolicyEngine(hero_name=hero_name)
        self.blocks_declared_count = 0
        self.reaction_attempts = {}
        self.last_attempted_play = None
        self.last_logged_combat_attack = None
        self.sent_actions = []
        self.chat_logs = []
        self.logs = []

    def log(self, msg):
        self.logs.append(msg)

    def send_chat_log(self, msg, **kwargs):
        self.chat_logs.append(msg)

    def send_action(self, **kwargs):
        self.sent_actions.append(kwargs)

    def get_combat_chain_desc(self, state):
        return "Dominate Attack (Power: 6)"


def test_reaction_phase_dominate_prohibits_hand_dr_when_hand_defended():
    """
    Dominate (CR 7.4.2a, CR 8.3.4b):
    Se o ataque possui Dominate e o defensor já declarou defesa com carta da mão
    (blocks_declared_count >= 1), jogar Defense Reaction da mão é ILEGAL.
    """
    client = MockReactionClient(player_id=1)
    client.blocks_declared_count = 1

    state = {
        "turnPlayer": 2,
        "playerHealth": 10,
        "playerHand": [
            {"cardNumber": "sink_below_red", "type": "DR", "cost": 0, "action": 27}
        ],
        "playerArsenal": [],
        "playerEquipment": [],
        "activeChainLink": {
            "cardNumber": "heavy_dominate_attack",
            "dominate": True,
            "totalPower": 6,
        },
    }

    unpayable = set()
    result = handle_reaction_phase(client, state, turn_num=1, turn_phase="D", prompt_buttons=[{"caption": "Pass", "mode": 99}], unpayable_set=unpayable)
    assert result is True
    assert len(client.sent_actions) == 1
    assert client.sent_actions[0]["mode"] == 99, f"Deveria ter passado prioridade sob Dominate, mas enviou: {client.sent_actions[0]}"


def test_reaction_phase_dominate_allows_arsenal_dr():
    """
    Arsenal em Fase de Reação sob Dominate (CR 7.4.2d, CR 7.5b, CR 8.3.4b):
    Mesmo que o jogador já tenha defendido com 1 carta da mão no Defend Step (blocks_declared_count >= 1),
    jogar uma Defense Reaction do Arsenal é 100% legal sob Dominate, pois a carta NÃO veio da mão!
    """
    client = MockReactionClient(player_id=1)
    client.blocks_declared_count = 1

    state = {
        "turnPlayer": 2,
        "playerHealth": 10,
        "playerHand": [],
        "playerArsenal": [
            {"cardNumber": "sink_below_red", "type": "DR", "cost": 0, "action": 5, "actionDataOverride": "0"}
        ],
        "playerEquipment": [],
        "activeChainLink": {
            "cardNumber": "heavy_dominate_attack",
            "dominate": True,
            "totalPower": 6,
        },
    }

    unpayable = set()
    result = handle_reaction_phase(client, state, turn_num=1, turn_phase="D", prompt_buttons=[], unpayable_set=unpayable)
    assert result is True
    assert len(client.sent_actions) == 1
    action = client.sent_actions[0]
    assert action["mode"] == 5, f"Esperado modo 5 (jogar do Arsenal), obtido: {action}"
    assert action["card_id"] == "0", f"Esperado slot 0 do Arsenal, obtido: {action}"
    assert action["button_input"] == "sink_below_red"


def test_reaction_phase_dominate_allows_hand_dr_if_no_hand_defended():
    """
    Dominate (CR 7.4.2a, CR 8.3.4b):
    Se nenhuma carta da mão defendeu ainda (blocks_declared_count == 0),
    jogar Defense Reaction da mão é permitido (será a única carta da mão a defender).
    """
    client = MockReactionClient(player_id=1)
    client.blocks_declared_count = 0

    state = {
        "turnPlayer": 2,
        "playerHealth": 10,
        "playerHand": [
            {"cardNumber": "sink_below_red", "type": "DR", "cost": 0, "action": 27}
        ],
        "playerArsenal": [],
        "playerEquipment": [],
        "activeChainLink": {
            "cardNumber": "heavy_dominate_attack",
            "dominate": True,
            "totalPower": 6,
        },
    }

    unpayable = set()
    result = handle_reaction_phase(client, state, turn_num=1, turn_phase="D", prompt_buttons=[], unpayable_set=unpayable)
    assert result is True
    assert len(client.sent_actions) == 1
    action = client.sent_actions[0]
    assert action["mode"] == 27, f"Deveria jogar Sink Below da mão se nenhuma defendeu ainda, obtido: {action}"
    assert action["button_input"] == "sink_below_red"


def test_reaction_phase_dominate_prohibits_hand_dr_when_combat_chain_has_hand_card():
    """
    Dominate (CR 7.4.2a, CR 8.3.4b):
    Mesmo com blocks_declared_count == 0, se a combat chain já contém carta defensora da mão,
    a Defense Reaction da mão é bloqueada pelo Dominate.
    """
    client = MockReactionClient(player_id=1)
    client.blocks_declared_count = 0

    state = {
        "turnPlayer": 2,
        "playerHealth": 10,
        "playerHand": [
            {"cardNumber": "sink_below_red", "type": "DR", "cost": 0, "action": 27}
        ],
        "combatChain": [
            {"cardNumber": "heavy_dominate_attack", "controller": 2},
            {"cardNumber": "regular_hand_blocker", "controller": 1}
        ],
        "playerArsenal": [],
        "playerEquipment": [],
        "activeChainLink": {
            "cardNumber": "heavy_dominate_attack",
            "dominate": True,
            "totalPower": 6,
        },
    }

    unpayable = set()
    result = handle_reaction_phase(client, state, turn_num=1, turn_phase="D", prompt_buttons=[{"caption": "Pass", "mode": 99}], unpayable_set=unpayable)
    assert result is True
    assert len(client.sent_actions) == 1
    assert client.sent_actions[0]["mode"] == 99, f"Deveria ter passado prioridade, obtido: {client.sent_actions[0]}"

