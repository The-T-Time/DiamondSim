# DiamondSim

A Monte Carlo simulation engine for MLB playoff probability, built with Python and Tkinter.

DiamondSim assigns every team a power rating using an Elo system trained on historical results, then simulates the remainder of the season tens of thousands of times to produce playoff odds, World Series odds, and a projected postseason bracket for all 30 teams. Real MLB roster and stat data feeds player-level detail into the postseason — starting pitcher matchups, bullpen fatigue, and lineup construction — on top of the team-level Elo math.

For a full explanation of how the simulation actually works (Elo, player ratings, Monte Carlo mechanics, the postseason bracket, and its assumptions/limitations), see **[SIMULATION.md](SIMULATION.md)**. For common questions, see **[FAQ.md](FAQ.md)**. For what's changed release to release, see **[CHANGELOG.md](CHANGELOG.md)**.

---

## Features

- **Simulate** — project the current season forward from today's live standings
- **Backtest** — run the sim at any past date and compare predictions against the actual postseason field
- **Dashboard** — the first screen after a run: World Series Favorites ranked by championship odds plus a run summary
- **World Series odds** — each Monte Carlo iteration plays out the full postseason bracket (Wild Card → Division Series → LCS → World Series), giving a championship probability for all 30 teams
- **Graphs** — sortable bar charts of playoff odds (overall and by division)
- **Teams** — click any team to see its full game log, Elo history, and upcoming schedule
- **Standings** — division tables with GB, Last 10, streak, and playoff odds; Wild Card race with cut-line; plus a sortable/searchable Table view
- **Statistics** — four sortable tables (Power Rankings, Run Differential, Splits, Momentum) with live search and league filtering
- **Players** — sortable pitcher/hitter leaderboards, real MLB stats, restricted to *qualified* players only (MLB's own 1.0 IP / 3.1 PA per team game standard) so the list isn't dominated by two-batter call-ups
- **Team logos** — shown throughout: the playoff bracket, Standings, the Teams tab's list and detail header, and the Dashboard's Favorites panel (see `assets/logos/README.md` to add your own)
- **Save / Load** — save any completed run to disk and reopen it later without re-fetching or re-simulating
- **Live progress** — a progress bar tracks fetch, Elo calculation, and the Monte Carlo run; the UI stays responsive because the simulation runs on a background thread
- **Multi-core simulation** — runs of 200+ simulations are split across every available CPU core instead of running one simulated season at a time (see [SIMULATION.md](SIMULATION.md#monte-carlo-simulations))

---

## Screenshots

*Coming soon.*

---

## Installation

1. **Python 3.11+** (see [Requirements](#requirements) below).
2. **Tkinter.** Bundled with Python on Windows and macOS. On Linux, install it separately:
   ```bash
   sudo apt install python3-tk        # Debian/Ubuntu
   sudo dnf install python3-tkinter   # Fedora/RHEL
   ```
3. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Fonts (optional, but recommended).** DiamondSim requests **Oswald** (headers) and **Inter** (body text) by name — both are free Google Fonts. Install them system-wide for the intended look; if either is missing, Tk silently falls back to a default font instead of erroring.

---

## Quick Start

```bash
# 1. Clone the repo
git clone <repo-url>
cd DiamondSim

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python main.py
```

No API key or account needed — DiamondSim pulls live schedule and score data from the public MLB Stats API (`https://statsapi.mlb.com/api/v1/`).

---

## Requirements

| Package        | Purpose                               |
|----------------|----------------------------------------|
| `requests`     | MLB Stats API HTTP calls                |
| `matplotlib`   | Chart figures (Graphs tab)              |
| `seaborn`      | Chart styling                           |
| `customtkinter`| Modern widget theme on top of Tkinter   |
| `tkinter-tooltip` | Hover tooltips on the Settings screen |
| `tkinter`      | GUI toolkit — bundled with Python on Windows/macOS, separate package on Linux (see [Installation](#installation)) |

See `requirements.txt` for exact version pins.

---

## Credits

**Developer:** Tyler Oberquell

**Built with:**
- Python
- CustomTkinter
- MLB Stats API

Live schedule, score, roster, and stat data is pulled from the public **MLB Stats API** (`https://statsapi.mlb.com/api/v1/`) — no API key required. DiamondSim is an independent project and is not affiliated with or endorsed by MLB.
