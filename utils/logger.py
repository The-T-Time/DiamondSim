# ==============================================================================
# LOGGING CONFIGURATION
# utils/logger.py
#
# Call setup_logging() once from main.py; every other module calls
# get_logger(__name__). Logs to console plus a rotating logs/simulator.log.
# ==============================================================================

from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

#Resolved in setup_logging() so we don't import config at module load time
_LOG_DIR: Path | None  = None
_CONFIGURED            = False


def setup_logging(level: int = logging.DEBUG) -> logging.Logger:
    """
    Configure the root 'mlb_sim' logger.
    Safe to call multiple times — only configures once.
    Returns the root simulator logger.
    """
    global _LOG_DIR, _CONFIGURED
    if _CONFIGURED:
        return logging.getLogger('mlb_sim')

    #Import here to avoid circular import at module level
    from config import PROJECT_ROOT
    _LOG_DIR = PROJECT_ROOT / 'logs'
    _LOG_DIR.mkdir(exist_ok=True)

    root = logging.getLogger('mlb_sim')
    root.setLevel(logging.DEBUG)   #capture everything; handlers filter by level

    #── File handler ─────────────────────────────────────────────────────────
    #Rotating: max 5 MB per file, keep 3 backups → at most ~20 MB of logs
    fh = logging.handlers.RotatingFileHandler(
        _LOG_DIR / 'simulator.log',
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding='utf-8',
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        fmt='%(asctime)s  %(levelname)-8s  %(name)s  %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))

    #── Console handler ───────────────────────────────────────────────────────
    #Plain message only — output looks identical to the old print() calls.
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))

    root.addHandler(fh)
    root.addHandler(ch)
    _CONFIGURED = True

    root.debug("Logging initialised — file: %s", _LOG_DIR / 'simulator.log')
    return root


def get_logger(name: str) -> logging.Logger:
    """
    Return a child logger under the 'mlb_sim' namespace.
    Pass __name__ for automatic module-level naming.

    Example
    -------
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Fetching schedule for %d", season)
    """
    #If setup_logging() hasn't been called yet (e.g. during tests),
    #fall back to a NullHandler so no output and no errors.
    logger = logging.getLogger(f'mlb_sim.{name}')
    if not logging.getLogger('mlb_sim').handlers:
        logger.addHandler(logging.NullHandler())
    return logger
