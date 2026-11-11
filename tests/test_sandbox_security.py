"""
In-process tests for qcanvas/sandbox.py (defence-in-depth layer) and the
cached FastQSim online-mode lookup in qcanvas/qsim.py.

These run execute_sandboxed() directly (fast); the process-isolation tests
live in tests/test_isolated_exec.py.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

sandbox = pytest.importorskip("qcanvas.sandbox")
from qcanvas import qsim as qsim_wrapper  # noqa: E402


def run(code: str):
    return sandbox.execute_sandboxed(code, timeout=0)


# The hybrid examples shipped in frontend/lib/store.ts (initialFiles) and
# frontend/app/examples/page.tsx ("Hybrid" category), verbatim.
HYBRID_EXAMPLE = '''# Hybrid CPU-QPU Execution Example
# Switch to "Hybrid" mode in the toolbar to run this code!

import cirq
from qcanvas import compile
import qsim

# Create a Bell state circuit
q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1]),
    cirq.measure(q[0], q[1], key='result')
])

print("Circuit created:")
print(circuit)
print()

# Compile circuit to OpenQASM 3.0
qasm = compile(circuit, framework="cirq")
print("Generated QASM:")
print(qasm)
print()

# Run multiple simulations in a loop
print("Running 3 simulations...")
for i in range(3):
    result = qsim.run(qasm, shots=100, backend="cirq")
    print(f"Run {i+1}: {result.counts}")
    print(f"  Probabilities: {result.probabilities}")

print()
print("Hybrid execution complete!")
'''

QRNG_EXAMPLE = '''import cirq

from qcanvas import compile
import qsim

print("=== Quantum Random Number Generator (QRNG) ===\\n")

# Create a simple circuit that generates one random bit
# H gate creates superposition, measurement collapses to 0 or 1
q = cirq.LineQubit(0)
circuit = cirq.Circuit([
    cirq.H(q),
    cirq.measure(q, key='random_bit')
])

# Compile to QASM
qasm = compile(circuit, framework="cirq")
print(f"QRNG Circuit QASM:\\n{qasm}\\n")

# Generate 10 random bits
print("Generating 10 random bits:")
random_bits = []
for i in range(10):
    result = qsim.run(qasm, shots=1, backend="cirq")
    # Extract the bit value (0 or 1)
    bit = list(result.counts.keys())[0]
    random_bits.append(bit)
    print(f"  Bit {i+1}: {bit}")

print(f"\\nRandom bit sequence: {''.join(random_bits)}")
'''


def test_hybrid_example_runs():
    r = run(HYBRID_EXAMPLE)
    assert r.success, (r.error, r.stderr)
    assert len(r.simulation_results) == 3
    assert "Hybrid execution complete!" in r.stdout
    for sim in r.simulation_results:
        assert set(sim["counts"]) <= {"00", "11"}


def test_qrng_example_runs():
    r = run(QRNG_EXAMPLE)
    assert r.success, (r.error, r.stderr)
    assert len(r.simulation_results) == 10
    assert "Random bit sequence:" in r.stdout


def test_common_legit_imports_still_work():
    code = (
        "import math, cmath, random, itertools, functools, collections, json, re, copy\n"
        "import statistics, fractions, decimal, datetime, time, typing, dataclasses, operator\n"
        "import numpy as np\n"
        "import cirq\n"
        "import qiskit\n"
        "from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister\n"
        "import pennylane as qml\n"
        "from pennylane import numpy as pnp\n"
        "import numpy.linalg\n"
        "from numpy.linalg import norm\n"
        "from qcanvas import compile\n"
        "import qsim\n"
        "from collections import Counter\n"
        "print(np.array([1, 2]).sum(), norm(np.array([3.0, 4.0])), math.pi > 3, operator.add(1, 2))\n"
        "print(isinstance(np, object), Counter('aab').most_common(1))\n"
        "class Model:\n"
        "    def __init__(self):\n"
        "        self._w = pnp.array([0.1], requires_grad=True)\n"
        "print(Model()._w)\n"
    )
    r = run(code)
    assert r.success, (r.error, r.stderr)


def test_qiskit_circuit_with_injected_compile_runs():
    # Uses the injected global `compile` (qcanvas.core.compile).
    code = (
        "from qiskit import QuantumCircuit\n"
        "import qsim\n"
        "qc = QuantumCircuit(2, 2)\n"
        "qc.h(0)\n"
        "qc.cx(0, 1)\n"
        "qc.measure([0, 1], [0, 1])\n"
        "qasm = compile(qc, framework='qiskit')\n"
        "r = qsim.run(qasm, shots=50, backend='qiskit')\n"
        "print(r.counts)\n"
    )
    r = run(code)
    assert r.success, (r.error, r.stderr)
    assert len(r.simulation_results) == 1


ESCAPES = {
    "import os": "import os\nos.system('echo PWNED')",
    "from os import system": "from os import system",
    "import os.path": "import os.path",
    "import sys": "import sys",
    "import subprocess": "import subprocess",
    "import shutil": "import shutil",
    "import ctypes": "import ctypes",
    "import importlib": "import importlib\nimportlib.import_module('os')",
    "import pickle": "import pickle",
    "import socket": "import socket",
    "import multiprocessing": "import multiprocessing",
    "import threading": "import threading",
    "import signal": "import signal",
    "import builtins": "import builtins\nbuiltins.open",
    "import gc": "import gc",
    "import inspect": "import inspect",
    "import timeit": "import timeit\ntimeit.timeit('import os')",
    "import string": "import string\nstring.Formatter().get_field('0.__class__', [()], {})",
    "__import__ name": "__import__('os')",
    "__builtins__": "__builtins__['__import__']('os')",
    "private module attr": "import random\nrandom._os.system('echo PWNED')",
    "subclasses walk": "().__class__.__base__.__subclasses__()",
    "function globals": "import cirq\ncirq.Circuit.__init__.__globals__['os']",
    "print.__self__": "print.__self__.open('/etc/passwd')",
    "traceback frames": "try:\n    1/0\nexcept Exception as e:\n    e.__traceback__.tb_frame.f_globals",
    "generator frame": "g = (i for i in [1])\ng.gi_frame.f_back",
    "qcanvas.os": "import qcanvas\nqcanvas.os.system('echo PWNED')",
    "injected qcanvas global .os": "qcanvas.os.system('echo PWNED')",
    "qsim.os": "import qsim\nqsim.os.system('echo PWNED')",
    "numpy ctypes": "import numpy as np\nnp.ctypeslib.ctypes",
    "from numpy import ctypeslib": "from numpy import ctypeslib",
    "numpy pickle load": "import numpy as np\nnp.load('x.npy', allow_pickle=True)",
    "operator.attrgetter": "import operator\noperator.attrgetter('__class__')(())",
    "eval": "eval('1')",
    "exec": "exec('import os')",
    "open": "open('/etc/passwd')",
    "getattr": "getattr((), '__class__')",
    "compile() string -> converter exec": (
        "compile('import os\\nos.system(\"echo PWNED\")\\nimport cirq\\nc = cirq.Circuit()', framework='cirq')"
    ),
    "module mutation": "import math\nmath.pi = 3",
}


@pytest.mark.parametrize("name", sorted(ESCAPES))
def test_escape_is_blocked(name):
    r = run(ESCAPES[name])
    assert not r.success, f"{name} was allowed"
    assert "PWNED" not in (r.stdout or "")


def test_security_errors_have_line_numbers():
    r = run("x = 1\ny = 2\nimport os\n")
    assert r.error_type == "SecurityViolationError"
    assert r.error_line == 3
    r = run("a = 1\nb = ().__class__\n")
    assert r.error_type == "SecurityViolationError"
    assert r.error_line == 2


def test_import_hook_is_removed_after_run():
    import builtins

    before = builtins.__import__
    run("import math\nprint(math.sqrt(4))")
    run("import os")
    assert builtins.__import__ is before
    assert sys.stdout is sys.__stdout__ or not isinstance(sys.stdout, sandbox.OutputCapture)


def test_in_process_timeout_returns_instead_of_hanging():
    import time

    started = time.monotonic()
    r = sandbox.execute_sandboxed("x = 0\nwhile x < 10**7:\n    x += 1\n", timeout=0.2)
    elapsed = time.monotonic() - started
    assert elapsed < 5
    if not r.success:
        assert r.error_type == "TimeoutError"
    # stdout must not stay hijacked by the timed-out thread
    assert not isinstance(sys.stdout, sandbox.OutputCapture)


def test_validate_code_reports_blocked_constructs():
    result = sandbox.validate_code("import os\nx = ().__class__\nimport numpy.ctypeslib\n")
    assert not result["valid"]
    joined = " ".join(result["errors"])
    assert "os" in joined and "__class__" in joined and "ctypeslib" in joined
    assert sandbox.validate_code(HYBRID_EXAMPLE)["valid"]


def test_dangerous_imports_blocked_by_default():
    from config import config

    assert config.HYBRID_BLOCK_DANGEROUS_IMPORTS is True
    for module in ("os", "sys", "subprocess", "shutil", "ctypes", "importlib", "pickle", "socket",
                   "multiprocessing", "threading", "signal", "builtins"):
        assert module in config.HYBRID_BLOCKED_MODULES, module
    for module in ("numpy", "math", "cirq", "qiskit", "pennylane", "random", "itertools", "qsim", "qcanvas"):
        assert module not in config.HYBRID_BLOCKED_MODULES, module


# ---------------------------------------------------------------------------
# FastQSim online-mode lookup is cached
# ---------------------------------------------------------------------------

@pytest.fixture
def fresh_online_mode(monkeypatch):
    monkeypatch.delenv("FASTQSIM_ONLINE_MODE", raising=False)
    monkeypatch.setattr(qsim_wrapper, "_online_mode_cache", None)
    monkeypatch.setattr(qsim_wrapper, "_online_mode_override", None)
    calls = []

    def fake_lookup():
        calls.append(1)
        return True

    monkeypatch.setattr(qsim_wrapper, "_lookup_online_mode_ssm", fake_lookup)
    return calls


def test_online_mode_ssm_lookup_is_cached(fresh_online_mode, monkeypatch):
    monkeypatch.setenv("FASTQSIM_ONLINE_MODE_CACHE_SECONDS", "300")
    assert qsim_wrapper.resolve_online_mode() is True
    assert qsim_wrapper.resolve_online_mode() is True
    assert qsim_wrapper.resolve_online_mode() is True
    assert len(fresh_online_mode) == 1


def test_online_mode_env_short_circuits_ssm(fresh_online_mode, monkeypatch):
    monkeypatch.setenv("FASTQSIM_ONLINE_MODE", "false")
    assert qsim_wrapper.resolve_online_mode() is False
    monkeypatch.setenv("FASTQSIM_ONLINE_MODE", "true")
    assert qsim_wrapper.resolve_online_mode() is True
    assert fresh_online_mode == []


def test_online_mode_override_wins(fresh_online_mode):
    qsim_wrapper.set_online_mode_override(False)
    try:
        assert qsim_wrapper.resolve_online_mode() is False
        assert fresh_online_mode == []
    finally:
        qsim_wrapper.set_online_mode_override(None)
