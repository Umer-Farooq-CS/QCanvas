from typing import Any, Dict, Optional
import numpy as np
from .base import BaseBackend
from qiskit_aer import Aer

_ALL_QUBITS_REG = "qsim_all_qubits"


class QiskitBackend(BaseBackend):
    """Backend for Qiskit circuits."""

    def __init__(self, backend_name: str = "aer_simulator"):
        """
        Args:
            backend_name: Qiskit backend (e.g., 'aer_simulator', 'statevector_simulator')
        """
        self.backend_name = backend_name
        self.Aer = Aer

    @staticmethod
    def _register_values(key: str, cregs) -> Dict[str, str]:
        """
        Split a Qiskit counts key into per-register bit strings.

        Qiskit prints registers in REVERSE order of ``qc.cregs`` separated by
        spaces, each register most-significant bit first.  Returns
        {reg_name: bits with bit 0 first}.
        """
        parts = key.split()
        if len(parts) != len(cregs):
            # Single register (no spaces) or unexpected format: slice manually.
            flat = key.replace(" ", "")
            parts, pos = [], 0
            for creg in reversed(cregs):
                parts.append(flat[pos:pos + creg.size])
                pos += creg.size
        out = {}
        for creg, part in zip(reversed(cregs), parts):
            out[creg.name] = part[::-1]
        return out

    def run(self, circuit: Any, shots: int = 1024, spec: Optional[Dict[str, Any]] = None,
            seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Run Qiskit circuit simulation.
        Args:
            circuit: qiskit.QuantumCircuit from visitor
            shots: Number of shots (0 for statevector)
        """
        from qiskit import transpile, ClassicalRegister

        if shots > 0:
            backend = self.Aer.get_backend('aer_simulator')
            qc = circuit.copy()
            run_kwargs = {'shots': shots}
            if seed is not None:
                run_kwargs['seed_simulator'] = seed

            measured = (spec.get('measured') if spec is not None
                        else any(instr.operation.name == 'measure' for instr in qc.data))

            if not measured:
                # Nothing measured: sample every qubit (q[0] first).
                qubits = list(spec['qubits']) if spec is not None else list(qc.qubits)
                reg = ClassicalRegister(len(qubits), _ALL_QUBITS_REG)
                qc.add_register(reg)
                for i, q in enumerate(qubits):
                    qc.measure(q, reg[i])
                wanted = [(_ALL_QUBITS_REG, i) for i in range(len(qubits))]
            else:
                clbits = list(spec['clbits']) if spec is not None else list(qc.clbits)
                wanted = []
                for clbit in clbits:
                    loc = qc.find_bit(clbit)
                    reg, idx = loc.registers[0]
                    wanted.append((reg.name, idx))

            qc_transpiled = transpile(qc, backend, optimization_level=0)
            result = backend.run(qc_transpiled, **run_kwargs).result()
            counts_raw = result.get_counts()

            counts: Dict[str, int] = {}
            for key, n in counts_raw.items():
                regs = self._register_values(key, qc.cregs)
                bitstring = ''.join(regs[name][idx] for name, idx in wanted)
                counts[bitstring] = counts.get(bitstring, 0) + n

            probs = {k: v / shots for k, v in counts.items()}
            return {
                'counts': counts,
                'probs': probs,
                'metadata': {'backend': 'qiskit', 'simulator': self.backend_name, 'shots': shots, 'seed': seed}
            }

        # Exact statevector mode
        # ('statevector_simulator' already saves the state; adding save_statevector()
        #  there fails with "Duplicate key statevector", so use aer_simulator.)
        backend = self.Aer.get_backend('aer_simulator')
        qc = circuit.copy()
        qc.remove_final_measurements(inplace=True)
        qc.save_statevector()
        qc_transpiled = transpile(qc, backend, optimization_level=0)
        result = backend.run(qc_transpiled).result()
        statevector = result.get_statevector()

        n_qubits = circuit.num_qubits
        probs_array = np.abs(statevector.data) ** 2
        probs = {}
        for idx, prob in enumerate(probs_array):
            if prob > 1e-10:
                bitstring = format(idx, f'0{n_qubits}b')[::-1]  # q[0] first
                probs[bitstring] = float(prob)
        return {
            'counts': {},
            'probs': probs,
            'statevector': statevector.data,
            'metadata': {'backend': 'qiskit', 'simulator': 'statevector', 'shots': 0}
        }
