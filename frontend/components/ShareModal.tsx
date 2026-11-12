"use client";

import { useState, useEffect, useRef } from "react";
import { Copy } from "@/components/Icons";
import { Share } from "@/components/Icons";
import { X, Check, Tag } from "lucide-react";
import toast from "react-hot-toast";
import { useAuthStore } from "@/lib/authStore";
import { isServerFileId, useFileStore } from "@/lib/store";
import { useGamificationStore } from "@/lib/gamificationStore";
import { sharedApi, fileApi } from "@/lib/api";

const COMMON_TAGS = [
  "quantum-circuits",
  "qubits",
  "superposition",
  "entanglement",
  "measurement",
  "quantum-states",
  "bloch-sphere",
  "pauli-x",
  "pauli-y",
  "pauli-z",
  "hadamard",
  "phase-gate",
  "t-gate",
  "cnot",
  "cz",
  "swap",
  "toffoli",
  "multi-controlled-gates",
  "quantum-algorithms",
  "grover",
  "shor",
  "qft",
  "quantum-teleportation",
  "superdense-coding",
  "quantum-walk",
  "phase-estimation",
  "quantum-randomness",
  "circuit-optimization",
  "depth-optimization",
  "noise-aware",
  "quantum-machine-learning",
  "qml",
  "variational-circuits",
  "vqc",
  "qnn",
  "hybrid-quantum-classical",
  "feature-maps",
  "optimization",
  "cryptography",
  "search",
  "linear-algebra",
];

interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  fileId?: string;
  fileContent: string;
  fileName: string;
}

export default function ShareModal({
  isOpen,
  onClose,
  fileId,
  fileContent,
  fileName,
}: ShareModalProps) {
  const { user } = useAuthStore();
  const [id, setId] = useState("");
  const [title, setTitle] = useState(fileName);
  const [description, setDescription] = useState("");
  const [framework, setFramework] = useState("none");
  const [difficulty, setDifficulty] = useState("beginner");
  const [category, setCategory] = useState("Basic Circuits");
  const [tags, setTags] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isIdManuallyEdited, setIsIdManuallyEdited] = useState(false);

  // Tag suggestion state
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [cursorPosition, setCursorPosition] = useState(0);

  // Helper to generate a unique slug
  const generateUniqueId = (baseTitle: string) => {
    const slug = baseTitle
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/(^-|-$)/g, "");
    const randomSuffix = Math.random().toString(36).substring(2, 7);
    return `${slug || "circuit"}-${randomSuffix}`;
  };

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setTitle(fileName);
      setId(generateUniqueId(fileName));
      setIsIdManuallyEdited(false);
      setDescription("");
      setFramework("none");
      setDifficulty("beginner");
      setCategory("Basic Circuits");
      setTags("");
      setSuggestions([]);
      setShowSuggestions(false);
    }
  }, [isOpen, fileName]);

  // Update ID when title changes (if not manually edited)
  useEffect(() => {
    if (!isIdManuallyEdited && title) {
      setId(generateUniqueId(title));
    }
  }, [title, isIdManuallyEdited]);

  const handleTagChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setTags(val);
    setCursorPosition(e.target.selectionStart || 0);

    // Find the current tag being typed (the one under the cursor or last one)
    const lastCommaIndex = val.lastIndexOf(",");
    const currentInput =
      lastCommaIndex === -1 ? val : val.slice(lastCommaIndex + 1);
    const trimmedInput = currentInput.trim().toLowerCase();

    if (trimmedInput.length > 0) {
      const filtered = COMMON_TAGS.filter(
        (t) => t.toLowerCase().includes(trimmedInput) && !val.includes(t), // Exclude already added tags
      ).slice(0, 5); // Limit to 5 suggestions
      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
    } else {
      setShowSuggestions(false);
    }
  };

  const addTag = (tag: string) => {
    const lastCommaIndex = tags.lastIndexOf(",");
    let newTags = "";

    if (lastCommaIndex === -1) {
      newTags = tag;
    } else {
      newTags = tags.substring(0, lastCommaIndex + 1) + " " + tag;
    }

    setTags(newTags + ", ");
    setShowSuggestions(false);

    // meaningful focus restore or keeping focus would be nice,
    // but for now simple state update is enough.
  };

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!id.trim()) {
      toast.error("Please enter a unique ID");
      return;
    }

    setIsSubmitting(true);
    const token = useAuthStore.getState().token;

    try {
      // Tags is a comma-separated string, but backend expects list of strings
      const formattedTags = tags
        .split(",")
        .map((tag) => tag.trim())
        .filter((tag) => tag.length > 0);

      const response = await sharedApi.createSharedSnippet(
        {
          id,
          title,
          description,
          framework,
          difficulty,
          category,
          tags: formattedTags,
          code: fileContent,
          filename: fileName,
          author: user?.full_name || user?.username || "Anonymous User",
        },
        token || undefined,
      );

      if (response.success) {
        // Success! Sharing worked.
        toast.success("File shared successfully! XP awarded.");

        // Now update the original file's is_shared status (Best effort)
        const token = useAuthStore.getState().token;
        if (token && isServerFileId(fileId)) {
          fileApi
            .updateFile(parseInt(fileId), { is_shared: true }, token)
            .then(() => console.log("Updated file share status in DB"))
            .catch((e) =>
              console.error("Failed to update file share status in DB", e),
            );
        }

        // Update the local store so the UI (sidebar) reflects the change in either case
        const { files, setFiles } = useFileStore.getState();
        const updatedFiles = files.map((f) =>
          f.id === fileId ? { ...f, isShared: true } : f,
        );
        setFiles(updatedFiles);

        // Refresh gamification stats
        if (token) {
          const gamificationStore = useGamificationStore.getState();
          gamificationStore.fetchStats(token, true);
          gamificationStore.fetchAchievements(token, true);
        }

        onClose();
      } else {
        // If it already exists, suggest changing the ID
        if (response.error?.includes("already exists")) {
          const newId = generateUniqueId(title || fileName);
          setId(newId);
          toast.error(
            "That ID was taken. We've suggested a new one, please try sharing again!",
          );
        } else {
          toast.error(response.error || "Failed to share file");
        }
      }
    } catch (error) {
      console.error("Share error:", error);
      toast.error("An error occurred while sharing");
    } finally {
      setIsSubmitting(false);
    }
  };

  const categories = [
    "Basic Circuits",
    "Quantum Algorithms",
    "Variational Algorithms",
    "Error Correction",
    "Quantum Machine Learning",
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop with blur */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-md transition-opacity duration-300"
        onClick={onClose}
      />

      {/* Modal Container */}
      <div className="relative w-full max-w-5xl quantum-glass-dark rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Animated Background Glow */}
        <div className="absolute top-0 right-0 -mt-20 -mr-20 w-64 h-64 bg-quantum-blue-light opacity-10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="absolute bottom-0 left-0 -mb-20 -ml-20 w-64 h-64 bg-purple-500 opacity-10 rounded-full blur-3xl pointer-events-none"></div>

        {/* Header */}
        <div className="relative flex items-center justify-between p-6 border-b border-white/10">
          <div>
            <h2 className="text-2xl font-bold text-white flex items-center gap-3">
              <div className="p-2 rounded-lg bg-gradient-to-br from-blue-500/20 to-purple-500/20 border border-white/10">
                <Share className="w-6 h-6 text-blue-400" />
              </div>
              <span className="quantum-gradient bg-clip-text text-transparent">
                Share Project
              </span>
            </h2>
            <p className="text-black dark:text-gray-400 text-sm mt-1 ml-14">
              Share your quantum circuit with the community
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-white/10 text-black dark:text-gray-400 hover:text-white transition-all duration-200"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <form
          onSubmit={handleSubmit}
          className="relative flex flex-col lg:flex-row h-[80vh] lg:h-[70vh]"
        >
          {/* Left Side: Inputs */}
          <div className="flex-1 p-6 overflow-y-auto custom-scrollbar border-b lg:border-b-0 lg:border-r border-white/10 flex flex-col gap-5">
            {/* Unique ID Field */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-black dark:text-gray-300 ml-1">
                Unique ID <span className="text-red-400">*</span>
              </label>
              <div className="relative group flex items-center gap-2">
                <div className="relative flex-1">
                  <div className="absolute -inset-0.5 bg-gradient-to-r from-blue-500 to-purple-600 rounded-lg blur opacity-20 group-focus-within:opacity-75 transition duration-500"></div>
                  <input
                    type="text"
                    value={id}
                    onChange={(e) => {
                      setId(e.target.value);
                      setIsIdManuallyEdited(true);
                    }}
                    placeholder="e.g., my-quantum-teleportation"
                    className="relative w-full px-4 py-3 bg-black/20 border border-white/10 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500/50 focus:border-blue-500/50 transition-all duration-200"
                    required
                  />
                </div>
                <button
                  type="button"
                  onClick={() => setId(generateUniqueId(title || fileName))}
                  className="p-3 rounded-lg bg-white/5 border border-white/10 text-blue-400 hover:bg-white/10 hover:text-blue-300 transition-all flex-shrink-0"
                  title="Regenerate ID"
                >
                  <svg
                    className="w-5 h-5"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
                    ></path>
                  </svg>
                </button>
              </div>
            </div>

            {/* Title */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-black dark:text-gray-300 ml-1">
                Project Title <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full px-4 py-2.5 bg-black/20 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors"
                required
              />
            </div>

            {/* Category */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-black dark:text-gray-300 ml-1">
                Category
              </label>
              <div className="relative">
                <select
                  value={category}
                  onChange={(e) => setCategory(e.target.value)}
                  className="w-full px-4 py-2.5 bg-black/20 border border-white/10 rounded-lg text-white appearance-none focus:outline-none focus:border-blue-500/50 transition-colors cursor-pointer"
                >
                  {categories.map((cat) => (
                    <option
                      key={cat}
                      value={cat}
                      className="bg-gray-800 text-white"
                    >
                      {cat}
                    </option>
                  ))}
                </select>
                <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-black dark:text-gray-400">
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M19 9l-7 7-7-7"
                    ></path>
                  </svg>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Framework */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-black dark:text-gray-300 ml-1">
                  Framework
                </label>
                <div className="relative">
                  <select
                    value={framework}
                    onChange={(e) => setFramework(e.target.value)}
                    className="w-full px-4 py-2.5 bg-black/20 border border-white/10 rounded-lg text-white appearance-none focus:outline-none focus:border-blue-500/50 transition-colors cursor-pointer"
                  >
                    <option value="none" className="bg-gray-800">
                      None / Generic
                    </option>
                    <option value="qiskit" className="bg-gray-800">
                      Qiskit
                    </option>
                    <option value="cirq" className="bg-gray-800">
                      Cirq
                    </option>
                    <option value="pennylane" className="bg-gray-800">
                      PennyLane
                    </option>
                  </select>
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-black dark:text-gray-400">
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M19 9l-7 7-7-7"
                      ></path>
                    </svg>
                  </div>
                </div>
              </div>

              {/* Difficulty */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-black dark:text-gray-300 ml-1">
                  Difficulty
                </label>
                <div className="relative">
                  <select
                    value={difficulty}
                    onChange={(e) => setDifficulty(e.target.value)}
                    className="w-full px-4 py-2.5 bg-black/20 border border-white/10 rounded-lg text-white appearance-none focus:outline-none focus:border-blue-500/50 transition-colors cursor-pointer"
                  >
                    <option value="beginner" className="bg-gray-800">
                      Beginner
                    </option>
                    <option value="intermediate" className="bg-gray-800">
                      Intermediate
                    </option>
                    <option value="advanced" className="bg-gray-800">
                      Advanced
                    </option>
                  </select>
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-black dark:text-gray-400">
                    <svg
                      className="w-4 h-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth="2"
                        d="M19 9l-7 7-7-7"
                      ></path>
                    </svg>
                  </div>
                </div>
              </div>
            </div>

            {/* Description & Tags Group - Reduced Gap */}
            <div className="flex flex-col gap-3">
              {/* Description */}
              <div className="space-y-2">
                <label className="text-sm font-medium text-black dark:text-gray-300 ml-1">
                  Description
                </label>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={4}
                  className="w-full px-4 py-3 bg-black/20 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors resize-none placeholder-gray-500"
                  placeholder="Describe what your circuit does, its inputs and outputs..."
                />
              </div>

              {/* Tags */}
              <div className="space-y-2 relative">
                <label className="text-sm font-medium text-black dark:text-gray-300 ml-1 flex items-center gap-2">
                  Tags
                  <span className="text-xs text-black dark:text-gray-500 font-normal">
                    (comma separated)
                  </span>
                </label>
                <div className="relative">
                  <input
                    type="text"
                    value={tags}
                    onChange={handleTagChange}
                    placeholder="quantum-circuits, qubit..."
                    className="w-full px-4 py-2.5 bg-black/20 border border-white/10 rounded-lg text-white focus:outline-none focus:border-blue-500/50 transition-colors placeholder-gray-500"
                    autoComplete="off"
                  />
                  <div className="absolute right-3 top-1/2 -translate-y-1/2 text-black dark:text-gray-500 pointer-events-none">
                    <Tag className="w-4 h-4" />
                  </div>
                </div>

                {/* Tag Suggestions Dropdown */}
                {showSuggestions && (
                  <div className="absolute z-10 w-full mt-1 bg-gray-900/95 backdrop-blur-xl border border-white/10 rounded-lg shadow-xl overflow-hidden animate-in fade-in slide-in-from-top-2 duration-150">
                    <div className="p-1">
                      {suggestions.map((tag) => (
                        <button
                          key={tag}
                          type="button"
                          onClick={() => addTag(tag)}
                          className="w-full text-left px-3 py-2 text-sm text-black dark:text-gray-300 hover:bg-white/10 hover:text-white rounded-md transition-colors flex items-center gap-2 group"
                        >
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-500/50 group-hover:bg-blue-400 transition-colors"></span>
                          {tag}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Right Side: Preview & Actions */}
          <div className="w-full lg:w-[45%] flex flex-col p-6 bg-black/10">
            {/* Code Preview - Expanded */}
            <div className="flex-1 space-y-2 flex flex-col min-h-0">
              <label className="text-sm font-medium text-black dark:text-gray-300 ml-1 flex justify-between items-center">
                <span>Code Preview</span>
                <span className="text-xs text-blue-200 bg-blue-500/20 px-2 py-0.5 rounded-full font-mono border border-blue-500/30 shadow-sm">
                  {fileContent.split("\n").length} lines
                </span>
              </label>
              <div className="flex-1 relative rounded-lg overflow-hidden border border-white/10 group">
                <div className="absolute inset-0 backdrop-blur-sm"></div>
                <pre className="absolute inset-0 p-4 text-xs text-blue-800 dark:text-blue-200/90 font-mono overflow-auto custom-scrollbar leading-relaxed">
                  <code>{fileContent}</code>
                </pre>

                {/* Overlay gradient at bottom */}
                <div className="absolute bottom-0 left-0 right-0 h-14 bg-gradient-to-t from-white/80 dark:from-black/60 to-transparent pointer-events-none"></div>
              </div>
            </div>

            {/* Footer Actions - Now in Right Column */}
            <div className="mt-6 flex flex-col gap-3">
              <button
                type="submit"
                disabled={isSubmitting}
                className="on-fill w-full py-3 rounded-xl bg-gradient-to-r from-blue-600 via-purple-600 to-blue-600 hover:brightness-110 active:scale-95 text-gray-100 font-bold shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 transition-all duration-300 transform disabled:opacity-50 disabled:cursor-not-allowed disabled:transform-none flex items-center justify-center gap-2 bg-[length:200%_auto] animate-gradient"
              >
                {isSubmitting ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                    <span>Publishing...</span>
                  </>
                ) : (
                  <>
                    <Share className="w-5 h-5" />
                    <span>Share Project Now</span>
                  </>
                )}
              </button>

              <button
                type="button"
                onClick={onClose}
                className="w-full py-2.5 rounded-xl text-black dark:text-gray-400 hover:text-white hover:bg-white/5 transition-all duration-200 font-medium text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
