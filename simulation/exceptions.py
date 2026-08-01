# ==============================================================================
# SIMULATION EXCEPTIONS
# simulation/exceptions.py
#
# Distinct exception types for the simulation engine, mirroring
# data/exceptions.py's reasoning: give callers (the GUI, mainly) a way to
# tell "the user asked us to stop" apart from "something actually broke."
# ==============================================================================

from __future__ import annotations


class SimulationCancelled(Exception):
    """
    Raised when a run is stopped mid-flight via the GUI's Cancel button
    (see gui/launcher/run_action.py). Not an error — the caller should
    quietly reset the UI rather than show an error dialog.
    """
