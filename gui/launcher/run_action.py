# ==============================================================================
# RUN ACTION
# gui/launcher/run_action.py
#
# Runs a simulate/backtest action on a background thread so the UI stays
# responsive with live progress, then routes the result back to the main
# thread. The worker never touches Tk — progress/result flow through a
# Queue, polled from the main thread via root.after.
# ==============================================================================

from __future__ import annotations

import queue
import threading
import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional

from data.exceptions import DataFetchError
from gui.launcher.progress import ProgressIndicator
from gui.results_window import ResultsWindow
from models.simulation_result import SimulationResult
from utils.logger import get_logger

logger = get_logger(__name__)


def run_action_with_progress(
    root: ctk.CTk,
    run_btn: ctk.CTkButton,
    back_btn: ctk.CTkButton,
    idle_label: str,
    action: Callable[[Callable[[int, int], None]], SimulationResult],
    progress: ProgressIndicator,
) -> None:
    """Disables `run_btn`/`back_btn`, shows `progress`, runs `action` on a
    background thread, and opens a ResultsWindow (or a friendly error
    dialog) once it finishes."""
    prog_q: queue.Queue[tuple[int, int]] = queue.Queue()
    holder: dict[str, object] = {}

    run_btn.configure(text='Simulating…', state='disabled')
    back_btn.configure(state='disabled')
    progress.show()

    def worker() -> None:
        def cb(done: int, total: int) -> None:
            prog_q.put((done, total))
        try:
            holder['result'] = action(cb)
        except Exception as e:          #noqa: BLE001 — surfaced on main thread
            holder['error'] = e

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    _poll_run(root, thread, prog_q, holder, run_btn, back_btn, idle_label, progress)


def _poll_run(
    root: ctk.CTk, thread: threading.Thread, prog_q: queue.Queue,
    holder: dict, run_btn: ctk.CTkButton, back_btn: ctk.CTkButton,
    idle_label: str, progress: ProgressIndicator,
) -> None:
    #If the window (or just this screen) was torn down while the run was
    #still in flight, every widget reference below is dead. There's
    #nothing left to update — stop polling rather than raise. The
    #simulation itself keeps running to completion on its daemon thread;
    #its result is simply never shown, which is the right behavior for
    #"the user navigated away."
    try:
        run_btn.winfo_exists()
    except tk.TclError:
        logger.debug("Run screen was closed before the simulation finished — abandoning polling.")
        return

    latest: Optional[tuple[int, int]] = None
    try:
        while True:
            latest = prog_q.get_nowait()
    except queue.Empty:
        pass

    try:
        if latest is not None:
            progress.update(*latest)
        else:
            progress.pulse()

        if thread.is_alive():
            root.after(100, lambda: _poll_run(
                root, thread, prog_q, holder, run_btn, back_btn, idle_label, progress))
            return

        progress.hide()
        run_btn.configure(text=idle_label, state='normal')
        back_btn.configure(state='normal')
    except tk.TclError:
        logger.debug("Run screen was closed mid-update — abandoning polling.")
        return

    if 'error' in holder:
        e = holder['error']
        if isinstance(e, DataFetchError):
            messagebox.showerror("Couldn't load MLB data",
                                 f"{e}\n\nCheck your internet connection and try again.")
        else:
            logger.exception("Unexpected error while running a simulation", exc_info=e)
            messagebox.showerror('Unexpected error',
                                 f"Something went wrong and the run couldn't finish:\n\n{e}")
        return
    ResultsWindow(root, holder['result'])
