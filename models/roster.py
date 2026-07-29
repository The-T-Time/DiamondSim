# ==============================================================================
# ROSTER
# models/roster.py
#
# A team's full roster: every Player on it right now, plus convenience
# views for availability and role. Pure data — no fetching (data/roster.py)
# or strength/health math (simulation/roster_strength.py) here.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

from models.player import Player
from models.team import TeamName


@dataclass(frozen=True)
class Roster:
    """One team's full roster at a point in time. `players` may be empty —
    unlike Rotation/Bullpen (which always guarantee at least one eligible
    arm via their synthetic fallback), an empty Roster is a valid, honest
    state meaning "no roster data available for this team," and callers
    should check for it rather than assume it can't happen."""
    team: TeamName
    players: tuple[Player, ...]

    def __post_init__(self) -> None:
        if not self.team:
            raise ValueError("Roster team cannot be empty")

    @property
    def available_players(self) -> tuple[Player, ...]:
        return tuple(p for p in self.players if p.is_available)

    @property
    def unavailable_players(self) -> tuple[Player, ...]:
        return tuple(p for p in self.players if not p.is_available)

    @property
    def pitchers(self) -> tuple[Player, ...]:
        return tuple(p for p in self.players if p.is_pitcher)

    @property
    def position_players(self) -> tuple[Player, ...]:
        return tuple(p for p in self.players if not p.is_pitcher)

    def find(self, person_id: int) -> Player | None:
        """The player with this MLB person id, or None if they're not on
        this roster."""
        for player in self.players:
            if player.person_id == person_id:
                return player
        return None
