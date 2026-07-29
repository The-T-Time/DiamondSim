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

        build_header(self, result, on_save=self._save_run)
        build_notebook(self, result)

    def _save_run(self) -> None:
        save_current_run(self, self._result)
