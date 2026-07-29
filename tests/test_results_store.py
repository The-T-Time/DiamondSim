# ==============================================================================
# tests/test_results_store.py
#
# Save/load round-trip for SimulationResult persistence. Uses a temporary
# SAVE_DIR so it never touches the real saved_results/ folder.
# ==============================================================================

import tempfile
import unittest
from pathlib import Path

import data.results_store as store
from data.results_store import (
    save_result, load_result, list_saved_results, SavedResultError,
)
from data.teams import ALL_TEAMS
from models.elo_snapshot import EloSnapshot
from models.game import Game
from models.playoff_bracket import PlayoffBracketResult
from models.simulation_config import SimulationConfig
from models.simulation_result import SimulationResult


def _sample_result() -> SimulationResult:
    played = [
        Game(game_pk=1, date='2026-04-01', home=ALL_TEAMS[0], away=ALL_TEAMS[1],
             home_score=5, away_score=2, winner=ALL_TEAMS[0]),
        Game(game_pk=2, date='2026-04-02', home=ALL_TEAMS[2], away=ALL_TEAMS[3],
             home_score=1, away_score=4, winner=ALL_TEAMS[3]),
    ]
    unplayed = [Game(game_pk=3, date='2026-05-01', home=ALL_TEAMS[0], away=ALL_TEAMS[2])]
    cfg = SimulationConfig(simulations=123, random_seed=99)
    bracket = PlayoffBracketResult(
        al_seeds=tuple(ALL_TEAMS[0:6]), nl_seeds=tuple(ALL_TEAMS[6:12]),
        al_wc_winners=(ALL_TEAMS[2], ALL_TEAMS[3]), nl_wc_winners=(ALL_TEAMS[8], ALL_TEAMS[9]),
        al_ds_winners=(ALL_TEAMS[0], ALL_TEAMS[2]), nl_ds_winners=(ALL_TEAMS[6], ALL_TEAMS[8]),
        al_champion=ALL_TEAMS[0], nl_champion=ALL_TEAMS[6],
        ws_host=ALL_TEAMS[0], ws_guest=ALL_TEAMS[6], champion=ALL_TEAMS[0],
    )
    return SimulationResult(
        mode='simulate', season=2026, cfg=cfg,
        playoff_odds={t: 10.0 for t in ALL_TEAMS},
        world_series_odds={t: 100.0 / len(ALL_TEAMS) for t in ALL_TEAMS},
        live_elo={t: 1500.0 for t in ALL_TEAMS},
        elo_log={1: EloSnapshot(elo_before_home=1500.0, elo_before_away=1500.0, elo_delta=7.5)},
        live_standings={t: {'W': 1, 'L': 0} for t in ALL_TEAMS},
        played_games=played, unplayed_games=unplayed,
        projected_team_stats={t: {'wins': 88.5, 'losses': 73.5, 'runs_scored': 750.2,
                                   'runs_allowed': 700.1, 'era': 4.15} for t in ALL_TEAMS},
        projected_bracket=bracket,
        projected_bracket_pct=27.3,
    )


class TestResultsStore(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._orig_dir = store.SAVE_DIR
        store.SAVE_DIR = Path(self._tmp.name)

    def tearDown(self) -> None:
        store.SAVE_DIR = self._orig_dir
        self._tmp.cleanup()

    def test_round_trip_preserves_core_fields(self) -> None:
        original = _sample_result()
        path = save_result(original, 'My Test Run')
        loaded = load_result(path)

        self.assertEqual(loaded.mode, original.mode)
        self.assertEqual(loaded.season, original.season)
        self.assertEqual(loaded.cfg.simulations, 123)
        self.assertEqual(loaded.cfg.random_seed, 99)
        self.assertEqual(loaded.playoff_odds, original.playoff_odds)
        self.assertEqual(set(loaded.world_series_odds), set(original.world_series_odds))
        self.assertEqual(len(loaded.played_games), 2)
        self.assertEqual(len(loaded.unplayed_games), 1)
        self.assertEqual(loaded.played_games[0].winner, ALL_TEAMS[0])

    def test_elo_log_rehydrates_to_elo_snapshot(self) -> None:
        path = save_result(_sample_result(), 'elo run')
        loaded = load_result(path)
        snap = loaded.elo_log[1]
        self.assertIsInstance(snap, EloSnapshot)
        self.assertAlmostEqual(snap.elo_delta, 7.5)

    def test_round_trip_preserves_projected_stats_and_bracket(self) -> None:
        original = _sample_result()
        path = save_result(original, 'projected stats run')
        loaded = load_result(path)

        self.assertEqual(loaded.projected_team_stats, original.projected_team_stats)
        self.assertAlmostEqual(loaded.projected_bracket_pct, 27.3)
        self.assertEqual(loaded.projected_bracket, original.projected_bracket)
        self.assertIsInstance(loaded.projected_bracket.al_seeds, tuple)
        self.assertEqual(loaded.projected_bracket.champion, ALL_TEAMS[0])

    def test_saved_result_missing_projected_fields_loads_with_defaults(self) -> None:
        """An older saved file won't have these keys at all —
        loading it should default to 'no projection available', not fail."""
        path = save_result(_sample_result(), 'legacy-shaped run')
        with open(path) as f:
            doc = store.json.load(f)
        del doc['result']['projected_team_stats']
        del doc['result']['projected_bracket']
        del doc['result']['projected_bracket_pct']
        with open(path, 'w') as f:
            store.json.dump(doc, f)

        loaded = load_result(path)
        self.assertEqual(loaded.projected_team_stats, {})
        self.assertIsNone(loaded.projected_bracket)
        self.assertEqual(loaded.projected_bracket_pct, 0.0)

    def test_filenames_are_unique_no_overwrite(self) -> None:
        r = _sample_result()
        p1 = save_result(r, 'same name')
        p2 = save_result(r, 'same name')
        self.assertNotEqual(p1, p2)
        self.assertTrue(p1.exists() and p2.exists())

    def test_listing_reports_saved_runs_newest_first(self) -> None:
        save_result(_sample_result(), 'run one')
        save_result(_sample_result(), 'run two')
        listing = list_saved_results()
        names = [row[0] for row in listing]
        self.assertIn('run one', names)
        self.assertIn('run two', names)
        for _name, path, _saved_at, season, mode in listing:
            self.assertTrue(Path(path).exists())
            self.assertEqual(season, 2026)
            self.assertEqual(mode, 'simulate')

    def test_missing_file_raises_saved_result_error(self) -> None:
        with self.assertRaises(SavedResultError):
            load_result(Path(self._tmp.name) / 'does_not_exist.json')

    def test_wrong_schema_version_raises(self) -> None:
        path = Path(self._tmp.name) / 'bad.json'
        path.write_text('{"schema_version": 999, "result": {}}')
        with self.assertRaises(SavedResultError):
            load_result(path)

    def test_corrupt_json_raises(self) -> None:
        path = Path(self._tmp.name) / 'corrupt.json'
        path.write_text('{not valid json')
        with self.assertRaises(SavedResultError):
            load_result(path)


if __name__ == '__main__':
    unittest.main()
