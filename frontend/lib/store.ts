import { create } from 'zustand'
import { devtools } from 'zustand/middleware'
import { useStoreWithEqualityFn } from 'zustand/traditional'
import { File, Folder, EditorState, FILE_TEMPLATES, CompileOptions } from '@/types'
import { generateId, getLanguageFromFilename } from './utils'
import { projectsApi, foldersApi, fileApi, Project } from './api'
import { useAuthStore } from './authStore'
import toast from 'react-hot-toast'

/**
 * Project as held in the store. The API returns numeric ids, but the store
 * normalises every id (files, folders, projects) to strings so equality checks
 * in the UI (`project.id === activeProjectId`) are reliable.
 */
export type StoreProject = Omit<Project, 'id' | 'files'> & { id: string; files?: File[] }

/**
 * True only for ids that came from the backend (integer primary keys).
 * Local/in-memory files use ids like `file-1` (templates) or `local-<random>`
 * (created while logged out); those must never be sent to `/api/files/{id}`.
 */
export const isServerFileId = (id: string | null | undefined): id is string =>
  typeof id === 'string' && /^\d+$/.test(id)

const toApiId = (id: string | null | undefined): number | undefined => {
  if (id == null || id === '') return undefined
  const n = Number.parseInt(String(id), 10)
  return Number.isNaN(n) ? undefined : n
}

const apiErrorText = (error: unknown) =>
  typeof error === 'object' && error !== null ? JSON.stringify(error) : String(error ?? 'Unknown error')

/**
 * Ask the mounted editor to push its latest (debounced) content into the store
 * synchronously, so save/run never act on content that is up to 300ms stale.
 */
export const EDITOR_FLUSH_EVENT = 'qcanvas:flush-editor'
const flushEditor = () => {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new Event(EDITOR_FLUSH_EVENT))
  }
}

// Guards against out-of-order responses when the user switches projects quickly.
let explorerTreeRequestSeq = 0
// Local (never-saved) files currently being created on the backend.
const savingLocalFileIds = new Set<string>()

// Conversion stats interface based on backend ConversionResult
interface ConversionStats {
  qubits?: number | null
  gates?: { [gateName: string]: number } | null
  depth?: number | null
  conversion_time?: string | null
  framework?: string
  qasm_version?: string
  success?: boolean
  error?: string | null
}

// QSim simulation results interface
interface SimulationResult {
  counts: { [state: string]: number }
  metadata: {
    n_qubits: number
    visitor?: string
    backend: string
    shots: number
    success?: boolean
    // Performance metrics (populated by backend)
    execution_time?: string
    simulation_time?: string
    postprocessing_time?: string
    memory_usage?: string
    cpu_usage?: string
    fidelity?: number
    successful_shots?: number
    [key: string]: any
  }
  probs?: { [state: string]: number } | null
  circuit?: any
}

// Hybrid execution result interface
interface HybridResult {
  success: boolean
  stdout: string
  stderr: string
  qasm_generated?: string | null
  simulation_results: Array<{
    counts: { [state: string]: number }
    probabilities: { [state: string]: number }
    shots: number
    backend: string
    execution_time: string
    n_qubits: number
    metadata: { [key: string]: any }
  }>
  execution_time: string
  error?: string | null
  error_line?: number | null
  error_type?: string | null
}

// Execution mode type
type ExecutionMode = 'basic' | 'expert'

interface FileStore extends EditorState {
  // Additional state for conversion stats and simulation results
  conversionStats: ConversionStats | null
  simulationResults: SimulationResult | null

  // Project state
  projects: StoreProject[]
  activeProjectId: string | null
  loading: boolean

  // Explorer tree state (folders + files)
  folders: Folder[]
  selectedFolderId: string | null

  // Editor tabs state
  openFileIds: string[]

  // Hybrid execution state
  hybridResult: HybridResult | null
  executionMode: ExecutionMode

  // Actions
  setActiveFile: (fileId: string | null) => void
  openFile: (fileId: string) => void
  closeFile: (fileId: string) => void
  closeOtherFiles: (fileId: string) => void
  updateFileContent: (fileId: string, content: string) => void
  addFile: (name: string, content?: string) => File
  addFileWithoutActivating: (name: string, content?: string) => File
  deleteFile: (fileId: string) => Promise<void>

  setTheme: (theme: 'light' | 'dark') => void
  toggleTheme: () => void
  setExplainItMode: (enabled: boolean) => void
  toggleExplainItMode: () => void
  toggleSidebar: () => void
  toggleResults: () => void
  setFiles: (files: File[]) => void
  getActiveFile: () => File | undefined
  setCompileOptions: (options: Partial<CompileOptions>) => void
  setCompiledQasm: (qasm: string | null) => void
  setConversionStats: (stats: ConversionStats | null) => void
  setSimulationResults: (results: SimulationResult | null) => void
  setHybridResult: (result: HybridResult | null) => void
  setExecutionMode: (mode: ExecutionMode) => void
  compileActiveToQasm: () => string | null

  // Async Actions
  fetchProjects: (token: string) => Promise<void>
  fetchExplorerTree: (projectId: string | null, token: string) => Promise<void>
  createFolder: (name: string, projectId?: string, parentFolderId?: string) => Promise<void>
  renameFolder: (folderId: string, newName: string) => Promise<void>
  deleteFolder: (folderId: string) => Promise<void>
  createProject: (name: string, isPublic: boolean, token: string) => Promise<void>
  saveActiveFile: () => Promise<void>
  createFile: (name: string, content?: string, projectId?: string, isShared?: boolean, folderId?: string) => Promise<void>
  renameFile: (fileId: string, newName: string) => Promise<void>
  moveFileToFolder: (fileId: string, folderId: string | null) => Promise<void>
}

// =============================================================================
// DEVELOPER TOGGLE: Set to true to show built-in template files in the sidebar
// =============================================================================
const SHOW_TEMPLATE_FILES = false

const BASIC_QISKIT_BELL_TEMPLATE = `from qiskit import QuantumCircuit

# Bell state circuit
qc = QuantumCircuit(2, 2)
qc.h(0)
qc.cx(0, 1)
qc.measure([0, 1], [0, 1])

print(qc)
`

const getDefaultNewFileContent = (name: string, content?: string) => {
  if (content !== undefined) return content
  const language = getLanguageFromFilename(name)
  if (language === 'python') return BASIC_QISKIT_BELL_TEMPLATE
  return FILE_TEMPLATES[language] ?? ''
}

const splitFilename = (name: string) => {
  const trimmed = name.trim()
  const dot = trimmed.lastIndexOf('.')
  if (dot <= 0 || dot === trimmed.length - 1) {
    return { base: trimmed, ext: '' }
  }
  return { base: trimmed.slice(0, dot), ext: trimmed.slice(dot) }
}

const makeUniqueFilename = (desiredName: string, existingNames: string[]) => {
  const existing = new Set(existingNames.map((n) => n.trim().toLowerCase()))
  const desiredTrimmed = desiredName.trim()
  if (!desiredTrimmed) return desiredName

  if (!existing.has(desiredTrimmed.toLowerCase())) return desiredTrimmed

  const { base, ext } = splitFilename(desiredTrimmed)
  let i = 1
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const candidate = `${base} (${i})${ext}`
    if (!existing.has(candidate.toLowerCase())) return candidate
    i += 1
  }
}

const makeUniqueFolderName = (desiredName: string, existingNames: string[]) => {
  const existing = new Set(existingNames.map((n) => n.trim().toLowerCase()))
  const desiredTrimmed = desiredName.trim()
  if (!desiredTrimmed) return desiredName

  if (!existing.has(desiredTrimmed.toLowerCase())) return desiredTrimmed

  let i = 1
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const candidate = `${desiredTrimmed} (${i})`
    if (!existing.has(candidate.toLowerCase())) return candidate
    i += 1
  }
}

const collectDescendantFolderIds = (folders: Folder[], rootFolderId: string) => {
  const childrenByParent = new Map<string, string[]>()
  for (const f of folders) {
    const parent = f.parentId
    if (!parent) continue
    const list = childrenByParent.get(parent) ?? []
    list.push(f.id)
    childrenByParent.set(parent, list)
  }

  const result = new Set<string>()
  const stack = [rootFolderId]
  while (stack.length > 0) {
    const cur = stack.pop() as string
    if (result.has(cur)) continue
    result.add(cur)
    const kids = childrenByParent.get(cur) ?? []
    for (const k of kids) stack.push(k)
  }
  return result
}

// Initial files - quantum algorithm examples from different frameworks
const initialFiles: File[] = [
  (() => {
    const content = `import cirq

# Create qubits
q0, q1 = cirq.LineQubit.range(2)

# Create Bell state circuit
circuit = cirq.Circuit(
    cirq.H(q0),           # Hadamard on first qubit
    cirq.CNOT(q0, q1),    # CNOT with q0 as control
    cirq.measure(q0, q1)  # Measure both qubits
)

print("Bell State Circuit (Cirq):")
print(circuit)
`;
    return {
      id: 'file-1',
      name: 'bell_state_cirq.py',
      content,
      language: 'python',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      size: content.length,
    };
  })(),
  // Hybrid execution example
  (() => {
    const content = `# Hybrid CPU-QPU Execution Example
# Switch to "Hybrid" mode in the toolbar to run this code!

import cirq
from qcanvas import compile
import qsim

# Create a Bell state circuit
q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1]),
    cirq.measure(q[0], q[1], key='result')
])

print("Circuit created:")
print(circuit)
print()

# Compile circuit to OpenQASM 3.0
qasm = compile(circuit, framework="cirq")
print("Generated QASM:")
print(qasm)
print()

# Run multiple simulations in a loop
print("Running 3 simulations...")
for i in range(3):
    result = qsim.run(qasm, shots=100, backend="cirq")
    print(f"Run {i+1}: {result.counts}")
    print(f"  Probabilities: {result.probabilities}")

print()
print("Hybrid execution complete!")
`;
    return {
      id: 'file-hybrid',
      name: 'hybrid_example.py',
      content,
      language: 'python',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      size: content.length,
    };
  })(),
  (() => {
    const content = `from qiskit import QuantumCircuit

# 3 qubits, 2 classical bits (only measure input qubits)
qc = QuantumCircuit(3, 2)

# STEP 1: Initialize ancilla to |1⟩
qc.x(2)

# STEP 2: Hadamard on all qubits
for i in range(3):
    qc.h(i)

# STEP 3: Balanced Oracle
qc.cx(0, 2)
qc.cx(1, 2)

# STEP 4: Hadamard on input qubits
qc.h(0)
qc.h(1)

# STEP 5: Measure input qubits
qc.measure(0, 0)
qc.measure(1, 1)
`;
    return {
      id: 'file-2',
      name: 'deutsch_jozsa_qiskit.py',
      content,
      language: 'python',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      size: content.length,
    };
  })(),
  (() => {
    const content = `import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def grover_circuit():
    # STEP 1: Initialize superposition
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    
    # STEP 2: Oracle - mark |11⟩
    qml.CZ(wires=[0, 1])
    
    # STEP 3: Diffusion Operator
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.PauliX(wires=0)
    qml.PauliX(wires=1)
    qml.CZ(wires=[0, 1])
    qml.PauliX(wires=0)
    qml.PauliX(wires=1)
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    
    # STEP 4: Measure
    qml.measure(wires=0)
    qml.measure(wires=1)
`;
    return {
      id: 'file-3',
      name: 'grovers_search_pennylane.py',
      content,
      language: 'python',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      size: content.length,
    };
  })(),
  // Quantum Random Number Generator (QRNG) - Hybrid example
  (() => {
    const content = `import cirq

from qcanvas import compile
import qsim

print("=== Quantum Random Number Generator (QRNG) ===\\n")

# Create a simple circuit that generates one random bit
# H gate creates superposition, measurement collapses to 0 or 1
q = cirq.LineQubit(0)
circuit = cirq.Circuit([
    cirq.H(q),
    cirq.measure(q, key='random_bit')
])

# Compile to QASM
qasm = compile(circuit, framework="cirq")
print(f"QRNG Circuit QASM:\\n{qasm}\\n")

# Generate 10 random bits
print("Generating 10 random bits:")
random_bits = []
for i in range(10):
    result = qsim.run(qasm, shots=1, backend="cirq")
    # Extract the bit value (0 or 1)
    bit = list(result.counts.keys())[0]
    random_bits.append(bit)
    print(f"  Bit {i+1}: {bit}")

print(f"\\nRandom bit sequence: {''.join(random_bits)}")
`;
    return {
      id: 'file-4',
      name: 'qrng_hybrid_cirq.py',
      content,
      language: 'python',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      size: content.length,
    };
  })(),
]

export const useFileStore = create<FileStore>()(
  devtools(
    (set, get) => ({
      // Initial state
      activeFileId: null, // No file active initially until loaded
      files: [], // Start empty, load from DB
      projects: [],
      activeProjectId: null,
      loading: false,
      folders: [],
      selectedFolderId: null,
      openFileIds: [],
      theme: 'dark', // Always default to dark
      explainItMode: true,
      sidebarCollapsed: false,
      resultsCollapsed: false,
      compiledQasm: null,
      conversionStats: null,
      simulationResults: null,
      hybridResult: null,
      executionMode: 'basic' as ExecutionMode,
      compileOptions: {
        inputLanguage: 'qasm',
        resultFormat: 'json',
        qasmVersion: '3.0',
        style: 'classic',
      },

      // Actions
      setActiveFile: (fileId) => {
        set({ activeFileId: fileId }, false, 'setActiveFile')
      },

      openFile: (fileId: string) => {
        set(
          (state) => {
            const openFileIds = state.openFileIds.includes(fileId)
              ? state.openFileIds
              : [...state.openFileIds, fileId]
            return { openFileIds, activeFileId: fileId }
          },
          false,
          'openFile'
        )
      },

      closeFile: (fileId: string) => {
        set(
          (state) => {
            const openFileIds = state.openFileIds.filter((id) => id !== fileId)
            let activeFileId = state.activeFileId
            if (state.activeFileId === fileId) {
              activeFileId = openFileIds.at(-1) ?? null
            }
            return { openFileIds, activeFileId }
          },
          false,
          'closeFile'
        )
      },

      closeOtherFiles: (fileId: string) => {
        set(
          (state) => {
            const openFileIds = state.openFileIds.includes(fileId) ? [fileId] : state.openFileIds
            const activeFileId = state.openFileIds.includes(fileId) ? fileId : state.activeFileId
            return { openFileIds, activeFileId }
          },
          false,
          'closeOtherFiles'
        )
      },

      updateFileContent: (fileId, content) => {
        set(
          (state) => ({
            files: state.files.map((file) =>
              file.id === fileId
                ? {
                  ...file,
                  content,
                  updatedAt: new Date().toISOString(),
                  size: content.length,
                }
                : file
            ),
          }),
          false,
          'updateFileContent'
        )
      },

      addFile: (name, content) => {
        const uniqueName = makeUniqueFilename(name, get().files.map((f) => f.name))
        const language = getLanguageFromFilename(uniqueName)
        const defaultContent = getDefaultNewFileContent(uniqueName, content)

        const newFile: File = {
          // `local-` prefix: never mistaken for a backend id (see isServerFileId).
          id: `local-${generateId()}`,
          name: uniqueName,
          content: defaultContent,
          language,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          size: defaultContent.length,
        }

        set(
          (state) => ({
            files: [...state.files, newFile],
            openFileIds: state.openFileIds.includes(newFile.id)
              ? state.openFileIds
              : [...state.openFileIds, newFile.id],
            activeFileId: newFile.id,
          }),
          false,
          'addFile'
        )

        return newFile
      },

      // Create a new file but keep the current active file unchanged
      addFileWithoutActivating: (name, content) => {
        const uniqueName = makeUniqueFilename(name, get().files.map((f) => f.name))
        const language = getLanguageFromFilename(uniqueName)
        const defaultContent = getDefaultNewFileContent(uniqueName, content)

        const newFile: File = {
          id: `local-${generateId()}`,
          name: uniqueName,
          content: defaultContent,
          language,
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          size: defaultContent.length,
        }

        set(
          (state) => ({
            files: [...state.files, newFile],
          }),
          false,
          'addFileWithoutActivating'
        )

        return newFile
      },

      deleteFile: async (fileId) => {
        const token = useAuthStore.getState().token

        // API call if token exists and the file exists on the backend.
        // apiRequest never throws; it reports failures via `success: false`.
        if (token && isServerFileId(fileId)) {
          const res = await fileApi.deleteFile(Number.parseInt(fileId, 10), token)
          if (!res.success) {
            console.error('Failed to delete remote file', res.error)
            const name = get().files.find((f) => f.id === fileId)?.name ?? 'file'
            toast.error(`Failed to delete ${name}: ${apiErrorText(res.error)}`)
            return
          }
        }

        set(
          (state) => {
            const newFiles = state.files.filter((file) => file.id !== fileId)
            const openFileIds = state.openFileIds.filter((id) => id !== fileId)
            const newActiveFileId =
              state.activeFileId === fileId
                ? openFileIds.at(-1) ?? null
                : state.activeFileId

            return {
              files: newFiles,
              openFileIds,
              activeFileId: newActiveFileId,
            }
          },
          false,
          'deleteFile'
        )
      },

      renameFile: async (fileId: string, newName: string) => {
        const state = get()
        const token = useAuthStore.getState().token
        const existingOtherNames = state.files
          .filter((f) => f.id !== fileId)
          .map((f) => f.name)
        const uniqueName = makeUniqueFilename(newName, existingOtherNames)
        const previous = state.files.find((f) => f.id === fileId)
        if (!previous) return

        // Optimistic update
        set(
          (state) => ({
            files: state.files.map((file) =>
              file.id === fileId
                ? {
                  ...file,
                  name: uniqueName,
                  language: getLanguageFromFilename(uniqueName),
                  updatedAt: new Date().toISOString(),
                }
                : file
            ),
          }),
          false,
          'renameFile'
        )

        // API call if token exists and the file exists on the backend.
        // /api/files/{id} PUT works for both root and project files the user owns.
        if (token && isServerFileId(fileId)) {
          const res = await fileApi.updateFile(Number.parseInt(fileId, 10), { filename: uniqueName }, token)
          if (!res.success) {
            console.error('Failed to rename file remotely', res.error)
            // Revert the optimistic rename (only if nothing renamed it again meanwhile).
            set(
              (s) => ({
                files: s.files.map((file) =>
                  file.id === fileId && file.name === uniqueName
                    ? { ...file, name: previous.name, language: previous.language }
                    : file
                ),
              }),
              false,
              'renameFile.revert'
            )
            toast.error(`Failed to rename file: ${apiErrorText(res.error)}`)
          }
        }
      },

      setTheme: (theme) => {
        set(
          () => {
            try {
              if (typeof window !== 'undefined') {
                localStorage.setItem('qcanvas-theme', theme)
                // Apply theme immediately to document
                document.documentElement.classList.toggle('dark', theme === 'dark')
                document.documentElement.classList.toggle('light', theme === 'light')
              }
            } catch { }
            return { theme }
          },
          false,
          'setTheme'
        )
      },

      toggleTheme: () => {
        set(
          (state) => {
            const next = state.theme === 'light' ? 'dark' : 'light'
            try {
              if (typeof window !== 'undefined') {
                localStorage.setItem('qcanvas-theme', next)
                // Apply theme immediately to document
                document.documentElement.classList.toggle('dark', next === 'dark')
                document.documentElement.classList.toggle('light', next === 'light')
              }
            } catch { }
            return { theme: next }
          },
          false,
          'toggleTheme'
        )
      },

      setExplainItMode: (enabled) => {
        set(
          () => {
            try {
              if (globalThis.window !== undefined) {
                localStorage.setItem('qcanvas-explain-it', enabled ? '1' : '0')
              }
            } catch { }
            return { explainItMode: enabled }
          },
          false,
          'setExplainItMode'
        )
      },

      toggleExplainItMode: () => {
        set(
          (state) => {
            const next = !state.explainItMode
            try {
              if (globalThis.window !== undefined) {
                localStorage.setItem('qcanvas-explain-it', next ? '1' : '0')
              }
            } catch { }
            return { explainItMode: next }
          },
          false,
          'toggleExplainItMode'
        )
      },

      toggleSidebar: () => {
        set(
          (state) => ({
            sidebarCollapsed: !state.sidebarCollapsed,
          }),
          false,
          'toggleSidebar'
        )
      },

      toggleResults: () => {
        set(
          (state) => ({
            resultsCollapsed: !state.resultsCollapsed,
          }),
          false,
          'toggleResults'
        )
      },

      setFiles: (files) => {
        set({ files }, false, 'setFiles')
      },

      getActiveFile: () => {
        const state = get()
        return state.files.find((file) => file.id === state.activeFileId)
      },

      setCompileOptions: (options) => {
        set(
          (state) => ({
            compileOptions: { ...state.compileOptions, ...options },
          }),
          false,
          'setCompileOptions'
        )
      },

      setCompiledQasm: (qasm) => {
        set({ compiledQasm: qasm }, false, 'setCompiledQasm')
      },

      setConversionStats: (stats) => {
        set({ conversionStats: stats }, false, 'setConversionStats')
      },

      setSimulationResults: (results) => {
        set({ simulationResults: results }, false, 'setSimulationResults')
      },

      setHybridResult: (result) => {
        set({ hybridResult: result }, false, 'setHybridResult')
      },

      setExecutionMode: (mode) => {
        set({ executionMode: mode }, false, 'setExecutionMode')
      },

      compileActiveToQasm: () => {
        const state = get()
        const active = state.files.find((f) => f.id === state.activeFileId)
        if (!active) return null

        // If already QASM, trust content
        if (active.language === 'qasm') {
          set({ compiledQasm: active.content }, false, 'compileActiveToQasm.qasm')
          return active.content
        }

        // Mock conversion to OpenQASM 3
        const header = `OPENQASM 3.0;\ninclude "stdgates.inc";\n\n// Converted from ${active.language.toUpperCase()} by QCanvas`;
        // Provide a minimal Bell-like placeholder when converting
        const body = [
          'qubit[2] q;',
          'bit[2] c;',
          '',
          'h q[0];',
          'cx q[0], q[1];',
          'c = measure q;',
          '',
          '// Original source:',
          ...active.content.split('\n').map((l) => `// ${l}`),
        ].join('\n')

        const qasm = `${header}\n\n${body}`
        set({ compiledQasm: qasm }, false, 'compileActiveToQasm.mock')
        return qasm
      },

      // Async Actions
      fetchProjects: async (token: string) => {
        set({ loading: true })
        try {
          const res = await projectsApi.getProjects(token)
          if (res.success && res.data) {
            // Map files within projects to frontend format
            const mappedProjects: StoreProject[] = res.data.map((project: any) => ({
              ...project,
              id: project.id.toString(),
              files: (project.files || []).map((f: any) => ({
                id: f.id.toString(),
                name: f.filename,
                content: f.content,
                language: getLanguageFromFilename(f.filename),
                createdAt: f.created_at || new Date().toISOString(),
                updatedAt: f.updated_at || new Date().toISOString(),
                size: f.content?.length || 0,
                projectId: project.id.toString(),
                isShared: f.is_shared,
                userId: f.user_id,
              }))
            }))
            set({ projects: mappedProjects }, false, 'fetchProjects')
          }
        } catch (error) {
          console.error("Failed to fetch projects", error)
        } finally {
          set({ loading: false })
        }
      },

      createProject: async (name: string, isPublic: boolean, token: string) => {
        set({ loading: true })
        try {
          const res = await projectsApi.createProject({ name, is_public: isPublic }, token)
          if (res.success && res.data) {
            const newProject: StoreProject = {
              ...res.data,
              id: String(res.data.id),
              files: [],
            }
            set(state => ({
              projects: [...state.projects, newProject],
              activeProjectId: newProject.id,
              activeFileId: null
            }), false, 'createProject')
            // Refresh explorer scope for the created project so folders/files stay in sync.
            get().fetchExplorerTree(newProject.id, token)
          } else {
            toast.error(`Failed to create project: ${apiErrorText(res.error)}`)
          }
        } catch (error) {
          console.error("Failed to create project", error)
          toast.error("Failed to create project")
        } finally {
          set({ loading: false })
        }
      },

      fetchExplorerTree: async (projectIdArg: string | number | null, token: string) => {
        const projectId = projectIdArg == null || projectIdArg === '' ? null : String(projectIdArg)
        const requestSeq = ++explorerTreeRequestSeq
        set({ loading: true })
        try {
          const res = await foldersApi.getExplorerTree(toApiId(projectId), token)
          // A newer request (e.g. the user switched project again) supersedes this one.
          if (requestSeq !== explorerTreeRequestSeq) return
          if (res.success && res.data) {
            const tree = res.data

            const folders: Folder[] = (tree.folders || []).map((f: any) => ({
              id: f.id.toString(),
              name: f.name,
              projectId: f.project_id == null ? undefined : f.project_id.toString(),
              parentId: f.parent_id == null ? undefined : f.parent_id.toString(),
              createdAt: f.created_at || new Date().toISOString(),
              updatedAt: f.updated_at || new Date().toISOString(),
            }))

            const fetchedFiles: File[] = (tree.files || []).map((f: any) => ({
              id: f.id.toString(),
              name: f.filename,
              content: f.content,
              language: getLanguageFromFilename(f.filename),
              createdAt: f.created_at || new Date().toISOString(),
              updatedAt: f.updated_at || new Date().toISOString(),
              size: f.content?.length || 0,
              projectId: f.project_id == null ? undefined : f.project_id.toString(),
              folderId: f.folder_id == null ? undefined : f.folder_id.toString(),
              isShared: f.is_shared,
              userId: f.user_id?.toString?.() ?? undefined,
            }))

            set((state) => {
              const templates = SHOW_TEMPLATE_FILES ? initialFiles : []
              const filesToShow = projectId ? fetchedFiles : [...templates, ...fetchedFiles]
              return {
                folders,
                files: filesToShow,
                activeProjectId: projectId,
              }
            }, false, 'fetchExplorerTree')
          }
        } catch (error) {
          console.error('Failed to fetch explorer tree', error)
        } finally {
          if (requestSeq === explorerTreeRequestSeq) set({ loading: false })
        }
      },

      createFolder: async (name: string, projectId?: string, parentFolderId?: string) => {
        const token = useAuthStore.getState().token
        if (!token) {
          toast.error('Please log in to create a folder')
          return
        }

        const state = get()
        const folderName = name.trim()
        if (!folderName) return

        const siblingFolderNames = state.folders
          .filter((f) => {
            const sameProject =
              (f.projectId ?? undefined) === (projectId ?? undefined)
            const sameParent =
              (f.parentId ?? undefined) === (parentFolderId ?? undefined)
            return sameProject && sameParent
          })
          .map((f) => f.name)
        const uniqueFolderName = makeUniqueFolderName(folderName, siblingFolderNames)

        const toastId = toast.loading('Creating folder...')
        try {
          const res = await foldersApi.createFolder({
            name: uniqueFolderName,
            project_id: toApiId(projectId),
            parent_id: toApiId(parentFolderId),
          }, token)

          if (res.success && res.data) {
            const f: any = res.data
            const newFolder: Folder = {
              id: f.id.toString(),
              name: f.name,
              projectId: f.project_id == null ? undefined : f.project_id.toString(),
              parentId: f.parent_id == null ? undefined : f.parent_id.toString(),
              createdAt: f.created_at || new Date().toISOString(),
              updatedAt: f.updated_at || new Date().toISOString(),
            }

            set((state) => ({
              folders: [...state.folders, newFolder],
            }), false, 'createFolder')

            toast.success(`Created folder ${uniqueFolderName}`, { id: toastId })
          } else {
            const errorText = typeof res.error === 'object' ? JSON.stringify(res.error) : res.error
            toast.error(`Failed to create folder: ${errorText}`, { id: toastId })
          }
        } catch (error) {
          console.error('Create folder failed', error)
          toast.error('Failed to create folder', { id: toastId })
        }
      },

      renameFolder: async (folderId: string, newName: string) => {
        const token = useAuthStore.getState().token
        if (!token) {
          toast.error('Please log in to rename a folder')
          return
        }

        const state = get()
        const folderName = newName.trim()
        if (!folderName) return

        const current = state.folders.find((f) => f.id === folderId)
        const siblingFolderNames = state.folders
          .filter((f) => {
            if (f.id === folderId) return false
            const sameProject = (f.projectId ?? undefined) === (current?.projectId ?? undefined)
            const sameParent = (f.parentId ?? undefined) === (current?.parentId ?? undefined)
            return sameProject && sameParent
          })
          .map((f) => f.name)
        const uniqueFolderName = makeUniqueFolderName(folderName, siblingFolderNames)

        const toastId = toast.loading('Renaming folder...')
        try {
          const res = await foldersApi.updateFolder(
            Number.parseInt(folderId, 10),
            { name: uniqueFolderName },
            token,
          )
          if (res.success && res.data) {
            set((state) => ({
              folders: state.folders.map((f) =>
                f.id === folderId
                  ? { ...f, name: uniqueFolderName, updatedAt: new Date().toISOString() }
                  : f
              ),
            }), false, 'renameFolder')
            toast.success('Folder renamed', { id: toastId })
          } else {
            const errorText = typeof res.error === 'object' ? JSON.stringify(res.error) : res.error
            toast.error(`Failed to rename folder: ${errorText}`, { id: toastId })
          }
        } catch (error) {
          console.error('Rename folder failed', error)
          toast.error('Failed to rename folder', { id: toastId })
        }
      },

      deleteFolder: async (folderId: string) => {
        const token = useAuthStore.getState().token
        if (!token) {
          toast.error('Please log in to delete a folder')
          return
        }

        const toastId = toast.loading('Deleting folder...')
        try {
          const state = get()
          const folderIdsToRemove = collectDescendantFolderIds(state.folders, folderId)
          const filesInTree = state.files.filter((f) => f.folderId && folderIdsToRemove.has(f.folderId))

          // 1) Delete files first (backend rejects non-empty folder deletes).
          for (const f of filesInTree) {
            // Local-only files have nothing to delete remotely.
            if (!isServerFileId(f.id)) continue
            const delRes = await fileApi.deleteFile(Number.parseInt(f.id, 10), token)
            if (!delRes.success) {
              const errorText =
                typeof delRes.error === 'object' ? JSON.stringify(delRes.error) : delRes.error
              toast.error(`Failed to delete file "${f.name}": ${errorText}`, { id: toastId })
              return
            }
          }

          // 2) Delete folders deepest-first.
          const depthOf = (id: string) => {
            const byId = new Map(state.folders.map((x) => [x.id, x]))
            let depth = 0
            let cur = byId.get(id)
            while (cur?.parentId) {
              depth += 1
              cur = byId.get(cur.parentId)
            }
            return depth
          }
          const folderIdsSorted = Array.from(folderIdsToRemove).sort((a, b) => depthOf(b) - depthOf(a))

          for (const fid of folderIdsSorted) {
            const delFolderRes = await foldersApi.deleteFolder(Number.parseInt(fid, 10), token)
            if (!delFolderRes.success) {
              const errorText =
                typeof delFolderRes.error === 'object'
                  ? JSON.stringify(delFolderRes.error)
                  : delFolderRes.error
              toast.error(`Failed to delete folder: ${errorText}`, { id: toastId })
              return
            }
          }

          // 3) Update local state after successful remote deletion.
          set((s) => {
            const removedFileIds = new Set(filesInTree.map((f) => f.id))
            const files = s.files.filter((f) => !removedFileIds.has(f.id))
            const folders = s.folders.filter((f) => !folderIdsToRemove.has(f.id))
            const openFileIds = s.openFileIds.filter((id) => !removedFileIds.has(id))
            const activeFileId =
              s.activeFileId && removedFileIds.has(s.activeFileId)
                ? openFileIds.at(-1) ?? null
                : s.activeFileId
            return { folders, files, openFileIds, activeFileId }
          }, false, 'deleteFolder')

          toast.success('Folder deleted', { id: toastId })
        } catch (error) {
          console.error('Delete folder failed', error)
          toast.error('Failed to delete folder', { id: toastId })
        }
      },

      moveFileToFolder: async (fileId: string, folderId: string | null) => {
        const token = useAuthStore.getState().token
        const prev = get().files.find((f) => f.id === fileId)
        if (!prev) return

        // Optimistic UI update
        set(
          (state) => ({
            files: state.files.map((f) =>
              f.id === fileId
                ? { ...f, folderId: folderId ?? undefined, updatedAt: new Date().toISOString() }
                : f,
            ),
          }),
          false,
          'moveFileToFolder',
        )

        // Local-only file or unauthenticated: done.
        if (!token || !isServerFileId(fileId)) return

        // NOTE: the backend ignores `folder_id: null`, so moving a file back to the
        // root is currently only reflected locally until the backend supports it.
        const res = await fileApi.updateFile(
          Number.parseInt(fileId, 10),
          {
            folder_id: toApiId(folderId),
          },
          token,
        )
        if (!res.success) {
          console.error('moveFileToFolder failed', res.error)
          // Revert on failure
          set(
            (state) => ({
              files: state.files.map((f) =>
                f.id === fileId ? { ...f, folderId: prev.folderId } : f,
              ),
            }),
            false,
            'moveFileToFolder.revert',
          )
          toast.error(`Failed to move file: ${apiErrorText(res.error)}`)
        }
      },

      saveActiveFile: async () => {
        // Make sure the store has the editor's latest keystrokes before saving.
        flushEditor()

        const state = get()
        const activeFile = state.getActiveFile()
        const token = useAuthStore.getState().token

        if (!activeFile || !token) {
          if (!token) toast.error("Please log in to save")
          return
        }

        // Backend ids are integers (stored as strings). Anything else (`file-1`
        // templates, `local-...` files created while logged out) has never been
        // persisted, so it must be created rather than updated.
        const isNew = !isServerFileId(activeFile.id)
        if (isNew) {
          // Prevent duplicate creates when Save is pressed repeatedly.
          if (savingLocalFileIds.has(activeFile.id)) return
          savingLocalFileIds.add(activeFile.id)
        }

        const toastId = toast.loading('Saving...')
        try {
          let res;
          if (isNew) {
            // Create
            res = await fileApi.createFile({
              filename: activeFile.name,
              content: activeFile.content,
              is_main: false,
              project_id: toApiId(state.activeProjectId),
              folder_id: toApiId(activeFile.folderId),
              is_shared: activeFile.isShared
            }, token)
          } else {
            // Update
            res = await fileApi.updateFile(Number.parseInt(activeFile.id, 10), {
              content: activeFile.content
            }, token)
          }

          if (res.success && res.data) {
            toast.success('Saved', { id: toastId })
            // Update local file metadata (the id changes if it was new). Keep the
            // local content: the user may have kept typing while the request was
            // in flight, and overwriting it with the saved copy would lose edits.
            const backendFile = res.data as any
            const newId = backendFile.id.toString()

            set(s => ({
              files: s.files.map(f => f.id === activeFile.id
                ? {
                  ...f,
                  id: newId,
                  name: backendFile.filename ?? f.name,
                  updatedAt: backendFile.updated_at || new Date().toISOString(),
                  projectId: backendFile.project_id?.toString(),
                  folderId: backendFile.folder_id == null ? f.folderId : backendFile.folder_id.toString(),
                  isShared: backendFile.is_shared
                }
                : f),
              openFileIds: s.openFileIds.map(id => id === activeFile.id ? newId : id),
              activeFileId: s.activeFileId === activeFile.id ? newId : s.activeFileId
            }), false, 'saveActiveFile')
          } else {
            const errorText = typeof res.error === 'object' ? JSON.stringify(res.error) : res.error
            toast.error(`Failed to save: ${errorText}`, { id: toastId })
          }
        } catch (error) {
          console.error('Save failed', error)
          toast.error('Save failed', { id: toastId })
        } finally {
          if (isNew) savingLocalFileIds.delete(activeFile.id)
        }
      },

      createFile: async (name: string, content?: string, projectId?: string, isShared: boolean = false, folderId?: string) => {
        const state = get()
        const token = useAuthStore.getState().token

        // Fallback to local if no token (but user asked for backend sync)
        if (!token) {
          // Toast or memory?
          get().addFile(name, content)
          return
        }

        const uniqueName = makeUniqueFilename(name, state.files.map((f) => f.name))
        const language = getLanguageFromFilename(uniqueName)
        const defaultContent = getDefaultNewFileContent(uniqueName, content)
        const toastId = toast.loading('Creating file...')

        try {
          const res = await fileApi.createFile({
            filename: uniqueName,
            content: defaultContent,
            is_main: false,
            project_id: toApiId(projectId),
            folder_id: toApiId(folderId),
            is_shared: isShared
          }, token)

          if (res.success && res.data) {
            const f = res.data as any
            const newFile: File = {
              id: f.id.toString(),
              name: f.filename,
              content: f.content,
              language: language,
              createdAt: f.created_at || new Date().toISOString(),
              updatedAt: f.updated_at || new Date().toISOString(),
              size: f.content.length,
              projectId: f.project_id?.toString(),
              folderId: f.folder_id?.toString(),
              isShared: f.is_shared,
              userId: f.user_id?.toString()
            }
            set(
              (state) => ({
                files: [...state.files, newFile],
                // Open the new file as a tab too, otherwise it is active but tab-less.
                openFileIds: state.openFileIds.includes(newFile.id)
                  ? state.openFileIds
                  : [...state.openFileIds, newFile.id],
                activeFileId: newFile.id,
              }),
              false,
              'createFile'
            )
            toast.success(`Created ${uniqueName}`, { id: toastId })
          } else {
            const errorText = typeof res.error === 'object' ? JSON.stringify(res.error) : res.error
            toast.error(`Failed to create file: ${errorText}`, { id: toastId })
          }
        } catch (error) {
          console.error("Create file failed", error)
          toast.error("Failed to create file", { id: toastId })
        }
      },
    }),
    {
      name: 'file-store',
    }
  )
)

// =============================================================================
// Fine-grained subscription helpers
// =============================================================================
// Typing in the editor updates `files` (debounced), which creates a new `files`
// array on every update. Components that subscribe to the whole store or to
// `files` therefore re-render on every edit. Use these helpers instead.

const sameFileListMeta = (a: File[], b: File[]) =>
  a === b ||
  (a.length === b.length &&
    a.every((f, i) => {
      const g = b[i]
      return (
        f.id === g.id &&
        f.name === g.name &&
        f.language === g.language &&
        f.folderId === g.folderId &&
        f.projectId === g.projectId &&
        f.isShared === g.isShared
      )
    }))

/**
 * The file list, re-rendering only when ids/names/folders change, not on content
 * edits. Do NOT read `content`/`size`/`updatedAt` from the returned objects (they
 * may be stale); use `useFileStore.getState()` for that at call time.
 */
export const useFileListMeta = (): File[] =>
  useStoreWithEqualityFn(useFileStore, (s) => s.files, sameFileListMeta)

/** The active file (re-renders when the active file's content changes). */
export const useActiveFile = (): File | undefined =>
  useFileStore((s) => s.files.find((f) => f.id === s.activeFileId))

/** Whether a file is active (does not re-render on content edits). */
export const useHasActiveFile = (): boolean =>
  useFileStore((s) => s.activeFileId != null && s.files.some((f) => f.id === s.activeFileId))
