import pennylane as qml
import numpy as np
from typing import Any, Dict, Optional
from .base import BaseBackend


def _is_measurement_value(obj) -> bool:
    try:
        from pennylane.measurements import MeasurementValue
        return isinstance(obj, MeasurementValue)
    except Exception:  # pragma: no cover - very old PennyLane
        return False


class PennylaneBackend(BaseBackend):
    """
    PennyLane-based concrete backend for executing quantum tapes.

    This uses PennyLane's 'default.qubit' or 'lightning.qubit' simulator
    to execute the compiled circuit (qml.QuantumTape).
    """

    def _get_dev_name(self) -> str:
        """Helper to check for faster simulator availability."""
        try:
            # Prefer lightning for speed if available
            qml.device("lightning.qubit", wires=1)
            return "lightning.qubit"
        except Exception:
            # Fallback to default if lightning is not installed / cannot load.
            # (qml.QuantumDeviceError does not exist in PennyLane >= 0.40, so
            # catching it would itself raise AttributeError.)
            return "default.qubit"

    @staticmethod
    def _has_mid_circuit_ops(operations) -> bool:
        for op in operations:
            name = type(op).__name__
            if name in ("MidMeasureMP", "Conditional"):
                return True
        return False

    @staticmethod
    def _split_terminal_measurements(operations):
        """
        Remove mid-circuit measurements that are equivalent to a final measurement:
        no later operation touches the wire and no condition reads the result.
        Returns (remaining operations, {id(MidMeasureMP): wire}).
        """
        referenced = set()
        for op in operations:
            if type(op).__name__ == "Conditional":
                for mp in getattr(op.meas_val, 'measurements', []):
                    referenced.add(id(mp))
        terminal = {}
        for idx, op in enumerate(operations):
            if type(op).__name__ != "MidMeasureMP":
                continue
            if getattr(op, 'reset', False) or getattr(op, 'postselect', None) is not None:
                continue
            if id(op) in referenced or len(op.wires) != 1:
                continue
            wire = op.wires[0]
            if any(wire in later.wires for later in operations[idx + 1:]):
                continue
            terminal[id(op)] = wire
        remaining = [op for op in operations if id(op) not in terminal]
        return remaining, terminal

    def run(self, tape: qml.tape.QuantumTape, shots: int = 1024, spec: Optional[Dict[str, Any]] = None,
            seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Run simulation on PennyLane tape.

        Args:
            tape: The quantum program as a qml.QuantumTape object.
            shots: Number of shots for sampling. Use 0 for exact probabilities.

        Returns:
            A dictionary containing counts and probabilities.
        """
        operations = list(tape.operations)
        if spec is not None and spec.get('qubits') is not None:
            wires = list(spec['qubits'])
        else:
            wires = list(tape.wires)
        num_qubits = len(wires)

        if num_qubits == 0 and not operations:
            return {'counts': {}, 'probs': {}, 'metadata': {'shots': shots, 'device': 'None'}}

        # Measurements that nothing depends on afterwards are just end-of-circuit
        # samples; only genuine mid-circuit measurements need deferral (which costs
        # one extra wire each -- 18 measured qubits would otherwise need 36 wires).
        operations, terminal_wire = self._split_terminal_measurements(operations)
        mid_circuit = self._has_mid_circuit_ops(operations)

        def apply_ops():
            for op in operations:
                qml.apply(op)

        if shots > 0:
            if mid_circuit:
                # Mid-circuit measurements / classically-controlled ops. Deferred
                # measurement is exact and ~100x faster than one-shot sampling.
                # No fixed wire count: deferral may need extra wires (e.g. reset).
                dev_name = "default.qubit"
                dev = qml.device(dev_name, shots=shots, seed=seed)
                qnode_kwargs = {"mcm_method": "deferred"}
            else:
                dev_name = self._get_dev_name()
                dev_kwargs = {"wires": wires, "shots": shots}
                if dev_name == "default.qubit":
                    dev_kwargs["seed"] = seed
                elif seed is not None:
                    dev_kwargs["seed"] = seed
                try:
                    dev = qml.device(dev_name, **dev_kwargs)
                except Exception:
                    dev_name = "default.qubit"
                    dev = qml.device(dev_name, wires=wires, shots=shots, seed=seed)
                qnode_kwargs = {}

            measured = spec.get('measured') if spec is not None else False
            if measured:
                clbits = list(spec['clbits'])
                mvs = []          # distinct mid-circuit measurement values to sample
                end_wires = []    # wires sampled at the end (terminal measurements)
                columns = []      # per clbit: ('mv', i) | ('wire', i) | ('const', value)
                for bit in clbits:
                    if _is_measurement_value(bit):
                        mps = list(getattr(bit, 'measurements', []))
                        if len(mps) == 1 and id(mps[0]) in terminal_wire:
                            w = terminal_wire[id(mps[0])]
                            if w not in end_wires:
                                end_wires.append(w)
                            columns.append(('wire', end_wires.index(w)))
                            continue
                        for i, existing in enumerate(mvs):
                            if existing is bit:
                                columns.append(('mv', i))
                                break
                        else:
                            mvs.append(bit)
                            columns.append(('mv', len(mvs) - 1))
                    else:
                        columns.append(('const', int(bit)))

                def circuit_fn():
                    apply_ops()
                    results = [qml.sample(op=mv) for mv in mvs]
                    if end_wires:
                        results.append(qml.sample(wires=end_wires))
                    return results

                mv_samples, wire_samples = [], None
                n_results = len(mvs) + (1 if end_wires else 0)
                if n_results:
                    out = qml.QNode(circuit_fn, dev, **qnode_kwargs)()
                    if n_results == 1 and not isinstance(out, (list, tuple)):
                        out = [out]
                    out = list(out)
                    mv_samples = [np.asarray(o).reshape(-1).astype(np.int64) for o in out[:len(mvs)]]
                    if end_wires:
                        wire_samples = np.asarray(out[len(mvs)]).astype(np.int64).reshape(shots, len(end_wires))
                bit_cols = []
                for kind, val in columns:
                    if kind == 'mv':
                        bit_cols.append(mv_samples[val])
                    elif kind == 'wire':
                        bit_cols.append(wire_samples[:, val])
                    else:
                        bit_cols.append(np.full(shots, val, dtype=np.int64))
                bits = np.stack(bit_cols, axis=1) if bit_cols else np.zeros((shots, 0), dtype=np.int64)
            else:
                def circuit_fn():
                    apply_ops()
                    return qml.sample(wires=wires)

                out = np.asarray(qml.QNode(circuit_fn, dev, **qnode_kwargs)())
                bits = out.reshape(shots, -1) if out.size else np.zeros((shots, 0), dtype=np.int64)

            counts = self._bit_matrix_to_counts(bits)
            probs_dict = {k: v / shots for k, v in counts.items()}
            return {
                'counts': counts,
                'probs': probs_dict,
                'metadata': {'shots': shots, 'device': dev_name, 'result_type': 'sampling', 'seed': seed}
            }

        # Exact probabilities over all qubits (q[0] first).
        dev_name = "default.qubit" if mid_circuit else self._get_dev_name()
        dev = qml.device(dev_name, wires=None if mid_circuit else wires)

        def qnode_wrapper_exact():
            apply_ops()
            return qml.probs(wires=wires)

        qnode_kwargs = {"diff_method": None}
        if mid_circuit:
            qnode_kwargs["mcm_method"] = "deferred"
        probs_vector = qml.QNode(qnode_wrapper_exact, dev, **qnode_kwargs)()
        probs_dict = self._probs_to_dict(probs_vector, num_qubits)
        return {
            'counts': {},
            'probs': probs_dict,
            'metadata': {'shots': shots, 'device': dev_name, 'result_type': 'exact'}
        }

    def _probs_to_dict(self, probs_vector: np.ndarray, num_qubits: int) -> Dict[str, float]:
        """Converts a probability vector to a dictionary with bitstring keys."""
        probs_dict = {}
        for i, prob in enumerate(probs_vector):
            # Format the index 'i' as a bitstring of length num_qubits
            bitstring = format(i, f'0{num_qubits}b')
            probs_dict[bitstring] = float(prob)
        return probs_dict
