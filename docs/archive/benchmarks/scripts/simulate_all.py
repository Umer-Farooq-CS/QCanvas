"""
Script: simulate_all.py
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking
Phase 3 – Simulation & Dynamic Metrics Collection

This script runs each generated QASM file through the QCanvas QSim backend
and collects dynamic performance metrics:
  - Measurement distribution (bitstring → count)
  - Simulation execution time (ms)
  - Peak memory usage (MB)
  - CPU utilisation (%)
  - Estimated fidelity (from SimResult metadata, where available)

Each (algorithm, framework, n_qubits, shot_count) combination is run N_REPEATS
times to compute mean and standard deviation.

Shot counts: [1024, 4096, 8192]  (as specified in the paper — Paper §3.3)

QSim API used:
  from quantum_simulator.qsim.core.api import run_qasm
  from quantum_simulator.qsim.core.types import RunArgs, SimResult
  result = run_qasm(RunArgs(qasm_input=qasm_str, backend='cirq', shots=1024))
  counts = result.counts   # dict: bitstring → int count

Output files:
  - benchmarks/metrics/simulation_metrics.csv
  - benchmarks/metrics/distributions/<algo>_<n>q_<framework>_<shots>_trial<k>.json
    (raw measurement distribution for each trial, for statistical analysis)

CRITICAL: All simulations use the SAME QSim backend (Cirq statevector simulator)
regardless of the source framework. This is what makes cross-framework simulation
comparison fair: the QASM is compiled to the same backend, so any distributional
differences arise from the QASM structure, not the simulation engine.

Called by:
  - benchmarks/notebooks/nb02_simulation_and_qv.ipynb
"""

# ──────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────

import os
import sys
import time
import json
import tracemalloc
import numpy as np
import pandas as pd
import psutil

# Add QCanvas project root to sys.path for module resolution
_QCANVAS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _QCANVAS_ROOT not in sys.path:
    sys.path.insert(0, _QCANVAS_ROOT)

# QSim backend API — same backend used for ALL frameworks (fairness guarantee)
from quantum_simulator.qsim.core.api   import run_qasm
from quantum_simulator.qsim.core.types import RunArgs


# ──────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────

# Number of simulation repetitions per (algo, framework, n_qubits, shots) combination.
# Paper §3.3: "Each experiment is repeated 10 times; results report mean ± std."
N_REPEATS = 10

# Shot counts specified in the paper methodology.
SHOT_COUNTS = [1024, 4096, 8192]

# QSim backend to use for ALL frameworks. Using 'cirq' (Cirq statevector) ensures
# all QASM files are evaluated on the same simulation engine — the key fairness
# guarantee of the cross-framework comparison (Paper §3.3).
QSIM_BACKEND = 'cirq'

# Directory paths — absolute, anchored to QCanvas root.
QASM_DIR          = os.path.join(_QCANVAS_ROOT, 'benchmarks', 'qasm_outputs')
METRICS_DIR       = os.path.join(_QCANVAS_ROOT, 'benchmarks', 'metrics')
DISTRIBUTIONS_DIR = os.path.join(_QCANVAS_ROOT, 'benchmarks', 'metrics', 'distributions')


# ──────────────────────────────────────────────────────────
# Filename parser (mirrors compile_all.py naming convention)
# ──────────────────────────────────────────────────────────

def _parse_qasm_filename(filename: str) -> dict:
    """
    Extract (algorithm, n_qubits, framework) from a QASM filename.

    Naming convention set by compile_all.py:
      <algorithm>_<n>q_<framework>.qasm
      e.g. grovers_algorithm_4q_cirq.qasm

    Returns dict with keys: algorithm, n_qubits (int), framework.
    Returns None on parse failure.
    """
    import re
    base  = os.path.splitext(filename)[0]
    parts = base.split('_')

    nq_idx = next(
        (i for i, p in enumerate(parts) if re.fullmatch(r'\d+q', p)),
        None
    )
    if nq_idx is None:
        return None

    return {
        'algorithm': '_'.join(parts[:nq_idx]),
        'n_qubits':  int(parts[nq_idx].rstrip('q')),
        'framework': '_'.join(parts[nq_idx + 1:]),
    }


# ──────────────────────────────────────────────────────────
# Single trial runner
# ──────────────────────────────────────────────────────────

def run_simulation_trial(qasm_str: str, shots: int) -> dict:
    """
    Run a single simulation trial and collect all dynamic performance metrics.

    The trial sequence:
      1. Start memory tracking (tracemalloc).
      2. Sample baseline CPU load (psutil).
      3. Invoke run_qasm(RunArgs(...)) against the Cirq backend.
      4. Record elapsed wall-clock time.
      5. Read peak memory from tracemalloc; stop tracking.
      6. Sample post-simulation CPU load.

    CPU utilisation is averaged before/after to approximate the simulation
    period load. The approximation is consistent across frameworks (same
    bias for all), so relative comparisons are valid.

    Args:
        qasm_str: Complete OpenQASM 3.0 source string to simulate.
        shots:    Number of measurement shots.

    Returns:
        dict with keys:
          'sim_time_ms'             (float): Wall-clock time in milliseconds
          'peak_memory_mb'          (float): Peak memory during simulation (MB)
          'cpu_pct'                 (float): Approximate CPU utilisation (%)
          'measurement_distribution' (dict): {bitstring: count}
          'fidelity'                (float or None): Backend-reported fidelity, if any
    """
    # --- Memory tracking ---
    tracemalloc.start()

    # --- CPU baseline (interval=None = immediately return cached value) ---
    cpu_before = psutil.cpu_percent(interval=None)

    # --- Simulation ---
    t_start = time.perf_counter()

    sim_result = run_qasm(
        RunArgs(qasm_input=qasm_str, backend=QSIM_BACKEND, shots=shots)
    )

    t_end = time.perf_counter()

    # --- Memory peak ---
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # --- CPU post-simulation ---
    cpu_after = psutil.cpu_percent(interval=None)

    return {
        'sim_time_ms':              (t_end - t_start) * 1000.0,
        'peak_memory_mb':           peak_bytes / (1024.0 * 1024.0),
        'cpu_pct':                  (cpu_before + cpu_after) / 2.0,
        'measurement_distribution': dict(sim_result.counts),
        'fidelity':                 sim_result.metadata.get('fidelity', None),
    }


# ──────────────────────────────────────────────────────────
# Multi-trial runner
# ──────────────────────────────────────────────────────────

def run_simulation_repeated(
    qasm_path: str,
    shots:     int,
    n_repeats: int = N_REPEATS,
) -> dict:
    """
    Run a QASM file through the simulation backend n_repeats times and return
    aggregated statistics.

    All trial distribution dictionaries are returned (not just the mean) because
    pairwise JSD analysis in statistical_tests.py operates on individual trials
    to compute variance of the JSD estimate.

    Args:
        qasm_path:  Path to the .qasm file on disk.
        shots:      Number of measurement shots per trial.
        n_repeats:  Number of simulation repetitions.

    Returns:
        dict with keys:
          'mean_sim_time_ms'  (float): Mean simulation wall-clock time
          'std_sim_time_ms'   (float): Std of simulation wall-clock times
          'mean_memory_mb'    (float): Mean peak memory
          'std_memory_mb'     (float): Std of peak memory
          'mean_cpu_pct'      (float): Mean CPU utilisation
          'final_distribution' (dict): counts from the final trial
          'all_distributions'  (list): list of count dicts (one per trial)
          'fidelity'           (float or None): Fidelity from final trial
          'success'            (bool): False if all trials failed
          'error'              (str): Error message on failure
    """
    try:
        with open(qasm_path, 'r', encoding='utf-8') as fh:
            qasm_str = fh.read()
    except OSError as exc:
        return {
            'mean_sim_time_ms': float('nan'), 'std_sim_time_ms': float('nan'),
            'mean_memory_mb':   float('nan'), 'std_memory_mb':   float('nan'),
            'mean_cpu_pct':     float('nan'),
            'final_distribution': {}, 'all_distributions': [],
            'fidelity': None, 'success': False,
            'error': str(exc),
        }

    times_ms  = []
    memories  = []
    cpu_pcts  = []
    all_dists = []
    fidelity  = None
    last_dist = {}

    for k in range(n_repeats):
        try:
            trial = run_simulation_trial(qasm_str, shots)
            times_ms.append(trial['sim_time_ms'])
            memories.append(trial['peak_memory_mb'])
            cpu_pcts.append(trial['cpu_pct'])
            all_dists.append(trial['measurement_distribution'])
            last_dist = trial['measurement_distribution']
            fidelity  = trial['fidelity']

        except Exception as exc:
            # One failed trial: log but continue — we can still compute
            # statistics from the remaining trials.
            all_dists.append({})
            print(f"      [WARN] Trial {k+1} failed: {exc}")

    successful = [t for t in times_ms]   # all recorded values are successes

    if not successful:
        return {
            'mean_sim_time_ms': float('nan'), 'std_sim_time_ms': float('nan'),
            'mean_memory_mb':   float('nan'), 'std_memory_mb':   float('nan'),
            'mean_cpu_pct':     float('nan'),
            'final_distribution': {}, 'all_distributions': all_dists,
            'fidelity': None, 'success': False,
            'error': 'All trials failed.',
        }

    return {
        'mean_sim_time_ms':   float(np.mean(times_ms)),
        'std_sim_time_ms':    float(np.std(times_ms)),
        'mean_memory_mb':     float(np.mean(memories)),
        'std_memory_mb':      float(np.std(memories)),
        'mean_cpu_pct':       float(np.mean(cpu_pcts)),
        'final_distribution': last_dist,
        'all_distributions':  all_dists,
        'fidelity':           fidelity,
        'success':            True,
        'error':              '',
    }


# ──────────────────────────────────────────────────────────
# Main runner
# ──────────────────────────────────────────────────────────

def run_all_simulations(
    n_repeats: int = N_REPEATS,
    shot_counts: list = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Simulate every .qasm file in QASM_DIR for each shot count in SHOT_COUNTS.

    For each (qasm_file, shot_count) pair:
      1. Run run_simulation_repeated() to get mean/std of all metrics.
      2. Save each trial's distribution JSON to DISTRIBUTIONS_DIR/.
      3. Append aggregate metrics to the results list.

    Distribution JSON filename convention:
      <algo>_<n>q_<framework>_<shots>_trial<k>.json

    Args:
        n_repeats:   Number of repetitions per (file, shots) combination.
        shot_counts: List of shot counts to test. Defaults to SHOT_COUNTS.
        verbose:     Whether to print per-file progress.

    Returns:
        pd.DataFrame with columns:
          [algorithm, framework, n_qubits, shots,
           mean_sim_time_ms, std_sim_time_ms,
           mean_memory_mb, std_memory_mb,
           mean_cpu_pct, fidelity,
           distribution_path, success]
    """
    if shot_counts is None:
        shot_counts = SHOT_COUNTS

    os.makedirs(DISTRIBUTIONS_DIR, exist_ok=True)

    qasm_files = sorted([f for f in os.listdir(QASM_DIR) if f.endswith('.qasm')])

    if not qasm_files:
        raise FileNotFoundError(
            f"No .qasm files found in {QASM_DIR}/\n"
            f"Run compile_all.py first."
        )

    total = len(qasm_files) * len(shot_counts)
    done  = 0
    rows  = []

    for fname in qasm_files:
        meta = _parse_qasm_filename(fname)
        if meta is None:
            if verbose:
                print(f"  [SKIP] Cannot parse filename: {fname}")
            continue

        algo      = meta['algorithm']
        n_qubits  = meta['n_qubits']
        framework = meta['framework']
        qasm_path = os.path.join(QASM_DIR, fname)

        for shots in shot_counts:
            done += 1
            label = (f"[{done}/{total}] {algo} ({n_qubits}q) "
                     f"{framework} @ {shots} shots")

            if verbose:
                print(f"  Simulating: {label} …", end=' ', flush=True)

            result = run_simulation_repeated(qasm_path, shots, n_repeats)

            # --- Save individual trial distribution JSON files ---
            dist_path = ''
            if result['success']:
                for k, trial_dist in enumerate(result['all_distributions']):
                    if not trial_dist:
                        continue
                    dist_fname = f"{algo}_{n_qubits}q_{framework}_{shots}_trial{k+1}.json"
                    dist_path  = os.path.join(DISTRIBUTIONS_DIR, dist_fname)
                    with open(dist_path, 'w', encoding='utf-8') as fh:
                        json.dump(trial_dist, fh)

                # Use the last saved distribution path as the reference in the CSV
                if verbose:
                    print(f"✓  {result['mean_sim_time_ms']:.1f} ± "
                          f"{result['std_sim_time_ms']:.1f} ms  |  "
                          f"mem={result['mean_memory_mb']:.1f} MB")
            else:
                if verbose:
                    print(f"✗  FAILED: {result['error'][:80]}")

            rows.append({
                'algorithm':          algo,
                'framework':          framework,
                'n_qubits':           n_qubits,
                'shots':              shots,
                'mean_sim_time_ms':   result['mean_sim_time_ms'],
                'std_sim_time_ms':    result['std_sim_time_ms'],
                'mean_memory_mb':     result['mean_memory_mb'],
                'std_memory_mb':      result['std_memory_mb'],
                'mean_cpu_pct':       result['mean_cpu_pct'],
                'fidelity':           result['fidelity'],
                'distribution_path':  dist_path,
                'success':            result['success'],
            })

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────
# Entry-point
# ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"\n{'='*65}")
    print(f"  Simulation Runner — Paper 5 Cross-Framework Benchmarking")
    print(f"  Backend: {QSIM_BACKEND} (same for ALL frameworks — fairness guarantee)")
    print(f"  Repeats: {N_REPEATS} per combination")
    print(f"  Shot counts: {SHOT_COUNTS}")
    print(f"{'='*65}\n")

    os.makedirs(DISTRIBUTIONS_DIR, exist_ok=True)

    df = run_all_simulations(n_repeats=N_REPEATS, shot_counts=SHOT_COUNTS, verbose=True)

    # Save simulation metrics CSV
    out_path = os.path.join(METRICS_DIR, 'simulation_metrics.csv')
    df.to_csv(out_path, index=False)
    print(f"\n[simulate_all] Saved → {out_path}  ({len(df)} rows)\n")

    # Summary: mean simulation time per framework
    success_df = df[df['success']]
    if not success_df.empty:
        print("Mean simulation time per framework (all algorithms, 4096 shots):")
        sub = success_df[success_df['shots'] == 4096]
        if not sub.empty:
            summary = (
                sub.groupby('framework')[['mean_sim_time_ms', 'mean_memory_mb']]
                .mean()
                .round(2)
            )
            print(summary.to_string())
        print()

    failed_df = df[~df['success']]
    if not failed_df.empty:
        print(f"⚠  {len(failed_df)} combinations failed.")

    print(f"\n{'='*65}\n")
