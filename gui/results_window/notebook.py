# ==============================================================================
# RESULTS WINDOW — NOTEBOOK
# gui/results_window/notebook.py
#
# Builds the tabbed view (Dashboard / Graphs / Teams / Standings /
# Statistics / Players / Bracket) inside a ResultsWindow, using
# CTkTabview.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from models.simulation_result import SimulationResult
from gui.widgets import C_BG
from gui.dashboard_tab import DashboardTab
from gui.graph_tab import GraphTab
from gui.teams_tab import TeamsTab
from gui.standings_tab import StandingsTab
from gui.stats_tab import StatsTab
from gui.player_tab import PlayerTab
from gui.bracket_tab import BracketTab

#(tab class, tab label) — order here is the tab order shown to the user.
#The label doubles as CTkTabview's internal tab name, so it must be unique.
_TABS = [
    (DashboardTab, '🏠  Dashboard'),
    (GraphTab,     '📊  Graphs'),
    (TeamsTab,     '🏟  Teams'),
    (StandingsTab, '📋  Standings'),
    (StatsTab,     '📈  Statistics'),
    (PlayerTab,    '🧢  Players'),
    (BracketTab,   '🏆  Bracket'),
]


def build_notebook(parent: tk.Widget, result: SimulationResult) -> ctk.CTkTabview:
    """Builds and packs the tabbed view into `parent`, with one tab per
    entry in _TABS, each constructed with `result`. Returns the CTkTabview
    widget in case a caller wants to select a specific tab afterward."""
    tabview = ctk.CTkTabview(parent, fg_color=C_BG)
    tabview.pack(fill='both', expand=True, padx=6, pady=6)

    for tab_class, label in _TABS:
        container = tabview.add(label)
        frame = tab_class(container, result)
        frame.pack(fill='both', expand=True)

    tabview.set(_TABS[0][1])
    return tabview
