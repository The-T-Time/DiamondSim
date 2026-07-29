# ==============================================================================
# tests/test_models.py
#
# "Test one game" + validation checks for Team / Game / SimulationConfig.
# ==============================================================================

import unittest

from models.game import Game
from models.team import Team
from models.simulation_config import SimulationConfig


class TestGame(unittest.TestCase):
    def test_one_unplayed_game(self) -> None:
        g = Game(game_pk=1, date='2026-04-01', home='Los Angeles Dodgers', away='San Diego Padres')
        self.assertFalse(g.is_played)
        self.assertIsNone(g.winner)
        self.assertIsNone(g.loser)
        self.assertIsNone(g.run_diff)

    def test_one_played_game(self) -> None:
        g = Game(
            game_pk=2, date='2026-04-02',
            home='Los Angeles Dodgers', away='San Diego Padres',
            home_score=5, away_score=2, winner='Los Angeles Dodgers',
        )
        self.assertTrue(g.is_played)
        self.assertEqual(g.loser, 'San Diego Padres')
        self.assertEqual(g.run_diff, 3)

    def test_loser_and_run_diff_cannot_drift(self) -> None:
        """loser/run_diff are computed, so they always agree with the scores —
        there's no way to construct a Game with a winner but a stale loser."""
        g = Game(
            game_pk=3, date='2026-04-03',
            home='Boston Red Sox', away='New York Yankees',
            home_score=1, away_score=9, winner='New York Yankees',
        )
        self.assertEqual(g.loser, 'Boston Red Sox')
        self.assertEqual(g.run_diff, 8)

    def test_opponent_and_home_helpers(self) -> None:
        g = Game(game_pk=4, date='2026-04-04', home='Chicago Cubs', away='Cincinnati Reds')
        self.assertEqual(g.opponent_of('Chicago Cubs'), 'Cincinnati Reds')
        self.assertEqual(g.opponent_of('Cincinnati Reds'), 'Chicago Cubs')
        self.assertTrue(g.is_home_team('Chicago Cubs'))
        self.assertFalse(g.is_home_team('Cincinnati Reds'))

    def test_team_cannot_play_itself(self) -> None:
        with self.assertRaises(ValueError):
            Game(game_pk=5, date='2026-04-05', home='Chicago Cubs', away='Chicago Cubs')

    def test_winner_must_be_a_participant(self) -> None:
        with self.assertRaises(ValueError):
            Game(
                game_pk=6, date='2026-04-06',
                home='Chicago Cubs', away='Cincinnati Reds',
                home_score=1, away_score=0, winner='Milwaukee Brewers',
            )


class TestTeam(unittest.TestCase):
    def test_valid_team_constructs(self) -> None:
        t = Team(id=119, name='Los Angeles Dodgers', division='NL West', league='NL')
        self.assertEqual(t.division, 'NL West')
        self.assertGreater(t.elo, 0)

    def test_rejects_invalid_league(self) -> None:
        with self.assertRaises(ValueError):
            Team(id=1, name='Fake Team', division='XL West', league='XL')

    def test_rejects_non_positive_elo(self) -> None:
        with self.assertRaises(ValueError):
            Team(id=1, name='Fake Team', division='NL West', league='NL', elo=0)


class TestSimulationConfig(unittest.TestCase):
    def test_presets_are_distinct(self) -> None:
        normal = SimulationConfig.normal()
        conservative = SimulationConfig.conservative()
        aggressive = SimulationConfig.aggressive()
        self.assertNotEqual(normal.elo_k, conservative.elo_k)
        self.assertNotEqual(normal.elo_k, aggressive.elo_k)

    def test_by_name_applies_overrides(self) -> None:
        cfg = SimulationConfig.by_name('conservative', simulations=500)
        self.assertEqual(cfg.simulations, 500)
        self.assertEqual(cfg.elo_k, SimulationConfig.conservative().elo_k)

    def test_rejects_unknown_preset(self) -> None:
        with self.assertRaises(ValueError):
            SimulationConfig.by_name('made_up_model')

    def test_rejects_non_positive_simulations(self) -> None:
        with self.assertRaises(ValueError):
            SimulationConfig(simulations=0)

    def test_rejects_regression_weight_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            SimulationConfig(regression_weight=1.5)


if __name__ == '__main__':
    unittest.main()
