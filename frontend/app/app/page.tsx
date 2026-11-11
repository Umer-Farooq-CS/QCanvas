"use client";

import { useCallback, useEffect, useState, useRef } from "react";
import { useFileStore } from "@/lib/store";
import { InputLanguage } from "@/types";
import { detectFramework } from "@/lib/utils";

import EditorPane from "@/components/EditorPane";
import ResultsPane from "@/components/ResultsPane";
import IDELayout from "@/components/ide/IDELayout";
import RunView from "@/components/ide/RunView";
import CirqAssistantSidebar from "@/components/ide/CirqAssistantSidebar";
import type { ActivityView } from "@/components/ide/ActivityBar";
import { useRouter } from "next/navigation";
import toast from "react-hot-toast";
import { hasValidAuth, useAuthStore } from "@/lib/authStore";
import { useExecutionActions } from "@/components/ide/useExecutionActions";

export default function AppPage() {
  const router = useRouter();
  const token = useAuthStore((s) => s.token);
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

  const { sidebarCollapsed, toggleSidebar, resultsCollapsed, executionMode } =
    useFileStore();
  const activeFile = useFileStore((s) => s.getActiveFile());

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

  // Auto-collapse sidebar on mobile
  useEffect(() => {
    if (isMobile && !sidebarCollapsed) {
      toggleSidebar();
    }
  }, [isMobile]); // eslint-disable-line react-hooks/exhaustive-deps

  // Authentication check
  useEffect(() => {
    const persistedAuth = localStorage.getItem("qcanvas-auth");

    if (!persistedAuth) {
      setIsAuthenticated(false);
      return;
    }

    try {
      const parsed = JSON.parse(persistedAuth);
      const persistedState = parsed?.state ?? parsed;
      setIsAuthenticated(hasValidAuth(persistedState));
    } catch {
      setIsAuthenticated(false);
    }
  }, []);

  // Load projects + explorer tree on component mount
  useEffect(() => {
    if (!isAuthenticated) return;

    if (!token) return;

    const { fetchProjects, fetchExplorerTree } = useFileStore.getState();

    fetchProjects(token);
    fetchExplorerTree(null, token);
  }, [isAuthenticated, token]);

  // In Basic mode, auto-fill framework/backend from the active code.
  useEffect(() => {
    if (executionMode !== "basic") return;
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
  }, [activeFile?.id, executionMode]);

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

  // Handle examples passed via sessionStorage (from Examples page or Homepage)
  useEffect(() => {
    if (!isAuthenticated || !token) return;

    const loadExample =
      new URLSearchParams(window.location.search).get("loadExample") === "1";
    if (!loadExample) {
      sessionStorage.removeItem("pending-example");
      return;
    }

    const pendingJson = sessionStorage.getItem("pending-example");
    if (pendingJson) {
      try {
        const example = JSON.parse(pendingJson);
        if (example && example.name && example.content) {
          // Use createFile to persist the example
          useFileStore.getState().createFile(example.name, example.content);
          toast.success(`Example loaded: ${example.name}`);
        }
      } catch (e) {
        console.error("Failed to parse pending example", e);
      } finally {
        // Clear immediately to prevent re-creation on refresh
        sessionStorage.removeItem("pending-example");
      }
    }

    window.history.replaceState(null, "", "/app");
  }, [isAuthenticated, token]);

  // Handle global save event
  useEffect(() => {
    const handleSave = () => {
      const store = useFileStore.getState();
      store.saveActiveFile();

      // Also download SVG to computer if available
      const activeFile = store.files.find(
        (f: any) => f.id === store.activeFileId,
      );
      if (activeFile) {
        // Try to capture and save the circuit visualization if it exists in the DOM
        const svgElement = document.querySelector(
          "svg.min-w-full",
        ) as SVGSVGElement | null;
        if (svgElement) {
          try {
            const serializer = new XMLSerializer();
            let source = serializer.serializeToString(svgElement);
            if (
              !source.match(
                /^<svg[^>]+xmlns="http\:\/\/www\.w3\.org\/2000\/svg"/,
              )
            ) {
              source = source.replace(
                /^<svg/,
                '<svg xmlns="http://www.w3.org/2000/svg"',
              );
            }
            source = '<?xml version="1.0" standalone="no"?>\r\n' + source;
            const svgUrl =
              "data:image/svg+xml;charset=utf-8," + encodeURIComponent(source);
            const svgLink = document.createElement("a");
            svgLink.href = svgUrl;
            svgLink.download =
              activeFile.name.replace(/\.[^/.]+$/, "") + "_circuit.svg";
            document.body.appendChild(svgLink);
            svgLink.click();
            document.body.removeChild(svgLink);
          } catch (e) {
            console.error("Failed to save SVG", e);
          }
        }
      }
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

  // Not authenticated - redirect to login
  if (!isAuthenticated) {
    router.replace("/login");
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
          onPrefillConsumed={() => setCirqPrefill(null)}
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
