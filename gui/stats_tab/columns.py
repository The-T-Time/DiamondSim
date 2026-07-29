# ==============================================================================
# COLUMNS
# gui/stats_tab/columns.py
#
# Column specs for the four Statistics sub-tabs (Power Rankings, Run
# Differential, Splits, Momentum): (col_id, header, pixel_width, anchor,
# sort_key_fn, display_fn) tuples; pixel_width 0 = measured at runtime.
# ==============================================================================

from __future__ import annotations

from typing import Any, Callable, Optional

ColumnSpec = tuple[str, str, int, str, Optional[Callable[[dict], Any]], Callable[[dict], str]]


def column_spec(cid: str, hdr: str, w: int, anchor: str,
                key_fn: Callable[[dict], Any] | None, disp_fn: Callable[[dict], str]) -> ColumnSpec:
    return (cid, hdr, w, anchor, key_fn, disp_fn)


def signed(v: float, fmt: str = '.1f') -> str:
    """Formats a number with an explicit leading '+' for non-negative
    values, e.g. signed(4.2) -> '+4.2', signed(-1.5) -> '-1.5'."""
    return ('+' if v >= 0 else '') + format(v, fmt)


POWER_COLS = [
    column_spec('rank', '#',       30, 'center', None,                        lambda s: str(s.get('_rank', ''))),
    column_spec('team', 'Team',     0, 'w',      None,                        lambda s: s['_team']),
    column_spec('w',    'W',       36, 'center', lambda s: s['W'],            lambda s: f"{s['W']:.0f}"),
    column_spec('l',    'L',       36, 'center', lambda s: s['L'],            lambda s: f"{s['L']:.0f}"),
    column_spec('pct',  'PCT',     52, 'e',      lambda s: s['PCT'],          lambda s: f"{s['PCT']:.3f}"),
    column_spec('elo',  'Elo',     54, 'e',      lambda s: s['ELO'],          lambda s: f"{s['ELO']:.0f}"),
    column_spec('dElo', 'ΔElo',    58, 'e',      lambda s: s['ELO_DELTA'],    lambda s: signed(s['ELO_DELTA'])),
    column_spec('odds', 'Playoff%',65, 'e',      lambda s: s['ODDS'],         lambda s: f"{s['ODDS']:.1f}%"),
]

RUNS_COLS = [
    column_spec('rank',  '#',      30, 'center', None,                        lambda s: str(s.get('_rank', ''))),
    column_spec('team',  'Team',    0, 'w',      None,                        lambda s: s['_team']),
    column_spec('rs',    'RS',     46, 'e',      lambda s: s['RS'],           lambda s: f"{s['RS']:.0f}"),
    column_spec('ra',    'RA',     46, 'e',      lambda s: s['RA'],           lambda s: f"{s['RA']:.0f}"),
    column_spec('rd',    'RD',     52, 'e',      lambda s: s['RD'],           lambda s: signed(s['RD'], '.0f')),
    column_spec('rsg',   'RS/G',   52, 'e',      lambda s: s['RS_G'],         lambda s: f"{s['RS_G']:.2f}"),
    column_spec('rag',   'RA/G',   52, 'e',      lambda s: s['RA_G'],         lambda s: f"{s['RA_G']:.2f}"),
    column_spec('pyth',  'Pyth W', 58, 'e',      lambda s: s['PYTH_W'],       lambda s: f"{s['PYTH_W']}-{s['PYTH_L']}"),
    column_spec('luck',  'Luck',   50, 'e',      lambda s: s['LUCK'],         lambda s: signed(s['LUCK'], '.0f')),
]

SPLITS_COLS = [
    column_spec('rank',   '#',      30, 'center', None,                       lambda s: str(s.get('_rank', ''))),
    column_spec('team',   'Team',    0, 'w',      None,                       lambda s: s['_team']),
    column_spec('hrec',   'Home',   58, 'center', lambda s: s['HOME_PCT'],    lambda s: s['HOME_REC']),
    column_spec('hpct',   'H-PCT',  52, 'e',      lambda s: s['HOME_PCT'],    lambda s: f"{s['HOME_PCT']:.3f}"),
    column_spec('arec',   'Away',   58, 'center', lambda s: s['AWAY_PCT'],    lambda s: s['AWAY_REC']),
    column_spec('apct',   'A-PCT',  52, 'e',      lambda s: s['AWAY_PCT'],    lambda s: f"{s['AWAY_PCT']:.3f}"),
    column_spec('last10', 'Last 10',58, 'center', lambda s: s['LAST10_W'],    lambda s: s['LAST10']),
    column_spec('streak', 'Streak', 52, 'center', lambda s: s['STREAK_VAL'],  lambda s: s['STREAK']),
]

MOMENTUM_COLS = [
    column_spec('rank',   '#',       30, 'center', None,                      lambda s: str(s.get('_rank', ''))),
    column_spec('team',   'Team',     0, 'w',      None,                      lambda s: s['_team']),
    column_spec('last10', 'Last 10', 58, 'center', lambda s: s['LAST10_W'],   lambda s: s['LAST10']),
    column_spec('streak', 'Streak',  52, 'center', lambda s: s['STREAK_VAL'], lambda s: s['STREAK']),
    column_spec('longw',  'Best Win',62, 'center', lambda s: s['LONG_W'],     lambda s: f"W{s['LONG_W']}"),
    column_spec('dElo',   'ΔElo',    58, 'e',      lambda s: s['ELO_DELTA'],  lambda s: signed(s['ELO_DELTA'])),
    column_spec('odds',   'Playoff%',65, 'e',      lambda s: s['ODDS'],       lambda s: f"{s['ODDS']:.1f}%"),
]
