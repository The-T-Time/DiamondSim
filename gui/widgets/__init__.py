# ==============================================================================
# gui/widgets/__init__.py
#
# Package entry point — re-exports every name the old flat gui/widgets.py
# module had, so existing imports (`from gui.widgets import FONT_NORMAL,
# C_BG, SortableTable, ...`) keep working unchanged after the package
# split. Never hard-code a hex color or font string directly in a
# tab file — import from here (or the specific submodule).
# ==============================================================================

from gui.widgets.colors import (
    C_BG, C_DARK, C_MID, C_PANEL, C_HDR, C_WHITE, C_ROW_ALT, C_SELECTED,
    C_HOVER, C_SASH, C_GREEN, C_GREEN_HOVER, C_BLUE, C_BLUE_DARK, C_GREEN_DARK, C_RED,
    C_RED_HOVER, C_ORANGE, C_ORANGE_DARK, C_GOLD, C_GRAY, C_LIGHT_GRAY, C_DIV_LEAD, C_WC_IN,
    C_WIN_HDR, C_LOSS_HDR, C_HEADER_BAR, C_HEADER_TEXT,
)
from gui.widgets.fonts import (
    FONT_TINY, FONT_TINY_BOLD, FONT_SMALL, FONT_SMALL_BOLD, FONT_NORMAL,
    FONT_NORMAL_BOLD, FONT_MEDIUM, FONT_MEDIUM_BOLD, FONT_HEADER,
    FONT_TITLE, FONT_LARGE, FONT_SCORE,
)
from gui.widgets.sizes import (
    W_RANK, W_SMALL, W_MED, W_LARGE, W_XL, W_DATE, W_HA, W_RESULT, W_DIV,
    W_TEAM_XS, W_TEAM, W_TEAM_LG, W_OPPONENT, W_STREAK, W_WL_PAIR,
)
from gui.widgets.layout import (
    create_scrollable_frame, make_header_bar, make_table_header,
    make_data_row, make_stat_card, set_row_bg, bind_hover,
)
from gui.widgets.formatting import format_decimal, format_pct
from gui.widgets.table import Column, SortableTable, dpi_scale
from gui.widgets.tooltip import add_tooltip

__all__ = [
    #colors
    'C_BG', 'C_DARK', 'C_MID', 'C_PANEL', 'C_HDR', 'C_WHITE', 'C_ROW_ALT',
    'C_SELECTED', 'C_HOVER', 'C_SASH', 'C_GREEN', 'C_GREEN_HOVER', 'C_BLUE', 'C_BLUE_DARK',
    'C_GREEN_DARK', 'C_RED', 'C_RED_HOVER', 'C_ORANGE', 'C_ORANGE_DARK', 'C_GOLD', 'C_GRAY', 'C_LIGHT_GRAY',
    'C_DIV_LEAD', 'C_WC_IN', 'C_WIN_HDR', 'C_LOSS_HDR', 'C_HEADER_BAR', 'C_HEADER_TEXT',
    #fonts
    'FONT_TINY', 'FONT_TINY_BOLD', 'FONT_SMALL', 'FONT_SMALL_BOLD',
    'FONT_NORMAL', 'FONT_NORMAL_BOLD', 'FONT_MEDIUM', 'FONT_MEDIUM_BOLD',
    'FONT_HEADER', 'FONT_TITLE', 'FONT_LARGE', 'FONT_SCORE',
    #sizes
    'W_RANK', 'W_SMALL', 'W_MED', 'W_LARGE', 'W_XL', 'W_DATE', 'W_HA',
    'W_RESULT', 'W_DIV', 'W_TEAM_XS', 'W_TEAM', 'W_TEAM_LG', 'W_OPPONENT',
    'W_STREAK', 'W_WL_PAIR',
    #layout helpers
    'create_scrollable_frame', 'make_header_bar', 'make_table_header',
    'make_data_row', 'make_stat_card', 'set_row_bg', 'bind_hover',
    #table
    'Column', 'SortableTable', 'dpi_scale',
    #formatting
    'format_decimal', 'format_pct',
    #tooltip
    'add_tooltip',
]
