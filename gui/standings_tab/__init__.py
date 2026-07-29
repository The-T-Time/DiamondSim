# ==============================================================================
# gui/standings_tab/__init__.py
#
# Package entry point — re-exports StandingsTab so existing imports
# (`from gui.standings_tab import StandingsTab`) keep working unchanged
# after the package split.
# ==============================================================================

from gui.standings_tab.tab import StandingsTab

__all__ = ['StandingsTab']
