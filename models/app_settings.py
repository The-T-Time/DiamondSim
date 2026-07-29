# ==============================================================================
# APP SETTINGS
# models/app_settings.py
#
# User-adjustable settings: simulation weights/toggles (saved values
# become the "User" model preset; see SimulationConfig.user()) and
# display settings (theme, decimal places, percentage format).
# ==============================================================================

from __future__ import annotations

from dataclasses import dataclass, fields

import config as _config


@dataclass
class AppSettings:
    #── simulation weights ────────────────────────────────────────────────────
    elo_k:                float = _config.ELO_K
    home_field_advantage: float = _config.HOME_FIELD_ADVANTAGE
    regression_weight:    float = _config.REGRESSION_WEIGHT
    mov_weight:           float = _config.MOV_WEIGHT
    sim_margin_cap:       int   = _config.SIM_MARGIN_CAP

    #── simulation feature toggles ───────────────────────────────────────────
    #enable_home_field_advantage off is equivalent to home_field_advantage=0
    #(see to_simulation_config_kwargs) — kept as its own toggle rather than
    #just "set the number to 0" so the slider's last value is remembered
    #even while the feature is switched off.
    enable_home_field_advantage: bool = True
    use_real_pitcher_stats:      bool = _config.USE_REAL_PITCHER_STATS
    use_real_hitter_stats:       bool = _config.USE_REAL_HITTER_STATS
    starting_pitcher_impact:     bool = _config.STARTING_PITCHER_IMPACT
    bullpen_fatigue_impact:      bool = _config.BULLPEN_FATIGUE_IMPACT
    lineup_impact:                bool = _config.LINEUP_IMPACT

    #── display settings ─────────────────────────────────────────────────────
    theme: str = 'light'                #'light' | 'dark'
    decimal_places: int = 1             #for most displayed decimals (ERA, PCT, etc.)
    percentage_format: str = 'percent'  #'percent' (63.4%) | 'fraction' (0.634)

    def to_simulation_config_kwargs(self) -> dict:
        """Field overrides for SimulationConfig, reflecting these settings."""
        return {
            'elo_k':                  self.elo_k,
            'home_field_advantage':   self.home_field_advantage if self.enable_home_field_advantage else 0.0,
            'regression_weight':      self.regression_weight,
            'mov_weight':             self.mov_weight,
            'sim_margin_cap':         self.sim_margin_cap,
            'use_real_pitcher_stats': self.use_real_pitcher_stats,
            'use_real_hitter_stats':  self.use_real_hitter_stats,
            'starting_pitcher_impact': self.starting_pitcher_impact,
            'bullpen_fatigue_impact': self.bullpen_fatigue_impact,
            'lineup_impact':          self.lineup_impact,
        }


DEFAULT_SETTINGS = AppSettings()

#The fields that define a simulation "model" — the same fields Conservative/
#Aggressive override in models/simulation_config.py. Feature toggles and
#display settings aren't part of "the model," so they're deliberately left
#out of the User-vs-Normal comparison below.
_MODEL_WEIGHT_FIELDS = (
    'elo_k', 'home_field_advantage', 'enable_home_field_advantage',
    'regression_weight', 'mov_weight', 'sim_margin_cap',
)


def has_customized_model_weights(settings: AppSettings) -> bool:
    """True if any simulation-weight field in `settings` differs from the
    factory default. Used to decide whether the Model dropdown on the
    Simulate/Backtest forms should default to 'Normal' (untouched) or
    'User' (customized) when the form opens."""
    return any(
        getattr(settings, f) != getattr(DEFAULT_SETTINGS, f)
        for f in _MODEL_WEIGHT_FIELDS
    )


def settings_field_names() -> list[str]:
    return [f.name for f in fields(AppSettings)]
