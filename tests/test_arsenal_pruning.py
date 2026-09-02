import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai.policy_engine import PolicyEngine
from ai.hero_strategies import RangerStrategy

def run_tests():
    engine = PolicyEngine(hero_name='marlinn')
    assert isinstance(engine.strategy, RangerStrategy), f'Estratégia esperada: RangerStrategy, obtida: {type(engine.strategy)}'

    # Caso 1: Mão apenas com recurso/gema (Riches of Tropal Dhani)
    state1 = {'playerHand': [{'cardNumber': 'riches_of_tropal_dhani_yellow', 'actionDataOverride': '1'}]}
    res1 = engine.select_arsenal_card(state1)
    print('Caso 1 (Apenas Riches of Tropal Dhani):', res1)
    assert res1 is None, f'Deveria ser None mas foi {res1}'

    # Caso 2: Mão com flecha e recurso
    state2 = {'playerHand': [
        {'cardNumber': 'riches_of_tropal_dhani_yellow', 'actionDataOverride': '1'},
        {'cardNumber': 'endless_arrow_red', 'actionDataOverride': '2'}
    ]}
    res2 = engine.select_arsenal_card(state2)
    print('Caso 2 (Flecha + Riches):', res2)
    assert res2 is not None and res2[0] == 'endless_arrow_red', f'Deveria ser endless_arrow_red mas foi {res2}'

    # Caso 3: Mão apenas com gemas lendárias (Heart of Fyendal, Eye of Ophidia)
    state3 = {'playerHand': [
        {'cardNumber': 'heart_of_fyendal_blue', 'actionDataOverride': '10'},
        {'cardNumber': 'eye_of_ophidia_blue', 'actionDataOverride': '11'}
    ]}
    res3 = engine.select_arsenal_card(state3)
    print('Caso 3 (Gemas Lendárias):', res3)
    assert res3 is None, f'Deveria ser None mas foi {res3}'

    # Caso 4: Mão com flecha vermelha e buff
    state4 = {'playerHand': [
        {'cardNumber': 'three_of_a_kind_red', 'actionDataOverride': '20'},
        {'cardNumber': 'king_kraken_harpoon_red', 'actionDataOverride': '21'}
    ]}
    res4 = engine.select_arsenal_card(state4)
    print('Caso 4 (Flecha vs Buff):', res4)
    assert res4 is not None and res4[0] == 'king_kraken_harpoon_red', f'Esperado flecha, obtido {res4}'

    # Caso 5: Down and Dirty (exceção com vantagem no Arsenal)
    state5 = {'playerHand': [
        {'cardNumber': 'autumns_touch_blue', 'block': 3, 'power': 3, 'pitch': 3},
        {'cardNumber': 'down_and_dirty_red', 'block': 3, 'power': 4, 'pitch': 1, 'actionDataOverride': '50'}
    ]}
    res5 = engine.select_arsenal_card(state5)
    print('Caso 5 (Down and Dirty):', res5)
    assert res5 is not None and res5[0] == 'down_and_dirty_red', f'Esperado down_and_dirty_red, obtido {res5}'

    # Caso 6: Ambush (Stadium Security)
    state6 = {'playerHand': [
        {'cardNumber': 'autumns_touch_blue', 'block': 3, 'power': 3, 'pitch': 3},
        {'cardNumber': 'stadium_security_red', 'block': 3, 'power': 0, 'pitch': 1, 'subtype': 'ambush', 'actionDataOverride': '60'}
    ]}
    res6 = engine.select_arsenal_card(state6)
    print('Caso 6 (Ambush):', res6)
    assert res6 is not None and res6[0] == 'stadium_security_red', f'Esperado stadium_security_red, obtido {res6}'

    # Caso 7: Defesa a partir do Arsenal com Down and Dirty
    state7 = {
        'playerHealth': 20,
        'playerHand': [{'cardNumber': 'card_in_hand', 'block': 2, 'pitch': 1, 'power': 3}],
        'playerArsenal': [{'cardNumber': 'down_and_dirty_red', 'block': 3, 'pitch': 1, 'power': 4, 'action': 27}],
        'activeChainLink': {'totalPower': 4, 'cardNumber': 'enemy_attack'}
    }
    blocks7 = engine.select_defense_blocks(state7)
    print('Caso 7 (Defesa Arsenal com Down and Dirty):', blocks7)
    assert any(b[2] == 'down_and_dirty_red' for b in blocks7), f'Deveria defender com Down and Dirty do Arsenal'

    # Caso 8: Mão com 4 recursos azuis (Cavar / Digging Mode)
    state8 = {'playerHand': [
        {'cardNumber': 'autumns_touch_blue', 'block': 3, 'power': 3, 'pitch': 3, 'type': 'AA', 'actionDataOverride': '80'},
        {'cardNumber': 'fruits_of_the_forest_blue', 'block': 3, 'power': 2, 'pitch': 3, 'type': 'AA'},
        {'cardNumber': 'blue_res_blue', 'block': 3, 'power': 1, 'pitch': 3, 'type': 'AA'},
        {'cardNumber': 'blue_weak_blue', 'block': 3, 'power': 0, 'pitch': 3, 'type': 'AA'},
    ]}
    res8 = engine.select_arsenal_card(state8)
    print('Caso 8 (Cavar com 4 recursos):', res8)
    assert res8 is not None and res8[0] == 'autumns_touch_blue', f'Esperado autumns_touch_blue para cavar, obtido {res8}'

    # Caso 9: Mão com 3 recursos (ação vs gema pura lendária)
    state9 = {'playerHand': [
        {'cardNumber': 'fruits_of_the_forest_blue', 'block': 3, 'power': 2, 'pitch': 3, 'type': 'AA', 'actionDataOverride': '90'},
        {'cardNumber': 'blue_res_blue', 'block': 3, 'power': 1, 'pitch': 3, 'type': 'AA'},
        {'cardNumber': 'heart_of_fyendal_blue', 'block': 0, 'power': 0, 'pitch': 3, 'type': 'R'},
    ]}
    res9 = engine.select_arsenal_card(state9)
    print('Caso 9 (Cavar com 3 recursos, ação vs gema):', res9)
    assert res9 is not None and res9[0] == 'fruits_of_the_forest_blue', f'Deveria preferir ação a gema para cavar, obtido {res9}'

    # Caso 10: Mão com 2 recursos (NÃO cavar, manter na mão para pitch)
    state10 = {'playerHand': [
        {'cardNumber': 'fruits_of_the_forest_blue', 'block': 3, 'power': 2, 'pitch': 3},
        {'cardNumber': 'blue_res_blue', 'block': 3, 'power': 1, 'pitch': 3},
    ]}
    res10 = engine.select_arsenal_card(state10)
    print('Caso 10 (2 recursos residuais -> manter na mão):', res10)
    assert res10 is None, f'Com 2 recursos na mão deveria retornar None, obtido {res10}'

    print('>>> TODOS OS TESTES DE PODA DE ARSENAL, AMBUSH E CAVAR PASSARAM COM SUCESSO! <<<')

if __name__ == '__main__':
    run_tests()
