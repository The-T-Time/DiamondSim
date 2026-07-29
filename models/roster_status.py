# ==============================================================================
# ROSTER STATUS
# models/roster_status.py
#
# The MLB Stats API roster-status convention shared by every module that
# needs "is this player active/injured?" — 'A' (active) means available
# to play; IL*/D1*/D6* mean injured; anything else is unavailable but not
# specifically an injury.
# ==============================================================================

from __future__ import annotations

ACTIVE_STATUS_CODE: str = 'A'
INJURY_STATUS_PREFIXES: tuple[str, ...] = ('IL', 'D1', 'D6')


def is_active_status(status_code: str) -> bool:
    """Whether `status_code` means this player can take the field/mound
    right now."""
    return status_code == ACTIVE_STATUS_CODE


def is_injury_status(status_code: str) -> bool:
    """Whether `status_code` specifically indicates an injury (narrower
    than `not is_active_status` — excludes optioned/suspended/restricted)."""
    return status_code.startswith(INJURY_STATUS_PREFIXES)
