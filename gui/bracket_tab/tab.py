# ==============================================================================
# BRACKET TAB
# gui/bracket_tab/tab.py
#
# Shows the single most common exact bracket across every simulation, as
# a mirrored tournament bracket (AL left-to-right, NL right-to-left,
# converging on one World Series box). If postseason simulation was off
# for this run, explains why instead of rendering an empty bracket.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

from data.teams import TEAM_REGISTRY
from models.playoff_bracket import PlayoffBracketResult
from models.simulation_result import SimulationResult
from gui.logos import get_team_logo
from gui.widgets import (
    C_BG, C_BLUE, C_DARK, C_DIV_LEAD, C_GOLD, C_GRAY, C_GREEN, C_HDR,
    C_MID, C_SASH, C_WHITE,
    FONT_HEADER, FONT_MEDIUM, FONT_MEDIUM_BOLD, FONT_NORMAL, FONT_NORMAL_BOLD,
    FONT_SMALL, FONT_TITLE,
    create_scrollable_frame, make_header_bar,
)

#── bracket geometry ─────────────────────────────────────────────────────────
#Fixed pixel coordinates rather than fractions of the widget's actual size
#— simpler than reflowing on every resize, and this comfortably fits the
#window widths this app targets (see gui/widgets/sizes.py's own
#fixed-width conventions for the same tradeoff elsewhere in the app).
#Box/canvas sizes were widened (and the checkmark/logo shrunk a touch) to
#make room for each row's team logo without crowding out the team name —
#see _fit_team_name below for the hard backstop against clipping regardless.
_CANVAS_W, _CANVAS_H = 1850, 420
_BOX_W, _BOX_H = 215, 56
_WS_BOX_W, _WS_BOX_H = 280, 100

#Row y-positions, shared by both leagues (mirrored horizontally, not
#vertically) — match 0 is the 3-vs-6 Wild Card game, match 1 is 4-vs-5.
_ROW_Y = {0: 100, 1: 280}
_CS_Y = (_ROW_Y[0] + _ROW_Y[1]) // 2   #Championship Series sits at the midpoint
_WS_Y = _CS_Y                          #World Series lines up with both leagues' CS row

#AL flows left -> right toward the center; NL mirrors it, right -> left.
_AL_X = {'wc': 110, 'ds': 390, 'cs': 640}
_NL_X = {'wc': _CANVAS_W - 110, 'ds': _CANVAS_W - 390, 'cs': _CANVAS_W - 640}
_WS_X = _CANVAS_W // 2

_ROUND_LABELS = ('Wild Card', 'Division Series', 'Championship Series')

#Fixed sizes for the checkmark/logo that sit to the left of a team name in
#a matchup-box row, and the trophy/logo that sit to the left of a team
#name in the World Series box — used both to lay those widgets out AND
#to compute how much width is actually left over for the name itself
#(see _fit_team_name).
_MARK_W, _MARK_PAD = 13, 4
_LOGO_W, _LOGO_PAD = 17, 2
_TEXT_PAD = 4   #CTkLabel's own internal padx, applied on both sides
_WS_TROPHY_W, _WS_TROPHY_PAD = 22, 10
_WS_LOGO_W, _WS_LOGO_PAD = 24, 3
_WS_HOME_AWAY_RESERVED = 74   #'Home-field' label + its own padx, reserved on both rows so they truncate consistently whether or not this particular row shows it


class BracketTab(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, result: SimulationResult) -> None:
        super().__init__(parent, fg_color=C_BG, corner_radius=0)
        self._result = result
        self._build()

    def _build(self) -> None:
        bracket = self._result.projected_bracket

        if bracket is None:
            make_header_bar(self, 'Playoff Bracket')
            ctk.CTkLabel(
                self, fg_color=C_BG, text_color=C_GRAY, font=FONT_MEDIUM,
                justify='left',
                text=("Postseason simulation was off for this run, so there's no\n"
                      "bracket to project. Turn on postseason simulation and re-run\n"
                      "to see the most common playoff outcome here."),
            ).pack(padx=20, pady=30, anchor='w')
            return

        pct = self._result.projected_bracket_pct
        n = self._result.num_sims
        tied = self._result.projected_bracket_tied_count
        occurrences = round(pct / 100 * n)
        pct_str = f'{pct:.1f}%' if pct >= 0.05 else f'{pct:.3f}%'
        subtitle = f'Most common of {n:,} simulations — {occurrences:,} of them ({pct_str})'
        if tied > 1:
            subtitle += f'  ·  tied with {tied - 1:,} other bracket(s) — no clear favorite yet'
        make_header_bar(self, 'Playoff Bracket', subtitle)

        _scroll, inner = create_scrollable_frame(self)
        self._draw_bracket(inner, bracket)
        self._build_footer(inner)

    def _draw_bracket(self, parent: tk.Widget, bracket: PlayoffBracketResult) -> None:
        wrap = ctk.CTkFrame(parent, fg_color=C_BG, corner_radius=0)
        wrap.pack(padx=8, pady=(14, 6))

        canvas = tk.Canvas(wrap, width=_CANVAS_W, height=_CANVAS_H,
                           bg=C_BG, highlightthickness=0)
        canvas.pack()

        canvas.create_text(_AL_X['wc'], 22, text=f'AL  —  {bracket.al_champion}',
                           fill=C_BLUE, font=(FONT_MEDIUM_BOLD[0], FONT_MEDIUM_BOLD[1], 'bold'),
                           anchor='w')
        canvas.create_text(_NL_X['wc'], 22, text=f'{bracket.nl_champion}  —  NL',
                           fill=C_GREEN, font=(FONT_MEDIUM_BOLD[0], FONT_MEDIUM_BOLD[1], 'bold'),
                           anchor='e')

        for key, label in zip(('wc', 'ds', 'cs'), _ROUND_LABELS):
            canvas.create_text(_AL_X[key], 50, text=label, fill=C_GRAY,
                               font=(FONT_SMALL[0], FONT_SMALL[1], 'bold'))
            canvas.create_text(_NL_X[key], 50, text=label, fill=C_GRAY,
                               font=(FONT_SMALL[0], FONT_SMALL[1], 'bold'))

        self._draw_league(canvas, 'AL', bracket, _AL_X)
        self._draw_league(canvas, 'NL', bracket, _NL_X)
        self._draw_world_series(canvas, bracket)

    def _draw_league(self, canvas: tk.Canvas, league: str,
                     bracket: PlayoffBracketResult, col_x: dict) -> None:
        seeds = bracket.al_seeds if league == 'AL' else bracket.nl_seeds
        wc_w = bracket.al_wc_winners if league == 'AL' else bracket.nl_wc_winners
        ds_w = bracket.al_ds_winners if league == 'AL' else bracket.nl_ds_winners
        champ = bracket.al_champion if league == 'AL' else bracket.nl_champion
        line_kw = dict(fill=C_SASH, width=2)

        for i in (0, 1):
            lo, hi = sorted([col_x['wc'], col_x['ds']])
            x1 = lo + _BOX_W // 2 if col_x['wc'] < col_x['ds'] else hi - _BOX_W // 2
            x2 = hi - _BOX_W // 2 if col_x['wc'] < col_x['ds'] else lo + _BOX_W // 2
            canvas.create_line(x1, _ROW_Y[i], x2, _ROW_Y[i], **line_kw)

        elbow_x = (col_x['ds'] + col_x['cs']) // 2
        for i in (0, 1):
            x1 = col_x['ds'] + (_BOX_W // 2 if col_x['ds'] < col_x['cs'] else -_BOX_W // 2)
            x2 = col_x['cs'] + (-_BOX_W // 2 if col_x['ds'] < col_x['cs'] else _BOX_W // 2)
            canvas.create_line(x1, _ROW_Y[i], elbow_x, _ROW_Y[i],
                               elbow_x, _CS_Y, x2, _CS_Y, **line_kw)

        cs_to_ws_x = col_x['cs'] + (_BOX_W // 2 if col_x['cs'] < _WS_X else -_BOX_W // 2)
        ws_edge_x = _WS_X + (-_WS_BOX_W // 2 if col_x['cs'] < _WS_X else _WS_BOX_W // 2)
        canvas.create_line(cs_to_ws_x, _CS_Y, ws_edge_x, _WS_Y, **line_kw)

        self._matchup_box(canvas, col_x['wc'], _ROW_Y[0], seeds[2], seeds[5], wc_w[0])
        self._matchup_box(canvas, col_x['wc'], _ROW_Y[1], seeds[3], seeds[4], wc_w[1])
        self._matchup_box(canvas, col_x['ds'], _ROW_Y[0], seeds[1], wc_w[0], ds_w[1])
        self._matchup_box(canvas, col_x['ds'], _ROW_Y[1], seeds[0], wc_w[1], ds_w[0])
        self._matchup_box(canvas, col_x['cs'], _CS_Y, ds_w[0], ds_w[1], champ, highlight=True)

    def _fit_team_name(self, font_tuple: tuple, text: str, max_width: int) -> str:
        """Truncates `text` with a trailing ellipsis if it wouldn't fit in
        `max_width` px at `font_tuple` — a hard backstop against clipping
        that doesn't depend on guessing exactly how wide any given
        system renders a name. This app requests the 'Inter' font, which
        isn't guaranteed to be installed everywhere; Tk silently
        substitutes a fallback when it isn't, and fallback fonts can
        render meaningfully wider than Inter does, so the box/column
        geometry above being "wide enough" for Inter is not by itself a
        guarantee for every machine this runs on."""
        weight = 'bold' if len(font_tuple) > 2 and font_tuple[2] == 'bold' else 'normal'
        f = tkfont.Font(family=font_tuple[0], size=font_tuple[1], weight=weight)
        if f.measure(text) <= max_width:
            return text
        ellipsis = '…'
        lo, hi = 0, len(text)
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if f.measure(text[:mid] + ellipsis) <= max_width:
                lo = mid
            else:
                hi = mid - 1
        return text[:lo].rstrip() + ellipsis if lo > 0 else ellipsis

    def _logo_label(self, parent: tk.Widget, team: str, bg: str, max_size: int, pad_left: int) -> None:
        #a team with no PNG yet just yields None — skipped, not an error (see gui/logos/loader.py)
        logo = get_team_logo(TEAM_REGISTRY[team].id, max_size=max_size)
        if logo is None:
            return
        lbl = tk.Label(parent, image=logo, bg=bg)
        lbl.image = logo   #extra ref so Tkinter can't garbage-collect it
        lbl.pack(side='left', padx=(pad_left, 0))

    def _matchup_box(self, canvas: tk.Canvas, x_center: int, y_center: int,
                     team_a: str, team_b: str, winner: str, highlight: bool = False) -> None:
        box = ctk.CTkFrame(canvas, fg_color=C_HDR, corner_radius=4,
                          border_width=2 if highlight else 1,
                          border_color=C_GOLD if highlight else C_SASH)
        available = _BOX_W - (_MARK_W + _MARK_PAD) - (_LOGO_W + _LOGO_PAD) - _TEXT_PAD * 2
        for team in (team_a, team_b):
            is_winner = (team == winner)
            row_bg = C_DIV_LEAD if is_winner else C_HDR
            r = ctk.CTkFrame(box, fg_color=row_bg, corner_radius=0)
            r.pack(fill='both', expand=True)
            mark = ctk.CTkLabel(r, text='✓' if is_winner else '', fg_color=row_bg,
                                text_color=C_DARK, font=FONT_NORMAL_BOLD, width=_MARK_W, anchor='e')
            mark.pack(side='left', padx=(_MARK_PAD, 0))
            self._logo_label(r, team, row_bg, max_size=_LOGO_W, pad_left=_LOGO_PAD)
            font = FONT_NORMAL_BOLD if is_winner else FONT_NORMAL
            color = C_DARK if is_winner else C_GRAY
            display_name = self._fit_team_name(font, team, available)
            ctk.CTkLabel(r, text=display_name, fg_color=row_bg, text_color=color,
                        font=font, anchor='w', padx=_TEXT_PAD).pack(side='left', fill='x')
        canvas.create_window(x_center, y_center, window=box, width=_BOX_W, height=_BOX_H)

    def _draw_world_series(self, canvas: tk.Canvas, bracket: PlayoffBracketResult) -> None:
        canvas.create_text(_WS_X, _WS_Y - _WS_BOX_H // 2 - 16, text='World Series',
                           fill=C_DARK, font=(FONT_HEADER[0], FONT_HEADER[1], 'bold'))

        box = ctk.CTkFrame(canvas, fg_color=C_WHITE, corner_radius=4,
                          border_width=2, border_color=C_GOLD)
        available = (_WS_BOX_W - (_WS_TROPHY_W + _WS_TROPHY_PAD) - (_WS_LOGO_W + _WS_LOGO_PAD)
                    - _TEXT_PAD * 2 - _WS_HOME_AWAY_RESERVED)
        for team, home_away in ((bracket.ws_host, 'Home-field'), (bracket.ws_guest, '')):
            is_champ = (team == bracket.champion)
            bg = C_DIV_LEAD if is_champ else C_WHITE
            row = ctk.CTkFrame(box, fg_color=bg, corner_radius=0)
            row.pack(fill='both', expand=True)
            trophy = '🏆' if is_champ else ''
            font = FONT_NORMAL_BOLD if is_champ else FONT_NORMAL
            color = C_GOLD if is_champ else C_MID
            ctk.CTkLabel(row, text=trophy, fg_color=bg, text_color=color, width=_WS_TROPHY_W,
                        font=font, anchor='w').pack(side='left', padx=(_WS_TROPHY_PAD, 0))
            self._logo_label(row, team, bg, max_size=_WS_LOGO_W, pad_left=_WS_LOGO_PAD)
            display_name = self._fit_team_name(font, team, available)
            ctk.CTkLabel(row, text=display_name, fg_color=bg, text_color=color,
                        font=font, anchor='w', padx=_TEXT_PAD).pack(side='left', fill='both', expand=True)
            if home_away:
                ctk.CTkLabel(row, text=home_away, fg_color=bg, text_color=C_GRAY,
                            font=FONT_SMALL, anchor='e', padx=10).pack(side='right')
        canvas.create_window(_WS_X, _WS_Y, window=box, width=_WS_BOX_W, height=_WS_BOX_H)

    def _build_footer(self, parent: tk.Widget) -> None:
        footer_text = ('This is the single most common exact bracket across every simulation, '
                      'not a guaranteed result — see the count above. With so many possible '
                      'bracket combinations, even "the most common" one is often a small slice '
                      'of all simulations.')
        tied = self._result.projected_bracket_tied_count
        if tied > 1:
            footer_text += (f' When brackets are tied for the top spot (as {tied:,} were here), '
                           'the one shown is picked by whichever tied champion had the best '
                           'overall championship odds — not an arbitrary pick.')
        ctk.CTkLabel(
            parent, fg_color=C_BG, text_color=C_GRAY, font=FONT_SMALL,
            text=footer_text, wraplength=1400, justify='left',
        ).pack(pady=(6, 16), padx=20)
