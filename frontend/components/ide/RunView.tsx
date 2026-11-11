"use client";

import { useFileStore, useHasActiveFile } from "@/lib/store";
import SimulationControls from "@/components/SimulationControls";
import { InputLanguage } from "@/types";

export default function RunView({
  inputLanguage,
  setInputLanguage,
  simBackend,
  setSimBackend,
  shots,
  setShots,
  onRun,
  isRunning,
}: Readonly<{
  inputLanguage: InputLanguage | "";
  setInputLanguage: (language: InputLanguage | "") => void;
  simBackend: "cirq" | "qiskit" | "pennylane" | "";
  setSimBackend: (backend: "cirq" | "qiskit" | "pennylane" | "") => void;
  shots: number;
  setShots: (shots: number) => void;
  onRun: () => void | Promise<void>;
  isRunning: boolean;
}>) {
  const executionMode = useFileStore((s) => s.executionMode);
  const setExecutionMode = useFileStore((s) => s.setExecutionMode);
  const hasActiveFile = useHasActiveFile();

  return (
    <div className="h-full flex flex-col overflow-hidden ">
      <div className="h-10 px-3 flex items-center">
        <div className="text-xs font-semibold tracking-wider text-black dark:text-gray-400 uppercase">
          Run
        </div>
      </div>

      <div className="p-3 space-y-3 overflow-y-auto bg-gray-100">
        <div className="text-xs text-black dark:text-gray-400">
          Execution mode
        </div>
        <div className="grid grid-cols-2 gap-2">
          {(["basic", "expert"] as const).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setExecutionMode(m)}
              className={`px-2 py-2 text-xs rounded border ${
                executionMode === m
                  ? "bg-editor-accent border-editor-accent text-white"
                  : "bg-editor-panelLowest border-editor-border text-editor-text hover:bg-editor-panelHigh"
              }`}
            >
              {m}
            </button>
          ))}
        </div>

        <button
          type="button"
          disabled={!hasActiveFile || isRunning}
          className="w-full px-3 py-2 rounded text-sm font-semibold disabled:opacity-50 btn-quantum"
          onClick={() => onRun()}
        >
          {executionMode === "expert" ? "Run Hybrid" : "Run"}
        </button>

        {executionMode === "basic" && (
          <div className="pt-3">
            <SimulationControls
              inputLanguage={inputLanguage}
              setInputLanguage={setInputLanguage}
              simBackend={simBackend}
              setSimBackend={setSimBackend}
              shots={shots}
              setShots={setShots}
            />
          </div>
        )}
      </div>
    </div>
  );
}
