# ==============================================================================
# DISPLAY FORMATTING
# gui/widgets/formatting.py
#
# Shared helpers so percentage/decimal display respects the user's saved
# display settings instead of each tab hardcoding its own f'{x:.1f}%'.
# ==============================================================================

from data.settings_store import load_settings

_settings = load_settings()


def format_pct(value: float) -> str:
    """Formats a percentage value (expected on a 0-100 scale, e.g. 63.4 for
    63.4%) according to the user's saved display settings: either
    'Percent' (63.4%) or 'Fraction' (0.634), at the user's chosen decimal
    place count."""
    places = _settings.decimal_places
    if _settings.percentage_format == 'fraction':
        return f'{value / 100:.{places}f}'
    return f'{value:.{places}f}%'


def format_decimal(value: float) -> str:
    """Formats a plain decimal (ERA, PCT, etc.) at the user's chosen
    decimal place count."""
    return f'{value:.{_settings.decimal_places}f}'
