# ==============================================================================
# BULLPEN FATIGUE
# simulation/fatigue.py
#
# Tracks how worn down each team's bullpen is across a simulated
# postseason run and converts that into a win-probability penalty for the
# next game. A fresh tracker is threaded through one Monte Carlo
# iteration's whole bracket so fatigue carries between rounds but never
# leaks into the next iteration.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass, field

from models.team import TeamName

#Fatigue points gained from one game, depending on how taxing it was on the
#bullpen (see simulation/pitching.py's is_taxing_game). A tight/extra-innings
#game burns high-leverage relievers hard; a comfortable game mostly uses
#long men and barely dents the pen.
FATIGUE_PER_TAXING_GAME: float = 15.0
FATIGUE_PER_NORMAL_GAME: float = 6.0

#Fatigue points shed per day of rest before a team's next game.
FATIGUE_RECOVERY_PER_DAY: float = 10.0

#Fatigue is clamped to [0, MAX_FATIGUE]; MAX_FATIGUE maps to the largest
#possible Elo penalty, MAX_FATIGUE_ELO_PENALTY (scales linearly below that).
MAX_FATIGUE: float = 100.0
MAX_FATIGUE_ELO_PENALTY: float = 20.0


@dataclass
class BullpenFatigueTracker:
    """Mutable per-team bullpen fatigue state for a single simulated
    postseason run. Starts every team at 0 (fully rested) — teams enter
    October having had a full 4-man rotation and normal bullpen usage
    through the end of the regular season, so there's no residual fatigue
    to carry in."""
    _fatigue: dict[TeamName, float] = field(default_factory=dict)

    def level(self, team: TeamName) -> float:
        """Current fatigue for `team`, 0 (fresh) to MAX_FATIGUE (gassed)."""
        return self._fatigue.get(team, 0.0)

    def record_game(self, team: TeamName, was_taxing: bool) -> None:
        """Add fatigue for `team` after it plays one game."""
        gain = FATIGUE_PER_TAXING_GAME if was_taxing else FATIGUE_PER_NORMAL_GAME
        self._fatigue[team] = min(MAX_FATIGUE, self.level(team) + gain)

    def rest(self, team: TeamName, days: float) -> None:
        """Shed fatigue for `team` after `days` days off (fractional allowed
        — used for the smaller gap built into back-to-back series games vs.
        the bigger gap between playoff rounds)."""
        if days <= 0:
            return
        self._fatigue[team] = max(0.0, self.level(team) - FATIGUE_RECOVERY_PER_DAY * days)

    def elo_penalty(self, team: TeamName) -> float:
        """Elo points to subtract from `team` for its next game, given its
        current fatigue level. 0 for a fully rested bullpen, up to
        MAX_FATIGUE_ELO_PENALTY for a completely gassed one."""
        return (self.level(team) / MAX_FATIGUE) * MAX_FATIGUE_ELO_PENALTY
