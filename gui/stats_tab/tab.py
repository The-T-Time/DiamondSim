# ==============================================================================
# STATS TAB
# gui/stats_tab/tab.py
#
# Four sortable sub-tabs (Power Rankings, Run Differential, Splits,
# Momentum) derived from a single walk of played_games — see
# stat_computation.py for the math. Ctrl+C copies the active sub-tab.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont

import customtkinter as ctk

from data.teams import ALL_TEAMS
from models.simulation_result import SimulationResult
from gui.stats_tab.columns import MOMENTUM_COLS, POWER_COLS, RUNS_COLS, SPLITS_COLS
from gui.stats_tab.stat_computation import compute_all_stats, rows_from_stats
from gui.widgets import C_BG, C_DARK, C_GREEN, C_HEADER_TEXT, C_MID, C_PANEL, Column, FONT_SMALL, FONT_SMALL_BOLD, SortableTable, make_header_bar


class StatsTab(ctk.CTkFrame):
    def __init__(self, parent: tk.Widget, result: SimulationResult) -> None:
        super().__init__(parent, fg_color=C_BG, corner_radius=0)
        self._result    = result
        self._simulated = False   #False = Current, True = Simulated (projected)
        self._build()

    def _current_rows(self) -> list[dict]:
        return rows_from_stats(compute_all_stats(self._result, simulated=self._simulated))

    def _switch_simulated(self, simulated: bool) -> None:
        if simulated == self._simulated:
            return
        self._simulated = simulated
        for btn, sim in [(self._current_btn, False), (self._simulated_btn, True)]:
            btn.configure(fg_color=C_GREEN if sim == self._simulated else C_PANEL,
                         text_color=C_HEADER_TEXT if sim == self._simulated else C_DARK)
        rows = self._current_rows()
        for table in self._tables:
            table.set_rows(rows)

    def _build(self) -> None:
        make_header_bar(
            self, 'Statistics',
            subtitle='Click a header to sort  ·  Search / filter above each table  ·  Ctrl+C copies',
        )

        #Current ↔ Simulated toggle — only meaningful if this run actually
        #has projected (averaged-across-sims) stats to show. Note: Splits
        #and Momentum have no simulated analog (see stat_computation.py's
        #docstring) and keep showing current values even when Simulated is
        #selected — only Power Rankings' W/L/PCT and Run Differential's
        #RS/RA/RD change with the toggle.
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
                sim_bar, text='Simulated (end of season) — Power Rankings & Run Differential only',
                font=FONT_SMALL_BOLD, corner_radius=0, cursor='hand2',
                command=lambda: self._switch_simulated(True),
            )
            self._current_btn.pack(side='left', padx=2, pady=4)
            self._simulated_btn.pack(side='left', padx=2, pady=4)

        #Measure team name column width once (requires Tk to exist)
        _mf = tkfont.Font(family='Inter', size=FONT_SMALL_BOLD[1], weight='bold')
        name_col_w = max(_mf.measure(t) for t in ALL_TEAMS) + 10

        tabview = ctk.CTkTabview(self, fg_color=C_BG)
        tabview.pack(fill='both', expand=True, padx=4, pady=4)

        tabs = [
            ('📊  Power Rankings',   POWER_COLS,    'elo',    'PowerStats.Treeview'),
            ('💥  Run Differential', RUNS_COLS,     'rd',     'RunsStats.Treeview'),
            ('🏠  Splits',           SPLITS_COLS,   'hpct',   'SplitStats.Treeview'),
            ('🔥  Momentum',         MOMENTUM_COLS, 'last10', 'MoStats.Treeview'),
        ]

        rows = self._current_rows()
        self._tables: list[SortableTable] = []
        for label, cols, default_sort, style_name in tabs:
            columns = [Column(*spec) for spec in cols]
            container = tabview.add(label)
            table = SortableTable(
                container, columns, rows,
                default_sort=default_sort, default_asc=False,
                show_search=True,
                search_key='team',
                filter_key='league',
                filter_values=['AL', 'NL'],
                filter_label='League',
                name_col_w=name_col_w,
                style_name=style_name,
            )
            table.pack(fill='both', expand=True)
            self._tables.append(table)

        tabview.set(tabs[0][0])
