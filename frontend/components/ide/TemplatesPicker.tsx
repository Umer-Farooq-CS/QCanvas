"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowUpRight, X } from "lucide-react";
import { FILE_TEMPLATES_PRESETS, type FileTemplate } from "@/lib/fileTemplates";

type Framework = "Qiskit" | "Cirq" | "PennyLane" | "Other";
type Filter = Framework | "All";

const FRAMEWORK_STYLE: Record<Framework, { dot: string; bar: string }> = {
  Qiskit: { dot: "bg-framework-qiskit", bar: "bg-framework-qiskit" },
  Cirq: { dot: "bg-framework-cirq", bar: "bg-framework-cirq" },
  PennyLane: { dot: "bg-framework-pennylane", bar: "bg-framework-pennylane" },
  Other: { dot: "bg-gray-400", bar: "bg-gray-400" },
};

function frameworkOf(t: FileTemplate): Framework {
  const key = `${t.filename} ${t.name}`.toLowerCase();
  if (key.includes("qiskit")) return "Qiskit";
  if (key.includes("cirq")) return "Cirq";
  if (key.includes("pennylane")) return "PennyLane";
  return "Other";
}

/** "Bell State (Qiskit)" -> "Bell State": the chip and colour already say the framework. */
function shortName(t: FileTemplate) {
  return t.name.replace(/\s*\((Qiskit|Cirq|PennyLane)\)\s*$/i, "");
}

export default function TemplatesPicker({
  open,
  onClose,
  onPick,
  onBrowseExamples,
}: Readonly<{
  open: boolean;
  onClose: () => void;
  onPick: (t: FileTemplate) => Promise<void> | void;
  onBrowseExamples: () => void;
}>) {
  // The workshop runs on Qiskit, so that's the default view.
  const [filter, setFilter] = useState<Filter>("Qiskit");
  const [creating, setCreating] = useState<string | null>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  const counts = useMemo(() => {
    const c: Record<Filter, number> = { All: 0, Qiskit: 0, Cirq: 0, PennyLane: 0, Other: 0 };
    for (const t of FILE_TEMPLATES_PRESETS) {
      c.All += 1;
      c[frameworkOf(t)] += 1;
    }
    return c;
  }, []);

  const filters = (["Qiskit", "Cirq", "PennyLane", "All"] as Filter[]).filter((f) => counts[f] > 0);
  const visible = FILE_TEMPLATES_PRESETS.filter((t) => filter === "All" || frameworkOf(t) === filter);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    // Move focus into the dialog for keyboard users.
    const first = panelRef.current?.querySelector<HTMLElement>("[data-autofocus]");
    first?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  const pick = async (t: FileTemplate) => {
    if (creating) return;
    setCreating(t.filename);
    try {
      await onPick(t);
    } finally {
      setCreating(null);
    }
  };

  return (
    <>
      <button
        type="button"
        className="qc-fade-in fixed inset-0 z-[55] cursor-default bg-black/55 backdrop-blur-[2px]"
        onClick={onClose}
        aria-label="Close templates"
        tabIndex={-1}
      />
      <div className="pointer-events-none fixed inset-0 z-[60] flex items-center justify-center p-4">
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="templates-title"
          className="qc-pop-in pointer-events-auto flex max-h-[82vh] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-editor-border bg-editor-sidebar shadow-[0_32px_80px_-24px_rgba(0,0,0,0.7)]"
        >
          <div className="flex items-start justify-between gap-4 px-6 pb-4 pt-5">
            <div>
              <h3 id="templates-title" className="text-base font-semibold text-white">
                New file from a template
              </h3>
              <p className="mt-1 text-xs text-editor-text">
                Each template runs as-is. Pick one to open it in a new tab.
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="grid h-8 w-8 place-items-center rounded-md text-editor-text transition-colors hover:bg-white/5 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
              aria-label="Close"
            >
              <X className="h-4 w-4" />
            </button>
          </div>

          <div className="flex flex-wrap items-center gap-2 px-6 pb-4" role="tablist" aria-label="Framework">
            {filters.map((f) => {
              const active = filter === f;
              return (
                <button
                  key={f}
                  type="button"
                  role="tab"
                  aria-selected={active}
                  {...(active ? { "data-autofocus": true } : {})}
                  onClick={() => setFilter(f)}
                  className={`flex items-center gap-2 rounded-full border px-3 py-1 text-xs transition-colors duration-150 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400 ${
                    active
                      ? "border-indigo-400/60 bg-indigo-500/15 text-white"
                      : "border-editor-border text-editor-text hover:border-white/20 hover:text-white"
                  }`}
                >
                  {f !== "All" && (
                    <span className={`h-1.5 w-1.5 rounded-full ${FRAMEWORK_STYLE[f as Framework].dot}`} aria-hidden="true" />
                  )}
                  {f}
                  <span className="tabular-nums opacity-80">{counts[f]}</span>
                </button>
              );
            })}
            <button
              type="button"
              onClick={onBrowseExamples}
              className="ml-auto inline-flex items-center gap-1 text-xs text-indigo-300 hover:text-indigo-200"
            >
              More in Examples
              <ArrowUpRight className="h-3.5 w-3.5" aria-hidden="true" />
            </button>
          </div>

          <div className="grid gap-3 overflow-y-auto border-t border-editor-border px-6 py-5 md:grid-cols-2">
            {visible.map((t, i) => {
              const fw = frameworkOf(t);
              const busy = creating === t.filename;
              return (
                <button
                  key={t.filename}
                  type="button"
                  disabled={!!creating}
                  onClick={() => void pick(t)}
                  style={{ animationDelay: `${Math.min(i, 8) * 25}ms` }}
                  className="qc-fade-in group relative flex flex-col overflow-hidden rounded-xl border border-editor-border bg-editor-bg p-4 pl-5 text-left transition-[border-color,transform,background-color] duration-150 hover:-translate-y-px hover:border-white/20 hover:bg-editor-bg active:translate-y-0 active:scale-[0.99] disabled:cursor-wait disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-indigo-400"
                >
                  <span className={`absolute inset-y-0 left-0 w-[3px] ${FRAMEWORK_STYLE[fw].bar} opacity-70 transition-opacity group-hover:opacity-100`} aria-hidden="true" />
                  <span className="flex items-center justify-between gap-3">
                    <span className="text-sm font-medium text-white">{shortName(t)}</span>
                    <span className="flex items-center gap-1.5 text-[11px] text-editor-text">
                      <span className={`h-1.5 w-1.5 rounded-full ${FRAMEWORK_STYLE[fw].dot}`} aria-hidden="true" />
                      {fw}
                    </span>
                  </span>
                  <span className="mt-1.5 text-xs leading-relaxed text-editor-text">{t.description}</span>
                  <span className="mt-3 flex items-center justify-between gap-2">
                    <span className="truncate font-mono text-[11px] text-gray-500">{t.filename}</span>
                    <span className="shrink-0 text-xs text-indigo-300 opacity-0 transition-opacity duration-150 group-hover:opacity-100 group-focus-visible:opacity-100">
                      {busy ? "Creating…" : "Use template"}
                    </span>
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </>
  );
}
