# Changelog

All notable changes to DiamondSim are documented in this file.

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
