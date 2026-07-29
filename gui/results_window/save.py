# ==============================================================================
# RESULTS WINDOW — SAVE RUN
# gui/results_window/save.py
#
# The "Save run" dialog flow: prompt for a name, write the result, report
# success/failure. Still tkinter.simpledialog/messagebox (standard even
# in CTk apps — no themed CTk replacement covers simpledialog's
# `initialvalue` pre-fill or messagebox at all).
# ==============================================================================

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, simpledialog

from data.results_store import SavedResultError, save_result
from models.simulation_result import SimulationResult
from utils.logger import get_logger

logger = get_logger(__name__)


def _default_save_name(result: SimulationResult) -> str:
    name = f"{result.season}_{result.mode}"
    if result.snapshot_date:
        name += f"_{result.snapshot_date}"
    return name


def save_current_run(parent: tk.Widget, result: SimulationResult) -> None:
    """Prompts for a save name and writes `result` to disk, showing a
    success or error dialog. Does nothing if the user cancels the prompt."""
    name = simpledialog.askstring(
        'Save run', 'Name this saved run:',
        initialvalue=_default_save_name(result), parent=parent,
    )
    if not name:
        return
    try:
        path = save_result(result, name)
    except SavedResultError as e:
        logger.warning("Save run failed for %r: %s", name, e)
        messagebox.showerror('Save failed', str(e), parent=parent)
        return
    messagebox.showinfo('Saved', f'Saved as:\n{path.name}', parent=parent)
