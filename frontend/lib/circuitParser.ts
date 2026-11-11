/**
 * Comprehensive Circuit Parser
 * 
 * Extracts quantum gates from Qiskit, Cirq, and PennyLane source code
 * and converts them to a unified format for visualization.
 */

import { getApiBase } from './api'
import { useAuthStore } from './authStore'

export interface ParsedGate {
  type: string           // 'h', 'x', 'cx', 'ry', etc.
  qubit: number          // Primary qubit index
  control?: number       // For controlled gates
  target?: number        // For two-qubit gates
  angle?: number         // For parameterized gates (in radians)
  qubits?: number[]      // For multi-qubit gates
  name?: string          // Display name
  timestamp?: number     // For animation
}

type Framework = 'qiskit' | 'cirq' | 'pennylane' | 'unknown'

/**
 * Detects the quantum framework from source code
 */
export function detectFramework(code: string): Framework {
  const lowerCode = code.toLowerCase()
  
  if (lowerCode.includes('from qiskit') || lowerCode.includes('import qiskit') || 
      lowerCode.includes('quantumcircuit') || lowerCode.includes('.h(') || 
      lowerCode.includes('.cx(') || lowerCode.includes('.x(')) {
    return 'qiskit'
  }
  
  if (lowerCode.includes('import cirq') || lowerCode.includes('cirq.') ||
      lowerCode.includes('linequbit') || lowerCode.includes('circuit.append')) {
    return 'cirq'
  }
  
  if (lowerCode.includes('import pennylane') || lowerCode.includes('import qml') ||
      lowerCode.includes('qml.') || lowerCode.includes('@qml.qnode') ||
      lowerCode.includes('wires=')) {
    return 'pennylane'
  }
  
  return 'unknown'
}

/**
 * Extracts qubit index from various formats: 0, qr[0], i, etc.
 */
function extractQubitFromArg(arg: string): number | null {
  const trimmed = arg.trim()
  
  // Direct number: 0, 1, 2
  const directNum = trimmed.match(/^(\d+)$/)
  if (directNum) return Number.parseInt(directNum[1], 10)
  
  // Array access: qr[0], q[1]
  const arrayAccess = trimmed.match(/\[(\d+)\]/)
  if (arrayAccess) return Number.parseInt(arrayAccess[1], 10)
  
  // Variable i, j, etc. - assume 0 for now (we'll handle loops separately)
  if (/^[a-z]$/.test(trimmed)) return 0
  
  return null
}

/**
 * Parses Qiskit code and extracts gates
 */
function parseQiskit(code: string): ParsedGate[] {
  const gates: ParsedGate[] = []
  const lines = code.split('\n')
  
  // First pass: detect for loops and their ranges
  const loopRanges: Map<string, { start: number; end: number; bodyStart: number; bodyEnd: number }> = new Map()
  let currentLoop: { variable: string; start: number; end: number; bodyStart: number } | null = null
  let indentLevel = 0
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const trimmedLine = line.trim()
    
    // Detect for loop: for i in range(n):
    const forMatch = trimmedLine.match(/^for\s+(\w+)\s+in\s+range\((\d+)(?:,\s*(\d+))?\):/)
    if (forMatch) {
      const variable = forMatch[1]
      const rangeStart = forMatch[3] ? Number.parseInt(forMatch[2], 10) : 0
      const rangeEnd = forMatch[3] ? Number.parseInt(forMatch[3], 10) : Number.parseInt(forMatch[2], 10)
      currentLoop = { variable, start: rangeStart, end: rangeEnd, bodyStart: i + 1 }
      indentLevel = line.search(/\S/) // Get indent level of 'for' statement
      continue
    }
    
    // Check if we're exiting a loop (back to same or lower indent, non-empty line)
    if (currentLoop && trimmedLine && !trimmedLine.startsWith('#')) {
      const currentIndent = line.search(/\S/)
      if (currentIndent <= indentLevel) {
        // Loop ended
        loopRanges.set(currentLoop.variable, {
          start: currentLoop.start,
          end: currentLoop.end,
          bodyStart: currentLoop.bodyStart,
          bodyEnd: i
        })
        currentLoop = null
      }
    }
  }
  
  // Close any open loop at end of file
  if (currentLoop) {
    loopRanges.set(currentLoop.variable, {
      start: currentLoop.start,
      end: currentLoop.end,
      bodyStart: currentLoop.bodyStart,
      bodyEnd: lines.length
    })
  }
  
  // Second pass: parse gates, expanding loops
  const processedLoops = new Set<string>()
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line || line.startsWith('#') || line.startsWith('"""') || line.startsWith('for ')) continue
    
    // Check if this line is inside a loop
    let loopVariable: string | null = null
    let loopRange: { start: number; end: number; bodyStart: number; bodyEnd: number } | null = null
    
    const entries = Array.from(loopRanges.entries())
    for (let j = 0; j < entries.length; j++) {
      const [variable, range] = entries[j]
      if (i >= range.bodyStart && i < range.bodyEnd) {
        loopVariable = variable
        loopRange = range
        break
      }
    }
    
    // Single qubit gates: .h(qubit), .x(qubit), .y(qubit), .z(qubit), .s(qubit), .t(qubit)
    // Matches: .h(0), .h(qr[0]), .h(i)
    const singleQubitMatch = line.match(/\.(h|x|y|z|s|t|id|i)\(([^)]+)\)/)
    if (singleQubitMatch) {
      const [, gateType, qubitArg] = singleQubitMatch
      // Skip range() calls - handled separately
      if (qubitArg.includes('range')) continue
      
      // Check if qubit is a loop variable
      if (loopVariable && loopRange && qubitArg.trim() === loopVariable) {
        // Expand the loop - add gate for each iteration
        const loopKey = `${loopVariable}-${i}`
        if (!processedLoops.has(loopKey)) {
          processedLoops.add(loopKey)
          for (let q = loopRange.start; q < loopRange.end; q++) {
            gates.push({
              type: gateType === 'id' || gateType === 'i' ? 'id' : gateType,
              qubit: q,
              timestamp: i
            })
          }
        }
        continue
      }
      
      const qubit = extractQubitFromArg(qubitArg)
      if (qubit !== null) {
        gates.push({
          type: gateType === 'id' || gateType === 'i' ? 'id' : gateType,
          qubit: qubit,
          timestamp: i
        })
      }
      continue
    }
    
    // Two qubit gates: .cx(control, target), .cz(control, target), .cy(control, target)
    // Matches: .cx(0, 1), .cx(qr[0], qr[1])
    const twoQubitMatch = line.match(/\.(cx|cnot|cz|cy|ch|swap)\(([^,]+),\s*([^)]+)\)/)
    if (twoQubitMatch) {
      const [, gateType, controlArg, targetArg] = twoQubitMatch
      const control = extractQubitFromArg(controlArg)
      const target = extractQubitFromArg(targetArg)
      if (control !== null && target !== null) {
        gates.push({
          type: gateType === 'cnot' ? 'cx' : gateType,
          qubit: control,
          control: control,
          target: target,
          timestamp: i
        })
      }
      continue
    }
    
    // Parameterized single qubit gates: .rx(angle, qubit), .ry(angle, qubit), .rz(angle, qubit), .p(angle, qubit)
    const paramSingleMatch = line.match(/\.(rx|ry|rz|p)\(([^,]+),\s*([^)]+)\)/)
    if (paramSingleMatch) {
      const [, gateType, angleStr, qubitArg] = paramSingleMatch
      const angle = parseAngle(angleStr)
      const qubit = extractQubitFromArg(qubitArg)
      if (qubit !== null) {
        gates.push({
          type: gateType,
          qubit: qubit,
          angle: angle,
          timestamp: i
        })
      }
      continue
    }
    
    // Universal gate: .u(theta, phi, lambda, qubit)
    const uGateMatch = line.match(/\.u\(([^,]+),\s*([^,]+),\s*([^,]+),\s*([^)]+)\)/)
    if (uGateMatch) {
      const [, theta, , , qubitArg] = uGateMatch
      const qubit = extractQubitFromArg(qubitArg)
      if (qubit !== null) {
        gates.push({
          type: 'u',
          qubit: qubit,
          angle: parseAngle(theta),
          name: 'U',
          timestamp: i
        })
      }
      continue
    }
    
    // Multi-qubit gates: .ccx(control1, control2, target), .cswap(control, target1, target2)
    const multiQubitMatch = line.match(/\.(ccx|toffoli|ccz|cswap|fredkin)\(([^,]+),\s*([^,]+),\s*([^)]+)\)/)
    if (multiQubitMatch) {
      const [, gateType, q1Arg, q2Arg, q3Arg] = multiQubitMatch
      const q1 = extractQubitFromArg(q1Arg)
      const q2 = extractQubitFromArg(q2Arg)
      const q3 = extractQubitFromArg(q3Arg)
      if (q1 !== null && q2 !== null && q3 !== null) {
        gates.push({
          type: gateType === 'toffoli' ? 'ccx' : gateType === 'fredkin' ? 'cswap' : gateType,
          qubit: q1,
          qubits: [q1, q2, q3],
          control: q1,
          target: q3,
          timestamp: i
        })
      }
      continue
    }
    
    // Measurements: .measure(qubits, bits) or .measure_all()
    if (line.includes('.measure_all()')) {
      // Add measurement gates for common qubit counts (assume 2 qubits)
      gates.push({ type: 'measure', qubit: 0, timestamp: i })
      gates.push({ type: 'measure', qubit: 1, timestamp: i })
      continue
    }
    
    const measureMatch = line.match(/\.measure\(([^)]+)\)/)
    if (measureMatch) {
      const args = measureMatch[1]
      // Try to extract qubit indices
      const qubit = extractQubitFromArg(args.split(',')[0])
      if (qubit !== null) {
        gates.push({
          type: 'measure',
          qubit: qubit,
          timestamp: i
        })
      }
      continue
    }
    
    // Handle range-based gates: .h(range(n)) or .h([0, 1, 2])
    const rangeMatch = line.match(/\.(h|x|y|z)\(range\((\d+)\)\)/)
    if (rangeMatch) {
      const [, gateType, maxQubit] = rangeMatch
      for (let q = 0; q < Number.parseInt(maxQubit, 10); q++) {
        gates.push({
          type: gateType,
          qubit: q,
          timestamp: i
        })
      }
      continue
    }
  }
  
  return gates
}

/**
 * Parses Cirq code and extracts gates
 */
function parseCirq(code: string): ParsedGate[] {
  const gates: ParsedGate[] = []
  const lines = code.split('\n')
  
  // Track qubit variables
  const qubitVars: Map<string, number> = new Map()
  let qubitCounter = 0
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line || line.startsWith('#') || line.startsWith('"""')) continue
    
    // Extract qubit declarations: q0, q1, q2 = cirq.LineQubit.range(3)
    const qubitRangeMatch = line.match(/(\w+)\s*=\s*cirq\.LineQubit\.range\((\d+)\)/)
    if (qubitRangeMatch) {
      const [, varName, count] = qubitRangeMatch
      const numQubits = Number.parseInt(count, 10)
      for (let j = 0; j < numQubits; j++) {
        qubitVars.set(`${varName}[${j}]`, j)
        qubitVars.set(`${varName}${j}`, j)
      }
      qubitCounter = numQubits
      continue
    }
    
    // Single qubit gates: cirq.H(qubit), cirq.X(qubit), cirq.Y(qubit), cirq.Z(qubit)
    const singleQubitMatch = line.match(/cirq\.(H|X|Y|Z|S|T|I)\(([^)]+)\)/)
    if (singleQubitMatch) {
      const [, gateType, qubitRef] = singleQubitMatch
      const qubit = extractQubitIndex(qubitRef, qubitVars, qubitCounter)
      if (qubit !== null) {
        gates.push({
          type: gateType.toLowerCase(),
          qubit: qubit,
          timestamp: i
        })
      }
      continue
    }
    
    // Two qubit gates: cirq.CNOT(control, target), cirq.CZ(control, target), cirq.SWAP(q1, q2)
    const twoQubitMatch = line.match(/cirq\.(CNOT|CX|CZ|CY|CH|SWAP)\(([^,]+),\s*([^)]+)\)/)
    if (twoQubitMatch) {
      const [, gateType, controlRef, targetRef] = twoQubitMatch
      const control = extractQubitIndex(controlRef, qubitVars, qubitCounter)
      const target = extractQubitIndex(targetRef, qubitVars, qubitCounter)
      if (control !== null && target !== null) {
        gates.push({
          type: gateType === 'CNOT' || gateType === 'CX' ? 'cx' : gateType.toLowerCase(),
          qubit: control,
          control: control,
          target: target,
          timestamp: i
        })
      }
      continue
    }
    
    // Parameterized gates: cirq.rx(angle)(qubit), cirq.ry(angle)(qubit), cirq.rz(angle)(qubit)
    const paramGateMatch = line.match(/cirq\.(rx|ry|rz)\(([^)]+)\)\(([^)]+)\)/)
    if (paramGateMatch) {
      const [, gateType, angleStr, qubitRef] = paramGateMatch
      const qubit = extractQubitIndex(qubitRef, qubitVars, qubitCounter)
      const angle = parseAngle(angleStr)
      if (qubit !== null) {
        gates.push({
          type: gateType,
          qubit: qubit,
          angle: angle,
          timestamp: i
        })
      }
      continue
    }
    
    // Circuit append: circuit.append(cirq.H(q0))
    const appendMatch = line.match(/circuit\.append\(([^)]+)\)/)
    if (appendMatch) {
      const gateCall = appendMatch[1]
      
      // Extract gate from append
      const singleAppend = gateCall.match(/cirq\.(H|X|Y|Z|S|T|I)\(([^)]+)\)/)
      if (singleAppend) {
        const [, gateType, qubitRef] = singleAppend
        const qubit = extractQubitIndex(qubitRef, qubitVars, qubitCounter)
        if (qubit !== null) {
          gates.push({
            type: gateType.toLowerCase(),
            qubit: qubit,
            timestamp: i
          })
        }
        continue
      }
      
      const twoQubitAppend = gateCall.match(/cirq\.(CNOT|CX|CZ|CY|CH|SWAP)\(([^,]+),\s*([^)]+)\)/)
      if (twoQubitAppend) {
        const [, gateType, controlRef, targetRef] = twoQubitAppend
        const control = extractQubitIndex(controlRef, qubitVars, qubitCounter)
        const target = extractQubitIndex(targetRef, qubitVars, qubitCounter)
        if (control !== null && target !== null) {
          gates.push({
            type: gateType === 'CNOT' || gateType === 'CX' ? 'cx' : gateType.toLowerCase(),
            qubit: control,
            control: control,
            target: target,
            timestamp: i
          })
        }
        continue
      }
    }
    
    // Measurements: cirq.measure(qubit, key='...')
    const measureMatch = line.match(/cirq\.measure\(([^,)]+)/)
    if (measureMatch) {
      const qubitRef = measureMatch[1]
      const qubit = extractQubitIndex(qubitRef, qubitVars, qubitCounter)
      if (qubit !== null) {
        gates.push({
          type: 'measure',
          qubit: qubit,
          timestamp: i
        })
      }
      continue
    }
  }
  
  return gates
}

/**
 * Extracts qubit from PennyLane wires= argument
 */
function extractPennyLaneQubit(arg: string): number | null {
  const trimmed = arg.trim()
  // Direct number
  const numMatch = trimmed.match(/^(\d+)$/)
  if (numMatch) return Number.parseInt(numMatch[1], 10)
  // Variable (i, j, etc.) - assume 0
  if (/^[a-z]$/.test(trimmed)) return 0
  return null
}

/**
 * Parses PennyLane code and extracts gates
 */
function parsePennyLane(code: string): ParsedGate[] {
  const gates: ParsedGate[] = []
  const lines = code.split('\n')
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim()
    if (!line || line.startsWith('#') || line.startsWith('"""')) continue
    
    // Single qubit gates: qml.Hadamard(wires=qubit), qml.PauliX(wires=qubit), etc.
    // More flexible: matches wires=0, wires=i, wires=qubit
    const singleQubitMatch = line.match(/qml\.(Hadamard|PauliX|PauliY|PauliZ|S|T|Identity)\(wires=(\w+)\)/)
    if (singleQubitMatch) {
      const [, gateType, qubitArg] = singleQubitMatch
      const qubit = extractPennyLaneQubit(qubitArg)
      if (qubit !== null) {
        let normalizedType: string
        if (gateType === 'Hadamard') normalizedType = 'h'
        else if (gateType === 'PauliX') normalizedType = 'x'
        else if (gateType === 'PauliY') normalizedType = 'y'
        else if (gateType === 'PauliZ') normalizedType = 'z'
        else normalizedType = gateType.toLowerCase()
        
        gates.push({
          type: normalizedType,
          qubit: qubit,
          timestamp: i
        })
      }
      continue
    }
    
    // Two qubit gates: qml.CNOT(wires=[control, target]), qml.CZ(wires=[control, target])
    const twoQubitMatch = line.match(/qml\.(CNOT|CZ|CY|CH|SWAP)\(wires=\[(\w+),\s*(\w+)\]\)/)
    if (twoQubitMatch) {
      const [, gateType, controlArg, targetArg] = twoQubitMatch
      const control = extractPennyLaneQubit(controlArg)
      const target = extractPennyLaneQubit(targetArg)
      if (control !== null && target !== null) {
        gates.push({
          type: gateType === 'CNOT' ? 'cx' : gateType.toLowerCase(),
          qubit: control,
          control: control,
          target: target,
          timestamp: i
        })
      }
      continue
    }
    
    // Parameterized gates: qml.RX(angle, wires=qubit), qml.RY(angle, wires=qubit), qml.RZ(angle, wires=qubit)
    const paramGateMatch = line.match(/qml\.(RX|RY|RZ|PhaseShift)\(([^,]+),\s*wires=(\w+)\)/)
    if (paramGateMatch) {
      const [, gateType, angleStr, qubitArg] = paramGateMatch
      const angle = parseAngle(angleStr)
      const qubit = extractPennyLaneQubit(qubitArg)
      if (qubit !== null) {
        gates.push({
          type: gateType === 'PhaseShift' ? 'p' : gateType.toLowerCase(),
          qubit: qubit,
          angle: angle,
          timestamp: i
        })
      }
      continue
    }
    
    // Measurements: qml.measure(wires=qubit)
    const measureMatch = line.match(/qml\.measure\(wires=(\w+)\)/)
    if (measureMatch) {
      const qubit = extractPennyLaneQubit(measureMatch[1])
      if (qubit !== null) {
        gates.push({
          type: 'measure',
          qubit: qubit,
          timestamp: i
        })
      }
      continue
    }
  }
  
  return gates
}

/**
 * Extracts qubit index from a qubit reference (handles q0, q[0], LineQubit(0), etc.)
 */
function extractQubitIndex(
  qubitRef: string, 
  qubitVars: Map<string, number>, 
  _defaultMax: number
): number | null {
  const trimmed = qubitRef.trim()
  
  // Direct number
  const numMatch = trimmed.match(/^(\d+)$/)
  if (numMatch) {
    return Number.parseInt(numMatch[1], 10)
  }
  
  // Array access: q[0], q0[1]
  const arrayMatch = trimmed.match(/\[(\d+)\]/)
  if (arrayMatch) {
    return Number.parseInt(arrayMatch[1], 10)
  }
  
  // Variable lookup: q0, q1, etc.
  if (qubitVars.has(trimmed)) {
    return qubitVars.get(trimmed)!
  }
  
  // Try to extract number from variable name: q0 -> 0, q1 -> 1
  const varNumMatch = trimmed.match(/(\d+)/)
  if (varNumMatch) {
    return Number.parseInt(varNumMatch[1], 10)
  }
  
  // Default: assume 0 if we can't parse
  return 0
}

/**
 * Parses angle expressions (handles pi, np.pi, math.pi, numeric values)
 */
function parseAngle(angleStr: string): number {
  const trimmed = angleStr.trim().toLowerCase()
  
  // Handle pi expressions
  if (trimmed.includes('pi')) {
    const piMatch = trimmed.match(/([\d.]*)\s*\*\s*pi|pi\s*\*\s*([\d.]+)|pi/)
    if (piMatch) {
      const multiplier = piMatch[1] ? parseFloat(piMatch[1]) : 
                        piMatch[2] ? parseFloat(piMatch[2]) : 1
      return multiplier * Math.PI
    }
    return Math.PI
  }
  
  // Handle numeric values
  const numMatch = trimmed.match(/([\d.]+)/)
  if (numMatch) {
    return parseFloat(numMatch[1])
  }
  
  // Default: return 0 if we can't parse
  return 0
}

/**
 * Simple fallback parser that works with basic patterns
 */
function parseSimple(code: string): ParsedGate[] {
  const gates: ParsedGate[] = []
  const lines = code.split('\n')
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    
    // Qiskit: .h(0), .h(qr[0])
    if (line.includes('.h(')) {
      const match = line.match(/\.h\((?:\w+\[)?(\d+)/)
      if (match) gates.push({ type: 'h', qubit: Number.parseInt(match[1], 10) })
    }
    if (line.includes('.x(')) {
      const match = line.match(/\.x\((?:\w+\[)?(\d+)/)
      if (match) gates.push({ type: 'x', qubit: Number.parseInt(match[1], 10) })
    }
    if (line.includes('.y(')) {
      const match = line.match(/\.y\((?:\w+\[)?(\d+)/)
      if (match) gates.push({ type: 'y', qubit: Number.parseInt(match[1], 10) })
    }
    if (line.includes('.z(')) {
      const match = line.match(/\.z\((?:\w+\[)?(\d+)/)
      if (match) gates.push({ type: 'z', qubit: Number.parseInt(match[1], 10) })
    }
    if (line.includes('.cx(')) {
      const match = line.match(/\.cx\((?:\w+\[)?(\d+)[\],\s]+(?:\w+\[)?(\d+)/)
      if (match) gates.push({ type: 'cx', qubit: Number.parseInt(match[1], 10), control: Number.parseInt(match[1], 10), target: Number.parseInt(match[2], 10) })
    }
    if (line.includes('.measure')) {
      const match = line.match(/\.measure\((?:\w+\[)?(\d+)/)
      if (match) gates.push({ type: 'measure', qubit: Number.parseInt(match[1], 10) })
    }
    
    // Cirq: cirq.H(q0), cirq.X(q[0])
    if (line.includes('cirq.H(')) {
      const match = line.match(/cirq\.H\((\w+)/)
      if (match) {
        const qubitMatch = match[1].match(/(\d+)/)
        gates.push({ type: 'h', qubit: qubitMatch ? Number.parseInt(qubitMatch[1], 10) : 0 })
      }
    }
    if (line.includes('cirq.X(')) {
      const match = line.match(/cirq\.X\((\w+)/)
      if (match) {
        const qubitMatch = match[1].match(/(\d+)/)
        gates.push({ type: 'x', qubit: qubitMatch ? Number.parseInt(qubitMatch[1], 10) : 0 })
      }
    }
    if (line.includes('cirq.CNOT(')) {
      const match = line.match(/cirq\.CNOT\((\w+),\s*(\w+)/)
      if (match) {
        const c = match[1].match(/(\d+)/)
        const t = match[2].match(/(\d+)/)
        gates.push({ type: 'cx', qubit: c ? Number.parseInt(c[1], 10) : 0, control: c ? Number.parseInt(c[1], 10) : 0, target: t ? Number.parseInt(t[1], 10) : 1 })
      }
    }
    
    // PennyLane: qml.Hadamard(wires=0)
    if (line.includes('qml.Hadamard(')) {
      const match = line.match(/qml\.Hadamard\(wires=(\d+)/)
      if (match) gates.push({ type: 'h', qubit: Number.parseInt(match[1], 10) })
    }
    if (line.includes('qml.PauliX(')) {
      const match = line.match(/qml\.PauliX\(wires=(\d+)/)
      if (match) gates.push({ type: 'x', qubit: Number.parseInt(match[1], 10) })
    }
    if (line.includes('qml.CNOT(')) {
      const match = line.match(/qml\.CNOT\(wires=\[(\d+),\s*(\d+)\]/)
      if (match) gates.push({ type: 'cx', qubit: Number.parseInt(match[1], 10), control: Number.parseInt(match[1], 10), target: Number.parseInt(match[2], 10) })
    }
  }
  
  return gates
}

/**
 * Main parser function - detects framework and parses accordingly
 */
export function parseCircuit(code: string): ParsedGate[] {
  if (!code || code.trim().length === 0) {
    return []
  }
  
  const framework = detectFramework(code)
  
  let gates: ParsedGate[] = []
  
  switch (framework) {
    case 'qiskit':
      gates = parseQiskit(code)
      break
    case 'cirq':
      gates = parseCirq(code)
      break
    case 'pennylane':
      gates = parsePennyLane(code)
      break
    default: {
      // Try all parsers and return the one with most gates
      const qiskitGates = parseQiskit(code)
      const cirqGates = parseCirq(code)
      const pennylaneGates = parsePennyLane(code)
      
      const results = [
        { framework: 'qiskit', gates: qiskitGates },
        { framework: 'cirq', gates: cirqGates },
        { framework: 'pennylane', gates: pennylaneGates }
      ]
      
      results.sort((a, b) => b.gates.length - a.gates.length)
      gates = results[0].gates
    }
  }
  
  // If comprehensive parsers didn't find anything, try the simple parser
  if (gates.length === 0) {
    gates = parseSimple(code)
  }
  
  // Assign proper timestamps based on circuit layers
  // Gates on different qubits that don't overlap get the same timestamp
  return assignTimestamps(gates)
}

/**
 * Gets all qubits that a gate operates on
 */
function getGateQubits(gate: ParsedGate): number[] {
  const qubits: number[] = []
  if (gate.qubit !== undefined) qubits.push(gate.qubit)
  if (gate.control !== undefined && !qubits.includes(gate.control)) qubits.push(gate.control)
  if (gate.target !== undefined && !qubits.includes(gate.target)) qubits.push(gate.target)
  if (gate.qubits) {
    for (const q of gate.qubits) {
      if (!qubits.includes(q)) qubits.push(q)
    }
  }
  return qubits
}

/**
 * Assigns proper timestamps to gates based on circuit layers
 * Gates on different qubits that don't overlap can be at the same timestamp
 */
function assignTimestamps(gates: ParsedGate[]): ParsedGate[] {
  if (gates.length === 0) return gates
  
  // Track the next available timestamp for each qubit
  const qubitNextTime: Map<number, number> = new Map()
  
  const result: ParsedGate[] = []
  
  for (const gate of gates) {
    const gateQubits = getGateQubits(gate)
    
    // Find the earliest timestamp where this gate can be placed
    // It must be >= the next available time for ALL qubits it uses
    let timestamp = 0
    for (const q of gateQubits) {
      const nextTime = qubitNextTime.get(q) || 0
      timestamp = Math.max(timestamp, nextTime)
    }
    
    // Update the next available time for all qubits this gate uses
    for (const q of gateQubits) {
      qubitNextTime.set(q, timestamp + 1)
    }
    
    result.push({
      ...gate,
      timestamp
    })
  }
  
  return result
}

/**
 * Calculates the number of qubits needed for a circuit
 */
export function calculateQubitCount(gates: ParsedGate[]): number {
  if (gates.length === 0) return 2 // Default to 2 qubits
  
  let maxQubit = 0
  
  for (const gate of gates) {
    if (gate.qubit !== undefined) {
      maxQubit = Math.max(maxQubit, gate.qubit)
    }
    if (gate.control !== undefined) {
      maxQubit = Math.max(maxQubit, gate.control)
    }
    if (gate.target !== undefined) {
      maxQubit = Math.max(maxQubit, gate.target)
    }
    if (gate.qubits) {
      for (const q of gate.qubits) {
        maxQubit = Math.max(maxQubit, q)
      }
    }
  }
  
  return Math.max(2, maxQubit + 1) // At least 2 qubits, or max + 1
}

/**
 * Response type from the backend parse API
 */
interface ParseApiResponse {
  success: boolean
  gates?: ParsedGate[]
  qubits?: number
  error?: string
  framework?: string
}

/**
 * POST to the backend AST parser. Must use the backend API base: a relative
 * `/api/converter/parse` hits the Next.js server (404), which silently forced
 * the regex fallback for every diagram.
 */
/**
 * The backend (Pydantic) serialises absent optional fields as `null`, but the
 * visualisers test `!== undefined` (e.g. `gate.angle.toFixed`), so drop nulls.
 */
function normalizeBackendGates(gates: ParsedGate[]): ParsedGate[] {
  return gates.map((gate) => {
    const clean: Record<string, unknown> = {}
    for (const [key, value] of Object.entries(gate)) {
      if (value !== null && value !== undefined) clean[key] = value
    }
    return clean as unknown as ParsedGate
  })
}

async function requestBackendParse(code: string, framework: string): Promise<Response> {
  const apiBase = await getApiBase()
  // Send the session token when we have one: the backend rate-limits per user
  // when authenticated, otherwise per IP (shared by everyone behind one NAT).
  const token = useAuthStore.getState().token
  return fetch(`${apiBase}/api/converter/parse`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      code,
      framework,
      qasm_version: '3.0',
      style: 'classic'
    })
  })
}

/**
 * Async circuit parser that uses backend AST parsing with regex fallback.
 * 
 * Calls the backend /api/converter/parse endpoint which uses Python's AST
 * module for accurate parsing. Falls back to regex parsing if the backend
 * is unavailable.
 * 
 * @param code - The quantum circuit source code
 * @returns Promise resolving to parsed gates array
 */
export async function parseCircuitAsync(code: string): Promise<ParsedGate[]> {
  if (!code || code.trim().length === 0) {
    return []
  }
  
  const framework = detectFramework(code)
  
  // If framework is unknown, use regex fallback directly
  if (framework === 'unknown') {
    return parseCircuit(code)
  }
  
  try {
    const response = await requestBackendParse(code, framework)
    
    if (!response.ok) {
      // Backend unavailable or error, fall back to regex
      console.warn('Circuit parse API returned error, using regex fallback')
      return parseCircuit(code)
    }
    
    const data: ParseApiResponse = await response.json()
    
    if (data.success && data.gates && data.gates.length > 0) {
      // Backend parsing succeeded
      return normalizeBackendGates(data.gates)
    }
    
    // Backend returned no gates or error, fall back to regex
    if (data.error) {
      console.warn('Circuit parse API error:', data.error, '- using regex fallback')
    }
    return parseCircuit(code)
    
  } catch (error) {
    // Network error or other issue, fall back to regex
    console.warn('Circuit parse API unavailable, using regex fallback:', error)
    return parseCircuit(code)
  }
}

/**
 * Result type for async parsing with qubit count
 */
export interface ParseResult {
  gates: ParsedGate[]
  qubits: number
}

/**
 * Async circuit parser that returns both gates and qubit count.
 * Uses backend AST parsing with regex fallback.
 * 
 * @param code - The quantum circuit source code
 * @returns Promise resolving to gates and qubit count
 */
export async function parseCircuitWithCountAsync(code: string): Promise<ParseResult> {
  if (!code || code.trim().length === 0) {
    return { gates: [], qubits: 2 }
  }
  
  const framework = detectFramework(code)
  
  // If framework is unknown, use regex fallback directly
  if (framework === 'unknown') {
    const gates = parseCircuit(code)
    return { gates, qubits: calculateQubitCount(gates) }
  }
  
  try {
    const response = await requestBackendParse(code, framework)
    
    if (!response.ok) {
      const gates = parseCircuit(code)
      return { gates, qubits: calculateQubitCount(gates) }
    }
    
    const data: ParseApiResponse = await response.json()
    
    if (data.success && data.gates && data.gates.length > 0) {
      // Backend parsing succeeded - use backend's qubit count if available
      const gates = normalizeBackendGates(data.gates)
      const qubits = data.qubits ?? calculateQubitCount(gates)
      return { gates, qubits }
    }
    
    // Fall back to regex
    const gates = parseCircuit(code)
    return { gates, qubits: calculateQubitCount(gates) }
    
  } catch {
    // Network error, fall back to regex
    const gates = parseCircuit(code)
    return { gates, qubits: calculateQubitCount(gates) }
  }
}
