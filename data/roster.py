# ==============================================================================
# ROSTER
# data/roster.py
#
# Fetches a team's full 40-man roster (every position) from the MLB Stats
# API and parses it into a Roster of Player objects — no stats or rating
# math, just who's on the roster and available right now. Short-TTL disk
# cached, same pattern as data/player_stats.py.
# ==============================================================================

from __future__ import annotations

from config import ROSTER_CACHE_EXPIRY_SECONDS
from data.api import fetch_full_roster_raw
from data.cache import load_json_cache, save_json_cache
from data.exceptions import DataFetchError
from models.player import Player
from models.roster import Roster
from models.team import TeamName
from utils.logger import get_logger

logger = get_logger(__name__)


def _parse_player(entry: dict) -> Player | None:
    person = entry.get('person') or {}
    person_id = person.get('id')
    full_name = person.get('fullName')
    if person_id is None or not full_name:
        return None
    position = entry.get('position') or {}
    status = entry.get('status') or {}
    return Player(
        person_id=person_id,
        full_name=full_name,
        position=position.get('abbreviation') or position.get('code') or '?',
        status_code=status.get('code', 'A'),
        status_description=status.get('description', 'Active'),
        jersey_number=entry.get('jerseyNumber') or None,
    )


def _cache_key(team_id: int, season: int) -> str:
    return f"mlb_full_roster_cache_{team_id}_{season}"


#------------------------------------------------------------------------------
#Public entry point
#------------------------------------------------------------------------------

def fetch_team_roster(team: TeamName, team_id: int, season: int) -> Roster:
    """
    Every player on `team`'s 40-man roster for `season` — all positions,
    with roster/injury status. Raises DataFetchError on a network/shape
    problem; callers that just want "the roster" for display should catch
    this and show an empty/unavailable state rather than crash a whole
    screen over one missing roster.
    """
    cache_key = _cache_key(team_id, season)
    payload = load_json_cache(cache_key, ROSTER_CACHE_EXPIRY_SECONDS)
    if payload is None:
        payload = fetch_full_roster_raw(team_id, season)
        save_json_cache(cache_key, payload)

    entries = payload.get('roster')
    if not isinstance(entries, list):
        raise DataFetchError(f"Roster response for team {team_id} was not in the expected format.")

    players: list[Player] = []
    for entry in entries:
        try:
            player = _parse_player(entry)
        except (KeyError, TypeError, ValueError) as e:
            logger.warning("Skipping malformed roster entry for team %s: %s", team_id, e)
            continue
        if player is not None:
            players.append(player)

    return Roster(team=team, players=tuple(players))
