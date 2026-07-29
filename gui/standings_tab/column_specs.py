# ==============================================================================
# COLUMN SPECS
# gui/standings_tab/column_specs.py
#
# Split out of the former gui/standings_tab.py into a package.
# ==============================================================================

from __future__ import annotations

from gui.widgets import W_DIV, W_LARGE, W_MED, W_SMALL, W_STREAK, W_TEAM, W_TEAM_LG

#Division table column spec: (label, char_width, anchor)
DIV_COLS: list[tuple[str, int, str]] = [
    ('Team',  W_TEAM,   'w'),
    ('W',     W_SMALL,  'e'),
    ('L',     W_SMALL,  'e'),
    ('PCT',   W_MED,    'e'),
    ('GB',    W_MED,    'e'),
    ('L10',   W_MED,    'c'),
    ('Strk',  W_STREAK, 'c'),
    ('Odds',  W_LARGE,  'e'),
]

WC_COLS: list[tuple[str, int, str]] = [
    ('Team',   W_TEAM_LG, 'w'),
    ('Div',    W_DIV,     'w'),
    ('W',      W_SMALL,   'e'),
    ('L',      W_SMALL,   'e'),
    ('PCT',    W_MED,     'e'),
    ('WC GB',  W_MED,     'e'),
    ('Odds',   W_LARGE,   'e'),
]
