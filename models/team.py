# ==============================================================================
# TEAM
# models/team.py
#
# Immutable record for one MLB team's static metadata (id, name, division,
# league). Simulation-derived state (Elo, W/L, playoff odds, ...) is NOT
# stored here — that stays in per-run structures (SimulationResult, the
# records/elo dicts inside simulator.py) because it changes every run.
# Kept hashable (frozen) so it's safe to use as a dict key or set member.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

import config

#Team name is used as the lookup key everywhere in the simulation engine
#(records, Elo, standings, etc). Aliased for readable signatures.
TeamName = str

_VALID_LEAGUES = ('AL', 'NL')


@dataclass
class Team:
    id: int
    name: TeamName
    division: str              #e.g. 'AL East'
    league: str                 #'AL' or 'NL'
    elo: float = config.ELO_BASELINE

    def __post_init__(self) -> None:
        if self.league not in _VALID_LEAGUES:
            raise ValueError(f"Team league must be one of {_VALID_LEAGUES}, got {self.league!r}")
        if self.elo <= 0:
            raise ValueError(f"Team elo must be positive, got {self.elo!r}")

    def __str__(self) -> str:
        return self.name


class TeamRecord(TypedDict):
    """Shape of the per-team W/L record used during tiebreaker resolution."""
    W: int
    L: int
    div_W: int
    div_L: int
    league_W: int
    league_L: int
    #Chronological intraleague game outcomes in schedule order: 1 = win, 0 = loss.
    #Used by the official tiebreaker's "last half of intraleague games" and the
    #plus-one walkback steps, which need per-game order, not just totals.
    league_results: list[int]
