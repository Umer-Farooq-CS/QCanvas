import Image from "next/image";
import Reveal from "@/components/site/Reveal";
import { StaticCircuit } from "@/components/CircuitVisualization";
import { bellState } from "@/lib/learningPathData";

const SIMULATORS = [
  { name: "Qiskit", dot: "bg-qc-qiskit" },
  { name: "Cirq", dot: "bg-qc-cirq" },
  { name: "PennyLane", dot: "bg-qc-pennylane" },
];

const QASM_LINES = [
  "OPENQASM 3.0;",
  'include "stdgates.inc";',
  "qubit[2] q;",
  "bit[2] c;",
  "h q[0];",
  "cx q[0], q[1];",
  "measure q[0] -> c[0];",
  "measure q[1] -> c[1];",
];

const CELL = "rounded-xl border border-qc-line p-6 lg:p-7";
const TITLE = "font-display text-xl font-semibold text-qc-fg";
const BODY = "mt-2 text-sm leading-relaxed text-qc-muted";

export default function Workbench() {
  return (
    <section className="border-t border-qc-line" aria-labelledby="workbench-heading">
      <div className="qc-container py-20 lg:py-24">
        <div className="max-w-2xl">
          <h2
            id="workbench-heading"
            className="mt-3 font-display text-display-2 font-semibold text-qc-fg"
          >
            Inside the workbench
          </h2>
          <p className="mt-4 text-qc-muted">
            Write, convert, simulate and inspect a circuit without leaving the
            page.
          </p>
        </div>

        <div className="mt-12 grid gap-4 lg:grid-cols-6 lg:gap-5">
          {/* 1. Editor: the large cell */}
          <Reveal className="lg:col-span-4 lg:row-span-2">
            <div className={`${CELL} flex h-full flex-col overflow-hidden bg-qc-surface pb-0 lg:pb-0`}>
              <h3 className={TITLE}>A real code editor</h3>
              <p className={`${BODY} max-w-xl`}>
                Monaco with completions for Qiskit, Cirq and PennyLane. Files
                and projects are saved to your account.
              </p>
              <div className="relative -mr-6 mt-6 min-h-[14rem] flex-1 overflow-hidden rounded-tl-lg border-l border-t border-qc-line-strong bg-qc-code lg:-mr-7">
                <Image
                  src="/home/editor-dark.png"
                  alt="The QCanvas editor with a Qiskit program open"
                  width={1600}
                  height={900}
                  sizes="(min-width: 1024px) 66vw, 100vw"
                  className="hidden h-auto w-[112%] max-w-none dark:block"
                />
                <Image
                  src="/home/editor-light.png"
                  alt="The QCanvas editor with a Qiskit program open"
                  width={1600}
                  height={900}
                  sizes="(min-width: 1024px) 66vw, 100vw"
                  className="block h-auto w-[112%] max-w-none dark:hidden"
                />
              </div>
            </div>
          </Reveal>

          {/* 2. Simulators: typographic list */}
          <Reveal delay={80} className="lg:col-span-2">
            <div className={`${CELL} h-full bg-qc-surface-2`}>
              <h3 className={TITLE}>Three simulators</h3>
              <p className={BODY}>
                The same OpenQASM program runs on the Cirq, Qiskit and
                PennyLane backends. Every shipped example passes on all three.
              </p>
              <ul className="mt-5 space-y-2 font-mono text-sm text-qc-fg">
                {SIMULATORS.map((s) => (
                  <li key={s.name} className="flex items-center gap-3">
                    <span
                      className={`h-2 w-2 rounded-full ${s.dot}`}
                      aria-hidden="true"
                    />
                    {s.name}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>

          {/* 3. Diagrams */}
          <Reveal delay={140} className="lg:col-span-2">
            <div className={`${CELL} h-full bg-qc-surface`}>
              <div className="rounded-lg border border-qc-line bg-qc-bg/60 p-3">
                <StaticCircuit
                  gates={bellState.gates}
                  qubits={bellState.qubits}
                  showAxis={false}
                  label="Bell circuit diagram"
                />
              </div>
              <h3 className={`${TITLE} mt-5`}>Circuit diagrams in 2D and 3D</h3>
              <p className={BODY}>
                Switch to a 3D view, hover a gate for its details, and export
                the diagram as SVG.
              </p>
            </div>
          </Reveal>

          {/* 4. QASM */}
          <Reveal delay={80} className="lg:col-span-2">
            <div className={`${CELL} h-full bg-qc-surface-2`}>
              <h3 className={TITLE}>OpenQASM 3.0 export</h3>
              <pre
                className="mt-4 overflow-x-auto rounded-lg border border-qc-line bg-qc-code p-3 font-mono text-xs leading-relaxed text-qc-muted"
                aria-label="Example OpenQASM 3.0 output for a Bell circuit"
              >
                <code>
                  {QASM_LINES.map((line) => (
                    <span key={line} className="block whitespace-pre">
                      {line}
                    </span>
                  ))}
                </code>
              </pre>
              <p className={BODY}>Copy it or download it as a .qasm file.</p>
            </div>
          </Reveal>

          {/* 5. Guest workspace */}
          <Reveal delay={140} className="lg:col-span-4">
            <div
              className={`${CELL} qc-lattice flex h-full flex-col justify-between gap-6 border-dashed border-qc-line-strong bg-qc-bg`}
            >
              <div>
                <p className="qc-eyebrow">No account needed</p>
                <h3 className={`${TITLE} mt-2`}>Try it without an account</h3>
                <p className={`${BODY} max-w-xl`}>
                  Guests get a private workspace of their own. It is deleted
                  when you log out or after 3 days.
                </p>
              </div>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
