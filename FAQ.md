# Frequently Asked Questions

**What is DiamondSim?**
A desktop app that simulates the remainder of the MLB season and postseason thousands of times to produce playoff odds, World Series odds, a projected bracket, and projected stats for all 30 teams. See [SIMULATION.md](SIMULATION.md) for how the math actually works.

**Is this affiliated with MLB?**
No. DiamondSim is an independent project that pulls public schedule/roster/stat data from the MLB Stats API. It isn't endorsed by or affiliated with Major League Baseball.

**Do I need an API key or account?**
No — the MLB Stats API used for schedule, roster, and stat data is public and requires no key or login.

**How many simulations should I run?**
100,000 is the default and gives stable odds for most purposes. A few hundred to a few thousand is enough to get a rough read quickly; if you're comparing small differences between teams (e.g. two Wild Card contenders within a percentage point of each other), more simulations reduce the noise. See [Performance](SIMULATION.md#monte-carlo-simulations) for how larger runs use multiple CPU cores.

**Why don't the playoff odds add up to exactly 100%?**
They're not supposed to — 12 teams make the playoffs each season, so playoff odds sum to 1200% across all 30 teams, not 100%. World Series odds *do* sum to ~100%, since exactly one team wins it per simulated season.

**What's the difference between the Conservative, Normal, Aggressive, and User models?**
They're different Elo weight presets — how fast ratings react to results, how much blowouts matter, and how much of last year's rating carries forward. Conservative is the slowest to react, Aggressive the fastest, Normal is the default in between, and User reflects whatever you've customized on the Settings screen. Full breakdown in [Model Presets](SIMULATION.md#model-presets).

**Why is a player missing from the Players tab?**
The Players tab only shows *qualified* players — MLB's own standard of 1.0 inning pitched per team game for pitchers, 3.1 plate appearances per team game for hitters. This keeps the leaderboard from being dominated by two-batter September call-ups and mop-up relievers. A player who hasn't reached that bar yet won't appear until they do.

**Why did a team's odds change a lot between two runs with the same settings?**
If the seed was left on "Random," each run draws different random numbers, so results will vary run to run (more so with fewer simulations). Set an explicit seed if you want a specific run to be exactly reproducible — though note that changing the number of simulations, the model, or the number of CPU cores available can also change results even with the same seed (see [Monte Carlo Simulations](SIMULATION.md#monte-carlo-simulations)).

**Does the simulation account for who's actually pitching a given regular-season game?**
No — the regular season is pure team-Elo. Starting pitcher matchups, bullpen fatigue, and lineup construction only come into play once the postseason bracket simulation starts. See [Assumptions and Limitations](SIMULATION.md#assumptions-and-limitations).

**Does the simulation account for defense?**
Not currently — there's no fielding/defensive data source wired in, so team and player ratings are offense/pitching only.

**What happens if real player stats aren't available for a team?**
DiamondSim falls back to a synthetic, Elo-derived rotation/bullpen/lineup for that team automatically, so a missing or incomplete API response degrades a run gracefully instead of crashing it.

**Can I add my own team logos?**
Yes — drop a PNG named `{team_id}.png` into `assets/logos/` (team IDs match `TEAM_REGISTRY` in `data/teams.py`). See `assets/logos/README.md` for details. A missing logo just gets skipped, not treated as an error.

**Can I change the simulation weights myself?**
Yes, from the Settings screen (⚙ Settings) — Basic weights (Elo K-factor, home-field advantage, prior-year regression), Advanced weights (margin-of-victory weight, simulated margin cap), and feature toggles (real pitcher/hitter stats, starting pitcher/bullpen fatigue/lineup impact). Saved changes become the "User" model.

**What's Backtest mode for?**
It runs the simulation from a past date instead of today, then scores its predictions against what actually happened in that season's real postseason — useful for sanity-checking the model against history rather than trusting projections on faith.

**Does DiamondSim work on Windows, macOS, and Linux?**
Yes. Tkinter ships with Python on Windows and macOS; on Linux it's usually a separate package (see [Installation](README.md#installation)).
