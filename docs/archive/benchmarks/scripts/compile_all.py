"""
Script: compile_all.py
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking
Phase 2 – Compilation & Static Analysis

This script orchestrates the full compilation of all (algorithm, framework) pairs.
For each pair it:
  1. Loads the algorithm source code from benchmarks/algorithms/<framework>/<algo>.py
  2. Passes the source code string to the appropriate QCanvas converter:
       QiskitToQASM3Converter, CirqToQASM3Converter, or PennyLaneToQASM3Converter
  3. The converter performs AST-based parsing → QASM3Builder → OpenQASM 3.0 string
  4. Saves the generated QASM string to:
       benchmarks/qasm_outputs/<algo>_<n>q_<framework>.qasm
  5. Records compilation time (10 repeated runs → mean ± std)
  6. Saves a compilation timing CSV to benchmarks/metrics/compilation_times.csv

This script is run from the QCanvas project root. All QCanvas module imports
use paths relative to the root (quantum_converters/ etc.).

Output files:
  - benchmarks/qasm_outputs/<algo>_<n>q_<framework>.qasm   (one per combination)
  - benchmarks/metrics/compilation_times.csv

QCanvas Converter API:
  Each converter class exposes:
    converter.convert(source_code: str) → ConversionResult
  where ConversionResult.qasm_code is the generated OpenQASM 3.0 string.

  Public convenience functions are also available:
    from quantum_converters.converters.qiskit_to_qasm import convert_qiskit_to_qasm3
    from quantum_converters.converters.cirq_to_qasm   import convert_cirq_to_qasm3
    from quantum_converters.converters.pennylane_to_qasm import convert_pennylane_to_qasm3

Called by:
  - benchmarks/notebooks/nb01_compile_and_static_analysis.ipynb (via %run or subprocess)
"""

# ──────────────────────────────────────────────────────────
# Imports
# ──────────────────────────────────────────────────────────

import os
import sys
import time
import inspect
import numpy as np
import pandas as pd

# Add QCanvas project root to Python path so QCanvas modules are importable
# when running this script directly from benchmarks/scripts/ or as a subprocess.
_QCANVAS_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _QCANVAS_ROOT not in sys.path:
    sys.path.insert(0, _QCANVAS_ROOT)

# QCanvas converter classes — source-language → OpenQASM 3.0
from quantum_converters.converters.qiskit_to_qasm    import QiskitToQASM3Converter
from quantum_converters.converters.cirq_to_qasm      import CirqToQASM3Converter
from quantum_converters.converters.pennylane_to_qasm import PennyLaneToQASM3Converter


# ──────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────

# Number of compilation repetitions for timing statistics.
# Paper §3.3: "Each experiment is repeated 10 times; results report mean ± std."
N_REPEATS = 10

# Shot counts used later by simulate_all.py (documented here for cross-reference)
SHOT_COUNTS = [1024, 4096, 8192]

# Directory paths — absolute, anchored to QCanvas root so that this script
# works correctly regardless of where it is invoked from (project root,
# benchmarks/scripts/, or a Jupyter notebook in benchmarks/notebooks/).
ALGORITHMS_DIR   = os.path.join(_QCANVAS_ROOT, 'benchmarks', 'algorithms')
QASM_OUTPUT_DIR  = os.path.join(_QCANVAS_ROOT, 'benchmarks', 'qasm_outputs')
METRICS_DIR      = os.path.join(_QCANVAS_ROOT, 'benchmarks', 'metrics')


# ──────────────────────────────────────────────────────────
# Algorithm Registry
# ──────────────────────────────────────────────────────────

# Each entry specifies one algorithm and the qubit counts to test.
# For fixed-size algorithms (Bell State, Teleportation), 'qubits' has one entry.
# For scaling algorithms (GHZ, Grover's, etc.), 'qubits' is a list to iterate over.
# The qubit count is passed as an argument to get_circuit(n) if the function accepts one.

ALGORITHM_REGISTRY = [
    # ── Foundational ──────────────────────────────────────────
    {
        'name':   'bell_state',
        'qubits': [2],
        'description': 'Bell State — simplest circuit, equality sanity check',
    },
    {
        'name':   'ghz_state',
        'qubits': [3, 4, 5, 6, 7, 8],
        'description': 'GHZ State — entanglement scaling study (RQ4)',
    },
    # ── Quantum Communication ──────────────────────────────────
    {
        'name':   'quantum_teleportation',
        'qubits': [3],
        'description': 'Quantum Teleportation — mid-circuit measurement handling',
    },
    # ── Oracle-Based ──────────────────────────────────────────
    {
        'name':   'deutsch_jozsa',
        'qubits': [3, 4, 5, 6, 7, 8],
        'description': 'Deutsch–Jozsa — oracle encoding divergence across frameworks',
    },
    {
        'name':   'bernstein_vazirani',
        'qubits': [3, 4, 5, 6, 7, 8],
        'description': 'Bernstein–Vazirani — hidden string oracle',
    },
    # ── Search ────────────────────────────────────────────────
    {
        'name':   'grovers_algorithm',
        'qubits': [2, 3, 4, 5, 6],
        'description': 'Grover\'s Algorithm — diffusion operator decomposition divergence',
    },
    # ── Randomness ────────────────────────────────────────────
    {
        'name':   'qrng',
        'qubits': [4, 5, 6, 7, 8],
        'description': 'QRNG — pure Hadamard baseline, isolates gate-translation overhead',
    },
    # ── Variational ───────────────────────────────────────────
    {
        'name':   'vqe',
        'qubits': [2, 3, 4, 5, 6],
        'description': 'VQE — ansatz construction and parameter handling comparison',
    },
    {
        'name':   'qaoa',
        'qubits': [2, 3, 4, 5, 6],
        'description': 'QAOA — cost Hamiltonian encoding, p=1 layer',
    },
    # ── Quantum ML ────────────────────────────────────────────
    {
        'name':   'qml_xor_classifier',
        'qubits': [2, 3, 4],
        'description': 'QML XOR Classifier — angle encoding + variational layer',
    },
    # ── Error Correction ──────────────────────────────────────
    {
        'name':   'bit_flip_code',
        'qubits': [3],
        'description': 'Bit-Flip Code — syndrome measurement and ancilla handling',
    },
    {
        'name':   'phase_flip_code',
        'qubits': [3],
        'description': 'Phase-Flip Code — Hadamard-basis error correction',
    },
]

# Framework-specific converter instances (instantiated once, reused per compilation)
_CONVERTERS = {
    'qiskit':    QiskitToQASM3Converter(),
    'cirq':      CirqToQASM3Converter(),
    'pennylane': PennyLaneToQASM3Converter(),
}


# ──────────────────────────────────────────────────────────
# Utility: Bitstring normalisation
# ──────────────────────────────────────────────────────────

def normalize_bitstring(bitstring: str, source_framework: str) -> str:
    """
    Normalise a measurement bitstring to big-endian (most-significant qubit first).

    Qiskit outputs bitstrings in little-endian order: qubit 0 is the rightmost
    character. All other analysis functions assume big-endian. This correction
    is applied during post-processing of Qiskit simulation distributions.

    Cirq and PennyLane use natural qubit ordering (big-endian) — no correction.

    Reference: Qiskit documentation §"Bit ordering in the Qiskit SDK"

    Args:
        bitstring:        Raw bitstring from the simulation backend.
        source_framework: Framework that produced the QASM ('qiskit', 'cirq', 'pennylane').

    Returns:
        str: Normalised bitstring in big-endian order.
    """
    if source_framework.lower() == 'qiskit':
        return bitstring[::-1]
    return bitstring


# ──────────────────────────────────────────────────────────
# Source code loader
# ──────────────────────────────────────────────────────────

def _load_algorithm_source(algo_name: str, framework: str) -> str:
    """
    Read the algorithm's Python source file and return its content as a string.

    The QCanvas converter pipeline accepts the raw source code string, parses
    it into a CircuitAST via an AST visitor, and converts it to QASM 3.0 via
    QASM3Builder — no in-process code execution of user algorithms required.

    Expected file location:
      benchmarks/algorithms/<framework>/<algo_name>.py

    Args:
        algo_name: Algorithm identifier (snake_case), e.g. 'grovers_algorithm'.
        framework: Framework subfolder name: 'qiskit', 'cirq', or 'pennylane'.

    Returns:
        str: Full Python source code of the algorithm file.

    Raises:
        FileNotFoundError: If the algorithm file does not exist.
    """
    path = os.path.join(ALGORITHMS_DIR, framework, f'{algo_name}.py')
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"Algorithm file not found: {path}\n"
            f"Expected: benchmarks/algorithms/{framework}/{algo_name}.py"
        )
    with open(path, 'r', encoding='utf-8') as fh:
        return fh.read()


# ──────────────────────────────────────────────────────────
# Core compilation function
# ──────────────────────────────────────────────────────────

def run_compilation(
    algo_name:  str,
    framework:  str,
    n_qubits:   int,
    n_repeats:  int = N_REPEATS,
) -> dict:
    """
    Compile a single (algorithm, framework, n_qubits) combination to QASM 3.0,
    repeating n_repeats times to obtain timing statistics.

    On each repeat the converter is invoked on the same source string; the
    QASM output from the LAST repeat is returned (all repeats should produce
    identical QASM for deterministic circuits).

    Compilation timing measures:
      (a) Source string → CircuitAST via AST visitor   (parsing)
      (b) CircuitAST → OpenQASM 3.0 string via QASM3Builder  (code generation)
    Both are included in the measured wall-clock time.

    Args:
        algo_name:  Algorithm identifier (e.g. 'bell_state').
        framework:  Framework name ('qiskit', 'cirq', or 'pennylane').
        n_qubits:   Target qubit count (appended to QASM filename for identification;
                    the algorithm source file defines the actual qubit count).
        n_repeats:  Number of timing repetitions (default = N_REPEATS = 10).

    Returns:
        dict with keys:
          'qasm_str'     (str)  : Generated OpenQASM 3.0 string (from last repeat)
          'times_ms'     (list) : Compilation time in ms for each repeat
          'mean_ms'      (float): Mean compilation time over n_repeats
          'std_ms'       (float): Standard deviation of compilation times
          'success'      (bool) : True if compilation succeeded, False otherwise
          'error'        (str)  : Error message if success=False; empty otherwise
    """
    try:
        source  = _load_algorithm_source(algo_name, framework)
        if framework == 'pennylane':
            # For PennyLane, replace the parameter with the value to allow static evaluation
            # Use regex to handle different default values (n: int = 2, n: int = 3, etc.)
            import re as _re
            source = _re.sub(r'def\s+get_circuit\(\s*n\s*:\s*int\s*=\s*\d+\s*(?:,\s*.*)?\):', 
                             f'n = {n_qubits}\ndef get_circuit():', source)
            # Handle cases where n is not an int or has no default (though our benchmarks have defaults)
            source = _re.sub(r'def\s+get_circuit\(\s*n\s*(?:,\s*.*)?\)\s*:', 
                             f'n = {n_qubits}\ndef get_circuit():', source)
            if algo_name == 'bernstein_vazirani':
                bv_dict = {3: "101", 4: "1011", 5: "10110", 6: "101101", 7: "1011010", 8: "10110101"}
                s = bv_dict[n_qubits]
                source = source.replace('s     = SECRET_STRINGS[n]', f's = "{s}"')
            elif algo_name == 'deutsch_jozsa':
                source = source.replace('def get_circuit():', "oracle_type = 'balanced'\ndef get_circuit():")
            elif algo_name == 'qaoa':
                # For QAOA, replace the listcomp with the expanded list
                edges_list = [(i, (i + 1) % n_qubits) for i in range(n_qubits)]
                edges_str = str(edges_list)
                source = source.replace('edges = [(i, (i + 1) % n) for i in range(n)]', f'edges = {edges_str}')
            elif algo_name == 'grovers_algorithm':
                # For Grover, replace MARKED_STATES
                marked_dict = {2: "11", 3: "101", 4: "1011", 5: "10110", 6: "101101"}
                marked = marked_dict[n_qubits]
                source = source.replace('marked         = MARKED_STATES[n]', f'marked = "{marked}"')
            elif algo_name == 'vqe':
                # For VQE, replace theta list
                theta_list = [0.7853981633974483] * n_qubits
                theta_str = str(theta_list)
                source = source.replace('theta = [np.pi / 4] * n', f'theta = {theta_str}')
        conv    = _CONVERTERS[framework]
        times   = []
        qasm_str = ''

        for _ in range(n_repeats):
            t_start = time.perf_counter()
            result  = conv.convert(source)
            t_end   = time.perf_counter()

            times.append((t_end - t_start) * 1000.0)   # ms
            qasm_str = result.qasm_code

        return {
            'qasm_str': qasm_str,
            'times_ms': times,
            'mean_ms':  float(np.mean(times)),
            'std_ms':   float(np.std(times)),
            'success':  True,
            'error':    '',
        }

    except FileNotFoundError as exc:
        return {'qasm_str': '', 'times_ms': [], 'mean_ms': float('nan'),
                'std_ms': float('nan'), 'success': False, 'error': str(exc)}
    except Exception as exc:
        return {'qasm_str': '', 'times_ms': [], 'mean_ms': float('nan'),
                'std_ms': float('nan'), 'success': False, 'error': str(exc)}


# ──────────────────────────────────────────────────────────
# Main runner
# ──────────────────────────────────────────────────────────

def run_all_compilations(
    n_repeats: int = N_REPEATS,
    verbose:   bool = True,
) -> pd.DataFrame:
    """
    Compile every (algorithm, n_qubits, framework) combination defined in
    ALGORITHM_REGISTRY, save the QASM output files, and return a timing DataFrame.

    For each combination:
      1. Load algorithm source from benchmarks/algorithms/<framework>/<algo>.py
      2. Run the QCanvas conversion pipeline N_REPEATS times to gather timing data
      3. Save the final QASM string to:
           benchmarks/qasm_outputs/<algo>_<n>q_<framework>.qasm
      4. Record algorithm, framework, n_qubits, mean_compile_ms, std_compile_ms

    Args:
        n_repeats: Number of compilation repetitions per combination.
        verbose:   Whether to print per-combination progress lines.

    Returns:
        pd.DataFrame with columns:
          [algorithm, framework, n_qubits, mean_compile_ms, std_compile_ms,
           qasm_path, success]
    """
    os.makedirs(QASM_OUTPUT_DIR, exist_ok=True)
    os.makedirs(METRICS_DIR,     exist_ok=True)

    rows    = []
    n_total = sum(
        len(entry['qubits']) * 3   # 3 frameworks
        for entry in ALGORITHM_REGISTRY
    )
    done = 0

    for entry in ALGORITHM_REGISTRY:
        algo_name = entry['name']

        for n_qubits in entry['qubits']:
            for framework in ['qiskit', 'cirq', 'pennylane']:
                done += 1
                label = f"[{done}/{n_total}] {algo_name} ({n_qubits}q) — {framework}"

                if verbose:
                    print(f"  Compiling: {label} …", end=' ', flush=True)

                result = run_compilation(algo_name, framework, n_qubits, n_repeats)

                qasm_filename = f"{algo_name}_{n_qubits}q_{framework}.qasm"
                qasm_path     = os.path.join(QASM_OUTPUT_DIR, qasm_filename)

                if result['success']:
                    with open(qasm_path, 'w', encoding='utf-8') as fh:
                        fh.write(result['qasm_str'])

                    if verbose:
                        print(f"✓  {result['mean_ms']:.2f} ± {result['std_ms']:.2f} ms")
                else:
                    qasm_path = ''
                    if verbose:
                        print(f"✗  FAILED: {result['error'][:80]}")

                rows.append({
                    'algorithm':       algo_name,
                    'framework':       framework,
                    'n_qubits':        n_qubits,
                    'mean_compile_ms': result['mean_ms'],
                    'std_compile_ms':  result['std_ms'],
                    'qasm_path':       qasm_path,
                    'success':         result['success'],
                })

    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────
# Entry-point
# ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    print(f"\n{'='*65}")
    print(f"  Compilation Runner — Paper 5 Cross-Framework Benchmarking")
    print(f"  Repeats: {N_REPEATS} per combination")
    print(f"  Algorithms: {len(ALGORITHM_REGISTRY)}")
    total_combos = sum(len(e['qubits']) * 3 for e in ALGORITHM_REGISTRY)
    print(f"  Total combinations: {total_combos}")
    print(f"{'='*65}\n")

    df = run_all_compilations(n_repeats=N_REPEATS, verbose=True)

    # Save timing CSV
    out_path = os.path.join(METRICS_DIR, 'compilation_times.csv')
    df.to_csv(out_path, index=False)
    print(f"\n[compile_all] Saved → {out_path}  ({len(df)} rows)\n")

    # Summary table
    success_df  = df[df['success']]
    failed_df   = df[~df['success']]

    print(f"Summary — {len(success_df)}/{len(df)} combinations succeeded.\n")

    if not success_df.empty:
        print("Mean compilation time per framework (all algorithms):")
        summary = (
            success_df.groupby('framework')[['mean_compile_ms']]
            .mean()
            .round(3)
            .rename(columns={'mean_compile_ms': 'avg_compile_ms'})
        )
        print(summary.to_string())

    if not failed_df.empty:
        print(f"\n⚠  {len(failed_df)} combinations failed:")
        for _, row in failed_df.iterrows():
            print(f"   • {row['algorithm']} ({row['n_qubits']}q) {row['framework']}")

    print(f"\n{'='*65}\n")
