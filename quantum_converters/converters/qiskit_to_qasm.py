"""
Qiskit to OpenQASM 3.0 Converter Module

WHAT THIS FILE DOES:
    Converts Qiskit quantum circuit source code to OpenQASM 3.0 format. Implements
    the AbstractConverter interface, supporting both AST-based parsing (secure, preferred)
    and runtime execution (fallback). Handles all standard Qiskit gates, measurements,
    resets, and barriers. Generates OpenQASM 3.0 code using QASM3Builder.

HOW IT LINKS TO OTHER FILES:
    - Inherits from: abstract_converter.py (AbstractConverter interface)
    - Uses: qiskit_parser.py (QiskitASTParser for AST-based parsing)
    - Uses: qasm3_builder.py (QASM3Builder for code generation)
    - Uses: circuit_ast.py (CircuitAST, GateNode, etc. as intermediate representation)
    - Uses: config/mappings.py (gate name mappings)
    - Returns: ConversionResult (from base/ConversionResult.py)
    - Part of: Converters module implementing framework-specific conversion logic

INPUT:
    - qiskit_source (str): Qiskit Python source code defining a quantum circuit
    - Expected format: Code that creates QuantumCircuit or defines get_circuit() function
    - Used in: convert() method (primary entry point)

OUTPUT:
    - ConversionResult: Contains OpenQASM 3.0 code string and conversion statistics
    - Returned by: convert() method
    - Includes: QASM code, qubit count, depth, gate counts, measurement flags

STAGE OF USE:
    - Conversion Stage: Primary converter for Qiskit framework
    - API Stage: Called by API endpoints when source framework is Qiskit
    - Used after: Framework detection/selection
    - Used before: Validation and response formatting

TOOLS USED:
    - qiskit: Qiskit library for QuantumCircuit objects (runtime fallback)
    - ast: Python AST module (via QiskitASTParser)
    - time: Performance timing for conversion steps
    - inspect: Code introspection utilities
    - typing: Type hints for method signatures

CONVERSION STRATEGY:
    1. AST-based parsing (preferred): Uses QiskitASTParser to extract operations without execution
    2. Runtime execution (fallback): Executes code in isolated namespace if AST parsing fails
    3. AST to QASM: Converts CircuitAST to OpenQASM 3.0 using QASM3Builder
    4. Statistics: Analyzes circuit for qubits, depth, gate counts, measurements

ARCHITECTURE ROLE:
    Implements Qiskit-specific conversion logic, bridging Qiskit source code and
    OpenQASM 3.0 output. Part of the converter strategy pattern, enabling polymorphic
    framework conversion through the AbstractConverter interface.

Author: QCanvas Team
Date: 2025-08-18
Version: 2.0.0 - Integrated with QASM3Builder
"""

import inspect
from typing import Dict, Any, Optional, Union, List
# Qiskit exposes QuantumCircuit from different import locations depending on
# the installed version and packaging layout.
try:
    from qiskit import QuantumCircuit
except Exception:
    try:
        from qiskit.circuit import QuantumCircuit
    except Exception:
        QuantumCircuit = 'QuantumCircuit'
from quantum_converters.base.ConversionResult import ConversionResult, ConversionStats
from quantum_converters.base.qasm3_builder import QASM3Builder
from quantum_converters.config.config import VERBOSE, vprint, INCLUDE_VARS, INCLUDE_CONSTANTS
from quantum_converters.base.circuit_ast import GateNode, MeasurementNode, ResetNode, BarrierNode, ForLoopNode, IfStatementNode
import time
from quantum_converters.base.qasm3_gates import QASM3GateLibrary
from quantum_converters.parsers.qiskit_parser import QiskitASTParser
from quantum_converters.base.circuit_validation import (
    GATE_SIGNATURES, UnsupportedCircuitError, validate_circuit_ast,
)
from quantum_converters.config import get_qiskit_inverse_qasm_map, QISKIT_TO_QASM_REGISTRY

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


class QiskitToQASM3Converter:
    """
    A converter class that transforms Qiskit quantum circuits to OpenQASM 3.0 format.
    
    This converter supports all standard Qiskit gates and circuit structures,
    leveraging Qiskit's native OpenQASM 3.0 export functionality.
    
    The converter expects source code that defines a function `get_circuit()` 
    which returns a qiskit.QuantumCircuit object.
    """
    
    def __init__(self):
        """Initialize the Qiskit to QASM3 converter."""
        self.qiskit_inverse_qasm = get_qiskit_inverse_qasm_map()
    
    # In QiskitToQASM.py, update the _execute_qiskit_source method:

    def _execute_qiskit_source(self, source: str) -> 'QuantumCircuit':
        """
        Execute Qiskit source code and extract the quantum circuit.

        Args:
            source (str): Qiskit source code defining a get_circuit() function

        Returns:
            QuantumCircuit: The extracted Qiskit quantum circuit

        Raises:
            ValueError: If source code doesn't define get_circuit() function
            ImportError: If Qiskit is not available
            RuntimeError: If circuit execution fails
        """
        self._ensure_qiskit_available()

        # Apply preprocessing to handle compatibility issues
        source = self._preprocess_qiskit_source(source)

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
                "Could not locate a QuantumCircuit. Define get_circuit() or assign the circuit to a variable."
            )

        return circuit

    def _preprocess_qiskit_source(self, source: str) -> str:
        """
        Preprocess Qiskit source code to handle compatibility issues.

        Args:
            source: Original Qiskit source code

        Returns:
            Preprocessed source code
        """
        import re

        # Replace qc.gphase(value) calls with qc.global_phase += value
        # since gphase is not a method in older Qiskit versions
        # Use regex to match variable.gphase( parameters )
        pattern = r'(\w+)\.gphase\(([^)]+)\)'
        replacement = r'\1.global_phase += \2'

        processed_source = re.sub(pattern, replacement, source)

        return processed_source

    def _ensure_qiskit_available(self) -> None:
        """Ensure Qiskit is available, raising ImportError if not."""
        try:
            import qiskit  # noqa: F401
        except ImportError:
            raise ImportError("Qiskit is required but not installed. Please install with: pip install qiskit")

    def _execute_source_code(self, source: str) -> dict:
        """Execute the source code in an isolated namespace."""
        namespace = {}
        try:
            exec(compile(source, "<qiskit_source>", "exec"), namespace)
        except Exception as e:
            raise RuntimeError(f"Failed to execute Qiskit source code: {str(e)}")
        return namespace

    def _try_get_circuit_function(self, namespace: dict) -> Optional['QuantumCircuit']:
        """Try to get circuit from get_circuit() function."""
        from qiskit import QuantumCircuit

        get_circuit = namespace.get("get_circuit")
        if callable(get_circuit):
            try:
                circuit = get_circuit()
                if isinstance(circuit, QuantumCircuit):
                    return circuit
            except Exception as e:
                raise RuntimeError(f"Failed to execute get_circuit() function: {str(e)}")
        return None

    def _try_find_circuit_instance(self, namespace: dict) -> Optional['QuantumCircuit']:
        """Try to find a QuantumCircuit instance in the namespace."""
        from qiskit import QuantumCircuit

        try:
            for name, obj in namespace.items():
                if isinstance(obj, QuantumCircuit):
                    return obj
        except Exception:
            pass
        return None

    def _try_factory_functions(self, namespace: dict) -> Optional['QuantumCircuit']:
        """Try calling factory functions that might create circuits."""
        from qiskit import QuantumCircuit

        factory_functions = self._find_factory_functions(namespace)

        for func in factory_functions:
            circuit = self._try_call_factory_function(func)
            if circuit is not None:
                return circuit

        return None

    def _find_factory_functions(self, namespace: dict) -> List[callable]:
        """Find potential factory functions in the namespace."""
        factory_functions = []
        for name, obj in namespace.items():
            if callable(obj) and name.startswith(("create_", "build_", "make_")):
                factory_functions.append(obj)
        return factory_functions

    def _try_call_factory_function(self, func: callable) -> Optional['QuantumCircuit']:
        """Try to call a factory function to create a circuit."""
        from qiskit import QuantumCircuit

        # First try no-arg call
        circuit = self._try_no_arg_call(func)
        if circuit is not None:
            return circuit

        # Try with common integer defaults
        return self._try_with_arg_call(func)

    def _try_no_arg_call(self, func: callable) -> Optional['QuantumCircuit']:
        """Try calling function with no arguments."""
        from qiskit import QuantumCircuit

        try:
            maybe_circuit = func()  # type: ignore
            if isinstance(maybe_circuit, QuantumCircuit):
                return maybe_circuit
        except TypeError:
            # Function requires arguments, will try with args next
            pass
        except Exception:
            # Other error, skip this function
            pass
        return None

    def _try_with_arg_call(self, func: callable) -> Optional['QuantumCircuit']:
        """Try calling function with common integer arguments."""
        from qiskit import QuantumCircuit

        for trial_n in (2, 3, 4):
            try:
                maybe_circuit = func(trial_n)
                if isinstance(maybe_circuit, QuantumCircuit):
                    return maybe_circuit
            except Exception:
                continue
        return None
    
    def _analyze_qiskit_circuit(self, qc: 'QuantumCircuit') -> ConversionStats:
        """
        Analyze a Qiskit circuit and extract statistics.
        
        Args:
            qc: Qiskit QuantumCircuit object
            
        Returns:
            ConversionStats: Circuit analysis statistics
        """
        try:
            # Get basic circuit properties
            try:
                n_qubits = qc.num_qubits
            except AttributeError:
                n_qubits = len(getattr(qc, "qubits", []))
            
            try:
                depth = qc.depth()
            except Exception:
                depth = None
            
            # Check for parameters (not used in return, but kept for potential future use)
            
            # Get basis gates and count them
            try:
                gate_counts = dict(qc.count_ops()) if hasattr(qc, "count_ops") else None
            except Exception:
                gate_counts = None
            
            # Check for measurements
            has_measurements = False
            try:
                if gate_counts:
                    has_measurements = any('measure' in gate.lower() for gate in gate_counts.keys())
            except Exception:
                has_measurements = False
            
            return ConversionStats(
                n_qubits=n_qubits,
                depth=depth,
                n_moments=depth,  # In Qiskit, depth is similar to moments
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
    
    def _convert_to_qasm3(self, qc: 'QuantumCircuit') -> str:
        """
        Convert Qiskit QuantumCircuit to enhanced OpenQASM 3.0 string with advanced features.
        Now uses QASM3Builder for proper code generation.

        Args:
            qc: Qiskit QuantumCircuit object

        Returns:
            str: Enhanced OpenQASM 3.0 representation with advanced features

        Raises:
            ImportError: If Qiskit dependencies are missing
            RuntimeError: If conversion fails
        """
        try:
            import numpy as np
            from qiskit.circuit import Parameter, ParameterVector
        except ImportError:
            raise ImportError("Qiskit is required for conversion")

        # Initialize the QASM3 builder
        if VERBOSE:
            vprint("[QiskitToQASM3Converter] Building prelude")
        builder = QASM3Builder()

        qc = self._lower_to_supported_gates(qc)

        # Get circuit dimensions
        num_qubits = qc.num_qubits
        num_clbits = qc.num_clbits

        # Build standard prelude using global config flags
        builder.build_standard_prelude(
            num_qubits=num_qubits,
            num_clbits=num_clbits,
            include_vars=INCLUDE_VARS,
            include_constants=INCLUDE_CONSTANTS
        )

        # Unbound Parameters have no value to simulate with.
        if qc.parameters:
            names = ", ".join(sorted(p.name for p in qc.parameters))
            raise UnsupportedCircuitError(
                f"The circuit has unbound parameters ({names}). Bind them with "
                f"qc.assign_parameters(...) before converting."
            )

        # Extract and define custom gates
        custom_gates = self._extract_custom_gates(qc)
        if custom_gates:
            builder.add_section_comment("Custom gate definitions")
            for gate_def in custom_gates:
                builder.lines.append(gate_def)
            builder.add_blank_line()

        # No extra classical operations for minimal translation
        
        # Convert circuit instructions
        builder.add_section_comment("Circuit operations")
        if VERBOSE:
            vprint("[QiskitToQASM3Converter] Emitting operations")
        for circuit_instruction in qc.data:
            # Use modern Qiskit 1.2+ named attributes
            instruction = circuit_instruction.operation
            qargs = circuit_instruction.qubits
            cargs = circuit_instruction.clbits
            self._add_qiskit_operation(builder, instruction, qargs, cargs, qc)
        
        # No demo control flow; emit only operations present in the source circuit

        code = builder.get_code()
        if VERBOSE:
            vprint("[QiskitToQASM3Converter] QASM generated, length:", len(code))
        return code

    _RUNTIME_SUPPORTED = frozenset({
        'h', 'x', 'y', 'z', 's', 't', 'sx', 'sdg', 'tdg', 'sxdg', 'id', 'rx', 'ry', 'rz', 'p', 'u',
        'u1', 'u2', 'u3', 'cx', 'cz', 'cy', 'ch', 'swap', 'iswap', 'cp', 'crx', 'cry', 'crz', 'cu',
        'cu1', 'cu3', 'rxx', 'ryy', 'rzz', 'ccx', 'ccz', 'cswap', 'measure', 'reset', 'barrier',
        'if_else', 'global_phase',
    })

    def _lower_to_supported_gates(self, qc):
        """Decompose composite/library instructions into gates we can emit exactly."""
        def unsupported_names(circ):
            names = set()
            for inst in circ.data:
                name = inst.operation.name
                if name == 'if_else':
                    for block in inst.operation.blocks:
                        if block is not None:
                            names |= unsupported_names(block)
                elif name not in self._RUNTIME_SUPPORTED:
                    names.add(name)
            return names

        bad = unsupported_names(qc)
        if not bad:
            return qc
        try:
            from qiskit import transpile
            basis = sorted(self._RUNTIME_SUPPORTED - {'if_else', 'global_phase'})
            lowered = transpile(qc, basis_gates=basis + ['if_else'], optimization_level=0)
        except Exception as e:
            raise UnsupportedCircuitError(f"Unsupported Qiskit instructions: {', '.join(sorted(bad))} ({e})")
        still = unsupported_names(lowered)
        if still:
            raise UnsupportedCircuitError(f"Unsupported Qiskit instructions: {', '.join(sorted(still))}")
        return lowered

    def _extract_custom_gates(self, _qc: 'QuantumCircuit') -> list:
        """Extract custom gate definitions from the circuit."""
        custom_gates = []
        # This is a simplified implementation - in a full implementation,
        # you'd need to analyze the circuit for custom gate definitions
        return custom_gates

    def _add_qiskit_operation(self, builder: QASM3Builder, instruction, qargs, cargs, qc):
        """Add a Qiskit operation to the QASM builder."""
        import numpy as np

        gate_name = instruction.name.lower()

        # Get qubit and clbit indices
        qubit_indices = [qc.qubits.index(q) for q in qargs]
        qubits_str = [f"q[{i}]" for i in qubit_indices]
        clbit_indices = [qc.clbits.index(c) for c in cargs] if cargs else []

        # Detect gate modifiers
        modifiers = self._detect_gate_modifiers(gate_name)

        # Route to appropriate handler based on gate type
        if gate_name in ('sdg', 'tdg', 'sxdg'):
            builder.apply_gate(gate_name[:-2], qubits_str, modifiers={'inv': True})
        elif gate_name in ['h', 'x', 'y', 'z', 's', 't', 'sx', 'id', 'i']:
            self._handle_single_qubit_gate(builder, gate_name, qubits_str, {})
        elif gate_name in ['rx', 'ry', 'rz', 'p', 'u1']:
            builder.apply_gate('p' if gate_name == 'u1' else gate_name, qubits_str,
                               parameters=[builder.format_parameter(instruction.params[0])])
        elif gate_name in ('u', 'u3'):
            self._handle_universal_gate(builder, instruction, qubits_str, {})
        elif gate_name == 'u2':
            phi, lam = instruction.params
            builder.apply_gate('u', qubits_str, parameters=[builder.format_parameter(np.pi / 2),
                                                             builder.format_parameter(phi),
                                                             builder.format_parameter(lam)])
        elif gate_name in ['cx', 'cnot', 'cz', 'cy', 'ch', 'swap', 'iswap']:
            self._handle_two_qubit_gate(builder, gate_name, qubits_str, {})
        elif gate_name in ['cp', 'crx', 'cry', 'crz', 'cu', 'cu1', 'rxx', 'ryy', 'rzz']:
            name = 'cp' if gate_name == 'cu1' else gate_name
            params = [builder.format_parameter(v) for v in instruction.params]
            builder.apply_gate(name, qubits_str, parameters=params)
        elif gate_name == 'cu3':
            params = [builder.format_parameter(v) for v in instruction.params] + ['0']
            builder.apply_gate('cu', qubits_str, parameters=params)
        elif gate_name in ('global_phase', 'gphase'):
            self._handle_global_phase(builder, instruction)
        elif gate_name in ['ccx', 'toffoli']:
            self._handle_toffoli_gate(builder, qubits_str, {})
        elif gate_name == 'ccz':
            self._handle_ccz_gate(builder, qubits_str, {})
        elif gate_name in ['cswap', 'fredkin']:
            self._handle_fredkin_gate(builder, qubits_str, {})
        elif gate_name == 'measure':
            self._handle_measurement(builder, qubits_str, clbit_indices)
        elif gate_name == 'reset':
            self._handle_reset(builder, qubits_str)
        elif gate_name == 'barrier':
            self._handle_barrier(builder, qubits_str)
        elif gate_name == 'if_else':
            self._handle_if_else(builder, instruction, qargs, cargs, qc)
        else:
            raise UnsupportedCircuitError(f"Unsupported Qiskit instruction: {gate_name}")

    def _handle_if_else(self, builder: QASM3Builder, instruction, qargs, cargs, qc):
        """IfElseOp with a (clbit|register, value) condition -> `if (...) { } else { }`."""
        from qiskit.circuit import Clbit, ClassicalRegister
        condition = instruction.condition
        if not isinstance(condition, tuple):
            raise UnsupportedCircuitError("if_else with a classical-expression condition is not supported")
        target, value = condition
        if isinstance(target, Clbit):
            cond = f"c[{qc.clbits.index(target)}] == {int(bool(value))}"
        elif isinstance(target, ClassicalRegister):
            idx = [qc.clbits.index(b) for b in target]
            if idx != list(range(len(qc.clbits))):
                raise UnsupportedCircuitError("if_else on a partial classical register is not supported")
            cond = f"c == {int(value)}"
        else:
            raise UnsupportedCircuitError(f"Unsupported if_else condition: {condition}")

        def emit(block):
            if block is None:
                return None
            saved = builder.lines
            builder.lines = []
            try:
                q_map = {bq: qargs[i] for i, bq in enumerate(block.qubits)}
                c_map = {bc: cargs[i] for i, bc in enumerate(block.clbits)}
                for inst in block.data:
                    self._add_qiskit_operation(
                        builder, inst.operation,
                        [q_map[q] for q in inst.qubits], [c_map[c] for c in inst.clbits], qc)
                return builder.lines
            finally:
                builder.lines = saved

        true_body, false_body = instruction.blocks[0], (instruction.blocks[1] if len(instruction.blocks) > 1 else None)
        builder.add_if_statement(cond, emit(true_body), emit(false_body))

    def _detect_gate_modifiers(self, gate_name: str) -> dict:
        """Detect gate modifiers from gate name."""
        modifiers = {}

        # Check for inverse gates (gates ending with 'dg')
        if gate_name.endswith('dg'):
            modifiers['inv'] = True
            gate_name = gate_name[:-2]  # Remove 'dg' suffix

        return modifiers

    def _handle_single_qubit_gate(self, builder: QASM3Builder, gate_name: str, qubits_str: list, modifiers: dict):
        """Handle single-qubit gates without parameters."""
        builder.apply_gate(gate_name, qubits_str, modifiers=modifiers if modifiers else None)

    def _handle_parameterized_single_qubit_gate(self, builder: QASM3Builder, gate_name: str, instruction, qubits_str: list, modifiers: dict):
        """Handle parameterized single-qubit gates honoring registry param order."""
        param_names = QISKIT_TO_QASM_REGISTRY.mapping[gate_name].param_order if gate_name in QISKIT_TO_QASM_REGISTRY.mapping else ["theta"]
        # Map Qiskit instruction.params to expected order; for single-param gates it's the first
        ordered_params = []
        if param_names:
            # Currently single parameter for rx/ry uses theta and rz/p use lambda
            ordered_params.append(builder.format_parameter(instruction.params[0]))
        builder.apply_gate(gate_name, qubits_str, parameters=ordered_params, modifiers=modifiers if modifiers else None)

    def _handle_universal_gate(self, builder: QASM3Builder, instruction, qubits_str: list, modifiers: dict):
        """Handle universal U gate."""
        # Enforce parameter order from registry (theta, phi, lambda)
        param_names = QISKIT_TO_QASM_REGISTRY.mapping['u'].param_order
        params = [builder.format_parameter(instruction.params[i]) for i, _ in enumerate(param_names)]
        builder.apply_gate('u', qubits_str, parameters=params, modifiers=modifiers if modifiers else None)

    def _handle_two_qubit_gate(self, builder: QASM3Builder, gate_name: str, qubits_str: list, modifiers: dict):
        """Handle two-qubit gates."""
        actual_gate = 'cx' if gate_name == 'cnot' else gate_name
        builder.apply_gate(actual_gate, qubits_str, modifiers=modifiers if modifiers else None)

    def _handle_controlled_parametric_gate(self, builder: QASM3Builder, gate_name: str, instruction, qubits_str: list, modifiers: dict):
        """Handle controlled parametric gates honoring registry param order."""
        param_names = QISKIT_TO_QASM_REGISTRY.mapping[gate_name].param_order if gate_name in QISKIT_TO_QASM_REGISTRY.mapping else ["theta"]
        ordered_params = []
        for idx, _ in enumerate(param_names):
            if idx < len(instruction.params):
                ordered_params.append(builder.format_parameter(instruction.params[idx]))
        builder.apply_gate(gate_name, qubits_str, parameters=ordered_params, modifiers=modifiers if modifiers else None)

    def _handle_global_phase(self, builder: QASM3Builder, instruction):
        """Handle global phase gate."""
        param = builder.format_parameter(instruction.params[0])
        builder.apply_gate('gphase', [], parameters=[param])


    def _handle_toffoli_gate(self, builder: QASM3Builder, qubits_str: list, modifiers: dict):
        """Handle Toffoli gate."""
        builder.apply_gate('ccx', qubits_str, modifiers=modifiers if modifiers else None)

    def _handle_ccz_gate(self, builder: QASM3Builder, qubits_str: list, modifiers: dict):
        """Handle CCZ gate."""
        builder.apply_gate('ccz', qubits_str, modifiers=modifiers if modifiers else None)

    def _handle_fredkin_gate(self, builder: QASM3Builder, qubits_str: list, modifiers: dict):
        """Handle Fredkin gate."""
        builder.apply_gate('cswap', qubits_str, modifiers=modifiers if modifiers else None)

    def _handle_barrier(self, builder: QASM3Builder, qubits_str: list):
        """Handle barrier operations."""
        builder.add_barrier(qubits_str if qubits_str else None)

    def _handle_measurement(self, builder: QASM3Builder, qubits_str: list, clbit_indices: list):
        """Handle measurement operation."""
        for q_str, c_idx in zip(qubits_str, clbit_indices):
            builder.add_measurement(q_str, f"c[{c_idx}]")

    def _handle_reset(self, builder: QASM3Builder, qubits_str: list):
        """Handle reset operation."""
        for q_str in qubits_str:
            builder.add_reset(q_str)
    
    def _analyze_circuit_ast(self, circuit_ast) -> ConversionStats:
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

    def _convert_ast_to_qasm3(self, circuit_ast) -> str:
        t0 = time.time()
        builder = QASM3Builder()

        self._build_ast_prelude(builder, circuit_ast)
        self._convert_ast_operations(builder, circuit_ast)

        code = builder.get_code()
        self._log_ast_conversion_complete(t0)
        return code

    def _build_ast_prelude(self, builder: QASM3Builder, circuit_ast) -> None:
        """Build the QASM prelude for AST conversion."""
        # Honor global flags for constants/vars inclusion
        include_consts = INCLUDE_CONSTANTS
        builder.build_standard_prelude(
            num_qubits=circuit_ast.qubits,
            num_clbits=circuit_ast.clbits,
            include_vars=INCLUDE_VARS,
            include_constants=include_consts,
        )

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

    def _convert_ast_operations(self, builder: QASM3Builder, circuit_ast) -> None:
        """Convert AST operations to QASM."""
        builder.add_section_comment("Circuit operations")

        for idx, op in enumerate(circuit_ast.operations):
            if isinstance(op, GateNode):
                self._convert_gate_node(builder, idx, op)
            elif isinstance(op, MeasurementNode):
                self._convert_measurement_node(builder, idx, op)
            elif isinstance(op, ResetNode):
                self._convert_reset_node(builder, idx, op)
            elif isinstance(op, BarrierNode):
                self._convert_barrier_node(builder, idx, op)
            elif isinstance(op, ForLoopNode):
                self._convert_for_loop_node(builder, idx, op)
            elif isinstance(op, IfStatementNode):
                self._convert_if_statement_node(builder, idx, op)
            else:
                raise UnsupportedCircuitError(f"Unsupported AST operation: {type(op).__name__}")

    def _convert_gate_node(self, builder: QASM3Builder, idx: int, op: GateNode) -> None:
        """Convert a gate node to QASM (every validated gate; nothing becomes a comment)."""
        qubits_str = [f"q[{i}]" for i in op.qubits]
        name = 'cx' if op.name == 'cnot' else op.name
        if VERBOSE:
            vprint(f"[QiskitToQASM3Converter] [{idx}] GateNode name={name} qubits={op.qubits} params={op.parameters} modifiers={getattr(op, 'modifiers', None)}")
        if name not in GATE_SIGNATURES:
            raise UnsupportedCircuitError(f"Unsupported gate: {name}")
        params = [builder.format_parameter(p) for p in (op.parameters or [])]
        modifiers = getattr(op, 'modifiers', None) or None
        if name == 'gphase':
            builder.apply_gate('gphase', [], parameters=params)
            return
        builder.apply_gate(name, qubits_str, parameters=params or None, modifiers=modifiers)

    def _convert_measurement_node(self, builder: QASM3Builder, idx: int, op: MeasurementNode) -> None:
        """Convert a measurement node to QASM."""
        if VERBOSE:
            vprint(f"[QiskitToQASM3Converter] [{idx}] Measurement q[{op.qubit}] -> c[{op.clbit}]")
        builder.add_measurement(f"q[{op.qubit}]", f"c[{op.clbit}]")

    def _convert_reset_node(self, builder: QASM3Builder, idx: int, op: ResetNode) -> None:
        """Convert a reset node to QASM."""
        if VERBOSE:
            vprint(f"[QiskitToQASM3Converter] [{idx}] Reset q[{op.qubit}]")
        builder.add_reset(f"q[{op.qubit}]")

    def _convert_barrier_node(self, builder: QASM3Builder, idx: int, op: BarrierNode) -> None:
        """Convert a barrier node to QASM."""
        if op.qubits:
            if VERBOSE:
                vprint(f"[QiskitToQASM3Converter] [{idx}] Barrier on {op.qubits}")
            builder.add_barrier([f"q[{i}]" for i in op.qubits])
        else:
            if VERBOSE:
                vprint(f"[QiskitToQASM3Converter] [{idx}] Barrier on all qubits")
            builder.add_barrier(None)

    def _convert_for_loop_node(self, builder: QASM3Builder, idx: int, op: ForLoopNode) -> None:
        """Convert a for loop node to QASM."""
        if VERBOSE:
            vprint(f"[QiskitToQASM3Converter] [{idx}] ForLoop: {op.variable} in range({op.range_start}, {op.range_end})")
        
        # OpenQASM 3.0 for loop syntax: for int i in [0:7] { ... }
        # Note: range_end is exclusive in Python, but inclusive in OpenQASM range syntax
        # So Python range(8) = [0,1,2,3,4,5,6,7] becomes [0:7] in OpenQASM
        if isinstance(op.range_end, int) and isinstance(op.range_start, int):
            openqasm_end = op.range_end - 1 if op.range_end > op.range_start else op.range_start
            range_spec = f"[{op.range_start}:{openqasm_end}]"
        else:
            # Symbolic range (e.g., from [0:n])
            # OpenQASM 3.0 range syntax is inclusive, Python's is exclusive
            range_spec = f"[{op.range_start}:{op.range_end}-1]"
        variable_decl = f"int {op.variable}"
        
        # Convert loop body operations to QASM statements
        body_statements = []
        saved_lines = builder.lines
        builder.lines = body_statements
        
        # Recursively convert all operations in the loop body
        for body_op in op.body:
            if isinstance(body_op, GateNode):
                self._convert_gate_node(builder, 0, body_op)
            elif isinstance(body_op, MeasurementNode):
                self._convert_measurement_node(builder, 0, body_op)
            elif isinstance(body_op, ResetNode):
                self._convert_reset_node(builder, 0, body_op)
            elif isinstance(body_op, BarrierNode):
                self._convert_barrier_node(builder, 0, body_op)
            elif isinstance(body_op, ForLoopNode):
                self._convert_for_loop_node(builder, 0, body_op)
            elif isinstance(body_op, IfStatementNode):
                self._convert_if_statement_node(builder, 0, body_op)
        
        # Extract statements (they're already indented by the builder)
        body_statements = builder.lines
        builder.lines = saved_lines
        
        # Add the for loop using the builder
        builder.add_for_loop(variable_decl, range_spec, body_statements)

    def _convert_if_statement_node(self, builder: QASM3Builder, idx: int, op: IfStatementNode) -> None:
        """Convert an if statement node to QASM."""
        if VERBOSE:
            vprint(f"[QiskitToQASM3Converter] [{idx}] IfStatement: {op.condition}")
        
        # Convert if body operations to QASM statements
        if_body_statements = []
        saved_lines = builder.lines
        builder.lines = if_body_statements
        
        # Recursively convert all operations in the if body
        for body_op in op.body:
            if isinstance(body_op, GateNode):
                self._convert_gate_node(builder, 0, body_op)
            elif isinstance(body_op, MeasurementNode):
                self._convert_measurement_node(builder, 0, body_op)
            elif isinstance(body_op, ResetNode):
                self._convert_reset_node(builder, 0, body_op)
            elif isinstance(body_op, BarrierNode):
                self._convert_barrier_node(builder, 0, body_op)
            elif isinstance(body_op, ForLoopNode):
                self._convert_for_loop_node(builder, 0, body_op)
            elif isinstance(body_op, IfStatementNode):
                self._convert_if_statement_node(builder, 0, body_op)
        
        # Extract statements
        if_body_statements = builder.lines
        builder.lines = saved_lines
        
        # Convert else body if present
        else_body_statements = None
        if op.else_body:
            else_body_statements = []
            builder.lines = else_body_statements
            
            for body_op in op.else_body:
                if isinstance(body_op, GateNode):
                    self._convert_gate_node(builder, 0, body_op)
                elif isinstance(body_op, MeasurementNode):
                    self._convert_measurement_node(builder, 0, body_op)
                elif isinstance(body_op, ResetNode):
                    self._convert_reset_node(builder, 0, body_op)
                elif isinstance(body_op, BarrierNode):
                    self._convert_barrier_node(builder, 0, body_op)
                elif isinstance(body_op, ForLoopNode):
                    self._convert_for_loop_node(builder, 0, body_op)
                elif isinstance(body_op, IfStatementNode):
                    self._convert_if_statement_node(builder, 0, body_op)
            
            else_body_statements = builder.lines
            builder.lines = saved_lines
        
        # Add the if statement using the builder
        builder.add_if_statement(op.condition, if_body_statements, else_body_statements)

    def _log_ast_conversion_complete(self, start_time: float) -> None:
        """Log completion of AST conversion."""
        if VERBOSE:
            vprint(f"[QiskitToQASM3Converter] Build done in {(time.time()-start_time)*1000:.1f} ms")

    def convert(self, qiskit_source: str) -> ConversionResult:
        """
        Convert Qiskit source code to OpenQASM 3.0 format using AST-based parsing.

        This method uses AST parsing for secure translation without code execution.
        It parses the source code to extract circuit operations without executing
        potentially unsafe code.

        Args:
            qiskit_source (str): Complete Qiskit source code defining circuit operations

        Returns:
            ConversionResult: Object containing QASM code and conversion statistics

        Raises:
            ValueError: If source code is invalid or cannot be parsed
            ImportError: If Qiskit dependencies are missing
            RuntimeError: If conversion process fails

        Example:
            >>> converter = QiskitToQASM3Converter()
            >>> source = '''
            ... from qiskit import QuantumCircuit
            ... n_bits = 8
            ... qc = QuantumCircuit(n_bits, n_bits)
            ... for i in range(n_bits):
            ...     qc.h(i)
            ... qc.measure(range(n_bits), range(n_bits))
            ... '''
            >>> result = converter.convert(source)
            >>> print(f"Circuit has {result.stats.n_qubits} qubits")
        """
        # Preprocess source code for compatibility
        qiskit_source = self._preprocess_qiskit_source(qiskit_source)

        # Try AST-based path first (secure, no execution)
        try:
            if VERBOSE:
                vprint("[QiskitToQASM3Converter] Attempt AST-based translation")
            parser = QiskitASTParser()
            circuit_ast = parser.parse(qiskit_source)
            validate_circuit_ast(circuit_ast, "Qiskit")
            stats = self._analyze_circuit_ast(circuit_ast)
            qasm3_program = self._convert_ast_to_qasm3(circuit_ast)
            return ConversionResult(qasm_code=qasm3_program, stats=stats)
        except Exception as e:
            if VERBOSE:
                vprint(f"[QiskitToQASM3Converter] AST failed: {e}")

        # Fallback: execute source to obtain QuantumCircuit
        if VERBOSE:
            vprint("[QiskitToQASM3Converter] Falling back to runtime execution path")
        try:
            circuit = self._execute_qiskit_source(qiskit_source)
            stats = self._analyze_qiskit_circuit(circuit)
            qasm3_program = self._convert_to_qasm3(circuit)
            return ConversionResult(qasm_code=qasm3_program, stats=stats)
        except Exception as e:
            raise ValueError(f"Failed to convert Qiskit source code: {str(e)}")


# Public API function for easy module usage
def convert_qiskit_to_qasm3(qiskit_source: str) -> ConversionResult:
    """
    Convert Qiskit quantum circuit source code to OpenQASM 3.0 format.
    
    This is a convenience function that creates a converter instance and performs
    the conversion in a single call, returning a ConversionResult object.
    
    Args:
        qiskit_source (str): Complete Qiskit source code defining get_circuit() function
        
    Returns:
        ConversionResult: Object containing QASM code and conversion statistics
        
    Raises:
        ValueError: If source code is invalid or doesn't define required function
        ImportError: If Qiskit dependencies are missing
        RuntimeError: If conversion process fails
        
    Example:
        >>> from qiskit_qasm_converter import convert_qiskit_to_qasm3
        >>> source = '''
        ... from qiskit import QuantumCircuit
        ... def get_circuit():
        ...     qc = QuantumCircuit(2, 2)
        ...     qc.h(0)
        ...     qc.cx(0, 1)
        ...     qc.measure([0, 1], [0, 1])
        ...     return qc
        ... '''
        >>> result = convert_qiskit_to_qasm3(source)
        >>> print(result.qasm_code)
    """
    converter = QiskitToQASM3Converter()
    return converter.convert(qiskit_source)