# ==============================================================================
# PLAYER DIRECTORY
# simulation/player_directory.py
#
# Builds the full-league player list for the Player Tab: every pitcher
# and hitter on every 40-man roster as a row dict, using the same
# fetch/rating pipelines the simulation itself uses. A team that fails to
# fetch is skipped and logged rather than failing the whole directory.
# ==============================================================================

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from data.exceptions import DataFetchError
from data.hitting_stats import fetch_team_hitters
from data.player_stats import fetch_team_pitching_staff
from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.simulation_config import SimulationConfig
from simulation.hitter_rating import blend_offense_rating_components
from simulation.player_rating import blend_rating_components, fip
from utils.logger import get_logger

logger = get_logger(__name__)

_FETCH_WORKERS = 10  #concurrent MLB Stats API requests — enough to erase the network wait without hammering the API


def build_pitcher_rows(season: int, as_of_date: str, cfg: SimulationConfig = SimulationConfig()) -> list[dict]:
    """
    One row per pitcher on every team's 40-man roster:
    name, team, pos ('P'), rating, status, and this season's ERA/W-L/IP/K/
    BB/HR/FIP — plus league/div for the tab's filters. `rating` is the same
    season/last-30-days/career blend the real-stats rotation pipeline uses
    (simulation/player_rating.py), not just this season's raw stats.

    Each team's fetch is independent (its own HTTP call, its own skip-on-
    failure), so all 30 run concurrently on a thread pool instead of one at
    a time — see build_all_team_staffs in simulation/pitching.py for the
    same pattern and full reasoning. Row order within a team's own block is
    preserved; team blocks appear in ALL_TEAMS order regardless of which
    fetch happened to finish first.
    """
    def _rows_for_team(team) -> list[dict]:
        team_id = TEAM_REGISTRY[team].id
        try:
            staff = fetch_team_pitching_staff(team_id, season, as_of_date)
        except DataFetchError as e:
            logger.warning("Skipping %s in the player directory (pitcher fetch failed: %s)", team, e)
            return []

        team_rows = []
        for p in staff:
            line = p.current_season
            rating = blend_rating_components(p.current_season, p.last_30_days, p.career, cfg)
            team_rows.append({
                'name': p.full_name,
                'team': team,
                'pos': 'P',
                'rating': rating,
                'status': p.status_description,
                'era': line.era if line else None,
                'wins': line.wins if line else 0,
                'losses': line.losses if line else 0,
                'ip': line.innings_pitched if line else 0.0,
                'so': line.strikeouts if line else 0,
                'bb': line.walks if line else 0,
                'hr': line.home_runs if line else 0,
                'fip': fip(line, cfg.pitcher_fip_constant) if line and line.innings_pitched > 0 else None,
                'league': TEAM_REGISTRY[team].league,
                'div': TEAM_REGISTRY[team].division,
            })
        return team_rows

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        for team_rows in pool.map(_rows_for_team, ALL_TEAMS):
            rows.extend(team_rows)
    return rows


def build_hitter_rows(season: int, as_of_date: str, cfg: SimulationConfig = SimulationConfig()) -> list[dict]:
    """
    One row per position player on every team's 40-man roster: name, team,
    pos, rating, status, and this season's AVG/OBP/SLG/OPS/HR/BB%/K% — plus
    league/div for the tab's filters. `rating` is the same season/last-30-
    days/career blend the real-stats lineup pipeline uses
    (simulation/hitter_rating.py).

    Each team's fetch is independent (its own HTTP call, its own skip-on-
    failure), so all 30 run concurrently on a thread pool instead of one at
    a time — see build_all_team_staffs in simulation/pitching.py for the
    same pattern and full reasoning. Row order within a team's own block is
    preserved; team blocks appear in ALL_TEAMS order regardless of which
    fetch happened to finish first.
    """
    def _rows_for_team(team) -> list[dict]:
        team_id = TEAM_REGISTRY[team].id
        try:
            hitters = fetch_team_hitters(team_id, season, as_of_date)
        except DataFetchError as e:
            logger.warning("Skipping %s in the player directory (hitter fetch failed: %s)", team, e)
            return []

        team_rows = []
        for h in hitters:
            line = h.current_season
            rating = blend_offense_rating_components(h.current_season, h.last_30_days, h.career, cfg)
            team_rows.append({
                'name': h.full_name,
                'team': team,
                'pos': h.position,
                'rating': rating,
                'status': h.status_description,
                'avg': line.avg if line else None,
                'obp': line.obp if line else None,
                'slg': line.slg if line else None,
                'ops': line.ops if line else None,
                'hr': line.home_runs if line else 0,
                'pa': line.plate_appearances if line else 0,
                'bb_pct': line.bb_rate if line else None,
                'k_pct': line.k_rate if line else None,
                'league': TEAM_REGISTRY[team].league,
                'div': TEAM_REGISTRY[team].division,
            })
        return team_rows

    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        for team_rows in pool.map(_rows_for_team, ALL_TEAMS):
            rows.extend(team_rows)
    return rows
