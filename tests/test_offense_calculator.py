# ==============================================================================
# tests/test_offense_calculator.py
#
# Position Player (Hitting) Ratings.
# Covers simulation/offense_calculator.py: building TeamOffense from real
# hitter data, injury exclusion + visibility, playing-time weighting of the
# team lineup_rating, and fallback to the synthetic generator. Hand-built
# RawHitterRecord fixtures — no network.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest
from unittest.mock import patch

from data.exceptions import DataFetchError
from models.hitting_stats import RawHitterRecord, SeasonHittingLine
from models.simulation_config import SimulationConfig
from simulation.offense_calculator import (
    build_team_offense,
    default_team_offense,
    offense_from_hitters,
)

CFG = SimulationConfig()
DODGERS = 'Los Angeles Dodgers'
AS_OF = '2026-07-12'


def _hitter(pid: int, name: str, pa: int, ab: int, h: int, hr: int, bb: int, so: int,
            status_code: str = 'A', status_desc: str = 'Active', games: int = None) -> RawHitterRecord:
    games = games if games is not None else max(1, pa // 4)
    line = SeasonHittingLine(plate_appearances=pa, at_bats=ab, hits=h, doubles=max(0, h // 5),
                              triples=0, home_runs=hr, walks=bb, hit_by_pitch=0, strikeouts=so,
                              sac_flies=0, games=games)
    return RawHitterRecord(person_id=pid, full_name=name, status_code=status_code,
                            status_description=status_desc, current_season=line,
                            last_30_days=None, career=None)


class TestDefaultTeamOffense(unittest.TestCase):
    def test_synthetic_offense_has_13_hitters_scaled_to_team_elo(self) -> None:
        strong = default_team_offense(DODGERS, 1600.0)
        weak = default_team_offense(DODGERS, 1400.0)
        self.assertEqual(len(strong.hitters), 13)
        self.assertGreater(strong.lineup_rating, weak.lineup_rating)

    def test_deterministic_for_same_team_and_elo(self) -> None:
        a = default_team_offense(DODGERS, 1550.0)
        b = default_team_offense(DODGERS, 1550.0)
        self.assertEqual([h.rating for h in a.hitters], [h.rating for h in b.hitters])


class TestOffenseFromHitters(unittest.TestCase):
    def test_returns_none_when_no_hitter_available(self) -> None:
        staff = [_hitter(1, 'Hurt Bat', 400, 350, 100, 15, 30, 80, status_code='IL15', status_desc='15-Day IL')]
        self.assertIsNone(offense_from_hitters(DODGERS, staff, CFG))

    def test_injured_hitter_excluded_but_visible_as_unavailable(self) -> None:
        staff = [
            _hitter(1, 'Star', 500, 440, 140, 30, 50, 90),
            _hitter(2, 'Hurt Bat', 400, 350, 100, 15, 30, 80, status_code='IL15', status_desc='15-Day IL'),
        ]
        offense = offense_from_hitters(DODGERS, staff, CFG)
        names = [h.name for h in offense.hitters]
        self.assertNotIn('Hurt Bat', names)
        self.assertIn('Hurt Bat', [h.name for h in offense.unavailable])

    def test_lineup_rating_is_playing_time_weighted(self) -> None:
        #An everyday regular with modest numbers vs. a bench bat with a
        #tiny hot sample -- the regular should dominate the team average.
        everyday_regular = _hitter(1, 'Regular', pa=600, ab=530, h=140, hr=15, bb=55, so=110)
        hot_bench_bat = _hitter(2, 'Bench', pa=15, ab=13, h=8, hr=2, bb=2, so=1)
        offense = offense_from_hitters(DODGERS, [everyday_regular, hot_bench_bat], CFG)

        regular_hitter = next(h for h in offense.hitters if h.name == 'Regular')
        bench_hitter = next(h for h in offense.hitters if h.name == 'Bench')
        #Bench bat's tiny sample should rate much higher (small-sample
        #noise), but the team lineup_rating should sit close to the
        #everyday regular's rating, not pulled way up by the bench bat.
        self.assertGreater(bench_hitter.rating, regular_hitter.rating)
        self.assertLess(abs(offense.lineup_rating - regular_hitter.rating), abs(offense.lineup_rating - bench_hitter.rating))

    def test_hitters_ordered_best_first(self) -> None:
        staff = [
            _hitter(1, 'Average', 500, 450, 115, 15, 35, 100),
            _hitter(2, 'Star', 550, 480, 155, 35, 60, 90),
            _hitter(3, 'Weak', 400, 370, 80, 5, 20, 130),
        ]
        offense = offense_from_hitters(DODGERS, staff, CFG)
        self.assertEqual(offense.hitters[0].name, 'Star')
        ratings = [h.rating for h in offense.hitters]
        self.assertEqual(ratings, sorted(ratings, reverse=True))


class TestBuildTeamOffenseFallback(unittest.TestCase):
    def test_falls_back_to_synthetic_when_disabled(self) -> None:
        cfg = SimulationConfig(use_real_hitter_stats=False)
        offense = build_team_offense(DODGERS, 119, 1550.0, 2026, AS_OF, cfg)
        expected = default_team_offense(DODGERS, 1550.0)
        self.assertEqual([h.rating for h in offense.hitters], [h.rating for h in expected.hitters])

    def test_falls_back_to_synthetic_when_fetch_fails(self) -> None:
        with patch('simulation.offense_calculator.fetch_team_hitters', side_effect=DataFetchError('boom')):
            offense = build_team_offense(DODGERS, 119, 1550.0, 2026, AS_OF, CFG)
        expected = default_team_offense(DODGERS, 1550.0)
        self.assertEqual([h.rating for h in offense.hitters], [h.rating for h in expected.hitters])

    def test_falls_back_to_synthetic_when_no_available_hitters(self) -> None:
        staff = [_hitter(1, 'Hurt Bat', 400, 350, 100, 15, 30, 80, status_code='IL60', status_desc='60-Day IL')]
        with patch('simulation.offense_calculator.fetch_team_hitters', return_value=staff):
            offense = build_team_offense(DODGERS, 119, 1550.0, 2026, AS_OF, CFG)
        expected = default_team_offense(DODGERS, 1550.0)
        self.assertEqual([h.rating for h in offense.hitters], [h.rating for h in expected.hitters])

    def test_uses_real_data_when_available(self) -> None:
        staff = [_hitter(1, 'Real Star', 550, 480, 155, 35, 60, 90)]
        with patch('simulation.offense_calculator.fetch_team_hitters', return_value=staff):
            offense = build_team_offense(DODGERS, 119, 1550.0, 2026, AS_OF, CFG)
        self.assertEqual(offense.hitters[0].name, 'Real Star')


class TestHitterImpactWiring(unittest.TestCase):
    def test_available_hitters_get_offense_impact(self) -> None:
        staff = [_hitter(1, 'Star', 550, 480, 155, 35, 60, 90)]
        offense = offense_from_hitters(DODGERS, staff, CFG)
        impact = offense.hitters[0].impact
        self.assertIsNotNone(impact.offense_value)
        self.assertIsNone(impact.starter_value)
        self.assertIsNone(impact.bullpen_value)


if __name__ == '__main__':
    unittest.main()
