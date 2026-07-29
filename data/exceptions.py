# ==============================================================================
# DATA EXCEPTIONS
# data/exceptions.py
#
# Distinct exception types so callers (the GUI, mainly) can tell "the
# internet/API is the problem" apart from "something in our own code broke,"
# and show the user something better than a raw traceback.
# ==============================================================================

from __future__ import annotations


class DataFetchError(Exception):
    """
    The MLB Stats API couldn't be reached, timed out, or returned something
    we can't parse (bad JSON, missing fields, unexpected shape). Not
    recoverable within the request — the caller should surface it to the
    user rather than retry silently.
    """


class CacheError(Exception):
    """
    The on-disk cache exists but is corrupted/unreadable. Recoverable —
    callers should treat this as a cache miss and refetch, not crash.
    Currently only raised internally by data/cache.py, which catches it
    itself; kept as a public type in case other code wants to catch it too.
    """
