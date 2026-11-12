import type { RawGate } from './circuitLayout'

/**
 * Circuits shown on the homepage, with real measurement counts.
 *
 * Counts were captured on 2026-11-12 from the QCanvas simulator
 * (POST /api/simulator/execute-qsim, backend "qiskit", 1,024 shots, no seed)
 * by running the equivalent OpenQASM 3.0 for each gate list below.
 * Bitstrings are q0 first, as in QCanvas results.
 */

export interface SiteCircuit {
  id: string
  name: string
  qubits: number
  gates: RawGate[]
  /** Real counts from one 1,024-shot run. */
  counts: Record<string, number>
  blurb: string
  takeaway: string
}

const m = (q: number): RawGate => ({ type: 'measure', qubit: q })

export const SITE_CIRCUITS: SiteCircuit[] = [
  {
    id: 'bell',
    name: 'Bell state',
    qubits: 2,
    gates: [
      { type: 'h', qubit: 0 },
      { type: 'cx', qubit: 0, control: 0, target: 1 },
      m(0),
      m(1),
    ],
    counts: { '00': 522, '11': 502 },
    blurb: 'Two qubits, one Hadamard and one CNOT.',
    takeaway:
      'Ideal is 50% each for |00⟩ and |11⟩. The run returned 522 and 502: that gap is shot noise, not an error. |01⟩ and |10⟩ never appear because the qubits are entangled.',
  },
  {
    id: 'ghz',
    name: 'GHZ',
    qubits: 3,
    gates: [
      { type: 'h', qubit: 0 },
      { type: 'cx', qubit: 0, control: 0, target: 1 },
      { type: 'cx', qubit: 1, control: 1, target: 2 },
      m(0),
      m(1),
      m(2),
    ],
    counts: { '000': 494, '111': 530 },
    blurb: 'The Bell pair extended to three qubits.',
    takeaway:
      'Three qubits share a single coin flip: only |000⟩ and |111⟩ ever appear, about half each (494 and 530 here).',
  },
  {
    id: 'grover',
    name: 'Grover search',
    qubits: 2,
    gates: [
      { type: 'h', qubit: 0 },
      { type: 'h', qubit: 1 },
      { type: 'cz', qubit: 0, control: 0, target: 1 },
      { type: 'h', qubit: 0 },
      { type: 'h', qubit: 1 },
      { type: 'x', qubit: 0 },
      { type: 'x', qubit: 1 },
      { type: 'cz', qubit: 0, control: 0, target: 1 },
      { type: 'x', qubit: 0 },
      { type: 'x', qubit: 1 },
      { type: 'h', qubit: 0 },
      { type: 'h', qubit: 1 },
      m(0),
      m(1),
    ],
    counts: { '11': 1024 },
    blurb: 'An oracle marks |11⟩, a diffusion step amplifies it.',
    takeaway:
      'Watch the bars: after the oracle all four states are still 25%, the marked one has only flipped sign. The diffusion step turns that sign into certainty: 1,024 of 1,024 shots.',
  },
  {
    id: 'qft',
    name: 'Fourier transform',
    qubits: 3,
    gates: [
      { type: 'x', qubit: 0 },
      { type: 'x', qubit: 2 },
      { type: 'h', qubit: 0 },
      { type: 'cp', qubit: 1, qubits: [1, 0], angle: Math.PI / 2 },
      { type: 'cp', qubit: 2, qubits: [2, 0], angle: Math.PI / 4 },
      { type: 'h', qubit: 1 },
      { type: 'cp', qubit: 2, qubits: [2, 1], angle: Math.PI / 2 },
      { type: 'h', qubit: 2 },
      { type: 'swap', qubit: 0, control: 0, target: 2 },
      m(0),
      m(1),
      m(2),
    ],
    counts: { '000': 119, '001': 129, '010': 140, '011': 149, '100': 134, '101': 108, '110': 136, '111': 109 },
    blurb: 'The quantum Fourier transform of |101⟩.',
    takeaway:
      'Every outcome is equally likely, so the counts look like noise. The answer lives in the phases, which no histogram can show: that is why QFT is used inside algorithms, not read out directly.',
  },
]

// ---------------------------------------------------------------------------
// Tiny exact simulator for the step-through view (at most a few qubits).
// ---------------------------------------------------------------------------

type C = [number, number]
const mul = (a: C, b: C): C => [a[0] * b[0] - a[1] * b[1], a[0] * b[1] + a[1] * b[0]]
const add = (a: C, b: C): C => [a[0] + b[0], a[1] + b[1]]
const S2 = Math.SQRT1_2

const ONE_QUBIT: Record<string, [C, C, C, C]> = {
  h: [[S2, 0], [S2, 0], [S2, 0], [-S2, 0]],
  x: [[0, 0], [1, 0], [1, 0], [0, 0]],
  z: [[1, 0], [0, 0], [0, 0], [-1, 0]],
  s: [[1, 0], [0, 0], [0, 0], [0, 1]],
  t: [[1, 0], [0, 0], [0, 0], [S2, S2]],
}

/** Probabilities (q0-first bitstrings) after applying `gates` in order. */
export function probabilities(n: number, gates: RawGate[]): Record<string, number> {
  const dim = 1 << n
  let re = new Float64Array(dim)
  let im = new Float64Array(dim)
  re[0] = 1
  const operands = (g: RawGate) =>
    g.qubits?.length ? g.qubits : g.control !== undefined && g.target !== undefined ? [g.control, g.target] : [g.qubit]

  for (const g of gates) {
    const t = g.type.toLowerCase()
    const qs = operands(g)
    if (t === 'measure' || t === 'barrier') continue
    if (ONE_QUBIT[t]) {
      const [a, b, c, d] = ONE_QUBIT[t]
      const bit = 1 << qs[0]
      for (let i = 0; i < dim; i++) {
        if (i & bit) continue
        const j = i | bit
        const v0: C = [re[i], im[i]]
        const v1: C = [re[j], im[j]]
        const n0 = add(mul(a, v0), mul(b, v1))
        const n1 = add(mul(c, v0), mul(d, v1))
        re[i] = n0[0]; im[i] = n0[1]; re[j] = n1[0]; im[j] = n1[1]
      }
    } else if (t === 'cx') {
      const [c, tg] = qs
      const nr = re.slice(); const ni = im.slice()
      for (let i = 0; i < dim; i++) if (i & (1 << c)) { const j = i ^ (1 << tg); nr[i] = re[j]; ni[i] = im[j] }
      re = nr; im = ni
    } else if (t === 'cz' || t === 'cp') {
      const [a, b] = qs
      const th = t === 'cz' ? Math.PI : g.angle ?? 0
      const ph: C = [Math.cos(th), Math.sin(th)]
      for (let i = 0; i < dim; i++) {
        if (i & (1 << a) && i & (1 << b)) { const v = mul(ph, [re[i], im[i]]); re[i] = v[0]; im[i] = v[1] }
      }
    } else if (t === 'swap') {
      const [a, b] = qs
      const nr = re.slice(); const ni = im.slice()
      for (let i = 0; i < dim; i++) {
        const ba = (i >> a) & 1, bb = (i >> b) & 1
        if (ba !== bb) { const j = i ^ (1 << a) ^ (1 << b); nr[i] = re[j]; ni[i] = im[j] }
      }
      re = nr; im = ni
    }
  }

  const out: Record<string, number> = {}
  for (let i = 0; i < dim; i++) {
    let key = ''
    for (let q = 0; q < n; q++) key += (i >> q) & 1
    out[key] = re[i] * re[i] + im[i] * im[i]
  }
  return out
}
