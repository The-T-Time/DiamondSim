# ==============================================================================
# BULLPEN
# models/bullpen.py
#
# Pure data: a team's relief corps, ordered by leverage (closer/setup
# first, mop-up last). Static roster shape only — current fatigue is
# run-specific mutable state that lives in simulation/fatigue.py instead.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

import config
from models.player_impact import PlayerImpact


@dataclass(frozen=True)
class Reliever:
    """One reliever. `rating` is Elo-scale, same units as Pitcher.rating.
    `leverage` (0-1) is how often this arm pitches the highest-stakes innings
    — 1.0 for a true closer down to ~0.3 for a long man/mop-up arm — and is
    used to weight the bullpen's overall strength toward its best relievers
    rather than averaging the whole staff evenly."""
    name: str
    rating: float = 1500.0
    leverage: float = 1.0

    #Same purpose as Pitcher.fip/status: informational only,
    #never read by the simulation math.
    fip: float | None = None
    status: str = 'Active'

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Reliever name cannot be empty")
        if self.rating <= 0:
            raise ValueError(f"Reliever rating must be positive, got {self.rating!r}")
        if not (0.0 < self.leverage <= 1.0):
            raise ValueError(f"Reliever leverage must be in (0, 1], got {self.leverage!r}")

    def __str__(self) -> str:
        return self.name

    @property
    def impact(self) -> PlayerImpact:
        """This reliever's value framed as a role-separated PlayerImpact —
        populates ONLY bullpen_value, never a generic scalar,
        since a Reliever is by definition a relief-corps arm."""
        return PlayerImpact(bullpen_value=self.rating - config.ELO_BASELINE)


@dataclass(frozen=True)
class Bullpen:
    """A team's relief corps, ordered highest-leverage first."""
    relievers: tuple[Reliever, ...]

    #Real relievers on the roster who are currently hurt/
    #optioned/suspended and excluded from `relievers`. See Rotation.
    #unavailable for the full reasoning; same deal here.
    unavailable: tuple[Reliever, ...] = ()

    def __post_init__(self) -> None:
        if not self.relievers:
            raise ValueError("Bullpen must have at least one reliever")

    @property
    def strength(self) -> float:
        """Leverage-weighted average rating — this bullpen's rating when
        fully rested. Weighting toward the high-leverage arms reflects that
        a great closer/setup pair matters more to a bullpen's identity than
        its long relievers do."""
        total_weight = sum(r.leverage for r in self.relievers)
        return sum(r.rating * r.leverage for r in self.relievers) / total_weight
