"""
ui/tabs/__init__.py - Exportação das funções de renderização das abas do Dashboard.
"""

from ui.tabs.tab_play import render_tab_play
from ui.tabs.tab_arena import render_tab_arena
from ui.tabs.tab_training import render_tab_training
from ui.tabs.tab_tournaments import render_tab_tournaments
from ui.tabs.tab_decks import render_tab_decks
from ui.tabs.tab_analytics import render_tab_analytics
from ui.tabs.tab_ismcts import render_tab_ismcts

__all__ = [
    "render_tab_play",
    "render_tab_arena",
    "render_tab_training",
    "render_tab_tournaments",
    "render_tab_decks",
    "render_tab_analytics",
    "render_tab_ismcts",
]
