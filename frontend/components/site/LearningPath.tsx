import Link from "next/link";
import { ArrowRight } from "lucide-react";
import Reveal from "@/components/site/Reveal";
import OpenExampleButton from "@/components/site/OpenExampleButton";
import { StaticCircuit } from "@/components/CircuitVisualization";
import { FILE_TEMPLATES_PRESETS } from "@/lib/fileTemplates";
import {
  bellState,
  deutschJozsa,
  teleportation,
  grover,
  qft,
  variational,
  type CapturedCircuit,
} from "@/lib/learningPathData";

/** Look up a shipped IDE template by filename (same programs the editor offers). */
function template(filename: string) {
  const t = FILE_TEMPLATES_PRESETS.find((p) => p.filename === filename);
  if (!t) throw new Error(`Missing template ${filename}`);
  return { name: t.filename, content: t.content };
}

type Level = "Beginner" | "Intermediate" | "Advanced";

interface Stop {
  file: string;
  title: string;
  framework: "Qiskit" | "PennyLane";
  level: Level;
  /** What the learner will see, written against the template source. */
  sees: string;
  circuit: CapturedCircuit;
}

const STOPS: Stop[] = [
  {
    file: "bell_state_qiskit.py",
    title: "Bell state",
    framework: "Qiskit",
    level: "Beginner",
    sees: "A Hadamard and a CNOT entangle two qubits. The histogram shows only 00 and 11, in roughly equal parts.",
    circuit: bellState,
  },
  {
    file: "deutsch_jozsa_qiskit.py",
    title: "Deutsch-Jozsa",
    framework: "Qiskit",
    level: "Intermediate",
    sees: "A balanced oracle on three input qubits and one ancilla. One query later, the inputs always read 111.",
    circuit: deutschJozsa,
  },
  {
    file: "quantum_teleportation_qiskit.py",
    title: "Quantum teleportation",
    framework: "Qiskit",
    level: "Intermediate",
    sees: "A Bell pair is shared between q1 and q2, then q0 and q1 are Bell-measured and all three qubits are read out.",
    circuit: teleportation,
  },
  {
    file: "grover_search_qiskit.py",
    title: "Grover's search",
    framework: "Qiskit",
    level: "Intermediate",
    sees: "A two-qubit search that marks |11> with a CZ oracle, then amplifies it with a diffuser. The result is 11.",
    circuit: grover,
  },
  {
    file: "qft_qiskit.py",
    title: "Quantum Fourier transform",
    framework: "Qiskit",
    level: "Advanced",
    sees: "Three qubits, Hadamards and controlled-phase rotations, then a swap to reverse the qubit order.",
    circuit: qft,
  },
  {
    file: "variational_ansatz_pennylane.py",
    title: "Variational circuit",
    framework: "PennyLane",
    level: "Advanced",
    sees: "A two-qubit ansatz: RY on each qubit, a CNOT, then RZ on each, with the angles held in a params array.",
    circuit: variational,
  },
];

const FRAMEWORK_DOT: Record<Stop["framework"], string> = {
  Qiskit: "bg-qc-qiskit",
  PennyLane: "bg-qc-pennylane",
};

export default function LearningPath() {
  return (
    <section className="border-t border-qc-line" aria-labelledby="path-heading">
      <div className="qc-container py-20 lg:py-24">
        <div className="max-w-2xl">
          <h2
            id="path-heading"
            className="mt-3 font-display text-display-2 font-semibold text-qc-fg"
          >
            A path through the workshop
          </h2>
          <p className="mt-4 text-qc-muted">
            Six real templates, ordered from a single entangled pair to a
            parameterised circuit. Each one opens in the editor, ready to run.
          </p>
        </div>

        <ol className="relative mt-14 lg:mt-20">
          <span
            className="absolute bottom-0 left-3 top-0 w-px -translate-x-1/2 bg-qc-line-strong lg:left-1/2"
            aria-hidden="true"
          />
          {STOPS.map((stop, i) => {
            const textLeft = i % 2 === 0;
            return (
              <Reveal
                as="li"
                key={stop.file}
                className="relative py-8 pl-10 lg:grid lg:grid-cols-2 lg:items-center lg:gap-x-24 lg:py-12 lg:pl-0"
              >
                <span
                  className="absolute left-3 top-8 grid h-6 w-6 -translate-x-1/2 place-items-center rounded-full border border-qc-line-strong bg-qc-bg font-mono text-[10px] text-qc-muted lg:left-1/2 lg:top-1/2 lg:-translate-y-1/2"
                  aria-hidden="true"
                >
                  {i + 1}
                </span>

                <div
                  className={
                    textLeft
                      ? "lg:text-right"
                      : "lg:order-2 lg:text-left"
                  }
                >
                  <div
                    className={`flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-xs text-qc-subtle ${
                      textLeft ? "lg:justify-end" : ""
                    }`}
                  >
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    <span className="text-qc-line-strong" aria-hidden="true">
                      /
                    </span>
                    <span>{stop.level}</span>
                    <span className="text-qc-line-strong" aria-hidden="true">
                      /
                    </span>
                    <span className="inline-flex items-center gap-1.5">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${FRAMEWORK_DOT[stop.framework]}`}
                        aria-hidden="true"
                      />
                      {stop.framework}
                    </span>
                  </div>
                  <h3 className="mt-3 font-display text-2xl font-semibold text-qc-fg">
                    {stop.title}
                  </h3>
                  <p
                    className={`mt-3 max-w-md text-sm leading-relaxed text-qc-muted ${
                      textLeft ? "lg:ml-auto" : ""
                    }`}
                  >
                    {stop.sees}
                  </p>
                  <div className="mt-5">
                    <OpenExampleButton
                      example={template(stop.file)}
                      className="qc-btn qc-btn-secondary qc-btn-sm qc-focus"
                      aria-label={`Open the ${stop.title} example in the editor`}
                    >
                      Open in editor
                      <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
                    </OpenExampleButton>
                  </div>
                </div>

                <div
                  className={`mt-6 lg:mt-0 ${textLeft ? "" : "lg:order-1"}`}
                >
                  <div
                    className={`qc-lattice max-w-[30rem] rounded-xl border border-qc-line bg-qc-surface/60 p-4 sm:p-5 ${
                      textLeft ? "lg:mr-auto" : "lg:ml-auto"
                    }`}
                  >
                    <StaticCircuit
                      gates={stop.circuit.gates}
                      qubits={stop.circuit.qubits}
                      showAxis={false}
                      label={`${stop.title} circuit diagram`}
                    />
                  </div>
                </div>
              </Reveal>
            );
          })}
        </ol>

        <div className="mt-12 flex justify-center lg:mt-16">
          <Link href="/examples" className="qc-link inline-flex items-center gap-1 text-sm">
            All examples
            <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
          </Link>
        </div>
      </div>
    </section>
  );
}
