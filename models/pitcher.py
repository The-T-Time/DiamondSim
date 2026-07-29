# ==============================================================================
# PITCHER
# models/pitcher.py
#
# Pure data: a starting pitcher's name and Elo-scale rating, plus Rotation
# (an ordered, ace-first tuple of starters and which arm goes in which
# game). No simulation logic here — that's simulation/pitching.py.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

import config
from models.player_impact import PlayerImpact


@dataclass(frozen=True)
class Pitcher:
    """One starting pitcher. `rating` is Elo-scale — comparable directly to
    Team.elo and to simulation.elo's home-field-advantage constant, so a
    +50 rating gap between two starters carries roughly the same weight as
    a 50-point team Elo gap (see STARTER_ELO_WEIGHT in simulation/pitching.py
    for the exact translation)."""
    name: str
    rating: float = 1500.0

    #Set when `rating` comes from real stats (simulation/
    #player_rating.py); None for the synthetic staffs, which have
    #no underlying FIP to show. Purely informational — never read by the
    #simulation math, only by anything that wants to display "why" a
    #rating is what it is.
    fip: float | None = None
    status: str = 'Active'

    #'L' or 'R' (defaults to 'R', the more common hand, when
    #unknown — e.g. the synthetic fallback staffs have no real handedness
    #to report). Lets the OPPONENT pick its vs-LHP or vs-RHP lineup for
    #this pitcher's starts (simulation/offense_calculator.py).
    throws: str = 'R'

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Pitcher name cannot be empty")
        if self.rating <= 0:
            raise ValueError(f"Pitcher rating must be positive, got {self.rating!r}")
        if self.throws not in ('L', 'R'):
            raise ValueError(f"Pitcher throws must be 'L' or 'R', got {self.throws!r}")

    def __str__(self) -> str:
        return self.name

    @property
    def impact(self) -> PlayerImpact:
        """This pitcher's value framed as a role-separated PlayerImpact —
        populates ONLY starter_value, never a generic scalar,
        since a Pitcher is by definition a starting-rotation arm."""
        return PlayerImpact(starter_value=self.rating - config.ELO_BASELINE)


@dataclass(frozen=True)
class Rotation:
    """A team's ordered starting rotation, ace (index 0) first."""
    starters: tuple[Pitcher, ...]

    #Real starters who exist on the roster but are currently
    #hurt/optioned/suspended and so are excluded from `starters`. Kept here
    #(rather than silently dropped) so the injury's impact is visible: a
    #missing ace shows up as a real, named, highly-rated arm sitting in
    #this list rather than as an unexplained gap. Never used in game
    #simulation math — informational only.
    unavailable: tuple[Pitcher, ...] = ()

    def __post_init__(self) -> None:
        if not self.starters:
            raise ValueError("Rotation must have at least one starter")

    def starter_for_game(self, game_index: int) -> Pitcher:
        """
        Which starter takes the mound for game `game_index` (0-based) of a
        series. Cycles from the top once the staff runs out (a short-rest
        turn back to the ace, or a 3-man October rotation reused for a
        potential game 4/5) rather than raising — the sim always needs an
        answer here, and reusing your best arm on short rest is exactly
        what real playoff teams do when a series runs long.
        """
        if game_index < 0:
            raise ValueError(f"game_index must be >= 0, got {game_index!r}")
        return self.starters[game_index % len(self.starters)]

    @property
    def ace(self) -> Pitcher:
        return self.starters[0]
