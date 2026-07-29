# ==============================================================================
# TOOLTIP
# gui/widgets/tooltip.py
#
# Thin wrapper around the third-party tkinter-tooltip package so every
# tooltip in the app looks the same. Uses the fixed dark-navy/white
# header colors so tooltips stay readable in both themes.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

from tktooltip import ToolTip

from gui.widgets.colors import C_HEADER_BAR, C_HEADER_TEXT
from gui.widgets.fonts import FONT_SMALL

_WRAP_WIDTH = 280   #pixels — keeps tooltip text from stretching across the whole window


def add_tooltip(widget: tk.Widget, text: str, delay: float = 0.35) -> ToolTip:
    """Attaches a themed hover tooltip to `widget`. Returns the ToolTip
    instance (rarely needed by the caller, but handy if it ever needs to
    be torn down early)."""
    return ToolTip(
        widget,
        msg=text,
        delay=delay,
        follow=True,
        parent_kwargs={'bg': C_HEADER_BAR, 'padx': 1, 'pady': 1},
        bg=C_HEADER_BAR,
        fg=C_HEADER_TEXT,
        font=FONT_SMALL,
        justify='left',
        width=_WRAP_WIDTH,
    )
