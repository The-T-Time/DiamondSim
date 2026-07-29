# ==============================================================================
# PLAYER TAB
# gui/player_tab/tab.py
#
# Every pitcher and every hitter across all 30 teams, one SortableTable at
# a time (Pitchers/Hitters toggle — never a combined view). Data loads
# once per tab on a background thread; switching role/filters/search
# afterward is instant local filtering.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
from datetime import date

import customtkinter as ctk

from data.teams import ALL_TEAMS
from models.simulation_result import SimulationResult
from gui.player_tab.columns import HITTER_COLUMNS, PITCHER_COLUMNS
from gui.player_tab.filters import ALL_DIVISIONS, ALL_LEAGUES, ALL_TEAMS_OPTION, DIVISIONS, filter_rows
from gui.player_tab.loader import load_players_async
from gui.player_tab.projection import project_hitter_rows, project_pitcher_rows
from gui.player_tab.qualification import filter_qualified_hitters, filter_qualified_pitchers
from gui.widgets import (
    C_BG, C_BLUE, C_DARK, C_GRAY, C_GREEN, C_HEADER_TEXT, C_MID, C_PANEL, C_RED,
    FONT_NORMAL, FONT_SMALL, FONT_SMALL_BOLD,
    SortableTable, make_header_bar,
)


class PlayerTab(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, result: SimulationResult) -> None:
        super().__init__(parent, fg_color=C_BG, corner_radius=0)
        self._result = result
        self._role = 'pitcher'          #'pitcher' | 'hitter'
        self._simulated = False         #False = Current, True = Simulated (projected)
        self._pitcher_rows: list[dict] | None = None
        self._hitter_rows: list[dict] | None = None
        self._table: SortableTable | None = None
        self._table_role: str | None = None

        self._league_var = tk.StringVar(value=ALL_LEAGUES)
        self._division_var = tk.StringVar(value=ALL_DIVISIONS)
        self._team_var = tk.StringVar(value=ALL_TEAMS_OPTION)
        self._search_var = tk.StringVar()

        self._build()
        self._load()

    #── layout ────────────────────────────────────────────────────────────────

    def _build(self) -> None:
        make_header_bar(self, 'Players', subtitle='Qualified players only  ·  Click a header to sort  ·  Ctrl+C copies the visible table')

        toggle_bar = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0)
        toggle_bar.pack(fill='x')
        self._pitcher_btn = ctk.CTkButton(
            toggle_bar, text='Pitchers', font=FONT_SMALL_BOLD, corner_radius=0, cursor='hand2',
            command=lambda: self._switch_role('pitcher'),
        )
        self._hitter_btn = ctk.CTkButton(
            toggle_bar, text='Hitters', font=FONT_SMALL_BOLD, corner_radius=0, cursor='hand2',
            command=lambda: self._switch_role('hitter'),
        )
        self._pitcher_btn.pack(side='left', padx=(12, 2), pady=4)
        self._hitter_btn.pack(side='left', padx=2, pady=4)

        #Current ↔ Simulated toggle. There's no per-player game simulation
        #to average (the engine is team-level — see projection.py's
        #docstring), so "Simulated" here means each player's current
        #counting stats (IP, K, BB, HR, W-L) scaled forward by how much
        #more of the season their team is projected to play. Rate stats
        #(ERA, AVG, OBP, etc.) are unchanged in both modes.
        self._current_btn = self._simulated_btn = None
        if self._result.projected_team_stats:
            sim_bar = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0)
            sim_bar.pack(fill='x')
            ctk.CTkLabel(sim_bar, text='Showing:', fg_color=C_PANEL, text_color=C_MID,
                        font=FONT_SMALL).pack(side='left', padx=(12, 6), pady=4)
            self._current_btn = ctk.CTkButton(
                sim_bar, text='Current', font=FONT_SMALL_BOLD,
                corner_radius=0, cursor='hand2', fg_color=C_GREEN, text_color=C_HEADER_TEXT,
                command=lambda: self._switch_simulated(False),
            )
            self._simulated_btn = ctk.CTkButton(
                sim_bar, text='Simulated (projected to end of season)', font=FONT_SMALL_BOLD,
                corner_radius=0, cursor='hand2',
                command=lambda: self._switch_simulated(True),
            )
            self._current_btn.pack(side='left', padx=2, pady=4)
            self._simulated_btn.pack(side='left', padx=2, pady=4)

        filter_bar = ctk.CTkFrame(self, fg_color=C_PANEL, corner_radius=0)
        filter_bar.pack(fill='x')

        self._add_dropdown(filter_bar, 'League:', self._league_var, [ALL_LEAGUES, 'AL', 'NL'])
        self._add_dropdown(filter_bar, 'Division:', self._division_var, [ALL_DIVISIONS] + DIVISIONS)
        self._add_dropdown(filter_bar, 'Team:', self._team_var, [ALL_TEAMS_OPTION] + list(ALL_TEAMS))

        ctk.CTkLabel(filter_bar, text='Search:', fg_color=C_PANEL, text_color=C_DARK,
                    font=FONT_SMALL_BOLD).pack(side='left', padx=(16, 4), pady=4)
        entry = ctk.CTkEntry(filter_bar, textvariable=self._search_var, width=120, font=FONT_SMALL)
        entry.pack(side='left', padx=(0, 12), pady=4)
        self._search_var.trace_add('write', lambda *_: self._refresh_table())

        self._content = ctk.CTkFrame(self, fg_color=C_BG, corner_radius=0)
        self._content.pack(fill='both', expand=True)

        self._update_role_buttons()

    def _add_dropdown(self, parent: tk.Widget, label: str, var: tk.StringVar, values: list[str]) -> None:
        ctk.CTkLabel(parent, text=label, fg_color=C_PANEL, text_color=C_DARK,
                    font=FONT_SMALL_BOLD).pack(side='left', padx=(12, 4), pady=4)
        menu = ctk.CTkOptionMenu(parent, variable=var, values=values, font=FONT_SMALL,
                                command=lambda _v: self._refresh_table())
        menu.pack(side='left', pady=4)

    def _update_role_buttons(self) -> None:
        for btn, role in ((self._pitcher_btn, 'pitcher'), (self._hitter_btn, 'hitter')):
            active = role == self._role
            btn.configure(fg_color=C_BLUE if active else C_PANEL,
                         text_color=C_HEADER_TEXT if active else C_DARK)

    #── loading ───────────────────────────────────────────────────────────────

    def _load(self) -> None:
        for w in self._content.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._content, text='Loading players…\n(fetching every team\'s roster — this can take a moment)',
                    fg_color=C_BG, text_color=C_GRAY, font=FONT_NORMAL, justify='center').pack(expand=True)

        as_of_date = self._result.snapshot_date or date.today().isoformat()
        load_players_async(
            self, self._result.season, as_of_date, self._result.cfg,
            on_success=self._on_loaded, on_error=self._on_load_error,
        )

    def _on_loaded(self, pitcher_rows: list[dict], hitter_rows: list[dict]) -> None:
        self._pitcher_rows = pitcher_rows
        self._hitter_rows = hitter_rows
        self._refresh_table()

    def _on_load_error(self, error: Exception) -> None:
        for w in self._content.winfo_children():
            w.destroy()
        ctk.CTkLabel(self._content, text=f"Couldn't load player data:\n\n{error}",
                    fg_color=C_BG, text_color=C_RED, font=FONT_NORMAL, justify='center').pack(expand=True)

    #── role switching ───────────────────────────────────────────────────────

    def _switch_role(self, role: str) -> None:
        if role == self._role:
            return
        self._role = role
        self._update_role_buttons()
        self._refresh_table()

    def _switch_simulated(self, simulated: bool) -> None:
        if simulated == self._simulated:
            return
        self._simulated = simulated
        for btn, sim in [(self._current_btn, False), (self._simulated_btn, True)]:
            btn.configure(fg_color=C_GREEN if sim == self._simulated else C_PANEL,
                         text_color=C_HEADER_TEXT if sim == self._simulated else C_DARK)
        self._refresh_table()

    #── filtering + rendering ───────────────────────────────────────────────────

    def _refresh_table(self) -> None:
        rows = self._pitcher_rows if self._role == 'pitcher' else self._hitter_rows
        if rows is None:
            return   #still loading

        if self._simulated:
            rows = (project_pitcher_rows(rows, self._result) if self._role == 'pitcher'
                    else project_hitter_rows(rows, self._result))

        rows = (filter_qualified_pitchers(rows, self._result, self._simulated) if self._role == 'pitcher'
                else filter_qualified_hitters(rows, self._result, self._simulated))

        filtered = filter_rows(
            rows,
            league=self._league_var.get(),
            division=self._division_var.get(),
            team=self._team_var.get(),
            search=self._search_var.get(),
        )

        if self._table is not None and self._table_role == self._role:
            self._table.set_rows(filtered)
            return

        for w in self._content.winfo_children():
            w.destroy()
        columns = PITCHER_COLUMNS if self._role == 'pitcher' else HITTER_COLUMNS
        self._table = SortableTable(
            self._content, columns, filtered,
            default_sort='rating', default_asc=False,
            style_name='PlayerPitchers.Treeview' if self._role == 'pitcher' else 'PlayerHitters.Treeview',
        )
        self._table.pack(fill='both', expand=True, padx=8, pady=6)
        self._table_role = self._role
