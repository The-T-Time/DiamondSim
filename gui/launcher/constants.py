# ==============================================================================
# LAUNCHER CONSTANTS
# gui/launcher/constants.py
#
# Split out of the former gui/launcher.py into a package.
# Customtkinter button kwargs (fg_color/text_color/hover_color
# instead of tkinter's bg/fg/activebackground); ascii_bar removed since
# progress.py now uses a native CTkProgressBar instead of a text-rendered bar.
# ==============================================================================

from __future__ import annotations

from gui.widgets import C_HEADER_TEXT

_BTN_SIM      = {'fg_color': '#2980b9', 'text_color': C_HEADER_TEXT, 'hover_color': '#3498db'}
_BTN_BACK     = {'fg_color': '#27ae60', 'text_color': C_HEADER_TEXT, 'hover_color': '#2ecc71'}
_BTN_LOAD     = {'fg_color': '#8e44ad', 'text_color': C_HEADER_TEXT, 'hover_color': '#9b59b6'}
_BTN_SETTINGS = {'fg_color': '#7f8c8d', 'text_color': C_HEADER_TEXT, 'hover_color': '#95a5a6'}

_MODELS = ('Conservative', 'Normal', 'Aggressive', 'User')
