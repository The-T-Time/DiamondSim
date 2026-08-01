# ==============================================================================
# tests/test_cache_store.py
#
# Covers data/cache_store.py — the 1.0.1 unified, per-data-type disk cache
# (cache/games.json, cache/rosters.json, cache/team_elo.json, etc.) that
# replaced the old one-file-per-team-per-fetch scheme. Exercises the
# generic store I/O, per-entry TTLs, incremental date-based games sync,
# the backtest snapshot re-derivation, season-rollover bookkeeping, and
# the manual full refresh.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import shutil
import time
import unittest
from unittest.mock import patch

import data.cache_store as cache_store
from models.game import Game

_HOME = 'New York Yankees'
_AWAY = 'Tampa Bay Rays'
_HOME_ID = '147'
_AWAY_ID = '139'


def _schedule_payload(date_str: str, game_pk: int, final: bool,
                     home_score: int = 4, away_score: int = 2) -> dict:
    status = {'abstractGameState': 'Final'} if final else {'abstractGameState': 'Preview'}
    return {
        'dates': [{
            'date': date_str,
            'games': [{
                'gamePk': game_pk,
                'gameType': 'R',
                'status': status,
                'teams': {
                    'home': {'team': {'id': int(_HOME_ID)}, 'score': home_score},
                    'away': {'team': {'id': int(_AWAY_ID)}, 'score': away_score},
                },
            }],
        }],
    }


class CacheStoreTestCase(unittest.TestCase):
    """Base class: points CACHE_DIR at a throwaway directory for every
    test so nothing here can collide with (or depend on) a real cache."""

    def setUp(self) -> None:
        enabled_patcher = patch('data.cache.CACHE_ENABLED', True)
        enabled_patcher.start()
        self.addCleanup(enabled_patcher.stop)

        self._tmp_dir = cache_store.CACHE_DIR.parent / '_test_cache_store_scratch'
        if self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir)
        dir_patcher = patch.object(cache_store, 'CACHE_DIR', self._tmp_dir)
        dir_patcher.start()
        self.addCleanup(dir_patcher.stop)
        self.addCleanup(self._cleanup_dir)

    def _cleanup_dir(self) -> None:
        if self._tmp_dir.exists():
            shutil.rmtree(self._tmp_dir)


class TestGenericStoreIO(CacheStoreTestCase):
    def test_write_then_read_round_trip(self) -> None:
        cache_store.write_store('games', {'2026': {'games': {'1': {'a': 1}}}})
        self.assertEqual(cache_store.read_store('games'), {'2026': {'games': {'1': {'a': 1}}}})

    def test_missing_store_reads_as_empty_dict(self) -> None:
        self.assertEqual(cache_store.read_store('rosters'), {})

    def test_corrupted_store_is_reset_and_read_as_empty(self) -> None:
        path = cache_store.store_path('rosters')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{not valid json::')
        self.assertEqual(cache_store.read_store('rosters'), {})
        self.assertFalse(path.exists())

    def test_disabled_cache_never_reads_or_writes(self) -> None:
        with patch('data.cache.CACHE_ENABLED', False):
            cache_store.write_store('rosters', {'a': 1})
            self.assertEqual(cache_store.read_store('rosters'), {})
        self.assertFalse(cache_store.store_path('rosters').exists())

    def test_unknown_store_name_raises(self) -> None:
        with self.assertRaises(KeyError):
            cache_store.store_path('not_a_real_store')


class TestEntryTTL(CacheStoreTestCase):
    def test_fresh_entry_is_a_hit(self) -> None:
        cache_store.set_entry('rosters', '147:2026', {'roster': []})
        self.assertEqual(cache_store.get_entry('rosters', '147:2026', 3600), {'roster': []})

    def test_missing_entry_is_a_miss(self) -> None:
        self.assertIsNone(cache_store.get_entry('rosters', 'nope', 3600))

    def test_expired_entry_is_a_miss(self) -> None:
        cache_store.set_entry('rosters', '147:2026', {'roster': []})
        entries = cache_store.read_store('rosters')
        entries['147:2026']['fetched_at'] = time.time() - 10_000
        cache_store.write_store('rosters', entries)
        self.assertIsNone(cache_store.get_entry('rosters', '147:2026', 60))

    def test_set_entries_bulk_writes_all_keys(self) -> None:
        cache_store.set_entries('pitching_stats', {'147:2026': {'x': 1}, '139:2026': {'x': 2}})
        self.assertEqual(cache_store.get_entry('pitching_stats', '147:2026', 3600), {'x': 1})
        self.assertEqual(cache_store.get_entry('pitching_stats', '139:2026', 3600), {'x': 2})

    def test_entries_for_different_teams_dont_collide(self) -> None:
        cache_store.set_entry('batting_stats', '147:2026:2026-07-01', {'v': 'a'})
        cache_store.set_entry('batting_stats', '139:2026:2026-07-01', {'v': 'b'})
        self.assertEqual(cache_store.get_entry('batting_stats', '147:2026:2026-07-01', 3600)['v'], 'a')
        self.assertEqual(cache_store.get_entry('batting_stats', '139:2026:2026-07-01', 3600)['v'], 'b')


class TestMetadataAndSeasonRollover(CacheStoreTestCase):
    def test_first_sync_of_a_season_is_new(self) -> None:
        self.assertTrue(cache_store.note_season_synced(2026))

    def test_resyncing_the_same_season_is_not_new(self) -> None:
        cache_store.note_season_synced(2026)
        self.assertFalse(cache_store.note_season_synced(2026))

    def test_a_later_season_is_detected_as_new(self) -> None:
        cache_store.note_season_synced(2026)
        self.assertTrue(cache_store.note_season_synced(2027))

    def test_metadata_tracks_current_season(self) -> None:
        cache_store.note_season_synced(2026)
        self.assertEqual(cache_store.load_metadata()['current_season'], 2026)


class TestRefreshAllData(CacheStoreTestCase):
    def test_refresh_clears_every_store(self) -> None:
        cache_store.set_entry('rosters', '147:2026', {'roster': []})
        cache_store.write_store('games', {'2026': {'games': {'1': {}}}})
        cache_store.note_season_synced(2026)

        cache_store.refresh_all_data()

        self.assertEqual(cache_store.read_store('rosters'), {})
        self.assertEqual(cache_store.read_store('games'), {})
        self.assertEqual(cache_store.load_metadata()['seasons_synced'], [])

    def test_refresh_is_safe_when_nothing_was_ever_cached(self) -> None:
        cache_store.refresh_all_data()   #should not raise
        self.assertEqual(cache_store.read_store('games'), {})


class TestSyncSeasonGames(CacheStoreTestCase):
    def setUp(self) -> None:
        super().setUp()
        boundaries_patcher = patch.object(
            cache_store, 'get_season_boundaries', return_value=('2026-03-26', '2026-09-27')
        )
        boundaries_patcher.start()
        self.addCleanup(boundaries_patcher.stop)

    def test_first_sync_fetches_the_whole_season(self) -> None:
        with patch.object(cache_store, 'fetch_schedule_range') as mock_fetch, \
             patch('data.api.parse_schedule_into_games') as mock_parse:
            mock_fetch.return_value = {}
            mock_parse.return_value = (
                [Game(game_pk=1, date='2026-04-01', home=_HOME, away=_AWAY,
                      home_score=4, away_score=2, winner=_HOME)],
                [Game(game_pk=2, date='2026-04-02', home=_AWAY, away=_HOME)],
            )
            with patch('data.cache_store.date') as mock_date:
                mock_date.today.return_value.isoformat.return_value = '2026-04-02'
                played, unplayed = cache_store.sync_season_games(2026)

            #first call has to span the whole season (no prior watermark)
            self.assertEqual(mock_fetch.call_args[0][0], '2026-03-26')
            self.assertEqual(len(played), 1)
            self.assertEqual(len(unplayed), 1)

    def test_second_sync_same_day_makes_no_api_call(self) -> None:
        with patch.object(cache_store, 'fetch_schedule_range') as mock_fetch, \
             patch('data.api.parse_schedule_into_games') as mock_parse:
            mock_fetch.return_value = {}
            mock_parse.return_value = (
                [Game(game_pk=1, date='2026-04-01', home=_HOME, away=_AWAY,
                      home_score=4, away_score=2, winner=_HOME)],
                [],
            )
            with patch('data.cache_store.date') as mock_date:
                mock_date.today.return_value.isoformat.return_value = '2026-04-01'
                cache_store.sync_season_games(2026)
                mock_fetch.reset_mock()
                played, unplayed = cache_store.sync_season_games(2026)

            mock_fetch.assert_not_called()
            self.assertEqual(len(played), 1)

    def test_new_day_only_fetches_the_missing_window(self) -> None:
        with patch.object(cache_store, 'fetch_schedule_range') as mock_fetch, \
             patch('data.api.parse_schedule_into_games') as mock_parse:
            mock_fetch.return_value = {}
            mock_parse.return_value = (
                [Game(game_pk=1, date='2026-04-01', home=_HOME, away=_AWAY,
                      home_score=4, away_score=2, winner=_HOME)],
                [],
            )
            with patch('data.cache_store.date') as mock_date:
                mock_date.today.return_value.isoformat.return_value = '2026-04-01'
                cache_store.sync_season_games(2026)

            mock_parse.return_value = (
                [Game(game_pk=2, date='2026-04-02', home=_HOME, away=_AWAY,
                      home_score=3, away_score=1, winner=_HOME)],
                [],
            )
            with patch('data.cache_store.date') as mock_date:
                mock_date.today.return_value.isoformat.return_value = '2026-04-02'
                played, unplayed = cache_store.sync_season_games(2026)

            #second call should start from the prior watermark, not the season start —
            #and must still run through the season's real end date, not just today
            #(see test_unplayed_games_are_never_truncated_to_today below for why)
            self.assertEqual(mock_fetch.call_args[0][0], '2026-04-01')
            self.assertEqual(mock_fetch.call_args[0][1], '2026-09-27')
            #both the previously-cached and newly-fetched games should be present
            self.assertEqual({g.game_pk for g in played}, {1, 2})

    def test_fetch_window_always_reaches_season_end_not_just_today(self) -> None:
        """
        Regression test: the fetch window used to be clamped to
        min(end_date, today), which meant every future/not-yet-played
        game — the vast majority of a mid-season sync — was silently
        never fetched at all. sync_season_games must always ask through
        the season's real end date so the unplayed portion of the
        schedule actually comes back, no matter how early in the season
        'today' is.
        """
        with patch.object(cache_store, 'fetch_schedule_range') as mock_fetch, \
             patch('data.api.parse_schedule_into_games') as mock_parse:
            mock_fetch.return_value = {}
            mock_parse.return_value = (
                [Game(game_pk=1, date='2026-04-01', home=_HOME, away=_AWAY,
                      home_score=4, away_score=2, winner=_HOME)],
                #a game scheduled deep in the future — this must come back as unplayed
                [Game(game_pk=2, date='2026-09-15', home=_AWAY, away=_HOME)],
            )
            #"today" is early in the season — the old bug clamped the fetch
            #window to this date, so the September game would never be requested
            with patch('data.cache_store.date') as mock_date:
                mock_date.today.return_value.isoformat.return_value = '2026-04-02'
                played, unplayed = cache_store.sync_season_games(2026)

            #the fetch must reach all the way to the season's end date, not today
            self.assertEqual(mock_fetch.call_args[0][1], '2026-09-27')
            self.assertEqual(len(played), 1)
            self.assertEqual(len(unplayed), 1)
            self.assertEqual(unplayed[0].date, '2026-09-15')

    def test_disabled_cache_always_fetches_fresh_and_skips_persistence(self) -> None:
        with patch('data.cache.CACHE_ENABLED', False), \
             patch.object(cache_store, 'fetch_schedule_range') as mock_fetch, \
             patch('data.api.parse_schedule_into_games') as mock_parse:
            mock_fetch.return_value = {}
            mock_parse.return_value = ([], [])
            cache_store.sync_season_games(2026)
            cache_store.sync_season_games(2026)
        self.assertEqual(mock_fetch.call_count, 2)


class TestBacktestSplit(CacheStoreTestCase):
    def test_games_after_snapshot_date_are_unplayed(self) -> None:
        games = [Game(game_pk=1, date='2026-08-01', home=_HOME, away=_AWAY,
                     home_score=5, away_score=1, winner=_HOME)]
        played, unplayed = cache_store.split_games_for_backtest(games, '2026-07-01')
        self.assertEqual(played, [])
        self.assertEqual(len(unplayed), 1)
        #the snapshot view must not leak the real result
        self.assertIsNone(unplayed[0].winner)

    def test_games_on_or_before_snapshot_date_with_a_winner_are_played(self) -> None:
        games = [Game(game_pk=1, date='2026-06-01', home=_HOME, away=_AWAY,
                     home_score=5, away_score=1, winner=_HOME)]
        played, unplayed = cache_store.split_games_for_backtest(games, '2026-07-01')
        self.assertEqual(len(played), 1)
        self.assertEqual(unplayed, [])

    def test_games_with_no_winner_are_unplayed_even_before_snapshot_date(self) -> None:
        games = [Game(game_pk=1, date='2026-06-01', home=_HOME, away=_AWAY)]
        played, unplayed = cache_store.split_games_for_backtest(games, '2026-07-01')
        self.assertEqual(played, [])
        self.assertEqual(len(unplayed), 1)


class TestConcurrentWrites(CacheStoreTestCase):
    """
    Regression test for the corruption/WinError-32 bug reported after
    1.0.1 shipped: several threads (one per team, mirroring
    simulation/pitching.py and simulation/offense_calculator.py's
    ThreadPoolExecutors) writing to the SAME shared store at once used to
    tear each other's writes. This drives real threads at a real store
    file and asserts every write survives intact.
    """

    def test_many_threads_writing_different_keys_never_corrupt_the_file(self) -> None:
        import concurrent.futures

        team_ids = [str(147 + i) for i in range(30)]

        def _write_one(team_id: str) -> None:
            for _ in range(20):   #repeat writes to also stress the same key repeatedly
                cache_store.set_entry(
                    'pitching_stats', f"{team_id}:2026:2026-07-30",
                    {'roster': [team_id] * 50, 'career': {'k': team_id}},
                )

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            futures = [pool.submit(_write_one, tid) for tid in team_ids]
            for f in futures:
                f.result()   #re-raises if any thread hit an exception

        #the store must still be valid, complete JSON with every team's entry intact
        final = cache_store.read_store('pitching_stats')
        self.assertEqual(len(final), len(team_ids))
        for team_id in team_ids:
            key = f"{team_id}:2026:2026-07-30"
            self.assertIn(key, final)
            self.assertEqual(final[key]['value']['roster'], [team_id] * 50)

        #no leftover .tmp files from a failed/aborted write
        leftover_tmp = list(self._tmp_dir.glob('*.tmp'))
        self.assertEqual(leftover_tmp, [])


class TestPriorClosingElo(CacheStoreTestCase):
    def test_miss_then_hit(self) -> None:
        self.assertIsNone(cache_store.get_prior_closing_elo(2025, None))
        cache_store.save_prior_closing_elo(2025, None, {_HOME: 1550.0, _AWAY: 1480.0})
        cached = cache_store.get_prior_closing_elo(2025, None)
        self.assertEqual(cached[_HOME], 1550.0)

    def test_different_seasons_dont_collide(self) -> None:
        cache_store.save_prior_closing_elo(2024, None, {_HOME: 1500.0})
        cache_store.save_prior_closing_elo(2025, None, {_HOME: 1600.0})
        self.assertEqual(cache_store.get_prior_closing_elo(2024, None)[_HOME], 1500.0)
        self.assertEqual(cache_store.get_prior_closing_elo(2025, None)[_HOME], 1600.0)


if __name__ == '__main__':
    unittest.main()
