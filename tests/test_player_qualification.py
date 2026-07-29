# ==============================================================================
# TEST: PLAYER QUALIFICATION
# tests/test_player_qualification.py
#
# Covers gui/player_tab/qualification.py's MLB-standard qualification bar
# (3.1 PA / team game for hitters, 1.0 IP / team game for pitchers).
# ==============================================================================

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from gui.player_tab.qualification import filter_qualified_hitters, filter_qualified_pitchers


def _result(win_loss: dict, projected_win_loss: dict | None = None) -> MagicMock:
    #a minimal stand-in for SimulationResult exposing just the two methods qualification.py actually calls
    result = MagicMock()
    result.win_loss.side_effect = lambda team: win_loss[team]
    result.projected_win_loss.side_effect = lambda team: (projected_win_loss or win_loss)[team]
    return result


class TestFilterQualifiedPitchers(unittest.TestCase):
    def test_keeps_pitchers_at_or_above_one_ip_per_team_game(self) -> None:
        result = _result({'Dodgers': (60, 40)})
        rows = [
            {'team': 'Dodgers', 'ip': 100.0},   #100 games played, 100 IP -> qualified
            {'team': 'Dodgers', 'ip': 99.9},    #just short -> not qualified
        ]
        kept = filter_qualified_pitchers(rows, result, simulated=False)
        self.assertEqual([r['ip'] for r in kept], [100.0])

    def test_uses_projected_games_when_simulated(self) -> None:
        result = _result({'Dodgers': (60, 40)}, projected_win_loss={'Dodgers': (100.0, 62.0)})
        rows = [{'team': 'Dodgers', 'ip': 150.0}]   #150 IP against a 162-game projection -> not qualified
        self.assertEqual(filter_qualified_pitchers(rows, result, simulated=True), [])

    def test_team_with_no_games_played_is_excluded(self) -> None:
        result = _result({'Dodgers': (0, 0)})
        rows = [{'team': 'Dodgers', 'ip': 5.0}]
        self.assertEqual(filter_qualified_pitchers(rows, result, simulated=False), [])

    def test_missing_ip_treated_as_zero(self) -> None:
        result = _result({'Dodgers': (10, 0)})
        rows = [{'team': 'Dodgers', 'ip': None}]
        self.assertEqual(filter_qualified_pitchers(rows, result, simulated=False), [])


class TestFilterQualifiedHitters(unittest.TestCase):
    def test_keeps_hitters_at_or_above_3_1_pa_per_team_game(self) -> None:
        result = _result({'Dodgers': (50, 50)})   #100 team games -> needs 310 PA
        rows = [
            {'team': 'Dodgers', 'pa': 310},
            {'team': 'Dodgers', 'pa': 309},
        ]
        kept = filter_qualified_hitters(rows, result, simulated=False)
        self.assertEqual([r['pa'] for r in kept], [310])

    def test_missing_pa_treated_as_zero(self) -> None:
        result = _result({'Dodgers': (10, 0)})
        rows = [{'team': 'Dodgers', 'pa': None}]
        self.assertEqual(filter_qualified_hitters(rows, result, simulated=False), [])


if __name__ == '__main__':
    unittest.main()
