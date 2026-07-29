# ==============================================================================
# tests/test_data_roster.py
#
# Roster & Player Availability.
# Covers data/roster.py's parsing of raw MLB Stats API roster JSON into a
# models/roster.Roster of models/player.Player objects. The network layer
# (data/api.py's fetch_full_roster_raw) is mocked with hand-built fixture
# payloads, so these tests run with no network access.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest
from unittest.mock import patch

from data.exceptions import DataFetchError
from data.roster import fetch_team_roster

DODGERS = 'Los Angeles Dodgers'


def _entry(person_id: int, name: str, position_abbr: str, status_code: str = 'A',
           status_desc: str = 'Active', jersey: str | None = None) -> dict:
    return {
        'person': {'id': person_id, 'fullName': name},
        'position': {'abbreviation': position_abbr, 'code': '1' if position_abbr == 'P' else '0'},
        'status': {'code': status_code, 'description': status_desc},
        'jerseyNumber': jersey,
    }


class TestFetchTeamRoster(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch('data.cache.CACHE_ENABLED', False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_parses_mixed_position_roster(self) -> None:
        payload = {'roster': [
            _entry(1, 'Ace Arm', 'P'),
            _entry(2, 'Star Shortstop', 'SS', jersey='7'),
            _entry(3, 'Backup Catcher', 'C'),
        ]}
        with patch('data.roster.fetch_full_roster_raw', return_value=payload):
            roster = fetch_team_roster(DODGERS, 119, 2026)

        self.assertEqual(roster.team, DODGERS)
        self.assertEqual(len(roster.players), 3)
        self.assertEqual(len(roster.pitchers), 1)
        self.assertEqual(len(roster.position_players), 2)
        shortstop = roster.find(2)
        self.assertEqual(shortstop.jersey_number, '7')

    def test_injured_and_optioned_players_are_flagged_correctly(self) -> None:
        payload = {'roster': [
            _entry(1, 'Hurt Ace', 'P', 'IL15', '15-Day Injured List'),
            _entry(2, 'Sent Down', 'OF', 'RM', 'Rehab Minors'),
            _entry(3, 'Healthy Arm', 'P', 'A', 'Active'),
        ]}
        with patch('data.roster.fetch_full_roster_raw', return_value=payload):
            roster = fetch_team_roster(DODGERS, 119, 2026)

        self.assertEqual(len(roster.available_players), 1)
        self.assertTrue(roster.find(1).is_injured)
        self.assertFalse(roster.find(2).is_injured)
        self.assertFalse(roster.find(2).is_available)

    def test_malformed_roster_shape_raises_data_fetch_error(self) -> None:
        with patch('data.roster.fetch_full_roster_raw', return_value={'roster': 'not-a-list'}):
            with self.assertRaises(DataFetchError):
                fetch_team_roster(DODGERS, 119, 2026)

    def test_malformed_single_entry_is_skipped_not_fatal(self) -> None:
        payload = {'roster': [
            {'person': None, 'position': {'abbreviation': 'P'}, 'status': {'code': 'A'}},
            _entry(2, 'Healthy Arm', 'P'),
        ]}
        with patch('data.roster.fetch_full_roster_raw', return_value=payload):
            roster = fetch_team_roster(DODGERS, 119, 2026)
        self.assertEqual(len(roster.players), 1)
        self.assertEqual(roster.players[0].full_name, 'Healthy Arm')

    def test_empty_roster_response_yields_empty_roster_not_an_error(self) -> None:
        with patch('data.roster.fetch_full_roster_raw', return_value={'roster': []}):
            roster = fetch_team_roster(DODGERS, 119, 2026)
        self.assertEqual(roster.players, ())


if __name__ == '__main__':
    unittest.main()
