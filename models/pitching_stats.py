# ==============================================================================
# PITCHING STATS
# models/pitching_stats.py
#
# Pure data pulled from the MLB Stats API: one stat-window's raw counting
# stats for one pitcher (SeasonPitchingLine) and one roster entry
# combining all three windows with roster/injury status
# (RawPlayerRecord). No rating math here — that's simulation/player_rating.py.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

from models.roster_status import is_active_status, is_injury_status


@dataclass(frozen=True)
class SeasonPitchingLine:
    """
    One pitcher's raw counting stats for one season, straight off the MLB
    Stats API 'pitching' stat group — just the fields simulation/
    player_rating.py's FIP calculation needs, plus a couple for display/
    role-classification (games, games_started) and earned_runs for the
    display-only `era` property.
    """
    innings_pitched: float
    strikeouts: int = 0
    walks: int = 0
    hit_batters: int = 0
    home_runs: int = 0
    earned_runs: int = 0
    games: int = 0
    games_started: int = 0
    wins: int = 0
    losses: int = 0

    def __post_init__(self) -> None:
        if self.innings_pitched < 0:
            raise ValueError(f"innings_pitched must be >= 0, got {self.innings_pitched!r}")
        if self.games < 0 or self.games_started < 0:
            raise ValueError("games/games_started must be >= 0")
        if self.wins < 0 or self.losses < 0:
            raise ValueError("wins/losses must be >= 0")

    @property
    def era(self) -> float | None:
        """Earned run average — display-only. Rating math uses FIP instead
        (simulation/player_rating.py), since FIP strips out the defense
        playing behind a pitcher and batted-ball luck; ERA is kept here
        only because it's the number people actually recognize."""
        if self.innings_pitched <= 0:
            return None
        return (self.earned_runs * 9.0) / self.innings_pitched

    @property
    def is_mostly_starter(self) -> bool:
        """Role heuristic: did most of this pitcher's appearances come as a
        starter? Used to sort real arms into rotation-eligible vs.
        bullpen-eligible pools (simulation/pitching.py)."""
        if self.games <= 0:
            return False
        return (self.games_started / self.games) > 0.5


#Roster status codes MLB's Stats API uses for a player who is NOT on the
#active roster — see models/roster_status.py for the shared convention
#(ACTIVE_STATUS_CODE / injury prefixes) that is_available/is_injured below
#rely on.


@dataclass(frozen=True)
class RawPlayerRecord:
    """
    One pitcher pulled off a team's 40-man roster, with whatever stat
    windows are available:

    - current_season: this year's stats to date.
    - last_30_days: a rolling 30-day window ending at the simulation's "as
      of" date — captures current form/health that a full-season line can
      miss (e.g. a pitcher who's been lights-out since returning from a
      mechanical tweak in June).
    - career: full MLB career totals — the largest, most stable sample,
      used as a baseline anchor.

    simulation/player_rating.py blends all three (60% season / 30% last 30
    days / 10% career by default) rather than picking one, and any window
    that's empty (e.g. a rookie has no meaningful career totals beyond this
    season) is simply dropped from the blend rather than treated as zero.
    """
    person_id: int
    full_name: str
    status_code: str
    status_description: str
    current_season: SeasonPitchingLine | None
    last_30_days: SeasonPitchingLine | None
    career: SeasonPitchingLine | None

    #'L' or 'R', or None if the API didn't report it (treated
    #as 'R' downstream, the more common hand, rather than left unhandled).
    #Lets the OPPOSING team pick its vs-LHP or vs-RHP lineup for this
    #pitcher's starts — see simulation/offense_calculator.py.
    throws: str | None = None

    def __post_init__(self) -> None:
        if not self.full_name:
            raise ValueError("full_name cannot be empty")

    @property
    def is_available(self) -> bool:
        """Whether this arm can take the mound right now — active roster
        status only. This is the sole gate the sim uses to decide whether a
        pitcher is selectable; there's no separate injury rating penalty
        layered on top (see simulation/pitching.py's module docstring)."""
        return is_active_status(self.status_code)

    @property
    def is_injured(self) -> bool:
        """Narrower than `not is_available` — distinguishes an actual
        injury from other inactive statuses (optioned, suspended,
        restricted) for display/logging purposes."""
        return is_injury_status(self.status_code)

    @property
    def is_mostly_starter(self) -> bool:
        """Which window's stats to trust for role classification: current
        season if he's actually pitched in it this year, else career (so a
        pitcher hurt all season, or freshly converted from a career
        long-relief role, still gets classified from real games-started
        history rather than defaulting to reliever)."""
        line = self.current_season if (self.current_season and self.current_season.games) else self.career
        return line.is_mostly_starter if line is not None else False
