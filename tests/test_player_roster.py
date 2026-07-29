# ==============================================================================
# tests/test_player_roster.py
#
# Roster & Player Availability.
# Covers models/player.py and models/roster.py in isolation — pure data,
# no network. Hand-built Player/Roster fixtures.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

from models.player import Player
from models.roster import Roster


def _player(pid: int, name: str, position: str, status_code: str = 'A',
            status_desc: str = 'Active') -> Player:
    return Player(person_id=pid, full_name=name, position=position,
                  status_code=status_code, status_description=status_desc)


class TestPlayer(unittest.TestCase):
    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            Player(person_id=1, full_name='', position='P', status_code='A', status_description='Active')

    def test_rejects_empty_position(self) -> None:
        with self.assertRaises(ValueError):
            Player(person_id=1, full_name='Arm', position='', status_code='A', status_description='Active')

    def test_is_pitcher_true_for_position_p(self) -> None:
        self.assertTrue(_player(1, 'Ace', 'P').is_pitcher)

    def test_is_pitcher_false_for_other_positions(self) -> None:
        for pos in ('C', '1B', '2B', '3B', 'SS', 'OF', 'DH'):
            self.assertFalse(_player(1, 'Bat', pos).is_pitcher, msg=pos)

    def test_active_status_is_available(self) -> None:
        self.assertTrue(_player(1, 'Arm', 'P', 'A', 'Active').is_available)
        self.assertFalse(_player(1, 'Arm', 'P', 'A', 'Active').is_injured)

    def test_il_status_is_unavailable_and_injured(self) -> None:
        p = _player(1, 'Arm', 'P', 'IL15', '15-Day Injured List')
        self.assertFalse(p.is_available)
        self.assertTrue(p.is_injured)

    def test_disabled_list_pre_2019_naming_is_injured(self) -> None:
        p = _player(1, 'Arm', 'P', 'D60', '60-Day Disabled List')
        self.assertTrue(p.is_injured)

    def test_optioned_status_is_unavailable_but_not_injured(self) -> None:
        p = _player(1, 'Kid', 'OF', 'RM', 'Rehab Minors')
        self.assertFalse(p.is_available)
        self.assertFalse(p.is_injured)

    def test_str_is_full_name(self) -> None:
        self.assertEqual(str(_player(1, 'Ace Arm', 'P')), 'Ace Arm')


class TestRoster(unittest.TestCase):
    def _sample_roster(self) -> Roster:
        return Roster(team='Los Angeles Dodgers', players=(
            _player(1, 'Ace', 'P', 'A'),
            _player(2, 'Hurt Starter', 'P', 'IL15', '15-Day IL'),
            _player(3, 'Closer', 'P', 'A'),
            _player(4, 'Shortstop', 'SS', 'A'),
            _player(5, 'Hurt Outfielder', 'OF', 'IL10', '10-Day IL'),
        ))

    def test_rejects_empty_team(self) -> None:
        with self.assertRaises(ValueError):
            Roster(team='', players=())

    def test_allows_empty_players(self) -> None:
        roster = Roster(team='Los Angeles Dodgers', players=())
        self.assertEqual(roster.players, ())
        self.assertEqual(roster.available_players, ())

    def test_available_and_unavailable_split(self) -> None:
        roster = self._sample_roster()
        self.assertEqual(len(roster.available_players), 3)
        self.assertEqual(len(roster.unavailable_players), 2)
        self.assertEqual(
            {p.full_name for p in roster.unavailable_players},
            {'Hurt Starter', 'Hurt Outfielder'},
        )

    def test_pitchers_and_position_players_split(self) -> None:
        roster = self._sample_roster()
        self.assertEqual({p.full_name for p in roster.pitchers}, {'Ace', 'Hurt Starter', 'Closer'})
        self.assertEqual({p.full_name for p in roster.position_players}, {'Shortstop', 'Hurt Outfielder'})

    def test_find_returns_matching_player(self) -> None:
        roster = self._sample_roster()
        found = roster.find(3)
        self.assertIsNotNone(found)
        self.assertEqual(found.full_name, 'Closer')

    def test_find_returns_none_for_unknown_id(self) -> None:
        roster = self._sample_roster()
        self.assertIsNone(roster.find(999))


if __name__ == '__main__':
    unittest.main()
