# ==============================================================================
# QUALIFICATION
# gui/player_tab/qualification.py
#
# Applies MLB's official rate-stat qualification standard (3.1 PA / team
# game for hitters, 1.0 IP / team game for pitchers) so the Player Tab
# reads like a real leaderboard. Tracks whichever view is on screen —
# games played so far, or the full projected season for the Simulated view.
# ==============================================================================

from __future__ import annotations

from models.simulation_result import SimulationResult

#MLB's official batter qualification rate — 502 PA over a 162-game season
PA_PER_TEAM_GAME = 3.1
#MLB's official pitcher qualification rate — 162 IP over a 162-game season
IP_PER_TEAM_GAME = 1.0


def _team_games(result: SimulationResult, team: str, simulated: bool) -> float:
    #the same (W, L) source project_rows() already uses for its own ratio, so "team games" here always matches whatever scaled the row's IP/PA
    w, l = result.projected_win_loss(team) if simulated else result.win_loss(team)
    return w + l


def filter_qualified_pitchers(rows: list[dict], result: SimulationResult, simulated: bool) -> list[dict]:
    #a team with 0 games played has nothing to qualify against yet
    return [
        row for row in rows
        if (games := _team_games(result, row['team'], simulated)) > 0
        and (row['ip'] or 0.0) >= games * IP_PER_TEAM_GAME
    ]


def filter_qualified_hitters(rows: list[dict], result: SimulationResult, simulated: bool) -> list[dict]:
    return [
        row for row in rows
        if (games := _team_games(result, row['team'], simulated)) > 0
        and (row['pa'] or 0) >= games * PA_PER_TEAM_GAME
    ]
