# ==============================================================================
# GRAPH TAB
# gui/graph_tab/tab.py
#
# Sortable bar charts of playoff odds (button-row/resize logic live in
# sibling modules view_switcher.py/resize.py). The matplotlib canvas
# stays classic tkinter — matplotlib's Tk backend embeds into a genuine
# tkinter widget, which a CTkFrame still is under the hood.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from charts.charts import build_simulation_figures, build_backtest_figures
from models.simulation_result import SimulationResult
from gui.graph_tab.resize import fit_figure_to_frame
from gui.graph_tab.view_switcher import build_view_buttons, highlight_active_button
from gui.widgets import C_BG


class GraphTab(ctk.CTkFrame):
    _SIM_LABELS  = ['Overall Odds', 'By Division']
    _BACK_LABELS = ['Predicted Odds', 'Accuracy Breakdown']

    def __init__(self, parent: tk.Widget, result: SimulationResult) -> None:
        super().__init__(parent, fg_color=C_BG, corner_radius=0)
        self._result    = result
        self._figures: list[Figure] = []
        self._canvas: FigureCanvasTkAgg | None    = None
        self._toolbar: NavigationToolbar2Tk | None = None
        self._buttons: list[ctk.CTkButton]           = []
        self._current   = 0
        self._resize_id: str | None = None

        labels = self._BACK_LABELS if result.mode == 'backtest' else self._SIM_LABELS
        self._build(labels)

    #── layout ────────────────────────────────────────────────────────────────

    def _build(self, labels: list[str]) -> None:
        self._buttons = build_view_buttons(self, labels, on_select=self._switch)

        #Plain tk.Frame here, not CTkFrame: matplotlib's FigureCanvasTkAgg
        #is dropped directly into this frame in _render, and there's no
        #benefit to CTk's rounded-corner rendering on a frame that's
        #entirely covered by a chart canvas anyway.
        self._canvas_frame = tk.Frame(self, bg=C_BG)
        self._canvas_frame.pack(fill='both', expand=True)
        self._canvas_frame.bind('<Configure>', self._on_resize)

        self.after(50, self._load_figures)

    #── figure loading ────────────────────────────────────────────────────────

    def _load_figures(self) -> None:
        self._figures = (build_backtest_figures(self._result)
                         if self._result.mode == 'backtest'
                         else build_simulation_figures(self._result))
        self._switch(0)

    #── switching ─────────────────────────────────────────────────────────────

    def _switch(self, idx: int) -> None:
        if not self._figures:
            return
        self._current = idx
        highlight_active_button(self._buttons, idx, inactive_bg=self._canvas_frame.cget('bg'))
        self._render(self._figures[idx])

    def _render(self, fig: Figure) -> None:
        for w in self._canvas_frame.winfo_children():
            w.destroy()
        self._canvas = self._toolbar = None

        fit_figure_to_frame(fig, self._canvas_frame)

        toolbar_frame = tk.Frame(self._canvas_frame, bg=C_BG)
        toolbar_frame.pack(side='bottom', fill='x')

        canvas = FigureCanvasTkAgg(fig, master=self._canvas_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill='both', expand=True)

        toolbar = NavigationToolbar2Tk(canvas, toolbar_frame)
        toolbar.update()

        self._canvas  = canvas
        self._toolbar = toolbar

    #── resize handling ───────────────────────────────────────────────────────

    def _on_resize(self, _: tk.Event) -> None:
        if self._resize_id:
            self.after_cancel(self._resize_id)
        self._resize_id = self.after(200, self._apply_resize)

    def _apply_resize(self) -> None:
        self._resize_id = None
        if not self._figures or self._canvas is None:
            return
        fit_figure_to_frame(self._figures[self._current], self._canvas_frame)
        self._canvas.draw_idle()
