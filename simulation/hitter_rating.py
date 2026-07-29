# ==============================================================================
# HITTER RATING
# simulation/hitter_rating.py
#
# Converts real hitting stats into the same Elo-scale rating used
# everywhere else in the engine (1500 = league average) — OPS as the
# primary signal with small HR/BB%/K% modifiers, shrunk for small
# samples and blended across season/last-30-days/career windows. The
# hitting-side counterpart to simulation/player_rating.py.
# ==============================================================================

from __future__ import annotations

from models.hitting_stats import SeasonHittingLine
from models.simulation_config import SimulationConfig

#A hitter with no plate appearances in ANY window gets exactly league
#average rather than an undefined OPS.
REPLACEMENT_RATING: float = 1500.0


def _apply_shrinkage(raw_rating: float, plate_appearances: float, shrinkage_pa: float) -> float:
    """Same n/(n+k) reliability formula as simulation/player_rating.py's
    _apply_shrinkage, just keyed on plate appearances instead of innings
    pitched — see that module's docstring for the full reasoning."""
    if plate_appearances <= 0:
        return REPLACEMENT_RATING
    reliability = plate_appearances / (plate_appearances + shrinkage_pa)
    return REPLACEMENT_RATING + reliability * (raw_rating - REPLACEMENT_RATING)


def offense_rating_from_window(
    line: SeasonHittingLine | None, cfg: SimulationConfig = SimulationConfig()
) -> tuple[float, float]:
    """
    Returns (shrunk_rating, plate_appearances) for one stat window (season,
    last-30-days, or career). A None line, a line with 0 PA, or a line
    where OPS is undefined (0 AB — e.g. a hitter who's only ever been hit
    by a pitch or walked) is treated as zero plate appearances of pure
    league average — it contributes nothing when blended with other
    windows in blend_offense_rating_components.
    """
    if line is None or line.plate_appearances <= 0:
        return REPLACEMENT_RATING, 0.0

    ops = line.ops
    if ops is None:
        return REPLACEMENT_RATING, 0.0

    raw_rating = REPLACEMENT_RATING + (ops - cfg.hitter_league_avg_ops) * cfg.hitter_ops_elo_scale

    hr_per_600 = line.hr_per_600_pa
    if hr_per_600 is not None:
        raw_rating += (hr_per_600 - cfg.hitter_league_avg_hr_per_600pa) * cfg.hitter_hr_rate_elo_scale

    bb_rate = line.bb_rate
    if bb_rate is not None:
        raw_rating += (bb_rate - cfg.hitter_league_avg_bb_rate) * cfg.hitter_bb_rate_elo_scale

    k_rate = line.k_rate
    if k_rate is not None:
        #Subtracted: an above-average K% pulls the rating down, a
        #below-average (good contact) K% gives a small bonus back.
        raw_rating -= (k_rate - cfg.hitter_league_avg_k_rate) * cfg.hitter_k_rate_elo_scale

    shrunk = _apply_shrinkage(raw_rating, line.plate_appearances, cfg.hitter_shrinkage_pa)
    return shrunk, line.plate_appearances


def blend_offense_rating_components(
    season: SeasonHittingLine | None,
    last_30_days: SeasonHittingLine | None,
    career: SeasonHittingLine | None,
    cfg: SimulationConfig = SimulationConfig(),
) -> float:
    """
    Blends three independently-shrunk window ratings using cfg's hitter
    season/last-30-days/career weights (default 60/30/10) — identical
    renormalization behavior to simulation/player_rating.py's
    blend_rating_components: any window with 0 PA is dropped and the
    remaining weights renormalized proportionally, rather than treated as
    a zero or faked as league average.
    """
    windows = (
        (season, cfg.hitter_season_weight),
        (last_30_days, cfg.hitter_last30_days_weight),
        (career, cfg.hitter_career_weight),
    )

    weighted_sum = 0.0
    weight_total = 0.0
    for line, weight in windows:
        rating, pa = offense_rating_from_window(line, cfg)
        if pa <= 0 or weight <= 0:
            continue
        weighted_sum += rating * weight
        weight_total += weight

    if weight_total <= 0:
        return REPLACEMENT_RATING
    return weighted_sum / weight_total
