# ==============================================================================
# tests/test_player_impact.py
#
# Role-Separated Player Impact.
# Covers models/player_impact.py and its wiring into Pitcher.impact /
# Reliever.impact: a starter never has bullpen_value populated, a reliever
# never has starter_value populated, and offense/defense stay None since
# this project has no batting/fielding data source (see the module
# docstring on models/player_impact.py).
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

import config
from models.bullpen import Reliever
from models.pitcher import Pitcher
from models.player_impact import PlayerImpact


class TestPlayerImpact(unittest.TestCase):
    def test_populated_roles_reflects_only_set_fields(self) -> None:
        impact = PlayerImpact(starter_value=42.0)
        self.assertEqual(impact.populated_roles, ('starter',))

    def test_populated_roles_empty_when_nothing_set(self) -> None:
        self.assertEqual(PlayerImpact().populated_roles, ())

    def test_populated_roles_can_include_multiple(self) -> None:
        impact = PlayerImpact(starter_value=10.0, defense_value=5.0)
        self.assertEqual(impact.populated_roles, ('starter', 'defense'))


class TestPitcherImpact(unittest.TestCase):
    def test_starter_above_average_has_positive_starter_value(self) -> None:
        ace = Pitcher(name='Ace', rating=config.ELO_BASELINE + 80.0)
        impact = ace.impact
        self.assertAlmostEqual(impact.starter_value, 80.0)

    def test_starter_below_average_has_negative_starter_value(self) -> None:
        weak = Pitcher(name='Weak', rating=config.ELO_BASELINE - 30.0)
        self.assertAlmostEqual(weak.impact.starter_value, -30.0)

    def test_starter_never_populates_other_roles(self) -> None:
        ace = Pitcher(name='Ace', rating=1600.0)
        impact = ace.impact
        self.assertIsNone(impact.bullpen_value)
        self.assertIsNone(impact.offense_value)
        self.assertIsNone(impact.defense_value)
        self.assertEqual(impact.populated_roles, ('starter',))


class TestRelieverImpact(unittest.TestCase):
    def test_closer_above_average_has_positive_bullpen_value(self) -> None:
        closer = Reliever(name='Closer', rating=config.ELO_BASELINE + 65.0, leverage=1.0)
        self.assertAlmostEqual(closer.impact.bullpen_value, 65.0)

    def test_reliever_never_populates_other_roles(self) -> None:
        closer = Reliever(name='Closer', rating=1550.0)
        impact = closer.impact
        self.assertIsNone(impact.starter_value)
        self.assertIsNone(impact.offense_value)
        self.assertIsNone(impact.defense_value)
        self.assertEqual(impact.populated_roles, ('bullpen',))

    def test_starter_and_reliever_impacts_are_not_comparable_on_the_same_field(self) -> None:
        """The core ask: no universal `player.impact` scalar. A starter and
        a reliever with the identical rating gap over average populate
        DIFFERENT fields, not the same one — so summing/comparing them
        blindly isn't possible by accident."""
        starter = Pitcher(name='Ace', rating=config.ELO_BASELINE + 50.0)
        reliever = Reliever(name='Closer', rating=config.ELO_BASELINE + 50.0)
        self.assertIsNotNone(starter.impact.starter_value)
        self.assertIsNone(starter.impact.bullpen_value)
        self.assertIsNotNone(reliever.impact.bullpen_value)
        self.assertIsNone(reliever.impact.starter_value)


if __name__ == '__main__':
    unittest.main()
