"""
ai/common/converters.py
=======================
Utilitários universais de conversão segura e tolerante a falhas para payloads
do Talishar (serializados em PHP / Apache), prevenindo exceções de tipo (NoneType,
TypeError, ValueError, KeyError) e garantindo robustez na execução da IA.
"""

import math
from typing import Any, List, Dict


def safe_int(val: Any, default: int = 0) -> int:
    """
    Converte com segurança strings, None, floats ou valores anômalos ('NaN', 'null', None, etc.)
    para int sem lançar TypeError ou ValueError.
    """
    if val is None:
        return default
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return default
        return int(val)
    if isinstance(val, str):
        cleaned = val.strip().lower()
        if not cleaned or cleaned in ("none", "null", "nan", "inf", "-inf", "undefined"):
            return default
        try:
            return int(cleaned)
        except ValueError:
            try:
                f = float(cleaned)
                if math.isnan(f) or math.isinf(f):
                    return default
                return int(f)
            except (ValueError, OverflowError):
                return default
    try:
        f = float(val)
        if math.isnan(f) or math.isinf(f):
            return default
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return default


def safe_list(val: Any) -> List[Any]:
    """
    Garante que se val for None ou não-iterável retorne lista vazia [].
    Strings, bytes, dicts, números e booleanos são tratados como não-listas.
    Essencial para evitar `NoneType has no len()` em `playerHand`, `buttons`, etc.
    """
    if val is None:
        return []
    if isinstance(val, list):
        return val
    if isinstance(val, (tuple, set)):
        return list(val)
    if isinstance(val, (str, bytes, bytearray, dict, int, float, bool)):
        return []
    try:
        return list(val)
    except (TypeError, ValueError):
        return []


def safe_dict(val: Any) -> Dict[Any, Any]:
    """
    Garante que se val for None ou não for dicionário retorne `{}`.
    """
    if val is None:
        return {}
    if isinstance(val, dict):
        return val
    return {}


def safe_str(val: Any, default: str = "") -> str:
    """
    Garante retorno de string limpa sem lançar exceções.
    """
    if val is None:
        return default
    if isinstance(val, str):
        return val
    try:
        return str(val)
    except Exception:
        return default
