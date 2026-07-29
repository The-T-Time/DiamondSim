# ==============================================================================
# DETERMINISTIC SEEDING
# simulation/deterministic_seed.py
#
# A random.Random seeded deterministically from a team name (not
# Python's per-process-randomized hash()) plus a caller-chosen salt —
# shared by every synthetic-fallback generator that needs the same team
# to always produce the same result run to run.
# ==============================================================================

from __future__ import annotations

import random
import zlib

from models.team import TeamName


def team_seed(team: TeamName, salt: int) -> random.Random:
    """
    A random.Random seeded deterministically from `team` and `salt`. Two
    calls with the same team name and salt always produce generators that
    yield the same sequence; different salts let the same team drive
    multiple independent-looking generators (e.g. one for a rotation, one
    for a bullpen) without them all producing identical jitter.
    """
    return random.Random(zlib.crc32(team.encode('utf-8')) ^ salt)
