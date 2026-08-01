# ==============================================================================
# LAUNCHER APP
# gui/launcher/app.py
#
# The three screens (main menu, Simulate/Backtest forms, Load-a-run list)
# and the wiring between them. Form-row widgets, the progress bar, and
# background-thread run logic live in sibling modules (forms.py,
# progress.py, run_action.py) — this file is just the screens.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

import customtkinter as ctk

from config import APP_NAME, DEFAULT_SIMS, BACKTEST_SEASON_MAX, LAUNCHER_WINDOW_SIZE
from data.results_store import list_saved_results, load_result, SavedResultError
from data.settings_store import reset_to_default
from models.simulation_config import SimulationConfig
from simulation.runner import SimulationRunner
from gui.launcher.constants import _BTN_SIM, _BTN_BACK, _BTN_LOAD, _BTN_SETTINGS
from gui.launcher.forms import action_row, form_row, model_row, parse_seed
from gui.launcher.progress import ProgressIndicator
from gui.launcher.run_action import run_action_with_progress
from gui.launcher.settings_screen import SettingsForm, save_from_form
from gui.results_window import ResultsWindow
from gui.widgets import (
    C_DARK, C_HDR, C_PANEL, C_SELECTED, C_WHITE,
    FONT_SMALL, FONT_NORMAL, FONT_NORMAL_BOLD, FONT_MEDIUM_BOLD, FONT_HEADER,
)
from utils.logger import get_logger

logger  = get_logger(__name__)
_runner = SimulationRunner()

_CHARS_TO_PX = 8   #tkinter Button/width is in characters; CTkButton's is in pixels
_SETTINGS_WINDOW_SIZE = '620x720'


class LauncherApp:
    def __init__(self, root: ctk.CTk) -> None:
        self.root = root
        root.title(APP_NAME)
        root.geometry(LAUNCHER_WINDOW_SIZE)
        root.resizable(False, False)
        self._progress = ProgressIndicator(root)
        self._build_main()

    #── shared widgets ────────────────────────────────────────────────────────

    def _back_button(self, command) -> ctk.CTkButton:
        """A small, consistently-placed top-left nav button, packed first
        so it sits above/left of everything else on the screen rather
        than competing with the Simulate/Backtest form's [Run] [Cancel]
        row for space — that row is reserved for the action itself now,
        with Cancel taking the slot Back used to occupy there."""
        btn = ctk.CTkButton(self.root, text='← Back', font=FONT_NORMAL,
                           cursor='hand2', width=10 * _CHARS_TO_PX, height=26,
                           fg_color='transparent', text_color=('gray10', 'gray90'),
                           border_width=1, command=command)
        btn.pack(anchor='w', padx=10, pady=(10, 0))
        return btn

    #── main menu ─────────────────────────────────────────────────────────────

    def _build_main(self) -> None:
        self._clear()
        root = self.root
        root.geometry(LAUNCHER_WINDOW_SIZE)   #Settings uses a larger window; restore on return

        ctk.CTkLabel(root, text=APP_NAME, font=FONT_HEADER).pack(pady=(12, 0))
        ctk.CTkLabel(root, text='Choose a mode to get started:', font=FONT_NORMAL).pack(pady=4)

        btn_frame = ctk.CTkFrame(root, fg_color='transparent')
        btn_frame.pack(pady=16)
        ctk.CTkButton(btn_frame, text='▶  Simulate',
                     font=FONT_MEDIUM_BOLD, width=14 * _CHARS_TO_PX, height=48,
                     cursor='hand2',
                     command=self._open_simulate, **_BTN_SIM).pack(side='left', padx=10)
        ctk.CTkButton(btn_frame, text='⏪  Backtest',
                     font=FONT_MEDIUM_BOLD, width=14 * _CHARS_TO_PX, height=48,
                     cursor='hand2',
                     command=self._open_backtest, **_BTN_BACK).pack(side='left', padx=10)

        row2 = ctk.CTkFrame(root, fg_color='transparent')
        row2.pack(pady=(0, 4))
        ctk.CTkButton(row2, text='📂  Load a saved run',
                     font=FONT_NORMAL_BOLD, width=20 * _CHARS_TO_PX,
                     cursor='hand2',
                     command=self._open_load, **_BTN_LOAD).pack(side='left', padx=4)
        ctk.CTkButton(row2, text='⚙  Settings',
                     font=FONT_NORMAL_BOLD, width=13 * _CHARS_TO_PX,
                     cursor='hand2',
                     command=self._open_settings, **_BTN_SETTINGS).pack(side='left', padx=4)

        ctk.CTkLabel(root,
                    text='Simulate  →  project the current season forward\n'
                         'Backtest  →  test accuracy against a completed season',
                    font=FONT_SMALL, text_color='#666').pack(pady=8)

    #── simulate ──────────────────────────────────────────────────────────────

    def _open_simulate(self) -> None:
        self._clear()
        root = self.root
        back_btn = self._back_button(self._build_main)
        ctk.CTkLabel(root, text='▶  Simulate Current Season', font=FONT_MEDIUM_BOLD).pack(pady=10)

        form = ctk.CTkFrame(root, fg_color='transparent')
        form.pack(pady=8)
        year_var  = form_row(form, 'Season year:',  '2026', 0)
        sims_var  = form_row(form, 'Simulations:',  str(DEFAULT_SIMS), 1)
        model_var = model_row(form, 2)
        seed_var  = form_row(form, 'Seed:', 'Random', 3)

        def run() -> None:
            try:
                season   = int(year_var.get())
                num_sims = int(sims_var.get())
                seed     = parse_seed(seed_var.get())
                assert 1990 <= season <= 2030 and 100 <= num_sims <= 100_000
            except Exception:
                messagebox.showerror('Invalid input',
                                     'Season: 1990–2030\nSimulations: 100–100,000\n'
                                     "Seed: an integer, or 'Random'")
                return
            cfg = SimulationConfig.by_name(model_var.get(), simulations=num_sims, random_seed=seed)
            run_action_with_progress(
                self.root, run_btn, cancel_btn, 'Run Simulation',
                lambda cb, cancel_event: _runner.run_simulate(
                    season, cfg, progress_callback=cb, cancel_event=cancel_event),
                self._progress, back_btn=back_btn,
            )

        run_btn, cancel_btn = action_row(root, 'Run Simulation', run, _BTN_SIM, lambda: None)

    #── backtest ──────────────────────────────────────────────────────────────

    def _open_backtest(self) -> None:
        self._clear()
        root = self.root
        back_btn = self._back_button(self._build_main)
        ctk.CTkLabel(root, text='⏪  Backtest a Completed Season', font=FONT_MEDIUM_BOLD).pack(pady=10)
        ctk.CTkLabel(root,
                    text='Pick a past season and a mid-season snapshot date.\n'
                         'The sim predicts from that date and compares\n'
                         'against the real postseason field.',
                    font=FONT_SMALL, text_color='#555').pack(pady=4)

        form = ctk.CTkFrame(root, fg_color='transparent')
        form.pack(pady=10)
        year_var  = form_row(form, 'Season year:',        '2024', 0, width=18)
        date_var  = form_row(form, 'Snapshot (YYYY-MM-DD):', '2024-07-01', 1, width=18, entry_w=14)
        sims_var  = form_row(form, 'Simulations:',         str(DEFAULT_SIMS), 2, width=18)
        model_var = model_row(form, 3, width=18)
        seed_var  = form_row(form, 'Seed:', 'Random', 4, width=18)

        def run() -> None:
            try:
                season        = int(year_var.get())
                snapshot_date = date_var.get().strip()
                num_sims      = int(sims_var.get())
                seed          = parse_seed(seed_var.get())
                parts = snapshot_date.split('-')
                assert len(parts) == 3 and all(p.isdigit() for p in parts)
                assert 1990 <= season <= BACKTEST_SEASON_MAX and 100 <= num_sims <= 100_000
            except Exception:
                messagebox.showerror('Invalid input',
                                     f'Season: 1990–{BACKTEST_SEASON_MAX}\n'
                                     'Date: YYYY-MM-DD\nSimulations: 100–100,000\n'
                                     "Seed: an integer, or 'Random'")
                return
            cfg = SimulationConfig.by_name(model_var.get(), simulations=num_sims, random_seed=seed)
            run_action_with_progress(
                self.root, run_btn, cancel_btn, 'Run Backtest',
                lambda cb, cancel_event: _runner.run_backtest(
                    season, snapshot_date, cfg, progress_callback=cb, cancel_event=cancel_event),
                self._progress, back_btn=back_btn,
            )

        run_btn, cancel_btn = action_row(root, 'Run Backtest', run, _BTN_BACK, lambda: None)

    #── load saved run ──────────────────────────────────────────────────────────

    def _open_load(self) -> None:
        self._clear()
        root = self.root
        self._back_button(self._build_main)
        ctk.CTkLabel(root, text='📂  Load a Saved Run', font=FONT_MEDIUM_BOLD).pack(pady=10)

        saved = list_saved_results()
        if not saved:
            ctk.CTkLabel(root, text='No saved runs yet.\n\nRun a simulation and use\n'
                                    '“Save run” to keep one here.',
                        font=FONT_NORMAL, text_color='#555').pack(pady=12)
            return

        #tk.Listbox (no CTk equivalent) inside a CTkFrame — see this
        #module's docstring. Both it and its Scrollbar are colored
        #explicitly (Listbox has no ttk/CTk styling hook at all, and an
        #un-styled ttk.Scrollbar falls back to the platform's native
        #chrome) so this doesn't look like a stray light-mode widget
        #dropped into a themed window.
        list_frame = ctk.CTkFrame(root, fg_color=C_PANEL)
        list_frame.pack(fill='both', expand=True, padx=12, pady=6)

        sb_style = 'DiamondSimLoad.Vertical.TScrollbar'
        sty = ttk.Style()
        sty.theme_use('clam')   #see gui/widgets/table.py — 'clam' is the one theme that reliably honors these color overrides across platforms
        sty.configure(sb_style, background=C_HDR, troughcolor=C_PANEL,
                     bordercolor=C_PANEL, arrowcolor=C_DARK, relief='flat')
        sb = ttk.Scrollbar(list_frame, orient='vertical', style=sb_style)
        lb = tk.Listbox(list_frame, font=FONT_SMALL, activestyle='none',
                        yscrollcommand=sb.set, height=8, relief='flat', borderwidth=0,
                        bg=C_WHITE, fg=C_DARK, highlightthickness=0,
                        selectbackground=C_SELECTED, selectforeground=C_DARK)
        sb.config(command=lb.yview)
        sb.pack(side='right', fill='y')
        lb.pack(side='left', fill='both', expand=True, padx=4, pady=4)

        for name, _path, saved_at, season, mode in saved:
            lb.insert('end', f'{name}   ·   {season} {mode}   ·   {saved_at}')
        lb.selection_set(0)

        def do_load() -> None:
            sel = lb.curselection()
            if not sel:
                return
            path = saved[sel[0]][1]
            try:
                result = load_result(path)
            except SavedResultError as e:
                logger.warning("Couldn't load saved run '%s': %s", path, e)
                messagebox.showerror("Couldn't load saved run", str(e))
                return
            ResultsWindow(self.root, result)

        row = ctk.CTkFrame(root, fg_color='transparent')
        row.pack(pady=10)
        ctk.CTkButton(row, text='Open', font=FONT_NORMAL_BOLD,
                     cursor='hand2', width=12 * _CHARS_TO_PX, command=do_load,
                     **_BTN_LOAD).pack(side='left', padx=8)
        lb.bind('<Double-Button-1>', lambda _e: do_load())

    #── settings ──────────────────────────────────────────────────────────────

    def _open_settings(self) -> None:
        self._clear()
        root = self.root
        root.geometry(_SETTINGS_WINDOW_SIZE)

        self._back_button(self._build_main)
        ctk.CTkLabel(root, text='⚙  Settings', font=FONT_MEDIUM_BOLD).pack(pady=(10, 4))

        scroll = ctk.CTkScrollableFrame(root, fg_color=C_PANEL)
        scroll.pack(fill='both', expand=True, padx=12, pady=6)
        form = SettingsForm(scroll)

        status_var = tk.StringVar(value='')
        status_lbl = ctk.CTkLabel(root, textvariable=status_var, font=FONT_SMALL, text_color='#27ae60')
        status_lbl.pack()

        def do_save() -> None:
            if save_from_form(form):
                status_var.set('Saved. New simulations will use these settings.')

        def do_reset() -> None:
            reset_to_default()
            status_var.set('Reset to default — reopening Settings to show the reset values.')
            self.root.after(600, self._open_settings)

        btn_row = ctk.CTkFrame(root, fg_color='transparent')
        btn_row.pack(pady=8)
        ctk.CTkButton(btn_row, text='Save', font=FONT_NORMAL_BOLD,
                     cursor='hand2', width=12 * _CHARS_TO_PX,
                     command=do_save, **_BTN_BACK).pack(side='left', padx=6)
        ctk.CTkButton(btn_row, text='Reset to Default', font=FONT_NORMAL,
                     cursor='hand2', width=16 * _CHARS_TO_PX,
                     fg_color='transparent', text_color=('gray10', 'gray90'),
                     border_width=1, command=do_reset).pack(side='left', padx=6)

    #── helpers ───────────────────────────────────────────────────────────────

    def _clear(self) -> None:
        for w in self.root.winfo_children():
            w.destroy()
