"""
Qiskit AST Parser Module

WHAT THIS FILE DOES:
    Parses Qiskit quantum circuit source code using Python's AST module to extract
    circuit operations without executing the code. Provides secure, static analysis
    of Qiskit code to build a CircuitAST representation. Identifies QuantumCircuit
    creation, gate operations, measurements, resets, and barriers.

HOW IT LINKS TO OTHER FILES:
    - Used by: qiskit_to_qasm.py (QiskitToQASM3Converter uses QiskitASTParser)
    - Uses: circuit_ast.py (builds CircuitAST, GateNode, MeasurementNode, etc.)
    - Uses: config/config.py (VERBOSE flag for debugging output)
    - Part of: Parsers module providing framework-specific parsing logic

INPUT:
    - qiskit_source (str): Qiskit Python source code
    - Expected format: Code with QuantumCircuit() calls and gate operations (e.g., qc.h(0))
    - Used in: QiskitASTParser.parse() method

OUTPUT:
    - CircuitAST: Unified circuit representation with operations list
    - Returned by: QiskitASTParser.parse() method
    - Contains: Qubit count, classical bit count, operations (gates, measurements, etc.)

STAGE OF USE:
    - Parsing Stage: First step in AST-based conversion pipeline
    - Security Stage: Provides secure alternative to code execution
    - Used before: AST analysis and QASM code generation
    - Used by: QiskitToQASM3Converter.convert() method

TOOLS USED:
    - ast: Python's Abstract Syntax Tree module for parsing source code
    - logging: Debug logging (via config)
    - typing: Type hints for method signatures
    - re: Regular expressions for pattern matching (if needed)

PARSING STRATEGY:
    1. AST Visitor Pattern: Uses ast.NodeVisitor to traverse AST nodes
    2. Circuit Detection: Identifies QuantumCircuit() constructor calls
    3. Operation Extraction: Visits method calls on circuit variables (qc.h(), qc.cx(), etc.)
    4. Parameter Extraction: Extracts qubit indices, gate parameters, measurement mappings
    5. AST Building: Constructs CircuitAST with GateNode, MeasurementNode, etc.

ARCHITECTURE ROLE:
    Provides secure, static analysis of Qiskit code. Enables conversion without
    executing potentially unsafe user code. Part of the parsing layer that bridges
    framework-specific syntax and the unified CircuitAST representation.

Author: QCanvas Team
Date: 2025-08-10
Version: 1.0.0
"""

import ast
import re
import numpy as np
import logging
from quantum_converters.config.config import VERBOSE, vprint
from typing import List, Dict, Any, Optional, Set, Tuple, Union
from quantum_converters.base.circuit_ast import (
    CircuitAST, GateNode, MeasurementNode, ResetNode, BarrierNode, ForLoopNode, IfStatementNode
)
from quantum_converters.base.circuit_validation import UnsupportedCircuitError
from quantum_converters.base.safe_eval import NotStatic, static_eval

# VERBOSE is imported from config.config


class QiskitASTVisitor(ast.NodeVisitor):
    """
    AST visitor that traverses Qiskit source code to extract circuit operations.

    This visitor identifies:
    - QuantumCircuit instantiation and configuration
    - Gate operations (h, x, cx, etc.)
    - Measurement operations
    - Reset operations
    - Barrier operations
    - Parameter usage
    """

    def __init__(self):
        self.circuit_vars: Set[str] = set()  # Variables holding QuantumCircuit instances
        self.operations: List[Any] = []  # Circuit operations in order
        self.parameters: Set[str] = set()  # Parameter names used
        self.qubits: int = 0  # Number of qubits
        self.clbits: int = 0  # Number of classical bits
        self.current_circuit: Optional[str] = None  # Current circuit variable being operated on
        self.variables: Dict[str, Any] = {}  # Track variable values
        self.registers: Dict[str, Dict] = {}  # Track Quantum/ClassicalRegister definitions
        self.quantum_registers: Set[str] = set() # Track quantum register names
        self.classical_registers: Set[str] = set()  # Track classical register names
        self.clbit_counter: int = 0  # Counter for automatic clbit allocation
        self.array_parameters: Dict[str, int] = {}  # Track array parameters and their sizes
        self.unsupported_operations: Set[str] = set()  # constructs we cannot translate exactly
        self.qreg_offsets: Dict[str, int] = {}  # quantum register -> first global qubit index
        self.creg_offsets: Dict[str, int] = {}  # classical register -> first global clbit index

    def visit_Assign(self, node: ast.Assign) -> None:
        """Handle variable assignments, particularly QuantumCircuit creation."""
        if VERBOSE:
            vprint("[QiskitASTVisitor] visit_Assign: inspecting assignment node")

        # Track variable assignments
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            var_name = node.targets[0].id
            # Don't store Python variable assignments for classical register names
            if var_name not in self.classical_registers:
                # Tracking a Python variable must not declare circuit parameters.
                params_before = set(self.parameters)
                val = self._extract_parameter(node.value)
                self.parameters = params_before
                if val != 'expr':
                    self.variables[var_name] = val
                    if VERBOSE:
                        vprint(f"[QiskitASTVisitor] Tracked variable: {var_name} = {val}")
                elif isinstance(node.value, ast.Name):
                    if node.value.id in self.variables:
                        self.variables[var_name] = self.variables[node.value.id]
                    elif node.value.id in ('pi', 'np.pi', 'numpy.pi'):
                        self.variables[var_name] = np.pi

        # Check for QuantumRegister / ClassicalRegister
        if isinstance(node.value, ast.Call) and self._is_register_call(node.value):
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Detected Register creation")
            self._handle_register_creation(node.targets[0], node.value)

        # Check if assigning a QuantumCircuit
        if isinstance(node.value, ast.Call) and self._is_quantum_circuit_call(node.value):
            if VERBOSE:
                vprint("[QiskitASTVisitor] Detected QuantumCircuit constructor")
            # Extract circuit dimensions from arguments
            self._extract_circuit_dimensions(node.value)
            # Track the variable name
            if isinstance(node.targets[0], ast.Name):
                var_name = node.targets[0].id
                self.circuit_vars.add(var_name)
                self.current_circuit = var_name

        # Check for method calls on circuit variables
        elif isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            if VERBOSE:
                vprint("[QiskitASTVisitor] Assignment invokes method; treating as circuit operation if applicable")
            func = node.value.func
            if (isinstance(func.value, ast.Name) and func.value.id in self.circuit_vars
                    and func.attr in ('copy', 'compose', 'decompose', 'inverse', 'reverse_bits',
                                      'reverse_ops', 'assign_parameters', 'power', 'repeat',
                                      'control', 'tensor', 'copy_empty_like')):
                self.unsupported_operations.add(f"qc.{func.attr}(...) result")
            else:
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
                        vprint(f"[QiskitASTVisitor] Tracked function arg default: {arg.arg} = {val}")

        # Parse the function body for circuit operations
        for stmt in node.body:
            self.visit(stmt)
        # Don't call generic_visit to avoid double processing

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        """Handle augmented assignments like qc.global_phase += value."""
        if VERBOSE:
            vprint("[QiskitASTVisitor] visit_AugAssign: inspecting augmented assignment node")
        # Check for qc.global_phase += value
        if isinstance(node.target, ast.Attribute) and isinstance(node.target.value, ast.Name) and node.target.value.id in self.circuit_vars and node.target.attr == 'global_phase':
            if VERBOSE:
                vprint("[QiskitASTVisitor] Detected global_phase assignment")
            param = self._extract_parameter(node.value)
            self.operations.append(GateNode(name='gphase', qubits=[], parameters=[param]))
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Added global phase gphase({param})")

        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> None:
        """Handle expression statements, typically method calls."""
        if VERBOSE:
            vprint("[QiskitASTVisitor] visit_Expr: inspecting expression node")
        if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute):
            self._handle_circuit_method_call(node.value)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Handle for loops in Qiskit code."""
        if VERBOSE:
            vprint("[QiskitASTVisitor] visit_For: inspecting for loop")

        if not isinstance(node.target, ast.Name):
            self.generic_visit(node)
            return

        loop_var = node.target.id
        range_start, range_end = self._extract_range(node.iter)
        if isinstance(range_start, str) or isinstance(range_end, str):
            # Symbolic bounds (e.g. a function argument) are not compile-time constants.
            if self._has_circuit_ops(node.body):
                self.unsupported_operations.add(f"for-loop over {ast.unparse(node.iter)}")
                return

        if self._has_circuit_ops(node.body) and range_start is not None and range_end is not None:
            # Preserve control flow in emitted QASM rather than unrolling.
            old_val = self.variables.get(loop_var)
            self.variables[loop_var] = loop_var

            loop_body = []
            saved_operations = self.operations
            self.operations = loop_body
            for stmt in node.body:
                self.visit(stmt)
            self.operations = saved_operations

            if old_val is None:
                self.variables.pop(loop_var, None)
            else:
                self.variables[loop_var] = old_val

            self.operations.append(
                ForLoopNode(
                    variable=loop_var,
                    range_start=range_start,
                    range_end=range_end,
                    body=loop_body,
                )
            )
            return

        if self._has_circuit_ops(node.body):
            self.unsupported_operations.add(f"for-loop over {ast.unparse(node.iter)}")
            return
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:
        """`with qc.if_test((clbit, value)):` -> classically controlled block."""
        if (len(node.items) == 1 and isinstance(node.items[0].context_expr, ast.Call)
                and isinstance(node.items[0].context_expr.func, ast.Attribute)
                and isinstance(node.items[0].context_expr.func.value, ast.Name)
                and node.items[0].context_expr.func.value.id in self.circuit_vars
                and node.items[0].context_expr.func.attr == 'if_test'
                and node.items[0].optional_vars is None):
            call = node.items[0].context_expr
            if len(call.args) != 1 or call.keywords:
                self.unsupported_operations.add("if_test(...) form")
                return
            condition = self._if_test_condition(call.args[0])
            if condition is None:
                return
            body = []
            saved = self.operations
            self.operations = body
            try:
                for stmt in node.body:
                    self.visit(stmt)
            finally:
                self.operations = saved
            self.operations.append(IfStatementNode(condition=condition, body=body, else_body=None))
            return
        if self._has_circuit_ops(node.body):
            self.unsupported_operations.add("with-block around circuit operations")
            return
        self.generic_visit(node)

    def _global_clbit(self, node: ast.expr) -> Optional[int]:
        """Global classical-bit index for cr[k] / qc.clbits[k] / k."""
        if isinstance(node, ast.Subscript):
            idx = self._resolve_int_arg(node.slice)
            if idx is None:
                return None
            base = node.value
            if isinstance(base, ast.Name) and base.id in self.creg_offsets:
                size = self.registers[base.id]['size']
                return self.creg_offsets[base.id] + (idx % size if idx < 0 else idx)
            if (isinstance(base, ast.Attribute) and base.attr == 'clbits'
                    and isinstance(base.value, ast.Name) and base.value.id in self.circuit_vars):
                return idx % self.clbits if idx < 0 else idx
            return None
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        return None

    def _if_test_condition(self, cond: ast.expr) -> Optional[str]:
        if isinstance(cond, ast.Tuple) and len(cond.elts) == 2:
            target, value_node = cond.elts
            value = self._resolve_int_arg(value_node)
            if value is None and isinstance(value_node, ast.Constant) and isinstance(value_node.value, bool):
                value = int(value_node.value)
            if value is None:
                self.unsupported_operations.add("if_test with a non-constant value")
                return None
            bit = self._global_clbit(target)
            if bit is not None:
                return f"c[{bit}] == {int(bool(value))}"
            if isinstance(target, ast.Name) and target.id in self.creg_offsets:
                if self.creg_offsets[target.id] == 0 and self.registers[target.id]['size'] == self.clbits:
                    return f"c == {value}"
        self.unsupported_operations.add(f"if_test({ast.unparse(cond)})")
        return None

    def visit_If(self, node: ast.If) -> None:
        """Handle if statements in Qiskit code."""
        if VERBOSE:
            vprint("[QiskitASTVisitor] visit_If: inspecting if statement")
        
        if self._is_main_guard(node):
            if VERBOSE:
                vprint("[QiskitASTVisitor] Skipping __main__ guard block")
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
                vprint(f"[QiskitASTVisitor] Added if statement: {condition}")
        else:
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Skipping empty if statement: {condition}")

    def _extract_range(self, node: ast.expr) -> Tuple[Optional[int], Optional[int]]:
        """Extract range start and end from a range() call."""
        if not isinstance(node, ast.Call):
            return None, None
        
        if not isinstance(node.func, ast.Name) or node.func.id != 'range':
            return None, None
        
        # Handle range(n) -> [0:n]
        if len(node.args) == 1:
            end = self._extract_range_bound(node.args[0])
            if end is not None:
                return 0, end
        
        # Handle range(start, end) -> [start:end]
        if len(node.args) == 2:
            start = self._extract_range_bound(node.args[0])
            end = self._extract_range_bound(node.args[1])
            if start is not None and end is not None:
                return start, end
        if len(node.args) == 3:
            self.unsupported_operations.add("range() with a step")

        return None, None

    def _extract_range_bound(self, node: ast.expr) -> Union[int, str, None]:
        """Extract a range bound - could be an int or a variable name."""
        val = self._extract_constant_value(node)
        if isinstance(val, int) and not isinstance(val, bool):
            return val
        resolved = self._resolve_int_arg(node)
        if resolved is not None:
            return resolved
        
        # If it's a variable name, return the name string
        if isinstance(node, ast.Name):
            return node.id
            
        return None

    def _extract_constant_value(self, node: ast.expr) -> Optional[int]:
        """Extract a constant integer value from an AST node."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, int):
                return node.value
        elif isinstance(node, ast.Name):
            # Check if it's a variable we know about
            val = self.variables.get(node.id)
            if isinstance(val, int) and not isinstance(val, bool):
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
            # Check if it's a known classical register name (from measurements)
            var_name = node.id
            if var_name in self.classical_registers:
                # This is a classical register, return as-is (will be used in subscript like c[i])
                return var_name
            # Map common classical register variable names to OpenQASM format
            if var_name.startswith('c') and len(var_name) > 1 and var_name[1:].isdigit():
                # Handle c0, c1, etc. -> c[0], c[1]
                return f"c[{var_name[1:]}]"
            return var_name
        elif isinstance(node, ast.Subscript):
            # Handle array indexing like c[i], creg[0], m[i]
            value = self._extract_condition_operand(node.value)
            # Check if the base value is a classical register
            if isinstance(node.value, ast.Name) and node.value.id in self.classical_registers:
                # This is a classical register access (e.g., c[1]), use it directly
                if isinstance(node.slice, ast.Index):  # Python < 3.9
                    index = self._extract_condition_operand(node.slice.value)
                elif isinstance(node.slice, ast.Constant):  # Python 3.9+
                    index = str(node.slice.value)
                elif isinstance(node.slice, ast.Name):
                    index = node.slice.id
                else:
                    index = self._extract_condition_operand(node.slice)
                return f"{value}[{index}]"
            
            # Regular array indexing
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
            # Handle attribute access like creg[i] or circuit.creg[i]
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

    def _is_quantum_circuit_call(self, node: ast.Call) -> bool:
        """Check if a call creates a QuantumCircuit."""
        if isinstance(node.func, ast.Name) and node.func.id == 'QuantumCircuit':
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == 'QuantumCircuit':
            return True
        return False

    def _extract_circuit_dimensions(self, node: ast.Call) -> None:
        """Extract qubits and clbits from QuantumCircuit constructor."""
        args = node.args
        if self.circuit_vars:
            # A second QuantumCircuit in the same program (sub-circuit, compose, ...)
            # cannot be merged statically.
            self.unsupported_operations.add("multiple QuantumCircuit objects")
        if args and all(isinstance(a, ast.Name) and a.id in self.registers for a in args):
            # QuantumCircuit(qr1, qr2, cr): registers are laid out in argument order.
            self.qubits, self.clbits = 0, 0
            for a in args:
                self._add_register_to_circuit(a.id)
            return
        if any(isinstance(a, ast.Name) and a.id in self.registers for a in args):
            self.unsupported_operations.add("QuantumCircuit with mixed register/int arguments")
            return
        if len(args) >= 1:
            # First argument is number of qubits — try constant/name first, then full expression
            try:
                val = self._resolve_int_arg(args[0])
                if val is not None:
                    self.qubits = val
                elif VERBOSE:
                    vprint(f"[QiskitASTVisitor] Could not resolve qubits count from {ast.dump(args[0])}")
            except Exception:
                if VERBOSE:
                    vprint(f"[QiskitASTVisitor] Exception resolving qubits count")

        if len(args) >= 2:
            # Second argument is number of classical bits
            try:
                val = self._resolve_int_arg(args[1])
                if val is not None:
                    self.clbits = val
                elif VERBOSE:
                    vprint(f"[QiskitASTVisitor] Could not resolve clbits count from {ast.dump(args[1])}")
            except Exception:
                if VERBOSE:
                    vprint(f"[QiskitASTVisitor] Exception resolving clbits count")

    def _add_register_to_circuit(self, reg_name: str) -> None:
        info = self.registers[reg_name]
        if info['type'] == 'quantum':
            self.qreg_offsets[reg_name] = self.qubits
            self.qubits += int(info['size'])
        else:
            self.creg_offsets[reg_name] = self.clbits
            self.clbits += int(info['size'])

    def _resolve_int_arg(self, node: ast.expr) -> Optional[int]:
        """
        Resolve an AST node to an integer value, handling:
        - Literal integers (ast.Constant)
        - Known variable names (ast.Name)
        - Named register references
        - Binary/unary expressions (e.g. n + 1, n - 1)
        Returns None if the value cannot be statically determined.
        """
        # 1. Direct integer literal
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value

        # 2. Known variable
        if isinstance(node, ast.Name):
            if node.id in self.variables:
                val = self.variables[node.id]
                try:
                    return int(val)
                except (TypeError, ValueError):
                    pass
            if node.id in self.registers:
                try:
                    return int(self.registers[node.id]['size'])
                except (TypeError, ValueError, KeyError):
                    pass
            return None

        # 3. Binary expression: evaluate with known variables
        if isinstance(node, ast.BinOp):
            left = self._resolve_int_arg(node.left)
            right = self._resolve_int_arg(node.right)
            if left is not None and right is not None:
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.FloorDiv) and right != 0:
                    return left // right
            return None

        # 4. Unary expression: -n
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            val = self._resolve_int_arg(node.operand)
            return -val if val is not None else None

        # 5. Fallback: use _extract_parameter which handles more cases
        try:
            result = self._extract_parameter(node)
            if isinstance(result, (int, float)) and result != 'expr':
                return int(result)
        except Exception:
            pass

        return None


    def _is_register_call(self, call: ast.Call) -> bool:
        """Check if this is a QuantumRegister or ClassicalRegister call."""
        if isinstance(call.func, ast.Name):
            return call.func.id in ['QuantumRegister', 'ClassicalRegister']
        elif isinstance(call.func, ast.Attribute):
            return call.func.attr in ['QuantumRegister', 'ClassicalRegister']
        return False

    def _handle_register_creation(self, target: ast.AST, call: ast.Call) -> None:
        """Handle QuantumRegister or ClassicalRegister creation."""
        if not isinstance(target, ast.Name):
            return
            
        reg_name = target.id
        func_name = ""
        if isinstance(call.func, ast.Name):
            func_name = call.func.id
        elif isinstance(call.func, ast.Attribute):
            func_name = call.func.attr
            
        reg_type = 'quantum' if 'QuantumRegister' in func_name else 'classical'
        
        # Extract size
        size = None
        if call.args:
            size = self._resolve_int_arg(call.args[0])
        if size is None:
            self.unsupported_operations.add(f"register '{reg_name}' with unknown size")
            size = 0
        
        self.registers[reg_name] = {'type': reg_type, 'size': size}
        if reg_type == 'quantum':
            self.quantum_registers.add(reg_name)
        else:
            self.classical_registers.add(reg_name)
                
        if VERBOSE:
            vprint(f"[QiskitASTVisitor] Tracked {reg_type} register: {reg_name} (size {size})")

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

    def _handle_circuit_method_call(self, node: ast.Call) -> None:
        """Handle method calls on circuit variables."""
        if not isinstance(node.func, ast.Attribute):
            return

        # Check if the method is called on a circuit variable
        if isinstance(node.func.value, ast.Name) and node.func.value.id in self.circuit_vars:
            method_name = node.func.attr
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Circuit method call detected: {method_name}")
                # Raw AST dumps for traceability
                try:
                    args_dump = [ast.dump(a, include_attributes=False) for a in node.args]
                except Exception:
                    args_dump = [str(a) for a in node.args]
                kw_dump = {}
                for kw in node.keywords:
                    try:
                        kw_dump[kw.arg] = ast.dump(kw.value, include_attributes=False)
                    except Exception:
                        kw_dump[kw.arg] = str(kw.value)
                vprint(f"[QiskitASTVisitor]   raw.args={args_dump}")
                vprint(f"[QiskitASTVisitor]   raw.keywords={kw_dump}")
            self._parse_gate_operation(method_name, node.args, node.keywords)

    def _parse_gate_operation(self, method_name: str, args: List[ast.expr], keywords: List[ast.keyword]) -> None:
        """Parse a gate operation and add it to operations list."""
        # Handle different gate types
        if VERBOSE:
            vprint(f"[QiskitASTVisitor] Parsing operation: {method_name}")
            vprint(f"[QiskitASTVisitor]   args_count={len(args)} kw_count={len(keywords)}")

        # Route to appropriate handler
        if method_name in ['h', 'x', 'y', 'z', 's', 't', 'sx', 'id', 'i']:
            self._handle_single_qubit_gate(method_name, args)
        elif method_name in ['cx', 'cnot', 'cz', 'cy', 'ch', 'swap']:
            self._handle_two_qubit_gate(method_name, args)
        elif method_name in ['rx', 'ry', 'rz', 'p']:
            self._handle_parameterized_single_qubit_gate(method_name, args)
        elif method_name in ['sdg', 'tdg']:
            self._handle_inverse_gate(method_name, args)
        elif method_name in ['ccx', 'ccz', 'cswap']:
            self._handle_three_qubit_gate(method_name, args)
        elif method_name == 'gphase':
            self._handle_global_phase(args)
        elif method_name in ['cp', 'crx', 'cry', 'crz', 'cu']:
            self._handle_controlled_two_qubit_gate(method_name, args)
        elif method_name == 'u':
            self._handle_universal_gate(args)
        elif method_name == 'mcx':
            self._handle_mcx_gate(args)
        elif method_name in ('rxx', 'ryy', 'rzz'):
            self._handle_controlled_two_qubit_gate(method_name, args)
        elif method_name == 'iswap':
            self._handle_two_qubit_gate(method_name, args)
        elif method_name == 'sxdg':
            if len(args) == 1:
                for q in self._extract_qubit_list(args[0]):
                    self.operations.append(GateNode(name='sx', qubits=[q], modifiers={'inv': True}))
        elif method_name == 'add_register':
            for a in args:
                if isinstance(a, ast.Name) and a.id in self.registers:
                    self._add_register_to_circuit(a.id)
                else:
                    self.unsupported_operations.add("add_register(...)")
        elif method_name == 'measure':
            self._handle_measurement_qiskit(args)
        elif method_name == 'measure_all':
            self._handle_measure_all_qiskit()
        elif method_name == 'reset':
            self._handle_reset_qiskit(args)
        elif method_name == 'barrier':
            self._handle_barrier_qiskit(args)
        elif method_name == 'if_else':
            # Bodies are separate QuantumCircuit objects; not modelled statically.
            self.unsupported_operations.add("qc.if_else(...)")
        elif method_name in self._READ_ONLY_METHODS:
            pass
        else:
            self.unsupported_operations.add(f"qc.{method_name}(...)")

    # Methods that do not change the circuit.
    _READ_ONLY_METHODS = frozenset({
        'draw', 'depth', 'size', 'width', 'count_ops', 'num_nonlocal_gates', 'num_tensor_factors',
        'num_unitary_factors', 'num_connected_components', 'qasm', 'to_instruction', 'to_gate',
        'copy', 'copy_empty_like', 'decompose', 'inverse', 'reverse_bits', 'reverse_ops',
        'remove_final_measurements', 'has_calibration_for', 'find_bit', 'get_parameter',
        'has_parameter', 'assign_parameters',
    })

    def _handle_single_qubit_gate(self, method_name: str, args: List[ast.expr]) -> None:
        """Handle single-qubit gates without parameters."""
        if len(args) != 1:
            self.unsupported_operations.add(f"qc.{method_name} with {len(args)} arguments")
            return
        if args:
            qubits = self._extract_qubit_list(args[0])
            for qubit in qubits:
                self.operations.append(GateNode(name=method_name, qubits=[qubit]))
                if VERBOSE:
                    vprint(f"[QiskitASTVisitor] Added single-qubit gate {method_name} on q[{qubit}]")

    def _handle_two_qubit_gate(self, method_name: str, args: List[ast.expr]) -> None:
        """Handle two-qubit gates."""
        if len(args) >= 2:
            qubits1 = self._extract_qubit_list(args[0])
            qubits2 = self._extract_qubit_list(args[1])
            gate_name = 'cx' if method_name == 'cnot' else method_name
            
            # Simple zip expansion for equal-sized lists or single qubit broadcast
            if len(qubits1) == 1 and len(qubits2) > 1:
                # One control, multiple targets
                for q2 in qubits2:
                    self.operations.append(GateNode(name=gate_name, qubits=[qubits1[0], q2]))
            elif len(qubits1) > 1 and len(qubits2) == 1:
                # Multiple controls, one target
                for q1 in qubits1:
                    self.operations.append(GateNode(name=gate_name, qubits=[q1, qubits2[0]]))
            else:
                # Zip them
                for q1, q2 in zip(qubits1, qubits2):
                    self.operations.append(GateNode(name=gate_name, qubits=[q1, q2]))

    def _handle_controlled_two_qubit_gate(self, method_name: str, args: List[ast.expr]) -> None:
        """Handle controlled parameterized two-qubit gates like cp, crx, cry, crz, cu."""
        param_counts = {
            'cp': 1,
            'crx': 1,
            'cry': 1,
            'crz': 1,
            'cu': 4,
        }
        required_params = param_counts.get(method_name, 1)
        total_required = required_params + 2  # parameters + two qubit indices
        if len(args) != total_required:
            self.unsupported_operations.add(f"qc.{method_name} with {len(args)} arguments")
            return

        params = [self._extract_parameter(arg) for arg in args[:required_params]]
        control = self._extract_qubit_index(args[required_params])
        target = self._extract_qubit_index(args[required_params + 1])
        self.operations.append(GateNode(
            name=method_name,
            qubits=[control, target],
            parameters=params
        ))
        if VERBOSE:
            vprint(f"[QiskitASTVisitor] Added {method_name} gate with params {params} on q[{control}], q[{target}]")

    def _handle_parameterized_single_qubit_gate(self, method_name: str, args: List[ast.expr]) -> None:
        """Handle parameterized single-qubit gates."""
        if len(args) != 2:
            self.unsupported_operations.add(f"qc.{method_name} with {len(args)} arguments")
            return
        if len(args) >= 2:
            if VERBOSE:
                vprint("[QiskitASTVisitor]   rule=rotation_gate -> extract_parameter(args[0]); extract_qubit_index(args[1])")
            param = self._extract_parameter(args[0])
            qubit = self._extract_qubit_index(args[1])
            self.operations.append(GateNode(
                name=method_name,
                qubits=[qubit],
                parameters=[param]
            ))
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Added rotation {method_name}({param}) on q[{qubit}]")

    def _handle_three_qubit_gate(self, method_name: str, args: List[ast.expr]) -> None:
        """Handle three-qubit gates like ccx, ccz, cswap."""
        if len(args) >= 3:
            q0 = self._extract_qubit_index(args[0])
            q1 = self._extract_qubit_index(args[1])
            q2 = self._extract_qubit_index(args[2])
            self.operations.append(GateNode(name=method_name, qubits=[q0, q1, q2]))
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Added three-qubit gate {method_name} on q[{q0}], q[{q1}], q[{q2}]")

    def _handle_global_phase(self, args: List[ast.expr]) -> None:
        """Handle global phase gate."""
        if args:
            param = self._extract_parameter(args[0])
            self.operations.append(GateNode(name='gphase', qubits=[], parameters=[param]))
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Added global phase gphase({param})")

    def _handle_inverse_gate(self, method_name: str, args: List[ast.expr]) -> None:
        """Handle inverse named gates like sdg/tdg by emitting inv modifier on s/t."""
        if len(args) >= 1:
            qubit = self._extract_qubit_index(args[0])
            base = 's' if method_name == 'sdg' else 't'
            # Represent as GateNode with modifier in metadata
            node = GateNode(name=base, qubits=[qubit], parameters=[])
            # attach a simple modifiers dict
            setattr(node, 'modifiers', {'inv': True})
            self.operations.append(node)

    def _handle_mcx_gate(self, args: List[ast.expr]) -> None:
        """Handle Multi-Controlled X gate."""
        if len(args) >= 2:
            controls = self._extract_qubit_list(args[0])
            target = self._extract_qubit_index(args[1])
            self.operations.append(GateNode(
                name='x',
                qubits=controls + [target],
                modifiers={'ctrl': len(controls)}
            ))
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Added mcx with {len(controls)} controls on q[{target}]")

    def _handle_compose_qiskit(self, args: List[ast.expr]) -> None:
        """
        Handle qc.compose(other, qubits=...) method.
        Ideally we would extract operations from 'other', but statically this is hard.
        For now, we at least avoid crashing and try to find local circuit variables.
        """
        if VERBOSE:
            vprint("[QiskitASTVisitor] compose detected - static extraction limited")
        # If 'other' is a variable name, and we tracked its creation, 
        # we might be able to append its operations. 
        # But for now, we leave as a placeholder or comment.
        pass

    def _handle_universal_gate(self, args: List[ast.expr]) -> None:
        """Handle universal U gate."""
        if len(args) >= 4:
            if VERBOSE:
                vprint("[QiskitASTVisitor]   rule=u_gate -> extract parameters args[0:3]; extract_qubit_index(args[3])")
            params = [self._extract_parameter(arg) for arg in args[0:3]]
            qubit = self._extract_qubit_index(args[3])
            self.operations.append(GateNode(
                name='u',
                qubits=[qubit],
                parameters=params
            ))
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Added u gate{tuple(params)} on q[{qubit}]")

    def _handle_measurement_qiskit(self, args: List[ast.expr]) -> None:
        """Handle measurement operations in Qiskit."""
        if len(args) < 2:
            return

        # Check for range(n) to range(n)
        if self._is_range_call(args):
            self._handle_range_call_measurement(args)
            return

        # Check for batch measurement [q0, q1] to [c0, c1]
        if self._is_batch_measurement(args):
            self._handle_batch_measurement(args)
            return

        # Standard processing
        qubits = self._extract_qubit_list(args[0])
        clbits = self._extract_qubit_list(args[1], kind='clbit')
        if len(qubits) != len(clbits):
            raise UnsupportedCircuitError("qc.measure() with different numbers of qubits and clbits")
        
        for q, c in zip(qubits, clbits):
            self.operations.append(MeasurementNode(qubit=q, clbit=c))
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Added measure q[{q}] -> c[{c}]")
            
            # Update clbit_counter to the highest bit index seen so far
            if isinstance(c, int):
                self.clbit_counter = max(self.clbit_counter, c + 1)
        
        # Track that 'c' is the default classical register name
        self.classical_registers.add('c')

    def _is_batch_measurement(self, args: List[ast.expr]) -> bool:
        """Check if this is a batch measurement with lists of qubits and clbits."""
        return (isinstance(args[0], ast.List) and isinstance(args[1], ast.List))

    def _is_range_call(self, args: List[ast.expr]) -> bool:
        """Check if this is a range call for measurement."""
        return (isinstance(args[0], ast.Call) and isinstance(args[0].func, ast.Name) and args[0].func.id == 'range' and
                isinstance(args[1], ast.Call) and isinstance(args[1].func, ast.Name) and args[1].func.id == 'range')

    def _handle_range_call_measurement(self, args: List[ast.expr]) -> None:
        """Handle measurement of range(n) to range(n)."""
        q_list = self._extract_qubit_list(args[0])
        c_list = self._extract_qubit_list(args[1], kind='clbit')
        if len(q_list) != len(c_list):
            raise UnsupportedCircuitError("qc.measure(range(...), range(...)) with different lengths")
        for q, c in zip(q_list, c_list):
            self.operations.append(MeasurementNode(qubit=q, clbit=c))

    def _handle_batch_measurement(self, args: List[ast.expr]) -> None:
        """Handle measurement of multiple qubits to multiple clbits."""
        qubits = [self._extract_qubit_index(item) for item in args[0].elts]
        clbits = [self._extract_clbit_index(item) for item in args[1].elts]
        if len(qubits) != len(clbits):
            raise UnsupportedCircuitError("qc.measure() with different numbers of qubits and clbits")

        for q, c in zip(qubits, clbits):
            self.operations.append(MeasurementNode(qubit=q, clbit=c))
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Added measure q[{q}] -> c[{c}]")
        
        # Track that 'c' is a classical register (common Qiskit convention)
        self.classical_registers.add('c')

    def _handle_single_measurement(self, args: List[ast.expr]) -> None:
        """Handle measurement of a single qubit to a single clbit."""
        qubit = self._extract_qubit_index(args[0])
        clbit = self._extract_clbit_index(args[1])
        self.operations.append(MeasurementNode(qubit=qubit, clbit=clbit))
        
        # Track that 'c' is a classical register (common Qiskit convention)
        # This helps identify c[i] references in if statements as classical register access
        self.classical_registers.add('c')

        if VERBOSE:
            vprint(f"[QiskitASTVisitor] Added measure q[{qubit}] -> c[{clbit}]")

    def _handle_measure_all_qiskit(self) -> None:
        """Handle qc.measure_all() - measure all qubits."""
        if VERBOSE:
            vprint(f"[QiskitASTVisitor] Adding measure_all (qubits={self.qubits})")
        
        # In Qiskit, measure_all() adds a new ClassicalRegister ("meas") after the
        # existing ones; we mirror that layout with new clbit indices.
        if self.qubits <= 0:
            raise UnsupportedCircuitError("measure_all() on a circuit of unknown size")
        offset = self.clbits
        for i in range(self.qubits):
            self.operations.append(MeasurementNode(qubit=i, clbit=offset + i))
        
        # Update high-level bit counts
        self.clbits += self.qubits
        self.clbit_counter = max(self.clbit_counter, self.clbits)

    def _handle_reset_qiskit(self, args: List[ast.expr]) -> None:
        """Handle reset operations in Qiskit."""
        if args:
            if VERBOSE:
                vprint("[QiskitASTVisitor]   rule=reset -> extract_qubit_index(args[0])")
            qubit = self._extract_qubit_index(args[0])
            self.operations.append(ResetNode(qubit=qubit))
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Added reset q[{qubit}]")

    def _handle_barrier_qiskit(self, args: List[ast.expr]) -> None:
        """Handle barrier operations in Qiskit."""
        qubits = []
        if args:
            if isinstance(args[0], ast.List):
                qubits = [self._extract_qubit_index(item) for item in args[0].elts]
            else:
                qubits = [self._extract_qubit_index(args[0])]
        self.operations.append(BarrierNode(qubits=qubits))
        if VERBOSE:
            vprint(f"[QiskitASTVisitor] Added barrier on {qubits if qubits else 'all qubits'}")

    def _handle_if_else_qiskit(self, args: List[ast.expr]) -> None:
        """
        Handle Qiskit 2.1+ if_else method: qc.if_else(condition, true_body, false_body=None)
        
        According to Qiskit 2.1 API (https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.1/qiskit.circuit.IfElseOp):
        - condition: (ClassicalRegister, int) | (Clbit, int/bool) | expr.Expr
        - true_body: QuantumCircuit
        - false_body: QuantumCircuit | None
        """
        if len(args) < 2:
            if VERBOSE:
                vprint("[QiskitASTVisitor] if_else requires at least 2 arguments (condition, true_body)")
            return
        
        # Extract condition from first argument
        condition = self._extract_qiskit_condition(args[0])
        
        # Extract true_body operations from second argument
        true_body_ops = []
        saved_operations = self.operations
        self.operations = true_body_ops
        
        # Try to extract operations from true_body (could be a variable or QuantumCircuit call)
        self._extract_circuit_body_operations(args[1])
        true_body_ops = self.operations
        
        # Extract false_body operations if present
        false_body_ops = None
        if len(args) >= 3:
            false_body_ops = []
            self.operations = false_body_ops
            self._extract_circuit_body_operations(args[2])
            false_body_ops = self.operations
        
        # Restore operations list
        self.operations = saved_operations
        
        # Create IfStatementNode
        if_stmt = IfStatementNode(
            condition=condition,
            body=true_body_ops,
            else_body=false_body_ops
        )
        self.operations.append(if_stmt)
        
        if VERBOSE:
            vprint(f"[QiskitASTVisitor] Added Qiskit if_else: {condition}")

    def _extract_qiskit_condition(self, node: ast.expr) -> str:
        """
        Extract condition from Qiskit if_else format.
        Supports: (ClassicalRegister, int), (Clbit, int/bool)
        Raises ValueError for unsupported conditions to trigger fallback.
        """
        # Only handle tuple condition: (creg, value) or (cbit, value)
        if isinstance(node, ast.Tuple) and len(node.elts) == 2:
            register_or_bit = node.elts[0]
            value = node.elts[1]
            
            # Extract register/bit name
            reg_name = self._extract_register_or_bit_name(register_or_bit)
            
            # Extract value
            if isinstance(value, ast.Constant):
                val = str(value.value)
            elif isinstance(value, ast.Name):
                val = value.id
            else:
                val = self._extract_condition_operand(value)
            
            # Format as OpenQASM condition: c[i] == value
            # For now, assume single bit access - could be enhanced for full register comparison
            if reg_name:
                return f"{reg_name} == {val}"
        else:
            raise ValueError("Unsupported if-condition - triggering fallback to runtime execution")

    def _extract_register_or_bit_name(self, node: ast.expr) -> str:
        """Extract classical register or bit name from AST node."""
        # Handle direct name: creg
        if isinstance(node, ast.Name):
            return node.id
        
        # Handle attribute access: circuit.creg
        if isinstance(node, ast.Attribute):
            return node.attr
        
        # Handle subscript: creg[0] -> creg[0]
        if isinstance(node, ast.Subscript):
            value = self._extract_register_or_bit_name(node.value)
            if isinstance(node.slice, ast.Index):  # Python < 3.9
                index = self._extract_condition_operand(node.slice.value)
            elif isinstance(node.slice, ast.Constant):  # Python 3.9+
                index = str(node.slice.value)
            else:
                index = self._extract_condition_operand(node.slice)
            return f"{value}[{index}]"
        
        return str(node)

    def _extract_circuit_body_operations(self, node: ast.expr) -> None:
        """
        Extract operations from a circuit body (true_body or false_body).
        Handles both variable references and QuantumCircuit constructor calls.
        Note: This is limited for AST parsing - we can't execute code to get circuit objects.
        """
        # If it's a variable name, we can't extract operations statically
        # This is a limitation of AST parsing - we'd need execution to get the circuit
        if isinstance(node, ast.Name):
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] if_else body is a variable '{node.id}' - cannot extract operations statically")
            # For now, we'll skip this - in a full implementation, you might want to
            # track circuit variables and their operations
            return
        
        # If it's a QuantumCircuit constructor call, we could parse it
        # but typically bodies are passed as variables, not inline
        if isinstance(node, ast.Call):
            if self._is_quantum_circuit_call(node):
                if VERBOSE:
                    vprint("[QiskitASTVisitor] if_else body is QuantumCircuit() - parsing inline circuit")
                # Could parse the circuit constructor, but this is uncommon
                # Usually bodies are pre-created variables
                return
        
        # For other cases, try to visit the node to see if it contains operations
        # This handles cases where the body might be a more complex expression
        try:
            self.visit(node)
        except Exception:
            if VERBOSE:
                vprint(f"[QiskitASTVisitor] Could not extract operations from if_else body: {type(node).__name__}")

    def _has_circuit_ops(self, nodes: List[ast.stmt]) -> bool:
        """Check if a list of AST nodes contains any circuit operations."""
        for node in nodes:
            # Check for direct calls on circuit variables
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name):
                    var_id = node.value.func.value.id
                    if VERBOSE:
                        vprint(f"[QiskitASTVisitor] _has_circuit_ops: checking call on {var_id}. Known circuits: {self.circuit_vars}")
                    if var_id in self.circuit_vars:
                        return True
            # Check for assignments that are circuit operations
            elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Attribute) and isinstance(node.value.func.value, ast.Name):
                    var_id = node.value.func.value.id
                    if var_id in self.circuit_vars:
                        return True
            # Recurse into If/For
            elif isinstance(node, ast.If):
                if VERBOSE:
                    vprint("[QiskitASTVisitor] _has_circuit_ops: recursing into If")
                if self._has_circuit_ops(node.body) or self._has_circuit_ops(node.orelse):
                    return True
            elif isinstance(node, ast.For):
                if VERBOSE:
                    vprint("[QiskitASTVisitor] _has_circuit_ops: recursing into For")
                if self._has_circuit_ops(node.body):
                    return True
        return False

    def _extract_qubit_list(self, node: ast.expr, kind: str = 'qubit') -> List[Union[int, str]]:
        """Extract a list of qubit indices from an AST node (Constant, Name, List, range() call)."""
        if isinstance(node, (ast.Constant, ast.Name, ast.Subscript)):
            # Check if it's a register object
            if isinstance(node, ast.Name) and node.id in self.registers:
                offsets = self.qreg_offsets if node.id in self.quantum_registers else self.creg_offsets
                if node.id not in offsets:
                    raise UnsupportedCircuitError(f"register '{node.id}' is not part of the circuit")
                size = self.registers[node.id]['size']
                return list(range(offsets[node.id], offsets[node.id] + size))
            if isinstance(node, ast.Name) and isinstance(self.variables.get(node.id), list):
                values = self.variables[node.id]
                if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
                    return list(values)
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice):
                raise UnsupportedCircuitError(f"register slices like '{ast.unparse(node)}' are not supported")
            return [self._extract_qubit_index(node, kind)]
        elif isinstance(node, (ast.List, ast.Tuple)):
            return [self._extract_qubit_index(elt, kind) for elt in node.elts]
        elif isinstance(node, ast.Call):
            # Try to extract range information
            r = self._extract_range(node)
            if r and isinstance(r[0], int) and isinstance(r[1], int):
                return list(range(r[0], r[1]))
            raise UnsupportedCircuitError(f"cannot resolve qubits '{ast.unparse(node)}' statically")
        return [self._extract_qubit_index(node, kind)]

    def _extract_qubit_index(self, node: ast.expr, kind: str = 'qubit') -> Union[int, str]:
        """Extract qubit index from AST node."""
        if VERBOSE:
            try:
                vprint(f"[QiskitASTVisitor]   _extract_qubit_index node={ast.dump(node, include_attributes=False)}")
            except Exception:
                pass

        # Special case for Subscript: qr[0] -> global index (register offset + 0)
        if isinstance(node, ast.Subscript):
            idx_node = node.slice
            if hasattr(ast, 'Index') and isinstance(idx_node, ast.Index):
                idx_node = idx_node.value
            base = node.value
            offsets = self.creg_offsets if kind == 'clbit' else self.qreg_offsets
            if isinstance(base, ast.Name) and base.id in self.registers:
                if base.id not in offsets:
                    raise UnsupportedCircuitError(f"register '{base.id}' is not part of the circuit")
                offset = offsets[base.id]
                size = self.registers[base.id]['size']
            elif (isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name)
                  and base.value.id in self.circuit_vars and base.attr in ('qubits', 'clbits')):
                offset, size = 0, (self.clbits if base.attr == 'clbits' else self.qubits)
            elif isinstance(base, ast.Name) and isinstance(self.variables.get(base.id), list):
                # plain Python list of indices, e.g. targets = [0, 2]
                val = self._extract_parameter(node)
                if isinstance(val, int) and not isinstance(val, bool):
                    return val
                raise UnsupportedCircuitError(f"cannot resolve index '{ast.unparse(node)}' statically")
            else:
                raise UnsupportedCircuitError(f"cannot resolve qubit '{ast.unparse(node)}' statically")
            val = self._extract_parameter(idx_node)
            if isinstance(val, bool) or not isinstance(val, (int, str)) or val == 'expr':
                val = self._extract_parameter_value(idx_node) if not isinstance(idx_node, ast.Constant) else val
            if isinstance(val, int):
                if val < 0:
                    val += size
                return offset + val
            if isinstance(val, str):
                val = val.replace(' ', '')
                return val if offset == 0 else f"{offset}+{val}"
            raise UnsupportedCircuitError(f"cannot resolve qubit '{ast.unparse(node)}' statically")

        # Use _extract_parameter to handle variables and arithmetic (i + 1)
        val = self._extract_parameter(node)
        if isinstance(val, float) and float(val).is_integer():
            val = int(val)
        if isinstance(val, (int, str)) and not isinstance(val, bool) and val != 'expr':
            return val
        
        # Fallback to symbolic if eval failed or it's a complex expression
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, (ast.BinOp, ast.UnaryOp)):
            return self._extract_parameter_value(node).replace(' ', '')
        raise UnsupportedCircuitError(f"cannot resolve qubit '{ast.unparse(node)}' statically")

    def _extract_clbit_index(self, node: ast.expr) -> Union[int, str]:
        """Extract classical bit index from AST node."""
        if VERBOSE:
            try:
                vprint(f"[QiskitASTVisitor]   _extract_clbit_index node={ast.dump(node, include_attributes=False)}")
            except Exception:
                vprint("[QiskitASTVisitor]   _extract_clbit_index node=<dump failed>")
        return self._extract_qubit_index(node, kind='clbit')

    def _extract_parameter(self, node: ast.expr) -> Any:
        """Extract parameter value or name from AST node."""
        if VERBOSE:
            try:
                vprint(f"[QiskitASTVisitor]   _extract_parameter node={ast.dump(node, include_attributes=False)}")
            except Exception:
                pass

        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.Name):
            # Try to resolve variable
            if node.id in self.variables:
                return self.variables[node.id]
            self.parameters.add(node.id)
            return node.id
        elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.attr == 'pi' and node.value.id in ('np', 'numpy'):
            return np.pi
        elif isinstance(node, (ast.BinOp, ast.UnaryOp, ast.Subscript, ast.Call, ast.List, ast.Tuple, ast.ListComp)):
            # Special handling for Subscript to track array parameters and handle unrolled loop variables
            if isinstance(node, ast.Subscript):
                base_name = None
                if isinstance(node.value, ast.Name):
                    base_name = node.value.id
                
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
                
                if base_name and base_name not in self.variables:
                    # Update shape tracking
                    current_shape = self.array_parameters.get(base_name, [])
                    while len(current_shape) < len(resolved_indices):
                        current_shape.append(1)
                    for i, idx in enumerate(resolved_indices):
                        if isinstance(idx, int):
                            current_shape[i] = max(current_shape[i], idx + 1)
                    self.array_parameters[base_name] = current_shape
                    
                    # Return substituted string
                    idx_str = ", ".join(str(idx) for idx in resolved_indices)
                    return f"{base_name}[{idx_str}]"

            # Static evaluation (never executes user code; never guesses values).
            if isinstance(node, ast.Call) and self._is_quantum_circuit_call(node):
                return 'expr'
            numeric_vars = {k: v for k, v in self.variables.items() if not isinstance(v, str)}
            try:
                return static_eval(node, numeric_vars)
            except NotStatic:
                pass
            try:
                return self._symbolic_expression(node)
            except NotStatic:
                return 'expr'

    _SYMBOLIC_FUNCS = {'sin', 'cos', 'tan', 'exp', 'sqrt', 'arcsin', 'arccos', 'arctan', 'log'}

    def _symbolic_expression(self, node: ast.expr) -> str:
        """OpenQASM text for an expression over loop variables / free parameters and pi."""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return repr(node.value)
        if isinstance(node, ast.Name):
            val = self.variables.get(node.id)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                return repr(val)
            if val == node.id:
                return node.id  # loop variable
            if node.id in ('pi', 'π'):
                return 'pi'
            if node.id in self.variables:
                raise NotStatic(node.id)
            self.parameters.add(node.id)
            return node.id
        if isinstance(node, ast.Attribute) and node.attr == 'pi' and isinstance(node.value, ast.Name) \
                and node.value.id in ('np', 'numpy', 'math'):
            return 'pi'
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return f"-({self._symbolic_expression(node.operand)})"
        if isinstance(node, ast.BinOp):
            ops = {ast.Add: '+', ast.Sub: '-', ast.Mult: '*', ast.Div: '/', ast.Pow: '**'}
            op = ops.get(type(node.op))
            if op is None:
                raise NotStatic("operator")
            return f"({self._symbolic_expression(node.left)} {op} {self._symbolic_expression(node.right)})"
        if isinstance(node, ast.Call) and not node.keywords and len(node.args) == 1:
            fname = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, 'id', None)
            if fname in self._SYMBOLIC_FUNCS:
                return f"{fname}({self._symbolic_expression(node.args[0])})"
        raise NotStatic(type(node).__name__)

    def _evaluate_simple_expression(self, node: ast.expr) -> Optional[Union[int, float]]:
        """Try to evaluate simple arithmetic expressions like n + 1 using tracked variables."""
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)):
                return node.value
        elif isinstance(node, ast.Name):
            val = self.variables.get(node.id)
            if isinstance(val, (int, float)):
                return val
        elif isinstance(node, ast.BinOp):
            left = self._evaluate_simple_expression(node.left)
            right = self._evaluate_simple_expression(node.right)
            if left is not None and right is not None:
                if isinstance(node.op, ast.Add): return left + right
                if isinstance(node.op, ast.Sub): return left - right
                if isinstance(node.op, ast.Mult): return left * right
                if isinstance(node.op, ast.Div): return left / right
        return None

    def _extract_expression(self, node: ast.expr) -> str:
        """Extract simple numpy pi expressions into OpenQASM constants."""
        text = self._extract_pi_constant(node)
        if text:
            return text
        text = self._extract_pi_fraction(node)
        if text:
            return text
        text = self._extract_pi_multiplication(node)
        if text:
            return text
        if VERBOSE:
            try:
                vprint(f"[QiskitASTVisitor]   _extract_expression node={ast.dump(node, include_attributes=False)}")
            except Exception:
                vprint("[QiskitASTVisitor]   _extract_expression node=<dump failed>")
        return "expr"

    def _extract_pi_constant(self, node: ast.expr) -> Optional[str]:
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.attr == 'pi' and node.value.id in ('np', 'numpy'):
            return 'pi'
        return None

    def _extract_pi_fraction(self, node: ast.expr) -> Optional[str]:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
            left, right = node.left, node.right
            if isinstance(left, ast.Attribute) and isinstance(left.value, ast.Name) and left.attr == 'pi' and left.value.id in ('np','numpy'):
                if isinstance(right, ast.Constant) and isinstance(right.value, int) and right.value in (2, 3, 4, 6, 8):
                    return f"pi/{int(right.value)}"
        return None

    def _extract_pi_multiplication(self, node: ast.expr) -> Optional[str]:
        """Extract expressions like expr * np.pi or np.pi * expr."""
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mult):
            left, right = node.left, node.right
            
            # Check if either side is pi
            pi_left = self._extract_pi_constant(left)
            pi_right = self._extract_pi_constant(right)
            
            if pi_right:
                # Case: expr * pi
                # Avoid infinite recursion if left is also a BinOp we're currently processing
                if isinstance(left, ast.BinOp) and isinstance(left.op, ast.Mult):
                    return f"expr*{pi_right}"
                other = self._extract_parameter(left)
                return f"{other}*{pi_right}"
            
            if pi_left:
                # Case: pi * expr
                if isinstance(right, ast.BinOp) and isinstance(right.op, ast.Mult):
                    return f"{pi_left}*expr"
                other = self._extract_parameter(right)
                return f"{pi_left}*{other}"
        return None

    def _extract_parameter_value(self, node: ast.expr) -> str:
        """Fallback for extracting a string representation of a parameter expression."""
        try:
            # Use ast.unparse for modern Python - it's the safest way to get valid Python expression strings
            if hasattr(ast, 'unparse'):
                return ast.unparse(node)
            
            # Explicitly handle common patterns if unparse is missing
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Constant):
                return str(node.value)
            if isinstance(node, ast.Subscript):
                value = self._extract_parameter_value(node.value)
                index = self._extract_parameter_value(node.slice)
                return f"{value}[{index}]"
            return "param"
        except Exception:
            return "param"


class QiskitASTParser:
    """
    Parser for Qiskit quantum circuit source code using AST parsing.

    This parser provides a secure alternative to dynamic code execution by
    analyzing the abstract syntax tree of Python source code to extract
    circuit operations.
    """

    def __init__(self):
        self.visitor = QiskitASTVisitor()

    def parse(self, source_code: str) -> CircuitAST:
        """
        Parse Qiskit source code and return CircuitAST representation.

        Args:
            source_code: Python source code containing Qiskit circuit definition

        Returns:
            CircuitAST: Parsed circuit representation

        Raises:
            ValueError: If source code cannot be parsed or doesn't contain valid circuit
        """
        # Log that AST parsing is being used
        logging.info("Using AST parsing for secure Qiskit code analysis")

        if VERBOSE:
            logging.info("VERBOSE: Starting AST parsing of Qiskit source code")
            logging.info(f"VERBOSE: Source code length: {len(source_code)} characters")

        try:
            # Parse the source code into AST
            tree = ast.parse(source_code)
            if VERBOSE:
                vprint("[QiskitASTParser] Parsed source code into AST")
        except SyntaxError as e:
            if VERBOSE:
                vprint(f"[QiskitASTParser] Syntax error during AST parsing: {e}")
            raise ValueError(f"Invalid Python syntax in source code: {e}")

        # Reset visitor state
        self.visitor = QiskitASTVisitor()

        # Visit all nodes
        self.visitor.visit(tree)

        if VERBOSE:
            vprint(f"[QiskitASTParser] Found operations: {len(self.visitor.operations)}")
            vprint(f"[QiskitASTParser] Qubits: {self.visitor.qubits}, Clbits: {self.visitor.clbits}")
            vprint(f"[QiskitASTParser] Parameters: {list(self.visitor.parameters)}")

        if self.visitor.unsupported_operations:
            unsupported = ", ".join(sorted(self.visitor.unsupported_operations))
            raise UnsupportedCircuitError(f"Unsupported Qiskit constructs encountered: {unsupported}")

        # Validate that we found a circuit. Empty circuits are still valid when
        # a QuantumCircuit was declared (e.g. range(0) loops).
        if not self.visitor.operations and self.visitor.qubits == 0 and not self.visitor.circuit_vars:
            raise ValueError("No circuit operations found in source code. Make sure to define a get_circuit() function or circuit operations.")

        # Create CircuitAST
        circuit_ast = CircuitAST(
            qubits=self.visitor.qubits,
            clbits=self.visitor.clbits,
            operations=self.visitor.operations,
            parameters=list(self.visitor.parameters),
            array_parameters=self.visitor.array_parameters
        )

        if VERBOSE:
            vprint("[QiskitASTParser] Built CircuitAST")

        return circuit_ast

    def get_supported_gates(self) -> List[str]:
        """Get list of supported gate operations."""
        return [
            'h', 'x', 'y', 'z', 's', 't', 'sx', 'id', 'i',  # Single qubit
            'cx', 'cnot', 'cz', 'cy', 'ch', 'swap',  # Two qubit
            'rx', 'ry', 'rz', 'p', 'u',  # Parameterized
            'ccx', 'ccz', 'cswap',  # Multi-qubit
            'measure', 'reset', 'barrier'  # Special operations
        ]
