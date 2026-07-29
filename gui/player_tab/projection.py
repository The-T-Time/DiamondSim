# ==============================================================================
# PLAYER STAT PROJECTION
# gui/player_tab/projection.py
#
# Scales a player's current counting stats forward by how much more of
# the season their team is projected to play (rate stats stay as-is).
# There's no per-player game simulation, so this is "if they keep
# performing the way they have been," not a new forecast.
# ==============================================================================

from __future__ import annotations

from models.simulation_result import SimulationResult

#Counting stats that grow with games played — scaled by the team's
#season-completion ratio. Anything not listed here (rating, ERA, FIP, AVG,
#OBP, SLG, OPS, BB%, K%, position, status) is a rate/descriptive stat and
#is left unchanged.
_PITCHER_COUNTING_FIELDS = ('wins', 'losses', 'ip', 'so', 'bb', 'hr')
_HITTER_COUNTING_FIELDS = ('hr', 'pa')


def _team_completion_ratio(result: SimulationResult, team: str) -> float:
    """projected total games / games played so far, for one team. 1.0
    (no scaling) if there's no projection or the team hasn't played yet."""
    played_w, played_l = result.win_loss(team)
    played_games = played_w + played_l
    if played_games == 0:
        return 1.0
    proj_w, proj_l = result.projected_win_loss(team)
    proj_games = proj_w + proj_l
    if proj_games <= 0:
        return 1.0
    return proj_games / played_games


def project_rows(rows: list[dict], result: SimulationResult, counting_fields: tuple[str, ...]) -> list[dict]:
    """Returns a new list of row dicts with counting_fields scaled forward
    by each player's team's season-completion ratio. None values (players
    with no innings/plate-appearances yet) are left as None — there's
    nothing to scale."""
    ratio_by_team: dict[str, float] = {}
    projected: list[dict] = []
    for row in rows:
        team = row['team']
        ratio = ratio_by_team.get(team)
        if ratio is None:
            ratio = _team_completion_ratio(result, team)
            ratio_by_team[team] = ratio

        new_row = dict(row)
        for field in counting_fields:
            value = row.get(field)
            if value is not None:
                new_row[field] = value * ratio
        projected.append(new_row)
    return projected


def project_pitcher_rows(rows: list[dict], result: SimulationResult) -> list[dict]:
    return project_rows(rows, result, _PITCHER_COUNTING_FIELDS)


def project_hitter_rows(rows: list[dict], result: SimulationResult) -> list[dict]:
    return project_rows(rows, result, _HITTER_COUNTING_FIELDS)
