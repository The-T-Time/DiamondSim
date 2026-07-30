# ==============================================================================
# SETTINGS SCREEN
# gui/launcher/settings_screen.py
#
# Builds the Settings screen: Basic weight sliders, a collapsible Advanced
# section, Feature toggles, Display options, and an About panel — each
# control with a hover tooltip. Kept separate from app.py, which just
# wires this into the launcher's screen-switching.
# ==============================================================================

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

from config import APP_NAME, APP_VERSION
from data.cache_store import refresh_all_data
from data.settings_store import load_settings, reset_to_default, save_settings
from models.app_settings import AppSettings
from gui.widgets import (
    C_DARK, C_GRAY, C_HEADER_BAR, C_HEADER_TEXT, C_ORANGE, C_PANEL, C_SASH,
    FONT_MEDIUM_BOLD, FONT_NORMAL, FONT_NORMAL_BOLD, FONT_SMALL, FONT_SMALL_BOLD,
    add_tooltip,
)

_CHARS_TO_PX = 8
_SLIDER_WIDTH = 260   #roughly half the settings window's content width


def _section_title(parent: tk.Widget, text: str) -> ctk.CTkLabel:
    lbl = ctk.CTkLabel(parent, text=text, font=FONT_MEDIUM_BOLD, text_color=C_DARK,
                       anchor='w')
    lbl.pack(fill='x', padx=4, pady=(14, 2))
    return lbl


def _info_icon(parent: tk.Widget, tooltip: str) -> ctk.CTkLabel:
    """A small 'ⓘ' badge that shows `tooltip` on hover — attached next to
    every variable so its meaning is a hover away instead of needing to be
    spelled out inline (which gets unreadable fast once every row has
    one)."""
    icon = ctk.CTkLabel(parent, text='\u24d8', font=FONT_SMALL, text_color=C_GRAY,
                        cursor='hand2', width=14)
    icon.pack(side='left', padx=(4, 0))
    add_tooltip(icon, tooltip)
    return icon


def _fmt_value(v: float, decimals: int, integer: bool) -> str:
    return str(int(round(v))) if integer else f'{v:.{decimals}f}'


def _slider_row(parent: tk.Widget, label: str, value: float, min_val: float, max_val: float,
                step: float, tooltip: str, decimals: int = 1, integer: bool = False) -> tk.DoubleVar:
    row = ctk.CTkFrame(parent, fg_color='transparent')
    row.pack(fill='x', pady=(6, 2))

    top = ctk.CTkFrame(row, fg_color='transparent')
    top.pack(fill='x')
    ctk.CTkLabel(top, text=label, font=FONT_NORMAL, anchor='w').pack(side='left')
    _info_icon(top, tooltip)
    value_lbl = ctk.CTkLabel(top, text=_fmt_value(value, decimals, integer),
                             font=FONT_NORMAL_BOLD, width=6 * _CHARS_TO_PX, anchor='e')
    value_lbl.pack(side='right')

    var = tk.DoubleVar(value=value)
    num_steps = max(1, round((max_val - min_val) / step))

    def _on_move(v) -> None:
        value_lbl.configure(text=_fmt_value(float(v), decimals, integer))

    ctk.CTkSlider(row, from_=min_val, to=max_val, number_of_steps=num_steps,
                 variable=var, command=_on_move, width=_SLIDER_WIDTH).pack(anchor='w', pady=(4, 0))
    return var


def _toggle_row(parent: tk.Widget, label: str, value: bool, tooltip: str) -> tk.BooleanVar:
    row = ctk.CTkFrame(parent, fg_color='transparent')
    row.pack(fill='x', pady=3)
    var = tk.BooleanVar(value=value)
    ctk.CTkCheckBox(row, text=label, variable=var, font=FONT_NORMAL,
                    onvalue=True, offvalue=False).pack(side='left', anchor='w')
    _info_icon(row, tooltip)
    return var


def _dropdown_row(parent: tk.Widget, label: str, value: str, options: list[str],
                  tooltip: str | None = None) -> tk.StringVar:
    row = ctk.CTkFrame(parent, fg_color='transparent')
    row.pack(fill='x', pady=3)
    ctk.CTkLabel(row, text=label, font=FONT_NORMAL, anchor='w',
                width=20 * _CHARS_TO_PX).pack(side='left')
    var = tk.StringVar(value=value)
    ctk.CTkOptionMenu(row, variable=var, values=options).pack(side='left')
    if tooltip is not None:
        _info_icon(row, tooltip)
    return var


class _AdvancedSection:
    """A collapsed-by-default 'Advanced' block. Starts hidden behind a
    toggle button so casual users aren't confronted with knobs they don't
    need — the fields inside are still built immediately (just not
    packed), so `SettingsForm.read()` can always reach them regardless of
    whether the user ever opened the section.

    `set_anchor()` must be called with the widget that should immediately
    follow this section (e.g. the next section's title) — tkinter's pack
    manager appends a freshly re-packed widget to the *end* of its
    container by default, which is what previously made the expanded
    section jump to the bottom of the form instead of appearing right
    below its toggle button. Packing with `before=anchor` keeps it in
    place."""

    def __init__(self, parent: tk.Widget) -> None:
        self._expanded = False
        self._anchor: tk.Widget | None = None

        self._toggle_btn = ctk.CTkButton(
            parent, text='\u25b8  Advanced Variables', font=FONT_NORMAL_BOLD,
            fg_color='transparent', text_color=C_DARK, hover_color=C_PANEL,
            border_width=1, border_color=C_SASH, anchor='w',
            cursor='hand2', command=self._toggle,
        )
        self._toggle_btn.pack(fill='x', pady=(14, 0))

        self.body = ctk.CTkFrame(parent, fg_color='transparent')
        #not packed yet — stays hidden until the user expands it

        warning = ctk.CTkLabel(
            self.body, font=FONT_SMALL, text_color=C_ORANGE, anchor='w', justify='left',
            wraplength=460,
            text=('These are intended for experienced users who understand how '
                  'changing them affects the simulator. The defaults are a safe '
                  'starting point for everyone else.'),
        )
        warning.pack(fill='x', padx=4, pady=(4, 6))

    def set_anchor(self, widget: tk.Widget) -> None:
        self._anchor = widget

    def _toggle(self) -> None:
        self._expanded = not self._expanded
        if self._expanded:
            self._toggle_btn.configure(text='\u25be  Advanced Variables')
            if self._anchor is not None:
                self.body.pack(fill='x', before=self._anchor)
            else:
                self.body.pack(fill='x')
        else:
            self._toggle_btn.configure(text='\u25b8  Advanced Variables')
            self.body.pack_forget()


def _data_section(parent: tk.Widget) -> None:
    _section_title(parent, 'Data')
    ctk.CTkLabel(
        parent, font=FONT_SMALL, text_color=C_GRAY, anchor='w', justify='left', wraplength=470,
        text=('Game, roster, and stat data is cached locally after the first run so '
              'later launches only pull whatever\u2019s new. Use this if you suspect the '
              'cache is stale or corrupted \u2014 it clears everything cached and '
              'rebuilds it from scratch on your next Simulate or Backtest run.'),
    ).pack(fill='x', padx=4, pady=(0, 8))

    def _on_refresh() -> None:
        if not messagebox.askyesno(
            'Refresh Data',
            'This clears all cached MLB data (games, rosters, stats, ratings). '
            'Everything will be re-downloaded the next time you run a simulation '
            'or backtest. Continue?',
        ):
            return
        try:
            refresh_all_data()
        except Exception as e:   #cache I/O should never be able to crash the app
            messagebox.showerror('Refresh Data', f"Couldn't refresh the cache: {e}")
            return
        messagebox.showinfo(
            'Refresh Data',
            'Cache cleared. Fresh data will be downloaded the next time you run '
            'a simulation or backtest.',
        )

    ctk.CTkButton(
        parent, text='\U0001f504  Refresh Data', font=FONT_NORMAL_BOLD,
        fg_color=C_ORANGE, hover_color=C_HEADER_BAR, command=_on_refresh,
    ).pack(anchor='w', padx=4, pady=(0, 10))


def _about_section(parent: tk.Widget) -> None:
    _section_title(parent, 'About')

    card = ctk.CTkFrame(parent, fg_color=C_HEADER_BAR, corner_radius=6)
    card.pack(fill='x', pady=(2, 16))

    ctk.CTkLabel(card, text=APP_NAME, font=FONT_MEDIUM_BOLD, text_color=C_HEADER_TEXT,
                anchor='w').pack(fill='x', padx=14, pady=(12, 0))
    ctk.CTkLabel(card, text=f'Version {APP_VERSION}', font=FONT_SMALL, text_color=C_GRAY,
                anchor='w').pack(fill='x', padx=14, pady=(0, 10))

    ctk.CTkLabel(
        card, font=FONT_SMALL, text_color=C_HEADER_TEXT, anchor='w', justify='left',
        wraplength=470,
        text=('A desktop application for simulating the remainder of the Major '
              'League Baseball season and postseason using team Elo ratings, '
              'player performance, and advanced statistical models. Run '
              'thousands of simulations to project standings, playoff odds, '
              'postseason brackets, and player and team statistics.'),
    ).pack(fill='x', padx=14, pady=(0, 10))

    ctk.CTkLabel(card, text='Developer: Tyler Oberquell', font=FONT_SMALL_BOLD,
                text_color=C_HEADER_TEXT, anchor='w').pack(fill='x', padx=14, pady=(0, 10))

    ctk.CTkLabel(card, text='Built With', font=FONT_SMALL_BOLD, text_color=C_HEADER_TEXT,
                anchor='w').pack(fill='x', padx=14)
    for item in ('Python', 'CustomTkinter', 'MLB Stats API'):
        ctk.CTkLabel(card, text=f'\u2022  {item}', font=FONT_SMALL, text_color=C_GRAY,
                    anchor='w').pack(fill='x', padx=22, pady=(0, 2))
    ctk.CTkLabel(card, text='', height=6).pack()   #bottom breathing room


class SettingsForm:
    """Builds every settings control into `parent` and knows how to read
    them back into a validated AppSettings on save."""

    def __init__(self, parent: tk.Widget) -> None:
        settings = load_settings()

        #── Simulation (basic) ───────────────────────────────────────────────
        _section_title(parent, 'Simulation')
        ctk.CTkLabel(parent, font=FONT_SMALL, text_color=C_GRAY, anchor='w', justify='left',
                    text='These become the "User" model once saved — Normal, Conservative, and\n'
                         'Aggressive presets are unaffected.').pack(fill='x', padx=4)

        self.elo_k = _slider_row(
            parent, 'Elo K-factor:', settings.elo_k, 5, 50, 1,
            "Controls how fast a team's Elo rating reacts to new results. Higher "
            "values make ratings swing more after each game; lower values make "
            "them more stable. Typical range: 16\u201332.")
        self.home_field_advantage = _slider_row(
            parent, 'Home-field advantage (Elo pts):', settings.home_field_advantage, 0, 50, 1,
            'Elo points added to the home team when computing that game\u2019s win '
            'probability. Higher values give home teams a bigger edge.')
        self.regression_weight = _slider_row(
            parent, 'Prior-year regression (0\u20131):', settings.regression_weight, 0.0, 1.0, 0.05,
            "How much of a team's final Elo rating from last season carries "
            "into this one. 1.0 keeps the full prior rating; 0.0 resets every "
            "team to the league-average baseline.", decimals=2)

        #── Advanced (collapsed by default) ─────────────────────────────────
        advanced = _AdvancedSection(parent)
        self.mov_weight = _slider_row(
            advanced.body, 'Margin-of-victory weight:', settings.mov_weight, 0.0, 1.0, 0.05,
            'Scales how much blowout wins/losses affect Elo updates, on top of '
            'the base K-factor. 0 disables it; higher values reward/punish '
            'lopsided scores more.', decimals=2)
        self.sim_margin_cap = _slider_row(
            advanced.body, 'Simulated margin cap:', settings.sim_margin_cap, 1, 20, 1,
            "Caps the run margin used when updating Elo during a simulated "
            "game, so an extreme simulated blowout can't swing ratings more "
            "than a real one would.", integer=True)

        #── Features ──────────────────────────────────────────────────────────
        features_title = _section_title(parent, 'Features')
        advanced.set_anchor(features_title)
        self.enable_home_field_advantage = _toggle_row(
            parent, 'Enable Home-Field Advantage', settings.enable_home_field_advantage,
            'When off, home teams get no rating boost at all — equivalent to '
            'setting home-field advantage to 0 while still remembering the '
            'value above for whenever you turn it back on.')
        self.use_real_pitcher_stats = _toggle_row(
            parent, 'Enable Real Pitcher Stats', settings.use_real_pitcher_stats,
            "Builds each team's rotation and bullpen from real MLB pitching "
            "stats instead of a synthetic, Elo-derived staff. Falls back to "
            "the synthetic staff automatically if a team's data can't be "
            "fetched.")
        self.use_real_hitter_stats = _toggle_row(
            parent, 'Enable Real Hitter Stats', settings.use_real_hitter_stats,
            "Builds each team's lineup offense rating from real MLB hitting "
            "stats instead of a synthetic, Elo-derived lineup. Falls back "
            "automatically if a team's data can't be fetched.")
        self.starting_pitcher_impact = _toggle_row(
            parent, 'Enable Starting Pitcher Impact', settings.starting_pitcher_impact,
            "Postseason games are decided by each game's starting-pitcher "
            "matchup on top of team Elo, instead of team Elo alone.")
        self.bullpen_fatigue_impact = _toggle_row(
            parent, 'Enable Bullpen Fatigue Impact', settings.bullpen_fatigue_impact,
            "Tracks each team's bullpen fatigue across a simulated postseason "
            "run — a tired bullpen lowers that team's win probability in its "
            "next game. Requires Starting Pitcher Impact.")
        self.lineup_impact = _toggle_row(
            parent, 'Enable Lineup Impact', settings.lineup_impact,
            "Factors each team's real lineup, matched against the opposing "
            "starter's throwing hand, into postseason win probability on top "
            "of the starter matchup and bullpen.")

        #── Display ───────────────────────────────────────────────────────────
        _section_title(parent, 'Display')
        self.theme = _dropdown_row(
            parent, 'Theme:', settings.theme.capitalize(), ['Light', 'Dark'])
        self.decimal_places = _dropdown_row(
            parent, 'Decimal places:', str(settings.decimal_places), ['0', '1', '2', '3'])
        self.percentage_format = _dropdown_row(
            parent, 'Percentages shown as:',
            'Percent (63.4%)' if settings.percentage_format == 'percent' else 'Fraction (0.634)',
            ['Percent (63.4%)', 'Fraction (0.634)'])

        #── Data ──────────────────────────────────────────────────────────────
        _data_section(parent)

        #── About ─────────────────────────────────────────────────────────────
        _about_section(parent)

    def read(self) -> AppSettings:
        """Reads every field back into a validated AppSettings. The weight
        sliders are already range-bound by construction, so this is mostly
        a formality — sim_margin_cap still gets rounded rather than
        truncated in case a slider lands a hair off an exact integer."""
        elo_k = float(self.elo_k.get())
        home_field_advantage = float(self.home_field_advantage.get())
        mov_weight = float(self.mov_weight.get())
        regression_weight = float(self.regression_weight.get())
        sim_margin_cap = int(round(self.sim_margin_cap.get()))

        if elo_k <= 0:
            raise ValueError('Elo K-factor must be positive.')
        if not (0.0 <= regression_weight <= 1.0):
            raise ValueError('Prior-year regression must be between 0 and 1.')
        if mov_weight < 0:
            raise ValueError('Margin-of-victory weight cannot be negative.')
        if sim_margin_cap < 1:
            raise ValueError('Simulated margin cap must be at least 1.')

        return AppSettings(
            elo_k=elo_k,
            home_field_advantage=home_field_advantage,
            mov_weight=mov_weight,
            regression_weight=regression_weight,
            sim_margin_cap=sim_margin_cap,
            enable_home_field_advantage=self.enable_home_field_advantage.get(),
            use_real_pitcher_stats=self.use_real_pitcher_stats.get(),
            use_real_hitter_stats=self.use_real_hitter_stats.get(),
            starting_pitcher_impact=self.starting_pitcher_impact.get(),
            bullpen_fatigue_impact=self.bullpen_fatigue_impact.get(),
            lineup_impact=self.lineup_impact.get(),
            theme=self.theme.get().lower(),
            decimal_places=int(self.decimal_places.get()),
            percentage_format='percent' if self.percentage_format.get().startswith('Percent') else 'fraction',
        )


def save_from_form(form: SettingsForm) -> bool:
    """Validates and saves. Returns True on success; shows an error dialog
    and returns False on invalid input."""
    try:
        settings = form.read()
    except ValueError as e:
        messagebox.showerror('Invalid settings', str(e))
        return False
    save_settings(settings)
    return True
