# ==============================================================================
# gui/teams_tab/__init__.py
#
# Package entry point — re-exports TeamsTab so existing imports
# (`from gui.teams_tab import TeamsTab`) keep working unchanged after the
# Package split.
# ==============================================================================

from gui.teams_tab.tab import TeamsTab

__all__ = ['TeamsTab']
