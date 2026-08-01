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
from simulation.exceptions import SimulationCancelled
from utils.logger import get_logger

logger = get_logger(__name__)


def run_action_with_progress(
    root: ctk.CTk,
    run_btn: ctk.CTkButton,
    cancel_btn: ctk.CTkButton,
    idle_label: str,
    action: Callable[[Callable[[int, int], None], threading.Event], SimulationResult],
    progress: ProgressIndicator,
    back_btn: ctk.CTkButton | None = None,
) -> None:
    """Disables `run_btn` and the persistent top-left `back_btn` (if
    given), enables `cancel_btn`, shows `progress`, runs `action` on a
    background thread, and opens a ResultsWindow (or a friendly error
    dialog) once it finishes. `action` receives a progress callback and a
    threading.Event it should treat as "stop as soon as practical" —
    `cancel_btn` sets that same event."""
    prog_q: queue.Queue[tuple[int, int]] = queue.Queue()
    holder: dict[str, object] = {}
    cancel_event = threading.Event()

    run_btn.configure(text='Running…', state='disabled')
    if back_btn is not None:
        back_btn.configure(state='disabled')
    cancel_btn.configure(text='✕  Cancel', state='normal', command=lambda: _request_cancel(cancel_btn, cancel_event))
    progress.show()

    def worker() -> None:
        def cb(done: int, total: int) -> None:
            prog_q.put((done, total))
        try:
            holder['result'] = action(cb, cancel_event)
        except Exception as e:          #noqa: BLE001 — surfaced on main thread
            holder['error'] = e

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    _poll_run(root, thread, prog_q, holder, run_btn, cancel_btn, idle_label, progress, back_btn)


def _request_cancel(cancel_btn: ctk.CTkButton, cancel_event: threading.Event) -> None:
    """Cancel was clicked: signal the run and give immediate feedback —
    the run itself may take a moment to actually unwind (see
    simulation/simulator.py's cancellation checkpoints), so a disabled
    'Cancelling…' state confirms the click registered instead of leaving
    the button looking unresponsive."""
    cancel_event.set()
    cancel_btn.configure(text='Cancelling…', state='disabled')


def _poll_run(
    root: ctk.CTk, thread: threading.Thread, prog_q: queue.Queue,
    holder: dict, run_btn: ctk.CTkButton, cancel_btn: ctk.CTkButton,
    idle_label: str, progress: ProgressIndicator, back_btn: ctk.CTkButton | None,
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
                root, thread, prog_q, holder, run_btn, cancel_btn, idle_label, progress, back_btn))
            return

        progress.hide()
        run_btn.configure(text=idle_label, state='normal')
        cancel_btn.configure(text='✕  Cancel', state='disabled')
        if back_btn is not None:
            back_btn.configure(state='normal')
    except tk.TclError:
        logger.debug("Run screen was closed mid-update — abandoning polling.")
        return

    if 'error' in holder:
        e = holder['error']
        if isinstance(e, SimulationCancelled):
            logger.info("Run cancelled by the user.")
        elif isinstance(e, DataFetchError):
            messagebox.showerror("Couldn't load MLB data",
                                 f"{e}\n\nCheck your internet connection and try again.")
        else:
            logger.exception("Unexpected error while running a simulation", exc_info=e)
            messagebox.showerror('Unexpected error',
                                 f"Something went wrong and the run couldn't finish:\n\n{e}")
        return
    ResultsWindow(root, holder['result'])
