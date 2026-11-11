"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useFileStore } from "@/lib/store";
import MenuBar from "./MenuBar";
import ActivityBar, { ActivityView } from "./ActivityBar";
import ExplorerView from "./ExplorerView";
import SearchView from "./SearchView";
import EditorTabs from "./EditorTabs";

export default function IDELayout({
  editor,
  bottom,
  bottomDragHandle,
  sidebarOverlay,
  sidebarContainerClassName,
  sidebarContainerStyle,
  sidebarResizeHandle,
  runView,
  cirqAssistantView,
  rightPanelOpen,
  onRightPanelClose,
  onRun,
  onAskAiAboutCircuit,
  sidebarActivity,
  onSidebarActivityChange,
  contentRef,
}: Readonly<{
  editor: React.ReactNode;
  bottom: React.ReactNode;
  bottomDragHandle: React.ReactNode;
  sidebarOverlay?: React.ReactNode;
  sidebarContainerClassName?: string;
  sidebarContainerStyle?: React.CSSProperties;
  sidebarResizeHandle?: React.ReactNode;
  runView?: React.ReactNode;
  cirqAssistantView?: React.ReactNode;
  rightPanelOpen?: boolean;
  onRightPanelClose?: () => void;
  onRun: () => void | Promise<void>;
  onAskAiAboutCircuit?: () => void;
  sidebarActivity: ActivityView;
  onSidebarActivityChange: (v: ActivityView) => void;
  contentRef?: React.RefObject<HTMLDivElement>;
}>) {
  const sidebarCollapsed = useFileStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useFileStore((s) => s.toggleSidebar);

  // VS Code-style activity bar: clicking the active view hides the sidebar,
  // clicking any view while the sidebar is hidden shows it again.
  const handleActivityClick = useCallback(
    (id: ActivityView) => {
      if (id === "cirqAssistant") {
        onSidebarActivityChange(id);
        return;
      }
      if (sidebarCollapsed) {
        onSidebarActivityChange(id);
        toggleSidebar();
        return;
      }
      if (id === sidebarActivity) {
        toggleSidebar();
        return;
      }
      onSidebarActivityChange(id);
    },
    [sidebarCollapsed, sidebarActivity, onSidebarActivityChange, toggleSidebar],
  );
  const [rightPanelWidth, setRightPanelWidth] = useState<number>(() => {
    if (globalThis.window === undefined) return 420;
    const stored = globalThis.window.localStorage.getItem(
      "qcanvas:rightPanelWidth",
    );
    const n = stored ? Number.parseInt(stored, 10) : 420;
    return Number.isFinite(n) ? n : 420;
  });
  const dragStateRef = useRef<{
    startX: number;
    startWidth: number;
    maxWidth: number;
  } | null>(null);

  const clampedRightPanelWidth = useMemo(() => {
    const minWidth = 340;
    const maxWidth =
      globalThis.window === undefined
        ? 720
        : Math.min(720, globalThis.window.innerWidth - 420);
    return Math.min(Math.max(rightPanelWidth, minWidth), maxWidth);
  }, [rightPanelWidth]);

  useEffect(() => {
    if (globalThis.window === undefined) return;
    globalThis.window.localStorage.setItem(
      "qcanvas:rightPanelWidth",
      String(clampedRightPanelWidth),
    );
  }, [clampedRightPanelWidth]);

  useEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragStateRef.current) return;
      const dx = dragStateRef.current.startX - e.clientX;
      const next = dragStateRef.current.startWidth + dx;
      const minWidth = 340;
      const maxWidth = dragStateRef.current.maxWidth;
      setRightPanelWidth(Math.min(Math.max(next, minWidth), maxWidth));
    };
    const onUp = () => {
      if (!dragStateRef.current) return;
      dragStateRef.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };

    globalThis.window.addEventListener("mousemove", onMove);
    globalThis.window.addEventListener("mouseup", onUp);
    return () => {
      globalThis.window.removeEventListener("mousemove", onMove);
      globalThis.window.removeEventListener("mouseup", onUp);
    };
  }, []);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <MenuBar onRun={onRun} onAskAiAboutCircuit={onAskAiAboutCircuit} />

      <div className="flex flex-1 min-h-0 overflow-hidden">
        {/* Activity bar */}
        <ActivityBar
          active={sidebarActivity}
          assistantOpen={!!rightPanelOpen}
          sidebarCollapsed={sidebarCollapsed}
          onChange={handleActivityClick}
          onToggleSidebar={toggleSidebar}
        />

        {/* Sidebar panel */}
        <div
          className={sidebarContainerClassName}
          style={sidebarContainerStyle}
        >
          {!sidebarCollapsed && (
            <div className="h-full bg-editor-sidebar border-r border-editor-border overflow-hidden">
              {sidebarActivity === "explorer" && <ExplorerView />}
              {sidebarActivity === "search" && <SearchView />}
              {sidebarActivity === "run" && (runView ?? null)}
            </div>
          )}
        </div>

        {!sidebarCollapsed && sidebarResizeHandle}

        {sidebarOverlay}

        {/* Editor + Results stack */}
        <main className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div
            ref={contentRef}
            className="flex flex-col h-full overflow-hidden"
          >
            <EditorTabs />
            {editor}
            {bottomDragHandle}
            {bottom}
          </div>
        </main>

        {/* Right assistant drawer (Stitch-style) */}
        {rightPanelOpen && (
          <>
            <button
              type="button"
              aria-label="Resize assistant panel"
              title="Drag to resize assistant panel"
              className="w-1.5 shrink-0 h-full cursor-col-resize bg-transparent hover:bg-white/5 active:bg-white/10"
              onMouseDown={(e: React.MouseEvent) => {
                const maxWidth =
                  globalThis.window === undefined
                    ? 720
                    : Math.min(720, globalThis.window.innerWidth - 420);
                dragStateRef.current = {
                  startX: e.clientX,
                  startWidth: clampedRightPanelWidth,
                  maxWidth,
                };
                document.body.style.cursor = "col-resize";
                document.body.style.userSelect = "none";
              }}
            />
            <aside
              className="shrink-0 h-full border-l border-editor-border/60 bg-gray-200 dark:bg-slate-900/90 backdrop-blur-2xl shadow-[0_32px_72px_rgba(0,0,0,0.65)]"
              style={{ width: clampedRightPanelWidth }}
            >
              <div className="h-full flex flex-col min-h-0">
                <div className="shrink-0 px-5 pt-5 pb-4 border-b border-editor-border/40">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-emerald-400 font-semibold tracking-tight text-lg">
                        Cirq-RAG Assistant
                      </div>
                      <div className="mt-1 text-[11px] text-editor-text/70">
                        Quantum AI Agent Active | Model: Claude Opus 4.6
                      </div>
                    </div>
                    {onRightPanelClose && (
                      <button
                        type="button"
                        className="px-2.5 py-1.5 text-xs rounded-md text-editor-text/70 hover:text-white hover:bg-white/5 border border-editor-border/40"
                        onClick={onRightPanelClose}
                      >
                        Close
                      </button>
                    )}
                  </div>
                </div>

                <div className="flex-1 min-h-0">
                  {cirqAssistantView ?? null}
                </div>
              </div>
            </aside>
          </>
        )}
      </div>
    </div>
  );
}
