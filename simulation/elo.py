# ==============================================================================
# ELO RATING SYSTEM
# simulation/elo.py
#
# Core Elo math: win probability, margin-of-victory scaling, per-game
# updates, and replaying a prior season to get closing ratings. Every
# tunable comes from a SimulationConfig passed in by the caller.
# ==============================================================================

from __future__ import annotations

import math as _math

from data.teams import ALL_TEAMS, TEAM_ID_MAP
from data.api import fetch_schedule
from models.simulation_config import SimulationConfig
from models.team import TeamName
from utils.logger import get_logger

logger = get_logger(__name__)

EloTable = dict[TeamName, float]


def _mov_multiplier(run_diff: float, cfg: SimulationConfig = SimulationConfig()) -> float:
    """
    Scales the Elo K-factor by margin of victory.
    log(run_diff) so blowouts matter but don't dominate.
    Returns 1.0 when cfg.mov_weight=0 (pure win/loss mode).
    """
    if cfg.mov_weight == 0 or run_diff <= 1:
        return 1.0
    return 1.0 + cfg.mov_weight * _math.log(run_diff)


def expected_home_win_prob(
    home_elo: float, away_elo: float, cfg: SimulationConfig = SimulationConfig()
) -> float:
    """Return the home team's expected win probability (0-1)."""
    return 1.0 / (1.0 + 10.0 ** ((away_elo - (home_elo + cfg.home_field_advantage)) / 400.0))


def apply_elo_update(
    elo: EloTable,
    home: TeamName,
    away: TeamName,
    home_won: bool,
    margin: float,
    cfg: SimulationConfig = SimulationConfig(),
) -> float:
    """
    Apply a home-centered Elo update for one game result.
    Mutates `elo` in place and returns the pre-update home win probability.
    """
    expected_home = expected_home_win_prob(elo[home], elo[away], cfg)
    delta = cfg.elo_k * _mov_multiplier(margin, cfg) * ((1.0 if home_won else 0.0) - expected_home)
    elo[home] += delta
    elo[away] -= delta
    return expected_home


def compute_regressed_starting_elo(
    season: int, cfg: SimulationConfig = SimulationConfig()
) -> EloTable:
    """YoY-regressed starting Elo for every team entering `season`."""
    prior_closing = calculate_prior_season_closing_elo(season - 1, cfg)
    return {
        t: v * cfg.regression_weight + cfg.elo_baseline * (1 - cfg.regression_weight)
        for t, v in prior_closing.items()
    }


def calculate_prior_season_closing_elo(
    prior_season: int, cfg: SimulationConfig = SimulationConfig()
) -> EloTable:
    """Simulates the entire prior season chronologically to get authentic ending Elos."""
    logger.info("Calculating Elo baseline from %d season history...", prior_season)
    schedule_data = fetch_schedule(prior_season)
    historical_elo: EloTable = {team: cfg.elo_baseline for team in ALL_TEAMS}

    for date_obj in sorted(schedule_data.get('dates', []), key=lambda d: d['date']):
        for game in date_obj.get('games', []):
            if game.get('gameType') != 'R':
                continue
            if game.get('status', {}).get('abstractGameState') != 'Final':
                continue
            home_id = str(game['teams']['home']['team']['id'])
            away_id = str(game['teams']['away']['team']['id'])
            if home_id not in TEAM_ID_MAP or away_id not in TEAM_ID_MAP:
                continue

            home_name = TEAM_ID_MAP[home_id]
            away_name = TEAM_ID_MAP[away_id]
            home_score = game['teams']['home'].get('score', 0)
            away_score = game['teams']['away'].get('score', 0)
            if home_score == away_score:
                continue

            apply_elo_update(
                historical_elo,
                home_name,
                away_name,
                home_score > away_score,
                abs(home_score - away_score),
                cfg,
            )

    return historical_elo
