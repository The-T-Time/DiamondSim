# ==============================================================================
# SIMULATION RUNNER
# simulation/runner.py
#
# The single interface the GUI uses to run simulations. The GUI imports only
# SimulationRunner — it never touches fetch_*, run_simulation_core, or any
# other internal. This keeps the GUI/sim boundary clean: swap out the
# simulation engine without touching a single line of GUI code.
# ==============================================================================

from __future__ import annotations

import threading
from typing import Callable

from models.simulation_config import SimulationConfig
from models.simulation_result import SimulationResult
from simulation.exceptions import SimulationCancelled
from simulation.simulator import (
    fetch_simulation_data,
    fetch_backtest_data,
    run_simulation_core,
)
from utils.logger import get_logger

logger = get_logger(__name__)


class SimulationRunner:
    """
    Thin controller: translate GUI intent -> simulation data -> SimulationResult.

    Usage
    -----
    runner = SimulationRunner()
    result = runner.run_simulate(season=2026, cfg=SimulationConfig(simulations=100_000))
    result = runner.run_backtest(season=2024, snapshot_date='2024-07-01',
                                  cfg=SimulationConfig.conservative())
    """

    def run_simulate(
        self,
        season: int,
        cfg: SimulationConfig = SimulationConfig(),
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> SimulationResult:
        """Forward-project the current season from today's live standings."""
        logger.info("=== SIMULATE MODE: %d season, %s sims ===",
                    season, f"{cfg.simulations:,}")
        data = fetch_simulation_data(season, cfg)
        if cancel_event is not None and cancel_event.is_set():
            raise SimulationCancelled()
        return run_simulation_core(data, season=season, mode='simulate', cfg=cfg,
                                   progress_callback=progress_callback, cancel_event=cancel_event)

    def run_backtest(
        self,
        season: int,
        snapshot_date: str,
        cfg: SimulationConfig = SimulationConfig(),
        progress_callback: Callable[[int, int], None] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> SimulationResult:
        """Test prediction accuracy at a historical mid-season snapshot date."""
        logger.info("=== BACKTEST: %d, snapshot %s, %s sims ===",
                    season, snapshot_date, f"{cfg.simulations:,}")
        data = fetch_backtest_data(season, snapshot_date, cfg)
        if cancel_event is not None and cancel_event.is_set():
            raise SimulationCancelled()
        return run_simulation_core(data, season=season, mode='backtest',
                                    snapshot_date=snapshot_date, cfg=cfg,
                                    progress_callback=progress_callback, cancel_event=cancel_event)
