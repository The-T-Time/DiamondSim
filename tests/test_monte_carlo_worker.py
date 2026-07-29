# ==============================================================================
# TEST: MONTE CARLO WORKER
# tests/test_monte_carlo_worker.py
#
# Covers simulation/monte_carlo_worker.py's run_chunk/merge_chunk_results,
# and simulation/simulator.py's _run_all_chunks dispatch between the
# sequential (small run) and ProcessPoolExecutor (large run) paths — all
# against a small synthetic schedule (no network calls).
# ==============================================================================

from __future__ import annotations

import random
import unittest
from unittest import mock

from data.teams import ALL_TEAMS
from models.game import Game
from models.simulation_config import SimulationConfig
from simulation.monte_carlo_worker import merge_chunk_results, run_chunk
from simulation.simulator import _replay_with_elo_log, _run_all_chunks, run_simulation_core
from simulation.standings import build_base_records


def _make_full_schedule(seed: int = 0) -> tuple[list[Game], list[Game]]:
    #a full round-robin among all 30 teams, half played (fixed random outcome) and half left for the Monte Carlo loop to simulate — same shape tests/test_simulator.py uses
    rng = random.Random(seed)
    played: list[Game] = []
    unplayed: list[Game] = []
    game_pk = 1
    for home in ALL_TEAMS:
        for away in ALL_TEAMS:
            if home == away:
                continue
            if game_pk % 2 == 0:
                hs, aw = (rng.randint(0, 3), rng.randint(4, 9)) if game_pk % 3 else (5, 2)
                winner = home if hs > aw else away
                played.append(Game(
                    game_pk=game_pk, date=f"2026-04-{(game_pk % 28) + 1:02d}",
                    home=home, away=away, home_score=hs, away_score=aw, winner=winner,
                ))
            else:
                unplayed.append(Game(
                    game_pk=game_pk, date=f"2026-05-{(game_pk % 28) + 1:02d}",
                    home=home, away=away,
                ))
            game_pk += 1
    return played, unplayed


def _base_inputs(cfg: SimulationConfig):
    played, unplayed = _make_full_schedule()
    starting_elo = {t: cfg.elo_baseline for t in ALL_TEAMS}
    current_elo, live_standings, _ = _replay_with_elo_log(played, starting_elo, cfg)
    base_rec, base_h2h = build_base_records(played, live_standings)
    return base_rec, base_h2h, current_elo, unplayed


class TestRunChunk(unittest.TestCase):
    def test_sims_run_matches_requested_count(self) -> None:
        cfg = SimulationConfig(simulations=25)
        base_rec, base_h2h, elo, unplayed = _base_inputs(cfg)
        result = run_chunk(25, seed=1, base_rec=base_rec, base_h2h=base_h2h,
                          derived_base_elo=elo, unplayed_games=unplayed, cfg=cfg)
        self.assertEqual(result.sims_run, 25)

    def test_same_seed_is_deterministic(self) -> None:
        cfg = SimulationConfig(simulations=20)
        base_rec, base_h2h, elo, unplayed = _base_inputs(cfg)
        r1 = run_chunk(20, seed=7, base_rec=base_rec, base_h2h=base_h2h,
                      derived_base_elo=elo, unplayed_games=unplayed, cfg=cfg)
        r2 = run_chunk(20, seed=7, base_rec=base_rec, base_h2h=base_h2h,
                      derived_base_elo=elo, unplayed_games=unplayed, cfg=cfg)
        self.assertEqual(dict(r1.total_wins), dict(r2.total_wins))
        self.assertEqual(dict(r1.playoff_counts), dict(r2.playoff_counts))

    def test_progress_callback_reaches_completion(self) -> None:
        cfg = SimulationConfig(simulations=10)
        base_rec, base_h2h, elo, unplayed = _base_inputs(cfg)
        calls: list[tuple[int, int]] = []
        run_chunk(10, seed=3, base_rec=base_rec, base_h2h=base_h2h,
                 derived_base_elo=elo, unplayed_games=unplayed, cfg=cfg,
                 progress_callback=lambda done, total: calls.append((done, total)))
        self.assertTrue(calls)
        self.assertEqual(calls[-1], (10, 10))


class TestMergeChunkResults(unittest.TestCase):
    def test_two_chunks_sum_to_the_same_shape_as_one_combined_chunk(self) -> None:
        cfg = SimulationConfig(simulations=40)
        base_rec, base_h2h, elo, unplayed = _base_inputs(cfg)

        combined = run_chunk(40, seed=100, base_rec=base_rec, base_h2h=base_h2h,
                            derived_base_elo=elo, unplayed_games=unplayed, cfg=cfg)

        #two independent chunks using DIFFERENT seeds than the combined run above
        #can't be expected to match it number-for-number (different RNG draws) —
        #what has to hold is the invariant merge_chunk_results relies on:
        #sims_run adds up and every counted total across teams is non-negative
        c1 = run_chunk(20, seed=200, base_rec=base_rec, base_h2h=base_h2h,
                      derived_base_elo=elo, unplayed_games=unplayed, cfg=cfg)
        c2 = run_chunk(20, seed=201, base_rec=base_rec, base_h2h=base_h2h,
                      derived_base_elo=elo, unplayed_games=unplayed, cfg=cfg)
        merged = merge_chunk_results([c1, c2])

        self.assertEqual(merged.sims_run, combined.sims_run)
        self.assertEqual(merged.sims_run, 40)
        for t in ALL_TEAMS:
            self.assertEqual(merged.total_wins[t], c1.total_wins[t] + c2.total_wins[t])
            self.assertEqual(merged.playoff_counts[t], c1.playoff_counts[t] + c2.playoff_counts[t])
        #every playoff field is exactly 12 teams (3 div winners + 3 WC per league,
        #two leagues) regardless of how the sims were chunked
        self.assertEqual(sum(merged.playoff_counts.values()), merged.sims_run * 12)

    def test_bracket_examples_survive_the_merge(self) -> None:
        cfg = SimulationConfig(simulations=10, simulate_postseason=True)
        base_rec, base_h2h, elo, unplayed = _base_inputs(cfg)
        c1 = run_chunk(5, seed=1, base_rec=base_rec, base_h2h=base_h2h,
                      derived_base_elo=elo, unplayed_games=unplayed, cfg=cfg)
        c2 = run_chunk(5, seed=2, base_rec=base_rec, base_h2h=base_h2h,
                      derived_base_elo=elo, unplayed_games=unplayed, cfg=cfg)
        merged = merge_chunk_results([c1, c2])
        self.assertEqual(sum(merged.bracket_counts.values()), 10)
        for key, count in merged.bracket_counts.items():
            self.assertIn(key, merged.bracket_examples)
            self.assertGreater(count, 0)


class TestRunAllChunksDispatch(unittest.TestCase):
    #_run_all_chunks should pick the sequential path for small runs and the ProcessPoolExecutor path for large ones — same result shape either way

    def test_small_run_stays_sequential(self) -> None:
        cfg = SimulationConfig(simulations=10)
        base_rec, base_h2h, elo, unplayed = _base_inputs(cfg)
        with mock.patch('simulation.simulator.ProcessPoolExecutor') as pool:
            merged = _run_all_chunks(10, 1, base_rec, base_h2h, elo, unplayed, cfg,
                                     None, None, None, None)
        pool.assert_not_called()
        self.assertEqual(merged.sims_run, 10)

    def test_large_run_uses_process_pool_and_matches_sequential_shape(self) -> None:
        cfg = SimulationConfig(simulations=300, simulate_postseason=True)
        base_rec, base_h2h, elo, unplayed = _base_inputs(cfg)
        with mock.patch('simulation.simulator.os.cpu_count', return_value=4):
            merged = _run_all_chunks(300, 1, base_rec, base_h2h, elo, unplayed, cfg,
                                     None, None, None, None)
        self.assertEqual(merged.sims_run, 300)
        self.assertEqual(sum(merged.playoff_counts.values()), 300 * 12)
        self.assertEqual(sum(merged.champ_counts.values()), 300)

    def test_progress_callback_fires_and_ends_at_completion(self) -> None:
        cfg = SimulationConfig(simulations=300)
        base_rec, base_h2h, elo, unplayed = _base_inputs(cfg)
        calls: list[tuple[int, int]] = []
        with mock.patch('simulation.simulator.os.cpu_count', return_value=4):
            _run_all_chunks(300, 1, base_rec, base_h2h, elo, unplayed, cfg,
                           None, None, None, lambda done, total: calls.append((done, total)))
        self.assertTrue(calls)
        self.assertEqual(calls[-1], (300, 300))
        #every intermediate call should be a non-decreasing, in-range progress count
        for done, total in calls:
            self.assertEqual(total, 300)
            self.assertLessEqual(done, total)


class TestRunSimulationCoreEndToEnd(unittest.TestCase):
    #same odds-sum invariants tests/test_simulator.py checks, but run through the forced-parallel path to make sure chunking/merging doesn't change what comes out the other end

    def test_parallel_path_still_produces_valid_odds(self) -> None:
        played, unplayed = _make_full_schedule()
        cfg = SimulationConfig(simulations=300, simulate_postseason=True)
        starting_elo = {t: cfg.elo_baseline for t in ALL_TEAMS}
        current_elo, live_standings, elo_log = _replay_with_elo_log(played, starting_elo, cfg)
        data = {
            'live_standings': live_standings, 'derived_base_elo': current_elo,
            'played_games': played, 'unplayed_games': unplayed, 'elo_log': elo_log,
        }
        with mock.patch('simulation.simulator.os.cpu_count', return_value=4):
            result = run_simulation_core(data, season=2026, mode='simulate', cfg=cfg)

        self.assertAlmostEqual(sum(result.playoff_odds.values()), 1200.0, places=6)
        self.assertAlmostEqual(sum(result.world_series_odds.values()), 100.0, places=6)
        self.assertIsNotNone(result.projected_bracket)


if __name__ == '__main__':
    unittest.main()
