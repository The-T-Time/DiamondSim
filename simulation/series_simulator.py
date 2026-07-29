# ==============================================================================
# SERIES SIMULATOR
# simulation/series_simulator.py
#
# Simulates a single best-of-N playoff series between two seeded teams,
# used for every round of the bracket. Elo is fixed for the whole series;
# starting-pitcher matchups and bullpen fatigue layer on top via optional
# parameters (rotations/bullpens/fatigue).
# ==============================================================================

from __future__ import annotations

import random

from models.bullpen import Bullpen
from models.hitter import TeamLineups
from models.pitcher import Rotation
from models.simulation_config import SimulationConfig
from models.team import TeamName
from simulation.elo import EloTable, expected_home_win_prob
from simulation.fatigue import BullpenFatigueTracker
from simulation.pitching import game_win_prob, is_taxing_game, simulate_game_margin

#Home-team pattern per series length. True = the series host (higher seed /
#better record) is home for that game; False = the other club is home.
#best-of-3 Wild Card: host hosts all three (the real MLB WC rule).
#best-of-5 Division Series: 2-2-1. best-of-7 LCS/World Series: 2-3-2.
HOME_PATTERNS: dict[int, list[bool]] = {
    3: [True, True, True],
    5: [True, True, False, False, True],
    7: [True, True, False, False, False, True, True],
}

#Rest applied to both series participants between each game played WITHIN
#a series — a stand-in for the travel/scheduling gaps built into a real
#playoff calendar (e.g. the DS's 2-2-1 format has a travel day before
#game 3). playoff_simulator.py applies a larger gap BETWEEN rounds.
INTRA_SERIES_REST_DAYS: float = 1.0


def play_series(
    higher: TeamName,
    lower: TeamName,
    elo: EloTable,
    cfg: SimulationConfig,
    rng: random.Random,
    best_of: int,
    rotations: dict[TeamName, Rotation] | None = None,
    bullpens: dict[TeamName, Bullpen] | None = None,
    fatigue: BullpenFatigueTracker | None = None,
    lineups: dict[TeamName, TeamLineups] | None = None,
) -> TeamName:
    """
    Simulate a best-of-`best_of` series and return the winner. `higher` is
    the series host (higher seed / better record); home-field alternates by
    MLB's real format (2-2-1 / 2-3-2), so the win probability is recomputed
    per game with that game's actual home team. Stops as soon as a club
    clinches — a sweep doesn't play out the rest of the pattern.

    `rotations`/`bullpens`/`fatigue` are optional:
      - Leave all None (the default) for the original pure-team-Elo game
        probability.
      - Pass `rotations` (and cfg.starting_pitcher_impact is True) to have
        each game's win probability reflect that game's starter matchup —
        game 1 of this series starts each team's Rotation over from its
        ace (see models/pitcher.py's rotation-cycling note for why that's
        a deliberate simplification rather than tracking rest days).
      - Additionally pass `bullpens` + a shared `fatigue` tracker (and
        cfg.bullpen_fatigue_impact is True) to have each game also record
        bullpen wear-and-tear into `fatigue` and apply the resulting
        penalty to both teams' win probability. `fatigue` is meant to be
        threaded across an entire postseason run by the caller (see
        playoff_simulator.py) so fatigue from an earlier round persists.
        `bullpens` also contributes each pen's BASELINE rating
        independent of fatigue, as long as it's passed at all.

    `lineups` is optional: pass it (with cfg.lineup_impact
    True and `rotations` also given, since picking a lineup needs to know
    the OPPOSING starter's throwing hand) to have each game's win
    probability also reflect that day's matchup-specific lineup — see
    models.hitter.TeamLineups.for_opposing_pitcher.
    """
    need = best_of // 2 + 1
    pattern = HOME_PATTERNS[best_of]
    use_pitching = cfg.starting_pitcher_impact and rotations is not None
    use_bullpen = cfg.bullpen_fatigue_impact and bullpens is not None and fatigue is not None
    use_lineups = cfg.lineup_impact and lineups is not None and use_pitching

    hi_wins = lo_wins = 0
    for game_index, host_is_home in enumerate(pattern):
        if hi_wins == need or lo_wins == need:
            break
        home, away = (higher, lower) if host_is_home else (lower, higher)

        if use_pitching:
            home_starter = rotations[home].starter_for_game(game_index)
            away_starter = rotations[away].starter_for_game(game_index)
            home_penalty = fatigue.elo_penalty(home) if use_bullpen else 0.0
            away_penalty = fatigue.elo_penalty(away) if use_bullpen else 0.0

            home_lineup_rating = away_lineup_rating = None
            if use_lineups:
                home_lineup_rating = lineups[home].for_opposing_pitcher(away_starter.throws).lineup_rating
                away_lineup_rating = lineups[away].for_opposing_pitcher(home_starter.throws).lineup_rating

            home_bullpen_rating = bullpens[home].strength if bullpens is not None else None
            away_bullpen_rating = bullpens[away].strength if bullpens is not None else None

            home_win_prob = game_win_prob(
                elo[home], elo[away],
                home_starter.rating, away_starter.rating,
                home_penalty, away_penalty,
                cfg,
                home_lineup_rating=home_lineup_rating, away_lineup_rating=away_lineup_rating,
                home_bullpen_rating=home_bullpen_rating, away_bullpen_rating=away_bullpen_rating,
            )
        else:
            home_win_prob = expected_home_win_prob(elo[home], elo[away], cfg)

        home_wins = rng.random() < home_win_prob
        higher_won = home_wins if host_is_home else not home_wins
        if higher_won:
            hi_wins += 1
        else:
            lo_wins += 1

        if use_bullpen:
            winner, loser = (home, away) if home_wins else (away, home)
            margin = simulate_game_margin(rng, elo[winner] - elo[loser], cfg)
            taxing = is_taxing_game(margin)
            fatigue.record_game(home, taxing)
            fatigue.record_game(away, taxing)
            #Travel/scheduling gap before the next game in this series.
            fatigue.rest(higher, INTRA_SERIES_REST_DAYS)
            fatigue.rest(lower, INTRA_SERIES_REST_DAYS)

    return higher if hi_wins == need else lower
