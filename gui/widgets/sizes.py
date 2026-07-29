# ==============================================================================
# SIZES
# gui/widgets/sizes.py
#
# Semantic column widths (Tk character units) — e.g. "enough chars for a
# W/L count". Referenced by name, so a font-size change only needs
# proportional review here, not changes throughout the codebase.
# ==============================================================================

W_RANK       = 4    ##, row number
W_SMALL      = 4    #W, L single digit counts
W_MED        = 6    #PCT, GB, L10
W_LARGE      = 8    #Odds %, Elo Δ, score
W_XL         = 10   #Elo rating (4 digits + decimal)
W_DATE       = 11   #YYYY-MM-DD
W_HA         = 4    #H / A indicator
W_RESULT     = 6    #W / L result cell
W_DIV        = 9    #division abbreviation  e.g. "NL West"
W_TEAM_XS    = 16   #narrow team column (left-pane list)
W_TEAM       = 22   #standard team name
W_TEAM_LG    = 26   #wide team name (stats/standings)
W_OPPONENT   = 22   #opponent column in game log
W_STREAK     = 5    #W3 / L2
W_WL_PAIR    = 7    #"82-80" formatted W-L pair
