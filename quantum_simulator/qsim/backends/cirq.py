import numpy as np
from typing import Any, Dict, Optional
from .base import BaseBackend

_ALL_QUBITS_KEY = "__qsim_all_qubits__"


class CirqBackend(BaseBackend):
    """Backend for Cirq circuits."""

    def __init__(self, simulator: str = "simulator"):
        """
        Args:
            simulator: 'simulator' for standard or 'density_matrix_simulator'
        """
        import cirq
        self.cirq = cirq
        self.simulator_kind = simulator

    def _make_simulator(self, seed: Optional[int]):
        if self.simulator_kind == "density_matrix_simulator":
            return self.cirq.DensityMatrixSimulator(seed=seed)
        return self.cirq.Simulator(seed=seed)

    @staticmethod
    def _last_instance(records, key):
        # records[key] has shape (repetitions, instances, n_qubits); the value a
        # classical bit holds at the end of the program is the LAST write.
        arr = np.asarray(records[key])
        if arr.ndim == 3:
            return arr[:, -1, 0]
        if arr.ndim == 2:
            return arr[:, 0]
        return arr.reshape(-1)

    def run(self, circuit: Any, shots: int = 1024, spec: Optional[Dict[str, Any]] = None,
            seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Run Cirq circuit simulation.
        Args:
            circuit: cirq.Circuit from visitor
            shots: Number of shots (0 for exact statevector)
        """
        cirq = self.cirq
        simulator = self._make_simulator(seed)

        if spec and spec.get('qubits') is not None:
            qubits = list(spec['qubits'])
        else:
            qubits = sorted(circuit.all_qubits())
        n_qubits = len(qubits)

        if shots > 0:
            if spec is not None and spec.get('measured'):
                result = simulator.run(circuit, repetitions=shots)
                records = getattr(result, 'records', None) or {
                    k: np.asarray(v)[:, None, :] for k, v in result.measurements.items()
                }
                columns = []
                for key, default in spec['clbits']:
                    if key in records:
                        columns.append(self._last_instance(records, key))
                    else:
                        columns.append(np.full(shots, int(default), dtype=np.int64))
                bits = np.stack(columns, axis=1) if columns else np.zeros((shots, 0), dtype=np.int64)
            elif spec is not None:
                # Nothing measured: sample every declared qubit (q[0] first).
                sampled = circuit.copy()
                if qubits:
                    sampled.append(cirq.measure(*qubits, key=_ALL_QUBITS_KEY))
                    result = simulator.run(sampled, repetitions=shots)
                    bits = np.asarray(result.measurements[_ALL_QUBITS_KEY])
                else:
                    bits = np.zeros((shots, 0), dtype=np.int64)
            else:
                # Legacy path (no spec): concatenate measurement keys in circuit order.
                result = simulator.run(circuit, repetitions=shots)
                if result.measurements:
                    bits = np.concatenate([np.asarray(v) for v in result.measurements.values()], axis=1)
                else:
                    sampled = circuit.copy()
                    sampled.append(cirq.measure(*qubits, key=_ALL_QUBITS_KEY))
                    bits = np.asarray(simulator.run(sampled, repetitions=shots).measurements[_ALL_QUBITS_KEY])

            counts = self._bit_matrix_to_counts(bits)
            probs = {k: v / shots for k, v in counts.items()}
            return {
                'counts': counts,
                'probs': probs,
                'metadata': {'backend': 'cirq', 'shots': shots, 'seed': seed}
            }

        # Exact statevector mode (unitary part only)
        unitary_part = cirq.drop_terminal_measurements(circuit) if hasattr(cirq, 'drop_terminal_measurements') else circuit
        result = simulator.simulate(unitary_part, qubit_order=qubits)
        state_vector = result.final_state_vector
        probs_array = np.abs(state_vector) ** 2
        probs = {}
        for idx, prob in enumerate(probs_array):
            if prob > 1e-10:
                probs[format(idx, f'0{n_qubits}b')] = float(prob)
        return {
            'counts': {},
            'probs': probs,
            'statevector': state_vector,
            'metadata': {'backend': 'cirq', 'shots': 0}
        }
