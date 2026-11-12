# QCanvas Tool Research Paper — Task Plan

**Paper Title:** QCanvas: A Unified Multi-Framework Compilation and High-Performance Simulation Platform for Quantum Software Engineering

**Target Venue:** Springer LNCS (14–16 pages)
**Target Directory:** `research-papers/QCanvas Tool/`
**Paper File:** `QCanvas-Tool-Paper.tex`

---

## Phase 1: Pre-Writing Research & Groundwork

- [x] Review QCanvas monorepo structure and documentation
- [x] Review QSim engine architecture (`quantum_simulator/qsim/`)
- [x] Review `quantum_converters/` module structure (Cirq, Qiskit, PennyLane -> QASM)
- [x] Review `docs/project-scope.md`, `docs/Description.md`, `docs/features.md`
- [x] Review `docs/qcanvas_python_sdk.md`
- [x] Review FastQubit API and FastQSim SDK docs
- [x] Review existing `Framework-Comparison/master_prompt.txt` for style reference
- [x] Read `docs/PERFORMANCE_METRICS.md` for empirical data to use in evaluation section
- [x] Read `docs/database-schema.md` for the platform architecture section
- [ ] Read the QCanvas FYP report PDF (`QCanvas Tool/QCanvas/S25-038-D-QCanvas.pdf`)
- [ ] Read the QSim FYP report PDF (`QCanvas Tool/QSim/FYP2-FinalReport-F25-203-D-QSim.pdf`)
- [x] Collect concrete performance numbers from benchmark results

---

## Phase 2: Paper Drafting — Section by Section

### Abstract (~200 words)
- [x] Draft abstract covering: problem (SDK fragmentation), solution (QCanvas unified stack), key features (4 layers), empirical scope, and practical impact
- [x] Add keywords: quantum compilation, multi-framework interoperability, OpenQASM 3.0, NISQ, simulation platform

---

### Section 1 - Introduction (~1.5 pages)
- [x] Para 1: Motivation — SDK fragmentation and NISQ-era practitioner challenge
- [x] Para 2: The gap — existing tools are either compilers OR simulators, not unified
- [x] Para 3: QCanvas as the solution — the 4-layer unified stack
- [x] Para 4: Numbered contributions list (4 items)
- [x] Para 5: Paper outline (one sentence per section)

---

### Section 2 - Related Work (~1 page)
- [x] 2.1 Multi-framework compilers: tket, pytket, Qiskit transpiler plugins
- [x] 2.2 Web-based quantum IDEs: IBM Quantum Composer, Quirk, Strangeworks
- [x] 2.3 Quantum simulation frameworks: Qiskit Aer, Cirq simulator, PennyLane device plugins
- [x] 2.4 Position QCanvas: differentiate as the only fully integrated platform

---

### Section 3 - Background (~0.75 pages)
- [x] 3.1 Quantum frameworks (Qiskit, Cirq, PennyLane) — one paragraph each
- [x] 3.2 OpenQASM 3.0 — why it was chosen as the universal IR
- [x] 3.3 AST-based compilation — brief conceptual framing

---

### Section 4 - System Architecture (~2.5 pages)
- [x] 4.1 Design Principles (framework neutrality, IR-first, modular backends)
- [x] 4.2 Four-layer architecture diagram (Fig. 1 — TikZ)
- [x] 4.3 End-to-end data flow: Source -> Adapter -> Compilation Engine -> OpenQASM 3.0 -> QSim -> Results
- [x] 4.4 FastAPI orchestration layer (REST + WebSocket)
- [x] 4.5 Redis caching, PostgreSQL persistence, Docker deployment

---

### Section 5 - Multi-Framework Compilation Plane (~2.5 pages)
- [x] 5.1 Ingestion adapters: QuantumCircuit (Qiskit), cirq.Circuit (Cirq), QNode (PennyLane)
- [x] 5.2 Gate vocabulary normalization across gate sets
- [x] 5.3 OpenQASM 3.0 Code Generation — Iteration I and Iteration II features
- [x] 5.4 Advanced features: multi-control ctrl(n)@, power pow(k)@, negctrl, complex types, while loops, subroutines
- [x] 5.5 If-else and control flow handling across frameworks
- [x] 5.6 Static analysis: syntax and semantic validation, error surfacing
- [x] SDK compile() API usage described

---

### Section 6 - High-Performance Execution Engine: QSim (~2.5 pages)
- [x] 6.1 QSim as QCanvas's native runtime (not a third-party integration)
- [x] 6.2 OpenQASM 3.0 parser within QSim (pyqasm -> Qasm3Module AST)
- [x] 6.3 Visitor pattern for circuit reconstruction (CirqVisitor, QiskitVisitor, PennylaneVisitor)
- [x] 6.4 Simulation backends (statevector, density matrix, stabilizer)
- [x] 6.5 Pluggable backend factory (get_backend)
- [x] 6.6 Unified API: RunArgs/SimResult with code example
- [x] 6.7 Orchestration pipeline: Parse -> Visit -> Execute

---

### Section 7 - Developer Workbench & Python SDK (~1.5 pages)
- [x] 7.1 Web IDE: Monaco editor, D3 circuit rendering, multi-file workspace, real-time validation
- [x] 7.2 Keyboard shortcut system
- [x] 7.3 Python SDK (qcanvas-sdk): compile() and compile_and_execute() APIs
- [x] 7.4 Example library: 25+ pre-built quantum algorithms across 3 frameworks
- [x] 7.5 Cirq-RAG Code Assistant

---

### Section 8 - Performance Evaluation (~3 pages)
- [x] 8.1 Experimental setup (12 algorithms, 3 frameworks, methodology)
- [x] 8.2 Compilation latency table (Table 2)
- [x] 8.3 QSim simulation scalability (Table 3 — qubit sweep)
- [x] 8.4 Cross-framework correctness: JSD equivalence verification
- [x] 8.5 Web IDE and API performance targets

---

### Section 9 - Discussion (~1 page)
- [x] 9.1 Design trade-offs: OpenQASM 3.0 as IR
- [x] 9.2 Known compilation edge cases (PennyLane multi-controlled gate decomposition)
- [x] 9.3 Extensibility: how new frameworks/backends can be added
- [x] 9.4 Limitations: classical simulation only; statevector ceiling; SDK monorepo; Cirq-RAG AWS dependency

---

### Section 10 - Conclusion (~0.5 pages)
- [x] Restate 4 contributions in 4 sentences
- [x] One sentence on future work (QPU dispatch, OpenPulse, Braket/Stim support)

---

## Phase 3: Figures, Tables & References

- [x] Fig. 1 — 4-Layer Architecture Diagram (TikZ in LaTeX)
- [x] Table 1 — Algorithm test suite (12 algorithms)
- [x] Table 2 — Compilation latency (mean +/- std, 12 algorithms x 3 frameworks)
- [x] Table 3 — QSim simulation performance targets by qubit count
- [ ] Fig. 2 — Web IDE Screenshot (to be added when available)
- [ ] Table 4 — Feature comparison vs related tools (optional, can be added)
- [x] References list (10 references in LNCS numbered format)

---

## Phase 4: Review & Polish

- [x] Verify all quantitative claims have concrete numbers
- [x] Confirm every figure/table is cited inline before it appears
- [x] Apply all LNCS style rules (numbered non-bold headings, format: "4.1 Title" not "4.1. Title")
- [x] Remove filler phrases and hedging language
- [x] QSim always referred to as QCanvas's execution engine, never as separate project
- [ ] Final length check: compile LaTeX and verify 14-16 pages
- [ ] Proofread for passive-voice overuse

---

## Key Decisions Log

| Decision | Choice | Rationale |
|---|---|---|
| Format | Springer LNCS | Consistent with existing research papers in repo |
| Paper Type | Tool / Systems paper | Presents QCanvas+QSim as an implemented platform |
| Framing | Single unified project | QCanvas (compilation) + QSim (execution) = one end-to-end stack |
| IR Choice | OpenQASM 3.0 | Lingua franca of quantum programs; supports full Iteration II features |
| Evaluation style | Empirical benchmarking + correctness | Matches tool paper conventions at LNCS venues |
| Architecture diagram | TikZ inline | No external image dependency |
