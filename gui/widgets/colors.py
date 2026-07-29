# ==============================================================================
# COLORS
# gui/widgets/colors.py
#
# Single source of truth for every hex color used across the GUI — import
# from here, never hard-code a hex color in a tab file. Structural colors
# (backgrounds/text) switch between light/dark theme variants; accent
# colors (green/red/gold/etc.) stay the same in both since they carry
# semantic meaning (win/loss, division leader, etc.).
# ==============================================================================

from data.settings_store import load_settings

_theme = load_settings().theme   #'light' | 'dark'
_dark = (_theme == 'dark')

#── structural colors: flip between themes ──────────────────────────────────
if _dark:
    C_BG          = '#1a1d21'   #main window / tab background
    C_DARK        = '#ecf0f1'   #header bars, primary text (light-on-dark)
    C_MID         = '#c3ccd1'   #secondary text
    C_PANEL       = '#202329'   #left-pane panel background
    C_HDR         = '#2b2f36'   #column header row
    C_WHITE       = '#25282e'   #card/table surface ("white" in light mode)
    C_ROW_ALT     = '#20242c'   #alternating row tint
    C_SELECTED    = '#25384a'   #selected row
    C_HOVER       = '#2b4054'   #hovered row (not selected)
    C_SASH        = '#3a3f45'   #PanedWindow sash
    C_GRAY        = '#8a949c'
    C_LIGHT_GRAY  = '#2a2e33'
    C_DIV_LEAD    = '#3a3520'   #division leader row tint (dark cream)
    C_WC_IN       = '#1c3329'   #wild card in-spot row tint (dark mint)
else:
    C_BG          = '#f8f9fa'   #main window / tab background
    C_DARK        = '#2c3e50'   #header bars, dark text
    C_MID         = '#34495e'   #secondary dark text
    C_PANEL       = '#ecf0f1'   #left-pane panel background
    C_HDR         = '#d5dbdb'   #column header row
    C_WHITE       = 'white'
    C_ROW_ALT     = '#eaf1fb'   #alternating row tint
    C_SELECTED    = '#d6eaf8'   #selected row
    C_HOVER       = '#c8dff0'   #hovered row (not selected)
    C_SASH        = '#bdc3c7'   #PanedWindow sash
    C_GRAY        = '#95a5a6'
    C_LIGHT_GRAY  = '#eaecee'
    C_DIV_LEAD    = '#fef9e7'   #cream  — division leader row
    C_WC_IN       = '#eafaf1'   #mint   — wild card in-spot row

#── accent colors: identical in both themes ──────────────────────────────────
C_GREEN       = '#27ae60'
C_BLUE        = '#2980b9'
C_BLUE_DARK   = '#1a5276'   #AL division title bars
C_GREEN_DARK  = '#145a32'   #NL division title bars
C_RED         = '#c0392b'
C_ORANGE      = '#e67e22'
C_GOLD        = '#d4ac0d'

C_WIN_HDR     = C_GREEN     #WIN header in game popup
C_LOSS_HDR    = C_RED       #LOSS header in game popup

#Fixed dark-navy accent bar + its text — used for header bars, panel title
#bars, etc. that should always look the same regardless of theme (the
#same idea as C_BLUE_DARK/C_GREEN_DARK division title bars already
#being theme-invariant). Do NOT use C_DARK/C_WHITE for this: those are
#theme-reactive body text/surface colors, and using them for a bar that's
#meant to always be dark-with-white-text produces a light bar with
#unreadable dark-on-dark text once dark theme is active.
C_HEADER_BAR  = '#2c3e50'
C_HEADER_TEXT = 'white'
