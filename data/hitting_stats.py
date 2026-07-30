# ==============================================================================
# HITTING STATS
# data/hitting_stats.py
#
# Fetches a team's roster plus season/last-30-days/career/platoon-split
# hitting stats from the MLB Stats API and parses it into RawHitterRecord
# objects. The hitting-side counterpart to data/player_stats.py — same
# structure, same short-TTL disk cache.
# ==============================================================================

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from typing import Any

from config import ROSTER_CACHE_EXPIRY_SECONDS
from data.api import (
    fetch_people_career_hitting_stats_raw,
    fetch_people_last_30_days_hitting_stats_raw,
    fetch_people_split_hitting_stats_raw,
    fetch_team_hitting_roster_raw,
)
from data.cache_store import get_entry, set_entry
from data.exceptions import DataFetchError
from models.hitting_stats import RawHitterRecord, SeasonHittingLine
from utils.logger import get_logger

logger = get_logger(__name__)

#MLB Stats API position code for pitcher — used here to EXCLUDE pitchers,
#the opposite filter from data/player_stats.py, which includes only them.
_PITCHER_POSITION_CODE = '1'

#How many days back the "recent form" window looks from the as-of date.
LAST_30_DAYS_WINDOW: int = 30


def _parse_stat_to_line(stat: dict) -> SeasonHittingLine:
    return SeasonHittingLine(
        plate_appearances=int(stat.get('plateAppearances', 0)),
        at_bats=int(stat.get('atBats', 0)),
        hits=int(stat.get('hits', 0)),
        doubles=int(stat.get('doubles', 0)),
        triples=int(stat.get('triples', 0)),
        home_runs=int(stat.get('homeRuns', 0)),
        walks=int(stat.get('baseOnBalls', 0)),
        hit_by_pitch=int(stat.get('hitByPitch', 0)),
        strikeouts=int(stat.get('strikeOuts', 0)),
        sac_flies=int(stat.get('sacFlies', 0)),
        games=int(stat.get('gamesPlayed', 0)),
    )


def _parse_season_line(person: dict, season: int, name_for_log: str = '?') -> SeasonHittingLine | None:
    """Pulls the hitting-group stat split matching `season` out of a
    hydrated person object's `stats` list, or None if there's no hitting
    stats for that season."""
    for group in person.get('stats', []):
        for split in group.get('splits', []):
            if str(split.get('season', '')) != str(season):
                continue
            try:
                return _parse_stat_to_line(split.get('stat', {}))
            except (TypeError, ValueError) as e:
                logger.warning("Skipping malformed hitting stat line for %s: %s", name_for_log, e)
                return None
    return None


def _parse_first_line(person: dict, name_for_log: str = '?') -> SeasonHittingLine | None:
    """Pulls whatever single hitting stat split is present, no season
    filter — used for last-30-days (byDateRange), career, and the vs-LHP/
    vs-RHP platoon splits, same reasoning as data/player_stats.py's
    identically-named helper."""
    for group in person.get('stats', []):
        for split in group.get('splits', []):
            try:
                return _parse_stat_to_line(split.get('stat', {}))
            except (TypeError, ValueError) as e:
                logger.warning("Skipping malformed hitting stat line for %s: %s", name_for_log, e)
                return None
    return None


def _is_pitcher_entry(entry: dict) -> bool:
    position = entry.get('position') or {}
    return position.get('code') == _PITCHER_POSITION_CODE or position.get('abbreviation') == 'P'


def _parse_roster_entry(entry: dict, season: int) -> RawHitterRecord | None:
    if _is_pitcher_entry(entry):
        return None   #this module is position players only
    person = entry.get('person') or {}
    person_id = person.get('id')
    full_name = person.get('fullName')
    if person_id is None or not full_name:
        return None
    status = entry.get('status') or {}
    position = entry.get('position') or {}
    return RawHitterRecord(
        person_id=person_id,
        full_name=full_name,
        status_code=status.get('code', 'A'),
        status_description=status.get('description', 'Active'),
        current_season=_parse_season_line(person, season, full_name),
        last_30_days=None,   #filled in below once we know which IDs to look up
        career=None,
        vs_lhp=None,
        vs_rhp=None,
        position=position.get('abbreviation') or '?',
    )


def _lines_by_id(payload: dict) -> dict[int, SeasonHittingLine]:
    """Shared reducer for the last30/career/vs_lhp/vs_rhp bulk /people
    payloads — all four have the identical {'people': [...]} shape."""
    by_id: dict[int, SeasonHittingLine] = {}
    for person in payload.get('people', []):
        pid = person.get('id')
        line = _parse_first_line(person, person.get('fullName', '?'))
        if pid is not None and line is not None:
            by_id[pid] = line
    return by_id


#------------------------------------------------------------------------------
#Disk cache — short TTL, one entry per team+season+as-of-date. Split
#across two unified stores (data/cache_store.py): season/last-30/career
#hitting lines live in cache/batting_stats.json, and the vs-LHP/vs-RHP
#platoon splits (used only for lineup selection, not the overall rating)
#live in cache/lineups.json — so each data type still ends up in the file
#its name promises, even though both come from the same bundled fetch.
#------------------------------------------------------------------------------

_BATTING_STORE = 'batting_stats'
_LINEUPS_STORE = 'lineups'


def _cache_key(team_id: int, season: int, as_of_date: str) -> str:
    return f"{team_id}:{season}:{as_of_date}"


#------------------------------------------------------------------------------
#Public entry point
#------------------------------------------------------------------------------

def fetch_team_hitters(team_id: int, season: int, as_of_date: str) -> list[RawHitterRecord]:
    """
    Every non-pitcher on `team_id`'s 40-man roster for `season`, with
    current-season, rolling last-30-days (ending at `as_of_date`,
    'YYYY-MM-DD'), career, and vs-LHP/vs-RHP platoon-split HITTING stats
    attached. simulation/offense_calculator.py blends season/last-30-days/
    career via simulation/hitter_rating.py for the overall rating, and uses
    vs_lhp/vs_rhp separately to build the two lineups (build_team_lineups).

    `as_of_date` should be "today" for a live simulation or the backtest
    snapshot date for a backtest run, same as data/player_stats.py's
    fetch_team_pitching_staff.

    Raises DataFetchError on a network/shape problem. Callers (simulation/
    offense_calculator.py) are expected to catch it and fall back to a
    synthetic Elo-derived lineup rather than let one missing roster crash
    an entire simulation run.
    """
    cache_key = _cache_key(team_id, season, as_of_date)
    batting_cached = get_entry(_BATTING_STORE, cache_key, ROSTER_CACHE_EXPIRY_SECONDS)
    lineups_cached = get_entry(_LINEUPS_STORE, cache_key, ROSTER_CACHE_EXPIRY_SECONDS)
    if batting_cached is not None and lineups_cached is not None:
        roster_payload  = batting_cached['roster']
        last30_payload  = batting_cached['last30']
        career_payload  = batting_cached['career']
        vs_lhp_payload  = lineups_cached.get('vs_lhp', {'people': []})
        vs_rhp_payload  = lineups_cached.get('vs_rhp', {'people': []})
    else:
        roster_payload = fetch_team_hitting_roster_raw(team_id, season)
        entries = roster_payload.get('roster')
        if not isinstance(entries, list):
            raise DataFetchError(f"Hitting roster response for team {team_id} was not in the expected format.")

        hitter_ids = [
            entry['person']['id']
            for entry in entries
            if not _is_pitcher_entry(entry) and isinstance(entry.get('person'), dict) and 'id' in entry['person']
        ]

        end_date = date.fromisoformat(as_of_date)
        start_date = end_date - timedelta(days=LAST_30_DAYS_WINDOW)
        last30_payload = (
            fetch_people_last_30_days_hitting_stats_raw(hitter_ids, start_date.isoformat(), end_date.isoformat())
            if hitter_ids else {'people': []}
        )
        career_payload = fetch_people_career_hitting_stats_raw(hitter_ids) if hitter_ids else {'people': []}
        vs_lhp_payload = (
            fetch_people_split_hitting_stats_raw(hitter_ids, season, 'vl') if hitter_ids else {'people': []}
        )
        vs_rhp_payload = (
            fetch_people_split_hitting_stats_raw(hitter_ids, season, 'vr') if hitter_ids else {'people': []}
        )

        set_entry(
            _BATTING_STORE, cache_key,
            {'roster': roster_payload, 'last30': last30_payload, 'career': career_payload},
        )
        set_entry(
            _LINEUPS_STORE, cache_key,
            {'vs_lhp': vs_lhp_payload, 'vs_rhp': vs_rhp_payload},
        )

    entries = roster_payload.get('roster', [])
    if not isinstance(entries, list):
        raise DataFetchError(f"Hitting roster response for team {team_id} was not in the expected format.")

    hitters: list[RawHitterRecord] = []
    for entry in entries:
        try:
            record = _parse_roster_entry(entry, season)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Skipping malformed hitting roster entry for team %s: %s", team_id, e)
            continue
        if record is not None:
            hitters.append(record)

    last30_by_id = _lines_by_id(last30_payload)
    career_by_id = _lines_by_id(career_payload)
    vs_lhp_by_id = _lines_by_id(vs_lhp_payload)
    vs_rhp_by_id = _lines_by_id(vs_rhp_payload)

    return [
        dataclasses.replace(
            h,
            last_30_days=last30_by_id.get(h.person_id),
            career=career_by_id.get(h.person_id),
            vs_lhp=vs_lhp_by_id.get(h.person_id),
            vs_rhp=vs_rhp_by_id.get(h.person_id),
        )
        for h in hitters
    ]
