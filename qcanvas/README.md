# qcanvas-sdk

Compile quantum circuits written in **Qiskit**, **Cirq** or **PennyLane** to **OpenQASM 3.0**.

This is the Python SDK behind [QCanvas](https://qcanvas.codes). It contains the `qcanvas` facade and
the `quantum_converters` compilation engine. The QCanvas web app, API server and simulator are not
part of this package.

## Installation

```bash
pip install qcanvas-sdk

# with the framework(s) you use
pip install "qcanvas-sdk[qiskit]"
pip install "qcanvas-sdk[cirq]"
pip install "qcanvas-sdk[pennylane]"
pip install "qcanvas-sdk[all]"
```

## Usage

```python
from qiskit import QuantumCircuit
from qcanvas import compile

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

print(compile(qc))                      # framework auto-detected from the object
print(compile(qc, framework="qiskit"))  # or explicit
```

`compile` also accepts **source code as a string** when you pass the framework:

```python
source = """
from qiskit import QuantumCircuit
qc = QuantumCircuit(1, 1)
qc.h(0)
qc.measure(0, 0)
"""
qasm = compile(source, framework="qiskit")
```

A string without `framework=` is treated as OpenQASM and returned unchanged.

### Supported inputs

| Framework | Circuit object | Source string |
|-----------|----------------|---------------|
| Qiskit    | `QuantumCircuit` | yes |
| Cirq      | `cirq.Circuit` | yes |
| PennyLane | not yet (use source) | yes |

Operations the converter can't translate exactly raise an error instead of producing silently wrong QASM.

## Public API

- `compile(circuit, framework=None, **kwargs) -> str`: compile to OpenQASM 3.0.
- `compile_and_execute(...)`, `SimulationResult` and `HybridExecutionResult` need the QCanvas backend
  runtime, which is **not** included in this distribution.

## License

Open Quantum Workbench Proprietary License. See `LICENSE`.
