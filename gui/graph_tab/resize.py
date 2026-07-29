# ==============================================================================
# GRAPH TAB — RESIZE
# gui/graph_tab/resize.py
#
# Fits a matplotlib Figure's size to its containing Tkinter frame.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

from matplotlib.figure import Figure


def fit_figure_to_frame(fig: Figure, frame: tk.Widget, min_width: int = 400, min_height: int = 300,
                         toolbar_height: int = 40) -> None:
    """Resizes `fig` in-place (via set_size_inches) to fill `frame`'s
    current pixel dimensions, respecting a minimum size and leaving room
    for the navigation toolbar below the canvas."""
    w_px = max(frame.winfo_width(), min_width)
    h_px = max(frame.winfo_height() - toolbar_height, min_height)
    fig.set_size_inches(w_px / fig.dpi, h_px / fig.dpi)
