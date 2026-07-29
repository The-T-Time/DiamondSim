# ==============================================================================
# tests/test_tiebreakers.py
# ==============================================================================

import unittest
from collections import defaultdict

from simulation.tiebreakers import run_mlb_tiebreaker

#Real team names so division/league lookups in tiebreakers.py resolve correctly.
DODGERS = 'Los Angeles Dodgers'   #NL West
PADRES  = 'San Diego Padres'      #NL West (same division as Dodgers)
BRAVES  = 'Atlanta Braves'        #NL East (same league as Dodgers, other div)
YANKEES = 'New York Yankees'      #AL East (different league entirely)
RAYS    = 'Tampa Bay Rays'        #AL East (same division as Yankees)


def _blank_record() -> dict:
    return {'W': 0, 'L': 0, 'div_W': 0, 'div_L': 0,
            'league_W': 0, 'league_L': 0, 'league_results': []}


def _h2h(pairs: dict) -> dict:
    """Build an H2H table from {(winner, loser): count} entries."""
    from data.teams import ALL_TEAMS
    table = {t: defaultdict(int) for t in ALL_TEAMS}
    for (w, l), n in pairs.items():
        table[w][l] += n
    return table


class TestHeadToHeadTiebreaker(unittest.TestCase):
    def test_head_to_head_winner_ranked_first(self) -> None:
        """Two teams tied on wins; Dodgers beat Padres more often head-to-head."""
        records = {DODGERS: _blank_record(), PADRES: _blank_record()}
        h2h = {DODGERS: defaultdict(int), PADRES: defaultdict(int)}
        h2h[DODGERS][PADRES] = 4
        h2h[PADRES][DODGERS] = 2

        result = run_mlb_tiebreaker([DODGERS, PADRES], records, h2h)
        self.assertEqual(result[0], DODGERS)

    def test_single_team_returns_unchanged(self) -> None:
        records = {DODGERS: _blank_record()}
        h2h = {DODGERS: defaultdict(int)}
        self.assertEqual(run_mlb_tiebreaker([DODGERS], records, h2h), [DODGERS])

    def test_empty_list_returns_empty(self) -> None:
        self.assertEqual(run_mlb_tiebreaker([], {}, {}), [])


class TestDivisionRecordTiebreaker(unittest.TestCase):
    def test_falls_back_to_division_record_when_h2h_is_even(self) -> None:
        """Same-division teams, dead-even head-to-head; better division record wins."""
        records = {
            DODGERS: {**_blank_record(), 'div_W': 40, 'div_L': 20},
            PADRES:  {**_blank_record(), 'div_W': 30, 'div_L': 30},
        }
        h2h = {DODGERS: defaultdict(int), PADRES: defaultdict(int)}
        h2h[DODGERS][PADRES] = 3
        h2h[PADRES][DODGERS] = 3

        result = run_mlb_tiebreaker([DODGERS, PADRES], records, h2h)
        self.assertEqual(result[0], DODGERS)


class TestLeagueRecordTiebreaker(unittest.TestCase):
    def test_falls_back_to_league_record_across_divisions(self) -> None:
        """Teams from different divisions/leagues can't share a division record,
        so an even h2h record should fall through to league record."""
        records = {
            YANKEES: {**_blank_record(), 'league_W': 50, 'league_L': 30},
            DODGERS: {**_blank_record(), 'league_W': 40, 'league_L': 40},
        }
        h2h = {YANKEES: defaultdict(int), DODGERS: defaultdict(int)}
        #No head-to-head games at all between AL/NL teams in this scenario.
        result = run_mlb_tiebreaker([YANKEES, DODGERS], records, h2h)
        self.assertEqual(result[0], YANKEES)

    def test_same_division_pair_does_not_use_league_record_prematurely(self) -> None:
        """Rays/Yankees share a division, so a division-record edge should decide
        it before league record is ever consulted."""
        records = {
            YANKEES: {**_blank_record(), 'div_W': 45, 'div_L': 15, 'league_W': 10, 'league_L': 50},
            RAYS:    {**_blank_record(), 'div_W': 20, 'div_L': 40, 'league_W': 60, 'league_L': 0},
        }
        h2h = {YANKEES: defaultdict(int), RAYS: defaultdict(int)}
        h2h[YANKEES][RAYS] = 3
        h2h[RAYS][YANKEES] = 3

        result = run_mlb_tiebreaker([YANKEES, RAYS], records, h2h)
        #Yankees have the far better division record despite a worse league record.
        self.assertEqual(result[0], YANKEES)


class TestIntradivisionAlwaysApplies(unittest.TestCase):
    """The 2022+ rule: each club's OWN-division winning pct is the second
    criterion even for a cross-division tie — not only when both share a
    division. Two NL clubs from different divisions, even h2h, must be
    separated by their respective intradivision records before league record."""

    def test_cross_division_uses_own_division_pct(self) -> None:
        records = {
            DODGERS: {**_blank_record(), 'div_W': 40, 'div_L': 20,   #.667
                      'league_W': 50, 'league_L': 50},
            BRAVES:  {**_blank_record(), 'div_W': 20, 'div_L': 40,   #.333
                      'league_W': 50, 'league_L': 50},               #league even
        }
        h2h = _h2h({(DODGERS, BRAVES): 3, (BRAVES, DODGERS): 3})     #h2h even
        result = run_mlb_tiebreaker([DODGERS, BRAVES], records, h2h)
        self.assertEqual(result[0], DODGERS)


class TestLastHalfTiebreaker(unittest.TestCase):
    """When h2h, intradivision and intraleague records are all even, the last
    half of intraleague games decides it."""

    def test_last_half_of_intraleague_decides(self) -> None:
        records = {
            DODGERS: {**_blank_record(), 'div_W': 10, 'div_L': 10,
                      'league_W': 2, 'league_L': 2,
                      'league_results': [0, 0, 1, 1]},   #last half [1,1] = 1.000
            PADRES:  {**_blank_record(), 'div_W': 10, 'div_L': 10,
                      'league_W': 2, 'league_L': 2,
                      'league_results': [1, 1, 0, 0]},   #last half [0,0] = 0.000
        }
        h2h = _h2h({(DODGERS, PADRES): 3, (PADRES, DODGERS): 3})
        result = run_mlb_tiebreaker([DODGERS, PADRES], records, h2h)
        self.assertEqual(result[0], DODGERS)


class TestPlusOneWalkback(unittest.TestCase):
    """If the last half itself ties, the window expands one older game at a
    time until the tie breaks."""

    def test_walkback_expands_until_separation(self) -> None:
        #Last three games identical; sequences differ only at index 0, so the
        #walkback must expand all the way back to the first game to separate.
        records = {
            DODGERS: {**_blank_record(), 'div_W': 10, 'div_L': 10,
                      'league_W': 3, 'league_L': 3,
                      'league_results': [1, 0, 0, 1, 0, 0]},
            PADRES:  {**_blank_record(), 'div_W': 10, 'div_L': 10,
                      'league_W': 3, 'league_L': 3,
                      'league_results': [0, 0, 0, 1, 0, 0]},
        }
        h2h = _h2h({(DODGERS, PADRES): 3, (PADRES, DODGERS): 3})
        result = run_mlb_tiebreaker([DODGERS, PADRES], records, h2h)
        self.assertEqual(result[0], DODGERS)


class TestDeterministicFallback(unittest.TestCase):
    """Every official criterion ties → deterministic total order: overall
    winning pct, then team name. The result is stable and reproducible."""

    def test_identical_records_fall_back_to_overall_then_name(self) -> None:
        base = {**_blank_record(), 'div_W': 10, 'div_L': 10,
                'league_W': 2, 'league_L': 2, 'league_results': [1, 0, 1, 0]}
        records = {
            DODGERS: {**base, 'W': 90, 'L': 72},   #better overall pct
            PADRES:  {**base, 'W': 81, 'L': 81},
        }
        h2h = _h2h({(DODGERS, PADRES): 3, (PADRES, DODGERS): 3})
        result = run_mlb_tiebreaker([DODGERS, PADRES], records, h2h)
        self.assertEqual(result, [DODGERS, PADRES])

    def test_total_tie_orders_by_name(self) -> None:
        base = {**_blank_record(), 'W': 81, 'L': 81, 'div_W': 10, 'div_L': 10,
                'league_W': 2, 'league_L': 2, 'league_results': [1, 0, 1, 0]}
        records = {DODGERS: dict(base), PADRES: dict(base)}
        h2h = _h2h({(DODGERS, PADRES): 3, (PADRES, DODGERS): 3})
        result = run_mlb_tiebreaker([DODGERS, PADRES], records, h2h)
        self.assertEqual(result, sorted([DODGERS, PADRES]))   #'Los...' < 'San...'


class TestMultiTeamTie(unittest.TestCase):
    """Three-club tie: a club that beats every other tied club ranks first; a
    club that loses to every other ranks last."""

    def test_sweeper_first_swept_last(self) -> None:
        teams = [DODGERS, PADRES, BRAVES]
        records = {t: {**_blank_record(), 'div_W': 10, 'div_L': 10} for t in teams}
        #DODGERS beat both others; BRAVES lost to both others.
        h2h = _h2h({
            (DODGERS, PADRES): 4, (PADRES, DODGERS): 2,
            (DODGERS, BRAVES): 4, (BRAVES, DODGERS): 2,
            (PADRES, BRAVES): 4, (BRAVES, PADRES): 2,
        })
        result = run_mlb_tiebreaker(teams, records, h2h)
        self.assertEqual(result[0], DODGERS)
        self.assertEqual(result[-1], BRAVES)

    def test_result_is_a_total_order_permutation(self) -> None:
        teams = [DODGERS, PADRES, BRAVES, YANKEES]
        records = {t: _blank_record() for t in teams}
        result = run_mlb_tiebreaker(teams, records, _h2h({}))
        self.assertEqual(sorted(result), sorted(teams))   #every team exactly once


if __name__ == '__main__':
    unittest.main()
