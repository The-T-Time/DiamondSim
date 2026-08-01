# ==============================================================================
# FORMS
# gui/launcher/forms.py
#
# Small, self-contained form-row builders (season/sims/model/seed
# dropdowns, etc.) for the Simulate/Backtest screens. Free functions, not
# LauncherApp methods, since none need any other app state.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional

import customtkinter as ctk

from data.settings_store import load_settings
from gui.launcher.constants import _MODELS
from gui.widgets import C_RED, C_RED_HOVER, FONT_NORMAL, FONT_NORMAL_BOLD
from models.app_settings import has_customized_model_weights

_CHARS_TO_PX = 8   #rough per-character pixel width at FONT_NORMAL's size


def parse_seed(text: str) -> Optional[int]:
    """'' or 'random' (any case) -> None (fresh random seed each run).
    Otherwise must be an int. Raises ValueError on anything else."""
    text = text.strip()
    if text == '' or text.lower() == 'random':
        return None
    return int(text)   #raises ValueError for non-integer text — caller handles it


def form_row(form: ctk.CTkFrame, label: str, default: str,
             row: int, width: int = 16, entry_w: int = 10) -> tk.StringVar:
    ctk.CTkLabel(form, text=label, font=FONT_NORMAL, anchor='e',
                width=width * _CHARS_TO_PX).grid(row=row, column=0, padx=6, pady=6, sticky='e')
    var = tk.StringVar(value=default)
    ctk.CTkEntry(form, textvariable=var, width=entry_w * _CHARS_TO_PX,
                font=FONT_NORMAL).grid(row=row, column=1, sticky='w')
    return var


def model_row(form: ctk.CTkFrame, row: int, width: int = 16) -> tk.StringVar:
    """Dropdown for Normal / Conservative / Aggressive / User Elo models.
    Defaults to 'Normal' unless the Settings screen's simulation weights
    have been changed from their factory defaults, in which case it
    defaults to 'User' instead."""
    ctk.CTkLabel(form, text='Model:', font=FONT_NORMAL, anchor='e',
                width=width * _CHARS_TO_PX).grid(row=row, column=0, padx=6, pady=6, sticky='e')
    initial = 'User' if has_customized_model_weights(load_settings()) else 'Normal'
    var = tk.StringVar(value=initial)
    ctk.CTkOptionMenu(form, variable=var, values=list(_MODELS)).grid(row=row, column=1, sticky='w')
    return var


def action_row(parent: ctk.CTkFrame, label: str,
               run_cmd: Callable[[], None], btn_style: dict,
               cancel_cmd: Callable[[], None]) -> tuple[ctk.CTkButton, ctk.CTkButton]:
    """Builds the [Run] [Cancel] pair shown under the Simulate/Backtest
    form. Cancel starts disabled — there's nothing to cancel until a run
    is actually in flight; run_action_with_progress enables it for the
    run's duration and disables it again once the run finishes (or is
    cancelled). Navigation itself now lives in a separate, always-visible
    top-left Back button (see gui/launcher/app.py's _back_button)."""
    row = ctk.CTkFrame(parent, fg_color='transparent')
    row.pack(pady=12)
    run_btn = ctk.CTkButton(row, text=label, font=FONT_NORMAL_BOLD,
                           cursor='hand2', width=16 * _CHARS_TO_PX,
                           command=run_cmd, **btn_style)
    run_btn.pack(side='left', padx=8)
    cancel_btn = ctk.CTkButton(row, text='✕  Cancel', font=FONT_NORMAL,
                              cursor='hand2', width=12 * _CHARS_TO_PX,
                              fg_color='transparent', text_color=C_RED, border_width=1,
                              border_color=C_RED, hover_color=C_RED_HOVER,
                              state='disabled', command=cancel_cmd)
    cancel_btn.pack(side='left', padx=8)
    return run_btn, cancel_btn
