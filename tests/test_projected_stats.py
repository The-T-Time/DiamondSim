# ==============================================================================
# tests/test_projected_stats.py
#
# Projected (averaged-across-all-sims) team stats and the
# most-common playoff bracket. Reuses the synthetic round-robin schedule
# from test_simulator.py's fixture pattern.
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


class TestProjectedStatsAndBracket(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        played, unplayed = _make_full_schedule()
        cfg = SimulationConfig(simulations=300, simulate_postseason=True)
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
        cls.played, cls.unplayed = played, unplayed

    def test_every_team_has_projected_stats(self) -> None:
        for t in ALL_TEAMS:
            self.assertIn(t, self.result.projected_team_stats)
            stats = self.result.projected_team_stats[t]
            for key in ('wins', 'losses', 'runs_scored', 'runs_allowed', 'era'):
                self.assertIn(key, stats)

    def test_projected_games_played_matches_full_schedule(self) -> None:
        """Every team's projected wins+losses should equal the number of
        games it's scheduled for (played + unplayed) — averaging shouldn't
        change the total games played, only the split between played real
        games and simulated ones."""
        games_per_team = {t: 0 for t in ALL_TEAMS}
        for g in self.played + self.unplayed:
            games_per_team[g.home] += 1
            games_per_team[g.away] += 1
        for t in ALL_TEAMS:
            stats = self.result.projected_team_stats[t]
            total = stats['wins'] + stats['losses']
            self.assertAlmostEqual(total, games_per_team[t], places=6)

    def test_projected_wins_at_least_real_wins(self) -> None:
        """Averaged projected wins should never be less than the wins a team
        has already actually banked from played games."""
        for t in ALL_TEAMS:
            real_w, _ = self.result.win_loss(t)
            self.assertGreaterEqual(self.result.projected_team_stats[t]['wins'], real_w - 1e-6)

    def test_era_is_nonnegative(self) -> None:
        for t in ALL_TEAMS:
            self.assertGreaterEqual(self.result.projected_team_stats[t]['era'], 0.0)

    def test_bracket_is_populated_when_postseason_simulated(self) -> None:
        self.assertIsNotNone(self.result.projected_bracket)
        self.assertGreater(self.result.projected_bracket_pct, 0.0)
        self.assertLessEqual(self.result.projected_bracket_pct, 100.0)

    def test_bracket_champion_matches_world_series_odds_leader_direction(self) -> None:
        """Not a strict equality (the most-FREQUENT single bracket's champion
        needn't be the team with the highest overall title share — many
        distinct brackets can share a champion) but the bracket's champion
        should at least be a team that won the title in at least one sim."""
        champ = self.result.projected_bracket.champion
        self.assertGreater(self.result.world_series_odds.get(champ, 0.0), 0.0)

    def test_bracket_fields_are_internally_consistent(self) -> None:
        b = self.result.projected_bracket
        self.assertIn(b.champion, (b.ws_host, b.ws_guest))
        self.assertEqual({b.ws_host, b.ws_guest}, {b.al_champion, b.nl_champion})
        self.assertEqual(len(b.al_seeds), 6)
        self.assertEqual(len(b.nl_seeds), 6)
        self.assertEqual(set(b.division_winners) | set(b.wild_card_teams),
                         set(b.al_seeds) | set(b.nl_seeds))

    def test_no_postseason_simulation_leaves_bracket_none(self) -> None:
        played, unplayed = _make_full_schedule(seed=1)
        cfg = SimulationConfig(simulations=50, simulate_postseason=False)
        starting_elo = {t: cfg.elo_baseline for t in ALL_TEAMS}
        current_elo, live_standings, elo_log = _replay_with_elo_log(played, starting_elo, cfg)
        data = {
            'live_standings': live_standings,
            'derived_base_elo': current_elo,
            'played_games': played,
            'unplayed_games': unplayed,
            'elo_log': elo_log,
        }
        result = run_simulation_core(data, season=2026, mode='simulate', cfg=cfg)
        self.assertIsNone(result.projected_bracket)
        self.assertEqual(result.projected_bracket_pct, 0.0)
        #Team-level projected stats are independent of postseason
        #simulation and should still be populated.
        self.assertIn(ALL_TEAMS[0], result.projected_team_stats)


if __name__ == '__main__':
    unittest.main()
