# ==============================================================================
# gui/logos/__init__.py
#
# Package entry point — re-exports the same public names the old flat
# gui/logos.py module had, so existing imports (`from gui.logos import
# get_team_logo`) keep working unchanged after the package split.
# ==============================================================================

from gui.logos.loader import clear_cache, get_team_logo
from gui.logos.paths import LOGOS_DIR, has_logo, logo_path

__all__ = ['get_team_logo', 'clear_cache', 'has_logo', 'logo_path', 'LOGOS_DIR']
