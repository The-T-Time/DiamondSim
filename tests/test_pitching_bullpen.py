# ==============================================================================
# tests/test_pitching_bullpen.py
#
# Starting Pitcher Impact & Bullpen Fatigue.
# Covers models/pitcher.py, models/bullpen.py, simulation/pitching.py,
# simulation/fatigue.py, and their integration into series_simulator.py /
# playoff_simulator.py. test_split_modules.py / test_postseason.py already
# pin down that the pre-5.7 pure-Elo path is untouched when rotations/
# bullpens aren't supplied; these tests focus on the new opt-in behavior.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import random
import unittest

from models.bullpen import Bullpen, Reliever
from models.pitcher import Pitcher, Rotation
from models.simulation_config import SimulationConfig
from simulation.fatigue import BullpenFatigueTracker, MAX_FATIGUE, MAX_FATIGUE_ELO_PENALTY
from simulation.pitching import (
    default_bullpen_for_team,
    default_rotation_for_team,
    game_win_prob,
    is_taxing_game,
)
from simulation.playoff_simulator import simulate_postseason
from simulation.series_simulator import play_series

DODGERS = 'Los Angeles Dodgers'   #NL West
PADRES  = 'San Diego Padres'      #NL West


class TestPitcherModel(unittest.TestCase):
    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            Pitcher(name='', rating=1500.0)

    def test_rejects_non_positive_rating(self) -> None:
        with self.assertRaises(ValueError):
            Pitcher(name='Ace', rating=0.0)

    def test_rotation_requires_at_least_one_starter(self) -> None:
        with self.assertRaises(ValueError):
            Rotation(starters=())

    def test_rotation_cycles_back_to_the_top_on_short_rest(self) -> None:
        ace = Pitcher(name='Ace', rating=1600.0)
        two = Pitcher(name='Two', rating=1550.0)
        rotation = Rotation(starters=(ace, two))
        self.assertEqual(rotation.starter_for_game(0), ace)
        self.assertEqual(rotation.starter_for_game(1), two)
        self.assertEqual(rotation.starter_for_game(2), ace)   #cycles, doesn't raise
        self.assertEqual(rotation.starter_for_game(3), two)

    def test_ace_is_the_first_starter(self) -> None:
        ace = Pitcher(name='Ace', rating=1600.0)
        rotation = Rotation(starters=(ace, Pitcher(name='Two', rating=1500.0)))
        self.assertEqual(rotation.ace, ace)


class TestBullpenModel(unittest.TestCase):
    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            Reliever(name='', rating=1500.0)

    def test_rejects_leverage_out_of_range(self) -> None:
        with self.assertRaises(ValueError):
            Reliever(name='Mopup', rating=1400.0, leverage=0.0)
        with self.assertRaises(ValueError):
            Reliever(name='Mopup', rating=1400.0, leverage=1.5)

    def test_bullpen_requires_at_least_one_reliever(self) -> None:
        with self.assertRaises(ValueError):
            Bullpen(relievers=())

    def test_strength_weights_toward_high_leverage_arms(self) -> None:
        closer = Reliever(name='Closer', rating=1700.0, leverage=1.0)
        mopup = Reliever(name='Mopup', rating=1300.0, leverage=0.1)
        strength = Bullpen(relievers=(closer, mopup)).strength
        #A near-zero-leverage mop-up arm should barely move strength off
        #the closer's rating, not pull it halfway toward 1300.
        self.assertGreater(strength, 1600.0)


class TestDefaultStaffGeneration(unittest.TestCase):
    def test_rotation_is_deterministic_for_the_same_team_and_elo(self) -> None:
        a = default_rotation_for_team(DODGERS, 1550.0)
        b = default_rotation_for_team(DODGERS, 1550.0)
        self.assertEqual([p.rating for p in a.starters], [p.rating for p in b.starters])

    def test_bullpen_is_deterministic_for_the_same_team_and_elo(self) -> None:
        a = default_bullpen_for_team(DODGERS, 1550.0)
        b = default_bullpen_for_team(DODGERS, 1550.0)
        self.assertEqual([r.rating for r in a.relievers], [r.rating for r in b.relievers])

    def test_two_different_teams_at_the_same_elo_get_different_staffs(self) -> None:
        dodgers = default_rotation_for_team(DODGERS, 1550.0)
        padres = default_rotation_for_team(PADRES, 1550.0)
        self.assertNotEqual(
            [p.rating for p in dodgers.starters], [p.rating for p in padres.starters]
        )

    def test_higher_team_elo_produces_a_stronger_ace(self) -> None:
        weak_ace = default_rotation_for_team(DODGERS, 1450.0).ace.rating
        strong_ace = default_rotation_for_team(DODGERS, 1650.0).ace.rating
        self.assertGreater(strong_ace, weak_ace)

    def test_rotation_is_ordered_best_starter_first(self) -> None:
        rotation = default_rotation_for_team(DODGERS, 1500.0)
        ratings = [p.rating for p in rotation.starters]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_bullpen_is_ordered_highest_leverage_first(self) -> None:
        bullpen = default_bullpen_for_team(DODGERS, 1500.0)
        leverages = [r.leverage for r in bullpen.relievers]
        self.assertEqual(leverages, sorted(leverages, reverse=True))


class TestGameWinProb(unittest.TestCase):
    def test_better_starter_raises_home_win_probability(self) -> None:
        cfg = SimulationConfig()
        baseline = game_win_prob(1500, 1500, 1500, 1500, 0.0, 0.0, cfg)
        with_ace = game_win_prob(1500, 1500, 1650, 1500, 0.0, 0.0, cfg)
        self.assertGreater(with_ace, baseline)

    def test_fatigued_opposing_bullpen_raises_home_win_probability(self) -> None:
        cfg = SimulationConfig()
        baseline = game_win_prob(1500, 1500, 1500, 1500, 0.0, 0.0, cfg)
        away_tired = game_win_prob(1500, 1500, 1500, 1500, 0.0, MAX_FATIGUE_ELO_PENALTY, cfg)
        self.assertGreater(away_tired, baseline)

    def test_probability_stays_in_valid_range_for_extreme_inputs(self) -> None:
        cfg = SimulationConfig()
        p = game_win_prob(2000, 1000, 1800, 1200, 0.0, 20.0, cfg)
        self.assertGreater(p, 0.0)
        self.assertLess(p, 1.0)


class TestIsTaxingGame(unittest.TestCase):
    def test_close_margin_is_taxing(self) -> None:
        self.assertTrue(is_taxing_game(1))

    def test_blowout_margin_is_not_taxing(self) -> None:
        self.assertFalse(is_taxing_game(8))


class TestBullpenFatigueTracker(unittest.TestCase):
    def test_fresh_team_has_zero_fatigue_and_no_penalty(self) -> None:
        tracker = BullpenFatigueTracker()
        self.assertEqual(tracker.level(DODGERS), 0.0)
        self.assertEqual(tracker.elo_penalty(DODGERS), 0.0)

    def test_taxing_games_accumulate_more_fatigue_than_normal_games(self) -> None:
        taxing = BullpenFatigueTracker()
        normal = BullpenFatigueTracker()
        taxing.record_game(DODGERS, was_taxing=True)
        normal.record_game(DODGERS, was_taxing=False)
        self.assertGreater(taxing.level(DODGERS), normal.level(DODGERS))

    def test_fatigue_is_capped_at_max(self) -> None:
        tracker = BullpenFatigueTracker()
        for _ in range(50):
            tracker.record_game(DODGERS, was_taxing=True)
        self.assertLessEqual(tracker.level(DODGERS), MAX_FATIGUE)

    def test_rest_reduces_fatigue(self) -> None:
        tracker = BullpenFatigueTracker()
        tracker.record_game(DODGERS, was_taxing=True)
        level_before = tracker.level(DODGERS)
        tracker.rest(DODGERS, days=1)
        self.assertLess(tracker.level(DODGERS), level_before)

    def test_rest_never_drops_fatigue_below_zero(self) -> None:
        tracker = BullpenFatigueTracker()
        tracker.rest(DODGERS, days=10)
        self.assertEqual(tracker.level(DODGERS), 0.0)

    def test_elo_penalty_scales_with_fatigue_level(self) -> None:
        tracker = BullpenFatigueTracker()
        tracker.record_game(DODGERS, was_taxing=True)
        light_penalty = tracker.elo_penalty(DODGERS)
        for _ in range(10):
            tracker.record_game(DODGERS, was_taxing=True)
        heavy_penalty = tracker.elo_penalty(DODGERS)
        self.assertGreater(heavy_penalty, light_penalty)
        self.assertLessEqual(heavy_penalty, MAX_FATIGUE_ELO_PENALTY)

    def test_teams_are_tracked_independently(self) -> None:
        tracker = BullpenFatigueTracker()
        tracker.record_game(DODGERS, was_taxing=True)
        self.assertEqual(tracker.level(PADRES), 0.0)


class TestPlaySeriesBackwardCompatibility(unittest.TestCase):
    """Omitting rotations/bullpens/fatigue must reproduce pre-5.7 behavior
    exactly — no new required arguments, no behavior change by default."""

    def test_series_still_resolves_without_pitching_data(self) -> None:
        elo = {DODGERS: 1550.0, PADRES: 1500.0}
        rng = random.Random(4)
        winner = play_series(DODGERS, PADRES, elo, SimulationConfig(), rng, best_of=5)
        self.assertIn(winner, (DODGERS, PADRES))

    def test_pure_elo_path_is_seed_for_seed_identical_with_or_without_the_gate_on(self) -> None:
        #cfg defaults have both new flags True, but rotations=None must
        #still short-circuit straight to the old expected_home_win_prob path.
        elo_a = {DODGERS: 1550.0, PADRES: 1500.0}
        elo_b = {DODGERS: 1550.0, PADRES: 1500.0}
        winner_a = play_series(DODGERS, PADRES, elo_a, SimulationConfig(), random.Random(7), best_of=7)
        winner_b = play_series(DODGERS, PADRES, elo_b, SimulationConfig(), random.Random(7), best_of=7)
        self.assertEqual(winner_a, winner_b)


class TestPlaySeriesWithPitching(unittest.TestCase):
    def _rotations(self):
        return {
            DODGERS: Rotation(starters=(Pitcher(name='D-Ace', rating=1700.0),)),
            PADRES: Rotation(starters=(Pitcher(name='P-Ace', rating=1300.0),)),
        }

    def test_stronger_starters_win_series_more_often_at_equal_team_elo(self) -> None:
        rotations = self._rotations()
        wins = 0
        trials = 150
        for i in range(trials):
            elo = {DODGERS: 1500.0, PADRES: 1500.0}   #team Elo dead even
            winner = play_series(
                DODGERS, PADRES, elo, SimulationConfig(), random.Random(i),
                best_of=7, rotations=rotations,
            )
            if winner == DODGERS:
                wins += 1
        #With team Elo even, the huge starter-rating edge should still make
        #the Dodgers the clear favorite.
        self.assertGreater(wins / trials, 0.65)

    def test_bullpen_fatigue_accumulates_across_the_series(self) -> None:
        rotations = self._rotations()
        bullpens = {
            DODGERS: default_bullpen_for_team(DODGERS, 1500.0),
            PADRES: default_bullpen_for_team(PADRES, 1500.0),
        }
        fatigue = BullpenFatigueTracker()
        elo = {DODGERS: 1500.0, PADRES: 1500.0}
        play_series(
            DODGERS, PADRES, elo, SimulationConfig(), random.Random(3),
            best_of=7, rotations=rotations, bullpens=bullpens, fatigue=fatigue,
        )
        #At least one game was played, so at least one team picked up fatigue.
        self.assertTrue(fatigue.level(DODGERS) > 0 or fatigue.level(PADRES) > 0)

    def test_disabling_starting_pitcher_impact_ignores_supplied_rotations(self) -> None:
        rotations = self._rotations()
        cfg = SimulationConfig(starting_pitcher_impact=False)
        elo_a = {DODGERS: 1500.0, PADRES: 1500.0}
        elo_b = {DODGERS: 1500.0, PADRES: 1500.0}
        winner_with_flag_off = play_series(
            DODGERS, PADRES, elo_a, cfg, random.Random(9), best_of=7, rotations=rotations,
        )
        winner_pure_elo = play_series(
            DODGERS, PADRES, elo_b, cfg, random.Random(9), best_of=7,
        )
        self.assertEqual(winner_with_flag_off, winner_pure_elo)


class TestSimulatePostseasonWithPitching(unittest.TestCase):
    @staticmethod
    def _synthetic_records_and_h2h():
        from collections import defaultdict
        from data.teams import ALL_TEAMS
        records = {}
        h2h = {t: defaultdict(int) for t in ALL_TEAMS}
        for i, t in enumerate(ALL_TEAMS):
            wins = 100 - i
            records[t] = {
                'W': wins, 'L': 162 - wins,
                'div_W': 0, 'div_L': 0, 'league_W': 0, 'league_L': 0,
                'league_results': [],
            }
        return records, h2h

    def test_champion_is_still_a_real_team_with_pitching_data_supplied(self) -> None:
        from data.teams import ALL_TEAMS
        records, h2h = self._synthetic_records_and_h2h()
        elo = {t: 1500.0 for t in ALL_TEAMS}
        rotations = {t: default_rotation_for_team(t, elo[t]) for t in ALL_TEAMS}
        bullpens = {t: default_bullpen_for_team(t, elo[t]) for t in ALL_TEAMS}
        champion = simulate_postseason(
            records, h2h, elo, SimulationConfig(), random.Random(11),
            rotations=rotations, bullpens=bullpens,
        ).champion
        self.assertIn(champion, ALL_TEAMS)

    def test_deterministic_given_the_same_seed_with_pitching_data_supplied(self) -> None:
        from data.teams import ALL_TEAMS
        records, h2h = self._synthetic_records_and_h2h()
        elo = {t: 1500.0 for t in ALL_TEAMS}
        rotations = {t: default_rotation_for_team(t, elo[t]) for t in ALL_TEAMS}
        bullpens = {t: default_bullpen_for_team(t, elo[t]) for t in ALL_TEAMS}
        champ_a = simulate_postseason(
            records, h2h, dict(elo), SimulationConfig(), random.Random(99),
            rotations=rotations, bullpens=bullpens,
        )
        champ_b = simulate_postseason(
            records, h2h, dict(elo), SimulationConfig(), random.Random(99),
            rotations=rotations, bullpens=bullpens,
        )
        self.assertEqual(champ_a, champ_b)


class TestPlaySeriesWithLineups(unittest.TestCase):
    """Lineups (vs LHP/RHP) wired into play_series."""

    def _rotation(self, team_label: str, throws: str) -> Rotation:
        return Rotation(starters=tuple(
            Pitcher(name=f'{team_label} SP{i+1}', rating=1500.0, throws=throws) for i in range(5)
        ))

    def test_series_still_resolves_with_lineups_supplied(self) -> None:
        from models.hitter import Hitter, TeamLineups, TeamOffense

        elo = {DODGERS: 1500.0, PADRES: 1500.0}
        rotations = {DODGERS: self._rotation('LAD', 'R'), PADRES: self._rotation('SD', 'L')}

        def _lineups(rating_vs_r: float, rating_vs_l: float) -> "TeamLineups":
            return TeamLineups(
                team=DODGERS,
                vs_rhp=TeamOffense(team=DODGERS, lineup_rating=rating_vs_r, hitters=(Hitter(name='A', rating=rating_vs_r),)),
                vs_lhp=TeamOffense(team=DODGERS, lineup_rating=rating_vs_l, hitters=(Hitter(name='A', rating=rating_vs_l),)),
            )

        lineups = {DODGERS: _lineups(1500.0, 1500.0), PADRES: _lineups(1500.0, 1500.0)}
        rng = random.Random(4)
        winner = play_series(DODGERS, PADRES, elo, SimulationConfig(), rng, best_of=5,
                             rotations=rotations, lineups=lineups)
        self.assertIn(winner, (DODGERS, PADRES))

    def test_lineup_impact_off_ignores_supplied_lineups(self) -> None:
        from models.hitter import Hitter, TeamLineups, TeamOffense

        elo = {DODGERS: 1500.0, PADRES: 1500.0}
        rotations = {DODGERS: self._rotation('LAD', 'R'), PADRES: self._rotation('SD', 'R')}
        strong = TeamOffense(team=DODGERS, lineup_rating=1700.0, hitters=(Hitter(name='A', rating=1700.0),))
        weak = TeamOffense(team=PADRES, lineup_rating=1300.0, hitters=(Hitter(name='B', rating=1300.0),))
        lineups = {DODGERS: TeamLineups(team=DODGERS, vs_rhp=strong, vs_lhp=strong),
                  PADRES: TeamLineups(team=PADRES, vs_rhp=weak, vs_lhp=weak)}

        cfg_off = SimulationConfig(lineup_impact=False)
        cfg_on  = SimulationConfig(lineup_impact=True)

        winners_off = [
            play_series(DODGERS, PADRES, dict(elo), cfg_off, random.Random(s), best_of=7,
                       rotations=rotations, lineups=lineups)
            for s in range(30)
        ]
        winners_on = [
            play_series(DODGERS, PADRES, dict(elo), cfg_on, random.Random(s), best_of=7,
                       rotations=rotations, lineups=lineups)
            for s in range(30)
        ]
        #With lineup_impact on, the Dodgers' huge lineup edge should win
        #them meaningfully more often than with it off (same seeds).
        self.assertGreater(winners_on.count(DODGERS), winners_off.count(DODGERS))

    def test_lineup_selection_uses_opposing_starters_hand(self) -> None:
        """A team with a big vs-LHP edge and no vs-RHP edge should win more
        often against a lefty-throwing rotation than a righty-throwing one."""
        from models.hitter import Hitter, TeamLineups, TeamOffense

        lefty_masher = TeamLineups(
            team=DODGERS,
            vs_rhp=TeamOffense(team=DODGERS, lineup_rating=1500.0, hitters=(Hitter(name='A', rating=1500.0),)),
            vs_lhp=TeamOffense(team=DODGERS, lineup_rating=1650.0, hitters=(Hitter(name='A', rating=1650.0),)),
        )
        neutral = TeamLineups(
            team=PADRES,
            vs_rhp=TeamOffense(team=PADRES, lineup_rating=1500.0, hitters=(Hitter(name='B', rating=1500.0),)),
            vs_lhp=TeamOffense(team=PADRES, lineup_rating=1500.0, hitters=(Hitter(name='B', rating=1500.0),)),
        )
        lineups = {DODGERS: lefty_masher, PADRES: neutral}
        cfg = SimulationConfig()

        rotations_vs_lefty = {DODGERS: self._rotation('LAD', 'R'), PADRES: self._rotation('SD', 'L')}
        rotations_vs_righty = {DODGERS: self._rotation('LAD', 'R'), PADRES: self._rotation('SD', 'R')}

        wins_vs_lefty = sum(
            play_series(DODGERS, PADRES, {DODGERS: 1500.0, PADRES: 1500.0}, cfg, random.Random(s), best_of=7,
                       rotations=rotations_vs_lefty, lineups=lineups) == DODGERS
            for s in range(40)
        )
        wins_vs_righty = sum(
            play_series(DODGERS, PADRES, {DODGERS: 1500.0, PADRES: 1500.0}, cfg, random.Random(s), best_of=7,
                       rotations=rotations_vs_righty, lineups=lineups) == DODGERS
            for s in range(40)
        )
        self.assertGreater(wins_vs_lefty, wins_vs_righty)


if __name__ == '__main__':
    unittest.main()
