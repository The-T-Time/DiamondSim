# ==============================================================================
# PLAYER IMPACT
# models/player_impact.py
#
# Role-separated player value — deliberately not a single scalar, since a
# starter's, reliever's, hitter's, and fielder's value aren't the same
# axis. Each field is Elo-scale points above/below league average (1500)
# for that role. defense_value stays reserved (None) since this project
# has no fielding data source yet.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlayerImpact:
    """Role-separated impact for one player. A player only ever has values
    populated for the role(s) they actually play this instant — a starting
    pitcher gets starter_value, a reliever gets bullpen_value, never both,
    since the role classification (RawPlayerRecord.is_mostly_starter)
    already sorts each arm into exactly one of the two pitching roles."""
    starter_value: float | None = None
    bullpen_value: float | None = None
    offense_value: float | None = None
    defense_value: float | None = None

    @property
    def populated_roles(self) -> tuple[str, ...]:
        """Which role(s) this player actually has a computed value for —
        useful for display ("this player's impact: +65 as a starter")
        without the caller needing to know which fields might be None."""
        fields = (
            ('starter', self.starter_value),
            ('bullpen', self.bullpen_value),
            ('offense', self.offense_value),
            ('defense', self.defense_value),
        )
        return tuple(name for name, value in fields if value is not None)
