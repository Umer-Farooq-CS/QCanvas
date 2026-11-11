# Paper 5 — Cross-Framework Quantum Algorithm Benchmarking

This directory contains all code, scripts, notebooks, and collected data for **Paper 5**:
> *Cross-Framework Quantum Algorithm Benchmarking via Unified Compilation to OpenQASM 3.0*

QCanvas is used as the unified compilation platform. Every algorithm is implemented idiomatically
in Qiskit, Cirq, and PennyLane, compiled to OpenQASM 3.0, and then simulated on the same QSim
backend for a controlled, apples-to-apples comparison.

## Directory Layout

```
benchmarks/
├── algorithms/          # Idiomatic algorithm implementations per framework
│   ├── qiskit/          # 12 algorithms in native Qiskit style
│   ├── cirq/            # 12 algorithms in native Cirq style
│   └── pennylane/       # 12 algorithms in native PennyLane style
├── notebooks/           # One Jupyter notebook per analysis phase
│   ├── nb01_compile_and_static_analysis.ipynb
│   ├── nb02_simulation_and_qv.ipynb
│   ├── nb03_statistical_analysis.ipynb
│   ├── nb04_case_studies.ipynb
│   ├── nb05_figures.ipynb
│   ├── nb06_results_tables.ipynb
│   └── nb07_validation.ipynb
├── scripts/             # reusable helper modules called by notebooks
│   ├── compile_all.py
│   ├── analyze_qasm.py
│   ├── simulate_all.py
│   ├── quantum_volume.py
│   ├── statistical_tests.py
│   └── figure_styles.py
├── qasm_outputs/        # Generated QASM 3.0 files (one per algo × framework)
├── metrics/             # CSV files with collected structural and simulation metrics
└── results/             # Processed outputs, plots, and tables
    ├── structural/
    ├── simulation/
    └── scaling/
```

## Notebook Execution Order

Run notebooks in numbered order. Each one builds on the outputs of the previous:

| Notebook | Input | Output |
|----------|-------|--------|
| `nb01` — Compile & Static Analysis | `algorithms/` | `qasm_outputs/`, `metrics/structural_metrics.csv` |
| `nb02` — Simulation & QV | `qasm_outputs/` | `metrics/simulation_metrics.csv`, QV estimates |
| `nb03` — Statistical Analysis | `metrics/*.csv` | JSD/Chi-squared results, equivalence decisions |
| `nb04` — Case Studies | `qasm_outputs/`, `metrics/` | Narrative-ready tables and listings |
| `nb05` — Figures | All metrics | Publication-quality figures in `results/` |
| `nb06` — Results Tables | All metrics | LaTeX/Markdown tables for paper sections |
| `nb07` — Validation | All outputs | Final validation checklist pass |

## Algorithm Suite (12 Algorithms)

| # | Algorithm | Category | Qubit Range |
|---|-----------|----------|------------|
| 1 | Bell State | Foundational | 2 |
| 2 | GHZ State | Foundational | 3–8 |
| 3 | Quantum Teleportation | Communication | 3 |
| 4 | Deutsch–Jozsa | Oracle-Based | 3–8 |
| 5 | Bernstein–Vazirani | Oracle-Based | 3–8 |
| 6 | Grover's Algorithm | Search | 2–6 |
| 7 | QRNG | Randomness | 4–8 |
| 8 | VQE | Variational | 2–6 |
| 9 | QAOA | Variational | 2–6 |
| 10 | QML XOR Classifier | Quantum ML | 2–4 |
| 11 | Bit-Flip Error Code | Error Correction | 3–9 |
| 12 | Phase-Flip Error Code | Error Correction | 3–9 |

## Key Metrics Collected

- Gate count (total and by type)
- Circuit depth
- Multi-qubit gate ratio
- QASM 3.0 modifier usage (ctrl@, inv@, pow@)
- Compilation time (mean ± std over 10 runs)
- Simulation time (mean ± std over 10 runs)
- Peak memory usage during simulation
- Measurement distributions (bitstring → count)
- Jensen–Shannon divergence (pairwise framework comparison)
- Chi-squared goodness-of-fit p-values
- **Quantum Volume estimate** (circuit-structure-implied, depolarizing noise model)
