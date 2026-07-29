# ==============================================================================
# tests/test_lineups_model.py
#
# Lineups (vs LHP/RHP).
# Covers models/hitter.TeamLineups.for_opposing_pitcher and
# models/pitcher.Pitcher.throws validation. No network.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

from models.hitter import Hitter, TeamLineups, TeamOffense
from models.pitcher import Pitcher


def _offense(rating: float) -> TeamOffense:
    return TeamOffense(team='Los Angeles Dodgers', lineup_rating=rating, hitters=(Hitter(name='A', rating=rating),))


class TestTeamLineups(unittest.TestCase):
    def test_rejects_empty_team(self) -> None:
        with self.assertRaises(ValueError):
            TeamLineups(team='', vs_rhp=_offense(1500), vs_lhp=_offense(1500))

    def test_for_opposing_pitcher_l_selects_vs_lhp(self) -> None:
        lineups = TeamLineups(team='Los Angeles Dodgers', vs_rhp=_offense(1500), vs_lhp=_offense(1560))
        self.assertEqual(lineups.for_opposing_pitcher('L').lineup_rating, 1560)

    def test_for_opposing_pitcher_r_selects_vs_rhp(self) -> None:
        lineups = TeamLineups(team='Los Angeles Dodgers', vs_rhp=_offense(1540), vs_lhp=_offense(1460))
        self.assertEqual(lineups.for_opposing_pitcher('R').lineup_rating, 1540)

    def test_unknown_hand_defaults_to_vs_rhp(self) -> None:
        lineups = TeamLineups(team='Los Angeles Dodgers', vs_rhp=_offense(1530), vs_lhp=_offense(1470))
        self.assertEqual(lineups.for_opposing_pitcher('?').lineup_rating, 1530)


class TestPitcherThrows(unittest.TestCase):
    def test_defaults_to_r(self) -> None:
        self.assertEqual(Pitcher(name='Ace').throws, 'R')

    def test_accepts_l(self) -> None:
        self.assertEqual(Pitcher(name='Lefty', throws='L').throws, 'L')

    def test_rejects_invalid_hand(self) -> None:
        with self.assertRaises(ValueError):
            Pitcher(name='Ace', throws='X')


if __name__ == '__main__':
    unittest.main()
