# ==============================================================================
# UNIFIED DATA CACHE
# data/cache_store.py
#
# Introduced in 1.0.1. Everything the app pulls from the MLB Stats API now
# lives under one `cache/` directory, organized BY DATA TYPE rather than by
# team — one games.json for every team's games, one rosters.json for every
# team's roster, and so on:
#
#   cache/
#   ├── metadata.json        — cache/season bookkeeping (see below)
#   ├── games.json            — parsed played/unplayed Game records, per season
#   ├── schedule.json          — season start/end boundaries + sync watermark
#   ├── standings.json          — derived live W/L standings snapshot, per season
#   ├── team_elo.json            — current + prior-season-closing Elo tables
#   ├── batting_stats.json        — roster + season/last-30/career hitting lines
#   ├── pitching_stats.json        — roster + season/last-30/career pitching lines
#   ├── lineups.json                — vs-LHP / vs-RHP platoon splits
#   ├── rosters.json                  — full 40-man roster + status (Teams tab)
#   ├── injuries.json                  — non-active roster entries, derived
#   ├── player_ratings.json             — reserved for future per-player rating cache
#   └── settings.json                    — cache-level settings (distinct from
#                                          user_settings.json's simulation prefs)
#
# Two different freshness models live side by side here, matching how the
# underlying data actually changes:
#
#   * Games/schedule are keyed by DATE. A season's games only grow (a new
#     day's results get appended), so we track the date we've already
#     synced through and only ask the API for anything after that ("only
#     request data for the missing dates" / "if the cache is already
#     current for the day ... without making unnecessary API requests").
#     Completed prior seasons stabilize permanently once fully synced —
#     there is nothing left to ever re-fetch.
#
#   * Rosters/stats (batting, pitching, lineups) are keyed by TEAM and
#     carry a short TTL (config.ROSTER_CACHE_EXPIRY_SECONDS) the same way
#     they always have — injury status and rolling 30-day form genuinely
#     change hour to hour, so a per-entry timestamp (not the file's mtime)
#     decides freshness.
#
# CACHE_ENABLED is checked dynamically off data.cache's module attribute
# (not imported as a plain value) so that tests which do
# `patch('data.cache.CACHE_ENABLED', False)` disable this cache too,
# exactly like they already disable data/cache.py's load_json_cache.
#
# CONCURRENCY: several teams' rosters/stats are fetched at once from a
# handful of threads (see simulation/pitching.py and
# simulation/offense_calculator.py's ThreadPoolExecutors) inside the same
# process. Because every team's data now lands in ONE shared file per
# type instead of one file per team, an unsynchronized read-modify-write
# from several threads at once will tear each other's writes and corrupt
# the file. Every write path below acquires that store's lock for the
# full read-modify-write-replace cycle, and each write goes to a
# process+thread-unique temp filename (so even a write outside a lock,
# or a lock timeout fallback, can never collide with another writer's
# temp file the way a single fixed 'name.tmp' can).
# ==============================================================================

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import threading
import time
import uuid
from datetime import date
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT
from data.api import fetch_schedule_range, get_season_boundaries
from models.game import Game
from utils.logger import get_logger

logger = get_logger(__name__)

CACHE_DIR: Path = PROJECT_ROOT / 'cache'

#Every named store this module knows about. Values are the on-disk
#filename under CACHE_DIR. player_ratings.json has no writer yet — it's
#reserved so a future per-player rating cache has an obvious home in the
#same layout instead of inventing a new convention.
STORE_FILES: dict[str, str] = {
    'metadata':       'metadata.json',
    'games':          'games.json',
    'schedule':       'schedule.json',
    'standings':      'standings.json',
    'team_elo':       'team_elo.json',
    'batting_stats':  'batting_stats.json',
    'pitching_stats': 'pitching_stats.json',
    'lineups':        'lineups.json',
    'rosters':        'rosters.json',
    'injuries':       'injuries.json',
    'player_ratings': 'player_ratings.json',
    'settings':       'settings.json',
}

SCHEMA_VERSION = 1


def _cache_enabled() -> bool:
    """Reads data.cache.CACHE_ENABLED off the module (not as a plain
    imported name) so tests that patch it there disable this cache too."""
    import data.cache as _cache_mod
    return _cache_mod.CACHE_ENABLED


#------------------------------------------------------------------------------
#Per-store locks. One threading.Lock per store name, created lazily and
#reused for the life of the process — guards every store's full
#read-modify-write-replace cycle so concurrent threads (e.g. the
#ThreadPoolExecutors in simulation/pitching.py and
#simulation/offense_calculator.py fetching several teams at once) can
#never tear each other's writes to the same shared file.
#------------------------------------------------------------------------------

_store_locks: dict[str, threading.Lock] = {}
_store_locks_guard = threading.Lock()


def _lock_for(name: str) -> threading.Lock:
    with _store_locks_guard:
        lock = _store_locks.get(name)
        if lock is None:
            lock = threading.Lock()
            _store_locks[name] = lock
        return lock


#------------------------------------------------------------------------------
#Low-level store I/O — one JSON file per data type, corruption-safe same
#as data/cache.py's philosophy: a bad file is a miss, not a crash.
#------------------------------------------------------------------------------

def store_path(name: str) -> Path:
    if name not in STORE_FILES:
        raise KeyError(f"Unknown cache store {name!r}; expected one of {list(STORE_FILES)}")
    return CACHE_DIR / STORE_FILES[name]


def read_store(name: str) -> dict[str, Any]:
    """Returns the named store's full contents as a dict, or {} if the
    cache is disabled, the file doesn't exist yet, or it's corrupted (the
    corrupt file is removed so it doesn't keep failing the same way). Not
    locked — every write goes through a single atomic rename (see
    write_store), so an unlocked reader can only ever see the file
    entirely before or entirely after a given write, never partway
    through it."""
    if not _cache_enabled():
        return {}
    path = store_path(name)
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as e:
        logger.warning("Cache store '%s' is corrupted or unreadable (%s) — resetting it.",
                       STORE_FILES[name], e)
        try:
            path.unlink()
        except OSError:
            pass
        return {}


def _replace_with_retry(tmp: Path, path: Path, attempts: int = 5, base_delay: float = 0.05) -> None:
    """tmp.replace(path) with a short retry/backoff — on Windows a
    rename can transiently fail with a sharing violation if something
    else (antivirus, a lingering handle) has the destination open for a
    moment; POSIX renames don't need this but it's harmless there too."""
    last_exc: OSError | None = None
    for attempt in range(attempts):
        try:
            tmp.replace(path)
            return
        except OSError as e:
            last_exc = e
            time.sleep(base_delay * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def write_store(name: str, data: dict[str, Any]) -> None:
    """Writes the named store's full contents. Best-effort — a write
    failure (full disk, read-only mount, ...) is logged and swallowed,
    never fatal, same as data/cache.py's save_cache. The temp filename is
    unique per call (pid + thread id + a random suffix) specifically so
    that even a write happening outside this module's own locking (or a
    second OS process/instance) can never collide with another writer's
    temp file the way a single shared 'name.tmp' would."""
    if not _cache_enabled():
        return
    path = store_path(name)
    tmp = path.with_name(f"{path.stem}.{os.getpid()}.{threading.get_ident()}.{uuid.uuid4().hex}.tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=2)
        _replace_with_retry(tmp, path)
    except OSError as e:
        logger.warning("Couldn't write cache store '%s' (%s) — continuing without it.",
                       STORE_FILES[name], e)
        try:
            tmp.unlink()
        except OSError:
            pass


def update_store(name: str, mutate) -> dict[str, Any]:
    """
    The safe way to read-modify-write a store: acquires that store's lock
    for the whole cycle, so two threads updating different teams/keys in
    the same file can never interleave their writes. `mutate(data)`
    updates the dict in place; the result is written back and returned.
    Every write path in this module goes through this instead of pairing
    read_store()/write_store() directly.
    """
    with _lock_for(name):
        data = read_store(name)
        mutate(data)
        write_store(name, data)
        return data


def clear_store(name: str) -> None:
    """Resets one store to empty. Used by refresh_all_data() and by tests."""
    with _lock_for(name):
        path = store_path(name)
        try:
            if path.exists():
                path.unlink()
        except OSError as e:
            logger.warning("Couldn't remove cache store '%s' (%s).", STORE_FILES[name], e)


#------------------------------------------------------------------------------
#Generic per-entry TTL cache, shared by rosters/batting_stats/pitching_
#stats/lineups/injuries. Each store file is {key: {"fetched_at": ts,
#"value": ...}} so many teams share one file while each entry still tracks
#its own freshness independently (unlike a whole-file mtime check, which
#would make every team's entry go stale the moment ANY team refreshes).
#------------------------------------------------------------------------------

def get_entry(store: str, key: str, ttl_seconds: float) -> Any | None:
    entries = read_store(store)
    entry = entries.get(key)
    if not isinstance(entry, dict) or 'value' not in entry:
        return None
    fetched_at = entry.get('fetched_at', 0)
    if time.time() - fetched_at >= ttl_seconds:
        return None
    return entry['value']


def set_entry(store: str, key: str, value: Any) -> None:
    def _mutate(entries: dict) -> None:
        entries[key] = {'fetched_at': time.time(), 'value': value}
    update_store(store, _mutate)


def set_entries(store: str, mapping: dict[str, Any]) -> None:
    """Bulk version of set_entry — one locked read-modify-write for
    several keys (e.g. every team in a slate) instead of one per key."""
    if not mapping:
        return
    def _mutate(entries: dict) -> None:
        now = time.time()
        for key, value in mapping.items():
            entries[key] = {'fetched_at': now, 'value': value}
    update_store(store, _mutate)


#------------------------------------------------------------------------------
#Metadata + season-rollover detection
#------------------------------------------------------------------------------

def load_metadata() -> dict[str, Any]:
    meta = read_store('metadata')
    meta.setdefault('schema_version', SCHEMA_VERSION)
    meta.setdefault('current_season', None)
    meta.setdefault('seasons_synced', [])
    meta.setdefault('last_refreshed', None)
    return meta


def save_metadata(meta: dict[str, Any]) -> None:
    with _lock_for('metadata'):
        write_store('metadata', meta)


def note_season_synced(season: int) -> bool:
    """
    Records that `season` has been (or is about to be) synced, and
    detects whether this is a season the cache hasn't seen before —
    i.e. a new MLB season starting. Returns True on that transition.

    No destructive wipe is needed to "create a fresh cache" for the new
    season: games/standings/team_elo are already keyed by season, so a
    season that has never been synced simply has no entry yet and gets
    fully (not incrementally) populated the first time it's requested.
    This just keeps a record of which season is "current" and logs the
    transition so it's visible in the app log.
    """
    is_new_season = False

    def _mutate(meta: dict) -> None:
        nonlocal is_new_season
        meta.setdefault('schema_version', SCHEMA_VERSION)
        seasons_synced = meta.get('seasons_synced') or []
        is_new_season = season not in seasons_synced

        if is_new_season:
            logger.info("New MLB season detected (%s) — building a fresh cache for it.", season)
            seasons_synced.append(season)

        #"current_season" tracks the most recently-requested season so a
        #future startup can tell at a glance which season is the live
        #one, without guessing from the calendar.
        meta['current_season'] = season
        meta['seasons_synced'] = sorted(set(seasons_synced))

    update_store('metadata', _mutate)
    return is_new_season


def refresh_all_data() -> None:
    """
    Manual 'Refresh Data' entry point: wipes every cached data-type file
    so the very next fetch of each kind rebuilds it from scratch. Used
    when the user wants a guaranteed-clean pull instead of trusting
    whatever's already on disk (e.g. after a suspected bad cache, or just
    to force today's numbers).
    """
    for name in STORE_FILES:
        if name == 'metadata':
            continue
        clear_store(name)

    def _mutate(meta: dict) -> None:
        meta.clear()
        meta.update({
            'schema_version': SCHEMA_VERSION,
            'current_season': None,
            'seasons_synced': [],
            'last_refreshed': time.time(),
        })
    update_store('metadata', _mutate)
    logger.info("Cache refresh: every cached data file has been cleared.")


#------------------------------------------------------------------------------
#Games / schedule — incremental, date-based sync
#------------------------------------------------------------------------------

def _cfg_fingerprint(cfg) -> str:
    """Short hash of the Elo-affecting SimulationConfig fields, so a
    changed model (different elo_k, home-field advantage, etc.) never
    reads back another model's cached Elo/standings numbers. Mirrors
    data/cache.py's _cfg_fingerprint but lives here too since this module
    doesn't import that (private) helper across module boundaries."""
    if cfg is None:
        return 'default'
    fields = ('elo_k', 'home_field_advantage', 'elo_baseline', 'regression_weight', 'mov_weight')
    material = tuple(getattr(cfg, f) for f in fields)
    return hashlib.sha1(repr(material).encode()).hexdigest()[:8]


def _game_key(g: Game) -> str:
    """game_pk is almost always present (the MLB Stats API assigns one to
    every scheduled game); the date+matchup fallback only matters for a
    malformed/edge-case payload that somehow omitted it."""
    return str(g.game_pk) if g.game_pk is not None else f"{g.date}:{g.home}:{g.away}"


def _to_dict(g: Game) -> dict:
    return dataclasses.asdict(g)


def _from_dict(d: dict) -> Game:
    return Game(**d)


def _season_key(season: int) -> str:
    return str(season)


def get_schedule_bounds(season: int) -> tuple[str, str]:
    """Season start/end dates. Cached indefinitely once a season's
    schedule bounds are known — MLB doesn't move Opening Day after the
    fact, so there's no TTL here, just a one-time API call per season."""
    schedule_store = read_store('schedule')
    entry = schedule_store.get(_season_key(season))
    if entry and 'start_date' in entry and 'end_date' in entry:
        return entry['start_date'], entry['end_date']

    #network call deliberately happens outside the lock — a slow API
    #round-trip must never hold up another thread's unrelated write to
    #this store. If two threads both race in here for the same never-
    #before-seen season, both fetch (a harmless, rare duplicate) and the
    #later locked write just wins; the result is identical either way.
    start_date, end_date = get_season_boundaries(season)

    def _mutate(store: dict) -> None:
        existing = store.get(_season_key(season), {})
        store[_season_key(season)] = {
            'start_date': start_date,
            'end_date': end_date,
            'last_synced_date': existing.get('last_synced_date'),
        }
    update_store('schedule', _mutate)
    return start_date, end_date


def _get_sync_watermark(season: int) -> str | None:
    return read_store('schedule').get(_season_key(season), {}).get('last_synced_date')


def _set_sync_watermark(season: int, synced_through: str) -> None:
    def _mutate(store: dict) -> None:
        entry = store.setdefault(_season_key(season), {})
        entry['last_synced_date'] = synced_through
    update_store('schedule', _mutate)


def sync_season_games(season: int) -> tuple[list[Game], list[Game]]:
    """
    Returns every game the cache knows about for `season` — (played,
    unplayed) — after syncing just the missing dates from the MLB Stats
    API. This is the incremental heart of the cache:

      * First call for a season: nothing cached yet, fetch the whole
        season's schedule once (through its actual end date, not just
        through today — the not-yet-played remainder of the schedule is
        exactly what a simulation needs, so it's never something to
        "skip" fetching).
      * Later calls the same day: the watermark already reaches today —
        no API call at all.
      * Later calls on a new day: fetch again from the watermark (not
        season start) through the season's end — re-including the
        watermark date itself, since a game live or postponed at the
        last sync may have finalized since — merge the results into
        what's already cached, and move the watermark to today.

    The watermark only ever shrinks how far BACK a re-sync has to reach
    (never re-walking already-settled early-season dates); the fetch
    window's far end is always the season's real end date so the
    unplayed portion of the schedule is always present. Once the
    watermark reaches the season's end date, the season is permanently
    settled — a completed historical season is never fetched again.
    """
    note_season_synced(season)

    if not _cache_enabled():
        start_date, end_date = get_season_boundaries(season)
        schedule_data = fetch_schedule_range(start_date, end_date)
        return _parse_and_split(schedule_data)

    start_date, end_date = get_schedule_bounds(season)
    today = date.today().isoformat()

    watermark = _get_sync_watermark(season)
    fetch_from = watermark if watermark else start_date

    already_synced_today = watermark is not None and watermark >= today
    season_fully_settled = (
        watermark is not None and end_date is not None and watermark >= end_date
    )

    if season_fully_settled or already_synced_today:
        logger.debug("Games cache for %d is already current — skipping the API.", season)
    else:
        logger.info("Syncing %d schedule from %s through %s...", season, fetch_from, end_date)
        #network call outside the lock, same reasoning as get_schedule_bounds
        schedule_data = fetch_schedule_range(fetch_from, end_date)
        fresh_played, fresh_unplayed = _parse_and_split(schedule_data)

        def _mutate(games_store: dict) -> None:
            season_entry = games_store.get(_season_key(season), {})
            existing_by_key = season_entry.get('games', {})
            for g in (*fresh_played, *fresh_unplayed):
                existing_by_key[_game_key(g)] = _to_dict(g)
            games_store[_season_key(season)] = {'games': existing_by_key}
        update_store('games', _mutate)
        _set_sync_watermark(season, today)

    existing_by_key = read_store('games').get(_season_key(season), {}).get('games', {})
    played = [g for g in (_from_dict(d) for d in existing_by_key.values()) if g.is_played]
    unplayed = [g for g in (_from_dict(d) for d in existing_by_key.values()) if not g.is_played]
    played.sort(key=lambda g: g.date)
    unplayed.sort(key=lambda g: g.date)
    return played, unplayed


def _parse_and_split(schedule_data: dict) -> tuple[list[Game], list[Game]]:
    """Local import to avoid a module-level cycle (data.api already
    imports models.game, and importing parse_schedule_into_games at the
    top would make data.api and data.cache_store import each other)."""
    from data.api import parse_schedule_into_games
    return parse_schedule_into_games(schedule_data)


def split_games_for_backtest(
    all_games: list[Game], backtest_date: str
) -> tuple[list[Game], list[Game]]:
    """
    Re-derives a backtest snapshot's played/unplayed split from the
    cache's already-parsed Game records, instead of re-fetching and
    re-parsing raw schedule JSON for every backtest run. `all_games`
    should be every game the cache has for the season (played + unplayed
    combined) — a completed historical season's real outcomes never
    change, so this split can be recomputed for any snapshot date for
    free once the season is cached.

    Mirrors data/api.py's _is_backtest_unplayed: games after the snapshot
    date are always in the "to simulate" bucket; games on or before it
    count as played only if they actually have a real winner recorded.
    """
    played: list[Game] = []
    unplayed: list[Game] = []
    for g in all_games:
        if g.date > backtest_date or g.winner is None:
            unplayed.append(Game(game_pk=g.game_pk, date=g.date, home=g.home, away=g.away))
        else:
            played.append(g)
    return played, unplayed


#------------------------------------------------------------------------------
#Standings + team Elo — derived artifacts, saved for reference/reuse.
#Cheap to recompute from the (cached) games list, so these are always
#recomputed fresh in-process rather than trusted blindly; persisting them
#is just so the right data type lives in the right file per the cache
#layout, and so a future feature (e.g. the Standings tab) could read them
#directly without recomputation.
#------------------------------------------------------------------------------

def save_standings(season: int, cfg, live_standings: dict) -> None:
    key = f"{season}:{_cfg_fingerprint(cfg)}"
    def _mutate(store: dict) -> None:
        store[key] = {
            'season': season,
            'live_standings': live_standings,
            'as_of': date.today().isoformat(),
        }
    update_store('standings', _mutate)


def save_current_elo(season: int, cfg, current_elo: dict, elo_log: dict) -> None:
    key = f"current:{season}:{_cfg_fingerprint(cfg)}"
    def _mutate(store: dict) -> None:
        store[key] = {
            'season': season,
            'current_elo': current_elo,
            'elo_log': {str(pk): dataclasses.asdict(snap) for pk, snap in elo_log.items()},
            'as_of': date.today().isoformat(),
        }
    update_store('team_elo', _mutate)


def get_prior_closing_elo(prior_season: int, cfg) -> dict[str, float] | None:
    """A completed prior season's closing Elo table never changes once
    computed, so this is cached indefinitely (no TTL) — huge savings vs.
    replaying the entire prior season's schedule on every single run."""
    store = read_store('team_elo')
    entry = store.get(f"prior:{prior_season}:{_cfg_fingerprint(cfg)}")
    return entry.get('closing_elo') if entry else None


def save_prior_closing_elo(prior_season: int, cfg, closing_elo: dict[str, float]) -> None:
    key = f"prior:{prior_season}:{_cfg_fingerprint(cfg)}"
    def _mutate(store: dict) -> None:
        store[key] = {'closing_elo': closing_elo}
    update_store('team_elo', _mutate)


#------------------------------------------------------------------------------
#Injuries — derived from roster parsing (data/roster.py), not its own
#fetch. Separated out from rosters.json purely so "who's hurt right now"
#has its own dedicated, easy-to-scan file rather than requiring a scan of
#every team's full roster.
#------------------------------------------------------------------------------

def save_team_injuries(team_id: int, season: int, injured: list[dict]) -> None:
    set_entry('injuries', f"{team_id}:{season}", injured)
