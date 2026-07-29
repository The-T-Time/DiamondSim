# ==============================================================================
# STAT COMPUTATION
# gui/stats_tab/stat_computation.py
#
# Walks played_games once and derives every stat needed by all four
# Statistics sub-tabs. No Tkinter here — unit-testable on its own.
# ==============================================================================

from __future__ import annotations

from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.simulation_result import SimulationResult


def _pct(w: int, l: int) -> float:
    return w / (w + l) if (w + l) else 0.0


def compute_all_stats(result: SimulationResult, simulated: bool = False) -> dict[str, dict]:
    """
    Walk played_games once and build every stat needed by all four sub-tabs.
    Returns {team_name: {stat_key: value}}.

    simulated=True overrides W/L/RS/RA/RD/RS_G/RA_G/PCT/PYTH*/LUCK with the
    projected (averaged-across-every-simulation) values from
    result.projected_team_stats, for teams where a projection exists.
    Splits (home/away), streak, and recent-form fields have no simulated
    analog — they describe specific actual games, not an average outcome —
    so they're left as current values in both modes.
    """
    stats: dict[str, dict] = {t: {
        'W': 0, 'L': 0, 'G': 0,
        'RS': 0, 'RA': 0,
        'home_W': 0, 'home_L': 0,
        'away_W': 0, 'away_L': 0,
        'results': [],        #'W'/'L' in chronological order
    } for t in ALL_TEAMS}

    for game in sorted(result.played_games, key=lambda g: g.date):
        home   = game.home
        away   = game.away
        winner = game.winner
        loser  = game.loser
        hs     = game.home_score or 0
        aw     = game.away_score or 0

        for t in (home, away):
            stats[t]['G'] += 1
        if winner and loser:
            stats[winner]['W'] += 1
            stats[loser]['L']  += 1
            stats[winner]['results'].append('W')
            stats[loser]['results'].append('L')

        stats[home]['RS'] += hs;  stats[home]['RA'] += aw
        stats[away]['RS'] += aw;  stats[away]['RA'] += hs

        if winner == home:
            stats[home]['home_W'] += 1;  stats[away]['away_L'] += 1
        elif loser == home:
            stats[home]['home_L'] += 1;  stats[away]['away_W'] += 1

    for t, s in stats.items():
        if simulated:
            proj = result.projected_team_stats.get(t)
            if proj is not None:
                s['W']  = proj['wins']
                s['L']  = proj['losses']
                s['G']  = proj['wins'] + proj['losses']
                s['RS'] = proj['runs_scored']
                s['RA'] = proj['runs_allowed']

        g  = max(s['G'], 1)
        rs, ra, w = s['RS'], s['RA'], s['W']

        #── Run stats ─────────────────────────────────────────────────────────
        s['RD']    = rs - ra
        s['RS_G']  = rs / g
        s['RA_G']  = ra / g
        s['PCT']   = _pct(w, s['L'])

        #Pythagorean expectation (exponent 1.83 more accurate than 2 for MLB)
        denom        = rs**1.83 + ra**1.83
        s['PYTH']    = (rs**1.83 / denom) if denom > 0 else 0.5
        s['PYTH_W']  = round(s['PYTH'] * g)
        s['PYTH_L']  = g - s['PYTH_W']
        s['LUCK']    = w - s['PYTH_W']     #+ve = outperforming run differential

        #── Streaks & recent form ─────────────────────────────────────────────
        res = s['results']
        if res:
            char, cnt = res[-1], 0
            for r in reversed(res):
                if r == char: cnt += 1
                else: break
            s['STREAK']    = f"{char}{cnt}"
            s['STREAK_VAL'] = cnt if char == 'W' else -cnt   #for numeric sort
        else:
            s['STREAK']     = '—'
            s['STREAK_VAL'] = 0

        last10        = res[-10:]
        w10           = last10.count('W')
        s['LAST10']   = f"{w10}-{len(last10)-w10}" if last10 else '—'
        s['LAST10_W'] = w10

        mx, cur = 0, 0
        for r in res:
            if r == 'W': cur += 1; mx = max(mx, cur)
            else: cur = 0
        s['LONG_W'] = mx

        #── Home / Away ───────────────────────────────────────────────────────
        s['HOME_REC'] = f"{s['home_W']}-{s['home_L']}"
        s['HOME_PCT'] = _pct(s['home_W'], s['home_L'])
        s['AWAY_REC'] = f"{s['away_W']}-{s['away_L']}"
        s['AWAY_PCT'] = _pct(s['away_W'], s['away_L'])

        #── Elo ───────────────────────────────────────────────────────────────
        s['ELO']       = result.live_elo.get(t, 1500.0)
        s['ELO_DELTA'] = s['ELO'] - 1500.0
        s['ODDS']      = result.playoff_odds.get(t, 0.0)

    return stats


def rows_from_stats(stats: dict[str, dict]) -> list[dict]:
    """Flatten {team: stats} into row dicts the SortableTable can render.

    Each row carries 'team'/'_team' (search + display), plus 'league'/'div'
    for the filter dropdown. '_rank' is injected per-render by the widget."""
    rows: list[dict] = []
    for t in ALL_TEAMS:
        row = dict(stats[t])
        row['team']   = t
        row['_team']  = t
        row['league'] = TEAM_REGISTRY[t].league
        row['div']    = TEAM_REGISTRY[t].division
        rows.append(row)
    return rows
