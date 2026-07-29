# ==============================================================================
# PITCHING
# simulation/pitching.py
#
# Builds a team's Rotation/Bullpen (real or synthetic fallback), and
# turns a (team Elo, starter, bullpen fatigue) combination into one
# postseason game's win probability — the flow: starting pitcher ->
# bullpen usage -> fatigue penalty -> game win probability.
# ==============================================================================

from __future__ import annotations

import random
from concurrent.futures import ThreadPoolExecutor

from data.exceptions import DataFetchError
from data.player_stats import fetch_team_pitching_staff
from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.bullpen import Bullpen, Reliever
from models.pitcher import Pitcher, Rotation
from models.pitching_stats import RawPlayerRecord
from models.simulation_config import SimulationConfig
from models.team import TeamName
from simulation.deterministic_seed import team_seed
from simulation.elo import expected_home_win_prob
from simulation.player_rating import REPLACEMENT_RATING, blend_rating_components
from utils.logger import get_logger

logger = get_logger(__name__)

#------------------------------------------------------------------------------
#Matchup weighting
#------------------------------------------------------------------------------

#How much of a starter's rating gap over their counterpart translates into
#Elo points for that one game. 1.0 would treat the starter matchup as just
#as decisive as the full team-talent gap; keeping it below 1.0 reflects
#that a start is one part (not all nine) of a ballgame — the lineup,
#defense, and bullpen (captured in team Elo / bullpen fatigue) still matter.
STARTER_ELO_WEIGHT: float = 0.6

#How much of a lineup's rating gap (vs the OPPOSING starter's throwing
#hand — see models/hitter.TeamLineups.for_opposing_pitcher) over its
#counterpart translates into Elo points for that one game. Smaller than
#STARTER_ELO_WEIGHT: a starting pitcher personally determines far more of
#a single game's shape than which of two lineups a team happens to run out.
LINEUP_ELO_WEIGHT: float = 0.4

#How much of a bullpen's BASELINE rating gap (a genuinely good pen vs a
#mediocre one, both equally rested) translates into Elo points for that
#one game — separate from BULLPEN_ELO_WEIGHT's fatigue PENALTY below,
#which only measures how tired a pen currently is, never how good it is
#at full rest. Without this, Bullpen.strength was computed but never
#actually read anywhere in the win-probability math.
BULLPEN_RATING_ELO_WEIGHT: float = 0.3

#Bullpen fatigue penalties (see simulation/fatigue.py) are already
#expressed in Elo points, so this is a straight 1:1 pass-through weight —
#kept as a named constant so it's as easy to retune as STARTER_ELO_WEIGHT.
BULLPEN_ELO_WEIGHT: float = 1.0

#A game is "taxing" on the bullpen — burns high-leverage arms rather than
#letting a long man mop up — when the simulated final margin is this close
#or tighter. Feeds simulation/fatigue.py's BullpenFatigueTracker.
TAXING_MARGIN_THRESHOLD: int = 2


def game_win_prob(
    home_elo: float,
    away_elo: float,
    home_starter_rating: float,
    away_starter_rating: float,
    home_bullpen_penalty: float,
    away_bullpen_penalty: float,
    cfg: SimulationConfig = SimulationConfig(),
    *,
    home_lineup_rating: float | None = None,
    away_lineup_rating: float | None = None,
    home_bullpen_rating: float | None = None,
    away_bullpen_rating: float | None = None,
) -> float:
    """
    Home win probability for one game, given each side's team Elo, today's
    starter, each bullpen's current fatigue penalty (Elo points to
    subtract — 0 for a fully rested pen, see BullpenFatigueTracker.
    elo_penalty), and each side's lineup rating (already
    selected for the OPPOSING starter's throwing hand, see models.hitter.
    TeamLineups.for_opposing_pitcher) and each bullpen's baseline rating
    (Bullpen.strength, independent of fatigue). Folds all of it into an
    "effective" home Elo and reuses the same logistic curve as the rest of
    the sim (simulation.elo.expected_home_win_prob), so every edge behaves
    exactly like an Elo edge everywhere else in the engine — same shape,
    same home-field constant, same math.

    This "effective" Elo exists for exactly one game and is never written
    back anywhere — a team's actual, permanent Elo rating only ever moves
    via a real win/loss (simulation.elo.apply_elo_update). Today's ace, a
    lefty-mashing lineup, or a lights-out bullpen all matter for today's
    game only; tomorrow the team is rated on its record again.

    The lineup/bullpen-rating keyword args are optional (default None,
    meaning "no adjustment") so existing callers that only have a starter
    matchup and fatigue penalties keep working unchanged.
    """
    starter_adj = (home_starter_rating - away_starter_rating) * STARTER_ELO_WEIGHT
    bullpen_fatigue_adj = (away_bullpen_penalty - home_bullpen_penalty) * BULLPEN_ELO_WEIGHT

    lineup_adj = 0.0
    if home_lineup_rating is not None and away_lineup_rating is not None:
        lineup_adj = (home_lineup_rating - away_lineup_rating) * LINEUP_ELO_WEIGHT

    bullpen_rating_adj = 0.0
    if home_bullpen_rating is not None and away_bullpen_rating is not None:
        bullpen_rating_adj = (home_bullpen_rating - away_bullpen_rating) * BULLPEN_RATING_ELO_WEIGHT

    effective_home_elo = home_elo + starter_adj + bullpen_fatigue_adj + lineup_adj + bullpen_rating_adj
    return expected_home_win_prob(effective_home_elo, away_elo, cfg)


def is_taxing_game(margin: int) -> bool:
    """Whether a game this close would have burned high-leverage relievers."""
    return margin <= TAXING_MARGIN_THRESHOLD


def simulate_game_margin(
    rng: random.Random, elo_diff: float, cfg: SimulationConfig = SimulationConfig()
) -> int:
    """
    Simulated final run margin for a game, given the winner-minus-loser Elo
    gap. Deliberately mirrors game_simulator.simulate_regular_season_game's
    margin formula (same expected-margin curve, same Gaussian noise, same
    cfg.sim_margin_cap) so postseason margins feel like the same sport as
    regular-season ones — kept as its own copy rather than a shared import
    because the two call sites simulate margin for different reasons (Elo
    updates there vs. bullpen-fatigue classification here) and shouldn't be
    coupled just because today's formula happens to match.
    """
    expected_margin = max(1.0, 1.0 + elo_diff / 200.0)
    return max(1, min(cfg.sim_margin_cap, round(rng.gauss(expected_margin, 2.0))))


#------------------------------------------------------------------------------
#Default staff generation
#------------------------------------------------------------------------------

#Rating offsets from team Elo for a 5-man rotation, ace first. Spread is
#wide enough that "Game 1 ace vs Game 1 ace" is a materially different
#matchup than "Game 4 #4 starter vs #4 starter" without a great team's #5
#starter being unrealistically bad.
_ROTATION_OFFSETS: tuple[float, ...] = (55.0, 20.0, -5.0, -30.0, -55.0)

#(role label, rating offset from team Elo, leverage) for a 6-man bullpen,
#highest-leverage first.
_BULLPEN_ROLES: tuple[tuple[str, float, float], ...] = (
    ('CL',  35.0, 1.0),
    ('SU1', 20.0, 0.85),
    ('SU2', 10.0, 0.7),
    ('MID1', -5.0, 0.5),
    ('MID2', -15.0, 0.4),
    ('LR',  -25.0, 0.3),
)

#Small per-arm random jitter so two teams with identical Elo don't get
#byte-for-byte identical staffs.
_JITTER: float = 8.0


def default_rotation_for_team(team: TeamName, team_elo: float) -> Rotation:
    """
    Synthesize a 5-man rotation for `team`, scaled off `team_elo` since
    there's no real roster data source wired in yet (see module docstring).
    Deterministic per team name; varies with team_elo so a contender's
    rotation actually looks like a contender's.
    """
    rng = team_seed(team, salt=0x50495443)  #'PITC'
    return Rotation(starters=tuple(
        Pitcher(
            name=f"{team} SP{i + 1}",
            rating=max(1.0, team_elo + offset + rng.uniform(-_JITTER, _JITTER)),
        )
        for i, offset in enumerate(_ROTATION_OFFSETS)
    ))


def default_bullpen_for_team(team: TeamName, team_elo: float) -> Bullpen:
    """Synthesize a 6-man bullpen for `team`, same approach/caveats as
    default_rotation_for_team above."""
    rng = team_seed(team, salt=0x42554c4c)  #'BULL'
    return Bullpen(relievers=tuple(
        Reliever(
            name=f"{team} {label}",
            rating=max(1.0, team_elo + offset + rng.uniform(-_JITTER, _JITTER)),
            leverage=leverage,
        )
        for label, offset, leverage in _BULLPEN_ROLES
    ))


#------------------------------------------------------------------------------
#Real staff generation
#------------------------------------------------------------------------------

#How many of a team's highest-rated starter-role arms make the rotation /
#reliever-role arms make the bullpen. Same shape as the synthetic staffs
#(5 starters, 6 relievers) so a real staff and a fallback synthetic staff
#behave identically everywhere downstream (series length, rotation cycling).
REAL_ROTATION_SIZE: int = 5
REAL_BULLPEN_SIZE: int = 6

#Leverage curve for real relievers, best arm first: 1.0 (closer) down to
#0.3 (long man), matching the endpoints of the synthetic _BULLPEN_ROLES
#curve above so a real bullpen's `strength` weighting behaves the same way.
_LEVERAGE_TOP: float = 1.0
_LEVERAGE_BOTTOM: float = 0.3


def _leverage_for_rank(rank: int, bullpen_size: int) -> float:
    """Leverage for the `rank`-th best reliever (0 = best arm) out of
    `bullpen_size` total, interpolating linearly from _LEVERAGE_TOP down to
    _LEVERAGE_BOTTOM."""
    if bullpen_size <= 1:
        return _LEVERAGE_TOP
    frac = rank / (bullpen_size - 1)
    return _LEVERAGE_TOP - (_LEVERAGE_TOP - _LEVERAGE_BOTTOM) * frac


def _rate_staff(
    staff: list[RawPlayerRecord], cfg: SimulationConfig
) -> list[tuple[RawPlayerRecord, float]]:
    """Each pitcher paired with their blended current+prior season rating
    (simulation/player_rating.py), computed once so sorting/slicing below
    doesn't recompute it per comparison."""
    return [
        (p, blend_rating_components(p.current_season, p.last_30_days, p.career, cfg))
        for p in staff
    ]


def rotation_from_staff(staff: list[RawPlayerRecord], cfg: SimulationConfig = SimulationConfig()) -> Rotation | None:
    """
    Builds a real Rotation from `staff` (one team's parsed 40-man roster):
    the REAL_ROTATION_SIZE highest-rated starter-role arms who are actually
    available (not hurt/optioned/suspended), ace first. Returns None if no
    starter-role arm on the roster is available — the caller
    (build_team_staff) falls back to the synthetic generator in that case.

    Unavailable starter-role arms are surfaced on Rotation.unavailable
    rather than silently dropped, at whatever rating they'd have earned had
    they been healthy — that's what makes losing a real ace show up as a
    real, named, highly-rated gap instead of an invisible one.
    """
    rated = _rate_staff([p for p in staff if p.is_mostly_starter], cfg)
    available = sorted((pair for pair in rated if pair[0].is_available), key=lambda pair: pair[1], reverse=True)
    unavailable = sorted((pair for pair in rated if not pair[0].is_available), key=lambda pair: pair[1], reverse=True)

    if not available:
        return None

    starters = tuple(
        Pitcher(name=p.full_name, rating=rating, fip=None, status=p.status_description,
                throws=p.throws if p.throws in ('L', 'R') else 'R')
        for p, rating in available[:REAL_ROTATION_SIZE]
    )
    unavailable_pitchers = tuple(
        Pitcher(name=p.full_name, rating=rating, fip=None, status=p.status_description,
                throws=p.throws if p.throws in ('L', 'R') else 'R')
        for p, rating in unavailable
    )
    return Rotation(starters=starters, unavailable=unavailable_pitchers)


def bullpen_from_staff(staff: list[RawPlayerRecord], cfg: SimulationConfig = SimulationConfig()) -> Bullpen | None:
    """
    Builds a real Bullpen from `staff`: the REAL_BULLPEN_SIZE highest-rated
    reliever-role arms who are available, leverage-ranked best arm first.
    Returns None if no reliever-role arm is available — the caller
    (build_team_staff) falls back to the synthetic generator in that case.
    Unavailable reliever-role arms are surfaced on Bullpen.unavailable, same
    reasoning as Rotation.unavailable above.
    """
    rated = _rate_staff([p for p in staff if not p.is_mostly_starter], cfg)
    available = sorted((pair for pair in rated if pair[0].is_available), key=lambda pair: pair[1], reverse=True)
    unavailable = sorted((pair for pair in rated if not pair[0].is_available), key=lambda pair: pair[1], reverse=True)

    if not available:
        return None

    top = available[:REAL_BULLPEN_SIZE]
    size = len(top)
    relievers = tuple(
        Reliever(name=p.full_name, rating=rating, leverage=_leverage_for_rank(i, size), status=p.status_description)
        for i, (p, rating) in enumerate(top)
    )
    unavailable_relievers = tuple(
        Reliever(name=p.full_name, rating=rating, leverage=_LEVERAGE_BOTTOM, status=p.status_description)
        for p, rating in unavailable
    )
    return Bullpen(relievers=relievers, unavailable=unavailable_relievers)


def build_team_staff(
    team: TeamName, team_id: int, team_elo: float, season: int, as_of_date: str,
    cfg: SimulationConfig = SimulationConfig(),
) -> tuple[Rotation, Bullpen]:
    """
    Real-stats rotation/bullpen for `team`, falling back to the synthetic
    Elo-derived staff (default_rotation_for_team / default_bullpen_for_team)
    whenever cfg.use_real_pitcher_stats is off, the roster/stats fetch
    fails, or the real roster doesn't have an eligible arm for a role.
    Each fallback is logged and independent — a team missing real bullpen
    data can still get a real rotation, and vice versa.

    `as_of_date` ('YYYY-MM-DD') anchors the last-30-days rolling window —
    "today" for a live simulation, or the backtest snapshot date for a
    backtest run, so recent form is always measured relative to the moment
    being simulated.
    """
    if not cfg.use_real_pitcher_stats:
        return default_rotation_for_team(team, team_elo), default_bullpen_for_team(team, team_elo)

    try:
        staff = fetch_team_pitching_staff(team_id, season, as_of_date)
    except DataFetchError as e:
        logger.warning("Falling back to synthetic staff for %s (roster fetch failed: %s)", team, e)
        return default_rotation_for_team(team, team_elo), default_bullpen_for_team(team, team_elo)

    rotation = rotation_from_staff(staff, cfg)
    if rotation is None:
        logger.warning("No available real starter found for %s — using synthetic rotation.", team)
        rotation = default_rotation_for_team(team, team_elo)

    bullpen = bullpen_from_staff(staff, cfg)
    if bullpen is None:
        logger.warning("No available real reliever found for %s — using synthetic bullpen.", team)
        bullpen = default_bullpen_for_team(team, team_elo)

    return rotation, bullpen


_FETCH_WORKERS = 10  #concurrent MLB Stats API requests — enough to erase the network wait without hammering the API


def build_all_team_staffs(
    season: int, as_of_date: str, team_elo: dict[TeamName, float], cfg: SimulationConfig = SimulationConfig()
) -> tuple[dict[TeamName, Rotation], dict[TeamName, Bullpen]]:
    """build_team_staff for every team in ALL_TEAMS, called once per
    simulation run (not once per Monte Carlo iteration — see simulator.py's
    comment on why rotations/bullpens are built outside the num_sims loop).

    Each team's fetch+build is independent (its own HTTP call, own
    fallback-on-failure), so this runs all 30 concurrently on a thread
    pool instead of one-at-a-time — the wait here is network latency, not
    CPU, so threads (unaffected by the GIL for I/O waits) turn ~30
    sequential round trips into ~30 parallel ones. Output is identical to
    the sequential version; only the wall-clock time changes.
    """
    def _one(team: TeamName) -> tuple[TeamName, Rotation, Bullpen]:
        team_id = TEAM_REGISTRY[team].id
        rotation, bullpen = build_team_staff(team, team_id, team_elo[team], season, as_of_date, cfg)
        return team, rotation, bullpen

    rotations: dict[TeamName, Rotation] = {}
    bullpens: dict[TeamName, Bullpen] = {}
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        for team, rotation, bullpen in pool.map(_one, ALL_TEAMS):
            rotations[team] = rotation
            bullpens[team] = bullpen
    return rotations, bullpens
