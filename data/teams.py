# ==============================================================================
# TEAM MASTER DATA
# data/teams.py
#
# Static reference data: team IDs, names, divisions, leagues. No logic
# here — just the lookup tables (TEAM_REGISTRY, ALL_TEAMS) everything
# else builds on.
# ==============================================================================

from __future__ import annotations

from models.team import Team, TeamName

#(mlb_team_id, name, division) — the only data that actually varies.
_RAW_TEAM_DATA: list[tuple[int, str, str]] = [
    #AL East
    (147, 'New York Yankees',      'AL East'),
    (139, 'Tampa Bay Rays',        'AL East'),
    (141, 'Toronto Blue Jays',     'AL East'),
    (110, 'Baltimore Orioles',     'AL East'),
    (111, 'Boston Red Sox',        'AL East'),
    #AL Central
    (145, 'Chicago White Sox',     'AL Central'),
    (114, 'Cleveland Guardians',   'AL Central'),
    (142, 'Minnesota Twins',       'AL Central'),
    (116, 'Detroit Tigers',        'AL Central'),
    (118, 'Kansas City Royals',    'AL Central'),
    #AL West
    (136, 'Seattle Mariners',      'AL West'),
    (133, 'Athletics',             'AL West'),
    (140, 'Texas Rangers',         'AL West'),
    (117, 'Houston Astros',        'AL West'),
    (108, 'Los Angeles Angels',    'AL West'),
    #NL East
    (144, 'Atlanta Braves',        'NL East'),
    (143, 'Philadelphia Phillies', 'NL East'),
    (146, 'Miami Marlins',         'NL East'),
    (120, 'Washington Nationals',  'NL East'),
    (121, 'New York Mets',         'NL East'),
    #NL Central
    (158, 'Milwaukee Brewers',     'NL Central'),
    (138, 'St. Louis Cardinals',   'NL Central'),
    (112, 'Chicago Cubs',          'NL Central'),
    (134, 'Pittsburgh Pirates',    'NL Central'),
    (113, 'Cincinnati Reds',       'NL Central'),
    #NL West
    (119, 'Los Angeles Dodgers',   'NL West'),
    (135, 'San Diego Padres',      'NL West'),
    (109, 'Arizona Diamondbacks',  'NL West'),
    (137, 'San Francisco Giants',  'NL West'),
    (115, 'Colorado Rockies',      'NL West'),
]


def _build_team(team_id: int, name: str, division: str) -> Team:
    league = 'AL' if division.startswith('AL') else 'NL'
    return Team(id=team_id, name=name, division=division, league=league)


TEAMS: list[Team] = [_build_team(tid, name, div) for tid, name, div in _RAW_TEAM_DATA]

#Canonical lookups — the only two dicts you should need for team metadata.
TEAM_REGISTRY: dict[TeamName, Team] = {t.name: t for t in TEAMS}
TEAM_REGISTRY_BY_ID: dict[str, Team] = {str(t.id): t for t in TEAMS}


def get_team(name: TeamName) -> Team:
    """Full Team record (division, league, elo) for a display name."""
    return TEAM_REGISTRY[name]


def get_team_by_id(mlb_team_id: int | str) -> Team:
    """Full Team record for an MLB Stats API numeric team id."""
    return TEAM_REGISTRY_BY_ID[str(mlb_team_id)]


#── Still string-keyed, and staying that way ────────────────────────────────
#TEAM_ID_MAP: MLB's numeric team id -> our display name, needed to parse the
#  raw schedule JSON (that's an identity mapping, not a Team attribute).
#ALL_TEAMS: plain list of names, used throughout the sim engine as dict keys
#  for per-team scratch state (records, h2h, working Elo). Iterating Team
#  objects there would just mean writing `.name` at every call site for no
#  benefit — this one's pulling its weight, unlike TEAM_DIVS/TEAM_LEAGUES.
TEAM_ID_MAP: dict[str, TeamName] = {tid: t.name for tid, t in TEAM_REGISTRY_BY_ID.items()}
ALL_TEAMS: list[TeamName] = [t.name for t in TEAMS]
