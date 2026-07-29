# ==============================================================================
# FORMATTERS
# gui/teams_tab/formatters.py
#
# Split out of the former gui/teams_tab.py into a package.
# ==============================================================================

from __future__ import annotations

from models.simulation_result import SimulationResult
from gui.widgets import C_DARK, C_GREEN, C_RED

#── Treeview column definitions (pixel widths) ────────────────────────────────
#ALL columns stretch=False.  The Treeview widget itself still expands to fill
#the pane, but columns keep their pixel widths — extra space shows as empty
#background when the pane is wide, and the rightmost columns clip off screen
#when the pane is narrowed.  This gives the "sliding panel" feel the user
#wants: drag left → stats disappear; drag right → empty background, no shift.
#
#"Arizona Diamondbacks" is the longest name (20 chars).  At Helvetica 9 bold
#with Treeview's 2px internal side padding, 230px comfortably fits it.
#The left sash stop is set to 230px + scrollbar (~17px) + 4px border = 251px,
#which means the sash rests exactly at the right edge of the longest name.
TV_COLS: list[tuple[str, str, str, int, str, bool]] = [
    ('name', 'name', 'Team',  230, 'w', False),
    ('wl',   'wl',   'W-L',   62, 'e', False),
    ('pct',  'pct',  'PCT',   56, 'e', False),
    ('odds', 'odds', 'Odds',  68, 'e', False),
    ('elo',  'elo',  'Elo',   58, 'e', False),
]
DEFAULT_LEFT_W = sum(w for *_, w, _, _ in TV_COLS) + 20   #+scrollbar
#Left sash stop = name column + scrollbar: stats can all slide off, names never
TEAM_COL_W     = TV_COLS[0][3] + 21    #230 + scrollbar width


def pct_str(w: int, l: int) -> str:
    return f"{w/(w+l):.3f}" if (w + l) else ".000"


def elo_fg(delta: float) -> str:
    return C_GREEN if delta > 0 else (C_RED if delta < 0 else C_DARK)


def sort_key(col: str, team: str, result: SimulationResult) -> float | str:
    w, l = result.win_loss(team)
    if col == 'name': return team.lower()
    if col == 'wl':   return w
    if col == 'pct':  return result.pct(team)
    if col == 'odds': return result.playoff_odds.get(team, 0.0)
    if col == 'elo':  return result.live_elo.get(team, 1500.0)
    return 0.0
