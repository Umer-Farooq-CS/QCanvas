# Quantum Framework Comparison Metrics

This document outlines the various metrics collected during the benchmarking and comparison of quantum computing frameworks (e.g., Qiskit, Cirq, PennyLane). The metrics are categorized based on the specific aspect of the framework they evaluate, providing a comprehensive view of performance, resource efficiency, and compilation quality.

## 1. Compilation Metrics (`compilation_times.csv`)

These metrics evaluate the efficiency and consistency of the framework's transpiler/compiler when converting a high-level circuit definition into a hardware-executable instruction set (like QASM).

*   **`mean_compile_ms`**: The average time (in milliseconds) taken by the framework to compile a given quantum algorithm for a specific number of qubits.
*   **`std_compile_ms`**: The standard deviation of the compilation time across multiple runs.
*   **`success`**: A boolean flag indicating whether the compilation process completed successfully.

**Why they are relevant:**
Compilation overhead is a critical factor in rapid prototyping and when dealing with dynamic circuits that require just-in-time compilation. High standard deviations indicate instability or unpredictable performance in the transpiler. A fast and reliable compiler drastically improves the developer experience and overall execution pipeline speed.

## 2. Structural & Optimization Metrics (`structural_metrics.csv`)

These metrics analyze the topology and composition of the compiled circuits, which directly impacts the likelihood of successful execution on physical hardware.

*   **`total_gates`**: The total number of quantum gates in the compiled circuit.
*   **`circuit_depth`**: The length of the longest execution path in the circuit.
*   **`multi_qubit_gates`**: The total number of gates acting on more than one qubit (e.g., CX, CZ).
*   **`multi_qubit_ratio`**: The proportion of multi-qubit gates relative to the total gate count.
*   **`gate_<TYPE>`**: Counts of specific individual gate types (e.g., `gate_H`, `gate_CX`, `gate_RZ`).

**Why they are relevant:**
Quantum states are fragile and degrade over time (decoherence) and with every applied operation (gate errors). Since multi-qubit gates currently have significantly higher error rates than single-qubit gates, a lower `circuit_depth` and fewer `multi_qubit_gates` directly translate to higher fidelity when executed on real hardware. Frameworks that produce optimized, shallower circuits are highly advantageous.

## 3. Scaling & Complexity Metrics (`power_law_fits.csv`)

These metrics characterize how a framework's resource requirements (usually circuit depth or gate count) scale as the size of the problem (number of qubits) increases. They are derived by fitting the structural metrics to a power-law curve: $y = c \cdot n^a$.

*   **`a` (Exponent)**: The exponent of the power-law fit.
*   **`coefficient` ($c$)**: The constant multiplier in the power-law fit.
*   **`r2`**: The R-squared value, indicating how well the power-law model fits the empirical data.
*   **`scaling_class`**: A qualitative categorization of the scaling behavior (e.g., `constant-depth`, `linear`, `sub-linear`, `super-linear`).

**Why they are relevant:**
Understanding scaling behavior is crucial for predicting whether an algorithm will remain feasible on larger quantum processors. For instance, if a framework transpiles an algorithm with `super-linear` depth scaling, it will quickly become unexecutable on near-term noisy hardware, whereas `constant-depth` or `linear` scaling is much more desirable.

## 4. Simulation Performance Metrics (`simulation_metrics.csv`)

These metrics measure the resource efficiency of the classical simulators provided by each framework.

*   **`mean_sim_time_ms` & `std_sim_time_ms`**: The average and standard deviation of the time taken to simulate the circuit and generate measurement samples (shots).
*   **`mean_memory_mb` & `std_memory_mb`**: The average and standard deviation of RAM consumed during the simulation.
*   **`mean_cpu_pct`**: The average CPU utilization percentage during the simulation.
*   **`fidelity`**: The accuracy of the simulated state or distribution compared to the ideal theoretical expectation.

**Why they are relevant:**
Before running on expensive physical quantum hardware, algorithms are extensively simulated classically. Memory and time requirements scale exponentially with the number of qubits for statevector simulation. Frameworks with highly optimized simulators (e.g., low memory footprint, high CPU/GPU utilization) allow developers to test larger circuits on standard classical hardware.

## 5. Statistical Equivalence Metrics (`statistical_tests.csv`)

These metrics assess whether different frameworks produce mathematically equivalent probability distributions for the same algorithm.

*   **`jsd_<framework1>_<framework2>`**: The Jensen-Shannon Divergence (JSD) between the output distributions of two frameworks. A value closer to 0 indicates identical distributions.
*   **`label_<fw1>_<fw2>`**: A categorical label or boolean (✓/✗) denoting whether the two frameworks are statistically equivalent based on a defined threshold.
*   **`all_equivalent`**: A boolean flag indicating if all tested frameworks yielded equivalent output distributions.

**Why they are relevant:**
This serves as a sanity check and validation layer. If frameworks produce significantly different output distributions for the exact same conceptual circuit, it highlights differences in default transpilation strategies, endianness conventions, or potential bugs within a framework's stack.

## 6. Holistic Benchmark Scores (`qpack_scores.csv` & `quantum_volume_estimates.csv`)

These metrics attempt to summarize the overall capability and power of the framework into high-level scores.

*   **`effective_qv` & `effective_qv_log2`**: Estimates of the Quantum Volume (QV) that the framework can effectively support. QV accounts for qubit count, connectivity, gate errors, and compiler efficiency.
*   **`S_compile_speed`**: A normalized score reflecting compilation performance.
*   **`S_scalability`**: A normalized score reflecting how well the framework scales to larger qubit sizes.
*   **`S_accuracy`**: A normalized score for simulation/execution fidelity.
*   **`S_capacity`**: A score representing the maximum problem size the framework can handle effectively.
*   **`S_overall`**: An aggregated QPack score summarizing the overall capability of the framework.

**Why they are relevant:**
While low-level metrics are essential for deep analysis, holistic scores like Quantum Volume and QPack scores provide a quick, comparative snapshot. They allow researchers and decision-makers to easily rank frameworks based on a balanced view of speed, accuracy, and scalability without getting bogged down in individual gate counts.
