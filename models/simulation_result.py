# ==============================================================================
# SIMULATION RESULT
# models/simulation_result.py
#
# Single source of truth for everything a simulation run produces.
# Every GUI tab reads from this object — nothing recalculates anything.
#
# Anything derivable from played_games/cfg is a property, not a stored
# field, so there's exactly one place it can be wrong.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from models.elo_snapshot import EloSnapshot
from models.game import Game
from models.playoff_bracket import PlayoffBracketResult
from models.simulation_config import SimulationConfig
from models.team import TeamName


@dataclass
class SimulationResult:
    #── mode / metadata ──────────────────────────────────────────────────────
    mode: str                        #'simulate' or 'backtest'
    season: int
    snapshot_date: Optional[str] = None   #backtest only
    cfg: SimulationConfig = field(default_factory=SimulationConfig)

    #── core outputs ─────────────────────────────────────────────────────────
    #playoff_odds[team] = float 0-100
    playoff_odds: dict[TeamName, float] = field(default_factory=dict)

    #world_series_odds[team] = float 0-100, the share of simulated postseasons
    #a team won the World Series. Empty when cfg.simulate_postseason is False.
    #When populated it covers all 30 teams and sums to ~100% (one champ / sim).
    world_series_odds: dict[TeamName, float] = field(default_factory=dict)

    #── Elo ──────────────────────────────────────────────────────────────────
    #live_elo[team] = Elo at the snapshot date (after all played games)
    live_elo: dict[TeamName, float] = field(default_factory=dict)

    #elo_log[game_pk] = Elo commentary for that played game (see EloSnapshot).
    #Kept out of Game itself — this is simulation output, not game history.
    elo_log: dict[int, EloSnapshot] = field(default_factory=dict)

    #── standings ────────────────────────────────────────────────────────────
    #live_standings[team] = {'W': int, 'L': int}
    live_standings: dict[TeamName, dict[str, int]] = field(default_factory=dict)

    #── game logs ────────────────────────────────────────────────────────────
    played_games: list[Game] = field(default_factory=list)
    unplayed_games: list[Game] = field(default_factory=list)

    #── backtest extras ───────────────────────────────────────────────────────
    #true_playoff_teams: list of team names that actually made the playoffs
    true_playoff_teams: list[TeamName] = field(default_factory=list)

    #── projected (end-of-season) stats ───────────────────────────────────────
    #projected_team_stats[team] = {'wins', 'losses', 'runs_scored',
    #'runs_allowed', 'era'} — each averaged across every simulation, not
    #a single sample season. Empty until a full simulation (not backtest)
    #has run with cfg.simulate_postseason True.
    projected_team_stats: dict[TeamName, dict[str, float]] = field(default_factory=dict)

    #unplayed_game_home_win_pct[game_pk] = what share of simulations the
    #HOME team won that specific unplayed game — e.g. 62.3 means the home
    #team won it in 62.3% of sims. Use win_probability() below rather than
    #indexing this directly; it handles picking the right side for
    #whichever team you're asking about. Empty for played games (there's
    #nothing to project) and for backtests.
    unplayed_game_home_win_pct: dict[int, float] = field(default_factory=dict)

    #The single playoff bracket that occurred most often across every
    #simulation (seeds, every round's winner, and the champion) — not the
    #bracket from any one sample season. None if postseason simulation was
    #off. See models/playoff_bracket.py.
    projected_bracket: Optional[PlayoffBracketResult] = None

    #What share of simulations produced projected_bracket exactly — e.g.
    #24.6 means this exact bracket (every seed and every round) came up in
    #24.6% of runs. Useful context: even "the most common" bracket is often
    #a small slice of a large simulation, since there are many possible
    #brackets. 0.0 if projected_bracket is None.
    projected_bracket_pct: float = 0.0

    #How many distinct brackets tied for the top occurrence count that
    #projected_bracket was picked from (see simulator.py's tiebreaker
    #comment). 1 means it was a clear, unambiguous winner. A number equal
    #to (or close to) the number of simulations run means essentially
    #every bracket was unique — normal early in a season, when the space
    #of possible outcomes vastly exceeds any practical simulation count.
    projected_bracket_tied_count: int = 0

    #── derived helpers ───────────────────────────────────────────────────────
    @property
    def num_sims(self) -> int:
        """How many Monte Carlo iterations produced playoff_odds. Derived from
        cfg so it can't drift out of sync with the config that actually ran."""
        return self.cfg.simulations

    def games_for_team(self, team: TeamName) -> list[Game]:
        """All played games involving `team`, in date order."""
        return [g for g in self.played_games if g.home == team or g.away == team]

    def win_loss(self, team: TeamName) -> tuple[int, int]:
        """Current (W, L) tuple for a team."""
        s = self.live_standings.get(team, {'W': 0, 'L': 0})
        return s['W'], s['L']

    def projected_win_loss(self, team: TeamName) -> tuple[float, float]:
        """Projected end-of-season (W, L), averaged across every simulation.
        Falls back to the current (W, L) if no projection is available."""
        stats = self.projected_team_stats.get(team)
        if stats is None:
            w, l = self.win_loss(team)
            return float(w), float(l)
        return stats['wins'], stats['losses']

    def projected_pct(self, team: TeamName) -> float:
        w, l = self.projected_win_loss(team)
        return w / (w + l) if (w + l) else 0.0

    def pct(self, team: TeamName) -> float:
        w, l = self.win_loss(team)
        return w / (w + l) if (w + l) else 0.0

    def win_probability(self, game: Game, team: TeamName) -> Optional[float]:
        """What share of simulations `team` won this specific game — e.g.
        62.3 means team won it in 62.3% of sims. `team` must be game.home
        or game.away. Returns None if this game was already played (no
        projection needed) or no projection is available (e.g. a backtest)."""
        home_pct = self.unplayed_game_home_win_pct.get(game.game_pk)
        if home_pct is None:
            return None
        return home_pct if team == game.home else 100.0 - home_pct

    def elo_snapshot(self, game: Game) -> Optional[EloSnapshot]:
        """Elo commentary for a played game, or None if unavailable (unplayed game)."""
        if game.game_pk is None:
            return None
        return self.elo_log.get(game.game_pk)
