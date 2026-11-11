"""
Script: figure_styles.py
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking
Phase 6 – Figure Generation (Shared Styling Module)

This module provides shared matplotlib/seaborn styling constants and helper
functions used by all figure-generation cells in:
  - benchmarks/notebooks/nb05_figures.ipynb
  - benchmarks/notebooks/nb06_results_tables.ipynb

Importing this module at the top of any notebook ensures all plots use
consistent colours, fonts, and layout — critical for a publication-quality paper.

Framework brand colours:
  Qiskit    → #6929C4  (IBM Purple)
  Cirq      → #009D9A  (Google Teal)
  PennyLane → #FF7F50  (Xanadu Orange/Coral)

These colours are chosen to:
  - Match each framework's official brand/logo palette
  - Be distinguishable when printed in greyscale
  - Be accessible for common forms of colour blindness (tested with CVD simulator)

Figure inventory (15 figures total — 14 original + 1 new QPack radar):
  Fig. 1  — QCanvas compilation pipeline architecture diagram
  Fig. 2  — Gate count per algorithm per framework (grouped bar)
  Fig. 3  — Circuit depth per algorithm per framework (grouped bar)
  Fig. 4  — Gate composition breakdown by framework (stacked bar)
  Fig. 5  — Gate count scaling with qubit count (GHZ, Grover's, QRNG)
  Fig. 6  — Compilation time per framework (box plot)
  Fig. 7  — Simulation time per framework (box plot)
  Fig. 8  — Memory usage per algorithm (bar chart)
  Fig. 9  — Pairwise JSD heatmap across all algorithms
  Fig. 10 — Chi-squared p-values heatmap
  Fig. 11 — Quantum Volume estimate per algorithm per framework (grouped bar)
  Fig. 12 — QV vs Circuit Depth scatter plot
  Fig. 13 — Bell State measurement histograms (3 frameworks)
  Fig. 14 — Grover's gate count scaling (2–5 qubits)
  Fig. 15 — QPack-adapted composite scores radar plot (NEW — from QPack §IV-F)
"""

# ──────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
import seaborn as sns
import pandas as pd

# Anchored to this file: benchmarks/scripts/ → up one → benchmarks/
_BENCHMARKS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ──────────────────────────────────────────────────────────
# Framework colour palette
# ──────────────────────────────────────────────────────────

FRAMEWORK_COLORS = {
    'qiskit':    '#6929C4',   # IBM Purple
    'cirq':      '#009D9A',   # Google Teal
    'pennylane': '#FF7F50',   # Xanadu Coral
}

FRAMEWORK_LABELS = {
    'qiskit':    'Qiskit',
    'cirq':      'Cirq',
    'pennylane': 'PennyLane',
}

# Markers for scatter/line plots — distinct shapes for greyscale readability
FRAMEWORK_MARKERS = {
    'qiskit':    'o',   # circle
    'cirq':      's',   # square
    'pennylane': '^',   # triangle
}

FRAMEWORK_ORDER = ['qiskit', 'cirq', 'pennylane']

# QPack radar plot axis keys and display labels (used in Fig. 15)
QPACK_AXES = ['S_compile_speed', 'S_scalability', 'S_accuracy', 'S_capacity']
QPACK_AXES_LABELS = {
    'S_compile_speed': 'Compile\nSpeed',
    'S_scalability':   'Scalability',
    'S_accuracy':      'Accuracy',
    'S_capacity':      'Capacity',
}


# ──────────────────────────────────────────────────────────
# Global matplotlib style settings
# ──────────────────────────────────────────────────────────

def apply_paper_style() -> None:
    """
    Apply publication-quality matplotlib rcParams for IEEE-style papers.

    Call this function at the top of every figure-generating notebook cell
    to guarantee consistent fonts, sizes, and DPI across all 15 figures.

    Settings mirror the IEEE Transactions LaTeX template:
      - Serif font (Computer Modern / Times-equivalent)
      - 11pt base size, 12pt titles
      - No top/right spines (clean axis style)
      - Light dashed grid for readability
      - 300 DPI for crisp rasterisation in PDFs
    """
    plt.rcParams.update({
        # Typography
        'font.family':       'serif',
        'font.size':         11,
        'axes.titlesize':    12,
        'axes.labelsize':    11,
        'xtick.labelsize':   9,
        'ytick.labelsize':   9,
        'legend.fontsize':   9,

        # Figure dimensions and resolution
        'figure.dpi':        300,
        'figure.figsize':    (8, 5),

        # Axis frame — remove top and right spines for a cleaner look
        'axes.spines.top':   False,
        'axes.spines.right': False,

        # Grid — subtle dashed lines, low alpha
        'axes.grid':         True,
        'grid.alpha':        0.3,
        'grid.linestyle':    '--',
        'grid.linewidth':    0.6,

        # Layout
        'axes.titlepad':     8,
        'axes.labelpad':     6,
    })


# ──────────────────────────────────────────────────────────
# Figure saving utility
# ──────────────────────────────────────────────────────────

def save_figure(fig: plt.Figure, name: str, results_subdir: str = 'structural') -> None:
    """
    Save a matplotlib figure to two formats for paper-ready output.

    Saves to:
    benchmarks/results/<results_subdir>/<name>.pdf   — for LaTeX \\includegraphics
      benchmarks/results/<results_subdir>/<name>.png   — for quick visual review

    Args:
        fig:            The matplotlib Figure object to save.
        name:           Base filename without extension (e.g. 'fig02_gate_counts').
        results_subdir: Subfolder inside benchmarks/results/ ('structural',
                        'simulation', 'scaling', or root '').
    """
    base_dir = os.path.join(_BENCHMARKS_DIR, 'results', results_subdir)
    os.makedirs(base_dir, exist_ok=True)

    for ext in ('pdf', 'png'):
        path = os.path.join(base_dir, f'{name}.{ext}')
        fig.savefig(path, bbox_inches='tight', dpi=300)

    print(f"[save_figure] Saved: {name}.pdf / .png → {base_dir}/")


# ──────────────────────────────────────────────────────────
# Reusable plotting helpers (Figs. 2, 3, 5, 11, 14)
# ──────────────────────────────────────────────────────────

def plot_grouped_bar(
    ax: plt.Axes,
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    group_col: str = 'framework',
    title: str = '',
    ylabel: str = '',
    error_col: str = None,
) -> None:
    """
    Draw a grouped bar chart with one cluster per x value and one bar per framework.

    Used for:
      Fig. 2  — Gate count per algorithm per framework
      Fig. 3  — Circuit depth per algorithm per framework
      Fig. 11 — Quantum Volume estimate per algorithm per framework

    Args:
        ax:        Matplotlib Axes to draw on.
        df:        DataFrame with at minimum columns [x_col, y_col, group_col].
        x_col:     Column name for the x-axis categories (e.g. 'algorithm').
        y_col:     Column name for the bar heights (e.g. 'total_gates').
        group_col: Column name for the grouping variable (default 'framework').
        title:     Axes title string.
        ylabel:    Y-axis label string.
        error_col: Optional column name for error bar half-widths (std dev).
    """
    apply_paper_style()

    x_values  = df[x_col].unique()
    groups    = FRAMEWORK_ORDER if group_col == 'framework' else df[group_col].unique()
    n_groups  = len(groups)
    n_x       = len(x_values)

    bar_width = 0.8 / n_groups
    x_indices = np.arange(n_x)

    for idx, fw in enumerate(groups):
        subset = df[df[group_col] == fw]
        # Ensure unique indices for lookup by averaging duplicates if any exist
        # This prevents "ValueError: setting an array element with a sequence"
        subset = subset.groupby(x_col).mean(numeric_only=True)
        
        heights = [subset[y_col].get(x, 0) for x in x_values]
        errors  = [subset[error_col].get(x, 0) for x in x_values] if error_col and error_col in subset.columns else None
        offset  = (idx - n_groups / 2 + 0.5) * bar_width

        label = FRAMEWORK_LABELS.get(fw, fw)
        color = FRAMEWORK_COLORS.get(fw, '#888888')

        ax.bar(
            x_indices + offset, heights,
            width=bar_width,
            label=label,
            color=color,
            alpha=0.88,
            yerr=errors,
            error_kw={'elinewidth': 1.0, 'capsize': 3},
            edgecolor='white',
            linewidth=0.5,
        )

    ax.set_xticks(x_indices)
    ax.set_xticklabels(
        [str(v).replace('_', ' ').title() for v in x_values],
        rotation=35, ha='right',
    )
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(framealpha=0.7, edgecolor='lightgrey')


def plot_scaling_lines(
    ax: plt.Axes,
    df: pd.DataFrame,
    x_col: str = 'n_qubits',
    y_col: str = 'total_gates',
    framework_col: str = 'framework',
    std_col: str = None,
    title: str = '',
    ylabel: str = '',
) -> None:
    """
    Draw a multi-line scaling plot with one line per framework.

    Optionally adds a 95% confidence interval shading when std_col is provided.

    Used for:
      Fig. 5  — Gate count scaling with qubit count (GHZ, Grover's, QRNG)
      Fig. 14 — Grover's gate count scaling (2–5 qubits)

    Args:
        ax:           Matplotlib Axes to draw on.
        df:           DataFrame with columns [x_col, y_col, framework_col].
        x_col:        X-axis column (default 'n_qubits').
        y_col:        Y-axis column (default 'total_gates').
        framework_col Column identifying the framework.
        std_col:      Optional column for standard deviation (shaded CI band).
        title:        Axes title string.
        ylabel:       Y-axis label string.
    """
    apply_paper_style()

    line_styles = {
        'qiskit': '-',
        'cirq': '--',
        'pennylane': '-',
    }
    z_orders = {
        'pennylane': 2,
        'cirq': 3,
        'qiskit': 4,
    }
    jitter_map = {
        'qiskit': -0.04,
        'cirq': 0.04,
        'pennylane': 0.0,
    }

    overlap_points = {
        (row[x_col], row[y_col])
        for _, row in df.groupby([x_col, y_col]).size().reset_index(name='count').iterrows()
        if row['count'] > 1
    }

    for fw in FRAMEWORK_ORDER:
        subset = df[df[framework_col] == fw].sort_values(x_col)
        if subset.empty:
            continue

        xs  = subset[x_col].values
        ys  = subset[y_col].values
        color  = FRAMEWORK_COLORS[fw]
        marker = FRAMEWORK_MARKERS[fw]

        xs_plot = xs.astype(float).copy()
        if overlap_points:
            for idx, (xv, yv) in enumerate(zip(xs, ys)):
                if (xv, yv) in overlap_points:
                    xs_plot[idx] += jitter_map.get(fw, 0.0)

        marker_face = 'none' if fw == 'qiskit' else 'white'
        marker_size = 8 if fw == 'qiskit' else 7

        ax.plot(
            xs_plot,
            ys,
            color=color,
            marker=marker,
            linewidth=2.0,
            linestyle=line_styles.get(fw, '-'),
            markersize=marker_size,
            markerfacecolor=marker_face,
            markeredgewidth=1.6,
            alpha=0.95,
            zorder=z_orders.get(fw, 3),
            label=FRAMEWORK_LABELS[fw],
        )

        if std_col and std_col in subset.columns:
            stds = subset[std_col].values
            ax.fill_between(xs, ys - 1.96 * stds, ys + 1.96 * stds,
                            color=color, alpha=0.15)

    ax.set_xlabel(x_col.replace('_', ' ').title())
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend(framealpha=0.7, edgecolor='lightgrey')
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))


def plot_jsd_heatmap(ax: plt.Axes, jsd_df: pd.DataFrame, title: str = '') -> None:
    """
    Draw a heatmap of pairwise Jensen–Shannon Divergence values across algorithms.

    Colour scale: green (low JSD ≈ 0) → red (high JSD ≈ 0.1+),
    centred at the 0.05 divergence threshold used in the paper.

    The heatmap uses annotations showing the raw JSD value formatted to 3 d.p.
    Cells at or below 0.01 are labelled '✓' — statistically equivalent.

    Used for Fig. 9.

    Args:
        ax:     Matplotlib Axes to draw on.
        jsd_df: DataFrame indexed by algorithm, columns are framework pairs
                (e.g. 'qiskit_vs_cirq', 'qiskit_vs_pennylane', 'cirq_vs_pennylane').
        title:  Axes title string.
    """
    apply_paper_style()

    cmap = sns.diverging_palette(145, 10, as_cmap=True)  # green → red

    sns.heatmap(
        jsd_df,
        ax=ax,
        cmap=cmap,
        vmin=0.0,
        vmax=0.10,
        center=0.05,
        annot=True,
        fmt='.3f',
        linewidths=0.5,
        linecolor='white',
        cbar_kws={'label': 'JSD (√ form)', 'shrink': 0.8},
    )

    ax.set_title(title)
    ax.tick_params(axis='x', rotation=30)
    ax.tick_params(axis='y', rotation=0)


def plot_measurement_histogram(
    ax: plt.Axes,
    distributions: dict,
    algorithm_name: str,
    n_qubits: int,
) -> None:
    """
    Draw side-by-side probability histograms for a single algorithm across all
    three frameworks.

    Counts are normalised to probabilities for a fair cross-framework comparison.
    Bar clusters are one group per bitstring state, one bar per framework.

    Used for Fig. 13 (Bell State histograms).

    Args:
        ax:              Matplotlib Axes to draw on.
        distributions:   Dict mapping framework → {bitstring: count}.
                         E.g. {'qiskit': {'00': 510, '11': 514}, 'cirq': {...}, ...}
        algorithm_name:  Human-readable algorithm name for the title.
        n_qubits:        Number of qubits (used to determine expected states).
    """
    apply_paper_style()

    # Collect the union of all bitstrings across frameworks
    all_states = sorted(
        set().union(*[set(d.keys()) for d in distributions.values()])
    )

    n_states  = len(all_states)
    n_fw      = len(FRAMEWORK_ORDER)
    bar_width = 0.8 / n_fw
    x_indices = np.arange(n_states)

    for idx, fw in enumerate(FRAMEWORK_ORDER):
        counts = distributions.get(fw, {})
        total  = sum(counts.values()) or 1
        probs  = [counts.get(s, 0) / total for s in all_states]
        offset = (idx - n_fw / 2 + 0.5) * bar_width

        ax.bar(
            x_indices + offset, probs,
            width=bar_width,
            label=FRAMEWORK_LABELS[fw],
            color=FRAMEWORK_COLORS[fw],
            alpha=0.88,
            edgecolor='white',
            linewidth=0.5,
        )

    ax.set_xticks(x_indices)
    ax.set_xticklabels([f"|{s}⟩" for s in all_states], rotation=0)
    ax.set_xlabel('Basis State')
    ax.set_ylabel('Probability')
    ax.set_title(f'{algorithm_name} ({n_qubits} qubits) — Measurement Distribution')
    ax.legend(framealpha=0.7, edgecolor='lightgrey')
    ax.set_ylim(0, 1.05)


# ──────────────────────────────────────────────────────────
# QPack Radar Plot (Fig. 15 — NEW, from QPack §IV-F)
# ──────────────────────────────────────────────────────────

def plot_radar(
    ax: plt.Axes,
    scores_dict: dict,
    framework_order: list = None,
) -> None:
    """
    Draw a spider/radar chart of the four QPack-adapted composite sub-scores,
    one filled polygon per framework — directly inspired by QPack Fig. 5
    (Donkers et al., arXiv:2205.12142v1).

    The four axes are:
      S_compile_speed  — log10(mean gates compiled per second)
      S_scalability    — arctan-mapped power-law exponent (smaller exponent = higher score)
      S_accuracy       — arctan-mapped mean relative error vs. theoretical ideal
      S_capacity       — maximum qubit count where JSD < 0.05 threshold

    The enclosed area of each polygon equals ½ × (S_speed + S_scale) ×
    (S_acc + S_cap) — i.e. the S_overall composite score (QPack §IV-F).

    QPack published reference values:
      QuEST Simulator  → S_overall ≈ 183.2  (highest in QPack paper)
      Cirq Simulator   → S_overall ≈ 157.6
      Qiskit Aer       → S_overall ≈ 147.2
      Rigetti QVM      → S_overall ≈ 104.8

    Our noiseless QSim baseline should produce values in the QuEST/Cirq range,
    providing external calibration of the scoring pipeline.

    Args:
        ax:              A polar Axes object (must be created with
                         subplot_kw={'projection': 'polar'}).
        scores_dict:     Dict mapping framework → sub-score dict, e.g.:
                           {
                             'qiskit':    {'S_compile_speed': 4.2, 'S_scalability': 7.1,
                                           'S_accuracy': 8.3, 'S_capacity': 6},
                             'cirq':      {...},
                             'pennylane': {...},
                           }
        framework_order: Optional list controlling the plotting order.
                         Defaults to FRAMEWORK_ORDER.
    """
    apply_paper_style()

    if framework_order is None:
        framework_order = FRAMEWORK_ORDER

    axes_keys   = QPACK_AXES                  # ['S_compile_speed', 'S_scalability', ...]
    n_axes      = len(axes_keys)
    ax_labels   = [QPACK_AXES_LABELS[k] for k in axes_keys]

    # Evenly-spaced angles around the circle; close by repeating first element
    angles = np.linspace(0, 2 * np.pi, n_axes, endpoint=False).tolist()
    angles += angles[:1]

    line_styles = {'qiskit': '-', 'cirq': '--', 'pennylane': '-'}
    z_orders = {'qiskit': 3, 'pennylane': 4, 'cirq': 5}

    for fw in framework_order:
        if fw not in scores_dict:
            continue

        scores = scores_dict[fw]
        values = [scores.get(k, 0) for k in axes_keys]
        values += values[:1]   # close the polygon

        color = FRAMEWORK_COLORS.get(fw, '#888888')
        label = FRAMEWORK_LABELS.get(fw, fw)

        marker = FRAMEWORK_MARKERS.get(fw, 'o')
        ax.plot(
            angles, values,
            color=color,
            linewidth=2.2,
            linestyle=line_styles.get(fw, '-'),
            marker=marker,
            markersize=6,
            markerfacecolor='none' if fw == 'qiskit' else color,
            markeredgewidth=2.0,
            label=label,
            zorder=z_orders.get(fw, 3),
        )
        ax.fill(angles, values, color=color, alpha=0.12)

    # Place axis labels at the spoke angles
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(ax_labels, size=9)

    # Remove default radial tick labels for a cleaner look;
    # add a subtle grid at even multiples
    ax.yaxis.set_tick_params(labelsize=7)
    ax.grid(color='grey', linestyle='--', linewidth=0.5, alpha=0.4)

    ax.set_title('QPack-Adapted Composite Scores\n(QCanvas Framework Comparison)',
                 pad=14, fontsize=12)
    ax.legend(
        loc='upper right',
        bbox_to_anchor=(1.35, 1.15),
        framealpha=0.8,
        edgecolor='lightgrey',
    )


# ──────────────────────────────────────────────────────────
# Legend patch helper
# ──────────────────────────────────────────────────────────

def framework_legend_patches() -> list:
    """
    Return a list of mpatches.Patch objects for a manual framework legend.

    Useful when a figure combines multiple subplots that share the same
    framework colour encoding and a single legend is preferred at the
    figure level.

    Returns:
        List of three Patch objects [Qiskit, Cirq, PennyLane].
    """
    return [
        mpatches.Patch(color=FRAMEWORK_COLORS[fw], label=FRAMEWORK_LABELS[fw])
        for fw in FRAMEWORK_ORDER
    ]
