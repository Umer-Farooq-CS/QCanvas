"use client";

import { memo, useState, useEffect } from "react";
import dynamic from "next/dynamic";
import {
  Terminal,
  BarChart3,
  Copy,
  Download,
  AlertCircle,
  AlertTriangle,
  Activity,
  Cpu,
  Zap,
  TrendingUp,
  ResultIcon,
  OutputIcon,
} from "@/components/Icons";
import {
  Minimize2,
  Maximize2,
  XCircle,
  CheckCircle,
  Trash2,
  FileCode2,
  FileDown,
  Copy as CopyIcon,
  Cloud,
  DollarSign,
} from "lucide-react";
import toast from "react-hot-toast";
import { useFileStore } from "@/lib/store";

// chart.js is only needed once there are results to plot, so load it lazily
// instead of shipping it in the /app first-load bundle.
const Bar = dynamic(() => import("./charts/BarChart"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full">
      <span className="text-sm text-editor-text/70">Loading chart…</span>
    </div>
  ),
});

// Dynamically import Monaco Editor (SSR-safe) for syntax highlighting in Results.
const MonacoEditor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.Editor),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-48 bg-editor-panelLowest border border-editor-border rounded">
        <span className="text-sm text-editor-text/70">Loading viewer…</span>
      </div>
    ),
  },
);

interface LogEntry {
  id: string;
  timestamp: string;
  type: "info" | "success" | "error" | "warning";
  message: string;
}

interface ErrorEntry {
  id: string;
  severity: "error" | "warning" | "info";
  message: string;
  line: number;
  column: number;
  file: string;
  code: string;
  suggestion?: string;
}

function ResultsPane() {
  // Narrow subscriptions: this used to subscribe to the whole store (including
  // `files`), so the results pane re-rendered on every editor update.
  const resultsCollapsed = useFileStore((s) => s.resultsCollapsed);
  const toggleResults = useFileStore((s) => s.toggleResults);
  const compiledQasm = useFileStore((s) => s.compiledQasm);
  const conversionStats = useFileStore((s) => s.conversionStats);
  const simulationResults = useFileStore((s) => s.simulationResults);
  const hybridResult = useFileStore((s) => s.hybridResult);
  const executionMode = useFileStore((s) => s.executionMode);
  const theme = useFileStore((s) => s.theme);

  // Use simulation results from store if available, otherwise check hybrid results
  const quantumResults = simulationResults
    ? {
        counts: simulationResults.counts,
        shots: simulationResults.metadata.shots || 1024,
        backend: simulationResults.metadata.backend || "N/A",
        execution_time: "N/A",
        circuit_info: {
          depth: conversionStats?.depth || 0,
          qubits: simulationResults.metadata.n_qubits || 0,
          gates: conversionStats?.gates
            ? Object.values(conversionStats.gates).reduce(
                (a: number, b: number) => a + b,
                0,
              )
            : 0,
        },
        metadata: simulationResults.metadata,
        probs: simulationResults.probs,
      }
    : hybridResult &&
        hybridResult.simulation_results &&
        hybridResult.simulation_results.length > 0
      ? {
          // Use the first simulation result from hybrid execution
          counts: hybridResult.simulation_results[0].counts,
          shots: hybridResult.simulation_results[0].shots,
          backend: hybridResult.simulation_results[0].backend,
          execution_time: hybridResult.simulation_results[0].execution_time || hybridResult.execution_time || "N/A",
          circuit_info: {
            depth: 0,
            qubits: hybridResult.simulation_results[0].n_qubits || 0,
            gates: 0,
          },
          metadata: {
            ...(hybridResult.simulation_results[0].metadata || {}),
            backend: hybridResult.simulation_results[0].backend,
            shots: hybridResult.simulation_results[0].shots,
            n_qubits: hybridResult.simulation_results[0].n_qubits || hybridResult.simulation_results[0].metadata?.n_qubits || 0,
            execution_time: hybridResult.simulation_results[0].execution_time || hybridResult.simulation_results[0].metadata?.execution_time || "N/A",
            simulation_time: (hybridResult.simulation_results[0] as any).simulation_time || hybridResult.simulation_results[0].metadata?.simulation_time || "N/A",
            memory_usage: (hybridResult.simulation_results[0] as any).memory_usage || hybridResult.simulation_results[0].metadata?.memory_usage || "N/A",
            cpu_usage: (hybridResult.simulation_results[0] as any).cpu_usage || hybridResult.simulation_results[0].metadata?.cpu_usage || "N/A",
          },
          probs: hybridResult.simulation_results[0].probabilities || null,
        }
      : null;

  // Helper function to get display stats from backend conversion stats
  const getDisplayStats = () => {
    // Convert backend stats to display format (handle null conversionStats)
    const gates = conversionStats?.gates || {};
    const totalGates = Object.values(gates).reduce(
      (sum: number, count) => sum + (count || 0),
      0,
    );
    const entanglingGates = ["cx", "cnot", "cz", "swap", "ccx"].reduce(
      (sum, gate) => sum + (gates[gate] || 0),
      0,
    );
    const singleQubitGates = totalGates - entanglingGates;

    // Use simulation results if available (even when conversionStats is null)
    const executionData = quantumResults
      ? {
          status: "completed",
          totalTime:
            (quantumResults.metadata as any).execution_time ||
            quantumResults.execution_time ||
            "N/A",
          simulationTime: (quantumResults.metadata as any).simulation_time || "N/A",
          postProcessingTime:
            (quantumResults.metadata as any).postprocessing_time || "<1ms",
          shots: quantumResults.shots || 0,
          successfulShots:
            (quantumResults.metadata as any).successful_shots ||
            Object.values(quantumResults.counts || {}).reduce(
              (a, b) => a + b,
              0,
            ),
          backend: quantumResults.backend || "N/A",
          visitor:
            (quantumResults.metadata as any).visitor ||
            quantumResults.backend ||
            "N/A",
          memoryUsage: (quantumResults.metadata as any).memory_usage || "N/A",
          cpuUsage: (quantumResults.metadata as any).cpu_usage || "N/A",
          fidelity:
            typeof (quantumResults.metadata as any).fidelity === "number"
              ? (quantumResults.metadata as any).fidelity
              : 0, // not measured by the simulator: don't invent a number
        }
      : {
          status: "pending",
          totalTime: "-",
          simulationTime: "-",
          postProcessingTime: "-",
          shots: 0,
          successfulShots: 0,
          backend: "N/A",
          visitor: "N/A",
          memoryUsage: "-",
          cpuUsage: "-",
          fidelity: 0,
        };

    // Use qubits from simulation results if available, otherwise from conversion stats
    const numQubits =
      (quantumResults?.metadata as any)?.n_qubits || conversionStats?.qubits || 0;

    // Determine compilation status
    const compilationStatus = conversionStats
      ? conversionStats.success
        ? "success"
        : "failed"
      : quantumResults
        ? "success"
        : "pending";

    return {
      compilation: {
        status: compilationStatus,
        time: conversionStats?.conversion_time || (quantumResults ? "<2ms" : "N/A"),
        originalGates: totalGates,
        optimizedGates: totalGates, // Same for now
        reductionPercentage: 0,
        circuitDepth: conversionStats?.depth || 0,
        qubits: numQubits,
        classicalBits: 0, // Not tracked yet
        warnings: 0,
        errors: conversionStats?.error ? 1 : 0,
      },
      circuit: {
        gates: gates,
        depth: conversionStats?.depth || 0,
        width: numQubits,
        complexity:
          totalGates > 10 ? "High" : totalGates > 5 ? "Medium" : "Low",
        entanglingGates: entanglingGates,
        singleQubitGates: singleQubitGates,
      },
      execution: executionData,
      optimization: {
        level: quantumResults ? 1 : 0,
        timeSpent: quantumResults ? "<1ms" : "-",
        gatesReduced: 0,
        depthReduced: 0,
        techniques: quantumResults ? ["AST Pass", "Gate Normalization"] : [],
      },
    };
  };
  const [activeTab, setActiveTab] = useState<
    "console" | "output" | "histogram" | "qasm" | "errors" | "stats"
  >("console");
  const [logs, setLogs] = useState<LogEntry[]>([
    {
      id: "1",
      timestamp: new Date().toISOString(),
      type: "info",
      message: "QCanvas Quantum Editor initialized",
    },
  ]);

  // Mock errors data - in real app, this would come from actual code analysis
  // Errors disabled for now; will be implemented later
  const [errors, setErrors] = useState<ErrorEntry[]>([]);

  // Get dynamic stats from backend conversion or use defaults
  const executionStats = getDisplayStats();
  const [legacyExecutionStats, setLegacyExecutionStats] = useState({
    compilation: {
      status: "success",
      time: "142ms",
      originalGates: 15,
      optimizedGates: 12,
      reductionPercentage: 20,
      circuitDepth: 8,
      qubits: 3,
      classicalBits: 3,
      warnings: 1,
      errors: 0,
    },
    execution: {
      status: "completed",
      totalTime: "2.1s",
      simulationTime: "1.8s",
      postProcessingTime: "0.3s",
      shots: 1024,
      successfulShots: 1024,
      backend: "qasm_simulator",
      memoryUsage: "45.2MB",
      cpuUsage: "23%",
      fidelity: 99.2,
    },
    circuit: {
      gates: {
        h: 3,
        cx: 4,
        measure: 3,
        rz: 2,
        ry: 1,
      },
      depth: 8,
      width: 3,
      complexity: "Medium",
      entanglingGates: 4,
      singleQubitGates: 6,
    },
    optimization: {
      level: 2,
      timeSpent: "38ms",
      gatesReduced: 3,
      depthReduced: 2,
      techniques: [
        "Gate cancellation",
        "Commutation analysis",
        "Single-qubit optimization",
      ],
    },
  });

  // quantumResults has been relocated to the top of the component above getDisplayStats

  // Helper function to generate all possible states for n qubits and merge with actual counts
  const getAllStatesWithCounts = (
    counts: { [state: string]: number },
    nQubits: number,
    shots: number,
  ) => {
    // Always infer n_qubits from actual state strings in counts (this handles cases where
    // circuit has more qubits than measured qubits, e.g., 3 qubits but only 2 measured)
    let inferredQubits = 0;
    if (Object.keys(counts).length > 0) {
      // Get the length of the first state string (all should be the same length)
      const firstState = Object.keys(counts)[0];
      inferredQubits = firstState.length;
    } else if (nQubits > 0) {
      // If no counts yet, use provided nQubits
      inferredQubits = nQubits;
    }

    // If still 0, default to 1 qubit
    if (inferredQubits === 0) {
      inferredQubits = 1;
    }

    // Generate all possible states (binary strings)
    const allStates: string[] = [];
    const maxState = Math.pow(2, inferredQubits);
    for (let i = 0; i < maxState; i++) {
      allStates.push(i.toString(2).padStart(inferredQubits, "0"));
    }

    // Merge actual counts with all possible states (fill 0 for missing states)
    const mergedCounts: { [state: string]: number } = {};
    allStates.forEach((state) => {
      mergedCounts[state] = counts[state] || 0;
    });

    // Sort by count in descending order
    const sortedEntries = Object.entries(mergedCounts).sort(
      (a, b) => b[1] - a[1],
    );

    return sortedEntries;
  };

  // Histogram should follow typical simulator-style display:
  // - show only states that actually occurred (non-zero)
  // - keep a simple "natural" ordering by bitstring (not count-sorted)
  const getHistogramStates = (counts: { [state: string]: number }) => {
    const entries = Object.entries(counts || {}).filter(
      ([, count]) => count > 0,
    );
    // Bitstrings are same length; lexicographic == numeric ascending for equal-length binary strings.
    entries.sort(([a], [b]) => a.localeCompare(b));
    return entries;
  };

  // Helper function to add an error entry
  const addError = (
    message: string,
    severity: "error" | "warning" | "info" = "error",
    details?: string,
  ) => {
    const newError: ErrorEntry = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      severity,
      message,
      // Pull the line number out of messages like "... (line 6)".
      line: Number((details || message).match(/\bline (\d+)\b/i)?.[1] ?? 0),
      column: 0,
      file: useFileStore.getState().getActiveFile()?.name ?? "current file",
      code: details || message,
      suggestion:
        severity === "error"
          ? "Check your code syntax and ensure all gates are supported."
          : undefined,
    };
    setErrors((prev) => [...prev, newError]);
  };

  // Listen for compilation events
  useEffect(() => {
    const handleCompile = (event: any) => {
      const { success, error } = event.detail || {};

      if (success) {
        // Clear previous errors on successful compilation
        setErrors([]);
        addLog("success", "Code compiled to OpenQASM 3.0");
        addLog("info", "Starting quantum simulation...");
      } else if (error) {
        addLog("error", `Compilation failed: ${error}`);
        // Add to errors tab
        addError("Compilation Failed", "error", error);
        setActiveTab("errors");
      }
    };

    window.addEventListener("circuit-compile", handleCompile);
    return () => window.removeEventListener("circuit-compile", handleCompile);
  }, []);

  // Listen for execution events
  useEffect(() => {
    const handleExecution = (event: any) => {
      const { success, error } = event.detail || {};

      addLog("info", "Starting quantum circuit execution...");

      if (!success && error) {
        addLog("error", `Execution failed: ${error}`);
        // Add to errors tab
        addError("Simulation Failed", "error", error);
        setActiveTab("errors");
      }
    };

    // Listen for custom events from TopBar
    window.addEventListener("circuit-execute", handleExecution);
    return () => window.removeEventListener("circuit-execute", handleExecution);
  }, []);

  // Log when simulation completes
  useEffect(() => {
    if (simulationResults) {
      addLog("success", "Simulation completed successfully");
      addLog("success", "Results displayed in Output and Histogram tabs");
      // Switch to output tab to show the summary
      setActiveTab("output");
    }
  }, [simulationResults]);

  // Listen for hybrid execution events
  useEffect(() => {
    const handleHybridExecution = (event: any) => {
      const { success, error, result } = event.detail || {};

      if (success) {
        addLog("success", "Hybrid execution completed");
        if (result?.simulation_results?.length > 0) {
          addLog(
            "info",
            `${result.simulation_results.length} simulation(s) executed`,
          );
        }
        if (result?.stdout) {
          addLog(
            "info",
            `Output captured: ${result.stdout.split("\n").length} lines`,
          );
        }
        setActiveTab("output");
      } else {
        addLog("error", `Hybrid execution failed: ${error || "Unknown error"}`);
        setActiveTab("output");
      }
    };

    window.addEventListener("hybrid-execute", handleHybridExecution);
    return () =>
      window.removeEventListener("hybrid-execute", handleHybridExecution);
  }, []);

  useEffect(() => {
    const showQasm = () => setActiveTab("qasm");
    window.addEventListener("show-qasm", showQasm);
    return () => window.removeEventListener("show-qasm", showQasm);
  }, []);

  const addLog = (type: LogEntry["type"], message: string) => {
    // Use timestamp + random number to ensure unique IDs even for simultaneous logs
    const newLog: LogEntry = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      timestamp: new Date().toISOString(),
      type,
      message,
    };
    setLogs((prev) => [...prev, newLog]);
  };

  const clearLogs = () => {
    setLogs([]);
    // Also clear all results from store
    useFileStore.getState().setSimulationResults(null);
    useFileStore.getState().setHybridResult(null);
    useFileStore.getState().setCompiledQasm(null);
    toast.success("Results and console cleared");
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success("Copied to clipboard");
  };

  const saveQasmNextToActiveFile = async () => {
    const { getActiveFile, files, createFile, activeProjectId } =
      useFileStore.getState();
    const activeFile = getActiveFile();
    if (!compiledQasm) {
      toast.error("No OpenQASM to save");
      return;
    }
    if (!activeFile) {
      toast.error("No active file");
      return;
    }

    const base = activeFile.name.replace(/\.[^/.]+$/, "");
    const desired = `${base}.qasm`;

    // Ensure uniqueness inside the current file scope list.
    const existing = new Set(
      (files || []).map((f) => f.name.trim().toLowerCase()),
    );
    let candidate = desired;
    if (existing.has(candidate.toLowerCase())) {
      let i = 1;
      // eslint-disable-next-line no-constant-condition
      while (true) {
        candidate = `${base} (${i}).qasm`;
        if (!existing.has(candidate.toLowerCase())) break;
        i += 1;
      }
    }

    try {
      await createFile(
        candidate,
        compiledQasm,
        activeProjectId ?? undefined,
        false,
        activeFile.folderId,
      );
      toast.success(`Saved ${candidate}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to save .qasm");
    }
  };

  const downloadResults = () => {
    if (!quantumResults || !simulationResults) {
      toast.error("No results to download");
      return;
    }

    const results = {
      timestamp: new Date().toISOString(),
      quantum_results: quantumResults,
      logs: logs,
    };

    const dataStr = JSON.stringify(results, null, 2);
    const dataUri =
      "data:application/json;charset=utf-8," + encodeURIComponent(dataStr);

    const exportFileDefaultName = `qcanvas-results-${Date.now()}.json`;

    const linkElement = document.createElement("a");
    linkElement.setAttribute("href", dataUri);
    linkElement.setAttribute("download", exportFileDefaultName);
    linkElement.click();

    toast.success("Results downloaded");
  };

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString();
  };

  const getLogIcon = (type: LogEntry["type"]) => {
    switch (type) {
      case "success":
        return "✓";
      case "error":
        return "✗";
      case "warning":
        return "⚠";
      default:
        return "ℹ";
    }
  };

  const getLogColor = (type: LogEntry["type"]) => {
    switch (type) {
      case "success":
        return "text-green-400";
      case "error":
        return "text-red-400";
      case "warning":
        return "text-yellow-400";
      default:
        return "text-blue-400";
    }
  };

  const getErrorIcon = (severity: ErrorEntry["severity"]) => {
    switch (severity) {
      case "error":
        return <XCircle className="w-4 h-4 text-red-400" />;
      case "warning":
        return <AlertTriangle className="w-4 h-4 text-yellow-400" />;
      case "info":
        return <AlertCircle className="w-4 h-4 text-blue-400" />;
      default:
        return (
          <AlertCircle className="w-4 h-4 text-black dark:text-gray-400" />
        );
    }
  };

  const getErrorColor = (severity: ErrorEntry["severity"]) => {
    switch (severity) {
      case "error":
        return "text-red-400";
      case "warning":
        return "text-yellow-400";
      case "info":
        return "text-blue-400";
      default:
        return "text-black dark:text-gray-400";
    }
  };

  const clearErrors = () => {
    setErrors([]);
    toast.success("Errors cleared");
  };

  if (resultsCollapsed) {
    return (
      <div className="h-8 bg-editor-panelLowest flex items-center justify-between px-4">
        <div className="flex items-center space-x-2">
          <ResultIcon className="w-4 h-4 text-editor-text" />
          <span className="text-sm text-editor-text">Results</span>
        </div>
        <button
          onClick={toggleResults}
          className="btn-ghost p-1"
          title="Expand Results"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="h-full results-panel flex flex-col bg-editor-panelLowest">
      {/* Results Header */}
      <div className="h-12 bg-editor-sidebar/10 flex items-center justify-between px-4 flex-shrink-0">
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2">
            <ResultIcon className="w-4 h-4 text-editor-text" />
            <span className="text-sm font-medium text-white">Results</span>
          </div>

          {/* Tabs */}
          <div className="flex items-center space-x-1">
            {[
              { id: "console", label: "Console", icon: Terminal },
              { id: "output", label: "Output", icon: OutputIcon },
              { id: "histogram", label: "Histogram", icon: BarChart3 },
              { id: "qasm", label: "OpenQASM", icon: FileCode2 },
              {
                id: "errors",
                label: "Errors",
                icon: AlertCircle,
                count: errors.filter((e) => e.severity === "error").length,
              },
              { id: "stats", label: "Stats", icon: Activity },
            ].map(({ id, label, icon: Icon, count }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id as any)}
                className={`px-3 py-1 text-xs rounded-md transition-colors flex items-center ${
                  activeTab === id
                    ? "bg-editor-accent text-gray-100"
                    : "text-editor-text hover:bg-editor-panelHigh/5"
                }`}
              >
                <Icon className="w-3 h-3 mr-1" />
                {label}
                {count !== undefined && count > 0 && (
                  <span className="ml-1 px-1.5 py-0.5 text-xs bg-red-500 text-white rounded-full">
                    {count}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center space-x-2">
          {activeTab === "qasm" && compiledQasm && (
            <>
              <button
                onClick={() => copyToClipboard(compiledQasm)}
                className="btn-ghost p-1"
                title="Copy OpenQASM"
              >
                <CopyIcon className="w-4 h-4" />
              </button>
              <button
                onClick={() => void saveQasmNextToActiveFile()}
                className="btn-ghost p-1"
                title="Save as .qasm (next to current file)"
              >
                <FileDown className="w-4 h-4" />
              </button>
            </>
          )}
          <button
            onClick={downloadResults}
            className="btn-ghost p-1"
            title="Download Results"
          >
            <Download className="w-4 h-4" />
          </button>

          {activeTab === "errors" ? (
            <button
              onClick={clearErrors}
              className="btn-ghost p-1"
              title="Clear Errors"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={clearLogs}
              className="btn-ghost p-1"
              title="Clear Console"
            >
              <Trash2 className="w-4 h-4" />
            </button>
          )}

          <button
            onClick={toggleResults}
            className="btn-ghost p-1"
            title="Minimize Results"
          >
            <Minimize2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Results Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "console" && (
          <div className="h-full overflow-y-auto results-content">
            {logs.length === 0 ? (
              <div className="text-center py-8 text-black dark:text-gray-500">
                <Terminal className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">No console output yet</p>
              </div>
            ) : (
              <div className="space-y-1">
                {logs.map((log) => (
                  <div
                    key={log.id}
                    className="flex items-start space-x-3 py-1 hover:bg-editor-panelHigh/10 rounded px-2"
                  >
                    <span className="text-xs text-black dark:text-gray-500 mt-0.5 min-w-[60px]">
                      {formatTimestamp(log.timestamp)}
                    </span>
                    <span className={`${getLogColor(log.type)} mt-0.5`}>
                      {getLogIcon(log.type)}
                    </span>
                    <span className="flex-1 text-sm text-editor-text">
                      {log.message}
                    </span>
                    <button
                      onClick={() => copyToClipboard(log.message)}
                      className="opacity-0 group-hover:opacity-100 p-1 hover:bg-editor-panelHigh rounded"
                      title="Copy"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {activeTab === "output" && (
          <div className="h-full overflow-y-auto results-content">
            <div className="space-y-4">
              {/* Hybrid Execution Output */}
              {hybridResult ? (
                <>
                  {/* Execution Status */}
                  <div
                    className={`p-3 rounded-lg border ${
                      hybridResult.success
                        ? "bg-green-500/10 border-green-500/30"
                        : "bg-red-500/10 border-red-500/30"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-2">
                        {hybridResult.success ? (
                          <CheckCircle className="w-4 h-4 text-green-400" />
                        ) : (
                          <XCircle className="w-4 h-4 text-red-400" />
                        )}
                        <span
                          className={`text-sm font-medium ${
                            hybridResult.success
                              ? "text-green-400"
                              : "text-red-400"
                          }`}
                        >
                          {hybridResult.success
                            ? "Execution Successful"
                            : "Execution Failed"}
                        </span>
                      </div>
                      {hybridResult.execution_time && (
                        <span className="text-xs text-black dark:text-gray-400">
                          {hybridResult.execution_time}
                        </span>
                      )}
                    </div>
                    {hybridResult.error && (
                      <div className="mt-2">
                        <div className="text-sm text-red-300">
                          <span className="font-medium">
                            {hybridResult.error_type || "Error"}
                          </span>
                          {hybridResult.error_line && (
                            <span className="text-red-400">
                              {" "}
                              (line {hybridResult.error_line})
                            </span>
                          )}
                          : {hybridResult.error}
                        </div>
                        {/* Show helpful hints based on error type */}
                        {hybridResult.error_type ===
                          "SecurityViolationError" && (
                          <div className="mt-2 text-xs text-yellow-400 bg-yellow-900/20 p-2 rounded">
                            <strong>Security Note:</strong> Certain imports and
                            operations are blocked in expert mode for safety.
                            Blocked: os, sys, subprocess, socket, file
                            operations, network access.
                          </div>
                        )}
                        {hybridResult.error_type === "TimeoutError" && (
                          <div className="mt-2 text-xs text-yellow-400 bg-yellow-900/20 p-2 rounded">
                            <strong>Tip:</strong> Code execution is limited to
                            180 seconds. Try reducing the number of simulations
                            or iterations.
                          </div>
                        )}
                        {hybridResult.error_type === "ImportError" && (
                          <div className="mt-2 text-xs text-blue-400 bg-blue-900/20 p-2 rounded">
                            <strong>Allowed imports:</strong> cirq, qiskit,
                            pennylane, fastqsim, numpy, math, qcanvas, qsim, typing,
                            dataclasses
                          </div>
                        )}
                        {hybridResult.error_type === "ConnectionError" && (
                          <div className="mt-2 text-xs text-orange-400 bg-orange-900/20 p-2 rounded">
                            <strong>Note:</strong> Make sure the backend server
                            is running with hybrid execution support enabled.
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Print Output */}
                  {hybridResult.stdout && (
                    <div>
                      <h4 className="text-sm font-medium text-white mb-2 flex items-center">
                        <Terminal className="w-4 h-4 mr-2 text-green-400" />
                        Print Output
                      </h4>
                      <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 font-mono text-sm">
                        <pre className="text-green-400 whitespace-pre-wrap break-words">
                          {hybridResult.stdout}
                        </pre>
                      </div>
                    </div>
                  )}

                  {/* Error Output (stderr) */}
                  {hybridResult.stderr && !hybridResult.success && (
                    <div>
                      <h4 className="text-sm font-medium text-white mb-2 flex items-center">
                        <AlertCircle className="w-4 h-4 mr-2 text-red-400" />
                        Error Details
                      </h4>
                      <div className="bg-red-900/20 border border-red-700/30 rounded-lg p-3 font-mono text-sm">
                        <pre className="text-red-300 whitespace-pre-wrap break-words">
                          {hybridResult.stderr}
                        </pre>
                      </div>
                    </div>
                  )}

                  {/* Simulation Results */}
                  {hybridResult.simulation_results &&
                    hybridResult.simulation_results.length > 0 && (
                      <div>
                        <h4 className="text-sm font-medium text-white mb-2 flex items-center">
                          <BarChart3 className="w-4 h-4 mr-2 text-blue-400" />
                          Simulation Results (
                          {hybridResult.simulation_results.length})
                        </h4>
                        <div className="space-y-3">
                          {hybridResult.simulation_results.map(
                            (result, idx) => (
                              <div
                                key={idx}
                                className="bg-editor-panelLowest border border-editor-border rounded-lg p-3"
                              >
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-xs font-medium text-black dark:text-gray-400">
                                    Simulation #{idx + 1}
                                  </span>
                                  <div className="flex items-center space-x-2 text-xs">
                                    <span className="px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded">
                                      {result.backend}
                                    </span>
                                    <span className="text-black dark:text-gray-400">
                                      {result.shots} shots
                                    </span>
                                  </div>
                                </div>
                                <div className="grid grid-cols-2 gap-2">
                                  {(() => {
                                    // Don't pass nQubits - let the function infer from actual state strings
                                    const sortedStates = getAllStatesWithCounts(
                                      result.counts,
                                      0,
                                      result.shots,
                                    );
                                    return sortedStates.map(
                                      ([state, count]) => (
                                        <div
                                          key={state}
                                          className="flex items-center justify-between px-2 py-1 bg-gray-800 dark:bg-gray-800 bg-gray-100 rounded"
                                        >
                                          <span className="font-mono text-white dark:text-white text-gray-800">
                                            |{state}⟩
                                          </span>
                                          <span className="text-black dark:text-gray-300 dark:text-gray-300 text-gray-700">
                                            {count} (
                                            {(
                                              (count / result.shots) *
                                              100
                                            ).toFixed(1)}
                                            %)
                                          </span>
                                        </div>
                                      ),
                                    );
                                  })()}
                                </div>
                              </div>
                            ),
                          )}
                        </div>
                      </div>
                    )}

                  {/* Generated QASM */}
                  {hybridResult.qasm_generated && (
                    <div>
                      <h4 className="text-sm font-medium text-white mb-2 flex items-center">
                        <FileCode2 className="w-4 h-4 mr-2 text-purple-400" />
                        Generated QASM
                      </h4>
                      <div className="bg-editor-panelLowest border border-editor-border rounded-lg p-3">
                        <pre className="text-sm text-editor-text whitespace-pre-wrap">
                          {hybridResult.qasm_generated}
                        </pre>
                      </div>
                    </div>
                  )}
                </>
              ) : simulationResults ? (
                <>
                  {/* Standard Execution Output - Text Summary */}
                  <div>
                    <h4 className="text-sm font-medium text-white mb-2 flex items-center">
                      <Terminal className="w-4 h-4 mr-2 text-green-400" />
                      Execution Summary
                    </h4>
                    <div className="bg-gray-900 border border-gray-700 rounded-lg p-3 font-mono text-sm">
                      <pre className="text-green-400 whitespace-pre-wrap break-words">
                        {`Execution completed successfully.\n`}
                        {`Backend: ${simulationResults.metadata.backend || "unknown"}\n`}
                        {`Shots: ${simulationResults.metadata.shots || 0}\n\n`}
                        {`Measurement Results:\n`}
                        {(() => {
                          const shots = simulationResults.metadata.shots || 0;
                          // Don't pass nQubits - let the function infer from actual state strings
                          const sortedStates = getAllStatesWithCounts(
                            simulationResults.counts || {},
                            0,
                            shots,
                          );
                          return sortedStates
                            .map(
                              ([state, count]) =>
                                `  |${state}⟩: ${count} (${((count / (shots || 1)) * 100).toFixed(1)}%)`,
                            )
                            .join("\n");
                        })()}
                      </pre>
                    </div>
                  </div>

                  <div>
                    <h4 className="text-sm font-medium text-white mb-2">
                      Circuit Information
                    </h4>
                    <div className="grid grid-cols-3 gap-4 text-sm">
                      <div>
                        <span className="text-black dark:text-gray-400">
                          Qubits:
                        </span>
                        <span className="text-white ml-2">
                          {simulationResults.metadata.n_qubits}
                        </span>
                      </div>
                      <div>
                        <span className="text-black dark:text-gray-400">
                          Backend:
                        </span>
                        <span className="text-white ml-2">
                          {simulationResults.metadata.backend}
                        </span>
                      </div>
                      <div>
                        <span className="text-black dark:text-gray-400">
                          Shots:
                        </span>
                        <span className="text-white ml-2">
                          {simulationResults.metadata.shots}
                        </span>
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <div className="text-center py-8 text-black dark:text-gray-500">
                  <AlertCircle className="w-8 h-8 mx-auto mb-2 opacity-50 text-yellow-400" />
                  <p className="text-sm">
                    {executionMode === "expert"
                      ? "No hybrid execution results yet."
                      : "No execution results available. Run the circuit to see output."}
                  </p>
                  {executionMode === "expert" && (
                    <div className="mt-4 text-left max-w-md mx-auto bg-editor-panelLowest p-4 rounded-lg border border-editor-border">
                      <p className="text-xs text-black dark:text-gray-400 mb-3">
                        Example hybrid code:
                      </p>
                      <pre className="text-xs text-green-400 font-mono whitespace-pre-wrap">
                        {`import cirq
from qcanvas import compile
import qsim

# Create circuit
q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1])
])

# Compile and run
qasm = compile(circuit, framework="cirq")
result = qsim.run(qasm, shots=100)
print(result.counts)`}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === "histogram" && (
          <div className="h-full overflow-y-auto results-content">
            {quantumResults ? (
              <div className="flex h-full min-h-[14rem] flex-col">
                <h4 className="mb-2 text-sm font-medium text-white">
                  Measurement Results
                </h4>

                {/* Chart.js Histogram: fills the pane so the axis is never cut off */}
                <div className="mb-2 min-h-[11rem] flex-1">
                  <Bar
                    data={(() => {
                      const shots = quantumResults.shots || 0;
                      const histStates = getHistogramStates(
                        quantumResults.counts,
                      );
                      return {
                        labels: histStates.map(([state]) => `|${state}⟩`),
                        datasets: [
                          {
                            label: "Measurement Counts",
                            data: histStates.map(([, count]) => count),
                            backgroundColor: "rgba(99, 102, 241, 0.6)",
                            borderColor: "rgba(99, 102, 241, 1)",
                            borderWidth: 1,
                            borderRadius: 4,
                          },
                        ],
                      };
                    })()}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      plugins: {
                        legend: {
                          display: false,
                        },
                        title: {
                          display: false,
                        },
                        tooltip: {
                          callbacks: {
                            label: (context) => {
                              const count = context.parsed.y ?? 0;
                              const shots = quantumResults.shots || 1;
                              const percentage = (
                                (count / shots) *
                                100
                              ).toFixed(1);
                              return `${count} (${percentage}%)`;
                            },
                          },
                        },
                      },
                      scales: {
                        x: {
                          grid: {
                            color:
                              theme === "light"
                                ? "rgba(0, 0, 0, 0.1)"
                                : "rgba(255, 255, 255, 0.1)",
                          },
                          ticks: {
                            color:
                              theme === "light"
                                ? "rgba(0, 0, 0, 0.8)"
                                : "rgba(255, 255, 255, 0.8)",
                            font: {
                              family: "monospace",
                            },
                          },
                        },
                        y: {
                          grid: {
                            color:
                              theme === "light"
                                ? "rgba(0, 0, 0, 0.1)"
                                : "rgba(255, 255, 255, 0.1)",
                          },
                          ticks: {
                            color:
                              theme === "light"
                                ? "rgba(0, 0, 0, 0.8)"
                                : "rgba(255, 255, 255, 0.8)",
                          },
                          beginAtZero: true,
                        },
                      },
                    }}
                  />
                </div>

                <div className="mt-4 pt-4 border-t border-editor-border">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-black dark:text-gray-400">
                        Total Shots:
                      </span>
                      <span className="text-white ml-2 font-mono">
                        {quantumResults.shots}
                      </span>
                    </div>
                    <div>
                      <span className="text-black dark:text-gray-400">
                        Backend:
                      </span>
                      <span className="text-white ml-2 font-mono">
                        {quantumResults.backend}
                      </span>
                    </div>
                    {simulationResults?.metadata.visitor && (
                      <div>
                        <span className="text-black dark:text-gray-400">
                          Visitor:
                        </span>
                        <span className="text-white ml-2 font-mono">
                          {simulationResults.metadata.visitor}
                        </span>
                      </div>
                    )}
                    <div>
                      <span className="text-black dark:text-gray-400">
                        States:
                      </span>
                      <span className="text-white ml-2 font-mono">
                        {Object.keys(quantumResults.counts).length}
                      </span>
                    </div>
                  </div>

                  {/* Show probabilities if available */}
                  {simulationResults?.probs &&
                    (() => {
                      const shots = simulationResults.metadata.shots || 0;
                      // Mirror histogram behavior: show only non-zero-probability states, in bitstring order
                      const probEntries = Object.entries(
                        simulationResults.probs,
                      )
                        .filter(([, prob]) => prob > 0)
                        .sort(([a], [b]) => a.localeCompare(b));
                      return (
                        <div className="mt-4 pt-4 border-t border-editor-border/50">
                          <h5 className="text-xs font-medium text-black dark:text-gray-400 mb-2">
                            State Probabilities
                          </h5>
                          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
                            {probEntries.map(([state, prob]) => {
                              return (
                                <div
                                  key={state}
                                  className="bg-editor-panelLowest border border-editor-border rounded px-2 py-1"
                                >
                                  <span className="text-black dark:text-gray-400">
                                    |{state}⟩:
                                  </span>
                                  <span className="text-white ml-1 font-mono">
                                    {(prob * 100).toFixed(2)}%
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })()}
                </div>
              </div>
            ) : (
              <div className="text-center py-8 text-black dark:text-gray-500">
                <BarChart3 className="w-8 h-8 mx-auto mb-2 opacity-50 text-yellow-400" />
                <p className="text-sm">
                  No execution results available. Run the circuit to see
                  histogram.
                </p>
              </div>
            )}
          </div>
        )}

        {activeTab === "qasm" && (
          <div className="h-full overflow-y-auto results-content">
            {!compiledQasm ? (
              <div className="text-center py-8 text-black dark:text-gray-500">
                <FileCode2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
                <p className="text-sm">
                  No compiled OpenQASM yet. Select &quot;Compile&quot; mode and
                  run to generate QASM.
                </p>
              </div>
            ) : (
              <div className="bg-editor-panelLowest border border-editor-border rounded overflow-hidden">
                <MonacoEditor
                  height="460px"
                  language="qasm"
                  theme={theme === "light" ? "quantum-light" : "quantum-dark"}
                  value={compiledQasm}
                  options={{
                    readOnly: true,
                    domReadOnly: true,
                    minimap: { enabled: false },
                    lineNumbers: "on",
                    wordWrap: "on",
                    scrollBeyondLastLine: false,
                    automaticLayout: true,
                    fontSize: 13,
                    fontFamily:
                      "JetBrains Mono, Fira Code, Monaco, Consolas, monospace",
                    renderWhitespace: "selection",
                    renderControlCharacters: false,
                    padding: { top: 12, bottom: 12 },
                  }}
                />
              </div>
            )}
          </div>
        )}

        {activeTab === "errors" && (
          <div className="h-full overflow-y-auto results-content">
            {errors.length === 0 ? (
              <div className="text-center py-8 text-black dark:text-gray-500">
                <CheckCircle className="w-8 h-8 mx-auto mb-2 opacity-50 text-green-400" />
                <p className="text-sm">
                  No errors found! Your code looks good.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {/* Error Summary */}
                <div className="bg-editor-bg border border-editor-border rounded-lg p-4 mb-4">
                  <h4 className="text-sm font-medium text-white mb-3">
                    Error Summary
                  </h4>
                  <div className="grid grid-cols-3 gap-4 text-center">
                    <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3">
                      <div className="text-lg font-bold text-red-400">
                        {errors.filter((e) => e.severity === "error").length}
                      </div>
                      <div className="text-xs text-red-300">Errors</div>
                    </div>
                    <div className="bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-3">
                      <div className="text-lg font-bold text-yellow-400">
                        {errors.filter((e) => e.severity === "warning").length}
                      </div>
                      <div className="text-xs text-yellow-300">Warnings</div>
                    </div>
                    <div className="bg-blue-500/10 border border-blue-500/20 rounded-lg p-3">
                      <div className="text-lg font-bold text-blue-400">
                        {errors.filter((e) => e.severity === "info").length}
                      </div>
                      <div className="text-xs text-blue-300">Info</div>
                    </div>
                  </div>
                </div>

                {/* Error List */}
                <div className="space-y-3">
                  {errors.map((error) => (
                    <div
                      key={error.id}
                      className="bg-editor-bg border border-editor-border rounded-lg p-4 hover:border-quantum-blue-light/30 transition-colors"
                    >
                      <div className="flex items-start space-x-3">
                        <div className="flex-shrink-0 mt-0.5">
                          {getErrorIcon(error.severity)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <p
                                className={`text-sm font-medium ${getErrorColor(error.severity)}`}
                              >
                                {error.message}
                              </p>
                              <div className="flex items-center space-x-4 mt-1 text-xs text-black dark:text-gray-400">
                                <span>File: {error.file}</span>
                                {error.line > 0 && (
                                  <span>
                                    Line {error.line}:{error.column}
                                  </span>
                                )}
                                <span className="px-2 py-1 bg-editor-border rounded text-white capitalize">
                                  {error.severity}
                                </span>
                              </div>
                            </div>
                            <button
                              onClick={() => copyToClipboard(error.message)}
                              className="p-1 hover:bg-editor-border rounded transition-colors ml-2"
                              title="Copy error message"
                            >
                              <Copy className="w-3 h-3 text-black dark:text-gray-400" />
                            </button>
                          </div>

                          {/* Error details */}
                          <div className="mt-3 bg-gray-900 border border-gray-700 rounded p-2">
                            <div className="flex items-center justify-between mb-1">
                              <span className="text-xs text-black dark:text-gray-400">
                                Error Details:
                              </span>
                              {error.line > 0 && (
                                <span className="text-xs text-black dark:text-gray-500">
                                  Line {error.line}
                                </span>
                              )}
                            </div>
                            <pre className="text-xs text-red-300 font-mono bg-red-900/20 px-2 py-1 rounded whitespace-pre-wrap break-words">
                              {error.code}
                            </pre>
                          </div>

                          {/* Suggestion */}
                          {error.suggestion && (
                            <div className="mt-3 bg-blue-900/20 border border-blue-700/30 rounded p-3">
                              <div className="flex items-center space-x-2 mb-2">
                                <AlertCircle className="w-3 h-3 text-blue-400" />
                                <span className="text-xs font-medium text-blue-300">
                                  Suggestion:
                                </span>
                              </div>
                              <p className="text-sm text-blue-200">
                                {error.suggestion}
                              </p>
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === "stats" && (
          <div className="h-full overflow-y-auto results-content">
            <div className="space-y-4 p-1">
              {/* Execution Summary - Hero Cards */}
              <div className="grid grid-cols-3 gap-3">
                <div
                  className={`relative overflow-hidden rounded-xl p-4 ${
                    executionStats.execution.status === "completed"
                      ? "bg-gradient-to-br from-green-500/20 to-green-600/10 border border-green-500/30"
                      : executionStats.execution.status === "pending"
                        ? "bg-gradient-to-br from-yellow-500/20 to-yellow-600/10 border border-yellow-500/30"
                        : "bg-gradient-to-br from-red-500/20 to-red-600/10 border border-red-500/30"
                  }`}
                >
                  <div className="flex flex-col items-center justify-center">
                    <div
                      className={`text-2xl font-bold capitalize ${
                        executionStats.execution.status === "completed"
                          ? "text-green-400"
                          : executionStats.execution.status === "pending"
                            ? "text-yellow-400"
                            : "text-red-400"
                      }`}
                    >
                      {executionStats.execution.status}
                    </div>
                    <div className="text-xs text-black dark:text-gray-400 mt-1">
                      Status
                    </div>
                  </div>
                </div>
                <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-blue-500/20 to-blue-600/10 border border-blue-500/30">
                  <div className="flex flex-col items-center justify-center">
                    <div className="text-2xl font-bold text-blue-400">
                      {executionStats.execution.totalTime}
                    </div>
                    <div className="text-xs text-black dark:text-gray-400 mt-1">
                      Total Time
                    </div>
                  </div>
                </div>
                <div className="relative overflow-hidden rounded-xl p-4 bg-gradient-to-br from-purple-500/20 to-purple-600/10 border border-purple-500/30">
                  <div className="flex flex-col items-center justify-center">
                    <div className="text-2xl font-bold text-purple-400">
                      {executionStats.execution.fidelity
                        ? `${executionStats.execution.fidelity.toFixed(1)}%`
                        : Number(executionStats.execution.shots || 0).toLocaleString("en-US")}
                    </div>
                    <div className="text-xs text-black dark:text-gray-400 mt-1">
                      {executionStats.execution.fidelity ? "Fidelity" : "Shots"}
                    </div>
                  </div>
                </div>
              </div>

              {/* Performance & Shot Stats - Combined Card */}
              <div className="rounded-xl border border-editor-border overflow-hidden">
                <div className="px-4 py-3 border-b border-editor-border bg-white/5">
                  <h4 className="text-sm font-semibold text-white flex items-center">
                    <TrendingUp className="w-4 h-4 mr-2 text-cyan-400" />
                    Performance Overview
                  </h4>
                </div>
                <div className="p-4">
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center p-3 rounded-lg bg-white/5">
                      <div className="text-lg font-semibold text-cyan-400">
                        {executionStats.execution.simulationTime}
                      </div>
                      <div className="text-xs text-black dark:text-gray-400">
                        Simulation
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-white/5">
                      <div className="text-lg font-semibold text-emerald-400">
                        {executionStats.execution.shots.toLocaleString()}
                      </div>
                      <div className="text-xs text-black dark:text-gray-400">
                        Total Shots
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-white/5">
                      <div className="text-lg font-semibold text-amber-400">
                        {executionStats.execution.memoryUsage}
                      </div>
                      <div className="text-xs text-black dark:text-gray-400">
                        Memory
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-white/5">
                      <div className="text-lg font-semibold text-rose-400">
                        {executionStats.execution.cpuUsage}
                      </div>
                      <div className="text-xs text-black dark:text-gray-400">
                        CPU
                      </div>
                    </div>
                  </div>

                  {/* Backend Info */}
                  <div className="mt-4 pt-4 border-t border-editor-border flex items-center justify-between">
                    <div className="flex items-center space-x-4">
                      <div className="flex items-center">
                        <span className="text-xs text-black dark:text-gray-400 mr-2">
                          Backend:
                        </span>
                        <span className="px-2 py-1 rounded-md bg-indigo-500/20 text-indigo-800 dark:text-indigo-300 text-xs font-mono">
                          {executionStats.execution.backend}
                        </span>
                      </div>
                      {(quantumResults?.metadata as any)?.visitor && (
                        <div className="flex items-center">
                          <span className="text-xs text-black dark:text-gray-400 mr-2">
                            Visitor:
                          </span>
                          <span className="px-2 py-1 rounded-md bg-violet-500/20 text-violet-800 dark:text-violet-300 text-xs font-mono">
                            {(quantumResults?.metadata as any)?.visitor}
                          </span>
                        </div>
                      )}
                    </div>
                    <div className="flex items-center">
                      <span className="text-xs text-black dark:text-gray-400 mr-2">
                        Successful:
                      </span>
                      <span className="text-sm font-medium text-green-400">
                        {executionStats.execution.successfulShots.toLocaleString()}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Measurement Results - Only show if we have quantum results */}
              {quantumResults && (
                <div className="rounded-xl border border-editor-border overflow-hidden">
                  <div className="px-4 py-3 border-b border-editor-border bg-white/5">
                    <h4 className="text-sm font-semibold text-white flex items-center">
                      <Zap className="w-4 h-4 mr-2 text-yellow-400" />
                      Measurement Results
                    </h4>
                  </div>
                  <div className="p-4">
                    <div className="grid grid-cols-3 gap-4 mb-4">
                      <div className="text-center p-3 rounded-lg bg-gradient-to-br from-indigo-500/10 to-indigo-600/5 border border-indigo-500/20">
                        <div className="text-xl font-bold text-indigo-400">
                          {Object.keys(quantumResults.counts).length}
                        </div>
                        <div className="text-xs text-black dark:text-gray-400">
                          Unique States
                        </div>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-gradient-to-br from-teal-500/10 to-teal-600/5 border border-teal-500/20">
                        <div className="text-xl font-bold text-teal-400">
                          {Object.values(quantumResults.counts)
                            .reduce((a, b) => a + b, 0)
                            .toLocaleString()}
                        </div>
                        <div className="text-xs text-black dark:text-gray-400">
                          Total Counts
                        </div>
                      </div>
                      <div className="text-center p-3 rounded-lg bg-gradient-to-br from-pink-500/10 to-pink-600/5 border border-pink-500/20">
                        <div className="text-xl font-bold text-pink-400">
                          {(quantumResults.metadata as any).n_qubits}
                        </div>
                        <div className="text-xs text-black dark:text-gray-400">
                          Qubits
                        </div>
                      </div>
                    </div>

                    {/* Top States */}
                    <div className="space-y-2">
                      <h5 className="text-xs font-medium text-black dark:text-gray-400">
                        Top Measurement Outcomes
                      </h5>
                      {Object.entries(quantumResults.counts)
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 4)
                        .map(([state, count]) => {
                          const total = Object.values(
                            quantumResults.counts,
                          ).reduce((a, b) => a + b, 0);
                          const percentage = total > 0 ? (count / total) * 100 : 0;
                          return (
                            <div
                              key={state}
                              className="flex items-center space-x-3"
                            >
                              <span className="text-sm font-mono text-white w-16">
                                |{state}⟩
                              </span>
                              <div className="flex-1 h-2 bg-editor-border rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-gradient-to-r from-indigo-500 to-purple-500 rounded-full transition-all duration-500"
                                  style={{ width: `${percentage}%` }}
                                />
                              </div>
                              <span className="text-sm text-black dark:text-gray-300 w-20 text-right">
                                {percentage.toFixed(1)}%
                              </span>
                            </div>
                          );
                        })}
                    </div>
                  </div>
                </div>
              )}

              {/* Cloud Execution & Billing Telemetry - Premium Card */}
              {(quantumResults?.metadata as any)?.job_id && (
                <div className="rounded-xl border border-quantum-blue/30 overflow-hidden bg-gradient-to-br from-quantum-blue-dark/20 to-gray-900 shadow-lg">
                  <div className="px-4 py-3 border-b border-quantum-blue/20 bg-quantum-blue-dark/40 flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-white flex items-center">
                      <Cloud className="w-4 h-4 mr-2 text-cyan-400" />
                      FastQSim Cloud Job Telemetry
                    </h4>
                    <span className="px-2 py-0.5 text-xs font-mono bg-cyan-500/20 text-cyan-300 rounded border border-cyan-500/30">
                      ID: {(quantumResults?.metadata as any)?.job_id}
                    </span>
                  </div>
                  <div className="p-4 space-y-4">
                    {/* Timing grid */}
                    <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                      <div className="bg-black/30 p-3 rounded-lg border border-white/5">
                        <div className="text-xs text-black dark:text-gray-400">Queue Time</div>
                        <div className="text-sm font-mono text-white mt-1">
                          {(quantumResults?.metadata as any)?.queue_enqueued_at ? new Date((quantumResults?.metadata as any)?.queue_enqueued_at).toLocaleTimeString() : "<1s"}
                        </div>
                      </div>
                      <div className="bg-black/30 p-3 rounded-lg border border-white/5">
                        <div className="text-xs text-black dark:text-gray-400">Execution Start</div>
                        <div className="text-sm font-mono text-white mt-1">
                          {(quantumResults?.metadata as any)?.execution_started_at ? new Date((quantumResults?.metadata as any)?.execution_started_at).toLocaleTimeString() : "N/A"}
                        </div>
                      </div>
                      <div className="bg-black/30 p-3 rounded-lg border border-white/5">
                        <div className="text-xs text-black dark:text-gray-400">Wall Time</div>
                        <div className="text-sm font-mono text-cyan-400 mt-1">
                          {typeof (quantumResults?.metadata as any)?.peak_memory_mb !== 'undefined' && (quantumResults?.metadata as any)?.execution_time_seconds ? `${(quantumResults?.metadata as any)?.execution_time_seconds.toFixed(3)}s` : (quantumResults?.metadata as any)?.execution_time || "N/A"}
                        </div>
                      </div>
                      <div className="bg-black/30 p-3 rounded-lg border border-white/5">
                        <div className="text-xs text-black dark:text-gray-400">Peak RAM</div>
                        <div className="text-sm font-mono text-emerald-400 mt-1">
                          {typeof (quantumResults?.metadata as any)?.peak_memory_mb !== 'undefined' ? `${(quantumResults?.metadata as any)?.peak_memory_mb.toFixed(1)} MB` : (quantumResults?.metadata as any)?.memory_usage || "N/A"}
                        </div>
                      </div>
                      <div className="bg-black/30 p-3 rounded-lg border border-white/5">
                        <div className="text-xs text-black dark:text-gray-400">CPU Compute</div>
                        <div className="text-sm font-mono text-yellow-400 mt-1">
                          {typeof (quantumResults?.metadata as any)?.cpu_seconds_total !== 'undefined' ? `${(quantumResults?.metadata as any)?.cpu_seconds_total.toFixed(3)}s` : "N/A"}
                        </div>
                      </div>
                    </div>

                    {/* Billing Telemetry */}
                    <div className="bg-white/5 p-3 rounded-lg border border-white/10">
                      <h5 className="text-xs font-semibold text-cyan-300 uppercase tracking-wider mb-2 flex items-center">
                        <DollarSign className="w-3.5 h-3.5 mr-1 text-yellow-400" />
                        Billing Telemetry & Resource Units
                      </h5>
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-xs text-black dark:text-gray-400">CPU Millicore-Seconds</div>
                          <div className="text-base font-mono font-bold text-yellow-400">
                            {typeof (quantumResults?.metadata as any)?.billing_cpu_millicore_seconds !== 'undefined' ? (quantumResults?.metadata as any)?.billing_cpu_millicore_seconds.toFixed(2) : "0.00"}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-black dark:text-gray-400">Memory GB-Seconds</div>
                          <div className="text-base font-mono font-bold text-amber-400">
                            {typeof (quantumResults?.metadata as any)?.billing_memory_gb_seconds !== 'undefined' ? (quantumResults?.metadata as any)?.billing_memory_gb_seconds.toFixed(4) : "0.0000"}
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Tags and metadata pills */}
                    {((quantumResults?.metadata as any)?.tags || (quantumResults?.metadata as any)?.metadata) && (
                      <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-white/5">
                        {(quantumResults?.metadata as any)?.tags && Object.keys((quantumResults?.metadata as any)?.tags).length > 0 && (
                          <>
                            <span className="text-xs text-black dark:text-gray-400 mr-1">Tags:</span>
                            {Object.entries((quantumResults?.metadata as any)?.tags).map(([k, v]) => (
                              <span key={k} className="px-2 py-0.5 text-xs bg-purple-500/20 text-purple-300 rounded-full border border-purple-500/30">
                                {k}: {String(v)}
                              </span>
                            ))}
                          </>
                        )}
                        {(quantumResults?.metadata as any)?.metadata && Object.keys((quantumResults?.metadata as any)?.metadata).length > 0 && (
                          <>
                            <span className="text-xs text-black dark:text-gray-400 ml-2 mr-1">Meta:</span>
                            {Object.entries((quantumResults?.metadata as any)?.metadata).filter(([k]) => k !== 'tags').map(([k, v]) => (
                              <span key={k} className="px-2 py-0.5 text-xs bg-blue-500/20 text-blue-300 rounded-full border border-blue-500/30">
                                {k}: {String(v)}
                              </span>
                            ))}
                          </>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Circuit Analysis */}
              <div className="rounded-xl border border-editor-border overflow-hidden">
                <div className="px-4 py-3 border-b border-editor-border bg-white/5">
                  <h4 className="text-sm font-semibold text-white flex items-center">
                    <Cpu className="w-4 h-4 mr-2 text-orange-400" />
                    Circuit Analysis
                  </h4>
                </div>
                <div className="p-4">
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-4">
                    <div className="text-center p-3 rounded-lg bg-white/5 border border-white/10">
                      <div className="text-lg font-semibold text-white">
                        {executionStats.circuit.depth}
                      </div>
                      <div className="text-xs text-black dark:text-gray-400">
                        Depth
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-white/5 border border-white/10">
                      <div className="text-lg font-semibold text-white">
                        {executionStats.circuit.width}
                      </div>
                      <div className="text-xs text-black dark:text-gray-400">
                        Qubits
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-white/5 border border-white/10">
                      <div
                        className={`text-lg font-semibold ${
                          executionStats.circuit.complexity === "High"
                            ? "text-red-400"
                            : executionStats.circuit.complexity === "Medium"
                              ? "text-yellow-400"
                              : "text-green-400"
                        }`}
                      >
                        {executionStats.circuit.complexity}
                      </div>
                      <div className="text-xs text-black dark:text-gray-400">
                        Complexity
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-white/5 border border-white/10">
                      <div className="text-lg font-semibold text-cyan-400">
                        {executionStats.circuit.entanglingGates}
                      </div>
                      <div className="text-xs text-black dark:text-gray-400">
                        Entangling
                      </div>
                    </div>
                    <div className="text-center p-3 rounded-lg bg-white/5 border border-white/10">
                      <div className="text-lg font-semibold text-violet-400">
                        {executionStats.circuit.singleQubitGates}
                      </div>
                      <div className="text-xs text-black dark:text-gray-400">
                        Single-Qubit
                      </div>
                    </div>
                  </div>

                  {/* Gate Distribution */}
                  {Object.keys(executionStats.circuit.gates).length > 0 && (
                    <div className="pt-3 border-t border-editor-border">
                      <h5 className="text-xs font-medium text-black dark:text-gray-400 mb-3">
                        Gate Distribution
                      </h5>
                      <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                        {Object.entries(executionStats.circuit.gates).map(
                          ([gate, count]) => (
                            <div
                              key={gate}
                              className="flex items-center justify-between px-3 py-2 rounded-lg bg-white/5"
                            >
                              <span className="text-xs font-mono text-black dark:text-gray-300">
                                {gate.toUpperCase()}
                              </span>
                              <span className="text-sm font-semibold text-white">
                                {count}
                              </span>
                            </div>
                          ),
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Compilation & Optimization */}
              <div className="rounded-xl border border-editor-border overflow-hidden">
                <div className="px-4 py-3 border-b border-editor-border bg-white/5">
                  <h4 className="text-sm font-semibold text-white flex items-center">
                    <Zap className="w-4 h-4 mr-2 text-emerald-400" />
                    Compilation & Optimization
                  </h4>
                </div>
                <div className="p-4">
                  <div className="grid md:grid-cols-2 gap-4">
                    {/* Compilation Stats */}
                    <div className="space-y-3">
                      <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
                        <span className="text-sm text-black dark:text-gray-400">
                          Status
                        </span>
                        <span
                          className={`px-2 py-1 rounded-md text-xs font-medium ${
                            executionStats.compilation.status === "success" ||
                            executionStats.compilation.status === "completed"
                              ? "bg-green-500/20 text-green-400"
                              : executionStats.compilation.status === "pending"
                                ? "bg-yellow-500/20 text-yellow-400"
                                : "bg-red-500/20 text-red-400"
                          }`}
                        >
                          {executionStats.compilation.status}
                        </span>
                      </div>
                      <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
                        <span className="text-sm text-black dark:text-gray-400">
                          Time
                        </span>
                        <span className="text-sm font-medium text-white">
                          {executionStats.compilation.time}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/20 text-center">
                          <div className="text-lg font-bold text-yellow-400">
                            {executionStats.compilation.warnings}
                          </div>
                          <div className="text-xs text-black dark:text-gray-400">
                            Warnings
                          </div>
                        </div>
                        <div className="p-3 rounded-lg bg-red-500/10 border border-red-500/20 text-center">
                          <div className="text-lg font-bold text-red-400">
                            {executionStats.compilation.errors}
                          </div>
                          <div className="text-xs text-black dark:text-gray-400">
                            Errors
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Optimization Stats */}
                    <div className="space-y-3">
                      <div className="p-3 rounded-lg bg-gradient-to-r from-green-500/10 to-emerald-500/10 border border-green-500/20">
                        <div className="text-xs text-black dark:text-gray-400 mb-2">
                          Optimization Level {executionStats.optimization.level}
                        </div>
                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <div className="text-lg font-bold text-green-400">
                              -{executionStats.optimization.gatesReduced}
                            </div>
                            <div className="text-xs text-black dark:text-gray-400">
                              Gates Reduced
                            </div>
                          </div>
                          <div>
                            <div className="text-lg font-bold text-green-400">
                              -{executionStats.optimization.depthReduced}
                            </div>
                            <div className="text-xs text-black dark:text-gray-400">
                              Depth Reduced
                            </div>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center justify-between p-3 rounded-lg bg-white/5 border border-white/10">
                        <span className="text-sm text-black dark:text-gray-400">
                          Opt. Time
                        </span>
                        <span className="text-sm font-medium text-white">
                          {executionStats.optimization.timeSpent}
                        </span>
                      </div>
                      {executionStats.optimization.techniques.length > 0 && (
                        <div className="flex flex-wrap gap-1">
                          {executionStats.optimization.techniques.map(
                            (technique: string, index: number) => (
                              <span
                                key={index}
                                className="px-2 py-1 text-xs bg-indigo-500/20 text-indigo-300 rounded-md border border-indigo-500/30"
                              >
                                {technique}
                              </span>
                            ),
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default memo(ResultsPane);
