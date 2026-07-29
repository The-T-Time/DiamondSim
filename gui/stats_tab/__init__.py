# ==============================================================================
# gui/stats_tab/__init__.py
#
# Package entry point — re-exports StatsTab so existing imports
# (`from gui.stats_tab import StatsTab`) keep working unchanged after the
# Package split.
# ==============================================================================

from gui.stats_tab.tab import StatsTab

__all__ = ['StatsTab']
