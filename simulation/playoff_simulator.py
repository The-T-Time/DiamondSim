# ==============================================================================
# PLAYOFF SIMULATOR
# simulation/playoff_simulator.py
#
# Orchestrates one full postseason from a simulated regular season's final
# records:
#
#   Regular Season -> Wild Card (best-of-3) -> Division Series (best-of-5)
#   -> Championship Series (best-of-7) -> World Series (best-of-7)
#
# Decides the bracket structure only (seeding, matchups, hosting); the
# actual game-by-game simulation is series_simulator.play_series.
# ==============================================================================

from __future__ import annotations

import random

from models.bullpen import Bullpen
from models.hitter import TeamLineups
from models.pitcher import Rotation
from models.playoff_bracket import PlayoffBracketResult
from models.simulation_config import SimulationConfig
from models.team import TeamName
from simulation.elo import EloTable
from simulation.fatigue import BullpenFatigueTracker
from simulation.series_simulator import play_series
from simulation.standings import H2HTable, RecordTable, seed_league
from simulation.tiebreakers import run_mlb_tiebreaker

#Days off between playoff rounds before the next series' game 1, on top of
#whatever incremental rest play_series already applies game-to-game within
#a round. Real MLB builds a multi-day gap in here for travel/scheduling;
#it's the main reason a team doesn't carry its LDS bullpen fatigue
#untouched straight into the LCS.
INTER_ROUND_REST_DAYS: float = 3.0


def simulate_postseason(
    records: RecordTable,
    h2h: H2HTable,
    elo: EloTable,
    cfg: SimulationConfig,
    rng: random.Random,
    rotations: dict[TeamName, Rotation] | None = None,
    bullpens: dict[TeamName, Bullpen] | None = None,
    lineups: dict[TeamName, TeamLineups] | None = None,
) -> PlayoffBracketResult:
    """
    Run one full postseason from the final simulated regular season and
    return the complete bracket (seeds, every round's winners, and the
    champion) — not just the champion — so callers can track the most
    common bracket across many simulations, not only the most common
    champion.

    `rotations`/`bullpens`/`lineups` are optional. Leave
    all None (the default) to reproduce the original pure-team-Elo bracket
    exactly — see series_simulator.play_series's docstring for the full
    behavior matrix. When given, a single BullpenFatigueTracker is created
    for this call and shared across every series in the bracket, with
    extra rest applied to the winner of each round before its next series
    begins.
    """
    fatigue = BullpenFatigueTracker() if bullpens is not None else None

    def _series(host: TeamName, guest: TeamName, best_of: int) -> TeamName:
        winner = play_series(
            host, guest, elo, cfg, rng, best_of=best_of,
            rotations=rotations, bullpens=bullpens, fatigue=fatigue, lineups=lineups,
        )
        if fatigue is not None:
            fatigue.rest(winner, INTER_ROUND_REST_DAYS)
        return winner

    league_champs: dict[str, TeamName] = {}
    league_seeds: dict[str, list[TeamName]] = {}
    league_wc_winners: dict[str, tuple[TeamName, TeamName]] = {}
    league_ds_winners: dict[str, tuple[TeamName, TeamName]] = {}
    for league in ('AL', 'NL'):
        s = seed_league(records, h2h, league)   #s[0]=seed1 ... s[5]=seed6
        league_seeds[league] = s

        #Wild Card round (best-of-3): 3 vs 6 and 4 vs 5, higher seed hosts.
        w36 = _series(s[2], s[5], 3)
        w45 = _series(s[3], s[4], 3)
        league_wc_winners[league] = (w36, w45)

        #Division Series (best-of-5): 1 vs winner(4/5), 2 vs winner(3/6).
        ds1 = _series(s[0], w45, 5)
        ds2 = _series(s[1], w36, 5)
        league_ds_winners[league] = (ds1, ds2)

        #League Championship Series (best-of-7): higher seed hosts.
        hi, lo = (ds1, ds2) if s.index(ds1) <= s.index(ds2) else (ds2, ds1)
        league_champs[league] = _series(hi, lo, 7)

    al, nl = league_champs['AL'], league_champs['NL']
    #World Series home-field: better regular-season record, tiebreaker if even.
    if records[al]['W'] != records[nl]['W']:
        host = al if records[al]['W'] > records[nl]['W'] else nl
    else:
        host = run_mlb_tiebreaker([al, nl], records, h2h)[0]
    guest = nl if host == al else al
    champion = _series(host, guest, 7)

    return PlayoffBracketResult(
        al_seeds=tuple(league_seeds['AL']),
        nl_seeds=tuple(league_seeds['NL']),
        al_wc_winners=league_wc_winners['AL'],
        nl_wc_winners=league_wc_winners['NL'],
        al_ds_winners=league_ds_winners['AL'],
        nl_ds_winners=league_ds_winners['NL'],
        al_champion=al,
        nl_champion=nl,
        ws_host=host,
        ws_guest=guest,
        champion=champion,
    )
