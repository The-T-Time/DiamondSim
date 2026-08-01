# ==============================================================================
# RESULTS WINDOW
# gui/results_window/window.py
#
# The toplevel window (CTkToplevel) that orchestrates the header/save/
# notebook pieces built in sibling modules (header.py, save.py,
# notebook.py).
# ==============================================================================

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from config import RESULTS_WINDOW_SIZE
from models.simulation_result import SimulationResult
from gui.results_window.header import build_header, window_title
from gui.results_window.notebook import build_notebook
from gui.results_window.save import save_current_run


class ResultsWindow(ctk.CTkToplevel):
    def __init__(self, parent: tk.Widget, result: SimulationResult) -> None:
        super().__init__(parent)
        self._result = result
        self.title(window_title(result))
        self.geometry(RESULTS_WINDOW_SIZE)
        self.minsize(900, 620)

        #Every tab (including Standings, whose division panels measure
        #self.winfo_toplevel().winfo_width() to decide how many fit
        #side-by-side) is built eagerly right here, before this window
        #has ever been mapped to the screen. Without this, winfo_width()
        #still reports Tk's pre-geometry default (effectively 1px) rather
        #than the size just requested above, which made the Standings
        #tab's division-panel layout collapse to one per row on first
        #open (it self-corrected on any later re-render, e.g. switching
        #AL/NL, because by then a geometry pass had already happened via
        #normal event handling). update_idletasks() forces Tk to process
        #the pending geometry request synchronously, so every tab built
        #below sees the real window size immediately.
        self.update_idletasks()

        build_header(self, result, on_save=self._save_run)
        build_notebook(self, result)

    def _save_run(self) -> None:
        save_current_run(self, self._result)
