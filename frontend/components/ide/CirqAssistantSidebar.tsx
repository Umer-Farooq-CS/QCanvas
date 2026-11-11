"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import toast from "react-hot-toast";
import {
  Copy,
  Loader2,
  History,
  ChevronDown,
  ChevronRight,
  MessageSquare,
  Settings,
  Send,
  Paperclip,
  Mic,
  Image as ImageIcon,
} from "lucide-react";
import { generateCirqCode, getCirqRun, listCirqRuns } from "@/lib/cirqAgentApi";
import { useAuthStore } from "@/lib/authStore";
import { EDITOR_FLUSH_EVENT, useFileStore } from "@/lib/store";
import type { InputLanguage } from "@/types";
import type { Dispatch, SetStateAction } from "react";
import type {
  CirqAgentClientConfig,
  CirqAgentStep,
  CirqRunSummary,
  EducationalDepth,
  GenerateCirqResponse,
} from "@/types/cirqAgent";
import dynamic from "next/dynamic";

import CirqCodePreview from "./CirqCodePreview";

// react-markdown + remark/rehype + KaTeX are only needed once an explanation
// is shown, so keep them out of the /app first-load bundle.
const CirqExplanationMarkdown = dynamic(
  () => import("./CirqExplanationMarkdown"),
  { ssr: false },
);

const STARTER_PROMPTS = [
  "Create a Bell state in Cirq",
  "Implement a 3-qubit Quantum Fourier Transform circuit",
  "Build a QAOA circuit for the MaxCut problem",
  "Generate a VQE ansatz with alternating CNOT layers",
];

const AGENT_LABELS: Record<string, string> = {
  designer: "Designer",
  validator: "Validator",
  optimizer: "Optimizer",
  final_validator: "Final validator",
  educational: "Educational",
};

function statusClass(status: string) {
  switch (status) {
    case "success":
      return "text-emerald-600 dark:text-emerald-300";
    case "warning":
      return "text-amber-600 dark:text-amber-400";
    case "error":
      return "text-red-600 dark:text-red-300";
    default:
      return "text-editor-text/70";
  }
}

function filterAgents(
  agents: CirqAgentStep[],
  optimizerWasEnabled: boolean,
): CirqAgentStep[] {
  if (optimizerWasEnabled) return agents;
  return agents.filter((a) => a.name !== "optimizer");
}

interface Turn {
  id: string;
  prompt: string;
  optimizerEnabled: boolean;
  result?: GenerateCirqResponse;
  error?: string;
}

function Toggle({
  checked,
  onChange,
  disabled,
  label,
  description,
}: Readonly<{
  checked: boolean;
  onChange?: (next: boolean) => void;
  disabled?: boolean;
  label: string;
  description?: string;
}>) {
  const isDisabled = !!disabled || !onChange;
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="min-w-0">
        <div
          className={`text-sm ${isDisabled ? "text-editor-text/55" : "text-editor-text"}`}
        >
          {label}
        </div>
        {description && (
          <div className="text-[11px] text-editor-text/55 mt-0.5">
            {description}
          </div>
        )}
      </div>
      <button
        type="button"
        disabled={isDisabled}
        onClick={() => onChange?.(!checked)}
        className={`relative inline-flex h-6 w-11 items-center rounded-full border transition-colors ${
          checked
            ? "bg-emerald-400/80 border-emerald-400/40"
            : "bg-slate-800/60 border-editor-border/40"
        } ${isDisabled ? "opacity-60 cursor-not-allowed" : "hover:brightness-110"}`}
        aria-pressed={checked}
        aria-label={label}
      >
        <span
          className={`inline-block h-5 w-5 transform rounded-full bg-slate-950 shadow transition-transform ${
            checked ? "translate-x-5" : "translate-x-1"
          }`}
        />
      </button>
    </div>
  );
}

export default function CirqAssistantSidebar({
  prefillPayload,
  onPrefillConsumed,
  onSetInputLanguage,
}: Readonly<{
  /** nonce must change each time the menu triggers “Ask AI”, even if text repeats */
  prefillPayload: { nonce: number; text: string } | null;
  onPrefillConsumed: () => void;
  onSetInputLanguage: Dispatch<SetStateAction<InputLanguage | "">>;
}>) {
  const currentUser = useAuthStore((s) => s.user);
  const canUseAssistant = currentUser?.role === "admin";

  const [activeTab, setActiveTab] = useState<"chat" | "settings">("chat");
  const [config, setConfig] = useState<CirqAgentClientConfig>({
    designerEnabled: true,
    validatorEnabled: false,
    optimizerEnabled: false,
    finalValidatorEnabled: true,
    educationalEnabled: false,
    educationalDepth: "intermediate",
    maxOptimizationLoops: 3,
  });
  const [algorithmHint, setAlgorithmHint] = useState("");
  const [input, setInput] = useState("");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [historyOpen, setHistoryOpen] = useState(false);
  const [runs, setRuns] = useState<CirqRunSummary[]>([]);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const lastPrefillNonce = useRef<number | null>(null);

  const loadRuns = useCallback(async () => {
    if (!canUseAssistant) return;
    setLoadingRuns(true);
    try {
      const list = await listCirqRuns();
      setRuns(list);
    } catch (e) {
      toast.error(
        e instanceof Error ? e.message : "Could not load run history",
      );
    } finally {
      setLoadingRuns(false);
    }
  }, [canUseAssistant]);

  useEffect(() => {
    if (historyOpen) void loadRuns();
  }, [historyOpen, loadRuns]);

  const runGenerate = useCallback(
    async (description: string) => {
      const trimmed = description.trim();
      if (!trimmed) return;

      if (!canUseAssistant) {
        toast.error(
          "You do not have permission to use the Cirq-RAG assistant.",
        );
        return;
      }

      // Enforce locked stages (Designer + Final Validator always enabled).
      const effectiveConfig: CirqAgentClientConfig = {
        ...config,
        designerEnabled: true,
        finalValidatorEnabled: true,
      };

      const id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}`;
      setTurns((t) => [
        ...t,
        { id, prompt: trimmed, optimizerEnabled: config.optimizerEnabled },
      ]);
      setIsGenerating(true);

      try {
        const algo = algorithmHint.trim() || undefined;
        const res = await generateCirqCode(trimmed, effectiveConfig, algo);
        setTurns((t) =>
          t.map((row) => (row.id === id ? { ...row, result: res } : row)),
        );

        if (res.status === "error") {
          const raw = res.raw_result as { errors?: unknown };
          const detail =
            Array.isArray(raw?.errors) && raw.errors.length
              ? String(raw.errors[0])
              : "Generation reported an error.";
          toast.error(detail);
        } else {
          void loadRuns();
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : "Request failed";
        setTurns((t) =>
          t.map((row) => (row.id === id ? { ...row, error: msg } : row)),
        );
        toast.error(msg);
      } finally {
        setIsGenerating(false);
      }
    },
    [algorithmHint, canUseAssistant, config, loadRuns],
  );

  useEffect(() => {
    if (!prefillPayload) {
      lastPrefillNonce.current = null;
      return;
    }
    if (lastPrefillNonce.current === prefillPayload.nonce) return;
    lastPrefillNonce.current = prefillPayload.nonce;
    const p = prefillPayload.text;
    onPrefillConsumed();
    void runGenerate(p);
  }, [prefillPayload, onPrefillConsumed, runGenerate]);

  const handleSubmit = () => {
    if (isGenerating) return;
    void runGenerate(input);
    setInput("");
  };

  const handleLoadRun = async (runId: string) => {
    try {
      const res = await getCirqRun(runId);
      const id =
        typeof crypto !== "undefined" && crypto.randomUUID
          ? crypto.randomUUID()
          : `${Date.now()}`;
      const meta = runs.find((r) => r.run_id === runId);
      setTurns((t) => [
        ...t,
        {
          id,
          prompt: res.prompt || meta?.prompt_preview || "(history)",
          optimizerEnabled: meta?.enable_optimizer ?? true,
          result: res,
        },
      ]);
      setHistoryOpen(false);
      toast.success("Loaded run");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load run");
    }
  };

  const copyCode = (code: string) => {
    void navigator.clipboard.writeText(code);
    toast.success("Copied to clipboard");
  };

  const loadIntoCanvas = (code: string | null | undefined) => {
    if (!code) {
      toast.error("No code to load");
      return;
    }
    const f = useFileStore.getState().getActiveFile();
    if (!f) {
      toast.error("Open or create a file first");
      return;
    }
    // Flush pending (debounced) keystrokes first so they can't land after,
    // and overwrite, the generated code.
    window.dispatchEvent(new Event(EDITOR_FLUSH_EVENT));
    useFileStore.getState().updateFileContent(f.id, code);
    onSetInputLanguage("cirq");
    toast.success("Loaded into editor (Cirq)");
  };

  return (
    <div className="flex flex-col h-full min-h-0 text-editor-text">
      {/* Tab bar (match Stitch multi-tab shell, but only 2 tabs) */}
      <div className="shrink-0 px-5 pt-4">
        <div className="flex gap-1 bg-gray-100/90 dark:bg-slate-800/40 p-1 rounded-xl border border-editor-border/30">
          <button
            type="button"
            onClick={() => setActiveTab("chat")}
            className={`flex-1 flex flex-col items-center justify-center py-2 rounded-lg transition-all ${
              activeTab === "chat"
                ? "bg-emerald-200/50 text-emerald-600/80 dark:bg-emerald-400/10 dark:text-emerald-300"
                : "text-editor-text/70 hover:bg-white/5 hover:text-editor-text"
            }`}
          >
            <MessageSquare className="w-5 h-5" />
            <span className="text-[10px] mt-1 tracking-tight font-medium">
              AI Chat
            </span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("settings")}
            className={`flex-1 flex flex-col items-center justify-center py-2 rounded-lg transition-all ${
              activeTab === "settings"
                ? "bg-emerald-200/50 text-emerald-600/80 dark:bg-emerald-400/10 dark:text-emerald-300"
                : "text-editor-text/70 hover:bg-gray-300/5 hover:text-editor-text"
            }`}
          >
            <Settings className="w-5 h-5" />
            <span className="text-[10px] mt-1 tracking-tight font-medium">
              Settings
            </span>
          </button>
        </div>
      </div>

      {activeTab === "settings" ? (
        <div className="flex-1 min-h-0 overflow-y-auto px-5 py-4 space-y-4">
          <div className="rounded-2xl border border-editor-border/30 bg-gray-200/20 dark:bg-slate-800/20 p-4 space-y-3 text-xs">
            <div className="text-[10px] uppercase tracking-[0.22em] text-editor-text/60">
              Agents
            </div>

            <Toggle
              label="Designer"
              description="Always runs first (locked)"
              checked
              disabled
            />

            <Toggle
              label="Validator"
              description="Initial validation stage"
              checked={config.validatorEnabled}
              onChange={(next) =>
                setConfig((c) => ({ ...c, validatorEnabled: next }))
              }
              disabled={isGenerating}
            />

            <Toggle
              label="Optimizer"
              description="Optimizes code + loops with validator"
              checked={config.optimizerEnabled}
              onChange={(next) =>
                setConfig((c) => ({ ...c, optimizerEnabled: next }))
              }
              disabled={isGenerating}
            />

            <Toggle
              label="Final validator"
              description="Always runs at the end (locked)"
              checked
              disabled
            />
          </div>

          <div className="rounded-2xl border border-editor-border/30 bg-gray-200/20 dark:bg-slate-800/20 p-4 space-y-3 text-xs">
            <div className="text-[10px] uppercase tracking-[0.22em] text-editor-text/60">
              Education
            </div>

            <Toggle
              label="Educational agent"
              description="Adds explanations and learning material"
              checked={config.educationalEnabled}
              onChange={(next) =>
                setConfig((c) => ({ ...c, educationalEnabled: next }))
              }
              disabled={isGenerating}
            />

            {config.educationalEnabled && (
              <div className="pt-1">
                <div className="text-[11px] text-editor-text/60 mb-2">
                  Explanation depth
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {(
                    [
                      ["low", "Low"],
                      ["intermediate", "Medium"],
                      ["high", "High"],
                      ["very_high", "Very High"],
                    ] as const
                  ).map(([value, label]) => {
                    const active = config.educationalDepth === value;
                    return (
                      <button
                        key={value}
                        type="button"
                        disabled={isGenerating}
                        onClick={() =>
                          setConfig((c) => ({
                            ...c,
                            educationalDepth: value as EducationalDepth,
                          }))
                        }
                        className={`px-3 py-2 rounded-xl text-xs border transition-colors ${
                          active
                            ? "bg-emerald-400/10 text-emerald-200 border-emerald-400/30"
                            : "bg-slate-900/20 text-editor-text/70 border-editor-border/30 hover:bg-white/5 hover:text-editor-text"
                        } ${isGenerating ? "opacity-60 cursor-not-allowed" : ""}`}
                      >
                        {label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          <div className="rounded-2xl border border-editor-border/30 bg-gray-200/20 dark:bg-slate-800/20 p-4 space-y-3 text-xs">
            <div className="text-[10px] uppercase tracking-[0.22em] text-editor-text/60">
              Optimization
            </div>

            <label className="flex flex-col gap-1">
              <span>Max optimization loops (1–10)</span>
              <input
                type="number"
                min={1}
                max={10}
                className="bg-editor-bg border border-editor-border rounded px-2 py-1.5 text-editor-text"
                value={config.maxOptimizationLoops}
                disabled={!config.optimizerEnabled}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (Number.isFinite(n))
                    setConfig((c) => ({
                      ...c,
                      maxOptimizationLoops: Math.min(10, Math.max(1, n)),
                    }));
                }}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span>Algorithm hint (optional)</span>
              <input
                className="bg-editor-bg border border-editor-border rounded px-2 py-1.5 text-editor-text placeholder:text-editor-text/40"
                placeholder="e.g. vqe, qaoa, grover"
                value={algorithmHint}
                onChange={(e) => setAlgorithmHint(e.target.value)}
              />
            </label>
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto px-5 py-4 space-y-6">
          <button
            type="button"
            onClick={() => setHistoryOpen((o) => !o)}
            className="w-full flex items-center justify-between text-xs text-editor-text/75 hover:text-white"
          >
            <span className="flex items-center gap-1">
              <History className="w-3.5 h-3.5" />
              Session run history
            </span>
            {historyOpen ? (
              <ChevronDown className="w-4 h-4" />
            ) : (
              <ChevronRight className="w-4 h-4" />
            )}
          </button>

          <AnimatePresence>
            {historyOpen && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="overflow-hidden"
              >
                <p className="text-[11px] text-amber-400/90 mb-2">
                  History is stored in memory on the Cirq service and is lost
                  when it restarts.
                </p>
                {loadingRuns ? (
                  <div className="flex justify-center py-4">
                    <Loader2 className="w-5 h-5 animate-spin text-quantum-blue-light" />
                  </div>
                ) : (
                  (() => {
                    if (runs.length === 0) {
                      return (
                        <p className="text-xs text-editor-text/50">
                          No runs yet.
                        </p>
                      );
                    }
                    return (
                      <ul className="space-y-1 max-h-40 overflow-y-auto">
                        {runs.map((r) => (
                          <li key={r.run_id}>
                            <button
                              type="button"
                              className="w-full text-left text-xs px-2 py-1.5 rounded hover:bg-editor-border/60 truncate"
                              onClick={() => void handleLoadRun(r.run_id)}
                              title={r.prompt_preview}
                            >
                              <span className="text-editor-text/60">
                                {new Date(r.created_at).toLocaleString()}
                              </span>
                              <br />
                              <span className="text-editor-text">
                                {r.prompt_preview}
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    );
                  })()
                )}
              </motion.div>
            )}
          </AnimatePresence>

          {turns.length === 0 && !isGenerating && (
            <div className="space-y-2">
              <p className="text-xs text-editor-text/60">Quick starters</p>
              <div className="flex flex-col gap-1.5">
                {STARTER_PROMPTS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    disabled={isGenerating}
                    className="text-left text-xs px-2 py-2 rounded border border-editor-border hover:border-quantum-blue-light/50 hover:bg-editor-border/30 transition-colors disabled:opacity-50"
                    onClick={() => void runGenerate(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="space-y-4">
            {turns.map((turn, idx) => (
              <motion.div
                key={turn.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: idx * 0.03 }}
                className="space-y-3"
              >
                {/* User bubble */}
                <div className="flex flex-col items-end gap-2">
                  <div className="bg-slate-800/60 border border-editor-border/20 px-4 py-3 rounded-2xl rounded-tr-md max-w-[92%] text-sm text-editor-text leading-relaxed">
                    {turn.prompt}
                  </div>
                  <div className="text-[10px] text-editor-text/45 uppercase tracking-widest px-1">
                    User
                  </div>
                </div>

                {turn.error && (
                  <div className="text-sm text-red-400 border border-red-500/30 rounded-xl p-3 bg-red-500/10">
                    {turn.error}
                  </div>
                )}

                {turn.result &&
                  (() => {
                    const result = turn.result;
                    return (
                      <>
                        {/* Assistant header */}
                        <div className="flex items-center gap-2">
                          <div className="w-6 h-6 rounded-full bg-emerald-400/15 flex items-center justify-center border border-emerald-400/20">
                            <span className="text-emerald-300 text-[11px] font-bold">
                              AI
                            </span>
                          </div>
                          <div className="text-[10px] text-emerald-300 font-bold uppercase tracking-widest">
                            Cirq-RAG
                          </div>
                        </div>

                        <div className="bg-slate-800/25 border border-editor-border/25 px-4 py-4 rounded-2xl rounded-tl-md w-full text-sm text-editor-text leading-relaxed space-y-4">
                          <div className="text-[10px] text-editor-text/55 uppercase tracking-[0.22em]">
                            Pipeline
                          </div>
                          <ul className="space-y-2">
                            {filterAgents(
                              result.agents || [],
                              turn.optimizerEnabled,
                            ).map((a, i) => (
                              <motion.li
                                key={`${turn.id}-${a.name}-${i}`}
                                initial={{ opacity: 0, x: -4 }}
                                animate={{ opacity: 1, x: 0 }}
                                transition={{ delay: i * 0.05 }}
                                className="text-xs border-l-2 border-editor-border pl-2"
                              >
                                <div className="font-medium text-white">
                                  {AGENT_LABELS[a.name] ?? a.name}
                                  <span
                                    className={`ml-2 ${statusClass(String(a.status))}`}
                                  >
                                    {a.status}
                                  </span>
                                </div>
                                {a.summary && (
                                  <p className="text-editor-text/75 mt-0.5">
                                    {a.summary}
                                  </p>
                                )}
                              </motion.li>
                            ))}
                          </ul>

                          {turn.result.agents && (
                            <div className="text-[11px] text-editor-text/60 space-y-1">
                              {(() => {
                                const opt = result.agents?.find(
                                  (x) => x.name === "optimizer",
                                );
                                const m = opt?.metrics;
                                if (
                                  m &&
                                  typeof m.gate_count_before === "number" &&
                                  typeof m.gate_count_after === "number"
                                ) {
                                  return (
                                    <p>
                                      Gates: {m.gate_count_before} →{" "}
                                      {m.gate_count_after}
                                    </p>
                                  );
                                }
                                return null;
                              })()}
                              {(() => {
                                const fv = result.agents?.find(
                                  (x) => x.name === "final_validator",
                                );
                                const m = fv?.metrics;
                                if (
                                  m &&
                                  typeof m.validation_passed === "boolean"
                                ) {
                                  return (
                                    <p>
                                      Final validation:{" "}
                                      {m.validation_passed
                                        ? "passed"
                                        : "not passed"}
                                    </p>
                                  );
                                }
                                return null;
                              })()}
                            </div>
                          )}

                          {result.final_code ? (
                            <>
                              <div className="flex items-center justify-between gap-2">
                                <span className="text-[10px] text-editor-text/55 uppercase tracking-[0.22em]">
                                  Output
                                </span>
                                <div className="flex gap-1.5">
                                  <button
                                    type="button"
                                    className="px-3 py-2 rounded-md text-xs bg-slate-900/70 border border-editor-border/30 hover:bg-white/5 text-editor-text"
                                    onClick={() =>
                                      copyCode(result.final_code ?? "")
                                    }
                                  >
                                    <Copy className="w-3.5 h-3.5 inline mr-1" />
                                    Copy
                                  </button>
                                  <button
                                    type="button"
                                    className="px-3 py-2 rounded-md text-xs font-semibold bg-gradient-to-br from-quantum-blue-light to-cyan-300 text-black hover:opacity-95"
                                    onClick={() =>
                                      loadIntoCanvas(result.final_code)
                                    }
                                  >
                                    Apply to Editor
                                  </button>
                                </div>
                              </div>

                              <div className="rounded-xl overflow-hidden border border-editor-border/25 bg-black/40">
                                <CirqCodePreview value={result.final_code} />
                              </div>
                            </>
                          ) : (
                            <p className="text-sm text-amber-400/90">
                              Code generation did not return final code.
                            </p>
                          )}

                          {result.status === "error" && (
                            <p className="text-sm text-red-400">
                              Run finished with error status. See raw details in
                              the response if needed.
                            </p>
                          )}

                          {(() => {
                            const ex = result.explanation;
                            if (!ex || typeof ex !== "object") return null;
                            const md =
                              "markdown" in ex &&
                              typeof ex.markdown === "string"
                                ? ex.markdown
                                : null;
                            if (!md) return null;
                            const depth = ex.depth as
                              | EducationalDepth
                              | undefined;
                            return (
                              <div className="rounded-xl border border-editor-border/25 bg-black/20 p-3">
                                <div className="text-[10px] text-editor-text/55 uppercase tracking-[0.22em] mb-2">
                                  Explanation
                                  {depth ? ` (${depth})` : ""}
                                </div>
                                <CirqExplanationMarkdown
                                  markdown={md}
                                  useMath={depth === "very_high"}
                                />
                              </div>
                            );
                          })()}
                        </div>
                      </>
                    );
                  })()}
              </motion.div>
            ))}
          </div>
        </div>
      )}

      <div className="shrink-0 border-t border-editor-border/40 px-5 py-4 bg-gray-300/20 dark:bg-slate-900/60">
        {!canUseAssistant && (
          <div className="mb-3 rounded-xl border border-amber-400/20 bg-amber-100/90 dark:bg-amber-500/10 px-3 py-2 text-xs text-amber-700/90 dark:text-amber-200/90">
            Cirq-RAG assistant is{" "}
            <span className="font-semibold">admin-only</span>.
          </div>
        )}
        {isGenerating && (
          <div className="flex items-center gap-2 text-xs text-emerald-600/90 dark:text-emerald-300/90">
            <Loader2 className="w-4 h-4 animate-spin" />
            Running pipeline (may take 15–60s)…
          </div>
        )}
        <div className="relative">
          <textarea
            className="w-full min-h-[96px] max-h-[200px] resize-y rounded-2xl border border-editor-border/70 bg-gray-100/90 dark:bg-slate-800/30 px-4 py-4 pr-14 text-sm text-editor-text placeholder:text-editor-text/80 focus:outline-none focus:ring-1 focus:ring-emerald-400/40 disabled:opacity-50"
            placeholder="Ask the assistant…"
            value={input}
            disabled={isGenerating}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
          />
          <button
            type="button"
            disabled={isGenerating || !input.trim()}
            onClick={handleSubmit}
            className="absolute bottom-4 right-4 w-9 h-9 rounded-xl bg-emerald-400 text-slate-950 flex items-center justify-center hover:shadow-[0_0_18px_rgba(0,252,154,0.25)] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
            title="Send"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>

        <div className="flex items-center justify-between mt-3 px-1">
          <div className="flex items-center gap-3 text-editor-text/55">
            <button
              type="button"
              className="hover:text-emerald-300 transition-colors"
              title="Attach"
            >
              <Paperclip className="w-4 h-4" />
            </button>
            <button
              type="button"
              className="hover:text-emerald-300 transition-colors"
              title="Mic"
            >
              <Mic className="w-4 h-4" />
            </button>
            <button
              type="button"
              className="hover:text-emerald-300 transition-colors"
              title="Image"
            >
              <ImageIcon className="w-4 h-4" />
            </button>
          </div>
          <div className="text-[10px] text-editor-text/50 font-mono">
            Cirq • context: 4.2k tokens
          </div>
        </div>
      </div>
    </div>
  );
}
