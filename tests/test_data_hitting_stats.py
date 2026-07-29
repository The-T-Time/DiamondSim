# ==============================================================================
# tests/test_data_hitting_stats.py
#
# Position Player (Hitting) Ratings.
# Covers data/hitting_stats.py's parsing of raw MLB Stats API roster/people
# JSON into RawHitterRecord objects (current season + last-30-days +
# career), and that pitchers are excluded. Network layer mocked — no real
# calls.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest
from unittest.mock import patch

from data.exceptions import DataFetchError
from data.hitting_stats import fetch_team_hitters

AS_OF = '2026-07-12'


def _stat_split(season, ab, h, d, t, hr, bb, hbp, so, sf, pa=None, games=1):
    pa = pa if pa is not None else (ab + bb + hbp + sf)
    split = {
        'stat': {
            'plateAppearances': pa, 'atBats': ab, 'hits': h, 'doubles': d, 'triples': t,
            'homeRuns': hr, 'baseOnBalls': bb, 'hitByPitch': hbp, 'strikeOuts': so,
            'sacFlies': sf, 'gamesPlayed': games,
        }
    }
    if season is not None:
        split['season'] = season
    return split


def _stat_group(display_name, splits):
    return {'type': {'displayName': display_name}, 'group': {'displayName': 'hitting'}, 'splits': splits}


def _roster_entry(person_id, name, position_abbr='OF', status_code='A', status_desc='Active', season_stats=None):
    return {
        'person': {'id': person_id, 'fullName': name, 'stats': season_stats or []},
        'position': {'abbreviation': position_abbr, 'code': '1' if position_abbr == 'P' else '7'},
        'status': {'code': status_code, 'description': status_desc},
    }


def _people_payload(person_id, name, stat_type, **stat_kwargs):
    return {'people': [{
        'id': person_id, 'fullName': name,
        'stats': [_stat_group(stat_type, [_stat_split(None, **stat_kwargs)])],
    }]}


class TestFetchTeamHitters(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch('data.cache.CACHE_ENABLED', False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _patch_all(self, roster_payload, last30_payload=None, career_payload=None):
        return (
            patch('data.hitting_stats.fetch_team_hitting_roster_raw', return_value=roster_payload),
            patch('data.hitting_stats.fetch_people_last_30_days_hitting_stats_raw',
                  return_value=last30_payload or {'people': []}),
            patch('data.hitting_stats.fetch_people_career_hitting_stats_raw',
                  return_value=career_payload or {'people': []}),
            patch('data.hitting_stats.fetch_people_split_hitting_stats_raw',
                  return_value={'people': []}),
        )

    def test_parses_active_hitter_with_current_season_stats(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Slugger', 'OF', season_stats=[
            _stat_group('season', [_stat_split('2026', ab=500, h=150, d=30, t=2, hr=25, bb=50, hbp=5, so=100, sf=4)])
        ])]}
        p1, p2, p3, p4 = self._patch_all(roster_payload)
        with p1, p2, p3, p4:
            hitters = fetch_team_hitters(team_id=119, season=2026, as_of_date=AS_OF)

        self.assertEqual(len(hitters), 1)
        hitter = hitters[0]
        self.assertEqual(hitter.full_name, 'Slugger')
        self.assertTrue(hitter.is_available)
        self.assertIsNotNone(hitter.current_season)
        self.assertEqual(hitter.current_season.home_runs, 25)

    def test_pitchers_are_excluded(self) -> None:
        roster_payload = {'roster': [
            _roster_entry(1, 'Slugger', 'OF', season_stats=[
                _stat_group('season', [_stat_split('2026', ab=400, h=110, d=20, t=1, hr=15, bb=30, hbp=2, so=90, sf=3)])
            ]),
            _roster_entry(2, 'Ace Arm', 'P'),
        ]}
        p1, p2, p3, p4 = self._patch_all(roster_payload)
        with p1, p2, p3, p4:
            hitters = fetch_team_hitters(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertEqual(len(hitters), 1)
        self.assertEqual(hitters[0].full_name, 'Slugger')

    def test_injured_hitter_flagged_correctly(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Hurt Bat', 'SS', status_code='IL10',
                                                     status_desc='10-Day IL')]}
        p1, p2, p3, p4 = self._patch_all(roster_payload)
        with p1, p2, p3, p4:
            hitters = fetch_team_hitters(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertFalse(hitters[0].is_available)
        self.assertTrue(hitters[0].is_injured)

    def test_last_30_days_and_career_merged_by_person_id(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Slugger', 'OF', season_stats=[
            _stat_group('season', [_stat_split('2026', ab=100, h=28, d=5, t=0, hr=5, bb=10, hbp=1, so=20, sf=1)])
        ])]}
        last30_payload = _people_payload(1, 'Slugger', 'byDateRange', ab=80, h=24, d=4, t=0, hr=4, bb=8, hbp=1, so=16, sf=1)
        career_payload = _people_payload(1, 'Slugger', 'career', ab=3000, h=850, d=160, t=10, hr=140, bb=300, hbp=20, so=650, sf=25)
        p1, p2, p3, p4 = self._patch_all(roster_payload, last30_payload, career_payload)
        with p1, p2, p3, p4:
            hitters = fetch_team_hitters(team_id=119, season=2026, as_of_date=AS_OF)

        hitter = hitters[0]
        self.assertIsNotNone(hitter.last_30_days)
        self.assertEqual(hitter.last_30_days.home_runs, 4)
        self.assertIsNotNone(hitter.career)
        self.assertEqual(hitter.career.home_runs, 140)

    def test_rookie_with_no_career_stats_gets_none(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Rookie Bat', '2B', season_stats=[
            _stat_group('season', [_stat_split('2026', ab=60, h=15, d=3, t=0, hr=1, bb=5, hbp=0, so=18, sf=0)])
        ])]}
        p1, p2, p3, p4 = self._patch_all(roster_payload)
        with p1, p2, p3, p4:
            hitters = fetch_team_hitters(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertIsNone(hitters[0].career)
        self.assertIsNone(hitters[0].last_30_days)

    def test_malformed_roster_shape_raises_data_fetch_error(self) -> None:
        with patch('data.hitting_stats.fetch_team_hitting_roster_raw', return_value={'roster': 'nope'}):
            with self.assertRaises(DataFetchError):
                fetch_team_hitters(team_id=119, season=2026, as_of_date=AS_OF)

    def test_malformed_single_entry_is_skipped_not_fatal(self) -> None:
        roster_payload = {'roster': [
            {'person': None, 'position': {'abbreviation': 'OF'}, 'status': {'code': 'A'}},
            _roster_entry(2, 'Healthy Bat', 'OF'),
        ]}
        p1, p2, p3, p4 = self._patch_all(roster_payload)
        with p1, p2, p3, p4:
            hitters = fetch_team_hitters(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertEqual(len(hitters), 1)
        self.assertEqual(hitters[0].full_name, 'Healthy Bat')

    def test_last_30_days_date_range_computed_from_as_of_date(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Bat', 'OF', season_stats=[
            _stat_group('season', [_stat_split('2026', ab=50, h=12, d=2, t=0, hr=1, bb=5, hbp=0, so=10, sf=0)])
        ])]}
        with patch('data.hitting_stats.fetch_team_hitting_roster_raw', return_value=roster_payload), \
             patch('data.hitting_stats.fetch_people_last_30_days_hitting_stats_raw',
                   return_value={'people': []}) as mock_last30, \
             patch('data.hitting_stats.fetch_people_career_hitting_stats_raw', return_value={'people': []}), \
             patch('data.hitting_stats.fetch_people_split_hitting_stats_raw', return_value={'people': []}):
            fetch_team_hitters(team_id=119, season=2026, as_of_date='2026-07-12')

        (_, start_date, end_date), _ = mock_last30.call_args
        self.assertEqual(end_date, '2026-07-12')
        self.assertEqual(start_date, '2026-06-12')


    def test_platoon_splits_are_merged_by_person_id(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Slugger', 'OF', season_stats=[
            _stat_group('season', [_stat_split('2026', ab=400, h=110, d=20, t=1, hr=15, bb=30, hbp=2, so=90, sf=3)])
        ])]}
        vs_lhp_payload = _people_payload(1, 'Slugger', 'vsLHP', ab=100, h=35, d=8, t=0, hr=6, bb=10, hbp=0, so=18, sf=1)
        vs_rhp_payload = _people_payload(1, 'Slugger', 'vsRHP', ab=300, h=75, d=12, t=1, hr=9, bb=20, hbp=2, so=72, sf=2)
        with patch('data.hitting_stats.fetch_team_hitting_roster_raw', return_value=roster_payload), \
             patch('data.hitting_stats.fetch_people_last_30_days_hitting_stats_raw', return_value={'people': []}), \
             patch('data.hitting_stats.fetch_people_career_hitting_stats_raw', return_value={'people': []}), \
             patch('data.hitting_stats.fetch_people_split_hitting_stats_raw',
                   side_effect=lambda ids, season, sit_code: vs_lhp_payload if sit_code == 'vl' else vs_rhp_payload):
            hitters = fetch_team_hitters(team_id=119, season=2026, as_of_date=AS_OF)

        hitter = hitters[0]
        self.assertIsNotNone(hitter.vs_lhp)
        self.assertEqual(hitter.vs_lhp.home_runs, 6)
        self.assertIsNotNone(hitter.vs_rhp)
        self.assertEqual(hitter.vs_rhp.home_runs, 9)

    def test_no_platoon_split_data_leaves_fields_none(self) -> None:
        roster_payload = {'roster': [_roster_entry(1, 'Slugger', 'OF', season_stats=[
            _stat_group('season', [_stat_split('2026', ab=400, h=110, d=20, t=1, hr=15, bb=30, hbp=2, so=90, sf=3)])
        ])]}
        p1, p2, p3, p4 = self._patch_all(roster_payload)
        with p1, p2, p3, p4:
            hitters = fetch_team_hitters(team_id=119, season=2026, as_of_date=AS_OF)
        self.assertIsNone(hitters[0].vs_lhp)
        self.assertIsNone(hitters[0].vs_rhp)


if __name__ == '__main__':
    unittest.main()
