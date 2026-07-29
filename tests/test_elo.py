# ==============================================================================
# tests/test_elo.py
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

from models.simulation_config import SimulationConfig
from simulation.elo import apply_elo_update, expected_home_win_prob, _mov_multiplier


class TestExpectedWinProb(unittest.TestCase):
    def test_stronger_team_favored(self) -> None:
        """A meaningfully higher-rated team should win more often than a coin flip."""
        strong_vs_weak = expected_home_win_prob(1700, 1400)
        self.assertGreater(strong_vs_weak, 0.5)

    def test_probability_is_symmetric_without_home_field(self) -> None:
        """With home-field advantage zeroed out, equal Elo means a true coin flip."""
        cfg = SimulationConfig(home_field_advantage=0.0)
        p = expected_home_win_prob(1500, 1500, cfg)
        self.assertAlmostEqual(p, 0.5, places=9)

    def test_home_field_advantage_favors_home_team(self) -> None:
        """Equal Elo, but home-field advantage should push the home team above 50%."""
        cfg = SimulationConfig(home_field_advantage=25)
        p = expected_home_win_prob(1500, 1500, cfg)
        self.assertGreater(p, 0.5)

    def test_probability_stays_in_valid_range(self) -> None:
        """No matter how lopsided the Elo gap, probability must stay in (0, 1)."""
        p_extreme_favorite  = expected_home_win_prob(2400, 800)
        p_extreme_underdog  = expected_home_win_prob(800, 2400)
        for p in (p_extreme_favorite, p_extreme_underdog):
            self.assertGreater(p, 0.0)
            self.assertLess(p, 1.0)

    def test_favorite_and_underdog_probabilities_are_complementary(self) -> None:
        """With home-field advantage zeroed out, swapping which team is 'home'
        for the same matchup must flip win probability exactly (p and 1-p)."""
        cfg = SimulationConfig(home_field_advantage=0.0)
        p_as_home = expected_home_win_prob(1600, 1400, cfg)
        p_flipped = expected_home_win_prob(1400, 1600, cfg)
        self.assertAlmostEqual(p_as_home + p_flipped, 1.0, places=9)


class TestApplyEloUpdate(unittest.TestCase):
    def test_update_is_zero_sum(self) -> None:
        """Whatever the home team gains, the away team must lose exactly that much."""
        elo = {'Home Team': 1500.0, 'Away Team': 1500.0}
        apply_elo_update(elo, 'Home Team', 'Away Team', home_won=True, margin=3)
        total_after = elo['Home Team'] + elo['Away Team']
        self.assertAlmostEqual(total_after, 3000.0, places=9)

    def test_upset_win_gains_more_than_expected_win(self) -> None:
        """An underdog home win should move Elo more than a big favorite winning as expected."""
        elo_upset = {'Underdog': 1400.0, 'Favorite': 1600.0}
        apply_elo_update(elo_upset, 'Underdog', 'Favorite', home_won=True, margin=1)
        upset_gain = elo_upset['Underdog'] - 1400.0

        elo_expected = {'Favorite': 1600.0, 'Underdog': 1400.0}
        apply_elo_update(elo_expected, 'Favorite', 'Underdog', home_won=True, margin=1)
        expected_gain = elo_expected['Favorite'] - 1600.0

        self.assertGreater(upset_gain, expected_gain)

    def test_winner_gains_elo_loser_loses_elo(self) -> None:
        elo = {'A': 1500.0, 'B': 1500.0}
        apply_elo_update(elo, 'A', 'B', home_won=True, margin=4)
        self.assertGreater(elo['A'], 1500.0)
        self.assertLess(elo['B'], 1500.0)


class TestMovMultiplier(unittest.TestCase):
    def test_disabled_when_weight_is_zero(self) -> None:
        cfg = SimulationConfig(mov_weight=0.0)
        self.assertEqual(_mov_multiplier(10, cfg), 1.0)

    def test_blowouts_increase_the_multiplier(self) -> None:
        cfg = SimulationConfig(mov_weight=0.3)
        small_margin  = _mov_multiplier(2, cfg)
        large_margin  = _mov_multiplier(10, cfg)
        self.assertGreater(large_margin, small_margin)

    def test_one_run_margin_is_the_baseline(self) -> None:
        cfg = SimulationConfig(mov_weight=0.3)
        self.assertEqual(_mov_multiplier(1, cfg), 1.0)


if __name__ == '__main__':
    unittest.main()
