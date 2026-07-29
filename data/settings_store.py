# ==============================================================================
# SETTINGS STORE
# data/settings_store.py
#
# Persists AppSettings to a small JSON file. Every field on
# AppSettings is a primitive (str/int/float/bool), so unlike
# results_store.py this needs no custom (de)serialization — just
# dataclasses.asdict() and **kwargs back.
# ==============================================================================

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from models.app_settings import AppSettings, settings_field_names

_SETTINGS_PATH = Path(__file__).resolve().parent.parent / 'user_settings.json'


def load_settings() -> AppSettings:
    """Returns the saved settings, or defaults if none have been saved yet
    (first run) or the file is corrupt/unreadable — a broken settings file
    should never prevent the app from starting."""
    if not _SETTINGS_PATH.exists():
        return AppSettings()
    try:
        with open(_SETTINGS_PATH) as f:
            payload = json.load(f)
    except (json.JSONDecodeError, OSError):
        return AppSettings()

    #Only accept known fields — if a saved file has fields from an older
    #or newer version of AppSettings, ignore what doesn't apply rather
    #than fail to load.
    known = settings_field_names()
    kwargs = {k: v for k, v in payload.items() if k in known}
    try:
        return AppSettings(**kwargs)
    except TypeError:
        return AppSettings()


def save_settings(settings: AppSettings) -> None:
    with open(_SETTINGS_PATH, 'w') as f:
        json.dump(dataclasses.asdict(settings), f, indent=2)


def reset_to_default() -> AppSettings:
    """Resets the saved settings to AppSettings' hardcoded defaults (which
    themselves come from config.py) and persists that reset."""
    defaults = AppSettings()
    save_settings(defaults)
    return defaults
