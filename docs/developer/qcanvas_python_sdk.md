# QCanvas Python SDK (PyPI) — What `import qcanvas` is today, and how to make it a real SDK

## Goal of this document

This document explains:

- **What the current `qcanvas` package import is** in this repository (what it does, why it exists).
- **Why it is not yet a “proper SDK”** that can be published to PyPI and used from any machine/project.
- **How to convert it into a real, versioned Python SDK** (package boundaries, public API, internal parts, build + publish workflow).

It is written to be the reference design for extracting the Python-facing “developer SDK” from the larger QCanvas web platform.

---

## What `import qcanvas` is in this repo (current state)

### The short version

In the current repository, the top-level Python package `qcanvas/` is a **thin import shim** designed for local development.

It exists so user code can do:

```python
from qcanvas import compile, compile_and_execute
```

…even though the *real implementation* lives in `backend/qcanvas_runtime/`.

### The exact behavior

Open `qcanvas/__init__.py` in this repo and you’ll see three key things:

1. **It computes the repo root** based on the location of `qcanvas/__init__.py`.
2. **It inserts `backend/` onto `sys.path`** at runtime.
3. **It imports and re-exports runtime functions/types** from `qcanvas_runtime`:
   - `qcanvas_runtime.core.compile`
   - `qcanvas_runtime.core.compile_and_execute`
   - `qcanvas_runtime.result.SimulationResult`
   - `qcanvas_runtime.result.HybridExecutionResult`

Conceptually:

```text
user code
  │
  ▼
import qcanvas
  │  (mutates sys.path to include ./backend)
  ▼
imports backend/qcanvas_runtime/*
  │
  ▼
compile() → quantum_converters → OpenQASM 3.0 string
compile_and_execute() → compile() + qcanvas_runtime.qsim.run()
```

### Why it was built this way

This shim is useful when:

- you run code **from the monorepo root**, and
- you want a “nice import” (`from qcanvas import compile`) without turning the backend runtime into a separately installed wheel.

It also aligns with the project’s “Hybrid CPU–QPU Execution” UX described in the Memory Bank (compile locally, run via QSim):

```python
import cirq
from qcanvas import compile
import qsim
```

### What is the “compilation package” behind it?

`qcanvas_runtime.core.compile()` ultimately calls converters from:

- `quantum_converters.converters.*_to_qasm`

Those converters parse framework code (or accept circuit-like inputs) and produce **OpenQASM 3.0** output, which is QCanvas’s universal IR.

So, *today’s* `qcanvas.compile()` is a **Python API wrapper** over the internal compilation engine.

---

## Why the current `qcanvas` package is not a PyPI-ready SDK

The current approach breaks the expectations of a real SDK installed via `pip install qcanvas` because:

### 1) It depends on monorepo-relative paths

Adding `./backend` to `sys.path` assumes a specific folder layout on disk. That layout does not exist when installed as a wheel from PyPI.

### 2) It merges “app internals” and “SDK API”

`backend/qcanvas_runtime` is a runtime module used by the FastAPI backend and the sandbox. It is not packaged as a standalone installable distribution in this repo’s root packaging metadata.

### 3) It has unclear dependency boundaries

The SDK function `compile()` relies on:

- `quantum_converters` (your compilation engine)
- one or more quantum frameworks (Cirq/Qiskit/PennyLane) depending on inputs

If you publish without a dependency strategy, users will face import errors or heavyweight installs.

### 4) Versioning and compatibility aren’t formalized

There are multiple `pyproject.toml` files in the repo (e.g., for other subprojects), and the root does not currently define a PyPI distribution for `qcanvas` itself.

---

## What “QCanvas SDK” should mean (scope)

To publish a clean SDK, you need a firm definition:

### SDK responsibilities (keep)

- **Compile** circuits/code to OpenQASM 3.0:
  - `qcanvas.compile(circuit_or_code, framework=...) -> str`
- **Optionally** run compiled QASM via QSim if the user has QSim installed:
  - `qcanvas.compile_and_execute(...) -> SimulationResult`
- Provide stable **result dataclasses/types**:
  - `SimulationResult`, `HybridExecutionResult`
- Provide safe(ish) **hybrid sandbox execution API** *only if you want it in the SDK*:
  - `qcanvas.sandbox.execute_sandboxed(code: str, ...) -> HybridExecutionResult`

### Not-SDK responsibilities (exclude)

These are platform/app concerns and should not be in the SDK distribution:

- FastAPI app, routes, DB models/migrations, authentication
- Next.js frontend
- Docker compose / deployment scripts
- Websocket managers, audit logging middleware, etc.

---

## Recommended packaging strategy (the cleanest path)

### Recommendation

Create a **dedicated Python package distribution** for the SDK using a `src/` layout, and ensure it imports everything by **normal Python packaging**, not `sys.path` hacks.

You have two viable options:

#### Option A (best long-term): multi-distribution “Python packages” in a monorepo

Publish separate wheels:

- **`qcanvas`** (the public SDK)
- **`quantum-converters`** (compilation engine; already a package folder `quantum_converters/`)
- **`qsim`** (already appears to be `quantum_simulator/qsim/` and is used as `import qsim`)

Pros:
- clean separation and independent versioning
- users can install only what they need

Cons:
- more release automation (3 projects)

#### Option B (fastest initial release): single distribution bundling runtime + converters

Publish one wheel:

- **`qcanvas`** includes:
  - `qcanvas` public API
  - `qcanvas_runtime` code moved under `qcanvas.runtime` (or vendored)
  - `quantum_converters` included (or refactored into `qcanvas.converters`)

Pros:
- easiest for users: `pip install qcanvas`
- one version to manage

Cons:
- bigger wheel; heavier dependencies and slower installs
- harder to reuse converters without installing everything

This document assumes **Option A** as the target architecture (best SDK design), but the “parts” and APIs are similar either way.

---

## Target SDK: public API design

### Core API (stable surface)

The SDK should provide a small, stable top-level API:

```python
from qcanvas import compile, compile_and_execute
from qcanvas import SimulationResult, HybridExecutionResult
```

Recommended signatures:

- `compile(circuit: Any, framework: str | None = None, /, *, options: CompileOptions | None = None) -> str`
- `compile_and_execute(circuit: Any, framework: str | None = None, /, *, shots: int = 1024, backend: str = "cirq", options: CompileOptions | None = None) -> SimulationResult`

Where:
- `framework ∈ {"cirq","qiskit","pennylane"}` (exactly what you support today)
- `backend ∈ {"cirq","qiskit","pennylane"}` (as per `backend/qcanvas_runtime/qsim.py`)

### Optional submodules (still public, but not “top-level”)

To keep the root namespace clean:

- `qcanvas.results` (dataclasses + helpers)
- `qcanvas.sandbox` (hybrid execution sandbox, if you ship it)
- `qcanvas.version` (SDK version + compatibility helpers)

### What to avoid

- Don’t expose `qcanvas_runtime.*` as public imports in the SDK.
- Don’t require users to import from `backend.*` or `quantum_converters.*` directly for common use.
- Don’t make `qcanvas.compile()` depend on being run inside the monorepo.

---

## Target SDK: internal architecture (what parts it will have)

Below is a recommended module breakdown for the SDK distribution.

### 1) `qcanvas` (public facade)

**Purpose**: friendly imports, stable API, minimal code.

Contains:
- `qcanvas/__init__.py`: re-export public functions/types
- `qcanvas/api.py` (or `qcanvas/_api.py`): actual implementation of public functions

### 2) `qcanvas.compile` (compilation orchestration)

**Purpose**: convert from “user objects” (circuits, code strings) to OpenQASM 3.0.

Contains:
- framework detection (currently `_detect_framework`)
- input normalization (circuit → code string where needed)
- calling the converter engine

The converter engine should be *a dependency*, not a relative import to a monorepo folder.

### 3) `qcanvas.results` (typed outputs)

**Purpose**: stable data types returned by the SDK.

Contains:
- `SimulationResult`
- `HybridExecutionResult`
- `to_dict()` / `from_dict()` helpers (already exist)

### 4) `qcanvas.execution` (optional convenience)

**Purpose**: glue to run OpenQASM 3.0 via QSim.

Contains:
- `run(qasm: str, shots: int, backend: str) -> SimulationResult`

Design note:
- This should be an **optional dependency** on `qsim` so that `pip install qcanvas` can remain lightweight if desired.

### 5) `qcanvas.sandbox` (optional, security-sensitive)

**Purpose**: safe(ish) execution of user Python in “hybrid mode”.

Contains:
- `execute_sandboxed()`
- import/builtin restrictions
- output capture

Important:
- Publishing this in an SDK means you need to treat it like a security boundary (document limits, threat model, and defaults).

### 6) `qcanvas.exceptions`

**Purpose**: consistent error handling for SDK consumers.

Recommended exception hierarchy:

- `QCanvasError(Exception)`
  - `UnsupportedFrameworkError(QCanvasError)`
  - `CompilationError(QCanvasError)`
  - `ExecutionError(QCanvasError)`
  - `SandboxViolationError(QCanvasError)`
  - `MissingOptionalDependencyError(QCanvasError)` (e.g., `qsim` not installed)

### 7) `qcanvas._compat` (optional)

**Purpose**: compatibility shims for differences across Cirq/Qiskit/PennyLane versions or object types.

---

## Dependency strategy (critical for PyPI)

### The problem

Quantum frameworks are heavy, and different users want different subsets.

### The recommended solution: extras

Publish the SDK with a minimal default install, plus extras:

- `pip install qcanvas` (minimal core, compilation engine only if you choose)
- `pip install qcanvas[cirq]`
- `pip install qcanvas[qiskit]`
- `pip install qcanvas[pennylane]`
- `pip install qcanvas[qsim]`
- `pip install qcanvas[all]`

How this maps to runtime behavior:

- If user passes a Cirq circuit object to `compile()`, but `cirq` isn’t installed, raise `MissingOptionalDependencyError` with an actionable message.

### Pinning vs ranges

For an SDK, prefer **version ranges** instead of strict pins, for example:

- `cirq>=1.2,<2`
- `qiskit>=0.45,<1` (or whatever you target)
- `pennylane>=0.34,<1`

Use CI to validate supported versions.

---

## PyPI packaging layout (recommended)

### Use `src/` layout

Example:

```text
python-sdk/
  qcanvas-sdk/
    pyproject.toml
    README.md
    LICENSE
    src/
      qcanvas/
        __init__.py
        api.py
        compile.py
        results.py
        execution.py
        sandbox.py
        exceptions.py
        py.typed
    tests/
      test_compile.py
      ...
```

Why `src/`:
- prevents accidental imports from the repo root during development
- ensures packaging works exactly like PyPI installs

### Where does existing code go?

Map current modules to SDK modules:

- `backend/qcanvas_runtime/core.py` → `src/qcanvas/compile.py` and/or `src/qcanvas/api.py`
- `backend/qcanvas_runtime/result.py` → `src/qcanvas/results.py`
- `backend/qcanvas_runtime/qsim.py` → `src/qcanvas/execution.py` (but keep it optional)
- `backend/qcanvas_runtime/sandbox.py` → `src/qcanvas/sandbox.py` (optional)

And the compilation engine:

- `quantum_converters/` becomes either:
  - a separate published dist (`quantum-converters`) and `qcanvas` depends on it, **or**
  - bundled inside the `qcanvas` dist (Option B)

---

## Build & publish workflow (PyPI)

This is the standard, repeatable release process for the SDK distribution.

### 1) Choose the package name

Decide what users will install:

- distribution name (PyPI): `qcanvas` (ideal) or `qcanvas-sdk` (if `qcanvas` is taken)
- import name (Python): `qcanvas`

Important:
- PyPI “project name” can differ from import name, but it’s cleaner when they match.

### 2) Create `pyproject.toml` for the SDK

Use modern packaging (setuptools or hatchling). Include:

- name, version, description
- dependencies + extras
- python requires
- license + classifiers
- package discovery for `src/`
- include `py.typed` if you ship typing

### 3) Add CI checks (minimum)

At least:

- `python -m build` (ensures wheel/sdist builds)
- `pip install dist/*.whl` in a clean env
- minimal smoke tests:
  - `import qcanvas`
  - `qcanvas.compile("...")` for string inputs or simple circuits (depending on extras)

### 4) Publish to TestPyPI first

Typical steps:

- build: `python -m build`
- upload to test: `twine upload --repository testpypi dist/*`
- install from TestPyPI and run smoke tests

### 5) Publish to PyPI

Once validated:

- `twine upload dist/*`

### 6) Versioning policy

Use SemVer:

- **MAJOR**: breaking API changes (signature changes, moved imports)
- **MINOR**: new features, new optional backends/frameworks
- **PATCH**: bug fixes only

---

## SDK documentation that should ship with the package

To make it feel like a real SDK, include:

- **Quickstart** (compile + execute)
- **API reference** (functions, parameters, exceptions)
- **Optional dependency guide** (extras)
- **Compatibility matrix** (supported framework versions)
- **Security notes** (if sandbox ships)

You already have a strong starting point in `docs/api/hybrid-execution-results.md`; the SDK can reuse and adapt that content.

---

## Migration plan from today’s shim to a real SDK

This is the concrete step-by-step refactor path.

### Phase 1 — make SDK installable without changing behavior

- Move code out of `backend/qcanvas_runtime/` into an installable package location (`src/qcanvas/...`).
- Replace `sys.path` mutation in `qcanvas/__init__.py` with normal imports.
- Ensure `compile()` still calls the same converter functions.

Deliverable:
- `pip install -e python-sdk/qcanvas-sdk` works
- existing app can still run (temporarily, by importing the SDK)

### Phase 2 — decouple from backend app

- Backend should depend on the SDK (not the other way around).
- Update backend imports from `qcanvas_runtime.*` to `qcanvas.*`.

Deliverable:
- backend continues working, but `qcanvas` is now a real package

### Phase 3 — publish on PyPI

- Add release automation (GitHub Actions) for tag-based releases.
- Publish to TestPyPI then PyPI.

### Phase 4 — split into multiple distributions (optional but recommended)

If you choose Option A:

- publish `quantum-converters`
- publish `qcanvas`
- keep `qsim` as separate project (already appears separate)

Deliverable:
- clean dependency graph and small installs

---

## What success looks like (definition of done)

You know you have a proper SDK when:

- A user on a fresh machine can do:

```bash
pip install qcanvas[qsim,cirq]
```

and then:

```python
import cirq
from qcanvas import compile
import qsim

q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit(cirq.H(q0), cirq.CNOT(q0, q1), cirq.measure(q0, q1, key="m"))
qasm = compile(circuit, framework="cirq")
result = qsim.run(qasm, shots=1000, backend="cirq")
print(result.counts)
```

- No part of the SDK relies on monorepo-relative paths like `./backend`.
- The backend app imports the SDK like any other dependency.
- The wheel contains only SDK code (not the entire web app).

---

## Appendix: Current repo modules relevant to the SDK

These are the current folders/files that form the SDK “core” today:

- **Shim API**
  - `qcanvas/__init__.py` (sys.path hack + re-export)
- **Runtime implementation**
  - `backend/qcanvas_runtime/core.py` (compile + compile_and_execute)
  - `backend/qcanvas_runtime/result.py` (SimulationResult, HybridExecutionResult)
  - `backend/qcanvas_runtime/qsim.py` (qsim wrapper used inside sandbox)
  - `backend/qcanvas_runtime/sandbox.py` (restricted execution environment)
- **Compilation engine**
  - `quantum_converters/` (Cirq/Qiskit/PennyLane → OpenQASM 3.0)
- **Execution engine dependency**
  - `quantum_simulator/qsim/` (installed as `qsim`, executes OpenQASM 3.0)

