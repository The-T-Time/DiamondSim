# ==============================================================================
# MLB API HELPERS
# data/api.py
#
# Raw HTTP access to the MLB Stats API, plus parsing the schedule response
# into played/unplayed Game lists. Every call is wrapped so a flaky
# connection or unexpected response raises a clear DataFetchError instead
# of an unhandled crash.
# ==============================================================================

from __future__ import annotations

import requests

from data.exceptions import DataFetchError
from data.teams import TEAM_ID_MAP
from models.game import Game
from utils.logger import get_logger

logger = get_logger(__name__)


def _get_json(url: str, what: str) -> dict:
    """GET `url` and return parsed JSON, or raise DataFetchError with context."""
    try:
        res = requests.get(url, timeout=15)
        res.raise_for_status()
    except requests.exceptions.Timeout as e:
        raise DataFetchError(f"Timed out reaching the MLB Stats API while fetching {what}.") from e
    except requests.exceptions.ConnectionError as e:
        raise DataFetchError(
            f"Couldn't reach the MLB Stats API while fetching {what} — check your internet connection."
        ) from e
    except requests.exceptions.HTTPError as e:
        raise DataFetchError(f"MLB Stats API returned an error ({e}) while fetching {what}.") from e
    except requests.exceptions.RequestException as e:
        raise DataFetchError(f"Request to the MLB Stats API failed while fetching {what}: {e}") from e

    try:
        return res.json()
    except ValueError as e:
        raise DataFetchError(f"MLB Stats API returned invalid JSON while fetching {what}.") from e


def get_season_boundaries(season: int) -> tuple[str, str]:
    """Queries MLB API to automatically determine regular season dates."""
    url = f"https://statsapi.mlb.com/api/v1/seasons/{season}?sportId=1"
    payload = _get_json(url, f"{season} season info")
    try:
        info = payload['seasons'][0]
        return info['regularSeasonStartDate'], info['regularSeasonEndDate']
    except (KeyError, IndexError, TypeError) as e:
        raise DataFetchError(
            f"MLB Stats API response for the {season} season was missing expected data."
        ) from e


def fetch_schedule(season: int, end_date_override: str | None = None) -> dict:
    """
    Fetches the full regular season schedule for a given season.
    If end_date_override is provided (YYYY-MM-DD), only games up to that date
    are fetched — used for mid-season backtest snapshots.
    """
    start_date, end_date = get_season_boundaries(season)
    if end_date_override:
        end_date = end_date_override
    url = (
        f"https://statsapi.mlb.com/api/v1/schedule"
        f"?sportId=1&startDate={start_date}&endDate={end_date}"
    )
    return _get_json(url, f"the {season} schedule")


def fetch_full_roster_raw(team_id: int, season: int) -> dict:
    """
    Fetches `team_id`'s full 40-man roster for `season`, no stats hydrate —
    just identity, position, and roster/injury status for every player
    (all positions, not just pitchers). Used by data/roster.py for the
    general Player/Roster/availability feature. data/player_stats.py's
    fetch_team_roster_raw is the pitching-specific counterpart that also
    hydrates each person's pitching stats onto the response; this one is
    the lighter, position-agnostic version for "who's on the roster and can
    they play" without the extra stats payload.
    """
    url = f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster?rosterType=40Man&season={season}"
    return _get_json(url, f"the {season} full roster for team {team_id}")


def fetch_team_roster_raw(team_id: int, season: int) -> dict:
    """
    Fetches `team_id`'s full 40-man roster for `season`, with each player's
    current-season pitching stats AND throwing hand hydrated directly onto
    the person object (one request instead of one-per-player).
    `rosterType=40Man` (not `active`) deliberately includes injured/
    optioned/restricted players too — data/player_stats.py needs to see
    them to know who's unavailable and why, not just who's currently active.
    Throwing hand is what lets the OPPOSING team pick its
    vs-LHP or vs-RHP lineup for this pitcher's starts.
    """
    url = (
        f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
        f"?rosterType=40Man&season={season}"
        f"&hydrate=person(stats(type=season,season={season},group=[pitching]),pitchHand)"
    )
    return _get_json(url, f"the {season} roster for team {team_id}")


def fetch_people_last_30_days_stats_raw(person_ids: list[int], start_date: str, end_date: str) -> dict:
    """
    Bulk rolling-window pitching stats for a list of MLB person ids, over
    the 30 days ending at `end_date` (inclusive; both dates 'YYYY-MM-DD').
    Used for the last-30-days component of the rating blend —
    captures current form a full-season line can miss.
    """
    if not person_ids:
        return {'people': []}
    ids_csv = ','.join(str(pid) for pid in person_ids)
    url = (
        f"https://statsapi.mlb.com/api/v1/people"
        f"?personIds={ids_csv}"
        f"&hydrate=stats(type=byDateRange,startDate={start_date},endDate={end_date},group=[pitching])"
    )
    return _get_json(url, f"last-30-days pitching stats for {len(person_ids)} players")


def fetch_people_career_stats_raw(person_ids: list[int]) -> dict:
    """
    Bulk career pitching totals for a list of MLB person ids. Used as the
    stable baseline anchor in the rating blend (season/last-30-
    days/career).
    """
    if not person_ids:
        return {'people': []}
    ids_csv = ','.join(str(pid) for pid in person_ids)
    url = (
        f"https://statsapi.mlb.com/api/v1/people"
        f"?personIds={ids_csv}"
        f"&hydrate=stats(type=career,group=[pitching])"
    )
    return _get_json(url, f"career pitching stats for {len(person_ids)} players")


def fetch_team_hitting_roster_raw(team_id: int, season: int) -> dict:
    """
    Fetches `team_id`'s full 40-man roster for `season`, with each player's
    current-season HITTING stats hydrated directly onto the person object.
    The hitting-group counterpart to fetch_team_roster_raw above — same
    request shape, different stat group, used by data/hitting_stats.py for
    the position-player rating pipeline.
    """
    url = (
        f"https://statsapi.mlb.com/api/v1/teams/{team_id}/roster"
        f"?rosterType=40Man&season={season}"
        f"&hydrate=person(stats(type=season,season={season},group=[hitting]))"
    )
    return _get_json(url, f"the {season} hitting roster for team {team_id}")


def fetch_people_last_30_days_hitting_stats_raw(person_ids: list[int], start_date: str, end_date: str) -> dict:
    """Bulk rolling-window HITTING stats for a list of MLB person ids, over
    the 30 days ending at `end_date` (inclusive; both dates 'YYYY-MM-DD').
    The hitting-group counterpart to fetch_people_last_30_days_stats_raw."""
    if not person_ids:
        return {'people': []}
    ids_csv = ','.join(str(pid) for pid in person_ids)
    url = (
        f"https://statsapi.mlb.com/api/v1/people"
        f"?personIds={ids_csv}"
        f"&hydrate=stats(type=byDateRange,startDate={start_date},endDate={end_date},group=[hitting])"
    )
    return _get_json(url, f"last-30-days hitting stats for {len(person_ids)} players")


def fetch_people_career_hitting_stats_raw(person_ids: list[int]) -> dict:
    """Bulk career HITTING totals for a list of MLB person ids. The
    hitting-group counterpart to fetch_people_career_stats_raw."""
    if not person_ids:
        return {'people': []}
    ids_csv = ','.join(str(pid) for pid in person_ids)
    url = (
        f"https://statsapi.mlb.com/api/v1/people"
        f"?personIds={ids_csv}"
        f"&hydrate=stats(type=career,group=[hitting])"
    )
    return _get_json(url, f"career hitting stats for {len(person_ids)} players")


def fetch_people_split_hitting_stats_raw(person_ids: list[int], season: int, sit_code: str) -> dict:
    """
    Bulk platoon-split HITTING stats for a list of MLB person ids —
    `sit_code` is 'vl' (vs left-handed pitching) or 'vr' (vs right-handed
    pitching), the MLB Stats API's situational-split codes. Used to build
    a team's two lineups (see simulation/offense_calculator.py's
    build_team_lineups): which hitters actually rake against a lefty starter
    can differ meaningfully from who rakes against a righty.
    """
    if not person_ids:
        return {'people': []}
    ids_csv = ','.join(str(pid) for pid in person_ids)
    url = (
        f"https://statsapi.mlb.com/api/v1/people"
        f"?personIds={ids_csv}"
        f"&hydrate=stats(type=season,season={season},group=[hitting],sitCodes=[{sit_code}])"
    )
    return _get_json(url, f"vs-{sit_code} hitting splits for {len(person_ids)} players")


def _is_backtest_unplayed(game: dict, game_date_str: str, backtest_date: str) -> bool:
    """
    Decide whether a game belongs in the unplayed/simulated bucket for a backtest.

    Games after the snapshot date are always simulated. Games on the snapshot
    date count as played only if they are Final. Earlier games follow the same
    Final/unplayed rule as forward simulation.
    """
    if game_date_str > backtest_date:
        return True
    return game.get('status', {}).get('abstractGameState') != 'Final'


def parse_schedule_into_games(
    schedule_data: dict, backtest_date: str | None = None
) -> tuple[list[Game], list[Game]]:
    """
    Splits a raw MLB Stats API schedule response into two Game lists based on
    absolute state or an optional chronological snapshot split date.

    Individual malformed game entries (missing fields, unrecognized team ids)
    are logged and skipped rather than aborting the whole parse — a schedule
    with one bad record shouldn't nuke every other game in it.
    """
    played: list[Game] = []
    unplayed: list[Game] = []

    if not isinstance(schedule_data, dict):
        raise DataFetchError("Schedule data was not in the expected format (not a JSON object).")

    for date_obj in schedule_data.get('dates', []):
        game_date_str = date_obj.get('date', '')
        for game in date_obj.get('games', []):
            try:
                if game.get('gameType') != 'R':
                    continue
                home_id = str(game['teams']['home']['team']['id'])
                away_id = str(game['teams']['away']['team']['id'])
                if home_id not in TEAM_ID_MAP or away_id not in TEAM_ID_MAP:
                    continue

                home_name = TEAM_ID_MAP[home_id]
                away_name = TEAM_ID_MAP[away_id]
                game_pk = game.get('gamePk')

                if backtest_date:
                    is_simulated = _is_backtest_unplayed(game, game_date_str, backtest_date)
                else:
                    is_simulated = game.get('status', {}).get('abstractGameState') != 'Final'

                if not is_simulated and game.get('status', {}).get('abstractGameState') == 'Final':
                    home_score = game['teams']['home'].get('score', 0)
                    away_score = game['teams']['away'].get('score', 0)
                    if home_score == away_score:
                        unplayed.append(Game(game_pk=game_pk, date=game_date_str,
                                              home=home_name, away=away_name))
                        continue
                    winner = home_name if home_score > away_score else away_name
                    played.append(Game(
                        game_pk=game_pk, date=game_date_str,
                        home=home_name, away=away_name,
                        home_score=home_score, away_score=away_score,
                        winner=winner,
                    ))
                else:
                    unplayed.append(Game(game_pk=game_pk, date=game_date_str,
                                          home=home_name, away=away_name))
            except (KeyError, TypeError, ValueError) as e:
                logger.warning(
                    "Skipping malformed game entry on %s (gamePk=%s): %s",
                    game_date_str, game.get('gamePk', '?') if isinstance(game, dict) else '?', e,
                )
                continue

    return played, unplayed
