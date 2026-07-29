# ==============================================================================
# tests/test_roster_strength.py
#
# Roster & Player Availability.
# Covers simulation/roster_strength.py in isolation — pure math over
# hand-built Roster fixtures, no network.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

from models.player import Player
from models.roster import Roster
from simulation.roster_strength import RosterStrength, compute_roster_strength


def _player(pid: int, name: str, position: str, status_code: str = 'A') -> Player:
    return Player(person_id=pid, full_name=name, position=position,
                  status_code=status_code, status_description='n/a')


class TestComputeRosterStrength(unittest.TestCase):
    def test_fully_healthy_roster_is_100_percent_available(self) -> None:
        roster = Roster(team='Los Angeles Dodgers', players=(
            _player(1, 'Ace', 'P'), _player(2, 'Closer', 'P'), _player(3, 'SS', 'SS'),
        ))
        strength = compute_roster_strength(roster)
        self.assertEqual(strength.availability_pct, 1.0)
        self.assertEqual(strength.pitching_availability_pct, 1.0)
        self.assertEqual(strength.position_player_availability_pct, 1.0)
        self.assertEqual(strength.unavailable_players, 0)

    def test_mixed_availability_is_split_correctly_by_role(self) -> None:
        roster = Roster(team='Los Angeles Dodgers', players=(
            _player(1, 'Ace', 'P', 'A'),
            _player(2, 'Hurt SP', 'P', 'IL15'),
            _player(3, 'Closer', 'P', 'A'),
            _player(4, 'SS', 'SS', 'A'),
            _player(5, 'Hurt OF', 'OF', 'IL10'),
        ))
        strength = compute_roster_strength(roster)
        self.assertEqual(strength.total_players, 5)
        self.assertEqual(strength.available_players, 3)
        self.assertEqual(strength.unavailable_players, 2)
        self.assertEqual(strength.pitchers_total, 3)
        self.assertEqual(strength.pitchers_available, 2)
        self.assertAlmostEqual(strength.pitching_availability_pct, 2 / 3)
        self.assertEqual(strength.position_players_total, 2)
        self.assertEqual(strength.position_players_available, 1)
        self.assertAlmostEqual(strength.position_player_availability_pct, 0.5)
        self.assertAlmostEqual(strength.availability_pct, 3 / 5)

    def test_empty_roster_reads_as_zero_percent_not_a_crash(self) -> None:
        roster = Roster(team='Los Angeles Dodgers', players=())
        strength = compute_roster_strength(roster)
        self.assertEqual(strength.availability_pct, 0.0)
        self.assertEqual(strength.pitching_availability_pct, 0.0)
        self.assertEqual(strength.position_player_availability_pct, 0.0)

    def test_roster_with_no_pitchers_has_zero_pitching_pct_not_a_crash(self) -> None:
        roster = Roster(team='Los Angeles Dodgers', players=(_player(1, 'SS', 'SS', 'A'),))
        strength = compute_roster_strength(roster)
        self.assertEqual(strength.pitchers_total, 0)
        self.assertEqual(strength.pitching_availability_pct, 0.0)


class TestRosterStrengthValidation(unittest.TestCase):
    def test_rejects_available_exceeding_total(self) -> None:
        with self.assertRaises(ValueError):
            RosterStrength(
                team='X', total_players=2, available_players=3,
                pitchers_total=1, pitchers_available=1,
                position_players_total=1, position_players_available=1,
            )

    def test_rejects_pitchers_available_exceeding_pitchers_total(self) -> None:
        with self.assertRaises(ValueError):
            RosterStrength(
                team='X', total_players=5, available_players=3,
                pitchers_total=1, pitchers_available=2,
                position_players_total=4, position_players_available=1,
            )


if __name__ == '__main__':
    unittest.main()
