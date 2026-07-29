# ==============================================================================
# tests/test_game_win_prob_lineup_bullpen.py
#
# Lineups (vs LHP/RHP) & bullpen baseline rating wired into
# game_win_prob. Covers the new optional keyword arguments in isolation —
# no network, pure math.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

from models.simulation_config import SimulationConfig
from simulation.elo import expected_home_win_prob
from simulation.pitching import game_win_prob

CFG = SimulationConfig()


class TestGameWinProbBackwardCompatibility(unittest.TestCase):
    def test_omitting_new_kwargs_matches_pre_6_7_behavior(self) -> None:
        """Existing callers that only pass the original 6 positional args
        (+ cfg) must get byte-for-byte the same result as before."""
        wp = game_win_prob(1520, 1480, 1550, 1500, 5.0, 10.0, CFG)
        starter_adj = (1550 - 1500) * 0.6
        bullpen_fatigue_adj = (10.0 - 5.0) * 1.0
        expected = expected_home_win_prob(1520 + starter_adj + bullpen_fatigue_adj, 1480, CFG)
        self.assertAlmostEqual(wp, expected, places=9)


class TestLineupAdjustment(unittest.TestCase):
    def test_better_home_lineup_raises_home_win_prob(self) -> None:
        base = game_win_prob(1500, 1500, 1500, 1500, 0.0, 0.0, CFG,
                             home_lineup_rating=1500, away_lineup_rating=1500,
                             home_bullpen_rating=1500, away_bullpen_rating=1500)
        boosted = game_win_prob(1500, 1500, 1500, 1500, 0.0, 0.0, CFG,
                                home_lineup_rating=1600, away_lineup_rating=1500,
                                home_bullpen_rating=1500, away_bullpen_rating=1500)
        self.assertGreater(boosted, base)

    def test_only_one_side_given_is_treated_as_no_adjustment(self) -> None:
        """Both sides must be given for the lineup adjustment to apply --
        a partially-specified matchup shouldn't silently bias one way."""
        no_lineups = game_win_prob(1500, 1500, 1500, 1500, 0.0, 0.0, CFG)
        one_sided = game_win_prob(1500, 1500, 1500, 1500, 0.0, 0.0, CFG,
                                  home_lineup_rating=1650)
        self.assertAlmostEqual(no_lineups, one_sided, places=9)


class TestBullpenRatingAdjustment(unittest.TestCase):
    def test_better_home_bullpen_raises_home_win_prob_even_at_equal_fatigue(self) -> None:
        """Without this fix, two equally-rested bullpens were indistinguishable
        regardless of how good either one actually was."""
        base = game_win_prob(1500, 1500, 1500, 1500, 0.0, 0.0, CFG,
                             home_bullpen_rating=1500, away_bullpen_rating=1500)
        better_pen = game_win_prob(1500, 1500, 1500, 1500, 0.0, 0.0, CFG,
                                   home_bullpen_rating=1600, away_bullpen_rating=1500)
        self.assertGreater(better_pen, base)

    def test_bullpen_rating_and_fatigue_penalty_are_independent(self) -> None:
        """A great bullpen that's exhausted should still be worse off than
        a great bullpen that's fresh -- rating and fatigue stack, not one
        replacing the other."""
        fresh_great_pen = game_win_prob(1500, 1500, 1500, 1500, 0.0, 0.0, CFG,
                                        home_bullpen_rating=1600, away_bullpen_rating=1500)
        tired_great_pen = game_win_prob(1500, 1500, 1500, 1500, 30.0, 0.0, CFG,
                                        home_bullpen_rating=1600, away_bullpen_rating=1500)
        self.assertGreater(fresh_great_pen, tired_great_pen)


class TestCombinedAdjustments(unittest.TestCase):
    def test_starter_lineup_and_bullpen_all_stack_additively(self) -> None:
        home_edge_everywhere = game_win_prob(
            1500, 1500, 1560, 1500, 0.0, 0.0, CFG,
            home_lineup_rating=1550, away_lineup_rating=1500,
            home_bullpen_rating=1540, away_bullpen_rating=1500,
        )
        home_edge_starter_only = game_win_prob(1500, 1500, 1560, 1500, 0.0, 0.0, CFG)
        #Adding lineup + bullpen edges on top of an existing starter edge
        #should push the probability further in the same direction.
        self.assertGreater(home_edge_everywhere, home_edge_starter_only)


if __name__ == '__main__':
    unittest.main()
