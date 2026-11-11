"use client";

import { X } from "lucide-react";
import { memo, useMemo } from "react";
import { useFileListMeta, useFileStore } from "@/lib/store";

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
    <div className="h-9 bg-slate-100 dark:bg-slate-900 flex items-end overflow-x-auto px-1.5 gap-0.5">
      {openFiles.map((f: any) => (
        <button
          key={f.id}
          type="button"
          className={`flex items-center gap-2 px-3 h-8 rounded-t-md transition-colors ${
            activeFileId === f.id
              ? "bg-gray-200 text-white dark:bg-gray-800"
              : "bg-editor-sidebar text-editor-text hover:bg-editor-panelHigh/70"
          }`}
          onClick={() => openFile(f.id)}
          role="tab"
          aria-selected={activeFileId === f.id}
        >
          <span className="text-xs whitespace-nowrap">{f.name}</span>
          <button
            type="button"
            className="p-1 rounded hover:bg-editor-bg/10"
            onClick={(e) => {
              e.stopPropagation();
              closeFile(f.id);
            }}
            title="Close"
          >
            <X className="w-3 h-3" />
          </button>
        </button>
      ))}
    </div>
  );
}

export default memo(EditorTabs);
