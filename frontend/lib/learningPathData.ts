/**
 * Gate lists for the homepage learning path thumbnails.
 *
 * Captured from the QCanvas parser (POST /api/converter/parse) for the shipped
 * templates in lib/fileTemplates.ts, with null fields and `timestamp` dropped.
 * To regenerate: POST {"code": <template content>, "framework": "qiskit" |
 * "pennylane"} to http://127.0.0.1:8000/api/converter/parse for each filename
 * below and paste the returned `qubits` and `gates`.
 *
 * Note: the parser reads gate calls, so Python-level `if` blocks (the
 * teleportation corrections) are not part of the diagram.
 */
import type { RawGate } from '@/lib/circuitLayout'

export interface CapturedCircuit {
  qubits: number
  gates: RawGate[]
}

/** bell_state_qiskit.py */
export const bellState: CapturedCircuit = {
  qubits: 2,
  gates: [
    { type: "h", qubit: 0 },
    { type: "cx", qubit: 0, control: 0, target: 1 },
    { type: "measure", qubit: 0 },
    { type: "measure", qubit: 1 },
  ],
}

/** deutsch_jozsa_qiskit.py */
export const deutschJozsa: CapturedCircuit = {
  qubits: 4,
  gates: [
    { type: "x", qubit: 3 },
    { type: "h", qubit: 0 },
    { type: "h", qubit: 1 },
    { type: "h", qubit: 2 },
    { type: "h", qubit: 3 },
    { type: "cx", qubit: 0, control: 0, target: 3 },
    { type: "cx", qubit: 1, control: 1, target: 3 },
    { type: "cx", qubit: 2, control: 2, target: 3 },
    { type: "h", qubit: 0 },
    { type: "h", qubit: 1 },
    { type: "h", qubit: 2 },
    { type: "measure", qubit: 0 },
    { type: "measure", qubit: 1 },
    { type: "measure", qubit: 2 },
  ],
}

/** quantum_teleportation_qiskit.py */
export const teleportation: CapturedCircuit = {
  qubits: 3,
  gates: [
    { type: "h", qubit: 0 },
    { type: "h", qubit: 1 },
    { type: "cx", qubit: 1, control: 1, target: 2 },
    { type: "cx", qubit: 0, control: 0, target: 1 },
    { type: "h", qubit: 0 },
    { type: "measure", qubit: 0 },
    { type: "measure", qubit: 1 },
    { type: "measure", qubit: 2 },
  ],
}

/** grover_search_qiskit.py */
export const grover: CapturedCircuit = {
  qubits: 2,
  gates: [
    { type: "h", qubit: 0 },
    { type: "h", qubit: 1 },
    { type: "cz", qubit: 0, control: 0, target: 1 },
    { type: "h", qubit: 0 },
    { type: "h", qubit: 1 },
    { type: "x", qubit: 0 },
    { type: "x", qubit: 1 },
    { type: "cz", qubit: 0, control: 0, target: 1 },
    { type: "x", qubit: 0 },
    { type: "x", qubit: 1 },
    { type: "h", qubit: 0 },
    { type: "h", qubit: 1 },
    { type: "measure", qubit: 0 },
    { type: "measure", qubit: 1 },
  ],
}

/** qft_qiskit.py */
export const qft: CapturedCircuit = {
  qubits: 3,
  gates: [
    { type: "x", qubit: 0 },
    { type: "h", qubit: 2 },
    { type: "cp", qubit: 1, angle: 1.5707963267948966, qubits: [1, 2] },
    { type: "cp", qubit: 0, angle: 0.7853981633974483, qubits: [0, 2] },
    { type: "h", qubit: 1 },
    { type: "cp", qubit: 0, angle: 1.5707963267948966, qubits: [0, 1] },
    { type: "h", qubit: 0 },
    { type: "swap", qubit: 0, control: 0, target: 2 },
    { type: "measure", qubit: 0 },
    { type: "measure", qubit: 1 },
    { type: "measure", qubit: 2 },
  ],
}

/** variational_ansatz_pennylane.py */
export const variational: CapturedCircuit = {
  qubits: 2,
  gates: [
    { type: "ry", qubit: 0, angle: 0.3 },
    { type: "ry", qubit: 1, angle: -0.7 },
    { type: "cx", qubit: 0, control: 0, target: 1 },
    { type: "rz", qubit: 0, angle: 0.2 },
    { type: "rz", qubit: 1, angle: 1.1 },
  ],
}
