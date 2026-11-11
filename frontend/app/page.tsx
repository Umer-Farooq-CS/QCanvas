import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import Navbar from "@/components/Navbar";
import SiteFooter from "@/components/site/SiteFooter";
import CodeSample from "@/components/site/CodeSample";
import OpenExampleButton from "@/components/site/OpenExampleButton";
import { config } from "@/lib/config";

// Example programs handed to the editor through sessionStorage.
const EXAMPLES = {
  "bell-state": {
    name: "bell_state_cirq.py",
    content: `import cirq

# Create qubits
q0, q1 = cirq.LineQubit.range(2)

# Create Bell State circuit
circuit = cirq.Circuit()
circuit.append(cirq.H(q0))          # Hadamard gate
circuit.append(cirq.CNOT(q0, q1))   # CNOT gate
circuit.append(cirq.measure(q0, key='m0'))
circuit.append(cirq.measure(q1, key='m1'))

# Expected: 50% |00⟩, 50% |11⟩`,
  },
  "quantum-teleportation": {
    name: "teleportation_qiskit.py",
    content: `from qiskit import QuantumCircuit

# Quantum Teleportation Circuit
qc = QuantumCircuit(3, 3)

# STEP 1: Prepare state to teleport
qc.h(0)

# STEP 2: Create Bell pair (q1, q2)
qc.h(1)
qc.cx(1, 2)

# STEP 3: Bell measurement
qc.cx(0, 1)
qc.h(0)
qc.measure(0, 0)
qc.measure(1, 1)

# STEP 4: Classical corrections
c = [0, 0, 0]  # Placeholder for conditions
if c[1] == 1:
    qc.x(2)
if c[0] == 1:
    qc.z(2)

# Measure teleported qubit
qc.measure(2, 2)`,
  },
  "grovers-search": {
    name: "grovers_pennylane.py",
    content: `import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def grovers_search():
    # Initialize superposition
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)

    # Oracle: mark |11⟩
    qml.CZ(wires=[0, 1])

    # Diffusion operator
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.PauliX(wires=0)
    qml.PauliX(wires=1)
    qml.CZ(wires=[0, 1])
    qml.PauliX(wires=0)
    qml.PauliX(wires=1)
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)

    return qml.probs(wires=[0, 1])

# Expected: High probability for |11⟩`,
  },
};

const HERO_PY = `import cirq

q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit(
    cirq.H(q0),
    cirq.CNOT(q0, q1),
    cirq.measure(q0, q1, key="m"),
)`;

const HERO_QASM = `OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
c = measure q;`;

// Counts from a real 1,024-shot run of the Bell state on qcanvas.codes.
const COUNTS = [
  { state: "00", count: 514 },
  { state: "01", count: 0 },
  { state: "10", count: 0 },
  { state: "11", count: 510 },
];

const DIALECTS = [
  {
    framework: "Cirq",
    color: "bg-qc-cirq",
    code: `q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit(
    cirq.H(q0),
    cirq.CNOT(q0, q1),
    cirq.measure(q0, q1, key="m"),
)`,
  },
  {
    framework: "Qiskit",
    color: "bg-qc-qiskit",
    code: `qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])`,
  },
  {
    framework: "PennyLane",
    color: "bg-qc-pennylane",
    code: `dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def bell():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    return qml.counts()`,
  },
];

const STEPS = [
  {
    title: "Write",
    body: "Start from a template or paste code you already have. Cirq, Qiskit and PennyLane files open in a Monaco editor with completions for each framework.",
  },
  {
    title: "Compile",
    body: "Your circuit is parsed and converted to OpenQASM 3.0. Read it next to your source, copy it, or download the .qasm file.",
  },
  {
    title: "Simulate",
    body: "Choose a backend and a shot count. You get measurement counts, a histogram, the circuit diagram and timing for the run.",
  },
];

const STARTERS = [
  {
    key: "bell-state" as const,
    title: "Bell state",
    framework: "Cirq",
    color: "bg-qc-cirq",
    level: "Beginner",
    body: "Entangle two qubits with H and CNOT. Expect roughly half |00⟩ and half |11⟩.",
  },
  {
    key: "quantum-teleportation" as const,
    title: "Teleportation",
    framework: "Qiskit",
    color: "bg-qc-qiskit",
    level: "Intermediate",
    body: "Move a qubit’s state using a shared Bell pair, a Bell measurement and classical corrections.",
  },
  {
    key: "grovers-search" as const,
    title: "Grover’s search",
    framework: "PennyLane",
    color: "bg-qc-pennylane",
    level: "Advanced",
    body: "Mark |11⟩ with an oracle and amplify it with one diffusion step on two qubits.",
  },
];

function ProductShot() {
  const max = Math.max(...COUNTS.map((c) => c.count));
  const shots = COUNTS.reduce((sum, c) => sum + c.count, 0);

  return (
    <figure className="overflow-hidden rounded-xl border border-qc-line bg-qc-surface shadow-qc">
      <div className="flex items-center gap-1 border-b border-qc-line bg-qc-surface-2 px-3 text-xs">
        <span className="border-b-2 border-qc-accent px-2 py-2.5 text-qc-fg">bell_state.py</span>
        <span className="px-2 py-2.5 text-qc-subtle">bell_state.qasm</span>
        <span className="ml-auto hidden items-center gap-1.5 py-2 font-mono text-[11px] text-qc-subtle sm:flex">
          <span className="h-1.5 w-1.5 rounded-full bg-qc-success" aria-hidden="true" />
          Ran in 29 ms
        </span>
      </div>

      <div className="grid sm:grid-cols-2">
        <div className="border-b border-qc-line sm:border-b-0 sm:border-r">
          <p className="qc-eyebrow px-4 pt-3">Cirq</p>
          <CodeSample plain code={HERO_PY} className="px-4 pb-4 pt-2" />
        </div>
        <div>
          <p className="qc-eyebrow px-4 pt-3">OpenQASM 3.0</p>
          <CodeSample plain code={HERO_QASM} lang="qasm" className="px-4 pb-4 pt-2" />
        </div>
      </div>

      <div className="border-t border-qc-line px-4 py-4">
        <div className="flex items-baseline justify-between">
          <p className="qc-eyebrow">Counts</p>
          <p className="font-mono text-[11px] tabular-nums text-qc-subtle">{shots.toLocaleString("en-US")} shots</p>
        </div>
        <ul className="mt-3 space-y-2" aria-label="Measurement counts">
          {COUNTS.map(({ state, count }) => (
            <li key={state} className="grid grid-cols-[2.5rem_1fr_3rem] items-center gap-3 font-mono text-xs">
              <span className="text-qc-muted">|{state}⟩</span>
              <span className="h-2 overflow-hidden rounded-sm bg-qc-surface-3">
                <span
                  className="block h-full rounded-sm bg-qc-accent"
                  style={{ width: `${(count / max) * 100}%` }}
                />
              </span>
              <span className="text-right tabular-nums text-qc-fg">{count}</span>
            </li>
          ))}
        </ul>
      </div>
      <figcaption className="sr-only">
        A Bell-state circuit in Cirq, the OpenQASM 3.0 it compiles to, and the
        measurement counts from 1,024 shots.
      </figcaption>
    </figure>
  );
}

export default function HomePage() {
  return (
    <div className="qc-page">
      <Navbar />

      <main id="main">
        {/* Hero */}
        <section className="qc-container grid items-center gap-12 pb-20 pt-28 sm:pt-32 lg:grid-cols-2 lg:gap-16 lg:pb-28">
          <div>
            <p className="qc-eyebrow">Open Quantum Workbench · FAST University</p>
            <h1 className="mt-4 font-display text-display-1 font-semibold text-qc-fg [text-wrap:balance]">
              Write it in Cirq, Qiskit or PennyLane. Run it as OpenQASM&nbsp;3.0.
            </h1>
            <p className="mt-6 max-w-[34rem] text-lg leading-relaxed text-qc-muted [text-wrap:pretty]">
              QCanvas is a quantum programming IDE in the browser. Bring a circuit
              from the framework you know, read the OpenQASM it compiles to, and
              simulate it to see the measurement counts.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <OpenExampleButton
                example={EXAMPLES["bell-state"]}
                className="qc-btn qc-btn-primary qc-btn-lg"
              >
                Open the editor
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </OpenExampleButton>
              <Link href="/examples" className="qc-btn qc-btn-secondary qc-btn-lg">
                Browse examples
              </Link>
            </div>
            <p className="mt-5 text-sm text-qc-subtle">
              Nothing to install. Use the demo account on the sign-in page to try it straight away.
            </p>
          </div>

          <ProductShot />
        </section>

        {/* How it works */}
        <section className="border-t border-qc-line" aria-labelledby="how-heading">
          <div className="qc-container py-20 lg:py-24">
            <div className="max-w-2xl">
              <h2 id="how-heading" className="font-display text-display-2 font-semibold text-qc-fg">
                From Python to counts in three steps
              </h2>
              <p className="mt-4 text-qc-muted">
                The editor, the compiler and the simulator share one window, so
                you can change a gate and see its effect on the results without
                switching tools.
              </p>
            </div>
            <ol className="mt-12 grid gap-8 sm:grid-cols-3 sm:gap-6">
              {STEPS.map((step, i) => (
                <li key={step.title} className="border-t border-qc-line-strong pt-5">
                  <span className="font-mono text-xs text-qc-subtle">0{i + 1}</span>
                  <h3 className="mt-2 text-title font-semibold text-qc-fg">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-qc-muted">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Dialects */}
        <section className="border-t border-qc-line bg-qc-surface/40" aria-labelledby="dialects-heading">
          <div className="qc-container py-20 lg:py-24">
            <div className="max-w-2xl">
              <h2 id="dialects-heading" className="font-display text-display-2 font-semibold text-qc-fg">
                One Bell state, three dialects
              </h2>
              <p className="mt-4 text-qc-muted">
                Each framework describes circuits its own way. QCanvas converts all
                three to the same OpenQASM 3.0, which makes it easy to check that
                two programs really do the same thing.
              </p>
            </div>
            <div className="mt-12 grid gap-4 lg:grid-cols-3">
              {DIALECTS.map((d) => (
                <div key={d.framework} className="qc-card overflow-hidden">
                  <div className="flex items-center gap-2 border-b border-qc-line px-4 py-2.5 text-sm text-qc-fg">
                    <span className={`h-2 w-2 rounded-full ${d.color}`} aria-hidden="true" />
                    {d.framework}
                  </div>
                  <CodeSample plain code={d.code} className="p-4" />
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* Starter examples */}
        <section className="border-t border-qc-line" aria-labelledby="examples-heading">
          <div className="qc-container py-20 lg:py-24">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="max-w-2xl">
                <h2 id="examples-heading" className="font-display text-display-2 font-semibold text-qc-fg">
                  Start from a working example
                </h2>
                <p className="mt-4 text-qc-muted">
                  Each one opens in the editor, ready to run.
                </p>
              </div>
              <Link href="/examples" className="qc-link inline-flex items-center gap-1 text-sm">
                All examples
                <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
              </Link>
            </div>

            <ul className="mt-10 divide-y divide-qc-line border-y border-qc-line">
              {STARTERS.map((ex) => (
                <li
                  key={ex.key}
                  className="grid gap-3 py-6 sm:grid-cols-[12rem_1fr_auto] sm:items-center sm:gap-8"
                >
                  <div>
                    <h3 className="font-medium text-qc-fg">{ex.title}</h3>
                    <p className="mt-1 flex items-center gap-2 text-xs text-qc-subtle">
                      <span className={`h-1.5 w-1.5 rounded-full ${ex.color}`} aria-hidden="true" />
                      {ex.framework} · {ex.level}
                    </p>
                  </div>
                  <p className="text-sm leading-relaxed text-qc-muted">{ex.body}</p>
                  <OpenExampleButton
                    example={EXAMPLES[ex.key]}
                    className="qc-btn qc-btn-secondary qc-btn-sm justify-self-start"
                    aria-label={`Open the ${ex.title} example in the editor`}
                  >
                    Open in editor
                  </OpenExampleButton>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Project */}
        <section className="border-t border-qc-line" aria-labelledby="project-heading">
          <div className="qc-container grid gap-8 py-20 lg:grid-cols-2 lg:items-end lg:py-24">
            <div>
              <h2 id="project-heading" className="font-display text-display-2 font-semibold text-qc-fg">
                Built at FAST University for teaching
              </h2>
              <p className="mt-4 max-w-xl text-qc-muted">
                QCanvas is developed by students and faculty as part of{" "}
                {config.initiative.name}. Use it for coursework, workshops or your
                own experiments, and read the docs to see how each framework is
                converted.
              </p>
            </div>
            <div className="flex flex-wrap gap-3 lg:justify-end">
              <Link href="/docs" className="qc-btn qc-btn-secondary">
                Read the docs
              </Link>
              <a
                href={config.social.github}
                target="_blank"
                rel="noopener noreferrer"
                className="qc-btn qc-btn-quiet"
              >
                Source on GitHub
                <ArrowUpRight className="h-4 w-4" aria-hidden="true" />
              </a>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
