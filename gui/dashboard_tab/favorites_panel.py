# ==============================================================================
# DASHBOARD TAB — FAVORITES PANEL
# gui/dashboard_tab/favorites_panel.py
#
# The "World Series Favorites" (or "Playoff Favorites", if the postseason
# wasn't simulated) leaderboard panel.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.simulation_result import SimulationResult
from gui.logos import get_team_logo
from gui.widgets import (
    C_WHITE, C_DARK, C_MID, C_PANEL, C_HDR, C_HEADER_BAR, C_HEADER_TEXT, C_ROW_ALT,
    C_GREEN, C_BLUE, C_GOLD, C_GRAY,
    FONT_TINY, FONT_SMALL_BOLD, FONT_MEDIUM_BOLD,
    format_pct,
)

_BAR_WIDTH_PX = 140
_MEDALS = {1: '🥇', 2: '🥈', 3: '🥉'}


def build_favorites_panel(parent: tk.Widget, result: SimulationResult) -> ctk.CTkFrame:
    """Builds the top-10 championship/playoff-odds leaderboard panel and
    grids it into column 0 of `parent`. Returns the panel frame."""
    has_ws = bool(result.world_series_odds)
    odds = result.world_series_odds if has_ws else result.playoff_odds
    title = 'World Series Favorites' if has_ws else 'Playoff Favorites'
    unit = 'WS%' if has_ws else 'Playoff%'

    panel = ctk.CTkFrame(parent, fg_color=C_WHITE, border_width=1)
    panel.grid(row=0, column=0, sticky='nsew', padx=(0, 8))

    ctk.CTkLabel(panel, text='🏆  ' + title, fg_color=C_HEADER_BAR, text_color=C_HEADER_TEXT,
                font=FONT_MEDIUM_BOLD, anchor='w', padx=10).pack(fill='x', pady=6)

    if not has_ws:
        ctk.CTkLabel(panel,
                    text='Postseason simulation was disabled — showing playoff odds.',
                    fg_color=C_WHITE, text_color=C_GRAY, font=FONT_TINY,
                    anchor='w', padx=10).pack(fill='x', pady=3)

    ranked = sorted(ALL_TEAMS, key=lambda t: odds.get(t, 0.0), reverse=True)
    top = [t for t in ranked if odds.get(t, 0.0) > 0][:10] or ranked[:10]
    max_odds = max((odds.get(t, 0.0) for t in top), default=1.0) or 1.0

    #Measured from the actual font/rows about to be shown, rather than a
    #fixed pixel guess — a static width tuned for one font size clips team
    #names the next time the base font size changes (see gui/widgets/fonts.py).
    name_font = tkfont.Font(family='Inter', size=FONT_SMALL_BOLD[1], weight='bold')
    name_col_w = max(name_font.measure(t) for t in top) + 10
    pct_col_w = max(name_font.measure(format_pct(odds.get(t, 0.0))) for t in top) + 10

    rows = ctk.CTkFrame(panel, fg_color=C_WHITE, corner_radius=0)
    rows.pack(fill='both', expand=True, padx=8, pady=6)

    for i, team in enumerate(top, 1):
        val = odds.get(team, 0.0)
        bg = C_WHITE if i % 2 else C_ROW_ALT
        row = ctk.CTkFrame(rows, fg_color=bg, corner_radius=0)
        row.pack(fill='x', pady=1)

        medal = _MEDALS.get(i, f'{i}.')
        ctk.CTkLabel(row, text=medal, fg_color=bg, text_color=C_DARK, font=FONT_SMALL_BOLD,
                    width=28, anchor='w').pack(side='left', padx=(4, 2))
        logo = get_team_logo(TEAM_REGISTRY[team].id, max_size=20)
        if logo is not None:
            logo_lbl = tk.Label(row, image=logo, bg=bg)
            logo_lbl.image = logo   #extra ref so Tkinter can't garbage-collect it
            logo_lbl.pack(side='left', padx=(0, 4))
        ctk.CTkLabel(row, text=team, fg_color=bg, text_color=C_DARK, font=FONT_SMALL_BOLD,
                    width=name_col_w, anchor='w').pack(side='left')

        bar_wrap = ctk.CTkFrame(row, fg_color=C_HDR, width=_BAR_WIDTH_PX, height=14, corner_radius=0)
        bar_wrap.pack(side='left', padx=6)
        bar_wrap.pack_propagate(False)
        fill_w = max(2, int(_BAR_WIDTH_PX * val / max_odds))
        fill_c = C_GOLD if i == 1 else (C_GREEN if i <= 3 else C_BLUE)
        ctk.CTkFrame(bar_wrap, fg_color=fill_c, width=fill_w, corner_radius=0).pack(side='left', fill='y')

        ctk.CTkLabel(row, text=format_pct(val), fg_color=bg, text_color=C_MID,
                    font=FONT_SMALL_BOLD, width=pct_col_w, anchor='e').pack(side='left', padx=(2, 6))

    ctk.CTkLabel(panel, text=f'Bars scaled to the leader.  {unit} across all 30 clubs.',
                fg_color=C_PANEL, text_color=C_GRAY, font=FONT_TINY,
                anchor='w', padx=10).pack(fill='x', pady=3)

    return panel
