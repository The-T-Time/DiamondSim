# ==============================================================================
# tests/test_hitting_models.py
#
# Position Player (Hitting) Ratings.
# Covers models/hitting_stats.py (SeasonHittingLine's OBP/SLG/OPS/BB%/K%/
# HR-rate math, RawHitterRecord availability) and models/hitter.py
# (Hitter/TeamOffense validation + role-scoped impact). No network.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest

import config
from models.hitter import Hitter, TeamOffense
from models.hitting_stats import RawHitterRecord, SeasonHittingLine
from models.player_impact import PlayerImpact


def _line(pa=0, ab=0, h=0, d=0, t=0, hr=0, bb=0, hbp=0, so=0, sf=0, g=0) -> SeasonHittingLine:
    return SeasonHittingLine(plate_appearances=pa, at_bats=ab, hits=h, doubles=d, triples=t,
                              home_runs=hr, walks=bb, hit_by_pitch=hbp, strikeouts=so, sac_flies=sf, games=g)


class TestSeasonHittingLine(unittest.TestCase):
    def test_rejects_negative_counts(self) -> None:
        with self.assertRaises(ValueError):
            _line(pa=-1)

    def test_obp_formula(self) -> None:
        #(H + BB + HBP) / (AB + BB + HBP + SF)
        line = _line(pa=10, ab=7, h=2, bb=2, hbp=1, sf=0)
        self.assertAlmostEqual(line.obp, (2 + 2 + 1) / (7 + 2 + 1 + 0))

    def test_obp_none_with_no_denominator(self) -> None:
        self.assertIsNone(_line().obp)

    def test_slg_formula(self) -> None:
        #1 single, 1 double, 1 triple, 1 HR in 10 AB -> TB = 1+2+3+4=10
        line = _line(ab=10, h=4, d=1, t=1, hr=1)
        self.assertAlmostEqual(line.slg, 10 / 10)

    def test_slg_none_with_zero_at_bats(self) -> None:
        self.assertIsNone(_line(ab=0).slg)

    def test_ops_is_obp_plus_slg(self) -> None:
        line = _line(pa=12, ab=10, h=4, d=1, t=1, hr=1, bb=2)
        self.assertAlmostEqual(line.ops, line.obp + line.slg)

    def test_ops_none_when_either_component_undefined(self) -> None:
        self.assertIsNone(_line(pa=0, ab=0).ops)

    def test_bb_rate_and_k_rate(self) -> None:
        line = _line(pa=100, bb=10, so=25)
        self.assertAlmostEqual(line.bb_rate, 0.10)
        self.assertAlmostEqual(line.k_rate, 0.25)

    def test_rates_none_with_zero_pa(self) -> None:
        line = _line(pa=0)
        self.assertIsNone(line.bb_rate)
        self.assertIsNone(line.k_rate)
        self.assertIsNone(line.hr_per_600_pa)

    def test_hr_per_600_pa_normalization(self) -> None:
        line = _line(pa=300, hr=15)
        self.assertAlmostEqual(line.hr_per_600_pa, 30.0)


class TestRawHitterRecord(unittest.TestCase):
    def _record(self, status_code='A', status_desc='Active') -> RawHitterRecord:
        return RawHitterRecord(person_id=1, full_name='Slugger', status_code=status_code,
                                status_description=status_desc, current_season=None,
                                last_30_days=None, career=None)

    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            RawHitterRecord(person_id=1, full_name='', status_code='A', status_description='Active',
                             current_season=None, last_30_days=None, career=None)

    def test_active_is_available(self) -> None:
        self.assertTrue(self._record('A', 'Active').is_available)
        self.assertFalse(self._record('A', 'Active').is_injured)

    def test_il_is_unavailable_and_injured(self) -> None:
        rec = self._record('IL10', '10-Day IL')
        self.assertFalse(rec.is_available)
        self.assertTrue(rec.is_injured)

    def test_optioned_is_unavailable_but_not_injured(self) -> None:
        rec = self._record('RM', 'Rehab Minors')
        self.assertFalse(rec.is_available)
        self.assertFalse(rec.is_injured)


class TestHitter(unittest.TestCase):
    def test_rejects_empty_name(self) -> None:
        with self.assertRaises(ValueError):
            Hitter(name='', rating=1500.0)

    def test_rejects_non_positive_rating(self) -> None:
        with self.assertRaises(ValueError):
            Hitter(name='Slugger', rating=0.0)

    def test_impact_only_populates_offense_value(self) -> None:
        hitter = Hitter(name='Slugger', rating=config.ELO_BASELINE + 90.0)
        impact = hitter.impact
        self.assertIsInstance(impact, PlayerImpact)
        self.assertAlmostEqual(impact.offense_value, 90.0)
        self.assertIsNone(impact.starter_value)
        self.assertIsNone(impact.bullpen_value)
        self.assertIsNone(impact.defense_value)
        self.assertEqual(impact.populated_roles, ('offense',))


class TestTeamOffense(unittest.TestCase):
    def test_rejects_empty_team(self) -> None:
        with self.assertRaises(ValueError):
            TeamOffense(team='', lineup_rating=1500.0, hitters=(Hitter(name='A'),))

    def test_rejects_empty_hitters(self) -> None:
        with self.assertRaises(ValueError):
            TeamOffense(team='Los Angeles Dodgers', lineup_rating=1500.0, hitters=())

    def test_rejects_non_positive_lineup_rating(self) -> None:
        with self.assertRaises(ValueError):
            TeamOffense(team='Los Angeles Dodgers', lineup_rating=0.0, hitters=(Hitter(name='A'),))

    def test_unavailable_defaults_empty(self) -> None:
        offense = TeamOffense(team='Los Angeles Dodgers', lineup_rating=1500.0, hitters=(Hitter(name='A'),))
        self.assertEqual(offense.unavailable, ())


if __name__ == '__main__':
    unittest.main()
