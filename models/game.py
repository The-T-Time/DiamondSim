# ==============================================================================
# GAME
# models/game.py
#
# A single regular-season game — played or not. Pure data: who played,
# when, and the score if played. `loser`/`run_diff` are computed
# properties so they can't drift out of sync with the scores. Elo
# commentary lives separately (see models/elo_snapshot.py) — it's
# simulation output, not part of the game's own record.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from models.team import TeamName


@dataclass
class Game:
    game_pk: Optional[int]
    date: str
    home: TeamName
    away: TeamName
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    winner: Optional[TeamName] = None

    def __post_init__(self) -> None:
        if self.home == self.away:
            raise ValueError(f"A team can't play itself: {self.home!r}")
        if self.winner is not None and self.winner not in (self.home, self.away):
            raise ValueError(f"winner {self.winner!r} did not play in this game")

    @property
    def is_played(self) -> bool:
        return self.winner is not None

    @property
    def loser(self) -> Optional[TeamName]:
        if self.winner is None:
            return None
        return self.away if self.winner == self.home else self.home

    @property
    def run_diff(self) -> Optional[int]:
        if self.home_score is None or self.away_score is None:
            return None
        return abs(self.home_score - self.away_score)

    def opponent_of(self, team: TeamName) -> TeamName:
        """The other team in this game, given one side."""
        return self.away if team == self.home else self.home

    def is_home_team(self, team: TeamName) -> bool:
        return self.home == team
