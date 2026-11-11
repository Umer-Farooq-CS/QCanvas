"""
Cirq AST Parser Module

WHAT THIS FILE DOES:
    Parses Cirq quantum circuit source code using Python's AST module to extract
    circuit operations without executing the code. Provides secure, static analysis
    of Cirq code to build a CircuitAST representation. Identifies Circuit creation,
    gate operations (cirq.H(), cirq.CNOT(), etc.), measurements, resets, and barriers.
    Handles Cirq-specific patterns like LineQubit.range() and constructor-based operations.

HOW IT LINKS TO OTHER FILES:
    - Used by: cirq_to_qasm.py (CirqToQASM3Converter uses CirqASTParser)
    - Uses: circuit_ast.py (builds CircuitAST, GateNode, MeasurementNode, etc.)
    - Uses: config/config.py (VERBOSE flag for debugging output)
    - Part of: Parsers module providing framework-specific parsing logic

INPUT:
    - cirq_source (str): Cirq Python source code
    - Expected format: Code with cirq.Circuit() and gate operations (e.g., cirq.H(q0))
    - Used in: CirqASTParser.parse() method

OUTPUT:
    - CircuitAST: Unified circuit representation with operations list
    - Returned by: CirqASTParser.parse() method
    - Contains: Qubit count, classical bit count, operations (gates, measurements, etc.)

STAGE OF USE:
    - Parsing Stage: First step in AST-based conversion pipeline
    - Security Stage: Provides secure alternative to code execution
    - Used before: AST analysis and QASM code generation
    - Used by: CirqToQASM3Converter.convert() method

TOOLS USED:
    - ast: Python's Abstract Syntax Tree module for parsing source code
    - logging: Debug logging (via config)
    - typing: Type hints for method signatures

PARSING STRATEGY:
    1. AST Visitor Pattern: Uses ast.NodeVisitor to traverse AST nodes
    2. Circuit Detection: Identifies cirq.Circuit() constructor calls
    3. Qubit Tracking: Handles qubit creation patterns (LineQubit.range(), etc.)
    4. Operation Extraction: Visits gate calls (cirq.H(), cirq.CNOT(), etc.) and constructor args
    5. Parameter Extraction: Extracts qubit references, gate parameters, measurement mappings
    6. AST Building: Constructs CircuitAST with GateNode, MeasurementNode, etc.

ARCHITECTURE ROLE:
    Provides secure, static analysis of Cirq code. Enables conversion without
    executing potentially unsafe user code. Part of the parsing layer that bridges
    framework-specific syntax and the unified CircuitAST representation.

Author: QCanvas Team
Date: 2025-08-12
Version: 1.0.0
"""

import ast
import logging
from quantum_converters.config.config import VERBOSE, vprint
from typing import List, Set, Any, Optional, Dict, Tuple, Union
from quantum_converters.base.circuit_ast import (
    CircuitAST, GateNode, MeasurementNode, ResetNode, BarrierNode, ForLoopNode, IfStatementNode
)
from quantum_converters.base.circuit_validation import UnsupportedCircuitError
from quantum_converters.base.safe_eval import NotStatic, static_number

# VERBOSE is imported from config.config


class CirqASTVisitor(ast.NodeVisitor):
    """
    AST visitor that traverses Cirq source code to extract circuit operations.

    This visitor identifies:
    - QuantumCircuit instantiation and configuration
    - Gate operations (h, x, cx, etc.)
    - Measurement operations
    - Reset operations
    - Barrier operations
    - Parameter usage
    """

    def __init__(self):
        self.circuit_vars: Set[str] = set()  # Variables holding Circuit instances
        self.operations: List[Any] = []  # Circuit operations in order
        self.parameters: Set[str] = set()  # Parameter names used
        self.qubits: int = 0  # Number of qubits (estimated)
        self.clbits: int = 0  # Number of classical bits (estimated)
        self.current_circuit: Optional[str] = None  # Current circuit variable being operated on
        self.qubit_vars: Dict[str, int] = {}  # Map variable names to qubit indices
        self.op_vars: Dict[str, Any] = {} # Map variable names to operations
        self.qubit_counter: int = 0  # Counter for qubit indices
        self.clbit_counter: int = 0  # Counter for classical bit indices
        self.measurement_keys: Dict[str, List[int]] = {} # Map measurement keys to list of clbit indices
        self.unsupported_operations: Set[str] = set()
        self.variables: Dict[str, Any] = {}  # Track numeric variable assignments
        self.array_parameters: Dict[str, int] = {}  # Track array parameters and their sizes
        self.qubit_ranges: Dict[str, int] = {}  # var -> size for `q = cirq.LineQubit.range(n)`
        self.loop_stack: List[Tuple[str, int, int]] = []  # enclosing range() loops (var, start, end)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Handle variable assignments, particularly Circuit creation."""
        if VERBOSE:
            vprint("[CirqASTVisitor] visit_Assign: inspecting assignment node")
        
        # Track simple numeric variable assignments like n_bits = 8
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            # Handle numeric variable assignments or simple mathematical expressions
            if isinstance(node.value, (ast.Constant, ast.Num, ast.BinOp, ast.Attribute)):
                val = self._extract_parameter(node.value)
                self.variables[var_name] = val
                if VERBOSE:
                    vprint(f"[CirqASTVisitor] Tracked variable: {var_name} = {val}")
        
        # Check if assigning a Circuit
        if isinstance(node.value, ast.Call) and self._is_cirq_circuit_call(node.value):
            if VERBOSE:
                vprint("[CirqASTVisitor] Detected cirq.Circuit constructor; parsing args")
            # Track the variable name
            if isinstance(node.targets[0], ast.Name):
                var_name = node.targets[0].id
                self.circuit_vars.add(var_name)
                self.current_circuit = var_name

            # Parse Circuit constructor arguments (operations)
            self._parse_circuit_constructor_args(node.value)

        # Check for qubit assignments (LineQubit.range, etc.)
        elif isinstance(node.value, ast.Call) and self._is_qubit_creation(node.value):
            if VERBOSE:
                vprint("[CirqASTVisitor] Detected qubit creation")
            self._handle_qubit_creation(node.targets[0], node.value)

        # Check for operation assignments (measure, gates, etc.)
        elif isinstance(node.value, ast.Call):
            op = self._resolve_operation(node.value)
            if op and isinstance(node.targets[0], ast.Name):
                var_name = node.targets[0].id
                self.op_vars[var_name] = op
                if VERBOSE:
                    vprint(f"[CirqASTVisitor] Tracked operation variable: {var_name}")

        # Check for method calls on circuit variables
        elif isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            if VERBOSE:
                vprint("[CirqASTVisitor] Assignment invokes method; treating as circuit operation if applicable")
            self._handle_circuit_method_call(node.value)

        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Handle function definitions, tracking arguments with defaults."""
        # Track arguments with default values
        if node.args.defaults:
            # defaults is a list of default values for the last N arguments
            num_defaults = len(node.args.defaults)
            args_with_defaults = node.args.args[-num_defaults:]
            for arg, default in zip(args_with_defaults, node.args.defaults):
                val = self._extract_constant_value(default)
                if val is not None:
                    self.variables[arg.arg] = val
                    if VERBOSE:
                        vprint(f"[CirqASTVisitor] Tracked function arg default: {arg.arg} = {val}")

        # Parse the function body for circuit operations
        for stmt in node.body:
            self.visit(stmt)
        # Don't call generic_visit to avoid double processing

    def visit_Expr(self, node: ast.Expr) -> None:
        """Handle expression statements, typically method calls."""
        if VERBOSE:
            vprint("[CirqASTVisitor] visit_Expr: inspecting expression node")
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            self._handle_circuit_method_call(node.value)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Handle for loops in Cirq code."""
        if VERBOSE:
            vprint("[CirqASTVisitor] visit_For: inspecting for loop")
        
        # Extract loop variable
        if not isinstance(node.target, ast.Name):
            self.generic_visit(node)
            return
        
        loop_var = node.target.id
        
        # Track loop variables to avoid them being treated as global parameters
        old_val = self.variables.get(loop_var)
        self.variables[loop_var] = "loop_var"
        
        # Extract range information
        range_start, range_end = self._extract_range(node.iter)
        if range_start is None or range_end is None:
            # Not a simple range() call, skip for now
            self.generic_visit(node)
            return
        
        # Collect operations in the loop body
        loop_body = []
        saved_operations = self.operations
        self.operations = loop_body
        self.loop_stack.append((loop_var, range_start, range_end))
        try:
            # Visit all statements in the loop body
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.loop_stack.pop()
            # Restore operations list
            self.operations = saved_operations
        
        # Create ForLoopNode only if it contains circuit operations
        if loop_body:
            for_loop = ForLoopNode(
                variable=loop_var,
                range_start=range_start,
                range_end=range_end,
                body=loop_body
            )
            self.operations.append(for_loop)
            
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Added for loop: {loop_var} in range({range_start}, {range_end})")
        else:
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Skipping empty for loop: {loop_var}")

        # Restore variable state
        if old_val is not None:
            self.variables[loop_var] = old_val
        else:
            del self.variables[loop_var]

    def visit_If(self, node: ast.If) -> None:
        """Handle if statements in Cirq code."""
        if VERBOSE:
            vprint("[CirqASTVisitor] visit_If: inspecting if statement")
        
        # Skip 'if __name__ == "__main__":' blocks
        if self._is_main_guard(node):
            if VERBOSE:
                vprint("[CirqASTVisitor] Skipping __main__ guard block")
            return

        # Extract condition
        condition = self._extract_condition(node.test)
        
        # Collect operations in the if body
        if_body = []
        saved_operations = self.operations
        self.operations = if_body
        
        # Visit all statements in the if body
        for stmt in node.body:
            self.visit(stmt)
        
        # Collect operations in the else body (if present)
        else_body = None
        if node.orelse:
            else_body = []
            self.operations = else_body
            for stmt in node.orelse:
                self.visit(stmt)
        
        # Restore operations list
        self.operations = saved_operations
        
        # Create IfStatementNode only if it contains circuit operations
        if if_body or else_body:
            if_stmt = IfStatementNode(
                condition=condition,
                body=if_body,
                else_body=else_body
            )
            self.operations.append(if_stmt)
            
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Added if statement: {condition}")
        else:
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Skipping empty if statement: {condition}")

    def _extract_range(self, node: ast.expr) -> Tuple[Optional[int], Optional[int]]:
        """Extract range start and end from a range() call."""
        if not isinstance(node, ast.Call):
            return None, None
        
        if not isinstance(node.func, ast.Name) or node.func.id != 'range':
            return None, None
        
        # Handle range(n) -> [0:n]
        if len(node.args) == 1:
            end = self._extract_constant_value(node.args[0])
            if end is not None:
                return 0, end
        
        # Handle range(start, end) -> [start:end]
        if len(node.args) == 2:
            start = self._extract_constant_value(node.args[0])
            end = self._extract_constant_value(node.args[1])
            if start is not None and end is not None:
                return start, end
        
        return None, None

    def _extract_constant_value(self, node: ast.expr) -> Optional[int]:
        """Extract a constant integer value from an AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int):
                return node.value
        elif isinstance(node, ast.Name):
            # Look up variable in tracked variables
            var_name = node.id
            if var_name in self.variables:
                val = self.variables[var_name]
                if isinstance(val, int):
                    if VERBOSE:
                        vprint(f"[CirqASTVisitor] Resolved range variable: {var_name} = {val}")
                    return val
            return None
        return None

    def _extract_condition(self, node: ast.expr) -> str:
        """
        Extract condition expression as a string representation.
        Supports OpenQASM 3.0 condition syntax including:
        - Comparisons (==, !=, <, >, <=, >=)
        - Boolean operators (and, or, not)
        - Classical register access (c[i], m[i])
        - Variable references
        """
        # Handle boolean operators (and, or, not) - OpenQASM 3.0 supports &&, ||, !
        if isinstance(node, ast.BoolOp):
            op_str = "&&" if isinstance(node.op, ast.And) else "||"
            values = [self._extract_condition(value) for value in node.values]
            return f"({f' {op_str} '.join(values)})"
        
        # Handle unary not operator
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            operand = self._extract_condition(node.operand)
            return f"!{operand}" if not operand.startswith("(") else f"!({operand})"
        
        # Handle comparisons
        if isinstance(node, ast.Compare):
            left = self._extract_condition_operand(node.left)
            ops = [self._extract_comparison_op(op) for op in node.ops]
            comparators = [self._extract_condition_operand(comp) for comp in node.comparators]
            
            if len(ops) == 1 and len(comparators) == 1:
                return f"{left} {ops[0]} {comparators[0]}"
            # Handle chained comparisons (a < b < c) - not standard in OpenQASM but handle gracefully
            elif len(ops) > 1:
                parts = [left]
                for i, (op, comp) in enumerate(zip(ops, comparators)):
                    parts.append(f"{op} {comp}")
                return " && ".join(parts)
        
        # Handle boolean constants
        if isinstance(node, ast.Constant):
            if isinstance(node.value, bool):
                return "true" if node.value else "false"
            return str(node.value)
        
        # Handle name references (variables, classical registers)
        if isinstance(node, ast.Name):
            # Map common Python boolean names to OpenQASM
            if node.id == "True":
                return "true"
            elif node.id == "False":
                return "false"
            return node.id
        
        # Fallback: return a string representation
        try:
            return ast.unparse(node) if hasattr(ast, 'unparse') else str(node)
        except:
            return str(node)

    def _extract_condition_operand(self, node: ast.expr) -> str:
        """
        Extract an operand from a condition.
        Handles constants, variables, array indexing, and classical register access.
        """
        if isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Name):
            # Check if it's a known variable that maps to a classical register
            # In Cirq, measurement results are often accessed via key names
            var_name = node.id
            # Map common classical register variable names to OpenQASM format
            if var_name.startswith('c') and len(var_name) > 1 and var_name[1:].isdigit():
                # Handle c0, c1, etc. -> c[0], c[1]
                return f"c[{var_name[1:]}]"
            return var_name
        elif isinstance(node, ast.Subscript):
            # Handle array indexing like c[i], m[i]
            value = self._extract_condition_operand(node.value)
            if isinstance(node.slice, ast.Index):  # Python < 3.9
                index = self._extract_condition_operand(node.slice.value)
            elif isinstance(node.slice, ast.Constant):  # Python 3.9+
                index = str(node.slice.value)
            elif isinstance(node.slice, ast.Name):
                # Handle variable indices like c[i]
                index = node.slice.id
            else:
                index = self._extract_condition_operand(node.slice)
            return f"{value}[{index}]"
        elif isinstance(node, ast.Attribute):
            # Handle attribute access like measurements[key]
            # For conditions, we typically want just the register name
            if isinstance(node.value, ast.Name):
                # Map common patterns: creg -> c, mreg -> m
                attr_name = node.attr
                if attr_name in ['creg', 'c']:
                    return 'c'
                elif attr_name in ['mreg', 'm']:
                    return 'm'
            return f"{self._extract_condition_operand(node.value)}.{node.attr}"
        return str(node)

    def _extract_comparison_op(self, op: ast.cmpop) -> str:
        """Extract comparison operator as string."""
        op_map = {
            ast.Eq: "==",
            ast.NotEq: "!=",
            ast.Lt: "<",
            ast.LtE: "<=",
            ast.Gt: ">",
            ast.GtE: ">=",
        }
        return op_map.get(type(op), "==")

    def _is_cirq_circuit_call(self, node: ast.Call) -> bool:
        """Check if a call creates a Cirq Circuit."""
        if isinstance(node.func, ast.Name) and node.func.id == 'Circuit':
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'Circuit':
            return True
        return False

    def _is_qubit_creation(self, node: ast.Call) -> bool:
        """Check if a call creates qubits."""
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in ['range', 'LineQubit', 'GridQubit', 'NamedQubit']:
                return True
        return False

    def _line_qubit_indices(self, call_node) -> List[int]:
        """
        Cirq qubit identity: cirq.LineQubit(k) is qubit k, LineQubit.range(a, b) is
        qubits a..b-1 (two range() calls of the same size are the SAME qubits).
        Grid/Named qubits have no static integer identity -> runtime path.
        """
        func = call_node.func
        owner = func.value.attr if isinstance(func.value, ast.Attribute) else getattr(func.value, 'id', None)
        if func.attr == 'range':
            if owner != 'LineQubit':
                raise UnsupportedCircuitError(f"{owner}.range(...) qubits are not supported statically")
            ints = {k: v for k, v in self.variables.items() if isinstance(v, int) and not isinstance(v, bool)}
            try:
                bounds = [int(static_number(a, ints)) for a in call_node.args]
            except NotStatic:
                raise UnsupportedCircuitError("could not determine the size of a LineQubit.range(...)")
            if not 1 <= len(bounds) <= 3 or call_node.keywords:
                raise UnsupportedCircuitError("unsupported LineQubit.range(...) call")
            return list(range(*bounds))
        if func.attr == 'LineQubit':
            if len(call_node.args) != 1 or call_node.keywords:
                raise UnsupportedCircuitError("unsupported cirq.LineQubit(...) call")
            ints = {k: v for k, v in self.variables.items() if isinstance(v, int) and not isinstance(v, bool)}
            try:
                return [int(static_number(call_node.args[0], ints))]
            except NotStatic:
                raise UnsupportedCircuitError("could not determine a cirq.LineQubit index statically")
        raise UnsupportedCircuitError(f"cirq.{func.attr}(...) qubits are not supported statically")

    def _handle_qubit_creation(self, target, call_node):
        """Handle qubit creation and assignment."""
        indices = self._line_qubit_indices(call_node)
        if indices:
            self.qubit_counter = max(self.qubit_counter, max(indices) + 1)
        if isinstance(target, ast.Tuple):
            if len(target.elts) != len(indices) or not all(isinstance(e, ast.Name) for e in target.elts):
                raise UnsupportedCircuitError("qubit unpacking does not match the number of qubits")
            for elt, idx in zip(target.elts, indices):
                self.qubit_vars[elt.id] = idx
        elif isinstance(target, ast.Name):
            if self._is_range_qubit_creation(call_node):
                self.qubit_ranges[target.id] = len(indices)
                for i, idx in enumerate(indices):
                    self.qubit_vars[f"{target.id}[{i}]"] = idx
            else:
                self.qubit_vars[target.id] = indices[0]
        else:
            raise UnsupportedCircuitError("unsupported qubit assignment target")

    def _is_main_guard(self, node: ast.If) -> bool:
        """Check if an if statement is the 'if __name__ == "__main__":' guard."""
        if not isinstance(node.test, ast.Compare):
            return False
        
        # Check __name__
        if not (isinstance(node.test.left, ast.Name) and node.test.left.id == '__name__'):
            return False
        
        # Check ==
        if not (len(node.test.ops) == 1 and isinstance(node.test.ops[0], ast.Eq)):
            return False
            
        # Check "__main__"
        if len(node.test.comparators) != 1:
            return False
        comp = node.test.comparators[0]
        if isinstance(comp, ast.Constant) and comp.value == '__main__':
            return True
        elif isinstance(comp, ast.Str) and comp.s == '__main__':
            return True
            
        return False

    def _is_range_qubit_creation(self, call_node) -> bool:
        """Check if this is a range-based qubit creation."""
        return (isinstance(call_node.func, ast.Attribute) and
                call_node.func.attr == 'range')

    def _parse_circuit_constructor_args(self, circuit_call: ast.Call) -> None:
        """Parse arguments passed to Circuit constructor (operations)."""
        # Circuit constructor arguments are the operations to add
        for arg in circuit_call.args:
            items = arg.elts if isinstance(arg, (ast.List, ast.Tuple)) else [arg]
            for item in items:
                self._append_item(item)
        for kw in circuit_call.keywords:
            self._unsupported(f"cirq.Circuit({kw.arg}=...)")

    def _unsupported(self, what: str) -> None:
        """Record a construct we cannot translate exactly (parse() then fails loudly)."""
        self.unsupported_operations.add(what)

    def _add_ops(self, op) -> None:
        if isinstance(op, list):
            self.operations.extend(op)
        else:
            self.operations.append(op)

    def _append_item(self, item: ast.expr) -> None:
        """Add one operation expression (as passed to Circuit(...) or circuit.append(...))."""
        if isinstance(item, ast.Name):
            if item.id in self.op_vars:
                self._add_ops(self.op_vars[item.id])
            else:
                self._unsupported(f"operation variable '{item.id}'")
            return
        if isinstance(item, ast.Call):
            inner_method = self._extract_method_name(item)
            if inner_method in ('on', 'with_classical_controls') or isinstance(item.func, ast.Call):
                op = self._resolve_operation(item)
                if op is not None:
                    self._add_ops(op)
                    return
                if isinstance(item.func, ast.Call):
                    param_method = self._extract_parameterized_gate_name(item.func)
                    if param_method:
                        before = len(self.unsupported_operations)
                        n_ops = len(self.operations)
                        self._parse_gate_operation(param_method, item.func.args + item.args, item.keywords, item)
                        if len(self.operations) > n_ops or len(self.unsupported_operations) > before:
                            return
                self._unsupported(self._describe(item))
                return
            if inner_method:
                self._parse_gate_operation(inner_method, item.args, item.keywords, item)
                return
        self._unsupported(self._describe(item))

    @staticmethod
    def _describe(node: ast.AST) -> str:
        try:
            text = ast.unparse(node)
        except Exception:
            text = type(node).__name__
        return text if len(text) <= 60 else text[:57] + "..."

    def _parse_operation_call(self, call_node: ast.Call) -> None:
        """Parse a single operation call like cirq.H(q0) or cirq.measure(q0)."""
        op = self._resolve_operation(call_node)
        if op:
            self._add_ops(op)
        else:
            self._unsupported(self._describe(call_node))

    def _resolve_operation(self, call_node: ast.Call) -> Optional[Any]:
        """Resolve a call node to an operation or list of operations."""
        method_name = self._extract_method_name(call_node)
        
        if method_name in ('on', 'with_classical_controls'):
            return self._handle_chained_method(call_node)

        if method_name:
            if VERBOSE:
                self._log_operation_call(method_name, call_node)
            return self._create_gate_operation(method_name, call_node.args, call_node.keywords, call_node)
        
        # Fallback for nested calls
        if isinstance(call_node.func, ast.Call):
            inner_op = self._resolve_operation(call_node.func)
            if inner_op:
                # Merge with current call args/keywords if needed
                # (e.g. cirq.Rx(theta)(q0))
                if isinstance(inner_op, GateNode) and not inner_op.qubits:
                    inner_op.qubits = [self._extract_qubit_index(arg) for arg in call_node.args]
                return inner_op
        return None

    def _handle_chained_method(self, call_node: ast.Call) -> Optional[Any]:
        """Handle chained methods like .with_classical_controls() or .on()."""
        method_name = call_node.func.attr
        base_call = call_node.func.value
        
        if not isinstance(base_call, ast.Call):
            return None
            
        base_op = self._resolve_operation(base_call)
        if not base_op:
            return None
            
        if method_name == 'with_classical_controls':
            # Extract key names
            keys = []
            for arg in call_node.args:
                if isinstance(arg, (ast.Constant, ast.Str)):
                    val = arg.value if isinstance(arg, ast.Constant) else arg.s
                    keys.append(str(val))
            
            if not keys: return base_op
            
            # Map keys to classical bit indices
            conditions = []
            for key in keys:
                if key in self.measurement_keys:
                    # All bits associated with this key should be part of the condition
                    # Default is truthy check (any bit set)
                    key_bits = self.measurement_keys[key]
                    if len(key_bits) == 1:
                        conditions.append(f"c[{key_bits[0]}]")
                    else:
                        bit_conds = [f"c[{idx}]" for idx in key_bits]
                        conditions.append(f"({' || '.join(bit_conds)})")
                else:
                    # If key not seen yet (unlikely in valid logic), allocate one
                    idx = self.clbit_counter
                    self.measurement_keys[key] = [idx]
                    self.clbit_counter += 1
                    conditions.append(f"c[{idx}]")
            
            condition_str = " && ".join(conditions)
            
            # Wrap in IfStatementNode
            body = base_op if isinstance(base_op, list) else [base_op]
            return IfStatementNode(condition=condition_str, body=body)
            
        elif method_name == 'on':
            # Update qubits if base_op is a GateNode
            if isinstance(base_op, GateNode) and call_node.args:
                base_op.qubits = [self._extract_qubit_index(arg) for arg in call_node.args]
            return base_op
            
        return base_op

    def _extract_method_name(self, call_node: ast.Call) -> Optional[str]:
        """Extract the method name from a function call node."""
        if isinstance(call_node.func, ast.Attribute):
            return call_node.func.attr
        elif isinstance(call_node.func, ast.Name):
            return call_node.func.id
        return None

    def _extract_parameterized_gate_name(self, call_node: ast.Call) -> Optional[str]:
        """Extract gate name from parameterized gate pattern like cirq.rx(param) or rx(param)."""
        if isinstance(call_node.func, ast.Attribute):
            if isinstance(call_node.func.value, ast.Name) and call_node.func.value.id == 'cirq':
                return call_node.func.attr
        elif isinstance(call_node.func, ast.Name):
            return call_node.func.id
        return None

    def _log_operation_call(self, method_name: str, call_node: ast.Call) -> None:
        """Log details of an operation call for debugging."""
        operation_type = "cirq operation" if isinstance(call_node.func, ast.Attribute) else "direct operation"
        vprint(f"[CirqASTVisitor] Found {operation_type}: {method_name}")

        if VERBOSE >= 2:  # Only dump args at higher verbosity
            arg_dump = self._dump_args(call_node.args)
            kw_dump = self._dump_keywords(call_node.keywords)
            vprint(f"[CirqASTVisitor]   raw.args={arg_dump}")
            vprint(f"[CirqASTVisitor]   raw.keywords={kw_dump}")

    def _dump_args(self, args: List[ast.expr]) -> List[str]:
        """Dump AST arguments to strings for logging."""
        arg_dump = []
        for a in args:
            try:
                arg_dump.append(ast.dump(a, include_attributes=False))
            except Exception:
                arg_dump.append(str(a))
        return arg_dump

    def _dump_keywords(self, keywords: List[ast.keyword]) -> Dict[str, str]:
        """Dump AST keywords to strings for logging."""
        return {kw.arg: (ast.dump(kw.value, include_attributes=False)
                        if hasattr(ast, 'dump') else str(kw.value))
                for kw in keywords}

    def _handle_circuit_method_call(self, node: ast.Call) -> None:
        """Handle method calls on circuit variables."""
        if not isinstance(node.func, ast.Attribute):
            return

        # Check if the method is called on a circuit variable
        if isinstance(node.func.value, ast.Name) and node.func.value.id in self.circuit_vars:
            method_name = node.func.attr
            
            # circuit.append(op) / circuit.append([op, op, ...])
            if method_name == 'append':
                if not node.args:
                    return
                target = node.args[0]
                items = target.elts if isinstance(target, (ast.List, ast.Tuple)) else [target]
                for item in items:
                    self._append_item(item)
                for kw in node.keywords:
                    # e.g. strategy=cirq.InsertStrategy.NEW only changes moment layout
                    if kw.arg != 'strategy':
                        self._unsupported(f"circuit.append({kw.arg}=...)")
                return

            if method_name in self._MUTATING_CIRCUIT_METHODS:
                self._unsupported(f"circuit.{method_name}(...)")
            # Read-only methods (to_text_diagram, all_qubits, ...) do not change the circuit.

    _MUTATING_CIRCUIT_METHODS = frozenset({
        'insert', 'batch_insert', 'batch_append', 'batch_insert_into', 'batch_remove', 'batch_replace',
        'clear_operations_touching', 'insert_at_frontier', 'insert_into_range', 'extend', '__iadd__',
    })

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """`circuit += op` is not modelled statically."""
        if isinstance(node.target, ast.Name) and node.target.id in self.circuit_vars:
            self._unsupported("circuit += ...")
        self.generic_visit(node)

    def _create_gate_operation(self, method_name: str, args: List[ast.expr], keywords: List[ast.keyword], call_node: ast.Call = None) -> Optional[Any]:
        """Create a gate operation node from a call."""
        # Preparation
        method_upper = method_name.upper()
        
        # Route to appropriate handler
        if method_upper in ['H', 'X', 'Y', 'Z', 'S', 'T', 'SX', 'I', 'ID']:
            qubit = self._extract_qubit_index(args[0]) if args else 0
            return GateNode(name=method_name.lower(), qubits=[qubit])
        elif method_upper in ['CNOT', 'CX', 'CZ', 'CY', 'CH', 'SWAP']:
            if len(args) >= 2:
                q1 = self._extract_qubit_index(args[0])
                q2 = self._extract_qubit_index(args[1])
                return GateNode(name='cx' if method_upper in ('CX', 'CNOT') else method_name.lower(), qubits=[q1, q2])
        elif method_upper in ['RX', 'RY', 'RZ']:
            # Handle parameterized rotations
            kw_param = None
            for kw in keywords or []:
                if kw.arg in ['rads', 'theta', 'exponent', 'half_turns']:
                    kw_param = self._extract_parameter(kw.value)
                    if kw.arg in ['exponent', 'half_turns']:
                        kw_param = f"({kw_param})*pi"
            name = method_name.lower()
            if len(args) >= 2:
                return GateNode(name=name, qubits=[self._extract_qubit_index(args[1])],
                                parameters=[self._extract_parameter(args[0])])
            if len(args) == 1:
                if kw_param is not None:
                    # Merged form Rx(rads=t)(q): the single positional arg is the qubit.
                    return GateNode(name=name, qubits=[self._extract_qubit_index(args[0])], parameters=[kw_param])
                # Factory form cirq.rx(theta): the outer call supplies the qubit.
                return GateNode(name=name, qubits=[], parameters=[self._extract_parameter(args[0])])
            if kw_param is not None:
                # cirq.Rx(rads=theta): the outer call supplies the qubit.
                return GateNode(name=name, qubits=[], parameters=[kw_param])
            return None
        elif method_upper == 'RESET':
            if args:
                qubit = self._extract_qubit_index(args[0])
                return ResetNode(qubit=qubit)
        elif method_upper in ('CCZ', 'ISWAP'):
            n = 3 if method_upper == 'CCZ' else 2
            if len(args) == n:
                return GateNode(name=method_upper.lower(), qubits=[self._extract_qubit_index(a) for a in args])
        elif method_upper in ('TOFFOLI', 'CCX', 'CCNOT'):
            if len(args) >= 3:
                q0 = self._extract_qubit_index(args[0])
                q1 = self._extract_qubit_index(args[1])
                q2 = self._extract_qubit_index(args[2])
                return GateNode(name='ccx', qubits=[q0, q1, q2])
        elif method_upper in ('FREDKIN', 'CSWAP'):
            if len(args) >= 3:
                q0 = self._extract_qubit_index(args[0])
                q1 = self._extract_qubit_index(args[1])
                q2 = self._extract_qubit_index(args[2])
                return GateNode(name='cswap', qubits=[q0, q1, q2])
        elif method_upper in ('MEASURE', 'MEASURE_EACH'):
            if method_upper == 'MEASURE_EACH' and keywords:
                return None
            return self._handle_measurement_cirq_node(args, keywords)
        
        # Fallback to old path if needed or return None
        if VERBOSE:
            vprint(f"[CirqASTVisitor] Unsupported gate for node creation: {method_name}")
        return None

    def _handle_measurement_cirq_node(self, args: List[ast.expr], keywords: List[ast.keyword]) -> Any:
        # Extract key if present
        key = None
        if keywords:
            for kw in keywords:
                if kw.arg == 'key':
                    if isinstance(kw.value, ast.Constant): key = str(kw.value.value)
                    elif isinstance(kw.value, (ast.Str, ast.Constant)): # Handle older and newer ASTs
                        val = kw.value.value if isinstance(kw.value, ast.Constant) else kw.value.s
                        key = str(val)

        for kw in keywords or []:
            if kw.arg != 'key':
                # invert_mask / confusion_map change the recorded bits
                raise UnsupportedCircuitError(f"cirq.measure({kw.arg}=...) is not supported")

        ops = []

        # If we have a key, ensure all qubits in this call are tracked under that key
        if key and key not in self.measurement_keys:
            self.measurement_keys[key] = []

        for qubit in self._expand_qubit_args(args):

            # Use a unique clbit for every measurement *execution*: inside loops each
            # iteration gets its own bit (c[base + flat_iteration_index]).
            clbit = self._allocate_clbit()
            
            if key:
                self.measurement_keys[key].append(clbit)
            
            ops.append(MeasurementNode(qubit=qubit, clbit=clbit))
        
        return ops if len(ops) > 1 else (ops[0] if ops else None)

    def _allocate_clbit(self) -> Union[int, str]:
        if not self.loop_stack:
            clbit = self.clbit_counter
            self.clbit_counter += 1
            return clbit
        total = 1
        for _, start, end in self.loop_stack:
            total *= max(0, end - start)
        base = self.clbit_counter
        self.clbit_counter += total
        terms = []
        stride = 1
        for var, start, end in reversed(self.loop_stack):
            term = var if start == 0 else f"({var}-{start})"
            terms.append(term if stride == 1 else f"{term}*{stride}")
            stride *= max(0, end - start)
        expr = "+".join(reversed(terms))
        return expr if base == 0 else f"{base}+{expr}"

    def _expand_qubit_args(self, args: List[ast.expr]) -> List[Union[int, str]]:
        """Resolve qubit arguments, expanding `*qubits` for LineQubit.range variables."""
        out = []
        for arg in args:
            if isinstance(arg, ast.Starred):
                inner = arg.value
                if isinstance(inner, ast.Name) and inner.id in self.qubit_ranges:
                    out.extend(self.qubit_vars[f"{inner.id}[{i}]"] for i in range(self.qubit_ranges[inner.id]))
                elif isinstance(inner, (ast.List, ast.Tuple)):
                    out.extend(self._extract_qubit_index(e) for e in inner.elts)
                else:
                    raise UnsupportedCircuitError(f"cannot expand '*{self._describe(inner)}' statically")
            elif isinstance(arg, (ast.List, ast.Tuple)):
                out.extend(self._extract_qubit_index(e) for e in arg.elts)
            elif isinstance(arg, ast.Name) and arg.id in self.qubit_ranges:
                out.extend(self.qubit_vars[f"{arg.id}[{i}]"] for i in range(self.qubit_ranges[arg.id]))
            else:
                out.append(self._extract_qubit_index(arg))
        return out

    def _parse_gate_operation(self, method_name: str, args: List[ast.expr], keywords: List[ast.keyword], call_node: ast.Call = None) -> None:
        """Parse a gate operation and add it to operations list."""
        op = self._create_gate_operation(method_name, args, keywords, call_node)
        if op:
            # Fully handled by the node factory (previously this fell through and
            # crashed with UnboundLocalError on `method_upper`).
            if isinstance(op, list): self.operations.extend(op)
            else: self.operations.append(op)
            return

        # Fallback for complex gates not yet in _create_gate_operation
        method_upper = method_name.upper()

        # Route to appropriate handler based on gate type
        if method_upper in ['RX', 'RY', 'RZ']:
            self._handle_parameterized_rotation_gate_cirq(method_name, args, keywords)
        elif method_upper in ['ZPOWGATE', 'RZPOWGATE']:
            self._handle_zpow_gate_cirq(args, call_node)
        elif method_upper == 'PHASEDXPOWGATE':
            self._handle_phased_xpow_gate_cirq(args, call_node)
        elif method_upper == 'CONTROLLEDGATE':
            self._handle_controlled_gate_cirq(args)
        elif method_upper == 'MEASURE':
            self._handle_measurement_cirq(args)
        elif method_upper == 'RESET':
            self._handle_reset_cirq(args)
        elif method_upper in ['TOFFOLI', 'FREDKIN']:
            self._handle_multi_qubit_named_gate(method_name, args)
        elif method_upper in ('CXPOWGATE', 'CZPOWGATE'):
            keywords_all = (call_node.keywords if call_node is not None and call_node.keywords else
                            (call_node.func.keywords if call_node is not None and isinstance(call_node.func, ast.Call) else []))
            exponent = self._extract_keyword_arg(keywords_all, 'exponent', 1.0)
            if exponent not in (1, 1.0):
                self._unsupported(f"{method_name}(exponent={exponent})")
            elif method_upper == 'CXPOWGATE':
                self._handle_cxpow_gate_cirq(args, call_node)
            else:
                self._handle_czpow_gate_cirq(args, call_node)
        else:
            # if VERBOSE:
            vprint(f"[CirqASTVisitor] Unsupported gate: {method_name}")
            self.unsupported_operations.add(method_name)

    def _handle_single_qubit_gate_cirq(self, method_name: str, args: List[ast.expr]) -> None:
        """Handle single-qubit gates in Cirq."""
        if args:
            if VERBOSE:
                vprint("[CirqASTVisitor]   rule=single_qubit_gate -> extract_qubit_index(args[0])")
            qubit = self._extract_qubit_index(args[0])
            gate_name = method_name.lower()
            self.operations.append(GateNode(name=gate_name, qubits=[qubit]))
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Added single-qubit gate {gate_name} on q[{qubit}]")

    def _handle_two_qubit_gate_cirq(self, method_name: str, args: List[ast.expr]) -> None:
        """Handle two-qubit gates in Cirq."""
        if len(args) >= 2:
            if VERBOSE:
                vprint("[CirqASTVisitor]   rule=two_qubit_gate -> extract_qubit_index(args[0,1])")
            qubit1 = self._extract_qubit_index(args[0])
            qubit2 = self._extract_qubit_index(args[1])
            gate_name = 'cx' if method_name in ['CNOT', 'CX'] else method_name.lower()
            self.operations.append(GateNode(name=gate_name, qubits=[qubit1, qubit2]))
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Added two-qubit gate {gate_name} on q[{qubit1}], q[{qubit2}]")

    def _handle_parameterized_rotation_gate_cirq(self, method_name: str, args: List[ast.expr], keywords: List[ast.keyword] = None) -> None:
        """Handle parameterized rotation gates in Cirq."""
        # Try to find angle/param in args or keywords
        param = None
        qubit_node = None
        
        if len(args) >= 2:
            # Standard pattern: gate(param, qubit)
            param = self._extract_parameter(args[0])
            qubit_node = args[1]
        elif len(args) == 1:
            # Patterns like Ry(param)(qubit) where merged args = [param, qubit]
            # OR patterns like Ry(rads=param)(qubit) where merged args = [qubit]
            # We treat the single arg as the qubit, and look for param in keywords
            qubit_node = args[0]
        
        # Check keywords for angle (theta, rads, half_turns, degs, exponent)
        if keywords:
            for kw in keywords:
                if kw.arg in ['rads', 'theta', 'half_turns', 'degs', 'exponent']:
                    param = self._extract_parameter(kw.value)
                    # In Cirq, exponent/half_turns are in units of PI
                    if kw.arg in ['exponent', 'half_turns']:
                        # Convert to PI multiple string for QASM
                        param = f"({param})*pi"
                    break
        
        if qubit_node is not None:
            qubit = self._extract_qubit_index(qubit_node)
            gate_name = method_name.lower()
            
            if param is not None:
                self.operations.append(GateNode(
                    name=gate_name,
                    qubits=[qubit],
                    parameters=[param]
                ))
                if VERBOSE:
                    vprint(f"[CirqASTVisitor] Added rotation gate {gate_name}({param}) on q[{qubit}]")
            else:
                # If no param found, check if maybe it's just a non-parameterized gate
                if VERBOSE:
                    vprint(f"[CirqASTVisitor] Could not extract parameter for {method_name}")

    def _handle_controlled_gate_cirq(self, args: List[ast.expr]) -> None:
        """Handle cirq.ControlledGate(...)(...) constructs."""
        if len(args) < 3:
            self.unsupported_operations.add("ControlledGate")
            return

        base_info = self._extract_controlled_gate_base(args[0])
        if base_info is None:
            self.unsupported_operations.add("ControlledGate")
            return

        qubit_exprs = args[1:]
        outer_controls = len(qubit_exprs) - base_info['qubit_count']
        if outer_controls < 0:
            self.unsupported_operations.add("ControlledGate")
            return

        total_controls = base_info['control_count'] + outer_controls
        gate_name, parameters = self._map_controlled_gate_to_qasm(base_info, total_controls)
        if gate_name is None:
            self.unsupported_operations.add("ControlledGate")
            return

        qubits = [self._extract_qubit_index(q) for q in qubit_exprs]
        self.operations.append(GateNode(
            name=gate_name,
            qubits=qubits,
            parameters=parameters or []
        ))

    def _extract_controlled_gate_base(self, expr: ast.expr) -> Optional[dict]:
        """Extract base gate info from a ControlledGate expression."""
        if isinstance(expr, ast.Call) and isinstance(expr.func, ast.Attribute) and isinstance(expr.func.value, ast.Name) and expr.func.value.id == 'cirq':
            attr = expr.func.attr
            if attr in ['rx', 'ry', 'rz']:
                if not expr.args:
                    return None
                param = self._extract_parameter(expr.args[0])
                return {'kind': attr, 'params': [param], 'control_count': 0, 'qubit_count': 1}
            if attr == 'ZPowGate':
                exponent = None
                if expr.args:
                    exponent = self._extract_parameter(expr.args[0])
                for kw in expr.keywords:
                    if kw.arg == 'exponent':
                        exponent = self._extract_parameter(kw.value)
                if exponent is None:
                    return None
                return {'kind': 'phase', 'params': [exponent], 'control_count': 0, 'qubit_count': 1}
            if attr == 'ControlledGate':
                if not expr.args:
                    return None
                nested = self._extract_controlled_gate_base(expr.args[0])
                if nested is None:
                    return None
                nested['control_count'] += 1
                nested['qubit_count'] += 1
                return nested

        if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name) and expr.value.id == 'cirq':
            attr = expr.attr.lower()
            if attr in ['x', 'y', 'z', 'h']:
                return {'kind': attr, 'params': [], 'control_count': 0, 'qubit_count': 1}

        return None

    def _map_controlled_gate_to_qasm(self, info: dict, total_controls: int) -> tuple[Optional[str], Optional[List[Any]]]:
        """Map base gate info + control count to QASM gate/parameters."""
        kind = info['kind']
        params = info['params']

        if kind == 'y':
            if total_controls == 1:
                return 'cy', []
        elif kind == 'h':
            if total_controls == 1:
                return 'ch', []
        elif kind == 'x':
            if total_controls == 1:
                return 'cx', []
        elif kind == 'z':
            if total_controls == 1:
                return 'cz', []
            if total_controls == 2:
                return 'ccz', []
        elif kind == 'rx':
            if total_controls == 1:
                return 'crx', params
        elif kind == 'ry':
            if total_controls == 1:
                return 'cry', params
        elif kind == 'rz':
            if total_controls == 1:
                return 'crz', params
        elif kind == 'phase':
            if total_controls == 1 and params:
                return 'cp', [self._parameter_times_pi(params[0])]

        return None, None

    def _parameter_times_pi(self, param):
        import numpy as np
        if isinstance(param, (int, float)):
            return param * np.pi
        return f"({param})*pi"

    def _handle_zpow_gate_cirq(self, args: List[ast.expr], call_node: ast.Call) -> None:
        """Handle ZPowGate in Cirq."""
        if args:
            if VERBOSE:
                vprint("[CirqASTVisitor]   rule=zpow_gate -> extract_qubit_index(args[0])")
            qubit = self._extract_qubit_index(args[0])
            # Extract exponent from keyword arguments (for parameterized gates, keywords are in func)
            keywords = call_node.keywords if call_node.keywords else (call_node.func.keywords if isinstance(call_node.func, ast.Call) else [])
            exponent = self._extract_keyword_arg(keywords, 'exponent', 1.0)
            gate_name = 'rz'  # ZPowGate with exponent corresponds to rz gate
            # ZPowGate exponent is in units of π, so multiply by pi
            param = f"{exponent}*pi"
            self.operations.append(GateNode(
                name=gate_name,
                qubits=[qubit],
                parameters=[param]
            ))
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Added ZPowGate rz({param}) on q[{qubit}]")

    def _handle_cxpow_gate_cirq(self, args: List[ast.expr], call_node: ast.Call) -> None:
        """Handle CXPowGate in Cirq."""
        if len(args) >= 2:
            qubit1 = self._extract_qubit_index(args[0])
            qubit2 = self._extract_qubit_index(args[1])
            # For now, treat as standard CX if exponent is 1.0 (default)
            # Full implementation would handle exponent
            self.operations.append(GateNode(name='cx', qubits=[qubit1, qubit2]))
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Added CXPowGate (as cx) on q[{qubit1}], q[{qubit2}]")

    def _handle_czpow_gate_cirq(self, args: List[ast.expr], call_node: ast.Call) -> None:
        """Handle CZPowGate in Cirq."""
        if len(args) >= 2:
            qubit1 = self._extract_qubit_index(args[0])
            qubit2 = self._extract_qubit_index(args[1])
            self.operations.append(GateNode(name='cz', qubits=[qubit1, qubit2]))
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Added CZPowGate (as cz) on q[{qubit1}], q[{qubit2}]")

    def _handle_phased_xpow_gate_cirq(self, args: List[ast.expr], call_node: ast.Call) -> None:
        """Handle PhasedXPowGate in Cirq."""
        if args:
            if VERBOSE:
                vprint("[CirqASTVisitor]   rule=phased_xpow_gate -> extract_qubit_index(args[0])")
            qubit = self._extract_qubit_index(args[0])
            # Extract phase_exponent and exponent from keyword arguments (for parameterized gates, keywords are in func)
            keywords = call_node.keywords if call_node.keywords else (call_node.func.keywords if isinstance(call_node.func, ast.Call) else [])
            phase_exponent = self._extract_keyword_arg(keywords, 'phase_exponent', 0.0)
            exponent = self._extract_keyword_arg(keywords, 'exponent', 1.0)

            # PhasedXPowGate(phase_exponent, exponent) decomposition:
            # Rz(phase_exponent * π) followed by Rx(exponent * π) followed by Rz(-phase_exponent * π)
            # In Cirq, phase_exponent and exponent are in units of π
            phase_param = f"{phase_exponent}*pi"
            rx_param = f"{exponent}*pi"
            neg_phase_param = f"-{phase_exponent}*pi"

            self.operations.append(GateNode(
                name='rz',
                qubits=[qubit],
                parameters=[phase_param]
            ))
            self.operations.append(GateNode(
                name='rx',
                qubits=[qubit],
                parameters=[rx_param]
            ))
            self.operations.append(GateNode(
                name='rz',
                qubits=[qubit],
                parameters=[neg_phase_param]
            ))
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Added PhasedXPowGate as rz({phase_param}) then rx({rx_param}) then rz({neg_phase_param}) on q[{qubit}]")

    def _extract_keyword_arg(self, keywords: List[ast.keyword], arg_name: str, default_value: Any) -> Any:
        """Extract value from keyword arguments."""
        for kw in keywords:
            if kw.arg == arg_name:
                return self._extract_parameter(kw.value)
        return default_value

    def _handle_multi_qubit_named_gate(self, method_name: str, args: List[ast.expr]) -> None:
        """Handle named multi-qubit gates like TOFFOLI/FREDKIN."""
        if method_name == 'TOFFOLI' and len(args) >= 3:
            q0 = self._extract_qubit_index(args[0])
            q1 = self._extract_qubit_index(args[1])
            q2 = self._extract_qubit_index(args[2])
            self.operations.append(GateNode(name='ccx', qubits=[q0, q1, q2]))
        elif method_name == 'FREDKIN' and len(args) >= 3:
            q0 = self._extract_qubit_index(args[0])
            q1 = self._extract_qubit_index(args[1])
            q2 = self._extract_qubit_index(args[2])
            self.operations.append(GateNode(name='cswap', qubits=[q0, q1, q2]))

    def _handle_measurement_cirq(self, args: List[ast.expr]) -> None:
        """Handle measurement operations in Cirq."""
        if len(args) >= 1:
            if VERBOSE:
                vprint("[CirqASTVisitor]   rule=measure -> iterate over all args (qubits)")
            
            # Iterate over all arguments, as each is a qubit being measured
            for arg in args:
                qubit = self._extract_qubit_index(arg)
                # For now, map to same index if possible, or just track it
                # In Cirq, measure(q0, q1) means q0->c0, q1->c1 effectively in simple cases
                # We'll use the qubit index as the clbit index for simplicity in this parser
                self.operations.append(MeasurementNode(qubit=qubit, clbit=qubit))
                if VERBOSE:
                    vprint(f"[CirqASTVisitor] Added measure q[{qubit}] -> c[{qubit}]")

    def _handle_reset_cirq(self, args: List[ast.expr]) -> None:
        """Handle reset operations in Cirq."""
        if args:
            if VERBOSE:
                vprint("[CirqASTVisitor]   rule=reset -> extract_qubit_index(args[0])")
            qubit = self._extract_qubit_index(args[0])
            self.operations.append(ResetNode(qubit=qubit))
            if VERBOSE:
                vprint(f"[CirqASTVisitor] Added reset q[{qubit}]")

    def _extract_qubit_index(self, node: ast.expr) -> Union[int, str]:
        """Extract qubit index from AST node. Returns int for concrete indices, str for variables."""
        if VERBOSE:
            try:
                vprint(f"[CirqASTVisitor]   _extract_qubit_index node={ast.dump(node, include_attributes=False)}")
            except Exception:
                vprint("[CirqASTVisitor]   _extract_qubit_index node=<dump failed>")

        # Route to appropriate handler based on node type
        if isinstance(node, ast.Constant):  # Python 3.8+
            return self._handle_constant_node(node)
        elif isinstance(node, ast.Name):
            return self._handle_name_node(node)
        elif isinstance(node, ast.Subscript):
            return self._handle_subscript_node(node)
        elif isinstance(node, ast.Call):
            # Handle cirq.LineQubit(i) where i is a variable
            return self._handle_call_qubit_node(node)
        elif isinstance(node, ast.BinOp):
            try:
                return int(static_number(node, {k: v for k, v in self.variables.items() if isinstance(v, int)}))
            except NotStatic:
                return ast.unparse(node).replace(' ', '')
        raise UnsupportedCircuitError(f"cannot resolve qubit '{self._describe(node)}' statically")

    # Removed deprecated ast.Num handler; ast.Constant path covers ints

    def _handle_constant_node(self, node: ast.Constant) -> int:
        """Handle constant nodes (Python 3.8+)."""
        return node.value

    def _handle_name_node(self, node: ast.Name) -> Union[int, str]:
        """Handle name/variable nodes."""
        # Check if it's a known qubit variable
        if node.id in self.qubit_vars:
            return self.qubit_vars[node.id]
        # Return variable name as string (for loop variables like 'i')
        return node.id

    def _handle_subscript_node(self, node: ast.Subscript) -> Union[int, str]:
        """Handle subscript/array access nodes."""
        # Handle array access like qubits[0]
        if isinstance(node.value, ast.Name):
            base_name = node.value.id
            index_node = node.slice
            
            # Python < 3.9 wraps index in ast.Index
            if hasattr(ast, 'Index') and isinstance(index_node, ast.Index):
                index_node = index_node.value
                
            if isinstance(index_node, (ast.Num, ast.Constant)):
                index = index_node.n if isinstance(index_node, ast.Num) else index_node.value
                if isinstance(index, int):
                    key = f"{base_name}[{index}]"
                    if key in self.qubit_vars:
                        return self.qubit_vars[key]
                    return index
            elif isinstance(index_node, ast.Name):
                key_var = index_node.id
                if key_var in self.variables and isinstance(self.variables[key_var], int):
                    key = f"{base_name}[{self.variables[key_var]}]"
                    if key in self.qubit_vars:
                        return self.qubit_vars[key]
                if base_name in self.qubit_ranges:
                    # q[i] inside a loop over the range variable
                    return index_node.id
        raise UnsupportedCircuitError(f"cannot resolve qubit '{self._describe(node)}' statically")

    def _handle_call_qubit_node(self, node: ast.Call) -> Union[int, str]:
        """Handle qubit creation calls like cirq.LineQubit(i) where i may be a variable."""
        # Check if it's cirq.LineQubit(something)
        if (isinstance(node.func, ast.Attribute) and
            isinstance(node.func.value, ast.Name) and
            node.func.value.id == 'cirq' and
            node.func.attr == 'LineQubit'):
            if node.args and len(node.args) == 1:
                arg = node.args[0]
                if isinstance(arg, ast.Constant) and isinstance(arg.value, int):
                    return arg.value
                elif isinstance(arg, ast.Name):
                    # Variable index like cirq.LineQubit(i)
                    val = self.variables.get(arg.id)
                    if isinstance(val, int) and not isinstance(val, bool):
                        return val
                    return arg.id
                elif isinstance(arg, ast.BinOp):
                    return ast.unparse(arg).replace(' ', '')
        raise UnsupportedCircuitError(f"cannot resolve qubit '{self._describe(node)}' statically")

    def _extract_parameter(self, node: ast.expr) -> Any:
        """Extract parameter value or name from AST node."""
        if VERBOSE:
            try:
                vprint(f"[CirqASTVisitor]   _extract_parameter node={ast.dump(node, include_attributes=False)}")
            except Exception:
                vprint("[CirqASTVisitor]   _extract_parameter node=<dump failed>")
        if isinstance(node, ast.Num):
            return node.n
        elif isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            # Parameter name - substitute if it's a known variable, else add to parameters set
            param_name = node.id
            if param_name in self.variables:
                val = self.variables[param_name]
                if isinstance(val, (int, float)):
                    return val
                return param_name
            
            self.parameters.add(param_name)
            return param_name
        elif isinstance(node, ast.BinOp):
            # Mathematical expression - do not add to parameters
            return self._extract_expression(node)
        elif isinstance(node, ast.Attribute):
            # Handle attributes like np.pi
            return self._extract_expression(node)
        elif isinstance(node, ast.Subscript):
            # Handle subscripts like gamma[layer]
            return self._extract_expression(node)
        elif isinstance(node, (ast.UnaryOp, ast.Call)):
            try:
                return static_number(node, {k: v for k, v in self.variables.items()
                                            if isinstance(v, (int, float)) and not isinstance(v, bool)})
            except NotStatic:
                pass
        raise UnsupportedCircuitError(f"cannot resolve parameter '{self._describe(node)}' statically")

    def _extract_expression(self, node: ast.expr) -> str:
        """Extract mathematical expression as string."""
        if isinstance(node, ast.BinOp):
            left = self._extract_expression(node.left)
            right = self._extract_expression(node.right)
            op = self._get_op_symbol(node.op)
            return f"{left}{op}{right}"
        elif isinstance(node, ast.Attribute):
            if isinstance(node.value, ast.Name) and node.value.id == 'np' and node.attr == 'pi':
                return 'pi'
            else:
                return f"{self._extract_expression(node.value)}.{node.attr}"
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Num):
            return str(node.n)
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Subscript):
            # Handle array access like gamma[layer]
            base = self._extract_expression(node.value)
            
            # Resolve all indices
            index_node = node.slice
            if hasattr(ast, 'Index') and isinstance(index_node, ast.Index):
                index_node = index_node.value
            
            indices_nodes = index_node.elts if isinstance(index_node, ast.Tuple) else [index_node]
            resolved_indices = []
            for idx_node in indices_nodes:
                val = self._extract_parameter(idx_node)
                if isinstance(val, (int, float)):
                    resolved_indices.append(int(val))
                else:
                    resolved_indices.append(str(val))
            
            if base and base not in self.variables:
                # Update shape tracking
                current_shape = self.array_parameters.get(base, [])
                while len(current_shape) < len(resolved_indices):
                    current_shape.append(1)
                for i, idx in enumerate(resolved_indices):
                    if isinstance(idx, int):
                        current_shape[i] = max(current_shape[i], idx + 1)
                self.array_parameters[base] = current_shape
            
            idx_str = ", ".join(str(idx) for idx in resolved_indices)
            return f"{base}[{idx_str}]"
        else:
            # Fallback for unsupported expressions
            try:
                expr_dump = ast.dump(node, include_attributes=False)
            except Exception:
                expr_dump = "<dump failed>"
            if VERBOSE:
                vprint(f"[CirqASTVisitor]   _extract_expression unsupported node={expr_dump}")
            return "expr"

    def _get_op_symbol(self, op) -> str:
        """Get the symbol for a binary operation."""
        if isinstance(op, ast.Div):
            return '/'
        elif isinstance(op, ast.Mult):
            return '*'
        elif isinstance(op, ast.Add):
            return '+'
        elif isinstance(op, ast.Sub):
            return '-'
        elif isinstance(op, ast.Pow):
            return '**'
        else:
            return '?'


class CirqASTParser:
    """
    Parser for Cirq quantum circuit source code using AST parsing.

    This parser provides a secure alternative to dynamic code execution by
    analyzing the abstract syntax tree of Python source code to extract
    circuit operations.
    """

    def __init__(self):
        self.visitor = CirqASTVisitor()

    def parse(self, source_code: str) -> CircuitAST:
        """
        Parse Cirq source code and return CircuitAST representation.

        Args:
            source_code: Python source code containing Cirq circuit definition

        Returns:
            CircuitAST: Parsed circuit representation

        Raises:
            ValueError: If source code cannot be parsed or doesn't contain valid circuit
        """
        # Log that AST parsing is being used
        if VERBOSE:
            vprint("[CirqASTParser] Starting AST parsing of Cirq source code")
            vprint(f"[CirqASTParser] Source code length: {len(source_code)} characters")

        try:
            # Parse the source code into AST
            tree = ast.parse(source_code)
            if VERBOSE:
                vprint("[CirqASTParser] Parsed source code into AST")
        except SyntaxError as e:
            if VERBOSE:
                vprint(f"[CirqASTParser] Syntax error during AST parsing: {e}")
            raise ValueError(f"Invalid Python syntax in source code: {e}")

        # Reset visitor state
        self.visitor = CirqASTVisitor()

        # Visit all nodes
        self.visitor.visit(tree)

        if VERBOSE:
            vprint(f"[CirqASTParser] Found operations: {len(self.visitor.operations)}")
            vprint(f"[CirqASTParser] Qubits: {self.visitor.qubit_counter}, Clbits: {self.visitor.qubit_counter}")
            vprint(f"[CirqASTParser] Parameters: {list(self.visitor.parameters)}")

        if self.visitor.unsupported_operations:
            unsupported = ", ".join(sorted(self.visitor.unsupported_operations))
            raise UnsupportedCircuitError(f"Unsupported Cirq operations encountered: {unsupported}")

        # Validate that we found a circuit
        if not self.visitor.operations:
            raise ValueError("No circuit operations found in source code. Make sure to define a get_circuit() function or circuit operations.")

        # Count actual measurements to determine classical bits needed
        all_ops = self._flatten_operations(self.visitor.operations)
        max_clbit = -1
        for op in all_ops:
            if isinstance(op, MeasurementNode):
                if isinstance(op.clbit, int):
                    max_clbit = max(max_clbit, op.clbit)
                elif isinstance(op.clbit, str) and op.clbit.isdigit():
                    max_clbit = max(max_clbit, int(op.clbit))

        clbit_count = max(max_clbit + 1, self.visitor.clbit_counter)
        
        # Determine qubit count - use qubit_counter if available, otherwise infer
        qubit_count = self.visitor.qubit_counter
        if qubit_count == 0:
            # Fallback: infer from for loop ranges and operations
            qubit_count = self._infer_qubit_count()
        else:
            # cirq.LineQubit(k) can be used inline without a prior declaration.
            for op in all_ops:
                qs = op.qubits if isinstance(op, GateNode) else ([op.qubit] if isinstance(op, (MeasurementNode, ResetNode)) else [])
                for q in qs:
                    if isinstance(q, int) and not isinstance(q, bool):
                        qubit_count = max(qubit_count, q + 1)
        
        # Create CircuitAST
        circuit_ast = CircuitAST(
            qubits=qubit_count,
            clbits=clbit_count if clbit_count > 0 else qubit_count,
            operations=self.visitor.operations,
            parameters=list(self.visitor.parameters),
            array_parameters=self.visitor.array_parameters
        )

        if VERBOSE:
            vprint("[CirqASTParser] Built CircuitAST")

        return circuit_ast

    def _flatten_operations(self, operations: List[Any]) -> List[Any]:
        """Recursively flatten operations from loops and if statements."""
        flat = []
        for op in operations:
            flat.append(op)
            if isinstance(op, ForLoopNode):
                flat.extend(self._flatten_operations(op.body))
            elif isinstance(op, IfStatementNode):
                flat.extend(self._flatten_operations(op.body))
                if op.else_body:
                    flat.extend(self._flatten_operations(op.else_body))
        return flat

    def _infer_qubit_count(self) -> int:
        """Infer qubit count from operations and for loop ranges."""
        max_qubit = 0
        
        for op in self.visitor.operations:
            # Check ForLoopNode ranges
            if isinstance(op, ForLoopNode):
                if op.range_end is not None:
                    max_qubit = max(max_qubit, op.range_end)
            # Check GateNode qubits
            elif isinstance(op, GateNode):
                for q in op.qubits:
                    if isinstance(q, int):
                        max_qubit = max(max_qubit, q + 1)
            # Check MeasurementNode qubits
            elif isinstance(op, MeasurementNode):
                if isinstance(op.qubit, int):
                    max_qubit = max(max_qubit, op.qubit + 1)
        
        # Also check variables for common patterns like n_bits
        for var_name, value in self.visitor.variables.items():
            if isinstance(value, int) and var_name in ['n_bits', 'n_qubits', 'num_qubits', 'qubits']:
                max_qubit = max(max_qubit, value)
        
        return max_qubit if max_qubit > 0 else 1

    def get_supported_gates(self) -> List[str]:
        """Get list of supported gate operations."""
        return [
            'h', 'x', 'y', 'z', 's', 't', 'sx', 'i',  # Single qubit
            'cx', 'cnot', 'cz', 'cy', 'ch', 'swap',  # Two qubit
            'rx', 'ry', 'rz',  # Parameterized
            'measure', 'reset'  # Special operations
        ]
