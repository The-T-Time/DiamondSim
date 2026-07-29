# ==============================================================================
# HITTER
# models/hitter.py
#
# The rated, Elo-scale output of the hitting pipeline — Hitter is one
# player; TeamOffense is a team's full lineup pool plus a single
# playing-time-weighted team rating. Mirrors Pitcher/Rotation on the
# pitching side.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

import config
from models.player_impact import PlayerImpact
from models.team import TeamName


@dataclass(frozen=True)
class Hitter:
    """One position player. `rating` is Elo-scale — same units and
    convention as models/pitcher.Pitcher.rating and models/bullpen.
    Reliever.rating (1500 = league average), built from OPS plus small HR/
    BB%/K% modifiers (see simulation/hitter_rating.py)."""
    name: str
    rating: float = 1500.0

    #Informational only, never read by simulation math — same purpose as
    #Pitcher.fip/status.
    ops: float | None = None
    status: str = 'Active'

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Hitter name cannot be empty")
        if self.rating <= 0:
            raise ValueError(f"Hitter rating must be positive, got {self.rating!r}")

    def __str__(self) -> str:
        return self.name

    @property
    def impact(self) -> PlayerImpact:
        """This hitter's value framed as a role-separated PlayerImpact —
        populates ONLY offense_value, never a generic scalar."""
        return PlayerImpact(offense_value=self.rating - config.ELO_BASELINE)


@dataclass(frozen=True)
class TeamOffense:
    """A team's available hitting pool, plus a single playing-time-weighted
    `lineup_rating` summarizing the team's offense as one Elo-scale number
    (heavier bats who actually play every day count more than a bench bat
    with a hot small sample — see simulation/offense_calculator.py)."""
    team: TeamName
    lineup_rating: float
    hitters: tuple[Hitter, ...]

    #Real hitters who exist on the roster but are currently
    #hurt/optioned/suspended, excluded from `hitters` and `lineup_rating`.
    #Kept here rather than silently dropped, same reasoning as Rotation.
    #unavailable / Bullpen.unavailable on the pitching side.
    unavailable: tuple[Hitter, ...] = ()

    def __post_init__(self) -> None:
        if not self.team:
            raise ValueError("TeamOffense team cannot be empty")
        if not self.hitters:
            raise ValueError("TeamOffense must have at least one available hitter")
        if self.lineup_rating <= 0:
            raise ValueError(f"TeamOffense lineup_rating must be positive, got {self.lineup_rating!r}")


@dataclass(frozen=True)
class TeamLineups:
    """
    A team's two lineups — vs_rhp for facing a right-handed
    starter, vs_lhp for facing a left-handed one — each a full TeamOffense
    built from that platoon split's stats rather than one lineup assumed to
    hit equally well against both. Which one applies to a given game is
    picked from the OPPOSING starter's Pitcher.throws (see
    simulation/offense_calculator.py's select_lineup).
    """
    team: TeamName
    vs_rhp: TeamOffense
    vs_lhp: TeamOffense

    def __post_init__(self) -> None:
        if not self.team:
            raise ValueError("TeamLineups team cannot be empty")

    def for_opposing_pitcher(self, throws: str) -> TeamOffense:
        """The lineup this team should use against a starter who throws
        `throws` ('L' or 'R') — defaults to the vs-RHP lineup for any other
        value, since right-handed starters are the large majority."""
        return self.vs_lhp if throws == 'L' else self.vs_rhp
