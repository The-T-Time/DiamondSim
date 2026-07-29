# ==============================================================================
# STANDINGS COMPUTATION
# gui/standings_tab/standings_computation.py
#
# Pure computation — no Tk widgets. Division/wild-card standings, streaks,
# games-back, and playoff-picture status, all derived from a
# SimulationResult.
# ==============================================================================

from __future__ import annotations

from config import ELIM_ODDS_THRESHOLD, WC_SPOTS
from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.game import Game
from models.simulation_result import SimulationResult
from gui.widgets import C_DARK, C_DIV_LEAD, C_GRAY, C_ROW_ALT, C_WC_IN, C_WHITE

LEAGUE_DIVS: dict[str, list[str]] = {
    'AL': ['AL East', 'AL Central', 'AL West'],
    'NL': ['NL East', 'NL Central', 'NL West'],
}


def team_game_results(played_games: list[Game]) -> dict[str, list[str]]:
    """Returns {team: ['W','L',...]} in chronological order."""
    results: dict[str, list[str]] = {t: [] for t in ALL_TEAMS}
    for g in sorted(played_games, key=lambda g: g.date):
        w = g.winner
        for t in (g.home, g.away):
            if t in results:
                results[t].append('W' if t == w else 'L')
    return results


def last10(game_results: list[str]) -> str:
    last = game_results[-10:]
    w    = last.count('W')
    return f"{w}-{len(last)-w}"


def streak(game_results: list[str]) -> str:
    if not game_results:
        return '—'
    char, count = game_results[-1], 0
    for r in reversed(game_results):
        if r == char:
            count += 1
        else:
            break
    return f"{char}{count}"


def games_back(leader_w: int, leader_l: int, team_w: int, team_l: int) -> str:
    val = ((leader_w - team_w) + (team_l - leader_l)) / 2
    if val <= 0:
        return '—'
    return f"{val:.1f}" if val != int(val) else str(int(val))


def sort_key(result: SimulationResult, team: str, simulated: bool = False) -> tuple[float, float]:
    if simulated:
        return result.projected_pct(team), result.projected_win_loss(team)[0]
    return result.pct(team), result.win_loss(team)[0]


def division_rows(result: SimulationResult, division: str, game_results: dict,
                  simulated: bool = False) -> list[dict]:
    teams = sorted(
        [t for t in ALL_TEAMS if TEAM_REGISTRY[t].division == division],
        key=lambda t: sort_key(result, t, simulated), reverse=True,
    )
    win_loss = result.projected_win_loss if simulated else result.win_loss
    pct = result.projected_pct if simulated else result.pct
    lw, ll = win_loss(teams[0])
    rows = []
    for t in teams:
        w, l = win_loss(t)
        rows.append({
            'team':   t,
            'w': w,   'l': l,
            'pct':    pct(t),
            'gb':     games_back(lw, ll, w, l),
            'last10': last10(game_results.get(t, [])),
            'streak': streak(game_results.get(t, [])),
            'odds':   result.playoff_odds.get(t, 0.0),
        })
    return rows


def wildcard_rows(result: SimulationResult, league: str,
                  div_leaders: list[str], game_results: dict,
                  simulated: bool = False) -> list[dict]:
    pool = sorted(
        [t for t in ALL_TEAMS
         if TEAM_REGISTRY[t].league == league and t not in div_leaders],
        key=lambda t: sort_key(result, t, simulated), reverse=True,
    )
    if not pool:
        return []
    win_loss = result.projected_win_loss if simulated else result.win_loss
    pct = result.projected_pct if simulated else result.pct
    wc1_w, wc1_l = win_loss(pool[0])
    rows = []
    for i, t in enumerate(pool):
        w, l = win_loss(t)
        rows.append({
            'team':    t,
            'div':     TEAM_REGISTRY[t].division,
            'w': w,    'l': l,
            'pct':     pct(t),
            'wcgb':    '—' if i == 0 else games_back(wc1_w, wc1_l, w, l),
            'in_spot': i < WC_SPOTS,
            'odds':    result.playoff_odds.get(t, 0.0),
        })
    return rows


def compute_playoff_picture(result: SimulationResult, simulated: bool = False) -> dict[str, str]:
    """Returns {team: 'div_leader'|'wc_in'|'contender'|'eliminated'}."""
    picture: dict[str, str] = {}
    for league in ('AL', 'NL'):
        l_teams     = [t for t in ALL_TEAMS if TEAM_REGISTRY[t].league == league]
        div_leaders = []
        for div in LEAGUE_DIVS[league]:
            d_teams = sorted([t for t in l_teams if TEAM_REGISTRY[t].division == div],
                             key=lambda t: sort_key(result, t, simulated), reverse=True)
            div_leaders.append(d_teams[0])
            picture[d_teams[0]] = 'div_leader'
        wc_pool = sorted([t for t in l_teams if t not in div_leaders],
                         key=lambda t: sort_key(result, t, simulated), reverse=True)
        for i, t in enumerate(wc_pool):
            if i < WC_SPOTS:
                picture[t] = 'wc_in'
            elif result.playoff_odds.get(t, 0) >= ELIM_ODDS_THRESHOLD:
                picture[t] = 'contender'
            else:
                picture[t] = 'eliminated'
    return picture


def row_bg(status: str, row_index: int) -> str:
    if status == 'div_leader': return C_DIV_LEAD
    if status == 'wc_in':      return C_WC_IN
    return C_WHITE if row_index % 2 == 0 else C_ROW_ALT


def row_fg(status: str) -> str:
    return C_GRAY if status == 'eliminated' else C_DARK
