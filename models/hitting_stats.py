# ==============================================================================
# HITTING STATS
# models/hitting_stats.py
#
# Pure data pulled from the MLB Stats API: one stat window's raw counting
# stats for one hitter (SeasonHittingLine) and one roster entry combining
# all three windows (RawHitterRecord). No rating math here — that's
# simulation/hitter_rating.py.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

from models.roster_status import is_active_status, is_injury_status

#Same MLB Stats API roster-status convention used throughout the project —
#see models/roster_status.py for ACTIVE_STATUS_CODE / injury-prefix
#details that is_available/is_injured below rely on.


@dataclass(frozen=True)
class SeasonHittingLine:
    """
    One hitter's raw counting stats for one stat window, straight off the
    MLB Stats API 'hitting' stat group — just the fields simulation/
    hitter_rating.py's OPS/OBP/SLG/HR-rate/BB%/K% math needs. Rate stats
    (obp, slg, ops, bb_rate, k_rate, hr_per_600_pa) are computed properties
    rather than stored fields, so they're always self-consistent with the
    underlying counts rather than trusting the API's own formatted strings.
    """
    plate_appearances: int = 0
    at_bats: int = 0
    hits: int = 0
    doubles: int = 0
    triples: int = 0
    home_runs: int = 0
    walks: int = 0
    hit_by_pitch: int = 0
    strikeouts: int = 0
    sac_flies: int = 0
    games: int = 0

    def __post_init__(self) -> None:
        counts = (
            self.plate_appearances, self.at_bats, self.hits, self.doubles, self.triples,
            self.home_runs, self.walks, self.hit_by_pitch, self.strikeouts, self.sac_flies, self.games,
        )
        if any(c < 0 for c in counts):
            raise ValueError("SeasonHittingLine counting stats must all be >= 0")

    @property
    def avg(self) -> float | None:
        """Batting average: H / AB."""
        if self.at_bats <= 0:
            return None
        return self.hits / self.at_bats

    @property
    def obp(self) -> float | None:
        """On-base percentage: (H + BB + HBP) / (AB + BB + HBP + SF)."""
        denom = self.at_bats + self.walks + self.hit_by_pitch + self.sac_flies
        if denom <= 0:
            return None
        return (self.hits + self.walks + self.hit_by_pitch) / denom

    @property
    def slg(self) -> float | None:
        """Slugging percentage: total bases / AB."""
        if self.at_bats <= 0:
            return None
        singles = max(0, self.hits - self.doubles - self.triples - self.home_runs)
        total_bases = singles + 2 * self.doubles + 3 * self.triples + 4 * self.home_runs
        return total_bases / self.at_bats

    @property
    def ops(self) -> float | None:
        """On-base plus slugging: OBP + SLG. None if either is undefined
        (no at-bats/plate-appearance denominator to compute from)."""
        obp, slg = self.obp, self.slg
        if obp is None or slg is None:
            return None
        return obp + slg

    @property
    def bb_rate(self) -> float | None:
        """Walk rate: BB / PA."""
        if self.plate_appearances <= 0:
            return None
        return self.walks / self.plate_appearances

    @property
    def k_rate(self) -> float | None:
        """Strikeout rate: SO / PA."""
        if self.plate_appearances <= 0:
            return None
        return self.strikeouts / self.plate_appearances

    @property
    def hr_per_600_pa(self) -> float | None:
        """Home runs normalized to a 600-PA (roughly a full season) rate,
        so power is comparable across hitters with very different playing
        time rather than penalizing a part-time slugger for a low raw count."""
        if self.plate_appearances <= 0:
            return None
        return (self.home_runs / self.plate_appearances) * 600.0


@dataclass(frozen=True)
class RawHitterRecord:
    """
    One position player pulled off a team's 40-man roster, with whatever
    stat windows are available (current season, rolling last-30-days, and
    career — same three-window shape as models/pitching_stats.py's
    RawPlayerRecord). simulation/hitter_rating.py blends all three (60%
    season / 30% last 30 days / 10% career by default); any missing window
    is simply dropped from the blend rather than treated as zero.

    vs_lhp / vs_rhp are this season's platoon splits — how this
    hitter has actually performed against left-handed vs. right-handed
    starters. Used to build a team's two lineups (simulation/
    offense_calculator.py's build_team_lineups) rather than assuming one
    lineup is equally good against everyone.
    """
    person_id: int
    full_name: str
    status_code: str
    status_description: str
    current_season: SeasonHittingLine | None
    last_30_days: SeasonHittingLine | None
    career: SeasonHittingLine | None
    vs_lhp: SeasonHittingLine | None = None
    vs_rhp: SeasonHittingLine | None = None

    #MLB Stats API position abbreviation ('1B', 'OF', 'SS',
    #etc. — never 'P', since this module is position players only). Purely
    #for display (gui/player_tab); no rating math reads it.
    position: str = '?'

    def __post_init__(self) -> None:
        if not self.full_name:
            raise ValueError("full_name cannot be empty")

    @property
    def is_available(self) -> bool:
        """Whether this hitter can take the field right now — active
        roster status only, same gate as RawPlayerRecord.is_available on
        the pitching side."""
        return is_active_status(self.status_code)

    @property
    def is_injured(self) -> bool:
        """Narrower than `not is_available` — distinguishes an actual
        injury from other inactive statuses (optioned, suspended,
        restricted) for display/logging purposes."""
        return is_injury_status(self.status_code)
