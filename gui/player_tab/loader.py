# ==============================================================================
# LOADER
# gui/player_tab/loader.py
#
# Fetches every team's pitchers and hitters on a background thread so
# opening the Player Tab never freezes the results window — same
# threading/polling pattern as gui/launcher/run_action.py.
# ==============================================================================

from __future__ import annotations

import threading
import tkinter as tk
from typing import Callable

from models.simulation_config import SimulationConfig
from simulation.player_directory import build_hitter_rows, build_pitcher_rows
from utils.logger import get_logger

logger = get_logger(__name__)


def load_players_async(
    anchor: tk.Widget,
    season: int,
    as_of_date: str,
    cfg: SimulationConfig,
    on_success: Callable[[list[dict], list[dict]], None],
    on_error: Callable[[Exception], None],
) -> None:
    """
    Fetches pitcher and hitter rows for every team on a background thread,
    then calls `on_success(pitcher_rows, hitter_rows)` (or `on_error(exc)`)
    back on the main thread via `anchor.after(...)`. `anchor` is any live
    Tk widget — polling stops silently if it's destroyed mid-fetch.
    """
    holder: dict[str, object] = {}

    def worker() -> None:
        try:
            pitcher_rows = build_pitcher_rows(season, as_of_date, cfg)
            hitter_rows = build_hitter_rows(season, as_of_date, cfg)
            holder['result'] = (pitcher_rows, hitter_rows)
        except Exception as e:          #noqa: BLE001 — surfaced on main thread
            holder['error'] = e

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    _poll(anchor, thread, holder, on_success, on_error)


def _poll(
    anchor: tk.Widget, thread: threading.Thread, holder: dict,
    on_success: Callable[[list[dict], list[dict]], None],
    on_error: Callable[[Exception], None],
) -> None:
    try:
        anchor.winfo_exists()
    except tk.TclError:
        logger.debug("Player Tab was closed before its data finished loading — abandoning polling.")
        return

    if thread.is_alive():
        anchor.after(150, lambda: _poll(anchor, thread, holder, on_success, on_error))
        return

    try:
        if 'error' in holder:
            on_error(holder['error'])
        else:
            pitcher_rows, hitter_rows = holder['result']
            on_success(pitcher_rows, hitter_rows)
    except tk.TclError:
        logger.debug("Player Tab was closed just as its data finished loading — dropping the result.")
