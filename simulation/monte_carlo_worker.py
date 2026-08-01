# ==============================================================================
# MONTE CARLO WORKER
# simulation/monte_carlo_worker.py
#
# The per-iteration body of the Monte Carlo loop, pulled into a standalone
# top-level function (run_chunk) so it can run in its own worker process
# for large runs — see simulator.py's run_simulation_core for how chunks
# get split up and merged back together.
# ==============================================================================

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Optional

from data.teams import ALL_TEAMS
from models.game import Game
from models.playoff_bracket import PlayoffBracketResult
from models.simulation_config import SimulationConfig
from models.team import TeamName
from simulation.elo import EloTable
from simulation.game_simulator import simulate_regular_season_game
from simulation.playoff_simulator import simulate_postseason
from simulation.standings import H2HTable, RecordTable, division_of, league_of, resolve_league_playoff_teams
import random


@dataclass
class ChunkResult:
    #one of these per worker/chunk; run_simulation_core sums a list of these back into the same totals a single sequential loop would have produced
    sims_run:               int = 0
    total_wins:             dict[TeamName, int] = field(default_factory=lambda: defaultdict(int))
    total_losses:           dict[TeamName, int] = field(default_factory=lambda: defaultdict(int))
    total_sim_runs_scored:  dict[TeamName, int] = field(default_factory=lambda: defaultdict(int))
    total_sim_runs_allowed: dict[TeamName, int] = field(default_factory=lambda: defaultdict(int))
    game_home_win_counts:   dict[int, int] = field(default_factory=lambda: defaultdict(int))
    playoff_counts:         dict[TeamName, int] = field(default_factory=lambda: defaultdict(int))
    champ_counts:           dict[TeamName, int] = field(default_factory=lambda: defaultdict(int))
    bracket_counts:         dict[tuple, int] = field(default_factory=lambda: defaultdict(int))
    bracket_examples:       dict[tuple, PlayoffBracketResult] = field(default_factory=dict)


def run_chunk(
    num_chunk_sims: int,
    seed: int,
    base_rec: RecordTable,
    base_h2h: H2HTable,
    derived_base_elo: EloTable,
    unplayed_games: list[Game],
    cfg: SimulationConfig,
    rotations=None,
    bullpens=None,
    lineups=None,
    progress_callback: Optional[Callable[[int, int], None]] = None,
    cancel_event=None,
) -> ChunkResult:
    """
    `cancel_event`, if given, is checked at the same ~1%-of-the-chunk
    cadence as progress reporting (cheap, and frequent enough to feel
    responsive) — set it and this returns early with a partial
    ChunkResult. Only meaningful for the single-process path (see
    simulator.py's _run_all_chunks): a threading.Event created in the
    main process can't be observed inside a separate worker process, so
    the multi-process path never passes one here and instead polls for
    cancellation between chunk completions in the caller.
    """
    #a local Random instance, not the `random` module, so this chunk's draws never interfere with another chunk's (or the caller's) randomness — same reasoning run_simulation_core's own rng used to have
    rng = random.Random(seed)
    result = ChunkResult()
    report_every = max(1, num_chunk_sims // 100)

    for i in range(num_chunk_sims):
        if cancel_event is not None and i % report_every == 0 and cancel_event.is_set():
            break

        records: RecordTable = {
            t: {**v, 'league_results': list(v['league_results'])}
            for t, v in base_rec.items()
        }
        h2h: H2HTable = {t: defaultdict(int, v) for t, v in base_h2h.items()}
        elo: EloTable = derived_base_elo.copy()

        for game in unplayed_games:
            home, away = game.home, game.away
            outcome = simulate_regular_season_game(home, away, elo, cfg, rng)

            records[outcome.winner]['W'] += 1
            records[outcome.loser]['L'] += 1
            h2h[outcome.winner][outcome.loser] += 1
            if division_of(home) == division_of(away):
                records[outcome.winner]['div_W'] += 1
                records[outcome.loser]['div_L'] += 1
            if league_of(home) == league_of(away):
                records[outcome.winner]['league_W'] += 1
                records[outcome.loser]['league_L'] += 1
                records[outcome.winner]['league_results'].append(1)
                records[outcome.loser]['league_results'].append(0)

            result.total_sim_runs_scored[outcome.winner] += outcome.winner_runs
            result.total_sim_runs_scored[outcome.loser] += outcome.loser_runs
            result.total_sim_runs_allowed[outcome.winner] += outcome.loser_runs
            result.total_sim_runs_allowed[outcome.loser] += outcome.winner_runs

            if outcome.winner == home:
                result.game_home_win_counts[game.game_pk] += 1

        for t in ALL_TEAMS:
            result.total_wins[t] += records[t]['W']
            result.total_losses[t] += records[t]['L']

        for league in ('AL', 'NL'):
            div_winners, wc_teams = resolve_league_playoff_teams(records, h2h, league)
            for t in div_winners:
                result.playoff_counts[t] += 1
            for t in wc_teams:
                result.playoff_counts[t] += 1

        if cfg.simulate_postseason:
            bracket = simulate_postseason(
                records, h2h, elo, cfg, rng, rotations=rotations, bullpens=bullpens, lineups=lineups,
            )
            result.champ_counts[bracket.champion] += 1
            key = bracket.as_key()
            result.bracket_counts[key] += 1
            if key not in result.bracket_examples:
                result.bracket_examples[key] = bracket

        result.sims_run += 1
        if progress_callback is not None and (i + 1) % report_every == 0:
            progress_callback(i + 1, num_chunk_sims)

    return result


def merge_chunk_results(chunks: list[ChunkResult]) -> ChunkResult:
    #combines every worker's partial totals into the same shape a single sequential run_chunk(num_sims, ...) call would have produced
    merged = ChunkResult()
    for c in chunks:
        merged.sims_run += c.sims_run
        for t in ALL_TEAMS:
            merged.total_wins[t] += c.total_wins.get(t, 0)
            merged.total_losses[t] += c.total_losses.get(t, 0)
            merged.total_sim_runs_scored[t] += c.total_sim_runs_scored.get(t, 0)
            merged.total_sim_runs_allowed[t] += c.total_sim_runs_allowed.get(t, 0)
            merged.playoff_counts[t] += c.playoff_counts.get(t, 0)
            merged.champ_counts[t] += c.champ_counts.get(t, 0)
        for game_pk, count in c.game_home_win_counts.items():
            merged.game_home_win_counts[game_pk] += count
        for key, count in c.bracket_counts.items():
            merged.bracket_counts[key] += count
            #every bracket sharing a key is identical by definition (PlayoffBracketResult.as_key) — so it doesn't matter which chunk's example wins, only that one gets kept
            merged.bracket_examples.setdefault(key, c.bracket_examples[key])
    return merged
