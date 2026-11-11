from qsim.visitors.base_visitor import BaseVisitor
import openqasm3
import pennylane as qml
import math
import numpy as np
from dataclasses import dataclass
from typing import Any, List
import operator
from pennylane.measurements import MeasurementValue
import os
from qsim.qasm_parser.parser import parse_openqasm3

@dataclass
class Symbol:
    """A structure to hold the result of resolving an identifier or expression."""
    value: Any
    type: str           # e.g., 'quantum', 'classical', 'classical_value', 'array'
    is_const: bool = False
    name: str = None  # Optional, for variables
    is_indexed: bool = False
    

@dataclass
class Angle:
    """Represents an angle as a fixed-point unsigned integer."""
    uint_value: int
    size: int


@dataclass
class GateDefinition:
    """Stores the definition of a custom quantum gate."""
    name: str
    classical_args: List[str]
    qubit_args: List[str]
    body: List[Any] # Stores the list of AST nodes in the gate's body


gate_map = {
    "id": lambda wires, params=None: qml.Identity(wires=wires),
    "x": lambda wires, params=None: qml.PauliX(wires=wires),
    "y": lambda wires, params=None: qml.PauliY(wires=wires),
    "z": lambda wires, params=None: qml.PauliZ(wires=wires),
    "h": lambda wires, params=None: qml.Hadamard(wires=wires),
    "s": lambda wires, params=None: qml.S(wires=wires),
    "p": lambda wires, params: qml.PhaseShift(params[0], wires=wires),
    "sx": lambda wires, params=None: qml.SX(wires=wires),
    "ch": lambda wires, params=None: qml.CH(wires=wires),
    "cp": lambda wires, params: qml.CPhase(params[0], wires=wires),
    "crx": lambda wires, params: qml.CRX(params[0], wires=wires),
    "cry": lambda wires, params: qml.CRY(params[0], wires=wires),
    "crz": lambda wires, params: qml.CRZ(params[0], wires=wires),
    "ccx": lambda wires, params=None: qml.Toffoli(wires=wires),
    "sdg": lambda wires, params=None: qml.adjoint(qml.S)(wires=wires),
    "t": lambda wires, params=None: qml.T(wires=wires),
    "tdg": lambda wires, params=None: qml.adjoint(qml.T)(wires=wires),
    "rx": lambda wires, params: qml.RX(params[0], wires=wires[0]),
    "ry": lambda wires, params: qml.RY(params[0], wires=wires[0]),
    "rz": lambda wires, params: qml.RZ(params[0], wires=wires[0]),
    "u": lambda wires, params: qml.U3(*params, wires=wires[0]),
    "cx": lambda wires, params=None: qml.CNOT(wires=wires),
    "cy": lambda wires, params=None: qml.CY(wires=wires),
    "cz": lambda wires, params=None: qml.CZ(wires=wires),
    "swap": lambda wires, params=None: qml.SWAP(wires=wires),
    "cswap": lambda wires, params=None: qml.CSWAP(wires=wires),
    "iswap": lambda wires, params=None: qml.ISWAP(wires=wires),
    "sqrtiswap": lambda wires, params=None: qml.SISWAP(wires=wires),
    "U": lambda wires, params: qml.U3(*params, wires=wires[0]),
    "u3": lambda wires, params: qml.U3(*params, wires=wires[0]),
    "u2": lambda wires, params: qml.U3(math.pi / 2, params[0], params[1], wires=wires[0]),
    "u1": lambda wires, params: qml.PhaseShift(params[0], wires=wires),
    "phase": lambda wires, params: qml.PhaseShift(params[0], wires=wires),
    "CX": lambda wires, params=None: qml.CNOT(wires=wires),
    "cphase": lambda wires, params: qml.CPhase(params[0], wires=wires),
    "cu1": lambda wires, params: qml.CPhase(params[0], wires=wires),
    "ccz": lambda wires, params=None: qml.CCZ(wires=wires),
    "cu": lambda wires, params: qml.ctrl(
        qml.QubitUnitary(np.exp(1j * params[3]) * _u_matrix(params[0], params[1], params[2]), wires=wires[1]),
        control=wires[0]),
    "cu3": lambda wires, params: qml.ctrl(
        qml.QubitUnitary(_u_matrix(params[0], params[1], params[2]), wires=wires[1]),
        control=wires[0]),
    "rzz": lambda wires, params: qml.IsingZZ(params[0], wires=wires),
    "rxx": lambda wires, params: qml.IsingXX(params[0], wires=wires),
    "ryy": lambda wires, params: qml.IsingYY(params[0], wires=wires),
}


def _u_matrix(theta, phi, lam):
    """Exact OpenQASM 3 U(theta, phi, lambda) matrix."""
    c, sn = math.cos(theta / 2), math.sin(theta / 2)
    return np.array([
        [c, -np.exp(1j * lam) * sn],
        [np.exp(1j * phi) * sn, np.exp(1j * (phi + lam)) * c],
    ], dtype=complex)


class PennylaneVisitor(BaseVisitor):
    
    
    
    def __init__(self):
        self.total_qubits = 0
        self.env_scopes = [{}]
        self.qubits_scopes = [{}]
        self.clbits_scopes = [{}]
        self.consts_scopes = [set()]
        self.scope_types = ['global']
        self.in_dynamic_branch = False
        self.queue_actions = []
        self.visited_files = set()
        self.current_directory_stack = []
        self.custom_gates = {}

        self.gate_definition_context_stack = []
        self._mcm_counter = 0


    def visit(self, module):
        """
        Main entry point for visiting an AST module. It sets up the
        initial directory context for handling includes.
        """
        # Reset state for a new top-level call.
        # The base path for includes will be the script's current working directory.
        self.visited_files.clear()
        self.current_directory_stack = [os.getcwd()]
        
        # Call the original visit logic from the base class
        super().visit(module)
        
        
    def get_var(self, category: str, var_name: str):
        """
        Gets a variable's value from the narrowest-most scope it is defined in.
        Enforces strict visibility rules when inside a gate's scope.
        """
        scopes = getattr(self, f"{category}_scopes")
        is_in_gate_scope = self.scope_types[-1] == 'gate'

        if is_in_gate_scope:
            # Rule: Inside a gate, check local scope first (for params/aliases)
            if var_name in scopes[-1]:
                return scopes[-1][var_name]
            
            # Then, check ONLY the global scope (scopes[0])
            if var_name in scopes[0]:
                # And if it's in the global scope, it MUST be a constant.
                global_consts = self.consts_scopes[0]
                if var_name in global_consts:
                    return scopes[0][var_name]
                else:
                    # It exists globally but is not const, so access is forbidden.
                    raise NameError(f"Gate cannot access non-constant global variable '{var_name}'.")
            return None # Not found in local or valid global scope
        else:
            # Original logic for non-gate scopes (if, for, global)
            for d in reversed(scopes):
                if var_name in d:
                    return d[var_name]
            return None


    def set_var(self, category: str, var_name: str, value: Any):
        scopes = getattr(self, f"{category}_scopes")
        scopes[-1][var_name] = value


    def update_var(self, category: str, var_name: str, value: Any):
        scopes = getattr(self, f"{category}_scopes")
        for d in reversed(scopes):
            if var_name in d:
                d[var_name] = value
                return
        raise NameError(f"{category.capitalize()} variable '{var_name}' not defined.")


    def enter_scope(self, scope_type: str):
        self.env_scopes.append({})
        self.qubits_scopes.append({})
        self.clbits_scopes.append({})
        self.consts_scopes.append(set())
        self.scope_types.append(scope_type)


    def exit_scope(self):
        self.env_scopes.pop()
        self.qubits_scopes.pop()
        self.clbits_scopes.pop()
        self.consts_scopes.pop()
        self.scope_types.pop()


    def is_const(self, var_name):
        for s in reversed(self.consts_scopes):
            if var_name in s:
                return True
        return False


    def add_const(self, var_name):
        self.consts_scopes[-1].add(var_name)
        

    def check_variable_declared(self, var_name):
        if (var_name in self.env_scopes[-1] or
            var_name in self.qubits_scopes[-1] or
            var_name in self.clbits_scopes[-1]):
            raise NameError(f"Variable '{var_name}' is already declared in this scope.") 
        return False 


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

    def visit_QubitDeclaration(self, node):
        """
        Visits a qubit declaration, ensuring its size is a const expression.
        """
        if self.scope_types[-1] != 'global':
            raise SyntaxError("Qubit declarations are only allowed in the global scope.")

        name = node.qubit.name
        self.check_variable_declared(name)
        # The size MUST be a compile-time constant
        size = Symbol(value=None, type='classical_value', is_const=True)
        
        if node.size:
            size = self._eval_rvalue(node.size)
            if not size.is_const:
                raise TypeError(f"Qubit register '{name}' size must be a compile-time constant.")
            
            if not isinstance(size.value, int) or size.value < 0:
                raise ValueError("Register size must be a non-negative integer.")
        else:
            size.value = 1  # Default size if not specified
        total_qubits = self.total_qubits
        self.set_var('qubits', name, list(range(total_qubits, total_qubits + size.value)))
        self.total_qubits += size.value


    def visit_ConstantDeclaration(self, node):
        """
        Handles the declaration of a compile-time constant.
        """
        if self.in_dynamic_branch:
            raise ValueError("Constant declarations not allowed in dynamic control blocks.")
        
        var_name = node.identifier.name
        self.check_variable_declared(var_name)

        # Rule: A const must be initialized (the parser enforces this, but we check again)
        if node.init_expression is None:
            raise ValueError(f"Constant variable '{var_name}' must be initialized.")

        # Evaluate the initializer expression
        eval_result: Symbol = self._eval_rvalue(node.init_expression)

        # Rule: The initializer for a const MUST be a compile-time constant itself.
        if not eval_result.is_const:
            raise TypeError(f"Initializer for constant variable '{var_name}' must be a compile-time constant.")

        # If all rules pass, store the variable and mark it as a constant.
        self.set_var('env', var_name, eval_result.value)
        self.add_const(var_name)


    def visit_ClassicalDeclaration(self, node):
        """
        Dynamically dispatches to the correct visitor method based on the
        specific classical type (e.g., IntType, FloatType).
        """
        if self.scope_types[-1] == 'gate':
            raise SyntaxError("Classical declarations are not allowed inside a gate definition.")
        
        if self.in_dynamic_branch:
            raise ValueError("Classical declarations not allowed in dynamic control blocks.")
        
        self.check_variable_declared(node.identifier.name)
        
        # Construct the method name, e.g., 'visit_IntType'
        method_name = 'visit_' + type(node.type).__name__
        
        if hasattr(self, method_name):
            # Get the method from the class instance
            visitor_method = getattr(self, method_name)
            visitor_method(node)
        else:
            classical_type = type(node.type).__name__
            raise NotImplementedError(f"Visitor for classical type '{classical_type}' not implemented.")


    def visit_AliasStatement(self, node):
        """
        Handles 'let' statements, which are now only for qubit aliases.
        """
        if self.in_dynamic_branch:
            raise ValueError("Alias statements not allowed in dynamic control blocks.")
        
        alias_name = node.target.name
        self.check_variable_declared(alias_name)
        
        value = self._visit_node(node.value)  ## can be identifier, indexed identifier, or concatenation 
        if value.type != 'quantum':
            raise TypeError("Aliases can only be created for quantum registers.")
        
        if value.is_indexed:
            qubit_ = self.get_var('qubits', value.name)
            reg_size = len(qubit_)
            wires = [qubit_[idx] for idx in self._expand_indices_to_list(value.value, reg_size)]
        else:
            wires = value.value        
        
        
        self.set_var('qubits', alias_name, wires)  # value is a list of qubit indices
        

    def visit_Identifier(self, node) -> Symbol:
        var = node.name
        const_map = {"pi": math.pi, "euler": math.e, "tau": 2 * math.pi}
        
        if any(var in d for d in reversed(self.qubits_scopes)):
            for d in reversed(self.qubits_scopes):
                if var in d:
                    value = self.get_var('qubits', var)
                    break
            return Symbol(name=var, value=value, type='quantum', is_const=self.is_const(var))
        if any(var in d for d in reversed(self.clbits_scopes)):
            for d in reversed(self.clbits_scopes):
                if var in d:
                    value = self.get_var('clbits', var)
                    break
            return Symbol(name=var, value=value, type='classical', is_const=self.is_const(var))
        
        if var in const_map:
            return Symbol(name=var, value=const_map[var], type='classical_value', is_const=True)
        
        if any(var in d for d in reversed(self.env_scopes)):
            for d in reversed(self.env_scopes):
                if var in d:
                    value = self.get_var('env', var)
                    break
            if isinstance(value, np.ndarray):
                return Symbol(name=var, value=value, type='array', is_const=self.is_const(var))
            else:
                return Symbol(name=var, value=value, type='classical_value', is_const=self.is_const(var))
        raise NameError(f"Identifier '{var}' is not defined.")


    def visit_BitType(self, node):
        """
        Handles bit declarations, using the _bits_from_rvalue helper for initialization.
        """
        name = node.identifier.name
        size = Symbol(value=None, type='classical_value', is_const=True)
         
        if node.type.size:
            size = self._eval_rvalue(node.type.size)
            if not size.is_const:
                raise TypeError(f"Size for bit register '{name}' must be a compile-time constant.")
        else:
            size.value = 1

        # Use the helper to handle initialization
        if node.init_expression:
            initial_bits = self._bits_from_rvalue(node.init_expression)
            
            # We still need to validate that the initializer size matches the declaration
            if len(initial_bits) != size.value:
                raise TypeError(
                    f"Initializer size ({len(initial_bits)}) does not match "
                    f"declared bit register size ({size.value}) for '{name}'."
                )
                
            self.set_var('clbits', name, initial_bits)
        else:
            # If there's no initializer, default to all zeros
            self.set_var('clbits', name, [0] * size.value)            
    
    
    def visit_BoolType(self, node):
        """Handles bool declarations."""
        var_name = node.identifier.name
        
        initial_value = Symbol(value=False, type='classical_value', is_const=True)
        if node.init_expression:
            initial_value: Symbol = self._eval_rvalue(node.init_expression)

        self.set_var('env', var_name, bool(initial_value.value))


    def visit_IntType(self, node):
        """Handles int[n] declarations."""
        var_name = node.identifier.name
        bit_width = Symbol(value=64, type='classical_value', is_const=True)
        
        if node.type.size:
            bit_width = self._eval_rvalue(node.type.size)
            if not bit_width.is_const:
                raise TypeError(f"Size for float '{var_name}' must be a compile-time constant.")  
                
        initial_value = Symbol(value=0, type='classical_value', is_const=True)
        if node.init_expression:
            initial_value = self._eval_rvalue(node.init_expression)
        
        self.set_var('env', var_name, self.to_int(initial_value.value, bit_width.value))


    def visit_UintType(self, node):
        """Handles uint[n] declarations."""
        var_name = node.identifier.name
        bit_width = Symbol(value=64, type='classical_value', is_const=True)
        
        if node.type.size:
            bit_width = self._eval_rvalue(node.type.size)
            if not bit_width.is_const:
                raise TypeError(f"Size for float '{var_name}' must be a compile-time constant.")
                
        initial_value = Symbol(value=0, type='classical_value', is_const=True)
        if node.init_expression:
            initial_value = self._eval_rvalue(node.init_expression)
            
        self.set_var('env', var_name, self.to_uint(initial_value.value, bit_width.value))


    def visit_FloatType(self, node):
        """Handles float[n] declarations with strict size checking."""
        var_name = node.identifier.name
        bit_width = Symbol(value=64, type='classical_value', is_const=True)
        
        if node.type.size:
            bit_width = self._eval_rvalue(node.type.size)
            if not bit_width.is_const:
                raise TypeError(f"Size for float '{var_name}' must be a compile-time constant.")
            
        supported_widths = [16, 32, 64]
        if bit_width.value not in supported_widths:
            raise TypeError(
                f"Unsupported float size: float[{bit_width.value}]. "
                f"Supported sizes are: {supported_widths}"
            )
        
        type_map = {16: np.float16, 32: np.float32, 64: float}
        float_type = type_map[bit_width.value]
        
        initial_value = Symbol(value=0.0, type='classical_value', is_const=True)
        if node.init_expression:
            initial_value = self._eval_rvalue(node.init_expression)
            
        self.set_var('env', var_name, float_type(initial_value.value))


    def visit_ArrayType(self, node):
        """
        Handles array declarations, including initialization from a nested ArrayLiteral,
        Identifier, IndexedIdentifier, or IndexExpression.
        """
        if self.scope_types[-1] != 'global':
            raise SyntaxError("Array declarations are only allowed in the global scope.")

        var_name = node.identifier.name

        base_type_node = node.type.base_type
        numpy_dtype = self._get_numpy_dtype(base_type_node)

        dims = []
        for dim_expr in node.type.dimensions:
            dim_symbol = self._eval_rvalue(dim_expr)
            if not dim_symbol.is_const:
                raise TypeError(f"Array dimensions for '{var_name}' must be constant.")
            dims.append(dim_symbol.value)
        
        if len(dims) > 7:
            raise ValueError(f"Array '{var_name}' exceeds the 7-dimension limit.")

        expected_size = np.prod(dims)
        expected_shape = tuple(dims)

        if node.init_expression:
            # Evaluate the initialization expression
            init_result = self._visit_node(node.init_expression)

            if isinstance(node.init_expression, openqasm3.ast.ArrayLiteral):
                # Case 1: Initialization from ArrayLiteral
                initial_values = init_result  # Flat list from visit_ArrayLiteral
                if len(initial_values) != expected_size:
                    raise ValueError(
                        f"Initializer for array '{var_name}' has {len(initial_values)} elements, "
                        f"but expected shape {expected_shape} requires {expected_size}."
                    )
                # Create and reshape the array
                initial_array = np.array(initial_values, dtype=numpy_dtype)
                self.set_var('env', var_name, initial_array.reshape(expected_shape))

            elif isinstance(node.init_expression, (openqasm3.ast.Identifier, openqasm3.ast.IndexedIdentifier, openqasm3.ast.IndexExpression)):
                # Case 2: Initialization from another array (Identifier or indexed array)
                if init_result.type != 'array':
                    raise TypeError(f"Initializer for array '{var_name}' must be an array, got type '{init_result.type}'.")
                
                # Fetch the array data
                if init_result.is_indexed:
                    # For IndexedIdentifier or IndexExpression, init_result.value is a tuple of indices
                    initial_array = self.get_var("env", init_result.name)[init_result.value]
                else:
                    # For Identifier, init_result.value is the NumPy array
                    initial_array = init_result.value

                # Validate shape
                if initial_array.shape != expected_shape:
                    raise ValueError(
                        f"Initializer array for '{var_name}' has shape {initial_array.shape}, "
                        f"but expected shape is {expected_shape}."
                    )
                
                # Convert to target dtype if necessary
                if initial_array.dtype != numpy_dtype:
                    try:
                        initial_array = initial_array.astype(numpy_dtype)
                    except (ValueError, TypeError) as e:
                        raise TypeError(
                            f"Cannot convert initializer array of type {initial_array.dtype} to {numpy_dtype} for '{var_name}'."
                        ) from e
                
                self.set_var('env', var_name, initial_array )

            else:
                raise TypeError(f"Unsupported initializer type for array '{var_name}': {type(node.init_expression).__name__}")

        else:
            # If no initializer, create a zero-filled array
            self.set_var('env', var_name, np.zeros(shape=expected_shape, dtype=numpy_dtype))


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

    def visit_AngleType(self, node):
        """Handles angle[size] declarations by creating an Angle object."""
        var_name = node.identifier.name
        
        # Default size and validation
        size = 64
        if node.type.size:
            size_symbol = self._eval_rvalue(node.type.size)
            if not size_symbol.is_const:
                raise TypeError(f"Size for angle '{var_name}' must be a compile-time constant.")
            size = size_symbol.value
            supported_sizes = [16, 32, 64]
            if size not in supported_sizes:
                raise TypeError(f"Unsupported angle size: angle[{size}]. Supported sizes are: {supported_sizes}")

        uint_value = 0
        if node.init_expression:
            float_value_radians = self._eval_rvalue(node.init_expression).value
            # Ensure float_value_radians is within [0, 2π) for normalization
            float_value_radians = float_value_radians % (2 * math.pi)
            if float_value_radians < 0:
                float_value_radians += 2 * math.pi
            uint_value = round((float_value_radians / (2 * math.pi)) * (2**size))

        self.set_var('env', var_name, Angle(uint_value=uint_value, size=size))


    @staticmethod
    def to_uint(value, n_bits):
        """Truncates a value to n-bit unsigned integer representation."""
        if value < 0:
            raise ValueError("Cannot convert negative value to unsigned integer.")
        
        mask = (1 << n_bits) - 1
        return value & mask


    @staticmethod
    def to_int(value, n_bits):
        """Converts a value to n-bit signed integer representation."""
        mask = (1 << n_bits) - 1
        truncated_value = value & mask
        sign_bit = 1 << (n_bits - 1)
        if truncated_value & sign_bit:
            return truncated_value - (1 << n_bits)
        else:
            return truncated_value
    
    
    def check_float(self, value, bit_width):
        """Checks if a float value can be represented in the specified precision without loss."""
        if not isinstance(value, float):
            raise TypeError(f"Expected float, got {type(value).__name__}")
        type_map = {16: np.float16, 32: np.float32, 64: float}
        f_type = type_map[bit_width]
        casted = f_type(value)
        if float(casted) != value:
            raise ValueError(f"Value {value} loses precision when cast to float[{bit_width}]")
        return casted


    def check_bool(self, value):
        if not isinstance(value, bool):
            raise TypeError(f"Expected bool, got {type(value).__name__}")
        return value


    def check_bit(self, value):
        if isinstance(value, int) and value in {0, 1}:
            return value
        raise TypeError(f"Expected bit (0 or 1), got {type(value).__name__} with value {value}")
    
    
    def visit_QuantumMeasurementStatement(self, node):
        """
        General measurement visitor that handles broadcasting, single indices,
        and slices.
        """
        if self.scope_types[-1] == 'gate':
            raise SyntaxError("Measurements are not allowed inside a gate definition.")
        
        if self.in_dynamic_branch:
            raise ValueError("Only quantum functions that contain no measurements can be applied conditionally.")
        # Use the helper to resolve the wires to be measured
        # return a symbol or IndexedAccess
        classical_indices = self._visit_node(node.target)
        
        wires = self._resolve_qubit_operand(node.measure.qubit)

        clbit = self.get_var('clbits', classical_indices.name)
        if classical_indices.is_indexed is False:
            # give list of all indices
            classical_indices.value = list(range(len(clbit)))
        else:
            classical_indices.value = self._expand_indices_to_list(classical_indices.value, len(clbit))
        
        # According to the spec, the number of qubits and bits must match
        if len(wires) != len(classical_indices.value):
            raise ValueError("Number of qubits to measure does not match number of classical bits.")

        # Create a measurement for each qubit and assign to the corresponding bit
        for wire, c_idx in zip(wires, classical_indices.value):
        
            # Create and record the measurement operation
            self._mcm_counter += 1
            meas_mp = qml.measurements.MidMeasureMP(wires=wire, reset=False, id=f"mcm{self._mcm_counter}_w{wire}")
            meas = MeasurementValue([meas_mp], processing_fn=lambda x: x)
            # Capture meas_mp by value in this lambda
            self.queue_actions.append(lambda mp=meas_mp: qml.apply(mp))
    
            # Store the measurement result placeholder in the correct classical bit
            clbit[c_idx] = meas
        self.set_var('clbits', classical_indices.name, clbit)


    def visit_QuantumReset(self, node):
        """
        Visits a Reset node and adds the corresponding state-preparation
        operations to reset the target qubits to the |0> state.
        """
        if self.scope_types[-1] == 'gate':
            raise SyntaxError("Reset instructions are not allowed inside a gate definition.")
        
        if self.scope_types[-1] == 'gate':
            raise SyntaxError("Classical declarations are not allowed inside a gate definition.")
        
        wires = self._resolve_qubit_operand(node.qubits)        
        ket_zero = [1, 0]
        
        for wire in wires:
            self._mcm_counter += 1
            reset_mp = qml.measurements.MidMeasureMP(wires=wire, reset=True, id=f"reset{self._mcm_counter}_w{wire}")
            self.queue_actions.append(lambda p=reset_mp: qml.apply(p))


    def visit_QuantumBarrier(self, node):
        """
        Visits a QuantumBarrier node, which prevents gate reordering across it.
        Maps to the qml.Barrier operation.
        """
        # Barriers are compiler directives and should not be in dynamic blocks.
        if self.in_dynamic_branch:
            raise ValueError("Barrier instructions are not allowed in dynamic control blocks.")

        all_wires = []
        # Check if specific qubits/registers are provided
        if node.qubits:
            # Iterate through all gate operands (q, r[1], etc.)
            for qubit_node in node.qubits:
                wires = self._resolve_qubit_operand(qubit_node)
                all_wires.extend(wires)
        else:
            # If no qubits are specified, it's a global barrier on all qubits
            all_wires = list(range(self.total_qubits))

        # Create the PennyLane Barrier operation
        # We use list(set(all_wires)) to remove any duplicate wires
        op = qml.Barrier(wires=list(set(all_wires)))
        
        # Queue the operation to be added to the tape
        self.queue_actions.append(lambda op=op: qml.apply(op))


    def visit_QuantumGateDefinition(self, node):
        """
        Parses a 'gate' definition and stores its signature and body
        in the custom_gates registry.
        """
        if self.scope_types[-1] != 'global':
            raise SyntaxError("Gate definitions are only allowed in the global scope.")
        
        gate_name = node.name.name
        if gate_name in self.custom_gates or gate_name in gate_map:
            raise NameError(f"Gate '{gate_name}' is already defined.")

        # Extract the names of the classical and qubit parameters
        classical_arg_names = [arg.name for arg in node.arguments]
        qubit_arg_names = [q.name for q in node.qubits]

        # Store the definition
        definition = GateDefinition(
            name=gate_name,
            classical_args=classical_arg_names,
            qubit_args=qubit_arg_names,
            body=node.body
        )
        self.custom_gates[gate_name] = definition
        
        original_actions = self.queue_actions
        self.queue_actions = []  # Use a temporary, isolated queue.

        self.enter_scope('gate')

        # Populate the temporary scope with placeholder parameters
        for param_name in classical_arg_names:
            # The value doesn't matter, only that the name exists.
            self.set_var('env', param_name, 0.0)
        for idx, param_name in enumerate(qubit_arg_names):
            # We use a dummy wire index like [dummy] to signify a valid qubit argument.
            self.set_var('qubits', param_name, [idx])

        # Visit the body to trigger static validation checks. Any generated
        # operations will go into the temporary queue and be discarded.
        for stmt in definition.body:
            self._visit_node(stmt)

        # Clean up and restore the original state
        self.exit_scope()
        # Restore the original action queue, discarding the temporary one from the dry run.
        self.queue_actions = original_actions


    def visit_QuantumGateModifier(self, node):
        """
        Returns a function that applies the given modifier to
        a list of qml.Operation objects.
        """
        mod_name = node.modifier.name

        if mod_name == 'inv':
            def apply_inv(ops, control_wires=None): # control_wires is ignored
                return [qml.adjoint(op) for op in reversed(ops)]
            return apply_inv

        elif mod_name == 'pow':
            power = self._eval_rvalue(node.argument).value
            if not isinstance(power, (int, float)):
                raise TypeError("pow() modifier requires a numeric argument.")

            def apply_pow(ops, control_wires=None): # control_wires is ignored
                if len(ops) == 1:
                    return [qml.pow(ops[0], z=power)]
                if not isinstance(power, int) or power < 1:
                    raise ValueError("pow() with multiple-operator custom gates only supports positive integer powers.")
                return ops * int(power)
            return apply_pow

        elif mod_name in ['ctrl', 'negctrl']:
            # Determine how many controls this modifier needs (e.g., 2 for 'ctrl(2)')
            num_controls = self._eval_rvalue(node.argument).value if node.argument else 1
            if not isinstance(num_controls, int) or num_controls < 1:
                raise TypeError("Control modifier argument must be a positive integer.")

            # Determine if control is on 0 (negctrl) or 1 (ctrl)
            control_values = [0] * num_controls if mod_name == 'negctrl' else None # PennyLane defaults to 1

            def apply_ctrl(ops, control_wires):
                # This function receives the specific wires it needs to use
                if len(control_wires) != num_controls:
                    raise ValueError(
                        f"Modifier '{mod_name}({num_controls})' expected {num_controls} control wires, "
                        f"but received {len(control_wires)}."
                    )
                # Wrap each operation in the list with the control logic
                return [qml.ctrl(op, control=control_wires, control_values=control_values) for op in ops]
            
            return apply_ctrl

        else:
            raise NameError(f"Unknown gate modifier: '{mod_name}'.")


    def visit_QuantumGate(self, node):
        """
        Visits a QuantumGate node and creates the corresponding PennyLane operation.
        """
        gate_name = node.name.name
        
        params = []
        for arg in node.arguments:
            param_symbol = self._eval_rvalue(arg)
            if isinstance(param_symbol.value, Angle):
                angle = param_symbol.value
                params.append((angle.uint_value / (2**angle.size)) * 2 * math.pi)
            else:
                params.append(param_symbol.value)

        # Resolve operand_wires per position
        operand_wires = []
        for qubit_node in node.qubits:
            wires = self._resolve_qubit_operand(qubit_node)
            operand_wires.append(wires)

        # Detect broadcast size N
        sizes = [len(ow) for ow in operand_wires]
        non_single_sizes = [s for s in sizes if s > 1]
        if non_single_sizes:
            N = non_single_sizes[0]
            if any(s != N for s in non_single_sizes):
                raise ValueError(f"Broadcast sizes mismatch: not all multi-qubit arguments have size {N}.")
            broadcast = True
        else:
            N = 1
            broadcast = False

        # Calculate wire splits for all modifiers
        modifiers = node.modifiers if hasattr(node, 'modifiers') else []
        num_control_qubits = 0
        control_configs = []  # Stores num_qubits for each ctrl modifier
        if modifiers:
            for mod_node in modifiers:
                if mod_node.modifier.name in ['ctrl', 'negctrl']:
                    num_qubits = self._eval_rvalue(mod_node.argument).value if mod_node.argument else 1
                    num_control_qubits += num_qubits
                    control_configs.append(num_qubits)

        # Wrapper for processing one gate instance (avoids full duplication)
        def process_gate_instance(all_wires, target_wires, control_wires, configs=None):
            # If no configs passed, use the class-level one (for N=1 compatibility)
            if configs is None:
                configs = control_configs[::-1]  # Reverse for pop order
            
            # Check for enough qubits per instance
            if num_control_qubits > len(all_wires):
                raise ValueError(f"Not enough qubits provided for {num_control_qubits} controls.")
            
            # for custom gates ---
            if gate_name in self.custom_gates:
                if gate_name in self.gate_definition_context_stack:
                    raise RecursionError(f"Recursive gate call detected: '{gate_name}' cannot call itself.")
                self.gate_definition_context_stack.append(gate_name)

                definition = self.custom_gates[gate_name]

                if len(target_wires) != len(definition.qubit_args):
                    raise TypeError(
                        f"Gate '{gate_name}' called with {len(target_wires)} qubit arguments, "
                        f"but definition requires {len(definition.qubit_args)}."
                    )
                if len(params) != len(definition.classical_args):
                    raise TypeError(
                        f"Gate '{gate_name}' called with {len(params)} classical arguments, "
                        f"but definition requires {len(definition.classical_args)}."
                    )
                
                # Map classical arguments (using the already resolved params)
                param_map = dict(zip(definition.classical_args, params))
                qubit_map = {name: [wire] for name, wire in zip(definition.qubit_args, target_wires)}
                
                self.enter_scope('gate')
                for name, val in param_map.items():
                    self.set_var('env', name, val)
                for name, wires_list in qubit_map.items():
                    self.set_var('qubits', name, wires_list)
                
                queue_snapshot = self.queue_actions
                self.queue_actions = []  # Isolate the gate's operations
                
                # Visit the statements in the gate's body
                with qml.tape.QuantumTape() as gate_tape:
                    for stmt in definition.body:
                        self._visit_node(stmt)

                # --- Extract recorded operations
                gate_operations = list(gate_tape.operations)
                
                flattened_ops = []
                for op in gate_operations:
                    if isinstance(op, qml.tape.QuantumTape):
                        flattened_ops.extend(op.operations)
                    else:
                        flattened_ops.append(op)

                gate_operations = flattened_ops
                self.queue_actions = queue_snapshot  # Restore the previous queue
                
                self.exit_scope()

                # Apply modifiers with the correct control wires
                current_control_idx = 0
                for modifier_node in reversed(modifiers):
                    modifier_fn = self.visit_QuantumGateModifier(modifier_node)
                    
                    mod_control_wires = []
                    if modifier_node.modifier.name in ['ctrl', 'negctrl']:
                        num_wires = self._eval_rvalue(modifier_node.argument).value if modifier_node.argument else 1
                        end = len(control_wires) - current_control_idx
                        mod_control_wires = control_wires[end - num_wires : end]
                        current_control_idx += num_wires
                    
                    # Pass the control wires to the modifier function
                    gate_operations = modifier_fn(gate_operations, mod_control_wires)

                for op in gate_operations:
                    self.queue_actions.append(lambda op=op: qml.apply(op))
                
                self.gate_definition_context_stack.pop()
                return
            
            # --- for built-in gates ---
            if gate_name not in gate_map:
                raise NameError(f"Gate '{gate_name}' is not defined.")
            op_func = gate_map[gate_name]

            # Create base 'op' using only target_wires
            op = op_func(wires=target_wires, params=params)
            
            # Apply modifiers with the correct control wires
            current_control_idx = 0
            for modifier_node in reversed(modifiers):
                wrapper = self.visit_QuantumGateModifier(modifier_node)
                
                mod_control_wires = []
                if modifier_node.modifier.name in ['ctrl', 'negctrl']:
                    num_wires = self._eval_rvalue(modifier_node.argument).value if modifier_node.argument else 1
                    end = len(control_wires) - current_control_idx
                    mod_control_wires = control_wires[end - num_wires : end]
                    current_control_idx += num_wires
                
                # Pass the control wires to the wrapper function
                op = wrapper([op], mod_control_wires)[0]

            self.queue_actions.append(lambda op=op: qml.apply(op))

        # Handle broadcast or single
        if not broadcast:
            # Single instance (N=1)
            all_wires = []
            for ow in operand_wires:
                all_wires.extend(ow)
            control_wires = all_wires[:num_control_qubits]
            target_wires = all_wires[num_control_qubits:]
            process_gate_instance(all_wires, target_wires, control_wires)  # Uses default configs
        else:
            # Broadcast loop
            configs_base = control_configs[::-1]  # Reverse once outside loop
            for i in range(N):
                this_all_wires = [
                    operand_wires[pos][i] if len(operand_wires[pos]) > 1 else operand_wires[pos][0]
                    for pos in range(len(operand_wires))
                ]
                this_control_wires = this_all_wires[:num_control_qubits]
                this_target_wires = this_all_wires[num_control_qubits:]
                this_configs = configs_base.copy()  # Fresh copy per instance
                process_gate_instance(this_all_wires, this_target_wires, this_control_wires, this_configs)
            

    def visit_QuantumPhase(self, node):
        """Handle global phase (gphase) nodes separately."""
        phase = self._eval_rvalue(node.argument)

        # Track global phase accumulation
        if not hasattr(self, "global_phase"):
            self.global_phase = 0.0
        self.global_phase += phase.value

        modifiers = getattr(node, "modifiers", None) or []
        angle = phase.value
        if modifiers:
            angle, controls = self._gphase_modifier_plan(modifiers, angle, lambda a: self._eval_rvalue(a).value)
            wires = []
            for qubit_node in getattr(node, "qubits", None) or []:
                wires.extend(self._resolve_qubit_operand(qubit_node))
            if len(wires) != len(controls):
                raise ValueError(f"gphase: expected {len(controls)} control qubit(s), got {len(wires)}")
            if controls:
                base = qml.PhaseShift(angle, wires=wires[-1])
                if len(wires) == 1:
                    op = base if controls[0] == 1 else None
                    if op is None:
                        flip = [qml.PauliX(wires=wires[0]), base, qml.PauliX(wires=wires[0])]
                        for o in flip:
                            self.queue_actions.append(lambda op=o: qml.apply(op))
                        return
                else:
                    flips = [w for w, v in zip(wires[-1:], controls[-1:]) if v == 0]
                    for w in flips:
                        self.queue_actions.append(lambda w=w: qml.apply(qml.PauliX(wires=w)))
                    op = qml.ctrl(base, control=wires[:-1], control_values=controls[:-1])
                    self.queue_actions.append(lambda op=op: qml.apply(op))
                    for w in flips:
                        self.queue_actions.append(lambda w=w: qml.apply(qml.PauliX(wires=w)))
                    return
                self.queue_actions.append(lambda op=op: qml.apply(op))
                return
        phase_op = qml.GlobalPhase(angle)
        self.queue_actions.append(lambda op=phase_op: qml.apply(op))


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


    def visit_ClassicalAssignment(self, node):
        """
        Handles classical assignments, including assignments to angle variables.
        """
        if self.scope_types[-1] == 'gate':
            raise SyntaxError("Classical assignments are not allowed inside a gate definition.")
        
        if self.in_dynamic_branch:
            raise ValueError("Constant declarations not allowed in dynamic control blocks.")
        
        op_map = {
            "+=": lambda cur, new: cur + new, "-=": lambda cur, new: cur - new,
            "*=": lambda cur, new: cur * new, "/=": lambda cur, new: cur / new,
            "%=": lambda cur, new: cur % new, "**=": lambda cur, new: cur ** new,
            "=": lambda cur, new: new,
        }

        lvalue_symbol = self._visit_node(node.lvalue)
        var_name = lvalue_symbol.name

        # Case 1: Assignment to a simple scalar variable or angle
        if not lvalue_symbol.is_indexed:

            if self.get_var('env', var_name) is None: # Just to check if it exists
                raise NameError(f"Env variable '{var_name}' is not defined.")


            if self.is_const(var_name):
                raise TypeError(f"Cannot assign to constant variable '{var_name}'.")

            rvalue_symbol = self._eval_rvalue(node.rvalue)
            op_func = op_map.get(node.op._name_)
            if not op_func:
                raise NotImplementedError(f"Unsupported op: {node.op._name_}")

            # Handle angle assignments
            if isinstance(self.get_var('env', var_name), Angle):
                var:Angle = self.get_var('env', var_name)
                float_value = op_func(var.uint_value / (2**var.size) * 2 * math.pi, rvalue_symbol.value)
                float_value = float_value % (2 * math.pi)  # Normalize to [0, 2π)
                if float_value < 0:
                    float_value += 2 * math.pi
                uint_value = round((float_value / (2 * math.pi)) * (2**var.size))
                self.update_var('env', var_name, Angle(uint_value=uint_value, size=var.size))
            else:
                self.update_var('env', var_name, op_func(self.get_var('env', var_name), rvalue_symbol.value))
                
        # Case 2: Classical bit register assignment
        elif self.get_var('clbits', var_name) is not None:
            if node.op._name_ != "=":
                raise NotImplementedError("Compound assignment is not supported for classical bit registers.")
            target_creg = self.get_var('clbits', var_name)
            bits_to_assign = self._bits_from_rvalue(node.rvalue)
            reg_size = len(target_creg)
            logical_indices = self._expand_indices_to_list(lvalue_symbol.value, reg_size)
            if len(logical_indices) != len(bits_to_assign):
                raise ValueError(
                    f"Number of bits to assign ({len(bits_to_assign)}) does not match "
                    f"number of target indices ({len(logical_indices)})."
                )
            for i, bit_index in enumerate(logical_indices):
                target_creg[bit_index] = bits_to_assign[i]
            self.update_var('clbits', var_name, target_creg)
            
        # Case 3: Array element assignment
        elif self.get_var('env', var_name) is not None and isinstance(self.get_var('env', var_name), np.ndarray):
            self._handle_array_assignment(node)
        else:
            raise NameError(f"Cannot perform indexed assignment on undefined variable '{var_name}'.")


    def visit_IntegerLiteral(self, node) -> Symbol:
        # The parser already converts hex/octal/binary and removes underscores
        return Symbol(value=node.value, type='classical_value', is_const=True)


    def visit_FloatLiteral(self, node) -> Symbol:
        # The parser handles scientific notation and different decimal formats
        return Symbol(value=node.value, type='classical_value', is_const=True)


    def visit_BooleanLiteral(self, node) -> Symbol:
        # The parser provides a Python bool directly
        return Symbol(value=node.value, type='classical_value', is_const=True)


    def visit_BitstringLiteral(self, node) -> Symbol:
        """
        Handles bitstring literals. The parser provides the integer value directly.
        """
        return Symbol(value=node.value, type='classical_value', is_const=True)
    
    
    def visit_ArrayLiteral(self, node):
        """
        Recursively processes an ArrayLiteral node from the AST and
        returns a flattened list of the evaluated initial values.
        
        This handles nested structures like {{1.1, 1.2}, {2.1, 2.2}}.
        """
        flat_values = []
        # The 'values' attribute of the node is a list of other nodes.
        for item in node.values:
            # We visit each item. The result will be either a list (from a
            # nested ArrayLiteral) or a Symbol (from a FloatLiteral, etc.).
            result = self._visit_node(item)
            
            # If the result is a list, it means we've processed a nested array.
            if isinstance(result, list):
                flat_values.extend(result)
            # Otherwise, it's a Symbol from a literal, so we extract its value.
            else:
                flat_values.append(result.value)
                
        return flat_values
    
    
    def visit_ExpressionStatement(self, node) -> Symbol:
        """
        Handles an ExpressionStatement, e.g., 
            3 * 6
            0 + (3 * 6)
        Returns the evaluated value.
        """
        if self.in_dynamic_branch:
            raise ValueError("Standalone expression statements not allowed in dynamic control blocks.")
        return self._visit_node(node.expression)
    

    def visit_UnaryExpression(self, node) -> Symbol:
        """
        Handles unary operations:
        - Arithmetic negation: -
        - Logical NOT: !
        Recursively evaluates the operand.
        """
        operand = self._eval_rvalue(node.expression)
        op_name = node.op._name_
        is_measurement = isinstance(operand.value, MeasurementValue)
        if is_measurement:
            if op_name == "~":
                result = ~operand.value
            elif op_name == "!":
                result = ~operand.value  # Treat ! as ~ for measurements
            elif op_name in ["+", "-"]:
                op_dict = {"+": operator.pos, "-": operator.neg}
                result = op_dict[op_name](operand.value)
            else:
                raise NotImplementedError(f"Unsupported unary operator '{op_name}' for measurement values.")
            return Symbol(value=result, type='classical_value', is_const=False)
        else:
            # Existing classical unary handling...
            op_func = {
                "+": operator.pos, "-": operator.neg, "!": operator.not_
            }.get(op_name)
            
            if not op_func:
                raise NotImplementedError(f"Unsupported unary operator: {op_name}")
            result_value = op_func(operand.value)
            return Symbol(value=result_value, type='classical_value', is_const=operand.is_const)
    
  
    @staticmethod
    def _register_as_integer(value):
        if not isinstance(value, list) or len(value) < 2:
            return value
        if not all(isinstance(b, (MeasurementValue, int, bool, np.integer)) for b in value):
            return value
        constant = 0
        dynamic = None
        for i, bit in enumerate(value):
            if isinstance(bit, MeasurementValue):
                term = bit * (2 ** i)
                dynamic = term if dynamic is None else dynamic + term
            else:
                constant += int(bit) * (2 ** i)
        if dynamic is None:
            return constant
        return dynamic + constant if constant else dynamic

    def visit_BinaryExpression(self, node):
        """
        Handles binary operations, including those involving Angle objects.
        """
        lhs_result = self._eval_rvalue(node.lhs)
        rhs_result = self._eval_rvalue(node.rhs)
        # Result is const only if both operands are
        result_is_const = lhs_result.is_const and rhs_result.is_const

        # Convert Angle objects to radians for computation
        lhs_value = lhs_result.value
        rhs_value = rhs_result.value

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

        if isinstance(lhs_value, list) and len(lhs_value) == 1:
            lhs_value = lhs_value[0]
        if isinstance(rhs_value, list) and len(rhs_value) == 1:
            rhs_value = rhs_value[0]
        # A multi-bit register used as a number (e.g. `if (c == 3)`) is the unsigned
        # integer sum(c[i] * 2**i); comparing the Python list itself was always False.
        lhs_value = self._register_as_integer(lhs_value)
        rhs_value = self._register_as_integer(rhs_value)

        is_measurement = isinstance(lhs_value, MeasurementValue) or isinstance(rhs_value, MeasurementValue)

        if is_measurement:
            op_name = node.op._name_
            op_dict = {
                "+": operator.add, "-": operator.sub, "*": operator.mul, "/": operator.truediv,
                "<": operator.lt, ">": operator.gt, "<=": operator.le, ">=": operator.ge,
                "==": operator.eq, "!=": operator.ne
            }
            if op_name in op_dict:
                try:
                    result = op_dict[op_name](lhs_value, rhs_value)
                except Exception as e:
                    raise RuntimeError(f"Error applying operator '{op_name}' to measurement values: {e}") from e
            elif op_name == "&&":
                try:
                    result = lhs_value & rhs_value
                except Exception as e:
                    raise RuntimeError(f"Error applying operator '{op_name}' to measurement values: {e}") from e
            elif op_name == "||":
                try:
                    result = lhs_value | rhs_value
                except Exception as e:
                    raise RuntimeError(f"Error applying operator '{op_name}' to measurement values: {e}") from e
            elif op_name in ["%", "**"]:
                raise NotImplementedError(f"Operator '{op_name}' not supported for measurement values.")
            else:
                raise NotImplementedError(f"Unsupported operator '{op_name}' for measurement values.")
            result_is_const = False  # Measurements are not const
            
        else:
            op_func = op_map.get(node.op._name_)
            if not op_func:
                raise NotImplementedError(f"Unsupported binary operator: {node.op._name_}")
            result = op_func(lhs_value, rhs_value)
        
        if not is_measurement and (isinstance(lhs_value, Angle) or isinstance(rhs_value, Angle)):
            result = result % (2 * math.pi)
            if result < 0:
                result += 2 * math.pi

        return Symbol(value=result, type='classical_value', is_const=result_is_const if not is_measurement else False)
   
        
    def visit_RangeDefinition(self, node) -> Symbol:
        """
        Visits a RangeDefinition node (e.g., -2: or 0:2) and returns a Python slice object.
        """
        # Evaluate start, end, and step expressions
        start_sym = self._eval_rvalue(node.start) if node.start is not None else Symbol(value=None, type='classical_value', is_const=True)
        end_sym = self._eval_rvalue(node.end) if node.end is not None else Symbol(value=None, type='classical_value', is_const=True)
        step_sym = self._eval_rvalue(node.step) if node.step is not None else Symbol(value=None, type='classical_value', is_const=True)

        start = start_sym.value if start_sym.value is not None else 0
        end = end_sym.value
        step = step_sym.value if step_sym.value is not None else 1

        # Validate step
        if step == 0:
            raise ValueError("Range step cannot be zero.")

        # Handle negative indices and None for end later in _expand_indices_to_list
        # OpenQASM ranges are INCLUSIVE, so adjust end by +1 if not None
        if end is not None:
            end += 1 if step > 0 else -1

        is_const = start_sym.is_const and end_sym.is_const and step_sym.is_const

        return Symbol(
            value=slice(start, end, step),
            type='classical_value',
            is_const=is_const
        )


    def visit_DiscreteSet(self, node) -> Symbol:
        """
        Visits a DiscreteSet node (e.g., {0, 2, 5}) and returns a list of values.
        """
        is_const = True
        elements = []
        for item in node.values:
            item_result = self._eval_rvalue(item)
            is_const = is_const and item_result.is_const
            elements.append(item_result.value)
        
        return Symbol(value=elements, type='classical_value', is_const=is_const)


    def visit_Concatenation(self, node) -> Symbol:
        """
        Resolves a concatenation of two registers by recursively visiting them.
        """
        # The context set by the caller is preserved for these recursive calls.
        lhs = self._visit_node(node.lhs)
        rhs = self._visit_node(node.rhs)

        if lhs.type != 'quantum' or rhs.type != 'quantum':
            raise TypeError("Can only concatenate quantum registers")
        
        lhs_wires = lhs.value
        if lhs.is_indexed:
            qubit_ = self.get_var('qubits', lhs.name)
            lhs_wires = [qubit_[idx] for idx in self._expand_indices_to_list(lhs.value, len(qubit_))]
        
        rhs_wires = rhs.value
        if rhs.is_indexed:  
            qubit_ = self.get_var('qubits', lhs.name)
            rhs_wires = [qubit_[idx] for idx in self._expand_indices_to_list(rhs.value, len(qubit_))]

        if set(lhs_wires) & set(rhs_wires):
            raise ValueError("Cannot concatenate a register with itself or its aliases.")
        
        return Symbol(value=lhs_wires + rhs_wires, type='quantum', is_const=False, is_indexed=False)


    def visit_IndexedIdentifier(self, node) -> Symbol:
        """
        Parses an indexed identifier and creates a tuple of index objects.
        This is simplified because visit_RangeDefinition now returns a slice.
        """
        base_symbol = self._visit_node(node.name)
        if self.scope_types[-1] == 'gate' and base_symbol.name in self.qubits_scopes[-1]:
            raise SyntaxError(
                f"Cannot index qubit parameter '{base_symbol.name}' within its own gate definition."
            )
        
        indices_for_numpy = []
        index_items = [item for index_set in node.indices for item in index_set]

        for item in index_items:
            index_symbol = self._visit_node(item)
            # This now works for ints, lists, AND slices directly!
            indices_for_numpy.append(index_symbol.value)
        
        index_tuple = tuple(indices_for_numpy)

        return Symbol(
            name=base_symbol.name,
            type=base_symbol.type,
            value=index_tuple,
            is_indexed=True
        )

    
    def visit_IndexExpression(self, node) -> Symbol:
        """
        Handles chained indexing by concatenating index tuples.
        This is simplified because visit_RangeDefinition now returns a slice.
        """
        base_symbol: Symbol = self._visit_node(node.collection)

        if self.scope_types[-1] == 'gate' and base_symbol.name in self.qubits_scopes[-1]:
            raise SyntaxError(
                f"Cannot index qubit parameter '{base_symbol.name}' within its own gate definition."
            )
            
        if base_symbol.is_indexed and base_symbol.type != "array":
            raise TypeError("Multi-dimensional indexing is only supported for classical arrays.")
        
        new_indices = []
        index_list = node.index if isinstance(node.index, list) else [node.index]

        for index_item in index_list:
            index_symbol = self._visit_node(index_item)
            # This also works universally now.
            new_indices.append(index_symbol.value)

        if base_symbol.is_indexed:
            # If the base is already indexed i.e., result of this function (recursive call)
            combined_indices = base_symbol.value + tuple(new_indices)
        else:
            combined_indices = tuple(new_indices)

        return Symbol(
            name=base_symbol.name,
            type=base_symbol.type,
            value=combined_indices,
            is_indexed=True
        )
    
    
    def visit_BranchingStatement(self, node):
        if self.in_dynamic_branch:
            raise ValueError("Nested dynamic control blocks are not allowed.")
        
        cond_symbol = self._eval_rvalue(node.condition)
        cond = cond_symbol.value
        is_dynamic = isinstance(cond, MeasurementValue)

        if is_dynamic:
            old_dynamic = self.in_dynamic_branch
            self.in_dynamic_branch = True

            if_actions = []
            old_actions = self.queue_actions
            self.queue_actions = if_actions
            self.enter_scope('block')
            for stmt in node.if_block:
                self._visit_node(stmt)
            self.exit_scope()
            self.queue_actions = old_actions

            else_actions = []
            self.queue_actions = else_actions
            if node.else_block:
                self.enter_scope('block')
                for stmt in node.else_block:
                    self._visit_node(stmt)
                self.exit_scope()
            self.queue_actions = old_actions
            self.in_dynamic_branch = old_dynamic

            def if_fn():
                for action in if_actions:
                    action()

            def else_fn():
                for action in else_actions:
                    action()
            cond_callable = qml.cond(cond, if_fn, else_fn if node.else_block else None)
            self.queue_actions.append(lambda op=cond_callable: op())
        else:
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
    
    
    def visit_ForInLoop(self, node):
        if self.in_dynamic_branch:
            raise ValueError("For loops not allowed in dynamic control blocks.")

        self.enter_scope('for')

        iter_sym = self._visit_node(node.set_declaration)

        values = self._resolve_iterable(iter_sym)

        to_convert, category, set_value = self._resolve_iterator(node)

        var_name = node.identifier.name
        self.check_variable_declared(var_name)
        # Do not add_const: loop var is reassigned per iteration

        for val in values:
            try:
                converted_val = to_convert(val)
            except Exception as e:
                raise TypeError(f"Error converting loop variable '{var_name}' value '{val}': {e}") from e
            self.set_var(category, var_name, set_value(converted_val))
            for stmt in node.block:
                self._visit_node(stmt)

        self.exit_scope()


    def _resolve_iterable(self, iter_sym: Symbol) -> List[Any]:
       
        if isinstance(iter_sym.value, slice):
            start = iter_sym.value.start if iter_sym.value.start is not None else 0
            stop = iter_sym.value.stop
            if stop is None:
                raise ValueError("Infinite ranges not supported in for loops.")
            step = iter_sym.value.step if iter_sym.value.step is not None else 1
            if step == 0:
                raise ValueError("Step cannot be zero.")
            return list(range(start, stop, step))
        elif isinstance(iter_sym.value, list):
            return iter_sym.value
        elif iter_sym.type == 'array':
            if iter_sym.is_indexed:
                array_data = self.get_var('env', iter_sym.name)[iter_sym.value]
            else:
                array_data = iter_sym.value
            if array_data.ndim != 1:
                raise TypeError("Only one-dimensional arrays can be iterated over.")
            if not np.issubdtype(array_data.dtype, np.number) and array_data.dtype != np.bool_:
                raise TypeError("Only scalar arrays (numeric or bool) can be iterated over.")
            return array_data.tolist()
        elif iter_sym.type == 'classical':
            if iter_sym.is_indexed:
                clbit = self.get_var('clbits', iter_sym.name)
                indices = self._expand_indices_to_list(iter_sym.value, len(clbit))
                return [clbit[i] for i in indices]
            else:
                return iter_sym.value
        else:
            raise TypeError(f"Cannot iterate over type '{iter_sym.type}' or single scalar value.")


    def _resolve_iterator(self, node):
        to_convert = lambda v: v
        category = 'env'
        set_value = lambda v: v
        if node.type:
            if isinstance(node.type, openqasm3.ast.IntType):
                bit_width = self._eval_rvalue(node.type.size).value if node.type.size else 64
                to_convert = lambda v: self.to_int(v, bit_width)
            elif isinstance(node.type, openqasm3.ast.UintType):
                bit_width = self._eval_rvalue(node.type.size).value if node.type.size else 64
                to_convert = lambda v: self.to_uint(v, bit_width)
            elif isinstance(node.type, openqasm3.ast.FloatType):
                bit_width = self._eval_rvalue(node.type.size).value if node.type.size else 64
                if bit_width not in {16, 32, 64}:
                    raise TypeError(f"Unsupported float size: {bit_width}")
                to_convert = lambda v: self.check_float(v, bit_width)
            elif isinstance(node.type, openqasm3.ast.BoolType):
                to_convert = lambda v: self.check_bool(v)
            elif isinstance(node.type, openqasm3.ast.BitType):
                size_sym = self._eval_rvalue(node.type.size) if node.type.size else Symbol(value=1, type='classical_value', is_const=True)
                if size_sym.value != 1:
                    raise NotImplementedError("Sized bits >1 as loop variables not supported.")
                category = 'clbits'
                set_value = lambda v: [v]
                to_convert = lambda v: self.check_bit(v)
            elif isinstance(node.type, openqasm3.ast.AngleType):
                size_sym = self._eval_rvalue(node.type.size) if node.type.size else Symbol(value=64, type='classical_value', is_const=True)
                to_convert = lambda v: Angle(uint_value=round((float(v) % (2 * math.pi) / (2 * math.pi)) * (2 ** size_sym.value)), size=size_sym.value)
            else:
                raise NotImplementedError(f"Unsupported loop variable type: {type(node.type).__name__}")
        return to_convert, category, set_value


    def _eval_rvalue(self, rval) -> Symbol:
        """
        Evaluates any RHS value recursively, including Angle objects.
        """
        result = self._visit_node(rval)

        if isinstance(result.value, Angle):
            # Convert Angle back to radians
            angle = result.value
            float_value = (angle.uint_value / (2**angle.size)) * 2 * math.pi
            return Symbol(value=float_value, type='classical_value', is_const=result.is_const)

        if result.is_indexed:
            if result.type == 'array':
                  # Just to check if it exists
                fetched = self.get_var('env', result.name)[result.value]
                if np.isscalar(fetched) or (isinstance(fetched, np.ndarray) and fetched.ndim == 0):
                    return Symbol(value=fetched.item(), type='classical_value', is_const=result.is_const)
                else:
                    raise NotImplementedError("Use of array slices in expressions is not yet supported.")
            elif result.type == 'classical':
                clbit = self.get_var('clbits', result.name)  # Just to check if it exists
                indices = self._expand_indices_to_list(result.value, len(clbit))
                fetched = [clbit[i] for i in indices]
                if len(fetched) == 1:
                    return Symbol(value=fetched[0], type='classical_value', is_const=result.is_const)
                else:
                    raise NotImplementedError("Use of bit register slices in expressions is not yet supported.")
            elif result.type == 'quantum':
                raise TypeError("Cannot evaluate quantum registers in classical expressions.")
            else:
                raise TypeError(f"Unsupported indexed type: {result.type}")

        return result


    def _bits_from_rvalue(self, node) -> List[int]:
            """
            Evaluates an rvalue node and returns a list of bits (0s or 1s).
            Handles BitstringLiterals, as well as any other expression that
            evaluates to a valid bit (0 or 1).
            """
            # Case 1: A bitstring literal like "101" is handled directly.
            if isinstance(node, openqasm3.ast.BitstringLiteral):
                int_value = node.value
                width = node.width
                binary_string = bin(int_value)[2:].zfill(width)
                return [int(bit) for bit in binary_string]
            
            # Case 2: For ANY other expression (IntegerLiteral, Identifier, IndexExpression),
            # we first evaluate it to get its final value.
            rvalue_symbol = self._eval_rvalue(node)
            value = rvalue_symbol.value

            # After evaluation, the resulting value must be a single bit.
            if isinstance(value, int) and value in {0, 1}:
                return [value]
            else:
                raise ValueError(
                    f"Cannot assign value '{value}' (type: {type(value).__name__}) to a bit. "
                    "Value must be 0, 1, or a bitstring."
                )


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


    def _expand_indices_to_list(self, indices_tuple: tuple, reg_size: int) -> List[int]:
        """
        Converts an index symbol's value (a tuple of slices, ints, lists)
        into a single flat list of integer indices. This is used for qubits
        and classical bit registers, but NOT for NumPy arrays.
        """
        flat_indices = []
        for item in indices_tuple:
            if isinstance(item, int):
                adjusted = item + reg_size if item < 0 else item
                if adjusted < 0 or adjusted >= reg_size:
                    raise IndexError(f"Index {item} out of bounds for size {reg_size}")
                flat_indices.append(adjusted)
            elif isinstance(item, slice):
                start = item.start if item.start is not None else 0
                stop = item.stop if item.stop is not None else reg_size
                step = item.step if item.step is not None else 1
                if start < 0: start += reg_size
                if stop <= 0: stop += reg_size
                if start < 0 or start > reg_size or stop < 0 or stop > reg_size:
                    raise IndexError(f"Slice {item} out of bounds for size {reg_size}")
                flat_indices.extend(range(start, stop, step))
            elif isinstance(item, list):
                for i in item:
                    adjusted = i + reg_size if i < 0 else i
                    if adjusted < 0 or adjusted >= reg_size:
                        raise IndexError(f"Index {i} out of bounds for size {reg_size}")
                    flat_indices.append(adjusted)
        return flat_indices


    def _handle_array_assignment(self, node):
            """
            Handles array assignments by calculating the result first and then
            applying overflow/underflow wrapping before the final assignment.
            """
            # 1. Resolve lvalue (no changes here)
            lvalue_symbol = self._visit_node(node.lvalue)
            target_array = self.get_var('env', lvalue_symbol.name)
            lvalue_index_tuple = lvalue_symbol.value
            target_dtype = target_array.dtype

            # 2. Resolve rvalue (no changes here)
            rvalue_node = node.rvalue
            rvalue_data = None
            if isinstance(rvalue_node, openqasm3.ast.Identifier):
                rvalue_data = self.get_var('env', rvalue_node.name)
            elif isinstance(rvalue_node, (openqasm3.ast.IndexedIdentifier, openqasm3.ast.IndexExpression)):
                rvalue_sym = self._visit_node(rvalue_node)
                rvalue_data = self.get_var('env', rvalue_sym.name)[rvalue_sym.value]
            else:
                rvalue_data = self._eval_rvalue(rvalue_node).value

            # 3. Calculate the new value using Python's arbitrary-precision integers
            is_scalar_element = all(isinstance(idx, int) for idx in lvalue_index_tuple)
            new_val = rvalue_data
            if node.op._name_ != "=":
                if not is_scalar_element:
                    raise TypeError("Compound assignment is only supported for single array elements, not slices.")
                
                current_val = target_array[lvalue_index_tuple]
                op_map = {
                    "+=": lambda c, n: c + n, "-=": lambda c, n: c - n,
                    "*=": lambda c, n: c * n, "/=": lambda c, n: c / n,
                    "%=": lambda c, n: c % n, "**=": lambda c, n: c ** n,
                }
                op_func = op_map.get(node.op._name_)
                if not op_func:
                    raise NotImplementedError(f"Unsupported compound op: {node.op._name_}")
                new_val = op_func(current_val.item(), rvalue_data) # Use .item() to get Python number

            # 4. If the target is a bounded integer type, wrap the calculated value (if scalar)
            if np.issubdtype(target_dtype, np.integer) and is_scalar_element:
                bit_width = target_dtype.itemsize * 8
                if np.issubdtype(target_dtype, np.unsignedinteger):
                    new_val = self.to_uint(new_val, bit_width)
                else: # Signed integer
                    new_val = self.to_int(new_val, bit_width)

            # 5. Perform shape validation (no changes here)
            target_slice_shape = target_array[lvalue_index_tuple].shape
            rvalue_shape = getattr(new_val, 'shape', ())
            if target_slice_shape != rvalue_shape:
                raise TypeError(f"Shape mismatch: cannot assign shape {rvalue_shape} to slice shape {target_slice_shape}.")

            # 6. Final assignment (now safe)
            target_array[lvalue_index_tuple] = new_val


    def _resolve_qubit_operand(self, qubit_node) -> List[int]:
        """Helper to resolve any qubit operand (Identifier, IndexedIdentifier) to a list of wires."""
        indices_info: Symbol = self._visit_node(qubit_node)
        qubit_register = self.get_var('qubits', indices_info.name)
        if indices_info.is_indexed:
            return [qubit_register[idx] for idx in self._expand_indices_to_list(indices_info.value, len(qubit_register))]
        else:
            return indices_info.value
    
    
    def output_spec(self):
        """
        Output layout (see qsim.backends.base.BaseBackend): every declared classical
        bit in declaration order (each a MeasurementValue or a constant 0/1), or all
        qubits when nothing was measured.
        """
        clbits = []
        measured = False
        for name, bits in self.clbits_scopes[0].items():
            values = bits if isinstance(bits, (list, tuple)) else [bits]
            for b in values:
                if isinstance(b, MeasurementValue):
                    measured = True
                    clbits.append(b)
                else:
                    try:
                        clbits.append(int(b) & 1)
                    except (TypeError, ValueError):
                        clbits.append(0)
        return {
            "measured": measured,
            "qubits": list(range(self.total_qubits)),
            "clbits": clbits,
        }

    def finalize(self):
        with qml.tape.QuantumTape() as tape:
            for action in self.queue_actions:
                action()
            if self.total_qubits > 0:
                qml.probs(wires=list(range(self.total_qubits)))
        return tape
