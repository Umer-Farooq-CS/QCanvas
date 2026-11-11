# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased] - workshop-polishing (2026-11-12)

### Fixed
- **Login:** stale sessions. Tokens expired after 30 min while the UI stayed "logged in", so files didn't load.
  Sessions now refresh while active, and expired sessions redirect to login.
- **Explorer:** the sidebar disappeared on narrow windows and never came back. It now restores automatically,
  and there's a toggle button plus Ctrl+B.
- **Converters/simulator:** wrong histograms. Fake gates were injected into Cirq and PennyLane QASM, and there
  were Qiskit/Cirq parser crashes, silent operation drops, gate gaps across backends, broken feed-forward and
  inconsistent bit order. All shipped examples now match on cirq/qiskit/pennylane.
- **SDK:** `qcanvas.compile(QuantumCircuit)` failed with "expected string".
- **Startup:** a fresh deploy crashed because SQLAlchemy 2.1 defaults to psycopg 3. The driver is now pinned to psycopg2.
- **Editor:** frontend bugs including dead shortcuts, failed deletes/renames that went unreported, lost typing
  on save, a Monaco QASM highlighting crash, and the `/profile` redirect bounce.
- **Gamification:** clients could award themselves XP; the first-simulation bonus never applied.

### Security
- User code (hybrid mode and `/convert`) runs in an isolated, killable child process with secrets stripped and
  dangerous imports blocked. Previously `while True` hung the server and `import os` worked.
- The shared demo account is replaced by private, temporary guest workspaces.
- Rate limits are keyed by user or real client IP (trusted proxies only), auth limits by IP. Logout revokes
  tokens, and sessions have an absolute cap.
- The qubit cap is enforced on the built circuit; FastQSim credentials are never exposed to user code.
- A committed FastQSim token cache was removed. **The token must be rotated.**

### Performance
- Multiple uvicorn workers; compiling and simulating run off the event loop with bounded queues.
- Audit logging is batched off the request path; the DB pool is configurable.
- `/app` first-load JS: 551 kB → 238 kB.

### Changed
- Public pages (landing, docs, examples, about, auth, profile) are redesigned on a shared palette; fabricated
  content was removed.
- Repo cleanup: removed the unused Vite/Express template and one-off scripts; reorganized backend scripts,
  legacy tests and archives.
- License metadata now matches `LICENSE` (proprietary).

## [0.1.0] - 2026-05-08

### Added
- **Initial public SDK release**: `qcanvas-sdk` distribution with `compile()` and `compile_and_execute()` API
- Support for **Cirq** circuits → OpenQASM 3.0 via `convert_cirq_to_qasm3()`
- Support for **Qiskit** circuits → OpenQASM 3.0 via `convert_qiskit_to_qasm3()`
- Support for **PennyLane** QNodes → OpenQASM 3.0 via `convert_pennylane_to_qasm3()`
- Framework auto-detection: `compile(circuit)` infers framework from object type
- Result types: `SimulationResult` and `HybridExecutionResult` dataclasses
- Graceful fallbacks: imports work with or without optional framework dependencies
- Package distributed via PyPI with optional extras: `[cirq]`, `[qiskit]`, `[pennylane]`, `[all]`
- GitHub Actions CI workflow for build/test and automated publish to TestPyPI and PyPI on tags
- Basic smoke tests for import and API validation

### Notes
- Backend runtime (`qcanvas_runtime`) and FastAPI server are separate distributions
- The wheel includes `quantum_converters` but does not require moving repo files
- Backward compatibility shim: if `quantum_converters` is not available, falls back to bundled runtime

## [0.1.2] - 2026-05-08

### Changed
- Bumped package version again to avoid TestPyPI file-name reuse during upload
