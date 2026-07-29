# How the Simulation Works

This document explains the math and mechanics behind DiamondSim's projections — what drives the numbers, how the postseason is simulated, and where the model's assumptions and limits are.

## Contents

- [Team Elo](#team-elo)
- [Player Ratings](#player-ratings)
- [Starting Pitcher Impact](#starting-pitcher-impact)
- [Bullpen Fatigue](#bullpen-fatigue)
- [Lineup Impact](#lineup-impact)
- [Monte Carlo Simulations](#monte-carlo-simulations)
- [Future Stats](#future-stats)
- [Playoff Simulation](#playoff-simulation)
- [Bracket Selection](#bracket-selection)
- [Probability Calculations](#probability-calculations)
- [Assumptions and Limitations](#assumptions-and-limitations)
- [Configuration Reference](#configuration-reference)

---

## Team Elo

Every team starts the season with an Elo rating derived from its previous year's closing rating, regressed toward the 1500 league-average baseline (`REGRESSION_WEIGHT`, 0.75 by default — 1.0 keeps the full prior rating, 0.0 resets to 1500).

After every played game, ratings update using:

```
expected_home = 1 / (1 + 10^((away_elo − (home_elo + home_field_advantage)) / 400))
delta         = K × MOV_multiplier × (actual − expected)
```

where `MOV_multiplier = 1 + MOV_WEIGHT × log(run_diff)`. `K` (how fast ratings react to new results), `home_field_advantage` (Elo points added to the home team), and `MOV_WEIGHT` (how much blowouts matter on top of `K`) are all tunable — see [Model Presets](#model-presets) below.

### Model Presets

The Model dropdown (Simulate/Backtest forms) and the Settings screen let you pick which weights drive the Elo math:

| | Elo K-factor | Home-field advantage | Margin-of-victory weight | Prior-year regression |
|---|---|---|---|---|
| **Conservative** | 20 | 15 | 0.05 | 0.85 |
| **Normal** (default) | 30 | 15 | 0.25 | 0.75 |
| **Aggressive** | 40 | 15 | 0.45 | 0.60 |
| **User** | whatever's saved in Settings | | | |

Conservative reacts the slowest to new results (heavy regression toward the baseline, low K, low MOV weight); Aggressive reacts the fastest. Both leave home-field advantage and the simulated margin cap at Normal's values — they only tune reactivity. **User** reflects whatever weights you've saved on the Settings screen, and the Model dropdown defaults to it automatically once any of those weights differ from Normal's.

---

## Player Ratings

Beyond team Elo, DiamondSim rates individual pitchers and hitters from real MLB stats, on the same 1500-average Elo scale as team ratings — a player's `.impact` is a positive or negative *adjustment* to that scale, not a standalone number.

- **Pitchers** — rated from **FIP** (Fielding Independent Pitching: strikeouts, walks, hit-by-pitches, home runs only — not skewed by the defense behind them or batted-ball luck).
- **Hitters** — rated from **OPS** as the primary signal, with small secondary modifiers for HR rate, BB%, and K%.
- **Small-sample shrinkage.** Every rating is regressed toward league average using an `IP/(IP+k)` (pitchers) or `PA/(PA+k)` (hitters) reliability formula, not a hard cutoff — a 20-inning hot streak lands close to average instead of reading as a true-talent superstar, while a full season's playing time is trusted close to face value.
- **Rolling blend.** Ratings blend three windows — current season (60%), a rolling last-30-days window (30%), and career totals (10%) by default — so current form matters most, hot/cold streaks still move the needle, and career history anchors against overreacting to either. A window with no innings/plate appearances (e.g. a rookie's career line) is dropped and the remaining weights renormalized.
- **Injuries.** Roster status comes from the MLB Stats API. Only active-roster players are eligible; an injured player is skipped until his status clears, with the next-best healthy option stepping in. Because every player carries his own real rating, losing a true ace or middle-of-the-order bat costs far more win probability than losing a replacement-level one — proportional to that specific player's rating gap, same as in reality.
- **Fallback.** If a team's roster/stats can't be fetched, that team falls back automatically to a synthetic Elo-derived staff/lineup — a failed API call degrades gracefully instead of crashing a run.

Toggle real pitcher/hitter stats independently with `USE_REAL_PITCHER_STATS` / `USE_REAL_HITTER_STATS` in `config.py`; the rating-conversion scales, shrinkage constants, and blend weights are all tunable there too.

Player ratings only ever apply during the **postseason bracket simulation** — the regular season stays pure team-Elo. When they do apply, none of it touches a team's real Elo rating — that still only moves via an actual simulated win/loss. For one postseason game, the actual players involved combine into a temporary effective Elo for that game only:

```
effective_elo = team_elo + starter_adj + lineup_adj + bullpen_adj + home_field_advantage
```

Tomorrow's game starts fresh from the team's real, un-adjusted Elo rating again.

---

## Starting Pitcher Impact

Each postseason game's win probability factors in that day's starting-pitcher matchup on top of team Elo. Rotations cycle from each team's ace at the start of every series ("Team A's Game 1 starter vs. Team B's Game 1 starter"), cycling back to the top on short rest if a series runs long. A starter's rating gap over his counterpart shifts win probability the same way a team Elo gap does.

Toggle with `STARTING_PITCHER_IMPACT` in `config.py`.

---

## Bullpen Fatigue

Each team's bullpen (closer down to a long man, weighted by leverage) accumulates fatigue across a simulated postseason run: a close or extra-innings game burns high-leverage relievers, while a comfortable game barely dents the pen. Fatigue sheds during rest days — a little between games within a series, more between rounds — and a tired bullpen lowers that team's win probability in its next game. A bullpen ground down through the LDS/LCS carries that wear into the World Series, since fatigue is tracked for one simulated postseason run at a time.

Independent of fatigue, each bullpen's overall *quality* (a leverage-weighted average rating across the pen) also factors into win probability as a baseline signal — a great, fully-rested pen and a replacement-level, fully-rested pen are not treated as equivalent.

Toggle with `BULLPEN_FATIGUE_IMPACT` in `config.py`.

---

## Lineup Impact

Teams get two lineups, not one — each rated off that season's actual platoon splits (vs. left-handed and vs. right-handed pitching). At game time, the lineup facing the *opposing* starter's actual throwing hand is used, rather than assuming a lineup hits equally well against everyone. Falls back to one overall lineup if split data isn't available, then to a synthetic lineup if no real data is available at all.

Toggle with `LINEUP_IMPACT` in `config.py`. Requires starting pitcher data (the opposing starter's throwing hand is what selects the lineup).

---

## Monte Carlo Simulations

The remaining schedule is simulated `N` times (100,000 by default). In each iteration:

1. Each unplayed game is decided probabilistically using the home team's Elo win probability.
2. Elo ratings update with a capped simulated run margin (`SIM_MARGIN_CAP`), so an extreme simulated blowout can't swing ratings more than a real one would.
3. At season end, division winners and Wild Card teams are resolved using the full MLB tiebreaker cascade (see [Assumptions and Limitations](#assumptions-and-limitations)).
4. If postseason simulation is enabled, the 12-team bracket is played out on the final simulated ratings.

**Performance.** Every simulated season is completely independent of every other one, so runs of 200+ simulations are split evenly across every available CPU core and run in separate worker processes rather than one simulated season at a time on a single core. Smaller runs stay single-process, since starting extra worker processes costs more than it saves for a couple hundred iterations. Each worker draws from its own random-number stream (seeded off the run's master seed), so re-running the exact same seed only reproduces the exact same result when the number of CPU cores available is also the same — a different core count splits the work into different-sized chunks, and the results, while statistically equivalent, won't be numerically identical down to the last decimal.

---

## Future Stats

Alongside odds, DiamondSim projects each team's end-of-season stat line — wins, losses, runs scored, runs allowed, and ERA — averaged across every simulation rather than taken from a single sample season. Real, already-played games contribute their actual runs to every simulated season (they already happened); only the unplayed games' simulated runs vary sim to sim.

---

## Playoff Simulation

If enabled (`SIMULATE_POSTSEASON`, on by default), each simulated season's final standings feed a full 12-team postseason bracket: Wild Card (best-of-3), Division Series (best-of-5), and LCS/World Series (best-of-7). Home-field formats follow MLB's real structure — the Wild Card host plays all three at home, the Division Series is 2-2-1, and the LCS/World Series are 2-3-2. The home-field Elo bump applies to the actual home team of each individual game, so win probability is recomputed game by game rather than fixed for a whole series. The series host is the higher seed (Wild Card / Division Series / LCS) or the better regular-season record (World Series).

---

## Bracket Selection

The bracket shown on the Playoff Bracket tab is the single most common exact bracket across every simulation — not a guaranteed outcome, just the most frequent one. With so many possible bracket combinations, even "the most common" is often a small slice of all simulations (the bracket screen shows what percentage of runs it actually represents). When multiple brackets are tied for the top spot, the one shown is picked by whichever tied champion had the best overall championship odds — not an arbitrary tiebreak.

---

## Probability Calculations

```
playoff_odds[team]      = (simulations where team made the playoffs) / N
world_series_odds[team] = (simulations where team won the World Series) / N
```

`playoff_odds` sums to 1200% across all 30 teams (12 playoff spots per simulated season). `world_series_odds` sums to ~100% across all teams.

---

## Assumptions and Limitations

- **The regular season is pure team-Elo.** Starting pitcher, bullpen fatigue, and lineup impact only apply once the postseason bracket simulation begins — an unplayed regular-season game's outcome depends only on the two teams' Elo ratings, not who's pitching that day.
- **No defense or baserunning rating.** Player value is tracked for pitching (starter/reliever) and hitting; `PlayerImpact.defense_value` exists in the data model but is never populated, since no fielding data source is wired in.
- **Real stats depend on data availability.** If the MLB Stats API doesn't have enough data for a team/player (too early in the season, a very limited sample, an API hiccup), the simulation falls back to synthetic Elo-derived ratings for that team rather than failing the whole run.
- **Tiebreakers use a deterministic approximation.** Ties are resolved with the official post-2022 (no Game 163) cascade — head-to-head record, intradivision record, intraleague record, then last-half-of-intraleague-games with an expanding walkback, then overall winning percentage — applied as a total order so any set of tied clubs resolves to a unique, reproducible ranking. MLB defines "last half" as games after the All-Star break; since a simulated remainder has no fixed break date, DiamondSim uses the chronological midpoint of each club's intraleague games as the standard approximation.
- **A different CPU core count can change results for the same seed.** See [Monte Carlo Simulations](#monte-carlo-simulations) above — this is a reproducibility caveat, not a correctness issue; results remain statistically equivalent.
- **Backtest accuracy is bounded by the model, not just the code.** Backtest mode scores predictions against the real postseason field (classification accuracy, Brier score — lower is better, random baseline is 0.24), but a well-calibrated model will still be "wrong" some fraction of the time by design — that's what a probability means.

---

## Configuration Reference

All parameters below live in `config.py`. `ELO_K`, `HOME_FIELD_ADVANTAGE`, `MOV_WEIGHT`, and `REGRESSION_WEIGHT` are the **Normal** model's values (see [Model Presets](#model-presets) for Conservative/Aggressive/User).

| Parameter | Default | Description |
|---|---|---|
| `ELO_K` | 30 | K-factor — how fast ratings shift |
| `HOME_FIELD_ADVANTAGE` | 15 | Elo points added to home team win probability |
| `ELO_BASELINE` | 1500 | Neutral starting rating |
| `REGRESSION_WEIGHT` | 0.75 | How much prior-year rating carries forward |
| `MOV_WEIGHT` | 0.25 | Margin-of-victory scaling (0 = win/loss only) |
| `DEFAULT_SIMS` | 100,000 | Monte Carlo iterations shown in launcher |
| `CACHE_ENABLED` | False | Toggle JSON schedule caching |
| `CACHE_EXPIRY_SECONDS` | 7200 | Cache TTL (2 hours) |
| `ELIM_ODDS_THRESHOLD` | 2.0 | Below this % → shown as eliminated in standings |
| `TEAMS_DEFAULT_SORT` | `'odds'` | Default sort column in the Teams tab |
| `SIMULATE_POSTSEASON` | True | Play out the postseason bracket for World Series odds |
| `STARTING_PITCHER_IMPACT` | True | Factor each postseason game's starter matchup into win probability |
| `BULLPEN_FATIGUE_IMPACT` | True | Track bullpen fatigue across a postseason run and penalize tired bullpens |
| `USE_REAL_PITCHER_STATS` | True | Build rotations/bullpens from real MLB roster + stats data (falls back to synthetic if unavailable) |
| `PITCHER_FIP_ELO_SCALE` | 65.0 | Elo points per 1.00 run of FIP above/below league average |
| `PITCHER_SHRINKAGE_INNINGS` | 60.0 | Innings at which a pitcher's rating is exactly 50% trusted (`IP/(IP+k)` reliability) |
| `PITCHER_SEASON_WEIGHT` / `PITCHER_LAST_30_DAYS_WEIGHT` / `PITCHER_CAREER_WEIGHT` | 0.60 / 0.30 / 0.10 | Rolling-stats blend weights |
| `ROSTER_CACHE_EXPIRY_SECONDS` | 3600 | Roster/injury-status/last-30-days cache TTL (1 hour) |
| `USE_REAL_HITTER_STATS` | True | Build TeamOffense from real MLB hitting data (falls back to synthetic if unavailable) |
| `HITTER_OPS_ELO_SCALE` | 500.0 | Elo points per 1.000 of OPS above/below league average |
| `HITTER_HR_RATE_ELO_SCALE` / `HITTER_BB_RATE_ELO_SCALE` / `HITTER_K_RATE_ELO_SCALE` | 0.6 / 150.0 / 80.0 | Secondary HR/BB%/K% modifier scales |
| `HITTER_SHRINKAGE_PA` | 200.0 | Plate appearances at which a hitter's rating is exactly 50% trusted |
| `HITTER_SEASON_WEIGHT` / `HITTER_LAST_30_DAYS_WEIGHT` / `HITTER_CAREER_WEIGHT` | 0.60 / 0.30 / 0.10 | Rolling-stats blend weights |
| `LINEUP_IMPACT` | True | Factor each postseason game's lineup (vs opposing starter's hand) + bullpen baseline rating into win probability |
