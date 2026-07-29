# ==============================================================================
# DASHBOARD TAB
# gui/dashboard_tab/tab.py
#
# The first screen after a run: World Series Favorites (top clubs by
# championship odds, or playoff odds if postseason wasn't simulated) plus
# a run summary. Pure view — everything reads straight off
# SimulationResult, nothing recomputes odds.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from models.simulation_result import SimulationResult
from gui.widgets import C_BG, make_header_bar
from gui.dashboard_tab.favorites_panel import build_favorites_panel
from gui.dashboard_tab.summary_panel import build_summary_panel


class DashboardTab(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, result: SimulationResult) -> None:
        super().__init__(parent, fg_color=C_BG, corner_radius=0)
        self._result = result
        self._build()

    def _build(self) -> None:
        r = self._result
        make_header_bar(
            self, 'Dashboard',
            subtitle=f"{r.season} {'Backtest' if r.mode == 'backtest' else 'Projection'}"
                     f"  ·  {r.num_sims:,} simulations",
        )

        body = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        body.pack(fill='both', expand=True, padx=12, pady=12)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        build_favorites_panel(body, r)
        build_summary_panel(body, r)
