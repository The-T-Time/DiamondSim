# ==============================================================================
# RESULTS WINDOW HEADER
# gui/results_window/header.py
#
# Builds the title/meta/save-button header bar at the top of a
# ResultsWindow.
# ==============================================================================

from __future__ import annotations

from typing import Callable

import tkinter as tk

import customtkinter as ctk

from config import APP_NAME
from models.simulation_result import SimulationResult
from gui.widgets import C_GRAY, C_GREEN, C_HEADER_BAR, C_HEADER_TEXT, FONT_HEADER, FONT_SMALL, FONT_SMALL_BOLD


def window_title(result: SimulationResult) -> str:
    """The ResultsWindow title for `result` — a backtest shows its
    snapshot date, a live projection doesn't."""
    if result.mode == 'backtest':
        return f"{APP_NAME} — {result.season} Backtest  (snapshot: {result.snapshot_date})"
    return f"{APP_NAME} — {result.season} Season Projection"


def build_header(parent: tk.Widget, result: SimulationResult, on_save: Callable[[], None]) -> None:
    """Packs the title bar (title, meta summary, Save run button) into `parent`."""
    title = window_title(result)

    hdr = ctk.CTkFrame(parent, fg_color=C_HEADER_BAR, corner_radius=0)
    hdr.pack(fill='x')
    ctk.CTkLabel(hdr, text=title, fg_color=C_HEADER_BAR, text_color=C_HEADER_TEXT,
                font=FONT_HEADER).pack(side='left', padx=14, pady=6)
    ctk.CTkButton(hdr, text='💾  Save run', font=FONT_SMALL_BOLD,
                 fg_color=C_GREEN, text_color=C_HEADER_TEXT, hover_color='#2ecc71',
                 cursor='hand2', width=130,
                 command=on_save).pack(side='right', padx=14, pady=6)

    meta = (f"{result.num_sims:,} simulations  ·  "
            f"{len(result.played_games)} games played  ·  "
            f"{len(result.unplayed_games)} remaining  ·  "
            f"seed {result.cfg.random_seed}")
    ctk.CTkLabel(hdr, text=meta, fg_color=C_HEADER_BAR, text_color=C_GRAY,
                font=FONT_SMALL).pack(side='right', padx=14, pady=6)
