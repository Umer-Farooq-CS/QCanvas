"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw } from "lucide-react";
import { useReducedMotion } from "framer-motion";
import { StaticCircuit } from "@/components/CircuitVisualization";
import { layoutCircuit } from "@/lib/circuitLayout";
import { SITE_CIRCUITS, probabilities } from "@/lib/siteCircuits";

const SHOTS = 1024;

/**
 * "Circuit to counts": pick a circuit, step through it moment by moment and
 * watch the exact probabilities change; at the end, compare with the counts
 * from a real 1,024-shot run on the QCanvas simulator.
 */
export default function CircuitShowcase() {
  const reduce = useReducedMotion() ?? false;
  const [id, setId] = useState(SITE_CIRCUITS[0].id);
  const circuit = SITE_CIRCUITS.find((c) => c.id === id) ?? SITE_CIRCUITS[0];
  const layout = useMemo(() => layoutCircuit(circuit.gates, circuit.qubits), [circuit]);
  const total = layout.columns;
  const [step, setStep] = useState(total);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<number | null>(null);

  // New circuit: show it complete.
  useEffect(() => {
    setStep(total);
    setPlaying(false);
  }, [id, total]);

  // Play: advance one moment at a time.
  useEffect(() => {
    if (!playing) return;
    if (step >= total) {
      setPlaying(false);
      return;
    }
    timer.current = window.setTimeout(() => setStep((s) => Math.min(total, s + 1)), reduce ? 0 : 750);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [playing, step, total, reduce]);

  // Gates applied so far, in time order.
  const applied = useMemo(() => {
    const ops = layout.ops.filter((o) => o.column < step).sort((a, b) => a.column - b.column || a.id - b.id);
    return ops.map((o) => circuit.gates[o.id]);
  }, [layout, step, circuit]);
  const probs = useMemo(() => probabilities(circuit.qubits, applied), [circuit.qubits, applied]);
  const states = Object.keys(probs).sort();
  const done = step >= total;

  const play = () => {
    if (done) setStep(0);
    setPlaying((p) => !p || done);
  };

  const ctrl =
    "qc-focus grid h-9 w-9 place-items-center rounded-lg border border-qc-line text-qc-muted transition-colors duration-150 hover:border-qc-line-strong hover:text-qc-fg disabled:opacity-40";

  return (
    <div className="grid gap-5 lg:grid-cols-[1.45fr_1fr]">
      {/* Diagram + transport */}
      <div className="flex min-w-0 flex-col rounded-xl border border-qc-line bg-qc-surface">
        <div role="tablist" aria-label="Example circuit" className="flex flex-wrap gap-1 border-b border-qc-line px-3 pt-2">
          {SITE_CIRCUITS.map((c) => (
            <button
              key={c.id}
              role="tab"
              type="button"
              aria-selected={c.id === id}
              onClick={() => setId(c.id)}
              className={`qc-focus relative px-3 py-2.5 text-sm transition-colors duration-150 ${
                c.id === id ? "text-qc-fg" : "text-qc-subtle hover:text-qc-fg"
              }`}
            >
              {c.name}
              {c.id === id && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-qc-accent" aria-hidden="true" />}
            </button>
          ))}
        </div>

        <div className="flex flex-1 items-center px-4 py-6 sm:px-8">
          <StaticCircuit
            gates={circuit.gates}
            qubits={circuit.qubits}
            step={done ? undefined : step}
            className="mx-auto max-h-[17rem]"
            label={`${circuit.name} circuit`}
          />
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t border-qc-line px-4 py-3">
          <button type="button" className={ctrl} onClick={() => setStep((s) => Math.max(0, s - 1))} disabled={step === 0} aria-label="Previous moment">
            <ChevronLeft className="h-4 w-4" />
          </button>
          <button type="button" onClick={play} className="qc-btn qc-btn-secondary qc-btn-sm min-w-[7.5rem]">
            {playing ? <Pause className="h-3.5 w-3.5" aria-hidden="true" /> : <Play className="h-3.5 w-3.5" aria-hidden="true" />}
            {playing ? "Pause" : done ? "Step through" : "Play"}
          </button>
          <button type="button" className={ctrl} onClick={() => setStep((s) => Math.min(total, s + 1))} disabled={done} aria-label="Next moment">
            <ChevronRight className="h-4 w-4" />
          </button>
          <button type="button" className={ctrl} onClick={() => { setPlaying(false); setStep(0); }} aria-label="Back to the start">
            <RotateCcw className="h-3.5 w-3.5" />
          </button>
          <span className="ml-auto font-mono text-xs tabular-nums text-qc-subtle" aria-live="polite">
            moment {step} / {total}
          </span>
        </div>
      </div>

      {/* Probabilities and counts */}
      <div className="flex flex-col rounded-xl border border-qc-line bg-qc-surface p-5 sm:p-6">
        <p className="text-sm text-qc-muted">{circuit.blurb}</p>
        <div className="mt-5 flex items-baseline justify-between text-xs text-qc-subtle">
          <span>State</span>
          <span className="flex gap-6">
            <span>Exact</span>
            <span className={done ? "text-qc-signal" : ""}>Measured</span>
          </span>
        </div>
        <ul className="mt-2 space-y-2.5" aria-label="Probability of each outcome">
          {states.map((s) => {
            const pr = probs[s];
            const measured = circuit.counts[s] ?? 0;
            return (
              <li key={s} className="grid grid-cols-[3.25rem_1fr_3.25rem_3.25rem] items-center gap-3 font-mono text-xs">
                <span className="text-qc-muted">|{s}⟩</span>
                <span className="relative h-2 overflow-hidden rounded-full bg-qc-surface-3">
                  <span
                    className="absolute inset-y-0 left-0 rounded-full bg-qc-accent-solid transition-[width] duration-500 ease-out"
                    style={{ width: `${pr * 100}%` }}
                  />
                  {done && (
                    <span
                      className="absolute inset-y-[-3px] w-0.5 rounded-full bg-qc-signal"
                      style={{ left: `calc(${(measured / SHOTS) * 100}% - 1px)` }}
                      aria-hidden="true"
                    />
                  )}
                </span>
                <span className="text-right tabular-nums text-qc-fg">{(pr * 100).toFixed(pr > 0 && pr < 0.1 ? 1 : 0)}%</span>
                <span className={`text-right tabular-nums ${done ? "text-qc-signal" : "text-qc-subtle/50"}`}>
                  {done ? measured : "·"}
                </span>
              </li>
            );
          })}
        </ul>
        <p className="mt-6 border-t border-qc-line pt-4 text-sm leading-relaxed text-qc-muted">
          {done ? circuit.takeaway : "Bars show the exact probabilities after the gates so far. Step to the end to compare with a real run."}
        </p>
        <p className="mt-auto pt-4 text-xs text-qc-subtle">
          Measured: one 1,024-shot run on the QCanvas simulator (Qiskit backend). Bit order q0 first.
        </p>
      </div>
    </div>
  );
}
