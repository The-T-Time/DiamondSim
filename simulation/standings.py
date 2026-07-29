# ==============================================================================
# STANDINGS
# simulation/standings.py
#
# Turns played games into per-team records and resolves the playoff field
# (division winners, Wild Cards, seeding) from those records. Kept
# separate from simulator.py/playoff_simulator.py so both can depend on
# it without a circular import between each other.
# ==============================================================================

from __future__ import annotations

from collections import defaultdict

from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.game import Game
from models.team import TeamName, TeamRecord
from simulation.tiebreakers import run_mlb_tiebreaker

Standings = dict[TeamName, dict[str, int]]          #{team: {'W': int, 'L': int}}
RecordTable = dict[TeamName, TeamRecord]
H2HTable = dict[TeamName, "defaultdict[TeamName, int]"]


def division_of(team: TeamName) -> str:
    return TEAM_REGISTRY[team].division


def league_of(team: TeamName) -> str:
    return TEAM_REGISTRY[team].league


def build_base_records(
    played_games: list[Game], live_standings: Standings
) -> tuple[RecordTable, H2HTable]:
    """Seed W/L, division, league, and head-to-head records from played games."""
    base_h2h: H2HTable = {t: defaultdict(int) for t in ALL_TEAMS}
    base_rec: RecordTable = {
        t: {
            'W': live_standings[t]['W'],
            'L': live_standings[t]['L'],
            'div_W': 0,
            'div_L': 0,
            'league_W': 0,
            'league_L': 0,
            'league_results': [],
        }
        for t in ALL_TEAMS
    }
    #played_games arrive date-sorted from the parser; keep that order so each
    #team's league_results reads chronologically for the last-half tiebreaker.
    for g in played_games:
        home, away = g.home, g.away
        w, l = g.winner, g.loser
        base_h2h[w][l] += 1
        if division_of(home) == division_of(away):
            base_rec[w]['div_W'] += 1
            base_rec[l]['div_L'] += 1
        if league_of(home) == league_of(away):
            base_rec[w]['league_W'] += 1
            base_rec[l]['league_L'] += 1
            base_rec[w]['league_results'].append(1)
            base_rec[l]['league_results'].append(0)
    return base_rec, base_h2h


def resolve_league_playoff_teams(
    records: RecordTable, h2h: H2HTable, league: str
) -> tuple[list[TeamName], list[TeamName]]:
    """Return (division_winners, wild_card_teams) for one league."""
    l_teams = [t for t in ALL_TEAMS if league_of(t) == league]
    divisions = (
        ['AL East', 'AL Central', 'AL West']
        if league == 'AL'
        else ['NL East', 'NL Central', 'NL West']
    )
    div_winners: list[TeamName] = []
    for div in divisions:
        d_teams = [t for t in l_teams if division_of(t) == div]
        max_wins = max(records[t]['W'] for t in d_teams)
        top = [t for t in d_teams if records[t]['W'] == max_wins]
        div_winners.append(run_mlb_tiebreaker(top, records, h2h)[0])

    wc_pool = [t for t in l_teams if t not in div_winners]
    wc_sorted: list[TeamName] = []
    wg: dict[int, list[TeamName]] = defaultdict(list)
    for t in wc_pool:
        wg[records[t]['W']].append(t)
    for wc in sorted(wg.keys(), reverse=True):
        tied = wg[wc]
        if len(tied) == 1:
            wc_sorted.append(tied[0])
        else:
            wc_sorted.extend(run_mlb_tiebreaker(tied, records, h2h))
    return div_winners, wc_sorted[:3]


def order_by_record(
    teams: list[TeamName], records: RecordTable, h2h: H2HTable
) -> list[TeamName]:
    """Order `teams` best-to-worst by wins, breaking ties with the official
    tiebreaker so the result is a stable total order (used for seeding)."""
    by_wins: dict[int, list[TeamName]] = defaultdict(list)
    for t in teams:
        by_wins[records[t]['W']].append(t)
    ordered: list[TeamName] = []
    for w in sorted(by_wins.keys(), reverse=True):
        tied = by_wins[w]
        ordered.extend(tied if len(tied) == 1 else run_mlb_tiebreaker(tied, records, h2h))
    return ordered


def seed_league(records: RecordTable, h2h: H2HTable, league: str) -> list[TeamName]:
    """Return one league's six playoff clubs in seed order (index 0 = seed 1).

    Seeds 1-3 are the division winners ranked by record; seeds 4-6 are the
    wild cards ranked by record. Seeds 1 and 2 get a bye to the Division
    Series; seed 3 hosts the wild-card round."""
    div_winners, wc_teams = resolve_league_playoff_teams(records, h2h, league)
    seeds = order_by_record(div_winners, records, h2h)      #seeds 1-3
    seeds += order_by_record(wc_teams, records, h2h)         #seeds 4-6
    return seeds
