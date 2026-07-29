# ==============================================================================
# CHART RENDERING
# charts/charts.py
# ==============================================================================

from __future__ import annotations

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.axes
import seaborn as sns

from data.settings_store import load_settings
from data.teams import ALL_TEAMS, TEAM_REGISTRY
from models.simulation_result import SimulationResult
from utils.logger import get_logger

logger = get_logger(__name__)

_DARK_THEME = (load_settings().theme == 'dark')
_FIG_BG   = '#1a1d21' if _DARK_THEME else 'white'
_AXES_BG  = '#25282e' if _DARK_THEME else 'white'
_TEXT_FG  = '#ecf0f1' if _DARK_THEME else '#2c3e50'
_GRID_FG  = '#3a3f45' if _DARK_THEME else '#b0b0b0'


def _style_axes_for_theme(fig: plt.Figure, *axes: matplotlib.axes.Axes) -> None:
    """Applies the app's light/dark theme to a matplotlib figure — done
    per-figure rather than globally via rcParams so this file works the
    same whether or not other code has touched matplotlib's global state.
    Matplotlib has no idea about the app's own theme setting by default,
    so without this a dark-themed app would still show stark white charts
    with barely-visible dark-on-dark text."""
    fig.patch.set_facecolor(_FIG_BG)
    for ax in axes:
        ax.set_facecolor(_AXES_BG)
        ax.tick_params(colors=_TEXT_FG)
        ax.xaxis.label.set_color(_TEXT_FG)
        ax.yaxis.label.set_color(_TEXT_FG)
        ax.title.set_color(_TEXT_FG)
        for spine in ax.spines.values():
            spine.set_color(_GRID_FG)
        ax.grid(color=_GRID_FG, alpha=0.4)


def _make_odds_bar(
    ax: matplotlib.axes.Axes,
    plot_data_sorted: list[dict],
    title: str,
    xlabel: str = 'Probability of Reaching Playoffs (%)',
) -> None:
    cmap    = plt.get_cmap('RdYlGn')
    teams   = [d['label']  for d in plot_data_sorted]
    chances = [d['chance'] for d in plot_data_sorted]
    colors  = [cmap(v / 100.0) for v in chances]

    bp = sns.barplot(x=chances, y=teams, palette=colors,
                     hue=teams, legend=False, width=0.75, ax=ax)

    for p in bp.patches:
        w = p.get_width()
        if w > 0:
            ax.text(w + 0.8, p.get_y() + p.get_height() / 2,
                    f'{w:.1f}%', ha='left', va='center',
                    fontsize=9, fontweight='bold', color=_TEXT_FG)

    ax.set_title(title, fontsize=13, fontweight='bold', pad=14)
    ax.set_xlabel(xlabel, fontsize=11, fontweight='bold')
    ax.set_xlim(0, 116)           #extra room so "100.0%" label never clips
    ax.tick_params(axis='y', labelsize=9)


def _new_fig(*args, **kwargs) -> tuple[plt.Figure, plt.Axes]:
    """
    Creates a figure with constrained_layout so margins auto-fit the
    content (long y-axis team-name labels, the x-axis title, title/subtitle)
    instead of a fixed manual margin that only fits one specific figure size.

    Explicit w_pad/h_pad are set because the figure gets resized after
    creation (see gui/graph_tab/resize.py, which fits it to the actual
    on-screen frame) — constrained_layout's default padding is tight enough
    that a label can end up flush against — or just past — the figure edge
    at some frame sizes, especially once the reserved toolbar strip below
    the canvas is accounted for. Padding here is a fixed guaranteed
    minimum regardless of final figure size.
    """
    fig, ax = plt.subplots(*args, layout='constrained', **kwargs)
    fig.get_layout_engine().set(w_pad=0.12, h_pad=0.08)
    axes_list = ax.flatten().tolist() if hasattr(ax, 'flatten') else [ax]
    _style_axes_for_theme(fig, *axes_list)
    return fig, ax


#==============================================================================
#SIMULATION FIGURES
#==============================================================================

def build_simulation_figures(result: SimulationResult) -> list[plt.Figure]:
    sns.set_theme(style='whitegrid')

    plot_data = [
        {
            'label':    f"{t} ({TEAM_REGISTRY[t].division})",
            'raw_team': t,
            'chance':   result.playoff_odds.get(t, 0.0),
            'division': TEAM_REGISTRY[t].division,
        }
        for t in ALL_TEAMS
    ]
    sorted_data = sorted(plot_data, key=lambda x: x['chance'], reverse=True)

    #── Figure 1: overall ranking ─────────────────────────────────────────────
    fig1, ax1 = _new_fig(figsize=(12, 14))
    _make_odds_bar(
        ax1, sorted_data,
        title=(
            f"Postseason Odds — {result.season} Simulation Engine\n"
            "(Regressed YoY Elo Baseline + Standard Tiebreakers)"
        ),
    )

    #── Figure 2: divisional breakdown ────────────────────────────────────────
    cmap = plt.get_cmap('RdYlGn')
    fig2, ax2 = _new_fig(figsize=(12, 16))
    sl, sc, sco = [], [], []
    separator_idx = []

    for div in sorted({t.division for t in TEAM_REGISTRY.values()}):
        separator_idx.append(len(sl))
        sl.append(f'— {div} —')
        sc.append(0)
        sco.append((0, 0, 0, 0))
        for item in sorted(
            [d for d in plot_data if d['division'] == div],
            key=lambda x: x['chance'], reverse=True,
        ):
            sl.append(f"  {item['raw_team']}")
            sc.append(item['chance'])
            sco.append(cmap(item['chance'] / 100.0))

    bp2 = sns.barplot(x=sc, y=sl, palette=sco, hue=sl,
                      legend=False, width=0.8, ax=ax2)
    for i, p in enumerate(bp2.patches):
        w = p.get_width()
        if i not in separator_idx and w > 0:
            ax2.text(w + 0.8, p.get_y() + p.get_height() / 2,
                     f'{w:.1f}%', ha='left', va='center',
                     fontsize=9, fontweight='bold')

    for i in range(6):
        if i > 0:
            ax2.axhline(y=i * 6, color='#333', linewidth=1, alpha=0.8)
        if i % 2 == 1:
            ax2.axhspan(i * 6, i * 6 + 5.5, color='gray', alpha=0.07, zorder=0)
    for lbl in ax2.get_yticklabels():
        if '—' in lbl.get_text():
            lbl.set_fontweight('bold')
            lbl.set_fontsize(10)
            lbl.set_color('#1f77b4')

    ax2.set_ylim(len(sl) - 0.5, -0.5)
    ax2.set_title(f'Postseason Odds by Division — {result.season}',
                  fontsize=13, fontweight='bold', pad=14)
    ax2.set_xlabel('Probability of Reaching Playoffs (%)', fontsize=11, fontweight='bold')
    ax2.set_xlim(0, 116)
    ax2.tick_params(axis='y', labelsize=9)
    ax2.grid(False, axis='y')

    return [fig1, fig2]


#==============================================================================
#BACKTEST FIGURES
#==============================================================================

def build_backtest_figures(result: SimulationResult) -> list[plt.Figure]:
    season        = result.season
    snapshot_date = result.snapshot_date
    true_playoff  = set(result.true_playoff_teams)
    num_played    = len(result.played_games)
    num_remaining = len(result.unplayed_games)
    total_games   = num_played + num_remaining
    pct_complete  = num_played / total_games * 100 if total_games else 0

    sns.set_theme(style='whitegrid')

    plot_data = sorted(
        [
            {
                'label':    f"{t} ({TEAM_REGISTRY[t].division})",
                'raw_team': t,
                'chance':   result.playoff_odds.get(t, 0.0),
                'division': TEAM_REGISTRY[t].division,
            }
            for t in ALL_TEAMS
        ],
        key=lambda x: x['chance'], reverse=True,
    )

    #── Figure 1: predicted odds ───────────────────────────────────────────────
    fig1, ax1 = _new_fig(figsize=(12, 14))
    _make_odds_bar(
        ax1, plot_data,
        title=(
            f"Backtest: {season} Predicted Playoff Odds as of {snapshot_date}\n"
            f"({pct_complete:.1f}% of season complete — {num_played} games played)"
        ),
        xlabel='Predicted Probability of Reaching Playoffs (%)',
    )

    #── Figure 2: accuracy breakdown ──────────────────────────────────────────
    threshold    = result.cfg.backtest_threshold_pct
    predicted_in = {d['raw_team'] for d in plot_data if d['chance'] >= threshold}
    true_pos  = predicted_in & true_playoff
    false_pos = predicted_in - true_playoff
    false_neg = true_playoff - predicted_in
    true_neg  = (set(ALL_TEAMS) - predicted_in) - true_playoff

    correct  = len(true_pos) + len(true_neg)
    accuracy = correct / len(ALL_TEAMS) * 100
    brier    = sum(
        ((d['chance'] / 100.0) - (1.0 if d['raw_team'] in true_playoff else 0.0)) ** 2
        for d in plot_data
    ) / len(plot_data)

    logger.info("\n=== BACKTEST RESULTS: %s as of %s ===", season, snapshot_date)
    logger.info("  Classification accuracy : %.1f%%  (%d/%d teams)",
                accuracy, correct, len(ALL_TEAMS))
    logger.info("  Brier score             : %.4f  (lower = better; random baseline = 0.2400)",
                brier)
    logger.info("  True positives  : %s", sorted(true_pos))
    logger.info("  False positives : %s", sorted(false_pos))
    logger.info("  False negatives : %s", sorted(false_neg))

    outcome_colors = []
    for d in plot_data:
        t = d['raw_team']
        if   t in true_pos:  outcome_colors.append('#2ecc71')
        elif t in true_neg:  outcome_colors.append('#95a5a6')
        elif t in false_pos: outcome_colors.append('#e74c3c')
        else:                outcome_colors.append('#e67e22')

    fig2, axes = _new_fig(1, 2, figsize=(16, 10),
                          gridspec_kw={'width_ratios': [2, 1]})
    ax_left, ax_right = axes

    bp2 = sns.barplot(x=[d['chance'] for d in plot_data],
                      y=[d['label']  for d in plot_data],
                      palette=outcome_colors, hue=[d['label'] for d in plot_data],
                      legend=False, width=0.75, ax=ax_left)
    for p in bp2.patches:
        w = p.get_width()
        if w > 0:
            ax_left.text(w + 0.8, p.get_y() + p.get_height() / 2,
                         f'{w:.1f}%', ha='left', va='center',
                         fontsize=8, fontweight='bold')

    ax_left.axvline(x=threshold, color=_TEXT_FG, linestyle='--', linewidth=1.5, alpha=0.6)
    ax_left.set_title(
        f"Backtest Accuracy — {season} as of {snapshot_date}\n"
        f"Accuracy: {accuracy:.1f}%  ({correct}/{len(ALL_TEAMS)} teams)   Brier: {brier:.4f}",
        fontsize=12, fontweight='bold', pad=12)
    ax_left.set_xlabel('Predicted Playoff Odds (%)', fontsize=10, fontweight='bold')
    ax_left.set_xlim(0, 122)
    ax_left.tick_params(axis='y', labelsize=9)
    ax_left.legend(handles=[
        plt.Rectangle((0,0),1,1, color='#2ecc71', label=f'True positive  ({len(true_pos)})'),
        plt.Rectangle((0,0),1,1, color='#95a5a6', label=f'True negative  ({len(true_neg)})'),
        plt.Rectangle((0,0),1,1, color='#e74c3c', label=f'False positive ({len(false_pos)})'),
        plt.Rectangle((0,0),1,1, color='#e67e22', label=f'False negative ({len(false_neg)})'),
    ], loc='lower right', fontsize=9)

    sizes  = [len(true_pos), len(true_neg), len(false_pos), len(false_neg)]
    labels = [f'True +\n({len(true_pos)})', f'True −\n({len(true_neg)})',
              f'False +\n({len(false_pos)})', f'False −\n({len(false_neg)})']
    colors = ['#2ecc71', '#95a5a6', '#e74c3c', '#e67e22']
    _, _, autotexts = ax_right.pie(
        sizes, labels=labels, colors=colors, autopct='%1.0f%%', startangle=90,
        wedgeprops={'width': 0.55, 'edgecolor': 'white', 'linewidth': 2},
        textprops={'fontsize': 10})
    for at in autotexts:
        at.set_fontweight('bold')
    ax_right.set_title(f'Prediction Breakdown\n(threshold >{threshold:.0f}%)',
                       fontsize=11, fontweight='bold', pad=12)
    ax_right.text(0, 0, f'{accuracy:.1f}%\naccuracy\nBrier: {brier:.4f}',
                  ha='center', va='center', fontsize=11, fontweight='bold', color=_TEXT_FG)

    fig2.suptitle(
        f"{season} Backtest — sim at {snapshot_date} vs actual postseason field",
        fontsize=13, fontweight='bold', color=_TEXT_FG)

    return [fig1, fig2]
