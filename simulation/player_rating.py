# ==============================================================================
# PLAYER RATING
# simulation/player_rating.py
#
# Converts real pitching stats (FIP-based) into the same Elo-scale rating
# used everywhere else in the engine, shrunk for small samples and
# blended across season/last-30-days/career windows.
# ==============================================================================

from __future__ import annotations

from models.pitching_stats import SeasonPitchingLine
from models.simulation_config import SimulationConfig

#A pitcher with no innings in ANY window gets exactly league average
#rather than an undefined FIP.
REPLACEMENT_RATING: float = 1500.0


def fip(line: SeasonPitchingLine, constant: float) -> float | None:
    """FIP for one stat window, or None if the pitcher hasn't thrown a
    pitch in it (0 IP — e.g. a rookie has no career-window innings before
    this season, or a hurt pitcher has 0 IP in the last-30-days window)."""
    if line.innings_pitched <= 0:
        return None
    return (
        (13 * line.home_runs + 3 * (line.walks + line.hit_batters) - 2 * line.strikeouts)
        / line.innings_pitched
    ) + constant


def _apply_shrinkage(raw_rating: float, innings_pitched: float, shrinkage_innings: float) -> float:
    """
    Regresses `raw_rating` toward REPLACEMENT_RATING using the standard
    sabermetric small-sample reliability formula:

        reliability = IP / (IP + k)

    rather than a hard linear cutoff — reliability climbs smoothly and
    never claims false certainty even at large IP (it approaches, but never
    reaches, 1.0), which is the more honest shape for "how much do I trust
    this sample." `shrinkage_innings` is k: the innings at which a pitcher
    is exactly 50% trusted (IP == k -> reliability == 0.5). This is what
    keeps a 20-inning small sample from being read as a true-talent
    superstar or bust — the same problem as a 20-AB .500 hitter, just
    measured in innings instead of at-bats.
    """
    if innings_pitched <= 0:
        return REPLACEMENT_RATING
    reliability = innings_pitched / (innings_pitched + shrinkage_innings)
    return REPLACEMENT_RATING + reliability * (raw_rating - REPLACEMENT_RATING)


def rating_from_window(
    line: SeasonPitchingLine | None, cfg: SimulationConfig = SimulationConfig()
) -> tuple[float, float]:
    """
    Returns (shrunk_rating, innings_pitched) for one stat window (season,
    last-30-days, or career). A None line, or a line with 0 IP, is treated
    as zero innings of pure league average — it contributes nothing when
    blended with other windows in blend_rating_components rather than
    raising or dragging the blend toward average by brute force.
    """
    if line is None or line.innings_pitched <= 0:
        return REPLACEMENT_RATING, 0.0
    fip_value = fip(line, cfg.pitcher_fip_constant)
    raw_rating = REPLACEMENT_RATING + (cfg.pitcher_league_avg_fip - fip_value) * cfg.pitcher_fip_elo_scale
    shrunk = _apply_shrinkage(raw_rating, line.innings_pitched, cfg.pitcher_shrinkage_innings)
    return shrunk, line.innings_pitched


def blend_rating_components(
    season: SeasonPitchingLine | None,
    last_30_days: SeasonPitchingLine | None,
    career: SeasonPitchingLine | None,
    cfg: SimulationConfig = SimulationConfig(),
) -> float:
    """
    Blends three independently-shrunk window ratings using cfg's
    season/last-30-days/career weights (default 60/30/10). A window with 0
    innings pitched (no stats in that window at all) is dropped from the
    blend entirely and the remaining weights renormalized proportionally —
    e.g. a rookie with no career stats blends purely off season + last 30
    days, at the same 60:30 ratio the three-way weights imply, rather than
    silently losing 10% of the blend to a fabricated league-average career
    number.
    """
    windows = (
        (season, cfg.pitcher_season_weight),
        (last_30_days, cfg.pitcher_last30_days_weight),
        (career, cfg.pitcher_career_weight),
    )

    weighted_sum = 0.0
    weight_total = 0.0
    for line, weight in windows:
        rating, ip = rating_from_window(line, cfg)
        if ip <= 0 or weight <= 0:
            continue
        weighted_sum += rating * weight
        weight_total += weight

    if weight_total <= 0:
        return REPLACEMENT_RATING
    return weighted_sum / weight_total
