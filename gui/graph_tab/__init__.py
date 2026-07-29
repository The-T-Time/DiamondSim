# ==============================================================================
# gui/graph_tab/__init__.py
#
# Package entry point — re-exports GraphTab so existing imports
# (`from gui.graph_tab import GraphTab`) keep working unchanged after the
# Package split.
# ==============================================================================

from gui.graph_tab.tab import GraphTab

__all__ = ['GraphTab']
