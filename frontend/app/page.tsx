import Link from "next/link";
import { ArrowRight } from "lucide-react";
import Navbar from "@/components/Navbar";
import SiteFooter from "@/components/site/SiteFooter";
import HeroRun from "@/components/site/HeroRun";
import OpenExampleButton from "@/components/site/OpenExampleButton";
import GuestStartButton from "@/components/site/GuestStartButton";
import InterferenceField from "@/components/site/InterferenceField";
import CircuitShowcase from "@/components/site/CircuitShowcase";
import FrameworkCompare from "@/components/site/FrameworkCompare";
import LearningPath from "@/components/site/LearningPath";
import Workbench from "@/components/site/Workbench";
import ResourcesStrip from "@/components/site/ResourcesStrip";
import Reveal from "@/components/site/Reveal";
import { FILE_TEMPLATES_PRESETS } from "@/lib/fileTemplates";
import { config } from "@/lib/config";

/** Look up a shipped IDE template by filename (same programs the editor offers). */
function template(filename: string) {
  const t = FILE_TEMPLATES_PRESETS.find((p) => p.filename === filename);
  if (!t) throw new Error(`Missing template ${filename}`);
  return { name: t.filename, content: t.content };
}

const FLOW = [
  { label: "Qiskit", dot: "bg-qc-qiskit" },
  { label: "Cirq", dot: "bg-qc-cirq" },
  { label: "PennyLane", dot: "bg-qc-pennylane" },
];

export default function HomePage() {
  return (
    <div className="qc-page overflow-x-clip">
      <Navbar />

      <main id="main">
        {/* Hero */}
        <section className="relative isolate flex min-h-[100dvh] items-center overflow-hidden">
          <InterferenceField />
          <div className="qc-container grid w-full items-center gap-12 pb-16 pt-28 lg:grid-cols-[1fr_1.08fr] lg:gap-16 lg:pb-20">
            <div>
              <p className="qc-eyebrow">Open Quantum Workbench · FAST University</p>
              <h1 className="mt-5 max-w-[19ch] font-display text-display-hero font-medium text-qc-fg [text-wrap:balance]">
                Write quantum circuits in the framework you already know.
              </h1>
              <p className="mt-6 max-w-[33rem] text-lg leading-relaxed text-qc-muted [text-wrap:pretty]">
                Qiskit, Cirq or PennyLane in. OpenQASM&nbsp;3.0, a circuit diagram and
                measurement counts out, in one browser tab.
              </p>
              <div className="mt-9 flex flex-wrap items-center gap-3">
                <OpenExampleButton
                  example={template("bell_state_qiskit.py")}
                  className="qc-btn qc-btn-primary qc-btn-lg"
                >
                  Open the editor
                  <ArrowRight className="h-4 w-4" aria-hidden="true" />
                </OpenExampleButton>
                <GuestStartButton className="qc-btn qc-btn-secondary qc-btn-lg">
                  Try it without an account
                </GuestStartButton>
              </div>

              {/* The pipeline in one line */}
              <div className="mt-12 flex flex-wrap items-center gap-x-3 gap-y-2 font-mono text-xs text-qc-subtle">
                {FLOW.map((f) => (
                  <span key={f.label} className="inline-flex items-center gap-1.5">
                    <span className={`h-1.5 w-1.5 rounded-full ${f.dot}`} aria-hidden="true" />
                    {f.label}
                  </span>
                ))}
                <span aria-hidden="true" className="text-qc-line-strong">→</span>
                <span>OpenQASM 3.0</span>
                <span aria-hidden="true" className="text-qc-line-strong">→</span>
                <span>3 simulators</span>
                <span aria-hidden="true" className="text-qc-line-strong">→</span>
                <span className="text-qc-signal">counts</span>
              </div>
            </div>

            <HeroRun />
          </div>
        </section>

        {/* Circuit to counts */}
        <section className="border-t border-qc-line" aria-labelledby="showcase-heading">
          <div className="qc-container py-20 lg:py-24">
            <Reveal className="mb-10 grid gap-6 lg:grid-cols-[1fr_1fr] lg:items-end">
              <h2 id="showcase-heading" className="font-display text-display-2 font-medium text-qc-fg">
                Run it, then read the noise.
              </h2>
              <p className="max-w-xl text-qc-muted lg:justify-self-end">
                Step through a circuit one moment at a time. The bars show the exact
                probabilities so far; at the end, compare them with what 1,024 real
                shots on the QCanvas simulator returned.
              </p>
            </Reveal>
            <Reveal delay={80}>
              <CircuitShowcase />
            </Reveal>
          </div>
        </section>

        <FrameworkCompare />
        <LearningPath />
        <Workbench />
        <ResourcesStrip />

        {/* Closing */}
        <section className="relative isolate overflow-hidden border-t border-qc-line" aria-labelledby="closing-heading">
          <InterferenceField variant="center" />
          <div className="qc-container flex flex-col items-center py-28 text-center lg:py-36">
            <h2 id="closing-heading" className="max-w-[18ch] font-display text-display-hero font-medium text-qc-fg [text-wrap:balance]">
              Open the editor and run your first circuit.
            </h2>
            <p className="mt-6 max-w-xl text-qc-muted">
              Built at FAST University as part of {config.initiative.name}. Free for
              coursework, workshops and your own experiments.
            </p>
            <div className="mt-10 flex flex-wrap justify-center gap-3">
              <OpenExampleButton
                example={template("bell_state_qiskit.py")}
                className="qc-btn qc-btn-primary qc-btn-lg"
              >
                Open the editor
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </OpenExampleButton>
              <Link href="/docs" className="qc-btn qc-btn-secondary qc-btn-lg">
                Read the docs
              </Link>
            </div>
          </div>
        </section>
      </main>

      <SiteFooter />
    </div>
  );
}
