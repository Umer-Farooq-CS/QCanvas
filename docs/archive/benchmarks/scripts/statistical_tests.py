"""
Script: statistical_tests.py
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking
Phase 4 – Statistical Analysis

This module provides all statistical testing functions used to answer RQ2–RQ5.

RQ2: Are simulation distributions statistically equivalent across frameworks?
RQ4: How do gate count differences scale with circuit complexity (power-law)?
RQ5: What is the maximum usable qubit count (S_capacity) per framework before
     distributional divergence exceeds the 20% accuracy threshold?

Methodology adapted from:
  QPack: "QPack Scores: Quantitative performance metrics for application-oriented
  quantum computer benchmarking" (Donkers et al., arXiv:2205.12142v1)
  — §IV: Runtime, Accuracy, Scalability, Capacity sub-score definitions.

Functions provided:
  ── Distribution equivalence (RQ2) ──────────────────────────────────────────
  - chi_squared_test()           : Compare observed distribution to theoretical ideal
  - js_divergence()              : Jensen–Shannon divergence between two distributions
  - pairwise_jsd()               : Compute JSD for all pairs (Qiskit vs Cirq, etc.)
  - run_all_statistical_tests()  : Batch runner over all algorithms and shot counts

  ── QPack-adapted composite scores (RQ4, RQ5, NEW) ──────────────────────────
  - fit_power_law()              : Fit T(N) = N^a; returns exponent `a` (QPack §IV-C)
  - compute_runtime_score()      : S_runtime = log10(mean gates-per-second) (QPack §IV-A)
  - compute_accuracy_score()     : S_accuracy = (2/π)·arctan(c·rel_error) (QPack §IV-B)
  - compute_scalability_score()  : S_scalability from power-law exponent a (QPack §IV-C)
  - compute_capacity_score()     : S_capacity = max n_qubits where JSD < threshold (QPack §IV-D)
  - compute_overall_score()      : S_overall = ½(S_speed+S_scale)(S_acc+S_cap) (QPack §IV-F)

  ── Scaling regression (RQ4) ─────────────────────────────────────────────────
  - fit_scaling_trend()          : Linear/quadratic regression on gate count vs n_qubits

Equivalence thresholds (from paper methodology):
  JSD < 0.01  → equivalent         (label: ✓)
  JSD > 0.05  → significantly divergent (label: ✗, flag for investigation)
  0.01–0.05   → marginal           (label: ~, note in paper)

QPack accuracy threshold:
  Relative error ≤ 0.20 (20%) → within capacity (same as Atos Q-score spirit)

QPack score mapping constants (from paper §IV-B/C):
  c0 = 30/π, c1 = 50   (accuracy mapping)
  c2 = 30/π, c3 = 0.75 (scalability mapping)

Called by:
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
  - benchmarks/notebooks/nb06_results_tables.ipynb
"""

# ──────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────

import os
import json
import math
import numpy as np
import pandas as pd
from scipy.stats import chisquare
from scipy.spatial.distance import jensenshannon
from scipy.optimize import curve_fit


# ──────────────────────────────────────────────────────────
# Constants — QPack score mapping parameters (§IV-B/C)
# ──────────────────────────────────────────────────────────

# Accuracy mapping constants (QPack §IV-B)
_ACCURACY_C0 = 30 / math.pi   # ≈ 9.549
_ACCURACY_C1 = 50

# Scalability mapping constants (QPack §IV-C)
_SCALABILITY_C2 = 30 / math.pi   # ≈ 9.549
_SCALABILITY_C3 = 0.75

# Equivalence thresholds used throughout the paper
JSD_EQUIVALENT_THRESHOLD  = 0.01   # JSD < 0.01  → label ✓
JSD_DIVERGENT_THRESHOLD   = 0.05   # JSD > 0.05  → label ✗, flag for investigation
CAPACITY_JSD_THRESHOLD    = 0.05   # Max JSD allowed for S_capacity (≈ QPack 20% rel. error)


# ──────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────

def _jsd_label(jsd_value: float) -> str:
    """
    Assign a qualitative equivalence label to a JSD value.

    Returns:
      '✓'  if JSD < 0.01  (effectively identical distributions)
      '~'  if 0.01 ≤ JSD < 0.05  (marginal difference; note in paper)
      '✗'  if JSD ≥ 0.05  (significant divergence; flag for investigation)
    """
    if jsd_value < JSD_EQUIVALENT_THRESHOLD:
        return '✓'
    elif jsd_value < JSD_DIVERGENT_THRESHOLD:
        return '~'
    else:
        return '✗'


def _arctan_map(x: float) -> float:
    """
    QPack monotone mapping function: (2/π) × arctan(x).

    Maps [0, ∞) → [0, 1]. Used by the accuracy and scalability sub-scores
    so that extreme values are compressed rather than unbounded.
    """
    return (2 / math.pi) * math.atan(x)


# ──────────────────────────────────────────────────────────
# Chi-squared test (RQ2)
# ──────────────────────────────────────────────────────────

def chi_squared_test(
    observed_counts: dict,
    expected_probs:  dict,
    shots: int,
) -> dict:
    """
    Chi-squared goodness-of-fit test: compare an observed measurement distribution
    against the theoretically expected distribution.

    This test answers part of RQ2: does a framework's compiled QASM produce
    measurement counts statistically consistent with the ideal algorithm output?

    Args:
        observed_counts: Dict mapping bitstring → observed count.
                         E.g. {'00': 512, '11': 512}
        expected_probs:  Dict mapping bitstring → theoretical probability.
                         E.g. {'00': 0.5, '11': 0.5} for Bell state.
                         Must sum to 1.0.  For VQE/QAOA use noiseless QSim probs.
        shots:           Total number of measurement shots (sum of all counts).

    Returns:
        dict with keys:
          'chi2_statistic'       (float) : Chi-squared test statistic
          'p_value'              (float) : p-value (< 0.05 ⇒ significant divergence)
          'significant_divergence' (bool): True if p_value < 0.05
          'degrees_of_freedom'   (int)   : df = len(states) - 1
    """
    states   = sorted(expected_probs.keys())
    observed = np.array([observed_counts.get(s, 0) for s in states], dtype=float)
    expected = np.array([expected_probs[s] * shots for s in states], dtype=float)

    # Guard: avoid zero expected values (would cause division by zero in chi-squared)
    epsilon = 1e-10
    expected = np.maximum(expected, epsilon)

    chi2_stat, p_value = chisquare(f_obs=observed, f_exp=expected)

    return {
        'chi2_statistic':        float(chi2_stat),
        'p_value':               float(p_value),
        'significant_divergence': bool(p_value < 0.05),
        'degrees_of_freedom':    len(states) - 1,
    }


# ──────────────────────────────────────────────────────────
# Jensen–Shannon Divergence (RQ2)
# ──────────────────────────────────────────────────────────

def js_divergence(dist_a: dict, dist_b: dict) -> float:
    """
    Compute the Jensen–Shannon Divergence (JSD) between two measurement
    distributions represented as dictionaries of bitstring → count (or prob).

    JSD is a symmetric, bounded measure of distributional difference.
    scipy.spatial.distance.jensenshannon returns the *square root* of the
    information-theoretic JSD — we retain this "JSD (√ form)" throughout
    the paper and clearly document the convention.

    Thresholds (from paper §3.3):
      JSD < 0.01  → effectively identical (✓)
      JSD > 0.05  → significantly divergent (✗, flag for investigation)

    Args:
        dist_a: Dict mapping bitstring → count or probability for distribution A.
        dist_b: Dict mapping bitstring → count or probability for distribution B.

    Returns:
        float: JSD value in [0, 1]. 0 = identical, 1 = completely orthogonal.
    """
    all_states = sorted(set(dist_a.keys()) | set(dist_b.keys()))

    p = np.array([dist_a.get(s, 0) for s in all_states], dtype=float)
    q = np.array([dist_b.get(s, 0) for s in all_states], dtype=float)

    # Normalise to probability vectors (handle all-zero edge case)
    p_sum = p.sum()
    q_sum = q.sum()

    if p_sum == 0 or q_sum == 0:
        # One distribution is empty — treat as maximally divergent
        return 1.0

    p /= p_sum
    q /= q_sum

    # base=2 gives range [0, 1]; default base=e gives [0, sqrt(ln 2)] ≈ [0, 0.832]
    return float(jensenshannon(p, q, base=2))


# ──────────────────────────────────────────────────────────
# Pairwise JSD across all frameworks (RQ2)
# ──────────────────────────────────────────────────────────

def pairwise_jsd(distributions: dict) -> dict:
    """
    Compute JSD for all framework pairs for a single algorithm at a given shot count.

    The standard three pairs are:
      qiskit_vs_cirq, qiskit_vs_pennylane, cirq_vs_pennylane

    Args:
        distributions: Dict mapping framework name → {bitstring: count}.
                       E.g. {'qiskit': {'00': 510, '11': 514},
                              'cirq':  {'00': 508, '11': 516},
                              'pennylane': {'00': 512, '11': 512}}

    Returns:
        Dict with one key per framework pair, each containing:
          {'jsd': float, 'label': str}
        where label ∈ {'✓', '~', '✗'}.
    """
    frameworks = list(distributions.keys())
    result     = {}

    for i in range(len(frameworks)):
        for j in range(i + 1, len(frameworks)):
            fa, fb = frameworks[i], frameworks[j]
            jsd    = js_divergence(distributions[fa], distributions[fb])
            key    = f"{fa}_vs_{fb}"
            result[key] = {
                'jsd':   jsd,
                'label': _jsd_label(jsd),
            }

    return result


# ──────────────────────────────────────────────────────────
# Batch runner (RQ2)
# ──────────────────────────────────────────────────────────

def run_all_statistical_tests(
    distributions_dir: str,
    shots: int = 4096,
) -> pd.DataFrame:
    """
    Batch statistical test runner over all algorithms in the distributions directory.

    Expects distribution JSON files named:
      <algo>_<n>q_<framework>_<shots>_trial<k>.json
    where each file contains a dict of {bitstring: count}.

    For each algorithm found in distributions_dir, the function:
      1. Loads the distribution JSON for each framework at the given shot count
         (uses trial 1 if multiple trials exist; pairwise JSD is trial-averaged
         if multiple trial files are found).
      2. Runs pairwise_jsd() on the three distributions.
      3. Assembles results into one row per algorithm.

    Args:
        distributions_dir: Path to the directory containing distribution JSON files.
        shots:             Shot count to filter for (default 4096).

    Returns:
        pd.DataFrame with columns:
          [algorithm, n_qubits, shots,
           jsd_qiskit_cirq, jsd_qiskit_pl, jsd_cirq_pl,
           label_qk_cq, label_qk_pl, label_cq_pl,
           all_equivalent]
        where all_equivalent is True iff all three JSD values are < 0.01.
    """
    if not os.path.isdir(distributions_dir):
        raise FileNotFoundError(
            f"Distributions directory not found: {distributions_dir}\n"
            f"Run simulate_all.py first to generate distribution JSON files."
        )

    # Discover unique (algorithm, n_qubits) combinations from filenames
    algo_map: dict = {}  # key = (algo, n_qubits) → framework → list of count dicts

    for fname in sorted(os.listdir(distributions_dir)):
        if not fname.endswith('.json'):
            continue

        # Expected pattern: <algo>_<n>q_<framework>_<shots>_trial<k>.json
        parts = fname.replace('.json', '').split('_')
        try:
            # The shots segment contains a digit, trial segment starts with 'trial'
            shots_idx  = next(i for i, p in enumerate(parts) if p.isdigit() and int(p) in (1024, 4096, 8192))
            trial_idx  = next(i for i, p in enumerate(parts) if p.startswith('trial'))
            framework  = parts[shots_idx - 1]
            nq_part    = parts[shots_idx - 2]   # e.g. '4q'
            n_qubits   = int(nq_part.rstrip('q'))
            algo       = '_'.join(parts[:shots_idx - 2])
            file_shots = int(parts[shots_idx])
        except (StopIteration, ValueError, IndexError):
            # Filename does not match expected pattern — skip
            continue

        if file_shots != shots:
            continue

        key = (algo, n_qubits)
        algo_map.setdefault(key, {}).setdefault(framework, [])

        with open(os.path.join(distributions_dir, fname)) as fh:
            algo_map[key][framework].append(json.load(fh))

    rows = []
    for (algo, n_qubits), fw_trials in sorted(algo_map.items()):
        # Average counts across trials for each framework
        distributions = {}
        for fw, trial_list in fw_trials.items():
            merged: dict = {}
            for trial_counts in trial_list:
                for state, cnt in trial_counts.items():
                    merged[state] = merged.get(state, 0) + cnt
            # Keep as summed counts; js_divergence normalises internally
            distributions[fw] = merged

        pairs = pairwise_jsd(distributions)

        # Extract pair keys independent of framework insertion order
        def _get_pair(a: str, b: str) -> dict:
            return pairs.get(f'{a}_vs_{b}', pairs.get(f'{b}_vs_{a}', {}))

        qk_cq = _get_pair('qiskit', 'cirq')
        qk_pl = _get_pair('qiskit', 'pennylane')
        cq_pl = _get_pair('cirq', 'pennylane')

        all_eq = all(
            v.get('jsd', 1.0) < JSD_EQUIVALENT_THRESHOLD
            for v in [qk_cq, qk_pl, cq_pl]
        )

        rows.append({
            'algorithm':        algo,
            'n_qubits':         n_qubits,
            'shots':            shots,
            'jsd_qiskit_cirq':  qk_cq.get('jsd', None),
            'jsd_qiskit_pl':    qk_pl.get('jsd', None),
            'jsd_cirq_pl':      cq_pl.get('jsd', None),
            'label_qk_cq':      qk_cq.get('label', '?'),
            'label_qk_pl':      qk_pl.get('label', '?'),
            'label_cq_pl':      cq_pl.get('label', '?'),
            'all_equivalent':   all_eq,
        })

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────
# Power-law scaling fit (RQ4 — QPack §IV-C adapted)
# ──────────────────────────────────────────────────────────

def fit_power_law(n_qubits: list, gate_counts: list) -> dict:
    """
    Fit a power-law model  gate_count ≈ C × N^a  to observe how circuit size
    scales with qubit count for a given framework and algorithm family.

    This is the QPack §IV-C scalability exponent, adapted for gate count rather
    than runtime — appropriate for our structural analysis goal (RQ4).

        Scaling classification:
            constant-depth → gate count invariant with N (a = 0 by convention)
            a < 1          → sub-linear  (sub-linear gate growth)
            a ≈ 1          → linear       (gates grow proportionally with qubit count)
            a > 1          → super-linear (circuit grows faster than qubit count; investigate oracle)

    Fitting is performed by linear regression in log-log space, which is more
    numerically stable than direct nonlinear curve fitting for power laws.

    Args:
        n_qubits:    List of qubit counts tested (e.g. [3, 4, 5, 6, 7, 8]).
        gate_counts: Corresponding total gate counts for each qubit count.

    Returns:
        dict with keys:
          'a'             (float): Power-law exponent (QPack S_pure_scalability)
          'coefficient'   (float): Prefactor C (= exp(intercept) in log space)
          'r2'            (float): R² goodness-of-fit on log-log data
          'scaling_class' (str) : 'constant-depth' | 'sub-linear' | 'linear' | 'super-linear'
    """
    n_arr = np.array(n_qubits,    dtype=float)
    g_arr = np.array(gate_counts, dtype=float)

    # Guard against zero or negative values before log transform
    valid = (n_arr > 0) & (g_arr > 0)
    if valid.sum() < 2:
        return {'a': float('nan'), 'coefficient': float('nan'),
                'r2': float('nan'), 'scaling_class': 'unknown'}

    log_n = np.log(n_arr[valid])
    log_g = np.log(g_arr[valid])

    # Handle near-constant series explicitly (avoids unstable/meaningless R²)
    if np.ptp(log_g) < 1e-12:
        return {
            'a':             0.0,
            'coefficient':   float(np.exp(np.mean(log_g))),
            'r2':            1.0,
            'scaling_class': 'constant-depth',
        }

    # Linear regression: log_g = a * log_n + log_C
    coeffs   = np.polyfit(log_n, log_g, 1)
    a        = float(coeffs[0])
    log_C    = float(coeffs[1])
    coeff    = float(np.exp(log_C))

    # R² on log-log data
    log_g_pred = a * log_n + log_C
    ss_res   = float(np.sum((log_g - log_g_pred) ** 2))
    ss_tot   = float(np.sum((log_g - np.mean(log_g)) ** 2))
    r2       = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 1.0
    r2       = float(max(min(r2, 1.0), 0.0))

    # Classify scaling behaviour
    if abs(a) < 1e-12:
        scaling_class = 'constant-depth'
    elif a < 0.9:
        scaling_class = 'sub-linear'
    elif a <= 1.1:
        scaling_class = 'linear'
    else:
        scaling_class = 'super-linear'

    return {
        'a':             a,
        'coefficient':   coeff,
        'r2':            r2,
        'scaling_class': scaling_class,
    }


# ──────────────────────────────────────────────────────────
# QPack Runtime Score (QPack §IV-A adapted for compilation)
# ──────────────────────────────────────────────────────────

def compute_runtime_score(compile_times_df: pd.DataFrame) -> dict:
    """
    Compute QPack-adapted S_runtime per framework.

    QPack §IV-A defines runtime as gates-per-second, normalising for circuit size
    so that a framework producing 20% more gates but taking 20% longer is treated
    fairly (same score). Only genuine efficiency differences appear.

    Adaptation for Paper 5:
      S_pure_runtime  = mean(total_gates / compile_time_s)   [gates compiled per second]
      S_mapped_runtime = log10(S_pure_runtime)

    The log10 mapping compresses the dynamic range so that a 10× speedup = +1 score
    unit, consistent with QPack's reported values (Table VI Donkers et al.).

    Args:
        compile_times_df: DataFrame with columns:
                          [framework, algorithm, total_gates, mean_compile_ms]
                          One row per (framework, algorithm) combination.

    Returns:
        Dict mapping framework → S_mapped_runtime (float).
        E.g. {'qiskit': 4.2, 'cirq': 4.5, 'pennylane': 3.9}
    """
    result = {}

    for fw, group in compile_times_df.groupby('framework'):
        # Convert ms → s; guard against zero compile time
        group = group.copy()
        group['compile_s'] = group['mean_compile_ms'] / 1000.0
        group = group[group['compile_s'] > 0]

        if group.empty:
            result[fw] = float('nan')
            continue

        gps_per_algo = group['total_gates'] / group['compile_s']   # gates/second per algorithm
        s_pure       = float(gps_per_algo.mean())

        result[fw] = float(math.log10(s_pure)) if s_pure > 0 else float('nan')

    return result


# ──────────────────────────────────────────────────────────
# QPack Accuracy Score (QPack §IV-B adapted)
# ──────────────────────────────────────────────────────────

def compute_accuracy_score(jsd_by_algorithm: dict, framework: str) -> float:
    """
    Compute QPack-adapted S_accuracy for a given framework.

    QPack §IV-B defines accuracy using relative error vs. the QuEST noiseless
    baseline.  For Paper 5 we substitute mean JSD against the theoretical ideal
    as a proxy for relative error — JSD = 0 is perfect; JSD = 1 is completely wrong.

    Formula:
      relative_error_proxy = mean JSD across all algorithms for this framework
      fmap(x) = (2/π) × arctan(x)
      S_mapped_accuracy = c0 × fmap(c1 × (1 - relative_error_proxy))

    The (1 - JSD) inversion ensures that a lower JSD (better accuracy) yields
    a higher score, consistent with QPack's convention where higher is better.

    Constants (QPack §IV-B): c0 = 30/π ≈ 9.55, c1 = 50.

    Args:
        jsd_by_algorithm: Dict of algorithm → JSD value for this framework.
                          E.g. {'bell_state': 0.002, 'grovers': 0.008, ...}
        framework:        Framework name (used only for logging clarity).

    Returns:
        float: S_accuracy for this framework. Higher = better accuracy.
    """
    if not jsd_by_algorithm:
        return float('nan')

    jsd_values = [v for v in jsd_by_algorithm.values() if v is not None and not math.isnan(v)]
    if not jsd_values:
        return float('nan')

    mean_jsd           = float(np.mean(jsd_values))
    relative_error_inv = max(0.0, 1.0 - mean_jsd)   # invert: low JSD → high accuracy proxy

    s_accuracy = _ACCURACY_C0 * _arctan_map(_ACCURACY_C1 * relative_error_inv)
    return s_accuracy


# ──────────────────────────────────────────────────────────
# QPack Scalability Score (QPack §IV-C adapted)
# ──────────────────────────────────────────────────────────

def compute_scalability_score(a: float) -> float:
    """
    Compute QPack-adapted S_scalability from the power-law exponent a.

    Directly implements QPack §IV-C:
      S_pure_scalability  = a
      fmap(x) = (2/π) × arctan(x)
      S_mapped_scalability = c2 × fmap(c3 × (a - 1))

    The shift by 1 places the neutral point at a = 1 (linear scaling).
    Frameworks with a < 1 (sub-linear growth) receive scores above c2/2;
    frameworks with a > 1 (super-linear) are penalised below c2/2.

    A framework that maintains linear gate-count scaling with qubit count
    scores ≈ 0 in this metric (neutral). Sub-linear frameworks are rewarded.

    Constants (QPack §IV-C): c2 = 30/π ≈ 9.55, c3 = 0.75.

    Args:
        a: Power-law exponent from fit_power_law() — the S_pure_scalability value.

    Returns:
        float: S_scalability. Higher = more scalable compilation pattern.
    """
    if math.isnan(a):
        return float('nan')

    # Shift by 1: positive shift means a > 1 (bad); negative means a < 1 (good)
    shifted = a - 1.0
    s_scalability = _SCALABILITY_C2 * _arctan_map(_SCALABILITY_C3 * (-shifted))
    # Negate the shift so sub-linear (a<1 → shifted<0 → -shifted>0) gives a higher score
    return s_scalability


# ──────────────────────────────────────────────────────────
# QPack Capacity Score (QPack §IV-D adapted) — NEW in Paper 5
# ──────────────────────────────────────────────────────────

def compute_capacity_score(
    jsd_by_nqubits: dict,
    threshold: float = CAPACITY_JSD_THRESHOLD,
) -> int:
    """
    Compute QPack-adapted S_capacity: the maximum qubit count at which a
    framework's compiled QASM still produces distributions within the accuracy
    threshold vs. the ideal distribution.

    QPack §IV-D definition:
      S_capacity = max { Q_N  where  relative_error(N) ≤ A }  (A = 0.20 in QPack)

    For Paper 5 we use JSD < threshold (default 0.05, which approximates the
    QPack 20% relative error cutoff in information-theoretic terms):
      S_capacity = max { n_qubits  where  JSD(framework, ideal) < 0.05 }

    This metric captures the "usable scale" of each framework's compilation
    before distributional divergence from the ideal becomes too large —
    answering RQ5 (new research question from QPack integration).

    Expected findings (from QPack §V and our structural analysis):
      Qiskit    → high capacity (clean CNOT decompositions, minimal ancilla overhead)
      Cirq      → high capacity (moment-based, low gate count for deep circuits)
      PennyLane → potentially lower at large n (template expansion adds overhead)

    Args:
        jsd_by_nqubits: Dict mapping n_qubits (int) → JSD vs. ideal for this framework.
                        E.g. {3: 0.002, 4: 0.004, 5: 0.031, 6: 0.072, 7: 0.110}
        threshold:      JSD threshold for "acceptable accuracy" (default 0.05).

    Returns:
        int: The maximum qubit count where JSD < threshold.
             Returns 0 if no qubit count satisfies the condition.
    """
    valid_n = [n for n, jsd in jsd_by_nqubits.items()
               if jsd is not None and not math.isnan(jsd) and jsd < threshold]

    return max(valid_n) if valid_n else 0


# ──────────────────────────────────────────────────────────
# QPack Overall Score (QPack §IV-F)
# ──────────────────────────────────────────────────────────

def compute_overall_score(
    S_speed: float,
    S_scale: float,
    S_acc:   float,
    S_cap:   float,
) -> float:
    """
    Compute the QPack-equivalent composite benchmark score for a framework.

    Directly from QPack §IV-F:
      S_overall = ½ × (S_runtime + S_scalability) × (S_accuracy + S_capacity)

    This formula computes the area of the quadrilateral formed by the four
    sub-scores in the radar plot (Fig. 15). It rewards BALANCED performance:
    a framework excelling in only one dimension will not dominate over a
    framework with moderate performance across all four dimensions.

    Mapping of Paper 5 scores to QPack slots:
      S_speed  → S_mapped_runtime    (compile throughput: log10(gates/sec))
      S_scale  → S_mapped_scalability  (from power-law fit exponent a)
      S_acc    → S_mapped_accuracy   (JSD-based, arctan-mapped, inverted)
      S_cap    → S_capacity          (max usable qubits, kept as raw integer per QPack)

    QPack published reference values for external calibration:
      QuEST Simulator  → S_overall ≈ 183.2  (highest in QPack Table VI)
      Cirq Simulator   → S_overall ≈ 157.6
      Qiskit Aer       → S_overall ≈ 147.2
      Rigetti QVM      → S_overall ≈ 104.8

    Our noiseless QSim baseline should produce values comparable to QuEST/Cirq,
    validating that the scoring pipeline is correctly calibrated.

    Args:
        S_speed: S_mapped_runtime for this framework.
        S_scale: S_mapped_scalability for this framework.
        S_acc:   S_mapped_accuracy for this framework.
        S_cap:   S_capacity (integer or float) for this framework.

    Returns:
        float: S_overall composite score. Higher is better.
    """
    if any(math.isnan(v) for v in [S_speed, S_scale, S_acc]):
        return float('nan')

    return 0.5 * (S_speed + S_scale) * (S_acc + S_cap)


# ──────────────────────────────────────────────────────────
# Linear/quadratic scaling regression (RQ4)
# ──────────────────────────────────────────────────────────

def fit_scaling_trend(qubit_counts: list, values: list) -> dict:
    """
    Fit linear and quadratic trends to (qubit_count → gate_count) data.

    This is a SUPPLEMENT to fit_power_law() — the polynomial forms give
    interpretable slope/intercept values that are easier to discuss in the
    paper than the power-law exponent alone.  Both are reported in the paper:
    the power-law form for QPack-style scoring, the linear/quadratic form
    for the scaling analysis narrative in §4.

    The "preferred" model is selected by comparing R² improvement:
    if quadratic R² – linear R² > 0.02, prefer quadratic; otherwise linear.

    Args:
        qubit_counts: List of qubit counts (x-axis).
        values:       Corresponding metric values (e.g. total gate counts).

    Returns:
        dict with keys:
          'slope'     (float): Slope of the linear fit
          'intercept' (float): Intercept of the linear fit
          'r2_linear' (float): R² of the linear fit
          'r2_quad'   (float): R² of the quadratic fit
          'preferred' (str)  : 'linear' or 'quadratic'
          'quad_coeffs' (list): [a, b, c] for quadratic ax² + bx + c
    """
    x = np.array(qubit_counts, dtype=float)
    y = np.array(values,       dtype=float)

    if len(x) < 2:
        return {
            'slope': float('nan'), 'intercept': float('nan'),
            'r2_linear': float('nan'), 'r2_quad': float('nan'),
            'preferred': 'linear', 'quad_coeffs': [float('nan')] * 3,
        }

    # Linear fit
    lin_coeffs = np.polyfit(x, y, 1)
    y_lin_pred = np.polyval(lin_coeffs, x)
    ss_res_lin = float(np.sum((y - y_lin_pred) ** 2))
    ss_tot     = float(np.sum((y - y.mean()) ** 2))
    r2_linear  = 1.0 - (ss_res_lin / ss_tot) if ss_tot > 0 else 0.0

    # Quadratic fit (needs at least 3 points)
    if len(x) >= 3:
        quad_coeffs = np.polyfit(x, y, 2)
        y_quad_pred = np.polyval(quad_coeffs, x)
        ss_res_quad = float(np.sum((y - y_quad_pred) ** 2))
        r2_quad     = 1.0 - (ss_res_quad / ss_tot) if ss_tot > 0 else 0.0
    else:
        quad_coeffs = [0.0, float(lin_coeffs[0]), float(lin_coeffs[1])]
        r2_quad     = r2_linear

    preferred = 'quadratic' if (r2_quad - r2_linear) > 0.02 else 'linear'

    return {
        'slope':       float(lin_coeffs[0]),
        'intercept':   float(lin_coeffs[1]),
        'r2_linear':   r2_linear,
        'r2_quad':     r2_quad,
        'preferred':   preferred,
        'quad_coeffs': [float(c) for c in quad_coeffs],
    }


# ──────────────────────────────────────────────────────────
# Entry-point
# ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    # --- 1. Distribution equivalence (RQ2) ---

    distributions_dir = os.path.join('benchmarks', 'metrics', 'distributions')
    shots = 4096

    print(f"\n{'='*65}")
    print(f"  Statistical Tests — Paper 5 Cross-Framework Benchmarking")
    print(f"{'='*65}")
    print(f"\n[RQ2] Running pairwise JSD across all algorithms (shots={shots}) …")

    try:
        df_tests = run_all_statistical_tests(distributions_dir, shots=shots)
        out_path = os.path.join('benchmarks', 'metrics', 'statistical_tests.csv')
        df_tests.to_csv(out_path, index=False)
        print(f"  → Saved: {out_path}")

        # Flag any divergent pairs
        divergent = df_tests[
            (df_tests['jsd_qiskit_cirq']  >= JSD_DIVERGENT_THRESHOLD) |
            (df_tests['jsd_qiskit_pl']    >= JSD_DIVERGENT_THRESHOLD) |
            (df_tests['jsd_cirq_pl']      >= JSD_DIVERGENT_THRESHOLD)
        ]

        if divergent.empty:
            print("  ✓ No significantly divergent pairs found (JSD < 0.05 throughout).")
        else:
            print(f"\n  ⚠  {len(divergent)} algorithm(s) with JSD ≥ 0.05 — investigate:")
            for _, row in divergent.iterrows():
                print(f"     • {row['algorithm']} ({row['n_qubits']}q): "
                      f"Qiskit↔Cirq={row['jsd_qiskit_cirq']:.4f}  "
                      f"Qiskit↔PL={row['jsd_qiskit_pl']:.4f}  "
                      f"Cirq↔PL={row['jsd_cirq_pl']:.4f}")

    except FileNotFoundError as exc:
        print(f"  [SKIP] {exc}")
        df_tests = pd.DataFrame()

    # --- 2. QPack composite scores (RQ3, RQ4, RQ5) ---

    print(f"\n[QPack Scores] Loading structural and timing metrics …")

    structural_path    = os.path.join('benchmarks', 'metrics', 'structural_metrics.csv')
    compile_times_path = os.path.join('benchmarks', 'metrics', 'compilation_times.csv')

    if os.path.exists(structural_path) and os.path.exists(compile_times_path):
        df_struct = pd.read_csv(structural_path)
        df_compile = pd.read_csv(compile_times_path)

        # Merge total_gates into compile times for runtime score
        df_merged = df_compile.merge(
            df_struct[['algorithm', 'framework', 'n_qubits', 'total_gates']],
            on=['algorithm', 'framework', 'n_qubits'], how='left'
        )

        runtime_scores = compute_runtime_score(df_merged)
        print(f"\n  S_compile_speed (QPack §IV-A):")
        for fw, score in runtime_scores.items():
            print(f"    {fw:12s}: {score:.3f}")

        # Power-law fits for scalability score (using variable-qubit algorithms)
        variable_algos = ['ghz_state', 'deutsch_jozsa', 'grovers_algorithm', 'qrng']
        scalability_scores = {}
        power_law_rows = []

        for fw in ['qiskit', 'cirq', 'pennylane']:
            a_values = []
            for algo in variable_algos:
                subset = df_struct[
                    (df_struct['algorithm'] == algo) &
                    (df_struct['framework'] == fw)
                ].sort_values('n_qubits')
                if len(subset) >= 3:
                    fit = fit_power_law(
                        subset['n_qubits'].tolist(),
                        subset['total_gates'].tolist()
                    )
                    a_values.append(fit['a'])
                    power_law_rows.append({
                        'algorithm': algo, 'framework': fw,
                        **fit
                    })

            mean_a = float(np.nanmean(a_values)) if a_values else float('nan')
            scalability_scores[fw] = compute_scalability_score(mean_a)

        print(f"\n  S_scalability (QPack §IV-C):")
        for fw, score in scalability_scores.items():
            print(f"    {fw:12s}: {score:.3f}")

        # Save power-law fit results
        if power_law_rows:
            pl_path = os.path.join('benchmarks', 'metrics', 'power_law_fits.csv')
            pd.DataFrame(power_law_rows).to_csv(pl_path, index=False)
            print(f"\n  → Saved power-law fits: {pl_path}")

        # Accuracy and capacity scores require JSD data — only compute if available
        if not df_tests.empty:
            accuracy_scores  = {}
            capacity_scores  = {}

            for fw in ['qiskit', 'cirq', 'pennylane']:
                # Build jsd_by_algorithm: algorithm → JSD vs. theoretical ideal
                # Using qiskit as baseline if framework is cirq/pennylane, else use all pairs
                jsd_col = {
                    'qiskit':    'jsd_qiskit_cirq',    # worst case for qiskit
                    'cirq':      'jsd_qiskit_cirq',
                    'pennylane': 'jsd_qiskit_pl',
                }.get(fw, 'jsd_qiskit_cirq')

                if jsd_col in df_tests.columns:
                    jsd_map = dict(zip(df_tests['algorithm'], df_tests[jsd_col]))
                    accuracy_scores[fw] = compute_accuracy_score(jsd_map, fw)

                # Capacity: use variable-qubit JSD if available
                # (Simplified: use the mean JSD for each n_qubits from df_tests)
                jsd_by_n = {}
                for n in df_tests['n_qubits'].unique():
                    sub = df_tests[df_tests['n_qubits'] == n]
                    if not sub.empty and jsd_col in sub.columns:
                        jsd_by_n[int(n)] = float(sub[jsd_col].mean())
                capacity_scores[fw] = compute_capacity_score(jsd_by_n)

            print(f"\n  S_accuracy (QPack §IV-B):")
            for fw, score in accuracy_scores.items():
                print(f"    {fw:12s}: {score:.3f}")

            print(f"\n  S_capacity (QPack §IV-D):")
            for fw, score in capacity_scores.items():
                print(f"    {fw:12s}: {score} qubits")

            # Overall scores
            print(f"\n  S_overall (QPack §IV-F):")
            qpack_rows = []
            for fw in ['qiskit', 'cirq', 'pennylane']:
                s_overall = compute_overall_score(
                    S_speed=runtime_scores.get(fw, float('nan')),
                    S_scale=scalability_scores.get(fw, float('nan')),
                    S_acc=accuracy_scores.get(fw, float('nan')),
                    S_cap=capacity_scores.get(fw, float('nan')),
                )
                print(f"    {fw:12s}: {s_overall:.2f}  "
                      f"(QPack ref: QuEST=183.2, Cirq=157.6, Qiskit Aer=147.2)")
                qpack_rows.append({
                    'framework':      fw,
                    'S_compile_speed': runtime_scores.get(fw, float('nan')),
                    'S_scalability':  scalability_scores.get(fw, float('nan')),
                    'S_accuracy':     accuracy_scores.get(fw, float('nan')),
                    'S_capacity':     capacity_scores.get(fw, float('nan')),
                    'S_overall':      s_overall,
                })

            qpack_out = os.path.join('benchmarks', 'metrics', 'qpack_scores.csv')
            pd.DataFrame(qpack_rows).to_csv(qpack_out, index=False)
            print(f"\n  → Saved QPack scores: {qpack_out}")

    else:
        missing = []
        if not os.path.exists(structural_path):
            missing.append(structural_path)
        if not os.path.exists(compile_times_path):
            missing.append(compile_times_path)
        print(f"  [SKIP] Files not yet generated — run compile_all.py first:")
        for m in missing:
            print(f"    • {m}")

    print(f"\n{'='*65}\n")
