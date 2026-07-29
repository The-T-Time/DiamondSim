# ==============================================================================
# tests/test_player_rating.py
#
# Real Pitcher Ratings, small-sample shrinkage, and the
# season/last-30-days/career rolling blend. Covers simulation/
# player_rating.py in isolation. No network involved — these operate
# purely on hand-built SeasonPitchingLine objects.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

from models.pitching_stats import SeasonPitchingLine
from models.simulation_config import SimulationConfig
from simulation.player_rating import (
    REPLACEMENT_RATING,
    blend_rating_components,
    fip,
    rating_from_window,
)

CFG = SimulationConfig()


def _line(ip: float, so: int = 0, bb: int = 0, hbp: int = 0, hr: int = 0,
          er: int = 0, games: int = 1, gs: int = 1) -> SeasonPitchingLine:
    return SeasonPitchingLine(
        innings_pitched=ip, strikeouts=so, walks=bb, hit_batters=hbp,
        home_runs=hr, earned_runs=er, games=games, games_started=gs,
    )


class TestFip(unittest.TestCase):
    def test_none_for_zero_innings(self) -> None:
        self.assertIsNone(fip(_line(ip=0.0), CFG.pitcher_fip_constant))

    def test_ace_line_produces_a_low_fip(self) -> None:
        ace = _line(ip=200.0, so=250, bb=40, hr=15, games=32, gs=32)
        value = fip(ace, CFG.pitcher_fip_constant)
        self.assertLess(value, 3.00)

    def test_bad_line_produces_a_high_fip(self) -> None:
        poor = _line(ip=100.0, so=60, bb=55, hr=25, games=20, gs=18)
        value = fip(poor, CFG.pitcher_fip_constant)
        self.assertGreater(value, 5.50)

    def test_more_strikeouts_lowers_fip_all_else_equal(self) -> None:
        low_k = _line(ip=100.0, so=60, bb=30, hr=10)
        high_k = _line(ip=100.0, so=120, bb=30, hr=10)
        self.assertLess(
            fip(high_k, CFG.pitcher_fip_constant),
            fip(low_k, CFG.pitcher_fip_constant),
        )

    def test_more_home_runs_raises_fip_all_else_equal(self) -> None:
        few_hr = _line(ip=100.0, so=90, bb=30, hr=5)
        many_hr = _line(ip=100.0, so=90, bb=30, hr=25)
        self.assertGreater(
            fip(many_hr, CFG.pitcher_fip_constant),
            fip(few_hr, CFG.pitcher_fip_constant),
        )


class TestRatingFromWindow(unittest.TestCase):
    def test_none_line_is_replacement_rating_with_zero_innings(self) -> None:
        rating, ip = rating_from_window(None, CFG)
        self.assertEqual(rating, REPLACEMENT_RATING)
        self.assertEqual(ip, 0.0)

    def test_ace_line_rates_above_replacement(self) -> None:
        ace = _line(ip=200.0, so=250, bb=40, hr=15, games=32, gs=32)
        rating, ip = rating_from_window(ace, CFG)
        self.assertGreater(rating, REPLACEMENT_RATING)
        self.assertEqual(ip, 200.0)

    def test_poor_line_rates_below_replacement(self) -> None:
        poor = _line(ip=100.0, so=60, bb=55, hr=25, games=20, gs=18)
        rating, _ = rating_from_window(poor, CFG)
        self.assertLess(rating, REPLACEMENT_RATING)

    def test_a_20_inning_hot_streak_does_not_become_a_superstar(self) -> None:
        """The exact failure mode this shrinkage exists to prevent: a
        tiny sample of video-game-good numbers (here, a hypothetical
        20 IP / 0 ER / 30 K line) should land closer to league average
        than to a true ace's rating."""
        tiny_but_perfect = _line(ip=20.0, so=30, bb=2, hr=0, er=0, games=4, gs=4)
        full_season_ace = _line(ip=200.0, so=250, bb=25, hr=8, er=50, games=32, gs=32)
        tiny_rating, _ = rating_from_window(tiny_but_perfect, CFG)
        ace_rating, _ = rating_from_window(full_season_ace, CFG)
        self.assertLess(tiny_rating, ace_rating)
        #Shrunk well below "superstar" territory (roughly halfway or less
        #of the way from average to the full-season ace).
        self.assertLess(tiny_rating - REPLACEMENT_RATING, (ace_rating - REPLACEMENT_RATING) * 0.6)

    def test_thin_sample_is_shrunk_toward_replacement(self) -> None:
        small = _line(ip=8.0, so=10, bb=1, hr=0, games=8, gs=0)
        full = _line(ip=200.0, so=250, bb=25, hr=0, games=32, gs=32)
        small_rating, _ = rating_from_window(small, CFG)
        full_rating, _ = rating_from_window(full, CFG)
        self.assertLess(small_rating - REPLACEMENT_RATING, full_rating - REPLACEMENT_RATING)
        self.assertGreater(small_rating, REPLACEMENT_RATING)   #still directionally correct

    def test_reliability_crosses_fifty_percent_near_the_shrinkage_constant(self) -> None:
        #At IP == pitcher_shrinkage_innings, reliability should be ~50%,
        #i.e. the shrunk rating sits about halfway between average and raw.
        line_at_k = _line(ip=CFG.pitcher_shrinkage_innings, so=90, bb=20, hr=5, games=20, gs=20)
        shrunk, _ = rating_from_window(line_at_k, CFG)
        raw = REPLACEMENT_RATING + (CFG.pitcher_league_avg_fip - fip(line_at_k, CFG.pitcher_fip_constant)) * CFG.pitcher_fip_elo_scale
        self.assertAlmostEqual(shrunk - REPLACEMENT_RATING, (raw - REPLACEMENT_RATING) * 0.5, delta=1.0)


class TestBlendRatingComponents(unittest.TestCase):
    def test_only_season_stats_available_rates_off_season_alone(self) -> None:
        season = _line(ip=150.0, so=170, bb=40, hr=15, games=28, gs=28)
        season_only_rating, _ = rating_from_window(season, CFG)
        blended = blend_rating_components(season, None, None, CFG)
        self.assertAlmostEqual(blended, season_only_rating, places=6)

    def test_no_windows_at_all_is_pure_replacement(self) -> None:
        self.assertEqual(blend_rating_components(None, None, None, CFG), REPLACEMENT_RATING)

    def test_rookie_with_no_career_stats_renormalizes_across_season_and_last30(self) -> None:
        season = _line(ip=60.0, so=70, bb=20, hr=6, games=12, gs=12)
        last30 = _line(ip=25.0, so=28, bb=8, hr=3, games=5, gs=5)
        blended = blend_rating_components(season, last30, None, CFG)
        season_rating, _ = rating_from_window(season, CFG)
        last30_rating, _ = rating_from_window(last30, CFG)
        expected = (
            season_rating * CFG.pitcher_season_weight + last30_rating * CFG.pitcher_last30_days_weight
        ) / (CFG.pitcher_season_weight + CFG.pitcher_last30_days_weight)
        self.assertAlmostEqual(blended, expected, places=6)

    def test_season_dominates_over_last30_and_career_by_default_weighting(self) -> None:
        great_season = _line(ip=180.0, so=210, bb=35, hr=12, games=30, gs=30)
        rough_last30 = _line(ip=25.0, so=15, bb=18, hr=8, games=5, gs=5)
        mediocre_career = _line(ip=600.0, so=550, bb=220, hr=90, games=100, gs=100)
        blended = blend_rating_components(great_season, rough_last30, mediocre_career, CFG)
        season_rating, _ = rating_from_window(great_season, CFG)
        #A great season (60% weight) should keep the blend above league
        #average even with a rough recent-30-days window dragging on it,
        #while still being pulled down somewhat from the season number alone.
        self.assertGreater(blended, REPLACEMENT_RATING)
        self.assertLess(blended, season_rating)

    def test_career_baseline_prevents_hot_streak_from_fully_dominating(self) -> None:
        hot_last30 = _line(ip=25.0, so=35, bb=3, hr=0, games=5, gs=5)
        modest_season = _line(ip=100.0, so=90, bb=40, hr=15, games=18, gs=18)
        modest_career = _line(ip=500.0, so=450, bb=180, hr=70, games=90, gs=90)
        with_career = blend_rating_components(modest_season, hot_last30, modest_career, CFG)
        without_career = blend_rating_components(modest_season, hot_last30, None, CFG)
        #Adding a modest career baseline should pull the blend down from
        #what it'd be without it (since the hot streak alone pulls up).
        self.assertLessEqual(with_career, without_career)


if __name__ == '__main__':
    unittest.main()
