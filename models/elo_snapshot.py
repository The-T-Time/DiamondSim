# ==============================================================================
# ELO SNAPSHOT
# models/elo_snapshot.py
#
# Simulation-time commentary on one played game: what each team's Elo was
# entering the game, and how much it moved. Kept separate from Game because
# it isn't part of the historical record — replaying the same game through a
# different SimulationConfig produces different numbers here.
#
# SimulationResult keys these by game_pk: `result.elo_log[game.game_pk]`.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EloSnapshot:
    elo_before_home: float
    elo_before_away: float
    elo_delta: float   #change for the HOME team; negate for the away team

    def elo_before(self, *, is_home: bool) -> float:
        return self.elo_before_home if is_home else self.elo_before_away

    def delta_for(self, *, is_home: bool) -> float:
        return self.elo_delta if is_home else -self.elo_delta
