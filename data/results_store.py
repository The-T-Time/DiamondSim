# ==============================================================================
# SAVED RESULTS STORE
# data/results_store.py
#
# Persist a finished SimulationResult to disk (versioned JSON in
# saved_results/) and load it back, so a run can be reopened later
# without re-fetching or re-simulating.
# ==============================================================================

from __future__ import annotations

import dataclasses
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from config import PROJECT_ROOT
from data.cache import _from_jsonable, _to_jsonable
from data.exceptions import DataFetchError
from models.playoff_bracket import PlayoffBracketResult
from models.simulation_config import SimulationConfig
from models.simulation_result import SimulationResult
from utils.logger import get_logger

logger = get_logger(__name__)

SCHEMA_VERSION = 1
SAVE_DIR: Path = PROJECT_ROOT / 'saved_results'

#The three keys cache's helpers know how to convert (Game lists + elo_log).
_GAME_KEYS = ('played_games', 'unplayed_games', 'elo_log')


class SavedResultError(Exception):
    """A saved-results file couldn't be written or read back cleanly."""


def _slugify(name: str) -> str:
    slug = re.sub(r'[^A-Za-z0-9]+', '_', name.strip()).strip('_').lower()
    return slug or 'run'


def _bracket_to_jsonable(bracket: PlayoffBracketResult | None) -> dict[str, Any] | None:
    if bracket is None:
        return None
    return dataclasses.asdict(bracket)   #tuples -> lists automatically


def _bracket_from_jsonable(payload: dict[str, Any] | None) -> PlayoffBracketResult | None:
    if payload is None:
        return None
    tuple_fields = (
        'al_seeds', 'nl_seeds', 'al_wc_winners', 'nl_wc_winners',
        'al_ds_winners', 'nl_ds_winners',
    )
    kwargs = dict(payload)
    for key in tuple_fields:
        kwargs[key] = tuple(kwargs[key])
    return PlayoffBracketResult(**kwargs)


def _result_to_jsonable(result: SimulationResult) -> dict[str, Any]:
    game_part = _to_jsonable({
        'played_games': result.played_games,
        'unplayed_games': result.unplayed_games,
        'elo_log': result.elo_log,
    })
    return {
        'mode':                   result.mode,
        'season':                 result.season,
        'snapshot_date':          result.snapshot_date,
        'cfg':                    dataclasses.asdict(result.cfg),
        'playoff_odds':           result.playoff_odds,
        'world_series_odds':      result.world_series_odds,
        'live_elo':               result.live_elo,
        'live_standings':         result.live_standings,
        'true_playoff_teams':     result.true_playoff_teams,
        'projected_team_stats':   result.projected_team_stats,
        'unplayed_game_home_win_pct': {str(pk): v for pk, v in result.unplayed_game_home_win_pct.items()},
        'projected_bracket':      _bracket_to_jsonable(result.projected_bracket),
        'projected_bracket_pct':  result.projected_bracket_pct,
        'projected_bracket_tied_count': result.projected_bracket_tied_count,
        **game_part,
    }


def _result_from_jsonable(payload: dict[str, Any]) -> SimulationResult:
    game_part = _from_jsonable({k: payload[k] for k in _GAME_KEYS if k in payload})
    cfg = SimulationConfig(**payload['cfg'])
    return SimulationResult(
        mode=payload['mode'],
        season=payload['season'],
        snapshot_date=payload.get('snapshot_date'),
        cfg=cfg,
        playoff_odds=payload.get('playoff_odds', {}),
        world_series_odds=payload.get('world_series_odds', {}),
        live_elo=payload.get('live_elo', {}),
        elo_log=game_part.get('elo_log', {}),
        live_standings=payload.get('live_standings', {}),
        played_games=game_part.get('played_games', []),
        unplayed_games=game_part.get('unplayed_games', []),
        true_playoff_teams=payload.get('true_playoff_teams', []),
        #Absent in files saved before — default to "no projection
        #available" rather than failing to load an older saved run.
        projected_team_stats=payload.get('projected_team_stats', {}),
        unplayed_game_home_win_pct={
            int(pk): v for pk, v in payload.get('unplayed_game_home_win_pct', {}).items()
        },
        projected_bracket=_bracket_from_jsonable(payload.get('projected_bracket')),
        projected_bracket_pct=payload.get('projected_bracket_pct', 0.0),
        projected_bracket_tied_count=payload.get('projected_bracket_tied_count', 0),
    )


def save_result(result: SimulationResult, name: str) -> Path:
    """Serialise `result` under a human-readable `name`. Returns the file path.

    Filenames are unique (slug + timestamp, plus a counter on the rare
    same-minute collision) so saving twice never silently overwrites."""
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M')
    slug = _slugify(name)
    path = SAVE_DIR / f"{slug}_{stamp}.json"
    counter = 1
    while path.exists():
        path = SAVE_DIR / f"{slug}_{stamp}_{counter}.json"
        counter += 1

    document = {
        'schema_version': SCHEMA_VERSION,
        'saved_at':       datetime.now().isoformat(timespec='seconds'),
        'name':           name,
        'result':         _result_to_jsonable(result),
    }
    try:
        with open(path, 'w') as f:
            json.dump(document, f, indent=2)
    except OSError as e:
        raise SavedResultError(f"Couldn't write saved result to {path.name}: {e}") from e
    logger.info("Saved simulation result to %s", path.name)
    return path


def load_result(path: str | Path) -> SimulationResult:
    """Load a saved result back into a SimulationResult. Raises
    SavedResultError on a missing, corrupt, or wrong-schema file."""
    path = Path(path)
    try:
        with open(path) as f:
            document = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise SavedResultError(f"Couldn't read saved result {path.name}: {e}") from e

    version = document.get('schema_version')
    if version != SCHEMA_VERSION:
        raise SavedResultError(
            f"Saved result {path.name} has schema version {version!r}; "
            f"this build expects {SCHEMA_VERSION}."
        )
    try:
        return _result_from_jsonable(document['result'])
    except (KeyError, TypeError, ValueError) as e:
        raise SavedResultError(f"Saved result {path.name} is malformed: {e}") from e


def list_saved_results() -> list[tuple[str, Path, str, int, str]]:
    """Return saved runs as (name, path, saved_at, season, mode), newest first.

    Individual unreadable files are skipped rather than aborting the listing."""
    if not SAVE_DIR.exists():
        return []
    out: list[tuple[str, Path, str, int, str]] = []
    for path in sorted(SAVE_DIR.glob('*.json'), reverse=True):
        try:
            with open(path) as f:
                doc = json.load(f)
            result = doc['result']
            out.append((
                doc.get('name', path.stem),
                path,
                doc.get('saved_at', ''),
                int(result.get('season', 0)),
                result.get('mode', '?'),
            ))
        except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            logger.warning("Skipping unreadable saved result %s: %s", path.name, e)
            continue
    out.sort(key=lambda r: r[2], reverse=True)
    return out


#DataFetchError is imported so callers can share one messagebox path for both
#"couldn't load MLB data" and "couldn't load a saved run" if they prefer.
__all__ = [
    'save_result', 'load_result', 'list_saved_results',
    'SavedResultError', 'DataFetchError', 'SAVE_DIR', 'SCHEMA_VERSION',
]
