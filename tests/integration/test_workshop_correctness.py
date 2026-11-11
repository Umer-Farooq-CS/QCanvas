"""
Cross-framework correctness tests for the workshop.

Every example program the IDE ships (frontend/lib/store.ts, frontend/lib/fileTemplates.ts,
frontend/app/examples/page.tsx -- non-hybrid ones) plus a few textbook circuits is
compiled from SOURCE TEXT to OpenQASM 3 with the same converter functions the backend's
ConversionService uses, then simulated with qsim.run_qasm on all three backends
(cirq, qiskit, pennylane). The measured distribution must match the distribution
derived by hand from the circuit (see tests/integration/workshop_programs.py).

Run as a script to print the example x backend table:
    python tests/integration/test_workshop_correctness.py
"""

import math
import os
import subprocess
import sys
import zlib

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

qsim = pytest.importorskip("qsim")
pytest.importorskip("cirq")
pytest.importorskip("qiskit")
pytest.importorskip("pennylane")

from qsim import RunArgs, run_qasm  # noqa: E402
from qsim.core.exceptions import QSimError, UnsupportedBackend  # noqa: E402

from quantum_converters.converters.cirq_to_qasm import CirqToQASM3Converter, convert_cirq_to_qasm3  # noqa: E402
from quantum_converters.converters.pennylane_to_qasm import (  # noqa: E402
    PennyLaneToQASM3Converter, convert_pennylane_to_qasm3,
)
from quantum_converters.converters.qiskit_to_qasm import QiskitToQASM3Converter, convert_qiskit_to_qasm3  # noqa: E402
from tests.integration.workshop_programs import PROGRAMS, PROGRAMS_BY_ID  # noqa: E402

BACKENDS = ("cirq", "qiskit", "pennylane")
SHOTS = 4000
CONVERTERS = {
    "cirq": convert_cirq_to_qasm3,
    "qiskit": convert_qiskit_to_qasm3,
    "pennylane": convert_pennylane_to_qasm3,
}

_QASM_CACHE = {}


def compile_program(program):
    key = program["id"]
    if key not in _QASM_CACHE:
        _QASM_CACHE[key] = CONVERTERS[program["framework"]](program["code"]).qasm_code
    return _QASM_CACHE[key]


def seed_for(*parts):
    return zlib.crc32("|".join(parts).encode()) & 0x7FFFFFFF


def simulate(qasm, backend, shots=SHOTS, seed=None):
    return run_qasm(RunArgs(qasm_input=qasm, backend=backend, shots=shots, seed=seed))


def total_variation(counts, expected):
    total = sum(counts.values())
    keys = set(counts) | set(expected)
    return 0.5 * sum(abs(counts.get(k, 0) / total - expected.get(k, 0.0)) for k in keys)


def check_distribution(counts, expected, shots=SHOTS):
    """Noiseless simulators: no outcome outside the support, and TVD within sampling noise."""
    assert sum(counts.values()) == shots, counts
    support = {k for k, p in expected.items() if p > 1e-12}
    width = len(next(iter(expected)))
    bad_width = [k for k in counts if len(k) != width]
    assert not bad_width, f"bitstrings have the wrong width (expected {width}): {bad_width[:5]}"
    unexpected = {k: v for k, v in counts.items() if k not in support}
    assert not unexpected, f"outcomes with probability 0 were observed: {dict(list(unexpected.items())[:8])}"
    k = len(support)
    tolerance = 0.02 + 2.0 * math.sqrt(k / (2 * math.pi * shots))
    tvd = total_variation(counts, expected)
    assert tvd < tolerance, f"TVD {tvd:.3f} >= {tolerance:.3f}; counts={dict(sorted(counts.items())[:16])}"
    return tvd


CHECKED = [p for p in PROGRAMS if p["expected"] is not None]
UNBOUND = ["templates/variational_ansatz_pennylane", "examples/quantum-neural-network"]


# ---------------------------------------------------------------------------
# The acceptance check
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("program", CHECKED, ids=[p["id"] for p in CHECKED])
def test_workshop_program_distribution(program, backend):
    qasm = compile_program(program)
    result = simulate(qasm, backend, seed=seed_for(program["id"], backend))
    check_distribution(result.counts, program["expected"])


@pytest.mark.integration
@pytest.mark.parametrize("backend", BACKENDS)
def test_uniform_qrng_bits_are_independent_fair_coins(backend):
    qasm = compile_program(PROGRAMS_BY_ID["examples/qrng-qiskit"])
    counts = simulate(qasm, backend, shots=8000, seed=seed_for("qrng", backend)).counts
    bits = np.array([[int(b) for b in k] * v for k, v in counts.items()], dtype=object)
    marginals = np.zeros(8)
    for key, n in counts.items():
        marginals += n * np.array([int(b) for b in key])
    marginals /= 8000
    assert np.all(np.abs(marginals - 0.5) < 0.04), marginals
    assert len(counts) > 200  # ~all 256 outcomes appear


@pytest.mark.integration
@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("framework", ["qiskit", "cirq", "pennylane"])
def test_parameterized_rotation_probability(framework, backend):
    """ry(pi/3)|0>: P(1) = sin^2(pi/6) = 0.25."""
    qasm = compile_program(PROGRAMS_BY_ID[f"extra/ry-pi3-{framework}"])
    counts = simulate(qasm, backend, shots=20000, seed=seed_for("ry", framework, backend)).counts
    p1 = counts.get("1", 0) / 20000
    assert abs(p1 - 0.25) < 0.015, p1


@pytest.mark.integration
@pytest.mark.parametrize("backend", BACKENDS)
def test_pennylane_rot_matches_pennylane_itself(backend):
    import pennylane as qml

    dev = qml.device("default.qubit", wires=1)

    @qml.qnode(dev)
    def reference():
        qml.Hadamard(wires=0)
        qml.Rot(np.pi / 2, np.pi / 3, 0.4, wires=0)
        qml.Hadamard(wires=0)
        return qml.probs(wires=0)

    probs = reference()
    expected = {"0": float(probs[0]), "1": float(probs[1])}
    qasm = compile_program(PROGRAMS_BY_ID["extra/rot-pennylane"])
    check_distribution(simulate(qasm, backend, seed=seed_for("rot", backend)).counts, expected)


@pytest.mark.integration
@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("pid", UNBOUND)
def test_unbound_parameters_fail_loudly(pid, backend):
    """Never invent values for parameters the program does not define."""
    qasm = compile_program(PROGRAMS_BY_ID[pid])
    assert "input " in qasm
    with pytest.raises(QSimError, match="has no value"):
        simulate(qasm, backend, shots=100)


def test_conversion_service_matches_direct_converters():
    """The backend's ConversionService must produce exactly the QASM tested above."""
    try:
        from backend.app.services.conversion_service import ConversionService
    except Exception as e:  # pragma: no cover - depends on backend deps
        pytest.skip(f"ConversionService not importable here: {e}")
    service = ConversionService()
    mismatches = []
    for program in PROGRAMS:
        response = service.convert_to_qasm(program["code"], program["framework"])
        if not response.get("success") or response.get("qasm_code") != compile_program(program):
            mismatches.append((program["id"], response.get("error")))
    assert not mismatches, mismatches


# ---------------------------------------------------------------------------
# Output layout: identical bit order on every backend
# ---------------------------------------------------------------------------

LAYOUT_CASES = {
    # c[0] is the LEFT-most character, whatever order the measurements happen in.
    "reversed_measure_order": ("""
qubit[2] q; bit[2] c;
x q[1];
c[1] = measure q[1];
c[0] = measure q[0];
""", {"01": 1.0}),
    "partial_measurement": ("""
qubit[3] q; bit[1] c;
x q[2];
c[0] = measure q[2];
""", {"1": 1.0}),
    "unmeasured_bit_reads_zero": ("""
qubit[2] q; bit[3] c;
x q[0];
c[0] = measure q[0];
c[1] = measure q[1];
""", {"100": 1.0}),
    "two_registers_in_declaration_order": ("""
qubit[2] q; bit[1] a; bit[1] b;
x q[1];
b[0] = measure q[1];
a[0] = measure q[0];
""", {"01": 1.0}),
    "no_measurement_samples_all_qubits": ("""
qubit[3] q;
x q[2];
""", {"001": 1.0}),
    "last_write_wins": ("""
qubit[1] q; bit[1] c;
x q[0];
c[0] = measure q[0];
x q[0];
c[0] = measure q[0];
""", {"0": 1.0}),
    "reset": ("""
qubit[2] q; bit[2] c;
h q[0];
cx q[0], q[1];
reset q[0];
c[0] = measure q[0];
c[1] = measure q[1];
""", {"00": 0.5, "01": 0.5}),
}


@pytest.mark.parametrize("backend", BACKENDS)
def test_wide_measured_circuit(backend):
    """20 measured qubits: terminal measurements must not each cost an extra wire."""
    n = 20
    body = "h q[0];\n" + "".join(f"cx q[{i}], q[{i + 1}];\n" for i in range(n - 1))
    body += "".join(f"c[{i}] = measure q[{i}];\n" for i in range(n))
    qasm = f'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[{n}] q;\nbit[{n}] c;\n' + body
    check_distribution(simulate(qasm, backend, seed=5).counts, {"0" * n: 0.5, "1" * n: 0.5})


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("case", sorted(LAYOUT_CASES))
def test_output_layout(case, backend):
    body, expected = LAYOUT_CASES[case]
    qasm = 'OPENQASM 3.0;\ninclude "stdgates.inc";\n' + body
    check_distribution(simulate(qasm, backend, seed=seed_for(case, backend)).counts, expected)


# ---------------------------------------------------------------------------
# Feed-forward (bug 6)
# ---------------------------------------------------------------------------

FEED_FORWARD = {
    "if_bit": ("""
qubit[2] q; bit[2] c;
h q[0];
c[0] = measure q[0];
if (c[0] == 1) { x q[1]; }
c[1] = measure q[1];
""", {"00": 0.5, "11": 0.5}),
    "if_else": ("""
qubit[2] q; bit[2] c;
h q[0];
c[0] = measure q[0];
if (c[0] == 1) { x q[1]; } else { h q[1]; }
c[1] = measure q[1];
""", {"11": 0.5, "00": 0.25, "01": 0.25}),
    "register_value": ("""
qubit[3] q; bit[2] c; bit[1] d;
x q[0];
h q[1];
c[0] = measure q[0];
c[1] = measure q[1];
if (c == 3) { x q[2]; }
d[0] = measure q[2];
""", {"100": 0.5, "111": 0.5}),
    "teleport_one_qasm": ("""
qubit[3] q; bit[3] c;
x q[0];
h q[1];
cx q[1], q[2];
cx q[0], q[1];
h q[0];
c[0] = measure q[0];
c[1] = measure q[1];
if (c[1] == 1) { x q[2]; }
if (c[0] == 1) { z q[2]; }
c[2] = measure q[2];
""", {"001": 0.25, "011": 0.25, "101": 0.25, "111": 0.25}),
}


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("case", sorted(FEED_FORWARD))
def test_feed_forward(case, backend):
    body, expected = FEED_FORWARD[case]
    qasm = 'OPENQASM 3.0;\ninclude "stdgates.inc";\n' + body
    check_distribution(simulate(qasm, backend, seed=seed_for(case, backend)).counts, expected)


# ---------------------------------------------------------------------------
# Every gate the converters can emit simulates identically everywhere (bug 5)
# ---------------------------------------------------------------------------

PARAMS = [0.37, 0.81, 1.23, 0.55]
PREP = "ry(0.3) q[0];\nry(1.1) q[1];\nry(2.0) q[2];\nrz(0.7) q[0];\nrz(1.3) q[1];\nrz(0.4) q[2];\n"
POST = "h q[0];\nh q[1];\nh q[2];\n"


def _reference_probs(apply):
    """Exact probabilities (q[0] first) from Qiskit's own gate library."""
    from qiskit import QuantumCircuit
    from qiskit.quantum_info import Statevector

    qc = QuantumCircuit(3)
    qc.ry(0.3, 0); qc.ry(1.1, 1); qc.ry(2.0, 2)
    qc.rz(0.7, 0); qc.rz(1.3, 1); qc.rz(0.4, 2)
    apply(qc)
    qc.h(0); qc.h(1); qc.h(2)
    probs = Statevector(qc).probabilities_dict()
    return {k[::-1]: v for k, v in probs.items()}


a, b, c, d = PARAMS
GATE_CASES = {
    # name: (qasm statement, reference builder)
    "id": ("id q[0];", lambda qc: qc.id(0)),
    "x": ("x q[0];", lambda qc: qc.x(0)),
    "y": ("y q[0];", lambda qc: qc.y(0)),
    "z": ("z q[0];", lambda qc: qc.z(0)),
    "h": ("h q[0];", lambda qc: qc.h(0)),
    "s": ("s q[0];", lambda qc: qc.s(0)),
    "sdg": ("sdg q[0];", lambda qc: qc.sdg(0)),
    "t": ("t q[0];", lambda qc: qc.t(0)),
    "tdg": ("tdg q[0];", lambda qc: qc.tdg(0)),
    "sx": ("sx q[0];", lambda qc: qc.sx(0)),
    "rx": (f"rx({a}) q[0];", lambda qc: qc.rx(a, 0)),
    "ry": (f"ry({a}) q[0];", lambda qc: qc.ry(a, 0)),
    "rz": (f"rz({a}) q[0];", lambda qc: qc.rz(a, 0)),
    "p": (f"p({a}) q[0];", lambda qc: qc.p(a, 0)),
    "phase": (f"phase({a}) q[0];", lambda qc: qc.p(a, 0)),
    "u1": (f"u1({a}) q[0];", lambda qc: qc.p(a, 0)),
    "u2": (f"u2({a}, {b}) q[0];", lambda qc: qc.u(math.pi / 2, a, b, 0)),
    "u": (f"u({a}, {b}, {c}) q[0];", lambda qc: qc.u(a, b, c, 0)),
    "u3": (f"u3({a}, {b}, {c}) q[0];", lambda qc: qc.u(a, b, c, 0)),
    "U": (f"U({a}, {b}, {c}) q[0];", lambda qc: qc.u(a, b, c, 0)),
    "cx": ("cx q[0], q[1];", lambda qc: qc.cx(0, 1)),
    "CX": ("CX q[0], q[1];", lambda qc: qc.cx(0, 1)),
    "cy": ("cy q[0], q[1];", lambda qc: qc.cy(0, 1)),
    "cz": ("cz q[0], q[1];", lambda qc: qc.cz(0, 1)),
    "ch": ("ch q[0], q[1];", lambda qc: qc.ch(0, 1)),
    "swap": ("swap q[0], q[1];", lambda qc: qc.swap(0, 1)),
    "iswap": ("iswap q[0], q[1];", lambda qc: qc.iswap(0, 1)),
    "crx": (f"crx({a}) q[0], q[1];", lambda qc: qc.crx(a, 0, 1)),
    "cry": (f"cry({a}) q[0], q[1];", lambda qc: qc.cry(a, 0, 1)),
    "crz": (f"crz({a}) q[0], q[1];", lambda qc: qc.crz(a, 0, 1)),
    "cp": (f"cp({a}) q[0], q[1];", lambda qc: qc.cp(a, 0, 1)),
    "cphase": (f"cphase({a}) q[0], q[1];", lambda qc: qc.cp(a, 0, 1)),
    "cu1": (f"cu1({a}) q[0], q[1];", lambda qc: qc.cp(a, 0, 1)),
    "cu3": (f"cu3({a}, {b}, {c}) q[0], q[1];", lambda qc: qc.cu(a, b, c, 0, 0, 1)),
    "cu": (f"cu({a}, {b}, {c}, {d}) q[0], q[1];", lambda qc: qc.cu(a, b, c, d, 0, 1)),
    "rxx": (f"rxx({a}) q[0], q[1];", lambda qc: qc.rxx(a, 0, 1)),
    "ryy": (f"ryy({a}) q[0], q[1];", lambda qc: qc.ryy(a, 0, 1)),
    "rzz": (f"rzz({a}) q[0], q[1];", lambda qc: qc.rzz(a, 0, 1)),
    "ccx": ("ccx q[0], q[1], q[2];", lambda qc: qc.ccx(0, 1, 2)),
    "ccz": ("ccz q[0], q[1], q[2];", lambda qc: qc.ccz(0, 1, 2)),
    "cswap": ("cswap q[0], q[1], q[2];", lambda qc: qc.cswap(0, 1, 2)),
    "gphase": (f"gphase({a});", lambda qc: None),
    # modifiers (emitted e.g. for qc.mcx, qc.sdg, cirq inverse gates)
    "ctrl@u": (f"ctrl @ u({a}, {b}, {c}) q[0], q[1];",
               lambda qc: qc.append(__import__("qiskit").circuit.library.UGate(a, b, c).control(1), [0, 1])),
    "ctrl(2)@x": ("ctrl(2) @ x q[0], q[1], q[2];", lambda qc: qc.ccx(0, 1, 2)),
    "negctrl@x": ("negctrl @ x q[0], q[1];", lambda qc: qc.cx(0, 1, ctrl_state=0)),
    "ctrl@negctrl@x": ("ctrl @ negctrl @ x q[0], q[1], q[2];",
                       lambda qc: qc.append(__import__("qiskit").circuit.library.XGate().control(2, ctrl_state="01"), [0, 1, 2])),
    "inv@s": ("inv @ s q[0];", lambda qc: qc.sdg(0)),
    "inv@rx": (f"inv @ rx({a}) q[0];", lambda qc: qc.rx(-a, 0)),
    "ctrl@rz": (f"ctrl @ rz({a}) q[0], q[1];", lambda qc: qc.crz(a, 0, 1)),
    "ctrl@gphase": (f"ctrl @ gphase({a}) q[0];", lambda qc: qc.p(a, 0)),
    "pow(0.5)@x": ("pow(0.5) @ x q[0];", lambda qc: qc.sx(0)),
}


@pytest.mark.parametrize("backend", BACKENDS)
@pytest.mark.parametrize("gate", sorted(GATE_CASES))
def test_gate_matches_qiskit_reference(gate, backend):
    statement, reference = GATE_CASES[gate]
    qasm = 'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[3] q;\n' + PREP + statement + "\n" + POST
    expected = _reference_probs(reference)
    probs = simulate(qasm, backend, shots=0).probs
    keys = set(expected) | set(probs)
    worst = max(abs(probs.get(k, 0.0) - expected.get(k, 0.0)) for k in keys)
    assert worst < 1e-6, (probs, expected)


def test_every_converter_gate_is_covered():
    from quantum_converters.base.circuit_validation import GATE_SIGNATURES
    missing = set(GATE_SIGNATURES) - set(GATE_CASES) - {"i"}
    assert not missing, f"gates the converters may emit but are not simulated in tests: {missing}"


# ---------------------------------------------------------------------------
# Regression tests for the individual review findings
# ---------------------------------------------------------------------------

def test_bug1_no_injected_operations():
    bell = PROGRAMS_BY_ID["examples/bell-state-cirq"]["code"]
    qasm = convert_cirq_to_qasm3(bell).qasm_code
    assert "if (" not in qasm and "for int" not in qasm and "ry(" not in qasm

    pl = PennyLaneToQASM3Converter()
    legacy = pl._convert_legacy("import pennylane as qml\ndev = qml.device('default.qubit', wires=2)\n"
                                "qml.Hadamard(wires=0)\nqml.CNOT(wires=[0, 1])\n").qasm_code
    for token in ("temp_angle", "loop_index", "if (", "ry("):
        assert token not in legacy


def test_bug2_cirq_append_parses_statically(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("fell back to exec()")
    monkeypatch.setattr(CirqToQASM3Converter, "_execute_cirq_source", boom)
    qasm = convert_cirq_to_qasm3(PROGRAMS_BY_ID["templates/bell_state_cirq"]["code"]).qasm_code
    assert "h q[0];" in qasm and "cx q[0], q[1];" in qasm


def test_bug3_legacy_loop_substitutes_loop_variable_only():
    conv = PennyLaneToQASM3Converter()
    info = conv._detect_loop_patterns("for i in range(n_qubits):\n    qml.PauliX(wires=i)\n")
    lines = conv._expand_wire_loops("qml.PauliX(wires=i)", 3, info)
    assert lines == ["qml.PauliX(wires=0)", "qml.PauliX(wires=1)", "qml.PauliX(wires=2)"]
    info = conv._detect_loop_patterns("for k in range(n - 1):\n    qml.CNOT(wires=[k, k + 1])\n")
    assert conv._expand_wire_loops("qml.CNOT(wires=[k, k + 1])", 3, info) == [
        "qml.CNOT(wires=[0, 1])", "qml.CNOT(wires=[1, 2])"]


@pytest.mark.parametrize("framework,code,fragment", [
    ("pennylane", "import pennylane as qml\ndev = qml.device('default.qubit', wires=2)\n"
                  "@qml.qnode(dev)\ndef c():\n    qml.QFT(wires=[0, 1])\n    return qml.probs(wires=[0, 1])\n",
     "qml.QFT"),
    ("pennylane", "import pennylane as qml\ndev = qml.device('default.qubit', wires=1)\n"
                  "@qml.qnode(dev)\ndef c():\n    qml.adjoint(qml.S)(wires=0)\n    return qml.probs(wires=0)\n",
     "qml.adjoint"),
    ("cirq", "import cirq, numpy as np\nq = cirq.LineQubit(0)\n"
             "circuit = cirq.Circuit(cirq.MatrixGate(np.eye(2))(q), cirq.measure(q, key='m'))\n",
     "MatrixGate"),
])
def test_bug4_unsupported_operations_raise(framework, code, fragment):
    with pytest.raises(Exception, match=fragment):
        CONVERTERS[framework](code)


def test_bug4_qiskit_compose_is_not_silently_dropped():
    code = """from qiskit import QuantumCircuit
sub = QuantumCircuit(2)
sub.x(0)
sub.x(1)
qc = QuantumCircuit(2, 2)
qc.compose(sub, inplace=True)
qc.measure([0, 1], [0, 1])
"""
    qasm = convert_qiskit_to_qasm3(code).qasm_code  # static path refuses; runtime path is exact
    for backend in BACKENDS:
        check_distribution(simulate(qasm, backend, seed=1).counts, {"11": 1.0})


def test_bug4_qiskit_rzz_supported():
    code = """from qiskit import QuantumCircuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.h(1)
qc.rzz(3.141592653589793, 0, 1)
qc.h(0)
qc.h(1)
qc.measure([0, 1], [0, 1])
"""
    qasm = convert_qiskit_to_qasm3(code).qasm_code
    assert "rzz(" in qasm
    for backend in BACKENDS:
        # H.H . exp(-i pi/2 ZZ) . H.H == -i X(x)X : |00> -> |11>
        check_distribution(simulate(qasm, backend, seed=2).counts, {"11": 1.0})


def test_bug4_qiskit_multiple_registers_use_offsets():
    code = """from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
a = QuantumRegister(1, 'a')
b = QuantumRegister(2, 'b')
cr = ClassicalRegister(3, 'cr')
qc = QuantumCircuit(a, b, cr)
qc.x(b[1])
qc.measure(a[0], cr[0])
qc.measure(b[0], cr[1])
qc.measure(b[1], cr[2])
"""
    qasm = convert_qiskit_to_qasm3(code).qasm_code
    for backend in BACKENDS:
        check_distribution(simulate(qasm, backend, seed=3).counts, {"001": 1.0})


@pytest.mark.parametrize("code,expected", [
    # Two LineQubit.range(2) calls are the SAME two qubits in Cirq: X.X == I.
    ("import cirq\na = cirq.LineQubit.range(2)\nb = cirq.LineQubit.range(2)\n"
     "circuit = cirq.Circuit(cirq.X(a[0]), cirq.X(b[0]), cirq.measure(a[0], a[1], key='m'))\n", {"00": 1.0}),
    # GridQubits are distinct qubits (they used to all collapse onto q[0]).
    ("import cirq\nq0 = cirq.GridQubit(0, 0)\nq1 = cirq.GridQubit(0, 1)\n"
     "circuit = cirq.Circuit(cirq.X(q1), cirq.measure(q0, q1, key='m'))\n", {"01": 1.0}),
    # cirq.rx keyword form must act on the qubit it is applied to (was always q[0]).
    ("import cirq, numpy as np\nq0, q1 = cirq.LineQubit.range(2)\n"
     "circuit = cirq.Circuit(cirq.Rx(rads=np.pi)(q1), cirq.measure(q0, q1, key='m'))\n", {"01": 1.0}),
])
def test_bug4_cirq_qubit_identity(code, expected):
    qasm = convert_cirq_to_qasm3(code).qasm_code
    for backend in BACKENDS:
        check_distribution(simulate(qasm, backend, seed=4).counts, expected)


def test_bug7_pennylane_device_fallback(monkeypatch):
    import pennylane as qml
    from qsim.backends.pennylane import PennylaneBackend

    real_device = qml.device

    def fake_device(name, *args, **kwargs):
        if name == "lightning.qubit":
            raise RuntimeError("lightning not available")
        return real_device(name, *args, **kwargs)

    monkeypatch.setattr(qml, "device", fake_device)
    assert PennylaneBackend()._get_dev_name() == "default.qubit"


@pytest.mark.parametrize("backend", BACKENDS)
def test_bug8_includes_restricted_to_standard_libraries(backend, tmp_path):
    secret = tmp_path / "secret.inc"
    secret.write_text('OPENQASM 3.0;\nqubit[1] r;\n')
    bad = (f'OPENQASM 3.0;\ninclude "stdgates.inc";\ninclude "{secret.as_posix()}";\n'
           'qubit[1] q;\nbit[1] c;\nc[0] = measure q[0];\n')
    with pytest.raises(QSimError, match="not allowed"):
        simulate(bad, backend, shots=10)
    good = 'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[1] q;\nbit[1] c;\nx q[0];\nc[0] = measure q[0];\n'
    assert simulate(good, backend, shots=10).counts == {"1": 10}


def test_bug9_ast_utils_import_has_no_side_effects(tmp_path):
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([ROOT, os.path.join(ROOT, "quantum_simulator")]))
    proc = subprocess.run([sys.executable, "-c", "import qsim.qasm_parser.ast_utils"],
                          cwd=tmp_path, capture_output=True, text=True, env=env, timeout=300)
    assert proc.returncode == 0, proc.stderr
    assert "Unique AST node types" not in proc.stdout


def test_bug10_converter_package_exports():
    import quantum_converters.converters as converters
    assert converters.convert_qiskit_to_qasm3 is convert_qiskit_to_qasm3
    assert converters.convert_cirq_to_qasm3 is convert_cirq_to_qasm3
    assert converters.convert_pennylane_to_qasm3 is convert_pennylane_to_qasm3


def test_bug11_unknown_backend_is_an_error():
    qasm = 'OPENQASM 3.0;\ninclude "stdgates.inc";\nqubit[1] q;\nx q[0];\n'
    with pytest.raises(UnsupportedBackend, match="Unknown simulation backend"):
        simulate(qasm, "qiskitt", shots=10)


# ---------------------------------------------------------------------------
# Script mode: print the example x backend table
# ---------------------------------------------------------------------------

def _table():
    rows = []
    for program in PROGRAMS:
        row = [program["id"], program["framework"]]
        try:
            qasm = compile_program(program)
        except Exception as e:  # noqa: BLE001
            rows.append(row + [f"CONVERT-ERROR: {e}"[:60]] * 3)
            continue
        for backend in BACKENDS:
            try:
                res = simulate(qasm, backend, seed=seed_for(program["id"], backend))
                if program["expected"] is None:
                    row.append("ran (no fixed expectation)")
                else:
                    tvd = check_distribution(res.counts, program["expected"])
                    row.append(f"PASS (TVD {tvd:.3f})")
            except AssertionError as e:
                row.append(f"FAIL {str(e)[:40]}")
            except Exception as e:  # noqa: BLE001
                expected_error = program["id"] in UNBOUND and "has no value" in str(e)
                row.append("ERROR as intended (unbound params)" if expected_error else f"ERROR {str(e)[:40]}")
        rows.append(row)
    return rows


if __name__ == "__main__":
    import contextlib
    import io
    import warnings
    warnings.filterwarnings("ignore")
    with contextlib.redirect_stdout(io.StringIO()):
        table = _table()
    header = ["program", "framework", *BACKENDS]
    print(" | ".join(header))
    print(" | ".join("---" for _ in header))
    for row in table:
        print(" | ".join(row))
