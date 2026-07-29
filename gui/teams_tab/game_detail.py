# ==============================================================================
# GAME DETAIL POPUP
# gui/teams_tab/game_detail.py
#
# Split out of the former gui/teams_tab.py into a package.
# CTkToplevel + CTk widgets throughout.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from models.elo_snapshot import EloSnapshot
from models.game import Game
from gui.widgets import (
    C_BG, C_BLUE, C_DARK, C_GRAY, C_HEADER_TEXT, C_WHITE, C_WIN_HDR, C_LOSS_HDR,
    FONT_LARGE, FONT_NORMAL, FONT_NORMAL_BOLD, FONT_SCORE, FONT_TINY,
)


def game_detail_popup(parent: tk.Widget, game: Game, team: str, elo_log: dict[int, EloSnapshot]) -> None:
    popup = ctk.CTkToplevel(parent)
    popup.title(f"Game Detail — {game.date}")
    popup.geometry('400x370')
    popup.resizable(False, False)

    is_home  = game.is_home_team(team)
    opponent = game.opponent_of(team)
    won      = game.winner == team

    hdr_bg = C_WIN_HDR if won else C_LOSS_HDR
    hdr    = ctk.CTkFrame(popup, fg_color=hdr_bg, corner_radius=0)
    hdr.pack(fill='x')
    ctk.CTkLabel(hdr, text='WIN' if won else 'LOSS',
                fg_color=hdr_bg, text_color=C_HEADER_TEXT, font=FONT_LARGE).pack(pady=(12, 0))
    ctk.CTkLabel(hdr, text=f"{team}  {'vs' if is_home else '@'}  {opponent}",
                fg_color=hdr_bg, text_color=C_HEADER_TEXT, font=FONT_NORMAL).pack(pady=(0, 12))

    hs, aw = game.home_score, game.away_score
    score_frame = ctk.CTkFrame(popup, fg_color=C_WHITE, corner_radius=0)
    score_frame.pack(fill='x')
    ctk.CTkLabel(score_frame, text=f"{hs}  –  {aw}", fg_color=C_WHITE, text_color=C_DARK,
                font=FONT_SCORE).pack(pady=(14, 0))
    ctk.CTkLabel(score_frame,
                text=f"{game.home} (home)  vs  {game.away} (away)",
                fg_color=C_WHITE, text_color=C_GRAY, font=FONT_TINY).pack(pady=(0, 14))

    snap = elo_log.get(game.game_pk) if game.game_pk is not None else None
    elo_before = snap.elo_before(is_home=is_home) if snap else None
    elo_delta  = snap.delta_for(is_home=is_home) if snap else None

    grid = ctk.CTkFrame(popup, fg_color=C_BG, corner_radius=0)
    grid.pack(fill='x', padx=20, pady=8)

    stat_rows = [
        ('Date',             game.date),
        ('Game PK',          str(game.game_pk if game.game_pk is not None else '—')),
        ('Run Differential', str(game.run_diff if game.run_diff is not None else '?')),
        ('Elo Before',       f"{elo_before:.1f}" if elo_before else '—'),
        ('Elo Change',       (f"+{elo_delta:.2f}" if elo_delta and elo_delta >= 0
                              else f"{elo_delta:.2f}" if elo_delta else '—')),
        ('Home / Away',      'Home' if is_home else 'Away'),
    ]
    for j, (label, value) in enumerate(stat_rows):
        bg = C_WHITE if j % 2 == 0 else C_BG
        r  = ctk.CTkFrame(grid, fg_color=bg, corner_radius=0)
        r.pack(fill='x')
        ctk.CTkLabel(r, text=label, fg_color=bg, text_color=C_GRAY,
                    font=FONT_NORMAL, width=155, anchor='w').pack(side='left', padx=6, pady=3)
        ctk.CTkLabel(r, text=value, fg_color=bg, text_color=C_DARK,
                    font=FONT_NORMAL_BOLD, anchor='w').pack(side='left')

    ctk.CTkButton(popup, text='Close', command=popup.destroy,
                 font=FONT_NORMAL, fg_color=C_BLUE, text_color=C_HEADER_TEXT,
                 cursor='hand2').pack(pady=10)
