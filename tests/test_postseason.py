# ==============================================================================
# tests/test_postseason.py
#
# World Series odds (postseason bracket) and progress-callback behaviour of
# run_simulation_core, against a small synthetic schedule (no network).
# ==============================================================================

import random
import unittest

from data.teams import ALL_TEAMS
from models.game import Game
from models.simulation_config import SimulationConfig
from simulation.simulator import _replay_with_elo_log, run_simulation_core


def _make_full_schedule(seed: int = 0) -> tuple[list[Game], list[Game]]:
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


def _run(cfg: SimulationConfig, seed_sched: int = 0, **core_kw):
    played, unplayed = _make_full_schedule(seed=seed_sched)
    starting_elo = {t: cfg.elo_baseline for t in ALL_TEAMS}
    current_elo, live_standings, elo_log = _replay_with_elo_log(played, starting_elo, cfg)
    data = {
        'live_standings': live_standings,
        'derived_base_elo': current_elo,
        'played_games': played,
        'unplayed_games': unplayed,
        'elo_log': elo_log,
    }
    return run_simulation_core(data, season=2026, mode='simulate', cfg=cfg, **core_kw)


class TestWorldSeriesOdds(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cfg = SimulationConfig(simulations=400, random_seed=42, simulate_postseason=True)
        cls.result = _run(cfg)

    def test_ws_odds_present_for_all_30_teams(self) -> None:
        self.assertEqual(set(self.result.world_series_odds), set(ALL_TEAMS))

    def test_ws_odds_sum_to_100_percent(self) -> None:
        total = sum(self.result.world_series_odds.values())
        self.assertAlmostEqual(total, 100.0, places=6)

    def test_ws_odds_never_exceed_playoff_odds(self) -> None:
        #A team can't win the WS more often than it makes the playoffs.
        for t in ALL_TEAMS:
            self.assertLessEqual(self.result.world_series_odds[t],
                                 self.result.playoff_odds[t] + 1e-9)

    def test_playoff_odds_still_sum_to_1200(self) -> None:
        self.assertAlmostEqual(sum(self.result.playoff_odds.values()), 1200.0, places=6)


class TestPostseasonGate(unittest.TestCase):
    def test_disabled_yields_empty_ws_odds(self) -> None:
        cfg = SimulationConfig(simulations=100, random_seed=1, simulate_postseason=False)
        result = _run(cfg)
        self.assertEqual(result.world_series_odds, {})
        #Playoff odds are unaffected by the postseason gate.
        self.assertAlmostEqual(sum(result.playoff_odds.values()), 1200.0, places=6)


class TestProgressCallback(unittest.TestCase):
    def test_callback_reports_monotonic_progress_ending_at_total(self) -> None:
        cfg = SimulationConfig(simulations=250, random_seed=5)
        seen: list[tuple[int, int]] = []
        _run(cfg, progress_callback=lambda done, total: seen.append((done, total)))

        self.assertTrue(seen, 'progress_callback was never called')
        self.assertTrue(all(total == 250 for _done, total in seen))
        dones = [d for d, _ in seen]
        self.assertEqual(dones, sorted(dones))          #monotonic non-decreasing
        self.assertEqual(seen[-1], (250, 250))          #final call hits 100%
        self.assertLessEqual(max(dones), 250)

    def test_no_callback_is_fine(self) -> None:
        cfg = SimulationConfig(simulations=100, random_seed=6)
        result = _run(cfg)   #progress_callback omitted
        self.assertEqual(result.num_sims, 100)


if __name__ == '__main__':
    unittest.main()
