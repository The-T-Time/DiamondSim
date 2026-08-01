# ==============================================================================
# MLB PLAYOFF SIMULATOR — CONFIGURATION
# config.py
# ==============================================================================

from pathlib import Path

#Project root — used for cache paths so runs work regardless of cwd.
PROJECT_ROOT: Path = Path(__file__).resolve().parent

#------------------------------------------------------------------------------
#APP IDENTITY
#------------------------------------------------------------------------------

APP_NAME: str = 'DiamondSim'
APP_VERSION: str = '1.0.2'

#------------------------------------------------------------------------------
#CACHING
#------------------------------------------------------------------------------

#Toggle disk caching entirely.  Set False when testing or pulling fresh data.
CACHE_ENABLED: bool = True

#Seconds before a cache file is considered stale and re-fetched.
#Default: 7200 (2 hours).  Set to 0 to always re-fetch while keeping cache on.
CACHE_EXPIRY_SECONDS: int = 7200

#------------------------------------------------------------------------------
#ELO SYSTEM
#------------------------------------------------------------------------------

#Base K-factor applied to every game result.
#Higher values = Elo shifts faster / reacts more to recent results.
#Typical range: 16–32.
ELO_K: int = 30

#Home-field advantage expressed as Elo points added to the home team when computing win probability.
HOME_FIELD_ADVANTAGE: int = 15

#Starting Elo for all teams at the beginning of a fresh simulation
ELO_BASELINE: float = 1500.0

#------------------------------------------------------------------------------
#YEAR-OVER-YEAR REGRESSION
#------------------------------------------------------------------------------

#How much each team's closing Elo from the prior season carries forward.
#The remainder (1 - REGRESSION_WEIGHT) reverts to ELO_BASELINE.
#Range: 0.0 (full regression) → 1.0 (no regression).
REGRESSION_WEIGHT: float = 0.75

#------------------------------------------------------------------------------
#MARGIN OF VICTORY
#------------------------------------------------------------------------------

#Scales the K-factor by log(run_differential) to reward blowout wins.
#0.0  — disabled
#0.4  — moderate
#1.0  — aggressive
MOV_WEIGHT: float = 0.25

#Maximum simulated run margin used when updating Elo mid-simulation.
#Caps the influence of randomly generated blowouts on in-sim Elo drift.
#Lowering this reduces noise; raising it increases sensitivity to sim variance.
SIM_MARGIN_CAP: int = 8

#------------------------------------------------------------------------------
#SIMULATION DEFAULTS
#------------------------------------------------------------------------------

#Default number of Monte Carlo iterations shown in the launcher UI.
DEFAULT_SIMS: int = 100_000

#Probability threshold (%) above which a team is classified as "predicted in"
#for backtest accuracy / classification metrics.
BACKTEST_THRESHOLD_PCT: float = 50.0

#Simulate the full postseason bracket inside each Monte Carlo iteration to
#produce World Series championship odds. Turning this off skips the bracket
#entirely (world_series_odds comes back empty) for a slightly faster run.
SIMULATE_POSTSEASON: bool = True

#------------------------------------------------------------------------------
#STARTING PITCHERS & BULLPEN FATIGUE  (postseason only)
#------------------------------------------------------------------------------

#When True, each postseason game is decided by team Elo AND that game's
#starting-pitcher matchup (Game 1 ace vs. Game 1 ace, etc.) instead of team
#Elo alone. Since there's no real roster data source wired in, rotations
#are synthesized from team Elo — see simulation/pitching.py.
STARTING_PITCHER_IMPACT: bool = True

#When True (and STARTING_PITCHER_IMPACT is also True), each team's bullpen
#accrues fatigue from taxing games across the whole simulated postseason
#run and sheds it during rest days between games/rounds — a tired bullpen
#lowers that team's win probability in its next game. See simulation/fatigue.py.
BULLPEN_FATIGUE_IMPACT: bool = True

#------------------------------------------------------------------------------
#REAL PITCHER RATINGS  (— replaces the synthetic staffs)
#------------------------------------------------------------------------------

#When True, rotations/bullpens are built from each team's real MLB 40-man
#roster and season pitching stats (data/player_stats.py, simulation/
#pitching.py) instead of the synthetic Elo-derived staff. Falls
#back automatically to the synthetic staff for any team whose roster/stats
#can't be fetched or parsed, or that doesn't have enough eligible arms, so
#a flaky API call degrades gracefully instead of crashing a run.
USE_REAL_PITCHER_STATS: bool = True

#Standard sabermetric FIP constant.
PITCHER_FIP_CONSTANT: float = 3.10

#League-average FIP == a real-stats rating of exactly ELO_BASELINE (1500).
PITCHER_LEAGUE_AVG_FIP: float = 4.00

#Elo points per 1.00 run of FIP above/below league average.
PITCHER_FIP_ELO_SCALE: float = 65.0

#Innings pitched at which a pitcher is exactly 50% trusted (n/(n+k)
#reliability — see simulation/player_rating.py's _apply_shrinkage). Below
#this, a pitcher's rating leans mostly toward league average; well above
#it, the rating is trusted close to face value. This is the main defense
#against a thin sample (a September call-up's 8 great innings) reading as
#a true-talent superstar or bust.
PITCHER_SHRINKAGE_INNINGS: float = 60.0

#Rolling-stats blend weights: how much of a pitcher's final
#rating comes from this season's stats, a rolling last-30-days window, and
#full-career totals. Weights don't need to sum to 1 — any missing window
#(0 IP, e.g. a rookie with no career stats) is dropped and the rest
#renormalized (see blend_rating_components).
PITCHER_SEASON_WEIGHT: float = 0.60
PITCHER_LAST_30_DAYS_WEIGHT: float = 0.30
PITCHER_CAREER_WEIGHT: float = 0.10

#How long a fetched roster/stats snapshot is considered fresh before
#re-fetching. Short — injury status and the last-30-days window both
#change day to day.
ROSTER_CACHE_EXPIRY_SECONDS: int = 3600

#------------------------------------------------------------------------------
#POSITION PLAYER (HITTING) RATINGS
#------------------------------------------------------------------------------

#When True, position-player offense ratings are built from each team's
#real MLB roster and hitting stats (data/hitting_stats.py, simulation/
#hitter_rating.py, simulation/offense_calculator.py) instead of a
#synthetic Elo-derived lineup. Falls back automatically to the synthetic
#lineup for any team whose roster/stats can't be fetched or parsed, or
#that doesn't have an eligible available hitter, same degrade-gracefully
#philosophy as USE_REAL_PITCHER_STATS above.
USE_REAL_HITTER_STATS: bool = True

#Whether a postseason game's win probability factors in each
#team's lineup (selected for the OPPOSING starter's throwing hand) on top
#of the starter matchup and bullpen. Off -> postseason games ignore
#lineups entirely (pre-6.7 behavior).
LINEUP_IMPACT: bool = True

#League-average OPS == a real-stats offense rating of exactly
#ELO_BASELINE (1500). Modern-era (post-2015) league OPS has hovered
#close to .720.
HITTER_LEAGUE_AVG_OPS: float = 0.720

#Elo points per 1.000 of OPS above/below league average -- the primary
#driver of a hitter's rating. Calibrated so a great hitter (~.900 OPS,
#+.180 over average) lands roughly +90 Elo points, a similar magnitude to
#the pitching side's ace-to-average gap.
HITTER_OPS_ELO_SCALE: float = 500.0

#Secondary modifiers layered ON TOP of the OPS-based rating above -- OPS
#already encodes on-base + power, so these are small adjustments for
#signal OPS blunts (raw power, plate discipline, and contact skill/
#dependability), not a second full rating. Each is expressed as "Elo
#points per unit of the underlying rate stat above/below league average,"
#same style as PITCHER_FIP_ELO_SCALE.

#Home runs, normalized to a 600-PA (roughly a full season) rate so it's
#comparable across different playing-time levels.
HITTER_LEAGUE_AVG_HR_PER_600PA: float = 20.0
HITTER_HR_RATE_ELO_SCALE: float = 0.6

#Walk rate (BB%) -- plate discipline bonus.
HITTER_LEAGUE_AVG_BB_RATE: float = 0.085
HITTER_BB_RATE_ELO_SCALE: float = 150.0

#Strikeout rate (K%) -- contact/dependability penalty (subtracted, so a
#below-average K% is a bonus and an above-average K% is a penalty).
HITTER_LEAGUE_AVG_K_RATE: float = 0.220
HITTER_K_RATE_ELO_SCALE: float = 80.0

#Plate appearances at which a hitter's rating is exactly 50% trusted
#(same IP/(IP+k) reliability idea as PITCHER_SHRINKAGE_INNINGS, just in
#PA instead of innings -- offensive rate stats stabilize slower than
#pitching FIP, so this is set higher than the pitching equivalent).
HITTER_SHRINKAGE_PA: float = 200.0

#Rolling-stats blend weights (season / last-30-days / career), same
#reasoning and default split as the pitching side.
HITTER_SEASON_WEIGHT: float = 0.60
HITTER_LAST_30_DAYS_WEIGHT: float = 0.30
HITTER_CAREER_WEIGHT: float = 0.10

#------------------------------------------------------------------------------
#SEASON RANGE (for UI validation)
#------------------------------------------------------------------------------

BACKTEST_SEASON_MAX: int = 2025  #Backtest requires a completed season

#------------------------------------------------------------------------------
#UI  —  tweak these to change the look of the app without touching widget code
#------------------------------------------------------------------------------

#Default window geometries
LAUNCHER_WINDOW_SIZE: str = '440x380'
RESULTS_WINDOW_SIZE: str = '1150x820'

#Standings: teams below this playoff probability get gray "eliminated" styling.
ELIM_ODDS_THRESHOLD: float = 2.0

#Teams tab: column the list is sorted by on first open.
#Options: 'odds' | 'name' | 'wl' | 'pct' | 'elo'
TEAMS_DEFAULT_SORT: str = 'odds'

#Wild Card spots per league (always 3 in modern MLB, here for reference).
WC_SPOTS: int = 3