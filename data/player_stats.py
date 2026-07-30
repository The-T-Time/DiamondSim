# ==============================================================================
# PLAYER STATS
# data/player_stats.py
#
# Fetches a team's 40-man roster plus season/last-30-days/career pitching
# stats from the MLB Stats API and parses it into RawPlayerRecord objects.
# No rating math here (simulation/player_rating.py) or staff assembly
# (simulation/pitching.py) — just roster JSON in, typed records out, with
# a short-TTL disk cache.
# ==============================================================================

from __future__ import annotations

import dataclasses
from datetime import date, timedelta
from typing import Any

from config import ROSTER_CACHE_EXPIRY_SECONDS
from data.api import (
    fetch_people_career_stats_raw,
    fetch_people_last_30_days_stats_raw,
    fetch_team_roster_raw,
)
from data.cache_store import get_entry, set_entry
from data.exceptions import DataFetchError
from models.pitching_stats import RawPlayerRecord, SeasonPitchingLine
from utils.logger import get_logger

logger = get_logger(__name__)

#MLB Stats API position code for pitcher (the other reliable signal,
#`position.abbreviation == 'P'`, is checked too since not every payload
#includes `code`).
_PITCHER_POSITION_CODE = '1'

#How many days back the "recent form" window looks from the as-of date.
LAST_30_DAYS_WINDOW: int = 30


def _parse_innings(ip_str: Any) -> float:
    """
    MLB reports innings pitched as e.g. '123.1', where the digit after the
    decimal point is OUTS within the inning (.1 = one out, .2 = two outs),
    not decimal tenths — '123.1' means 123⅓ innings, not 123.1 innings.
    """
    text = str(ip_str)
    if '.' not in text:
        return float(text or 0.0)
    whole, _, frac = text.partition('.')
    thirds = {'0': 0.0, '1': 1.0 / 3.0, '2': 2.0 / 3.0}.get(frac, 0.0)
    return float(whole or 0) + thirds


def _stat_to_line(stat: dict) -> SeasonPitchingLine:
    return SeasonPitchingLine(
        innings_pitched=_parse_innings(stat.get('inningsPitched', 0)),
        strikeouts=int(stat.get('strikeOuts', 0)),
        walks=int(stat.get('baseOnBalls', 0)),
        hit_batters=int(stat.get('hitBatsmen', 0)),
        home_runs=int(stat.get('homeRuns', 0)),
        earned_runs=int(stat.get('earnedRuns', 0)),
        games=int(stat.get('gamesPitched', 0)),
        games_started=int(stat.get('gamesStarted', 0)),
        wins=int(stat.get('wins', 0)),
        losses=int(stat.get('losses', 0)),
    )


def _parse_season_line(person: dict, season: int, name_for_log: str = '?') -> SeasonPitchingLine | None:
    """Pulls the pitching-group stat split matching `season` out of a
    hydrated person object's `stats` list, or None if there's no pitching
    stats for that season (didn't pitch, or hasn't debuted yet)."""
    for group in person.get('stats', []):
        for split in group.get('splits', []):
            if str(split.get('season', '')) != str(season):
                continue
            try:
                return _stat_to_line(split.get('stat', {}))
            except (TypeError, ValueError) as e:
                logger.warning("Skipping malformed stat line for %s: %s", name_for_log, e)
                return None
    return None


def _parse_first_line(person: dict, name_for_log: str = '?') -> SeasonPitchingLine | None:
    """
    Pulls whatever single pitching stat split is present, with no season
    filter — used for last-30-days (byDateRange) and career stat types,
    where the hydrate request only ever returns the one window asked for
    (so there's nothing to disambiguate by season the way current-season
    stats sometimes need). Returns None if there's simply no split (the
    player has no stats in that window at all).
    """
    for group in person.get('stats', []):
        for split in group.get('splits', []):
            try:
                return _stat_to_line(split.get('stat', {}))
            except (TypeError, ValueError) as e:
                logger.warning("Skipping malformed stat line for %s: %s", name_for_log, e)
                return None
    return None


def _is_pitcher_entry(entry: dict) -> bool:
    position = entry.get('position') or {}
    return position.get('code') == _PITCHER_POSITION_CODE or position.get('abbreviation') == 'P'


def _parse_roster_entry(entry: dict, season: int) -> RawPlayerRecord | None:
    if not _is_pitcher_entry(entry):
        return None
    person = entry.get('person') or {}
    person_id = person.get('id')
    full_name = person.get('fullName')
    if person_id is None or not full_name:
        return None
    status = entry.get('status') or {}
    throws = (person.get('pitchHand') or {}).get('code') or None
    return RawPlayerRecord(
        person_id=person_id,
        full_name=full_name,
        status_code=status.get('code', 'A'),
        status_description=status.get('description', 'Active'),
        current_season=_parse_season_line(person, season, full_name),
        last_30_days=None,   #filled in below once we know which IDs to look up
        career=None,
        throws=throws,
    )


#------------------------------------------------------------------------------
#Disk cache — short TTL, separate entry per team+season+as-of-date (roster/
#injury status and the last-30-days window both change far more often than
#the Elo numbers cached elsewhere). Lives in the unified cache/
#pitching_stats.json store (data/cache_store.py) — every team's entry in
#one file instead of one file per team, each entry still tracking its own
#freshness independently.
#------------------------------------------------------------------------------

_STORE = 'pitching_stats'


def _cache_key(team_id: int, season: int, as_of_date: str) -> str:
    return f"{team_id}:{season}:{as_of_date}"


#------------------------------------------------------------------------------
#Public entry point
#------------------------------------------------------------------------------

def fetch_team_pitching_staff(team_id: int, season: int, as_of_date: str) -> list[RawPlayerRecord]:
    """
    Every pitcher on `team_id`'s 40-man roster for `season`, with current-
    season, rolling last-30-days (ending at `as_of_date`, 'YYYY-MM-DD'), and
    career stats attached — simulation/pitching.py blends the three via
    simulation/player_rating.py's blend_rating_components (default 60%
    season / 30% last 30 days / 10% career).

    `as_of_date` should be "today" for a live simulation or the backtest
    snapshot date for a backtest run, so the last-30-days window always
    reflects form as of the moment being simulated, not the real-world
    current date.

    Raises DataFetchError on a network/shape problem. Callers (simulation/
    pitching.py) are expected to catch it and fall back to the synthetic
    Elo-derived staff generator rather than let one missing roster crash an
    entire simulation run.
    """
    cache_key = _cache_key(team_id, season, as_of_date)
    cached = get_entry(_STORE, cache_key, ROSTER_CACHE_EXPIRY_SECONDS)
    if cached is not None:
        roster_payload, last30_payload, career_payload = (
            cached['roster'], cached['last30'], cached['career'],
        )
    else:
        roster_payload = fetch_team_roster_raw(team_id, season)
        entries = roster_payload.get('roster')
        if not isinstance(entries, list):
            raise DataFetchError(f"Roster response for team {team_id} was not in the expected format.")

        pitcher_ids = [
            entry['person']['id']
            for entry in entries
            if _is_pitcher_entry(entry) and isinstance(entry.get('person'), dict) and 'id' in entry['person']
        ]

        end_date = date.fromisoformat(as_of_date)
        start_date = end_date - timedelta(days=LAST_30_DAYS_WINDOW)
        last30_payload = (
            fetch_people_last_30_days_stats_raw(pitcher_ids, start_date.isoformat(), end_date.isoformat())
            if pitcher_ids else {'people': []}
        )
        career_payload = fetch_people_career_stats_raw(pitcher_ids) if pitcher_ids else {'people': []}

        set_entry(
            _STORE, cache_key,
            {'roster': roster_payload, 'last30': last30_payload, 'career': career_payload},
        )

    entries = roster_payload.get('roster', [])
    if not isinstance(entries, list):
        raise DataFetchError(f"Roster response for team {team_id} was not in the expected format.")

    pitchers: list[RawPlayerRecord] = []
    for entry in entries:
        try:
            record = _parse_roster_entry(entry, season)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Skipping malformed roster entry for team %s: %s", team_id, e)
            continue
        if record is not None:
            pitchers.append(record)

    last30_by_id: dict[int, SeasonPitchingLine] = {}
    for person in last30_payload.get('people', []):
        pid = person.get('id')
        line = _parse_first_line(person, person.get('fullName', '?'))
        if pid is not None and line is not None:
            last30_by_id[pid] = line

    career_by_id: dict[int, SeasonPitchingLine] = {}
    for person in career_payload.get('people', []):
        pid = person.get('id')
        line = _parse_first_line(person, person.get('fullName', '?'))
        if pid is not None and line is not None:
            career_by_id[pid] = line

    return [
        dataclasses.replace(
            p,
            last_30_days=last30_by_id.get(p.person_id),
            career=career_by_id.get(p.person_id),
        )
        for p in pitchers
    ]
