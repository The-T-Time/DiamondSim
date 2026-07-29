# ==============================================================================
# tests/test_generic_cache.py
#
# Covers data/cache.py's generic keyed JSON cache (load_json_cache /
# save_json_cache) — the shared implementation data/player_stats.py,
# data/hitting_stats.py, and data/roster.py all use instead of three
# separate copies of the same read/write/expiry/corruption-handling logic.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import time
import unittest
from unittest.mock import patch

from data.cache import generic_cache_path, load_json_cache, save_json_cache

_TEST_KEY = 'test_generic_cache_entry_do_not_collide'


class TestGenericJsonCache(unittest.TestCase):
    def setUp(self) -> None:
        patcher = patch('data.cache.CACHE_ENABLED', True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._cleanup_file)

    def _cleanup_file(self) -> None:
        path = generic_cache_path(_TEST_KEY)
        if path.exists():
            path.unlink()

    def test_round_trip(self) -> None:
        save_json_cache(_TEST_KEY, {'hello': 'world', 'n': 3})
        result = load_json_cache(_TEST_KEY, expiry_seconds=3600)
        self.assertEqual(result, {'hello': 'world', 'n': 3})

    def test_missing_key_is_a_miss(self) -> None:
        self.assertIsNone(load_json_cache('this_key_was_never_saved_xyz', expiry_seconds=3600))

    def test_expired_entry_is_a_miss(self) -> None:
        save_json_cache(_TEST_KEY, {'a': 1})
        path = generic_cache_path(_TEST_KEY)
        old_time = time.time() - 10_000
        import os
        os.utime(path, (old_time, old_time))
        self.assertIsNone(load_json_cache(_TEST_KEY, expiry_seconds=60))

    def test_corrupted_entry_is_a_miss_and_is_removed(self) -> None:
        path = generic_cache_path(_TEST_KEY)
        path.write_text('{not valid json::')
        self.assertIsNone(load_json_cache(_TEST_KEY, expiry_seconds=3600))
        self.assertFalse(path.exists())

    def test_disabled_cache_never_reads_or_writes(self) -> None:
        with patch('data.cache.CACHE_ENABLED', False):
            save_json_cache(_TEST_KEY, {'a': 1})
            self.assertIsNone(load_json_cache(_TEST_KEY, expiry_seconds=3600))
        self.assertFalse(generic_cache_path(_TEST_KEY).exists())


if __name__ == '__main__':
    unittest.main()
