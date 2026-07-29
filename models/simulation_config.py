# ==============================================================================
# SIMULATION CONFIG
# models/simulation_config.py
#
# Tunable knobs for one simulation run, bundled instead of scattered as
# module-level constants. Defaults mirror config.py; pass a custom
# instance (or a named preset) to try a different model.
# ==============================================================================

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Optional

import config as _config


@dataclass(frozen=True)
class SimulationConfig:
    simulations:            int   = _config.DEFAULT_SIMS
    elo_k:                  float = _config.ELO_K
    home_field_advantage:   float = _config.HOME_FIELD_ADVANTAGE
    elo_baseline:           float = _config.ELO_BASELINE
    regression_weight:      float = _config.REGRESSION_WEIGHT
    mov_weight:             float = _config.MOV_WEIGHT
    sim_margin_cap:         int   = _config.SIM_MARGIN_CAP
    backtest_threshold_pct: float = _config.BACKTEST_THRESHOLD_PCT
    simulate_postseason:    bool  = _config.SIMULATE_POSTSEASON

    #Starting-pitcher matchups and bullpen fatigue in the
    #postseason bracket. Both default on but are independent gates: turning
    #starting_pitcher_impact off falls back to pure team-Elo postseason
    #games (5.6 behavior); bullpen_fatigue_impact only matters when
    #starting_pitcher_impact is also on, since fatigue tracking rides
    #along with the same per-game simulation path. Neither touches the
    #regular season, which stays pure team-Elo either way.
    starting_pitcher_impact: bool = _config.STARTING_PITCHER_IMPACT
    bullpen_fatigue_impact:  bool = _config.BULLPEN_FATIGUE_IMPACT

    #Whether a postseason game's win probability also factors
    #in each team's lineup (see simulation/pitching.py's game_win_prob).
    lineup_impact: bool = _config.LINEUP_IMPACT

    #Real pitcher ratings derived from MLB roster/stats data
    #(simulation/player_rating.py, data/player_stats.py) instead of the
    #Synthetic Elo-derived staff. use_real_pitcher_stats is the
    #master gate; the rest tune the FIP-to-Elo conversion.
    #Small-sample shrinkage constant + the season/last-30-days/
    #career rolling blend weights. See config.py for the reasoning behind
    #each default.
    use_real_pitcher_stats:   bool  = _config.USE_REAL_PITCHER_STATS
    pitcher_fip_constant:     float = _config.PITCHER_FIP_CONSTANT
    pitcher_league_avg_fip:   float = _config.PITCHER_LEAGUE_AVG_FIP
    pitcher_fip_elo_scale:    float = _config.PITCHER_FIP_ELO_SCALE
    pitcher_shrinkage_innings: float = _config.PITCHER_SHRINKAGE_INNINGS
    pitcher_season_weight:        float = _config.PITCHER_SEASON_WEIGHT
    pitcher_last30_days_weight:   float = _config.PITCHER_LAST_30_DAYS_WEIGHT
    pitcher_career_weight:         float = _config.PITCHER_CAREER_WEIGHT

    #Position player (hitting) ratings, same structure and
    #reasoning as the pitcher fields above: an OPS-based Elo conversion
    #with small HR/BB%/K% modifiers, PA-based shrinkage, and a season/
    #last-30-days/career blend. See config.py for the reasoning behind
    #each default.
    use_real_hitter_stats:           bool  = _config.USE_REAL_HITTER_STATS
    hitter_league_avg_ops:           float = _config.HITTER_LEAGUE_AVG_OPS
    hitter_ops_elo_scale:            float = _config.HITTER_OPS_ELO_SCALE
    hitter_league_avg_hr_per_600pa:  float = _config.HITTER_LEAGUE_AVG_HR_PER_600PA
    hitter_hr_rate_elo_scale:        float = _config.HITTER_HR_RATE_ELO_SCALE
    hitter_league_avg_bb_rate:       float = _config.HITTER_LEAGUE_AVG_BB_RATE
    hitter_bb_rate_elo_scale:        float = _config.HITTER_BB_RATE_ELO_SCALE
    hitter_league_avg_k_rate:        float = _config.HITTER_LEAGUE_AVG_K_RATE
    hitter_k_rate_elo_scale:         float = _config.HITTER_K_RATE_ELO_SCALE
    hitter_shrinkage_pa:             float = _config.HITTER_SHRINKAGE_PA
    hitter_season_weight:            float = _config.HITTER_SEASON_WEIGHT
    hitter_last30_days_weight:       float = _config.HITTER_LAST_30_DAYS_WEIGHT
    hitter_career_weight:            float = _config.HITTER_CAREER_WEIGHT

    #None = pick a fresh random seed each run (default). Set an int to make
    #a run byte-for-byte reproducible — same season + same cfg + same seed
    #always produces the same playoff_odds. run_simulation_core resolves
    #None to an actual int and returns it on the result's cfg, so a random
    #run can always be reproduced afterward from result.cfg.random_seed.
    random_seed: Optional[int] = None

    def __post_init__(self) -> None:
        if self.simulations <= 0:
            raise ValueError(f"simulations must be positive, got {self.simulations!r}")
        if self.elo_k <= 0:
            raise ValueError(f"elo_k must be positive, got {self.elo_k!r}")
        if self.elo_baseline <= 0:
            raise ValueError(f"elo_baseline must be positive, got {self.elo_baseline!r}")
        if not (0.0 <= self.regression_weight <= 1.0):
            raise ValueError(f"regression_weight must be in [0, 1], got {self.regression_weight!r}")
        if self.mov_weight < 0:
            raise ValueError(f"mov_weight must be >= 0, got {self.mov_weight!r}")
        if self.sim_margin_cap < 1:
            raise ValueError(f"sim_margin_cap must be >= 1, got {self.sim_margin_cap!r}")
        if self.pitcher_shrinkage_innings <= 0:
            raise ValueError(
                f"pitcher_shrinkage_innings must be positive, got {self.pitcher_shrinkage_innings!r}"
            )
        if self.pitcher_season_weight < 0 or self.pitcher_last30_days_weight < 0 or self.pitcher_career_weight < 0:
            raise ValueError("pitcher window weights must be >= 0")
        if self.pitcher_season_weight + self.pitcher_last30_days_weight + self.pitcher_career_weight <= 0:
            raise ValueError("at least one pitcher window weight must be positive")
        if self.hitter_shrinkage_pa <= 0:
            raise ValueError(f"hitter_shrinkage_pa must be positive, got {self.hitter_shrinkage_pa!r}")
        if self.hitter_season_weight < 0 or self.hitter_last30_days_weight < 0 or self.hitter_career_weight < 0:
            raise ValueError("hitter window weights must be >= 0")
        if self.hitter_season_weight + self.hitter_last30_days_weight + self.hitter_career_weight <= 0:
            raise ValueError("at least one hitter window weight must be positive")

    #── presets ──────────────────────────────────────────────────────────────
    @classmethod
    def normal(cls) -> SimulationConfig:
        """The 'Normal' preset — the simulator's out-of-the-box defaults
        (config.py's hardcoded constants), same as Conservative/Aggressive:
        a fixed reference point that ignores whatever is saved in the
        Settings screen."""
        return cls()

    @classmethod
    def user(cls) -> SimulationConfig:
        """The 'User' preset — whatever is currently saved in the Settings
        screen (see models/app_settings.py). Adjusting weights/toggles
        there and saving changes what 'User' means from then on; Normal/
        Conservative/Aggressive are unaffected."""
        from data.settings_store import load_settings
        overrides = load_settings().to_simulation_config_kwargs()
        return cls(**overrides)

    @classmethod
    def conservative(cls) -> SimulationConfig:
        """Slower-reacting ratings: heavier prior-year regression, wins matter more than margin."""
        return cls(elo_k=20.0, mov_weight=0.05, regression_weight=0.85)

    @classmethod
    def aggressive(cls) -> SimulationConfig:
        """Fast-reacting ratings: recent form and blowouts move the needle hard."""
        return cls(elo_k=40.0, mov_weight=0.45, regression_weight=0.6)

    @classmethod
    def by_name(cls, name: str, **overrides) -> SimulationConfig:
        """Look up a preset by name (case-insensitive) and apply any field overrides."""
        presets = {
            'normal':       cls.normal,
            'user':         cls.user,
            'conservative': cls.conservative,
            'aggressive':   cls.aggressive,
        }
        try:
            cfg = presets[name.lower()]()
        except KeyError:
            raise ValueError(f"Unknown model preset {name!r}; choose from {list(presets)}") from None
        return dataclasses.replace(cfg, **overrides) if overrides else cfg
