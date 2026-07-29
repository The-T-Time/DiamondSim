# ==============================================================================
# TEAMS TAB
# gui/teams_tab/tab.py
#
# Left pane: the 30-team list (ttk.Treeview). Right pane: team header card
# + Game Log / Upcoming sub-tabs. A few widgets stay classic tkinter
# (PanedWindow, Treeview, right-click Menu, the logo Label) since
# customtkinter has no equivalent — they coexist fine inside CTk frames.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

import customtkinter as ctk

from config import TEAMS_DEFAULT_SORT
from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.simulation_result import SimulationResult
from gui.logos import get_team_logo
from gui.teams_tab.formatters import TEAM_COL_W, TV_COLS, pct_str, sort_key
from gui.teams_tab.game_log import build_game_log
from gui.teams_tab.upcoming import build_upcoming
from gui.widgets import (
    C_BG, C_BLUE, C_DARK, C_GRAY, C_GREEN, C_HDR, C_HEADER_BAR, C_HEADER_TEXT,
    C_HOVER, C_PANEL, C_RED, C_ROW_ALT, C_SASH, C_SELECTED, C_WHITE,
    FONT_NORMAL, FONT_SMALL, FONT_SMALL_BOLD, FONT_TINY, FONT_TITLE,
    make_header_bar, make_stat_card, dpi_scale,
)


class TeamsTab(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, result: SimulationResult) -> None:
        super().__init__(parent, fg_color=C_BG, corner_radius=0)
        self._result         = result
        self._selected_team: str | None         = None
        self._sort_col       = TEAMS_DEFAULT_SORT
        self._sort_asc       = (TEAMS_DEFAULT_SORT == 'name')
        self._tree: ttk.Treeview | None         = None
        self._tree_ids: dict[str, str]          = {}   #team → item iid
        self._search_bar: ctk.CTkFrame | None    = None
        self._search_var: tk.StringVar | None   = None
        self._search_entry: ctk.CTkEntry | None  = None
        self._search_visible: bool              = False
        self._pane: tk.PanedWindow | None       = None
        self._build()

    #── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        make_header_bar(self, 'Teams',
                        subtitle='Click a team · drag divider · ↑↓ navigate · Ctrl+F search')

        #── Measure actual font width of the longest team name ────────────────
        #Must happen AFTER a Tk root exists (which it does here).
        #This gives us the exact pixel width needed for the name column so
        #there's no blank space between the last character and the stat columns.
        #
        #Measured at the SAME font/size the Treeview style actually renders
        #(see dpi_scale() in gui/widgets/table.py) — measuring at a stale,
        #smaller hardcoded size here would under-size the column and clip
        #team names ("Milwaukee Brewers" -> "Milwaukee Brev") even though
        #the Treeview itself is rendering at the correct, bigger size.
        scale = dpi_scale(self)
        _tree_font_size = round(12 * scale)
        _mf = tkfont.Font(family='Inter', size=_tree_font_size, weight='bold')
        self._name_col_w: int = max(_mf.measure(t) for t in ALL_TEAMS) + 10  #+5px padding each side
        _scrollbar_w   : int  = 18   #typical Treeview scrollbar width
        #Stat column widths were hand-tuned for the old 9pt Treeview font
        #(see formatters.py) — scaled by the same ratio the font grew, for
        #the same reason column widths are scaled in gui/widgets/table.py.
        _width_scale   : float = _tree_font_size / 9
        self._stat_col_w: dict[str, int] = {
            c[0]: round(c[3] * _width_scale) for c in TV_COLS[1:]
        }
        _stat_total    : int  = sum(self._stat_col_w.values())

        #Sash initial position = name col + all stat cols + scrollbar
        self._default_left_w: int = self._name_col_w + _stat_total + _scrollbar_w
        #Left sash stop = name col + scrollbar only (all stats slide off)
        _left_minsize: int = self._name_col_w + _scrollbar_w

        #── opaqueresize=False: show a ghost sash during drag, resize on release
        #This is the definitive fix for Windows smearing — the pane content
        #never changes during the drag so there's nothing to smear. Kept as
        #classic tk.PanedWindow — customtkinter has no equivalent widget.
        pane = tk.PanedWindow(self, orient='horizontal',
                              sashrelief='groove', sashwidth=8, bg=C_SASH,
                              opaqueresize=False)
        pane.pack(fill='both', expand=True)
        self._pane = pane

        left  = ctk.CTkFrame(pane, fg_color=C_PANEL, corner_radius=0)
        right = ctk.CTkFrame(pane, fg_color=C_BG, corner_radius=0)
        pane.add(left,  minsize=_left_minsize, stretch='never')
        pane.add(right, minsize=320,           stretch='always')

        self._build_list_pane(left)
        self._right_frame = right
        self._show_placeholder()

        self.after(50, self._place_sash)
        self.bind('<Map>',   self._register_shortcuts)
        self.bind('<Unmap>', self._unregister_shortcuts)

    def _place_sash(self) -> None:
        try:
            self._pane.sash_place(0, self._default_left_w, 1)
        except Exception:
            pass

    #── LEFT: Treeview list pane ──────────────────────────────────────────────

    def _build_list_pane(self, parent: tk.Widget) -> None:
        #── Ctrl+F search bar (hidden until activated) ────────────────────────
        #height=1 avoids CTkFrame's own default of height=200: with the
        #search bar hidden, top_bar has no visible children, and without an
        #explicit height it would still claim a 200px blank strip above the
        #team list (CTkFrame doesn't auto-shrink to "no children" the way a
        #bare tk.Frame would). height=1 lets it collapse when empty and
        #still grow to fit the search bar when shown.
        top_bar = ctk.CTkFrame(parent, fg_color=C_PANEL, corner_radius=0, height=1)
        top_bar.pack(fill='x', side='top')

        self._search_var = tk.StringVar()
        self._search_bar = ctk.CTkFrame(top_bar, fg_color=C_HDR, corner_radius=0)
        ctk.CTkLabel(self._search_bar, text='🔍', fg_color=C_HDR,
                    font=FONT_SMALL).pack(side='left', padx=(6, 2), pady=2)
        entry = ctk.CTkEntry(self._search_bar, textvariable=self._search_var,
                            font=FONT_SMALL, width=140,
                            fg_color=C_WHITE, text_color=C_DARK)
        entry.pack(side='left', padx=2, pady=2)
        entry.bind('<KeyRelease>', self._on_search_key)
        entry.bind('<Escape>',     lambda e: self._hide_search())
        ctk.CTkButton(self._search_bar, text='✕', font=FONT_TINY,
                     fg_color=C_HDR, text_color=C_GRAY, hover_color=C_ROW_ALT,
                     cursor='hand2', width=28, height=22,
                     command=self._hide_search).pack(side='left', padx=2, pady=2)
        self._search_entry = entry

        #── Treeview style ────────────────────────────────────────────────────
        #Font/rowheight are scaled by the same DPI factor CTk applies to its
        #own widgets — plain ttk.Treeview is invisible to CTk's automatic
        #scaling, so left unscaled it renders far smaller than the CTk
        #widgets around it on any scaled-DPI display (see gui/widgets/table.py's
        #dpi_scale() for the full explanation).
        scale = dpi_scale(self)
        sty = ttk.Style()
        sty.theme_use('clam')   #'clam' honors rowheight/fieldbackground overrides reliably; native themes often ignore them
        sty.configure('Teams.Treeview',
                       font=('Inter', round(12 * scale)),
                       rowheight=round(30 * scale),
                       background=C_WHITE,
                       fieldbackground=C_WHITE,
                       foreground=C_DARK,
                       borderwidth=0,
                       padding=[2, 0, 2, 0])   #tighter cell padding: left/top/right/bottom
        sty.configure('Teams.Treeview.Heading',
                       font=('Inter', round(12 * scale), 'bold'),
                       background=C_HDR,
                       foreground=C_DARK,
                       relief='flat',
                       padding=(4, 6))
        sty.map('Teams.Treeview',
                background=[('selected', C_SELECTED)],
                foreground=[('selected', C_DARK)])
        sty.map('Teams.Treeview.Heading',
                background=[('active', C_HOVER)],
                relief=[('active', 'flat')])

        #── Treeview widget ───────────────────────────────────────────────────
        tv_frame = ctk.CTkFrame(parent, fg_color=C_PANEL, corner_radius=0)
        tv_frame.pack(fill='both', expand=True)

        tree = ttk.Treeview(tv_frame,
                            columns=[c[0] for c in TV_COLS],
                            show='tree headings',
                            selectmode='browse',
                            style='Teams.Treeview')
        #the '#0' tree column is normally hidden by show='headings'; reserving it as a narrow
        #icon-only column is the only place ttk.Treeview will actually render a per-row image.
        #A few extra px beyond the logo's own size (22, see _render_rows) leaves a small gap
        #before the team name in the next column instead of the two butting up against each other.
        icon_w = round(34 * scale)
        tree.column('#0', width=icon_w, minwidth=icon_w, stretch=False, anchor='center')
        tree.heading('#0', text='')

        for col_id, sk, header, px_width, anchor, stretch in TV_COLS:
            #Use the runtime-measured width for the name column so it's
            #exactly wide enough for the longest team name with no wasted
            #space; other columns use the width scaled for the current font
            #(see the scaling note where self._stat_col_w is computed).
            col_w    = self._name_col_w if col_id == 'name' else self._stat_col_w[col_id]
            col_minw = self._name_col_w if col_id == 'name' else 30
            tree.column(col_id, width=col_w, anchor=anchor,
                        minwidth=col_minw, stretch=stretch)
            tree.heading(col_id, text=header,
                         command=lambda k=sk: self._on_sort(k))

        #Row colour tags
        tree.tag_configure('high',     foreground=C_GREEN)
        tree.tag_configure('mid',      foreground=C_BLUE)
        tree.tag_configure('low',      foreground=C_RED)
        tree.tag_configure('row_odd',  background=C_ROW_ALT)

        sb = ttk.Scrollbar(tv_frame, orient='vertical', command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')

        tree.bind('<<TreeviewSelect>>', self._on_tree_select)
        tree.bind('<Button-3>',         self._on_tree_right_click)
        tree.bind('<MouseWheel>',
                  lambda e: tree.yview_scroll(-1*(e.delta//120), 'units'))

        self._tree = tree
        self._update_sort_headers()
        self._render_rows()

    #── keyboard shortcuts ────────────────────────────────────────────────────

    def _register_shortcuts(self, _: tk.Event | None = None) -> None:
        self.winfo_toplevel().bind('<Control-f>', self._toggle_search)

    def _unregister_shortcuts(self, _: tk.Event | None = None) -> None:
        try:
            self.winfo_toplevel().unbind('<Control-f>')
        except Exception:
            pass

    #── Ctrl+F search ─────────────────────────────────────────────────────────

    def _toggle_search(self, _: tk.Event | None = None) -> None:
        if self._search_visible:
            self._hide_search()
        else:
            self._show_search()

    def _show_search(self) -> None:
        if self._search_bar and not self._search_visible:
            self._search_bar.pack(fill='x')
            self._search_visible = True
        if self._search_entry:
            self._search_entry.focus_set()

    def _hide_search(self) -> None:
        if self._search_bar:
            self._search_bar.pack_forget()
        self._search_visible = False
        if self._search_var:
            self._search_var.set('')
        if self._tree:
            self._tree.focus_set()

    def _on_search_key(self, _: tk.Event) -> None:
        query = (self._search_var.get() if self._search_var else '').lower().strip()
        if not query:
            return
        for team in self._sorted_teams():
            if query in team.lower():
                self._on_team_click(team)
                break

    #── Treeview event handlers ───────────────────────────────────────────────

    def _on_tree_select(self, _: tk.Event) -> None:
        """Fired whenever the Treeview selection changes (click OR arrow key)."""
        if not self._tree:
            return
        sel = self._tree.selection()
        if not sel:
            return
        values = self._tree.item(sel[0], 'values')
        if not values:
            return
        team = values[0]
        if team == self._selected_team:
            return
        self._selected_team = team
        self._show_team_detail(self._right_frame, team)

    def _on_tree_right_click(self, event: tk.Event) -> None:
        if not self._tree:
            return
        item_id = self._tree.identify_row(event.y)
        if not item_id:
            return
        self._tree.selection_set(item_id)
        values = self._tree.item(item_id, 'values')
        if values:
            self._on_right_click(event, values[0])

    #── right-click context menu ──────────────────────────────────────────────
    #tk.Menu — no customtkinter equivalent exists.

    def _on_right_click(self, event: tk.Event, team: str) -> None:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label=f'📋  {team}',
                         state='disabled', font=FONT_SMALL_BOLD)
        menu.add_separator()
        menu.add_command(label='View Game Log',
                         command=lambda: self._on_team_click(team))
        menu.add_command(label='Copy Stats to Clipboard',
                         command=lambda: self._copy_team_stats(team))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def _copy_team_stats(self, team: str) -> None:
        w, l  = self._result.win_loss(team)
        pct   = self._result.pct(team)
        odds  = self._result.playoff_odds.get(team, 0.0)
        elo   = self._result.live_elo.get(team, 1500.0)
        div   = TEAM_REGISTRY[team].division
        text  = (f"{team} ({div})  {w}-{l}  "
                 f".{int(pct*1000):03d}  {odds:.1f}% playoff odds  Elo {elo:.0f}")
        self.clipboard_clear()
        self.clipboard_append(text)

    #── sorting ───────────────────────────────────────────────────────────────

    def _on_sort(self, col_key: str) -> None:
        if self._sort_col == col_key:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col_key
            self._sort_asc = (col_key == 'name')
        self._update_sort_headers()
        self._render_rows()

    def _update_sort_headers(self) -> None:
        if not self._tree:
            return
        arrow = ' ▲' if self._sort_asc else ' ▼'
        for col_id, sk, header, *_ in TV_COLS:
            if sk == self._sort_col:
                self._tree.heading(col_id, text=header + arrow)
            else:
                self._tree.heading(col_id, text=header)

    def _sorted_teams(self) -> list[str]:
        return sorted(
            ALL_TEAMS,
            key=lambda t: sort_key(self._sort_col, t, self._result),
            reverse=not self._sort_asc,
        )

    #── row rendering ─────────────────────────────────────────────────────────

    def _render_rows(self) -> None:
        if not self._tree:
            return
        self._tree.delete(*self._tree.get_children())
        self._tree_ids.clear()

        for i, team in enumerate(self._sorted_teams()):
            w_count, l = self._result.win_loss(team)
            pct  = self._result.pct(team)
            odds = self._result.playoff_odds.get(team, 0.0)
            elo  = self._result.live_elo.get(team, 1500.0)

            #Odds tier tag (determines foreground color)
            if odds >= 70:   tier = 'high'
            elif odds >= 35: tier = 'mid'
            else:            tier = 'low'

            #Alternating row background — odds tag overrides foreground only
            row_bg_tag = 'row_odd' if i % 2 == 1 else ''
            tags       = tuple(t for t in (row_bg_tag, tier) if t)

            iid = self._tree.insert(
                '', 'end',
                image=get_team_logo(TEAM_REGISTRY[team].id, max_size=22) or '',
                values=(team,
                        f"{w_count}–{l}",
                        pct_str(w_count, l),
                        f"{odds:.1f}%",
                        f"{elo:.0f}"),
                tags=tags,
            )
            self._tree_ids[team] = iid

        #Restore selection if team is still in the list
        if self._selected_team and self._selected_team in self._tree_ids:
            self._tree.selection_set(self._tree_ids[self._selected_team])
            self._tree.see(self._tree_ids[self._selected_team])

    #── team click (programmatic — search / nav fallback) ────────────────────

    def _on_team_click(self, team: str) -> None:
        if team == self._selected_team:
            return
        self._selected_team = team
        if self._tree and team in self._tree_ids:
            self._tree.selection_set(self._tree_ids[team])
            self._tree.see(self._tree_ids[team])
        self._show_team_detail(self._right_frame, team)

    #── RIGHT: placeholder ────────────────────────────────────────────────────

    def _show_placeholder(self) -> None:
        for w in self._right_frame.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._right_frame,
                    text='← Select a team to view its game log',
                    fg_color=C_BG, text_color=C_GRAY, font=FONT_NORMAL).pack(expand=True)

    #── RIGHT: team detail ────────────────────────────────────────────────────

    def _show_team_detail(self, parent: tk.Widget, team: str) -> None:
        for w in parent.winfo_children():
            w.destroy()

        result     = self._result
        w_count, l = result.win_loss(team)
        pct        = result.pct(team)
        odds       = result.playoff_odds.get(team, 0.0)
        elo        = result.live_elo.get(team, 1500.0)
        div        = TEAM_REGISTRY[team].division

        #── header card ───────────────────────────────────────────────────────
        card = ctk.CTkFrame(parent, fg_color=C_HEADER_BAR, corner_radius=0)
        card.pack(fill='x')

        #Logo — only shown once its PNG has been dropped into
        #assets/logos/{team_id}.png (see that folder's README); a team
        #without one yet just gets no image here, nothing breaks. Plain
        #tk.Label here on purpose — see this module's docstring.
        logo_img = get_team_logo(TEAM_REGISTRY[team].id, max_size=56)
        if logo_img is not None:
            logo_label = tk.Label(card, image=logo_img, bg=C_HEADER_BAR)
            logo_label.image = logo_img   #extra ref so Tkinter can't GC it
            logo_label.pack(side='left', padx=(16, 4), pady=10)

        left_card = ctk.CTkFrame(card, fg_color=C_HEADER_BAR, corner_radius=0)
        left_card.pack(side='left', padx=16 if logo_img is None else (0, 16), pady=10)
        ctk.CTkLabel(left_card, text=team, fg_color=C_HEADER_BAR, text_color=C_HEADER_TEXT,
                    font=FONT_TITLE).pack(anchor='w')
        ctk.CTkLabel(left_card, text=div, fg_color=C_HEADER_BAR, text_color=C_GRAY,
                    font=FONT_NORMAL).pack(anchor='w')
        make_stat_card(card, [
            ('Record',  f"{w_count}–{l}"),
            ('Pct',     pct_str(w_count, l)),
            ('Elo',     f"{elo:.1f}"),
            ('Playoff', f"{odds:.1f}%"),
        ])

        #── sub-tabs ──────────────────────────────────────────────────────────
        tab_bar = ctk.CTkFrame(parent, fg_color=C_PANEL, corner_radius=0)
        tab_bar.pack(fill='x')
        content = ctk.CTkFrame(parent, fg_color=C_BG, corner_radius=0)
        content.pack(fill='both', expand=True)

        games  = result.games_for_team(team)
        played = [g for g in games if g.is_played]
        upcome = [g for g in result.unplayed_games
                  if g.home == team or g.away == team]

        log_panel  = ctk.CTkFrame(content, fg_color=C_BG, corner_radius=0)
        next_panel = ctk.CTkFrame(content, fg_color=C_BG, corner_radius=0)
        build_game_log(log_panel,  played, team, result.elo_log)
        build_upcoming(next_panel, upcome, team, result)

        tab_btns: dict[str, ctk.CTkButton] = {}

        def show_tab(name: str) -> None:
            for b in tab_btns.values():
                b.configure(fg_color=C_PANEL, text_color=C_DARK)
            tab_btns[name].configure(fg_color=C_BLUE, text_color=C_HEADER_TEXT)
            log_panel.pack_forget()
            next_panel.pack_forget()
            (log_panel if name == 'log' else next_panel).pack(fill='both', expand=True)

        for key, label in [('log',      f'Game Log ({len(played)})'),
                            ('upcoming', f'Upcoming ({len(upcome)})')]:
            b = ctk.CTkButton(tab_bar, text=label, font=FONT_NORMAL,
                             fg_color=C_PANEL, text_color=C_DARK,
                             corner_radius=0, cursor='hand2',
                             command=lambda k=key: show_tab(k))
            b.pack(side='left')
            tab_btns[key] = b

        show_tab('log')
