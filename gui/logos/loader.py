# ==============================================================================
# LOGO LOADER
# gui/logos/loader.py
#
# Loads each team's logo PNG (see gui/logos/paths.py) as a tk.PhotoImage.
# A missing file isn't an error — get_team_logo() returns None and
# callers just skip the image.
# ==============================================================================

from __future__ import annotations

import tkinter as tk

from gui.logos.paths import logo_path
from utils.logger import get_logger

logger = get_logger(__name__)

#tk.PhotoImage objects must be kept referenced somewhere for the lifetime
#of whatever's displaying them, or Tkinter silently garbage-collects the
#image and the label goes blank. This module-level cache IS that
#reference — one PhotoImage per (team_id, shrink factor), loaded from
#disk once and reused across every call rather than reloaded each time a
#tab redraws.
_image_cache: dict[tuple[int, int], tk.PhotoImage] = {}


def get_team_logo(team_id: int, max_size: int = 64) -> tk.PhotoImage | None:
    """
    Returns a tk.PhotoImage for `team_id`'s logo, shrunk to fit within
    `max_size` pixels on its longest side, or None if no PNG has been added
    for this team yet at assets/logos/{team_id}.png.

    Tkinter's PhotoImage can only shrink by whole-number factors
    (`subsample`), not resize smoothly — this picks the largest integer
    factor that fits the image within max_size, which is exact for
    power-of-two-ish source sizes and close enough otherwise for a small
    UI thumbnail.

    Requires a Tk root to already exist (PhotoImage needs a default Tk
    interpreter) — call this from within GUI code, not at import time or
    from a non-GUI script.
    """
    path = logo_path(team_id)
    if not path.is_file():
        return None

    try:
        raw = tk.PhotoImage(file=str(path))
    except tk.TclError as e:
        logger.warning("Couldn't load logo PNG for team %s (%s) — skipping it.", team_id, e)
        return None

    factor = max(1, max(raw.width(), raw.height()) // max_size)
    image = raw.subsample(factor, factor) if factor > 1 else raw

    _image_cache[(team_id, factor)] = image   #keep it alive for Tkinter
    return image


def clear_cache() -> None:
    """Drops all cached PhotoImage objects — mainly useful for tests, or if
    a logo file is replaced on disk mid-session and needs a fresh reload."""
    _image_cache.clear()
