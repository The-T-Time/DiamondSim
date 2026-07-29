# ==============================================================================
# tests/test_hitter_rating.py
#
# Position Player (Hitting) Ratings.
# Covers simulation/hitter_rating.py in isolation: the OPS-based rating,
# HR/BB%/K% modifiers, PA-based shrinkage, and the season/last-30-days/
# career blend. No network — hand-built SeasonHittingLine objects.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

from models.hitting_stats import SeasonHittingLine
from models.simulation_config import SimulationConfig
from simulation.hitter_rating import (
    REPLACEMENT_RATING,
    blend_offense_rating_components,
    offense_rating_from_window,
)

CFG = SimulationConfig()


def _line(pa=0, ab=0, h=0, d=0, t=0, hr=0, bb=0, hbp=0, so=0, sf=0, games=0) -> SeasonHittingLine:
    return SeasonHittingLine(plate_appearances=pa, at_bats=ab, hits=h, doubles=d, triples=t,
                              home_runs=hr, walks=bb, hit_by_pitch=hbp, strikeouts=so, sac_flies=sf, games=games)


def _full_season(hits, doubles, triples, hr, bb, so, ab=550, pa=None, games=155) -> SeasonHittingLine:
    pa = pa if pa is not None else ab + bb
    return _line(pa=pa, ab=ab, h=hits, d=doubles, t=triples, hr=hr, bb=bb, so=so, games=games)


class TestOffenseRatingFromWindow(unittest.TestCase):
    def test_none_line_is_replacement_with_zero_pa(self) -> None:
        rating, pa = offense_rating_from_window(None, CFG)
        self.assertEqual(rating, REPLACEMENT_RATING)
        self.assertEqual(pa, 0.0)

    def test_zero_pa_line_is_replacement(self) -> None:
        rating, pa = offense_rating_from_window(_line(pa=0), CFG)
        self.assertEqual(rating, REPLACEMENT_RATING)
        self.assertEqual(pa, 0.0)

    def test_great_full_season_rates_above_replacement(self) -> None:
        #~.955 OPS, 38 HR, decent BB%, moderate K% -- an MVP-caliber year.
        great = _full_season(hits=180, doubles=35, triples=3, hr=38, bb=60, so=110)
        rating, pa = offense_rating_from_window(great, CFG)
        self.assertGreater(rating, REPLACEMENT_RATING)
        self.assertGreater(pa, 0)

    def test_poor_full_season_rates_below_replacement(self) -> None:
        #Low average, no power, few walks, lots of strikeouts.
        poor = _full_season(hits=110, doubles=15, triples=1, hr=5, bb=25, so=160)
        rating, _ = offense_rating_from_window(poor, CFG)
        self.assertLess(rating, REPLACEMENT_RATING)

    def test_a_20_ab_hot_streak_does_not_become_a_superstar(self) -> None:
        """The exact failure mode this shrinkage exists to prevent: a
        20-AB / .500-AVG stretch should land far closer to league average
        than to a real full-season star's rating."""
        tiny_hot = _line(pa=22, ab=20, h=10, d=2, hr=2, bb=2, so=3, games=6)
        great_season = _full_season(hits=180, doubles=35, triples=3, hr=38, bb=60, so=110)
        tiny_rating, _ = offense_rating_from_window(tiny_hot, CFG)
        great_rating, _ = offense_rating_from_window(great_season, CFG)
        self.assertLess(tiny_rating, great_rating)
        self.assertLess(tiny_rating - REPLACEMENT_RATING, (great_rating - REPLACEMENT_RATING) * 0.6)

    def test_more_home_runs_raises_rating_all_else_equal(self) -> None:
        low_hr = _full_season(hits=150, doubles=25, triples=2, hr=10, bb=40, so=100)
        high_hr = _full_season(hits=150, doubles=25, triples=2, hr=35, bb=40, so=100)
        low_rating, _ = offense_rating_from_window(low_hr, CFG)
        high_rating, _ = offense_rating_from_window(high_hr, CFG)
        self.assertGreater(high_rating, low_rating)

    def test_higher_strikeout_rate_lowers_rating_all_else_equal(self) -> None:
        low_k = _full_season(hits=150, doubles=25, triples=2, hr=20, bb=40, so=80)
        high_k = _full_season(hits=150, doubles=25, triples=2, hr=20, bb=40, so=190)
        low_k_rating, _ = offense_rating_from_window(low_k, CFG)
        high_k_rating, _ = offense_rating_from_window(high_k, CFG)
        self.assertGreater(low_k_rating, high_k_rating)

    def test_higher_walk_rate_raises_rating_all_else_equal(self) -> None:
        low_bb = _full_season(hits=150, doubles=25, triples=2, hr=20, bb=20, so=100)
        high_bb = _full_season(hits=150, doubles=25, triples=2, hr=20, bb=90, so=100)
        low_bb_rating, _ = offense_rating_from_window(low_bb, CFG)
        high_bb_rating, _ = offense_rating_from_window(high_bb, CFG)
        self.assertGreater(high_bb_rating, low_bb_rating)

    def test_larger_sample_is_trusted_closer_to_the_raw_rating(self) -> None:
        #Identical underlying RATES, just scaled up 20x in sample size --
        #isolates shrinkage as the only variable between the two.
        small_scale = 1
        big_scale = 20
        small_line = _line(pa=100 * small_scale, ab=90 * small_scale, h=27 * small_scale,
                            d=5 * small_scale, hr=4 * small_scale, bb=8 * small_scale,
                            so=22 * small_scale, games=25 * small_scale)
        big_line = _line(pa=100 * big_scale, ab=90 * big_scale, h=27 * big_scale,
                          d=5 * big_scale, hr=4 * big_scale, bb=8 * big_scale,
                          so=22 * big_scale, games=25 * big_scale)
        small_rating, _ = offense_rating_from_window(small_line, CFG)
        big_rating, _ = offense_rating_from_window(big_line, CFG)
        #Same rates, but the bigger sample should be trusted further from
        #league average (closer to the "raw," un-shrunk rating).
        self.assertLess(abs(small_rating - REPLACEMENT_RATING), abs(big_rating - REPLACEMENT_RATING))


class TestBlendOffenseRatingComponents(unittest.TestCase):
    def test_only_season_available_rates_off_season_alone(self) -> None:
        season = _full_season(hits=150, doubles=25, triples=2, hr=20, bb=40, so=100)
        season_only, _ = offense_rating_from_window(season, CFG)
        blended = blend_offense_rating_components(season, None, None, CFG)
        self.assertAlmostEqual(blended, season_only, places=6)

    def test_no_windows_is_pure_replacement(self) -> None:
        self.assertEqual(blend_offense_rating_components(None, None, None, CFG), REPLACEMENT_RATING)

    def test_rookie_with_no_career_stats_renormalizes_across_season_and_last30(self) -> None:
        season = _line(pa=200, ab=180, h=48, d=10, hr=6, bb=15, so=45, games=45)
        last30 = _line(pa=90, ab=80, h=25, d=5, hr=4, bb=8, so=18, games=22)
        blended = blend_offense_rating_components(season, last30, None, CFG)
        season_rating, _ = offense_rating_from_window(season, CFG)
        last30_rating, _ = offense_rating_from_window(last30, CFG)
        expected = (
            season_rating * CFG.hitter_season_weight + last30_rating * CFG.hitter_last30_days_weight
        ) / (CFG.hitter_season_weight + CFG.hitter_last30_days_weight)
        self.assertAlmostEqual(blended, expected, places=6)

    def test_career_baseline_prevents_hot_streak_from_fully_dominating(self) -> None:
        hot_last30 = _line(pa=100, ab=88, h=35, d=8, hr=6, bb=10, so=12, games=24)
        modest_season = _full_season(hits=140, doubles=22, triples=1, hr=14, bb=35, so=110)
        modest_career = _full_season(hits=1400, doubles=220, triples=15, hr=140, bb=350, so=1100, ab=5500, games=1550)
        with_career = blend_offense_rating_components(modest_season, hot_last30, modest_career, CFG)
        without_career = blend_offense_rating_components(modest_season, hot_last30, None, CFG)
        self.assertLessEqual(with_career, without_career)


if __name__ == '__main__':
    unittest.main()
