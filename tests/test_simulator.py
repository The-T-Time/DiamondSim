# ==============================================================================
# tests/test_simulator.py
#
# Integration-level tests against a small synthetic schedule (no network
# calls — the MLB API is never hit in tests).
# ==============================================================================

import random
import unittest

from data.teams import ALL_TEAMS
from models.game import Game
from models.simulation_config import SimulationConfig
from simulation.simulator import _replay_with_elo_log, run_simulation_core
from simulation.standings import build_base_records, resolve_league_playoff_teams


def _make_full_schedule(seed: int = 0) -> tuple[list[Game], list[Game]]:
    """A full round-robin among all 30 teams, half played (with a fixed random
    outcome) and half left for the Monte Carlo loop to simulate."""
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


class TestPlayoffProbabilitiesSumCorrectly(unittest.TestCase):
    """Every simulated season produces exactly 12 playoff teams (6 per league:
    3 division winners + 3 wild cards). So across many simulations, the odds
    percentages for all 30 teams must sum to exactly 1200%."""

    @classmethod
    def setUpClass(cls) -> None:
        played, unplayed = _make_full_schedule()
        cfg = SimulationConfig(simulations=300)
        starting_elo = {t: cfg.elo_baseline for t in ALL_TEAMS}
        current_elo, live_standings, elo_log = _replay_with_elo_log(played, starting_elo, cfg)
        data = {
            'live_standings': live_standings,
            'derived_base_elo': current_elo,
            'played_games': played,
            'unplayed_games': unplayed,
            'elo_log': elo_log,
        }
        cls.result = run_simulation_core(data, season=2026, mode='simulate', cfg=cfg)

    def test_odds_sum_to_1200_percent(self) -> None:
        total = sum(self.result.playoff_odds.values())
        self.assertAlmostEqual(total, 1200.0, places=6)

    def test_every_team_has_an_entry_between_0_and_100(self) -> None:
        for team in ALL_TEAMS:
            odds = self.result.playoff_odds[team]
            self.assertGreaterEqual(odds, 0.0)
            self.assertLessEqual(odds, 100.0)

    def test_num_sims_matches_config(self) -> None:
        self.assertEqual(self.result.num_sims, 300)


class TestStrongTeamOutperformsWeakTeam(unittest.TestCase):
    """End-to-end sanity check: a team that enters with a much higher Elo
    should make the playoffs more often than one that enters much lower,
    all else being equal."""

    def test_high_elo_team_beats_low_elo_team_in_odds(self) -> None:
        played, unplayed = _make_full_schedule(seed=1)
        cfg = SimulationConfig(simulations=400)
        strong, weak = ALL_TEAMS[0], ALL_TEAMS[1]
        starting_elo = {t: cfg.elo_baseline for t in ALL_TEAMS}
        starting_elo[strong] = 1750.0
        starting_elo[weak] = 1300.0

        current_elo, live_standings, elo_log = _replay_with_elo_log(played, starting_elo, cfg)
        data = {
            'live_standings': live_standings,
            'derived_base_elo': current_elo,
            'played_games': played,
            'unplayed_games': unplayed,
            'elo_log': elo_log,
        }
        result = run_simulation_core(data, season=2026, mode='simulate', cfg=cfg)
        self.assertGreater(result.playoff_odds[strong], result.playoff_odds[weak])


class TestOnePlayoffSeriesResolution(unittest.TestCase):
    """'One playoff series' at the season level: given final win totals with a
    tie at the top of a division, the tiebreaker must produce exactly one
    division winner and a fully-ordered wild card list."""

    def test_league_playoff_resolution_produces_six_teams(self) -> None:
        played, _ = _make_full_schedule(seed=2)
        base_rec, base_h2h = build_base_records(played, {t: {'W': 0, 'L': 0} for t in ALL_TEAMS})
        #live_standings passed to _build_base_records must reflect W/L; reuse
        #the same replay path used by the real engine.
        starting_elo = {t: 1500.0 for t in ALL_TEAMS}
        cfg = SimulationConfig()
        _, live_standings, _ = _replay_with_elo_log(played, starting_elo, cfg)
        records, h2h = build_base_records(played, live_standings)

        div_winners, wc_teams = resolve_league_playoff_teams(records, h2h, 'AL')
        self.assertEqual(len(div_winners), 3)
        self.assertEqual(len(wc_teams), 3)
        self.assertEqual(len(set(div_winners)), 3)          #no duplicates
        self.assertTrue(set(div_winners).isdisjoint(wc_teams))  #no overlap


class TestSeedReproducibility(unittest.TestCase):
    """Same seed + same inputs must produce byte-identical results — this is
    the whole point of exposing a seed control in the GUI."""

    def _run(self, seed):
        played, unplayed = _make_full_schedule(seed=99)
        cfg = SimulationConfig(simulations=150, random_seed=seed)
        starting_elo = {t: cfg.elo_baseline for t in ALL_TEAMS}
        current_elo, live_standings, elo_log = _replay_with_elo_log(played, starting_elo, cfg)
        data = {
            'live_standings': live_standings, 'derived_base_elo': current_elo,
            'played_games': played, 'unplayed_games': unplayed, 'elo_log': elo_log,
        }
        return run_simulation_core(data, season=2026, mode='simulate', cfg=cfg)

    def test_same_seed_gives_identical_odds(self) -> None:
        result_a = self._run(seed=12345)
        result_b = self._run(seed=12345)
        self.assertEqual(result_a.playoff_odds, result_b.playoff_odds)

    def test_different_seeds_can_give_different_odds(self) -> None:
        result_a = self._run(seed=1)
        result_b = self._run(seed=2)
        #Not a hard guarantee for every possible pair, but with 150 sims
        #over a real schedule the odds essentially never match exactly.
        self.assertNotEqual(result_a.playoff_odds, result_b.playoff_odds)

    def test_none_seed_is_resolved_and_reported_on_result(self) -> None:
        """cfg.random_seed=None means 'pick one for me' — the actual seed
        used must come back on result.cfg so the run can be reproduced."""
        result = self._run(seed=None)
        self.assertIsInstance(result.cfg.random_seed, int)

    def test_explicit_seed_is_preserved_unchanged(self) -> None:
        result = self._run(seed=777)
        self.assertEqual(result.cfg.random_seed, 777)


if __name__ == '__main__':
    unittest.main()
