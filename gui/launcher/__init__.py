# ==============================================================================
# gui/launcher/__init__.py
#
# Package entry point — re-exports LauncherApp so existing imports
# (`from gui.launcher import LauncherApp`) keep working unchanged after the
# Package split.
# ==============================================================================

from gui.launcher.app import LauncherApp

__all__ = ['LauncherApp']
