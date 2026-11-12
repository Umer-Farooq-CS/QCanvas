"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { animate, motion, useReducedMotion } from "framer-motion";
import { RotateCcw } from "lucide-react";
import { highlight, type Lang } from "./CodeSample";

/**
 * The homepage's one orchestrated moment: a Bell-state program "runs" in front
 * of the visitor. Source appears, compiles to OpenQASM line by line, then the
 * measurement histogram fills in. Switching framework or pressing "Run again"
 * replays it. Reduced motion shows the finished state immediately.
 *
 * The QASM below is what QCanvas's converter emits for the Qiskit and Cirq
 * programs (verified), and the counts come from a real 1,024-shot run.
 */

const PROGRAMS: Record<"Qiskit" | "Cirq" | "PennyLane", string> = {
  Qiskit: `from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])`,
  Cirq: `import cirq

q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit(
    cirq.H(q0),
    cirq.CNOT(q0, q1),
    cirq.measure(q0, q1),
)`,
  PennyLane: `import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def bell():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    return qml.counts()`,
};

const FRAMEWORKS = Object.keys(PROGRAMS) as Array<keyof typeof PROGRAMS>;

const FRAMEWORK_DOT: Record<keyof typeof PROGRAMS, string> = {
  Qiskit: "bg-qc-qiskit",
  Cirq: "bg-qc-cirq",
  PennyLane: "bg-qc-pennylane",
};

const QASM = `OPENQASM 3.0;
include "stdgates.inc";
qubit[2] q;
bit[2] c;
h q[0];
cx q[0], q[1];
measure q[0] -> c[0];
measure q[1] -> c[1];`;

const COUNTS = [
  { state: "00", count: 514 },
  { state: "01", count: 0 },
  { state: "10", count: 0 },
  { state: "11", count: 510 },
];
const MAX = 514;

type Phase = "source" | "compile" | "simulate" | "done";

const EASE = [0.16, 1, 0.3, 1] as const;

function Lines({
  code,
  lang,
  stagger,
  animateIn,
}: {
  code: string;
  lang: Lang;
  stagger: number;
  animateIn: boolean;
}) {
  return (
    <pre className="qc-code qc-code--plain overflow-x-auto overflow-y-hidden whitespace-pre text-[0.6875rem] leading-[1.75] sm:text-[0.78125rem]">
      <code>
        {code.split("\n").map((line, i) => (
          <motion.span
            key={i}
            className="block min-h-[1.75em]"
            initial={animateIn ? { opacity: 0, y: 3 } : false}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.28, delay: animateIn ? i * stagger : 0, ease: EASE }}
          >
            {line ? highlight(line, lang) : " "}
          </motion.span>
        ))}
      </code>
    </pre>
  );
}

function Count({ to, run, instant }: { to: number; run: number; instant: boolean }) {
  const ref = useRef<HTMLSpanElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (instant || to === 0) {
      el.textContent = String(to);
      return;
    }
    const controls = animate(0, to, {
      duration: 0.9,
      ease: EASE,
      onUpdate: (v) => {
        el.textContent = String(Math.round(v));
      },
    });
    return () => controls.stop();
  }, [to, run, instant]);
  return <span ref={ref}>0</span>;
}

export default function HeroRun() {
  const reduce = useReducedMotion() ?? false;
  const [framework, setFramework] = useState<keyof typeof PROGRAMS>("Qiskit");
  const [run, setRun] = useState(0);
  const [phase, setPhase] = useState<Phase>(reduce ? "done" : "source");

  const source = PROGRAMS[framework];
  const sourceLines = source.split("\n").length;

  // Drive the sequence: source -> compile -> simulate -> done.
  useEffect(() => {
    if (reduce) {
      setPhase("done");
      return;
    }
    setPhase("source");
    const tCompile = 250 + sourceLines * 45;
    const tSimulate = tCompile + 300 + 8 * 55;
    const tDone = tSimulate + 950;
    const timers = [
      window.setTimeout(() => setPhase("compile"), tCompile),
      window.setTimeout(() => setPhase("simulate"), tSimulate),
      window.setTimeout(() => setPhase("done"), tDone),
    ];
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [run, framework, reduce, sourceLines]);

  const replay = useCallback(() => setRun((r) => r + 1), []);
  const pick = (f: keyof typeof PROGRAMS) => {
    if (f === framework) return;
    setFramework(f);
  };

  const showQasm = phase !== "source";
  const showCounts = phase === "simulate" || phase === "done";
  const status =
    phase === "source"
      ? "Ready"
      : phase === "compile"
        ? "Compiling to OpenQASM 3.0"
        : phase === "simulate"
          ? "Simulating 1,024 shots"
          : "Ran in 29 ms";

  return (
    <figure className="relative">
      {/* Soft brand glow behind the card: the single decorative accent. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute -inset-x-6 -inset-y-8 -z-10 rounded-[2rem] opacity-60 blur-3xl"
        style={{
          background:
            "radial-gradient(60% 50% at 70% 30%, rgb(99 102 241 / 0.28), transparent 70%), radial-gradient(50% 45% at 20% 80%, rgb(6 182 212 / 0.16), transparent 70%)",
        }}
      />

      <div className="overflow-hidden rounded-2xl border border-qc-line bg-qc-surface shadow-qc">
        {/* Framework tabs + status */}
        <div className="flex items-center gap-1 border-b border-qc-line bg-qc-surface-2/70 px-2">
          <div role="tablist" aria-label="Framework" className="flex">
            {FRAMEWORKS.map((f) => (
              <button
                key={f}
                type="button"
                role="tab"
                aria-selected={framework === f}
                onClick={() => pick(f)}
                className={`qc-focus relative flex items-center gap-2 px-3 py-2.5 text-xs transition-colors duration-150 ${
                  framework === f ? "text-qc-fg" : "text-qc-subtle hover:text-qc-fg"
                }`}
              >
                <span className={`h-1.5 w-1.5 rounded-full ${FRAMEWORK_DOT[f]}`} aria-hidden="true" />
                {f}
                {framework === f && (
                  <motion.span
                    layoutId="hero-tab"
                    className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-qc-accent"
                    transition={{ type: "spring", stiffness: 500, damping: 40 }}
                  />
                )}
              </button>
            ))}
          </div>
          <span
            className="ml-auto hidden items-center gap-2 pr-2 font-mono text-[0.6875rem] text-qc-subtle sm:flex"
            aria-live="polite"
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                phase === "done" ? "bg-qc-success" : "bg-qc-accent animate-pulse"
              }`}
              aria-hidden="true"
            />
            {status}
          </span>
        </div>

        {/* Source */}
        <div className="border-b border-qc-line px-5 py-4" key={`src-${framework}-${run}`}>
          <Lines code={source} lang="python" stagger={0.045} animateIn={!reduce} />
        </div>

        {/* QASM + counts */}
        <div className="grid sm:grid-cols-[1.05fr_1fr]">
          <div className="min-h-[13.5rem] border-b border-qc-line px-5 py-4 sm:border-b-0 sm:border-r">
            <p className="mb-2 text-xs font-medium text-qc-subtle">OpenQASM 3.0</p>
            {showQasm && (
              <Lines key={`qasm-${framework}-${run}`} code={QASM} lang="qasm" stagger={0.055} animateIn={!reduce} />
            )}
          </div>

          <div className="px-5 py-4">
            <div className="mb-3 flex items-baseline justify-between">
              <p className="text-xs font-medium text-qc-subtle">Counts</p>
              <p className="font-mono text-[0.6875rem] tabular-nums text-qc-subtle">1,024 shots</p>
            </div>
            <ul className="space-y-3" aria-label="Measurement counts">
              {COUNTS.map(({ state, count }, i) => (
                <li key={state} className="grid grid-cols-[2.6rem_1fr_2.5rem] items-center gap-3 font-mono text-xs">
                  <span className="text-qc-muted">|{state}⟩</span>
                  <span className="h-2 overflow-hidden rounded-full bg-qc-surface-3">
                    <motion.span
                      key={`${framework}-${run}`}
                      className="block h-full origin-left rounded-full"
                      style={{
                        width: `${(count / MAX) * 100}%`,
                        background: "linear-gradient(90deg, #6366f1, #8b5cf6 60%, #06b6d4)",
                      }}
                      initial={reduce ? false : { scaleX: 0 }}
                      animate={{ scaleX: showCounts ? 1 : 0 }}
                      transition={{ type: "spring", stiffness: 120, damping: 20, delay: reduce ? 0 : i * 0.06 }}
                    />
                  </span>
                  <span className="text-right tabular-nums text-qc-fg">
                    {showCounts ? <Count key={`${framework}-${run}`} to={count} run={run} instant={reduce} /> : "0"}
                  </span>
                </li>
              ))}
            </ul>

            <button
              type="button"
              onClick={replay}
              disabled={phase !== "done"}
              className="qc-btn qc-btn-quiet qc-btn-sm mt-5 -ml-2.5"
            >
              <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
              Run again
            </button>
          </div>
        </div>
      </div>
      <figcaption className="sr-only">
        A Bell-state program in Qiskit, Cirq or PennyLane, the OpenQASM 3.0 it
        compiles to, and the measurement counts from 1,024 shots: about half 00
        and half 11.
      </figcaption>
    </figure>
  );
}
