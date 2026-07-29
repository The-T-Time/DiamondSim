# ==============================================================================
# GAME LOG
# gui/teams_tab/game_log.py
#
# The "Game Log" sub-tab of a team's detail pane: every played game this
# season, W/L, score, and the Elo shift from that result.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from models.elo_snapshot import EloSnapshot
from models.game import Game
from gui.teams_tab.formatters import elo_fg
from gui.teams_tab.game_detail import game_detail_popup
from gui.widgets import (
    C_BG, C_BLUE, C_DARK, C_GRAY, C_GREEN, C_HOVER, C_ORANGE, C_RED, C_ROW_ALT,
    C_SELECTED, C_WHITE, FONT_NORMAL,
    W_DATE, W_HA, W_LARGE, W_OPPONENT, W_RANK, W_RESULT, W_XL,
    create_scrollable_frame, make_data_row, make_table_header, set_row_bg,
)

LOG_COLS: list[tuple[str, int, str]] = [
    ('#',          W_RANK,    'center'),
    ('Date',       W_DATE,    'center'),
    ('H/A',        W_HA,      'center'),
    ('Opponent',   W_OPPONENT,'w'),
    ('Score',      W_LARGE,   'center'),
    ('Result',     W_RESULT,  'center'),
    ('Elo Before', W_XL,      'center'),
    ('Elo Δ',      W_LARGE,   'center'),
]


def build_game_log(
    parent: tk.Widget, played_games: list[Game], team: str, elo_log: dict[int, EloSnapshot]
) -> None:
    if not played_games:
        ctk.CTkLabel(parent, text='No played games recorded.',
                    fg_color=C_BG, text_color=C_GRAY, font=FONT_NORMAL).pack(expand=True)
        return

    games = sorted(played_games, key=lambda g: g.date)
    make_table_header(parent, LOG_COLS)
    canvas, inner = create_scrollable_frame(parent, bg=C_BG)

    for i, game in enumerate(games):
        is_home   = game.is_home_team(team)
        opponent  = game.opponent_of(team)
        ha_str    = 'H' if is_home else 'A'
        won       = game.winner == team
        hs, aw    = game.home_score, game.away_score
        score_str = f"{hs}–{aw}" if is_home else f"{aw}–{hs}"

        snap = elo_log.get(game.game_pk) if game.game_pk is not None else None
        elo_before = snap.elo_before(is_home=is_home) if snap else None
        elo_delta  = snap.delta_for(is_home=is_home) if snap else None

        elo_before_str = f"{elo_before:.1f}" if elo_before is not None else '—'
        if elo_delta is not None:
            sign = '+' if elo_delta >= 0 else ''
            elo_delta_str = f"{sign}{elo_delta:.1f}"
            delta_fg      = elo_fg(elo_delta)
        else:
            elo_delta_str, delta_fg = '—', C_DARK

        result_fg = C_GREEN if won else C_RED
        base_bg   = C_WHITE if i % 2 == 0 else C_ROW_ALT

        cells: list[tuple[str, int, str, str, bool]] = [
            (str(i + 1),            W_RANK,    'center', C_GRAY,                          False),
            (game.date,              W_DATE,    'center', C_DARK,                          False),
            (ha_str,                W_HA,      'center', C_BLUE if is_home else C_ORANGE, True),
            (opponent,              W_OPPONENT,'w',      C_DARK,                          False),
            (score_str,             W_LARGE,   'center', C_DARK,                          False),
            ('W' if won else 'L',   W_RESULT,  'center', result_fg,                       True),
            (elo_before_str,        W_XL,      'center', C_DARK,                          False),
            (elo_delta_str,         W_LARGE,   'center', delta_fg,                        True),
        ]
        row, labels = make_data_row(inner, cells, bg=base_bg, cursor='hand2')
        bind_game_row(row, labels, base_bg, game, team, elo_log)


def bind_game_row(
    row: ctk.CTkFrame,
    labels: list[ctk.CTkLabel],
    base_bg: str,
    game: Game,
    team: str,
    elo_log: dict[int, EloSnapshot],
) -> None:
    selected = [False]

    def on_select(_: tk.Event) -> None:
        set_row_bg(row, labels, C_SELECTED)
        selected[0] = True

    def on_double(_: tk.Event) -> None:
        game_detail_popup(row, game, team, elo_log)

    def on_enter(_: tk.Event) -> None:
        if not selected[0]:
            set_row_bg(row, labels, C_HOVER)

    def on_leave(_: tk.Event) -> None:
        if not selected[0]:
            set_row_bg(row, labels, base_bg)

    for w in [row, *labels]:
        w.bind('<Button-1>',        on_select)
        w.bind('<Double-Button-1>', on_double)
        w.bind('<Enter>',           on_enter)
        w.bind('<Leave>',           on_leave)
