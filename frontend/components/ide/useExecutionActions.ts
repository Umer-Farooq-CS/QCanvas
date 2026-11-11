'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/lib/authStore'
import { EDITOR_FLUSH_EVENT, useFileStore } from '@/lib/store'
import { quantumApi } from '@/lib/api'
import { detectFramework } from '@/lib/utils'
import { useGamificationStore } from '@/lib/gamificationStore'
import { InputLanguage } from '@/types'

type SimulationBackend = 'cirq' | 'qiskit' | 'pennylane' | ''

function formatErrorMessage(error: string | undefined | null): string {
  if (!error) return 'Run failed'

  const errorLower = error.toLowerCase()

  if (errorLower.includes('http error') || errorLower.includes('status:')) return 'Run failed'
  if (errorLower.includes('network error') || errorLower.includes('fetch')) return 'Run failed: Network connection issue'
  if (errorLower.includes('timeout')) return 'Run failed: Request timed out'
  if (errorLower.includes('500') || errorLower.includes('502') || errorLower.includes('503')) return 'Run failed: Server error occurred'
  if (errorLower.includes('400')) return 'Run failed: Invalid request'
  if (errorLower.includes('401') || errorLower.includes('403')) return 'Run failed: Authentication error'
  if (errorLower.includes('404')) return 'Run failed: Resource not found'
  if (error.length > 100 || error.includes('Error:') || error.includes('Exception:')) return 'Run failed'

  return error
}

function formatHybridError(errorType: string | null | undefined, error: string | null | undefined, errorLine: number | null | undefined): string {
  const line = errorLine ? ` (line ${errorLine})` : ''

  switch (errorType) {
    case 'SecurityViolationError':
      return `Security Violation${line}: ${error || 'Blocked operation detected'}`
    case 'TimeoutError':
      return `Timeout${line}: Code execution exceeded time limit`
    case 'SyntaxError':
      return `Syntax Error${line}: ${error || 'Invalid Python syntax'}`
    case 'ImportError':
      return `Import Error${line}: ${error || 'Module import failed'}`
    case 'DisabledError':
      return 'Hybrid execution is disabled in server configuration'
    case 'NameError':
      return `Name Error${line}: ${error || 'Undefined variable or function'}`
    case 'TypeError':
      return `Type Error${line}: ${error || 'Invalid type operation'}`
    case 'ValueError':
      return `Value Error${line}: ${error || 'Invalid value'}`
    case 'RuntimeError':
      return `Runtime Error${line}: ${error || 'Execution failed'}`
    default:
      return error || 'Unknown error occurred'
  }
}

// Match an algorithm name as a whole identifier part, so "grover_oracle",
// "grovers_search" and "Grover's" match but "shortest"/"shore" do not match
// "shor". (No lookbehind: older Safari versions reject it at parse time.)
const wordish = (name: string) => new RegExp(`(?:^|[^a-z])${name}(?:'?s)?(?![a-z])`)
const GROVER_RE = wordish('grover')
const SHOR_RE = wordish('shor')
const QAOA_RE = wordish('qaoa')
const VQE_RE = wordish('vqe')
const DEUTSCH_RE = /(?:^|[^a-z])deutsch(?:[_-]?jozsa)?(?![a-z])|deutschjozsa/

function detectAlgorithmHint(code: string): string | null {
  const lower = code.toLowerCase()

  // An explicit tag always wins: "# algorithm: grover" / "# @algorithm grover".
  const tagMatch = lower.match(/#\s*@?algorithm[:\s]+([a-z_-]+)/)
  if (tagMatch) return tagMatch[1].trim()

  if (GROVER_RE.test(lower)) return 'grover'
  if (SHOR_RE.test(lower)) return 'shor'
  if (VQE_RE.test(lower) || lower.includes('variational_quantum_eigensolver') || lower.includes('vqecost')) return 'vqe'
  if (QAOA_RE.test(lower)) return 'qaoa'
  if (DEUTSCH_RE.test(lower)) return 'deutsch'

  return null
}

export function useExecutionActions({
  inputLanguage,
  simBackend,
  shots,
}: Readonly<{
  inputLanguage: InputLanguage | ''
  simBackend: SimulationBackend
  shots: number
}>) {
  // Read everything else from the stores at call time instead of subscribing:
  // subscribing to the active file here re-rendered the whole IDE page (and
  // recreated `run`, defeating memoised children) on every keystroke.
  const paramsRef = useRef({ inputLanguage, simBackend, shots })
  useEffect(() => {
    paramsRef.current = { inputLanguage, simBackend, shots }
  }, [inputLanguage, simBackend, shots])

  const [isRunning, setIsRunning] = useState(false)
  const isRunningRef = useRef(false)

  const runHybrid = useCallback(async () => {
    // Push any debounced editor content into the store first.
    window.dispatchEvent(new Event(EDITOR_FLUSH_EVENT))
    const { setSimulationResults, setHybridResult, setCompiledQasm } = useFileStore.getState()
    const activeFile = useFileStore.getState().getActiveFile()
    const { inputLanguage } = paramsRef.current
    const { token } = useAuthStore.getState()

    if (!activeFile) {
      toast.error('No file selected')
      return
    }

    setSimulationResults(null)
    setHybridResult(null)
    setCompiledQasm(null)

    const isQasmFile = activeFile.name.endsWith('.qasm') || activeFile.content.trim().startsWith('OPENQASM')
    if (isQasmFile) {
      toast.error("Expert mode is for Python code with qcanvas/qsim APIs. Switch to 'Basic' mode for QASM files.", {
        duration: 5000,
      })
      return
    }

    if (isRunningRef.current) return
    isRunningRef.current = true
    setIsRunning(true)
    try {
      toast.loading('Running hybrid Python code...', { id: 'hybrid-execution' })
      const detected = detectFramework(activeFile.content, activeFile.name)
      const result = await quantumApi.executeHybrid(activeFile.content, detected || inputLanguage || undefined, 180, token || undefined)

      if (!result.success) {
        let errorMsg = result.error || 'Hybrid execution failed'
        if (errorMsg.includes('404') || errorMsg.includes('not found')) {
          errorMsg = 'Hybrid execution API not available. Please ensure the backend is running with hybrid support.'
        } else if (errorMsg.includes('network') || errorMsg.includes('fetch') || errorMsg.includes('connection')) {
          errorMsg = 'Cannot connect to backend server. Please check your connection.'
        }

        toast.error(errorMsg, { id: 'hybrid-execution' })
        setHybridResult({
          success: false,
          stdout: '',
          stderr: errorMsg,
          simulation_results: [],
          execution_time: '',
          error: errorMsg,
          error_type: 'ConnectionError',
        })

        window.dispatchEvent(new CustomEvent('hybrid-execute', { detail: { success: false, error: errorMsg } }))
        return
      }

      const hybridResult = result.data!
      setHybridResult(hybridResult)

      if (hybridResult.success) {
        toast.success(`Hybrid execution completed in ${hybridResult.execution_time}`, { id: 'hybrid-execution' })
        if (hybridResult.simulation_results.length > 0) {
          setTimeout(() => {
            toast.success(`${hybridResult.simulation_results.length} simulation(s) completed`, { duration: 3000 })
          }, 1000)
        }

        window.dispatchEvent(new CustomEvent('hybrid-execute', { detail: { success: true, result: hybridResult } }))
      } else {
        const formattedError = formatHybridError(hybridResult.error_type, hybridResult.error, hybridResult.error_line)
        toast.error(formattedError, { id: 'hybrid-execution', duration: 6000 })
        window.dispatchEvent(new CustomEvent('hybrid-execute', { detail: { success: false, error: formattedError, result: hybridResult } }))
      }
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error)
      const displayError = errorMsg.includes('Failed to fetch') || errorMsg.includes('NetworkError')
        ? "Cannot connect to backend server. Please ensure it's running."
        : errorMsg

      toast.error(`Hybrid execution failed: ${displayError}`, { id: 'hybrid-execution' })
      console.error('Hybrid execution error:', error)

      setHybridResult({
        success: false,
        stdout: '',
        stderr: errorMsg,
        simulation_results: [],
        execution_time: '',
        error: displayError,
        error_type: 'NetworkError',
      })

      window.dispatchEvent(new CustomEvent('hybrid-execute', { detail: { success: false, error: displayError } }))
    } finally {
      isRunningRef.current = false
      setIsRunning(false)
    }
  }, [])

  const run = useCallback(async () => {
    if (useFileStore.getState().executionMode === 'expert') {
      return runHybrid()
    }

    // Push any debounced editor content into the store first.
    window.dispatchEvent(new Event(EDITOR_FLUSH_EVENT))
    const { setSimulationResults, setHybridResult, setCompiledQasm, setConversionStats } = useFileStore.getState()
    const activeFile = useFileStore.getState().getActiveFile()
    const { inputLanguage, simBackend, shots } = paramsRef.current
    const { isAuthenticated, user, token } = useAuthStore.getState()
    const { fetchStats, fetchRecentActivities } = useGamificationStore.getState()

    if (isRunningRef.current) return

    if (!activeFile) {
      toast.error('No file selected')
      return
    }

    setSimulationResults(null)
    setHybridResult(null)
    setCompiledQasm(null)

    const isQasmFile = activeFile.name.endsWith('.qasm') || activeFile.content.trim().startsWith('OPENQASM')

    if (!isQasmFile && !inputLanguage) {
      toast.error('Please select an input framework for your code')
      return
    }

    if (!simBackend) {
      toast.error('Please select a simulation backend')
      return
    }

    const detected = detectFramework(activeFile.content, activeFile.name)
    if (inputLanguage && detected && detected !== inputLanguage) {
      toast.error(`Incorrect language selected. Detected: ${detected}`)
      return
    }

    isRunningRef.current = true
    setIsRunning(true)
    // Only claim "Compilation successful" when we actually compiled source code
    // (not for QASM files, and not when the failure happened before conversion).
    let compiledFromSource = false
    const simFailurePrefix = () => (compiledFromSource ? 'Compilation successful, but simulation failed: ' : 'Simulation failed: ')
    try {
      toast.loading('Running quantum circuit...', { id: 'execution' })

      let qasmCode = ''
      if (isQasmFile) {
        qasmCode = activeFile.content
        setCompiledQasm(qasmCode)
      } else {
        const sourceFramework = inputLanguage || ''
        toast.loading(`Converting ${sourceFramework} to OpenQASM...`, { id: 'execution' })
        const conversionResult = await quantumApi.convertToQasm(activeFile.content, sourceFramework, 'classic', token || undefined)

        if (!conversionResult.success || !conversionResult.data?.success) {
          const rawError = conversionResult.data?.error || conversionResult.error || 'Compilation failed'
          const errorMsg = formatErrorMessage(rawError)
          setSimulationResults(null)
          toast.error(`Compilation failed: ${errorMsg}`, { id: 'execution' })
          window.dispatchEvent(new CustomEvent('circuit-compile', { detail: { success: false, error: errorMsg } }))
          return
        }

        if (isAuthenticated && token && user?.role !== 'demo') {
          fetchStats(token, true)
          fetchRecentActivities(token)
        }

        qasmCode = conversionResult.data.qasm_code
        compiledFromSource = true
        setCompiledQasm(qasmCode)
        setConversionStats({
          qubits: conversionResult.data.qubits,
          gates: conversionResult.data.gates,
          depth: conversionResult.data.depth,
          conversion_time: conversionResult.data.conversion_time,
          framework: sourceFramework,
          qasm_version: '3.0',
          success: true,
        })

        window.dispatchEvent(new CustomEvent('circuit-compile', { detail: { success: true, stats: conversionResult.data } }))
        toast.loading('Running simulation with QSim...', { id: 'execution' })
      }

      const algorithmHint = !isQasmFile && activeFile?.content ? detectAlgorithmHint(activeFile.content) ?? undefined : undefined
      const inputFramework = !isQasmFile && inputLanguage ? inputLanguage : undefined

      const executionResult = await quantumApi.executeQasmWithQSim(
        qasmCode,
        simBackend,
        shots,
        token || undefined,
        algorithmHint,
        inputFramework,
      )

      if (!executionResult.success) {
        setSimulationResults(null)
        const rawError = executionResult.error || executionResult.data?.error || 'Run failed'
        const errorMsg = formatErrorMessage(rawError)
        toast.error(`${simFailurePrefix()}${errorMsg}`, { id: 'execution' })
        window.dispatchEvent(new CustomEvent('circuit-execute', { detail: { success: false, error: errorMsg } }))
        return
      }

      if (executionResult.data?.success) {
        if (isAuthenticated && token && user?.role !== 'demo') {
          fetchStats(token, true)
          fetchRecentActivities(token)
        }

        const simResult = executionResult.data.results
        useFileStore.getState().setSimulationResults(simResult)
        window.dispatchEvent(new CustomEvent('circuit-execute', { detail: { success: true } }))
        toast.success(
          `${compiledFromSource ? 'Compilation successful. ' : ''}Simulation completed on ${simBackend} backend!`,
          { id: 'execution' },
        )
      } else {
        setSimulationResults(null)
        const rawError = executionResult.data?.error || executionResult.data?.detail || executionResult.error || 'Run failed'
        const errorMsg = formatErrorMessage(rawError)
        toast.error(`${simFailurePrefix()}${errorMsg}`, { id: 'execution' })
        window.dispatchEvent(new CustomEvent('circuit-execute', { detail: { success: false, error: errorMsg } }))
      }
    } catch (error) {
      setSimulationResults(null)
      const errorMsg = formatErrorMessage(error instanceof Error ? error.message : String(error))
      // Unknown failure point: only mention compilation if it really succeeded.
      toast.error(compiledFromSource ? `${simFailurePrefix()}${errorMsg}` : errorMsg, { id: 'execution' })
      console.error('Execution error:', error)
      window.dispatchEvent(new CustomEvent('circuit-execute', { detail: { success: false, error: errorMsg } }))
    } finally {
      isRunningRef.current = false
      setIsRunning(false)
    }
  }, [runHybrid])

  return { run, runHybrid, isRunning }
}