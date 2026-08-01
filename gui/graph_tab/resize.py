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
    for the navigation toolbar below the canvas.

    fig.dpi is reset to frame.winfo_fpixels('1i') — Tk's own idea of how
    many real pixels make up an inch right now — instead of matplotlib's
    unrelated hardcoded default (100). CustomTkinter sets Tk's `tk
    scaling` for HiDPI displays, and Tk then realizes pixel-sized widgets
    (including the matplotlib canvas FigureCanvasTkAgg creates) according
    to that scaling. Sizing the figure in inches using a fixed dpi=100
    ignores that scaling entirely, so on any scaled display (125%+ on
    Windows, Retina on macOS) the canvas actually painted on screen comes
    out far larger than the frame it's meant to fill — reusing Tk's own
    conversion keeps the two consistent regardless of the display's
    scaling factor.
    """
    fig.dpi = frame.winfo_fpixels('1i')
    w_px = max(frame.winfo_width(), min_width)
    h_px = max(frame.winfo_height() - toolbar_height, min_height)
    fig.set_size_inches(w_px / fig.dpi, h_px / fig.dpi)

