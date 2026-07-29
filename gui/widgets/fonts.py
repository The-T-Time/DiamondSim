# ==============================================================================
# FONTS
# gui/widgets/fonts.py
#
# Single source of truth for every font used across the GUI — Oswald for
# big/header text, Inter for small/body text. Import these FONT_*
# constants; never hard-code a family/size in a tab file.
# ==============================================================================

_BIG_FAMILY = 'Oswald'      #headers, titles, scoreboard numbers
_SMALL_FAMILY = 'Inter'     #everything else — body text, table cells, buttons

FONT_TINY        = (_SMALL_FAMILY, 10)
FONT_TINY_BOLD   = (_SMALL_FAMILY, 10, 'bold')
FONT_SMALL       = (_SMALL_FAMILY, 12)
FONT_SMALL_BOLD  = (_SMALL_FAMILY, 12, 'bold')
FONT_NORMAL      = (_SMALL_FAMILY, 13)
FONT_NORMAL_BOLD = (_SMALL_FAMILY, 13, 'bold')
FONT_MEDIUM      = (_SMALL_FAMILY, 14)
FONT_MEDIUM_BOLD = (_SMALL_FAMILY, 14, 'bold')
FONT_HEADER      = (_BIG_FAMILY,   16, 'bold')
FONT_TITLE       = (_BIG_FAMILY,   18, 'bold')
FONT_LARGE       = (_BIG_FAMILY,   22, 'bold')
FONT_SCORE       = (_BIG_FAMILY,   32, 'bold')
