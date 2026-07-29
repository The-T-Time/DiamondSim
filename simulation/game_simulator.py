# ==============================================================================
# GAME SIMULATOR
# simulation/game_simulator.py
#
# Simulates the outcome of one regular-season game from two teams' Elo and
# applies the resulting update. Called once per unplayed game, per Monte
# Carlo iteration. Not used by the postseason bracket — those games don't
# move Elo game-to-game (see playoff_simulator.py).
# ==============================================================================

from __future__ import annotations

import random
from dataclasses import dataclass

from models.simulation_config import SimulationConfig
from models.team import TeamName
from simulation.elo import EloTable, apply_elo_update, expected_home_win_prob


@dataclass(frozen=True)
class GameSimResult:
    winner: TeamName
    loser: TeamName
    margin: int
    winner_runs: int
    loser_runs: int


def simulate_regular_season_game(
    home: TeamName,
    away: TeamName,
    elo: EloTable,
    cfg: SimulationConfig,
    rng: random.Random,
) -> GameSimResult:
    """
    Simulates one unplayed regular-season game and updates `elo` in place
    (both teams' ratings move as a result — this is what lets a hot streak
    compound across the rest of a simulated season). Returns who won, who
    lost, and the simulated run margin so the caller can update W/L and
    head-to-head records.
    """
    exp_home = expected_home_win_prob(elo[home], elo[away], cfg)
    if rng.random() < exp_home:
        winner, loser = home, away
    else:
        winner, loser = away, home

    elo_diff = elo[winner] - elo[loser]
    expected_margin = max(1.0, 1.0 + elo_diff / 200.0)
    margin = max(1, min(cfg.sim_margin_cap, round(rng.gauss(expected_margin, 2.0))))
    apply_elo_update(elo, home, away, winner == home, margin, cfg)

    #Approximate box score: the loser's runs are drawn around the MLB
    #league-average runs/game (~4.3), and the winner's runs are set so the
    #margin comes out right. This is only precise enough for tracking
    #season-long team runs-scored/runs-allowed averages — it is not a
    #substitute for an actual play-by-play simulation.
    loser_runs = max(0, round(rng.gauss(4.3, 1.6)))
    winner_runs = loser_runs + margin

    return GameSimResult(winner=winner, loser=loser, margin=margin,
                         winner_runs=winner_runs, loser_runs=loser_runs)
