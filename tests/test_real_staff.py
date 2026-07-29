# ==============================================================================
# tests/test_real_staff.py
#
# Real Pitcher Ratings & Injuries.
# Covers simulation/pitching.py's real-stats rotation/bullpen construction:
# role classification, injury exclusion (with visibility via .unavailable),
# fallback to the synthetic generator, and the "losing an ace costs more
# than losing a #5" mechanic this whole feature was built for. Hand-built
# RawPlayerRecord fixtures — no network involved.
#
# Run with:  python3 -m unittest discover -s tests   (from the project root)
# ==============================================================================

import random
import unittest
from unittest.mock import patch

from data.exceptions import DataFetchError
from models.pitching_stats import RawPlayerRecord, SeasonPitchingLine
from models.simulation_config import SimulationConfig
from simulation.pitching import (
    build_team_staff,
    bullpen_from_staff,
    default_bullpen_for_team,
    default_rotation_for_team,
    game_win_prob,
    rotation_from_staff,
)

CFG = SimulationConfig()
DODGERS = 'Los Angeles Dodgers'
AS_OF = '2026-07-12'


def _starter(pid: int, name: str, ip: float, so: int, bb: int, hr: int,
             status_code: str = 'A', status_desc: str = 'Active', throws: str | None = None) -> RawPlayerRecord:
    line = SeasonPitchingLine(innings_pitched=ip, strikeouts=so, walks=bb,
                               home_runs=hr, games=max(1, int(ip / 6)), games_started=max(1, int(ip / 6)))
    return RawPlayerRecord(person_id=pid, full_name=name, status_code=status_code,
                            status_description=status_desc, current_season=line, last_30_days=None, career=None,
                            throws=throws)


def _reliever(pid: int, name: str, ip: float, so: int, bb: int, hr: int,
              status_code: str = 'A', status_desc: str = 'Active') -> RawPlayerRecord:
    line = SeasonPitchingLine(innings_pitched=ip, strikeouts=so, walks=bb,
                               home_runs=hr, games=max(1, int(ip / 1.0)), games_started=0)
    return RawPlayerRecord(person_id=pid, full_name=name, status_code=status_code,
                            status_description=status_desc, current_season=line, last_30_days=None, career=None)


class TestRotationFromStaff(unittest.TestCase):
    def test_throwing_hand_is_passed_through_to_pitcher(self) -> None:
        staff = [
            _starter(1, 'Lefty', ip=200, so=250, bb=30, hr=10, throws='L'),
            _starter(2, 'Righty', ip=180, so=170, bb=50, hr=20, throws='R'),
            _starter(3, 'Unknown', ip=160, so=140, bb=55, hr=22, throws=None),
        ]
        rotation = rotation_from_staff(staff, CFG)
        by_name = {p.name: p for p in rotation.starters}
        self.assertEqual(by_name['Lefty'].throws, 'L')
        self.assertEqual(by_name['Righty'].throws, 'R')
        self.assertEqual(by_name['Unknown'].throws, 'R')   #unknown defaults to 'R'

    def test_builds_rotation_ordered_best_first(self) -> None:
        staff = [
            _starter(1, 'Ace', ip=200, so=250, bb=30, hr=10),
            _starter(2, 'Two', ip=180, so=170, bb=50, hr=20),
            _starter(3, 'Three', ip=160, so=140, bb=55, hr=22),
        ]
        rotation = rotation_from_staff(staff, CFG)
        self.assertIsNotNone(rotation)
        names = [p.name for p in rotation.starters]
        self.assertEqual(names[0], 'Ace')
        ratings = [p.rating for p in rotation.starters]
        self.assertEqual(ratings, sorted(ratings, reverse=True))

    def test_injured_starter_is_excluded_from_starters_but_listed_as_unavailable(self) -> None:
        staff = [
            _starter(1, 'Ace', ip=200, so=250, bb=30, hr=10, status_code='IL15', status_desc='15-Day IL'),
            _starter(2, 'Backup', ip=150, so=130, bb=60, hr=25),
        ]
        rotation = rotation_from_staff(staff, CFG)
        names = [p.name for p in rotation.starters]
        self.assertNotIn('Ace', names)
        self.assertIn('Backup', names)
        unavailable_names = [p.name for p in rotation.unavailable]
        self.assertIn('Ace', unavailable_names)

    def test_relievers_are_excluded_from_rotation(self) -> None:
        staff = [
            _starter(1, 'Ace', ip=200, so=250, bb=30, hr=10),
            _reliever(2, 'Closer', ip=65, so=90, bb=15, hr=4),
        ]
        rotation = rotation_from_staff(staff, CFG)
        names = [p.name for p in rotation.starters]
        self.assertNotIn('Closer', names)

    def test_returns_none_when_no_starter_is_available(self) -> None:
        staff = [
            _starter(1, 'Ace', ip=200, so=250, bb=30, hr=10, status_code='IL60', status_desc='60-Day IL'),
        ]
        self.assertIsNone(rotation_from_staff(staff, CFG))

    def test_caps_rotation_at_five(self) -> None:
        staff = [_starter(i, f"SP{i}", ip=150, so=140, bb=50, hr=20) for i in range(8)]
        rotation = rotation_from_staff(staff, CFG)
        self.assertEqual(len(rotation.starters), 5)


class TestBullpenFromStaff(unittest.TestCase):
    def test_builds_bullpen_ordered_best_first_with_leverage(self) -> None:
        staff = [
            _reliever(1, 'Closer', ip=65, so=90, bb=15, hr=4),
            _reliever(2, 'Setup', ip=60, so=70, bb=20, hr=6),
            _reliever(3, 'Mopup', ip=40, so=30, bb=25, hr=10),
        ]
        bullpen = bullpen_from_staff(staff, CFG)
        self.assertIsNotNone(bullpen)
        names = [r.name for r in bullpen.relievers]
        self.assertEqual(names[0], 'Closer')
        leverages = [r.leverage for r in bullpen.relievers]
        self.assertEqual(leverages, sorted(leverages, reverse=True))

    def test_injured_reliever_is_excluded_but_listed_as_unavailable(self) -> None:
        staff = [
            _reliever(1, 'Closer', ip=65, so=90, bb=15, hr=4, status_code='IL15', status_desc='15-Day IL'),
            _reliever(2, 'Setup', ip=60, so=70, bb=20, hr=6),
        ]
        bullpen = bullpen_from_staff(staff, CFG)
        names = [r.name for r in bullpen.relievers]
        self.assertNotIn('Closer', names)
        self.assertIn('Closer', [r.name for r in bullpen.unavailable])

    def test_returns_none_when_no_reliever_is_available(self) -> None:
        staff = [_reliever(1, 'Closer', ip=65, so=90, bb=15, hr=4, status_code='D60', status_desc='60-Day DL')]
        self.assertIsNone(bullpen_from_staff(staff, CFG))


class TestBuildTeamStaffFallback(unittest.TestCase):
    def test_falls_back_to_synthetic_when_stats_disabled(self) -> None:
        cfg = SimulationConfig(use_real_pitcher_stats=False)
        rotation, bullpen = build_team_staff(DODGERS, 119, 1550.0, 2026, AS_OF, cfg)
        expected_rotation = default_rotation_for_team(DODGERS, 1550.0)
        self.assertEqual([p.rating for p in rotation.starters], [p.rating for p in expected_rotation.starters])

    def test_falls_back_to_synthetic_when_fetch_fails(self) -> None:
        with patch('simulation.pitching.fetch_team_pitching_staff', side_effect=DataFetchError('boom')):
            rotation, bullpen = build_team_staff(DODGERS, 119, 1550.0, 2026, AS_OF, CFG)
        expected_rotation = default_rotation_for_team(DODGERS, 1550.0)
        self.assertEqual([p.rating for p in rotation.starters], [p.rating for p in expected_rotation.starters])

    def test_falls_back_to_synthetic_when_no_eligible_starters(self) -> None:
        staff = [_reliever(1, 'Only Reliever', ip=60, so=70, bb=20, hr=6)]
        with patch('simulation.pitching.fetch_team_pitching_staff', return_value=staff):
            rotation, bullpen = build_team_staff(DODGERS, 119, 1550.0, 2026, AS_OF, CFG)
        expected_rotation = default_rotation_for_team(DODGERS, 1550.0)
        self.assertEqual([p.rating for p in rotation.starters], [p.rating for p in expected_rotation.starters])
        #Bullpen, on the other hand, should be REAL since a reliever was available.
        self.assertEqual(bullpen.relievers[0].name, 'Only Reliever')

    def test_uses_real_data_when_available(self) -> None:
        staff = [
            _starter(1, 'Real Ace', ip=200, so=250, bb=30, hr=10),
            _reliever(2, 'Real Closer', ip=65, so=90, bb=15, hr=4),
        ]
        with patch('simulation.pitching.fetch_team_pitching_staff', return_value=staff):
            rotation, bullpen = build_team_staff(DODGERS, 119, 1550.0, 2026, AS_OF, CFG)
        self.assertEqual(rotation.starters[0].name, 'Real Ace')
        self.assertEqual(bullpen.relievers[0].name, 'Real Closer')


class TestInjuryImpactMechanic(unittest.TestCase):
    """The core ask: losing a real ace should swing win probability more
    than losing a real #5 starter, because each arm's own rating (not a
    fixed rotation-slot offset) is what's missing when he's hurt."""

    def _staff(self, injure_who: str | None) -> list[RawPlayerRecord]:
        def status(name: str) -> tuple[str, str]:
            if name == injure_who:
                return ('IL15', '15-Day IL')
            return ('A', 'Active')

        ace_status = status('Ace')
        fifth_status = status('Five')
        return [
            _starter(1, 'Ace', ip=200, so=260, bb=25, hr=8, status_code=ace_status[0], status_desc=ace_status[1]),
            _starter(2, 'Two', ip=180, so=190, bb=45, hr=15),
            _starter(3, 'Three', ip=170, so=160, bb=55, hr=20),
            _starter(4, 'Four', ip=150, so=120, bb=65, hr=25),
            _starter(5, 'Five', ip=140, so=100, bb=70, hr=28, status_code=fifth_status[0], status_desc=fifth_status[1]),
            _starter(6, 'Six', ip=120, so=90, bb=75, hr=30),   #depth arm behind the rotation
        ]

    def test_losing_the_ace_costs_more_win_probability_than_losing_the_five(self) -> None:
        healthy = rotation_from_staff(self._staff(injure_who=None), CFG)
        ace_hurt = rotation_from_staff(self._staff(injure_who='Ace'), CFG)
        five_hurt = rotation_from_staff(self._staff(injure_who='Five'), CFG)

        healthy_game1_rating = healthy.starter_for_game(0).rating
        ace_hurt_game1_rating = ace_hurt.starter_for_game(0).rating
        five_hurt_game1_rating = five_hurt.starter_for_game(0).rating

        #Losing the ace changes who starts Game 1; losing the #5 shouldn't.
        drop_from_losing_ace = healthy_game1_rating - ace_hurt_game1_rating
        drop_from_losing_five = healthy_game1_rating - five_hurt_game1_rating

        self.assertGreater(drop_from_losing_ace, drop_from_losing_five)

        #And translate that into an actual win-probability swing via the
        #same game_win_prob the sim uses everywhere else.
        baseline_wp = game_win_prob(1500, 1500, healthy_game1_rating, 1500, 0.0, 0.0, CFG)
        ace_hurt_wp = game_win_prob(1500, 1500, ace_hurt_game1_rating, 1500, 0.0, 0.0, CFG)
        five_hurt_wp = game_win_prob(1500, 1500, five_hurt_game1_rating, 1500, 0.0, 0.0, CFG)

        self.assertGreater(baseline_wp - ace_hurt_wp, baseline_wp - five_hurt_wp)


if __name__ == '__main__':
    unittest.main()
