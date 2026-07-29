# ==============================================================================
# GRAPH TAB — VIEW SWITCHER
# gui/graph_tab/view_switcher.py
#
# The row of "View: [Overall Odds] [By Division]"-style buttons at the
# top of the Graphs tab, and the highlight logic showing which is active.
# ==============================================================================

from __future__ import annotations

from typing import Callable

import tkinter as tk

import customtkinter as ctk

from gui.widgets import C_BLUE, C_DARK, C_HEADER_BAR, C_HEADER_TEXT, FONT_SMALL


def build_view_buttons(parent: tk.Widget, labels: list[str], on_select: Callable[[int], None]) -> list[ctk.CTkButton]:
    """Packs a 'View:' label followed by one button per entry in `labels`
    into `parent`. `on_select(idx)` is called with the button's index when
    clicked. Returns the buttons in the same order as `labels`, so the
    caller can pass them to highlight_active_button later."""
    ctrl = ctk.CTkFrame(parent, fg_color=C_HEADER_BAR, corner_radius=0)
    ctrl.pack(fill='x', side='top')
    ctk.CTkLabel(ctrl, text='View:', fg_color=C_HEADER_BAR, text_color=C_HEADER_TEXT,
                font=FONT_SMALL).pack(side='left', padx=(10, 4), pady=4)

    buttons: list[ctk.CTkButton] = []
    for i, label in enumerate(labels):
        btn = ctk.CTkButton(
            ctrl, text=label, font=FONT_SMALL,
            cursor='hand2',
            command=lambda idx=i: on_select(idx),
        )
        btn.pack(side='left', padx=2, pady=4)
        buttons.append(btn)
    return buttons


def highlight_active_button(buttons: list[ctk.CTkButton], active_idx: int, inactive_bg: str) -> None:
    """Recolors `buttons` so only the one at `active_idx` looks selected."""
    for i, btn in enumerate(buttons):
        is_active = i == active_idx
        btn.configure(fg_color=C_BLUE if is_active else inactive_bg,
                     text_color=C_HEADER_TEXT if is_active else C_DARK)
