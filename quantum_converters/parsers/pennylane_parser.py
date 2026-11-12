"""
PennyLane AST Parser Module

WHAT THIS FILE DOES:
    Parses PennyLane quantum circuit source code using Python's AST module to extract
    circuit operations without executing the code. Provides secure, static analysis
    of PennyLane code to build a CircuitAST representation. Identifies qml.device()
    definitions, gate operations (qml.Hadamard(), qml.CNOT(), etc.), and measurements.
    Supports Iteration I features: basic gates, simple parameters, and measurements.

HOW IT LINKS TO OTHER FILES:
    - Used by: pennylane_to_qasm.py (PennyLaneToQASM3Converter uses PennyLaneASTParser)
    - Uses: circuit_ast.py (builds CircuitAST, GateNode, MeasurementNode, etc.)
    - Uses: config/mappings.py (gate name mappings via get_pl_inverse_qasm_map())
    - Uses: config/config.py (VERBOSE flag for debugging output)
    - Part of: Parsers module providing framework-specific parsing logic

INPUT:
    - pennylane_code (str): PennyLane Python source code
    - Expected format: Code with qml.device() and qml operations (e.g., qml.Hadamard(wires=0))
    - Used in: PennyLaneASTParser.parse() method

OUTPUT:
    - CircuitAST: Unified circuit representation with operations list
    - Returned by: PennyLaneASTParser.parse() method
    - Contains: Qubit count (from wires), operations (gates, measurements, etc.)

STAGE OF USE:
    - Parsing Stage: First step in AST-based conversion pipeline
    - Security Stage: Provides secure alternative to code execution
    - Used before: AST analysis and QASM code generation
    - Used by: PennyLaneToQASM3Converter.convert() method

TOOLS USED:
    - ast: Python's Abstract Syntax Tree module for parsing source code
    - logging: Debug logging (via config)
    - typing: Type hints for method signatures

PARSING STRATEGY:
    1. AST Visitor Pattern: Uses ast.NodeVisitor to traverse AST nodes
    2. Device Detection: Identifies qml.device() calls to extract wire count
    3. Operation Extraction: Visits qml.* function calls (qml.Hadamard(), qml.CNOT(), etc.)
    4. Wire Extraction: Extracts wire indices from keyword or positional arguments
    5. Parameter Extraction: Extracts gate parameters (angles, phases, etc.)
    6. Gate Mapping: Maps PennyLane gate names to OpenQASM mnemonics
    7. AST Building: Constructs CircuitAST with GateNode, MeasurementNode, etc.

ARCHITECTURE ROLE:
    Provides secure, static analysis of PennyLane code. Enables conversion without
    executing potentially unsafe user code. Part of the parsing layer that bridges
    framework-specific syntax and the unified CircuitAST representation.

Author: QCanvas Team
Date: 2025-08-14
Version: 1.0.0
"""

import ast
import numpy as np
from quantum_converters.config.config import VERBOSE, vprint
from quantum_converters.config import get_pl_inverse_qasm_map
from typing import List, Any, Set, Optional, Tuple, Dict, Union

from quantum_converters.base.circuit_ast import (
    CircuitAST, GateNode, MeasurementNode, ResetNode, BarrierNode, ForLoopNode, IfStatementNode
)
from quantum_converters.base.circuit_validation import MAX_STATIC_RANGE, UnsupportedCircuitError, bounded_range
from quantum_converters.base.safe_eval import NotStatic, static_eval


# VERBOSE is imported from config.config


class PennyLaneASTVisitor(ast.NodeVisitor):
    """
    AST visitor to extract PennyLane circuit operations.

    Assumptions (Iteration I):
    - Device declared via qml.device(..., wires=N)
    - Gates are called as qml.<Gate>(..., wires=...)
    - Measurements via qml.measure(wires=i) are mapped to classical bits
    - We support a core set of gates consistent with Iteration I
    """

    def __init__(self):
        self.operations: List[Any] = []
        self.parameters: Set[str] = set()
        self.qubits: int = 0
        self.clbits: int = 0
        self.variables: Dict[str, Any] = {}  # Track variable assignments
        # Maps array name -> required size (max_index + 1) for undeclared subscript params
        self.array_parameters: Dict[str, int] = {}
        self.unsupported_operations: Set[str] = set()
        self.mcm_vars: Dict[str, Any] = {}   # m = qml.measure(...) -> clbit index
        self.loop_stack: List[Tuple[str, Any, Any]] = []
        self.unrolled_iterations: int = 0  # total loop iterations unrolled at parse time
        self.measured = False

    # Detect qml.device(..., wires=N) and track variable assignments
    def visit_Assign(self, node: ast.Assign) -> None:
        if isinstance(node.value, ast.Call) and self._is_qml_call(node.value, 'measure'):
            clbits = self._handle_measurement_pennylane(node.value)
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and clbits:
                self.mcm_vars[node.targets[0].id] = clbits[0]
            return
        if (isinstance(node.value, ast.Call) and self._is_qml_call(node.value)
                and node.value.func.attr not in self._NON_OPERATION_CALLS):
            # e.g. op = qml.RX(0.1, wires=0) records the op on the tape in PennyLane.
            self._handle_qml_call(node.value)
            return
        try:
            # Track simple variable assignments
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                var_name = node.targets[0].id
                val = self._extract_parameter(node.value)
                if val != 'expr':
                    self.variables[var_name] = val
                    if VERBOSE:
                        vprint(f"[PennyLaneASTVisitor] Tracked variable: {var_name} = {val}")
                elif isinstance(node.value, ast.Name) and node.value.id in self.variables:
                    self.variables[var_name] = self.variables[node.value.id]
            
            if isinstance(node.value, ast.Call) and self._is_qml_call(node.value, 'device'):
                self._extract_wires_from_device(node.value)
        except Exception:
            pass
        self.generic_visit(node)

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

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Handle function definitions, tracking arguments with defaults."""
        # Track arguments with default values
        if node.args.defaults:
            num_defaults = len(node.args.defaults)
            args_with_defaults = node.args.args[-num_defaults:]
            for arg, default in zip(args_with_defaults, node.args.defaults):
                val = self._extract_constant_value(default)
                if val is not None:
                    self.variables[arg.arg] = val
                    if VERBOSE:
                        vprint(f"[PennyLaneASTVisitor] Tracked function arg default: {arg.arg} = {val}")

        # Parse the function body for circuit operations
        for stmt in node.body:
            self.visit(stmt)

    def visit_Expr(self, node: ast.Expr) -> None:
        # Capture qml gate/measurement expressions
        if isinstance(node.value, ast.Call):
            call = node.value
            if isinstance(call.func, ast.Call) and self._is_qml_call(call.func):
                inner = call.func.func.attr
                if inner == 'cond':
                    self._handle_cond(call)
                else:
                    # qml.adjoint(op)(...), qml.ctrl(op, ...)(...), templates, ...
                    self.unsupported_operations.add(f"qml.{inner}(...)(...)")
                return
            self._handle_qml_call(call)

    _NON_OPERATION_CALLS = frozenset({'device', 'qnode', 'QNode', 'draw', 'draw_mpl', 'specs', 'grad',
                                      'jacobian', 'workflow', 'transforms', 'math', 'numpy'})

    def _mcm_condition(self, node: ast.AST) -> str:
        """Translate a qml.cond condition on measurement variables into OpenQASM."""
        if isinstance(node, ast.Name) and node.id in self.mcm_vars:
            return f"c[{self.mcm_vars[node.id]}] == 1"
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Invert) \
                and isinstance(node.operand, ast.Name) and node.operand.id in self.mcm_vars:
            return f"c[{self.mcm_vars[node.operand.id]}] == 0"
        if (isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.left, ast.Name)
                and node.left.id in self.mcm_vars and isinstance(node.comparators[0], ast.Constant)
                and node.comparators[0].value in (0, 1, True, False) and isinstance(node.ops[0], (ast.Eq, ast.NotEq))):
            value = int(node.comparators[0].value)
            if isinstance(node.ops[0], ast.NotEq):
                value = 1 - value
            return f"c[{self.mcm_vars[node.left.id]}] == {value}"
        if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.BitAnd, ast.BitOr)):
            joiner = " && " if isinstance(node.op, ast.BitAnd) else " || "
            return f"({self._mcm_condition(node.left)}){joiner}({self._mcm_condition(node.right)})"
        raise UnsupportedCircuitError(f"qml.cond condition '{ast.unparse(node)}' is not supported")

    def _handle_cond(self, call: ast.Call) -> None:
        """qml.cond(m, qml.Gate)(args, wires=...) -> if (c[k] == 1) { gate }."""
        cond_call = call.func
        if len(cond_call.args) != 2 or cond_call.keywords:
            self.unsupported_operations.add("qml.cond with a false branch / keywords")
            return
        condition = self._mcm_condition(cond_call.args[0])
        target = cond_call.args[1]
        if not (isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == 'qml'):
            self.unsupported_operations.add(f"qml.cond(..., {ast.unparse(target)})")
            return
        fake = ast.Call(func=target, args=call.args, keywords=call.keywords)
        body = []
        saved = self.operations
        self.operations = body
        try:
            self._handle_qml_call(fake)
        finally:
            self.operations = saved
        if any(isinstance(op, MeasurementNode) for op in body):
            raise UnsupportedCircuitError("measurements inside qml.cond are not supported")
        self.operations.append(IfStatementNode(condition=condition, body=body, else_body=None))

    def visit_Return(self, node: ast.Return) -> None:
        """Handle return statements, which often contain PennyLane measurements."""
        if node.value:
            # Check if returning a qml measurement call
            if isinstance(node.value, ast.Call):
                self._handle_qml_call(node.value)
            # Check if returning a tuple of calls
            elif isinstance(node.value, ast.Tuple):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Call):
                        self._handle_qml_call(elt)
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        """Handle for loops in PennyLane code."""
        if VERBOSE:
            vprint("[PennyLaneASTVisitor] visit_For: inspecting for loop")
        
        # Special handling for enumerate with tuple target
        if (isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2 and
            isinstance(node.target.elts[0], ast.Name) and isinstance(node.target.elts[1], ast.Name) and
            isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) and node.iter.func.id == 'enumerate' and
            len(node.iter.args) == 1):
            
            iter_arg = node.iter.args[0]
            s = None
            if isinstance(iter_arg, ast.Str):
                s = iter_arg.s
            elif isinstance(iter_arg, ast.Constant) and isinstance(iter_arg.value, str):
                s = iter_arg.value
            elif isinstance(iter_arg, ast.Name) and iter_arg.id in self.variables:
                val = self.variables[iter_arg.id]
                if isinstance(val, str):
                    s = val
            
            if s is not None:
                # for i, bit in enumerate("string")
                i_var = node.target.elts[0].id
                bit_var = node.target.elts[1].id
                if VERBOSE:
                    vprint(f"[PennyLaneASTVisitor] Expanding enumerate loop for {s} with vars {i_var}, {bit_var}")
                for i, char in enumerate(s):
                    self.variables[i_var] = i
                    self.variables[bit_var] = char
                    for stmt in node.body:
                        self.visit(stmt)
                return  # Don't create ForLoopNode, already expanded

        # Special handling for iteration over list variable
        if (isinstance(node.target, ast.Name) and
            isinstance(node.iter, ast.Name) and node.iter.id in self.variables and
            isinstance(self.variables[node.iter.id], list)):
            # for var in list_var
            list_var = self.variables[node.iter.id]
            loop_var = node.target.id
            if VERBOSE:
                vprint(f"[PennyLaneASTVisitor] Expanding list loop for {node.iter.id} with var {loop_var}")
            for val in list_var:
                self.variables[loop_var] = val
                for stmt in node.body:
                    self.visit(stmt)
            return

        # Special handling for tuple iteration over list of tuples
        if (isinstance(node.target, ast.Tuple) and len(node.target.elts) == 2 and
            isinstance(node.target.elts[0], ast.Name) and isinstance(node.target.elts[1], ast.Name) and
            isinstance(node.iter, ast.Name) and node.iter.id in self.variables and
            isinstance(self.variables[node.iter.id], list) and
            all(isinstance(item, tuple) and len(item) == 2 for item in self.variables[node.iter.id])):
            # for u, v in edges
            list_var = self.variables[node.iter.id]
            u_var = node.target.elts[0].id
            v_var = node.target.elts[1].id
            if VERBOSE:
                vprint(f"[PennyLaneASTVisitor] Expanding tuple list loop for {node.iter.id} with vars {u_var}, {v_var}")
            for u, v in list_var:
                self.variables[u_var] = u
                self.variables[v_var] = v
                for stmt in node.body:
                    self.visit(stmt)
            return

        # Extract loop variable for simple range loops
        if not isinstance(node.target, ast.Name):
            self.generic_visit(node)
            return
        
        loop_var = node.target.id
        
        # Extract range information
        range_start, range_end = self._extract_range(node.iter)
        if range_start is None or range_end is None:
            # Not a simple range() call: we cannot translate its body faithfully.
            if any(isinstance(n, ast.Call) and self._is_qml_call(n) for n in ast.walk(node)):
                self.unsupported_operations.add(f"for-loop over {ast.unparse(node.iter)}")
                return
            self.generic_visit(node)
            return

        # A loop whose body indexes a known array with the loop variable (inputs[i],
        # weights[layer, i, 0]) cannot stay a symbolic loop: every iteration needs its
        # own concrete angle. Unroll it, with a hard cap on the total work.
        if (isinstance(range_start, int) and isinstance(range_end, int)
                and self._body_indexes_known_array(node, loop_var)):
            iterations = bounded_range(range_start, range_end)
            self.unrolled_iterations += len(iterations)
            if self.unrolled_iterations > MAX_STATIC_RANGE:
                raise UnsupportedCircuitError(
                    f"unrolling loops that index arrays would produce more than "
                    f"{MAX_STATIC_RANGE:,} iterations (limit {MAX_STATIC_RANGE:,})"
                )
            had_old = loop_var in self.variables
            old_val = self.variables.get(loop_var)
            try:
                for value in iterations:
                    self.variables[loop_var] = value
                    for stmt in node.body:
                        self.visit(stmt)
            finally:
                if had_old:
                    self.variables[loop_var] = old_val
                else:
                    self.variables.pop(loop_var, None)
            return

        # Preserve loop structure for OpenQASM output instead of unrolling.
        old_val = self.variables.get(loop_var)
        self.variables[loop_var] = loop_var

        loop_body = []
        saved_operations = self.operations
        self.operations = loop_body
        self.loop_stack.append((loop_var, range_start, range_end))
        try:
            for stmt in node.body:
                self.visit(stmt)
        finally:
            self.loop_stack.pop()
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

    def visit_If(self, node: ast.If) -> None:
        """Handle if statements in PennyLane code."""
        if VERBOSE:
            vprint("[PennyLaneASTVisitor] visit_If: inspecting if statement")
        
        # Skip 'if __name__ == "__main__":' blocks
        if self._is_main_guard(node):
            if VERBOSE:
                vprint("[PennyLaneASTVisitor] Skipping __main__ guard block")
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
                vprint(f"[PennyLaneASTVisitor] Added if statement: {condition}")
        else:
            if VERBOSE:
                vprint(f"[PennyLaneASTVisitor] Skipping empty if statement: {condition}")

    @staticmethod
    def _subscript_chain(node: ast.Subscript) -> Tuple[Optional[str], List[ast.AST]]:
        """a[i][j, k] -> ('a', [i, j, k]); the base name is None if it is not a plain name."""
        index_nodes: List[ast.AST] = []
        cur: ast.AST = node
        while isinstance(cur, ast.Subscript):
            sl = cur.slice.value if isinstance(cur.slice, getattr(ast, "Index", ())) else cur.slice
            index_nodes = (list(sl.elts) if isinstance(sl, ast.Tuple) else [sl]) + index_nodes
            cur = cur.value
        return (cur.id if isinstance(cur, ast.Name) else None), index_nodes

    def _body_indexes_known_array(self, loop: ast.For, loop_var: str) -> bool:
        """True if the loop body indexes a known numeric array using the loop variable."""
        for sub in ast.walk(loop):
            if not isinstance(sub, ast.Subscript):
                continue
            base, index_nodes = self._subscript_chain(sub)
            if base is None or not isinstance(self.variables.get(base), (list, tuple)):
                continue
            if any(isinstance(n, ast.Name) and n.id == loop_var
                   for idx in index_nodes for n in ast.walk(idx)):
                return True
        return False

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
        
        return None, None

    def _extract_range_bound(self, node: ast.expr) -> Union[int, str, None]:
        """Extract a range bound - could be an int, variable name, or simple expression."""
        # Try to resolve constant values (including tracked variables)
        val = self._extract_constant_value(node)
        if val is not None:
            return val

        # Handle simple binary expressions like n-1 or n+1 when variable is known
        if isinstance(node, ast.BinOp):
            left = self._extract_range_bound(node.left)
            right = self._extract_range_bound(node.right)
            if isinstance(left, int) and isinstance(right, int):
                if isinstance(node.op, ast.Sub):
                    return left - right
                if isinstance(node.op, ast.Add):
                    return left + right
                if isinstance(node.op, ast.Mult):
                    return left * right
                if isinstance(node.op, ast.Div) and right != 0:
                    return left // right

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
            # Look up variable in tracked variables
            var_name = node.id
            if var_name in self.variables:
                val = self.variables[var_name]
                if isinstance(val, int):
                    if VERBOSE:
                        vprint(f"[PennyLaneASTVisitor] Resolved range variable: {var_name} = {val}")
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
            # In PennyLane, measurement results are accessed via wires
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

    def _is_qml_call(self, call: ast.Call, attr_name: Optional[str] = None) -> bool:
        """Check if this is a qml function call, optionally matching a specific attribute."""
        is_qml = (isinstance(call.func, ast.Attribute) and
                  isinstance(call.func.value, ast.Name) and
                  call.func.value.id == 'qml')
        if not is_qml:
            return False
        if attr_name:
            return call.func.attr == attr_name
        return True

    def _extract_wires_from_device(self, call: ast.Call) -> None:
        for kw in call.keywords:
            if kw.arg == 'wires':
                if isinstance(kw.value, ast.Constant):
                    self.qubits = int(kw.value.value)
                elif isinstance(kw.value, ast.Name):
                    # Handle variable reference like wires=n_bits
                    var_name = kw.value.id
                    if var_name in self.variables:
                        self.qubits = int(self.variables[var_name])
                        if VERBOSE:
                            vprint(f"[PennyLaneASTVisitor] Resolved wires from variable: {var_name} = {self.qubits}")
                return

    def _handle_qml_call(self, call: ast.Call) -> None:
        if not self._is_qml_call(call):
            if VERBOSE:
                vprint("[PennyLaneASTVisitor]   Not a qml call")
            return

        method_name = call.func.attr
        if VERBOSE:
            vprint(f"[PennyLaneASTVisitor] Handling qml.{method_name}")

        # Handle measurements - qml.measure(wires=i), qml.probs(wires=[...]), etc.
        if method_name in ['measure', 'probs', 'sample', 'counts', 'expval', 'var', 'state',
                           'density_matrix', 'vn_entropy', 'mutual_info', 'purity']:
            if VERBOSE:
                vprint(f"[PennyLaneASTVisitor]   Routing to measurement handler: {method_name}")
            self._handle_measurement_pennylane(call)
            return

        gate_map = self._get_gate_mapping()

        if method_name == 'MultiControlledX':
            if any(kw.arg not in ('wires',) for kw in call.keywords):
                raise UnsupportedCircuitError("qml.MultiControlledX with control_values/work_wires is not supported")
            qubits = self._extract_wires(call)
            if qubits:
                # In MultiControlledX(wires=wires), the last wire is target, others are controls
                controls = qubits[:-1]
                if len(qubits) == 3:
                    self.operations.append(GateNode(name='ccx', qubits=qubits))
                else:
                    self.operations.append(GateNode(name='x', qubits=qubits, modifiers={'ctrl': len(controls)}))
                return

        if method_name == 'GroverOperator':
            qubits = self._extract_wires(call)
            if qubits:
                self._decompose_grover_operator(qubits)
                return

        if method_name == 'Rot':
            # Rot(phi, theta, omega) = RZ(omega) RY(theta) RZ(phi)  (RZ(phi) acts first)
            qubits = self._extract_wires(call)
            params = self._extract_params(call, method_name)
            if len(qubits) != 1 or len(params) != 3:
                raise UnsupportedCircuitError(f"could not parse qml.Rot call '{ast.unparse(call)}'")
            phi, theta, omega = params
            self.operations.append(GateNode(name='rz', qubits=list(qubits), parameters=[phi]))
            self.operations.append(GateNode(name='ry', qubits=list(qubits), parameters=[theta]))
            self.operations.append(GateNode(name='rz', qubits=list(qubits), parameters=[omega]))
            return

        if method_name == 'Barrier':
            self.operations.append(BarrierNode(qubits=self._extract_wires(call) or None))
            return

        if method_name == 'GlobalPhase':
            # Emitted for fidelity of the QASM; it never changes measurement statistics.
            params = self._extract_params(call, method_name)
            self.operations.append(GateNode(name='gphase', qubits=[], parameters=params))
            return

        if method_name in self._GATE_ALIASES:
            gate_map = dict(gate_map)
            gate_map[method_name] = self._GATE_ALIASES[method_name]

        if method_name in gate_map:
            self._log_qml_call(method_name, call)
            qubits = self._extract_wires(call)
            params = self._extract_params(call, method_name)

            if VERBOSE:
                vprint(f"[PennyLaneASTVisitor]   Extracted wires: {qubits}")
                vprint(f"[PennyLaneASTVisitor]   Extracted params: {params}")

            if not qubits:
                raise UnsupportedCircuitError(f"could not resolve the wires of '{ast.unparse(call)}'")

            self.operations.append(GateNode(name=gate_map[method_name], qubits=qubits, parameters=params))
            if VERBOSE:
                vprint(f"[PennyLaneASTVisitor] Added op {method_name} wires={qubits} params={params}")
        elif method_name not in self._NON_OPERATION_CALLS:
            self.unsupported_operations.add(f"qml.{method_name}")

    # PennyLane names (and aliases) that map 1:1 onto OpenQASM gates.
    _GATE_ALIASES = {
        'X': 'x', 'Y': 'y', 'Z': 'z', 'H': 'h', 'SX': 'sx', 'CH': 'ch', 'ISWAP': 'iswap',
        'U1': 'p', 'U2': 'u2', 'U3': 'u3', 'CPhase': 'cp', 'IsingXX': 'rxx', 'IsingYY': 'ryy',
        'IsingZZ': 'rzz', 'CCZ': 'ccz', 'CSWAP': 'cswap', 'Toffoli': 'ccx', 'Identity': 'id',
        'I': 'id',
    }
    # Number and keyword names of the angle parameters of each gate.
    _PARAM_NAMES = {
        'RX': ['phi'], 'RY': ['phi'], 'RZ': ['phi'], 'PhaseShift': ['phi'], 'U1': ['phi'],
        'CRX': ['phi'], 'CRY': ['phi'], 'CRZ': ['phi'], 'ControlledPhaseShift': ['phi'], 'CPhase': ['phi'],
        'IsingXX': ['phi'], 'IsingYY': ['phi'], 'IsingZZ': ['phi'], 'GlobalPhase': ['phi'],
        'U2': ['phi', 'delta'], 'U3': ['theta', 'phi', 'delta'], 'Rot': ['phi', 'theta', 'omega'],
    }

    def _decompose_grover_operator(self, wires: List[int]):
        """Decompose Grover's diffusion operator into standard gates."""
        # H on all
        for w in wires:
            self.operations.append(GateNode(name='h', qubits=[w]))
        # X on all
        for w in wires:
            self.operations.append(GateNode(name='x', qubits=[w]))
        # MCZ: H on last, MCX, H
        self.operations.append(GateNode(name='h', qubits=[wires[-1]]))
        controls = wires[:-1]
        if len(wires) == 3:
            self.operations.append(GateNode(name='ccx', qubits=wires))
        else:
            self.operations.append(GateNode(name='x', qubits=wires, modifiers={'ctrl': len(controls)}))
        self.operations.append(GateNode(name='h', qubits=[wires[-1]]))
        # X on all
        for w in wires:
            self.operations.append(GateNode(name='x', qubits=[w]))
        # H on all
        for w in wires:
            self.operations.append(GateNode(name='h', qubits=[w]))

    def _handle_measurement_pennylane(self, call: ast.Call) -> None:
        """
        Handle qml.measure() calls and create MeasurementNode.
        
        PennyLane measurements: qml.measure(wires=i)
        Maps to OpenQASM: c[clbit_index] = measure q[qubit_index];
        """
        method = call.func.attr
        if method in ('expval', 'var', 'state', 'density_matrix', 'vn_entropy', 'mutual_info', 'purity'):
            # Not a computational-basis readout; the simulator samples the final state.
            return []
        for kw in call.keywords:
            if kw.arg in ('postselect',) or (kw.arg == 'reset' and method != 'measure'):
                raise UnsupportedCircuitError(f"qml.{method}({kw.arg}=...) is not supported")
            if kw.arg not in ('wires', 'reset', 'op'):
                raise UnsupportedCircuitError(f"qml.{method}({kw.arg}=...) is not supported")
        wires = self._extract_wires(call)
        if not wires:
            if VERBOSE:
                vprint("[PennyLaneASTVisitor] measurement with no wires found")
            return []
        reset = any(kw.arg == 'reset' and isinstance(kw.value, ast.Constant) and kw.value.value is True
                    for kw in call.keywords)

        clbits = []
        for wire in wires:
            clbit = self._allocate_clbit()
            clbits.append(clbit)
            self.operations.append(MeasurementNode(qubit=wire, clbit=clbit))
            if reset:
                self.operations.append(ResetNode(qubit=wire))
            self.measured = True
            if VERBOSE:
                vprint(f"[PennyLaneASTVisitor] Added measurement q[{wire}] -> c[{clbit}]")
        return clbits

    def _allocate_clbit(self):
        """Next classical bit; inside range() loops each iteration gets its own bit."""
        if not self.loop_stack:
            clbit = self.clbits
            self.clbits += 1
            return clbit
        total = 1
        for var, start, end in self.loop_stack:
            if not isinstance(start, int) or not isinstance(end, int):
                raise UnsupportedCircuitError(f"measurement inside a loop with non-constant range over '{var}'")
            total *= max(0, end - start)
        base = self.clbits
        self.clbits += total
        terms, stride = [], 1
        for var, start, end in reversed(self.loop_stack):
            term = var if start == 0 else f"({var}-{start})"
            terms.append(term if stride == 1 else f"{term}*{stride}")
            stride *= max(0, end - start)
        expr = "+".join(reversed(terms))
        return expr if base == 0 else f"{base}+{expr}"

    def _get_gate_mapping(self) -> dict:
        """Get mapping of PennyLane gate names to OpenQASM mnemonics."""
        # Centralized registry: invert once and reuse
        return dict(get_pl_inverse_qasm_map())

    def _log_qml_call(self, method_name: str, call: ast.Call) -> None:
        """Log detailed information about qml call if verbose."""
        if not VERBOSE:
            return

        try:
            args_dump = [ast.dump(a, include_attributes=False) for a in call.args]
        except Exception:
            args_dump = [str(a) for a in call.args]

        kw_dump = {}
        for kw in call.keywords:
            try:
                kw_dump[kw.arg] = ast.dump(kw.value, include_attributes=False)
            except Exception:
                kw_dump[kw.arg] = str(kw.value)

        vprint(f"[PennyLaneASTVisitor] qml.{method_name} raw.args={args_dump}")
        vprint(f"[PennyLaneASTVisitor] qml.{method_name} raw.keywords={kw_dump}")

    def _extract_wires(self, call: ast.Call) -> List[Any]:
        # wires may appear as keyword or positional last arg
        # Prefer keyword 'wires'
        if VERBOSE:
            vprint("[PennyLaneASTVisitor]   _extract_wires")
        for kw in call.keywords:
            if kw.arg == 'wires':
                return self._parse_wires_value(kw.value)
        # Fallback: try last positional if reasonable
        if call.args:
            last = call.args[-1]
            parsed = self._parse_wires_value(last)
            if parsed:
                return parsed
        return []

    def _parse_wires_value(self, node: ast.AST) -> List[Any]:
        if VERBOSE:
            try:
                vprint(f"[PennyLaneASTVisitor]     _parse_wires_value node={ast.dump(node, include_attributes=False)}")
            except Exception:
                vprint("[PennyLaneASTVisitor]     _parse_wires_value node=<dump failed>")
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return [int(node.value)]
        if isinstance(node, ast.Name):
            # Variable wire index (e.g., wires=i in a for loop)
            if node.id in self.variables:
                val = self.variables[node.id]
                if isinstance(val, int):
                    return [val]
                if isinstance(val, list):
                    return val
            return [node.id]
        if isinstance(node, ast.List):
            result: List[Any] = []
            for elt in node.elts:
                if isinstance(elt, ast.Constant) and isinstance(elt.value, int):
                    result.append(int(elt.value))
                elif isinstance(elt, ast.Name):
                    if elt.id in self.variables:
                        val = self.variables[elt.id]
                        if isinstance(val, int):
                            result.append(val)
                        else:
                            result.append(elt.id)
                    else:
                        result.append(elt.id)
                elif isinstance(elt, ast.BinOp):
                    # Support expressions like i + 1 (common in loop wires)
                    try:
                        expr = ast.unparse(elt) if hasattr(ast, 'unparse') else None
                        if expr:
                            try:
                                # Try evaluating the expression with current variables
                                val = static_eval(ast.parse(expr, mode='eval'), self._numeric_variables())
                                if isinstance(val, int):
                                    result.append(val)
                                else:
                                    result.append(expr.replace(' ', ''))
                            except Exception:
                                # Fallback to symbolic if evaluation fails
                                result.append(expr.replace(' ', ''))
                        else:
                            result.append('expr')
                    except Exception:
                        result.append('expr')
            return result
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id == 'range' and len(node.args) == 1:
                    arg = self._parse_wires_value(node.args[0])
                    if arg and isinstance(arg[0], int):
                        return bounded_range(arg[0])
                elif node.func.id == 'list' and len(node.args) == 1:
                    arg = self._parse_wires_value(node.args[0])
                    if arg:
                        return arg
            return []
        
        if isinstance(node, ast.BinOp):
            try:
                expr = ast.unparse(node) if hasattr(ast, 'unparse') else None
                if expr:
                    try:
                        val = static_eval(ast.parse(expr, mode='eval'), self._numeric_variables())
                        if isinstance(val, int):
                            return [val]
                        return [expr.replace(' ', '')]
                    except Exception:
                        return [expr.replace(' ', '')]
            except Exception:
                return ['expr']

        return []

    def _extract_params(self, call: ast.Call, method_name: str) -> List[Any]:
        """Angle parameters, positional (before the wires) or by keyword."""
        names = self._PARAM_NAMES.get(method_name, [])
        if not names:
            if any(kw.arg not in ('wires', 'id') for kw in call.keywords):
                raise UnsupportedCircuitError(f"unsupported keyword arguments in '{ast.unparse(call)}'")
            return []
        has_wires_kw = any(kw.arg == 'wires' for kw in call.keywords)
        positional = list(call.args if has_wires_kw else call.args[:-1])
        values: List[Any] = [None] * len(names)
        for i, arg in enumerate(positional):
            if i >= len(names):
                raise UnsupportedCircuitError(f"too many arguments in '{ast.unparse(call)}'")
            values[i] = self._extract_parameter(arg)
        for kw in call.keywords:
            if kw.arg in ('wires', 'id'):
                continue
            if kw.arg not in names:
                raise UnsupportedCircuitError(f"unsupported keyword '{kw.arg}' in '{ast.unparse(call)}'")
            values[names.index(kw.arg)] = self._extract_parameter(kw.value)
        if any(v is None for v in values):
            raise UnsupportedCircuitError(f"missing parameters in '{ast.unparse(call)}'")
        if VERBOSE:
            vprint(f"[PennyLaneASTVisitor]   _extract_params method={method_name} -> {values}")
        return values

    def _extract_parameter(self, node: ast.AST):
        if VERBOSE:
            self._log_parameter_extraction(node)

        # Route to appropriate handler based on node type
        if isinstance(node, ast.Constant):
            return self._handle_constant_parameter(node)
        elif isinstance(node, ast.Name):
            return self._handle_name_parameter(node)
        elif isinstance(node, ast.UnaryOp):
            return self._handle_unary_op_parameter(node)
        elif isinstance(node, ast.Attribute):
            return self._handle_attribute_parameter(node)
        elif isinstance(node, ast.BinOp):
            return self._handle_binary_op_parameter(node)
        elif isinstance(node, ast.List):
            return self._handle_list_parameter(node)
        elif isinstance(node, ast.Subscript):
            return self._handle_subscript_parameter(node)
        elif isinstance(node, ast.ListComp):
            return self._handle_listcomp_parameter(node)
        elif isinstance(node, ast.Call):
            return self._handle_call_parameter(node)
        else:
            return 'expr'  # Fallback

    def _log_parameter_extraction(self, node: ast.AST) -> None:
        """Log parameter extraction details if verbose."""
        if not VERBOSE:
            return
        try:
            vprint(f"[PennyLaneASTVisitor]   _extract_parameter node={ast.dump(node, include_attributes=False)}")
        except Exception:
            vprint("[PennyLaneASTVisitor]   _extract_parameter node=<dump failed>")

    # Removed deprecated ast.Num handler; ast.Constant path covers ints

    def _handle_constant_parameter(self, node: ast.Constant):
        """Handle constant parameters (Python 3.8+)."""
        return node.value

    def _handle_name_parameter(self, node: ast.Name):
        """Handle named/symbolic parameters."""
        if node.id in self.variables:
            return self.variables[node.id]
        self.parameters.add(node.id)
        return node.id

    def _handle_unary_op_parameter(self, node: ast.UnaryOp):
        """Handle unary operations (like negation)."""
        if isinstance(node.op, ast.USub):
            inner = self._extract_parameter(node.operand)
            return f"-{inner}" if isinstance(inner, (str, int, float)) else inner
        return 'expr'

    def _handle_attribute_parameter(self, node: ast.Attribute):
        """Handle attribute access (like np.pi)."""
        if (isinstance(node.value, ast.Name) and
            node.value.id in ('np', 'numpy') and
            node.attr == 'pi'):
            return np.pi
        return 'expr'

    def _handle_binary_op_parameter(self, node: ast.BinOp):
        """Handle binary operations (+, -, *, /)."""
        left = self._extract_parameter(node.left)
        right = self._extract_parameter(node.right)

        if isinstance(node.op, ast.Add):
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left + right
            if isinstance(left, list) and isinstance(right, list):
                return left + right
            return f"{left} + {right}"
        elif isinstance(node.op, ast.Sub):
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left - right
            return f"{left} - {right}"
        elif isinstance(node.op, ast.Mult):
            if isinstance(left, (int, float)) and isinstance(right, (int, float)):
                return left * right
            if isinstance(left, list) and isinstance(right, int):
                return left * right
            return f"{left}*{right}"
        elif isinstance(node.op, ast.Div):
            if isinstance(left, (int, float)) and isinstance(right, (int, float)) and right != 0:
                return left / right
            return self._format_division(left, right)
        else:
            return 'expr'

    def _handle_list_parameter(self, node: ast.List):
        """Handle list literals."""
        return [self._extract_parameter(elt) for elt in node.elts]

    def _handle_subscript_parameter(self, node: ast.Subscript):
        """Handle subscript access like theta[w], list[:n], or weights[layer, i, 0]."""
        # ── 1/2. Flatten a[i][j] / a[i, j] / a[i][j, k] into base name + index nodes ──
        base_name, indices_nodes = self._subscript_chain(node)

        resolved_indices: List[Union[int, str]] = []
        for idx_node in indices_nodes:
            val = self._extract_parameter(idx_node)
            if not isinstance(val, (int, float, np.integer, np.floating)) or isinstance(val, bool):
                try:  # index arithmetic such as (a + b) % 2, resolved without running user code
                    val = static_eval(idx_node, self._numeric_variables())
                except NotStatic:
                    pass
            if isinstance(val, bool):
                resolved_indices.append(str(val))
            elif isinstance(val, (int, np.integer)):
                resolved_indices.append(int(val))
            elif isinstance(val, (float, np.floating)) and float(val).is_integer():
                resolved_indices.append(int(val))
            else:
                resolved_indices.append(str(val))

        all_concrete = all(isinstance(idx, int) for idx in resolved_indices)

        # ── 3. Handle known variables (e.g. lists or numpy arrays in scope) ──
        if base_name and base_name in self.variables:
            base = self.variables[base_name]
            try:
                if all_concrete:
                    # Try to index into the actual object if it's in scope
                    target = base
                    for idx in resolved_indices:
                        target = target[idx]
                    if isinstance(target, (int, float, complex)):
                        return float(target)
            except Exception:
                pass

        # ── 4. Track symbolic parameter array and declare shape ───────────────
        if base_name and base_name not in self.variables:
            # Initialize or update the tracked shape (list of max sizes seen so far)
            current_shape = self.array_parameters.get(base_name, [])
            
            # Ensure current_shape has enough dimensions
            while len(current_shape) < len(resolved_indices):
                current_shape.append(1)
            
            # Update each dimension's size
            for i, idx in enumerate(resolved_indices):
                if isinstance(idx, int):
                    current_shape[i] = max(current_shape[i], idx + 1)
                else:
                    # For symbolic indices, we can't accurately know the size
                    # but we've already registered the dimension above with size 1
                    pass
            
            self.array_parameters[base_name] = current_shape

            # Return the substituted or partially-substituted string
            # e.g. "weights[0, 1, 0]" instead of raw "weights[layer, i, 0]"
            idx_str = ", ".join(str(idx) for idx in resolved_indices)
            return f"{base_name}[{idx_str}]"

        # ── 5. Fallback ──────────────────────────────────────────────────────
        try:
            expr = ast.unparse(node) if hasattr(ast, 'unparse') else None
            if expr:
                return expr.replace(' ', '')
        except Exception:
            pass
        return f"{base_name}[?]"

        # ── Generic eval fallback ─────────────────────────────────────────────
        try:
            expr = ast.unparse(node) if hasattr(ast, 'unparse') else None
            if expr:
                try:
                    val = static_eval(ast.parse(expr, mode='eval'), self._numeric_variables())
                    if isinstance(val, (int, float, list)):
                        return val
                except Exception:
                    return expr.replace(' ', '')
        except Exception:
            pass

        return 'expr'

    def _handle_listcomp_parameter(self, node: ast.ListComp):
        """[f(i) for i in range(n)] evaluated statically (no eval of user code)."""
        if len(node.generators) != 1 or node.generators[0].ifs or not isinstance(node.generators[0].target, ast.Name):
            return 'expr'
        gen = node.generators[0]
        try:
            values = self._static_iterable(gen.iter)
            out = []
            for v in values:
                env = dict(self._numeric_variables())
                env[gen.target.id] = v
                out.append(static_eval(node.elt, env))
            return out
        except NotStatic:
            return 'expr'

    def _numeric_variables(self):
        return {k: v for k, v in self.variables.items() if not isinstance(v, str)}

    def _static_iterable(self, node):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'range' \
                and not node.keywords and 1 <= len(node.args) <= 3:
            bounds = [static_eval(a, self._numeric_variables()) for a in node.args]
            if not all(isinstance(b, int) for b in bounds):
                raise NotStatic("range bounds")
            return bounded_range(*bounds)
        value = static_eval(node, self._numeric_variables())
        if not isinstance(value, list):
            raise NotStatic("not iterable")
        return value

    def _handle_call_parameter(self, node: ast.Call):
        """Handle calls like list(range(n)), np.array([...]) or np.sin(x) statically."""
        if self._is_qml_call(node):
            return 'expr'
        if isinstance(node.func, ast.Name) and node.func.id == 'list' and len(node.args) == 1:
            try:
                return self._static_iterable(node.args[0])
            except NotStatic:
                return 'expr'
        try:
            return static_eval(node, self._numeric_variables())
        except NotStatic:
            return 'expr'


class PennyLaneASTParser:
    """
    Parse PennyLane source into CircuitAST using static AST analysis.
    """

    def __init__(self):
        self.visitor = PennyLaneASTVisitor()

    def parse(self, source_code: str) -> CircuitAST:
        vprint("[PennyLaneASTParser] Using AST parsing for secure PennyLane code analysis")
        if VERBOSE:
            vprint("[PennyLaneASTParser] Starting AST parsing of PennyLane source code")
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            vprint(f"[PennyLaneASTParser] Syntax error during AST parsing: {e}")
            raise ValueError(f"Invalid Python syntax in source code: {e}")

        # Reset visitor
        self.visitor = PennyLaneASTVisitor()
        self.visitor.visit(tree)
        if self.visitor.unsupported_operations:
            unsupported = ", ".join(sorted(self.visitor.unsupported_operations))
            raise UnsupportedCircuitError(f"Unsupported PennyLane operations encountered: {unsupported}")

        # Determine qubit count: prefer device wires; else infer from max wire index
        if self.visitor.qubits <= 0:
            self.visitor.qubits = self._infer_qubit_count()

        # Determine classical bit count: use clbits if set, else infer from qubits
        clbit_count = self.visitor.clbits

        circuit_ast = CircuitAST(
            qubits=self.visitor.qubits,
            clbits=clbit_count,
            operations=self.visitor.operations,
            parameters=list(self.visitor.parameters),
            variables=self.visitor.variables,
            array_parameters=self.visitor.array_parameters
        )

        vprint("[PennyLaneASTParser] Built CircuitAST")
        return circuit_ast

    def _infer_qubit_count(self) -> int:
        """Infer qubit count from operations, for loop ranges, and variables."""
        max_qubit = 0
        
        for op in self.visitor.operations:
            # Check ForLoopNode ranges
            if isinstance(op, ForLoopNode):
                # Python range end is exclusive; ensure we allocate enough qubits for possible q[i+1] usage.
                if isinstance(op.range_end, int):
                    max_qubit = max(max_qubit, op.range_end + 1)
                elif op.range_end is not None:
                    max_qubit = max(max_qubit, 1)
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
            if isinstance(value, int) and var_name in ['n_bits', 'n_qubits', 'num_qubits', 'wires']:
                max_qubit = max(max_qubit, value)
        
        return max_qubit if max_qubit > 0 else 1

    def get_supported_gates(self) -> List[str]:
        return [
            'PauliX', 'PauliY', 'PauliZ', 'Hadamard', 'S', 'T', 'Identity',
            'RX', 'RY', 'RZ', 'PhaseShift', 'CNOT', 'CZ', 'SWAP', 'Toffoli'
        ]

