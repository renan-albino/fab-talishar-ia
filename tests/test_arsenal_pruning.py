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

    print('>>> TODOS OS TESTES DE PODA DE ARSENAL E RANGER PASSARAM COM SUCESSO! <<<')

if __name__ == '__main__':
    run_tests()
