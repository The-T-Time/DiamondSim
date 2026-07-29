# ==============================================================================
# tests/test_offense_lineups.py
#
# Lineups (vs LHP/RHP).
# Covers simulation/offense_calculator.py's build_team_lineups /
# build_team_lineups_for_team: platoon-split ratings, graceful fallback
# when split data is missing, and full fallback to the synthetic lineup.
# No network — hand-built RawHitterRecord fixtures.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import unittest
from unittest.mock import patch

from data.exceptions import DataFetchError
from models.hitting_stats import RawHitterRecord, SeasonHittingLine
from models.simulation_config import SimulationConfig
from simulation.offense_calculator import (
    build_team_lineups,
    build_team_lineups_for_team,
    default_team_offense,
)

CFG = SimulationConfig()
DODGERS = 'Los Angeles Dodgers'
AS_OF = '2026-07-12'


def _split_line(pa: int, ab: int, h: int, hr: int, bb: int, so: int) -> SeasonHittingLine:
    return SeasonHittingLine(plate_appearances=pa, at_bats=ab, hits=h, doubles=max(0, h // 5),
                              triples=0, home_runs=hr, walks=bb, hit_by_pitch=0, strikeouts=so,
                              sac_flies=0, games=max(1, pa // 4))


def _hitter(pid: int, name: str, overall_pa: int, vs_lhp=None, vs_rhp=None,
            status_code: str = 'A', status_desc: str = 'Active') -> RawHitterRecord:
    overall = _split_line(overall_pa, int(overall_pa * 0.9), int(overall_pa * 0.27),
                          int(overall_pa * 0.03), int(overall_pa * 0.09), int(overall_pa * 0.2))
    return RawHitterRecord(person_id=pid, full_name=name, status_code=status_code,
                            status_description=status_desc, current_season=overall,
                            last_30_days=None, career=None, vs_lhp=vs_lhp, vs_rhp=vs_rhp)


class TestBuildTeamLineups(unittest.TestCase):
    def test_returns_none_with_no_split_data_anywhere(self) -> None:
        staff = [_hitter(1, 'Bat', 500)]   #no vs_lhp/vs_rhp given
        self.assertIsNone(build_team_lineups(DODGERS, staff, CFG))

    def test_mashes_lefties_but_not_righties_shows_up_in_the_right_lineup(self) -> None:
        masher = _hitter(
            1, 'Lefty Masher', overall_pa=500,
            vs_lhp=_split_line(pa=150, ab=130, h=48, hr=10, bb=15, so=20),   #great vs LHP
            vs_rhp=_split_line(pa=350, ab=310, h=70, hr=8, bb=25, so=90),    #mediocre vs RHP
        )
        lineups = build_team_lineups(DODGERS, [masher], CFG)
        self.assertIsNotNone(lineups)
        self.assertGreater(lineups.vs_lhp.lineup_rating, lineups.vs_rhp.lineup_rating)

    def test_injured_hitter_excluded_from_both_lineups(self) -> None:
        hurt = _hitter(
            1, 'Hurt Bat', overall_pa=500,
            vs_lhp=_split_line(150, 130, 48, 10, 15, 20),
            vs_rhp=_split_line(350, 310, 70, 8, 25, 90),
            status_code='IL15', status_desc='15-Day IL',
        )
        healthy = _hitter(
            2, 'Healthy Bat', overall_pa=400,
            vs_lhp=_split_line(120, 100, 25, 3, 10, 25),
            vs_rhp=_split_line(280, 250, 65, 6, 20, 60),
        )
        lineups = build_team_lineups(DODGERS, [hurt, healthy], CFG)
        self.assertIsNotNone(lineups)
        for offense in (lineups.vs_lhp, lineups.vs_rhp):
            names = [h.name for h in offense.hitters]
            self.assertNotIn('Hurt Bat', names)
            self.assertIn('Healthy Bat', names)


class TestBuildTeamLineupsForTeamFallback(unittest.TestCase):
    def test_falls_back_to_synthetic_for_both_sides_when_disabled(self) -> None:
        cfg = SimulationConfig(use_real_hitter_stats=False)
        lineups = build_team_lineups_for_team(DODGERS, 119, 1550.0, 2026, AS_OF, cfg)
        expected = default_team_offense(DODGERS, 1550.0)
        self.assertEqual([h.rating for h in lineups.vs_rhp.hitters], [h.rating for h in expected.hitters])
        self.assertEqual([h.rating for h in lineups.vs_lhp.hitters], [h.rating for h in expected.hitters])

    def test_falls_back_to_synthetic_when_fetch_fails(self) -> None:
        with patch('simulation.offense_calculator.fetch_team_hitters', side_effect=DataFetchError('boom')):
            lineups = build_team_lineups_for_team(DODGERS, 119, 1550.0, 2026, AS_OF, CFG)
        expected = default_team_offense(DODGERS, 1550.0)
        self.assertEqual([h.rating for h in lineups.vs_rhp.hitters], [h.rating for h in expected.hitters])

    def test_falls_back_to_one_overall_lineup_when_no_split_data(self) -> None:
        staff = [_hitter(1, 'Bat', 500)]   #real hitter, but no platoon splits at all
        with patch('simulation.offense_calculator.fetch_team_hitters', return_value=staff):
            lineups = build_team_lineups_for_team(DODGERS, 119, 1550.0, 2026, AS_OF, CFG)
        #Same underlying rating used for both sides (one overall lineup).
        self.assertEqual(lineups.vs_rhp.lineup_rating, lineups.vs_lhp.lineup_rating)
        self.assertEqual(lineups.vs_rhp.hitters[0].name, 'Bat')

    def test_uses_real_split_data_when_available(self) -> None:
        masher = _hitter(
            1, 'Lefty Masher', overall_pa=500,
            vs_lhp=_split_line(150, 130, 48, 10, 15, 20),
            vs_rhp=_split_line(350, 310, 70, 8, 25, 90),
        )
        with patch('simulation.offense_calculator.fetch_team_hitters', return_value=[masher]):
            lineups = build_team_lineups_for_team(DODGERS, 119, 1550.0, 2026, AS_OF, CFG)
        self.assertGreater(lineups.vs_lhp.lineup_rating, lineups.vs_rhp.lineup_rating)


if __name__ == '__main__':
    unittest.main()
