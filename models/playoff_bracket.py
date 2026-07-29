# ==============================================================================
# PLAYOFF BRACKET RESULT
# models/playoff_bracket.py
#
# One full postseason outcome from a single simulated (or real) season:
# who was seeded where, who won each round, and the eventual champion.
# Frozen + built entirely from tuples so it's hashable — that's what lets
# simulator.py count "how many times did this exact bracket happen" across
# every Monte Carlo iteration and pick the most common one at the end.
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass

from models.team import TeamName


@dataclass(frozen=True)
class PlayoffBracketResult:
    #seeds[league] = (seed1, seed2, seed3, seed4, seed5, seed6) — seeds 1-3
    #are the division winners in record order, 4-6 are the wild cards.
    al_seeds: tuple[TeamName, ...]
    nl_seeds: tuple[TeamName, ...]

    #Wild Card round winners: (winner of 3-vs-6, winner of 4-vs-5)
    al_wc_winners: tuple[TeamName, TeamName]
    nl_wc_winners: tuple[TeamName, TeamName]

    #Division Series winners: (winner of 1-vs-lower-WC, winner of 2-vs-other-WC)
    al_ds_winners: tuple[TeamName, TeamName]
    nl_ds_winners: tuple[TeamName, TeamName]

    al_champion: TeamName
    nl_champion: TeamName

    ws_host: TeamName
    ws_guest: TeamName
    champion: TeamName

    @property
    def division_winners(self) -> tuple[TeamName, ...]:
        return self.al_seeds[:3] + self.nl_seeds[:3]

    @property
    def wild_card_teams(self) -> tuple[TeamName, ...]:
        return self.al_seeds[3:6] + self.nl_seeds[3:6]

    def as_key(self) -> tuple:
        """A single hashable value uniquely identifying this bracket, for
        use as a dict key when counting how often each distinct bracket
        occurs across many simulations.

        Deliberately excludes anything that affected how the games were
        simulated but isn't part of the displayed bracket itself: series
        scores (play_series only ever returns a winner, never a score —
        see series_simulator.py), World Series home-field advantage,
        number of games played, win probabilities, and Elo. Two
        simulations whose displayed bracket is identical must produce the
        same key, even if the underlying simulation details (e.g. which
        team had home-field, or exactly how many games a series went)
        differed. Only home-field advantage is a field on this dataclass
        (ws_host/ws_guest, kept for display) — it's intentionally left out
        of the key below.

        Seeds 3-vs-6 and 4-vs-5 are treated as interchangeable: it's
        literally the same Wild Card matchup regardless of which team
        happened to be the 3-seed vs the 6-seed (or 4 vs 5) in this
        particular simulation. Seeds 1 and 2 themselves are kept exact,
        though — they aren't paired with each other the way 3/6 and 4/5
        are, each is paired with a *different* external group (seed 1
        always faces the 4-vs-5 winner, seed 2 always faces the 3-vs-6
        winner), so relabeling which bye team is "1" vs "2" would actually
        change who they play, not just how the result is labeled.

        What IS just a labeling artifact is which Division Series result
        gets called "DS1" vs "DS2" internally — that's an arbitrary
        ordering choice, not a real distinction — so the two DS winners
        are compared as an unordered pair rather than a fixed order."""
        def normalize(seeds: tuple[TeamName, ...]) -> tuple:
            return (seeds[0], seeds[1],
                    frozenset({seeds[2], seeds[5]}), frozenset({seeds[3], seeds[4]}))

        return (
            normalize(self.al_seeds), normalize(self.nl_seeds),
            self.al_wc_winners, self.nl_wc_winners,
            frozenset(self.al_ds_winners), frozenset(self.nl_ds_winners),
            self.al_champion, self.nl_champion,
            self.champion,
        )
