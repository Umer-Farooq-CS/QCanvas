"""
PennyLane module-level arrays indexed by loop variables (the "Quantum Neural Network"
example: ``qml.RX(inputs[i], wires=i)`` / ``qml.RX(weights[layer, i, 0], wires=i)``).

The static parser unrolls such loops so every angle is a concrete number. Anything it
cannot resolve exactly must still raise UnsupportedCircuitError (never wrong QASM).
"""

import os
import re
import sys

import numpy as np
import pytest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from quantum_converters.base.circuit_validation import MAX_STATIC_RANGE, UnsupportedCircuitError  # noqa: E402
from quantum_converters.parsers.pennylane_parser import PennyLaneASTParser  # noqa: E402
from quantum_converters.converters.pennylane_to_qasm import convert_pennylane_to_qasm3  # noqa: E402

pytestmark = pytest.mark.integration


def _convert(code):
    return convert_pennylane_to_qasm3(code).qasm_code

HEADER = "import pennylane as qml\nimport numpy as np\n\ndev = qml.device('default.qubit', wires=2)\n"

WEIGHTS_NUMPY = """
weights = np.array([
    [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
    [[0.7, 0.8, 0.9], [1.0, 1.1, 1.2]],
])
"""


def _angles(qasm, gate):
    return [float(m) for m in re.findall(rf"^{gate}\(([^)]*)\)", qasm, flags=re.M)]


def _qnn(index_expr):
    return HEADER + "inputs = np.array([0.5, -0.3])\n" + WEIGHTS_NUMPY + f"""
@qml.qnode(dev)
def circuit():
    for i in range(2):
        qml.RX(inputs[i], wires=i)
    for layer in range(2):
        for i in range(2):
            qml.RY({index_expr}, wires=i)
    return qml.probs(wires=[0, 1])
"""


@pytest.mark.parametrize("index_expr", ["weights[layer, i, 1]", "weights[layer][i][1]", "weights[layer, i][1]"])
def test_loop_indexed_nested_array_both_styles(index_expr):
    qasm = _convert(_qnn(index_expr))
    assert _angles(qasm, "rx") == [0.5, -0.3]
    assert _angles(qasm, "ry") == [0.2, 0.5, 0.8, 1.1]


def test_plain_nested_list_and_one_dimensional_array():
    code = HEADER + """
theta = [0.25, 0.5, 0.75]

@qml.qnode(dev)
def circuit():
    for k in range(3):
        qml.RZ(theta[k], wires=0)
    qml.RZ(theta[-1], wires=1)
    return qml.probs(wires=[0, 1])
"""
    qasm = _convert(code)
    assert _angles(qasm, "rz") == [0.25, 0.5, 0.75, 0.75]


def test_arithmetic_on_indexed_values():
    code = HEADER + """
inputs = np.array([0.5, -0.3])

@qml.qnode(dev)
def circuit():
    for i in range(2):
        qml.RX(2 * inputs[i], wires=i)
    return qml.probs(wires=[0, 1])
"""
    assert _angles(_convert(code), "rx") == [1.0, -0.6]


def test_loop_with_offset_range_start():
    code = HEADER + """
inputs = np.array([0.1, 0.2])

@qml.qnode(dev)
def circuit():
    for i in range(1, 2):
        qml.RX(inputs[i], wires=i)
    return qml.probs(wires=[0, 1])
"""
    qasm = _convert(code)
    assert _angles(qasm, "rx") == [0.2]
    assert "rx(0.2) q[1];" in qasm


def test_out_of_range_index_is_refused():
    code = HEADER + """
inputs = np.array([0.5, -0.3])

@qml.qnode(dev)
def circuit():
    for i in range(3):
        qml.RX(inputs[i], wires=0)
    return qml.probs(wires=[0])
"""
    with pytest.raises(Exception) as exc:
        _convert(code)
    assert "inputs" in str(exc.value)


def test_unresolvable_index_into_known_array_is_refused():
    code = HEADER + """
inputs = np.array([0.5, -0.3])

@qml.qnode(dev)
def circuit():
    for i in range(2):
        qml.RX(inputs[some_runtime_value], wires=i)
    return qml.probs(wires=[0, 1])
"""
    with pytest.raises(ValueError) as exc:
        _convert(code)
    assert "inputs" in str(exc.value)


def test_unrolling_beyond_the_cap_is_refused():
    big = MAX_STATIC_RANGE + 1
    code = HEADER + f"""
inputs = np.array([0.5, -0.3])

@qml.qnode(dev)
def circuit():
    for i in range({big}):
        qml.RX(inputs[0 if i % 2 == 0 else 1] , wires=0)
    return qml.probs(wires=[0])
"""
    with pytest.raises(UnsupportedCircuitError):
        PennyLaneASTParser().parse(code)


def test_nested_unrolls_share_one_budget():
    # 400 x 400 = 160,000 total iterations: each range is fine, the product is not.
    code = HEADER + """
inputs = np.array([0.5, -0.3])

@qml.qnode(dev)
def circuit():
    for a in range(400):
        for b in range(400):
            qml.RX(inputs[(a + b) % 2], wires=0)
    return qml.probs(wires=[0])
"""
    with pytest.raises(UnsupportedCircuitError):
        PennyLaneASTParser().parse(code)


def test_qnn_example_matches_pennylane_numerically():
    """Distribution of the converted QASM equals real PennyLane's for the QNN example."""
    qsim = pytest.importorskip("qsim")
    qml = pytest.importorskip("pennylane")
    pytest.importorskip("cirq")
    pytest.importorskip("qiskit")

    code = HEADER + "inputs = np.array([0.5, -0.3])\n" + WEIGHTS_NUMPY + """
@qml.qnode(dev)
def circuit():
    for i in range(2):
        qml.RX(inputs[i], wires=i)
        qml.RY(inputs[i], wires=i)
    for layer in range(2):
        for i in range(2 - 1):
            qml.CNOT(wires=[i, i + 1])
        for i in range(2):
            qml.RX(weights[layer, i, 0], wires=i)
            qml.RY(weights[layer, i, 1], wires=i)
            qml.RZ(weights[layer, i, 2], wires=i)
    return qml.probs(wires=[0, 1])
"""
    qasm = _convert(code)
    ns = {}
    exec(code, ns)  # trusted literal defined in this test
    reference = {format(i, "02b"): float(p) for i, p in enumerate(ns["circuit"]())}
    from qsim import RunArgs, run_qasm

    for backend in ("pennylane", "qiskit", "cirq"):
        probs = run_qasm(RunArgs(qasm_input=qasm, backend=backend, shots=0, seed=1)).probs
        for key, expected in reference.items():
            assert abs(probs.get(key, 0.0) - expected) < 1e-6, (backend, key, probs, reference)
