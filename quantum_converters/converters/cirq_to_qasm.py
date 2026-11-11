"""
Cirq to OpenQASM 3.0 Converter Module

WHAT THIS FILE DOES:
    Converts Cirq quantum circuit source code to OpenQASM 3.0 format. Implements
    the AbstractConverter interface, supporting both AST-based parsing (secure, preferred)
    and runtime execution (fallback). Handles all standard Cirq gates, measurements,
    resets, and barriers. Generates OpenQASM 3.0 code using QASM3Builder.

HOW IT LINKS TO OTHER FILES:
    - Inherits from: abstract_converter.py (AbstractConverter interface)
    - Uses: cirq_parser.py (CirqASTParser for AST-based parsing)
    - Uses: qasm3_builder.py (QASM3Builder for code generation)
    - Uses: circuit_ast.py (CircuitAST, GateNode, etc. as intermediate representation)
    - Uses: config/mappings.py (gate name mappings)
    - Returns: ConversionResult (from base/ConversionResult.py)
    - Part of: Converters module implementing framework-specific conversion logic

INPUT:
    - cirq_source (str): Cirq Python source code defining a quantum circuit
    - Expected format: Code that creates cirq.Circuit or defines get_circuit() function
    - Used in: convert() method (primary entry point)

OUTPUT:
    - ConversionResult: Contains OpenQASM 3.0 code string and conversion statistics
    - Returned by: convert() method
    - Includes: QASM code, qubit count, depth, gate counts, measurement flags

STAGE OF USE:
    - Conversion Stage: Primary converter for Cirq framework
    - API Stage: Called by API endpoints when source framework is Cirq
    - Used after: Framework detection/selection
    - Used before: Validation and response formatting

TOOLS USED:
    - cirq: Cirq library for Circuit objects (runtime fallback)
    - ast: Python AST module (via CirqASTParser)
    - time: Performance timing for conversion steps
    - inspect: Code introspection utilities
    - typing: Type hints for method signatures

CONVERSION STRATEGY:
    1. AST-based parsing (preferred): Uses CirqASTParser to extract operations without execution
    2. Runtime execution (fallback): Executes code in isolated namespace if AST parsing fails
    3. AST to QASM: Converts CircuitAST to OpenQASM 3.0 using QASM3Builder
    4. Statistics: Analyzes circuit for qubits, depth, gate counts, measurements

ARCHITECTURE ROLE:
    Implements Cirq-specific conversion logic, bridging Cirq source code and
    OpenQASM 3.0 output. Part of the converter strategy pattern, enabling polymorphic
    framework conversion through the AbstractConverter interface.

Author: QCanvas Team
Date: 2025-08-20
Version: 2.0.0 - Integrated with QASM3Builder
"""

import inspect
from typing import Dict, Any, Optional, Union, List
from quantum_converters.base.ConversionResult import ConversionResult, ConversionStats
from quantum_converters.base.qasm3_builder import QASM3Builder
from quantum_converters.base.qasm3_gates import QASM3GateLibrary, GateModifier
from quantum_converters.base.circuit_ast import CircuitAST, GateNode, MeasurementNode, ResetNode, BarrierNode, ForLoopNode, IfStatementNode
from quantum_converters.parsers.cirq_parser import CirqASTParser
from quantum_converters.base.circuit_validation import (
    GATE_SIGNATURES, UnsupportedCircuitError, validate_circuit_ast,
)
from quantum_converters.config.config import VERBOSE, vprint, INCLUDE_VARS, INCLUDE_CONSTANTS
import time
from quantum_converters.config import get_cirq_inverse_qasm_map, CIRQ_TO_QASM_REGISTRY

# Import Circuit only when needed to avoid dependency issues
try:
    from cirq import Circuit
except ImportError:
    # Define a placeholder for type hints
    Circuit = 'Circuit'

import contextlib as _contextlib
import io as _io


@_contextlib.contextmanager
def _captured_user_output():
    """Swallow print() output of user code run by the fallback path. Besides being
    noise in the server log, printing Unicode circuit diagrams to a non-UTF-8
    console raises UnicodeEncodeError and used to fail the whole conversion."""
    buffer = _io.StringIO()
    with _contextlib.redirect_stdout(buffer), _contextlib.redirect_stderr(buffer):
        yield buffer


class CirqToQASM3Converter:
    """
    A converter class that transforms Cirq quantum circuits to OpenQASM 3.0 format.
    
    This converter supports all standard Cirq gates and circuit structures,
    leveraging Cirq's native OpenQASM 3.0 export functionality when available.
    
    The converter expects source code that defines a function `get_circuit()` 
    which returns a cirq.Circuit object.
    """
    
    def __init__(self):
        """Initialize the Cirq to QASM3 converter."""
        self.cirq_inverse_qasm = get_cirq_inverse_qasm_map()
    
    def _execute_cirq_source(self, source: str) -> 'Circuit':
        """
        Execute Cirq source code and extract the quantum circuit.

        Args:
            source (str): Cirq source code defining a get_circuit() function

        Returns:
            Circuit: The extracted Cirq quantum circuit

        Raises:
            ValueError: If source code doesn't define get_circuit() function
            ImportError: If Cirq is not available
            RuntimeError: If circuit execution fails
        """
        self._ensure_cirq_available()

        try:
            import cirq as _cirq
            if isinstance(source, _cirq.Circuit):
                return source
        except Exception:
            pass

        with _captured_user_output():
            namespace = self._execute_source_code(source)

            # Try different strategies to extract the circuit
            circuit = (
                self._try_get_circuit_function(namespace) or
                self._try_find_circuit_instance(namespace) or
                self._try_factory_functions(namespace)
            )

        if circuit is None:
            raise ValueError(
                "Could not locate a cirq.Circuit. Define get_circuit() or assign the circuit to a variable."
            )

        return circuit

    def _ensure_cirq_available(self) -> None:
        """Ensure Cirq is available, raising ImportError if not."""
        try:
            import cirq  # noqa: F401
        except ImportError:
            raise ImportError("Cirq is required but not installed. Please install with: pip install cirq")

    def _execute_source_code(self, source: str) -> dict:
        """Execute the source code in an isolated namespace."""
        namespace = {}
        try:
            exec(compile(source, "<cirq_source>", "exec"), namespace)
        except Exception as e:
            raise RuntimeError(f"Failed to execute Cirq source code: {str(e)}")
        return namespace

    def _try_get_circuit_function(self, namespace: dict) -> Optional['Circuit']:
        """Try to get circuit from get_circuit() function."""
        get_circuit = namespace.get("get_circuit")
        if callable(get_circuit):
            try:
                circuit = get_circuit()
                if hasattr(circuit, 'all_qubits') and hasattr(circuit, 'moments'):
                    return circuit
            except Exception as e:
                raise RuntimeError(f"Failed to execute get_circuit() function: {str(e)}")
        return None

    def _try_find_circuit_instance(self, namespace: dict) -> Optional['Circuit']:
        """Try to find a Circuit instance in the namespace."""
        try:
            import cirq as _cirq
            for name, obj in namespace.items():
                if isinstance(obj, _cirq.Circuit):
                    return obj
        except Exception:
            pass
        return None

    def _try_factory_functions(self, namespace: dict) -> Optional['Circuit']:
        """Try calling factory functions that might create circuits."""
        import cirq as _cirq

        for name, obj in namespace.items():
            if callable(obj) and name.startswith(("create_", "build_", "make_")):
                try:
                    maybe_circuit = obj()  # type: ignore
                    if isinstance(maybe_circuit, _cirq.Circuit):
                        return maybe_circuit
                except Exception:
                    continue
        return None
    
    def _analyze_cirq_circuit(self, circuit: 'Circuit') -> ConversionStats:
        """
        Analyze a Cirq circuit and extract statistics.
        
        Args:
            circuit: Cirq Circuit object
            
        Returns:
            ConversionStats: Circuit analysis statistics
        """
        try:
            # Get basic circuit properties
            try:
                n_qubits = len(circuit.all_qubits())
            except Exception:
                n_qubits = 0
            
            try:
                depth = len(circuit)  # Number of moments
            except Exception:
                depth = None
            
            try:
                n_moments = len(circuit.moments)
            except Exception:
                n_moments = None
            
            # Count gate types
            gate_counts = {}
            has_measurements = False
            
            try:
                for moment in circuit:
                    for operation in moment:
                        gate_name = type(operation.gate).__name__
                        gate_counts[gate_name] = gate_counts.get(gate_name, 0) + 1
                        
                        # Check for measurements
                        if hasattr(operation.gate, '_measurement_key') or 'measure' in gate_name.lower():
                            has_measurements = True
            except Exception:
                gate_counts = None
                has_measurements = False
            
            return ConversionStats(
                n_qubits=n_qubits,
                depth=depth,
                n_moments=n_moments,
                gate_counts=gate_counts,
                has_measurements=has_measurements
            )
            
        except Exception:
            # Return minimal stats if analysis fails
            return ConversionStats(
                n_qubits=0,
                depth=None,
                n_moments=None,
                gate_counts=None,
                has_measurements=False
            )
    
    def _convert_to_qasm3(self, circuit: 'Circuit') -> str:
        """
        Convert Cirq Circuit to enhanced OpenQASM 3.0 string with advanced features.
        Now uses QASM3Builder for proper code generation.

        Args:
            circuit: Cirq Circuit object

        Returns:
            str: Enhanced OpenQASM 3.0 representation with advanced features

        Raises:
            ImportError: If Cirq dependencies are missing
            RuntimeError: If conversion fails
        """
        self._ensure_dependencies_available()

        if VERBOSE:
            vprint("[CirqToQASM3Converter] Building prelude")
        t0 = time.time()

        import cirq as _cirq
        if _cirq.is_parameterized(circuit):
            names = ", ".join(sorted(_cirq.parameter_names(circuit)))
            raise UnsupportedCircuitError(
                f"The circuit has unresolved symbolic parameters ({names}). Give them numeric values "
                f"(e.g. cirq.resolve_parameters(circuit, {{...}})) before converting."
            )
        builder = QASM3Builder()
        qubit_map = self._create_qubit_mapping(circuit)
        self._clbit_map = self._create_clbit_mapping(circuit)

        builder.build_standard_prelude(
            num_qubits=len(qubit_map),
            num_clbits=sum(len(v) for v in self._clbit_map.values()),
            include_vars=INCLUDE_VARS,
            include_constants=INCLUDE_CONSTANTS
        )
        self._add_custom_gates(builder, circuit)
        self._convert_operations(builder, circuit, qubit_map)

        code = builder.get_code()
        self._log_conversion_complete(code, t0)
        return code

    def _ensure_dependencies_available(self) -> None:
        """Ensure required dependencies are available."""
        try:
            import cirq  # noqa: F401
            import numpy as np  # noqa: F401
        except ImportError:
            raise ImportError("Cirq is required for conversion")

    def _create_qubit_mapping(self, circuit: 'Circuit') -> dict:
        """Create a mapping from qubits to indices."""
        all_qubits = list(circuit.all_qubits())
        if VERBOSE:
            vprint(f"[CirqToQASM3Converter] Circuit qubits detected: {len(all_qubits)}")
        try:
            ordered = sorted(all_qubits)
        except TypeError:
            ordered = sorted(all_qubits, key=str)
        return {qubit: i for i, qubit in enumerate(ordered)}

    def _create_clbit_mapping(self, circuit: 'Circuit') -> dict:
        """
        Allocate classical bits in circuit order: measurement key -> [clbit, ...]
        (one bit per measured qubit). Matches the AST path, where the k-th measured
        qubit in the program lands in c[k].
        """
        import cirq as _cirq
        mapping = {}
        next_bit = 0
        for op in circuit.all_operations():
            if _cirq.is_measurement(op) and not isinstance(op, _cirq.ClassicallyControlledOperation):
                key = str(_cirq.measurement_key_name(op))
                if key in mapping:
                    raise UnsupportedCircuitError(f"measurement key '{key}' is used more than once")
                mapping[key] = list(range(next_bit, next_bit + len(op.qubits)))
                next_bit += len(op.qubits)
        return mapping

    def _detect_measurements(self, circuit: 'Circuit') -> bool:
        """Detect if the circuit contains measurement operations."""
        return any(
            any(self._is_measurement_operation(op) for op in moment)
            for moment in circuit
        )

    def _is_measurement_operation(self, operation) -> bool:
        """Check if an operation is a measurement."""
        return (hasattr(operation.gate, '_measurement_key') or
                str(type(operation.gate).__name__) == 'MeasurementGate')

    def _build_prelude(self, builder: QASM3Builder, num_qubits: int, has_measurements: bool) -> None:
        """Build the QASM prelude with appropriate registers."""
        builder.build_standard_prelude(
            num_qubits=num_qubits,
            num_clbits=num_qubits if has_measurements else 0,
            include_vars=INCLUDE_VARS,
            include_constants=INCLUDE_CONSTANTS
        )

    def _add_custom_gates(self, builder: QASM3Builder, circuit: 'Circuit') -> None:
        """Add custom gate definitions if any exist."""
        custom_gates = self._extract_custom_gates(circuit)
        if custom_gates:
            builder.add_section_comment("Custom gate definitions")
            for gate_def in custom_gates:
                builder.lines.append(gate_def)
            builder.add_blank_line()

    def _convert_operations(self, builder: QASM3Builder, circuit: 'Circuit', qubit_map: dict) -> None:
        """Convert circuit operations to QASM."""
        builder.add_section_comment("Circuit operations")
        if VERBOSE:
            vprint("[CirqToQASM3Converter] Emitting operations")

        for moment in circuit:
            for operation in moment:
                if VERBOSE:
                    vprint(f"[CirqToQASM3Converter] Op: {type(operation.gate).__name__} on {[str(q) for q in operation.qubits]}")
                self._add_cirq_operation(builder, operation, qubit_map)

    def _log_conversion_complete(self, code: str, start_time: float) -> None:
        """Log completion of conversion."""
        if VERBOSE:
            vprint("[CirqToQASM3Converter] QASM generated, length:", len(code))
            vprint(f"[CirqToQASM3Converter] Build done in {(time.time()-start_time)*1000:.1f} ms")

    def _extract_custom_gates(self, circuit: 'Circuit') -> list:
        """Extract custom gate definitions from the circuit."""
        custom_gates = []
        # This is a simplified implementation - in a full implementation,
        # you'd need to analyze the circuit for custom gate definitions
        return custom_gates

    def _add_cirq_operation(self, builder: QASM3Builder, operation, qubit_map: dict):
        """Add a Cirq operation to the QASM builder."""
        import cirq as _cirq
        if isinstance(operation, _cirq.ClassicallyControlledOperation):
            self._add_classically_controlled(builder, operation, qubit_map)
            return
        gate = operation.gate
        if gate is None:
            raise UnsupportedCircuitError(f"Unsupported Cirq operation: {operation!r}")
        qubits = operation.qubits
        qubit_indices = [qubit_map[qubit] for qubit in qubits]
        qubits_str = [f"q[{i}]" for i in qubit_indices]

        # Get gate name and properties
        gate_name = type(gate).__name__
        modifiers, actual_exponent = self._extract_gate_properties(gate)

        # Handle special structured gates before generic dispatch
        if gate_name == 'ControlledGate':
            self._handle_controlled_gate(builder, gate, qubits_str)
            return

        # Handle different gate types sequentially, stopping once handled
        if self._handle_standard_gates(builder, gate_name, qubits_str, modifiers, actual_exponent):
            return
        if self._handle_parameterized_gates(builder, gate_name, qubits_str, modifiers, actual_exponent, gate):
            return
        self._handle_special_gates(builder, gate_name, qubits_str, qubit_indices, gate)

    def _add_classically_controlled(self, builder: QASM3Builder, operation, qubit_map: dict):
        """cirq `op.with_classical_controls(key...)` -> `if (c[k] == 1 ...) { op }`."""
        import cirq as _cirq
        parts = []
        for cond in operation.classical_controls:
            if not isinstance(cond, _cirq.KeyCondition):
                raise UnsupportedCircuitError(f"Unsupported classical control condition: {cond}")
            key = str(cond.key)
            if key not in self._clbit_map:
                raise UnsupportedCircuitError(f"classical control on unknown measurement key '{key}'")
            bits = self._clbit_map[key]
            # KeyCondition is true when the measured value is non-zero.
            any_bit = " || ".join(f"c[{b}] == 1" for b in bits)
            parts.append(any_bit if len(bits) == 1 else f"({any_bit})")
        body_builder_lines = builder.lines
        builder.lines = []
        try:
            self._add_cirq_operation(builder, operation.without_classical_controls(), qubit_map)
            body = builder.lines
        finally:
            builder.lines = body_builder_lines
        builder.add_if_statement(" && ".join(parts), body, else_body=None)

    def _extract_gate_properties(self, gate) -> tuple:
        """Extract modifiers and actual exponent from a gate."""
        import numpy as np

        modifiers = {}
        actual_exponent = None

        # Check for inverse (negative exponent)
        if hasattr(gate, 'exponent'):
            actual_exponent = gate.exponent
            if actual_exponent < 0:
                modifiers['inv'] = True
                # Use positive exponent for parameter calculation
                actual_exponent = abs(actual_exponent)
            elif actual_exponent != 1 and actual_exponent != 0:
                # Handle fractional exponents as power modifier (Iteration II feature)
                # For now, just process as normal parameter
                pass
        else:
            actual_exponent = 1  # Default

        return modifiers, actual_exponent

    def _handle_standard_gates(self, builder: QASM3Builder, gate_name: str, qubits_str: list,
                              modifiers: dict, actual_exponent):
        """Handle standard single/two-qubit gates using a compact mapping."""
        if not self._is_standard_exponent(actual_exponent):
            return
        gate_map = {
            'HPowGate': 'h', '_H': 'h',
            'XPowGate': 'x', '_PauliX': 'x', '_X': 'x',
            'YPowGate': 'y', '_PauliY': 'y', '_Y': 'y',
            'ZPowGate': 'z', '_PauliZ': 'z', '_Z': 'z',
            'SPowGate': 's', '_S': 's',
            'TPowGate': 't', '_T': 't',
            'CNotPowGate': 'cx', 'CXPowGate': 'cx', '_CNOT': 'cx',
            'CZPowGate': 'cz', '_CZ': 'cz',
            'SwapPowGate': 'swap', '_SWAP': 'swap',
            'CCXPowGate': 'ccx', 'CCZPowGate': 'ccz', 'CSwapGate': 'cswap', 'ISwapPowGate': 'iswap',
        }
        qasm_name = gate_map.get(gate_name)
        if qasm_name:
            builder.apply_gate(qasm_name, qubits_str, modifiers=modifiers if modifiers else None)
            return True
        return False

    def _is_standard_exponent(self, exponent) -> bool:
        """Check if exponent represents a standard gate (not parameterized)."""
        return exponent is None or abs(exponent) == 1

    def _handle_parameterized_gates(self, builder: QASM3Builder, gate_name: str, qubits_str: list,
                                   modifiers: dict, actual_exponent, gate):
        """Handle parameterized rotation gates."""
        import numpy as np

        if gate_name in ['XPowGate', 'YPowGate', 'ZPowGate'] and actual_exponent is not None and abs(actual_exponent) != 1:
            if actual_exponent == 0:
                return True  # identity
            self._apply_rotation_gate(builder, gate_name, qubits_str, actual_exponent, modifiers)
            return True
        elif gate_name == 'CZPowGate' and actual_exponent is not None and abs(actual_exponent) != 1:
            # CZ**t == cp(pi*t) exactly; a negative exponent is carried by `inv`.
            builder.apply_gate('cp', qubits_str, parameters=[builder.format_parameter(actual_exponent * np.pi)],
                               modifiers=modifiers if modifiers else None)
            return True
        elif gate_name.lower() in ['rx', 'ry', 'rz']:
            self._apply_direct_rotation_gate(builder, gate_name, qubits_str, gate, modifiers)
            return True
        elif gate_name == 'PhasedXPowGate':
            self._apply_phased_x_gate(builder, qubits_str, actual_exponent, gate, modifiers)
            return True
        return False

    def _apply_rotation_gate(self, builder: QASM3Builder, gate_name: str, qubits_str: list,
                           exponent, modifiers: dict):
        """Apply a rotation gate based on exponent."""
        import numpy as np

        angle = exponent * np.pi
        param = builder.format_parameter(angle)

        gate_map = {'XPowGate': 'rx', 'YPowGate': 'ry', 'ZPowGate': 'rz'}
        qasm_gate = gate_map.get(gate_name)
        if qasm_gate:
            builder.apply_gate(qasm_gate, qubits_str, parameters=[param],
                             modifiers=modifiers if modifiers else None)

    def _apply_direct_rotation_gate(self, builder: QASM3Builder, gate_name: str, qubits_str: list,
                                  gate, modifiers: dict):
        """Apply a rotation gate with direct angle parameter."""
        import numpy as np

        angle = self._extract_angle_from_gate(gate)
        param = builder.format_parameter(angle)

        gate_map = {'Rx': 'rx', 'Ry': 'ry', 'Rz': 'rz'}
        qasm_gate = gate_map.get(gate_name)
        if qasm_gate:
            # Enforce parameter order (single param 'theta' or 'lambda') from registry
            _ = CIRQ_TO_QASM_REGISTRY.mapping[qasm_gate].param_order if qasm_gate in CIRQ_TO_QASM_REGISTRY.mapping else ["theta"]
            builder.apply_gate(qasm_gate, qubits_str, parameters=[param],
                             modifiers=modifiers if modifiers else None)

    def _extract_angle_from_gate(self, gate):
        """Extract angle parameter from a rotation gate."""
        import numpy as np

        angle_attrs = ['rads', '_rads', 'angle', '_angle', 'theta', '_theta']
        for attr in angle_attrs:
            if hasattr(gate, attr):
                return getattr(gate, attr)

        return np.pi/2  # Default fallback

    def _apply_phased_x_gate(self, builder: QASM3Builder, qubits_str: list,
                           actual_exponent, gate, modifiers: dict):
        """Apply a phased X gate."""
        import numpy as np

        phase_exponent = getattr(gate, 'phase_exponent', 0)
        if phase_exponent == 0:
            param = builder.format_parameter(actual_exponent * np.pi)
            builder.apply_gate("rx", qubits_str, parameters=[param],
                             modifiers=modifiers if modifiers else None)
        else:
            # PhasedX(p, t) = Z^p X^t Z^-p  (time order: Z^-p, X^t, Z^p); equal up to global phase.
            builder.apply_gate("rz", qubits_str, parameters=[builder.format_parameter(-phase_exponent * np.pi)])
            builder.apply_gate("rx", qubits_str, parameters=[builder.format_parameter(gate.exponent * np.pi)])
            builder.apply_gate("rz", qubits_str, parameters=[builder.format_parameter(phase_exponent * np.pi)])

    def _handle_special_gates(self, builder: QASM3Builder, gate_name: str, qubits_str: list,
                            qubit_indices: list, gate):
        """Handle special gates like measurements, resets, and barriers."""
        import numpy as np

        if gate_name == 'MatrixGate':
            raise UnsupportedCircuitError(f"Unsupported Cirq gate: arbitrary MatrixGate {gate}")
        elif gate_name == 'MeasurementGate' or hasattr(gate, '_measurement_key'):
            # Support multi-qubit measurements by emitting one measurement per qubit.
            # Example:
            #   cirq.measure(q0, q1, key='m')
            # becomes:
            #   c[0] = measure q[0];
            #   c[1] = measure q[1];
            import cirq as _cirq
            if getattr(gate, 'invert_mask', None) and any(gate.invert_mask):
                raise UnsupportedCircuitError("cirq.measure(invert_mask=...) is not supported")
            key = str(_cirq.measurement_key_name(gate))
            for q_str, c_idx in zip(qubits_str, self._clbit_map[key]):
                builder.add_measurement(q_str, f"c[{c_idx}]")
        elif gate_name in ['ResetChannel', '_ResetGate'] or str(gate) == 'reset':
            builder.add_reset(qubits_str[0])
        elif gate_name == 'IdentityGate' or str(gate) == 'I':
            for q_str in qubits_str:
                builder.apply_gate("id", [q_str])
        elif gate_name == 'ControlledGate':
            raise UnsupportedCircuitError(f"Unsupported controlled gate: {gate}")
        elif gate_name == 'GlobalPhaseGate':
            # coefficient is the complex number e^{i*theta}; gphase takes theta.
            phase = float(np.angle(complex(gate.coefficient)))
            param = builder.format_parameter(phase)
            builder.apply_gate("gphase", [], parameters=[param])
        elif str(gate).startswith('barrier'):
            builder.add_barrier(qubits_str if qubits_str else None)
        else:
            raise UnsupportedCircuitError(f"Unsupported Cirq gate: {type(gate).__name__} ({gate})")

    def _handle_controlled_gate(self, builder: QASM3Builder, gate, qubits_str: list):
        """Handle Cirq ControlledGate instances, mapping to OpenQASM controlled gates."""
        import numpy as np

        base_gate, total_controls = self._flatten_controlled_gate(gate)
        if base_gate is None:
            raise UnsupportedCircuitError(f"Unsupported controlled gate structure: {gate}")
        try:
            control_values = [tuple(v) for v in gate.control_values]
        except Exception:
            control_values = []
        if any(v != (1,) for v in control_values):
            raise UnsupportedCircuitError(f"Controlled gate with non-|1> control values: {gate}")

        mapping = self._map_controlled_base_gate(builder, base_gate, total_controls)
        if mapping is None:
            raise UnsupportedCircuitError(f"Unsupported controlled gate: {gate}")

        gate_name, params = mapping
        builder.apply_gate(gate_name, qubits_str, parameters=params if params else None)

    def _flatten_controlled_gate(self, gate):
        """Flatten nested ControlledGate structures."""
        total_controls = getattr(gate, 'num_controls', lambda: 1)()
        sub_gate = getattr(gate, 'sub_gate', None)

        while sub_gate is not None and hasattr(sub_gate, 'sub_gate') and hasattr(sub_gate, 'num_controls'):
            total_controls += sub_gate.num_controls()
            sub_gate = getattr(sub_gate, 'sub_gate', None)

        return sub_gate, total_controls

    def _map_controlled_base_gate(self, builder: QASM3Builder, base_gate, total_controls: int):
        """Map a base gate to its controlled OpenQASM counterpart."""
        import numpy as np

        gate_type = type(base_gate).__name__
        exponent = getattr(base_gate, 'exponent', None)

        if gate_type in ['YPowGate', '_PauliY', '_Y']:
            if total_controls == 1 and self._is_full_turn(exponent):
                return ('cy', [])

        if gate_type in ['HPowGate', '_H']:
            if total_controls == 1 and self._is_full_turn(exponent):
                return ('ch', [])

        if gate_type in ['XPowGate', '_PauliX', '_X']:
            if total_controls == 1 and self._is_full_turn(exponent):
                return ('cx', [])
            if total_controls == 2 and self._is_full_turn(exponent):
                return ('ccx', [])

        if gate_type in ['ZPowGate', '_PauliZ', '_Z']:
            if total_controls == 1 and self._is_full_turn(exponent):
                return ('cz', [])
            if total_controls == 2 and self._is_full_turn(exponent):
                return ('ccz', [])
            angle = self._angle_from_exponent(exponent)
            if angle is not None and total_controls == 1 and getattr(base_gate, 'global_shift', 0) == 0:
                return ('cp', [builder.format_parameter(angle)])

        if gate_type in ['Rx', 'Ry', 'Rz']:
            angle_attr = getattr(base_gate, 'rads', None)
            if angle_attr is None:
                angle_attr = getattr(base_gate, '_rads', None)
            if angle_attr is not None and total_controls == 1:
                qasm_gate = {'Rx': 'crx', 'Ry': 'cry', 'Rz': 'crz'}.get(gate_type)
                if qasm_gate:
                    return (qasm_gate, [builder.format_parameter(angle_attr)])

        if gate_type in ['RXPowGate', 'RYPowGate', 'RZPowGate']:
            angle = self._angle_from_exponent(exponent)
            name_map = {
                'RXPowGate': 'crx',
                'RYPowGate': 'cry',
                'RZPowGate': 'crz',
            }
            if angle is not None and total_controls == 1 and gate_type in name_map:
                return (name_map[gate_type], [builder.format_parameter(angle)])

        return None

    def _angle_from_exponent(self, exponent):
        import numpy as np
        if exponent is None:
            return None
        return exponent * np.pi

    def _is_full_turn(self, exponent) -> bool:
        if exponent is None:
            return False
        return abs(abs(exponent) - 1.0) < 1e-9
        
    def _analyze_circuit_ast(self, circuit_ast: CircuitAST) -> ConversionStats:
        try:
            return ConversionStats(
                n_qubits=circuit_ast.qubits,
                depth=circuit_ast.get_depth(),
                n_moments=circuit_ast.get_depth(),
                gate_counts=circuit_ast.get_gate_count(),
                has_measurements=circuit_ast.has_measurements(),
            )
        except Exception:
            return ConversionStats(n_qubits=0, depth=None, n_moments=None, gate_counts=None, has_measurements=False)

    def _add_ast_operation(self, builder: QASM3Builder, operation):
        """Add an AST operation to the QASM builder."""
        if isinstance(operation, GateNode):
            self._add_ast_gate_operation(builder, operation)
        elif isinstance(operation, MeasurementNode):
            builder.add_measurement(f"q[{operation.qubit}]", f"c[{operation.clbit}]")
        elif isinstance(operation, ResetNode):
            builder.add_reset(f"q[{operation.qubit}]")
        elif isinstance(operation, BarrierNode):
            self._add_ast_barrier_operation(builder, operation)
        elif isinstance(operation, ForLoopNode):
            self._add_ast_for_loop(builder, operation)
        elif isinstance(operation, IfStatementNode):
            self._add_ast_if_statement(builder, operation)

    def _add_ast_gate_operation(self, builder: QASM3Builder, operation: GateNode):
        """Add a gate operation from AST to QASM builder."""
        gate_name = operation.name
        qubits_str = [f"q[{i}]" for i in operation.qubits]
        modifiers = operation.modifiers if operation.modifiers else None

        if gate_name not in GATE_SIGNATURES:
            raise UnsupportedCircuitError(f"Unsupported gate: {gate_name}")
        if gate_name == 'gphase':
            self._add_global_phase_gate(builder, operation)
            return
        params = [builder.format_parameter(p) for p in (operation.parameters or [])]
        builder.apply_gate(gate_name, qubits_str, parameters=params or None, modifiers=modifiers)

    def _is_standard_gate(self, gate_name: str) -> bool:
        """Check if gate is a standard single-qubit gate."""
        return gate_name in ['h', 'x', 'y', 'z', 's', 't', 'sx', 'i', 'id']

    def _is_two_qubit_gate(self, gate_name: str) -> bool:
        """Check if gate is a supported two-qubit gate."""
        return gate_name in ['cx', 'cz', 'swap', 'cy', 'ch', 'crx', 'cry', 'crz', 'cp']

    def _is_three_qubit_gate(self, gate_name: str) -> bool:
        """Check if gate is a supported three-qubit gate."""
        return gate_name in ['ccx', 'cswap', 'ccz']

    def _is_parameterized_gate(self, gate_name: str) -> bool:
        """Check if gate is a parameterized rotation gate."""
        return gate_name in ['rx', 'ry', 'rz', 'crx', 'cry', 'crz', 'cp']

    def _add_parameterized_gate(self, builder: QASM3Builder, gate_name: str, qubits_str: list,
                               operation: GateNode, modifiers):
        """Add a parameterized gate to the QASM builder."""
        if operation.parameters:
            formatted_params = [builder.format_parameter(p) for p in operation.parameters]
            builder.apply_gate(gate_name, qubits_str, parameters=formatted_params, modifiers=modifiers)
        else:
            builder.add_comment(f"Parameterized gate {gate_name} missing parameter")

    def _add_global_phase_gate(self, builder: QASM3Builder, operation: GateNode):
        """Add a global phase gate to the QASM builder."""
        if operation.parameters:
            param = builder.format_parameter(operation.parameters[0])
            builder.apply_gate('gphase', [], parameters=[param])

    def _add_ast_barrier_operation(self, builder: QASM3Builder, operation: BarrierNode):
        """Add a barrier operation from AST to QASM builder."""
        if operation.qubits:
            builder.add_barrier([f"q[{i}]" for i in operation.qubits])
        else:
            builder.add_barrier(None)

    def _add_ast_for_loop(self, builder: QASM3Builder, operation: ForLoopNode):
        """Add a for loop from AST to QASM builder."""
        # OpenQASM 3.0 for loop syntax: for int i in [0:7] { ... }
        if isinstance(operation.range_end, int) and isinstance(operation.range_start, int):
            openqasm_end = operation.range_end - 1 if operation.range_end > operation.range_start else operation.range_start
            range_spec = f"[{operation.range_start}:{openqasm_end}]"
        else:
            # Symbolic range (e.g., from [0:n])
            # OpenQASM 3.0 range syntax is inclusive, Python's is exclusive
            range_spec = f"[{operation.range_start}:{operation.range_end}-1]"
        variable_decl = f"int {operation.variable}"
        
        # Convert loop body operations to QASM statements
        body_statements = []
        saved_lines = builder.lines
        builder.lines = body_statements
        
        # Recursively convert all operations in the loop body
        for body_op in operation.body:
            self._add_ast_operation(builder, body_op)
        
        # Extract statements
        body_statements = builder.lines
        builder.lines = saved_lines
        
        # Add the for loop using the builder
        builder.add_for_loop(variable_decl, range_spec, body_statements)

    def _add_ast_if_statement(self, builder: QASM3Builder, operation: IfStatementNode):
        """Add an if statement from AST to QASM builder."""
        # Convert if body operations to QASM statements
        if_body_statements = []
        saved_lines = builder.lines
        builder.lines = if_body_statements
        
        # Recursively convert all operations in the if body
        for body_op in operation.body:
            self._add_ast_operation(builder, body_op)
        
        # Extract statements
        if_body_statements = builder.lines
        builder.lines = saved_lines
        
        # Convert else body if present
        else_body_statements = None
        if operation.else_body:
            else_body_statements = []
            builder.lines = else_body_statements
            
            for body_op in operation.else_body:
                self._add_ast_operation(builder, body_op)
            
            else_body_statements = builder.lines
            builder.lines = saved_lines
        
        # Add the if statement using the builder
        builder.add_if_statement(operation.condition, if_body_statements, else_body_statements)

    def _convert_ast_to_qasm3(self, circuit_ast: CircuitAST) -> str:
        builder = QASM3Builder()
        builder.build_standard_prelude(
            num_qubits=circuit_ast.qubits,
            num_clbits=circuit_ast.clbits,
            include_vars=INCLUDE_VARS,
            include_constants=INCLUDE_CONSTANTS,
        )
        # ── Array parameters (e.g. theta[0]..theta[3]) ─────────────────────────
        if hasattr(circuit_ast, 'array_parameters') and circuit_ast.array_parameters:
            builder.add_section_comment("Array input parameters")
            for param_name, param_shape in sorted(circuit_ast.array_parameters.items()):
                # Format shape as comma-separated list
                shape_str = ", ".join(str(s) for s in param_shape)
                builder.lines.append(f"input array[float[64], {shape_str}] {param_name};")
            builder.add_blank_line()

        # ── Simple scalar parameters (bare variable names used in gates) ────────
        # Filter out names that were already declared as array parameters above.
        all_params = circuit_ast.parameters if isinstance(circuit_ast.parameters, list) else list(circuit_ast.parameters or [])
        array_param_names = getattr(circuit_ast, 'array_parameters', {}).keys()
        scalar_params = [p for p in all_params if p not in array_param_names]
        
        if scalar_params:
            builder.add_section_comment("Scalar input parameters")
            for param_name in scalar_params:
                builder.add_input_directive(param_name, 'float[64]')
            builder.add_blank_line()
        builder.add_section_comment("Circuit operations")
        for op in circuit_ast.operations:
            self._add_ast_operation(builder, op)
        # Only the operations the user wrote are emitted (no demo control flow).
        return builder.get_code()

    def convert(self, cirq_source: str) -> ConversionResult:
        """
        Convert Cirq source code to OpenQASM 3.0 format.
        
        Args:
            cirq_source (str): Complete Cirq source code defining get_circuit() function
            
        Returns:
            ConversionResult: Object containing QASM code and conversion statistics
            
        Raises:
            ValueError: If source code is invalid or doesn't define required function
            ImportError: If Cirq dependencies are missing
            RuntimeError: If conversion process fails
            
        Example:
            >>> converter = CirqToQASM3Converter()
            >>> source = '''
            ... import cirq
            ... def get_circuit():
            ...     q0, q1 = cirq.LineQubit.range(2)
            ...     circuit = cirq.Circuit(
            ...         cirq.H(q0),
            ...         cirq.CNOT(q0, q1),
            ...         cirq.measure(q0, key="m0"),
            ...         cirq.measure(q1, key="m1")
            ...     )
            ...     return circuit
            ... '''
            >>> result = converter.convert(source)
            >>> print(f"Circuit has {result.stats.n_qubits} qubits and {result.stats.depth} moments")
        """
        # Direct object conversion bypass
        try:
            import cirq as _cirq
            if isinstance(cirq_source, _cirq.Circuit):
                stats = self._analyze_cirq_circuit(cirq_source)
                qasm3_program = self._convert_to_qasm3(cirq_source)
                return ConversionResult(qasm_code=qasm3_program, stats=stats)
        except Exception:
            pass

        # Try AST-based path first (secure, no execution)
        try:
            if VERBOSE:
                vprint("[CirqToQASM3Converter] Attempt AST-based conversion")
            parser = CirqASTParser()
            circuit_ast = parser.parse(cirq_source)
            validate_circuit_ast(circuit_ast, "Cirq")
            stats = self._analyze_circuit_ast(circuit_ast)
            qasm3_program = self._convert_ast_to_qasm3(circuit_ast)
            return ConversionResult(qasm_code=qasm3_program, stats=stats)
        except Exception as e:
            # The static translation could not represent the program exactly;
            # fall back to building the real cirq.Circuit.
            if VERBOSE:
                vprint(f"[CirqToQASM3Converter] AST path rejected: {e}")

        # Fallback: execute source to obtain cirq.Circuit
        if VERBOSE:
            vprint("[CirqToQASM3Converter] AST failed, fallback to runtime execution path")
        circuit = self._execute_cirq_source(cirq_source)
        stats = self._analyze_cirq_circuit(circuit)
        qasm3_program = self._convert_to_qasm3(circuit)
        return ConversionResult(qasm_code=qasm3_program, stats=stats)


# Public API function for easy module usage
def convert_cirq_to_qasm3(cirq_source: str) -> ConversionResult:
    """
    Convert Cirq quantum circuit source code to OpenQASM 3.0 format.
    
    This is a convenience function that creates a converter instance and performs
    the conversion in a single call, returning a ConversionResult object.
    
    Args:
        cirq_source (str): Complete Cirq source code defining get_circuit() function
        
    Returns:
        ConversionResult: Object containing QASM code and conversion statistics
        
    Raises:
        ValueError: If source code is invalid or doesn't define required function
        ImportError: If Cirq dependencies are missing
        RuntimeError: If conversion process fails
        
    Example:
        >>> from cirq_qasm_converter import convert_cirq_to_qasm3
        >>> source = '''
        ... import cirq
        ... def get_circuit():
        ...     q0, q1 = cirq.LineQubit.range(2)
        ...     circuit = cirq.Circuit(
        ...         cirq.H(q0),
        ...         cirq.CNOT(q0, q1)
        ...     )
        ...     return circuit
        ... '''
        >>> result = convert_cirq_to_qasm3(source)
        >>> print(result.qasm_code)
    """
    converter = CirqToQASM3Converter()
    return converter.convert(cirq_source)