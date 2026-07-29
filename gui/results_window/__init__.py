# ==============================================================================
# gui/results_window/__init__.py
#
# Package entry point — re-exports ResultsWindow so existing imports
# (`from gui.results_window import ResultsWindow`) keep working unchanged
# after the package split.
# ==============================================================================

from gui.results_window.window import ResultsWindow

__all__ = ['ResultsWindow']
