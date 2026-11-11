import Link from "next/link";
import { ArrowRight, ArrowUpRight } from "lucide-react";
import Navbar from "@/components/Navbar";
import SiteFooter from "@/components/site/SiteFooter";
import HeroRun from "@/components/site/HeroRun";
import OpenExampleButton from "@/components/site/OpenExampleButton";
import { FILE_TEMPLATES_PRESETS } from "@/lib/fileTemplates";
import { config } from "@/lib/config";

/** Look up a shipped IDE template by filename (same programs the editor offers). */
function template(filename: string) {
  const t = FILE_TEMPLATES_PRESETS.find((p) => p.filename === filename);
  if (!t) throw new Error(`Missing template ${filename}`);
  return { name: t.filename, content: t.content };
}

const STEPS = [
  {
    title: "Write",
    body: "Start from a template or paste code you already have. Qiskit, Cirq and PennyLane files open in a Monaco editor with completions for each framework.",
  },
  {
    title: "Compile",
    body: "Your circuit is converted to OpenQASM 3.0. Read it next to your source, copy it, or save it as a .qasm file.",
  },
  {
    title: "Simulate",
    body: "Pick a backend and a shot count. You get measurement counts, a histogram, the circuit diagram and timing for the run.",
  },
];

const STARTERS = [
  {
    file: "bell_state_qiskit.py",
    title: "Bell state",
    level: "Beginner",
    body: "Entangle two qubits with H and CNOT. Expect roughly half |00⟩ and half |11⟩.",
  },
  {
    file: "deutsch_jozsa_qiskit.py",
    title: "Deutsch-Jozsa",
    level: "Beginner",
    body: "Decide whether an oracle is constant or balanced with a single query.",
  },
  {
    file: "quantum_teleportation_qiskit.py",
    title: "Teleportation",
    level: "Intermediate",
    body: "Move a qubit’s state using a shared Bell pair, a Bell measurement and classical corrections.",
  },
  {
    file: "grover_search_qiskit.py",
    title: "Grover’s search",
    level: "Intermediate",
    body: "Mark one of four states with an oracle and amplify it with a diffusion step.",
  },
];

export default function HomePage() {
  return (
    <div className="qc-page overflow-x-clip">
      <Navbar />

      <main id="main">
        {/* Hero */}
        <section className="qc-container grid items-center gap-12 pb-14 pt-24 sm:pt-28 lg:grid-cols-[1fr_1.12fr] lg:gap-14 lg:pb-20">
          <div>
            <p className="qc-eyebrow">Open Quantum Workbench, FAST University</p>
            <h1 className="mt-4 font-display text-display-1 font-semibold text-qc-fg [text-wrap:balance]">
              Write it in Qiskit, Cirq or PennyLane. Run it as OpenQASM&nbsp;3.0.
            </h1>
            <p className="mt-6 max-w-[34rem] text-lg leading-relaxed text-qc-muted [text-wrap:pretty]">
              A quantum programming IDE in your browser. Write a circuit, read the
              OpenQASM it compiles to, and simulate it in one window.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <OpenExampleButton
                example={template("bell_state_qiskit.py")}
                className="qc-btn qc-btn-primary qc-btn-lg"
              >
                Open the editor
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </OpenExampleButton>
              <Link href="/examples" className="qc-btn qc-btn-secondary qc-btn-lg">
                Browse examples
              </Link>
            </div>
          </div>

          <HeroRun />
        </section>

        {/* How it works */}
        <section className="border-t border-qc-line" aria-labelledby="how-heading">
          <div className="qc-container py-14 lg:py-16">
            <div className="max-w-2xl">
              <h2 id="how-heading" className="font-display text-display-2 font-semibold text-qc-fg">
                From Python to counts in three steps
              </h2>
              <p className="mt-4 text-qc-muted">
                The editor, the compiler and the simulator share one window, so you
                can change a gate and see its effect without switching tools.
              </p>
            </div>
            <ol className="mt-12 grid gap-8 sm:grid-cols-3 sm:gap-6">
              {STEPS.map((step, i) => (
                <li key={step.title} className="group relative pt-6">
                  <span
                    className="absolute inset-x-0 top-0 h-px bg-qc-line-strong"
                    aria-hidden="true"
                  />
                  <span
                    className="absolute left-0 top-0 h-px w-10 bg-qc-accent transition-[width] duration-500 ease-out group-hover:w-full"
                    aria-hidden="true"
                  />
                  <span className="font-mono text-xs text-qc-subtle">{i + 1}</span>
                  <h3 className="mt-2 text-title font-semibold text-qc-fg">{step.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-qc-muted">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* Starter examples */}
        <section className="border-t border-qc-line bg-qc-surface/40" aria-labelledby="examples-heading">
          <div className="qc-container py-14 lg:py-16">
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="max-w-2xl">
                <h2 id="examples-heading" className="font-display text-display-2 font-semibold text-qc-fg">
                  Start from a working Qiskit program
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

            <ul className="mt-10 grid gap-3 sm:grid-cols-2">
              {STARTERS.map((ex) => (
                <li key={ex.file}>
                  <OpenExampleButton
                    example={template(ex.file)}
                    className="qc-focus group flex h-full w-full flex-col items-start rounded-xl border border-qc-line bg-qc-surface p-5 text-left transition-[border-color,transform] duration-200 ease-out hover:-translate-y-0.5 hover:border-qc-accent/50 active:translate-y-0 active:scale-[0.99]"
                    aria-label={`Open the ${ex.title} example in the editor`}
                  >
                    <span className="flex w-full items-center justify-between gap-3">
                      <span className="font-medium text-qc-fg">{ex.title}</span>
                      <span className="text-xs text-qc-subtle">{ex.level}</span>
                    </span>
                    <span className="mt-2 text-sm leading-relaxed text-qc-muted">{ex.body}</span>
                    <span className="mt-4 inline-flex items-center gap-1 text-sm text-qc-accent">
                      Open in editor
                      <ArrowRight
                        className="h-3.5 w-3.5 transition-transform duration-200 group-hover:translate-x-0.5"
                        aria-hidden="true"
                      />
                    </span>
                  </OpenExampleButton>
                </li>
              ))}
            </ul>
          </div>
        </section>

        {/* Project */}
        <section className="border-t border-qc-line" aria-labelledby="project-heading">
          <div className="qc-container grid gap-8 py-14 lg:grid-cols-2 lg:items-end lg:py-16">
            <div>
              <h2 id="project-heading" className="font-display text-display-2 font-semibold text-qc-fg">
                Built at FAST University for teaching
              </h2>
              <p className="mt-4 max-w-xl text-qc-muted">
                QCanvas is developed by students and faculty as part of{" "}
                {config.initiative.name}. Use it for coursework, workshops or your
                own experiments.
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
