# ==============================================================================
# DASHBOARD TAB — SUMMARY PANEL
# gui/dashboard_tab/summary_panel.py
#
# The "Run Summary" panel: mode/season/sims/games facts, plus a Division
# Leaders mini-table.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.simulation_result import SimulationResult
from gui.widgets import (
    C_WHITE, C_DARK, C_MID, C_HDR, C_HEADER_BAR, C_HEADER_TEXT, C_ROW_ALT, C_GRAY,
    FONT_TINY, FONT_SMALL, FONT_SMALL_BOLD, FONT_MEDIUM_BOLD,
)

_LEAGUE_DIVISIONS = {
    'AL': ['AL East', 'AL Central', 'AL West'],
    'NL': ['NL East', 'NL Central', 'NL West'],
}


def _division_sort_key(result: SimulationResult, team: str) -> tuple[float, int]:
    return result.pct(team), result.win_loss(team)[0]


def _run_facts(result: SimulationResult) -> list[tuple[str, str]]:
    facts = [
        ('Mode', 'Backtest' if result.mode == 'backtest' else 'Projection'),
        ('Season', str(result.season)),
        ('Simulations', f'{result.num_sims:,}'),
        ('Games played', str(len(result.played_games))),
        ('Games remaining', str(len(result.unplayed_games))),
        ('Seed', str(result.cfg.random_seed)),
    ]
    if result.mode == 'backtest' and result.snapshot_date:
        facts.insert(2, ('Snapshot', result.snapshot_date))
    return facts


def _build_facts_grid(panel: tk.Widget, result: SimulationResult) -> None:
    grid = ctk.CTkFrame(panel, fg_color=C_WHITE, corner_radius=0)
    grid.pack(fill='x', padx=10, pady=6)
    facts = _run_facts(result)
    #Measured from the actual labels about to be shown, rather than a
    #fixed pixel guess — a static width tuned for one font size clips
    #text the next time the base font size changes (see gui/widgets/fonts.py).
    label_font = tkfont.Font(family='Inter', size=FONT_SMALL[1])
    label_col_w = max(label_font.measure(label) for label, _ in facts) + 10
    for i, (label, value) in enumerate(facts):
        bg = C_WHITE if i % 2 else C_ROW_ALT
        row = ctk.CTkFrame(grid, fg_color=bg, corner_radius=0)
        row.pack(fill='x')
        ctk.CTkLabel(row, text=label, fg_color=bg, text_color=C_GRAY, font=FONT_SMALL,
                    width=label_col_w, anchor='w').pack(side='left', padx=(2, 6), pady=2)
        ctk.CTkLabel(row, text=value, fg_color=bg, text_color=C_DARK, font=FONT_SMALL_BOLD,
                    anchor='w').pack(side='left')


def _build_division_leaders(panel: tk.Widget, result: SimulationResult) -> None:
    ctk.CTkFrame(panel, fg_color=C_HDR, height=1, corner_radius=0).pack(fill='x', padx=10, pady=(6, 0))
    ctk.CTkLabel(panel, text='Division Leaders', fg_color=C_WHITE, text_color=C_DARK,
                font=FONT_SMALL_BOLD, anchor='w', padx=10).pack(fill='x', pady=(6, 2))

    leaders = ctk.CTkFrame(panel, fg_color=C_WHITE, corner_radius=0)
    leaders.pack(fill='x', padx=10, pady=(0, 8))
    #Measured from real team names rather than a fixed pixel guess — see
    #the matching note in _build_facts_grid above.
    name_font = tkfont.Font(family='Inter', size=FONT_SMALL_BOLD[1], weight='bold')
    name_col_w = max(name_font.measure(t) for t in ALL_TEAMS) + 10
    i = 0
    for league in ('AL', 'NL'):
        for division in _LEAGUE_DIVISIONS[league]:
            division_teams = sorted(
                [t for t in ALL_TEAMS if TEAM_REGISTRY[t].division == division],
                key=lambda t: _division_sort_key(result, t), reverse=True,
            )
            leader = division_teams[0]
            wins, losses = result.win_loss(leader)
            bg = C_WHITE if i % 2 else C_ROW_ALT
            row = ctk.CTkFrame(leaders, fg_color=bg, corner_radius=0)
            row.pack(fill='x')
            ctk.CTkLabel(row, text=division, fg_color=bg, text_color=C_GRAY, font=FONT_TINY,
                        width=88, anchor='w').pack(side='left', padx=(2, 4), pady=1)
            ctk.CTkLabel(row, text=leader, fg_color=bg, text_color=C_DARK, font=FONT_SMALL_BOLD,
                        width=name_col_w, anchor='w').pack(side='left')
            ctk.CTkLabel(row, text=f'{wins}-{losses}', fg_color=bg, text_color=C_MID, font=FONT_SMALL,
                        anchor='e').pack(side='left')
            i += 1


def build_summary_panel(parent: tk.Widget, result: SimulationResult) -> ctk.CTkFrame:
    """Builds the Run Summary + Division Leaders panel and grids it into
    column 1 of `parent`. Returns the panel frame."""
    panel = ctk.CTkFrame(parent, fg_color=C_WHITE, border_width=1)
    panel.grid(row=0, column=1, sticky='nsew')

    ctk.CTkLabel(panel, text='📋  Run Summary', fg_color=C_HEADER_BAR, text_color=C_HEADER_TEXT,
                font=FONT_MEDIUM_BOLD, anchor='w', padx=10).pack(fill='x', pady=6)

    _build_facts_grid(panel, result)
    _build_division_leaders(panel, result)

    return panel
