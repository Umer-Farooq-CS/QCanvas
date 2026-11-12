"use client";

import { useState } from "react";
import { ArrowDown } from "lucide-react";
import Reveal from "@/components/site/Reveal";
import { highlight, type Lang } from "@/components/site/CodeSample";
import {
  OPS,
  PROGRAMS,
  QASM_VIEWS,
  qasmOp,
  type OpId,
  type QasmView,
} from "@/lib/frameworkCompareData";

const COLS = "lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1fr)_minmax(0,1.15fr)]";

interface Handlers {
  active: OpId | null;
  setActive: (op: OpId | null) => void;
}

function CodeLines({
  lines,
  lang,
  opFor,
  active,
  setActive,
}: Handlers & {
  lines: string[];
  lang: Lang;
  opFor: (line: string, index: number) => OpId | null;
}) {
  return (
    <pre className="qc-code qc-code--plain overflow-x-auto whitespace-pre py-4 text-[0.6875rem] leading-[1.75] sm:text-[0.78125rem]">
      <code className="block min-w-max">
        {lines.map((line, i) => {
          const op = opFor(line, i);
          const on = op !== null && op === active;
          const dim = active !== null && !on;
          return (
            <span
              key={i}
              onMouseEnter={op ? () => setActive(op) : undefined}
              onMouseLeave={op ? () => setActive(null) : undefined}
              onClick={op ? () => setActive(active === op ? null : op) : undefined}
              className={`block min-h-[1.75em] border-l-2 px-4 transition-[background-color,border-color,opacity] duration-150 motion-reduce:transition-none ${
                on ? "border-qc-accent bg-qc-accent/10" : "border-transparent"
              } ${op ? "cursor-default" : ""} ${dim ? "opacity-60" : "opacity-100"}`}
            >
              {line ? highlight(line, lang) : " "}
            </span>
          );
        })}
      </code>
    </pre>
  );
}

export default function FrameworkCompare() {
  const [active, setActive] = useState<OpId | null>(null);
  const [viewId, setViewId] = useState<QasmView["id"]>("shared");
  const view = QASM_VIEWS.find((v) => v.id === viewId) ?? QASM_VIEWS[0];
  const qasmLines = view.qasm.replace(/\n+$/, "").split("\n");

  return (
    <section className="border-t border-qc-line" aria-labelledby="compare-heading">
      <div className="qc-container py-20 lg:py-24">
        <Reveal>
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-end">
            <div className="max-w-2xl">
              <p className="qc-eyebrow mb-3">One circuit, three frameworks</p>
              <h2 id="compare-heading" className="font-display text-display-2 text-qc-fg">
                Same circuit. Same gates.
              </h2>
              <p className="mt-4 text-base text-qc-muted">
                Each framework compiles to OpenQASM 3.0, so you can switch syntax without
                relearning the circuit.
              </p>
            </div>

            <div
              className="flex flex-wrap items-center gap-2"
              role="group"
              aria-label="Trace an operation across the code"
            >
              <span className="qc-eyebrow mr-1">Trace</span>
              {OPS.map((op) => {
                const on = active === op.id;
                return (
                  <button
                    key={op.id}
                    type="button"
                    aria-pressed={on}
                    title={op.gloss}
                    onMouseEnter={() => setActive(op.id)}
                    onMouseLeave={() => setActive(null)}
                    onFocus={() => setActive(op.id)}
                    onBlur={() => setActive(null)}
                    className={`qc-focus rounded-lg border px-3 py-1.5 font-mono text-xs transition-colors duration-150 motion-reduce:transition-none ${
                      on
                        ? "border-qc-accent bg-qc-accent/10 text-qc-fg"
                        : "border-qc-line text-qc-muted hover:border-qc-line-strong hover:text-qc-fg"
                    }`}
                  >
                    {op.label}
                  </button>
                );
              })}
            </div>
          </div>
        </Reveal>

        <Reveal delay={80} className="mt-10">
          <figure>
            <div className="overflow-hidden rounded-xl border border-qc-line bg-qc-surface">
              {/* Source panes */}
              <div className={`grid divide-y divide-qc-line lg:divide-x lg:divide-y-0 ${COLS}`}>
                {PROGRAMS.map((p) => (
                  <div key={p.id} className="min-w-0">
                    <div className="flex items-center gap-2 border-b border-qc-line bg-qc-surface-2/60 px-4 py-2.5 text-xs text-qc-muted">
                      <span className={`h-1.5 w-1.5 rounded-full ${p.dot}`} aria-hidden="true" />
                      <span className="font-medium text-qc-fg">{p.name}</span>
                      <span className="ml-auto font-mono text-[0.6875rem] text-qc-subtle">python</span>
                    </div>
                    <CodeLines
                      lines={p.code.split("\n")}
                      lang="python"
                      opFor={(_, i) => p.ops[i] ?? null}
                      active={active}
                      setActive={setActive}
                    />
                  </div>
                ))}
              </div>

              {/* Connectors: each pane feeds the shared QASM frame below. */}
              <div
                aria-hidden="true"
                className={`hidden h-9 border-t border-qc-line bg-qc-surface-2/30 lg:grid lg:divide-x lg:divide-qc-line ${COLS}`}
              >
                {PROGRAMS.map((p) => (
                  <div key={p.id} className="relative flex items-end justify-center">
                    <span className="absolute inset-y-0 left-1/2 w-px bg-qc-line-strong" />
                    <ArrowDown className="relative -mb-px h-3.5 w-3.5 bg-qc-surface text-qc-subtle" />
                  </div>
                ))}
              </div>

              {/* QASM */}
              <div className="border-t border-qc-line">
                <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-b border-qc-line bg-qc-surface-2/60 px-4 py-2.5">
                  <span className="text-xs font-medium text-qc-fg">OpenQASM 3.0</span>
                  <div
                    className="flex flex-wrap items-center gap-1 sm:ml-auto"
                    role="group"
                    aria-label="QASM output from"
                  >
                    <span className="qc-eyebrow mr-1">Output from</span>
                    {QASM_VIEWS.map((v) => {
                      const on = v.id === viewId;
                      return (
                        <button
                          key={v.id}
                          type="button"
                          aria-pressed={on}
                          onClick={() => setViewId(v.id)}
                          className={`qc-focus flex items-center gap-2 rounded-lg px-2.5 py-1 text-xs transition-colors duration-150 motion-reduce:transition-none ${
                            on ? "bg-qc-surface-3 text-qc-fg" : "text-qc-subtle hover:text-qc-fg"
                          }`}
                        >
                          <span className="flex gap-0.5" aria-hidden="true">
                            {v.dots.map((d) => (
                              <span key={d} className={`h-1.5 w-1.5 rounded-full ${d}`} />
                            ))}
                          </span>
                          {v.label}
                        </button>
                      );
                    })}
                  </div>
                </div>
                <CodeLines
                  lines={qasmLines}
                  lang="qasm"
                  opFor={(line) => qasmOp(line)}
                  active={active}
                  setActive={setActive}
                />
                <p className="border-t border-qc-line px-4 py-2.5 text-xs text-qc-subtle">
                  {view.id === "shared"
                    ? "Qiskit and Cirq produce identical QASM."
                    : "Same h and cx gates. qml.counts() measures at run time, so there are no measure lines."}
                </p>
              </div>
            </div>

            <figcaption className="mt-4 text-xs text-qc-subtle">
              QASM shown is the output of the QCanvas converter, not hand-written.
            </figcaption>
          </figure>
        </Reveal>
      </div>
    </section>
  );
}
