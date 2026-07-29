# ==============================================================================
# OFFENSE CALCULATOR
# simulation/offense_calculator.py
#
# Builds a team's TeamOffense (real or synthetic fallback) and its two
# platoon-split lineups (vs LHP / vs RHP) for the postseason bracket sim.
# Mirrors simulation/pitching.py's structure on the hitting side.
# ==============================================================================

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Callable

from data.exceptions import DataFetchError
from data.hitting_stats import fetch_team_hitters
from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.hitter import Hitter, TeamLineups, TeamOffense
from models.hitting_stats import RawHitterRecord, SeasonHittingLine
from models.simulation_config import SimulationConfig
from models.team import TeamName
from simulation.deterministic_seed import team_seed
from simulation.hitter_rating import REPLACEMENT_RATING, blend_offense_rating_components, offense_rating_from_window
from utils.logger import get_logger

logger = get_logger(__name__)


#A typical active-roster-plus-bench hitting pool: 8 lineup regulars, a DH,
#and 4 bench bats, best to worst. Spread (~45 to -58, ~103 points total)
#calibrated to a similar magnitude as simulation/pitching.py's
#_ROTATION_OFFSETS spread, for a comparably "shaped" synthetic fallback.
_LINEUP_OFFSETS: tuple[float, ...] = (
    45.0, 32.0, 22.0, 13.0, 5.0, -2.0, -10.0, -18.0, -26.0, -34.0, -42.0, -50.0, -58.0,
)
_JITTER: float = 8.0


def default_team_offense(team: TeamName, team_elo: float) -> TeamOffense:
    """
    Synthesize a 13-hitter lineup pool for `team`, scaled off `team_elo` —
    the hitting-side counterpart to simulation/pitching.py's
    default_rotation_for_team, used whenever real hitting data can't be
    fetched/parsed. Deterministic per team name; varies with team_elo so a
    contender's lineup actually looks like a contender's.
    """
    rng = team_seed(team, salt=0x42415454)  #'BATT'
    hitters = tuple(
        Hitter(name=f"{team} H{i + 1}", rating=max(1.0, team_elo + offset + rng.uniform(-_JITTER, _JITTER)))
        for i, offset in enumerate(_LINEUP_OFFSETS)
    )
    lineup_rating = sum(h.rating for h in hitters) / len(hitters)
    return TeamOffense(team=team, lineup_rating=lineup_rating, hitters=hitters)


#------------------------------------------------------------------------------
#Real offense generation
#------------------------------------------------------------------------------

def _playing_time_weight(hitter: RawHitterRecord) -> float:
    """
    How much a hitter counts toward the team-level lineup_rating average —
    plate appearances, so an everyday regular pulls the team rating much
    harder than a September call-up with a hot 10-PA cameo. Falls back to
    career PA if there's no current-season sample yet (e.g. a rookie who
    just debuted), and a small floor of 1.0 so a hitter with genuinely zero
    recorded PA anywhere still counts a little rather than vanishing from
    the average entirely.
    """
    if hitter.current_season and hitter.current_season.plate_appearances > 0:
        return float(hitter.current_season.plate_appearances)
    if hitter.career and hitter.career.plate_appearances > 0:
        return float(hitter.career.plate_appearances)
    return 1.0


def offense_from_hitters(
    team: TeamName, hitters: list[RawHitterRecord], cfg: SimulationConfig = SimulationConfig()
) -> TeamOffense | None:
    """
    Builds a real TeamOffense from `hitters` (one team's parsed roster,
    position players only): every available hitter gets a Hitter with its
    blended rating, and the team's `lineup_rating` is the playing-time-
    weighted average across them (see _playing_time_weight) — an everyday
    regular's real form counts far more than a bench bat's small sample.
    Returns None if there's no available hitter at all — the caller
    (build_team_offense) falls back to the synthetic generator in that case.

    Unavailable hitters are surfaced on TeamOffense.unavailable rather than
    silently dropped, at whatever rating they'd have earned had they been
    healthy — same reasoning as Rotation.unavailable on the pitching side.
    """
    rated = [
        (h, blend_offense_rating_components(h.current_season, h.last_30_days, h.career, cfg))
        for h in hitters
    ]
    available = sorted((pair for pair in rated if pair[0].is_available), key=lambda pair: pair[1], reverse=True)
    unavailable = sorted((pair for pair in rated if not pair[0].is_available), key=lambda pair: pair[1], reverse=True)

    if not available:
        return None

    hitter_objs = tuple(
        Hitter(name=h.full_name, rating=rating, ops=(h.current_season.ops if h.current_season else None),
               status=h.status_description)
        for h, rating in available
    )
    unavailable_objs = tuple(
        Hitter(name=h.full_name, rating=rating, ops=(h.current_season.ops if h.current_season else None),
               status=h.status_description)
        for h, rating in unavailable
    )

    total_weight = sum(_playing_time_weight(h) for h, _ in available)
    lineup_rating = (
        sum(rating * _playing_time_weight(h) for h, rating in available) / total_weight
        if total_weight > 0 else REPLACEMENT_RATING
    )

    return TeamOffense(team=team, lineup_rating=lineup_rating, hitters=hitter_objs, unavailable=unavailable_objs)


def build_team_offense(
    team: TeamName, team_id: int, team_elo: float, season: int, as_of_date: str,
    cfg: SimulationConfig = SimulationConfig(),
) -> TeamOffense:
    """
    Real-stats TeamOffense for `team`, falling back to the synthetic
    Elo-derived lineup (default_team_offense) whenever
    cfg.use_real_hitter_stats is off, the roster/stats fetch fails, or the
    real roster doesn't have an available hitter.
    """
    if not cfg.use_real_hitter_stats:
        return default_team_offense(team, team_elo)

    try:
        hitters = fetch_team_hitters(team_id, season, as_of_date)
    except DataFetchError as e:
        logger.warning("Falling back to synthetic offense for %s (roster fetch failed: %s)", team, e)
        return default_team_offense(team, team_elo)

    offense = offense_from_hitters(team, hitters, cfg)
    if offense is None:
        logger.warning("No available real hitter found for %s — using synthetic offense.", team)
        offense = default_team_offense(team, team_elo)

    return offense


_FETCH_WORKERS = 10  #concurrent MLB Stats API requests — enough to erase the network wait without hammering the API


def build_all_team_offenses(
    season: int, as_of_date: str, team_elo: dict[TeamName, float], cfg: SimulationConfig = SimulationConfig()
) -> dict[TeamName, TeamOffense]:
    """build_team_offense for every team in ALL_TEAMS. This is the single-
    lineup overall rating (used as a fallback by build_team_lineups below
    when platoon-split data isn't available) — game_win_prob itself reads
    the split-aware TeamLineups from build_all_team_lineups instead.

    Each team's fetch+build is independent, so this runs all 30 concurrently
    on a thread pool rather than one at a time — see build_all_team_staffs
    in simulation/pitching.py for the same pattern and full reasoning.
    """
    def _one(team: TeamName) -> tuple[TeamName, TeamOffense]:
        team_id = TEAM_REGISTRY[team].id
        return team, build_team_offense(team, team_id, team_elo[team], season, as_of_date, cfg)

    offenses: dict[TeamName, TeamOffense] = {}
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        for team, offense in pool.map(_one, ALL_TEAMS):
            offenses[team] = offense
    return offenses


#------------------------------------------------------------------------------
#Two lineups: vs LHP / vs RHP
#------------------------------------------------------------------------------

def _split_offense_from_hitters(
    team: TeamName,
    hitters: list[RawHitterRecord],
    split_of: Callable[[RawHitterRecord], SeasonHittingLine | None],
    cfg: SimulationConfig = SimulationConfig(),
) -> TeamOffense | None:
    """
    Builds a TeamOffense the same way offense_from_hitters does, except
    each hitter's rating comes from ONE platoon-split stat line (picked out
    by `split_of` — h.vs_lhp or h.vs_rhp) instead of the season/last-30-
    days/career blend. Playing-time weighting for the team-level
    lineup_rating still uses each hitter's OVERALL playing time
    (_playing_time_weight), not the split's own (smaller) sample — how much
    a player plays day to day shouldn't change depending on which lineup
    we're building, only how good he is in that matchup should.

    Returns None if no available hitter has any stats at all for this
    split (e.g. split data wasn't fetched) — the caller falls back to the
    single overall TeamOffense in that case.
    """
    rated = [(h, offense_rating_from_window(split_of(h), cfg)[0]) for h in hitters]
    has_any_split_data = any(split_of(h) is not None for h in hitters)
    if not has_any_split_data:
        return None

    available = sorted((pair for pair in rated if pair[0].is_available), key=lambda pair: pair[1], reverse=True)
    unavailable = sorted((pair for pair in rated if not pair[0].is_available), key=lambda pair: pair[1], reverse=True)
    if not available:
        return None

    def _to_hitter(h: RawHitterRecord, rating: float) -> Hitter:
        line = split_of(h)
        return Hitter(name=h.full_name, rating=rating, ops=(line.ops if line else None), status=h.status_description)

    hitter_objs = tuple(_to_hitter(h, r) for h, r in available)
    unavailable_objs = tuple(_to_hitter(h, r) for h, r in unavailable)

    total_weight = sum(_playing_time_weight(h) for h, _ in available)
    lineup_rating = (
        sum(rating * _playing_time_weight(h) for h, rating in available) / total_weight
        if total_weight > 0 else REPLACEMENT_RATING
    )
    return TeamOffense(team=team, lineup_rating=lineup_rating, hitters=hitter_objs, unavailable=unavailable_objs)


def build_team_lineups(
    team: TeamName, hitters: list[RawHitterRecord], cfg: SimulationConfig = SimulationConfig()
) -> TeamLineups | None:
    """
    Builds `team`'s two lineups (vs RHP and vs LHP) from `hitters`' platoon
    splits. Returns None if there's no split data at all for this roster,
    or no available hitter under either split — the caller (build_team_lineups_for_team)
    falls back to the single overall TeamOffense (offense_from_hitters) for
    both sides in that case, then to the synthetic lineup if that's
    unavailable too.
    """
    vs_rhp = _split_offense_from_hitters(team, hitters, lambda h: h.vs_rhp, cfg)
    vs_lhp = _split_offense_from_hitters(team, hitters, lambda h: h.vs_lhp, cfg)
    if vs_rhp is None or vs_lhp is None:
        return None
    return TeamLineups(team=team, vs_rhp=vs_rhp, vs_lhp=vs_lhp)


def build_team_lineups_for_team(
    team: TeamName, team_id: int, team_elo: float, season: int, as_of_date: str,
    cfg: SimulationConfig = SimulationConfig(),
) -> TeamLineups:
    """
    Real-stats TeamLineups for `team`, with a two-level fallback:
    1. No split data available at all -> both lineups become the single
       overall TeamOffense (offense_from_hitters) — better to use one
       real, unsplit rating than none.
    2. No real hitting data available at all (fetch failed, disabled, or
       no eligible hitter) -> both lineups become the synthetic
       Elo-derived lineup (default_team_offense), same as
       build_team_offense's fallback.
    """
    if not cfg.use_real_hitter_stats:
        synthetic = default_team_offense(team, team_elo)
        return TeamLineups(team=team, vs_rhp=synthetic, vs_lhp=synthetic)

    try:
        hitters = fetch_team_hitters(team_id, season, as_of_date)
    except DataFetchError as e:
        logger.warning("Falling back to synthetic lineups for %s (roster fetch failed: %s)", team, e)
        synthetic = default_team_offense(team, team_elo)
        return TeamLineups(team=team, vs_rhp=synthetic, vs_lhp=synthetic)

    lineups = build_team_lineups(team, hitters, cfg)
    if lineups is not None:
        return lineups

    logger.warning("No platoon-split data for %s — using one overall lineup for both LHP/RHP.", team)
    overall = offense_from_hitters(team, hitters, cfg)
    if overall is None:
        logger.warning("No available real hitter found for %s — using synthetic lineups.", team)
        overall = default_team_offense(team, team_elo)
    return TeamLineups(team=team, vs_rhp=overall, vs_lhp=overall)


def build_all_team_lineups(
    season: int, as_of_date: str, team_elo: dict[TeamName, float], cfg: SimulationConfig = SimulationConfig()
) -> dict[TeamName, TeamLineups]:
    """build_team_lineups_for_team for every team in ALL_TEAMS — the
    per-run entry point series_simulator.py uses to get each team's two
    lineups.

    Each team's fetch+build is independent, so this runs all 30 concurrently
    on a thread pool rather than one at a time — see build_all_team_staffs
    in simulation/pitching.py for the same pattern and full reasoning.
    """
    def _one(team: TeamName) -> tuple[TeamName, TeamLineups]:
        team_id = TEAM_REGISTRY[team].id
        return team, build_team_lineups_for_team(team, team_id, team_elo[team], season, as_of_date, cfg)

    lineups: dict[TeamName, TeamLineups] = {}
    with ThreadPoolExecutor(max_workers=_FETCH_WORKERS) as pool:
        for team, team_lineups in pool.map(_one, ALL_TEAMS):
            lineups[team] = team_lineups
    return lineups
