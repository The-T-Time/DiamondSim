# ==============================================================================
# DISK CACHE
# data/cache.py
#
# JSON cache for simulate mode's fetched schedule + computed Elo (backtest
# mode always fetches fresh). Converts Game/EloSnapshot dataclasses to/from
# JSON at the cache boundary only. Filename is fingerprinted on the
# SimulationConfig fields that affect cached Elo, so switching models
# never serves back another model's cached numbers.
# ==============================================================================

from __future__ import annotations

import dataclasses
import hashlib
import json
import time
from pathlib import Path
from typing import Any

from config import CACHE_ENABLED, CACHE_EXPIRY_SECONDS, PROJECT_ROOT
from models.elo_snapshot import EloSnapshot
from models.game import Game
from models.simulation_config import SimulationConfig
from utils.logger import get_logger

logger = get_logger(__name__)

_GAME_LIST_KEYS = ('played_games', 'unplayed_games')

#Only fields that change the cached Elo numbers belong in the fingerprint.
#sim_margin_cap/backtest_threshold_pct/simulations only affect the live
#Monte Carlo loop, which is never cached.
_FINGERPRINT_FIELDS = (
    'elo_k', 'home_field_advantage', 'elo_baseline', 'regression_weight', 'mov_weight',
)


def _cfg_fingerprint(cfg: SimulationConfig) -> str:
    material = tuple(getattr(cfg, f) for f in _FINGERPRINT_FIELDS)
    return hashlib.sha1(repr(material).encode()).hexdigest()[:8]


def cache_path(season: int, cfg: SimulationConfig | None = None) -> Path:
    suffix = f"_{_cfg_fingerprint(cfg)}" if cfg is not None else ""
    return PROJECT_ROOT / f"mlb_data_cache_{season}{suffix}.json"


def _to_jsonable(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of payload with Game/EloSnapshot objects turned into plain JSON."""
    out = dict(payload)
    for key in _GAME_LIST_KEYS:
        if key in out:
            out[key] = [dataclasses.asdict(g) for g in out[key]]
    if 'elo_log' in out:
        out['elo_log'] = {str(pk): dataclasses.asdict(snap) for pk, snap in out['elo_log'].items()}
    return out


def _from_jsonable(payload: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of payload with Game/EloSnapshot objects rehydrated from JSON."""
    out = dict(payload)
    for key in _GAME_LIST_KEYS:
        if key in out:
            out[key] = [Game(**g) for g in out[key]]
    if 'elo_log' in out:
        out['elo_log'] = {int(pk): EloSnapshot(**snap) for pk, snap in out['elo_log'].items()}
    return out


def load_cache(season: int, cfg: SimulationConfig | None = None) -> dict[str, Any] | None:
    """
    Returns the cached payload dict for `season`/`cfg` if caching is enabled,
    the file exists, and it isn't stale. Otherwise returns None.

    A corrupted or unreadable cache file is treated as a cache miss, not a
    crash: it's logged, the bad file is removed, and we fall through to a
    fresh fetch. Cache data is disposable by design — it should never be
    able to bring the app down.
    """
    cache_file = cache_path(season, cfg)
    if not (CACHE_ENABLED and cache_file.exists()):
        return None

    try:
        age = time.time() - cache_file.stat().st_mtime
    except OSError as e:
        logger.warning("Couldn't stat cache file '%s' (%s) — ignoring it.", cache_file.name, e)
        return None

    if age >= CACHE_EXPIRY_SECONDS:
        return None

    try:
        with open(cache_file) as f:
            raw = json.load(f)
        return _from_jsonable(raw)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, OSError) as e:
        logger.warning(
            "Cache file '%s' is corrupted or unreadable (%s) — ignoring and refetching.",
            cache_file.name, e,
        )
        try:
            cache_file.unlink()
        except OSError:
            pass   #best-effort cleanup; a leftover bad file is harmless, just wasted disk
        return None


def save_cache(season: int, payload: dict[str, Any], cfg: SimulationConfig | None = None) -> None:
    """
    Writes `payload` to the season/cfg's cache file as pretty-printed JSON.
    Caching is a nice-to-have — if the disk is full, read-only, or otherwise
    unwritable, we log it and move on rather than failing the whole run.
    """
    cache_file = cache_path(season, cfg)
    try:
        with open(cache_file, 'w') as f:
            json.dump(_to_jsonable(payload), f, indent=4)
        logger.debug("Cache written: %s", cache_file.name)
    except OSError as e:
        logger.warning("Couldn't write cache file '%s' (%s) — continuing without caching.",
                       cache_file.name, e)


#------------------------------------------------------------------------------
#Generic keyed JSON cache
#
#data/player_stats.py, data/hitting_stats.py, and data/roster.py each cache
#a plain dict (raw MLB Stats API JSON — no Game/EloSnapshot objects to
#convert) under a short TTL. That's three copies of the same read/write/
#expiry/corruption-handling logic with only the filename and TTL differing
#— load_json_cache/save_json_cache below is the one shared implementation
#all three call, so a caller just picks a `key` (e.g.
#f"mlb_roster_cache_{team_id}_{season}_{as_of_date}") and an expiry.
#------------------------------------------------------------------------------

def generic_cache_path(key: str) -> Path:
    """Path for a generic keyed cache entry. Callers own their own
    key-naming scheme (typically embedding whatever makes the entry unique
    — team id, season, as-of date); this just resolves it under
    PROJECT_ROOT as a JSON file."""
    return PROJECT_ROOT / f"{key}.json"


def load_json_cache(key: str, expiry_seconds: int) -> dict[str, Any] | None:
    """
    Generic raw-JSON disk cache read: returns the cached dict for `key` if
    caching is enabled, the file exists, and it's younger than
    `expiry_seconds` — otherwise None. Same disposable-cache philosophy as
    load_cache above: a stale, missing, or corrupted entry is a plain miss,
    never a crash, and a corrupted file is removed rather than left to fail
    the same way again next time.
    """
    path = generic_cache_path(key)
    if not (CACHE_ENABLED and path.exists()):
        return None
    try:
        if time.time() - path.stat().st_mtime >= expiry_seconds:
            return None
        with open(path) as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        logger.warning("Cache entry '%s' unreadable (%s) — ignoring it.", key, e)
        try:
            path.unlink()
        except OSError:
            pass
        return None


def save_json_cache(key: str, payload: dict[str, Any]) -> None:
    """Writes `payload` as JSON under `key`. Best-effort, same as save_cache
    above — a write failure is logged and swallowed, never fatal."""
    if not CACHE_ENABLED:
        return
    try:
        with open(generic_cache_path(key), 'w') as f:
            json.dump(payload, f)
    except OSError as e:
        logger.warning("Couldn't write cache entry '%s' (%s) — continuing without it.", key, e)
