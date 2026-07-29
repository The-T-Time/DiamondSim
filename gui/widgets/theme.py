# ==============================================================================
# THEME
# gui/widgets/theme.py
#
# One-time CTk setup, called from main.py before the root window is
# created. Sets CTk's global appearance mode/color theme, kept in sync
# with the user's saved light/dark setting so CTk's own built-in widget
# chrome (borders, scrollbars) matches the rest of the app.
# ==============================================================================

from __future__ import annotations

import customtkinter as ctk

from data.settings_store import load_settings


def apply_theme() -> None:
    """Call once, before creating the CTk root window."""
    theme = load_settings().theme   #'light' | 'dark'
    ctk.set_appearance_mode(theme)        #keeps CTk's built-in widget chrome (borders, scrollbars, etc.) in sync with gui.widgets.colors
    ctk.set_default_color_theme('blue')   #CTk's built-in accent theme; individual widgets still override fg_color/text_color from gui.widgets.colors where the app needs a specific look
