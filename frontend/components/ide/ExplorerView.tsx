"use client";

import { memo, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  ChevronRight,
  ChevronDown,
  File as FileIcon,
  Folder as FolderIcon,
  FolderPlus,
  Plus,
  Trash2,
  Check,
  X,
  Edit2,
} from "lucide-react";
import { useFileListMeta, useFileStore } from "@/lib/store";
import { useAuthStore } from "@/lib/authStore";
import { Code, FileText } from "@/components/Icons";
import { Folder, File } from "@/types";

type TreeNode =
  | { kind: "folder"; folder: Folder; children: TreeNode[]; depth: number }
  | { kind: "file"; file: File; depth: number };

function getFileAccentClasses(fileName: string): { icon: string; dot: string } {
  const ext = fileName.split(".").pop()?.toLowerCase() ?? "";

  if (ext === "py")
    return { icon: "text-framework-qiskit", dot: "bg-framework-qiskit" };
  if (ext === "qasm")
    return { icon: "text-framework-cirq", dot: "bg-framework-cirq" };
  if (ext === "md") return { icon: "text-sky-300", dot: "bg-sky-400" };
  if (ext === "json")
    return { icon: "text-emerald-300", dot: "bg-emerald-400" };
  if (ext === "ts" || ext === "tsx")
    return { icon: "text-framework-qiskit", dot: "bg-framework-qiskit" };
  if (ext === "js" || ext === "jsx")
    return { icon: "text-framework-pennylane", dot: "bg-framework-pennylane" };

  return { icon: "text-editor-text", dot: "bg-editor-text" };
}

function getFileTypeIcon(file: File, isActive: boolean, accentClass: string) {
  const iconClass = `w-4 h-4 ${isActive ? "text-white" : accentClass}`;
  const language = file.language?.toLowerCase();

  if (language === "python" || file.name.endsWith(".py"))
    return <Code className={iconClass} />;
  if (language === "qasm" || file.name.endsWith(".qasm"))
    return <FileIcon className={iconClass} />;
  if (
    language === "javascript" ||
    language === "typescript" ||
    file.name.endsWith(".js") ||
    file.name.endsWith(".jsx") ||
    file.name.endsWith(".ts") ||
    file.name.endsWith(".tsx")
  ) {
    return <Code className={iconClass} />;
  }
  if (language === "json" || file.name.endsWith(".json"))
    return <FileText className={iconClass} />;
  if (file.name.endsWith(".md")) return <FileText className={iconClass} />;

  return <FileIcon className={iconClass} />;
}

function buildTree(folders: Folder[], files: File[]): TreeNode[] {
  const byParent = new Map<string | null, Folder[]>();
  for (const f of folders) {
    const key = f.parentId ?? null;
    const list = byParent.get(key) ?? [];
    list.push(f);
    byParent.set(key, list);
  }
  Array.from(byParent.values()).forEach((list) => {
    list.sort((a, b) => a.name.localeCompare(b.name));
  });

  const filesByFolder = new Map<string | null, File[]>();
  for (const file of files) {
    const key = file.folderId ?? null;
    const list = filesByFolder.get(key) ?? [];
    list.push(file);
    filesByFolder.set(key, list);
  }
  Array.from(filesByFolder.values()).forEach((list) => {
    list.sort((a, b) => a.name.localeCompare(b.name));
  });

  const walk = (parentId: string | null, depth: number): TreeNode[] => {
    const nodes: TreeNode[] = [];

    const childFolders = byParent.get(parentId) ?? [];
    for (const folder of childFolders) {
      nodes.push({
        kind: "folder",
        folder,
        children: walk(folder.id, depth + 1),
        depth,
      });
    }

    const childFiles = filesByFolder.get(parentId) ?? [];
    for (const file of childFiles) {
      nodes.push({ kind: "file", file, depth });
    }

    return nodes;
  };

  return walk(null, 0);
}

// "New file" requests from the menu bar / Alt+N. The explorer may not be
// mounted yet (sidebar closed or another view showing), so the request is
// remembered until it mounts.
let pendingNewFileRequest = false;
export const NEW_FILE_EVENT = "qcanvas:new-file";
export function requestNewFile() {
  pendingNewFileRequest = true;
  window.dispatchEvent(new Event(NEW_FILE_EVENT));
}

function ExplorerView() {
  const folders = useFileStore((s) => s.folders);
  // Ids/names/folders only: re-rendering (and rebuilding the tree) on every
  // editor content update is unnecessary.
  const files = useFileListMeta();
  const projects = useFileStore((s) => s.projects);
  const activeFileId = useFileStore((s) => s.activeFileId);
  const openFile = useFileStore((s) => s.openFile);
  const createFile = useFileStore((s) => s.createFile);
  const createFolder = useFileStore((s) => s.createFolder);
  const createProject = useFileStore((s) => s.createProject);
  const renameFolder = useFileStore((s) => s.renameFolder);
  const deleteFolder = useFileStore((s) => s.deleteFolder);
  const renameFile = useFileStore((s) => s.renameFile);
  const deleteFile = useFileStore((s) => s.deleteFile);
  const moveFileToFolder = useFileStore((s) => s.moveFileToFolder);
  const fetchExplorerTree = useFileStore((s) => s.fetchExplorerTree);

  const activeProjectId = useFileStore((s) => s.activeProjectId);
  const token = useAuthStore((s) => s.token);

  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [projectMenuOpen, setProjectMenuOpen] = useState(false);
  const [projectMenuPos, setProjectMenuPos] = useState<{
    top: number;
    left: number;
    width: number;
  } | null>(null);
  const [showNewFileInput, setShowNewFileInput] = useState(false);
  const [newFileName, setNewFileName] = useState("new.py");
  const [showNewProjectInput, setShowNewProjectInput] = useState(false);
  const [newProjectName, setNewProjectName] = useState("");
  const [showNewFolderInput, setShowNewFolderInput] = useState(false);
  const [newFolderName, setNewFolderName] = useState("New Folder");
  const [selectedFolderId, setSelectedFolderId] = useState<string | null>(null);
  const [editingFileId, setEditingFileId] = useState<string | null>(null);
  const [editingFileName, setEditingFileName] = useState("");
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null);
  const [editingFolderName, setEditingFolderName] = useState("");
  const [contextMenu, setContextMenu] = useState<
    | { type: "file"; id: string; name: string; x: number; y: number }
    | { type: "folder"; id: string; name: string; x: number; y: number }
    | null
  >(null);
  const [deleteFolderConfirm, setDeleteFolderConfirm] = useState<{
    folderId: string;
    folderName: string;
    fileCount: number;
  } | null>(null);
  const [dragOverFolderId, setDragOverFolderId] = useState<string | null>(null);
  const projectMenuRef = useRef<HTMLDivElement>(null);
  const projectMenuButtonRef = useRef<HTMLButtonElement>(null);

  const tree = useMemo(() => buildTree(folders, files), [folders, files]);
  const explorerStats = useMemo(
    () => ({
      files: files.length,
      folders: folders.length,
    }),
    [files.length, folders.length],
  );

  const toggleFolder = (folderId: string) => {
    setExpanded((p) => ({ ...p, [folderId]: !(p[folderId] ?? true) }));
  };

  useEffect(() => {
    if (!contextMenu) return;
    const onDocClick = () => setContextMenu(null);
    document.addEventListener("click", onDocClick);
    return () => document.removeEventListener("click", onDocClick);
  }, [contextMenu]);

  useEffect(() => {
    if (!projectMenuOpen) return;
    const updatePos = () => {
      const btn = projectMenuButtonRef.current;
      if (!btn) return;
      const r = btn.getBoundingClientRect();
      setProjectMenuPos({
        top: r.bottom + 6,
        left: Math.max(8, r.right - 240),
        width: Math.min(260, Math.max(200, r.width)),
      });
    };
    updatePos();

    const onResize = () => updatePos();
    const onScroll = () => updatePos();
    window.addEventListener("resize", onResize);
    window.addEventListener("scroll", onScroll, true);
    return () => {
      window.removeEventListener("resize", onResize);
      window.removeEventListener("scroll", onScroll, true);
    };
  }, [projectMenuOpen]);

  const startCreateFile = (folderId?: string) => {
    setContextMenu(null);
    setShowNewFileInput(true);
    setNewFileName("new.py");
    if (folderId !== undefined) {
      setSelectedFolderId(folderId);
      setExpanded((p) => ({ ...p, [folderId]: true }));
    }
  };

  const startCreateFileRef = useRef(startCreateFile);
  startCreateFileRef.current = startCreateFile;
  useEffect(() => {
    const consume = () => {
      if (!pendingNewFileRequest) return;
      pendingNewFileRequest = false;
      startCreateFileRef.current();
    };
    consume();
    window.addEventListener(NEW_FILE_EVENT, consume);
    return () => window.removeEventListener(NEW_FILE_EVENT, consume);
  }, []);

  const startCreateProject = () => {
    setShowNewProjectInput(true);
    setNewProjectName("");
  };

  const submitCreateProject = async () => {
    const projectName = newProjectName.trim();
    if (!projectName || !token) return;

    try {
      await createProject(projectName, false, token);
      setShowNewProjectInput(false);
      setNewProjectName("");
      setSelectedFolderId(null);
    } catch {
      // Toast handling lives in the store.
    }
  };

  const cancelCreateProject = () => {
    setShowNewProjectInput(false);
    setNewProjectName("");
  };

  const submitCreateFile = async () => {
    const fileName = newFileName.trim();
    if (!fileName) return;

    try {
      await createFile(
        fileName,
        undefined,
        activeProjectId ?? undefined,
        false,
        selectedFolderId ?? undefined,
      );
      setShowNewFileInput(false);
      setNewFileName("new.py");
    } catch {
      // Toast handling lives in the store.
    }
  };

  const cancelCreateFile = () => {
    setShowNewFileInput(false);
    setNewFileName("new.py");
  };

  const startCreateFolder = (parentFolderId?: string) => {
    setShowNewFolderInput(true);
    setNewFolderName("New Folder");
    if (parentFolderId !== undefined) {
      setSelectedFolderId(parentFolderId);
    }
  };

  const submitCreateFolder = async () => {
    const folderName = newFolderName.trim();
    if (!folderName) return;

    try {
      await createFolder(
        folderName,
        activeProjectId ?? undefined,
        selectedFolderId ?? undefined,
      );
      setShowNewFolderInput(false);
      setNewFolderName("New Folder");
    } catch {
      // Toast handling lives in the store.
    }
  };

  const cancelCreateFolder = () => {
    setShowNewFolderInput(false);
    setNewFolderName("New Folder");
  };

  const startRenameFile = (fileId: string, currentName: string) => {
    setEditingFileId(fileId);
    setEditingFileName(currentName);
    setContextMenu(null);
  };

  const submitRenameFile = async (fileId: string, currentName: string) => {
    const nextName = editingFileName.trim();
    if (!nextName || nextName === currentName) {
      setEditingFileId(null);
      return;
    }

    try {
      await renameFile(fileId, nextName);
    } catch {
      // Toast handling lives in the store.
    } finally {
      setEditingFileId(null);
      setEditingFileName("");
    }
  };

  const cancelRenameFile = () => {
    setEditingFileId(null);
    setEditingFileName("");
  };

  const startRenameFolder = (folderId: string, currentName: string) => {
    setEditingFolderId(folderId);
    setEditingFolderName(currentName);
    setContextMenu(null);
  };

  const submitRenameFolder = async (folderId: string, currentName: string) => {
    const nextName = editingFolderName.trim();
    if (!nextName || nextName === currentName) {
      setEditingFolderId(null);
      return;
    }

    try {
      await renameFolder(folderId, nextName);
    } catch {
      // Toast handling lives in the store.
    } finally {
      setEditingFolderId(null);
      setEditingFolderName("");
    }
  };

  const cancelRenameFolder = () => {
    setEditingFolderId(null);
    setEditingFolderName("");
  };

  const activeProjectLabel = useMemo(() => {
    if (!activeProjectId) return "My Files";
    const p = projects.find((x) => x.id === activeProjectId);
    return p?.name ?? "Project";
  }, [activeProjectId, projects]);

  const getFolderDescendants = (rootId: string) => {
    const childrenByParent = new Map<string, string[]>();
    for (const f of folders) {
      if (!f.parentId) continue;
      const list = childrenByParent.get(f.parentId) ?? [];
      list.push(f.id);
      childrenByParent.set(f.parentId, list);
    }
    const result = new Set<string>();
    const stack = [rootId];
    while (stack.length > 0) {
      const cur = stack.pop() as string;
      if (result.has(cur)) continue;
      result.add(cur);
      const kids = childrenByParent.get(cur) ?? [];
      for (const k of kids) stack.push(k);
    }
    return result;
  };

  const countFilesInFolderTree = (folderId: string) => {
    const folderIds = getFolderDescendants(folderId);
    return files.filter((f) => f.folderId && folderIds.has(f.folderId)).length;
  };

  const requestDeleteFolder = (folderId: string, folderName: string) => {
    const fileCount = countFilesInFolderTree(folderId);
    if (fileCount > 0) {
      setDeleteFolderConfirm({ folderId, folderName, fileCount });
      return;
    }
    void deleteFolder(folderId);
  };

  const renderNode = (node: TreeNode, idx: number) => {
    const pad = 8 + node.depth * 12;
    if (node.kind === "folder") {
      const isOpen = expanded[node.folder.id] ?? true;
      return (
        <div key={`folder-${node.folder.id}-${idx}`}>
          <div
            className="group relative"
            style={{ paddingLeft: pad }}
            data-explorer-node="true"
          >
            {editingFolderId === node.folder.id ? (
              <div className="w-full flex items-center gap-2 py-1.5 pr-2 pl-2 text-sm rounded-md border border-editor-border/20 bg-editor-bg shadow-sm">
                <FolderIcon className="w-4 h-4 text-quantum-blue-light" />
                <input
                  value={editingFolderName}
                  onChange={(e) => setEditingFolderName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter")
                      void submitRenameFolder(node.folder.id, node.folder.name);
                    if (e.key === "Escape") cancelRenameFolder();
                  }}
                  className="flex-1 bg-editor-bg border border-editor-border rounded px-2 py-1 text-xs text-editor-text focus-quantum"
                  autoFocus
                />
                <button
                  type="button"
                  className="p-1 rounded hover:bg-green-500/20 text-green-400"
                  title="Confirm rename"
                  onClick={() =>
                    void submitRenameFolder(node.folder.id, node.folder.name)
                  }
                >
                  <Check className="w-3.5 h-3.5" />
                </button>
                <button
                  type="button"
                  className="p-1 rounded hover:bg-red-500/20 text-red-400"
                  title="Cancel rename"
                  onClick={cancelRenameFolder}
                >
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <>
                <button
                  type="button"
                  className={`w-full flex items-center gap-2 py-1.5 pr-12 text-sm rounded-md border transition-all duration-150 ${
                    selectedFolderId === node.folder.id
                      ? "bg-editor-border/45 border-editor-border/90 text-white shadow-sm"
                      : dragOverFolderId === node.folder.id
                        ? "bg-quantum-blue-light/10 border-quantum-blue-light/40 text-white"
                        : "bg-transparent border-transparent text-editor-text hover:bg-editor-border/40 hover:border-editor-border/60"
                  }`}
                  onClick={() => {
                    setSelectedFolderId(node.folder.id);
                    toggleFolder(node.folder.id);
                  }}
                  onDragOver={(e) => {
                    e.preventDefault();
                    setDragOverFolderId(node.folder.id);
                  }}
                  onDragLeave={() => {
                    setDragOverFolderId((cur) =>
                      cur === node.folder.id ? null : cur,
                    );
                  }}
                  onDrop={(e) => {
                    e.preventDefault();
                    const fileId = e.dataTransfer.getData(
                      "text/qcanvas-file-id",
                    );
                    if (!fileId) return;
                    void moveFileToFolder(fileId, node.folder.id);
                    setDragOverFolderId(null);
                    setExpanded((p) => ({ ...p, [node.folder.id]: true }));
                  }}
                  onContextMenu={(e) => {
                    e.preventDefault();
                    setSelectedFolderId(node.folder.id);
                    setContextMenu({
                      type: "folder",
                      id: node.folder.id,
                      name: node.folder.name,
                      x: e.clientX,
                      y: e.clientY,
                    });
                  }}
                  title="Click to expand/collapse"
                >
                  {isOpen ? (
                    <ChevronDown className="w-4 h-4" />
                  ) : (
                    <ChevronRight className="w-4 h-4" />
                  )}
                  <FolderIcon className="w-4 h-4 text-quantum-blue-light" />
                  <span className="truncate">{node.folder.name}</span>
                </button>

                <div className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
                  <button
                    type="button"
                    className="p-1 rounded-md hover:bg-editor-border/70 text-editor-text"
                    title="New file in folder"
                    onClick={(e) => {
                      e.stopPropagation();
                      startCreateFile(node.folder.id);
                    }}
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    className="p-1 rounded-md hover:bg-editor-border/70 text-editor-text"
                    title="New folder in folder"
                    onClick={(e) => {
                      e.stopPropagation();
                      startCreateFolder(node.folder.id);
                      setExpanded((p) => ({ ...p, [node.folder.id]: true }));
                    }}
                  >
                    <FolderPlus className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    className="p-1 rounded-md hover:bg-editor-border/70 text-editor-text"
                    title="Rename folder"
                    onClick={(e) => {
                      e.stopPropagation();
                      startRenameFolder(node.folder.id, node.folder.name);
                    }}
                  >
                    <Edit2 className="w-3.5 h-3.5" />
                  </button>
                  <button
                    type="button"
                    className="p-1 rounded-md hover:bg-editor-border/70 text-editor-text"
                    title="Delete folder"
                    onClick={(e) => {
                      e.stopPropagation();
                      requestDeleteFolder(node.folder.id, node.folder.name);
                    }}
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </>
            )}
          </div>
          {isOpen &&
            node.children.map((child, childIdx) => renderNode(child, childIdx))}
        </div>
      );
    }

    const accent = getFileAccentClasses(node.file.name);

    return (
      <div
        key={`file-${node.file.id}-${idx}`}
        style={{ paddingLeft: pad + 18 }}
        className="group relative"
        data-explorer-node="true"
      >
        {editingFileId === node.file.id ? (
          <div className="w-full flex items-center gap-2 py-1.5 pr-2 text-sm rounded-md border border-editor-border/30 bg-editor-bg shadow-sm">
            {getFileTypeIcon(node.file, false, accent.icon)}
            <input
              value={editingFileName}
              onChange={(e) => setEditingFileName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter")
                  void submitRenameFile(node.file.id, node.file.name);
                if (e.key === "Escape") cancelRenameFile();
              }}
              className="flex-1 bg-editor-bg border border-editor-border rounded px-2 py-1 text-xs text-editor-text focus-quantum"
              autoFocus
            />
            <button
              type="button"
              className="p-1 rounded hover:bg-green-500/20 text-green-400"
              title="Confirm rename"
              onClick={() =>
                void submitRenameFile(node.file.id, node.file.name)
              }
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              className="p-1 rounded hover:bg-red-500/20 text-red-400"
              title="Cancel rename"
              onClick={cancelRenameFile}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <>
            <button
              type="button"
              draggable
              className={`w-full flex items-center gap-2 py-1.5 pr-8 pl-2 text-sm rounded-md border transition-all duration-150 ${
                activeFileId === node.file.id
                  ? "on-fill bg-editor-accent/90 border-editor-accent text-gray-100 shadow-sm"
                  : "text-gray-900 dark:text-gray-100 border-transparent hover:bg-editor-border/40 hover:border-editor-border/60"
              }`}
              onDragStart={(e) => {
                e.dataTransfer.setData("text/qcanvas-file-id", node.file.id);
                e.dataTransfer.effectAllowed = "move";
              }}
              onClick={() => openFile(node.file.id)}
              onDoubleClick={() =>
                startRenameFile(node.file.id, node.file.name)
              }
              onContextMenu={(e) => {
                e.preventDefault();
                setContextMenu({
                  type: "file",
                  id: node.file.id,
                  name: node.file.name,
                  x: e.clientX,
                  y: e.clientY,
                });
              }}
              title="Double click or right-click to rename"
            >
              {getFileTypeIcon(
                node.file,
                activeFileId === node.file.id,
                accent.icon,
              )}
              <span className="truncate">{node.file.name}</span>
            </button>

            <div className="absolute right-1 top-1/2 -translate-y-1/2 opacity-0 group-hover:opacity-100 transition-opacity flex items-center gap-1">
              <button
                type="button"
                className={`p-1 rounded-md hover:bg-editor-border/70 ${
                  activeFileId === node.file.id
                    ? "on-fill bg-editor-accent/90 border-editor-accent text-gray-100 shadow-sm"
                    : "text-gray-900 dark:text-gray-200 border-transparent hover:bg-editor-border/40 hover:border-editor-border/60"
                }`}
                title="Rename file"
                onClick={(e) => {
                  e.stopPropagation();
                  startRenameFile(node.file.id, node.file.name);
                }}
              >
                <Edit2 className="w-3.5 h-3.5" />
              </button>
              <button
                type="button"
                // className="p-1 rounded-md hover:bg-editor-border/70 dark:text-red-600
                // "
                className={`p-1 rounded-md hover:bg-editor-border/70 ${
                  activeFileId === node.file.id
                    ? "on-fill bg-editor-accent/90 border-editor-accent text-gray-100 shadow-sm"
                    : "text-gray-900 dark:text-gray-200 border-transparent hover:bg-editor-border/40 hover:border-editor-border/60"
                }`}
                title="Delete file"
                onClick={(e) => {
                  e.stopPropagation();
                  void deleteFile(node.file.id);
                }}
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </>
        )}
      </div>
    );
  };

  return (
    <div className="h-full flex flex-col overflow-hidden bg-editor-sidebar">
      <div className="px-3 py-2.5 bg-gray-500/10 backdrop-blur-sm">
        <div className="flex items-center justify-between gap-2">
          <div className="min-w-0">
            <div className="text-[11px] font-semibold tracking-[0.14em] text-black dark:text-gray-400 uppercase">
              Explorer
            </div>
            <div className="text-[10px] text-black dark:text-gray-500 mt-0.5">
              {explorerStats.files} files, {explorerStats.folders} folders
            </div>
          </div>
          <div className="flex items-center gap-1 min-w-0">
            <div className="relative" ref={projectMenuRef}>
              <button
                type="button"
                ref={projectMenuButtonRef}
                className="max-w-[180px] inline-flex items-center gap-2 bg-editor-bg border border-editor-border rounded-md px-2 py-1 text-xs text-editor-text shadow-sm hover:bg-white/10 transition-colors"
                title="Switch project"
                onClick={() => setProjectMenuOpen((o) => !o)}
              >
                <span className="truncate">{activeProjectLabel}</span>
                <ChevronDown className="w-3.5 h-3.5 opacity-80" />
              </button>

              {projectMenuOpen &&
                projectMenuPos &&
                typeof document !== "undefined" &&
                createPortal(
                  <>
                    <button
                      type="button"
                      className="fixed inset-0 z-[150] cursor-default bg-transparent"
                      aria-label="Close project menu"
                      onClick={() => setProjectMenuOpen(false)}
                    />
                    <div
                      className="fixed z-[160] bg-editor-bg border border-editor-border rounded-lg shadow-[0_24px_48px_rgba(0,0,0,0.5)] backdrop-blur-xl overflow-hidden"
                      role="dialog"
                      aria-label="Project menu"
                      style={{
                        top: projectMenuPos.top,
                        left: projectMenuPos.left,
                        width: 240,
                      }}
                      onMouseDown={(e) => e.stopPropagation()}
                    >
                      <div className="p-1.5">
                        <button
                          type="button"
                          className={`w-full flex items-center justify-between px-3 py-2 text-xs rounded-md transition-colors ${
                            activeProjectId
                              ? "text-editor-text hover:bg-white/10 hover:text-white"
                              : "bg-editor-panelHigh/90 text-gray-100 shadow-sm"
                          }`}
                          onClick={() => {
                            if (!token) return;
                            fetchExplorerTree(null, token);
                            setProjectMenuOpen(false);
                          }}
                        >
                          <span className="truncate">My Files</span>
                        </button>

                        {projects.map((project) => {
                          const active = activeProjectId === project.id;
                          return (
                            <button
                              key={project.id}
                              type="button"
                              className={`w-full flex items-center justify-between px-3 py-2 text-xs rounded-md transition-colors ${
                                active
                                  ? "bg-editor-panelHigh text-gray-100"
                                  : "text-editor-text hover:bg-editor-panelHigh hover:text-gray-100"
                              }`}
                              onClick={() => {
                                if (!token) return;
                                fetchExplorerTree(project.id, token);
                                setProjectMenuOpen(false);
                              }}
                              title={project.name}
                            >
                              <span className="truncate">{project.name}</span>
                            </button>
                          );
                        })}
                      </div>

                      <div className="border-t border-editor-border/70 p-2">
                        <div className="px-2 pb-1 text-[10px] uppercase tracking-[0.22em] text-editor-text/60">
                          Add new
                        </div>
                        <button
                          type="button"
                          className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-xs font-semibold bg-emerald-400/10 text-emerald-700 dark:text-emerald-200 border border-emerald-400/25 hover:bg-emerald-400/15 transition-colors"
                          onClick={() => {
                            setProjectMenuOpen(false);
                            startCreateProject();
                          }}
                        >
                          <Plus className="w-4 h-4" />
                          Create new project
                        </button>
                      </div>
                    </div>
                  </>,
                  document.body,
                )}
            </div>
            <button
              type="button"
              className="p-1.5 rounded-md border border-transparent hover:bg-white/10 hover:border-editor-border text-editor-text transition-colors"
              title="New Folder"
              onClick={() => startCreateFolder()}
            >
              <FolderPlus className="w-4 h-4" />
            </button>
            <button
              type="button"
              className="p-1.5 rounded-md border border-transparent hover:bg-white/10 hover:border-editor-border text-editor-text transition-colors"
              title={
                selectedFolderId ? "New File in Selected Folder" : "New File"
              }
              onClick={() => startCreateFile()}
            >
              <Plus className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      <div
        className="flex-1 overflow-y-auto p-2.5 space-y-1.5"
        onDragOver={(e) => {
          // Allow dropping files to move them to root (out of folders).
          if (e.dataTransfer.types.includes("text/qcanvas-file-id")) {
            e.preventDefault();
          }
        }}
        onDrop={(e) => {
          const fileId = e.dataTransfer.getData("text/qcanvas-file-id");
          if (!fileId) return;
          // Drop on empty area => move to root
          const target = e.target as HTMLElement;
          if (!target.closest('[data-explorer-node="true"]')) {
            e.preventDefault();
            void moveFileToFolder(fileId, null);
          }
        }}
        onClick={(e) => {
          const target = e.target as HTMLElement;
          if (!target.closest('[data-explorer-node="true"]')) {
            setSelectedFolderId(null);
          }
        }}
      >
        {showNewProjectInput && (
          <>
            <button
              type="button"
              className="fixed inset-0 bg-black/50 z-[110] cursor-default"
              onClick={cancelCreateProject}
              aria-label="Close create project"
            />
            <div className="fixed inset-0 z-[115] flex items-center justify-center p-4">
              <div
                className="quantum-glass-dark rounded-2xl p-6 max-w-md w-full border border-editor-border shadow-[0_24px_48px_rgba(0,0,0,0.5)]"
                role="dialog"
                aria-modal="true"
                aria-labelledby="create-project-title"
                onMouseDown={(e) => e.stopPropagation()}
              >
                <div
                  id="create-project-title"
                  className="text-lg font-bold text-white"
                >
                  Create new project
                </div>
                <div className="mt-2 text-sm text-editor-text">
                  Projects group your files and folders.
                </div>

                <div className="mt-4">
                  <label
                    htmlFor="explorer-new-project-name"
                    className="text-[10px] uppercase tracking-[0.22em] text-editor-text/60"
                  >
                    Project name
                  </label>
                  <div className="mt-2 flex items-center gap-2 rounded-xl border border-editor-border/40 bg-black/20 px-3 py-2">
                    <FolderIcon className="w-4 h-4 text-emerald-300" />
                    <input
                      id="explorer-new-project-name"
                      value={newProjectName}
                      onChange={(e) => setNewProjectName(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") void submitCreateProject();
                        if (e.key === "Escape") cancelCreateProject();
                      }}
                      placeholder="e.g. Grover Experiments"
                      className="flex-1 bg-transparent outline-none text-sm text-white placeholder:text-editor-text/40"
                      autoFocus
                    />
                  </div>
                </div>

                <div className="mt-5 flex items-center justify-end gap-2">
                  <button
                    type="button"
                    className="px-3 py-2 rounded-md text-sm text-editor-text hover:bg-editor-border/60"
                    onClick={cancelCreateProject}
                  >
                    Cancel
                  </button>
                  <button
                    type="button"
                    className="px-3 py-2 rounded-md text-sm font-semibold bg-emerald-400/80 hover:bg-emerald-400 text-slate-950"
                    onClick={() => void submitCreateProject()}
                    disabled={!newProjectName.trim()}
                  >
                    Create project
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        {showNewFolderInput && (
          <div className="flex items-center gap-2 py-1.5 px-2 text-sm rounded-md border border-editor-border/20 bg-editor-bg shadow-sm">
            <FolderIcon className="w-4 h-4 text-quantum-blue-light" />
            <input
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void submitCreateFolder();
                if (e.key === "Escape") cancelCreateFolder();
              }}
              className="flex-1 bg-editor-bg border border-editor-border rounded px-2 py-1 text-xs text-editor-text focus-quantum"
              autoFocus
            />
            <button
              type="button"
              className="p-1 rounded hover:bg-green-500/20 text-green-400"
              title="Create folder"
              onClick={() => void submitCreateFolder()}
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              className="p-1 rounded hover:bg-red-500/20 text-red-400"
              title="Cancel"
              onClick={cancelCreateFolder}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {showNewFileInput && (
          <div className="flex items-center gap-2 py-1.5 px-2 text-sm rounded-md border border-editor-border/20 bg-editor-bg shadow-sm">
            <FileIcon className="w-4 h-4 text-editor-text" />
            <input
              value={newFileName}
              onChange={(e) => setNewFileName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") void submitCreateFile();
                if (e.key === "Escape") cancelCreateFile();
              }}
              className="flex-1 bg-editor-bg border border-editor-border rounded px-2 py-1 text-xs text-editor-text focus-quantum"
              autoFocus
            />
            <button
              type="button"
              className="p-1 rounded hover:bg-green-500/20 text-green-400"
              title="Create file"
              onClick={() => void submitCreateFile()}
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              className="p-1 rounded hover:bg-red-500/20 text-red-400"
              title="Cancel"
              onClick={cancelCreateFile}
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

        {tree.map((n, i) => renderNode(n, i))}
      </div>

      {contextMenu && (
        <div
          className="fixed z-[120] min-w-[180px] bg-editor-panelHighest/90 border border-editor-border rounded-lg shadow-[0_24px_48px_rgba(0,0,0,0.5)] p-1.5 backdrop-blur-xl"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {contextMenu.type === "folder" ? (
            <>
              <button
                type="button"
                className="w-full text-left px-3 py-1.5 text-xs text-editor-text hover:bg-editor-border/70 rounded-md"
                onClick={() => startCreateFile(contextMenu.id)}
              >
                New File
              </button>
              <button
                type="button"
                className="w-full text-left px-3 py-1.5 text-xs text-editor-text hover:bg-editor-border/70 rounded-md"
                onClick={() => startCreateFolder(contextMenu.id)}
              >
                New Folder
              </button>
              <button
                type="button"
                className="w-full text-left px-3 py-1.5 text-xs text-editor-text hover:bg-editor-border/70 rounded-md"
                onClick={() =>
                  startRenameFolder(contextMenu.id, contextMenu.name)
                }
              >
                Rename
              </button>
              <button
                type="button"
                className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/20 rounded-md"
                onClick={() => {
                  requestDeleteFolder(contextMenu.id, contextMenu.name);
                  setContextMenu(null);
                }}
              >
                Delete
              </button>
            </>
          ) : (
            <>
              <button
                type="button"
                className="w-full text-left px-3 py-1.5 text-xs text-editor-text hover:bg-editor-border/70 rounded-md"
                onClick={() => openFile(contextMenu.id)}
              >
                Open
              </button>
              <button
                type="button"
                className="w-full text-left px-3 py-1.5 text-xs text-editor-text hover:bg-editor-border/70 rounded-md"
                onClick={() =>
                  startRenameFile(contextMenu.id, contextMenu.name)
                }
              >
                Rename
              </button>
              <button
                type="button"
                className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/20 rounded-md"
                onClick={() => {
                  void deleteFile(contextMenu.id);
                  setContextMenu(null);
                }}
              >
                Delete
              </button>
            </>
          )}
        </div>
      )}

      {deleteFolderConfirm && (
        <>
          <button
            type="button"
            className="fixed inset-0 bg-black/50 z-[110] cursor-default"
            onClick={() => setDeleteFolderConfirm(null)}
            aria-label="Close delete folder confirmation"
          />
          <div className="fixed inset-0 z-[115] flex items-center justify-center p-4">
            <div className="quantum-glass-dark rounded-2xl p-6 max-w-md w-full border border-editor-border shadow-[0_24px_48px_rgba(0,0,0,0.5)]">
              <div className="text-lg font-bold text-white">Delete folder?</div>
              <div className="mt-2 text-sm text-editor-text">
                <div className="font-mono text-white/90">
                  {deleteFolderConfirm.folderName}
                </div>
                <div className="mt-2">
                  This folder contains{" "}
                  <span className="text-white font-semibold">
                    {deleteFolderConfirm.fileCount}
                  </span>{" "}
                  file{deleteFolderConfirm.fileCount === 1 ? "" : "s"}. Deleting
                  it will delete all files inside.
                </div>
              </div>

              <div className="mt-5 flex items-center justify-end gap-2">
                <button
                  type="button"
                  className="px-3 py-2 rounded-md text-sm text-editor-text hover:bg-editor-border/60"
                  onClick={() => setDeleteFolderConfirm(null)}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="px-3 py-2 rounded-md text-sm font-semibold bg-red-500/80 hover:bg-red-500 text-white"
                  onClick={() => {
                    const { folderId } = deleteFolderConfirm;
                    setDeleteFolderConfirm(null);
                    void deleteFolder(folderId);
                  }}
                >
                  Delete folder & files
                </button>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default memo(ExplorerView);
