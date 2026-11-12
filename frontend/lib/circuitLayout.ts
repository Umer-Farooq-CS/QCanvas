/**
 * Shared circuit layout for the 2D (SVG) and 3D (three.js) diagrams.
 *
 * Takes the gate list produced by the backend parser (or the regex fallback)
 * and turns it into drawable operations placed in columns. Layout is computed
 * here, not trusted from backend timestamps, because a controlled gate's
 * vertical line occupies every qubit between its control and target: placing
 * another gate in that span (e.g. cx(0,3) next to crx(1,2)) draws them on top
 * of each other.
 */

export interface RawGate {
  type: string
  qubit: number
  control?: number
  target?: number
  angle?: number
  name?: string
  qubits?: number[]
  timestamp?: number
}

export type OpKind = 'single' | 'controlled' | 'swap' | 'multi' | 'measure' | 'reset' | 'barrier'

/**
 * Visual role: drives colour. Single-qubit gates, rotations, entangling
 * (multi-qubit) operations and measurement each get one colour; reset and
 * barriers stay neutral.
 */
export type GateFamily = 'clifford' | 'rotation' | 'entangle' | 'measure' | 'other'

export interface LayoutOp {
  id: number
  kind: OpKind
  /** Base gate name without control prefixes, e.g. "x" for ccx, "rx" for crx. */
  base: string
  /** Short label drawn on the gate, e.g. "H", "RX", "S†", "√X". */
  label: string
  /** Formatted angle, e.g. "π/2", "-π/4", "0.73". */
  angleLabel?: string
  angle?: number
  controls: number[]
  targets: number[]
  /** All qubits touched (controls + targets), sorted. */
  qubits: number[]
  column: number
  family: GateFamily
  /** Original gate type as written, for tooltips. */
  sourceType: string
}

export interface CircuitLayout {
  ops: LayoutOp[]
  qubits: number
  columns: number
}

/** Most wires the diagram will draw (the simulator caps far lower). */
export const MAX_DRAWN_QUBITS = 256

const CLIFFORD = new Set(['h', 'x', 'y', 'z', 's', 'sdg', 't', 'tdg', 'sx', 'sxdg', 'id', 'i'])
const ROTATION = new Set(['rx', 'ry', 'rz', 'p', 'phase', 'u', 'u1', 'u2', 'u3', 'gphase', 'r', 'rot'])
/** Base gates a "c"-prefix can control (crx -> rx, ccx -> x, cswap -> swap). */
const CONTROLLABLE = new Set([...CLIFFORD, ...ROTATION, 'swap'])

const LABELS: Record<string, string> = {
  h: 'H', x: 'X', y: 'Y', z: 'Z', s: 'S', sdg: 'S†', t: 'T', tdg: 'T†',
  sx: '√X', sxdg: '√X†', id: 'I', i: 'I',
  rx: 'RX', ry: 'RY', rz: 'RZ', p: 'P', phase: 'P', u: 'U', u1: 'U1', u2: 'U2', u3: 'U3',
  gphase: 'GP', r: 'R', rot: 'Rot',
}

const ALIASES: Record<string, string> = {
  cnot: 'cx', hadamard: 'h', 'pauli-x': 'x', 'pauli-y': 'y', 'pauli-z': 'z',
  paulix: 'x', pauliy: 'y', pauliz: 'z', phaseshift: 'p', measurement: 'measure',
  toffoli: 'ccx', fredkin: 'cswap', cphase: 'cp', cu1: 'cp',
}

/** Format radians as a multiple of π when it is a clean fraction. */
export function formatAngle(angle: number): string {
  if (!Number.isFinite(angle)) return String(angle)
  const ratio = angle / Math.PI
  for (const den of [1, 2, 3, 4, 6, 8, 12, 16]) {
    const num = Math.round(ratio * den)
    if (num !== 0 && Math.abs(ratio * den - num) < 1e-6) {
      const sign = num < 0 ? '-' : ''
      const n = Math.abs(num)
      const top = n === 1 ? 'π' : `${n}π`
      return den === 1 ? `${sign}${top}` : `${sign}${top}/${den}`
    }
  }
  if (Math.abs(angle) < 1e-9) return '0'
  return Number(angle.toFixed(2)).toString()
}

function familyOf(base: string, kind: OpKind): GateFamily {
  if (kind === 'measure') return 'measure'
  if (kind === 'reset' || kind === 'barrier') return 'other'
  if (kind === 'controlled' || kind === 'swap' || kind === 'multi') return 'entangle'
  if (ROTATION.has(base)) return 'rotation'
  if (CLIFFORD.has(base)) return 'clifford'
  return 'entangle'
}

function labelOf(base: string): string {
  return LABELS[base] ?? base.toUpperCase().slice(0, 4)
}

/** Split "ccx" -> {controls: 2, base: "x"}, "crx" -> {1, "rx"}, "mcx" -> {-1, "x"}. */
function splitControls(type: string): { prefix: number; base: string } {
  if (type.startsWith('mc') && CONTROLLABLE.has(type.slice(2))) return { prefix: -1, base: type.slice(2) }
  let i = 0
  while (type[i] === 'c' && i < type.length - 1) i++
  const base = type.slice(i)
  if (i > 0 && CONTROLLABLE.has(base)) return { prefix: i, base }
  return { prefix: 0, base: type }
}

function normalize(g: RawGate, id: number, nQubits: number): Omit<LayoutOp, 'column'> | null {
  const rawType = (g.type || '').trim().toLowerCase()
  const type = ALIASES[rawType] ?? rawType
  const angle = typeof g.angle === 'number' ? g.angle : undefined
  const angleLabel = angle !== undefined ? formatAngle(angle) : undefined
  const listed = Array.isArray(g.qubits) && g.qubits.length ? g.qubits : undefined

  const make = (kind: OpKind, base: string, controls: number[], targets: number[]) => {
    const qubits = Array.from(new Set([...controls, ...targets])).sort((a, b) => a - b)
    return {
      id, kind, base, label: labelOf(base), angle, angleLabel,
      controls, targets, qubits, family: familyOf(base, kind), sourceType: g.type,
    }
  }

  if (type === 'measure') return make('measure', 'measure', [], [g.qubit])
  if (type === 'reset') return make('reset', 'reset', [], [g.qubit])
  if (type === 'barrier') {
    const qs = listed ?? Array.from({ length: nQubits }, (_, i) => i)
    return make('barrier', 'barrier', [], qs)
  }

  // Ordered operand list: explicit qubits[], else control/target, else qubit.
  const operands: number[] = listed
    ? listed
    : g.control !== undefined && g.target !== undefined
      ? [g.control, g.target]
      : [g.qubit]

  if (type === 'swap' && operands.length >= 2) return make('swap', 'swap', [], operands.slice(0, 2))

  const { prefix, base } = splitControls(type)
  if (prefix !== 0 && operands.length >= 2) {
    const nTargets = base === 'swap' ? 2 : 1
    const nControls = prefix === -1 ? operands.length - nTargets : Math.min(prefix, operands.length - nTargets)
    if (nControls >= 1) {
      const controls = operands.slice(0, nControls)
      const targets = operands.slice(nControls, nControls + nTargets)
      return make(base === 'swap' ? 'swap' : 'controlled', base, controls, targets)
    }
  }

  // Uncontrolled gate on several qubits (rxx, iswap, custom): one tall box.
  if (operands.length >= 2) {
    const op = make('multi', type, [], operands)
    return { ...op, label: type.toUpperCase().slice(0, 5) }
  }
  return make('single', type, [], operands)
}

/**
 * Greedy column assignment. Each op occupies every qubit from its lowest to its
 * highest operand (the connecting line passes through them), so nothing can be
 * drawn on top of a control line.
 */
export function layoutCircuit(gates: RawGate[], qubitHint = 0): CircuitLayout {
  const maxOperand = gates.reduce((m, g) => {
    const qs = [g.qubit, g.control, g.target, ...(g.qubits ?? [])].filter(
      (q): q is number => typeof q === 'number' && Number.isFinite(q),
    )
    return Math.max(m, ...qs)
  }, -1)
  // Indices come from user code: a typo like cx(0, 10**9) must not allocate a
  // billion-entry array and freeze the tab. Gates past the cap are not drawn.
  const nQubits = Math.min(Math.max(qubitHint, maxOperand + 1, 1), MAX_DRAWN_QUBITS)

  const next = new Array<number>(nQubits).fill(0)
  const ops: LayoutOp[] = []
  gates.forEach((g, i) => {
    const op = normalize(g, i, nQubits)
    if (!op || op.qubits.length === 0) return
    if (op.qubits[0] < 0 || op.qubits[op.qubits.length - 1] >= nQubits) return
    const lo = Math.max(0, op.qubits[0])
    const hi = Math.min(nQubits - 1, op.qubits[op.qubits.length - 1])
    let column = 0
    for (let q = lo; q <= hi; q++) column = Math.max(column, next[q])
    for (let q = lo; q <= hi; q++) next[q] = column + 1
    ops.push({ ...op, column })
  })

  // Line final measurements up in one column at the end (as textbook diagrams
  // do). Moving a qubit's last operation later can never collide with
  // anything, because nothing comes after it on that wire.
  const lastOnQubit = new Map<number, LayoutOp>()
  for (const op of ops) {
    if (op.kind === 'barrier') continue
    for (const q of op.qubits) {
      const prev = lastOnQubit.get(q)
      if (!prev || prev.column <= op.column) lastOnQubit.set(q, op)
    }
  }
  const finalMeasures = Array.from(new Set(lastOnQubit.values())).filter((o) => o.kind === 'measure')
  if (finalMeasures.length > 1) {
    const col = Math.max(...finalMeasures.map((o) => o.column))
    for (const o of finalMeasures) o.column = col
  }

  const columns = ops.reduce((m, o) => Math.max(m, o.column + 1), 0)
  return { ops, qubits: nQubits, columns }
}

/** Human-readable one-liner for tooltips and screen readers. */
export function describeOp(op: LayoutOp): string {
  const q = (n: number) => `q${n}`
  const angle = op.angleLabel ? `(${op.angleLabel})` : ''
  switch (op.kind) {
    case 'measure':
      return `Measure ${q(op.targets[0])}`
    case 'reset':
      return `Reset ${q(op.targets[0])} to |0⟩`
    case 'barrier':
      return `Barrier on ${op.targets.map(q).join(', ')}`
    case 'swap':
      return op.controls.length
        ? `Controlled SWAP: control ${op.controls.map(q).join(', ')}, swap ${op.targets.map(q).join(' ↔ ')}`
        : `SWAP ${op.targets.map(q).join(' ↔ ')}`
    case 'controlled':
      return `${'C'.repeat(op.controls.length)}${op.label}${angle}: control ${op.controls.map(q).join(', ')}, target ${op.targets.map(q).join(', ')}`
    case 'multi':
      return `${op.label}${angle} on ${op.targets.map(q).join(', ')}`
    default:
      return `${op.label}${angle} on ${q(op.targets[0])}`
  }
}
