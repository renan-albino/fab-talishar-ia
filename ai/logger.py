"""
ai/logger.py
============
Logger centralizado do FAB AI Engine.

Todos os módulos devem usar este logger em vez de print() ou except-pass silencioso.
Formato padronizado com timestamp, nível e módulo de origem.
"""

import logging
import os
import sys


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Retorna um logger configurado com formato padronizado."""
    logger = logging.getLogger(f"fab_ai.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(level)
        logger.propagate = False
    return logger
