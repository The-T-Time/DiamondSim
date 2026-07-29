# ==============================================================================
# PLAYER
# models/player.py
#
# A general, position-agnostic player on an MLB roster: identity,
# position, and roster/injury status. Separate from RawPlayerRecord
# (pitching-specific, carries stat windows for rating math) — this is the
# broader "who's on this roster and can they play right now" concept.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

from models.roster_status import is_active_status, is_injury_status


@dataclass(frozen=True)
class Player:
    """One player on a team's roster, any position — a pitcher, a catcher,
    an outfielder, whatever. Pure identity/status; no stats or rating here
    (see models/pitching_stats.py + simulation/player_rating.py for the
    pitching-specific rating pipeline, which this model doesn't replace)."""
    person_id: int
    full_name: str
    position: str                        #MLB Stats API position abbreviation, e.g. 'P', 'C', '1B', 'OF', 'SS'
    status_code: str
    status_description: str
    jersey_number: str | None = None

    def __post_init__(self) -> None:
        if not self.full_name:
            raise ValueError("Player full_name cannot be empty")
        if not self.position:
            raise ValueError("Player position cannot be empty")

    def __str__(self) -> str:
        return self.full_name

    @property
    def is_pitcher(self) -> bool:
        return self.position == 'P'

    @property
    def is_available(self) -> bool:
        """Whether this player can take the field right now — active
        roster status only, same convention as RawPlayerRecord.is_available
        in models/pitching_stats.py."""
        return is_active_status(self.status_code)

    @property
    def is_injured(self) -> bool:
        """Narrower than `not is_available` — distinguishes an actual
        injury from other inactive statuses (optioned, suspended,
        restricted) for display/logging purposes."""
        return is_injury_status(self.status_code)
