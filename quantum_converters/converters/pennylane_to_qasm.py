"""
PennyLane to OpenQASM 3.0 Converter Module

WHAT THIS FILE DOES:
    Converts PennyLane quantum circuit source code to OpenQASM 3.0 format. Implements
    the AbstractConverter interface, supporting both AST-based parsing (secure, preferred)
    and legacy string-based parsing (fallback). Handles PennyLane gates, measurements,
    and device definitions. Generates OpenQASM 3.0 code using QASM3Builder.

HOW IT LINKS TO OTHER FILES:
    - Inherits from: abstract_converter.py (AbstractConverter interface)
    - Uses: pennylane_parser.py (PennyLaneASTParser for AST-based parsing)
    - Uses: qasm3_builder.py (QASM3Builder for code generation)
    - Uses: circuit_ast.py (CircuitAST, GateNode, etc. as intermediate representation)
    - Uses: config/mappings.py (gate name mappings)
    - Returns: ConversionResult (from base/ConversionResult.py)
    - Part of: Converters module implementing framework-specific conversion logic

INPUT:
    - pennylane_code (str): PennyLane Python source code defining a quantum circuit
    - Expected format: Code with qml.device() and qml operations (qnode functions)
    - Used in: convert() method (primary entry point)

OUTPUT:
    - ConversionResult: Contains OpenQASM 3.0 code string and conversion statistics
    - Returned by: convert() method
    - Includes: QASM code, qubit count, depth, gate counts, measurement flags

STAGE OF USE:
    - Conversion Stage: Primary converter for PennyLane framework
    - API Stage: Called by API endpoints when source framework is PennyLane
    - Used after: Framework detection/selection
    - Used before: Validation and response formatting

TOOLS USED:
    - numpy: Numerical operations and constant detection
    - re: Regular expressions for string-based parsing (legacy fallback)
    - ast: Python AST module (via PennyLaneASTParser)
    - time: Performance timing for conversion steps
    - typing: Type hints for method signatures

CONVERSION STRATEGY:
    1. AST-based parsing (preferred): Uses PennyLaneASTParser to extract operations
    2. Legacy parsing (fallback): String-based regex parsing if AST parsing fails
    3. AST to QASM: Converts CircuitAST to OpenQASM 3.0 using QASM3Builder
    4. Statistics: Analyzes circuit for qubits, depth, gate counts, measurements

ARCHITECTURE ROLE:
    Implements PennyLane-specific conversion logic, bridging PennyLane source code and
    OpenQASM 3.0 output. Part of the converter strategy pattern, enabling polymorphic
    framework conversion through the AbstractConverter interface.

Author: QCanvas Team
Date: 2025-08-22
Version: 2.0.0 - Integrated with QASM3Builder
"""
import numpy as np
import re
import re as _re_mod
from typing import List, Dict, Any, Union, Optional
from quantum_converters.base.ConversionResult import ConversionResult, ConversionStats
from quantum_converters.base.qasm3_builder import QASM3Builder
from quantum_converters.base.qasm3_gates import QASM3GateLibrary, GateModifier
from quantum_converters.base.circuit_ast import CircuitAST, GateNode, MeasurementNode, ResetNode, BarrierNode, ForLoopNode, IfStatementNode
from quantum_converters.parsers.pennylane_parser import PennyLaneASTParser
from quantum_converters.base.circuit_validation import (
    GATE_SIGNATURES, UnsupportedCircuitError, validate_circuit_ast,
)
from quantum_converters.base.safe_eval import NotStatic, static_number
from quantum_converters.config.config import VERBOSE, vprint, INCLUDE_VARS, INCLUDE_CONSTANTS
from quantum_converters.config import get_pl_inverse_qasm_map
import time

class PennyLaneToQASM3Converter:
    """
    A converter class that transforms PennyLane quantum circuits to OpenQASM 3.0 format.
    
    This converter supports basic quantum gates including:
    - Single-qubit gates: PauliX, PauliY, PauliZ, Hadamard, S, T, Identity
    - Parameterized gates: RX, RY, RZ, PhaseShift
    - Two-qubit gates: CNOT, CZ, SWAP
    - Three-qubit gates: Toffoli
    
    Attributes:
        pl_inverse_qasm (Mapping[str, str]): PennyLane gate name → OpenQASM mnemonic
    """
    
    def __init__(self):
        """Initialize the converter with centralized, typed mappings."""
        self.pl_inverse_qasm = get_pl_inverse_qasm_map()
    
    def _extract_circuit_info(self, circuit_code: str) -> Dict[str, Any]:
        """
        Extract circuit information from PennyLane code string.

        Args:
            circuit_code (str): The PennyLane circuit code as a string

        Returns:
            Dict[str, Any]: Dictionary containing:
                - num_qubits (int): Number of qubits in the circuit
                - operations (List[str]): List of operation strings
        """
        num_qubits = self._extract_num_qubits(circuit_code)
        operations = self._extract_operations(circuit_code)


        return {
            'num_qubits': num_qubits,
            'operations': operations
        }

    def _extract_num_qubits(self, circuit_code: str) -> int:
        """Extract the number of qubits from the device definition."""
        device_match = re.search(r'qml\.device\([^,]+,\s*wires=(\d+)', circuit_code)
        return int(device_match.group(1)) if device_match else 2

    def _extract_operations(self, circuit_code: str) -> List[str]:
        """Extract quantum operations from the circuit code lines."""
        operations = []
        lines = circuit_code.split('\n')

        for line in lines:
            line = line.strip()
            # Look for qml operations inside a qnode function body
            if self._is_quantum_operation(line):
                operations.append(line)

        return operations

    def _is_quantum_operation(self, line: str) -> bool:
        """Check if a line contains a quantum operation."""
        return (line.startswith('qml.') and
                not line.startswith('qml.expval') and
                not line.startswith('qml.device'))


    def _find_qnode_candidates(self, namespace: Dict[str, Any]) -> List[Any]:
        """Find potential qnode functions in the executed namespace."""
        candidate_funcs = []

        # Prefer a get_circuit returning a callable qnode
        qnode = namespace.get('get_circuit')
        if callable(qnode):
            try:
                qnode = qnode()
            except Exception:
                pass
            if callable(qnode):
                candidate_funcs.append(qnode)

        # Also scan other callables that look like qnodes
        for name, obj in namespace.items():
            if callable(obj) and (hasattr(obj, 'qml') or hasattr(obj, 'device')):
                candidate_funcs.append(obj)

        return candidate_funcs
    
    def _parse_operation(self, op_line: str, num_qubits: int) -> Dict[str, Any]:
        """
        Parse a single PennyLane operation line to extract gate name, parameters, and wires.

        Args:
            op_line (str): A single line of PennyLane operation code

        Returns:
            Dict[str, Any]: Dictionary containing:
                - gate (str): Gate name
                - params (List[str]): List of parameters
                - wires (List[int]): List of wire indices
        """
        # Remove qml. prefix for processing
        op_line = op_line.replace('qml.', '').strip()

        if '(' in op_line:
            return self._parse_parameterized_operation(op_line, num_qubits)
        else:
            return self._parse_simple_operation(op_line)

    def _parse_parameterized_operation(self, op_line: str, num_qubits: int) -> Dict[str, Any]:
        """Parse an operation that has parameters and/or wires in parentheses."""
        gate_name = op_line.split('(')[0]
        params_and_wires = op_line.split('(')[1].rstrip(')')

        param_part, wire_part = self._split_params_and_wires(params_and_wires)
        params = self._parse_parameters(param_part)
        wires = self._parse_wires(wire_part, num_qubits)

        if isinstance(wires, dict) and wires.get('unsupported'):
            return wires  # Return error dict

        return {
            'gate': gate_name,
            'params': params,
            'wires': wires
        }

    def _split_params_and_wires(self, params_and_wires: str) -> tuple:
        """Split the parameter and wire parts of an operation."""
        parts = params_and_wires.split('wires=')

        if len(parts) > 1:
            # Has explicit wires parameter
            param_part = parts[0].rstrip(', ')
            wire_part = parts[1]
        else:
            # Only wires specified, no parameters
            param_part = ''
            wire_part = params_and_wires

        return param_part, wire_part

    def _parse_parameters(self, param_part: str) -> List[str]:
        """Parse the parameter part of an operation."""
        params = []
        if not param_part:
            return params

        param_part = param_part.strip()
        # Handle list format [param1, param2]
        if param_part.startswith('[') and param_part.endswith(']'):
            param_part = param_part[1:-1]

        # Split multiple parameters
        if ',' in param_part:
            params = [p.strip() for p in param_part.split(',')]
        else:
            params = [param_part] if param_part else []

        return params

    def _parse_wires(self, wire_part: str, num_qubits: int) -> Union[List[int], Dict[str, Any]]:
        """Parse the wire indices from an operation."""
        wire_part = wire_part.strip()

        # Expand range(n_qubits) patterns
        if wire_part.startswith('range('):
            return list(range(num_qubits))

        # Handle list format [wire1, wire2]
        if wire_part.startswith('[') and wire_part.endswith(']'):
            wire_part = wire_part[1:-1]

        parts = [p.strip() for p in wire_part.split(',')]
        wires = []
        unsupported = False

        for p in parts:
            wire_index = self._parse_single_wire(p)
            if wire_index is not None:
                wires.append(wire_index)
            else:
                unsupported = True

        if unsupported:
            # Mark operation as unsupported due to dynamic wire indices
            return {'unsupported': True, 'reason': 'dynamic_wires'}

        return wires

    def _parse_single_wire(self, wire_str: str) -> Optional[int]:
        """Parse a single wire index, handling various formats."""
        try:
            return int(wire_str)
        except ValueError:
            # Dynamic wire expressions (e.g. "i + 1") cannot be resolved here.
            return None

    def _parse_simple_operation(self, op_line: str) -> Dict[str, Any]:
        """Parse a simple operation without parameters or parentheses."""
        return {
            'gate': op_line,
            'params': [],
            'wires': []
        }
    
    def _evaluate_parameter(self, param_str: str) -> Union[float, str]:
        """
        Evaluate numerical expressions in parameters, including mathematical constants.

        Args:
            param_str (str): Parameter string that may contain mathematical expressions

        Returns:
            Union[float, str]: Evaluated numerical value or symbolic constant
        """
        # Check for direct mathematical constants first
        constant_value = self._check_direct_constants(param_str)
        if constant_value is not None:
            return constant_value

        # Handle complex expressions with symbolic constants
        symbolic_expr = self._process_symbolic_constants(param_str)
        # Check if symbolic constants are present in the processed expression
        if 'pi' in symbolic_expr or 'e' in symbolic_expr or 'E' in symbolic_expr:
            return symbolic_expr

        # Evaluate numerical expressions
        return self._evaluate_numerical_expression(param_str)

    def _check_direct_constants(self, param_str: str) -> Optional[str]:
        """Check for direct mathematical constant references."""
        stripped = param_str.strip()

        constants = {
            ('np.pi', 'numpy.pi', 'pi', 'math.pi'): "pi",
            ('np.e', 'numpy.e', 'e', 'math.e'): "e",
            ('np.pi/2', 'pi/2'): "pi/2",
            ('np.pi/4', 'pi/4'): "pi/4"
        }

        for constant_names, qasm_name in constants.items():
            if stripped in constant_names:
                return qasm_name

        return None

    def _process_symbolic_constants(self, param_str: str) -> str:
        """Replace numpy constants with symbolic versions."""
        # Replace numpy constants with symbolic versions
        processed_str = param_str.replace('np.pi', 'pi')
        processed_str = processed_str.replace('numpy.pi', 'pi')
        processed_str = processed_str.replace('np.e', 'e')
        processed_str = processed_str.replace('numpy.e', 'e')

        # Return the processed string (will be different if symbolic constants were replaced)
        return processed_str

    def _evaluate_numerical_expression(self, param_str: str) -> Union[float, str]:
        """Safely evaluate numerical expressions."""
        import ast as _ast
        try:
            result = static_number(_ast.parse(param_str.strip(), mode='eval'))
            return self._format_numerical_result(result)
        except (NotStatic, SyntaxError):
            raise UnsupportedCircuitError(f"cannot evaluate parameter '{param_str}' statically")

    def _get_eval_namespace(self) -> Dict[str, Any]:
        """Get the safe namespace for expression evaluation."""
        return {
            "__builtins__": {},
            "pi": np.pi,
            "e": np.e,
            "sqrt": np.sqrt,
            "sin": np.sin,
            "cos": np.cos,
            "tan": np.tan,
        }

    def _format_numerical_result(self, result: Union[int, float]) -> str:
        """Format numerical results, recognizing common constants."""
        if isinstance(result, float):
            # Check for common mathematical constants
            constant_checks = [
                (np.pi, "pi"),
                (np.pi/2, "pi/2"),
                (np.pi/4, "pi/4"),
                (np.e, "e")
            ]

            for constant_value, constant_name in constant_checks:
                if abs(result - constant_value) < 1e-10:
                    return constant_name

            return f"{result:.6f}"
        else:
            return str(result)
    
    def _convert_gate(self, parsed_op: Dict[str, Any]) -> str:
        """
        Convert a parsed PennyLane operation to its OpenQASM 3.0 equivalent.

        Args:
            parsed_op (Dict[str, Any]): Parsed operation containing gate, params, and wires

        Returns:
            str: OpenQASM 3.0 gate instruction string
        """
        if parsed_op.get('unsupported'):
            return self._format_unsupported_operation(parsed_op)

        gate_name = parsed_op['gate']
        qasm_gate = self._get_qasm_gate_name(gate_name)
        if qasm_gate is None:
            return f"// Unsupported gate: {gate_name}"

        params = parsed_op['params']
        wires = parsed_op['wires']

        param_str = self._format_parameters(params)
        wire_str = self._format_wires(wires)

        return f"{qasm_gate}{param_str} {wire_str};"

    def _format_unsupported_operation(self, parsed_op: Dict[str, Any]) -> str:
        """Format an unsupported operation as a comment."""
        return f"// Unsupported PennyLane op: {parsed_op.get('raw')}"

    def _get_qasm_gate_name(self, gate_name: str) -> Optional[str]:
        """Get the OpenQASM equivalent of a PennyLane gate name."""
        return self.pl_inverse_qasm.get(gate_name)

    def _format_parameters(self, params: List[Any]) -> str:
        """Format parameters for OpenQASM output."""
        if not params:
            return ""

        evaluated_params = []
        for param in params:
            if isinstance(param, str):
                evaluated_params.append(self._evaluate_parameter(param))
            else:
                evaluated_params.append(param)

        param_str = ', '.join(str(p) for p in evaluated_params)
        return f"({param_str})"

    def _format_wires(self, wires: List[int]) -> str:
        """Format wire indices for OpenQASM output."""
        return ', '.join(f"q[{w}]" for w in wires)
    
    def _add_pennylane_operation(self, builder: QASM3Builder, parsed_op: Dict[str, Any]):
        """Add a PennyLane operation to the QASM builder."""
        if parsed_op.get('unsupported'):
            raise UnsupportedCircuitError(f"Unsupported PennyLane op: {parsed_op.get('raw') or parsed_op}")

        gate_name = parsed_op['gate']
        params = parsed_op['params']
        wires = parsed_op['wires']

        # Check if gate is supported
        if gate_name not in self.pl_inverse_qasm or self.pl_inverse_qasm[gate_name] not in GATE_SIGNATURES:
            raise UnsupportedCircuitError(f"Unsupported PennyLane gate: {gate_name}")
        n_q, n_p = GATE_SIGNATURES[self.pl_inverse_qasm[gate_name]]
        if len(wires) != n_q or len(params) != n_p:
            raise UnsupportedCircuitError(f"could not parse PennyLane op '{gate_name}' exactly")
        
        qasm_gate = self.pl_inverse_qasm[gate_name]
        qubits_str = [f"q[{w}]" for w in wires]
        
        # Handle parameterized gates
        if params:
            evaluated_params = []
            for param in params:
                if isinstance(param, str):
                    evaluated_params.append(builder.format_parameter(self._evaluate_parameter(param)))
                else:
                    evaluated_params.append(builder.format_parameter(param))
            
            builder.apply_gate(qasm_gate, qubits_str, parameters=evaluated_params)
        else:
            builder.apply_gate(qasm_gate, qubits_str)
    
    # ===== AST-based path (primary) =====
    def _analyze_circuit_ast(self, circuit_ast: CircuitAST) -> ConversionStats:
        try:
            return ConversionStats(
                n_qubits=circuit_ast.qubits,
                depth=circuit_ast.get_depth(),
                n_moments=circuit_ast.get_depth(),
                gate_counts=circuit_ast.get_gate_count(),
                has_measurements=circuit_ast.has_measurements()
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
        qubits_str = [f"q[{i}]" for i in operation.qubits]
        modifiers = operation.modifiers if operation.modifiers else None
        name = operation.name
        if name not in GATE_SIGNATURES:
            raise UnsupportedCircuitError(f"Unsupported gate: {name}")
        params = [builder.format_parameter(p) for p in (operation.parameters or [])]
        if name == 'gphase':
            builder.apply_gate('gphase', [], parameters=params)
            return
        builder.apply_gate(name, qubits_str, parameters=params or None, modifiers=modifiers)

    def _is_standard_gate(self, gate_name: str) -> bool:
        """Check if gate is a standard single-qubit or multi-qubit gate."""
        return gate_name in ['h', 'x', 'y', 'z', 's', 't', 'sx', 'i', 'id', 'swap', 'cx', 'cz', 'cy', 'ch', 'ccx', 'cswap', 'ccz', 'mcx', 'grover']

    def _is_parameterized_gate(self, gate_name: str) -> bool:
        """Check if gate is a parameterized gate."""
        return gate_name in ['rx', 'ry', 'rz', 'p', 'crx', 'cry', 'crz', 'cp', 'gphase']

    def _add_parameterized_gate(self, builder: QASM3Builder, gate_name: str, qubits_str: list,
                               operation: GateNode, modifiers):
        """Add a parameterized gate to the QASM builder."""
        if operation.parameters:
            param = builder.format_parameter(operation.parameters[0])
            builder.apply_gate(gate_name, qubits_str, parameters=[param], modifiers=modifiers)
        else:
            builder.add_comment(f"Parameterized gate {gate_name} missing parameter")

    def _add_ast_barrier_operation(self, builder: QASM3Builder, operation: BarrierNode):
        """Add a barrier operation from AST to QASM builder."""
        if operation.qubits:
            builder.add_barrier([f"q[{i}]" for i in operation.qubits])
        else:
            builder.add_barrier(None)

    def _add_ast_for_loop(self, builder: QASM3Builder, operation: ForLoopNode):
        """Add a for loop from AST to QASM builder."""
        # OpenQASM 3.0 for loop syntax: for int i in [0:7] { ... }
        # Note: range_end is exclusive in Python, but inclusive in OpenQASM range syntax
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
            include_constants=INCLUDE_CONSTANTS
        )

        # ── Array parameters (e.g. theta[0]..theta[3]) ─────────────────────────
        # Emitted as `array[float[64], N] name;` — the OpenQASM 3 syntax that
        # pyqasm parses as ClassicalDeclaration/ArrayType, which the visitor fully
        # supports via visit_ArrayType. This also allows subscript access theta[i].
        if circuit_ast.array_parameters:
            builder.add_section_comment("Array input parameters")
            for param_name, param_shape in sorted(circuit_ast.array_parameters.items()):
                # Format shape as comma-separated list
                shape_str = ", ".join(str(s) for s in param_shape)
                builder.lines.append(f"input array[float[64], {shape_str}] {param_name};")
            builder.add_blank_line()

        # ── Simple scalar parameters (bare variable names used in gates) ────────
        # Filter out names that were already declared as array parameters above.
        scalar_params = [
            p for p in (circuit_ast.parameters or [])
            if p not in circuit_ast.array_parameters
        ]
        if scalar_params:
            builder.add_section_comment("Scalar input parameters")
            for param_name in scalar_params:
                builder.add_input_directive(param_name, 'float[64]')
            builder.add_blank_line()

        # We skip declaring circuit_ast.variables because they are used internally
        # during PennyLane AST parsing to expand loops and resolve parameters.
        # Emitting them to QASM can cause name collisions with reserved keywords (e.g., 'bit').

        builder.add_section_comment("Circuit operations")
        for op in circuit_ast.operations:
            self._add_ast_operation(builder, op)
        return builder.get_code()


    def convert(self, pennylane_code: str) -> ConversionResult:
        """
        Convert PennyLane quantum circuit code to OpenQASM 3.0 format with statistics.

        Args:
            pennylane_code (str): Complete PennyLane circuit code as a string

        Returns:
            ConversionResult: Object containing QASM code and conversion statistics

        Raises:
            ValueError: If the input code cannot be parsed or contains unsupported operations
        """
        # First try AST-based conversion (preferred)
        self._last_ast_error = None
        ast_result = self._try_ast_conversion(pennylane_code)
        if ast_result is not None:
            return ast_result
        if isinstance(self._last_ast_error, UnsupportedCircuitError):
            # The program uses something we cannot translate exactly; say so instead of
            # producing an approximate circuit.
            raise ValueError(f"Failed to convert PennyLane code to OpenQASM 3.0: {self._last_ast_error}")

        # Fall back to legacy conversion (strict: raises on anything it cannot parse exactly)
        try:
            return self._convert_legacy(pennylane_code)
        except ValueError as legacy_error:
            if self._last_ast_error is not None:
                raise ValueError(f"Failed to convert PennyLane code to OpenQASM 3.0: {self._last_ast_error}") from legacy_error
            raise

    def _convert_legacy(self, pennylane_code: str) -> ConversionResult:
        """Convert using the legacy parsing approach."""
        try:
            circuit_info = self._extract_circuit_info(pennylane_code)
            loop_info = self._detect_loop_patterns(pennylane_code)

            if VERBOSE:
                vprint("[PennyLaneToQASM3Converter] Legacy path: building prelude and emitting operations")

            builder = self._initialize_builder(circuit_info)
            stats = self._process_operations(builder, circuit_info, loop_info)

            code = builder.get_code()
            if VERBOSE:
                vprint("[PennyLaneToQASM3Converter] QASM generated (legacy), length:", len(code))

            return ConversionResult(qasm_code=code, stats=stats)

        except Exception as e:
            raise ValueError(f"Failed to convert PennyLane code to OpenQASM 3.0: {str(e)}")

    def _initialize_builder(self, circuit_info: Dict[str, Any]) -> QASM3Builder:
        """Initialize the QASM3 builder with prelude and sections."""
        num_qubits = circuit_info['num_qubits']
        operations = circuit_info['operations']

        builder = QASM3Builder()

        # Check if measurements exist
        has_measurements = any('measure' in op.lower() for op in operations)
        num_clbits = num_qubits if has_measurements else 0

        # Build standard prelude
        builder.build_standard_prelude(
            num_qubits=num_qubits,
            num_clbits=num_clbits,
            include_vars=INCLUDE_VARS,
            include_constants=INCLUDE_CONSTANTS
        )

        # Add sections
        self._add_builder_sections(builder)

        return builder

    def _add_builder_sections(self, builder: QASM3Builder):
        """Add standard sections to the builder."""
        builder.add_section_comment("Gate definitions")
        builder.add_comment("(Custom gate definitions would go here)")
        builder.add_blank_line()

        builder.add_section_comment("Circuit operations")

    def _process_operations(self, builder: QASM3Builder, circuit_info: Dict[str, Any],
                          loop_info: Dict[str, Any]) -> ConversionStats:
        """Process all operations and collect statistics."""
        operations = circuit_info['operations']
        num_qubits = circuit_info['num_qubits']

        gate_counts = {}
        has_measurements = False
        depth = 0

        for op_line in operations:
            expanded_lines = self._expand_operation_lines(op_line, num_qubits, loop_info)

            for line in expanded_lines:
                parsed_op = self._parse_operation(line, num_qubits)
                self._add_pennylane_operation(builder, parsed_op)

                # Update statistics
                gate_name = parsed_op.get('gate', '')
                if not parsed_op.get('unsupported') and gate_name:
                    gate_counts[gate_name] = gate_counts.get(gate_name, 0) + 1
                    if 'measure' in gate_name.lower():
                        has_measurements = True
                    depth += 1

        return ConversionStats(
            n_qubits=num_qubits,
            depth=depth,
            n_moments=depth,
            gate_counts=gate_counts,
            has_measurements=has_measurements
        )

    def _expand_operation_lines(self, op_line: str, num_qubits: int, loop_info: Dict[str, Any]) -> List[str]:
        """Expand operation lines based on detected loop patterns."""
        expanded_lines = [op_line]

        # Expand loops when the wires use the loop variable
        if loop_info.get('loop_var') and self._should_expand_wire_loops(op_line, loop_info['loop_var']):
            expanded_lines = self._expand_wire_loops(op_line, num_qubits, loop_info)

        # Expand over layers if parameters index by layer
        final_lines = self._expand_layer_loops(expanded_lines, op_line, loop_info)

        return final_lines

    def _should_expand_wire_loops(self, op_line: str, loop_var: str = 'i') -> bool:
        """Check if operation line needs wire loop expansion."""
        return bool(_re_mod.search(rf"wires\s*=\s*\[?[^\]\)]*\b{_re_mod.escape(loop_var)}\b", op_line))

    def _expand_wire_loops(self, op_line: str, num_qubits: int, loop_info: Dict[str, Any]) -> List[str]:
        """Expand wire loops, substituting the actual loop variable on word boundaries
        (a plain str.replace('i', ...) corrupted identifiers: PauliX -> Paul0X)."""
        var = loop_info.get('loop_var') or 'i'
        pattern = rf"\b{_re_mod.escape(var)}\b"
        if loop_info.get('has_loop_i_n_minus_1'):
            count = max(0, num_qubits - 1)
        elif loop_info.get('has_loop_i_n'):
            count = num_qubits
        else:
            raise UnsupportedCircuitError(f"cannot determine the range of loop variable '{var}'")
        new_lines = []
        for k in range(count):
            line = _re_mod.sub(pattern, str(k), op_line)
            # fold simple "k + 1" arithmetic produced by the substitution
            line = _re_mod.sub(r"\b(\d+)\s*\+\s*(\d+)\b", lambda m: str(int(m.group(1)) + int(m.group(2))), line)
            line = _re_mod.sub(r"\b(\d+)\s*-\s*(\d+)\b", lambda m: str(int(m.group(1)) - int(m.group(2))), line)
            new_lines.append(line)
        return new_lines

    def _expand_layer_loops(self, expanded_lines: List[str], op_line: str, loop_info: Dict[str, Any]) -> List[str]:
        """Expand layer loops if parameters index by layer."""
        if 'gamma[' in op_line or 'beta[' in op_line:
            # Layer-indexed parameters cannot be resolved by the line-based parser.
            raise UnsupportedCircuitError("layer-indexed parameters (gamma[...], beta[...]) are not supported")
        return expanded_lines


    def _try_ast_conversion(self, pennylane_code: str) -> Optional[ConversionResult]:
        """Try AST-based conversion, return None if it fails."""
        try:
            if VERBOSE:
                vprint("[PennyLaneToQASM3Converter] Attempt AST-based conversion")
            parser = PennyLaneASTParser()
            t_parse = time.time()
            circuit_ast = parser.parse(pennylane_code)
            if VERBOSE:
                vprint(f"[PennyLaneToQASM3Converter] AST parsed in {(time.time()-t_parse)*1000:.1f} ms; analyzing AST")
            t_ana = time.time()
            stats = self._analyze_circuit_ast(circuit_ast)
            if VERBOSE:
                vprint(f"[PennyLaneToQASM3Converter] AST analyzed in {(time.time()-t_ana)*1000:.1f} ms")
            validate_circuit_ast(circuit_ast, "PennyLane")
            qasm = self._convert_ast_to_qasm3(circuit_ast)
            return ConversionResult(qasm_code=qasm, stats=stats)
        except Exception as e:
            self._last_ast_error = e
            return None

    def _detect_loop_patterns(self, pennylane_code: str) -> dict:
        """Detect common loop patterns in the code."""
        p_default = self._extract_default_p(pennylane_code)

        # Detect loops like `for i in range(n - 1):` or `for i in range(n):` (common in Pennylane benchmarks)
        m_n = re.search(r"for\s+(\w+)\s+in\s+range\(\s*(?:n|n_qubits|num_qubits)\s*\)", pennylane_code)
        m_n1 = re.search(r"for\s+(\w+)\s+in\s+range\(\s*(?:n|n_qubits|num_qubits)\s*-\s*1\s*\)", pennylane_code)
        loop_var = (m_n or m_n1).group(1) if (m_n or m_n1) else None

        return {
            'has_loop_i_n': bool(m_n),
            'has_loop_i_n_minus_1': bool(m_n1),
            'loop_var': loop_var,
            'has_layer_loop': 'for layer in range(p):' in pennylane_code,
            'p_default': p_default
        }

    def _extract_default_p(self, pennylane_code: str) -> int:
        """Extract default p value from function signature."""
        try:
            import re as _re
            m = _re.search(r'p\s*=\s*(\d+)', pennylane_code)
            return int(m.group(1)) if m else 2
        except Exception:
            return 2


# Public API function for easy module usage
def convert_pennylane_to_qasm3(pennylane_code: str) -> ConversionResult:
    """
    Convert PennyLane quantum circuit code to OpenQASM 3.0 format with statistics.
    
    Args:
        pennylane_code (str): Complete PennyLane circuit code as a string
        
    Returns:
        ConversionResult: Object containing QASM code and conversion statistics
        
    Raises:
        ValueError: If the input code cannot be parsed or contains unsupported operations
    """
    converter = PennyLaneToQASM3Converter()
    return converter.convert(pennylane_code)