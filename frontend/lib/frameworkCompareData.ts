/**
 * Data for the homepage "same circuit, three frameworks" section.
 *
 * The programs are the Bell-state samples from components/site/HeroRun.tsx.
 * The QASM strings are the verbatim `qasm_code` field returned by the QCanvas
 * backend: POST /api/converter/convert with { code, framework, style: "classic" },
 * captured 2026-11-12 against a local backend (127.0.0.1:8000).
 *
 * Observed: Qiskit and Cirq produce byte-identical QASM. PennyLane produces the
 * same two gates, but no `bit` register and no `measure` lines, because
 * `qml.counts()` measures at run time rather than as a circuit instruction.
 * Re-capture these if the converter's output format changes.
 */

export type FrameworkId = "qiskit" | "cirq" | "pennylane";

/** The operations the section lets a reader trace across panes. */
export type OpId = "h" | "cx" | "measure";

export const OPS: ReadonlyArray<{ id: OpId; label: string; gloss: string }> = [
  { id: "h", label: "Hadamard", gloss: "H on qubit 0" },
  { id: "cx", label: "CNOT", gloss: "qubit 0 to qubit 1" },
  { id: "measure", label: "Measure", gloss: "read out both qubits" },
];

export interface FrameworkProgram {
  id: FrameworkId;
  name: string;
  /** Tailwind background class for the framework colour dot. */
  dot: string;
  code: string;
  /** Zero-based source line index -> the operation that line performs. */
  ops: Record<number, OpId>;
}

/**
 * Which operation each source line performs, found by matching the code
 * itself (hand-counted line numbers drifted: PennyLane was off by one).
 * qml.counts() is where PennyLane measures, so it maps to "measure".
 */
const OP_PATTERNS: ReadonlyArray<[OpId, RegExp]> = [
  ["h", /\.h\(|cirq\.H\(|qml\.Hadamard\(/],
  ["cx", /\.cx\(|cirq\.CNOT\(|qml\.CNOT\(/],
  ["measure", /\.measure\(|cirq\.measure\(|qml\.counts\(/],
];

function opsFrom(code: string): Record<number, OpId> {
  const ops: Record<number, OpId> = {};
  code.split("\n").forEach((line, i) => {
    const hit = OP_PATTERNS.find(([, re]) => re.test(line));
    if (hit) ops[i] = hit[0];
  });
  return ops;
}

const SOURCES: ReadonlyArray<Omit<FrameworkProgram, "ops">> = [
  {
    id: "qiskit",
    name: "Qiskit",
    dot: "bg-qc-qiskit",
    code: `from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])`,
  },
  {
    id: "cirq",
    name: "Cirq",
    dot: "bg-qc-cirq",
    code: `import cirq

q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit(
    cirq.H(q0),
    cirq.CNOT(q0, q1),
    cirq.measure(q0, q1),
)`,
  },
  {
    id: "pennylane",
    name: "PennyLane",
    dot: "bg-qc-pennylane",
    code: `import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def bell():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    return qml.counts()`,
  },
];

export const PROGRAMS: ReadonlyArray<FrameworkProgram> = SOURCES.map((p) => ({ ...p, ops: opsFrom(p.code) }));

const QISKIT_CIRQ_QASM = `OPENQASM 3.0;
include "stdgates.inc";

// Quantum and classical registers
qubit[2] q;
bit[2] c;

// Circuit operations
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];
`;

const PENNYLANE_QASM = `OPENQASM 3.0;
include "stdgates.inc";

// Quantum and classical registers
qubit[2] q;

// Circuit operations
h q[0];
cx q[0], q[1];
`;

export interface QasmView {
  id: "shared" | "pennylane";
  label: string;
  /** Which framework colours the tab dots use. */
  dots: string[];
  qasm: string;
}

export const QASM_VIEWS: ReadonlyArray<QasmView> = [
  {
    id: "shared",
    label: "Qiskit and Cirq",
    dots: ["bg-qc-qiskit", "bg-qc-cirq"],
    qasm: QISKIT_CIRQ_QASM,
  },
  {
    id: "pennylane",
    label: "PennyLane",
    dots: ["bg-qc-pennylane"],
    qasm: PENNYLANE_QASM,
  },
];

/** Which operation a QASM line performs, or null for headers and comments. */
export function qasmOp(line: string): OpId | null {
  if (/^h\s/.test(line)) return "h";
  if (/^cx\s/.test(line)) return "cx";
  if (/^measure\s/.test(line)) return "measure";
  return null;
}
