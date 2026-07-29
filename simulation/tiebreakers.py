# ==============================================================================
# TIEBREAKER
# simulation/tiebreakers.py
#
# Implements MLB's official (2022+, no Game 163) tiebreaker cascade —
# head-to-head, intradivision record, intraleague record, last-half
# intraleague record, then a deterministic fallback — as a total order
# over any set of tied clubs, including multi-club ties.
# ==============================================================================

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Optional

from models.team import TeamName, TeamRecord

RecordTable = dict[TeamName, TeamRecord]
H2HTable = dict[TeamName, "DefaultDict[TeamName, int]"]

#Fixed cascade level indices.
_LVL_H2H = 0
_LVL_DIV = 1
_LVL_LEAGUE = 2
_LVL_LAST_HALF = 3   #and every level beyond is the plus-one walkback


def _pct(w: int, l: int) -> float:
    return w / (w + l) if (w + l) > 0 else 0.5


def _get_div_pct(team: TeamName, records: RecordTable) -> float:
    r = records[team]
    return _pct(r['div_W'], r['div_L'])


def _get_league_pct(team: TeamName, records: RecordTable) -> float:
    r = records[team]
    return _pct(r['league_W'], r['league_L'])


def _overall_pct(team: TeamName, records: RecordTable) -> float:
    r = records[team]
    return _pct(r['W'], r['L'])


def _league_results(team: TeamName, records: RecordTable) -> list[int]:
    #.get keeps older/simpler record dicts (e.g. in unit tests that only need
    #levels 1-3) working without a KeyError when the walkback is never reached.
    return records[team].get('league_results', [])  #type: ignore[attr-defined]


def _window_pct(results: list[int], back: int) -> float:
    """Winning pct over the last-half window expanded `back` games earlier.

    back=0 is exactly the last half of the sequence; back=1 adds the single
    game immediately before the half point, and so on."""
    n = len(results)
    if n == 0:
        return 0.5
    start = max(0, n // 2 - back)
    window = results[start:]
    return sum(window) / len(window) if window else 0.5


def _h2h_score(team: TeamName, group: list[TeamName], h2h: H2HTable) -> float:
    """Combined head-to-head winning pct among the tied `group`, with the
    official sweep rule layered on top: a club with a winning record against
    every other tied club it has played ranks strictly first (score 2.0); one
    with a losing record against every such club ranks strictly last (-1.0)."""
    wins = total = 0
    played_any = False
    beat_all = lost_all = True
    for opp in group:
        if opp == team:
            continue
        w = h2h[team][opp]
        l = h2h[opp][team]
        wins += w
        total += w + l
        if w + l == 0:
            continue                       #never played — ignore for sweep test
        played_any = True
        if not (w > l):
            beat_all = False
        if not (l > w):
            lost_all = False
    if played_any and beat_all:
        return 2.0
    if played_any and lost_all:
        return -1.0
    return wins / total if total > 0 else 0.5


def _score_at_level(
    level: int, group: list[TeamName], records: RecordTable, h2h: H2HTable
) -> Optional[dict[TeamName, float]]:
    """Score every club in `group` for a given cascade level (higher = better),
    or return None when the walkback is exhausted (caller falls back to the
    deterministic total-order tiebreak)."""
    if level == _LVL_H2H:
        return {t: _h2h_score(t, group, h2h) for t in group}
    if level == _LVL_DIV:
        return {t: _get_div_pct(t, records) for t in group}
    if level == _LVL_LEAGUE:
        return {t: _get_league_pct(t, records) for t in group}

    #level >= _LVL_LAST_HALF: last-half intraleague, then plus-one walkback.
    back = level - _LVL_LAST_HALF
    max_back = max((len(_league_results(t, records)) // 2 for t in group), default=0)
    if back > max_back:
        return None
    return {t: _window_pct(_league_results(t, records), back) for t in group}


def _resolve(
    group: list[TeamName], records: RecordTable, h2h: H2HTable, level: int = 0
) -> list[TeamName]:
    """Order `group` best-to-worst, descending the cascade from `level`.

    Progress (and therefore termination) is guaranteed: at each step we either
    advance the level with the same group, or split into strictly smaller
    subgroups that restart the cascade from the top.  The final fallback splits
    on team name, which is unique, so we always bottom out at singletons."""
    if len(group) <= 1:
        return list(group)

    scores = _score_at_level(level, group, records, h2h)
    if scores is None:
        #Official criteria exhausted — impose a deterministic total order.
        return sorted(group, key=lambda t: (-_overall_pct(t, records), t))

    buckets: DefaultDict[float, list[TeamName]] = defaultdict(list)
    for t in group:
        buckets[scores[t]].append(t)

    ordered = sorted(buckets.keys(), reverse=True)
    if len(ordered) == 1:
        #This level didn't separate anyone; move to the next criterion.
        return _resolve(group, records, h2h, level + 1)

    result: list[TeamName] = []
    for s in ordered:
        sub = buckets[s]
        if len(sub) == 1:
            result.append(sub[0])
        else:
            #Smaller subgroup — restart the whole cascade for it (head-to-head
            #among just these clubs, then division, ...).
            result.extend(_resolve(sub, records, h2h, 0))
    return result


def run_mlb_tiebreaker(
    teams: list[TeamName], records: RecordTable, h2h_matrix: H2HTable
) -> list[TeamName]:
    """Return `teams` as a fully ordered list (best first) per the official MLB
    tiebreaker cascade. The ordering is a total order and reproducible for any
    input, so callers can safely take [0] as the unique winner."""
    if len(teams) <= 1:
        return list(teams)
    return _resolve(list(teams), records, h2h_matrix, 0)
