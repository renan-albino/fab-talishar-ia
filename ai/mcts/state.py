"""
ai/mcts/state.py
================
Representação imutável do estado do jogo (Game State).
Garante que o estado não seja mutado acidentalmente durante rollouts do MCTS.
"""

from collections.abc import Mapping
from typing import Any, Iterator

def _freeze_value(v: Any) -> Any:
    """Converte estruturas mutáveis para imutáveis recursivamente."""
    if isinstance(v, dict):
        return ImmutableGameState(v)
    elif isinstance(v, list):
        return tuple(_freeze_value(x) for x in v)
    elif isinstance(v, set):
        return frozenset(_freeze_value(x) for x in v)
    return v

class ImmutableGameState(Mapping):
    """
    Representação imutável do Game State.
    """
    __slots__ = ("_data", "_hash")

    def __init__(self, data: Mapping[str, Any]):
        if isinstance(data, ImmutableGameState):
            self._data = data._data
        else:
            self._data = {k: _freeze_value(v) for k, v in data.items()}
        self._hash = None

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def copy(self):
        return self

    def replace(self, **kwargs) -> "ImmutableGameState":
        """
        Retorna uma nova instância com os campos atualizados (imutável).
        """
        new_data = dict(self._data)
        for k, v in kwargs.items():
            new_data[k] = v
        return ImmutableGameState(new_data)

    def without(self, *keys) -> "ImmutableGameState":
        """
        Retorna uma nova instância sem as chaves especificadas.
        """
        new_data = dict(self._data)
        for k in keys:
            new_data.pop(k, None)
        return ImmutableGameState(new_data)

    def __hash__(self):
        if self._hash is None:
            self._hash = hash(frozenset(self._data.items()))
        return self._hash

    def __eq__(self, other):
        if not isinstance(other, ImmutableGameState):
            return False
        return self._data == other._data

    def to_dict(self) -> dict:
        """Converte recursivamente para dicionário normal."""
        def _unfreeze(v: Any) -> Any:
            if isinstance(v, ImmutableGameState):
                return v.to_dict()
            elif isinstance(v, tuple):
                return list(_unfreeze(x) for x in v)
            elif isinstance(v, frozenset):
                return set(_unfreeze(x) for x in v)
            return v
        return {k: _unfreeze(v) for k, v in self._data.items()}
