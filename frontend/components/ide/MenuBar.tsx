"use client";

import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  EDITOR_FLUSH_EVENT,
  useFileStore,
  useHasActiveFile,
} from "@/lib/store";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/authStore";
import ProfileDropdown from "@/components/ProfileDropdown";
import ShareModal from "@/components/ShareModal";
import AddNewLanguage from "@/components/AddNewLanguage";
import { FILE_TEMPLATES_PRESETS } from "@/lib/fileTemplates";
import { Code, FileText } from "@/components/Icons";
import { Check, X } from "lucide-react";

type MenuId =
  | "file"
  | "edit"
  | "selection"
  | "view"
  | "run"
  | "terminal"
  | "help";

interface MenuItem {
  label: string;
  shortcut?: string;
  disabled?: boolean;
  onSelect: () => void;
}

/**
 * "New File" flow shared by the menu item and the keyboard shortcut.
 */
function promptAndCreateFile() {
  const entered = globalThis.window?.prompt("Enter new file name", "new.py");
  const fileName = entered?.trim();
  if (!fileName) return;

  const { token } = useAuthStore.getState();
  const store = useFileStore.getState();
  if (token) {
    void store.createFile(
      fileName,
      undefined,
      store.activeProjectId ?? undefined,
      false,
    );
  } else {
    store.addFile(fileName, undefined);
  }
}

/**
 * Global IDE shortcuts advertised in the menus.
 *
 * Registered on `window` in the bubbling phase, so when Monaco has focus and
 * handles a key itself (e.g. Ctrl+Shift+K = delete line) it stops propagation
 * and the editor keeps that binding. Keys Monaco does not bind (Ctrl+B, Ctrl+J,
 * Ctrl+Shift+R, Alt+N) bubble up and work from inside the editor too.
 */
function useIdeShortcuts(onRun: () => void | Promise<void>) {
  const onRunRef = useRef(onRun);
  useEffect(() => {
    onRunRef.current = onRun;
  }, [onRun]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.isComposing) return;
      const mod = e.ctrlKey || e.metaKey;
      const key = (e.key ?? "").toLowerCase();

      // New file: Ctrl/Cmd+N is reserved by most browsers (opens a window and
      // never reaches the page), so Alt+N is the reliable binding.
      if (
        (e.altKey && !mod && !e.shiftKey && (key === "n" || e.code === "KeyN")) ||
        (mod && !e.shiftKey && !e.altKey && key === "n")
      ) {
        e.preventDefault();
        promptAndCreateFile();
        return;
      }

      if (!mod || e.altKey) return;

      if (!e.shiftKey && key === "b") {
        e.preventDefault();
        useFileStore.getState().toggleSidebar();
      } else if (!e.shiftKey && key === "j") {
        e.preventDefault();
        useFileStore.getState().toggleResults();
      } else if (e.shiftKey && key === "k") {
        e.preventDefault();
        useFileStore.getState().toggleTheme();
      } else if (e.shiftKey && key === "r") {
        e.preventDefault();
        void onRunRef.current();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);
}

function MenuBar({
  onRun,
  onAskAiAboutCircuit,
}: Readonly<{
  onRun: () => void | Promise<void>;
  onAskAiAboutCircuit?: () => void;
}>) {
  // Narrow subscriptions: MenuBar used to subscribe to the whole store (and to
  // the active file object), so it re-rendered on every editor update.
  const toggleSidebar = useFileStore((s) => s.toggleSidebar);
  const toggleResults = useFileStore((s) => s.toggleResults);
  const theme = useFileStore((s) => s.theme);
  const toggleTheme = useFileStore((s) => s.toggleTheme);
  const setExecutionMode = useFileStore((s) => s.setExecutionMode);
  const executionMode = useFileStore((s) => s.executionMode);
  const activeProjectId = useFileStore((s) => s.activeProjectId);
  const hasActiveFile = useHasActiveFile();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const clearAuth = useAuthStore((s) => s.clearAuth);
  const token = useAuthStore((s) => s.token);
  const router = useRouter();

  useIdeShortcuts(onRun);

  const [openMenu, setOpenMenu] = useState<MenuId | null>(null);
  const [showShareModal, setShowShareModal] = useState(false);
  // Only track the active file's content while the share dialog is open.
  const shareFile = useFileStore((s) =>
    showShareModal ? s.getActiveFile() : undefined,
  );
  const [showShortcuts, setShowShortcuts] = useState(false);
  const [showTemplatesPicker, setShowTemplatesPicker] = useState(false);
  const [showAddLanguage, setShowAddLanguage] = useState(false);
  const [showNewProjectModal, setShowNewProjectModal] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const barRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (!barRef.current) return;
      if (!barRef.current.contains(e.target as Node)) setOpenMenu(null);
    };
    document.addEventListener("mousedown", onDocClick);
    return () => document.removeEventListener("mousedown", onDocClick);
  }, []);

  const handleExport = useCallback(() => {
    // Flush debounced editor content so the export has the latest text.
    globalThis.window?.dispatchEvent(new Event(EDITOR_FLUSH_EVENT));
    const activeFile = useFileStore.getState().getActiveFile();
    if (!activeFile) return;
    const blob = new Blob([activeFile.content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = activeFile.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }, []);

  const handleLogout = () => {
    clearAuth();
    router.push("/login");
  };

  const menus = useMemo<Record<MenuId, MenuItem[]>>(
    () => ({
      file: [
        {
          label: "New File",
          shortcut: "Alt+N",
          onSelect: promptAndCreateFile,
        },
        {
          label: "New Project…",
          onSelect: () => {
            setNewProjectName("");
            setShowNewProjectModal(true);
          },
        },
        {
          label: "Templates…",
          onSelect: () => setShowTemplatesPicker(true),
        },
        {
          label: "Save",
          shortcut: "Ctrl/Cmd+S",
          disabled: !hasActiveFile,
          onSelect: () =>
            globalThis.window?.dispatchEvent(new CustomEvent("save-file")),
        },
        {
          label: "Export",
          disabled: !hasActiveFile,
          onSelect: handleExport,
        },
        {
          label: "Share",
          disabled: !hasActiveFile,
          onSelect: () => {
            globalThis.window?.dispatchEvent(new Event(EDITOR_FLUSH_EVENT));
            setShowShareModal(true);
          },
        },
      ],
      edit: [
        {
          label: "Find",
          shortcut: "Ctrl/Cmd+F",
          disabled: !hasActiveFile,
          onSelect: () =>
            globalThis.window?.dispatchEvent(
              new CustomEvent("open-find", { detail: { mode: "find" } }),
            ),
        },
        {
          label: "Replace",
          shortcut: "Ctrl/Cmd+H",
          disabled: !hasActiveFile,
          onSelect: () =>
            globalThis.window?.dispatchEvent(
              new CustomEvent("open-find", { detail: { mode: "replace" } }),
            ),
        },
        {
          label: "Keyboard Shortcuts",
          onSelect: () => setShowShortcuts(true),
        },
      ],
      selection: [
        {
          label: "Select All",
          shortcut: "Ctrl/Cmd+A",
          disabled: !hasActiveFile,
          onSelect: () =>
            globalThis.window?.dispatchEvent(new Event("editor-select-all")),
        },
      ],
      view: [
        {
          label: "Toggle Sidebar",
          shortcut: "Ctrl/Cmd+B",
          onSelect: toggleSidebar,
        },
        {
          label: `Theme: ${theme === "dark" ? "Dark" : "Light"}`,
          shortcut: "Ctrl/Cmd+Shift+K",
          onSelect: toggleTheme,
        },
      ],
      run: [
        {
          label: "Mode: Basic",
          disabled: executionMode === "basic",
          onSelect: () => setExecutionMode("basic"),
        },
        {
          label: "Mode: Expert",
          disabled: executionMode === "expert",
          onSelect: () => setExecutionMode("expert"),
        },
        {
          label: "Run",
          shortcut: "Ctrl/Cmd+Shift+R",
          disabled: !hasActiveFile,
          onSelect: () => onRun(),
        },
      ],
      terminal: [
        {
          label: "Toggle Results Pane",
          shortcut: "Ctrl/Cmd+J",
          onSelect: toggleResults,
        },
      ],
      help: [
        {
          label: "Examples",
          onSelect: () => globalThis.window?.open("/examples", "_blank"),
        },
        {
          label: "Documentation",
          onSelect: () => globalThis.window?.open("/docs", "_blank"),
        },
        {
          label: "Ask AI about this circuit",
          disabled: !hasActiveFile || !onAskAiAboutCircuit,
          onSelect: () => onAskAiAboutCircuit?.(),
        },
        {
          label: "Add New Language…",
          onSelect: () => setShowAddLanguage(true),
        },
      ],
    }),
    [
      hasActiveFile,
      executionMode,
      handleExport,
      onAskAiAboutCircuit,
      onRun,
      setExecutionMode,
      theme,
      toggleResults,
      toggleSidebar,
      toggleTheme,
    ],
  );

  const menuLabels: Array<{ id: MenuId; label: string }> = [
    { id: "file", label: "File" },
    { id: "edit", label: "Edit" },
    { id: "selection", label: "Selection" },
    { id: "view", label: "View" },
    { id: "run", label: "Run" },
    { id: "terminal", label: "Terminal" },
    { id: "help", label: "Help" },
  ];

  const getTemplateMeta = (
    template: (typeof FILE_TEMPLATES_PRESETS)[number],
  ) => {
    const filename = template.filename.toLowerCase();
    const name = template.name.toLowerCase();

    if (name.includes("qiskit") || filename.includes("qiskit")) {
      return {
        language: "python",
        icon: <Code className="w-4 h-4 text-blue-400" />,
      };
    }
    if (name.includes("cirq") || filename.includes("cirq")) {
      return {
        language: "python",
        icon: <Code className="w-4 h-4 text-purple-400" />,
      };
    }
    if (name.includes("pennylane") || filename.includes("pennylane")) {
      return {
        language: "python",
        icon: <Code className="w-4 h-4 text-green-400" />,
      };
    }

    return {
      language: filename.endsWith(".py") ? "python" : "template",
      icon: <FileText className="w-4 h-4 text-editor-text" />,
    };
  };

  return (
    <>
      <div
        ref={barRef}
        className="h-12 bg-editor-sidebar flex items-center px-3 select-none"
      >
        <Link href="/" className="flex items-center gap-2 pr-3">
          <div className="flex items-center justify-center w-6 h-6">
            <Image
              src="/QCanvas-logo-Black.svg"
              alt="QCanvas"
              width={24}
              height={24}
              className="object-contain block dark:hidden"
              priority
            />
            <Image
              src="/QCanvas-logo-White.svg"
              alt="QCanvas"
              width={24}
              height={24}
              className="object-contain hidden dark:block"
              priority
            />
          </div>
          <span className="text-lg font-bold quantum-gradient bg-clip-text text-transparent hidden sm:block">
            QCanvas
          </span>
        </Link>

        <div className="flex items-center gap-1">
          {menuLabels.map((m) => (
            <div key={m.id} className="relative">
              <button
                type="button"
                className={`px-2 py-1 text-xs rounded-md transition-colors ${openMenu === m.id ? "bg-editor-bg/10 text-white" : "text-editor-text hover:bg-editor-panelHigh/10 hover:text-white"}`}
                onClick={() =>
                  setOpenMenu((cur) => (cur === m.id ? null : m.id))
                }
                onMouseEnter={() => {
                  if (openMenu) setOpenMenu(m.id);
                }}
              >
                {m.label}
              </button>

              {openMenu === m.id && (
                <div className="absolute left-0 top-full mt-1.5 w-56 bg-editor-bg border border-editor-border rounded-md z-50 overflow-hidden">
                  {menus[m.id].map((item, idx) => (
                    <button
                      key={`${m.id}-${idx}`}
                      type="button"
                      disabled={item.disabled}
                      className={`w-full flex items-center justify-between px-3 py-2 text-xs text-left ${
                        item.disabled
                          ? "opacity-50 cursor-not-allowed text-editor-text"
                          : "text-editor-text hover:border hover:rounded-md hover:bg-editor-panelHigh/10 hover:text-white"
                      }`}
                      onClick={() => {
                        item.onSelect();
                        setOpenMenu(null);
                      }}
                    >
                      <span>{item.label}</span>
                      {item.shortcut && (
                        <span className="text-[10px] text-black dark:text-gray-400">
                          {item.shortcut}
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            className="text-xs text-editor-text hover:text-white px-2 py-1 rounded-md hover:bg-editor-bg/10 hidden sm:inline-flex"
            onClick={() => setShowTemplatesPicker(true)}
          >
            Templates
          </button>
          {/* <div className="text-[11px] text-black dark:text-gray-400 hidden md:block">
            {activeFile ? activeFile.name : "No file selected"}
          </div> */}
          {isAuthenticated ? (
            <ProfileDropdown onLogout={handleLogout} />
          ) : (
            <Link
              href="/login"
              className="text-xs text-editor-text hover:text-white px-2 py-1 rounded-md hover:bg-editor-panelHigh"
            >
              Login
            </Link>
          )}
        </div>
      </div>

      <ShareModal
        isOpen={showShareModal}
        onClose={() => setShowShareModal(false)}
        fileId={shareFile?.id}
        fileContent={shareFile?.content || ""}
        fileName={shareFile?.name || ""}
      />

      {showNewProjectModal && (
        <>
          <button
            type="button"
            className="fixed inset-0 bg-black/50 z-[55] cursor-default"
            onClick={() => setShowNewProjectModal(false)}
            aria-label="Close create project"
          />
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
            <div className="quantum-glass-dark rounded-2xl p-6 max-w-md w-full border border-editor-border shadow-[0_24px_48px_rgba(0,0,0,0.5)]">
              <div className="flex items-center justify-between">
                <div className="text-lg font-bold text-white">
                  Create new project
                </div>
                <button
                  type="button"
                  className="btn-ghost p-1 hover:bg-editor-border rounded-lg"
                  onClick={() => setShowNewProjectModal(false)}
                  aria-label="Close"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="mt-2 text-sm text-editor-text">
                Projects keep files organized and switchable.
              </div>

              <div className="mt-4">
                <label
                  htmlFor="menubar-new-project-name"
                  className="text-[10px] uppercase tracking-[0.22em] text-editor-text/60"
                >
                  Project name
                </label>
                <input
                  id="menubar-new-project-name"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") setShowNewProjectModal(false);
                    if (e.key === "Enter") {
                      const name = newProjectName.trim();
                      if (!name) return;
                      if (!token) return;
                      void useFileStore
                        .getState()
                        .createProject(name, false, token);
                      setShowNewProjectModal(false);
                    }
                  }}
                  placeholder="e.g. Bell States"
                  className="mt-2 w-full bg-editor-bg border border-editor-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-editor-text/40 focus:outline-none focus:ring-1 focus:ring-emerald-400/40"
                  autoFocus
                />
                {!token && (
                  <div className="mt-2 text-xs text-amber-300">
                    You must be logged in to create projects.
                  </div>
                )}
              </div>

              <div className="mt-5 flex items-center justify-end gap-2">
                <button
                  type="button"
                  className="px-3 py-2 rounded-md text-sm text-editor-text hover:bg-editor-border/60"
                  onClick={() => setShowNewProjectModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  disabled={!token || !newProjectName.trim()}
                  className="px-3 py-2 rounded-md text-sm font-semibold bg-emerald-400/80 hover:bg-emerald-400 text-slate-950 disabled:opacity-50 disabled:cursor-not-allowed inline-flex items-center gap-2"
                  onClick={() => {
                    const name = newProjectName.trim();
                    if (!name || !token) return;
                    void useFileStore
                      .getState()
                      .createProject(name, false, token);
                    setShowNewProjectModal(false);
                  }}
                >
                  <Check className="w-4 h-4" />
                  Create project
                </button>
              </div>
            </div>
          </div>
        </>
      )}

      <AddNewLanguage
        isOpen={showAddLanguage}
        onClose={() => setShowAddLanguage(false)}
      />

      {showTemplatesPicker && (
        <>
          <button
            type="button"
            className="fixed inset-0 bg-black/50 z-[55] cursor-default"
            onClick={() => setShowTemplatesPicker(false)}
            aria-label="Close templates picker"
          />
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
            <div className="quantum-glass-dark rounded-2xl p-6 max-w-3xl w-full border border-editor-border shadow-[0_24px_48px_rgba(0,0,0,0.5)] max-h-[80vh] overflow-hidden">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-white">File Templates</h3>
                <button
                  type="button"
                  className="btn-ghost p-1 hover:bg-editor-border"
                  onClick={() => setShowTemplatesPicker(false)}
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>

              <div className="mb-4 flex items-center justify-between rounded-lg border border-editor-border bg-editor-bg/10 px-3 py-2">
                <p className="text-xs text-editor-text">
                  Start quickly with ready-made templates.
                </p>
                <button
                  type="button"
                  className="text-xs text-quantum-blue-light hover:underline"
                  onClick={() => {
                    setShowTemplatesPicker(false);
                    router.push("/examples");
                  }}
                >
                  View more example templates
                </button>
              </div>

              <div className="overflow-y-auto max-h-[65vh] pr-1 grid md:grid-cols-2 gap-4">
                {FILE_TEMPLATES_PRESETS.map((t) => (
                  <button
                    key={t.filename}
                    type="button"
                    className="quantum-glass-dark rounded-lg p-4 border border-editor-border hover:border-framework-qiskit/60 transition-all duration-200 cursor-pointer"
                    onClick={async () => {
                      setOpenMenu(null);
                      await useFileStore
                        .getState()
                        .createFile(
                          t.filename,
                          t.content,
                          activeProjectId ?? undefined,
                          false,
                        );
                      setShowTemplatesPicker(false);
                    }}
                  >
                    <div className="flex items-center space-x-3 mb-2">
                      {getTemplateMeta(t).icon}
                      <h4 className="font-medium text-white">{t.name}</h4>
                    </div>
                    <p className="text-sm text-editor-text mb-3">
                      {t.description}
                    </p>
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-black dark:text-gray-400">
                        {getTemplateMeta(t).language}
                      </span>
                      <button
                        type="button"
                        className="text-xs text-quantum-blue-light hover:underline"
                        onClick={(e) => {
                          e.stopPropagation();
                          void useFileStore
                            .getState()
                            .createFile(
                              t.filename,
                              t.content,
                              activeProjectId ?? undefined,
                              false,
                            )
                            .then(() => setShowTemplatesPicker(false));
                        }}
                      >
                        Use Template
                      </button>
                    </div>
                    <div className="text-[11px] text-black dark:text-gray-500 mt-1 font-mono">
                      {t.filename}
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        </>
      )}

      {showShortcuts && (
        <>
          <button
            type="button"
            className="fixed inset-0 bg-black/50 z-[55] cursor-default"
            onClick={() => setShowShortcuts(false)}
            aria-label="Close keyboard shortcuts"
          />
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-4">
            <div className="quantum-glass-dark rounded-2xl p-6 max-w-md w-full border border-editor-border shadow-[0_24px_48px_rgba(0,0,0,0.5)]">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-white">
                  Keyboard Shortcuts
                </h3>
                <button
                  type="button"
                  className="btn-ghost p-1 hover:bg-editor-border"
                  onClick={() => setShowShortcuts(false)}
                  aria-label="Close"
                >
                  ✕
                </button>
              </div>
              <div className="space-y-2 text-sm text-editor-text">
                <div className="flex justify-between">
                  <span>Save</span>
                  <kbd className="px-2 py-1 bg-editor-bg border border-editor-border rounded text-xs">
                    Ctrl/Cmd+S
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span>Find</span>
                  <kbd className="px-2 py-1 bg-editor-bg border border-editor-border rounded text-xs">
                    Ctrl/Cmd+F
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span>Replace</span>
                  <kbd className="px-2 py-1 bg-editor-bg border border-editor-border rounded text-xs">
                    Ctrl/Cmd+H
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span>New File</span>
                  <kbd className="px-2 py-1 bg-editor-bg border border-editor-border rounded text-xs">
                    Alt+N
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span>Toggle Sidebar</span>
                  <kbd className="px-2 py-1 bg-editor-bg border border-editor-border rounded text-xs">
                    Ctrl/Cmd+B
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span>Toggle Theme</span>
                  <kbd className="px-2 py-1 bg-editor-bg border border-editor-border rounded text-xs">
                    Ctrl/Cmd+Shift+K
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span>Run</span>
                  <kbd className="px-2 py-1 bg-editor-bg border border-editor-border rounded text-xs">
                    Ctrl/Cmd+Shift+R
                  </kbd>
                </div>
                <div className="flex justify-between">
                  <span>Toggle Results</span>
                  <kbd className="px-2 py-1 bg-editor-bg border border-editor-border rounded text-xs">
                    Ctrl/Cmd+J
                  </kbd>
                </div>
              </div>
            </div>
          </div>
        </>
      )}
    </>
  );
}

export default memo(MenuBar);
