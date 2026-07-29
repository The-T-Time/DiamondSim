# ==============================================================================
# tests/test_deterministic_seed.py
#
# Covers simulation/deterministic_seed.py's team_seed — the shared helper
# previously duplicated (as _team_seed) in both simulation/pitching.py and
# simulation/offense_calculator.py.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

from simulation.deterministic_seed import team_seed


class TestTeamSeed(unittest.TestCase):
    def test_same_team_and_salt_produce_the_same_sequence(self) -> None:
        a = team_seed('Los Angeles Dodgers', salt=0x1234)
        b = team_seed('Los Angeles Dodgers', salt=0x1234)
        self.assertEqual([a.random() for _ in range(5)], [b.random() for _ in range(5)])

    def test_different_teams_produce_different_sequences(self) -> None:
        a = team_seed('Los Angeles Dodgers', salt=0x1234)
        b = team_seed('New York Yankees', salt=0x1234)
        self.assertNotEqual([a.random() for _ in range(5)], [b.random() for _ in range(5)])

    def test_different_salts_produce_different_sequences_for_same_team(self) -> None:
        a = team_seed('Los Angeles Dodgers', salt=0x1111)
        b = team_seed('Los Angeles Dodgers', salt=0x2222)
        self.assertNotEqual([a.random() for _ in range(5)], [b.random() for _ in range(5)])


if __name__ == '__main__':
    unittest.main()
