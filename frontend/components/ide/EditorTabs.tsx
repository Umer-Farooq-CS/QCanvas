"use client";

import { X } from "lucide-react";
import { memo, useMemo } from "react";
import { useFileListMeta, useFileStore } from "@/lib/store";

/** Framework hint from the filename, shown as a small coloured dot. */
function frameworkDot(name: string): string {
  const n = name.toLowerCase();
  if (n.endsWith(".qasm")) return "bg-amber-400";
  if (n.includes("qiskit")) return "bg-framework-qiskit";
  if (n.includes("cirq")) return "bg-framework-cirq";
  if (n.includes("pennylane")) return "bg-framework-pennylane";
  return "bg-gray-500";
}

function EditorTabs() {
  const openFileIds = useFileStore((s) => s.openFileIds);
  const files = useFileListMeta();
  const activeFileId = useFileStore((s) => s.activeFileId);
  const openFile = useFileStore((s) => s.openFile);
  const closeFile = useFileStore((s) => s.closeFile);

  const openFiles = useMemo(() => {
    const byId = new Map(files.map((f) => [f.id, f]));
    return openFileIds.map((id) => byId.get(id)).filter(Boolean);
  }, [files, openFileIds]);

  if (openFiles.length === 0) return null;

  return (
    <div
      role="tablist"
      aria-label="Open files"
      className="flex h-9 shrink-0 items-end gap-px overflow-x-auto border-b border-editor-border bg-editor-sidebar px-1 [scrollbar-width:thin]"
    >
      {openFiles.map((f: any) => {
        const active = activeFileId === f.id;
        return (
          <div
            key={f.id}
            onMouseDown={(e) => {
              // Middle-click closes the tab, like every desktop editor.
              if (e.button === 1) {
                e.preventDefault();
                closeFile(f.id);
              }
            }}
            className={`group relative flex h-8 shrink-0 items-center rounded-t-md transition-colors duration-100 ${
              active
                ? "bg-editor-bg text-white"
                : "text-editor-text hover:bg-white/[0.04] hover:text-white"
            }`}
          >
            {active && (
              <span className="absolute inset-x-0 top-0 h-0.5 rounded-full bg-editor-accent" aria-hidden="true" />
            )}
            <button
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => openFile(f.id)}
              title={f.name}
              className="flex h-full items-center gap-2 pl-3 pr-1 text-xs focus-visible:outline-none focus-visible:underline"
            >
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${frameworkDot(f.name)}`} aria-hidden="true" />
              <span className="max-w-[14rem] truncate">{f.name}</span>
            </button>
            <button
              type="button"
              onClick={() => closeFile(f.id)}
              title={`Close ${f.name}`}
              aria-label={`Close ${f.name}`}
              className={`mr-1.5 grid h-5 w-5 place-items-center rounded transition-[opacity,background-color] duration-100 hover:bg-white/10 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-400 ${
                active ? "opacity-80" : "opacity-0 group-hover:opacity-80"
              }`}
            >
              <X className="h-3 w-3" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export default memo(EditorTabs);
