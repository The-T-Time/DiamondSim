# ==============================================================================
# COLUMNS
# gui/player_tab/columns.py
#
# Column specs for the two player tables (pitchers / hitters). A missing
# stat (e.g. a September call-up with no innings yet) sorts to the bottom
# rather than crashing on a None comparison.
# ==============================================================================

from __future__ import annotations

from typing import Any

from gui.widgets import Column

_WORST_HIGH = float('-inf')   #sentinel for "higher is better" stats (missing -> worst)
_WORST_LOW = float('inf')     #sentinel for "lower is better" stats (missing -> worst)


def _num(value: Any, worst: float) -> float:
    return value if value is not None else worst


def _fmt(value: Any, spec: str, dash: str = '—') -> str:
    return format(value, spec) if value is not None else dash


PITCHER_COLUMNS: list[Column] = [
    Column('name',   'Player', 0,   'w',      lambda r: r['name'].lower(),                  lambda r: r['name']),
    Column('team',   'Team',   150, 'w',      lambda r: r['team'],                          lambda r: r['team']),
    Column('pos',    'Pos',    44,  'center', lambda r: r['pos'],                            lambda r: r['pos']),
    Column('rating', 'Rating', 62,  'e',      lambda r: r['rating'],                         lambda r: f"{r['rating']:.0f}"),
    Column('era',    'ERA',    56,  'e',      lambda r: _num(r['era'], _WORST_LOW),          lambda r: _fmt(r['era'], '.2f')),
    Column('wl',     'W-L',    54,  'center', lambda r: r['wins'],                           lambda r: f"{r['wins']:.0f}-{r['losses']:.0f}"),
    Column('ip',     'IP',     54,  'e',      lambda r: r['ip'],                             lambda r: f"{r['ip']:.1f}"),
    Column('so',     'K',      44,  'e',      lambda r: r['so'],                             lambda r: f"{r['so']:.0f}"),
    Column('bb',     'BB',     44,  'e',      lambda r: r['bb'],                             lambda r: f"{r['bb']:.0f}"),
    Column('hr',     'HR',     44,  'e',      lambda r: r['hr'],                             lambda r: f"{r['hr']:.0f}"),
    Column('fip',    'FIP',    56,  'e',      lambda r: _num(r['fip'], _WORST_LOW),          lambda r: _fmt(r['fip'], '.2f')),
]

HITTER_COLUMNS: list[Column] = [
    Column('name',   'Player', 0,   'w',      lambda r: r['name'].lower(),                  lambda r: r['name']),
    Column('team',   'Team',   150, 'w',      lambda r: r['team'],                          lambda r: r['team']),
    Column('pos',    'Pos',    44,  'center', lambda r: r['pos'],                            lambda r: r['pos']),
    Column('rating', 'Rating', 62,  'e',      lambda r: r['rating'],                         lambda r: f"{r['rating']:.0f}"),
    Column('avg',    'AVG',    56,  'e',      lambda r: _num(r['avg'], _WORST_HIGH),         lambda r: _fmt(r['avg'], '.3f')),
    Column('obp',    'OBP',    56,  'e',      lambda r: _num(r['obp'], _WORST_HIGH),         lambda r: _fmt(r['obp'], '.3f')),
    Column('slg',    'SLG',    56,  'e',      lambda r: _num(r['slg'], _WORST_HIGH),         lambda r: _fmt(r['slg'], '.3f')),
    Column('ops',    'OPS',    58,  'e',      lambda r: _num(r['ops'], _WORST_HIGH),         lambda r: _fmt(r['ops'], '.3f')),
    Column('hr',     'HR',     44,  'e',      lambda r: r['hr'],                             lambda r: f"{r['hr']:.0f}"),
    Column('bb_pct', 'BB%',    54,  'e',      lambda r: _num(r['bb_pct'], _WORST_HIGH),      lambda r: _fmt(r['bb_pct'] * 100 if r['bb_pct'] is not None else None, '.1f')),
    Column('k_pct',  'K%',     54,  'e',      lambda r: _num(r['k_pct'], _WORST_LOW),        lambda r: _fmt(r['k_pct'] * 100 if r['k_pct'] is not None else None, '.1f')),
]
