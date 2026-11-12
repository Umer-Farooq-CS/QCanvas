"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import { useFileStore } from "@/lib/store";
import { InputLanguage } from "@/types";
import { detectFramework } from "@/lib/utils";

import EditorPane from "@/components/EditorPane";
import ResultsPane from "@/components/ResultsPane";
import IDELayout from "@/components/ide/IDELayout";
import RunView from "@/components/ide/RunView";
import dynamic from "next/dynamic";

// The assistant pulls in framer-motion + markdown; load it only when opened.
const CirqAssistantSidebar = dynamic(
  () => import("@/components/ide/CirqAssistantSidebar"),
  { ssr: false },
);
import type { ActivityView } from "@/components/ide/ActivityBar";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import {
  handleSessionExpired,
  hasValidAuth,
  useAuthStore,
} from "@/lib/authStore";
import { refreshSession, useSessionKeepAlive } from "@/lib/session";
import { useExecutionActions } from "@/components/ide/useExecutionActions";

/** Examples handed over to the editor expire after this long. */
const PENDING_EXAMPLE_TTL_MS = 10 * 60 * 1000;

/** Open an example handed over via sessionStorage (homepage / examples page). */
function openPendingExample() {
  let pendingJson: string | null = null;
  try {
    pendingJson = sessionStorage.getItem("pending-example");
    // Clear immediately so a refresh (or StrictMode re-run) can't create it twice.
    sessionStorage.removeItem("pending-example");
  } catch {
    return;
  }
  if (!pendingJson) return;
  try {
    const example = JSON.parse(pendingJson);
    // A hand-off left behind (e.g. "Open in editor" while signed out, then the
    // visitor wandered off) must not pop up in a later editor session.
    const fresh = typeof example?.savedAt !== "number" || Date.now() - example.savedAt < PENDING_EXAMPLE_TTL_MS;
    if (fresh && example?.name && example?.content) {
      void useFileStore.getState().createFile(example.name, example.content);
    }
  } catch (e) {
    console.error("Failed to parse pending example", e);
  }
}

export default function AppPage() {
  const router = useRouter();
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [isMobile, setIsMobile] = useState(false);
  const [resultsHeight, setResultsHeight] = useState(320); // Default height
  const [isDragging, setIsDragging] = useState(false);
  const [isSidebarResizing, setIsSidebarResizing] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(320);
  const containerRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const pendingResultsHeightRef = useRef<number>(320);
  const rafIdRef = useRef<number | null>(null);
  const pendingSidebarWidthRef = useRef<number>(320);
  const rafSidebarIdRef = useRef<number | null>(null);

  // Simulation settings state
  const [inputLanguage, setInputLanguage] = useState<InputLanguage | "">("");
  const [simBackend, setSimBackend] = useState<
    "cirq" | "qiskit" | "pennylane" | ""
  >("");
  const [shots, setShots] = useState(1024);
  const { run, isRunning } = useExecutionActions({
    inputLanguage,
    simBackend,
    shots,
  });

  // Narrow selectors: subscribing to the whole store re-rendered the entire
  // IDE on every keystroke.
  const sidebarCollapsed = useFileStore((s) => s.sidebarCollapsed);
  const toggleSidebar = useFileStore((s) => s.toggleSidebar);
  const resultsCollapsed = useFileStore((s) => s.resultsCollapsed);
  const executionMode = useFileStore((s) => s.executionMode);
  const activeFileId = useFileStore((s) => s.activeFileId);

  const [sidebarActivity, setSidebarActivity] =
    useState<ActivityView>("explorer");
  const [assistantOpen, setAssistantOpen] = useState(false);
  const [cirqPrefill, setCirqPrefill] = useState<{
    nonce: number;
    text: string;
  } | null>(null);

  const handleSidebarActivityChange = useCallback((v: ActivityView) => {
    if (v === "cirqAssistant") {
      setAssistantOpen(true);
      return;
    }
    setSidebarActivity(v);
  }, []);

  const handlePrefillConsumed = useCallback(() => setCirqPrefill(null), []);

  // "New file" from the menu bar / Alt+N: make sure the explorer is showing.
  useEffect(() => {
    const showExplorer = () => setSidebarActivity("explorer");
    window.addEventListener("qcanvas:new-file", showExplorer);
    return () => window.removeEventListener("qcanvas:new-file", showExplorer);
  }, []);

  const handleAskAiAboutCircuit = useCallback(() => {
    const f = useFileStore.getState().getActiveFile();
    if (!f?.content?.trim()) {
      toast.error("Open a file with code first");
      return;
    }
    const text = `I have this quantum circuit open in QCanvas:\n\n${f.content}\n\nCan you explain what it does and suggest any optimizations?`;
    setCirqPrefill({ nonce: Date.now(), text });
    setAssistantOpen(true);
  }, [handleSidebarActivityChange]);

  // Check for mobile screen size
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };

    checkMobile();
    window.addEventListener("resize", checkMobile);
    return () => window.removeEventListener("resize", checkMobile);
  }, []);

  // Auto-collapse the sidebar when the window gets narrow, and bring it back
  // when the window is wide again (previously it stayed hidden until a hard reload).
  const autoCollapsedRef = useRef(false);
  useEffect(() => {
    const { sidebarCollapsed: collapsed, toggleSidebar: toggle } =
      useFileStore.getState();
    if (isMobile && !collapsed) {
      autoCollapsedRef.current = true;
      toggle();
    } else if (!isMobile && collapsed && autoCollapsedRef.current) {
      autoCollapsedRef.current = false;
      toggle();
    }
  }, [isMobile]);

  // If the user toggles the sidebar manually, respect that choice.
  useEffect(() => {
    if (!sidebarCollapsed) autoCollapsedRef.current = false;
  }, [sidebarCollapsed]);

  // Authentication check: validate the stored session with the backend and
  // refresh the token BEFORE loading any user data. A stale/expired token used
  // to leave the IDE looking logged in but with no files or projects.
  useEffect(() => {
    let cancelled = false;
    const persistedAuth = localStorage.getItem("qcanvas-auth");

    let locallyValid = false;
    try {
      const parsed = persistedAuth ? JSON.parse(persistedAuth) : null;
      locallyValid = hasValidAuth(parsed?.state ?? parsed);
    } catch {
      locallyValid = false;
    }

    if (!locallyValid) {
      // Expired or missing token: clear leftovers and go to login with a message.
      handleSessionExpired();
      setIsAuthenticated(false);
      return;
    }

    refreshSession(true).then((status) => {
      if (cancelled) return;
      setIsAuthenticated(status !== "expired");
    });

    return () => {
      cancelled = true;
    };
  }, []);

  // Keep the session alive while the IDE is open (hourly + on tab focus).
  useSessionKeepAlive(isAuthenticated === true);

  // Redirect to login if we know the user isn't authenticated.
  useEffect(() => {
    if (isAuthenticated === false) router.replace("/login");
  }, [isAuthenticated, router]);

  // Load projects + explorer tree once the session is confirmed.
  // Reads the token from the store so a background token refresh doesn't
  // trigger a full re-fetch of the explorer.
  useEffect(() => {
    if (!isAuthenticated) return;
    const currentToken = useAuthStore.getState().token;
    if (!currentToken) return;

    const { fetchProjects, fetchExplorerTree } = useFileStore.getState();

    fetchProjects(currentToken);
    // Load the explorer FIRST, then open any example handed over from the
    // homepage/examples page. Doing both at once raced: the tree response
    // could drop the new file or list it twice.
    void fetchExplorerTree(null, currentToken).finally(() => {
      openPendingExample();
    });
  }, [isAuthenticated]);

  // In Basic mode, auto-fill framework/backend from the active code.
  useEffect(() => {
    if (executionMode !== "basic") return;
    const activeFile = useFileStore.getState().getActiveFile();
    if (!activeFile) return;

    const detected = detectFramework(activeFile.content, activeFile.name);
    if (!detected) return;

    if (inputLanguage !== detected) {
      setInputLanguage(detected);
    }

    const backendMatch: Record<string, "cirq" | "qiskit" | "pennylane"> = {
      cirq: "cirq",
      qiskit: "qiskit",
      pennylane: "pennylane",
    };

    const nextBackend = backendMatch[detected];
    if (nextBackend && simBackend !== nextBackend) {
      setSimBackend(nextBackend);
    }
  }, [activeFileId, executionMode]); // eslint-disable-line react-hooks/exhaustive-deps

  // Listen for inter-tab messages to add files from examples page
  useEffect(() => {
    if (!isAuthenticated) return;

    const channel = new BroadcastChannel("qcanvas-examples");

    channel.onmessage = async (event) => {
      if (event.data.type === "add-example-file") {
        const { filename, code } = event.data;
        // Use createFile to persist to database instead of just memory
        await useFileStore.getState().createFile(filename, code);
        toast.success(`Loaded and saved example: ${filename}`);

        // Send confirmation back to examples page
        channel.postMessage({
          type: "file-added",
          filename,
        });
      }
    };

    return () => {
      channel.close();
    };
  }, [isAuthenticated]);



  // Handle global save event. (Saving used to also force-download an SVG of the
  // circuit on every Ctrl+S; that side effect has been removed.)
  useEffect(() => {
    const handleSave = () => {
      useFileStore.getState().saveActiveFile();
    };

    window.addEventListener("save-file", handleSave);
    return () => window.removeEventListener("save-file", handleSave);
  }, []);

  // Handle drag resize for results panel
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!contentRef.current) return;

      const containerRect = contentRef.current.getBoundingClientRect();
      const newHeight = containerRect.bottom - e.clientY;
      const minHeight = 100;
      const minEditorHeight = 220;
      const maxHeight = Math.max(
        minHeight,
        containerRect.height - minEditorHeight,
      );

      const clamped = Math.max(minHeight, Math.min(maxHeight, newHeight));
      pendingResultsHeightRef.current = clamped;
      if (rafIdRef.current != null) return;
      rafIdRef.current =
        globalThis.window?.requestAnimationFrame(() => {
          rafIdRef.current = null;
          setResultsHeight(pendingResultsHeightRef.current);
        }) ?? null;
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    document.body.classList.add("select-none", "cursor-row-resize");
    document.addEventListener("mousemove", handleMouseMove, { passive: true });
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      if (rafIdRef.current != null) {
        globalThis.window?.cancelAnimationFrame(rafIdRef.current);
        rafIdRef.current = null;
      }
      document.body.classList.remove("select-none", "cursor-row-resize");
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);

  // Keep results height within bounds when viewport/layout changes.
  useEffect(() => {
    const clampResultsHeight = () => {
      if (!contentRef.current) return;
      const containerRect = contentRef.current.getBoundingClientRect();
      const minHeight = 100;
      const minEditorHeight = 220;
      const maxHeight = Math.max(
        minHeight,
        containerRect.height - minEditorHeight,
      );
      setResultsHeight((prev) =>
        Math.max(minHeight, Math.min(maxHeight, prev)),
      );
    };

    clampResultsHeight();
    window.addEventListener("resize", clampResultsHeight);
    return () => window.removeEventListener("resize", clampResultsHeight);
  }, [resultsCollapsed]);

  // Handle drag resize for sidebar (desktop only)
  useEffect(() => {
    if (!isSidebarResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      const minWidth = 220;
      const maxWidth = Math.max(minWidth, Math.floor(window.innerWidth * 0.6));
      const next = Math.max(minWidth, Math.min(maxWidth, e.clientX - 48));
      pendingSidebarWidthRef.current = next;
      if (rafSidebarIdRef.current != null) return;
      rafSidebarIdRef.current =
        globalThis.window?.requestAnimationFrame(() => {
          rafSidebarIdRef.current = null;
          setSidebarWidth(pendingSidebarWidthRef.current);
        }) ?? null;
    };

    const handleMouseUp = () => {
      setIsSidebarResizing(false);
    };

    document.body.classList.add("select-none", "cursor-col-resize");
    document.addEventListener("mousemove", handleMouseMove, { passive: true });
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      if (rafSidebarIdRef.current != null) {
        globalThis.window?.cancelAnimationFrame(rafSidebarIdRef.current);
        rafSidebarIdRef.current = null;
      }
      document.body.classList.remove("select-none", "cursor-col-resize");
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isSidebarResizing]);

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleSidebarResizeStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsSidebarResizing(true);
  };

  // Loading state
  if (isAuthenticated === null) {
    return (
      <div className="flex items-center justify-center h-screen bg-editor-bg">
        <div className="flex flex-col items-center space-y-4">
          <div className="w-8 h-8 border-4 border-quantum-blue-light border-t-transparent rounded-full spinner"></div>
          <p className="text-editor-text">Loading QCanvas...</p>
        </div>
      </div>
    );
  }

  // Not authenticated - redirect happens in the effect above
  if (!isAuthenticated) {
    return (
      <div className="flex items-center justify-center h-screen bg-editor-bg px-4">
        <div className="max-w-md mx-auto p-8 quantum-glass-dark rounded-lg text-center">
          <h2 className="text-2xl font-bold text-white mb-4">
            Redirecting to Login...
          </h2>
          <p className="text-editor-text mb-6">
            Please wait while we redirect you to the login page.
          </p>
        </div>
      </div>
    );
  }

  // Authenticated - show main app
  return (
    <>
      {/* SEO: screen-reader-only h1 and descriptive content.
          The IDE renders almost no readable text, so we add a hidden
          content block so search engines understand this page's purpose.
          word-count: ~220+ words */}
      <div className="sr-only" aria-hidden="false">
        <h1>QCanvas Quantum Circuit IDE — Write, Convert &amp; Simulate</h1>
        <p>
          Welcome to the QCanvas Quantum Circuit Integrated Development
          Environment. This browser-based IDE lets you write quantum programs
          in Cirq, Qiskit, or PennyLane, compile them to OpenQASM 3.0, and
          simulate the results in real time using the QSim backend engine.
        </p>
        <p>
          Use the Monaco-powered code editor to author quantum algorithms
          including Bell state preparation, quantum teleportation, Grover&apos;s
          search, the Deutsch-Jozsa algorithm, and quantum machine learning
          classifiers. The built-in AI assistant, powered by a Retrieval
          Augmented Generation architecture, can explain your circuit, suggest
          optimizations, and generate new circuit code on request.
        </p>
        <p>
          Simulation results are displayed as measurement histograms, state
          vector probabilities, and execution timing metrics. Supports
          multi-qubit entanglement, conditional gates, for-loop constructs, and
          if-else classical control flow in OpenQASM 3.0. Export circuits as
          SVG diagrams or share them via the project file system.
        </p>
        <p>
          QCanvas is a FAST University initiative supporting quantum computing
          education. The editor works with all major frameworks: Google Cirq,
          IBM Qiskit, and Xanadu PennyLane. Authentication is secured with JWT
          tokens and all projects are persisted server-side.
        </p>
      </div>
      <IDELayout
      sidebarActivity={sidebarActivity}
      onSidebarActivityChange={handleSidebarActivityChange}
      onAskAiAboutCircuit={handleAskAiAboutCircuit}
      rightPanelOpen={assistantOpen}
      onRightPanelClose={() => setAssistantOpen(false)}
      cirqAssistantView={
        <CirqAssistantSidebar
          prefillPayload={cirqPrefill}
          onPrefillConsumed={handlePrefillConsumed}
          onSetInputLanguage={setInputLanguage}
        />
      }
      sidebarContainerClassName={`${sidebarCollapsed ? "w-0" : "w-full md:shrink-0"} ${isSidebarResizing ? "" : "transition-all duration-200"} ${
        isMobile && !sidebarCollapsed
          ? "absolute inset-y-0 left-12 z-50 shadow-xl"
          : ""
      } overflow-hidden`}
      sidebarContainerStyle={
        !isMobile && !sidebarCollapsed
          ? { width: `${sidebarWidth}px` }
          : undefined
      }
      sidebarResizeHandle={
        !isMobile && !sidebarCollapsed ? (
          <div
            className={`w-1 ${isSidebarResizing ? "w-1.5" : "hover:w-1.5"} ${isSidebarResizing ? "" : "transition-all"} bg-editor-border hover:bg-quantum-blue-light cursor-col-resize ${
              isSidebarResizing ? "bg-quantum-blue-light" : ""
            }`}
            onMouseDown={handleSidebarResizeStart}
            title="Drag to resize explorer"
          />
        ) : null
      }
      sidebarOverlay={
        isMobile && !sidebarCollapsed ? (
          <div
            className="absolute inset-0 bg-black bg-opacity-50 z-40"
            onClick={toggleSidebar}
          />
        ) : undefined
      }
      editor={
        <div ref={containerRef} className="flex-1 overflow-hidden">
          <EditorPane
            onRun={run}
            isRunning={isRunning}
            inputLanguage={inputLanguage}
            setInputLanguage={setInputLanguage}
            simBackend={simBackend}
            setSimBackend={setSimBackend}
            shots={shots}
            setShots={setShots}
          />
        </div>
      }
      runView={
        <RunView
          inputLanguage={inputLanguage}
          setInputLanguage={setInputLanguage}
          simBackend={simBackend}
          setSimBackend={setSimBackend}
          shots={shots}
          setShots={setShots}
          onRun={run}
          isRunning={isRunning}
        />
      }
      bottomDragHandle={
        resultsCollapsed ? (
          <></>
        ) : (
          <div
            className={`h-1 bg-editor-border hover:bg-quantum-blue-light cursor-row-resize transition-colors ${
              isDragging ? "bg-quantum-blue-light" : ""
            }`}
            onMouseDown={handleDragStart}
            title="Drag to resize"
          />
        )
      }
      bottom={
        <div
          className="overflow-hidden border-t border-editor-border"
          style={{ height: resultsCollapsed ? "32px" : `${resultsHeight}px` }}
        >
          <ResultsPane />
        </div>
      }
      onRun={run}
      contentRef={contentRef}
    />
    </>
  );
}
