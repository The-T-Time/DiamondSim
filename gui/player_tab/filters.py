# ==============================================================================
# FILTERS
# gui/player_tab/filters.py
#
# Pure filtering logic — no Tk. Three dropdowns (League/Division/Team)
# plus free-text search, combined with AND logic. Kept separate from
# tab.py so the rules are testable without a display.
# ==============================================================================

from __future__ import annotations

ALL_LEAGUES = 'All'
ALL_DIVISIONS = 'All'
ALL_TEAMS_OPTION = 'All'

DIVISIONS = ['AL East', 'AL Central', 'AL West', 'NL East', 'NL Central', 'NL West']


def filter_rows(
    rows: list[dict],
    league: str = ALL_LEAGUES,
    division: str = ALL_DIVISIONS,
    team: str = ALL_TEAMS_OPTION,
    search: str = '',
) -> list[dict]:
    """Returns the subset of `rows` matching every given filter. Any filter
    left at its "All" default is a no-op — all three at once ("MLB") is the
    whole league. `search` matches case-insensitively against the player's
    name (substring match)."""
    result = rows
    if league != ALL_LEAGUES:
        result = [r for r in result if r['league'] == league]
    if division != ALL_DIVISIONS:
        result = [r for r in result if r['div'] == division]
    if team != ALL_TEAMS_OPTION:
        result = [r for r in result if r['team'] == team]
    query = search.strip().lower()
    if query:
        result = [r for r in result if query in r['name'].lower()]
    return result
