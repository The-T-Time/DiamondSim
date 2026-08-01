# Changelog

All notable changes to DiamondSim are documented in this file.

## [1.0.2]

### Fixed
- **Critical:** the incremental data cache introduced in 1.0.1 was clamping its schedule fetch to today's date, so the not-yet-played portion of the season (the vast majority of a mid-season sync) was never actually retrieved. Simulations ran with an almost-empty remaining schedule, making several teams' playoff odds look artificially fixed at 100% regardless of seed. Fixed — the fetch window now always reaches the season's real end date.
- Settings' "Reset to Default" button raised a `NameError` on click (`reset_to_default` was called but never imported).
- The Simulate screen's Cancel button referenced an undefined color constant, which would have crashed the screen on open.
- The Load-a-run screen's list used unstyled system-default colors and an unthemed scrollbar regardless of the app's light/dark theme.
- Settings' "Refresh Data" button flashed dark navy on hover instead of a matching orange shade; the results window's "Save run" button used a hardcoded hex color instead of the shared palette.
- The Standings tab's division panels only laid out correctly once (right after the results window opened); resizing the window afterward left the same panel-per-row count locked in instead of reflowing.
- Charts on the Graphs tab could render far larger than their panel on a scaled ("HiDPI"/125%+) display. The chart was sized in inches using matplotlib's own fixed default DPI, which has nothing to do with the display scaling CustomTkinter applies — the two disagreed on how many real pixels an "inch" was, so the rendered chart didn't match the space actually available. Fixed by sizing off Tk's own real DPI instead.

### Added
- A **Cancel** button for in-progress simulation/backtest runs, replacing the inline Back button in the run screen's action row. The Back button now lives in a persistent top-left position on every screen instead.
- Cancelling a run stops it promptly: checked continuously during the Monte Carlo loop (including across worker processes) and before/after the roster & stat fetch phase.
- `assets/logos/README.md` now lists every team's MLB id alongside its name and division, for anyone dropping in logo PNGs.

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
