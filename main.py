# ==============================================================================
# MLB PLAYOFF SIMULATOR — ENTRY POINT
# main.py
#
# Creates the customtkinter root window and hands off to the launcher.
# ==============================================================================

from __future__ import annotations

import customtkinter as ctk

from config import LAUNCHER_WINDOW_SIZE
from utils.logger import setup_logging
from gui.widgets.theme import apply_theme
from gui.launcher import LauncherApp


def main() -> None:
    setup_logging()           #initialise file + console logging before GUI starts
    apply_theme()             #CTk appearance mode/color theme — must run before the root is created
    root = ctk.CTk()
    root.geometry(LAUNCHER_WINDOW_SIZE)
    LauncherApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()
