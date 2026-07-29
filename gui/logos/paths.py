# ==============================================================================
# LOGO PATHS
# gui/logos/paths.py
#
# Where a team's logo PNG is expected to live on disk, and whether it's
# actually there yet. No Tkinter dependency here.
# ==============================================================================

from __future__ import annotations

from pathlib import Path

from config import PROJECT_ROOT

LOGOS_DIR: Path = PROJECT_ROOT / 'assets' / 'logos'


def logo_path(team_id: int) -> Path:
    """Where `team_id`'s logo PNG is expected to live, e.g. assets/logos/147.png."""
    return LOGOS_DIR / f"{team_id}.png"


def has_logo(team_id: int) -> bool:
    """Whether a PNG has been added for this team yet — lets calling code
    decide to skip reserving layout space for a logo at all, rather than
    just getting back None after the fact."""
    return logo_path(team_id).is_file()
