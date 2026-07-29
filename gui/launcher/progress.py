# ==============================================================================
# PROGRESS INDICATOR
# gui/launcher/progress.py
#
# A small class wrapping the launcher's progress bar + status label state,
# so LauncherApp holds one ProgressIndicator instance instead of several
# loosely-related attributes.
# ==============================================================================

from __future__ import annotations

import customtkinter as ctk

from gui.widgets import C_BG, C_DARK, C_GRAY, FONT_SMALL


class ProgressIndicator:
    """Owns the progress-bar UI shown under the Simulate/Backtest form while
    a run is in flight. `show()` to create it, `pulse()`/`update()` while
    running, `hide()` to tear it down."""

    def __init__(self, root: ctk.CTk) -> None:
        self._root = root
        self._frame: ctk.CTkFrame | None = None
        self._bar: ctk.CTkProgressBar | None = None
        self._count: ctk.CTkLabel | None = None
        self._pulse_frac = 0.0

    def show(self) -> None:
        self._pulse_frac = 0.0
        self._frame = ctk.CTkFrame(self._root, fg_color=C_BG)
        self._frame.pack(pady=6)
        self._bar = ctk.CTkProgressBar(self._frame, width=280, progress_color=C_DARK)
        self._bar.set(0.0)
        self._bar.pack(pady=(4, 4))
        self._count = ctk.CTkLabel(self._frame, text='Preparing… fetching data',
                                   font=FONT_SMALL, text_color=C_GRAY, fg_color=C_BG)
        self._count.pack()
        self._root.update_idletasks()

    def pulse(self) -> None:
        """Indeterminate-style animation for the fetch/Elo-calc phase
        (pre-sim), shown while there's no (done, total) progress yet to
        report — sweeps the bar back and forth rather than sitting still."""
        if self._bar is None:
            return
        self._pulse_frac += 0.04
        if self._pulse_frac > 1.0:
            self._pulse_frac = 0.0
        self._bar.set(self._pulse_frac)

    def update(self, done: int, total: int) -> None:
        if self._bar is None or self._count is None:
            return
        fraction = (done / total) if total else 0.0
        self._bar.set(fraction)
        self._count.configure(text=f'{done:,} / {total:,} simulations')

    def hide(self) -> None:
        if self._frame is not None:
            self._frame.destroy()
        self._frame = None
        self._bar = None
        self._count = None
