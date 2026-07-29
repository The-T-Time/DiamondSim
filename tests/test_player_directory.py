# ==============================================================================
# tests/test_player_directory.py
#
# Player Tab.
# Covers simulation/player_directory.py's build_pitcher_rows/build_hitter_rows:
# row shape, rating wiring, and graceful per-team failure handling. Network
# fully mocked — no live calls.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest
from unittest.mock import patch

from data.exceptions import DataFetchError
from models.hitting_stats import RawHitterRecord, SeasonHittingLine
from models.pitching_stats import RawPlayerRecord, SeasonPitchingLine
from models.simulation_config import SimulationConfig
from simulation.player_directory import build_hitter_rows, build_pitcher_rows

CFG = SimulationConfig()
AS_OF = '2026-07-12'


def _pitcher(pid: int, name: str, ip=180.0, so=170, bb=50, hr=18, er=70, w=12, l=8) -> RawPlayerRecord:
    line = SeasonPitchingLine(innings_pitched=ip, strikeouts=so, walks=bb, home_runs=hr,
                              earned_runs=er, games=30, games_started=30, wins=w, losses=l)
    return RawPlayerRecord(person_id=pid, full_name=name, status_code='A', status_description='Active',
                            current_season=line, last_30_days=None, career=None)


def _hitter(pid: int, name: str, position='OF', pa=550, ab=490, h=140, hr=20, bb=45, so=110) -> RawHitterRecord:
    line = SeasonHittingLine(plate_appearances=pa, at_bats=ab, hits=h, doubles=25, triples=2,
                             home_runs=hr, walks=bb, hit_by_pitch=3, strikeouts=so, sac_flies=4, games=140)
    return RawHitterRecord(person_id=pid, full_name=name, status_code='A', status_description='Active',
                           current_season=line, last_30_days=None, career=None, position=position)


class TestBuildPitcherRows(unittest.TestCase):
    def test_row_shape_and_values(self) -> None:
        with patch('simulation.player_directory.fetch_team_pitching_staff',
                  return_value=[_pitcher(1, 'Ace Arm')]):
            with patch('simulation.player_directory.ALL_TEAMS', ['Los Angeles Dodgers']):
                rows = build_pitcher_rows(2026, AS_OF, CFG)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['name'], 'Ace Arm')
        self.assertEqual(row['team'], 'Los Angeles Dodgers')
        self.assertEqual(row['pos'], 'P')
        self.assertIsInstance(row['rating'], float)
        self.assertEqual(row['wins'], 12)
        self.assertEqual(row['losses'], 8)
        self.assertIsNotNone(row['era'])
        self.assertIsNotNone(row['fip'])
        self.assertIn(row['league'], ('AL', 'NL'))
        self.assertIn('div', row)

    def test_better_pitcher_gets_higher_rating(self) -> None:
        ace = _pitcher(1, 'Ace', ip=200, so=250, bb=30, hr=10, er=50, w=18, l=4)
        scrub = _pitcher(2, 'Scrub', ip=100, so=60, bb=55, hr=25, er=70, w=3, l=12)
        with patch('simulation.player_directory.fetch_team_pitching_staff', return_value=[ace, scrub]):
            with patch('simulation.player_directory.ALL_TEAMS', ['Los Angeles Dodgers']):
                rows = build_pitcher_rows(2026, AS_OF, CFG)
        by_name = {r['name']: r for r in rows}
        self.assertGreater(by_name['Ace']['rating'], by_name['Scrub']['rating'])

    def test_team_fetch_failure_is_skipped_not_fatal(self) -> None:
        with patch('simulation.player_directory.fetch_team_pitching_staff', side_effect=DataFetchError('boom')):
            with patch('simulation.player_directory.ALL_TEAMS', ['Los Angeles Dodgers']):
                rows = build_pitcher_rows(2026, AS_OF, CFG)
        self.assertEqual(rows, [])


class TestBuildHitterRows(unittest.TestCase):
    def test_row_shape_and_values(self) -> None:
        with patch('simulation.player_directory.fetch_team_hitters',
                  return_value=[_hitter(1, 'Slugger', position='1B')]):
            with patch('simulation.player_directory.ALL_TEAMS', ['Los Angeles Dodgers']):
                rows = build_hitter_rows(2026, AS_OF, CFG)

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row['name'], 'Slugger')
        self.assertEqual(row['pos'], '1B')
        self.assertIsInstance(row['rating'], float)
        self.assertIsNotNone(row['avg'])
        self.assertIsNotNone(row['ops'])
        self.assertIsNotNone(row['bb_pct'])
        self.assertIsNotNone(row['k_pct'])

    def test_team_fetch_failure_is_skipped_not_fatal(self) -> None:
        with patch('simulation.player_directory.fetch_team_hitters', side_effect=DataFetchError('boom')):
            with patch('simulation.player_directory.ALL_TEAMS', ['Los Angeles Dodgers']):
                rows = build_hitter_rows(2026, AS_OF, CFG)
        self.assertEqual(rows, [])


if __name__ == '__main__':
    unittest.main()
