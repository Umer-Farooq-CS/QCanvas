"use client";

import { FILE_TEMPLATES_PRESETS } from "@/lib/fileTemplates";

import { memo, useCallback, useEffect, useRef, useState } from "react";
import dynamic from "next/dynamic";
import { Play, ChevronDown } from "lucide-react";
import { EDITOR_FLUSH_EVENT, useActiveFile, useFileStore } from "@/lib/store";
import { debounce } from "@/lib/utils";
import {
  getHoverForSymbol,
  formatHoverMarkdown,
} from "@/lib/quantumHoverSymbols";
import {
  parseCircuit,
  calculateQubitCount,
  parseCircuitWithCountAsync,
  ParsedGate,
} from "@/lib/circuitParser";
import FindReplace from "./FindReplace";
import { InputLanguage } from "@/types";

// Lazy-load heavy, optional views so they are not part of the /app first load:
// the 2D circuit diagram pulls in all of d3, and the markdown preview pulls in
// react-markdown + remark/rehype + KaTeX. Both are only shown on demand.
const CircuitVisualization = dynamic(() => import("./CircuitVisualization"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full text-black dark:text-gray-500">
      Loading circuit view...
    </div>
  ),
});

const MarkdownPreview = dynamic(() => import("./MarkdownPreview"), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center h-full text-black dark:text-gray-500">
      Loading preview...
    </div>
  ),
});

type SimulationBackend = "cirq" | "qiskit" | "pennylane" | "";

type EditorPaneProps = {
  onRun: () => void | Promise<void>;
  isRunning: boolean;
  inputLanguage: InputLanguage | "";
  setInputLanguage: (language: InputLanguage | "") => void;
  simBackend: SimulationBackend;
  setSimBackend: (backend: SimulationBackend) => void;
  shots: number;
  setShots: (shots: number) => void;
};

// Dynamically import 3D Visualization to avoid SSR issues
const CircuitVisualization3D = dynamic(
  () => import("./CircuitVisualization3D"),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full text-black dark:text-gray-500">
        Loading 3D View...
      </div>
    ),
  },
);

// Dynamically import Monaco Editor with SSR disabled to prevent server-side rendering issues
const Editor = dynamic(
  () => import("@monaco-editor/react").then((mod) => mod.Editor),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full bg-editor-bg">
        <div className="flex items-center space-x-2">
          <div className="w-6 h-6 border-2 border-quantum-blue-light border-t-transparent rounded-full spinner"></div>
          <span className="text-editor-text">Loading editor...</span>
        </div>
      </div>
    ),
  },
);

function EditorPane({
  onRun,
  isRunning,
  inputLanguage,
  setInputLanguage,
  simBackend,
  setSimBackend,
  shots,
  setShots,
}: Readonly<EditorPaneProps>) {
  // Fine-grained subscriptions: re-render only for the active file / theme /
  // execution mode, not for unrelated store updates.
  const theme = useFileStore((s) => s.theme);
  const executionMode = useFileStore((s) => s.executionMode);
  const setExecutionMode = useFileStore((s) => s.setExecutionMode);
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const hoverProviderRef = useRef<any>(null);
  const completionProviderRef = useRef<any>(null);
  const hoverProviderPythonqRef = useRef<any>(null);
  const completionProviderPythonqRef = useRef<any>(null);
  const qasmTokensProviderRef = useRef<any>(null);
  const qasmConfigProviderRef = useRef<any>(null);
  const pythonqTokensProviderRef = useRef<any>(null);
  const pythonqConfigProviderRef = useRef<any>(null);
  const pendingRevealRef = useRef<{
    fileId: string;
    lineNumber: number;
    column?: number;
    query?: string;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const runMenuRef = useRef<HTMLDivElement>(null);
  const activeFile = useActiveFile();
  const [showFindReplace, setShowFindReplace] = useState(false);
  const [findReplaceMode, setFindReplaceMode] = useState<"find" | "replace">(
    "find",
  );
  const [showCircuitVisualization, setShowCircuitVisualization] =
    useState(false);
  const [is3DMode, setIs3DMode] = useState(false);
  const [showRunMenu, setShowRunMenu] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const [circuitHeight, setCircuitHeight] = useState(200);
  const [isDraggingCircuit, setIsDraggingCircuit] = useState(false);
  const [showMarkdownPreview, setShowMarkdownPreview] = useState(false);

  const disposeMonacoProviders = () => {
    if (hoverProviderRef.current) {
      hoverProviderRef.current.dispose();
      hoverProviderRef.current = null;
    }
    if (hoverProviderPythonqRef.current) {
      hoverProviderPythonqRef.current.dispose();
      hoverProviderPythonqRef.current = null;
    }
    if (completionProviderRef.current) {
      completionProviderRef.current.dispose();
      completionProviderRef.current = null;
    }
    if (completionProviderPythonqRef.current) {
      completionProviderPythonqRef.current.dispose();
      completionProviderPythonqRef.current = null;
    }
    if (qasmTokensProviderRef.current) {
      qasmTokensProviderRef.current.dispose();
      qasmTokensProviderRef.current = null;
    }
    if (qasmConfigProviderRef.current) {
      qasmConfigProviderRef.current.dispose();
      qasmConfigProviderRef.current = null;
    }
    if (pythonqTokensProviderRef.current) {
      pythonqTokensProviderRef.current.dispose();
      pythonqTokensProviderRef.current = null;
    }
    if (pythonqConfigProviderRef.current) {
      pythonqConfigProviderRef.current.dispose();
      pythonqConfigProviderRef.current = null;
    }
  };

  // Parsed circuit state for async AST parsing
  const [parsedGates, setParsedGates] = useState<ParsedGate[]>([]);
  const [parsedQubits, setParsedQubits] = useState(2);
  const [isParsing, setIsParsing] = useState(false);

  // Ensure component is mounted on client before rendering Monaco
  useEffect(() => {
    setIsMounted(true);
  }, []);

  // Monaco providers are language-level singletons; always release them on unmount
  // so remounts/hot reloads do not stack duplicate hover providers.
  useEffect(() => {
    return () => {
      disposeMonacoProviders();
    };
  }, []);

  // Default to preview when switching to a markdown file.
  useEffect(() => {
    const isMd = !!activeFile?.name?.toLowerCase().endsWith(".md");
    setShowMarkdownPreview(isMd);
  }, [activeFile?.id]);

  useEffect(() => {
    if (!showRunMenu) return;

    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (!runMenuRef.current?.contains(target)) {
        setShowRunMenu(false);
      }
    };

    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [showRunMenu]);

  // Async circuit parsing with debouncing
  // Uses backend AST parsing when available, falls back to regex
  useEffect(() => {
    if (!showCircuitVisualization || !activeFile?.content) {
      return;
    }

    // Debounce the parsing to avoid too many API calls
    const timer = setTimeout(async () => {
      setIsParsing(true);
      try {
        const result = await parseCircuitWithCountAsync(activeFile.content);
        setParsedGates(result.gates);
        setParsedQubits(result.qubits);
      } catch (err) {
        // Fallback to sync parsing on error
        console.warn("Async parsing failed, using sync fallback:", err);
        const gates = parseCircuit(activeFile.content);
        setParsedGates(gates);
        setParsedQubits(calculateQubitCount(gates));
      } finally {
        setIsParsing(false);
      }
    }, 500); // 500ms debounce

    return () => clearTimeout(timer);
  }, [activeFile?.content, showCircuitVisualization]);

  // Handle drag resize for circuit visualization panel
  useEffect(() => {
    if (!isDraggingCircuit) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;

      const containerRect = containerRef.current.getBoundingClientRect();
      // Calculate height from the top of the container (after the header)
      const headerHeight = 48; // h-12 = 48px
      const newHeight = e.clientY - containerRect.top - headerHeight;
      const minHeight = 100;
      const maxHeight = containerRect.height - 200; // Leave space for editor

      setCircuitHeight(Math.max(minHeight, Math.min(maxHeight, newHeight)));
    };

    const handleMouseUp = () => {
      setIsDraggingCircuit(false);
    };

    document.addEventListener("mousemove", handleMouseMove);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDraggingCircuit]);

  const handleCircuitDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    setIsDraggingCircuit(true);
  };

  // Debounced content update to avoid too frequent store updates. The latest
  // unsaved edit is kept in a ref so it can be flushed synchronously (before a
  // save/run, or when switching files) instead of being lost or arriving late.
  const pendingEditRef = useRef<{ fileId: string; content: string } | null>(
    null,
  );
  const flushPendingEdit = useCallback(() => {
    const pending = pendingEditRef.current;
    if (!pending) return;
    pendingEditRef.current = null;
    useFileStore.getState().updateFileContent(pending.fileId, pending.content);
  }, []);
  const debouncedFlush = useRef(debounce(() => flushPendingEdit(), 300)).current;

  // Saving must not have side effects such as downloading the circuit SVG;
  // the explicit "SVG" button in the circuit toolbar handles exports.
  // saveActiveFile() flushes pending editor content itself (EDITOR_FLUSH_EVENT).
  const handleManualSave = useCallback(() => {
    void useFileStore.getState().saveActiveFile();
  }, []);

  // Let save/run (and anything else) ask for the latest editor content.
  useEffect(() => {
    globalThis.window?.addEventListener(EDITOR_FLUSH_EVENT, flushPendingEdit);
    return () => {
      globalThis.window?.removeEventListener(
        EDITOR_FLUSH_EVENT,
        flushPendingEdit,
      );
      // Don't drop the last keystrokes when the editor unmounts.
      flushPendingEdit();
    };
  }, [flushPendingEdit]);

  // Menu "Selection > Select All" targets the Monaco editor.
  useEffect(() => {
    const onSelectAll = () => {
      const editor = editorRef.current;
      const model = editor?.getModel?.();
      if (!editor || !model) return;
      editor.focus?.();
      editor.setSelection?.(model.getFullModelRange());
    };
    globalThis.window?.addEventListener("editor-select-all", onSelectAll);
    return () =>
      globalThis.window?.removeEventListener("editor-select-all", onSelectAll);
  }, []);

  const handleEditorDidMount = (editor: any, monacoInstance: any) => {
    // Guard against SSR - ensure we're in browser environment
    if (typeof window === "undefined" || !editor || !monacoInstance) {
      return;
    }

    editorRef.current = editor;
    monacoRef.current = monacoInstance;

    const applyRevealIfReady = (payload: {
      fileId: string;
      lineNumber: number;
      column?: number;
      query?: string;
    }) => {
      pendingRevealRef.current = payload;

      const model = editorRef.current?.getModel?.();
      const currentActiveId = useFileStore.getState().activeFileId;
      if (!model) return;
      if (!currentActiveId || currentActiveId !== payload.fileId) return;

      const lineNumber = Math.max(1, payload.lineNumber);
      const maxColumn = model.getLineMaxColumn(lineNumber);
      const column = Math.min(
        Math.max(1, payload.column ?? 1),
        Math.max(1, maxColumn),
      );

      const qLen = payload.query ? payload.query.length : 0;
      const endColumn = qLen > 0 ? Math.min(maxColumn, column + qLen) : column;

      editorRef.current.setSelection?.({
        startLineNumber: lineNumber,
        startColumn: column,
        endLineNumber: lineNumber,
        endColumn,
      });
      editorRef.current.setPosition?.({ lineNumber, column });
      editorRef.current.revealLineInCenter?.(lineNumber);
      editorRef.current.focus?.();
    };

    const onReveal = (e: Event) => {
      const ce = e as CustomEvent;
      if (!ce.detail) return;
      applyRevealIfReady(ce.detail);
    };

    globalThis.window?.addEventListener("qcanvas:reveal-in-editor", onReveal);

    // Cleanup listener if Monaco is disposed/re-mounted.
    editor.onDidDispose?.(() => {
      globalThis.window?.removeEventListener(
        "qcanvas:reveal-in-editor",
        onReveal,
      );
    });

    // Register language-level providers only once; dispose previous on re-mount.
    disposeMonacoProviders();

    // Ensure Ctrl+A selects all text as a single continuous selection
    // The issue: setSelection might not clear existing multi-cursor selections
    // Solution: Use setSelections with exactly one selection to ensure a single continuous selection
    editor.addCommand(
      monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyA,
      () => {
        const model = editor.getModel();
        if (!model) return;

        // Get the full range of the document
        const fullRange = model.getFullModelRange();

        // Create a Selection object from the Range
        // This ensures we have exactly one selection, clearing any existing multi-cursor state
        const selection = new monacoInstance.Selection(
          fullRange.startLineNumber,
          fullRange.startColumn,
          fullRange.endLineNumber,
          fullRange.endColumn,
        );

        // Use setSelections with a single selection array to ensure exactly one continuous selection
        // This prevents the selection from being split into multiple parts
        editor.setSelections([selection]);

        // Reveal the selection to ensure it's visible
        editor.revealRangeInCenter(fullRange);
      },
    );

    // Configure Monaco Editor themes
    monacoInstance.editor.defineTheme("quantum-dark", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "", foreground: "E5E2E1" },
        { token: "comment", foreground: "8B90A0", fontStyle: "italic" },
        { token: "keyword", foreground: "A7C8FF" },
        { token: "keyword.control", foreground: "A7C8FF" },
        { token: "keyword.operator", foreground: "E5E2E1" },
        { token: "string", foreground: "46EAED" },
        { token: "string.escape", foreground: "46EAED" },
        { token: "number", foreground: "FFABF3" },
        { token: "type", foreground: "A7C8FF" },
        { token: "type.identifier", foreground: "A7C8FF" },
        { token: "function", foreground: "46EAED" },
        { token: "identifier", foreground: "E5E2E1" },
        { token: "delimiter", foreground: "8B90A0" },
      ],
      colors: {
        "editor.background": "#131313",
        "editor.foreground": "#e5e2e1",
        "editor.lineHighlightBackground": "#1b1b1c",
        "editor.selectionBackground": "#2f4d74",
        "editor.inactiveSelectionBackground": "#2a2a2a",
        "editorCursor.foreground": "#a7c8ff",
        "editorWhitespace.foreground": "#414755",
        "editorGutter.background": "#0e0e0e",
        "editorLineNumber.foreground": "#8b90a0",
        "editorLineNumber.activeForeground": "#e5e2e1",
        "editorBracketHighlight.foreground1": "#a7c8ff",
        "editorBracketHighlight.foreground2": "#46eaed",
        "editorBracketHighlight.foreground3": "#ffabf3",
        "editorBracketHighlight.foreground4": "#a7c8ff",
        "editorBracketHighlight.foreground5": "#46eaed",
        "editorBracketHighlight.foreground6": "#ffabf3",
      },
    });

    monacoInstance.editor.defineTheme("quantum-light", {
      base: "vs",
      inherit: true,
      rules: [
        { token: "", foreground: "1F2937" },
        { token: "comment", foreground: "64748B", fontStyle: "italic" },
        { token: "keyword", foreground: "2563EB" },
        { token: "keyword.control", foreground: "2563EB" },
        { token: "keyword.operator", foreground: "1F2937" },
        { token: "string", foreground: "0F9EA8" },
        { token: "string.escape", foreground: "0F9EA8" },
        { token: "number", foreground: "B832A6" },
        { token: "type", foreground: "2563EB" },
        { token: "type.identifier", foreground: "2563EB" },
        { token: "function", foreground: "0F9EA8" },
        { token: "identifier", foreground: "1F2937" },
        { token: "delimiter", foreground: "64748B" },
      ],
      colors: {
        "editor.background": "#f7f9fc",
        "editor.foreground": "#1f2937",
        "editor.lineHighlightBackground": "#eef2f8",
        "editor.selectionBackground": "#d9e8ff",
        "editor.inactiveSelectionBackground": "#e6ebf2",
        "editorCursor.foreground": "#2563eb",
        "editorWhitespace.foreground": "#cbd5e1",
        "editorGutter.background": "#eef2f8",
        "editorLineNumber.foreground": "#64748b",
        "editorLineNumber.activeForeground": "#1f2937",
        "editorBracketHighlight.foreground1": "#2563eb",
        "editorBracketHighlight.foreground2": "#0f9ea8",
        "editorBracketHighlight.foreground3": "#b832a6",
        "editorBracketHighlight.foreground4": "#2563eb",
        "editorBracketHighlight.foreground5": "#0f9ea8",
        "editorBracketHighlight.foreground6": "#b832a6",
      },
    });

    // Use store theme so editor follows app theme immediately.
    monacoInstance.editor.setTheme(
      theme === "light" ? "quantum-light" : "quantum-dark",
    );

    // Register OpenQASM language + tokenizer (Monarch)
    // Monaco has no built-in QASM, so we provide minimal tokenization.
    const ensureQasmLanguage = () => {
      const existing = monacoInstance.languages
        .getLanguages()
        ?.some((l: any) => l.id === "qasm");

      if (!existing) {
        monacoInstance.languages.register({
          id: "qasm",
          extensions: [".qasm", ".qasm3"],
          aliases: ["OpenQASM", "QASM", "qasm"],
          mimetypes: ["text/x-qasm"],
        });
      }

      qasmConfigProviderRef.current =
        monacoInstance.languages.setLanguageConfiguration("qasm", {
          comments: {
            lineComment: "//",
            blockComment: ["/*", "*/"],
          },
          brackets: [
            ["{", "}"],
            ["[", "]"],
            ["(", ")"],
          ],
          autoClosingPairs: [
            { open: "{", close: "}" },
            { open: "[", close: "]" },
            { open: "(", close: ")" },
            { open: '"', close: '"' },
          ],
          surroundingPairs: [
            { open: "{", close: "}" },
            { open: "[", close: "]" },
            { open: "(", close: ")" },
            { open: '"', close: '"' },
          ],
        });

      const keywords = [
        "OPENQASM",
        "include",
        "def",
        "gate",
        "cal",
        "extern",
        "const",
        "input",
        "output",
        "return",
        "if",
        "else",
        "for",
        "while",
        "break",
        "continue",
        "end",
        "barrier",
        "measure",
        "reset",
        "let",
      ];

      const types = [
        "qubit",
        "bit",
        "int",
        "uint",
        "float",
        "angle",
        "bool",
        "complex",
        "duration",
        "stretch",
        "array",
      ];

      // Common built-in functions/macros (non-exhaustive)
      const builtins = [
        "sin",
        "cos",
        "tan",
        "asin",
        "acos",
        "atan",
        "atan2",
        "exp",
        "ln",
        "sqrt",
        "pow",
        "mod",
        "abs",
        "min",
        "max",
        "popcount",
      ];

      // Common gate/instruction identifiers (non-exhaustive).
      // Treated as "function" tokens so they get gate-like coloring.
      const quantumGates = [
        // Single-qubit
        "id",
        "x",
        "y",
        "z",
        "h",
        "s",
        "sdg",
        "t",
        "tdg",
        "sx",
        "sxdg",
        "p",
        // Parametric rotations
        "rx",
        "ry",
        "rz",
        "u",
        "u1",
        "u2",
        "u3",
        // Two/three-qubit
        "cx",
        "cnot",
        "cz",
        "cy",
        "ch",
        "swap",
        "iswap",
        "cswap",
        "ccx",
        "toffoli",
        "ccz",
        // Controlled-phase / rotation families
        "cp",
        "crx",
        "cry",
        "crz",
        // Instructions (also appear in keywords, but harmless here)
        "barrier",
        "measure",
        "reset",
      ];

      qasmTokensProviderRef.current =
        monacoInstance.languages.setMonarchTokensProvider("qasm", {
          keywords,
          types,
          builtins,
          quantumGates,
          tokenizer: {
            root: [
              // Whitespace
              { include: "@whitespace" },

              // Directives / version
              [
                // Non-capturing inner group: Monaco requires every capture
                // group to be matched consecutively (a nested group threw).
                /(OPENQASM)(\s+)(\d+(?:\.\d+)?)(\s*;)/,
                ["keyword", "", "number", "delimiter"],
              ],

              // Identifiers and keywords
              [
                /[a-zA-Z_]\w*/,
                {
                  cases: {
                    "@keywords": "keyword",
                    "@types": "type",
                    "@builtins": "function",
                    "@quantumGates": "function",
                    "@default": "identifier",
                  },
                },
              ],

              // Numbers
              [/\d+(_\d+)*(\.\d+(_\d+)*)?([eE][+-]?\d+)?/, "number"],

              // Strings
              [
                /"/,
                { token: "string.quote", bracket: "@open", next: "@string" },
              ],

              // Operators & delimiters
              [/[-+*/%]=?/, "operator"],
              [/==|!=|<=|>=|<|>|&&|\|\||!/, "operator"],
              [/[[\]{}()]/, "@brackets"],
              [/[,.;:]/, "delimiter"],

              // Annotations (e.g., @foo)
              [/@[a-zA-Z_]\w*/, "annotation"],
            ],

            whitespace: [
              [/[ \t\r\n]+/, ""],
              [/\/\*/, "comment", "@comment"],
              [/\/\/.*$/, "comment"],
            ],

            comment: [
              [/[^/*]+/, "comment"],
              [/\*\//, "comment", "@pop"],
              [/[/*]/, "comment"],
            ],

            string: [
              [/[^\\"]+/, "string"],
              [/\\./, "string.escape"],
              [/"/, { token: "string.quote", bracket: "@close", next: "@pop" }],
            ],
          },
        });
    };

    ensureQasmLanguage();

    // Register Python+Quantum language mode (Monarch)
    // Keeps normal Python highlighting strong and also highlights quantum gates/classes.
    const ensurePythonQuantumLanguage = () => {
      const existing = monacoInstance.languages
        .getLanguages()
        ?.some((l: any) => l.id === "pythonq");

      if (!existing) {
        monacoInstance.languages.register({
          id: "pythonq",
          extensions: [".py"],
          aliases: ["Python (Quantum)", "pythonq"],
          mimetypes: ["text/x-python"],
        });
      }

      pythonqConfigProviderRef.current =
        monacoInstance.languages.setLanguageConfiguration("pythonq", {
          comments: { lineComment: "#" },
          brackets: [
            ["{", "}"],
            ["[", "]"],
            ["(", ")"],
          ],
          autoClosingPairs: [
            { open: "{", close: "}" },
            { open: "[", close: "]" },
            { open: "(", close: ")" },
            { open: '"', close: '"' },
            { open: "'", close: "'" },
          ],
          surroundingPairs: [
            { open: "{", close: "}" },
            { open: "[", close: "]" },
            { open: "(", close: ")" },
            { open: '"', close: '"' },
            { open: "'", close: "'" },
          ],
        });

      const pyKeywords = [
        "False",
        "None",
        "True",
        "and",
        "as",
        "assert",
        "async",
        "await",
        "break",
        "class",
        "continue",
        "def",
        "del",
        "elif",
        "else",
        "except",
        "finally",
        "for",
        "from",
        "global",
        "if",
        "import",
        "in",
        "is",
        "lambda",
        "nonlocal",
        "not",
        "or",
        "pass",
        "raise",
        "return",
        "try",
        "while",
        "with",
        "yield",
        "match",
        "case",
      ];

      const builtins = [
        "print",
        "len",
        "range",
        "list",
        "dict",
        "set",
        "tuple",
        "int",
        "float",
        "str",
        "bool",
        "sum",
        "min",
        "max",
        "enumerate",
        "zip",
        "map",
        "filter",
        "any",
        "all",
        "isinstance",
        // Qiskit helpers commonly used in examples
        "execute",
      ];

      const quantumGateMethods = [
        "h",
        "x",
        "y",
        "z",
        "s",
        "sdg",
        "t",
        "tdg",
        "rx",
        "ry",
        "rz",
        "u",
        "u1",
        "u2",
        "u3",
        "cx",
        "cnot",
        "cz",
        "cy",
        "ch",
        "cp",
        "crx",
        "cry",
        "crz",
        "swap",
        "cswap",
        "ccx",
        "toffoli",
        "ccz",
        "barrier",
        "measure",
        "measure_all",
        "reset",
      ];

      const quantumGateClasses = [
        // Generic gates across frameworks
        "H",
        "X",
        "Y",
        "Z",
        "S",
        "T",
        "CNOT",
        "CX",
        "CZ",
        "CY",
        "CH",
        "SWAP",
        "CSWAP",
        "CCX",
        "CCZ",
        "RX",
        "RY",
        "RZ",
        "CRX",
        "CRY",
        "CRZ",
        "CP",
        "U",
        "Hadamard",
        "PauliX",
        "PauliY",
        "PauliZ",
        "Rot",
        "PhaseShift",
      ];

      const quantumFrameworkMethods = [
        // PennyLane
        "device",
        "qnode",
        "measure",
        "expval",
        "probs",
        "state",
        "sample",
        "counts",
        // Cirq / Qiskit common helpers that appear in examples
        "Circuit",
        "LineQubit",
      ];

      const quantumFrameworkClasses = [
        // Cirq
        "Circuit",
        "LineQubit",
        "GridQubit",
        "NamedQubit",
        "Simulator",
        "DensityMatrixSimulator",
        // Qiskit
        "QuantumCircuit",
        "Aer",
      ];

      pythonqTokensProviderRef.current =
        monacoInstance.languages.setMonarchTokensProvider("pythonq", {
          keywords: pyKeywords,
          builtins,
          quantumGateMethods,
          quantumGateClasses,
          quantumFrameworkMethods,
          quantumFrameworkClasses,
          tokenizer: {
            root: [
              { include: "@whitespace" },

              [/#.*$/, "comment"],

              [/'''/, "string.quote", "@stringS3"],
              [/"""/, "string.quote", "@stringD3"],
              [/'/, "string.quote", "@stringS"],
              [/"/, "string.quote", "@stringD"],

              [/\d+(_\d+)*(\.\d+(_\d+)*)?([eE][+-]?\d+)?/, "number"],

              [/@[a-zA-Z_]\w*/, "annotation"],

              // `.h(`, `.cx(`, `.measure_all(` ...
              [
                /(\.)([a-zA-Z_]\w*)(\s*)(\()/,
                {
                  cases: {
                    "$2@quantumGateMethods": [
                      "delimiter",
                      "function",
                      "",
                      "delimiter.parenthesis",
                    ],
                    "$2@quantumGateClasses": [
                      "delimiter",
                      "function",
                      "",
                      "delimiter.parenthesis",
                    ],
                    "$2@quantumFrameworkMethods": [
                      "delimiter",
                      "function",
                      "",
                      "delimiter.parenthesis",
                    ],
                    "@default": [
                      "delimiter",
                      "identifier",
                      "",
                      "delimiter.parenthesis",
                    ],
                  },
                },
              ],

              // Gate classes like `CNOT`, `RX`, etc.
              [
                /\b([A-Z][A-Za-z0-9_]*)\b/,
                {
                  cases: {
                    "@quantumGateClasses": "function",
                    "@quantumFrameworkClasses": "type.identifier",
                    "@default": "type.identifier",
                  },
                },
              ],

              [
                /[a-zA-Z_]\w*/,
                {
                  cases: {
                    "@keywords": "keyword",
                    "@builtins": "function",
                    "@default": "identifier",
                  },
                },
              ],

              [
                /==|!=|<=|>=|<|>|:=|=|\+|\-|\*|\/|%|\*\*|\||&|\^|~|<<|>>/,
                "operator",
              ],
              [/[,.;:]/, "delimiter"],
              [/[[\]{}()]/, "@brackets"],
            ],

            whitespace: [[/[ \t\r\n]+/, ""]],

            stringS: [
              [/[^\\']+/, "string"],
              [/\\./, "string.escape"],
              [/'/, "string.quote", "@pop"],
            ],
            stringD: [
              [/[^\\"]+/, "string"],
              [/\\./, "string.escape"],
              [/"/, "string.quote", "@pop"],
            ],
            stringS3: [
              [/[^']+/, "string"],
              [/'''/, "string.quote", "@pop"],
              [/'/, "string"],
            ],
            stringD3: [
              [/[^"]+/, "string"],
              [/"""/, "string.quote", "@pop"],
              [/"/, "string"],
            ],
          },
        });
    };

    ensurePythonQuantumLanguage();

    // Add keyboard shortcuts
    editor.addCommand(
      monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyS,
      () => {
        // Trigger save action
        handleManualSave();
      },
    );

    // Find and Replace shortcuts
    editor.addCommand(
      monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyF,
      () => {
        setFindReplaceMode("find");
        setShowFindReplace(true);
      },
    );

    editor.addCommand(
      monacoInstance.KeyMod.CtrlCmd | monacoInstance.KeyCode.KeyH,
      () => {
        setFindReplaceMode("replace");
        setShowFindReplace(true);
      },
    );

    // Add quantum-specific snippets for Python/Qiskit (register for both python + pythonq)
    const registerQuantumSnippets = (langId: string) =>
      monacoInstance.languages.registerCompletionItemProvider(langId, {
        provideCompletionItems: () => {
          return {
            suggestions: [
              {
                label: "qiskit-bell",
                kind: monacoInstance.languages.CompletionItemKind.Snippet,
                insertText: [
                  "from qiskit import QuantumCircuit, execute, Aer",
                  "",
                  "# Create Bell state circuit",
                  "qc = QuantumCircuit(2, 2)",
                  "qc.h(0)  # Hadamard gate",
                  "qc.cx(0, 1)  # CNOT gate",
                  "qc.measure_all()",
                  "",
                  "# Execute circuit",
                  'backend = Aer.get_backend("qasm_simulator")',
                  "job = execute(qc, backend, shots=1024)",
                  "result = job.result()",
                  "counts = result.get_counts(qc)",
                  "print(counts)",
                ].join("\n"),
                documentation: "Create a Bell state quantum circuit",
              },
              {
                label: "qiskit-grover",
                kind: monacoInstance.languages.CompletionItemKind.Snippet,
                insertText: [
                  "from qiskit import QuantumCircuit, execute, Aer",
                  "import numpy as np",
                  "",
                  "def grovers_algorithm(n_qubits, oracle):",
                  "    qc = QuantumCircuit(n_qubits, n_qubits)",
                  "    ",
                  "    # Initialize superposition",
                  "    qc.h(range(n_qubits))",
                  "    ",
                  "    # Apply oracle",
                  "    oracle(qc)",
                  "    ",
                  "    # Diffusion operator",
                  "    qc.h(range(n_qubits))",
                  "    qc.x(range(n_qubits))",
                  "    qc.h(n_qubits-1)",
                  "    qc.mct(list(range(n_qubits-1)), n_qubits-1)",
                  "    qc.h(n_qubits-1)",
                  "    qc.x(range(n_qubits))",
                  "    qc.h(range(n_qubits))",
                  "    ",
                  "    qc.measure_all()",
                  "    return qc",
                ].join("\n"),
                documentation: "Grover's algorithm template",
              },
            ],
          };
        },
      });

    // Keep existing ref semantics; register pythonq alongside.
    completionProviderRef.current = registerQuantumSnippets("python");
    completionProviderPythonqRef.current = registerQuantumSnippets("pythonq");

    // Quantum Explain It: hover tooltips for framework symbols (when explainItMode is on)
    const registerQuantumHover = (langId: string) =>
      monacoInstance.languages.registerHoverProvider(langId, {
        provideHover: (model: any, position: any) => {
          if (!useFileStore.getState().explainItMode) return null;
          const wordAt = model.getWordAtPosition(position);
          if (!wordAt) return null;
          const word = wordAt.word;
          const line = model.getLineContent(position.lineNumber);
          let dottedPrefix: string | undefined;
          const dotPos = wordAt.startColumn - 2;
          if (dotPos >= 0 && line[dotPos] === ".") {
            const before = line.slice(0, dotPos);
            const match = before.match(/([a-zA-Z_]\w*)\s*$/);
            if (match) dottedPrefix = match[1];
          }
          const entry = getHoverForSymbol(word, dottedPrefix);
          if (!entry) return null;
          const markdown = formatHoverMarkdown(entry);
          const range = new monacoInstance.Range(
            position.lineNumber,
            wordAt.startColumn,
            position.lineNumber,
            wordAt.endColumn,
          );
          return {
            contents: [{ value: markdown }],
            range,
          };
        },
      });

    hoverProviderRef.current = registerQuantumHover("python");
    hoverProviderPythonqRef.current = registerQuantumHover("pythonq");
  };

  // Apply a pending "reveal in editor" after the correct file becomes active.
  useEffect(() => {
    const pending = pendingRevealRef.current;
    if (!pending) return;
    if (!activeFile) return;
    if (activeFile.id !== pending.fileId) return;
    if (!editorRef.current?.getModel?.()) return;

    const model = editorRef.current.getModel();
    const lineNumber = Math.max(1, pending.lineNumber);
    const maxColumn = model.getLineMaxColumn(lineNumber);
    const column = Math.min(
      Math.max(1, pending.column ?? 1),
      Math.max(1, maxColumn),
    );
    const qLen = pending.query ? pending.query.length : 0;
    const endColumn = qLen > 0 ? Math.min(maxColumn, column + qLen) : column;

    editorRef.current.setSelection?.({
      startLineNumber: lineNumber,
      startColumn: column,
      endLineNumber: lineNumber,
      endColumn,
    });
    editorRef.current.setPosition?.({ lineNumber, column });
    editorRef.current.revealLineInCenter?.(lineNumber);
    editorRef.current.focus?.();
  }, [activeFile?.id]);

  const handleEditorChange = (value: string | undefined) => {
    if (activeFile && value !== undefined) {
      // An edit for a different file must not overwrite the pending one.
      if (
        pendingEditRef.current &&
        pendingEditRef.current.fileId !== activeFile.id
      ) {
        flushPendingEdit();
      }
      pendingEditRef.current = { fileId: activeFile.id, content: value };
      debouncedFlush();
    }
  };

  useEffect(() => {
    if (!monacoRef.current) return;
    monacoRef.current.editor.setTheme(
      theme === "light" ? "quantum-light" : "quantum-dark",
    );
  }, [theme]);

  // Handle keyboard shortcuts globally (only on client)
  useEffect(() => {
    if (typeof window === "undefined" || typeof document === "undefined")
      return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        // Trigger save action
        handleManualSave();
      } else if ((e.ctrlKey || e.metaKey) && e.key === "f") {
        e.preventDefault();
        setFindReplaceMode("find");
        setShowFindReplace(true);
      } else if ((e.ctrlKey || e.metaKey) && e.key === "h") {
        e.preventDefault();
        setFindReplaceMode("replace");
        setShowFindReplace(true);
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [handleManualSave]); // handleManualSave is stable, so this subscribes once

  // Handle find events from TopBar (only on client)
  useEffect(() => {
    if (typeof window === "undefined") return;

    const handleOpenFind = (e: CustomEvent) => {
      const mode = e.detail?.mode || "find";
      setFindReplaceMode(mode);
      setShowFindReplace(true);
    };

    window.addEventListener("open-find", handleOpenFind as EventListener);
    return () =>
      window.removeEventListener("open-find", handleOpenFind as EventListener);
  }, []);

  // Get Monaco language from file extension
  const getMonacoLanguage = (language: string) => {
    switch (language) {
      case "python":
        return "pythonq";
      case "javascript":
        return "javascript";
      case "typescript":
        return "typescript";
      case "json":
        return "json";
      case "qasm":
        return "qasm";
      case "markdown":
        return "markdown";
      default:
        return "plaintext";
    }
  };

  if (!activeFile) {
    return <EmptyEditor />;
  }

  return (
    <div ref={containerRef} className="editor-pane">
      {/* Top utility row with VS Code-style run controls on the right */}
      <div className="relative z-40 overflow-visible h-10 bg-editor-bg border-b border-editor-border/80 flex items-center justify-between px-2.5 gap-2 backdrop-blur-sm">
        {/* <div className="relative z-40 overflow-visible h-10 bg-gradient-to-r from-editor-sidebar via-editor-sidebar to-editor-bg/90 border-b border-editor-border/80 flex items-center justify-between px-2.5 gap-2 backdrop-blur-sm"> */}
        <div className="flex items-center gap-2">
          {activeFile.name.toLowerCase().endsWith(".md") && (
            <button
              type="button"
              onClick={() => setShowMarkdownPreview((p) => !p)}
              className={`px-2.5 py-1 text-xs rounded-md border transition-all duration-200 ${
                showMarkdownPreview
                  ? "bg-emerald-400/10 border-emerald-400/30 text-emerald-800 dark:text-emerald-300 shadow-[0_0_0_1px_rgba(132, 225, 190, 0.4)]"
                  : "bg-editor-bg border-editor-border text-editor-text hover:bg-editor-border/70 hover:border-editor-border/90"
              }`}
              title="Toggle Markdown Preview"
            >
              {showMarkdownPreview ? "Preview: On" : "Preview"}
            </button>
          )}
          {(activeFile.language === "python" ||
            activeFile.language === "qasm") && (
            <>
              <button
                onClick={() =>
                  setShowCircuitVisualization(!showCircuitVisualization)
                }
                className={`px-2.5 py-1 text-xs rounded-md border transition-all duration-200 ${
                  showCircuitVisualization
                    ? "bg-quantum-blue-light/20 border-quantum-blue-light/50 text-quantum-blue-light shadow-[0_0_0_1px_rgba(99,102,241,0.2)]"
                    : "bg-editor-bg border-editor-border text-editor-text hover:bg-editor-border/70 hover:border-editor-border/90"
                }`}
                title="Toggle Circuit View"
              >
                Circuit
              </button>

              {showCircuitVisualization && (
                <>
                  <div className="flex items-center bg-editor-bg border border-editor-border rounded-md p-0.5 shadow-sm">
                    <button
                      onClick={() => setIs3DMode(false)}
                      className={`px-2 py-1 text-[11px] rounded transition-colors ${is3DMode ? "text-editor-text hover:bg-editor-border/70 hover:bg-editor-bg/10" : "bg-editor-accent text-white shadow-sm"}`}
                    >
                      2D
                    </button>
                    <button
                      onClick={() => setIs3DMode(true)}
                      className={`px-2 py-1 text-[11px] rounded transition-colors ${is3DMode ? "bg-editor-accent text-white shadow-sm" : "text-editor-text hover:bg-editor-border/70 hover:bg-editor-bg/10"}`}
                    >
                      3D
                    </button>
                  </div>
                  {!is3DMode && (
                    <button
                      onClick={() => window.dispatchEvent(new CustomEvent('download-circuit-svg'))}
                      className="px-2 py-1.5 text-[11px] bg-editor-bg border border-editor-border rounded-md text-editor-text hover:bg-editor-border/70 hover:text-quantum-blue-light shadow-sm transition-colors flex items-center gap-1.5"
                      title="Download Circuit Diagram"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                        <polyline points="7 10 12 15 17 10"></polyline>
                        <line x1="12" y1="15" x2="12" y2="3"></line>
                      </svg>
                      SVG
                    </button>
                  )}
                </>
              )}
            </>
          )}
        </div>

        <div className="relative z-50" ref={runMenuRef}>
          <div className="flex items-stretch rounded-lg border border-editor-border/80 overflow-hidden bg-editor-bg shadow-[0_4px_16px_rgba(0,0,0,0.22)]">
            <button
              type="button"
              onClick={() => onRun()}
              disabled={!activeFile || isRunning}
              className="px-3 py-1.5 text-xs font-semibold bg-gradient-to-r from-quantum-blue-light/20 to-quantum-blue-light/10 text-editor-text hover:from-quantum-blue-light/30 hover:to-quantum-blue-light/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5 transition-all duration-200"
              title={
                executionMode === "expert"
                  ? "Run (Expert mode)"
                  : "Run (Basic mode)"
              }
            >
              <Play className="w-3.5 h-3.5 text-quantum-blue-light" />
              <span>{executionMode === "expert" ? "Run Expert" : "Run"}</span>
            </button>
            <button
              type="button"
              onClick={() => setShowRunMenu((prev) => !prev)}
              className="px-2 py-1.5 bg-editor-bg text-editor-text hover:bg-editor-border/70 border-l border-editor-border/80 transition-colors"
              aria-label="Run options"
              title="Run options"
            >
              <ChevronDown
                className={`w-3.5 h-3.5 transition-transform ${showRunMenu ? "rotate-180" : ""}`}
              />
            </button>
          </div>

          {showRunMenu && (
            <div className="absolute bg-editor-bg right-0 top-11 z-[120] w-80 rounded-xl border border-editor-border/80 bg-gradient-to-b shadow-[0_20px_45px_rgba(0,0,0,0.45)] p-3.5 space-y-3 backdrop-blur-md">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <div className="text-[11px] uppercase tracking-wide text-black dark:text-gray-400">
                    Execution Mode
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full bg-editor-bg border border-editor-border text-black dark:text-gray-400 capitalize">
                    {executionMode}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {(["basic", "expert"] as const).map((m) => (
                    <button
                      key={m}
                      type="button"
                      onClick={() => setExecutionMode(m)}
                      className={`px-2.5 py-2 text-xs rounded-md border capitalize transition-all duration-200 ${
                        executionMode === m
                          ? "bg-editor-accent border-editor-accent text-gray-100 shadow-[0_0_18px_rgba(99,102,241,0.25)]"
                          : "bg-editor-bg border-editor-border text-editor-text hover:bg-editor-border/70"
                      }`}
                    >
                      {m}
                    </button>
                  ))}
                </div>
              </div>

              {executionMode === "basic" ? (
                <>
                  <div>
                    <label className="text-[11px] uppercase tracking-wide text-black dark:text-gray-400 block mb-1">
                      Input Framework
                    </label>
                    <select
                      value={inputLanguage}
                      onChange={(e) =>
                        setInputLanguage(e.target.value as InputLanguage | "")
                      }
                      className="w-full bg-editor-bg/95 border border-editor-border rounded-md px-2.5 py-2 text-xs text-editor-text focus:outline-none focus:ring-1 focus:ring-quantum-blue-light/60"
                    >
                      <option value="">Auto Detect</option>
                      <option value="qasm">OpenQASM</option>
                      <option value="qiskit">Qiskit</option>
                      <option value="cirq">Cirq</option>
                      <option value="pennylane">PennyLane</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] uppercase tracking-wide text-black dark:text-gray-400 block mb-1">
                      Output Backend
                    </label>
                    <select
                      value={simBackend}
                      onChange={(e) =>
                        setSimBackend(e.target.value as SimulationBackend)
                      }
                      className="w-full bg-editor-bg/95 border border-editor-border rounded-md px-2.5 py-2 text-xs text-editor-text focus:outline-none focus:ring-1 focus:ring-quantum-blue-light/60"
                    >
                      <option value="">Auto Select</option>
                      <option value="qiskit">Qiskit Aer</option>
                      <option value="cirq">Cirq Simulator</option>
                      <option value="pennylane">PennyLane</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[11px] uppercase tracking-wide text-black dark:text-gray-400 block mb-1">
                      Shots
                    </label>
                    <input
                      type="number"
                      min={1}
                      max={100000}
                      step={1}
                      value={shots}
                      onChange={(e) => {
                        const parsed = Number.parseInt(e.target.value, 10);
                        if (!Number.isNaN(parsed)) {
                          setShots(Math.max(1, Math.min(100000, parsed)));
                        }
                      }}
                      className="w-full bg-editor-bg/95 border border-editor-border rounded-md px-2.5 py-2 text-xs text-editor-text focus:outline-none focus:ring-1 focus:ring-quantum-blue-light/60"
                    />
                  </div>
                </>
              ) : (
                <div className="text-xs text-black dark:text-gray-400 bg-editor-bg/10 border border-editor-border rounded-md p-2.5 leading-relaxed">
                  Expert mode runs hybrid Python workflows. Basic simulation
                  settings are not used in this mode.
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Find and Replace */}
      <FindReplace
        isVisible={showFindReplace}
        onClose={() => setShowFindReplace(false)}
        mode={findReplaceMode}
        editorRef={editorRef}
      />

      {/* Circuit Visualization - Resizable */}
      {showCircuitVisualization && activeFile && (
        <>
          <div
            className="bg-editor-bg border-b border-editor-border p-4 overflow-auto"
            style={{ height: `${circuitHeight}px` }}
          >
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-medium text-white">
                Circuit Visualization
              </h4>
              {isParsing && (
                <span className="text-xs text-black dark:text-gray-400 flex items-center">
                  <div className="w-3 h-3 border border-quantum-blue-light border-t-transparent rounded-full animate-spin mr-1"></div>
                  Parsing...
                </span>
              )}
            </div>
            {is3DMode ? (
              <CircuitVisualization3D
                gates={parsedGates}
                qubits={parsedQubits}
                className="h-full"
              />
            ) : (
              <CircuitVisualization
                gates={parsedGates}
                qubits={parsedQubits}
                className="h-full"
              />
            )}
          </div>
          {/* Drag Handle for Circuit Visualization */}
          <div
            role="separator"
            aria-orientation="horizontal"
            aria-label="Resize circuit visualization"
            tabIndex={0}
            className={`h-1 bg-editor-border hover:bg-quantum-blue-light cursor-row-resize transition-colors ${isDraggingCircuit ? "bg-quantum-blue-light" : ""}`}
            onMouseDown={handleCircuitDragStart}
            onKeyDown={(e) => {
              if (e.key === "ArrowUp")
                setCircuitHeight((h) => Math.max(100, h - 20));
              if (e.key === "ArrowDown")
                setCircuitHeight((h) => Math.min(500, h + 20));
            }}
            title="Drag to resize circuit view"
          />
        </>
      )}

      {/* Monaco Editor - only render when mounted on client */}
      <div className="flex-1 overflow-hidden">
        {activeFile.name.toLowerCase().endsWith(".md") &&
        showMarkdownPreview ? (
          <MarkdownPreview markdown={activeFile.content} />
        ) : isMounted ? (
          <Editor
            key={activeFile.id}
            height="100%"
            path={activeFile.id}
            language={getMonacoLanguage(activeFile.language)}
            theme={theme === "light" ? "quantum-light" : "quantum-dark"}
            value={activeFile.content}
            onChange={handleEditorChange}
            onMount={handleEditorDidMount}
            options={{
              fixedOverflowWidgets: true,
              fontSize: 14,
              fontFamily:
                "JetBrains Mono, Fira Code, Monaco, Consolas, monospace",
              lineNumbers: "on",
              rulers: [],
              wordWrap: "on",
              minimap: {
                enabled: true,
                maxColumn: 120,
              },
              scrollBeyondLastLine: false,
              automaticLayout: true,
              tabSize: 4,
              insertSpaces: true,
              detectIndentation: true,
              renderWhitespace: "selection",
              renderControlCharacters: false,
              cursorBlinking: "smooth",
              cursorSmoothCaretAnimation: "on",
              smoothScrolling: true,
              mouseWheelZoom: true,
              contextmenu: true,
              quickSuggestions: true,
              suggestOnTriggerCharacters: true,
              acceptSuggestionOnEnter: "on",
              snippetSuggestions: "top",
              wordBasedSuggestions: "off",
              bracketPairColorization: {
                enabled: true,
              },
              guides: {
                bracketPairs: true,
                indentation: true,
              },
              padding: {
                top: 16,
                bottom: 16,
              },
            }}
          />
        ) : (
          <div className="flex items-center justify-center h-full bg-editor-bg">
            <div className="flex items-center space-x-2">
              <div className="w-6 h-6 border-2 border-quantum-blue-light border-t-transparent rounded-full spinner"></div>
              <span className="text-editor-text">Loading editor...</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// Memoised: the IDE page re-renders for layout state (drag/resize, auth, etc.);
// EditorPane's props are stable, so it only re-renders for its own store slices.
export default memo(EditorPane);


/** Shown when no file is open: point people straight at something runnable. */
function EmptyEditor() {
  const [busy, setBusy] = useState(false);

  const startBell = async () => {
    if (busy) return;
    const bell = FILE_TEMPLATES_PRESETS.find((t) => t.filename === "bell_state_qiskit.py");
    if (!bell) return;
    setBusy(true);
    try {
      const { activeProjectId, createFile } = useFileStore.getState();
      await createFile(bell.filename, bell.content, activeProjectId ?? undefined, false);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="editor-pane">
      <div className="flex flex-1 items-center justify-center bg-editor-bg px-6">
        <div className="qc-fade-in max-w-sm text-center">
          <span className="qc-brand-mark mx-auto mb-5 block h-12 w-12 opacity-90" aria-hidden="true" />
          <h3 className="text-lg font-semibold text-white">Start a circuit</h3>
          <p className="mt-2 text-sm leading-relaxed text-editor-text">
            Open a file from the explorer, or start from a program that runs as-is.
          </p>
          <div className="mt-6 flex flex-col items-center justify-center gap-2 sm:flex-row">
            <button
              type="button"
              onClick={() => void startBell()}
              disabled={busy}
              className="inline-flex h-9 items-center justify-center rounded-lg bg-indigo-600 px-4 text-sm font-medium text-white transition-[background-color,transform] duration-150 hover:bg-indigo-500 active:scale-[0.98] disabled:opacity-60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
            >
              {busy ? "Creating…" : "Qiskit Bell state"}
            </button>
            <button
              type="button"
              onClick={() => window.dispatchEvent(new CustomEvent("qcanvas:open-templates"))}
              className="inline-flex h-9 items-center justify-center rounded-lg border border-editor-border px-4 text-sm text-editor-text transition-[border-color,color,transform] duration-150 hover:border-white/25 hover:text-white active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-indigo-400"
            >
              Browse templates
            </button>
          </div>
          <p className="mt-6 text-xs text-gray-500">
            <kbd className="rounded border border-editor-border px-1.5 py-0.5 font-mono text-[11px]">Alt+N</kbd> new file
            <span className="mx-2" aria-hidden="true">/</span>
            <kbd className="rounded border border-editor-border px-1.5 py-0.5 font-mono text-[11px]">Ctrl+B</kbd> toggle sidebar
          </p>
        </div>
      </div>
    </div>
  );
}
