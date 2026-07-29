# ==============================================================================
# UPCOMING GAMES PANEL
# gui/teams_tab/upcoming.py
#
# The "Upcoming" sub-tab of a team's detail pane: remaining schedule with
# simulation-derived win probability and opponent record for each game.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from models.game import Game
from models.simulation_result import SimulationResult
from gui.widgets import (
    C_BG, C_BLUE, C_DARK, C_GRAY, C_GREEN, C_ORANGE, C_RED, C_ROW_ALT, C_WHITE,
    FONT_NORMAL, FONT_SMALL,
    W_DATE, W_HA, W_MED, W_RANK, W_STREAK, W_TEAM,
    bind_hover, create_scrollable_frame, make_data_row, make_table_header,
)

UPCOMING_COLS: list[tuple[str, int, str]] = [
    ('#',          W_RANK,   'center'),
    ('Date',       W_DATE,   'center'),
    ('H/A',        W_HA,     'center'),
    ('Opponent',   W_TEAM,   'w'),
    ('Opp. Record', W_MED,   'center'),
    ('Win Prob.',  W_STREAK, 'center'),
]


def build_upcoming(parent: tk.Widget, upcoming_games: list[Game], team: str,
                   result: SimulationResult | None = None) -> None:
    if not upcoming_games:
        ctk.CTkLabel(parent, text='No remaining games — season complete.',
                    fg_color=C_BG, text_color=C_GRAY, font=FONT_NORMAL).pack(expand=True)
        return

    games = sorted(upcoming_games, key=lambda g: g.date)
    make_table_header(parent, UPCOMING_COLS)

    if result is not None and result.unplayed_game_home_win_pct:
        note = ('Win probability is the share of simulations this team won that specific game — '
                'not a single prediction.')
        ctk.CTkLabel(parent, text=note, fg_color=C_BG, text_color=C_GRAY,
                    font=FONT_SMALL, anchor='w', padx=8).pack(fill='x', pady=(2, 4))

    _, inner = create_scrollable_frame(parent, bg=C_BG)

    for i, game in enumerate(games):
        is_home  = game.is_home_team(team)
        opponent = game.opponent_of(team)
        ha_str   = 'H' if is_home else 'A'
        base_bg  = C_WHITE if i % 2 == 0 else C_ROW_ALT

        if result is not None:
            opp_w, opp_l = result.win_loss(opponent)
            opp_record = f'{opp_w}-{opp_l}'
            win_prob = result.win_probability(game, team)
        else:
            opp_record = '—'
            win_prob = None

        if win_prob is None:
            win_prob_str, win_prob_color = '—', C_GRAY
        else:
            win_prob_str = f'{win_prob:.0f}%'
            win_prob_color = C_GREEN if win_prob >= 55 else (C_RED if win_prob <= 45 else C_GRAY)

        cells: list[tuple[str, int, str, str, bool]] = [
            (str(i + 1),      W_RANK,   'center', C_GRAY,                          False),
            (game.date,       W_DATE,   'center', C_DARK,                          False),
            (ha_str,          W_HA,     'center', C_BLUE if is_home else C_ORANGE, True),
            (opponent,        W_TEAM,   'w',      C_DARK,                          False),
            (opp_record,      W_MED,    'center', C_GRAY,                          False),
            (win_prob_str,    W_STREAK, 'center', win_prob_color,                  True),
        ]
        row, labels = make_data_row(inner, cells, bg=base_bg)
        bind_hover(row, labels, base_bg)
