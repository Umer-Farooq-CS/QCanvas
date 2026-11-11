import os
import numpy as np
import math
from qsim.visitors.base_visitor import BaseVisitor
from qiskit.circuit import Parameter, QuantumCircuit, QuantumRegister, ClassicalRegister
from typing import List, Dict, Any
from dataclasses import dataclass
import openqasm3

@dataclass
class Symbol:
    """A structure to hold the result of resolving an identifier or expression."""
    value: Any
    type: str  # e.g., 'quantum', 'classical', 'classical_value', 'array'
    is_const: bool = False
    name: str = None  # Optional, for variables
    is_indexed: bool = False

@dataclass
class Angle:
    """Represents an angle as a fixed-point unsigned integer."""
    uint_value: int
    size: int

class QiskitVisitor(BaseVisitor):
    def __init__(self):
        self.qc = QuantumCircuit()
        self.env_scopes = [{}]  # For classical variables (int, float, bool, etc.)
        self.qubits_scopes = [{}]  # For quantum registers
        self.clbits_scopes = [{}]  # For classical registers
        self.consts_scopes = [set()]  # Track constant variable names
        self.scope_types = ['global']  # Track scope type (global, block, gate)
        self.in_dynamic_branch = False  # Flag for dynamic control blocks
        self.custom_gates = {}
        self.builtin_gates = {
            'id', 'x', 'y', 'z', 'h', 's', 'sdg', 't', 'tdg', 'sx',
            'rx', 'ry', 'rz', 'u', 'cx', 'cy', 'cz', 'cp', 'ch', 'cu',
            'swap', 'cswap',
            'crx', 'cry', 'crz',
            'ccx', 'ccz', 'p', 'phase', 'u1', 'u2', 'u3', 'U', 'CX', 'cphase', 'cu1', 'cu3',
            'rzz', 'rxx', 'ryy', 'iswap'
        }
        self.gate_call_stack = []  # Track recursion
        self.measured_bits = set()  # Track which bits have been measured
        self.variables = {  # Predefined constants
            "pi": {"type": "const float[64]", "value": math.pi, "const": True},
            "π": {"type": "const float[64]", "value": math.pi, "const": True},
            "tau": {"type": "const float[64]", "value": 2 * math.pi, "const": True},
            "τ": {"type": "const float[64]", "value": 2 * math.pi, "const": True},
            "euler": {"type": "const float[64]", "value": math.e, "const": True},
            "ℇ": {"type": "const float[64]", "value": math.e, "const": True}
        }

    def get_var(self, category: str, var_name: str) -> Any:
        """Retrieve a variable from the specified category's scope stack.
        Returns None if not found, raises NameError if accessed incorrectly in gate scope."""
        scopes = getattr(self, f"{category}_scopes")
        is_in_gate_or_def = self.scope_types[-1] in ['gate', 'def']

        if is_in_gate_or_def:
            # Inside gate/def, check local scope first (params, locals, aliases)
            if var_name in scopes[-1]:
                return scopes[-1][var_name]
            
            # Then, check ONLY global scope (scopes[0]), and only if const or gate/subroutine
            if category == 'env':
                if var_name in scopes[0]:
                    if self.is_const_in_scope(var_name, 0) or var_name in self.custom_gates:  # Allow global consts and gates
                        return scopes[0][var_name]
                    else:
                        raise NameError(f"Gate or subroutine cannot access non-constant global variable '{var_name}'.")
            elif category in ['qubits', 'clbits']:  # Qubits/clbits only if params (local) or hardware (global const-like)
                if var_name in scopes[0] and self.is_const_in_scope(var_name, 0):
                    return scopes[0][var_name]
            return None
        else:
            # Normal search for other scopes (global, block)
            for d in reversed(scopes):
                if var_name in d:
                    return d[var_name]
            # Variable not found - check if it truly doesn't exist anywhere
            # This helps tests verify proper scoping
            exists_anywhere = any(var_name in scope for scope in scopes)
            if not exists_anywhere and category == 'env' and var_name not in self.variables:
                # Only raise if this appears to be a test/verification call (not internal usage)
                # We can detect this by checking the call stack, but simpler: just raise for env category
                raise NameError(f"Variable '{var_name}' is not defined in any scope.")
            return None

    def is_const_in_scope(self, var_name: str, scope_idx: int) -> bool:
        """Check if a variable is constant in a specific scope."""
        if scope_idx < len(self.consts_scopes):
            return var_name in self.consts_scopes[scope_idx]
        return False

    def set_var(self, category: str, var_name: str, value: Any):
        """Set a variable in the current scope."""
        scopes = getattr(self, f"{category}_scopes")
        scopes[-1][var_name] = value

    def update_var(self, category: str, var_name: str, value: Any):
        """Update a variable in the nearest scope where it exists."""
        scopes = getattr(self, f"{category}_scopes")
        for d in reversed(scopes):
            if var_name in d:
                d[var_name] = value
                return
        raise NameError(f"{category.capitalize()} variable '{var_name}' not defined.")

    def enter_scope(self, scope_type: str):
        """Enter a new scope."""
        self.env_scopes.append({})
        self.qubits_scopes.append({})
        self.clbits_scopes.append({})
        self.consts_scopes.append(set())
        self.scope_types.append(scope_type)

    def exit_scope(self):
        """Exit the current scope."""
        self.env_scopes.pop()
        self.qubits_scopes.pop()
        self.clbits_scopes.pop()
        self.consts_scopes.pop()
        self.scope_types.pop()

    def is_const(self, var_name: str) -> bool:
        """Check if a variable is constant."""
        for s in reversed(self.consts_scopes):
            if var_name in s:
                return True
        return False

    def add_const(self, var_name: str):
        """Mark a variable as constant in the current scope."""
        self.consts_scopes[-1].add(var_name)


    def visit_GateDefinition(self, node):
        """Handle gate definitions."""
        if self.scope_types[-1] != 'global':
            raise SyntaxError("gate declarations must be global")
        name = node.name.name
        if name in self.custom_gates or self.get_var('env', name) is not None:
            raise NameError(f"Gate '{name}' is already defined and cannot be redeclared.")
        
        classical_args = [arg.name for arg in node.arguments or []]
        qubit_args = [q.name for q in node.qubits]
        self.custom_gates[name] = {'classical_args': classical_args, 'qubit_args': qubit_args, 'body': node.body}
        
        # Validate the body without executing
        self.enter_scope('gate')
        try:
            # Set dummy params
            for arg in classical_args:
                self.set_var('env', arg, 0)
            for q in qubit_args:
                self.set_var('qubits', q, None)
            for stmt in node.body:
                self._validate_stmt(stmt)
        finally:
            self.exit_scope()
        
        return None

    def _check_qubit_indexing(self, qubit_node):
        """Check if a qubit node is indexing a gate parameter."""
        base_name = None
        is_indexed = False
        
        if isinstance(qubit_node, openqasm3.ast.IndexedIdentifier):
            is_indexed = True
            if isinstance(qubit_node.name, openqasm3.ast.Identifier):
                base_name = qubit_node.name.name
            elif isinstance(qubit_node.name, str):
                base_name = qubit_node.name
            elif hasattr(qubit_node.name, 'name'):
                base_name = qubit_node.name.name
        elif isinstance(qubit_node, openqasm3.ast.IndexExpression):
            is_indexed = True
            current = qubit_node.collection
            while isinstance(current, openqasm3.ast.IndexExpression):
                current = current.collection
            if isinstance(current, openqasm3.ast.Identifier):
                base_name = current.name
            elif isinstance(current, openqasm3.ast.IndexedIdentifier):
                if isinstance(current.name, openqasm3.ast.Identifier):
                    base_name = current.name.name
                elif isinstance(current.name, str):
                    base_name = current.name
                elif hasattr(current.name, 'name'):
                    base_name = current.name.name
        
        if is_indexed and base_name and base_name in self.qubits_scopes[-1]:
            raise ValueError(f"Cannot index qubit parameter '{base_name}' in gate definition.")
        
    def _validate_stmt(self, stmt):
        """Validate a statement for gate body (checks without executing)."""
        if isinstance(stmt, openqasm3.ast.QuantumGate):
            for qubit_node in stmt.qubits:
                self._check_qubit_indexing(qubit_node)
        elif isinstance(stmt, openqasm3.ast.ClassicalDeclaration):
            raise ValueError("cannot declare classical variables in a gate")
        elif isinstance(stmt, openqasm3.ast.ClassicalAssignment):
            raise ValueError("cannot assign to classical parameters in a gate")
        elif isinstance(stmt, openqasm3.ast.QuantumMeasurementStatement):
            raise ValueError("cannot have a non-unitary 'measure' instruction in a gate")
        elif isinstance(stmt, openqasm3.ast.QuantumReset):
            raise ValueError("cannot have a non-unitary 'reset' instruction in a gate")
        elif isinstance(stmt, openqasm3.ast.QubitDeclaration):
            raise ValueError("cannot declare qubits in a gate body")
        elif isinstance(stmt, openqasm3.ast.ConstantDeclaration):
            pass
        elif isinstance(stmt, openqasm3.ast.AliasStatement):
            pass
        elif isinstance(stmt, openqasm3.ast.ForInLoop):
            for s in stmt.block:
                self._validate_stmt(s)
        elif isinstance(stmt, openqasm3.ast.BranchingStatement):
            for s in stmt.if_block:
                self._validate_stmt(s)
            if stmt.else_block:
                for s in stmt.else_block:
                    self._validate_stmt(s)
        elif isinstance(stmt, openqasm3.ast.QuantumPhase):
            pass
        elif isinstance(stmt, openqasm3.ast.QuantumBarrier):
            pass
        else:
            raise NotImplementedError(f"Unsupported statement in gate body: {type(stmt).__name__}")


    STANDARD_INCLUDES = frozenset({"stdgates.inc", "qelib1.inc", "stdgates.qasm", "stdctrl.inc"})

    def visit_Include(self, node):
        """
        Only the standard gate libraries may be included. Programs come from
        users, so reading arbitrary paths from the server's disk is never allowed.
        """
        filename = str(node.filename).replace('"', '').strip()
        if filename.lower() in self.STANDARD_INCLUDES:
            return
        raise PermissionError(
            f"Only the standard libraries {sorted(self.STANDARD_INCLUDES)} may be included; "
            f"'{filename}' is not allowed."
        )

    def check_variable_declared(self, var_name: str) -> bool:
        """Check if a variable is already declared in the current scope."""
        if (var_name in self.env_scopes[-1] or
                var_name in self.qubits_scopes[-1] or
                var_name in self.clbits_scopes[-1]):
            raise NameError(f"Variable '{var_name}' is already declared in this scope.")
        return False

    def visit_QubitDeclaration(self, node):
        """Handle qubit declarations like: qubit[SIZE] q1;"""
        if self.scope_types[-1] != 'global':
            raise SyntaxError("qubit declarations must be global")
        name = node.qubit.name
        self.check_variable_declared(name)
        size = Symbol(value=1, type='classical_value', is_const=True)
        if node.size:
            size = self._eval_rvalue(node.size)
            if not size.is_const:
                raise TypeError(f"Qubit register '{name}' size must be a compile-time constant.")
            if not isinstance(size.value, int) or size.value < 0:
                raise ValueError("Register size must be a non-negative integer.")
        qr = QuantumRegister(size.value, name)
        if self.qc is None:
            self.qc = QuantumCircuit(qr)
        else:
            self.qc.add_register(qr)
        self.set_var('qubits', name, qr)
        return qr

    def visit_BitDeclaration(self, node):
        """Handle bit declarations like: bit[SIZE] c;"""
        name = node.identifier.name
        self.check_variable_declared(name)
        size = Symbol(value=1, type='classical_value', is_const=True)
        if node.type.size:
            size = self._eval_rvalue(node.type.size)
            if not size.is_const:
                raise TypeError(f"Size for bit register '{name}' must be a compile-time constant.")
        cr = ClassicalRegister(size.value, name)
        if self.qc is None:
            self.qc = QuantumCircuit(cr)
        else:
            self.qc.add_register(cr)
        self.set_var('clbits', name, cr)
        return cr

    def visit_ConstantDeclaration(self, node):
        """Handle const declarations like: const uint SIZE = 32;"""
        if self.in_dynamic_branch:
            raise ValueError("Constant declarations not allowed in dynamic control blocks.")
        # Note: Const declarations ARE allowed in gate bodies (they're local constants)
        var_name = node.identifier.name
        self.check_variable_declared(var_name)
        if node.init_expression is None:
            raise ValueError(f"Constant variable '{var_name}' must be initialized.")
        eval_result = self._eval_rvalue(node.init_expression)
        if not eval_result.is_const:
            raise TypeError(f"Initializer for constant variable '{var_name}' must be a compile-time constant.")
        self.set_var('env', var_name, eval_result.value)
        self.add_const(var_name)
        return None

    def visit_ClassicalDeclaration(self, node):
        """Handle classical declarations like: int[SIZE] i1; angle[SIZE] a1;"""
        if self.in_dynamic_branch:
            raise ValueError("Classical declarations not allowed in dynamic control blocks.")
        # Note: Classical declarations in gates are caught by the parser, not here
        var_name = node.identifier.name
        self.check_variable_declared(var_name)
        method_name = 'visit_' + type(node.type).__name__
        if hasattr(self, method_name):
            visitor_method = getattr(self, method_name)
            return visitor_method(node)
        raise NotImplementedError(f"Visitor for classical type '{type(node.type).__name__}' not implemented.")

    def visit_AngleType(self, node):
        """Handle angle[size] declarations."""
        var_name = node.identifier.name
        size = Symbol(value=64, type='classical_value', is_const=True)
        if node.type.size:
            size = self._eval_rvalue(node.type.size)
            if not size.is_const:
                raise TypeError(f"Size for angle '{var_name}' must be a compile-time constant.")
            supported_sizes = [16, 32, 64]
            if size.value not in supported_sizes:
                raise TypeError(f"Unsupported angle size: angle[{size.value}]. Supported sizes are: {supported_sizes}")
        uint_value = 0
        if node.init_expression:
            float_value_radians = self._eval_rvalue(node.init_expression).value
            float_value_radians = float_value_radians % (2 * math.pi)
            if float_value_radians < 0:
                float_value_radians += 2 * math.pi
            uint_value = round((float_value_radians / (2 * math.pi)) * (2**size.value))
        self.set_var('env', var_name, Angle(uint_value=uint_value, size=size.value))
        return None

    def visit_IntType(self, node):
        """Handle int[n] declarations."""
        var_name = node.identifier.name
        bit_width = Symbol(value=64, type='classical_value', is_const=True)
        if node.type.size:
            bit_width = self._eval_rvalue(node.type.size)
            if not bit_width.is_const:
                raise TypeError(f"Size for int '{var_name}' must be a compile-time constant.")
        initial_value = Symbol(value=0, type='classical_value', is_const=True)
        if node.init_expression:
            initial_value = self._eval_rvalue(node.init_expression)
        self.set_var('env', var_name, self.to_int(initial_value.value, bit_width.value))
        return None

    def visit_UintType(self, node):
        """Handle uint[n] declarations."""
        var_name = node.identifier.name
        bit_width = Symbol(value=64, type='classical_value', is_const=True)
        if node.type.size:
            bit_width = self._eval_rvalue(node.type.size)
            if not bit_width.is_const:
                raise TypeError(f"Size for uint '{var_name}' must be a compile-time constant.")
        initial_value = Symbol(value=0, type='classical_value', is_const=True)
        if node.init_expression:
            initial_value = self._eval_rvalue(node.init_expression)
        self.set_var('env', var_name, self.to_uint(initial_value.value, bit_width.value))
        return None

    def visit_FloatType(self, node):
        """Handle float[n] declarations."""
        var_name = node.identifier.name
        bit_width = Symbol(value=64, type='classical_value', is_const=True)
        if node.type.size:
            bit_width = self._eval_rvalue(node.type.size)
            if not bit_width.is_const:
                raise TypeError(f"Size for float '{var_name}' must be a compile-time constant.")
        supported_widths = [16, 32, 64]
        if bit_width.value not in supported_widths:
            raise TypeError(f"Unsupported float size: float[{bit_width.value}]. Supported sizes are: {supported_widths}")
        type_map = {16: np.float16, 32: np.float32, 64: float}
        float_type = type_map[bit_width.value]
        initial_value = Symbol(value=0.0, type='classical_value', is_const=True)
        if node.init_expression:
            initial_value = self._eval_rvalue(node.init_expression)
        self.set_var('env', var_name, float_type(initial_value.value))
        return None

    def visit_BoolType(self, node):
        """Handle bool declarations."""
        var_name = node.identifier.name
        initial_value = Symbol(value=False, type='classical_value', is_const=True)
        if node.init_expression:
            initial_value = self._eval_rvalue(node.init_expression)
        self.set_var('env', var_name, bool(initial_value.value))
        return None

    def visit_BitType(self, node):
        """Handle bit declarations."""
        name = node.identifier.name
        size = Symbol(value=1, type='classical_value', is_const=True)
        if node.type.size:
            size = self._eval_rvalue(node.type.size)
            if not size.is_const:
                raise TypeError(f"Size for bit register '{name}' must be a compile-time constant.")
        if node.init_expression:
            initial_bits = self._bits_from_rvalue(node.init_expression)
            if len(initial_bits) != size.value:
                raise TypeError(f"Initializer size ({len(initial_bits)}) does not match declared bit register size ({size.value}) for '{name}'.")
            cr = ClassicalRegister(size.value, name)
            self.set_var('clbits', name, initial_bits)
        else:
            cr = ClassicalRegister(size.value, name)
            self.set_var('clbits', name, [0] * size.value)
        if self.qc is None:
            self.qc = QuantumCircuit(cr)
        else:
            self.qc.add_register(cr)
        return cr

    def visit_QuantumMeasurementStatement(self, node):
        if self.in_dynamic_branch:
            raise ValueError("Measurements not allowed in dynamic control blocks.")
        # Note: Measurements in gates are caught by the parser, not here
        quantum_indices = self._visit_node(node.measure.qubit)
        qubit_reg = self.get_var('qubits', quantum_indices.name)
        if quantum_indices.is_indexed:
            qubits = [qubit_reg[i] for i in self._expand_indices_to_list(quantum_indices.value, len(qubit_reg))]
        else:
            qubits = list(qubit_reg)
        if node.target:
            classical_indices = self._visit_node(node.target)
            clbit_reg = self.get_var('clbits', classical_indices.name)
            self.measured_bits.add(classical_indices.name)
            if classical_indices.is_indexed:
                clbit_indices = self._expand_indices_to_list(classical_indices.value, len(clbit_reg))
                circuit_creg = None
                for creg in self.qc.cregs:
                    if creg.name == classical_indices.name:
                        circuit_creg = creg
                        break
                if circuit_creg is None:
                    raise ValueError(f"Classical register '{classical_indices.name}' not found in circuit")
                clbits = [circuit_creg[i] for i in clbit_indices]
            else:
                circuit_creg = None
                for creg in self.qc.cregs:
                    if creg.name == classical_indices.name:
                        circuit_creg = creg
                        break
                if circuit_creg is None:
                    raise ValueError(f"Classical register '{classical_indices.name}' not found in circuit")
                clbits = list(circuit_creg)
        else:
            clbit_reg_name = quantum_indices.name + "_cl"
            clbit_reg = self.get_var('clbits', clbit_reg_name)
            if clbit_reg is None:
                clbit_reg = ClassicalRegister(len(qubits), clbit_reg_name)
                self.set_var('clbits', clbit_reg_name, clbit_reg)
                if self.qc is None:
                    self.qc = QuantumCircuit(clbit_reg)
                else:
                    self.qc.add_register(clbit_reg)
            circuit_creg = None
            for creg in self.qc.cregs:
                if creg.name == clbit_reg_name:
                    circuit_creg = creg
                    break
            clbits = list(circuit_creg)
            self.measured_bits.add(clbit_reg_name)
        if len(qubits) != len(clbits):
            raise ValueError(f"Number of qubits ({len(qubits)}) to measure does not match number of classical bits ({len(clbits)}).")
        for i, (q, c) in enumerate(zip(qubits, clbits)):
            self.qc.measure(q, c)
        if node.target and classical_indices.is_indexed:
            indices = self._expand_indices_to_list(classical_indices.value, len(clbit_reg))
            for i, idx in enumerate(indices):
                clbit_reg[idx] = 0
            self.update_var('clbits', classical_indices.name, clbit_reg)
        elif not node.target:
            for i in range(len(clbits)):
                clbits[i] = 0
            self.update_var('clbits', clbit_reg_name, clbits)
        return None

    def visit_QuantumReset(self, node):
        """Handle reset statements like: reset q; or reset qubits[10];"""
        # Note: Resets in gates are caught by the parser, not here
        qubits = self._visit_node(node.qubits)
        qubit_reg = self.get_var('qubits', qubits.name)
        if qubits.is_indexed:
            indices = self._expand_indices_to_list(qubits.value, len(qubit_reg))
            for idx in indices:
                self.qc.reset(qubit_reg[idx])
        else:
            for qubit in qubit_reg:
                self.qc.reset(qubit)
        return None

    def visit_Qubit(self, node) -> Symbol:
        """Handle Qubit nodes (single qubit references in gate definitions)."""
        var_name = node.name
        if any(var_name in d for d in reversed(self.qubits_scopes)):
            value = self.get_var('qubits', var_name)
            if not isinstance(value, list):
                value = [value]
            return Symbol(name=var_name, value=value, type='quantum', is_const=False)
        raise NameError(f"Qubit '{var_name}' is not defined.")

    def visit_QuantumGate(self, node):
        """Handle gate applications with modifier and broadcasting support."""
        from qiskit.circuit import Qubit, QuantumRegister
        gate_name = node.name.name.lower()
        
        # Evaluate parameters
        args = [self._eval_rvalue(arg).value for arg in node.arguments] if node.arguments else []
        
        # Collect all qubit operands and check if broadcasting is needed
        qubit_operands = []  # List of lists - each element is a list of qubits for that operand
        max_broadcast_size = 1
        has_broadcasting = False
        
        for qubit_node in node.qubits:
            indices_info = self._visit_node(qubit_node)
            
            if self.scope_types[-1] == 'gate' and indices_info.is_indexed:
                if indices_info.name in self.qubits_scopes[-1]:
                    raise ValueError(f"Cannot index qubit parameter '{indices_info.name}' in gate definition.")
            
            # Resolve to list of qubits
            if indices_info.type == 'quantum' and isinstance(indices_info.value, list):
                qubits_for_operand = indices_info.value
            else:
                qubit_reg = self.get_var('qubits', indices_info.name)
                
                if indices_info.is_indexed:
                    qubits_for_operand = [qubit_reg[i] for i in self._expand_indices_to_list(indices_info.value, len(qubit_reg))]
                else:
                    if isinstance(qubit_reg, QuantumRegister):
                        qubits_for_operand = list(qubit_reg)
                    else:
                        qubits_for_operand = qubit_reg if isinstance(qubit_reg, list) else [qubit_reg]
            
            qubit_operands.append(qubits_for_operand)
            
            # Check if this is a register (multiple qubits) - triggers broadcasting
            if len(qubits_for_operand) > 1:
                has_broadcasting = True
                if max_broadcast_size == 1:
                    max_broadcast_size = len(qubits_for_operand)
                elif len(qubits_for_operand) != max_broadcast_size:
                    raise ValueError(
                        f"Broadcasting error: All quantum register operands must have the same size. "
                        f"Expected {max_broadcast_size}, got {len(qubits_for_operand)}"
                    )
        
        # If broadcasting, expand the gate calls
        if has_broadcasting:
            # Broadcast: apply gate multiple times with corresponding indexed qubits
            for i in range(max_broadcast_size):
                # Collect qubits for this broadcast iteration
                broadcast_qubits = []
                for operand in qubit_operands:
                    if len(operand) == 1:
                        # Single qubit operand - use same qubit for all broadcasts
                        broadcast_qubits.append(operand[0])
                    else:
                        # Multi-qubit operand - use i-th qubit
                        broadcast_qubits.append(operand[i])
                
                # Apply the gate with this specific set of qubits
                self._apply_single_gate(gate_name, args, broadcast_qubits, node)
        else:
            # No broadcasting - flatten all qubits and apply once
            all_qubits = []
            for operand in qubit_operands:
                all_qubits.extend(operand)
            
            self._apply_single_gate(gate_name, args, all_qubits, node)
        
    def _apply_modifiers_to_range(self, start_idx: int, end_idx: int, modifier_stack: List, control_qubits: List):
        """Apply modifiers to a range of operations in the circuit."""
        # Process modifiers in reverse order (outermost first)
        for mod_type, param in reversed(modifier_stack):
            if mod_type == 'inv':
                # Apply inverse to all operations in range
                ops_to_inverse = []
                for idx in range(start_idx, end_idx):
                    ops_to_inverse.append(self.qc.data[idx])
                
                # Remove original operations
                for _ in range(end_idx - start_idx):
                    self.qc.data.pop(start_idx)
                
                # Add inversed operations in reverse order
                for gate_instruction in reversed(ops_to_inverse):
                    inv_op = gate_instruction.operation.inverse()
                    self.qc.append(inv_op, gate_instruction.qubits, gate_instruction.clbits)
                
                # Update end_idx as operations are now at same position
                end_idx = start_idx + len(ops_to_inverse)
            
            elif mod_type == 'pow':
                power = param
                
                # Get all operations in range
                ops_to_power = []
                for idx in range(start_idx, end_idx):
                    ops_to_power.append(self.qc.data[idx])
                
                # Remove original operations
                for _ in range(end_idx - start_idx):
                    self.qc.data.pop(start_idx)
                
                # Apply power modifier
                if isinstance(power, int):
                    if power > 0:
                        # Repeat operations 'power' times
                        for _ in range(power):
                            for gate_instruction in ops_to_power:
                                self.qc.append(
                                    gate_instruction.operation.copy(),
                                    gate_instruction.qubits,
                                    gate_instruction.clbits
                                )
                    elif power < 0:
                        # Apply inverse and repeat abs(power) times
                        for _ in range(abs(power)):
                            for gate_instruction in reversed(ops_to_power):
                                inv_op = gate_instruction.operation.inverse()
                                self.qc.append(inv_op, gate_instruction.qubits, gate_instruction.clbits)
                    # power == 0 means no operation (remove all)
                else:
                    # For float power, use Qiskit's power method if available
                    # Only works for single-gate operations
                    if len(ops_to_power) == 1:
                        gate_instruction = ops_to_power[0]
                        try:
                            powered_op = gate_instruction.operation.power(power)
                            self.qc.append(powered_op, gate_instruction.qubits, gate_instruction.clbits)
                        except (AttributeError, NotImplementedError):
                            raise NotImplementedError(
                                f"Fractional power not supported for gate '{gate_instruction.operation.name}'"
                            )
                    else:
                        raise ValueError(
                            "Fractional power modifier only supported for single-gate operations. "
                            f"Custom gates with multiple operations require integer powers."
                        )
                
                # Update end_idx
                end_idx = len(self.qc.data)
                
            elif mod_type in ['ctrl', 'negctrl']:
                num_controls = param
                
                # Get the control qubits for this modifier
                ctrl_qubits_for_mod = control_qubits[len(control_qubits) - num_controls:]
                control_qubits = control_qubits[:len(control_qubits) - num_controls]  # Remove used controls
                
                # Determine control state (0 for negctrl, 1 for ctrl)
                ctrl_state = '0' * num_controls if mod_type == 'negctrl' else None
                
                # Apply control to all operations in range
                ops_to_control = []
                for idx in range(start_idx, end_idx):
                    ops_to_control.append(self.qc.data[idx])
                
                # Remove original operations
                for _ in range(end_idx - start_idx):
                    self.qc.data.pop(start_idx)
                
                # Add controlled versions
                for gate_instruction in ops_to_control:
                    try:
                        ctrl_op = gate_instruction.operation.control(
                            num_ctrl_qubits=num_controls,
                            ctrl_state=ctrl_state
                        )
                        all_qubits = list(ctrl_qubits_for_mod) + list(gate_instruction.qubits)
                        self.qc.append(ctrl_op, all_qubits, gate_instruction.clbits)
                    except Exception as e:
                        raise RuntimeError(f"Failed to create controlled version of gate: {e}")
                
                # Update end_idx
                end_idx = start_idx + len(ops_to_control)
                

    def _apply_single_gate(self, gate_name, args, qubits, node):
        """
        Apply a single gate (built-in or custom) with the given parameters and qubits.
        This is extracted to support broadcasting.
        """
        # Process modifiers
        modifiers = getattr(node, "modifiers", [])
        modifier_stack = []
        
        for mod in modifiers:
            mod_name = mod.modifier.name if hasattr(mod.modifier, 'name') else mod.modifier
            
            if mod_name in ['ctrl', 'negctrl']:
                num_controls = 1
                if hasattr(mod, 'argument') and mod.argument:
                    num_controls = self._eval_rvalue(mod.argument).value
                    if not isinstance(num_controls, int) or num_controls < 1:
                        raise TypeError("Control modifier argument must be a positive integer.")
                modifier_stack.append((mod_name, num_controls))
            elif mod_name == 'inv':
                modifier_stack.append(('inv', 0))
            elif mod_name == 'pow':
                if not hasattr(mod, 'argument') or mod.argument is None:
                    raise ValueError("pow modifier requires an argument.")
                power = self._eval_rvalue(mod.argument).value
                if not isinstance(power, (int, float)):
                    raise TypeError("pow modifier argument must be numeric.")
                modifier_stack.append(('pow', power))
            else:
                raise NotImplementedError(f"Unsupported modifier: {mod_name}")
        
        # Calculate total control qubits needed
        total_controls = sum(nc for mod_type, nc in modifier_stack if mod_type in ['ctrl', 'negctrl'])
        
        if total_controls > len(qubits):
            raise ValueError(f"Not enough qubits provided for {total_controls} controls.")
        
        # Split qubits into controls and targets
        control_qubits = qubits[:total_controls]
        target_qubits = qubits[total_controls:]
        
        # Define built-in gate map
        gate_map = {
            "id": lambda q, p: self.qc.id(q[0]) if len(q) == 1 else None,
            "x": lambda q, p: self.qc.x(q[0]) if len(q) == 1 else None,
            "y": lambda q, p: self.qc.y(q[0]) if len(q) == 1 else None,
            "z": lambda q, p: self.qc.z(q[0]) if len(q) == 1 else None,
            "h": lambda q, p: self.qc.h(q[0]) if len(q) == 1 else None,
            "s": lambda q, p: self.qc.s(q[0]) if len(q) == 1 else None,
            "sdg": lambda q, p: self.qc.sdg(q[0]) if len(q) == 1 else None,
            "t": lambda q, p: self.qc.t(q[0]) if len(q) == 1 else None,
            "tdg": lambda q, p: self.qc.tdg(q[0]) if len(q) == 1 else None,
            "rx": lambda q, p: self.qc.rx(p[0], q[0]) if len(q) == 1 and len(p) == 1 else None,
            "ry": lambda q, p: self.qc.ry(p[0], q[0]) if len(q) == 1 and len(p) == 1 else None,
            "rz": lambda q, p: self.qc.rz(p[0], q[0]) if len(q) == 1 and len(p) == 1 else None,
            "sx": lambda q, p: self.qc.sx(q[0]) if len(q) == 1 else None, 
            "u": lambda q, p: self.qc.u(p[0], p[1], p[2], q[0]) if len(q) == 1 and len(p) == 3 else None,
            "cx": lambda q, p: self.qc.cx(q[0], q[1]) if len(q) == 2 else None,
            "cy": lambda q, p: self.qc.cy(q[0], q[1]) if len(q) == 2 else None,
            "cz": lambda q, p: self.qc.cz(q[0], q[1]) if len(q) == 2 else None,
            "cp": lambda q, p: self.qc.cp(p[0], q[0], q[1]) if len(q) == 2 and len(p) == 1 else None,  
            "ch": lambda q, p: self.qc.ch(q[0], q[1]) if len(q) == 2 else None,  
            "cu": lambda q, p: self.qc.cu(p[0], p[1], p[2], p[3], q[0], q[1]) if len(q) == 2 and len(p) == 4 else None,  
            "swap": lambda q, p: self.qc.swap(q[0], q[1]) if len(q) == 2 else None,
            "cswap": lambda q, p: self.qc.cswap(q[0], q[1], q[2]) if len(q) == 3 else None,
            "crx": lambda q, p: self.qc.crx(p[0], q[0], q[1]) if len(q) == 2 and len(p) == 1 else None,
            "cry": lambda q, p: self.qc.cry(p[0], q[0], q[1]) if len(q) == 2 and len(p) == 1 else None,
            "crz": lambda q, p: self.qc.crz(p[0], q[0], q[1]) if len(q) == 2 and len(p) == 1 else None,
            "ccx": lambda q, p: self.qc.ccx(q[0], q[1], q[2]) if len(q) == 3 else None,
            "ccz": lambda q, p: self.qc.ccz(q[0], q[1], q[2]) if len(q) == 3 else None,
            "p": lambda q, p: self.qc.p(p[0], q[0]) if len(q) == 1 and len(p) == 1 else None,
            "phase": lambda q, p: self.qc.p(p[0], q[0]) if len(q) == 1 and len(p) == 1 else None,
            "u1": lambda q, p: self.qc.p(p[0], q[0]) if len(q) == 1 and len(p) == 1 else None,
            "u2": lambda q, p: self.qc.u(math.pi / 2, p[0], p[1], q[0]) if len(q) == 1 and len(p) == 2 else None,
            "u3": lambda q, p: self.qc.u(p[0], p[1], p[2], q[0]) if len(q) == 1 and len(p) == 3 else None,
            "cphase": lambda q, p: self.qc.cp(p[0], q[0], q[1]) if len(q) == 2 and len(p) == 1 else None,
            "cu1": lambda q, p: self.qc.cp(p[0], q[0], q[1]) if len(q) == 2 and len(p) == 1 else None,
            "cu3": lambda q, p: self.qc.cu(p[0], p[1], p[2], 0.0, q[0], q[1]) if len(q) == 2 and len(p) == 3 else None,
            "rzz": lambda q, p: self.qc.rzz(p[0], q[0], q[1]) if len(q) == 2 and len(p) == 1 else None,
            "rxx": lambda q, p: self.qc.rxx(p[0], q[0], q[1]) if len(q) == 2 and len(p) == 1 else None,
            "ryy": lambda q, p: self.qc.ryy(p[0], q[0], q[1]) if len(q) == 2 and len(p) == 1 else None,
            "iswap": lambda q, p: self.qc.iswap(q[0], q[1]) if len(q) == 2 else None,
        }
        gate_map["U"] = gate_map["u"]
        gate_map["CX"] = gate_map["cx"]
        
        # Handle custom gates
        if gate_name in self.custom_gates:
            gate_def = self.custom_gates[gate_name]
            
            if len(args) != len(gate_def["classical_args"]):
                raise TypeError(
                    f"Gate '{gate_name}' called with {len(args)} classical arguments, "
                    f"but definition requires {len(gate_def['classical_args'])}."
                )
            
            expected_qubits = len(gate_def["qubit_args"])
            if len(target_qubits) != expected_qubits:
                raise TypeError(
                    f"Gate '{gate_name}' called with {len(target_qubits)} qubit arguments, "
                    f"but definition requires {expected_qubits}."
                )
            
            if gate_name in self.gate_call_stack:
                raise RecursionError(f"Recursive gate call detected: '{gate_name}'")
            
            self.gate_call_stack.append(gate_name)
            
            try:
                self.enter_scope('gate')
                
                # Bind classical parameters
                for param_name, param_value in zip(gate_def["classical_args"], args):
                    self.set_var('env', param_name, param_value)
                
                # Bind qubit parameters
                for qubit_param_name, qubit_obj in zip(gate_def["qubit_args"], target_qubits):
                    self.set_var('qubits', qubit_param_name, qubit_obj)
                
                # Store starting point for operations
                start_idx = len(self.qc.data)
                
                # Execute gate body
                for stmt in gate_def["body"]:
                    stmt_type = stmt.__class__.__name__
                    if stmt_type == "QuantumGate":
                        self.visit_QuantumGate(stmt)
                    elif stmt_type == "QuantumPhase":
                        phase = self._eval_rvalue(stmt.argument).value
                        self.qc.global_phase += phase
                    elif stmt_type == "AliasStatement":
                        self.visit_AliasStatement(stmt)
                    elif stmt_type == "ConstantDeclaration":
                        self.visit_ConstantDeclaration(stmt)
                    elif stmt_type == "ForInLoop":
                        self.visit_ForInLoop(stmt)
                    elif stmt_type == "BranchingStatement":
                        self.visit_BranchingStatement(stmt)
                    elif stmt_type == "QuantumBarrier":
                        self.visit_QuantumBarrier(stmt)
                    else:
                        raise NotImplementedError(f"Unsupported statement in custom gate body: {stmt_type}")
                
                # Apply modifiers to all operations added by the custom gate
                end_idx = len(self.qc.data)
                if modifier_stack and end_idx > start_idx:
                    self._apply_modifiers_to_range(start_idx, end_idx, modifier_stack, control_qubits)
                
            finally:
                self.exit_scope()
                self.gate_call_stack.pop()
        
        # Handle built-in gates
        elif gate_name in gate_map:
            result = gate_map[gate_name](target_qubits, args)
            if result is None:
                raise ValueError(
                    f"Invalid arguments for gate '{gate_name}': "
                    f"qubits={len(target_qubits)}, params={len(args)}"
                )
            
            # Apply modifiers to the just-added gate
            if modifier_stack:
                last_gate_idx = len(self.qc.data) - 1
                self._apply_modifiers_to_range(last_gate_idx, last_gate_idx + 1, modifier_stack, control_qubits)
        else:
            raise NameError(f"Gate '{gate_name}' is not defined.")
        

    def visit_QuantumGateDefinition(self, node):
        """Handle gate definitions."""
        if self.scope_types[-1] != 'global':
            raise SyntaxError("gate declarations must be global")
        
        gate_name = node.name.name.lower()
        
        # Check if redefining a builtin gate
        if gate_name in self.builtin_gates:
            raise NameError(f"Gate '{gate_name}' is already defined and cannot be redeclared.")
        
        # Check if redefining a custom gate
        if gate_name in self.custom_gates:
            raise NameError(f"Gate '{gate_name}' is already defined and cannot be redeclared.")
        
        # Store definition
        classical_args = [arg.name for arg in (node.arguments or [])]
        qubit_args = [q.name for q in node.qubits]
        
        self.custom_gates[gate_name] = {
            'classical_args': classical_args,
            'qubit_args': qubit_args,
            'body': node.body
        }
        
        # Validate the body without executing
        self.enter_scope('gate')
        try:
            # Set dummy params
            for arg in classical_args:
                self.set_var('env', arg, 0)
            for q in qubit_args:
                self.set_var('qubits', q, None)
            
            # Validate each statement
            for stmt in node.body:
                self._validate_stmt(stmt)
            
        finally:
            self.exit_scope()
        
        return None

    def visit_QuantumBarrier(self, node):
        """Handle barrier statements like: barrier r, q[0]; or barrier;"""
        qubits = []
        for target in getattr(node, "qubits", []):
            indices_info = self._visit_node(target)
            qubit_reg = self.get_var('qubits', indices_info.name)
            if indices_info.is_indexed:
                wires = [qubit_reg[idx] for idx in self._expand_indices_to_list(indices_info.value, len(qubit_reg))]
            else:
                wires = qubit_reg
            qubits.extend(wires)
        if not qubits:
            self.qc.barrier()
        else:
            self.qc.barrier(qubits)
        return None

    def visit_QuantumPhase(self, node):
        """Handle global phase statements like: gphase(π/2);"""
        phase = self._eval_rvalue(node.argument).value
        modifiers = getattr(node, "modifiers", None) or []
        if modifiers:
            phase, controls = self._gphase_modifier_plan(modifiers, phase, lambda a: self._eval_rvalue(a).value)
            qubits = []
            for qubit_node in getattr(node, "qubits", None) or []:
                info = self._visit_node(qubit_node)
                reg = self.get_var('qubits', info.name)
                if info.is_indexed:
                    qubits.extend(reg[i] for i in self._expand_indices_to_list(info.value, len(reg)))
                else:
                    qubits.extend(list(reg) if not isinstance(reg, list) else reg)
            if len(qubits) != len(controls):
                raise ValueError(f"gphase: expected {len(controls)} control qubit(s), got {len(qubits)}")
            if controls:
                flips = [q for q, v in zip(qubits, controls) if v == 0]
                for q in flips:
                    self.qc.x(q)
                if len(qubits) == 1:
                    self.qc.p(phase, qubits[0])
                else:
                    self.qc.mcp(phase, qubits[:-1], qubits[-1])
                for q in flips:
                    self.qc.x(q)
                return None
        self.qc.global_phase += phase
        return None

    @staticmethod
    def _gphase_modifier_plan(modifiers, angle, eval_arg):
        """
        Resolve modifiers on gphase. Returns (angle, control_values) where
        control_values lists 1 (ctrl) / 0 (negctrl) per control operand, in operand order.
        """
        controls = []
        for mod in modifiers:
            kind = mod.modifier.name if hasattr(mod.modifier, 'name') else str(mod.modifier)
            arg = getattr(mod, 'argument', None)
            if kind in ('ctrl', 'negctrl'):
                n = int(eval_arg(arg)) if arg is not None else 1
                controls.extend([1 if kind == 'ctrl' else 0] * n)
        for mod in reversed(modifiers):
            kind = mod.modifier.name if hasattr(mod.modifier, 'name') else str(mod.modifier)
            arg = getattr(mod, 'argument', None)
            if kind == 'inv':
                angle = -angle
            elif kind == 'pow':
                angle = angle * float(eval_arg(arg))
        return angle, controls


    def visit_AliasStatement(self, node):
        """Handle alias statements like: let alias = q;"""
        if self.in_dynamic_branch:
            raise ValueError("Alias statements not allowed in dynamic control blocks.")
        alias_name = node.target.name
        self.check_variable_declared(alias_name)
        value = self._visit_node(node.value)
        if value.type != 'quantum':
            raise TypeError("Aliases can only be created for quantum registers.")
        if value.is_indexed:
            qubit_reg = self.get_var('qubits', value.name)
            wires = [qubit_reg[idx] for idx in self._expand_indices_to_list(value.value, len(qubit_reg))]
        else:
            wires = value.value
        self.set_var('qubits', alias_name, wires)
        return None
    

    def visit_Concatenation(self, node) -> Symbol:
        """
        Handle register concatenation (++) operator.
        Two or more registers of the same type can be concatenated.
        The concatenated register is a reference to the bits/qubits of the original registers.
        A register cannot be concatenated with any part of itself.
        """
        # Recursively visit left and right sides
        lhs = self._visit_node(node.lhs)
        rhs = self._visit_node(node.rhs)
        
        # Rule: Can only concatenate quantum registers
        if lhs.type != 'quantum' or rhs.type != 'quantum':
            raise TypeError("Can only concatenate quantum registers")
        
        # Get the wire lists for left and right sides
        lhs_wires = lhs.value
        if lhs.is_indexed:
            qubit_reg = self.get_var('qubits', lhs.name)
            lhs_wires = [qubit_reg[idx] for idx in self._expand_indices_to_list(lhs.value, len(qubit_reg))]
        elif not isinstance(lhs_wires, list):
            # If it's a QuantumRegister, convert to list
            lhs_wires = list(lhs_wires)
        
        rhs_wires = rhs.value
        if rhs.is_indexed:
            qubit_reg = self.get_var('qubits', rhs.name)
            rhs_wires = [qubit_reg[idx] for idx in self._expand_indices_to_list(rhs.value, len(qubit_reg))]
        elif not isinstance(rhs_wires, list):
            # If it's a QuantumRegister, convert to list
            rhs_wires = list(rhs_wires)
        
        # Rule: Cannot concatenate a register with itself or any part of itself
        # Check if there's any overlap between the qubit objects (not their local _index)
        lhs_wire_set = set(lhs_wires)
        rhs_wire_set = set(rhs_wires)
        
        if lhs_wire_set & rhs_wire_set:
            raise ValueError("Cannot concatenate registers with overlapping qubits")
        
        # Return the concatenated list of qubits
        return Symbol(
            value=lhs_wires + rhs_wires,
            type='quantum',
            is_const=False,
            is_indexed=False
        )

    def visit_ArrayType(self, node):
        var_name = node.identifier.name
        dims = [self._eval_rvalue(dim).value for dim in node.type.dimensions]
        base_type = node.type.base_type
        method_name = 'visit_' + type(base_type).__name__
        if not hasattr(self, method_name):
            raise NotImplementedError(f"Base type {type(base_type).__name__} not supported for arrays.")
        
        # Validate angle size for AngleType
        if isinstance(base_type, openqasm3.ast.AngleType):
            size = Symbol(value=64, type='classical_value', is_const=True)
            if base_type.size:
                size = self._eval_rvalue(base_type.size)
                if not size.is_const:
                    raise TypeError(f"Size for angle in array '{var_name}' must be a compile-time constant.")
                supported_sizes = [16, 32, 64]
                if size.value not in supported_sizes:
                    raise TypeError(f"Unsupported angle size: angle[{size.value}]. Supported sizes are: {supported_sizes}")

        type_map = {
            'IntType': np.int32,
            'UintType': np.uint32,
            'FloatType': np.float64,
            'AngleType': np.float64,
            'BoolType': np.bool_,  # Added BoolType support
        }
        base_type_name = type(base_type).__name__
        if base_type_name not in type_map:
            raise TypeError(f"Unsupported array base type: {base_type_name}")
        dtype = type_map[base_type_name]
        
        # Handle size attribute for sized types (skip for BoolType)
        if hasattr(base_type, 'size') and base_type.size and base_type_name != 'BoolType':
            bit_width = self._eval_rvalue(base_type.size).value
            if base_type_name == 'IntType':
                dtype = {8: np.int8, 16: np.int16, 32: np.int32, 64: np.int64}.get(bit_width, np.int32)
            elif base_type_name == 'UintType':
                dtype = {8: np.uint8, 16: np.uint16, 32: np.uint32, 64: np.uint64}.get(bit_width, np.uint32)
            elif base_type_name == 'FloatType':
                dtype = {16: np.float16, 32: np.float32, 64: np.float64}.get(bit_width, np.float64)
            elif base_type_name == 'AngleType':
                dtype = {16: np.float16, 32: np.float32, 64: np.float64}.get(bit_width, np.float64)
        
        if node.init_expression:
            init_values = self._eval_array_initializer(node.init_expression, dims, dtype)
            array = np.array(init_values, dtype=dtype)
            if array.shape != tuple(dims):
                raise ValueError(f"Initializer for array '{var_name}' has {array.size} elements, but expected array of size {dims[0]}")
        else:
            array = np.zeros(tuple(dims), dtype=dtype)
        self.set_var('env', var_name, array)
        return None

    def _eval_array_initializer(self, node, dims, dtype):
        if isinstance(node, openqasm3.ast.ArrayLiteral):
            values = [self._eval_array_initializer(item, dims[1:], dtype) if len(dims) > 1 else
                    self._eval_rvalue(item).value for item in node.values]
            return values
        elif isinstance(node, openqasm3.ast.IndexExpression):
            result = self._eval_rvalue(node)
            if result.type == 'array':
                if isinstance(result.value, np.ndarray):
                    return result.value.tolist()
                return result.value
            return result.value
        result = self._eval_rvalue(node)
        return result.value

    def visit_ClassicalAssignment(self, node):
        """Handle classical assignments like: a = b + c; or arr[1] += 2;"""
        if self.in_dynamic_branch:
            raise ValueError("Classical assignments not allowed in dynamic control blocks.")
        # Note: Classical assignments in gates are caught by the parser, not here
        op_map = {
            "=": lambda cur, new: new,
            "+=": lambda cur, new: cur + new,
            "-=": lambda cur, new: cur - new,
            "*=": lambda cur, new: cur * new,
            "/=": lambda cur, new: cur / new,
            "%=": lambda cur, new: cur % new,
            "**=": lambda cur, new: cur ** new,
        }
        lvalue_symbol = self._visit_node(node.lvalue)
        var_name = lvalue_symbol.name
        if lvalue_symbol.is_indexed:
            if self.get_var('clbits', var_name) is not None:
                if node.op._name_ != "=":
                    raise NotImplementedError("Compound assignment is not supported for classical bit registers.")
                target_creg = self.get_var('clbits', var_name)
                bits_to_assign = self._bits_from_rvalue(node.rvalue)
                reg_size = len(target_creg)
                logical_indices = self._expand_indices_to_list(lvalue_symbol.value, reg_size)
                if len(logical_indices) != len(bits_to_assign):
                    raise ValueError(f"Number of bits to assign ({len(bits_to_assign)}) does not match number of target indices ({len(logical_indices)}).")
                for i, bit_index in enumerate(logical_indices):
                    target_creg[bit_index] = bits_to_assign[i]
                self.update_var('clbits', var_name, target_creg)
            elif self.get_var('env', var_name) is not None and isinstance(self.get_var('env', var_name), np.ndarray):
                self._handle_array_assignment(node)
            else:
                raise NameError(f"Cannot perform indexed assignment on undefined variable '{var_name}'.")
        else:
            if self.get_var('env', var_name) is None:
                raise NameError(f"Env variable '{var_name}' is not defined.")
            if self.is_const(var_name):
                raise TypeError(f"Cannot assign to constant variable '{var_name}'.")
            rvalue_symbol = self._eval_rvalue(node.rvalue)
            op_func = op_map.get(node.op._name_)
            if not op_func:
                raise NotImplementedError(f"Unsupported op: {node.op._name_}")
            if isinstance(self.get_var('env', var_name), Angle):
                var = self.get_var('env', var_name)
                float_value = op_func(var.uint_value / (2**var.size) * 2 * math.pi, rvalue_symbol.value)
                float_value = float_value % (2 * math.pi)
                if float_value < 0:
                    float_value += 2 * math.pi
                uint_value = round((float_value / (2 * math.pi)) * (2**var.size))
                self.update_var('env', var_name, Angle(uint_value=uint_value, size=var.size))
            else:
                self.update_var('env', var_name, op_func(self.get_var('env', var_name), rvalue_symbol.value))

        env_val = None
        clbits_val = None
        try:
            env_val = self.get_var('env', var_name)
        except NameError:
            pass
        if env_val is None:
            try:
                clbits_val = self.get_var('clbits', var_name)
            except NameError:
                pass
        return None

    def _depends_on_measured_bits(self, node) -> bool:
        """Check if an expression depends on any measured classical bits."""
        if node is None:
            return False
        node_type = type(node).__name__
        if node_type == 'Identifier':
            return node.name in self.measured_bits
        elif node_type == 'IndexedIdentifier':
            return node.name.name in self.measured_bits
        elif node_type == 'BinaryExpression':
            return self._depends_on_measured_bits(node.lhs) or self._depends_on_measured_bits(node.rhs)
        elif node_type == 'UnaryExpression':
            return self._depends_on_measured_bits(node.expression)
        elif node_type == 'IndexExpression':
            return self._depends_on_measured_bits(node.collection)
        return False

    

    def visit_BranchingStatement(self, node):
        if self.in_dynamic_branch:
            if self._depends_on_measured_bits(node.condition):
                raise ValueError("Nested dynamic control blocks are not allowed.")
        is_dynamic = self._depends_on_measured_bits(node.condition)
        if is_dynamic:
            old_dynamic = self.in_dynamic_branch
            self.in_dynamic_branch = True
            if_circuit = QuantumCircuit()
            for qreg in self.qc.qregs:
                if_circuit.add_register(qreg)
            for creg in self.qc.cregs:
                if_circuit.add_register(creg)
            else_circuit = None
            if node.else_block:
                else_circuit = QuantumCircuit()
                for qreg in self.qc.qregs:
                    else_circuit.add_register(qreg)
                for creg in self.qc.cregs:
                    else_circuit.add_register(creg)
            original_qc = self.qc
            self.qc = if_circuit
            self.enter_scope('block')
            for stmt in node.if_block:
                self._visit_node(stmt)
            self.exit_scope()
            if node.else_block:
                self.qc = else_circuit
                self.enter_scope('block')
                for stmt in node.else_block:
                    self._visit_node(stmt)
                self.exit_scope()
            self.qc = original_qc
            self.in_dynamic_branch = old_dynamic
            
            condition = self._build_dynamic_condition(node.condition)
            all_qubits = list(self.qc.qubits)
            all_clbits = list(self.qc.clbits)
            self.qc.if_else(
                condition=condition,
                true_body=if_circuit,
                false_body=else_circuit,
                qubits=all_qubits,
                clbits=all_clbits,
                label=None
            )
        else:
            cond_symbol = self._eval_rvalue(node.condition)
            cond = cond_symbol.value
            if cond:
                self.enter_scope('block')
                for stmt in node.if_block:
                    self._visit_node(stmt)
                self.exit_scope()
            elif node.else_block:
                self.enter_scope('block')
                for stmt in node.else_block:
                    self._visit_node(stmt)
                self.exit_scope()
        return None

    def visit_ForInLoop(self, node):
        """Handle for loops by unrolling them at compile time."""
        if self.in_dynamic_branch:
            raise ValueError("For loops not allowed in dynamic control blocks.")

        # The iterable is in node.set_declaration, not node.iterable
        iterable_sym = self._eval_rvalue(node.set_declaration)
        
        # Check if this is a compile-time evaluable iterable
        # Arrays and bit registers are stored variables but their values are known at compile time
        is_compile_time_iterable = (
            iterable_sym.is_const or 
            iterable_sym.type == 'array' or 
            (iterable_sym.type == 'classical' and isinstance(iterable_sym.value, list)) or
            (iterable_sym.type == 'classical_value' and isinstance(iterable_sym.value, list))  # For bit slices
        )
        
        if not is_compile_time_iterable:
            # Check if it's a scalar value (not iterable)
            if iterable_sym.type == 'classical_value' and not isinstance(iterable_sym.value, (list, slice)):
                raise TypeError(f"Cannot iterate over type '{iterable_sym.type}' or single scalar value.")
            raise TypeError("Iterable for for-loop must be a compile-time constant.")

        # Determine iterable values
        if isinstance(iterable_sym.value, slice):
            # Handle range (inclusive per OpenQASM spec)
            start = iterable_sym.value.start if iterable_sym.value.start is not None else 0
            end = iterable_sym.value.stop if iterable_sym.value.stop is not None else 0
            step = iterable_sym.value.step if iterable_sym.value.step is not None else 1
            if step == 0:
                raise ValueError("Range step cannot be zero.")
            if step > 0:
                iterable_values = list(range(start, end + 1, step))
            else:
                iterable_values = list(range(start, end - 1, step))
        elif iterable_sym.type == 'array':
            if iterable_sym.value.ndim > 1:
                raise TypeError("Only one-dimensional arrays can be iterated over.")
            # Convert to Python native types to avoid precision issues
            iterable_values = [float(x) if isinstance(x, (np.floating, np.float32, np.float64)) 
                            else int(x) if isinstance(x, (np.integer, np.int32, np.int64, np.uint32, np.uint64))
                            else bool(x) if isinstance(x, (np.bool_, bool))
                            else x 
                            for x in iterable_sym.value.tolist()]
        elif (iterable_sym.type == 'classical' or iterable_sym.type == 'classical_value') and isinstance(iterable_sym.value, list):
            # Bit register or bit slice (list of 0/1)
            iterable_values = iterable_sym.value
        elif isinstance(iterable_sym.value, list):
            # Discrete set or similar
            iterable_values = iterable_sym.value
        else:
            raise TypeError(f"Cannot iterate over type '{iterable_sym.type}' or single scalar value.")

        # Get loop variable type info
        loop_type = node.type
        var_name = node.identifier.name
        bit_width = None
        if hasattr(loop_type, 'size') and loop_type.size:
            size_sym = self._eval_rvalue(loop_type.size)
            if not size_sym.is_const:
                raise TypeError("Loop variable size must be compile-time constant.")
            bit_width = size_sym.value
        elif isinstance(loop_type, (openqasm3.ast.IntType, openqasm3.ast.UintType, openqasm3.ast.FloatType, openqasm3.ast.AngleType)):
            bit_width = 32  # Default for unspecified size, per OpenQASM convention
        signed = isinstance(loop_type, openqasm3.ast.IntType)

        # Unroll the loop
        for val in iterable_values:
            try:
                # Convert val to loop var type with overflow if applicable
                if isinstance(loop_type, (openqasm3.ast.IntType, openqasm3.ast.UintType)):
                    # Strict check: don't allow float->int conversion if value is actually float
                    if isinstance(val, float) and val != int(val):
                        raise ValueError(f"Cannot convert float {val} to integer type without loss")
                    converted_val = int(val)
                    if bit_width:
                        if signed:
                            converted_val = self.to_int(converted_val, bit_width)
                        else:
                            converted_val = self.to_uint(converted_val, bit_width)
                elif isinstance(loop_type, openqasm3.ast.FloatType):
                    converted_val = float(val)
                elif isinstance(loop_type, openqasm3.ast.BoolType):
                    converted_val = bool(val)
                elif isinstance(loop_type, openqasm3.ast.BitType):
                    converted_val = int(val)
                    if converted_val not in {0, 1}:
                        raise ValueError("Bit value must be 0 or 1.")
                elif isinstance(loop_type, openqasm3.ast.AngleType):
                    float_val = float(val) % (2 * math.pi)
                    if float_val < 0:
                        float_val += 2 * math.pi
                    uint_val = round((float_val / (2 * math.pi)) * (2 ** bit_width))
                    converted_val = Angle(uint_value=uint_val, size=bit_width)
                else:
                    raise NotImplementedError(f"Unsupported loop variable type: {type(loop_type).__name__}")
            except (ValueError, TypeError) as e:
                raise TypeError(f"Error converting loop variable '{var_name}' value '{val}' to type '{type(loop_type).__name__}': {str(e)}")

            # Enter new block scope for this iteration
            self.enter_scope('block')

            # Set loop variable in the new scope
            self.set_var('env', var_name, converted_val)

            # Visit body statements (use node.block, not node.body)
            for stmt in node.block:
                self._visit_node(stmt)

            # Exit scope
            self.exit_scope()


    def _get_numpy_dtype(self, node):
        """Maps an OpenQASM AST type node to a NumPy dtype."""
        if isinstance(node, (openqasm3.ast.IntType, openqasm3.ast.UintType)):
            prefix = "u" if isinstance(node, openqasm3.ast.UintType) else ""
            size = 64
            if node.size:
                size_symbol = self._eval_rvalue(node.size)
                if not size_symbol.is_const:
                    raise TypeError("Array base type size must be constant.")
                size = size_symbol.value
            supported_sizes = [8, 16, 32, 64]
            if size not in supported_sizes:
                raise TypeError(f"Unsupported integer size: {prefix}int[{size}]. Supported sizes are: {supported_sizes}")
            return np.dtype(f'{prefix}int{size}')
        elif isinstance(node, openqasm3.ast.FloatType):
            size = 64
            if node.size:
                size_symbol = self._eval_rvalue(node.size)
                if not size_symbol.is_const:
                    raise TypeError("Array base type size must be constant.")
                size = size_symbol.value
            type_map = {16: np.float16, 32: np.float32, 64: np.float64}
            if size not in type_map:
                raise TypeError(f"Unsupported float size: float[{size}]. Supported sizes are: {list(type_map.keys())}")
            return type_map[size]
        elif isinstance(node, openqasm3.ast.BoolType):
            return np.bool_
        elif isinstance(node, openqasm3.ast.BitType):
            return np.uint8
        elif isinstance(node, openqasm3.ast.AngleType):
            size = 64
            if node.size:
                size_symbol = self._eval_rvalue(node.size)
                if not size_symbol.is_const:
                    raise TypeError("Array base type size must be constant.")
                size = size_symbol.value
            type_map = {16: np.float16, 32: np.float32, 64: np.float64}
            if size not in type_map:
                raise TypeError(f"Unsupported angle size: angle[{size}]. Supported sizes are: {list(type_map.keys())}")
            return type_map[size]
        elif isinstance(node, openqasm3.ast.ComplexType):
            raise NotImplementedError("Array of 'complex' is not yet supported.")
        else:
            raise TypeError(f"Unsupported array base type: {type(node).__name__}")

    def visit_ExpressionStatement(self, node):
        if self.in_dynamic_branch:
            raise ValueError("Standalone expression statements not allowed in dynamic control blocks.")
        return self._eval_rvalue(node.expression)

    def visit_Identifier(self, node) -> Symbol:
        """Handle identifiers like variables or registers."""
        var = node.name
        if any(var in d for d in reversed(self.qubits_scopes)):
            value = self.get_var('qubits', var)
            return Symbol(name=var, value=value, type='quantum', is_const=self.is_const(var))
        if any(var in d for d in reversed(self.clbits_scopes)):
            value = self.get_var('clbits', var)
            return Symbol(name=var, value=value, type='classical', is_const=self.is_const(var))
        if any(var in d for d in reversed(self.env_scopes)):
            value = self.get_var('env', var)
            if isinstance(value, np.ndarray):
                return Symbol(name=var, value=value, type='array', is_const=self.is_const(var))
            if isinstance(value, Angle):
                return Symbol(name=var, value=value, type='angle', is_const=self.is_const(var))
            return Symbol(name=var, value=value, type='classical_value', is_const=self.is_const(var))
        if var in self.variables:
            return Symbol(name=var, value=self.variables[var]["value"], type='classical_value', is_const=True)
        raise NameError(f"Identifier '{var}' is not defined.")

    def visit_IndexedIdentifier(self, node) -> Symbol:
        """Handle indexed identifiers like q[0] or arr[1]."""
        base_symbol = self._visit_node(node.name)
        indices = []
        for index_set in node.indices:
            for item in index_set:
                index_symbol = self._visit_node(item)
                indices.append(index_symbol.value)
        index_tuple = tuple(indices)
        return Symbol(
            name=base_symbol.name,
            type=base_symbol.type,
            value=index_tuple,
            is_indexed=True
        )

    def visit_IndexExpression(self, node) -> Symbol:
        """Handle chained indexing like arr[1][0] or arr[1:2]."""
        base_symbol = self._visit_node(node.collection)
        if base_symbol.is_indexed and base_symbol.type != "array":
            raise TypeError("Multi-dimensional indexing is only supported for classical arrays.")
        new_indices = []
        index_list = node.index if isinstance(node.index, list) else [node.index]
        for index_item in index_list:
            index_symbol = self._visit_node(index_item)
            new_indices.append(index_symbol.value)
        if base_symbol.is_indexed:
            combined_indices = base_symbol.value + tuple(new_indices)
        else:
            combined_indices = tuple(new_indices)
        return Symbol(
            name=base_symbol.name,
            type=base_symbol.type,
            value=combined_indices,
            is_indexed=True
        )

    def visit_IntegerLiteral(self, node) -> Symbol:
        """Handle integer literals."""
        return Symbol(value=node.value, type='classical_value', is_const=True)

    def visit_FloatLiteral(self, node) -> Symbol:
        """Handle float literals."""
        return Symbol(value=node.value, type='classical_value', is_const=True)

    def visit_BooleanLiteral(self, node) -> Symbol:
        """Handle boolean literals."""
        return Symbol(value=node.value, type='classical_value', is_const=True)

    def visit_BitstringLiteral(self, node) -> Symbol:
        """Handle bitstring literals."""
        return Symbol(value=node.value, type='classical_value', is_const=True)

    def visit_BinaryExpression(self, node) -> Symbol:
        """Handle binary expressions like a + b."""
        lhs_result = self._eval_rvalue(node.lhs)
        rhs_result = self._eval_rvalue(node.rhs)
        result_is_const = lhs_result.is_const and rhs_result.is_const
        op_map = {
            "+": lambda a, b: a + b,
            "-": lambda a, b: a - b,
            "*": lambda a, b: a * b,
            "/": lambda a, b: a / b,
            "%": lambda a, b: a % b,
            "**": lambda a, b: a ** b,
            "<": lambda a, b: a < b,
            ">": lambda a, b: a > b,
            "<=": lambda a, b: a <= b,
            ">=": lambda a, b: a >= b,
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            "&&": lambda a, b: bool(a) and bool(b),
            "||": lambda a, b: bool(a) or bool(b),
        }
        op_func = op_map.get(node.op._name_)
        if not op_func:
            raise NotImplementedError(f"Unsupported binary operator: {node.op._name_}")
        result = op_func(lhs_result.value, rhs_result.value)
        if isinstance(lhs_result.value, Angle) or isinstance(rhs_result.value, Angle):
            result = result % (2 * math.pi)
            if result < 0:
                result += 2 * math.pi
        return Symbol(value=result, type='classical_value', is_const=result_is_const)

    def visit_UnaryExpression(self, node) -> Symbol:
        """Handle unary expressions like -x or !b."""
        operand = self._eval_rvalue(node.expression)
        op_map = {
            "+": lambda x: +x,
            "-": lambda x: -x,
            "!": lambda x: not x,
            "~": lambda x: ~x if isinstance(x, int) else NotImplementedError("Bitwise NOT only supported for integers")
        }
        op_func = op_map.get(node.op._name_)
        if not op_func:
            raise NotImplementedError(f"Unsupported unary operator: {node.op._name_}")
        result = op_func(operand.value)
        return Symbol(value=result, type='classical_value', is_const=operand.is_const)

    def visit_RangeDefinition(self, node) -> Symbol:
        """Handle range definitions like 0:2."""
        start = self._eval_rvalue(node.start).value if node.start else 0
        end = self._eval_rvalue(node.end).value if node.end else None
        step = self._eval_rvalue(node.step).value if node.step else 1
        if step == 0:
            raise ValueError("Range step cannot be zero.")
        return Symbol(value=slice(start, end, step), type='classical_value', is_const=True)

    def visit_DiscreteSet(self, node) -> Symbol:
        """Handle discrete sets like {0, 2, 5}."""
        elements = [self._eval_rvalue(item).value for item in node.values]
        return Symbol(value=elements, type='classical_value', is_const=True)

    def _eval_rvalue(self, rval) -> Symbol:
        result = self._visit_node(rval)
        if isinstance(result.value, Angle):
            angle = result.value
            float_value = (angle.uint_value / (2**angle.size)) * 2 * math.pi
            return Symbol(value=float_value, type='classical_value', is_const=result.is_const)
        if result.is_indexed:
            if result.type == 'array':
                array_var = self.get_var('env', result.name)
                indices_tuple = result.value
                if len(indices_tuple) == 1 and isinstance(indices_tuple[0], slice):
                    s = indices_tuple[0]
                    start = s.start if s.start is not None else 0
                    stop = s.stop if s.stop is not None else len(array_var) - 1
                    step = s.step if s.step is not None else 1
                    value = array_var[start:stop+1:step]
                else:
                    value = array_var[indices_tuple]
                if np.isscalar(value) or (isinstance(value, np.ndarray) and value.ndim == 0):
                    return Symbol(value=value.item() if hasattr(value, 'item') else value, type='classical_value', is_const=result.is_const)
                return Symbol(value=value, type='array', is_const=result.is_const)
            elif result.type == 'classical':
                clbit = self.get_var('clbits', result.name)
                indices = self._expand_indices_to_list(result.value, len(clbit))
                fetched = [clbit[i] for i in indices]
                if len(fetched) == 1:
                    return Symbol(value=fetched[0], type='classical_value', is_const=result.is_const)
                return Symbol(value=fetched, type='classical_value', is_const=result.is_const)
            elif result.type == 'quantum':
                raise TypeError("Cannot evaluate quantum registers in classical expressions.")
            raise TypeError(f"Unsupported indexed type: {result.type}")
        return result

    def _bits_from_rvalue(self, node) -> List[int]:
        """Evaluate an rvalue node to a list of bits."""
        if isinstance(node, openqasm3.ast.BitstringLiteral):
            binary_string = bin(node.value)[2:].zfill(node.width)
            return [int(bit) for bit in binary_string]
        rvalue_symbol = self._eval_rvalue(node)
        value = rvalue_symbol.value
        if isinstance(value, int) and value in {0, 1}:
            return [value]
        if isinstance(value, list) and all(v in {0, 1} for v in value):
            return value
        raise ValueError(f"Cannot assign value '{value}' to a bit. Value must be 0, 1, or a bitstring.")

    def _expand_indices_to_list(self, indices_tuple: tuple, reg_size: int) -> List[int]:
        flat_indices = []
        for item in indices_tuple:
            if isinstance(item, int):
                adjusted = item + reg_size if item < 0 else item
                if adjusted < 0 or adjusted >= reg_size:
                    raise IndexError(f"Index {item} out of bounds for size {reg_size}")
                flat_indices.append(adjusted)
            elif isinstance(item, slice):
                start = item.start if item.start is not None else 0
                stop = item.stop if item.stop is not None else reg_size - 1
                step = item.step if item.step is not None else 1
                if start < 0: start += reg_size
                if stop < 0: stop += reg_size
                if start < 0 or start >= reg_size or stop < 0 or stop >= reg_size:
                    raise IndexError(f"Slice {item} out of bounds for size {reg_size}")
                flat_indices.extend(range(start, stop + 1, step))
            elif isinstance(item, list):
                for i in item:
                    adjusted = i + reg_size if i < 0 else i
                    if adjusted < 0 or adjusted >= reg_size:
                        raise IndexError(f"Index {i} out of bounds for size {reg_size}")
                    flat_indices.append(adjusted)
        return flat_indices

    def _handle_array_assignment(self, node):
        """Handle array assignments like arr[1] += 2."""
        lvalue_symbol = self._visit_node(node.lvalue)
        target_array = self.get_var('env', lvalue_symbol.name)
        lvalue_index_tuple = lvalue_symbol.value
        target_dtype = target_array.dtype
        rvalue_data = self._eval_rvalue(node.rvalue).value
        is_scalar_element = all(isinstance(idx, int) for idx in lvalue_index_tuple)
        new_val = rvalue_data
        if node.op._name_ != "=":
            if not is_scalar_element:
                raise TypeError("Compound assignment is only supported for single array elements, not slices.")
            current_val = target_array[lvalue_index_tuple]
            op_map = {
                "+=": lambda c, n: c + n,
                "-=": lambda c, n: c - n,
                "*=": lambda c, n: c * n,
                "/=": lambda c, n: c / n,
                "%=": lambda c, n: c % n,
                "**=": lambda c, n: c ** n,
            }
            op_func = op_map.get(node.op._name_)
            if not op_func:
                raise NotImplementedError(f"Unsupported compound op: {node.op._name_}")
            new_val = op_func(current_val.item(), rvalue_data)
        if np.issubdtype(target_dtype, np.integer) and is_scalar_element:
            bit_width = target_dtype.itemsize * 8
            if np.issubdtype(target_dtype, np.unsignedinteger):
                new_val = self.to_uint(new_val, bit_width)
            else:
                new_val = self.to_int(new_val, bit_width)
        target_slice_shape = target_array[lvalue_index_tuple].shape
        rvalue_shape = getattr(new_val, 'shape', ())
        if target_slice_shape != rvalue_shape:
            raise TypeError(f"Shape mismatch: cannot assign shape {rvalue_shape} to slice shape {target_slice_shape}.")
        target_array[lvalue_index_tuple] = new_val

    @staticmethod
    def to_uint(value, n_bits):
        """Truncate to n-bit unsigned integer."""
        mask = (1 << n_bits) - 1
        return int(value) & mask

    @staticmethod
    def to_int(value, n_bits):
        """Convert to n-bit signed integer."""
        mask = (1 << n_bits) - 1
        truncated_value = int(value) & mask
        sign_bit = 1 << (n_bits - 1)
        if truncated_value & sign_bit:
            return truncated_value - (1 << n_bits)
        return truncated_value

    # ------------------------------------------------------------------
    # Feed-forward conditions
    # ------------------------------------------------------------------
    def _circuit_creg(self, name):
        for creg in self.qc.cregs:
            if creg.name == name:
                return creg
        raise ValueError(f"Classical register '{name}' not found in circuit")

    def _condition_operand(self, node):
        """Return ('bit', Clbit) | ('reg', ClassicalRegister) | ('const', value)."""
        node_type = type(node).__name__
        if node_type == 'Identifier' and node.name in self.measured_bits:
            return ('reg', self._circuit_creg(node.name))
        if node_type in ('IndexExpression', 'IndexedIdentifier'):
            if node_type == 'IndexExpression':
                coll = node.collection
                name = coll.name if type(coll).__name__ == 'Identifier' else None
                index = node.index
            else:
                name = node.name.name
                index = node.indices[0] if node.indices else None
            if name is not None and name in self.measured_bits:
                if isinstance(index, list):
                    if len(index) != 1:
                        raise ValueError("Only single-bit indexing is supported in measurement-dependent conditions.")
                    index = index[0]
                creg = self._circuit_creg(name)
                idx = int(self._eval_rvalue(index).value)
                if idx < 0:
                    idx += creg.size
                return ('bit', creg[idx])
        return ('const', self._eval_rvalue(node).value)

    def _build_dynamic_condition(self, node):
        """
        Translate an OpenQASM condition on measured bits into a Qiskit condition.
        Simple forms use the (bit|register, value) tuple form; anything else is
        built as a qiskit.circuit.classical.expr expression.
        """
        from qiskit.circuit.classical import expr

        def as_expr(n):
            n_type = type(n).__name__
            if n_type == 'BinaryExpression':
                op = n.op.name
                if op in ('&&', '||'):
                    l, r = to_bool(as_expr(n.lhs)), to_bool(as_expr(n.rhs))
                    return expr.logic_and(l, r) if op == '&&' else expr.logic_or(l, r)
                lhs, rhs = as_expr(n.lhs), as_expr(n.rhs)
                lhs, rhs = coerce(lhs, rhs)
                fn = {'==': expr.equal, '!=': expr.not_equal, '<': expr.less, '<=': expr.less_equal,
                      '>': expr.greater, '>=': expr.greater_equal}.get(op)
                if fn is None:
                    raise ValueError(f"Operator '{op}' is not supported in a measurement-dependent condition.")
                return fn(lhs, rhs)
            if n_type == 'UnaryExpression':
                if n.op.name == '!':
                    return expr.logic_not(to_bool(as_expr(n.expression)))
                raise ValueError(f"Operator '{n.op.name}' is not supported in a measurement-dependent condition.")
            kind, value = self._condition_operand(n)
            if kind in ('bit', 'reg'):
                return expr.lift(value)
            return value

        def is_bool_expr(e):
            return hasattr(e, 'type') and getattr(e.type, 'kind', None) is not None and type(e.type).__name__ == 'Bool'

        def coerce(a, b):
            # Compare a single measured bit against 0/1 as a boolean.
            if is_bool_expr(a) and isinstance(b, (int, bool, np.integer)):
                return a, bool(b)
            if is_bool_expr(b) and isinstance(a, (int, bool, np.integer)):
                return bool(a), b
            if isinstance(a, (int, np.integer)) and not isinstance(a, bool):
                a = int(a)
            if isinstance(b, (int, np.integer)) and not isinstance(b, bool):
                b = int(b)
            return a, b

        def to_bool(e):
            if isinstance(e, (bool, int, np.integer)):
                return expr.lift(bool(e))
            if is_bool_expr(e):
                return e
            return expr.not_equal(e, 0)

        # Fast paths: `bit == v`, `reg == v`, bare `bit`.
        n_type = type(node).__name__
        if n_type == 'BinaryExpression' and node.op.name == '==':
            lk, lv = self._condition_operand(node.lhs)
            rk, rv = self._condition_operand(node.rhs)
            if lk in ('bit', 'reg') and rk == 'const':
                return (lv, bool(rv) if lk == 'bit' else int(rv))
            if rk in ('bit', 'reg') and lk == 'const':
                return (rv, bool(lv) if rk == 'bit' else int(lv))
        if n_type in ('IndexExpression', 'IndexedIdentifier', 'Identifier'):
            kind, value = self._condition_operand(node)
            if kind == 'bit':
                return (value, True)
            if kind == 'reg':
                return expr.not_equal(expr.lift(value), 0)

        return to_bool(as_expr(node))

    def visit_IODeclaration(self, node):
        """`output` annotations are ignored; `input` values cannot be supplied, so refuse
        to simulate rather than silently using 0."""
        io_kind = str(getattr(node, 'io_identifier', '')).lower()
        if 'output' in io_kind:
            return None
        ident = getattr(node, 'identifier', None)
        name = getattr(ident, 'name', ident)
        raise ValueError(
            f"Input parameter '{name}' has no value. QCanvas simulations cannot bind "
            f"external inputs; give it a concrete value in your code (for example "
            f"theta = 0.5) or call the circuit with numbers before simulating."
        )

    def finalize(self):
        """Return the constructed QuantumCircuit."""
        return self.qc

    def output_spec(self):
        """
        Output layout (see qsim.backends.base.BaseBackend): all declared classical
        bits in declaration order, or all qubits when nothing was measured.
        """
        return {
            "measured": bool(self.measured_bits),
            "qubits": list(self.qc.qubits),
            "clbits": list(self.qc.clbits),
        }
