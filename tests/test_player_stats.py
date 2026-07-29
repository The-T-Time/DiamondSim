# ==============================================================================
# tests/test_player_stats.py
#
# Real Pitcher Ratings & rolling stats.
# Covers data/player_stats.py's parsing of raw MLB Stats API roster/people
# JSON into RawPlayerRecord objects (current season + last-30-days +
# career). The network layer (data/api.py's fetch_team_roster_raw /
# fetch_people_last_30_days_stats_raw / fetch_people_career_stats_raw) is
# mocked out with hand-built fixture payloads shaped like real API
# responses, so these tests run with no network access.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest
from unittest.mock import patch

from data.exceptions import DataFetchError
from data.player_stats import fetch_team_pitching_staff

AS_OF = '2026-07-12'


def _stat_split(season: str | None, ip: str, so: int, bb: int, hr: int,
                 hbp: int = 0, er: int = 0, games: int = 1, gs: int = 1) -> dict:
    split = {
        'stat': {
            'inningsPitched': ip,
            'strikeOuts': so,
            'baseOnBalls': bb,
            'homeRuns': hr,
            'hitBatsmen': hbp,
            'earnedRuns': er,
            'gamesPitched': games,
            'gamesStarted': gs,
        }
    }
    if season is not None:
        split['season'] = season
    return split


def _stat_group(display_name: str, splits: list[dict]) -> dict:
    return {'type': {'displayName': display_name}, 'group': {'displayName': 'pitching'}, 'splits': splits}


def _roster_entry(person_id: int, name: str, status_code: str = 'A',
                   status_desc: str = 'Active', season_stats: list | None = None,
                   pitch_hand: str | None = None) -> dict:
    person = {'id': person_id, 'fullName': name, 'stats': season_stats or []}
    if pitch_hand is not None:
        person['pitchHand'] = {'code': pitch_hand}
    return {
        'person': person,
        'position': {'code': '1', 'abbreviation': 'P'},
        'status': {'code': status_code, 'description': status_desc},
    }


def _hitter_entry(person_id: int, name: str) -> dict:
    return {
        'person': {'id': person_id, 'fullName': name, 'stats': []},
        'position': {'code': '3', 'abbreviation': '1B'},
        'status': {'code': 'A', 'description': 'Active'},
    }


def _people_payload(person_id: int, name: str, stat_type: str, ip: str, so: int, bb: int, hr: int) -> dict:
    return {'people': [{
        'id': person_id, 'fullName': name,
        'stats': [_stat_group(stat_type, [_stat_split(None, ip, so, bb, hr)])],
    }]}


class TestFetchTeamPitchingStaff(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch('data.cache.CACHE_ENABLED', False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch_all(self, roster_payload, last30_payload=None, career_payload=None):
        return (
            patch('data.player_stats.fetch_team_roster_raw', return_value=roster_payload),
            patch('data.player_stats.fetch_people_last_30_days_stats_raw',
                  return_value=last30_payload or {'people': []}),
            patch('data.player_stats.fetch_people_career_stats_raw',
                  return_value=career_payload or {'people': []}),
        )

    def test_parses_active_pitcher_with_current_season_stats(self) -> None:
        roster_payload = {
            'roster': [_roster_entry(1, 'Ace Arm', season_stats=[
                _stat_group('season', [_stat_split('2026', '180.1', 200, 40, 15)])
            ])]
        }
        p1, p2, p3 = self._patch_all(roster_payload)
        with p1, p2, p3:
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)

        self.assertEqual(len(staff), 1)
        pitcher = staff[0]
        self.assertEqual(pitcher.full_name, 'Ace Arm')
        self.assertTrue(pitcher.is_available)
        self.assertIsNotNone(pitcher.current_season)
        self.assertAlmostEqual(pitcher.current_season.innings_pitched, 180 + 1 / 3, places=4)
        self.assertEqual(pitcher.current_season.strikeouts, 200)

    def test_non_pitchers_are_excluded(self) -> None:
        roster_payload = {
            'roster': [
                _roster_entry(1, 'Ace Arm', season_stats=[
                    _stat_group('season', [_stat_split('2026', '100.0', 100, 20, 10)])
                ]),
                _hitter_entry(2, 'Slugger'),
            ]
        }
        p1, p2, p3 = self._patch_all(roster_payload)
        with p1, p2, p3:
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertEqual(len(staff), 1)
        self.assertEqual(staff[0].full_name, 'Ace Arm')

    def test_injured_list_status_is_marked_unavailable_and_injured(self) -> None:
        roster_payload = {
            'roster': [_roster_entry(1, 'Hurt Arm', status_code='IL15', status_desc='15-Day Injured List',
                                      season_stats=[_stat_group('season', [_stat_split('2026', '40.0', 45, 12, 5)])])]
        }
        p1, p2, p3 = self._patch_all(roster_payload)
        with p1, p2, p3:
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)
        pitcher = staff[0]
        self.assertFalse(pitcher.is_available)
        self.assertTrue(pitcher.is_injured)

    def test_optioned_status_is_unavailable_but_not_injured(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Sent Down', status_code='RM', status_desc='Rehab Minors')]}
        p1, p2, p3 = self._patch_all(roster_payload)
        with p1, p2, p3:
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertFalse(staff[0].is_available)

    def test_last_30_days_and_career_are_merged_in_by_person_id(self) -> None:
        roster_payload = {
            'roster': [_roster_entry(1, 'Ace Arm', season_stats=[
                _stat_group('season', [_stat_split('2026', '20.0', 25, 5, 2)])
            ])]
        }
        last30_payload = _people_payload(1, 'Ace Arm', 'byDateRange', '18.0', 22, 4, 1)
        career_payload = _people_payload(1, 'Ace Arm', 'career', '900.0', 1000, 250, 90)
        p1, p2, p3 = self._patch_all(roster_payload, last30_payload, career_payload)
        with p1, p2, p3:
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)

        pitcher = staff[0]
        self.assertIsNotNone(pitcher.last_30_days)
        self.assertEqual(pitcher.last_30_days.strikeouts, 22)
        self.assertIsNotNone(pitcher.career)
        self.assertEqual(pitcher.career.strikeouts, 1000)

    def test_rookie_with_no_career_stats_gets_none(self) -> None:
        roster_payload = {
            'roster': [_roster_entry(1, 'Rookie Arm', season_stats=[
                _stat_group('season', [_stat_split('2026', '30.0', 35, 10, 3)])
            ])]
        }
        p1, p2, p3 = self._patch_all(roster_payload)
        with p1, p2, p3:
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertIsNone(staff[0].career)
        self.assertIsNone(staff[0].last_30_days)

    def test_innings_pitched_thirds_are_parsed_correctly(self) -> None:
        roster_payload = {
            'roster': [_roster_entry(1, 'Arm', season_stats=[
                _stat_group('season', [_stat_split('2026', '100.2', 90, 30, 10)])
            ])]
        }
        p1, p2, p3 = self._patch_all(roster_payload)
        with p1, p2, p3:
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertAlmostEqual(staff[0].current_season.innings_pitched, 100 + 2 / 3, places=4)

    def test_malformed_roster_shape_raises_data_fetch_error(self) -> None:
        with patch('data.player_stats.fetch_team_roster_raw', return_value={'roster': 'not-a-list'}):
            with self.assertRaises(DataFetchError):
                fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)

    def test_malformed_single_entry_is_skipped_not_fatal(self) -> None:
        roster_payload = {
            'roster': [
                {'person': None, 'position': {'code': '1'}, 'status': {'code': 'A'}},   #malformed
                _roster_entry(2, 'Healthy Arm', season_stats=[
                    _stat_group('season', [_stat_split('2026', '100.0', 90, 30, 10)])
                ]),
            ]
        }
        p1, p2, p3 = self._patch_all(roster_payload)
        with p1, p2, p3:
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertEqual(len(staff), 1)
        self.assertEqual(staff[0].full_name, 'Healthy Arm')

    def test_last_30_days_date_range_is_computed_from_as_of_date(self) -> None:
        roster_payload = {
            'roster': [_roster_entry(1, 'Arm', season_stats=[
                _stat_group('season', [_stat_split('2026', '20.0', 20, 5, 2)])
            ])]
        }
        with patch('data.player_stats.fetch_team_roster_raw', return_value=roster_payload), \
             patch('data.player_stats.fetch_people_last_30_days_stats_raw',
                   return_value={'people': []}) as mock_last30, \
             patch('data.player_stats.fetch_people_career_stats_raw', return_value={'people': []}):
            fetch_team_pitching_staff(team_id=119, season=2026, as_of_date='2026-07-12')

        (_, start_date, end_date), _ = mock_last30.call_args
        self.assertEqual(end_date, '2026-07-12')
        self.assertEqual(start_date, '2026-06-12')

    def test_pitch_hand_is_parsed_into_throws(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Lefty Arm', pitch_hand='L')]}
        with patch('data.player_stats.fetch_team_roster_raw', return_value=roster_payload), \
             patch('data.player_stats.fetch_people_last_30_days_stats_raw', return_value={'people': []}), \
             patch('data.player_stats.fetch_people_career_stats_raw', return_value={'people': []}):
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertEqual(staff[0].throws, 'L')

    def test_missing_pitch_hand_leaves_throws_none(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Arm')]}
        with patch('data.player_stats.fetch_team_roster_raw', return_value=roster_payload), \
             patch('data.player_stats.fetch_people_last_30_days_stats_raw', return_value={'people': []}), \
             patch('data.player_stats.fetch_people_career_stats_raw', return_value={'people': []}):
            staff = fetch_team_pitching_staff(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertIsNone(staff[0].throws)


if __name__ == '__main__':
    unittest.main()
