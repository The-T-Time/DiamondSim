# ==============================================================================
# STANDINGS TAB
# gui/standings_tab/tab.py
#
# Division tables (GB, Last 10, streak, playoff odds), the Wild Card race
# with its cut-line, and a sortable/searchable Table view — toggled by
# league/view buttons at the top.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

from config import WC_SPOTS
from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.simulation_result import SimulationResult
from gui.logos import get_team_logo
from gui.standings_tab.column_specs import DIV_COLS, WC_COLS
from gui.standings_tab.standings_computation import (
    LEAGUE_DIVS, compute_playoff_picture, division_rows, last10, row_bg, row_fg,
    sort_key, team_game_results, wildcard_rows,
)
from gui.widgets import (
    C_BG, C_BLUE, C_BLUE_DARK, C_DARK, C_DIV_LEAD, C_GOLD, C_GRAY, C_GREEN,
    C_GREEN_DARK, C_HDR, C_HEADER_BAR, C_HEADER_TEXT, C_LIGHT_GRAY, C_MID,
    C_ORANGE, C_PANEL, C_RED, C_SASH, C_WC_IN,
    FONT_HEADER, FONT_MEDIUM_BOLD, FONT_SMALL, FONT_SMALL_BOLD, FONT_TINY,
    Column, SortableTable, create_scrollable_frame,
)

def _measure_col_widths(col_specs: list[tuple[str, int, str]], rows: list[dict],
                        cell_texts: list[list[str]]) -> list[int]:
    """
    Real pixel width for each column, measured from the actual header text
    and every cell that will be shown — not a guessed per-character pixel
    constant. `cell_texts[i]` is the list of formatted strings that will
    appear in column i across all `rows`.

    Why this replaces a fixed per-character constant: a guess like "7px per
    character" is only right for one specific font/size. Whenever the
    Treeview/label font size changes (as it did when the app's base font
    was bumped for readability), every width tuned against the old guess
    is wrong — some columns clip text, and the cumulative error across 8
    columns Ã 3 division panels is exactly what pushed the AL West panel
    off the right edge of the window. Measuring the real font's rendered
    width is correct at any font size, so this fix doesn't need retuning
    the next time a font size changes.
    """
    header_font = tkfont.Font(family='Inter', size=FONT_SMALL_BOLD[1], weight='bold')
    body_font = tkfont.Font(family='Inter', size=FONT_SMALL[1])
    widths = []
    for i, (col_name, _fallback_w, _anchor) in enumerate(col_specs):
        w = header_font.measure(col_name)
        for text in cell_texts[i]:
            w = max(w, body_font.measure(text))
        widths.append(w + 16)   #padding to match the padx=2 CTkLabel padding on each side plus breathing room
    return widths


class StandingsTab(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, result: SimulationResult) -> None:
        super().__init__(parent, fg_color=C_BG, corner_radius=0)
        self._result       = result
        self._league       = 'AL'
        self._view         = 'divisions'      #'divisions' | 'table'
        self._simulated    = False            #False = Current, True = Simulated (projected)
        self._game_results = team_game_results(result.played_games)
        self._picture      = compute_playoff_picture(result)
        self._resize_after_id: str | None = None
        self._build()

    #── chrome ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        #Header bar with legend + Ctrl+C hint
        bar = ctk.CTkFrame(self, fg_color=C_HEADER_BAR, corner_radius=0)
        bar.pack(fill='x')
        ctk.CTkLabel(bar, text='Standings', fg_color=C_HEADER_BAR, text_color=C_HEADER_TEXT,
                    font=FONT_HEADER).pack(side='left', padx=14, pady=7)

        hint = ctk.CTkLabel(bar, text='Ctrl+C  copy standings',
                           fg_color=C_HEADER_BAR, text_color='#5d8aa8', font=FONT_TINY, cursor='hand2')
        hint.pack(side='right', padx=14, pady=7)
        hint.bind('<Button-1>', lambda _: self._copy_standings())

        leg = ctk.CTkFrame(bar, fg_color=C_HEADER_BAR, corner_radius=0)
        leg.pack(side='right', padx=14, pady=7)
        for colour, label in [(C_DIV_LEAD, 'Div Leader'), (C_WC_IN, 'Wild Card In')]:
            ctk.CTkFrame(leg, fg_color=colour, width=12, height=12,
                        border_width=1, corner_radius=0).pack(side='left', padx=(6, 2))
            ctk.CTkLabel(leg, text=label, fg_color=C_HEADER_BAR, text_color=C_GRAY,
                        font=FONT_TINY).pack(side='left', padx=(0, 4))

        #League toggle
        toggle_bar = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0)
        toggle_bar.pack(fill='x')
        self._al_btn = ctk.CTkButton(
            toggle_bar, text='American League', font=FONT_MEDIUM_BOLD,
            corner_radius=0, cursor='hand2',
            command=lambda: self._switch_league('AL'),
        )
        self._nl_btn = ctk.CTkButton(
            toggle_bar, text='National League', font=FONT_MEDIUM_BOLD,
            corner_radius=0, cursor='hand2',
            command=lambda: self._switch_league('NL'),
        )
        self._al_btn.pack(side='left', padx=(12, 2), pady=4)
        self._nl_btn.pack(side='left', padx=2, pady=4)

        #View toggle (Divisions ↔ sortable Table), right-aligned
        self._div_view_btn = ctk.CTkButton(
            toggle_bar, text='Divisions', font=FONT_SMALL_BOLD,
            corner_radius=0, cursor='hand2',
            command=lambda: self._switch_view('divisions'),
        )
        self._tbl_view_btn = ctk.CTkButton(
            toggle_bar, text='Table', font=FONT_SMALL_BOLD,
            corner_radius=0, cursor='hand2',
            command=lambda: self._switch_view('table'),
        )
        self._tbl_view_btn.pack(side='right', padx=(2, 12), pady=4)
        self._div_view_btn.pack(side='right', padx=2, pady=4)

        #Current ↔ Simulated toggle — only meaningful if this run actually
        #has projected (averaged-across-sims) stats to show.
        if self._result.projected_team_stats:
            sim_bar = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0)
            sim_bar.pack(fill='x')
            ctk.CTkLabel(sim_bar, text='Showing:', fg_color=C_PANEL, text_color=C_MID,
                        font=FONT_SMALL).pack(side='left', padx=(12, 6), pady=(0, 4))
            self._current_btn = ctk.CTkButton(
                sim_bar, text='Current', font=FONT_SMALL_BOLD,
                corner_radius=0, cursor='hand2',
                command=lambda: self._switch_simulated(False),
            )
            self._simulated_btn = ctk.CTkButton(
                sim_bar, text='Simulated (end of season)', font=FONT_SMALL_BOLD,
                corner_radius=0, cursor='hand2',
                command=lambda: self._switch_simulated(True),
            )
            self._current_btn.pack(side='left', padx=2, pady=(0, 4))
            self._simulated_btn.pack(side='left', padx=2, pady=(0, 4))
        else:
            self._current_btn = self._simulated_btn = None

        #Content container — repopulated on every league/view switch.
        self._content = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self._content.pack(fill='both', expand=True)

        #Ctrl+C at the window level
        self.bind('<Map>',   lambda _: self.winfo_toplevel().bind(
            '<Control-c>', lambda e: self._copy_standings()))
        self.bind('<Unmap>', lambda _: self._try_unbind('<Control-c>'))

        #The Divisions view's panel-per-row count is computed from the
        #window's current width (see _render_league) — without this, it's
        #only ever right for whatever size the window happened to be at
        #first render, and dragging the window wider/narrower afterward
        #leaves the same panel count locked in rather than reflowing.
        #Debounced the same way gui/graph_tab/tab.py debounces its own
        #resize handler: a live window drag fires many Configure events a
        #second, and only the size it settles on actually matters.
        self.bind('<Configure>', self._on_resize)

        self._render()

    def _try_unbind(self, seq: str) -> None:
        try:
            self.winfo_toplevel().unbind(seq)
        except Exception:
            pass

    def _on_resize(self, _event: tk.Event) -> None:
        #Table view's Treeview already fills its space responsively via
        #pack(fill='both', expand=True) — only Divisions needs an actual
        #re-layout, so skip the (comparatively expensive) full re-render
        #unless that's the active view.
        if self._view != 'divisions':
            return
        if self._resize_after_id:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(200, self._apply_resize)

    def _apply_resize(self) -> None:
        self._resize_after_id = None
        self._render()

    #── league toggle ─────────────────────────────────────────────────────────

    def _switch_league(self, league: str) -> None:
        self._league = league
        self._render()

    def _switch_view(self, view: str) -> None:
        self._view = view
        self._render()

    def _switch_simulated(self, simulated: bool) -> None:
        self._simulated = simulated
        self._picture = compute_playoff_picture(self._result, simulated=simulated)
        self._render()

    def _render(self) -> None:
        league = self._league
        for btn, lg in [(self._al_btn, 'AL'), (self._nl_btn, 'NL')]:
            btn.configure(fg_color=C_BLUE if lg == league else C_PANEL,
                         text_color=C_HEADER_TEXT if lg == league else C_DARK)
        for btn, v in [(self._div_view_btn, 'divisions'), (self._tbl_view_btn, 'table')]:
            btn.configure(fg_color=C_HEADER_BAR if v == self._view else C_PANEL,
                         text_color=C_HEADER_TEXT if v == self._view else C_DARK)
        if self._current_btn is not None:
            for btn, sim in [(self._current_btn, False), (self._simulated_btn, True)]:
                btn.configure(fg_color=C_GREEN if sim == self._simulated else C_PANEL,
                             text_color=C_HEADER_TEXT if sim == self._simulated else C_DARK)

        for w in self._content.winfo_children():
            w.destroy()

        if self._view == 'table':
            self._render_table(league)
            return

        self._canvas, self._inner = create_scrollable_frame(self._content)
        self._canvas.scroll_to_top()
        self._render_league(league)

    #── sortable table view ─────────────────────────────────────────────────────

    def _render_table(self, league: str) -> None:
        has_ws = bool(self._result.world_series_odds)
        teams = [t for t in ALL_TEAMS if TEAM_REGISTRY[t].league == league]
        win_loss = self._result.projected_win_loss if self._simulated else self._result.win_loss
        pct = self._result.projected_pct if self._simulated else self._result.pct
        rows: list[dict] = []
        for t in teams:
            w, l = win_loss(t)
            rows.append({
                'team':   t,
                'div':    TEAM_REGISTRY[t].division,
                'div_sh': TEAM_REGISTRY[t].division.split()[-1],
                'W': w, 'L': l,
                'pct':    pct(t),
                'odds':   self._result.playoff_odds.get(t, 0.0),
                'ws':     self._result.world_series_odds.get(t, 0.0),
                'l10':    last10(self._game_results.get(t, [])),
                'l10_w':  self._game_results.get(t, [])[-10:].count('W'),
            })

        cols = [
            Column('rank', '#',    34, 'center', None,                 lambda r: str(r['_rank'])),
            Column('team', 'Team',  0, 'w',      lambda r: r['team'],  lambda r: r['team']),
            Column('div',  'Div',  70, 'w',      lambda r: r['div'],   lambda r: r['div_sh']),
            Column('w',    'W',    40, 'e',      lambda r: r['W'],     lambda r: f"{r['W']:.0f}" if self._simulated else str(r['W'])),
            Column('l',    'L',    40, 'e',      lambda r: r['L'],     lambda r: f"{r['L']:.0f}" if self._simulated else str(r['L'])),
            Column('pct',  'PCT',  58, 'e',      lambda r: r['pct'],   lambda r: f"{r['pct']:.3f}"),
            Column('l10',  'L10',  56, 'center', lambda r: r['l10_w'], lambda r: r['l10']),
            Column('odds', 'Playoff%', 74, 'e',  lambda r: r['odds'],  lambda r: f"{r['odds']:.1f}%"),
        ]
        if has_ws:
            cols.append(
                Column('ws', 'WS%', 64, 'e', lambda r: r['ws'], lambda r: f"{r['ws']:.1f}%")
            )

        table = SortableTable(
            self._content, cols, rows,
            default_sort='pct', default_asc=False,
            show_search=True, search_key='team',
            filter_key='div', filter_values=LEAGUE_DIVS[league], filter_label='Division',
            name_col_w=190, style_name='StandTable.Treeview',
            row_image=lambda r: get_team_logo(TEAM_REGISTRY[r['team']].id, max_size=22),
        )
        table.pack(fill='both', expand=True, padx=8, pady=6)

    #── render ────────────────────────────────────────────────────────────────

    def _render_league(self, league: str) -> None:
        divs = LEAGUE_DIVS[league]
        simulated = self._simulated

        div_leaders: list[str] = []
        rows_by_div: dict[str, list[dict]] = {}
        for div in divs:
            d_teams = sorted([t for t in ALL_TEAMS if TEAM_REGISTRY[t].division == div],
                             key=lambda t: sort_key(self._result, t, simulated), reverse=True)
            div_leaders.append(d_teams[0])
            rows_by_div[div] = division_rows(self._result, div, self._game_results, simulated)

        #Column widths are measured once across every division's rows (not
        #per-division) so all panels end up the same width and line up —
        #see _measure_col_widths for why this replaced a fixed per-
        #character pixel guess.
        all_rows = [r for div_rows in rows_by_div.values() for r in div_rows]
        cell_texts: list[list[str]] = [
            [r['team'] + (' ★' if self._picture.get(r['team']) == 'div_leader' else
                          ' •' if self._picture.get(r['team']) == 'wc_in' else '') for r in all_rows],
            [str(r['w']) for r in all_rows],
            [str(r['l']) for r in all_rows],
            [f"{r['pct']:.3f}" for r in all_rows],
            [r['gb'] for r in all_rows],
            [r['last10'] for r in all_rows],
            [r['streak'] for r in all_rows],
            [f"{r['odds']:.1f}%" for r in all_rows],
        ]
        col_widths = _measure_col_widths(DIV_COLS, all_rows, cell_texts)

        #Three division tables, side-by-side when there's room for them —
        #CTkScrollableFrame only scrolls vertically, so a row wider than the
        #viewport doesn't get a horizontal scrollbar, it just gets silently
        #clipped (this is what was cutting AL West down to 2 visible
        #columns). Measuring how many panels actually fit and wrapping the
        #rest onto additional rows keeps every column reachable regardless
        #of window size or font/DPI scaling.
        div_row = ctk.CTkFrame(self._inner, fg_color=C_BG, corner_radius=0)
        div_row.pack(fill='x', padx=10, pady=(14, 6))

        #panel_w is the raw label-content width (no extra buffer added —
        #the measured empirical frame reqwidth matches col_widths' sum
        #closely enough that padding shouldn't be double-counted here);
        #the +16 below is each panel's own grid padx=8-per-side spacing.
        panel_w = sum(col_widths)
        #The toplevel's width is used rather than self._inner's: _inner
        #(the CTkScrollableFrame just created above) hasn't had a geometry
        #pass yet at this point in construction and reports an unreliable
        #near-zero width, whereas the toplevel already has its real size
        #from the explicit .geometry() call made when the window opened
        #(see gui/results_window/window.py's update_idletasks() call,
        #which is what makes that value trustworthy immediately rather
        #than only after the window's first real event-loop pass).
        #-40 gives a little room for the scrollable frame's own scrollbar
        #and outer padding.
        #
        #Floored at the window's own configured minsize rather than 0:
        #if winfo_width() is ever still unreliable (e.g. this tab gets
        #reused somewhere without that update_idletasks() call), a
        #near-zero width used to silently collapse every division onto
        #its own row instead of the intended side-by-side layout —
        #falling back to the window's guaranteed-minimum width keeps that
        #from happening even if the real width can't be read yet.
        toplevel = self.winfo_toplevel()
        min_w, _min_h = toplevel.wm_minsize()
        avail_w = max(toplevel.winfo_width(), min_w) - 40
        per_row = max(1, min(len(divs), avail_w // (panel_w + 16))) if panel_w else len(divs)

        for i, div in enumerate(divs):
            row_idx, col_idx = divmod(i, per_row)
            self._make_division_block(div_row, div, rows_by_div[div], col_idx, row_idx, col_widths)

        #Separator
        ctk.CTkFrame(self._inner, fg_color=C_SASH, height=2, corner_radius=0).pack(
            fill='x', padx=12, pady=(4, 10))

        #Wild Card table
        wc_rows = wildcard_rows(self._result, league, div_leaders, self._game_results, simulated)
        self._make_wildcard_block(self._inner, league, wc_rows)

    #── division block ────────────────────────────────────────────────────────

    def _make_division_block(self, parent: tk.Widget, division: str, rows: list[dict],
                             col_idx: int, row_idx: int, col_widths: list[int]) -> None:
        title_bg = C_BLUE_DARK if division.startswith('AL') else C_GREEN_DARK
        frame = ctk.CTkFrame(parent, fg_color=C_BG, border_width=1, corner_radius=0)
        frame.grid(row=row_idx, column=col_idx, padx=8, pady=(0, 8), sticky='n')

        ctk.CTkLabel(frame, text=division, fg_color=title_bg, text_color=C_HEADER_TEXT,
                    font=FONT_MEDIUM_BOLD, anchor='w', padx=8).pack(fill='x', pady=5)

        #Column headers
        hdr = ctk.CTkFrame(frame, fg_color=C_HDR, corner_radius=0)
        hdr.pack(fill='x')
        for (col_name, _fallback_w, anchor), w in zip(DIV_COLS, col_widths):
            a = anchor if anchor != 'c' else 'center'
            ctk.CTkLabel(hdr, text=col_name, fg_color=C_HDR, text_color=C_DARK,
                        font=FONT_SMALL_BOLD, width=w, anchor=a,
                        padx=2).pack(side='left')

        for i, row in enumerate(rows):
            team   = row['team']
            status = self._picture.get(team, 'contender')
            bg, fg = row_bg(status, i), row_fg(status)

            odds_fg = (C_GOLD   if status == 'div_leader' else
                       C_GREEN  if status == 'wc_in'      else
                       C_ORANGE if row['odds'] >= 10       else C_RED)

            streak_fg = (C_GREEN if row['streak'].startswith('W') else
                         C_RED   if row['streak'].startswith('L') else C_MID)

            rank_marker = ' ★' if status == 'div_leader' else (' •' if status == 'wc_in' else '')

            r = ctk.CTkFrame(frame, fg_color=bg, corner_radius=0)
            r.pack(fill='x')
            logo = get_team_logo(TEAM_REGISTRY[team].id, max_size=18)
            if logo is not None:
                logo_lbl = tk.Label(r, image=logo, bg=bg)
                logo_lbl.image = logo   #extra ref so Tkinter can't garbage-collect it
                logo_lbl.pack(side='left', padx=(4, 0))
            cells: list[tuple[str, int, str, str]] = [
                (row['team'] + rank_marker, col_widths[0], 'w',      fg),
                (str(row['w']),             col_widths[1], 'e',      fg),
                (str(row['l']),             col_widths[2], 'e',      fg),
                (f"{row['pct']:.3f}",       col_widths[3], 'e',      fg),
                (row['gb'],                 col_widths[4], 'e',      fg),
                (row['last10'],             col_widths[5], 'center', C_MID),
                (row['streak'],             col_widths[6], 'center', streak_fg),
                (f"{row['odds']:.1f}%",     col_widths[7], 'e',      odds_fg),
            ]
            for text, w, anchor, cell_fg in cells:
                bold = (text == f"{row['odds']:.1f}%" or
                        text == row['streak'] or
                        rank_marker and text.endswith(rank_marker))
                font = FONT_SMALL_BOLD if bold else FONT_SMALL
                ctk.CTkLabel(r, text=text, fg_color=bg, text_color=cell_fg,
                            font=font, width=w, anchor=anchor,
                            padx=2).pack(side='left', pady=2)

    #── wild card block ───────────────────────────────────────────────────────

    def _make_wildcard_block(self, parent: tk.Widget,
                             league: str, rows: list[dict]) -> None:
        title_bg = C_BLUE_DARK if league == 'AL' else C_GREEN_DARK
        outer = ctk.CTkFrame(parent, fg_color=C_BG, corner_radius=0)
        outer.pack(fill='x', padx=18, pady=(0, 16))

        ctk.CTkLabel(outer, text=f'{league} Wild Card Race',
                    fg_color=title_bg, text_color=C_HEADER_TEXT, font=FONT_MEDIUM_BOLD,
                    anchor='w', padx=8).pack(fill='x', pady=5)

        #Measured from the actual rows about to be shown — see
        #_measure_col_widths for why this replaced a fixed per-character
        #pixel guess.
        cell_texts: list[list[str]] = [
            [r['team'] + (' •' if r['in_spot'] else '') for r in rows],
            [r['div'].split()[-1] for r in rows],
            [str(r['w']) for r in rows],
            [str(r['l']) for r in rows],
            [f"{r['pct']:.3f}" for r in rows],
            [r['wcgb'] for r in rows],
            [f"{r['odds']:.1f}%" for r in rows],
        ]
        col_widths = _measure_col_widths(WC_COLS, rows, cell_texts)

        hdr = ctk.CTkFrame(outer, fg_color=C_HDR, corner_radius=0)
        hdr.pack(fill='x')
        for (col_name, _fallback_w, anchor), w in zip(WC_COLS, col_widths):
            ctk.CTkLabel(hdr, text=col_name, fg_color=C_HDR, text_color=C_DARK,
                        font=FONT_SMALL_BOLD, width=w, anchor=anchor,
                        padx=2).pack(side='left')

        cutline_drawn = False
        for i, row in enumerate(rows):
            if i == WC_SPOTS and not cutline_drawn:
                ctk.CTkFrame(outer, fg_color=C_RED, height=2, corner_radius=0).pack(fill='x')
                ctk.CTkLabel(outer, text='─── Wild Card cut line ───',
                            fg_color='#fadbd8', text_color='#922b21',
                            font=FONT_SMALL_BOLD, anchor='w', padx=8).pack(fill='x')
                cutline_drawn = True

            team   = row['team']
            status = self._picture.get(team, 'contender')
            bg, fg = row_bg(status, i), row_fg(status)
            odds_fg = C_GREEN if row['in_spot'] else (C_ORANGE if row['odds'] >= 10 else C_RED)
            marker  = ' •' if row['in_spot'] else ''

            r = ctk.CTkFrame(outer, fg_color=bg, corner_radius=0)
            r.pack(fill='x')
            logo = get_team_logo(TEAM_REGISTRY[team].id, max_size=18)
            if logo is not None:
                logo_lbl = tk.Label(r, image=logo, bg=bg)
                logo_lbl.image = logo   #extra ref so Tkinter can't garbage-collect it
                logo_lbl.pack(side='left', padx=(4, 0))
            cells: list[tuple[str, int, str, str]] = [
                (team + marker,               col_widths[0], 'w',      fg),
                (row['div'].split()[-1],       col_widths[1], 'w',      C_GRAY),
                (str(row['w']),                col_widths[2], 'e',      fg),
                (str(row['l']),                col_widths[3], 'e',      fg),
                (f"{row['pct']:.3f}",          col_widths[4], 'e',      fg),
                (row['wcgb'],                  col_widths[5], 'e',      fg),
                (f"{row['odds']:.1f}%",        col_widths[6], 'e',      odds_fg),
            ]
            for text, w, anchor, cell_fg in cells:
                bold = text.endswith('%') or text.endswith(marker)
                font = FONT_SMALL_BOLD if bold else FONT_SMALL
                ctk.CTkLabel(r, text=text, fg_color=bg, text_color=cell_fg,
                            font=font, width=w, anchor=anchor,
                            padx=2).pack(side='left', pady=2)

        ctk.CTkLabel(outer,
                    text='★ = Division Leader   • = Wild Card Position   '
                         'Odds = Monte Carlo playoff probability   Ctrl+C = copy standings',
                    fg_color=C_LIGHT_GRAY, text_color=C_GRAY,
                    font=FONT_TINY, anchor='w', padx=8).pack(fill='x', pady=4)

    #── copy to clipboard ─────────────────────────────────────────────────────

    def _copy_standings(self) -> None:
        divs = LEAGUE_DIVS[self._league]
        simulated = self._simulated
        div_leaders: list[str] = []
        for div in divs:
            d_teams = sorted([t for t in ALL_TEAMS if TEAM_REGISTRY[t].division == div],
                             key=lambda t: sort_key(self._result, t, simulated), reverse=True)
            div_leaders.append(d_teams[0])

        label = 'Projected End-of-Season' if simulated else 'Current'
        lines = [f"{self._league} Standings — {label}  (Playoff Sim {self._result.season})",
                 '=' * 70]
        for div in divs:
            lines.append(f"\n{div}")
            lines.append(f"{'Team':<26} {'W':>4} {'L':>4} {'PCT':>6} "
                         f"{'GB':>6} {'L10':>5} {'Strk':>5} {'Odds':>7}")
            lines.append('-' * 70)
            for row in division_rows(self._result, div, self._game_results, simulated):
                lines.append(
                    f"{row['team']:<26} {row['w']:>4.0f} {row['l']:>4.0f} "
                    f"{row['pct']:>6.3f} {row['gb']:>6} {row['last10']:>5} "
                    f"{row['streak']:>5} {row['odds']:>6.1f}%"
                )

        lines += [f"\n{self._league} Wild Card Race", '-' * 70,
                  f"{'Team':<26} {'Div':<10} {'W':>4} {'L':>4} "
                  f"{'PCT':>6} {'WC GB':>6} {'Odds':>7}"]
        wc_rows = wildcard_rows(self._result, self._league, div_leaders, self._game_results, simulated)
        for i, row in enumerate(wc_rows):
            if i == WC_SPOTS:
                lines.append('  --- cut line ---')
            lines.append(
                f"{row['team']:<26} {row['div']:<10} {row['w']:>4.0f} {row['l']:>4.0f} "
                f"{row['pct']:>6.3f} {row['wcgb']:>6} {row['odds']:>6.1f}%"
            )

        text = '\n'.join(lines)
        self.clipboard_clear()
        self.clipboard_append(text)
        self._flash_copied()

    def _flash_copied(self) -> None:
        """Briefly shows a 'Copied!' toast in the header area."""
        toast = ctk.CTkLabel(self, text='  ✓ Copied to clipboard  ',
                            fg_color=C_GREEN, text_color=C_HEADER_TEXT, font=FONT_SMALL_BOLD)
        toast.place(relx=0.5, rely=0.05, anchor='center')
        self.after(1800, toast.destroy)
