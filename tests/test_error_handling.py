# ==============================================================================
# tests/test_error_handling.py
#
# Corrupted cache and unreachable API must degrade gracefully — never an
# unhandled crash.
# ==============================================================================

import json
import unittest
from unittest import mock

import requests

import data.cache as cache_mod
from data.api import get_season_boundaries, fetch_schedule, parse_schedule_into_games
from data.exceptions import DataFetchError
from models.simulation_config import SimulationConfig


class TestCorruptedCache(unittest.TestCase):
    def setUp(self) -> None:
        cache_mod.CACHE_ENABLED = True
        cache_mod.CACHE_EXPIRY_SECONDS = 999999
        self.cfg = SimulationConfig(simulations=100)
        self.season = 8888
        self.path = cache_mod.cache_path(self.season, self.cfg)

    def tearDown(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def test_invalid_json_is_treated_as_a_cache_miss(self) -> None:
        self.path.write_text("{this is not valid json,,,")
        result = cache_mod.load_cache(self.season, self.cfg)
        self.assertIsNone(result)

    def test_invalid_json_cache_file_is_cleaned_up(self) -> None:
        self.path.write_text("not json at all")
        cache_mod.load_cache(self.season, self.cfg)
        self.assertFalse(self.path.exists())

    def test_valid_json_with_wrong_shape_is_treated_as_a_cache_miss(self) -> None:
        """Valid JSON, but missing fields Game(**g) needs — e.g. an old cache
        schema from before a refactor. Must not raise, must not crash."""
        self.path.write_text(json.dumps({
            'live_standings': {},
            'derived_base_elo': {},
            'played_games': [{'unexpected_field': 1}],   #missing home/away/etc.
            'unplayed_games': [],
        }))
        result = cache_mod.load_cache(self.season, self.cfg)
        self.assertIsNone(result)

    def test_save_cache_survives_unwritable_directory(self) -> None:
        """If the cache file can't be written (permissions, full disk, ...),
        save_cache must log and return, not raise."""
        payload = {'live_standings': {}, 'derived_base_elo': {}, 'played_games': [], 'unplayed_games': []}
        with mock.patch('builtins.open', side_effect=OSError("disk full")):
            try:
                cache_mod.save_cache(self.season, payload, self.cfg)
            except OSError:
                self.fail("save_cache raised OSError instead of handling it")


class TestApiFailureHandling(unittest.TestCase):
    def test_connection_error_becomes_data_fetch_error(self) -> None:
        with mock.patch('requests.get', side_effect=requests.exceptions.ConnectionError("no network")):
            with self.assertRaises(DataFetchError):
                get_season_boundaries(2026)

    def test_timeout_becomes_data_fetch_error(self) -> None:
        with mock.patch('requests.get', side_effect=requests.exceptions.Timeout("timed out")):
            with self.assertRaises(DataFetchError):
                fetch_schedule(2026)

    def test_invalid_json_response_becomes_data_fetch_error(self) -> None:
        fake_response = mock.Mock()
        fake_response.raise_for_status = mock.Mock()
        fake_response.json = mock.Mock(side_effect=ValueError("bad json"))
        with mock.patch('requests.get', return_value=fake_response):
            with self.assertRaises(DataFetchError):
                get_season_boundaries(2026)

    def test_missing_expected_fields_becomes_data_fetch_error(self) -> None:
        """API reachable and returns valid JSON, but not the shape we expect."""
        fake_response = mock.Mock()
        fake_response.raise_for_status = mock.Mock()
        fake_response.json = mock.Mock(return_value={'seasons': []})   #empty list -> IndexError
        with mock.patch('requests.get', return_value=fake_response):
            with self.assertRaises(DataFetchError):
                get_season_boundaries(2026)

    def test_http_error_becomes_data_fetch_error(self) -> None:
        fake_response = mock.Mock()
        fake_response.raise_for_status = mock.Mock(
            side_effect=requests.exceptions.HTTPError("500 Server Error")
        )
        with mock.patch('requests.get', return_value=fake_response):
            with self.assertRaises(DataFetchError):
                get_season_boundaries(2026)


class TestMalformedScheduleParsing(unittest.TestCase):
    def test_one_bad_game_entry_does_not_abort_the_whole_parse(self) -> None:
        """A schedule with one malformed game (missing team ids) should skip
        just that game, not raise and lose every other game in the response."""
        schedule = {
            'dates': [{
                'date': '2026-04-01',
                'games': [
                    {'gameType': 'R'},   #missing 'teams' entirely — malformed
                    {
                        'gameType': 'R',
                        'status': {'abstractGameState': 'Final'},
                        'teams': {
                            'home': {'team': {'id': 119}, 'score': 5},   #Dodgers
                            'away': {'team': {'id': 135}, 'score': 2},   #Padres
                        },
                    },
                ],
            }]
        }
        played, unplayed = parse_schedule_into_games(schedule)
        self.assertEqual(len(played), 1)
        self.assertEqual(played[0].winner, 'Los Angeles Dodgers')

    def test_non_dict_schedule_raises_data_fetch_error(self) -> None:
        with self.assertRaises(DataFetchError):
            parse_schedule_into_games(["not", "a", "dict"])


if __name__ == '__main__':
    unittest.main()
