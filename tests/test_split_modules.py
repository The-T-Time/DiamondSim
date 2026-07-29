# ==============================================================================
# tests/test_split_modules.py
#
# Targeted unit tests for the modules pulled out of simulator.py in the 5.6
# split: game_simulator.py, series_simulator.py, playoff_simulator.py.
# test_simulator.py / test_postseason.py already cover the end-to-end
# behavior through run_simulation_core; these tests pin down each piece in
# isolation so a future change to one can't silently break another.
# ==============================================================================

import random
import unittest

from models.simulation_config import SimulationConfig
from simulation.game_simulator import simulate_regular_season_game
from simulation.series_simulator import HOME_PATTERNS, play_series
from simulation.playoff_simulator import simulate_postseason
from simulation.standings import build_base_records

DODGERS = 'Los Angeles Dodgers'   #NL West
PADRES  = 'San Diego Padres'      #NL West
ROCKIES = 'Colorado Rockies'      #NL West


class TestGameSimulator(unittest.TestCase):
    def test_returns_one_of_the_two_teams_as_winner(self) -> None:
        elo = {DODGERS: 1600.0, PADRES: 1400.0}
        rng = random.Random(1)
        outcome = simulate_regular_season_game(DODGERS, PADRES, elo, SimulationConfig(), rng)
        self.assertIn(outcome.winner, (DODGERS, PADRES))
        self.assertEqual({outcome.winner, outcome.loser}, {DODGERS, PADRES})

    def test_margin_respects_the_configured_cap(self) -> None:
        elo = {DODGERS: 2000.0, PADRES: 1000.0}   #huge gap -> big implied margin
        cfg = SimulationConfig(sim_margin_cap=4)
        rng = random.Random(2)
        for _ in range(50):
            outcome = simulate_regular_season_game(DODGERS, PADRES, elo.copy(), cfg, rng)
            self.assertLessEqual(outcome.margin, 4)
            self.assertGreaterEqual(outcome.margin, 1)

    def test_elo_is_updated_in_place(self) -> None:
        elo = {DODGERS: 1500.0, PADRES: 1500.0}
        rng = random.Random(3)
        simulate_regular_season_game(DODGERS, PADRES, elo, SimulationConfig(), rng)
        #Someone moved up, someone moved down — Elo can't stay exactly 1500/1500.
        self.assertNotEqual((elo[DODGERS], elo[PADRES]), (1500.0, 1500.0))

    def test_much_stronger_team_wins_more_often(self) -> None:
        wins = 0
        trials = 300
        for i in range(trials):
            elo = {DODGERS: 1800.0, PADRES: 1200.0}
            rng = random.Random(i)
            outcome = simulate_regular_season_game(DODGERS, PADRES, elo, SimulationConfig(), rng)
            if outcome.winner == DODGERS:
                wins += 1
        self.assertGreater(wins / trials, 0.8)


class TestSeriesSimulator(unittest.TestCase):
    def test_wild_card_pattern_is_all_home_for_the_host(self) -> None:
        self.assertEqual(HOME_PATTERNS[3], [True, True, True])

    def test_division_series_pattern_is_2_2_1(self) -> None:
        self.assertEqual(HOME_PATTERNS[5], [True, True, False, False, True])

    def test_lcs_and_ws_pattern_is_2_3_2(self) -> None:
        self.assertEqual(HOME_PATTERNS[7], [True, True, False, False, False, True, True])

    def test_series_winner_is_one_of_the_two_teams(self) -> None:
        elo = {DODGERS: 1550.0, PADRES: 1500.0}
        rng = random.Random(4)
        winner = play_series(DODGERS, PADRES, elo, SimulationConfig(), rng, best_of=5)
        self.assertIn(winner, (DODGERS, PADRES))

    def test_much_stronger_higher_seed_wins_series_more_often(self) -> None:
        wins = 0
        trials = 200
        for i in range(trials):
            elo = {DODGERS: 1900.0, PADRES: 1100.0}
            rng = random.Random(i + 1000)
            winner = play_series(DODGERS, PADRES, elo, SimulationConfig(), rng, best_of=7)
            if winner == DODGERS:
                wins += 1
        self.assertGreater(wins / trials, 0.9)

    def test_unknown_series_length_raises(self) -> None:
        elo = {DODGERS: 1500.0, PADRES: 1500.0}
        with self.assertRaises(KeyError):
            play_series(DODGERS, PADRES, elo, SimulationConfig(), random.Random(0), best_of=4)


class TestPlayoffSimulator(unittest.TestCase):
    """Full-bracket smoke test with a tiny synthetic league (still needs all
    30 real teams for standings.py's division/league lookups, but only cares
    that the champion is a legitimate playoff participant)."""

    @staticmethod
    def _synthetic_records_and_h2h():
        from data.teams import ALL_TEAMS
        from collections import defaultdict
        #Give every AL/NL team a distinct win total so seeding is unambiguous,
        #and a division/league split that matches TEAM_REGISTRY's real layout.
        records = {}
        h2h = {t: defaultdict(int) for t in ALL_TEAMS}
        for i, t in enumerate(ALL_TEAMS):
            wins = 100 - i   #strictly decreasing, so nobody ties
            records[t] = {
                'W': wins, 'L': 162 - wins,
                'div_W': 0, 'div_L': 0, 'league_W': 0, 'league_L': 0,
                'league_results': [],
            }
        return records, h2h

    def test_champion_is_a_real_team(self) -> None:
        from data.teams import ALL_TEAMS
        records, h2h = self._synthetic_records_and_h2h()
        elo = {t: 1500.0 for t in ALL_TEAMS}
        rng = random.Random(11)
        champion = simulate_postseason(records, h2h, elo, SimulationConfig(), rng).champion
        self.assertIn(champion, ALL_TEAMS)

    def test_champion_is_deterministic_given_the_same_seed(self) -> None:
        from data.teams import ALL_TEAMS
        records, h2h = self._synthetic_records_and_h2h()
        elo = {t: 1500.0 for t in ALL_TEAMS}
        champ_a = simulate_postseason(records, h2h, dict(elo), SimulationConfig(), random.Random(99))
        champ_b = simulate_postseason(records, h2h, dict(elo), SimulationConfig(), random.Random(99))
        self.assertEqual(champ_a, champ_b)


if __name__ == '__main__':
    unittest.main()
