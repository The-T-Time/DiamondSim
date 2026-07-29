# ==============================================================================
# ROSTER STRENGTH
# simulation/roster_strength.py
#
# Turns a Roster into an availability snapshot — how much of the roster
# is healthy and able to play right now. Not a talent rating (that's
# simulation/player_rating.py); the two are meant to be read together.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

from models.roster import Roster
from models.team import TeamName


@dataclass(frozen=True)
class RosterStrength:
    """Availability snapshot for one team's roster at a point in time."""
    team: TeamName
    total_players: int
    available_players: int
    pitchers_total: int
    pitchers_available: int
    position_players_total: int
    position_players_available: int

    def __post_init__(self) -> None:
        if self.available_players > self.total_players:
            raise ValueError("available_players cannot exceed total_players")
        if self.pitchers_available > self.pitchers_total:
            raise ValueError("pitchers_available cannot exceed pitchers_total")
        if self.position_players_available > self.position_players_total:
            raise ValueError("position_players_available cannot exceed position_players_total")

    @property
    def unavailable_players(self) -> int:
        return self.total_players - self.available_players

    @property
    def availability_pct(self) -> float:
        """Fraction (0-1) of the whole roster currently available. A roster
        with zero players (no data fetched) reads as 0% available rather
        than raising or faking full health."""
        return self.available_players / self.total_players if self.total_players else 0.0

    @property
    def pitching_availability_pct(self) -> float:
        return self.pitchers_available / self.pitchers_total if self.pitchers_total else 0.0

    @property
    def position_player_availability_pct(self) -> float:
        return (
            self.position_players_available / self.position_players_total
            if self.position_players_total else 0.0
        )


def compute_roster_strength(roster: Roster) -> RosterStrength:
    """Builds a RosterStrength availability snapshot from `roster`."""
    pitchers = roster.pitchers
    position_players = roster.position_players
    return RosterStrength(
        team=roster.team,
        total_players=len(roster.players),
        available_players=len(roster.available_players),
        pitchers_total=len(pitchers),
        pitchers_available=sum(1 for p in pitchers if p.is_available),
        position_players_total=len(position_players),
        position_players_available=sum(1 for p in position_players if p.is_available),
    )
