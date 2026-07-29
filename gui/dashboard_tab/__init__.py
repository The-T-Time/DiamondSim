# ==============================================================================
# gui/dashboard_tab/__init__.py
#
# Package entry point — re-exports DashboardTab so existing imports
# (`from gui.dashboard_tab import DashboardTab`) keep working unchanged
# after the package split.
# ==============================================================================

from gui.dashboard_tab.tab import DashboardTab

__all__ = ['DashboardTab']
