# ==============================================================================
# SIMULATION
# simulation/simulator.py
#
# Orchestration only: fetch/replay real games, dispatch the Monte Carlo
# run (sequential or across worker processes), aggregate into a
# SimulationResult. The actual mechanics live in dedicated modules —
# standings.py (records/playoff field), game_simulator.py (one game),
# series_simulator.py (one series), playoff_simulator.py (the bracket).
# ==============================================================================

from __future__ import annotations

import dataclasses
import multiprocessing
import os
import random
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from typing import Any, Callable

from data.teams import ALL_TEAMS
from data.cache_store import (
    save_current_elo,
    save_standings,
    split_games_for_backtest,
    sync_season_games,
)
from models.elo_snapshot import EloSnapshot
from models.game import Game
from models.playoff_bracket import PlayoffBracketResult
from models.simulation_config import SimulationConfig
from models.simulation_result import SimulationResult
from models.team import TeamName
from simulation.elo import EloTable, apply_elo_update, compute_regressed_starting_elo
from simulation.monte_carlo_worker import ChunkResult, merge_chunk_results, run_chunk
from simulation.offense_calculator import build_all_team_lineups
from simulation.pitching import build_all_team_staffs
from simulation.standings import (
    H2HTable,
    RecordTable,
    Standings,
    build_base_records,
    division_of,
    league_of,
    resolve_league_playoff_teams,
)
from utils.logger import get_logger

logger = get_logger(__name__)

#below this many total simulations, splitting into worker processes costs more (process
#startup, pickling the per-chunk inputs) than it saves — run in-process instead
_PARALLEL_MIN_SIMS = 200


#==============================================================================
#REPLAYING REAL GAMES
#==============================================================================

def _replay_with_elo_log(
    played_games: list[Game], starting_elo: EloTable, cfg: SimulationConfig
) -> tuple[EloTable, Standings, dict[int, EloSnapshot]]:
    """
    Walk played games chronologically, tracking Elo before/after each game.
    Returns (current_elo, live_standings, elo_log) where elo_log maps
    game_pk -> EloSnapshot for the Teams tab's Elo history display.
    """
    current_elo = starting_elo.copy()
    live_standings: Standings = {t: {'W': 0, 'L': 0} for t in ALL_TEAMS}
    elo_log: dict[int, EloSnapshot] = {}

    for game in played_games:
        home, away = game.home, game.away
        w, l = game.winner, game.loser
        live_standings[w]['W'] += 1
        live_standings[l]['L'] += 1

        elo_before_home = current_elo[home]
        elo_before_away = current_elo[away]
        apply_elo_update(current_elo, home, away, w == home, game.run_diff or 1, cfg)
        elo_delta = current_elo[home] - elo_before_home

        if game.game_pk is not None:
            elo_log[game.game_pk] = EloSnapshot(
                elo_before_home=round(elo_before_home, 2),
                elo_before_away=round(elo_before_away, 2),
                elo_delta=round(elo_delta, 2),   #from home team's perspective
            )

    return current_elo, live_standings, elo_log


#==============================================================================
#DATA FETCH
#==============================================================================

def fetch_simulation_data(season: int, cfg: SimulationConfig = SimulationConfig()) -> dict[str, Any]:
    """
    Loads the data payload for forward simulation. Game/schedule data
    comes from the incremental cache (data/cache_store.py) — only dates
    since the last sync are actually fetched from the API; a second call
    the same day is served entirely from disk. Elo/standings are cheap to
    recompute locally from that (mostly-cached) game list, so they're
    always rebuilt fresh in-process rather than trusted from an older
    snapshot, then persisted into the cache's team_elo.json/standings.json
    entries for reference.
    """
    starting_elo = compute_regressed_starting_elo(season, cfg)
    played_games, unplayed_games = sync_season_games(season)
    current_elo, live_standings, elo_log = _replay_with_elo_log(played_games, starting_elo, cfg)

    save_standings(season, cfg, live_standings)
    save_current_elo(season, cfg, current_elo, elo_log)

    return {
        'live_standings':   live_standings,
        'derived_base_elo': current_elo,
        'played_games':     played_games,
        'unplayed_games':   unplayed_games,
        'elo_log':          elo_log,
    }


def fetch_backtest_data(
    season: int, snapshot_date: str, cfg: SimulationConfig = SimulationConfig()
) -> dict[str, Any]:
    """
    Builds the data payload for backtesting. A backtest season is
    historical, so once the cache has fully synced it (every date through
    the season's end already fetched), re-running the same or a
    different backtest snapshot date costs zero API calls — the
    played/unplayed split for any snapshot date is re-derived locally
    from the cached, already-parsed games instead of re-fetching and
    re-parsing raw schedule data every time.
    """
    logger.info("Building backtest snapshot: %d season as of %s...", season, snapshot_date)
    starting_elo = compute_regressed_starting_elo(season, cfg)
    cached_played, cached_unplayed = sync_season_games(season)
    played_games, unplayed_games = split_games_for_backtest(
        cached_played + cached_unplayed, snapshot_date
    )
    current_elo, live_standings, elo_log = _replay_with_elo_log(played_games, starting_elo, cfg)
    full_played = cached_played

    return {
        'live_standings':     live_standings,
        'derived_base_elo':   current_elo,
        'played_games':       played_games,
        'unplayed_games':     unplayed_games,
        'elo_log':            elo_log,
        'true_playoff_teams': derive_actual_playoff_field(full_played),
        'snapshot_date':      snapshot_date,
        'season':             season,
    }


def derive_actual_playoff_field(full_played_games: list[Game]) -> list[TeamName]:
    """Returns a list of 12 team names that actually made the playoffs."""
    records: RecordTable = {
        t: {'W': 0, 'L': 0, 'div_W': 0, 'div_L': 0,
            'league_W': 0, 'league_L': 0, 'league_results': []}
        for t in ALL_TEAMS
    }
    h2h: H2HTable = {t: defaultdict(int) for t in ALL_TEAMS}
    for g in full_played_games:
        home, away = g.home, g.away
        w, l = g.winner, g.loser
        records[w]['W'] += 1
        records[l]['L'] += 1
        h2h[w][l] += 1
        if division_of(home) == division_of(away):
            records[w]['div_W'] += 1
            records[l]['div_L'] += 1
        if league_of(home) == league_of(away):
            records[w]['league_W'] += 1
            records[l]['league_L'] += 1
            records[w]['league_results'].append(1)
            records[l]['league_results'].append(0)

    playoff_teams: list[TeamName] = []
    for league in ['AL', 'NL']:
        div_winners, wc_teams = resolve_league_playoff_teams(records, h2h, league)
        playoff_teams.extend(div_winners)
        playoff_teams.extend(wc_teams)
    return playoff_teams


#==============================================================================
#CHUNK DISPATCH
#
#Splits num_sims across worker processes (each running
#simulation.monte_carlo_worker.run_chunk on its own independent slice)
#when the run is big enough to be worth it, or just runs one chunk
#in-process otherwise. See monte_carlo_worker.py's own header comment for
#why each chunk is a picklable top-level function rather than a method,
#and why re-running the same seed only reproduces the same result when
#the worker count also matches.
#==============================================================================

def _split_evenly(total: int, parts: int) -> list[int]:
    """Splits `total` into `parts` chunk sizes as evenly as possible (e.g.
    10 into 3 -> [4, 3, 3]) — plain `total // parts` would silently drop
    the remainder and run fewer sims than num_sims asked for."""
    base, remainder = divmod(total, parts)
    return [base + 1 if i < remainder else base for i in range(parts)]


def _run_all_chunks(
    num_sims: int,
    seed: int,
    base_rec: RecordTable,
    base_h2h: H2HTable,
    derived_base_elo: EloTable,
    unplayed_games: list[Game],
    cfg: SimulationConfig,
    rotations, bullpens, lineups,
    progress_callback: Callable[[int, int], None] | None,
) -> ChunkResult:
    worker_count = min(os.cpu_count() or 1, num_sims)
    if worker_count <= 1 or num_sims < _PARALLEL_MIN_SIMS:
        #Small run, or nothing to parallelize across — run it as a single
        #chunk in-process, with the same per-1%-of-run progress
        #granularity run_simulation_core used to report directly.
        logger.info("Running %d simulations sequentially (single process).", num_sims)
        return run_chunk(
            num_sims, seed, base_rec, base_h2h, derived_base_elo, unplayed_games, cfg,
            rotations=rotations, bullpens=bullpens, lineups=lineups,
            progress_callback=progress_callback,
        )

    chunk_sizes = _split_evenly(num_sims, worker_count)
    logger.info("Running %d simulations across %d worker processes (chunks: %s).",
               num_sims, worker_count, chunk_sizes)

    results: list[ChunkResult] = []
    completed = 0
    #spawn, not the platform default (fork on Linux) — this runs on a background
    #thread so the GUI stays responsive (see gui/launcher's run-in-thread pattern),
    #and forking a multi-threaded process is a known deadlock risk; spawn always
    #starts each worker as a clean fresh interpreter instead, at the cost of a
    #small one-time per-worker startup delay
    mp_context = multiprocessing.get_context('spawn')
    with ProcessPoolExecutor(max_workers=worker_count, mp_context=mp_context) as pool:
        futures = {
            pool.submit(
                run_chunk, chunk_size, seed + i, base_rec, base_h2h, derived_base_elo,
                unplayed_games, cfg, rotations, bullpens, lineups,
                #No progress_callback here — it can't cross a process boundary
                #(workers can't touch the caller's GUI/closures), so progress
                #is reported per-chunk-completed from the main process below
                #instead of per-1%-of-the-whole-run. Coarser, but still live.
                None,
            ): chunk_size
            for i, chunk_size in enumerate(chunk_sizes)
        }
        for future in as_completed(futures):
            results.append(future.result())
            completed += futures[future]
            if progress_callback is not None:
                progress_callback(completed, num_sims)

    if progress_callback is not None:
        progress_callback(num_sims, num_sims)

    return merge_chunk_results(results)


#==============================================================================
#SIMULATION CORE
#==============================================================================

def run_simulation_core(
    data: dict[str, Any],
    season: int,
    mode: str,
    cfg: SimulationConfig = SimulationConfig(),
    snapshot_date: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> SimulationResult:
    """
    Runs cfg.simulations Monte Carlo simulations given a data payload.
    Returns a SimulationResult.

    progress_callback, if given, is called as progress_callback(completed,
    total) roughly every 1% of the run (and once at the end). It must be
    cheap and thread-safe from the caller's side — the engine never touches
    any GUI object itself.
    """
    live_standings: Standings   = data['live_standings']
    derived_base_elo: EloTable  = data['derived_base_elo']
    played_games: list[Game]    = data['played_games']
    unplayed_games: list[Game]  = data['unplayed_games']
    elo_log: dict[int, EloSnapshot] = data.get('elo_log', {})
    num_sims = cfg.simulations

    #None means "pick a fresh seed" — resolve it now so it can be reported
    #back on the result. A local Random instance (not the `random` module)
    #keeps this run's randomness isolated from anything else using `random`.
    seed = cfg.random_seed if cfg.random_seed is not None else random.SystemRandom().randrange(2**31 - 1)
    resolved_cfg = cfg if cfg.random_seed == seed else dataclasses.replace(cfg, random_seed=seed)

    logger.info("Played games cataloged : %d", len(played_games))
    logger.info("Remaining sim queue    : %d", len(unplayed_games))
    logger.info("Random seed            : %d", seed)

    base_rec, base_h2h = build_base_records(played_games, live_standings)

    #Pitching staffs, built once from each team's starting
    #Elo and real roster/stats data (real rosters don't
    #reshuffle mid-simulation, so there's no need to regenerate these
    #inside the num_sims loop below — same reasoning as why
    #derived_base_elo itself is computed once per run). None when both
    #config gates are off, which is what tells play_series to fall back to
    #pure team-Elo games (see series_simulator.py).
    rotations = bullpens = lineups = None
    if cfg.simulate_postseason and (cfg.starting_pitcher_impact or cfg.bullpen_fatigue_impact or cfg.lineup_impact):
        #"As of" date for the last-30-days rolling stats window (Phase
        #6.1): the backtest snapshot date if we're backtesting, else
        #today — never the real current date during a backtest, or recent
        #form would be measured against games that haven't "happened" yet
        #from the simulation's point of view.
        as_of_date = snapshot_date or date.today().isoformat()
        all_rotations, all_bullpens = build_all_team_staffs(season, as_of_date, derived_base_elo, cfg)
        rotations = all_rotations if cfg.starting_pitcher_impact else None
        bullpens = all_bullpens if cfg.bullpen_fatigue_impact else None
        #Lineup selection needs to know the OPPOSING starter's throwing
        #hand, so it's only meaningful alongside real rotations.
        if cfg.lineup_impact and rotations is not None:
            lineups = build_all_team_lineups(season, as_of_date, derived_base_elo, cfg)

    merged = _run_all_chunks(
        num_sims, seed, base_rec, base_h2h, derived_base_elo, unplayed_games, cfg,
        rotations, bullpens, lineups, progress_callback,
    )

    playoff_odds = {t: merged.playoff_counts[t] / num_sims * 100 for t in ALL_TEAMS}
    world_series_odds = (
        {t: merged.champ_counts[t] / num_sims * 100 for t in ALL_TEAMS}
        if cfg.simulate_postseason else {}
    )

    #── projected (averaged) stats + most-common bracket ──────────────────────
    #Real played games contribute the SAME runs to every simulated season
    #(they already happened), so that part is summed once here rather than
    #every iteration; only the unplayed games' simulated runs need to be
    #accumulated inside the loop below.
    real_runs_scored: dict[TeamName, int] = defaultdict(int)
    real_runs_allowed: dict[TeamName, int] = defaultdict(int)
    for g in played_games:
        if g.home_score is None or g.away_score is None:
            continue
        real_runs_scored[g.home] += g.home_score
        real_runs_scored[g.away] += g.away_score
        real_runs_allowed[g.home] += g.away_score
        real_runs_allowed[g.away] += g.home_score

    #Running totals across all num_sims iterations — averaged at the end
    #rather than storing every season, per the "don't need to save all
    #1,000 seasons" design: just enough state to reconstruct the average.
    #(See simulation/monte_carlo_worker.py's ChunkResult/merge_chunk_results
    #for where these actually get built now — one ChunkResult per worker,
    #summed together in _run_all_chunks below.)

    #── projected (averaged) stats ────────────────────────────────────────
    projected_team_stats: dict[TeamName, dict[str, float]] = {}
    for t in ALL_TEAMS:
        games_avg = (merged.total_wins[t] + merged.total_losses[t]) / num_sims
        runs_scored_avg = real_runs_scored[t] + merged.total_sim_runs_scored[t] / num_sims
        runs_allowed_avg = real_runs_allowed[t] + merged.total_sim_runs_allowed[t] / num_sims
        projected_team_stats[t] = {
            'wins':          merged.total_wins[t] / num_sims,
            'losses':        merged.total_losses[t] / num_sims,
            'runs_scored':   runs_scored_avg,
            'runs_allowed':  runs_allowed_avg,
            #Approximate team ERA from runs allowed, treating all of them as
            #earned (a standard simplification): ERA = earned runs * 9 / IP,
            #and IP per game is ~9, so this reduces to runs allowed per game
            #— only as precise as the runs model in game_simulator.py.
            'era':           (runs_allowed_avg / games_avg) if games_avg else 0.0,
        }

    #── per-game win probability (unplayed games only) ──────────────────────
    unplayed_game_home_win_pct: dict[int, float] = {
        g.game_pk: merged.game_home_win_counts[g.game_pk] / num_sims * 100 for g in unplayed_games
    }

    #── most common bracket ───────────────────────────────────────────────
    #Purely outcome-based: a bracket's identity is its seeds and which team
    #won each round (see PlayoffBracketResult.as_key and play_series, which
    #only ever returns the winning team — game/series scores never factor
    #into what counts as "the same bracket").
    #
    #When the top count is shared by more than one bracket — the normal
    #case whenever many games remain, since the space of possible exact
    #brackets is astronomically larger than any practical number of
    #simulations (verified: 5,000 sims with a half season left produced
    #5,000 distinct brackets, zero repeats) — picking "whichever happened
    #to occur first in simulation order" would be arbitrary and would tell
    #you nothing. Instead, among brackets tied for the top count, this
    #breaks the tie by preferring whichever tied bracket's CHAMPION has the
    #highest overall championship odds across every simulation (already
    #computed as champ_counts) — a real, principled signal about which of
    #the tied outcomes is actually more likely, rather than an artifact of
    #iteration order.
    projected_bracket: PlayoffBracketResult | None = None
    projected_bracket_pct = 0.0
    projected_bracket_tied_count = 0
    if merged.bracket_counts:
        max_count = max(merged.bracket_counts.values())
        tied_keys = [k for k, c in merged.bracket_counts.items() if c == max_count]
        best_key = max(tied_keys, key=lambda k: merged.champ_counts.get(merged.bracket_examples[k].champion, 0))
        projected_bracket = merged.bracket_examples[best_key]
        projected_bracket_pct = merged.bracket_counts[best_key] / num_sims * 100
        projected_bracket_tied_count = len(tied_keys)

    return SimulationResult(
        mode=mode,
        season=season,
        cfg=resolved_cfg,
        snapshot_date=snapshot_date,
        playoff_odds=playoff_odds,
        world_series_odds=world_series_odds,
        live_elo=derived_base_elo,
        elo_log=elo_log,
        live_standings=live_standings,
        played_games=played_games,
        unplayed_games=unplayed_games,
        true_playoff_teams=data.get('true_playoff_teams', []),
        projected_team_stats=projected_team_stats,
        unplayed_game_home_win_pct=unplayed_game_home_win_pct,
        projected_bracket=projected_bracket,
        projected_bracket_pct=projected_bracket_pct,
        projected_bracket_tied_count=projected_bracket_tied_count,
    )
