"""
FaB Talishar AI - Bot Runtime Package
Módulos decompostos para execução, tomadas de decisão e ciclo de vida do bot em partidas.
"""

def __getattr__(name: str):
    if name == "FabBotClient":
        from ai.bot_runtime.client import FabBotClient
        return FabBotClient
    if name in ("choice_handler", "phase_decider", "lobby_manager", "match_tracker", "client"):
        import importlib
        return importlib.import_module(f"ai.bot_runtime.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["FabBotClient", "choice_handler", "phase_decider", "lobby_manager", "match_tracker", "client"]
