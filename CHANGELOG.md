# Changelog

All notable changes to DiamondSim are documented in this file.

## [1.0.1]

### Data caching
- Replaced the old one-file-per-team cache with a single unified, per-data-type cache under `cache/` (`games.json`, `schedule.json`, `standings.json`, `team_elo.json`, `batting_stats.json`, `pitching_stats.json`, `lineups.json`, `rosters.json`, `injuries.json`, `metadata.json`), instead of one JSON file per team per fetch.
- Game/schedule data now syncs incrementally: on every run, DiamondSim only requests dates it hasn't already cached, merges the results into the existing cache, and skips the API entirely if the cache is already current for the day.
- Completed prior seasons' closing Elo ratings are now cached indefinitely — previously recalculated from a full season replay on every single run.
- Backtests against an already-synced historical season no longer make any API calls; the played/unplayed snapshot for any date is re-derived locally from cached games.
- Automatic detection of a new MLB season starting a fresh cache, with a manual **Refresh Data** option (Settings → Data) to rebuild everything from scratch.
- Fixed a bug (introduced during 1.0.1 development) where concurrent roster/stat fetches for different teams could corrupt a shared cache file or fail with a file-in-use error; all cache writes are now synchronized and use unique temp files.

## [1.0.0]

Initial public release.

### Simulation
- Elo-based team rating system with Conservative / Normal / Aggressive / User model presets.
- Monte Carlo regular-season simulation (configurable iteration count) producing playoff odds for all 30 teams.
- Full postseason bracket simulation (Wild Card, Division Series, LCS, World Series) producing World Series odds and a projected bracket.
- Real MLB roster/stat-driven starting pitcher matchups, bullpen fatigue tracking, and platoon-split lineup construction for the postseason.
- Multi-core simulation — runs of 200+ simulations are split across every available CPU core.
- Backtest mode — run the sim from any past date and score it against the real postseason field (classification accuracy, Brier score).

### Interface
- Dashboard, Graphs, Teams, Standings, Statistics, Players, and Playoff Bracket tabs.
- Team logos throughout the bracket, Standings, Teams tab, and Favorites panel.
- Player leaderboards restricted to MLB-qualified players (1.0 IP / 3.1 PA per team game).
- Settings screen with Basic/Advanced simulation weights (sliders), feature toggles, and Display options, all with hover tooltips.
- Save/Load completed runs to disk.
- Light and dark themes.

### Under the hood
- Background-threaded simulation runs with live progress reporting; the UI never freezes.
- Disk caching for schedule, roster, and stat fetches.
