from fileinput import filename
from qsim.visitors.base_visitor import BaseVisitor
import cirq
import numpy as np
from enum import Enum
from qsim.qasm_parser.parser import parse_openqasm3
import os



def get_index_value(index_node):
    """Safely extract integer index value regardless of nesting."""
    if isinstance(index_node, list):
        index_node = index_node[0]
    return index_node.value if hasattr(index_node, "value") else int(index_node)

def evaluate_size(size_node, variables=None):
    """Helper to safely evaluate a type size expression."""
    if size_node is None:
        return None

    if hasattr(size_node, "value"):
        return int(size_node.value)

    elif hasattr(size_node, "name"):
        name = size_node.name
        if name in variables and variables[name].get("const", False):
            const_val = variables[name]["value"]
            if not isinstance(const_val, int):
                raise TypeError(f"Type size '{name}' must be an integer constant")
            return const_val
        else:
            raise ValueError(f"Size '{name}' must be a constant integer, not runtime variable")
    else:
        raise ValueError("Invalid size expression for type declaration")

def popcount(value, size=None):
    """Count number of 1 bits in integer representation."""
    if size:
        mask = (1 << size) - 1
        value = value & mask
    return bin(value).count('1')

def rotl(value, shift, size):
    """Rotate bits left for a given bit size."""
    if size is None:
        raise ValueError("Bitwise rotation 'rotl' requires a variable with a defined size.")
    shift %= size
    mask = (1 << size) - 1
    return ((value << shift) | (value >> (size - shift))) & mask

def rotr(value, shift, size):
    """Rotate bits right for a given bit size."""
    if size is None:
        raise ValueError("Bitwise rotation 'rotr' requires a variable with a defined size.")
    shift %= size
    mask = (1 << size) - 1
    return ((value >> shift) | (value << (size - shift))) & mask

def parse_bit_string(bit_string):
    """
    Parse a bit string literal to an integer, correctly handling underscores.
    """
    if isinstance(bit_string, str):
        cleaned_string = bit_string.strip('"\'').replace('_', '')
        if cleaned_string.startswith('0b'):
            cleaned_string = cleaned_string[2:]
        return int(cleaned_string, 2)
    elif isinstance(bit_string, int):
        return bit_string
    else:
        raise ValueError(f"Invalid bit string format: {bit_string}")

def normalize_index(index, length):
    """Convert negative indices to positive indices."""
    if index < 0:
        return length + index
    return index

def validate_array_index(indices, dimensions):
    """Validate that indices are within bounds."""
    if len(indices) > len(dimensions):
        raise IndexError(f"Too many indices: got {len(indices)}, expected at most {len(dimensions)}")
    
    for i, (idx, dim) in enumerate(zip(indices, dimensions)):
        normalized = normalize_index(idx, dim)
        if normalized < 0 or normalized >= dim:
            raise IndexError(f"Index {idx} out of bounds for dimension {i} with size {dim}")

def get_array_element_type(array_metadata):
    """Extract the base type from array metadata."""
    return array_metadata["base_type"]

def get_array_shape(array_metadata):
    """Extract the shape/dimensions from array metadata."""
    return array_metadata["dimensions"]

def compute_flat_index(indices, dimensions):
    """Compute flat index for multi-dimensional array access."""
    flat_idx = 0
    multiplier = 1
    
    # Work backwards through dimensions
    for i in range(len(indices) - 1, -1, -1):
        normalized_idx = normalize_index(indices[i], dimensions[i])
        flat_idx += normalized_idx * multiplier
        if i > 0:
            multiplier *= dimensions[i]
    
    return flat_idx

def eval_param(expr, variables=None, const_context=False):
    """
    Recursively evaluate QASM parameter expressions.
    """
    variables = variables or {}
    expr_type = type(expr).__name__
    
    # Handle range expressions
    if expr_type in ('RangeDefinition', 'RangeExpression'):
        start = eval_param(expr.start, variables, const_context) if hasattr(expr, 'start') and expr.start else 0
        end = eval_param(expr.end, variables, const_context) if hasattr(expr, 'end') and expr.end else None
        step = eval_param(expr.step, variables, const_context) if hasattr(expr, 'step') and expr.step else 1
        return ('RANGE', start, step, end)
    
    # Handle indexed access (arrays or bit slicing)
    if expr_type == 'IndexExpression':
        collection_name = expr.collection.name
        if collection_name not in variables:
            raise NameError(f"[IndexAccess] Variable '{collection_name}' not declared")
        
        var_metadata = variables[collection_name]
        var_type = var_metadata.get("type")
        
        # Case 1: Array element access
        if var_type == "array":
            index_list = expr.index if isinstance(expr.index, list) else [expr.index]
            indices = []
            for idx in index_list:
                idx_result = eval_param(idx, variables)
                if isinstance(idx_result, tuple) and idx_result[0] == 'RANGE':
                    raise ValueError(f"[ArrayAccess] Range expressions cannot be used directly in eval_param context")
                indices.append(int(idx_result))
            
            dimensions = var_metadata["dimensions"]
            validate_array_index(indices, dimensions)
            
            flat_idx = compute_flat_index(indices, dimensions)
            return var_metadata["data"][flat_idx]
        
        # Case 2: Bit slicing from int/uint/bit variables
        elif var_type in ("int", "uint", "bit"):
            value = var_metadata["value"]
            var_size = var_metadata.get("size", 32)
            
            index_list = expr.index if isinstance(expr.index, list) else [expr.index]
            
            # Check if this is a range or single index
            if len(index_list) == 1:
                idx_expr = index_list[0]
                idx_expr_type = type(idx_expr).__name__
                
                # Single bit access: myInt[5] or myInt[-1]
                if idx_expr_type in ('IntegerLiteral', 'UnaryExpression') or hasattr(idx_expr, 'value'):
                    bit_index = int(eval_param(idx_expr, variables))
                    
                    # Handle negative indices
                    if bit_index < 0:
                        bit_index = var_size + bit_index
                    
                    if bit_index < 0 or bit_index >= var_size:
                        raise IndexError(f"Bit index {bit_index} out of bounds for size {var_size}")
                    
                    # Extract the bit
                    bit_value = (value >> bit_index) & 1
                    return bit_value
                
                # Range access: myInt[0:15] or myInt[0:2:31]
                elif idx_expr_type in ('RangeDefinition', 'RangeExpression'):
                    range_tuple = eval_param(idx_expr, variables)
                    if range_tuple[0] == 'RANGE':
                        _, start, step, end = range_tuple
                        if end is None:
                            end = var_size - 1
                        
                        indices = expand_range(start, step, end, var_size)
                        
                        # Extract bits and pack into integer
                        result = 0
                        for i, bit_index in enumerate(indices):
                            bit = (value >> bit_index) & 1
                            result |= (bit << i)
                        return result
            
            raise ValueError(f"[BitSlice] Unsupported bit slicing expression")
        
        else:
            raise TypeError(f"'{collection_name}' cannot be indexed (type: {var_type})")

    # Case 1: Literals
    if hasattr(expr, "value"):
        return expr.value
    elif type(expr).__name__ == 'DurationLiteral':
        value = float(expr.value)
        unit = expr.unit.name
        if unit == 'dt':
            return cirq.Duration(nanos=value)
        else:
            return cirq.Duration(value, unit)
      
    # Case 2: Function Calls
    elif hasattr(expr, "name") and hasattr(expr, "arguments"):
        fn_name = expr.name.name
        args = [eval_param(arg, variables, const_context) for arg in expr.arguments]
        size = None
        if hasattr(expr.arguments[0], 'name'):
            arg_var_name = expr.arguments[0].name
            size = variables.get(arg_var_name, {}).get("size")
        if fn_name == "popcount":
            return popcount(args[0], size)
        elif fn_name == "rotl":
            return rotl(args[0], args[1], size)
        elif fn_name == "rotr":
            return rotr(args[0], args[1], size)
        else:
            raise NameError(f"Unsupported function call: {fn_name}")

    # Case 3: Identifiers (Variables)
    elif hasattr(expr, "name"):
        name = expr.name
        if name in ("pi", "π"):
            return np.pi
        elif name in variables:
            val = variables[name]
            if const_context and not val.get("const", False):
                raise ValueError(
                f"Cannot use non-const variable '{name}' in const context. "
                f"Only constants and literal values are allowed."
                )
            # Return the actual value, not the metadata dictionary
            if isinstance(val, dict):
                return val.get("value", val)
            return val
        else:
            raise NameError(f"'{name}' is not defined")
    
    # Case 4: Unary Expressions
    elif hasattr(expr, "op") and hasattr(expr, "expression"):
        val = eval_param(expr.expression, variables, const_context)
        op = expr.op.name
        if op in ("-", "NEG"): return -val
        if op in ("+", "POS"): return +val
        if op in ("!", "NOT"): return not val
        if op in ("~", "BITNOT"): return ("BITNOT", int(val))
        raise ValueError(f"Unsupported unary operator {op}")

    # Case 5: Binary Expressions
    elif hasattr(expr, "op") and hasattr(expr, "lhs") and hasattr(expr, "rhs"):
        op = expr.op.name

        lhs_raw = eval_param(expr.lhs, variables, const_context)
        rhs_raw = eval_param(expr.rhs, variables, const_context)

        is_bitwise_op = op in ("&", "BITAND", "|", "BITOR", "^", "BITXOR", "<<", "LSHIFT", ">>", "RSHIFT")
        angle_info = None
        lhs, rhs = lhs_raw, rhs_raw

        if is_bitwise_op and hasattr(expr.lhs, "name"):
            lhs_name = expr.lhs.name
            if lhs_name in variables and variables[lhs_name].get("type") == "angle":
                angle_info = variables[lhs_name]
                lhs = angle_info["bit_repr"]

        result = None
        if op == "+": result = lhs + rhs
        elif op == "-": result = lhs - rhs
        elif op == "*": result = lhs * rhs
        elif op == "/": result = lhs / rhs
        elif op == "**": result = lhs ** rhs
        elif op == "%": result = lhs % rhs
        elif op in ("&", "BITAND"): result = int(lhs) & int(rhs)
        elif op in ("|", "BITOR"):  result = int(lhs) | int(rhs)
        elif op in ("^", "BITXOR"): result = int(lhs) ^ int(rhs)
        elif op in ("<<", "LSHIFT"): result = int(lhs) << int(rhs)
        elif op in (">>", "RSHIFT"): result = int(lhs) >> int(rhs)
        elif op in ("==", "EQ"): return lhs_raw == rhs_raw
        elif op in ("!=", "NE"): return lhs_raw != rhs_raw
        elif op in ("<", "LT"):  return lhs_raw < rhs_raw
        elif op in ("<=", "LE"): return lhs_raw <= rhs_raw
        elif op in (">", "GT"):  return lhs_raw > rhs_raw
        elif op in (">=", "GE"): return lhs_raw >= rhs_raw
        elif op in ("&&", "AND"): return bool(lhs_raw) and bool(rhs_raw)
        elif op in ("||", "OR"): return bool(lhs_raw) or bool(rhs_raw)
        else:
            raise ValueError(f"Unsupported operator: {op}")

        if angle_info:
            size = angle_info["size"]
            if not size:
                raise ValueError("Bitwise operations on angles require a defined size.")
            
            modulus = 1 << size
            masked_bit_repr = result & (modulus - 1)
            return (masked_bit_repr / modulus) * (2 * np.pi)
        else:
            return result
    else:
        raise ValueError(f"Unsupported expression type: {expr}")

def evaluate_size_expression(size_node, variables=None):
    """Extended helper to evaluate size expressions with arithmetic."""
    variables = variables or {}

    try:
        return evaluate_size(size_node, variables)
    except ValueError as e:
        if "must be a constant" in str(e):
            raise e
        else:
            pass

    value = eval_param(size_node, variables, const_context=True)
    
    if not isinstance(value, (int, np.integer)):
        raise TypeError(f"Qubit/bit array size must evaluate to integer, got {value} ({type(value).__name__})")

    if value <= 0:
        raise ValueError(f"Qubit/bit array size must be positive, got {value}")

    return int(value)

def parse_range_expression(range_expr, variables=None):
    """
    Parse a range expression (a:b or a:c:b) and return (start, step, end).
    Returns a tuple (start, step, end) where all are integers.
    """
    variables = variables or {}
    
    if hasattr(range_expr, 'start'):
        # This is a RangeExpression node
        start = eval_param(range_expr.start, variables) if range_expr.start else 0
        step = eval_param(range_expr.step, variables) if hasattr(range_expr, 'step') and range_expr.step else 1
        end = eval_param(range_expr.end, variables) if range_expr.end else None
        return (int(start), int(step), int(end) if end is not None else None)
    else:
        raise ValueError(f"Invalid range expression: {range_expr}")


def expand_range(start, step, end, max_size):
    """
    Expand a range specification into a list of indices.
    Follows OpenQASM 3.0 semantics: a:c:b where c is step.
    """
    if step == 0:
        raise ValueError("Step in range cannot be zero")
    
    if end is None:
        end = max_size - 1
    
    # Normalize negative indices
    if start < 0:
        start = max_size + start
    if end < 0:
        end = max_size + end
    
    indices = []
    if step > 0:
        current = start
        while current <= end:
            if 0 <= current < max_size:
                indices.append(current)
            current += step
    else:  # step < 0
        current = start
        while current >= end:
            if 0 <= current < max_size:
                indices.append(current)
            current += step
    
    return indices


def parse_index_set(index_expr, size, variables=None):
    """
    Parse an index set expression and return a list of indices.
    Handles single indices, lists of indices, ranges, and discrete sets.
    """
    variables = variables or {}
    
    # The parser sometimes wraps single indices/ranges in an extra list
    if isinstance(index_expr, list):
        if not index_expr: return []
        index_expr = index_expr[0]

    expr_type = type(index_expr).__name__

    # Case for a Range (e.g., [0:6])
    if expr_type in ('RangeExpression', 'RangeDefinition'):
        start_expr = index_expr.start
        end_expr = index_expr.end
        step_expr = index_expr.step if hasattr(index_expr, 'step') else None

        start = eval_param(start_expr, variables) if start_expr else 0
        end = eval_param(end_expr, variables) if end_expr else (size - 1)
        step = eval_param(step_expr, variables) if step_expr else 1

        return expand_range(int(start), int(step), int(end), size)

    # --- FIX: Add handling for DiscreteSet (e.g., [{0, 2, 4}]) ---
    elif expr_type in ('DiscreteSet', 'IndexSet'):
        indices = []
        for val_expr in index_expr.values:
            idx = int(eval_param(val_expr, variables))
            normalized_idx = normalize_index(idx, size)
            if not (0 <= normalized_idx < size):
                raise IndexError(f"Index {idx} out of bounds for size {size}")
            indices.append(normalized_idx)
        return indices

    # Fallback for a single index (IntegerLiteral, Identifier, etc.)
    else:
        idx = int(eval_param(index_expr, variables))
        normalized_idx = normalize_index(idx, size)
        if not (0 <= normalized_idx < size):
            raise IndexError(f"Index {idx} out of bounds for size {size}")
        return [normalized_idx]

def _u_matrix(theta, phi, lam):
    """Exact OpenQASM 3 U(theta, phi, lambda) matrix."""
    c, sn = np.cos(theta / 2), np.sin(theta / 2)
    return np.array([
        [c, -np.exp(1j * lam) * sn],
        [np.exp(1j * phi) * sn, np.exp(1j * (phi + lam)) * c],
    ], dtype=complex)


STANDARD_INCLUDES = frozenset({"stdgates.inc", "qelib1.inc", "stdgates.qasm"})


class ProgramTermination(Exception):
    """Exception raised when a program termination statement is encountered."""
    pass

    
class CirqVisitor(BaseVisitor):
    def __init__(self):
        self.circuit = None
        self.qubits = {}
        self.clbits = {}
        self.custom_gates = {}
        self.variables = {}
        self.scope_stack = []  # Stack of sets containing variables declared in each scope
        self._loop_break = False
        self._loop_continue = False
        self._measured_keys = set()      # measurement keys written so far (circuit order)
        self._declared_qregs = []        # qubit registers in declaration order
        self._declared_cregs = []        # bit registers in declaration order
        self._in_dynamic_block = False

        self.STD_GATES_ALLOWED = False
        self._gate_call_stack = []  # Track gate calls for recursion detection
        self._in_gate_body = False   # Track if we're inside a gate body

        self.STD_GATES = frozenset([
        # Single-qubit gates
        "u", "U", "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx",
        # Single-qubit rotations
        "rx", "ry", "rz",
        # Two-qubit gates
        "cx", "CX", "cy", "cz", "ch", "cp", "swap", "iswap", "sqrtiswap",
        # Controlled rotations
        "crx", "cry", "crz",
        # Three-qubit gates
        "ccx", "cswap",
        # Other
        "cu1", "cu3", "rzz", "rxx", "ryy", "gphase", "p", "phase", "cphase",
        "ccz", "cu", "u1", "u2", "u3"
         ])

    def visit_Include(self, node):
        """Handles 'include "<path>"' statements.

        Only the standard gate libraries are accepted. Reading arbitrary paths
        from the server's disk is never allowed (programs come from users).
        """
        filename = node.filename.replace('"', '').strip()

        if filename.lower() in STANDARD_INCLUDES:
            self.STD_GATES_ALLOWED = True
            return

        raise PermissionError(
            f"[Include] Only the standard libraries {sorted(STANDARD_INCLUDES)} may be included; "
            f"'{filename}' is not allowed."
        )

    def visit_AliasStatement(self, node):
        """
        Handles 'let' alias statements for qubits and classical registers,
        now correctly identifying IndexExpressions.
        """
        alias_name = node.target.name
        value_expr = node.value
        expr_type = type(value_expr).__name__

        # Case 1: Concatenation (e.g., let c = a ++ b;)
        if expr_type == 'Concatenation':
            return self._handle_concatenation_alias(alias_name, value_expr)

        # --- FIX: Handle IndexExpression and simple Identifier ---
        # Case 2: Slicing/Indexing (e.g., let a = q[0];) or Renaming (e.g., let b = q;)
        elif expr_type in ('IndexExpression', 'Identifier'):
            source_name = ""
            if expr_type == 'IndexExpression':
                source_name = value_expr.collection.name
            else: # Identifier
                source_name = value_expr.name
            
            # Determine if the source is a qubit or classical register
            if source_name in self.qubits:
                return self._handle_qubit_alias(alias_name, value_expr, source_name)
            elif source_name in self.variables:
                return self._handle_classical_alias(alias_name, value_expr, source_name)
            else:
                raise NameError(f"[Alias] Unknown register or variable: {source_name}")
        
        raise ValueError(f"[Alias] Unsupported alias expression type: {expr_type}")


    def _handle_qubit_alias(self, alias_name, value_expr, source_name):
        """Handle aliasing of qubits with slicing/indexing."""
        # Check for duplicate names (optional validation)
        if alias_name in self.qubits:
            raise ValueError(
                f"[Alias] Cannot create alias '{alias_name}': "
                f"a qubit register with this name already exists"
            )
        
        source_qubits = self.qubits[source_name]
        
        if hasattr(value_expr, 'index') and value_expr.index:
            index_specifier = value_expr.index
            index_list = parse_index_set(index_specifier, len(source_qubits), self.variables)
            aliased_qubits = [source_qubits[i] for i in index_list]
        else:
            aliased_qubits = source_qubits[:]
        
        self.qubits[alias_name] = aliased_qubits
        return alias_name

    def _handle_classical_alias(self, alias_name, value_expr, source_name):
        """Handle aliasing of classical variables (reference, not copy)."""
        source_var = self.variables[source_name]
        
        # Check if this is a bit type - bit aliases are not allowed
        if source_var.get("type") == "bit":
            raise TypeError(
                f"[Alias] Cannot create alias '{alias_name}' for classical bit register '{source_name}'. "
                f"Classical bit register aliasing is not supported. Use qubit registers instead."
            )
        
        # For other classical types (arrays, etc.), create a reference
        self.variables[alias_name] = {
            "type": source_var["type"],
            "size": source_var.get("size"),
            "value": source_var.get("value"),
            "data": source_var.get("data"),
            "base_type": source_var.get("base_type"),
            "dimensions": source_var.get("dimensions"),
            "const": False,
            "alias_of": source_name  # Track that this is an alias
        }
        
        return alias_name

    def _handle_concatenation_alias(self, alias_name, concat_expr):
        """
        Handle register concatenation with ++ operator.
        Examples:
        - let concatenated = one ++ two;
        - let both = sliced ++ last_three;
        """
        # Get left and right operands
        left_expr = concat_expr.lhs
        right_expr = concat_expr.rhs
        
        # Extract register names - handle both Identifier and IndexExpression
        def get_source_name(expr):
            """Helper to extract source register name from expression."""
            if hasattr(expr, 'name'):
                # Simple Identifier: q1
                return expr.name if isinstance(expr, str) else expr.name
            elif hasattr(expr, 'collection'):
                # IndexExpression: q1[0:2]
                return expr.collection.name
            else:
                raise ValueError(f"Unable to extract name from expression: {type(expr).__name__}")
        
        left_name = get_source_name(left_expr)
        right_name = get_source_name(right_expr)
        
        # Determine type (qubit or classical)
        if left_name in self.qubits and right_name in self.qubits:
            # Qubit concatenation - ALLOWED
            left_qubits = self.qubits[left_name]
            right_qubits = self.qubits[right_name]
            
            # Handle slicing if present
            if type(left_expr).__name__ == 'IndexExpression' and hasattr(left_expr, 'index'):
                indices = parse_index_set(left_expr.index, len(left_qubits), self.variables)
                left_qubits = [left_qubits[i] for i in indices]
            
            if type(right_expr).__name__ == 'IndexExpression' and hasattr(right_expr, 'index'):
                indices = parse_index_set(right_expr.index, len(right_qubits), self.variables)
                right_qubits = [right_qubits[i] for i in indices]
            
            concatenated = left_qubits + right_qubits
            self.qubits[alias_name] = concatenated
            return alias_name
        
        elif left_name in self.variables and right_name in self.variables:
            # Classical array concatenation - NOT ALLOWED
            raise NotImplementedError(
                f"[Concatenation] Array concatenation is not allowed. "
                f"Cannot create alias '{alias_name}' using '{left_name} ++ {right_name}'. "
                f"Array concatenation with the '++' operator is not supported for classical arrays."
            )
        
        else:
            raise TypeError(f"[Concatenation] Type mismatch in concatenation")

    def visit_QuantumBarrier(self, node):
        """
        Handles the 'barrier' statement, correctly processing both
        full registers and specific indexed qubits.
        """
        target_qubits = []
        
        if not node.qubits:
            for reg in self.qubits.values():
                target_qubits.extend(reg)
        else:
            for q_arg in node.qubits:
                reg_name = q_arg.name if isinstance(q_arg.name, str) else q_arg.name.name

                if not hasattr(q_arg, "indices") or not q_arg.indices:
                    if reg_name in self.qubits:
                        target_qubits.extend(self.qubits[reg_name])
                else:
                    idx = get_index_value(q_arg.indices[0]) 
                    if reg_name in self.qubits:
                        target_qubits.append(self.qubits[reg_name][idx])

        if not target_qubits:
            return

        barrier_op = cirq.IdentityGate(len(target_qubits)).on(*target_qubits)
        self.circuit.append(barrier_op)
        
        return None

    def visit_ArrayDeclaration(self, node):
        """
        Handles array declarations:
        array[int[32], 5] myArray = {0, 1, 2, 3, 4};
        array[float[32], 3, 2] multiDim = {{1.1, 1.2}, {2.1, 2.2}, {3.1, 3.2}};
        """
        var_name = node.identifier.name
        
        # Extract base type
        base_type_node = node.type.base_type if hasattr(node.type, 'base_type') else None
        if not base_type_node:
            raise ValueError(f"[ArrayDeclaration] Array '{var_name}' missing base type")
        
        base_type_name = type(base_type_node).__name__
        base_type = base_type_name.replace("Type", "").lower()
        
        # Extract base type size (e.g., int[32])
        base_size = None
        if hasattr(base_type_node, 'size') and base_type_node.size:
            base_size = evaluate_size_expression(base_type_node.size, self.variables)
        
        # Extract array dimensions
        dimensions = []
        if hasattr(node.type, 'dimensions'):
            for dim_node in node.type.dimensions:
                dim_size = evaluate_size_expression(dim_node, self.variables)
                dimensions.append(dim_size)
        else:
            raise ValueError(f"[ArrayDeclaration] Array '{var_name}' missing dimensions")
        
        if len(dimensions) > 7:
            raise ValueError(f"[ArrayDeclaration] Array '{var_name}' exceeds maximum of 7 dimensions")
        
        # Calculate total number of elements
        total_elements = 1
        for dim in dimensions:
            total_elements *= dim
        
        # Initialize array with default values
        default_value = self._get_default_value(base_type)
        flat_data = [default_value] * total_elements
        
        # Handle initialization
        if hasattr(node, 'init_expression') and node.init_expression:
            init_values = self._parse_array_initializer(node.init_expression, self.variables)
            flat_init = self._flatten_nested_list(init_values)
            
            if len(flat_init) != total_elements:
                raise ValueError(
                    f"[ArrayDeclaration] Array '{var_name}' size mismatch: "
                    f"expected {total_elements} elements, got {len(flat_init)}"
                )
            
            flat_data = flat_init
        
        # Store array metadata
        self.variables[var_name] = {
            "type": "array",
            "base_type": base_type,
            "base_size": base_size,
            "dimensions": dimensions,
            "data": flat_data,
            "const": False
        }
        
        return var_name

    def visit_ArrayReferenceExpression(self, node):
        """
        Handles array element access:
        myArray[0]
        multiDim[2, 1]
        myArray[-1]
        """
        array_name = node.name.name if hasattr(node.name, 'name') else node.name
        
        if array_name not in self.variables:
            raise NameError(f"[ArrayAccess] Array '{array_name}' not declared")
        
        array_metadata = self.variables[array_name]
        
        if array_metadata.get("type") != "array":
            raise TypeError(f"[ArrayAccess] '{array_name}' is not an array")
        
        # Extract indices - handle both 'indices' and 'index' attributes
        indices = []
        if hasattr(node, 'indices'):
            for idx_node in node.indices:
                idx_value = eval_param(idx_node, self.variables)
                indices.append(int(idx_value))
        elif hasattr(node, 'index'):
            index_list = node.index if isinstance(node.index, list) else [node.index]
            for idx_node in index_list:
                idx_value = eval_param(idx_node, self.variables)
                indices.append(int(idx_value))
        
        dimensions = array_metadata["dimensions"]
        validate_array_index(indices, dimensions)
        
        # Compute flat index
        flat_idx = compute_flat_index(indices, dimensions)
        
        return array_metadata["data"][flat_idx]

    def visit_ClassicalAssignment(self, node):
        """
        Enhanced to handle array element assignments:
        myArray[4] = 10;
        multiDim[0, 0] = 0.0;
        bb[0] = aa; // array-to-array assignment
        """
        # Check if lvalue is an array access (IndexExpression or similar)
        lvalue_type = type(node.lvalue).__name__
        if lvalue_type in ('ArrayReferenceExpression', 'IndexExpression', 'IndexedIdentifier'):
            return self._handle_array_element_assignment(node)
        
        # Regular variable assignment
        # Extract the name properly - it might be an Identifier object or a string
        if hasattr(node.lvalue, 'name'):
            target_name = node.lvalue.name if isinstance(node.lvalue.name, str) else node.lvalue.name.name
        else:
            target_name = str(node.lvalue)
            
        if target_name not in self.variables:
            raise NameError(f"[Assignment] Variable '{target_name}' not declared")

        var_entry = self.variables[target_name]

        if var_entry.get("const"):
            raise ValueError(f"[Assignment] Variable '{target_name}' cannot be assigned (const)")

        # Check for compound assignment operators
        if hasattr(node, "op") and node.op:
            op = node.op.name if hasattr(node.op, "name") else node.op
            
            if op == "=":
                try:
                    rhs_value = eval_param(node.rvalue, self.variables)
                except Exception as e:
                    raise ValueError(f"[Assignment] Failed to evaluate RHS for '{target_name}': {e}")
            else:
                current_val = var_entry["value"]
                rhs_value = eval_param(node.rvalue, self.variables)
                
                if op == "+=":
                    rhs_value = current_val + rhs_value
                elif op == "-=":
                    rhs_value = current_val - rhs_value
                elif op == "*=":
                    rhs_value = current_val * rhs_value
                elif op == "/=":
                    if rhs_value == 0:
                        raise ValueError(f"[Assignment] Division by zero")
                    rhs_value = current_val / rhs_value
                elif op == "&=":
                    rhs_value = int(current_val) & int(rhs_value)
                elif op == "|=":
                    rhs_value = int(current_val) | int(rhs_value)
                elif op == "^=":
                    rhs_value = int(current_val) ^ int(rhs_value)
                elif op == "<<=":
                    shift_amount = int(rhs_value)
                    if shift_amount < 0:
                        raise ValueError("[Assignment] Shift amount cannot be negative")
                    rhs_value = int(current_val) << shift_amount
                elif op == ">>=":
                    shift_amount = int(rhs_value)
                    if shift_amount < 0:
                        raise ValueError("[Assignment] Shift amount cannot be negative")
                    rhs_value = int(current_val) >> shift_amount
                else:
                    raise ValueError(f"[Assignment] Unsupported compound assignment operator: {op}")
        else:
            try:
                rhs_value = eval_param(node.rvalue, self.variables)
            except Exception as e:
                raise ValueError(f"[Assignment] Failed to evaluate RHS for '{target_name}': {e}")

        # Handle special function returns
        if isinstance(rhs_value, tuple):
            if rhs_value[0] in ("rotl", "rotr"):
                func_name, value, shift = rhs_value
                size = var_entry.get("size")
                if not size:
                    raise ValueError(f"[Assignment] {func_name} requires a sized type")
                if func_name == "rotl":
                    rhs_value = rotl(value, shift, size)
                else:
                    rhs_value = rotr(value, shift, size)
            elif rhs_value[0] == "BITNOT":
                _, value = rhs_value
                size = var_entry.get("size")
                if size:
                    mask = (1 << size) - 1
                    rhs_value = (~value) & mask
                else:
                    rhs_value = ~value

        declared_type = var_entry["type"]

        # Special handling for bit arrays
        if declared_type == "bit":
            size_val = var_entry.get("size", 1)
            if isinstance(rhs_value, str):
                rhs_value = parse_bit_string(rhs_value)
            rhs_value = int(rhs_value)
            if size_val:
                mask = (1 << size_val) - 1
                rhs_value = rhs_value & mask
            self.variables[target_name]["value"] = rhs_value
            return target_name

        # Special handling for angle type
        if declared_type == "angle":
            size_val = var_entry.get("size")
            if isinstance(rhs_value, int) and size_val:
                two_pi = 2 * np.pi
                modulus = 2 ** size_val
                bit_repr = rhs_value & (modulus - 1)
                angle_value = (bit_repr / modulus) * two_pi
                self.variables[target_name]["value"] = angle_value
                self.variables[target_name]["bit_repr"] = bit_repr
                return target_name
            
            elif isinstance(rhs_value, (int, float)):
                two_pi = 2 * np.pi
                angle_value = float(rhs_value) % two_pi
                bit_repr = None
                if size_val:
                    modulus = 2 ** size_val
                    scaled = (angle_value / two_pi) * modulus
                    bit_repr = int(round(scaled)) % modulus
                self.variables[target_name]["value"] = angle_value
                self.variables[target_name]["bit_repr"] = bit_repr
                return target_name

        # Type checking
        rhs_type = None
        if isinstance(rhs_value, bool):
            rhs_type = "bool"
        elif isinstance(rhs_value, int):
            rhs_type = "int"
        elif isinstance(rhs_value, float):
            rhs_type = "float"

        compatible_types = {
            "bool": ["bool"],
            "int": ["int", "uint", "bool"],
            "uint": ["uint", "int", "bool"],
            "float": ["float", "int", "uint"],
            "angle": ["angle", "float", "int", "uint"],
            "bit": ["bit", "int", "uint", "bool"],
        }

        if rhs_type is not None:
            allowed = rhs_type in compatible_types.get(declared_type, [])
            if not allowed:
                raise TypeError(
                    f"[Assignment] Type mismatch: declared {declared_type}, got {rhs_type}"
                )

        # Apply size constraints
        if declared_type == "uint":
            size_val = var_entry.get("size")
            if size_val:
                mask = (1 << size_val) - 1
                rhs_value = int(rhs_value) & mask
            else:
                rhs_value = abs(int(rhs_value))
        elif declared_type == "int":
            size_val = var_entry.get("size")
            if size_val:
                rhs_value = int(rhs_value)
                mask = (1 << size_val) - 1
                rhs_value = rhs_value & mask
                if rhs_value >= (1 << (size_val - 1)):
                    rhs_value -= (1 << size_val)

        self.variables[target_name]["value"] = rhs_value

        return target_name

    def _handle_array_element_assignment(self, node):
        """Handle assignment to array elements."""
        lvalue = node.lvalue
        array_name = lvalue.name.name if hasattr(lvalue.name, 'name') else lvalue.name
        
        if array_name not in self.variables:
            raise NameError(f"[ArrayAssignment] Array '{array_name}' not declared")
        
        array_metadata = self.variables[array_name]
        
        if array_metadata.get("type") != "array":
            raise TypeError(f"[ArrayAssignment] '{array_name}' is not an array")
        
        # Extract indices
        indices = []
        if hasattr(lvalue, 'indices') and lvalue.indices:
        # The parser gives a list containing one list of indices: [[idx1, idx2, ...]]
            index_nodes = lvalue.indices[0] 
            for idx_node in index_nodes:
                idx_value = eval_param(idx_node, self.variables)
                indices.append(int(idx_value))
        dimensions = array_metadata["dimensions"]
        
        # Check if this is a subarray assignment
        if len(indices) < len(dimensions):
            # Subarray assignment (e.g., bb[0] = aa)
            return self._handle_subarray_assignment(array_name, indices, node.rvalue)
        
        # Single element assignment
        validate_array_index(indices, dimensions)
        flat_idx = compute_flat_index(indices, dimensions)
        
        # Evaluate RHS
        rhs_value = eval_param(node.rvalue, self.variables)
        
        base_type = array_metadata["base_type"]
        converted_value = self._convert_to_type(rhs_value, base_type, array_metadata.get("base_size"))    
        # Apply type-specific conversions
        array_metadata["data"][flat_idx] = converted_value
        
        return array_name

    def _handle_subarray_assignment(self, array_name, indices, rvalue):
        """Handle assignment to a subarray (e.g., bb[0] = aa)."""
        array_metadata = self.variables[array_name]
        dimensions = array_metadata["dimensions"]
        
        # Determine target subarray shape
        subarray_dims = dimensions[len(indices):]
        subarray_size = 1
        for dim in subarray_dims:
            subarray_size *= dim
        
        # Evaluate RHS
        if type(rvalue).__name__ == 'Identifier':
            # RHS is another array
            rhs_name = rvalue.name
            if rhs_name not in self.variables:
                raise NameError(f"[SubarrayAssignment] Variable '{rhs_name}' not declared")
            
            rhs_metadata = self.variables[rhs_name]
            
            if rhs_metadata.get("type") != "array":
                raise TypeError(f"[SubarrayAssignment] '{rhs_name}' is not an array")
            
            # Check shape compatibility
            if rhs_metadata["dimensions"] != subarray_dims:
                raise ValueError(
                    f"[SubarrayAssignment] Shape mismatch: cannot assign array with shape "
                    f"{rhs_metadata['dimensions']} to subarray with shape {subarray_dims}"
                )
            
            # Copy data
            start_idx = compute_flat_index(indices + [0] * len(subarray_dims), dimensions)
            for i in range(subarray_size):
                array_metadata["data"][start_idx + i] = rhs_metadata["data"][i]
            
        else:
            # RHS is a scalar - error
            raise ValueError(
                f"[SubarrayAssignment] Shape mismatch: cannot assign scalar to subarray with shape {subarray_dims}"
            )
        
        return array_name

    def _get_default_value(self, base_type):
        """Get default value for a type."""
        defaults = {
            "int": 0,
            "uint": 0,
            "float": 0.0,
            "bool": False,
            "bit": 0,
            "angle": 0.0,
            "complex": complex(0, 0)
        }
        return defaults.get(base_type, 0)

    def _parse_array_initializer(self, init_expr, variables):
        """Parse array initializer expression (handles nested lists)."""
        if hasattr(init_expr, 'values'):
            # List/Array literal
            return [self._parse_array_initializer(val, variables) for val in init_expr.values]
        else:
            # Single value
            return eval_param(init_expr, variables)

    def _flatten_nested_list(self, nested):
        """Flatten a nested list structure."""
        if isinstance(nested, list):
            result = []
            for item in nested:
                if isinstance(item, list):
                    result.extend(self._flatten_nested_list(item))
                else:
                    result.append(item)
            return result
        else:
            return [nested]

    def _validate_array_element_type(self, value, expected_type):
        """Validate that a value matches the expected array element type."""
        value_type = None
        if isinstance(value, bool):
            value_type = "bool"
        elif isinstance(value, int):
            value_type = "int"
        elif isinstance(value, float):
            value_type = "float"
        elif isinstance(value, complex):
            value_type = "complex"
        
        compatible_types = {
            "bool": ["bool"],
            "int": ["int", "uint", "bool"],
            "uint": ["uint", "int", "bool"],
            "float": ["float", "int", "uint"],
            "angle": ["angle", "float", "int", "uint"],
            "bit": ["bit", "int", "uint", "bool"],
            "complex": ["complex", "float", "int", "uint"]
        }
        
        if value_type and expected_type in compatible_types:
            if value_type not in compatible_types[expected_type]:
                raise TypeError(
                    f"[ArrayType] Type mismatch: expected {expected_type}, got {value_type}"
                )

    def _convert_to_type(self, value, target_type, size=None):
        """Convert a value to the target type with size constraints."""
        if target_type == "int":
            value = int(value)
            if size:
                mask = (1 << size) - 1
                value &= mask
                if value >= (1 << (size - 1)):
                    value -= (1 << size)
        elif target_type == "uint":
            value = int(value)
            if size:
                mask = (1 << size) - 1
                value &= mask
        elif target_type == "float":
            value = float(value)
        elif target_type == "bool":
            value = bool(value)
        elif target_type == "bit":
            value = int(value)
            if size:
                mask = (1 << size) - 1
                value &= mask
        elif target_type == "angle":
            value = float(value) % (2 * np.pi)
        elif target_type == "complex":
            value = complex(value)
        
        return value

    def visit_ConstantDeclaration(self, node):
        """Handles constant declarations in OpenQASM 3.0"""
        typename = type(node.type).__name__
        var_name = node.identifier.name

        if not hasattr(node, "init_expression") or not node.init_expression:
             raise ValueError(f"[ConstDeclaration] Constant '{var_name}' must have an initializer")

        try:
            # IMPORTANT: Pass const_context=True to enforce const-only evaluation
            init_value = eval_param(node.init_expression, variables=self.variables, const_context=True)
        except ValueError as e:
            # Re-raise with clearer message if it's about non-const access
            if "non-const" in str(e).lower() or "const context" in str(e).lower():
                raise ValueError(
                    f"[ConstDeclaration] Cannot initialize constant '{var_name}' with non-const variable. "
                    f"Constants must be initialized with literal values or other constants."
                ) from e
            raise ValueError(f"[ConstDeclaration] Failed to evaluate constant initializer for {var_name}: {e}") from e
        except Exception as e:
            raise ValueError(f"[ConstDeclaration] Failed to evaluate constant initializer for {var_name}: {e}") from e


        if isinstance(init_value, tuple):
            if init_value[0] == "BITNOT":
                raise ValueError(f"[ConstDeclaration] Bitwise NOT requires size context")
            elif init_value[0] in ("rotl", "rotr"):
                raise ValueError(f"[ConstDeclaration] {init_value[0]} requires size context")

        size_val = None
        if hasattr(node.type, "size"):
            size_val = evaluate_size_expression(node.type.size, self.variables)

        rhs_type = None
        if isinstance(init_value, bool):
            rhs_type = "bool"
        elif isinstance(init_value, int):
            rhs_type = "int"
        elif isinstance(init_value, float):
            rhs_type = "float"
        elif init_value is None:
            rhs_type = "none"

        declared_type = typename.replace("Type", "").lower()

        compatible_types = {
            "bool": ["bool"],
            "int": ["int", "uint", "bool"],
            "uint": ["uint", "int", "bool"],
            "float": ["float", "int", "uint"],
            "angle": ["angle", "float", "int", "uint"],
        }

        if rhs_type != "none":
            allowed = rhs_type in compatible_types.get(declared_type, [])
            if not allowed:
                raise TypeError(
                    f"[ConstDeclaration] Type mismatch in declaration '{var_name}': "
                    f"declared {declared_type}, got {rhs_type}"
                )

        if declared_type == "int":
            value = int(init_value)
            if size_val:
                mask = (1 << size_val) - 1
                value &= mask
                if value >= (1 << (size_val - 1)):
                    value -= (1 << size_val)

        elif declared_type == "uint":
            value = int(init_value)
            if size_val:
                mask = (1 << size_val) - 1
                value &= mask

        elif declared_type == "float":
            value = float(init_value)

        elif declared_type == "bool":
            value = bool(init_value)

        elif declared_type == "angle":
            if str(init_value).lower() in ("pi", "π"):
                value = float(np.pi)
            else:
                value = float(init_value)
            two_pi = 2 * np.pi
            value = value % two_pi

        else:
            raise ValueError(f"[ConstDeclaration] Unsupported type: {declared_type}")

        self.variables[var_name] = {
            "type": declared_type,
            "size": size_val,
            "value": value,
            "const": True,
        }

        return var_name

    def visit_QubitDeclaration(self, node):
        """Handles qubit register declarations."""
        size_val = None
        if hasattr(node, "size") and node.size:
            size_val = evaluate_size_expression(node.size, self.variables)

        if size_val is None:
            size_val = 1

        qubits = [
            cirq.NamedQubit(f"{node.qubit.name}_{i}") for i in range(size_val)
        ]
        
        if self.circuit is None:
            self.circuit = cirq.Circuit()
        self.qubits[node.qubit.name] = qubits
        if node.qubit.name not in self._declared_qregs:
            self._declared_qregs.append(node.qubit.name)
        return qubits

# Add this exception class at the top of your cirq_visitor.py file


    def visit_ForInLoop(self, node):
        """
        Handles for-in loops with full validation and edge case handling.
        
        Example:
            for int i in {1, 5, 10} {
                b += i;
            }
            
            for int i in [0:2:20] {
                subroutine(i);
            }
            
            for float f in my_array {
                // do something
            }
        """
        # Check if we're in a dynamic context (after measurements)
        if hasattr(self, '_in_dynamic_context') and self._in_dynamic_context:
            raise ValueError("[ForLoop] For loops not allowed in dynamic control blocks.")
        
        # Extract loop variable info
        loop_var_type = type(node.type).__name__.replace("Type", "").lower()
        loop_var_name = node.identifier.name
        
        
        # Determine the values to iterate over
        try:
            values = self._get_loop_values(node.set_declaration, loop_var_type)
        except Exception as e:
            raise ValueError(f"[ForLoop] Error getting loop values: {e}")
        
        
        # Save loop variable if it exists in outer scope (for shadowing)
        saved_var = self.variables.get(loop_var_name)
        outer_var_existed = loop_var_name in self.variables
        
        # Initialize loop control flags if they don't exist
        if not hasattr(self, '_loop_break'):
            self._loop_break = False
        if not hasattr(self, '_loop_continue'):
            self._loop_continue = False
        
        # Reset flags before starting loop
        self._loop_break = False
        self._loop_continue = False
        
        # Execute loop
        for i, value in enumerate(values):
            # Convert value to the appropriate type
            try:
                converted_value = self._convert_loop_value(value, loop_var_type)
            except Exception as e:
                raise TypeError(f"[ForLoop] Error converting loop variable '{loop_var_name}' value {value} to type {loop_var_type}: {e}")
            
            # Set loop variable
            self.variables[loop_var_name] = {
                "type": loop_var_type,
                "size": None,
                "value": converted_value,
                "const": False
            }
            
             
            
            # Reset continue flag at start of each iteration
            self._loop_continue = False
            
            # Execute loop body
            if hasattr(node, 'block') and node.block:
                self._execute_block(node.block)
            elif hasattr(node, 'body') and node.body:
                self._execute_block(node.body)
            
            # Check for break - exit loop immediately
            if self._loop_break:
                 
                break
            
            # Continue is handled automatically by resetting at start of next iteration
            if self._loop_continue:
                 
                continue
        
        # Clean up: reset flags
        self._loop_break = False
        self._loop_continue = False
        
        # Remove loop variable from scope (it's local to the loop)
        if loop_var_name in self.variables:
            del self.variables[loop_var_name]
        
        # Restore saved variable if it existed in outer scope
        if outer_var_existed and saved_var is not None:
            self.variables[loop_var_name] = saved_var
        
         
        return None


    def visit_BreakStatement(self, node):
        """
        Handle break statements in loops.
        
        Sets a flag that will be checked by loop implementations.
        """
         
        self._loop_break = True
        return None


    def visit_ContinueStatement(self, node):
        """
        Handle continue statements in loops.
        
        Sets a flag that will be checked by loop implementations.
        """
         
        self._loop_continue = True
        return None


    def _convert_loop_value(self, value, target_type):
        """
        Convert a loop iteration value to the target type.
        
        Args:
            value: The value to convert
            target_type: The target type (e.g., 'int', 'float', 'bool', 'angle')
        
        Returns:
            Converted value
        """
        if target_type == "int":
            return int(value)
        elif target_type == "uint":
            return int(abs(value))
        elif target_type == "float":
            return float(value)
        elif target_type == "bool":
            return bool(value)
        elif target_type == "bit":
            return int(value) & 1
        elif target_type == "angle":
            return float(value) % (2 * np.pi)
        else:
            # For other types, just return as-is
            return value


    def _get_loop_values(self, set_declaration, loop_var_type):
        """
        Extract values to iterate over from a for loop set declaration.
        
        Args:
            set_declaration: The set/range/array to iterate over
            loop_var_type: The type of the loop variable
        
        Returns:
            List of values to iterate over
        """
        set_type = type(set_declaration).__name__
        
        # Case 1: Discrete set {1, 2, 3}
        if set_type in ('DiscreteSet', 'ArrayLiteral'):
            values = []
            if hasattr(set_declaration, 'values'):
                for val_expr in set_declaration.values:
                    val = eval_param(val_expr, self.variables)
                    values.append(val)
            return values
        
       # Case 2: Range expression [start:step:stop] or [start:stop]
        elif set_type in ('RangeDefinition', 'RangeExpression'):
            start_val = eval_param(set_declaration.start, self.variables) if set_declaration.start else 0
            end_val = eval_param(set_declaration.end, self.variables) if set_declaration.end else None
            step_val = eval_param(set_declaration.step, self.variables) if hasattr(set_declaration, 'step') and set_declaration.step else 1
            
            # Convert to integers
            start = int(start_val)
            end = int(end_val) if end_val is not None else None
            step = int(step_val)
            
            if end is None:
                raise ValueError("[ForLoop] Range end must be specified")
            
            # Generate range values
            values = []
            if step > 0:
                current = start
                while current <= end:
                    values.append(current)
                    current += step
            elif step < 0:
                current = start
                while current >= end:
                    values.append(current)
                    current += step
            else:
                raise ValueError("[ForLoop] Step cannot be zero")
            
            return values
        
        # Case 3: Identifier (could be bit register, array, or alias)
        elif set_type == 'Identifier':
            var_name = set_declaration.name
            
            if var_name not in self.variables:
                raise NameError(f"[ForLoop] Variable '{var_name}' not found")
            
            var_metadata = self.variables[var_name]
            var_type = var_metadata.get("type")
            
            # Check for scalar types that can't be iterated
            if var_type in ('int', 'uint', 'float', 'bool', 'angle'):
                raise TypeError(
                f"[ForLoop] Cannot iterate over type '{var_type}' (single scalar value)."
                )
            
            # Case 3a: Bit register - iterate over individual bits
            if var_type == "bit":
                size = var_metadata.get("size", 1)
                value = var_metadata.get("value", 0)
                
                # Extract individual bits in order (bit 0 first)
                values = []
                for i in range(size):
                    bit_value = (value >> i) & 1
                    values.append(bit_value)
                return values
            
            # Case 3b: Array - iterate over elements
            elif var_type == "array":
                if len(var_metadata["dimensions"]) != 1:
                    raise TypeError(
                        f"[ForLoop] Only one-dimensional arrays can be iterated over. "
                        f"Got {len(var_metadata['dimensions'])}D array."
                    )
                
                return var_metadata["data"][:]
            
            else:
                raise TypeError(f"[ForLoop] Cannot iterate over variable of type '{var_type}'")
        
        # Case 4: IndexExpression (e.g., my_array[1:3] or breg[1:3])
        elif set_type == 'IndexExpression':
            collection_name = set_declaration.collection.name
            
            if collection_name not in self.variables:
                raise NameError(f"[ForLoop] Variable '{collection_name}' not found")
            
            var_metadata = self.variables[collection_name]
            var_type = var_metadata.get("type")
            
            # Parse index/range
            index_expr = set_declaration.index
            if isinstance(index_expr, list) and len(index_expr) > 0:
                index_expr = index_expr[0]
            
            if var_type == "array":
                # Check dimension
                if len(var_metadata["dimensions"]) != 1:
                    raise TypeError(
                        f"[ForLoop] Only one-dimensional arrays can be iterated over. "
                        f"Got {len(var_metadata['dimensions'])}D array."
                    )
                
                # Get the sliced portion of the array
                indices = parse_index_set(index_expr, len(var_metadata["data"]), self.variables)
                values = [var_metadata["data"][i] for i in indices]
                return values
            
            elif var_type == "bit":
                # Bit slicing
                size = var_metadata.get("size", 32)
                value = var_metadata.get("value", 0)
                
                # Parse the range
                if type(index_expr).__name__ in ('RangeDefinition', 'RangeExpression'):
                    start = eval_param(index_expr.start, self.variables) if index_expr.start else 0
                    end = eval_param(index_expr.end, self.variables) if index_expr.end else (size - 1)
                    step = eval_param(index_expr.step, self.variables) if hasattr(index_expr, 'step') and index_expr.step else 1
                    
                    indices = expand_range(int(start), int(step), int(end), size)
                    
                    # Extract bits
                    values = []
                    for bit_index in indices:
                        bit_value = (value >> bit_index) & 1
                        values.append(bit_value)
                    return values
                else:
                    # Single index - create single element list
                    idx = int(eval_param(index_expr, self.variables))
                    bit_value = (value >> idx) & 1
                    return [bit_value]
            
            else:
                raise TypeError(f"[ForLoop] Cannot iterate over indexed '{var_type}'")
        
        else:
            raise ValueError(f"[ForLoop] Unsupported set declaration type: {set_type}")

        
    def visit_BranchingStatement(self, node):
        """
        Handles if-else statements.

        * Conditions that depend on mid-circuit measurement results (feed-forward,
          e.g. teleportation corrections) become classically-controlled Cirq
          operations evaluated per shot by the simulator.
        * Purely classical conditions are evaluated at circuit-construction time.
        """
        if self._condition_reads_measured_bits(node.condition):
            return self._visit_dynamic_branch(node)

        try:
            condition = eval_param(node.condition, self.variables)
        except Exception as e:
            raise ValueError(f"[BranchingStatement] Failed to evaluate condition: {e}")

        if condition:
            if hasattr(node, 'if_block') and node.if_block:
                self._execute_block(node.if_block, context="static")
            elif hasattr(node, 'true_branch') and node.true_branch:
                self._execute_block(node.true_branch, context="static")
        else:
            if hasattr(node, 'else_block') and node.else_block:
                self._execute_block(node.else_block, context="static")
            elif hasattr(node, 'false_branch') and node.false_branch:
                self._execute_block(node.false_branch, context="static")
        return None

    # ------------------------------------------------------------------
    # Feed-forward (measurement-dependent) control flow
    # ------------------------------------------------------------------
    def _bit_reference(self, expr):
        """Return (register, index or None) if expr names a classical bit/register."""
        etype = type(expr).__name__
        if etype == 'Identifier' and expr.name in self.clbits:
            return expr.name, None
        if etype == 'IndexExpression':
            coll = expr.collection
            if type(coll).__name__ == 'Identifier' and coll.name in self.clbits:
                idx = expr.index
                if isinstance(idx, list):
                    if len(idx) != 1:
                        raise ValueError("[BranchingStatement] Only single-bit indexing is supported in conditions.")
                    idx = idx[0]
                return coll.name, int(eval_param(idx, self.variables))
        if etype == 'IndexedIdentifier':
            name = expr.name.name if hasattr(expr.name, 'name') else expr.name
            if name in self.clbits and expr.indices:
                idx = expr.indices[0]
                if isinstance(idx, list):
                    idx = idx[0]
                return name, int(eval_param(idx, self.variables))
        return None

    def _condition_reads_measured_bits(self, expr):
        if expr is None:
            return False
        ref = self._bit_reference(expr)
        if ref is not None:
            reg, idx = ref
            keys = self.clbits[reg] if idx is None else [self.clbits[reg][normalize_index(idx, len(self.clbits[reg]))]]
            return any(k in self._measured_keys for k in keys)
        for attr in ('lhs', 'rhs', 'expression', 'operand'):
            child = getattr(expr, attr, None)
            if child is not None and not isinstance(child, (str, int, float)) and self._condition_reads_measured_bits(child):
                return True
        return False

    def _bit_symbol(self, reg, idx):
        import sympy
        keys = self.clbits[reg]
        idx = normalize_index(idx, len(keys))
        key = keys[idx]
        if key in self._measured_keys:
            return sympy.Symbol(key)
        info = self.variables.get(reg, {})
        value = info.get("value", 0) if isinstance(info, dict) else 0
        return sympy.Integer((int(value) >> idx) & 1)

    def _sympy_value(self, expr):
        """Translate a QASM classical expression into a sympy expression over measurement keys."""
        import sympy
        etype = type(expr).__name__
        ref = self._bit_reference(expr)
        if ref is not None:
            reg, idx = ref
            if idx is not None:
                return self._bit_symbol(reg, idx)
            # Whole register: unsigned integer, bit i has weight 2**i.
            total = sympy.Integer(0)
            for i in range(len(self.clbits[reg])):
                total = total + self._bit_symbol(reg, i) * (2 ** i)
            return total
        if etype == 'BinaryExpression':
            op = expr.op.name if hasattr(expr.op, 'name') else str(expr.op)
            lhs = self._sympy_value(expr.lhs)
            rhs = self._sympy_value(expr.rhs)
            if op == '==':
                return sympy.Eq(lhs, rhs)
            if op == '!=':
                return sympy.Ne(lhs, rhs)
            if op == '<':
                return sympy.Lt(lhs, rhs)
            if op == '<=':
                return sympy.Le(lhs, rhs)
            if op == '>':
                return sympy.Gt(lhs, rhs)
            if op == '>=':
                return sympy.Ge(lhs, rhs)
            if op == '&&':
                return sympy.And(self._as_bool(lhs), self._as_bool(rhs))
            if op == '||':
                return sympy.Or(self._as_bool(lhs), self._as_bool(rhs))
            if op == '+':
                return lhs + rhs
            if op == '-':
                return lhs - rhs
            if op == '*':
                return lhs * rhs
            raise ValueError(f"[BranchingStatement] Operator '{op}' is not supported in a measurement-dependent condition.")
        if etype == 'UnaryExpression':
            op = expr.op.name if hasattr(expr.op, 'name') else str(expr.op)
            inner = self._sympy_value(expr.expression)
            if op == '!':
                return sympy.Not(self._as_bool(inner))
            if op == '-':
                return -inner
            raise ValueError(f"[BranchingStatement] Operator '{op}' is not supported in a measurement-dependent condition.")
        if etype == 'BooleanLiteral':
            return sympy.true if expr.value else sympy.false
        if etype == 'IntegerLiteral':
            return sympy.Integer(int(expr.value))
        if etype == 'FloatLiteral':
            return sympy.Float(expr.value)
        # Anything else must be a compile-time classical value.
        value = eval_param(expr, self.variables)
        if isinstance(value, dict) and 'value' in value:
            value = value['value']
        if isinstance(value, bool):
            return sympy.true if value else sympy.false
        return sympy.sympify(value)

    @staticmethod
    def _as_bool(value):
        import sympy
        if isinstance(value, (sympy.logic.boolalg.Boolean, sympy.core.relational.Relational)):
            return value
        return sympy.Ne(value, 0)

    def _collect_block_ops(self, block):
        """Run a block into a scratch circuit and return its operations."""
        saved_circuit = self.circuit
        saved_flag = self._in_dynamic_block
        self.circuit = cirq.Circuit()
        self._in_dynamic_block = True
        try:
            self._execute_block(block, context="dynamic")
            return list(self.circuit.all_operations())
        finally:
            self.circuit = saved_circuit
            self._in_dynamic_block = saved_flag

    def _visit_dynamic_branch(self, node):
        import sympy
        condition = self._as_bool(self._sympy_value(node.condition))
        if_block = getattr(node, 'if_block', None) or getattr(node, 'true_branch', None)
        else_block = getattr(node, 'else_block', None) or getattr(node, 'false_branch', None)

        branches = [(if_block, condition)]
        if else_block:
            branches.append((else_block, sympy.Not(condition)))

        for block, cond in branches:
            if not block:
                continue
            ops = self._collect_block_ops(block)
            if cond == sympy.true:
                self.circuit.append(ops)
                continue
            if cond == sympy.false:
                continue
            sympy_condition = cirq.SympyCondition(cond)
            for op in ops:
                self.circuit.append(op.with_classical_controls(sympy_condition))
        return None

    def _condition_has_measurement(self, condition_expr):
        """
        Check if a condition expression involves measurement results.
        
        This checks if any variable in the condition was assigned from a measurement.
        """
        if condition_expr is None:
            return False
        
        # Check if condition references a bit variable that was assigned from measurement
        if hasattr(condition_expr, 'name'):
            var_name = condition_expr.name
            if var_name in self.variables:
                var_info = self.variables[var_name]
                # Check if this variable was assigned from a measurement
                if var_info.get('from_measurement', False):
                     
                    return True
            elif var_name in self.clbits:
                # Classical bit registers could be from measurements
                # Check if the variable metadata marks it as from measurement
                if var_name in self.variables and self.variables[var_name].get('from_measurement', False):
                     
                    return True
        
        # Check IndexExpression (e.g., m[0] == 1)
        if hasattr(condition_expr, 'collection'):
            return self._condition_has_measurement(condition_expr.collection)
        
        # Recursively check binary expressions
        if hasattr(condition_expr, 'lhs') and hasattr(condition_expr, 'rhs'):
            return (self._condition_has_measurement(condition_expr.lhs) or 
                    self._condition_has_measurement(condition_expr.rhs))
        
        # Check unary expressions
        if hasattr(condition_expr, 'expression'):
            return self._condition_has_measurement(condition_expr.expression)
        
        return False


    def _execute_block(self, block, allow_declarations=True, allow_aliases=True, context="static"):
        """
        Execute a block of statements with proper variable scoping.
        
        Args:
            block: A block containing statements to execute
            allow_declarations: Whether to allow classical declarations
            allow_aliases: Whether to allow alias statements
            context: "static" or "dynamic" - controls validation
        """
        if block is None:
            return
        
        # Get statements from block
        statements = []
        if isinstance(block, list):
            statements = block
        elif hasattr(block, '_statements'):
            statements = block._statements
        elif hasattr(block, 'statements'):
            statements = block.statements
        else:
            # Try to iterate
            try:
                statements = list(block)
            except (TypeError, AttributeError):
                 
                return
        
        # Create new scope for this block - stores (var_name, saved_value) tuples
        self.scope_stack.append({})
         
        
        try:
            # Execute each statement
            for statement in statements:
                # Check for break or continue
                if hasattr(self, '_loop_break') and self._loop_break:
                     
                    break
                if hasattr(self, '_loop_continue') and self._loop_continue:
                     
                    break
                
                statement_type = type(statement).__name__
                
                # Validate statement type based on context
                if context == "dynamic":
                    if statement_type in ('ClassicalDeclaration', 'ConstantDeclaration') and not allow_declarations:
                        raise ValueError(
                            f"[ExecuteBlock] Classical declarations not allowed in dynamic control blocks."
                        )
                    
                    if statement_type == 'AliasStatement' and not allow_aliases:
                        raise ValueError(
                            f"[ExecuteBlock] Alias statements not allowed in dynamic control blocks."
                        )
                    
                    if statement_type in ('QuantumMeasurementStatement', 'QuantumMeasurementAssignment'):
                        raise ValueError(
                            f"[ExecuteBlock] Only quantum operations that contain no measurements "
                            f"can be applied conditionally."
                        )
                    
                    if statement_type == 'BranchingStatement':
                        if self._condition_has_measurement(statement.condition):
                            raise ValueError(
                                f"[ExecuteBlock] Nested dynamic control blocks are not allowed."
                            )
                
                visitor_method = f"visit_{statement_type}"
                
                if hasattr(self, visitor_method):
                    try:
                        getattr(self, visitor_method)(statement)
                    except ProgramTermination:
                        raise
        
        finally:
            # Exit scope - restore or remove variables
            scope_vars = self.scope_stack.pop()
             
            
            for var_name, saved_value in scope_vars.items():
                if saved_value is None:
                    # Variable was newly declared in this scope - remove it
                    if var_name in self.variables:
                         
                        del self.variables[var_name]
                    if var_name in self.clbits:
                        del self.clbits[var_name]
                else:
                    # Variable was shadowed - restore old value
                     
                    self.variables[var_name] = saved_value



            
    def visit_ClassicalDeclaration(self, node):
        """Handles classical variable declarations"""
        typename = type(node.type).__name__
        var_name = node.identifier.name
 # Handle shadowing in nested scopes
        saved_value = None
        if self.scope_stack:
            current_scope = self.scope_stack[-1]
            # If variable already exists in outer scope, save it for restoration
            if var_name in self.variables:
                saved_value = self.variables[var_name].copy()
                 
            # Track this variable in current scope
            current_scope[var_name] = saved_value    
            if hasattr(node, 'init_expression') and node.init_expression:
                init_expr_type = type(node.init_expression).__name__
            
            # Handle array slicing ONLY if declaring an array type
            if init_expr_type == 'IndexExpression' and typename == "ArrayType":
                source_name = node.init_expression.collection.name
                if source_name in self.variables:
                    source_var = self.variables[source_name]
                    if source_var.get("type") == "array":
                        return self._handle_array_slice_declaration(node, source_var, source_name)
            
            # Handle concatenation: array[int[8], 5] concat = first ++ second;
            elif init_expr_type == 'Concatenation':
                raise NotImplementedError(
                f"[ArrayDeclaration] Array concatenation is not allowed. "
                f"Cannot declare '{var_name}' using the '++' operator."
                 )
         # Handle ArrayType Declarations
        if typename == "ArrayType":
            base_type_node = node.type.base_type
            base_type_name = type(base_type_node).__name__.replace("Type", "").lower()
            
            base_size = None
            if hasattr(base_type_node, 'size') and base_type_node.size:
                base_size = evaluate_size_expression(base_type_node.size, self.variables)

            dimensions = [evaluate_size_expression(dim, self.variables) for dim in node.type.dimensions]
            
            if len(dimensions) > 7:
                raise ValueError(f"Array '{var_name}' exceeds maximum of 7 dimensions")
                
            total_elements = np.prod(dimensions)

            default_value = self._get_default_value(base_type_name)
            flat_data = [default_value] * int(total_elements)
            
            if hasattr(node, 'init_expression') and node.init_expression:
                # Check if this is an array slice assignment (e.g., sliced = source[1:3])
                if type(node.init_expression).__name__ == 'IndexExpression':
                    source_name = node.init_expression.collection.name
                    if source_name in self.variables:
                        return self._handle_array_slice_declaration(node, self.variables[source_name], source_name)
                
                init_values = self._parse_array_initializer(node.init_expression, self.variables)
                flat_init = self._flatten_nested_list(init_values)
                
                if len(flat_init) != total_elements:
                    raise ValueError(
                        f"[ArrayDeclaration] Array '{var_name}' size mismatch: "
                        f"expected {total_elements} elements, got {len(flat_init)}"
                    )
                
                flat_data = [self._convert_to_type(val, base_type_name, base_size) for val in flat_init]

            self.variables[var_name] = {
                "type": "array",
                "base_type": base_type_name,
                "base_size": base_size,
                "dimensions": dimensions,
                "data": flat_data,
                "const": False
            }
            
             
            return var_name
        
        
        if typename == "BitType":
            size = getattr(node.type.size, "value", 1) if hasattr(node.type, "size") else 1
            
            init_value = 0
            if hasattr(node, "init_expression") and node.init_expression:
                try:
                    init_expr_value = eval_param(node.init_expression, self.variables)
                    if isinstance(init_expr_value, str):
                        init_value = parse_bit_string(init_expr_value)
                    else:
                        init_value = int(init_expr_value)
                except Exception as e:
                    if hasattr(node.init_expression, "value"):
                        val = node.init_expression.value
                        if isinstance(val, str):
                            init_value = parse_bit_string(val)
                        else:
                            init_value = int(val)
                    else:
                        raise ValueError(f"[ClassicalDeclaration] Failed to parse bit array initializer: {e}")
    
            mask = (1 << size) - 1
            init_value = init_value & mask
                
            self.variables[var_name] = {
                "type": "bit", 
                "size": size, 
                "value": init_value,
                "from_measurement": False  # Initially false, will be set by measurement
            }
            self.clbits[var_name] = [f"{var_name}_{i}" for i in range(size)]
            if not self.scope_stack and var_name not in self._declared_cregs:
                self._declared_cregs.append(var_name)

            return var_name

        elif typename in ("IntType", "UintType", "FloatType", "BoolType", "AngleType"):
            size_val = None
            if hasattr(node.type, "size"):
                size_val = evaluate_size_expression(node.type.size, self.variables)

            init_value = None
            if hasattr(node, "init_expression") and node.init_expression:
                try:
                    init_value = eval_param(node.init_expression, variables=self.variables)
                    
                    # If init_value is a dict (from accessing a variable), extract the actual value
                    if isinstance(init_value, dict) and "value" in init_value:
                        init_value = init_value["value"]
                    
                    if isinstance(init_value, tuple):
                        if init_value[0] in ("rotl", "rotr"):
                            if size_val:
                                func_name, value, shift = init_value
                                if func_name == "rotl":
                                    init_value = rotl(value, shift, size_val)
                                else:
                                    init_value = rotr(value, shift, size_val)
                            else:
                                raise ValueError(f"[ClassicalDeclaration] {init_value[0]} requires a sized type")
                        elif init_value[0] == "BITNOT":
                            _, value = init_value
                            if size_val:
                                mask = (1 << size_val) - 1
                                init_value = (~value) & mask
                            else:
                                init_value = ~value
                except Exception as e:
                    expr = node.init_expression
                    if hasattr(expr, "value"):
                        init_value = expr.value
                    elif hasattr(expr, "name") and expr.name in ("pi", "π"):
                        init_value = np.pi
                    else:
                        raise e

            if init_value is None:
                if typename == "FloatType":
                    init_value = 0.0
                elif typename == "BoolType":
                    init_value = False
                elif typename in ("IntType", "UintType", "AngleType"):
                    init_value = 0
                else:
                    init_value = 0

            if init_value is not None:
                rhs_type = None
                if isinstance(init_value, bool):
                    rhs_type = "bool"
                elif isinstance(init_value, int):
                    rhs_type = "int"
                elif isinstance(init_value, float):
                    rhs_type = "float"

                declared_type = typename.replace("Type", "").lower()

                compatible_types = {
                    "bool": ["bool"],
                    "int": ["int", "uint", "bool"],
                    "uint": ["uint", "int", "bool"],
                    "float": ["float", "int", "uint"],
                    "angle": ["angle", "float", "int", "uint"],
                }

                if rhs_type is not None:
                    allowed = rhs_type in compatible_types.get(declared_type, [])
                    if not allowed:
                        raise TypeError(
                            f"[ClassicalDeclaration] Type mismatch in declaration '{var_name}': "
                            f"declared {declared_type}, got {rhs_type}"
                        )

            if typename == "IntType":
                value = int(init_value)
                if size_val:
                    mask = (1 << size_val) - 1
                    value &= mask
                    if value >= (1 << (size_val - 1)):
                        value -= (1 << size_val)
                
                self.variables[var_name] = {"type": "int", "size": size_val, "value": value}
                 
                return var_name

            elif typename == "UintType":
                value = int(init_value)
                if size_val:
                    mask = (1 << size_val) - 1
                    value &= mask
                
                self.variables[var_name] = {"type": "uint", "size": size_val, "value": value}
                 
                return var_name

            elif typename == "FloatType":
                value = float(init_value)
                self.variables[var_name] = {"type": "float", "size": size_val, "value": value}
                 
                return var_name

            elif typename == "BoolType":
                value = bool(init_value)
                self.variables[var_name] = {"type": "bool", "size": size_val, "value": value}
                 
                return var_name

            elif typename == "AngleType":
                value = float(init_value)
                two_pi = 2 * np.pi
                normalized_value = value % two_pi
                bit_repr = None
                if size_val:
                    modulus = 1 << size_val
                    scaled = (normalized_value / two_pi) * modulus
                    bit_repr = int(round(scaled)) % modulus
                
                self.variables[var_name] = {
                    "type": "angle", "size": size_val, 
                    "value": normalized_value, "bit_repr": bit_repr
                }
                 
                return var_name

            else:
                raise ValueError(f"[ClassicalDeclaration] Unsupported classical type: {typename}")

        else:
            raise ValueError(f"[ClassicalDeclaration] Unsupported classical declaration: {node}")
                
    def _handle_array_slice_declaration(self, node, source_var, source_name):
        """Handle array slicing in declaration: arr2 = arr1[1:3];"""
        var_name = node.identifier.name
        slice_expr = node.init_expression
        
        # Parse the index/range - handle both wrapped and unwrapped index expressions
        source_size = source_var["dimensions"][0]  # For 1D arrays
        
        # The index can be wrapped in a list or be direct
        if hasattr(slice_expr, 'index'):
            index_expr = slice_expr.index
            if isinstance(index_expr, list) and len(index_expr) > 0:
                index_expr = index_expr[0]
            indices = parse_index_set(index_expr, source_size, self.variables)
        else:
            raise ValueError(f"[ArraySlice] Invalid slice expression for {var_name}")
        
        # Extract sliced data
        sliced_data = [source_var["data"][i] for i in indices]
        
        # Create new array variable
        self.variables[var_name] = {
            "type": "array",
            "base_type": source_var["base_type"],
            "base_size": source_var.get("base_size"),
            "dimensions": [len(sliced_data)],
            "data": sliced_data,
            "const": False
        }
        
         
        return var_name




    def _handle_sliced_assignment(self, node):
        """
        Handle sliced assignment: second[1:2] = first[0:1];
        This modifies elements of an existing array.
        """
        lvalue = node.lvalue
        array_name = lvalue.name.name if hasattr(lvalue.name, 'name') else lvalue.name
        
        if array_name not in self.variables:
            raise NameError(f"[SlicedAssignment] Array '{array_name}' not declared")
        
        array_metadata = self.variables[array_name]
        
        if array_metadata.get("type") != "array":
            raise TypeError(f"[SlicedAssignment] '{array_name}' is not an array")
        
        # Parse LHS slice
        lhs_indices = parse_index_set(lvalue.indices[0], array_metadata["dimensions"][0], self.variables)
        
        # Parse RHS
        rhs = node.rvalue
        if type(rhs).__name__ == 'IndexExpression':
            # RHS is also a slice
            rhs_name = rhs.collection.name
            rhs_var = self.variables[rhs_name]
            rhs_indices = parse_index_set(rhs.index[0], rhs_var["dimensions"][0], self.variables)
            rhs_data = [rhs_var["data"][i] for i in rhs_indices]
        elif type(rhs).__name__ == 'Concatenation':
            # RHS is concatenation
            rhs_data = self._evaluate_concatenation(rhs)
        else:
            raise ValueError(f"[SlicedAssignment] Unsupported RHS type")
        
        # Check size match
        if len(lhs_indices) != len(rhs_data):
            raise ValueError(
                f"[SlicedAssignment] Size mismatch: LHS has {len(lhs_indices)} elements, "
                f"RHS has {len(rhs_data)} elements"
            )
        
        # Perform assignment
        for lhs_idx, rhs_val in zip(lhs_indices, rhs_data):
            array_metadata["data"][lhs_idx] = rhs_val
        
         
        return array_name


    def _evaluate_concatenation(self, concat_expr):
        """Evaluate a concatenation expression and return the resulting data."""
        left_name = concat_expr.lhs.name if hasattr(concat_expr.lhs, 'name') else concat_expr.lhs.collection.name
        right_name = concat_expr.rhs.name if hasattr(concat_expr.rhs, 'name') else concat_expr.rhs.collection.name
        
        left_var = self.variables[left_name]
        right_var = self.variables[right_name]
        
        left_data = left_var["data"][:]
        right_data = right_var["data"][:]
        
        # Handle slicing
        if type(concat_expr.lhs).__name__ == 'IndexExpression':
            indices = parse_index_set(concat_expr.lhs.index[0], len(left_data), self.variables)
            left_data = [left_data[i] for i in indices]
        
        if type(concat_expr.rhs).__name__ == 'IndexExpression':
            indices = parse_index_set(concat_expr.rhs.index[0], len(right_data), self.variables)
            right_data = [right_data[i] for i in indices]
        
        return left_data + right_data

    def _validate_gate_body(self, statements, gate_qubits, gate_name):
        """
        Validate that gate body contains only allowed statements.
        
        Forbidden in gate bodies:
        - Classical variable declarations
        - Classical assignments to non-parameters
        - Measurements
        - Resets
        - Qubit declarations
        - Indexing of gate qubit arguments
        """
        """
        Validate that gate body contains only allowed statements.
        """
        for statement in statements:
            statement_type = type(statement).__name__
            
            # Constants are ALLOWED, but mutable variables are NOT
            if statement_type == 'ClassicalDeclaration':
                raise SyntaxError(
                    f"[GateDefinition] Gate '{gate_name}' cannot declare classical variables in a gate body. "
                    f"Use 'const' declarations instead."
                )
            
            # ConstantDeclaration is OK - constants are allowed
            # (no error for ConstantDeclaration)
            
            elif statement_type == 'ClassicalAssignment':
                raise SyntaxError(
                    f"[GateDefinition] Gate '{gate_name}' cannot assign to classical parameters in a gate body. "
                    f"Gate bodies must be purely unitary."
                )
            
            elif statement_type in ('QuantumMeasurementStatement', 'QuantumMeasurementAssignment'):
                raise SyntaxError(
                    f"[GateDefinition] Gate '{gate_name}' cannot have a non-unitary 'measure' instruction in a gate body."
                )
            
            elif statement_type == 'QuantumReset':
                raise SyntaxError(
                    f"[GateDefinition] Gate '{gate_name}' cannot have a non-unitary 'reset' instruction in a gate body."
                )
            
            elif statement_type == 'QubitDeclaration':
                raise SyntaxError(
                    f"[GateDefinition] Gate '{gate_name}': qubit declarations must be global, not in gate body."
                )
            
            # Check for indexing of gate qubit arguments in QuantumGate statements
            elif statement_type == 'QuantumGate':
                for q_arg in statement.qubits:
                    # Check if this references a gate parameter with indexing
                    if hasattr(q_arg, 'indices') and q_arg.indices:
                        qubit_name = q_arg.name if isinstance(q_arg.name, str) else q_arg.name.name
                        if qubit_name in gate_qubits:
                            raise SyntaxError(
                                f"[GateDefinition] Cannot index qubit parameter '{qubit_name}' in gate '{gate_name}'. "
                                f"Gate qubit arguments cannot be indexed within the gate body."
                            )
            
            # Recursively check nested blocks (for loops, if statements, etc.)
            if hasattr(statement, 'body'):
                body = statement.body
                nested_statements = []
                if isinstance(body, list):
                    nested_statements = body
                elif hasattr(body, '_statements'):
                    nested_statements = body._statements
                elif hasattr(body, 'statements'):
                    nested_statements = body.statements
                
                if nested_statements:
                    self._validate_gate_body(nested_statements, gate_qubits, gate_name)

            
    def visit_QuantumGateDefinition(self, node):
        """
        Handles custom gate definitions with full validation.
        """
        gate_name = node.name.name
        
        # Check if gate is being redefined (custom gate conflict)
        # NOTE: We allow redefining built-in gates with custom implementations
        if gate_name in self.STD_GATES:
          raise NameError(f"[GateDefinition] Gate '{gate_name}' is already defined (built-in gate).")
        
        # Check if gate is being redefined
        if gate_name in self.custom_gates:
            raise NameError(f"[GateDefinition] Gate '{gate_name}' is already defined.")
            
        # REMOVED: Don't prevent redefining STD_GATES
        # Users can provide their own implementation of standard gates
        # if gate_name in self.STD_GATES:
        #     raise NameError(f"[GateDefinition] Gate '{gate_name}' is already defined (built-in gate).")
        
        # Extract parameters (if any)
        gate_params = []
        if hasattr(node, 'arguments') and node.arguments:
            gate_params = [param.name if hasattr(param, 'name') else str(param) for param in node.arguments]
        
        # Extract qubit arguments
        gate_qubits = []
        if hasattr(node, 'qubits') and node.qubits:
            gate_qubits = [qubit.name if hasattr(qubit, 'name') else str(qubit) for qubit in node.qubits]
        
        # Extract body statements
        body_statements = []
        if hasattr(node, 'body') and node.body is not None:
            if isinstance(node.body, list):
                body_statements = node.body
            else:
                try:
                    body_statements = list(node.body)
                except (TypeError, AttributeError):
                    body_statements = []
        
        # Validate gate body (check for illegal statements)
        self._validate_gate_body(body_statements, gate_qubits, gate_name)
        
        # Store the gate definition
        self.custom_gates[gate_name] = {
            "params": gate_params,
            "qubits": gate_qubits,
            "body": body_statements
        }
        
         
        return None

    def _apply_custom_gate(self, gate_name, target_qubits, params):
        """
        Apply a custom gate by expanding its definition with recursion detection.
        """
        if gate_name not in self.custom_gates:
            raise NameError(f"[CustomGate] Gate '{gate_name}' is not defined")
        
        # Check for recursion
        if gate_name in self._gate_call_stack:
            raise RecursionError(
                f"[CustomGate] Recursive gate call detected: '{gate_name}' is already "
                f"in the call stack {self._gate_call_stack}"
            )
        
        gate_def = self.custom_gates[gate_name]
        
        # Validate argument count
        if len(target_qubits) != len(gate_def["qubits"]):
            raise ValueError(
                f"[CustomGate] Gate '{gate_name}' expects {len(gate_def['qubits'])} qubits, "
                f"got {len(target_qubits)}"
            )
        
        if len(params) != len(gate_def["params"]):
            raise ValueError(
                f"[CustomGate] Gate '{gate_name}' expects {len(gate_def['params'])} parameters, "
                f"got {len(params)}"
            )
        
        # Create mappings
        qubit_map = {}
        for gate_qubit_name, actual_qubit in zip(gate_def["qubits"], target_qubits):
            qubit_map[gate_qubit_name] = actual_qubit
        
        param_map = {}
        for gate_param_name, actual_param in zip(gate_def["params"], params):
            param_map[gate_param_name] = actual_param
        
        # Save current context
        saved_qubits = self.qubits.copy()
        saved_variables = self.variables.copy()
        
        # Create NEW scope for gate body - only include const globals and parameters
        # Filter out non-const globals
        gate_scope_variables = {}
        for var_name, var_data in self.variables.items():
            if var_data.get("const", False):
                # Allow const globals
                gate_scope_variables[var_name] = var_data
        
        # Replace variables with filtered scope
        self.variables = gate_scope_variables
        
        # Create temporary qubit registers for the gate body
        for gate_qubit_name, actual_qubit in qubit_map.items():
            self.qubits[gate_qubit_name] = [actual_qubit]
        
        # Add parameters to variables (as constants)
        for param_name, param_value in param_map.items():
            self.variables[param_name] = {
                "type": "angle",
                "size": None,
                "value": param_value,
                "const": True
            }
        
         
        
        # Push gate onto recursion stack
        self._gate_call_stack.append(gate_name)
        
        try:
            # Execute the gate body
            for statement in gate_def["body"]:
                statement_type = type(statement).__name__
                visitor_method = f"visit_{statement_type}"
                
                if hasattr(self, visitor_method):
                    getattr(self, visitor_method)(statement)
        finally:
            # Pop gate from recursion stack
            self._gate_call_stack.pop()
            
            # Restore context
            self.qubits = saved_qubits
            self.variables = saved_variables
            
    def visit_QuantumPhase(self, node):
        """Handle global phase (gphase) operations."""
        if not hasattr(node, "argument"):
            raise ValueError(
                f"[QuantumPhase] QuantumPhase (gphase) requires an argument (e.g., pi/2). Got: {node.__dict__}"
            )

        phase = eval_param(node.argument, self.variables)  # FIX: Add self.variables
        modifiers = getattr(node, "modifiers", None) or []
        if modifiers:
            phase, controls = self._gphase_modifier_plan(modifiers, phase, lambda a: eval_param(a, self.variables))
            qubits = []
            for q_arg in getattr(node, "qubits", None) or []:
                qubits.extend(self._resolve_operand_qubits(q_arg))
            if len(qubits) != len(controls):
                raise ValueError(f"[QuantumPhase] expected {len(controls)} control qubit(s), got {len(qubits)}")
            if controls:
                gate = cirq.ControlledGate(cirq.GlobalPhaseGate(np.exp(1j * phase)),
                                           num_controls=len(controls), control_values=controls)
                self.circuit.append(gate(*qubits))
                return None
        self.circuit.append(cirq.global_phase_operation(np.exp(1j * phase)))
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

    def _handle_custom_gate_application(self, node):
        """Handle application of custom user-defined gates."""
        gate_name = node.name.name
    
         
        
        # Check if this is a custom gate or standard gate
        # Priority: custom gates override standard gates
        if gate_name not in self.custom_gates:
            # Not a custom gate, must be standard gate
            if gate_name not in self.STD_GATES:
                raise NameError(f"[CustomGate] Gate '{gate_name}' is not defined")
            # Let standard gate handler deal with it
            return None
        
        # Parse qubit arguments
        target_qubits = []
        for q_arg in node.qubits:
            reg_name = q_arg.name if isinstance(q_arg.name, str) else q_arg.name.name
            
            if not hasattr(q_arg, "indices") or not q_arg.indices:
                # Single qubit register or direct qubit reference
                if reg_name in self.qubits:
                    if len(self.qubits[reg_name]) == 1:
                        target_qubits.append(self.qubits[reg_name][0])
                    else:
                        raise ValueError(
                            f"[CustomGate] Gate '{gate_name}' requires individual qubits. "
                            f"Register '{reg_name}' has {len(self.qubits[reg_name])} qubits."
                        )
                else:
                    raise NameError(f"[CustomGate] Qubit '{reg_name}' not found")
            else:
                # Indexed qubit
                index_expr = q_arg.indices[0]
                
                # Handle list wrapping
                if isinstance(index_expr, list):
                    index_expr = index_expr[0]
                
                index_expr_type = type(index_expr).__name__
                
                # Handle different index types
                if index_expr_type == 'UnaryExpression':
                    # Negative index
                    idx_value = eval_param(index_expr, self.variables)
                    idx = normalize_index(idx_value, len(self.qubits[reg_name]))
                else:
                    # Regular index
                    idx_value = eval_param(index_expr, self.variables)
                    idx = int(idx_value)
                    idx = normalize_index(idx, len(self.qubits[reg_name]))                
                if reg_name in self.qubits:
                    target_qubits.append(self.qubits[reg_name][idx])
                else:
                    raise NameError(f"[CustomGate] Qubit register '{reg_name}' not found")
        
        # Parse parameters
        params = []
        raw_params = []
        if hasattr(node, "parameters") and node.parameters:
            raw_params = node.parameters
        elif hasattr(node, "arguments") and node.arguments:
            raw_params = node.arguments
        
        if raw_params:
            params = [eval_param(p, variables=self.variables) for p in raw_params]
             
        
        # Apply the custom gate
        self._apply_custom_gate(gate_name, target_qubits, params)
        
        return None
    
    def _resolve_operand_qubits(self, q_arg):
        """Resolve one gate operand to a list of cirq qubits."""
        reg_name = q_arg.name if isinstance(q_arg.name, str) else q_arg.name.name
        if reg_name not in self.qubits:
            raise NameError(f"[QuantumGate] Qubit register '{reg_name}' is not declared")
        reg = self.qubits[reg_name]
        if not hasattr(q_arg, "indices") or not q_arg.indices:
            return list(reg)
        index_expr = q_arg.indices[0]
        if isinstance(index_expr, list):
            index_expr = index_expr[0]
        etype = type(index_expr).__name__
        if etype in ('RangeDefinition', 'RangeExpression', 'DiscreteSet', 'IndexSet'):
            return [reg[i] for i in parse_index_set(index_expr, len(reg), self.variables)]
        idx = normalize_index(int(eval_param(index_expr, self.variables)), len(reg))
        return [reg[idx]]

    def _handle_modified_gate(self, node, modifiers):
        """
        Handle gates with modifiers (ctrl, negctrl, inv, pow), any combination.

        OpenQASM semantics: modifiers apply right-to-left to the gate; control
        qubits come first in the operand list.  Standard gates are built from
        their exact matrices; custom gates use the legacy expansion path.
        """
        gate_name = node.name.name
        params = []
        raw = getattr(node, "arguments", None) or getattr(node, "parameters", None) or []
        if raw:
            params = [eval_param(p, self.variables) for p in raw]

        if gate_name in self.custom_gates:
            return self._handle_modified_gate_legacy(node, modifiers)

        if gate_name == 'gphase':
            base = cirq.GlobalPhaseGate(np.exp(1j * params[0]))
        else:
            base = self._base_cirq_gate(gate_name, params)
        if base is None:
            raise NotImplementedError(f"[ModifiedGate] Modifiers on gate '{gate_name}' are not supported")

        gate = base
        for modifier in reversed(modifiers):
            mod = modifier.modifier if hasattr(modifier, 'modifier') else modifier
            name = mod.name if hasattr(mod, 'name') else str(mod)
            arg = getattr(modifier, 'argument', None)
            if name in ('inv', 'InverseModifier'):
                gate = cirq.inverse(gate)
            elif name in ('pow', 'PowModifier'):
                gate = gate ** float(eval_param(arg, self.variables))
            elif name in ('ctrl', 'ControlModifier', 'negctrl', 'NegControlModifier'):
                n = int(eval_param(arg, self.variables)) if arg is not None else 1
                value = 0 if name.startswith('neg') or name.startswith('Neg') else 1
                gate = cirq.ControlledGate(gate, num_controls=n, control_values=[value] * n)
            else:
                raise NotImplementedError(f"[ModifiedGate] Modifier '{name}' not implemented")

        operands = [self._resolve_operand_qubits(q) for q in node.qubits]
        width = cirq.num_qubits(gate)
        sizes = {len(o) for o in operands if len(o) > 1}
        if len(sizes) > 1:
            raise ValueError("[ModifiedGate] Broadcast registers must have the same size")
        if not sizes:
            qubits = [o[0] for o in operands]
            if len(qubits) != width:
                raise ValueError(f"[ModifiedGate] '{gate_name}' with modifiers expects {width} qubits, got {len(qubits)}")
            self.circuit.append(gate(*qubits))
        else:
            for i in range(sizes.pop()):
                qubits = [o[i] if len(o) > 1 else o[0] for o in operands]
                self.circuit.append(gate(*qubits))
        return None

    def _handle_modified_gate_legacy(self, node, modifiers):
        """
        Legacy modifier handling (used for custom gates).
        Modifiers are applied in order from right to left.
        """
        for i in range(len(modifiers) - 1, -1, -1):
            modifier = modifiers[i]

            # Extract the actual modifier type from the modifier attribute (enum)
            if hasattr(modifier, 'modifier'):
                modifier_enum = modifier.modifier
                # Get the enum name (e.g., 'ctrl', 'negctrl', 'inv')
                modifier_name = modifier_enum.name if hasattr(modifier_enum, 'name') else str(modifier_enum)
            else:
                # Fallback to class name
                modifier_name = type(modifier).__name__

            if i > 0:
                raise NotImplementedError("[ModifiedGate] Multiple modifiers on a custom gate are not supported")
            # Map enum names to handler methods
            if modifier_name in ('ctrl', 'ControlModifier'):
                return self._apply_control_modifier(node, modifier, modifiers[:i])
            elif modifier_name in ('negctrl', 'NegControlModifier'):
                return self._apply_negcontrol_modifier(node, modifier, modifiers[:i])
            elif modifier_name in ('inv', 'InverseModifier'):
                return self._apply_inverse_modifier(node, modifiers[:i])
            else:
                raise NotImplementedError(f"[ModifiedGate] Modifier '{modifier_name}' not implemented")

        return None

    def _apply_control_modifier(self, node, ctrl_modifier, remaining_modifiers):
        """
        Apply ctrl @ gate modifier.
        
        ctrl @ gate creates a controlled gate where the first qubit(s) are controls.
        ctrl(n) @ gate means n control qubits.
        """
        gate_name = node.name.name
            
        # Get number of control qubits (default is 1)
        num_controls = 1
        if hasattr(ctrl_modifier, 'argument') and ctrl_modifier.argument:
            num_controls = int(eval_param(ctrl_modifier.argument, self.variables))
        
         
        
        # Parse all qubit arguments - track whether they're registers or single qubits
        qubit_args = []
        for q_arg in node.qubits:
            reg_name = q_arg.name if isinstance(q_arg.name, str) else q_arg.name.name
            
            if not hasattr(q_arg, "indices") or not q_arg.indices:
                # Full register
                if reg_name in self.qubits:
                    qubit_args.append({
                        "type": "register",
                        "qubits": self.qubits[reg_name],
                        "size": len(self.qubits[reg_name])
                    })
            else:
                index_expr = q_arg.indices[0]
                if isinstance(index_expr, list):
                    index_expr = index_expr[0]
                
                index_expr_type = type(index_expr).__name__
                
                if index_expr_type in ('RangeDefinition', 'RangeExpression', 'DiscreteSet', 'IndexSet'):
                    # Range or set - treat as register
                    indices = parse_index_set(index_expr, len(self.qubits[reg_name]), self.variables)
                    qubit_args.append({
                        "type": "register",
                        "qubits": [self.qubits[reg_name][i] for i in indices],
                        "size": len(indices)
                    })
                else:
                    # Single indexed qubit
                    idx_value = eval_param(index_expr, self.variables)
                    idx = int(idx_value)
                    idx = normalize_index(idx, len(self.qubits[reg_name]))
                    qubit_args.append({
                        "type": "single",
                        "qubits": [self.qubits[reg_name][idx]],
                        "size": 1
                    })
                        
        # Parse parameters
        params = []
        if hasattr(node, "arguments") and node.arguments:
            params = [eval_param(p, self.variables) for p in node.arguments]
        
        # Determine if we should broadcast or split
        # Broadcasting happens when:
        # 1. We have multiple register arguments
        # 2. They are ALL the same size
        # 3. The number of arguments matches what we expect (num_controls + 1 for control + target)
        
        registers = [arg for arg in qubit_args if arg["type"] == "register"]
        
        # Check for broadcasting condition
        should_broadcast = False
        if len(registers) > 1:
            register_sizes = [reg["size"] for reg in registers]
            # All registers same size AND all args are registers
            if len(set(register_sizes)) == 1 and len(registers) == len(qubit_args):
                # Check if we have the right number of arguments for broadcasting
                # For ctrl(n) @ gate, we need n+1 arguments minimum
                if len(qubit_args) >= num_controls + 1:
                    should_broadcast = True
        
        if should_broadcast:
            # Broadcasting mode
            broadcast_size = registers[0]["size"]
             
            
            for i in range(broadcast_size):
                # For each iteration, take the i-th qubit from each register
                all_qubits = [arg["qubits"][i] for arg in qubit_args]
                control_qubits = all_qubits[:num_controls]
                target_qubits = all_qubits[num_controls:]
                
                self._apply_controlled_gate(gate_name, control_qubits, target_qubits, params, negative=False)
            
            return None
        
        # No broadcasting - we need to interpret the arguments differently
        # The first num_controls arguments provide control qubits
        # The remaining arguments provide target qubits
        
        if len(qubit_args) < num_controls + 1:
            raise ValueError(
                f"[ControlModifier] Not enough qubit arguments: need at least {num_controls + 1} "
                f"(for {num_controls} control(s) + target(s)), got {len(qubit_args)}"
            )
        
        control_qubits = []
        target_qubits = []
        
        # Collect control qubits from first num_controls arguments
        for i in range(num_controls):
            arg = qubit_args[i]
            if arg["type"] == "register":
                # If a control argument is a register, we need all its qubits as controls
                control_qubits.extend(arg["qubits"])
            else:
                control_qubits.append(arg["qubits"][0])
        
        # Collect target qubits from remaining arguments
        for i in range(num_controls, len(qubit_args)):
            arg = qubit_args[i]
            target_qubits.extend(arg["qubits"])
        
        # Validate we have at least one target
        if len(target_qubits) == 0:
            raise ValueError(
                f"[ControlModifier] No target qubits found for controlled gate"
            )
        
        # Update num_controls if we got more control qubits than expected
        actual_num_controls = len(control_qubits)
        
         
        
        # Apply controlled gate with the actual number of controls we collected
        self._apply_controlled_gate(gate_name, control_qubits, target_qubits, params, negative=False)
        
        return None


    def _apply_negcontrol_modifier(self, node, negctrl_modifier, remaining_modifiers):
        """
        Apply negctrl @ gate modifier.
        
        negctrl @ gate creates a negative controlled gate (controlled on |0⟩).
        """
        gate_name = node.name.name
        
        # Get number of control qubits (default is 1)
        num_controls = 1
        if hasattr(negctrl_modifier, 'argument') and negctrl_modifier.argument:
            num_controls = int(eval_param(negctrl_modifier.argument, self.variables))
        
         
        
        # Parse all qubit arguments - track whether they're registers or single qubits
        qubit_args = []
        for q_arg in node.qubits:
            reg_name = q_arg.name if isinstance(q_arg.name, str) else q_arg.name.name
            
            if not hasattr(q_arg, "indices") or not q_arg.indices:
                # Full register
                if reg_name in self.qubits:
                    qubit_args.append({
                        "type": "register",
                        "qubits": self.qubits[reg_name],
                        "size": len(self.qubits[reg_name])
                    })
            else:
                index_expr = q_arg.indices[0]
                if isinstance(index_expr, list):
                    index_expr = index_expr[0]
                
                index_expr_type = type(index_expr).__name__
                
                if index_expr_type in ('RangeDefinition', 'RangeExpression', 'DiscreteSet', 'IndexSet'):
                    # Range or set - treat as register
                    indices = parse_index_set(index_expr, len(self.qubits[reg_name]), self.variables)
                    qubit_args.append({
                        "type": "register",
                        "qubits": [self.qubits[reg_name][i] for i in indices],
                        "size": len(indices)
                    })
                else:
                    # Single indexed qubit
                    idx_value = eval_param(index_expr, self.variables)
                    idx = int(idx_value)
                    idx = normalize_index(idx, len(self.qubits[reg_name]))
                    qubit_args.append({
                        "type": "single",
                        "qubits": [self.qubits[reg_name][idx]],
                        "size": 1
                    })
        
        # Parse parameters
        params = []
        if hasattr(node, "arguments") and node.arguments:
            params = [eval_param(p, self.variables) for p in node.arguments]
        
        # Determine if we should broadcast or split
        registers = [arg for arg in qubit_args if arg["type"] == "register"]
        
        # Check for broadcasting condition
        should_broadcast = False
        if len(registers) > 1:
            register_sizes = [reg["size"] for reg in registers]
            if len(set(register_sizes)) == 1 and len(registers) == len(qubit_args):
                if len(qubit_args) >= num_controls + 1:
                    should_broadcast = True
        
        if should_broadcast:
            # Broadcasting mode
            broadcast_size = registers[0]["size"]
             
            
            for i in range(broadcast_size):
                all_qubits = [arg["qubits"][i] for arg in qubit_args]
                control_qubits = all_qubits[:num_controls]
                target_qubits = all_qubits[num_controls:]
                
                self._apply_controlled_gate(gate_name, control_qubits, target_qubits, params, negative=True)
            
            return None
        
        # No broadcasting - interpret arguments as control args + target args
        if len(qubit_args) < num_controls + 1:
            raise ValueError(
                f"[NegControlModifier] Not enough qubit arguments: need at least {num_controls + 1}, got {len(qubit_args)}"
            )
        
        control_qubits = []
        target_qubits = []
        
        # Collect control qubits from first num_controls arguments
        for i in range(num_controls):
            arg = qubit_args[i]
            if arg["type"] == "register":
                control_qubits.extend(arg["qubits"])
            else:
                control_qubits.append(arg["qubits"][0])
        
        # Collect target qubits from remaining arguments
        for i in range(num_controls, len(qubit_args)):
            arg = qubit_args[i]
            target_qubits.extend(arg["qubits"])
        
        if len(target_qubits) == 0:
            raise ValueError(
                f"[NegControlModifier] No target qubits found"
            )
        
         
        
        # Apply negative controlled gate
        self._apply_controlled_gate(gate_name, control_qubits, target_qubits, params, negative=True)
        
        return None
    
    def _apply_controlled_custom_gate(self, gate_name, control_qubits, target_qubits, params, negative=False):
        """
        Apply a controlled custom gate by expanding its definition with controls.
        
        This works by recursively applying control modifiers to each gate in the custom gate's body.
        """
        if gate_name not in self.custom_gates:
            raise NameError(f"[ControlledCustomGate] Gate '{gate_name}' is not defined")
        
        gate_def = self.custom_gates[gate_name]
        
        # Validate arguments
        if len(target_qubits) != len(gate_def["qubits"]):
            raise ValueError(
                f"[ControlledCustomGate] Gate '{gate_name}' expects {len(gate_def['qubits'])} qubits, "
                f"got {len(target_qubits)}"
            )
        
        if len(params) != len(gate_def["params"]):
            raise ValueError(
                f"[ControlledCustomGate] Gate '{gate_name}' expects {len(gate_def['params'])} parameters, "
                f"got {len(params)}"
            )
        
        # Create mappings
        qubit_map = dict(zip(gate_def["qubits"], target_qubits))
        param_map = dict(zip(gate_def["params"], params))
        
        # Save context
        saved_qubits = self.qubits.copy()
        saved_variables = self.variables.copy()
        
        # Create temporary qubit registers
        for gate_qubit_name, actual_qubit in qubit_map.items():
            self.qubits[gate_qubit_name] = [actual_qubit]
        
        # Add control qubits to context
        control_register_name = f"__ctrl_{gate_name}"
        self.qubits[control_register_name] = control_qubits
        
        # Add parameters to variables
        for param_name, param_value in param_map.items():
            self.variables[param_name] = {
                "type": "angle",
                "size": None,
                "value": param_value,
                "const": True
            }
        
         
        
        # Execute the gate body with control context
        # We need to apply controls to each gate in the body
        for statement in gate_def["body"]:
            statement_type = type(statement).__name__
            
            if statement_type == "QuantumGate":
                # Apply control modifier to this gate
                # We'll temporarily inject the control into the statement processing
                inner_gate_name = statement.name.name
                
                # Parse the gate's qubits
                inner_target_qubits = []
                for q_arg in statement.qubits:
                    reg_name = q_arg.name if isinstance(q_arg.name, str) else q_arg.name.name
                    if reg_name in self.qubits:
                        if not hasattr(q_arg, "indices") or not q_arg.indices:
                            inner_target_qubits.extend(self.qubits[reg_name])
                        else:
                            idx = get_index_value(q_arg.indices[0])
                            inner_target_qubits.append(self.qubits[reg_name][idx])
                
                # Parse parameters
                inner_params = []
                if hasattr(statement, "arguments") and statement.arguments:
                    inner_params = [eval_param(p, self.variables) for p in statement.arguments]
                
                # Apply the controlled version
                self._apply_controlled_gate(inner_gate_name, control_qubits, inner_target_qubits, inner_params, negative)
            
            elif statement_type == "QuantumPhase":
                # For gphase in custom gate body, apply controlled version
                phase = eval_param(statement.argument, self.variables)
                # ctrl @ gphase = rz on control qubits
                for ctrl in control_qubits:
                    self.circuit.append(cirq.rz(phase)(ctrl))
            
            else:
                # For other statement types, process normally
                visitor_method = f"visit_{statement_type}"
                if hasattr(self, visitor_method):
                    getattr(self, visitor_method)(statement)
        
        # Restore context
        self.qubits = saved_qubits
        self.variables = saved_variables


    @staticmethod
    def _base_cirq_gate(gate_name, params):
        """
        Exact cirq.Gate for an OpenQASM standard gate (matrix identical to the
        stdgates.inc definition, including phase, so controlled versions are right).
        Returns None for unknown names.
        """
        params = list(params or [])
        fixed = {
            "id": cirq.I, "x": cirq.X, "y": cirq.Y, "z": cirq.Z, "h": cirq.H,
            "s": cirq.S, "sdg": cirq.S ** -1, "t": cirq.T, "tdg": cirq.T ** -1,
            "sx": cirq.XPowGate(exponent=0.5),
            "cx": cirq.CNOT, "CX": cirq.CNOT, "cy": cirq.ControlledGate(cirq.Y), "cz": cirq.CZ,
            "ch": cirq.ControlledGate(cirq.H), "swap": cirq.SWAP, "iswap": cirq.ISWAP,
            "sqrtiswap": cirq.SQRT_ISWAP, "ccx": cirq.CCX, "ccz": cirq.CCZ, "cswap": cirq.CSWAP,
        }
        if gate_name in fixed:
            return fixed[gate_name]
        if gate_name in ("rx", "ry", "rz") and len(params) == 1:
            return {"rx": cirq.rx, "ry": cirq.ry, "rz": cirq.rz}[gate_name](params[0])
        if gate_name in ("p", "phase", "u1") and len(params) == 1:
            return cirq.ZPowGate(exponent=params[0] / np.pi)
        if gate_name in ("cp", "cphase", "cu1") and len(params) == 1:
            return cirq.CZPowGate(exponent=params[0] / np.pi)
        if gate_name in ("crx", "cry", "crz") and len(params) == 1:
            return cirq.ControlledGate({"crx": cirq.rx, "cry": cirq.ry, "crz": cirq.rz}[gate_name](params[0]))
        if gate_name in ("U", "u", "u3") and len(params) == 3:
            return cirq.MatrixGate(_u_matrix(*params))
        if gate_name == "u2" and len(params) == 2:
            return cirq.MatrixGate(_u_matrix(np.pi / 2, params[0], params[1]))
        if gate_name == "cu3" and len(params) == 3:
            return cirq.ControlledGate(cirq.MatrixGate(_u_matrix(*params)))
        if gate_name == "cu" and len(params) == 4:
            return cirq.ControlledGate(cirq.MatrixGate(np.exp(1j * params[3]) * _u_matrix(*params[:3])))
        if gate_name in ("rzz", "rxx", "ryy") and len(params) == 1:
            cls = {"rzz": cirq.ZZPowGate, "rxx": cirq.XXPowGate, "ryy": cirq.YYPowGate}[gate_name]
            return cls(exponent=params[0] / np.pi, global_shift=-0.5)
        return None

    def _apply_controlled_gate(self, gate_name, control_qubits, target_qubits, params, negative=False):
        """
        Apply ctrl @ / negctrl @ <gate> with any number of control qubits.

        Uses the exact base-gate matrix wrapped in cirq.ControlledGate, so phases
        of the base gate are controlled correctly.
        """
        num_controls = len(control_qubits)
        control_values = [0 if negative else 1] * num_controls

        if gate_name in self.custom_gates:
            # Handle controlled custom gates by expanding with control context
            if negative:
                for ctrl in control_qubits:
                    self.circuit.append(cirq.X(ctrl))
            self._apply_controlled_custom_gate(gate_name, control_qubits, target_qubits, params, negative)
            if negative:
                for ctrl in control_qubits:
                    self.circuit.append(cirq.X(ctrl))
            return

        if gate_name == 'gphase':
            if len(params) != 1:
                raise ValueError("[ControlledGate] gphase requires 1 parameter.")
            # ctrl @ gphase(a): phase e^{ia} when all controls are satisfied.
            phase = cirq.ZPowGate(exponent=params[0] / np.pi)
            if negative:
                for ctrl in control_qubits:
                    self.circuit.append(cirq.X(ctrl))
            if num_controls == 1:
                self.circuit.append(phase(control_qubits[0]))
            else:
                self.circuit.append(cirq.ControlledGate(phase, num_controls=num_controls - 1)(*control_qubits))
            if negative:
                for ctrl in control_qubits:
                    self.circuit.append(cirq.X(ctrl))
            return

        base = self._base_cirq_gate(gate_name, params)
        if base is None:
            raise NotImplementedError(
                f"[ControlledGate] Controlled version of gate '{gate_name}' not implemented"
            )
        width = cirq.num_qubits(base)
        controlled = cirq.ControlledGate(base, num_controls=num_controls, control_values=control_values)
        if len(target_qubits) == width:
            self.circuit.append(controlled(*control_qubits, *target_qubits))
        elif width == 1 and len(target_qubits) > 1:
            # Broadcast a single-qubit base gate over several targets.
            for tgt in target_qubits:
                self.circuit.append(controlled(*control_qubits, tgt))
        else:
            raise ValueError(
                f"[ControlledGate] '{gate_name}' expects {width} target qubit(s), got {len(target_qubits)}."
            )

    def _apply_inverse_modifier(self, node, remaining_modifiers):
        """
        Apply inv @ gate modifier.
        
        The inverse is computed by:
        - For U(θ, φ, λ): inv @ U = U(-θ, -λ, -φ)
        - For gphase(a): inv @ gphase = gphase(-a)
        - For other gates: apply the gate with inverse flag
        """
        gate_name = node.name.name
        
         
        
        # Parse qubits
        target_qubits = []
        for q_arg in node.qubits:
            reg_name = q_arg.name if isinstance(q_arg.name, str) else q_arg.name.name
            
            if not hasattr(q_arg, "indices") or not q_arg.indices:
                if reg_name in self.qubits:
                    if len(self.qubits[reg_name]) == 1:
                        target_qubits.append(self.qubits[reg_name][0])
                    else:
                        target_qubits.extend(self.qubits[reg_name])
            else:
                # FIX: Handle index parsing properly
                index_expr = q_arg.indices[0]
                
                # Unwrap list if needed
                if isinstance(index_expr, list):
                    if len(index_expr) > 0:
                        index_expr = index_expr[0]
                    else:
                        raise ValueError(f"[InverseModifier] Empty index list for qubit '{reg_name}'")
                
                # Evaluate the index
                idx_value = eval_param(index_expr, self.variables)
                idx = int(idx_value)
                idx = normalize_index(idx, len(self.qubits[reg_name]))
                target_qubits.append(self.qubits[reg_name][idx])
        
        # Parse parameters
        params = []
        if hasattr(node, "arguments") and node.arguments:
            params = [eval_param(p, self.variables) for p in node.arguments]
        
        # Apply inverse transformation based on gate type
        if gate_name in ('U', 'u') and len(params) == 3:
            # inv @ U(θ, φ, λ) = U(-θ, -λ, -φ)
            theta, phi, lam = params
            inv_params = [-theta, -lam, -phi]
            self._apply_gate('U', target_qubits, inv_params)
        elif gate_name == 'gphase' and len(params) == 1:
            # inv @ gphase(a) = gphase(-a)
            angle = params[0]
            self._apply_gate('gphase', target_qubits, [-angle])
        elif gate_name in ('rx', 'ry', 'rz') and len(params) == 1:
            # inv @ R(θ) = R(-θ)
            angle = params[0]
            self._apply_gate(gate_name, target_qubits, [-angle])
        elif gate_name in ('s', 't'):
            # Use sdg and tdg for inverse
            inv_gate = {'s': 'sdg', 't': 'tdg'}
            self._apply_gate(inv_gate[gate_name], target_qubits, [])
        elif gate_name in ('sdg', 'tdg'):
            # Inverse of inverse is original
            orig_gate = {'sdg': 's', 'tdg': 't'}
            self._apply_gate(orig_gate[gate_name], target_qubits, [])
        elif gate_name in ('x', 'y', 'z', 'h', 'cx', 'swap'):
            # Self-inverse gates
            self._apply_gate(gate_name, target_qubits, params)
        else:
            # For custom gates or unknown gates
            raise NotImplementedError(
                f"[InverseModifier] Inverse of gate '{gate_name}' not implemented"
            )
        
        return None
    def visit_QuantumGate(self, node):
        """Handles quantum gate applications with broadcasting support."""
        gate_name = node.name.name
        
        # Check for modifiers
        modifiers = []
        if hasattr(node, 'modifiers') and node.modifiers:
            modifiers = node.modifiers
        
        # If there are modifiers, handle them
        if modifiers:
            return self._handle_modified_gate(node, modifiers)
        
        # PRIORITY: Check custom gates FIRST (they can override standard gates)
        if gate_name in self.custom_gates:
            return self._handle_custom_gate_application(node)
        
        # Check standard gates (only if not custom)
        if gate_name in self.STD_GATES and not self.STD_GATES_ALLOWED:
            raise PermissionError(f"Standard gate '{gate_name}' used without including stdgates.qasm")

         
        # Parse all qubit arguments and separate indexed vs full registers
        qubit_args = []
        for q_arg in node.qubits:
            reg_name = q_arg.name if isinstance(q_arg.name, str) else q_arg.name.name
            
            if not hasattr(q_arg, "indices") or not q_arg.indices:
                # Full register - store as list of qubits with metadata
                if reg_name in self.qubits:
                    qubit_args.append({
                        "type": "register",
                        "name": reg_name,
                        "qubits": self.qubits[reg_name],
                        "size": len(self.qubits[reg_name])
                    })
            else:
                # Has indices - check what type
                index_expr = q_arg.indices[0]
                
                # Check if it's a list wrapper
                if isinstance(index_expr, list):
                    index_expr = index_expr[0]
                
                index_expr_type = type(index_expr).__name__
                
                if index_expr_type in ('RangeDefinition', 'RangeExpression'):
                    # This is a range like q[1:3]
                    if reg_name in self.qubits:
                        indices = parse_index_set(index_expr, len(self.qubits[reg_name]), self.variables)
                        selected_qubits = [self.qubits[reg_name][i] for i in indices]
                        qubit_args.append({
                            "type": "register",
                            "name": reg_name,
                            "qubits": selected_qubits,
                            "size": len(selected_qubits)
                        })
                elif index_expr_type in ('DiscreteSet', 'IndexSet'):
                    # This is a discrete set like q[{0, 2, 4}]
                    if reg_name in self.qubits:
                        indices = parse_index_set(index_expr, len(self.qubits[reg_name]), self.variables)
                        selected_qubits = [self.qubits[reg_name][i] for i in indices]
                        qubit_args.append({
                            "type": "register",
                            "name": reg_name,
                            "qubits": selected_qubits,
                            "size": len(selected_qubits)
                        })
                elif index_expr_type == 'UnaryExpression':
                    # This might be a negative index like reg[-1]
                    if reg_name in self.qubits:
                        # Evaluate the expression to get the actual index
                        idx_value = eval_param(index_expr, self.variables)
                        # Normalize negative indices
                        idx = normalize_index(idx_value, len(self.qubits[reg_name]))
                        qubit_args.append({
                            "type": "single",
                            "name": reg_name,
                            "qubits": [self.qubits[reg_name][idx]],
                            "size": 1
                        })
                else:
                    # Single indexed qubit (IntegerLiteral, Identifier, etc.)
                    if reg_name in self.qubits:
                        # Evaluate the index expression to handle variables
                        idx_value = eval_param(index_expr, self.variables)
                        idx = int(idx_value)
                        # Normalize in case it's negative
                        idx = normalize_index(idx, len(self.qubits[reg_name]))
                        qubit_args.append({
                            "type": "single",
                            "name": reg_name,
                            "qubits": [self.qubits[reg_name][idx]],
                            "size": 1
                        })

        # Check for broadcasting: find all registers and verify they have the same size
        registers = [arg for arg in qubit_args if arg["type"] == "register"]
        
        if registers:
            # Verify all registers have the same size
            register_sizes = [reg["size"] for reg in registers]
            if len(set(register_sizes)) > 1:
                register_names = [reg["name"] for reg in registers]
                raise ValueError(
                    f"[QuantumGate] Broadcasting error: registers {register_names} have different sizes {register_sizes}. "
                    f"All register arguments must have the same length."
                )
            
            # Broadcast over the register size
            broadcast_size = register_sizes[0]
             
            
            # Evaluate parameters once (they're the same for all broadcasts)
            params = []
            raw_params = []
            if hasattr(node, "parameters") and node.parameters:
                raw_params = node.parameters
            elif hasattr(node, "arguments") and node.arguments:
                raw_params = node.arguments
            
            if raw_params:
                params = [eval_param(p, variables=self.variables) for p in raw_params]
                 
            
            # Apply gate for each broadcast iteration
            for i in range(broadcast_size):
                target_qubits = []
                for arg in qubit_args:
                    if arg["type"] == "register":
                        # Take the i-th qubit from the register
                        target_qubits.append(arg["qubits"][i])
                    else:
                        # Single qubit - same for all iterations
                        target_qubits.append(arg["qubits"][0])
                
                 
                self._apply_gate(gate_name, target_qubits, params)
        else:
            # No broadcasting - just collect all qubits and apply once
            target_qubits = []
            for arg in qubit_args:
                target_qubits.extend(arg["qubits"])
            
             
            
            # Evaluate parameters
            params = []
            raw_params = []
            if hasattr(node, "parameters") and node.parameters:
                raw_params = node.parameters
            elif hasattr(node, "arguments") and node.arguments:
                raw_params = node.arguments
            
            if raw_params:
                params = [eval_param(p, variables=self.variables) for p in raw_params]
                 
            
            self._apply_gate(gate_name, target_qubits, params)

        return None
    def _apply_gate(self, gate_name, target_qubits, params):
        """Apply a gate to specific qubits with given parameters."""
        if gate_name in ("h", "x", "y", "z", "s", "sdg", "t", "tdg", "id", "sx"):
            gate_map = {"h": cirq.H, "x": cirq.X, "y": cirq.Y, "z": cirq.Z, 
                        "s": cirq.S, "t": cirq.T, "id": cirq.I, "sx": cirq.XPowGate(exponent=0.5)}
            if gate_name == "sdg":
                for q in target_qubits:
                    self.circuit.append(cirq.S(q)**-1)
            elif gate_name == "tdg":
                for q in target_qubits:
                    self.circuit.append(cirq.T(q)**-1)
            else:
                for q in target_qubits:
                    self.circuit.append(gate_map[gate_name](q))
        
        elif gate_name in ("U", "u", "u3", "u2", "u1"):
            # OpenQASM U(theta, phi, lambda) =
            #   [[cos(t/2), -e^{i l} sin(t/2)], [e^{i p} sin(t/2), e^{i(p+l)} cos(t/2)]]
            expected = {"U": 3, "u": 3, "u3": 3, "u2": 2, "u1": 1}[gate_name]
            if len(params) != expected:
                raise ValueError(f"Gate '{gate_name}' requires {expected} parameter(s).")
            if gate_name == "u2":
                theta, phi, lam = np.pi / 2, params[0], params[1]
            elif gate_name == "u1":
                theta, phi, lam = 0.0, 0.0, params[0]
            else:
                theta, phi, lam = params
            gate = cirq.MatrixGate(_u_matrix(theta, phi, lam))
            for q in target_qubits:
                self.circuit.append(gate(q))

        elif gate_name in ("crx", "cry", "crz"):
            if len(target_qubits) != 2:
                raise ValueError(f"Gate '{gate_name}' requires 2 qubits.")
            if not params:
                raise ValueError(f"Gate '{gate_name}' requires 1 parameter.")
            
            angle = params[0]
            control, target = target_qubits[0], target_qubits[1]
            
            if gate_name == "crx":
                self.circuit.append(cirq.ControlledGate(cirq.rx(angle))(control, target))
            elif gate_name == "cry":
                self.circuit.append(cirq.ControlledGate(cirq.ry(angle))(control, target))
            elif gate_name == "crz":
                self.circuit.append(cirq.ControlledGate(cirq.rz(angle))(control, target))
        
        elif gate_name in ("rx", "ry", "rz", "gphase"):
            if not params:
                raise ValueError(f"Gate '{gate_name}' requires 1 parameter.")
            angle = params[0]
            
            if gate_name == "gphase":
                # Global phase gate
                self.circuit.append(cirq.global_phase_operation(np.exp(1j * angle)))
            else:
                # Rotation gates
                gate_map = {"rx": cirq.rx, "ry": cirq.ry, "rz": cirq.rz}
                for q in target_qubits:
                    self.circuit.append(gate_map[gate_name](angle)(q))

        elif gate_name in ("cx", "cy", "cz", "ch", "swap", "iswap"):
            if len(target_qubits) != 2:
                raise ValueError(f"Gate '{gate_name}' requires 2 qubits.")
            q0, q1 = target_qubits[0], target_qubits[1]
            gate_map = {"cx": cirq.CNOT, "cz": cirq.CZ, "swap": cirq.SWAP, "iswap": cirq.ISWAP}
            if gate_name == "cy":
                self.circuit.append(cirq.ControlledGate(cirq.Y)(q0, q1))
            elif gate_name == "ch":
                self.circuit.append(cirq.ControlledGate(cirq.H)(q0, q1))
            else:
                self.circuit.append(gate_map[gate_name](q0, q1))
        
        elif gate_name == "cp":
            # Controlled phase gate
            if len(target_qubits) != 2:
                raise ValueError(f"Gate 'cp' requires 2 qubits.")
            if not params:
                raise ValueError(f"Gate 'cp' requires 1 parameter.")
            
            angle = params[0]
            control, target = target_qubits[0], target_qubits[1]
            self.circuit.append(cirq.CZPowGate(exponent=angle/np.pi)(control, target))

        elif gate_name in ("ccx", "cswap"):
            if len(target_qubits) != 3:
                raise ValueError(f"Gate '{gate_name}' requires 3 qubits.")
            q0, q1, q2 = target_qubits[0], target_qubits[1], target_qubits[2]
            if gate_name == "ccx":
                self.circuit.append(cirq.CCX(q0, q1, q2))
            else:
                self.circuit.append(cirq.CSWAP(q0, q1, q2))
        
        elif gate_name == "CX":
            # Uppercase CX (same as cx/CNOT)
            if len(target_qubits) != 2:
                raise ValueError(f"Gate 'CX' requires 2 qubits.")
            self.circuit.append(cirq.CNOT(target_qubits[0], target_qubits[1]))

        elif gate_name in ("p", "phase"):
            if not params:
                raise ValueError(f"Gate '{gate_name}' requires 1 parameter.")
            for q in target_qubits:
                self.circuit.append(cirq.ZPowGate(exponent=params[0] / np.pi)(q))

        elif gate_name in ("cphase", "cu1"):
            if len(target_qubits) != 2 or not params:
                raise ValueError(f"Gate '{gate_name}' requires 2 qubits and 1 parameter.")
            self.circuit.append(cirq.CZPowGate(exponent=params[0] / np.pi)(target_qubits[0], target_qubits[1]))

        elif gate_name == "ccz":
            if len(target_qubits) != 3:
                raise ValueError("Gate 'ccz' requires 3 qubits.")
            self.circuit.append(cirq.CCZ(*target_qubits))

        elif gate_name in ("cu", "cu3"):
            n_params = 4 if gate_name == "cu" else 3
            if len(target_qubits) != 2 or len(params) != n_params:
                raise ValueError(f"Gate '{gate_name}' requires 2 qubits and {n_params} parameters.")
            theta, phi, lam = params[0], params[1], params[2]
            gamma = params[3] if gate_name == "cu" else 0.0
            base = cirq.MatrixGate(np.exp(1j * gamma) * _u_matrix(theta, phi, lam))
            self.circuit.append(cirq.ControlledGate(base)(target_qubits[0], target_qubits[1]))

        elif gate_name in ("rzz", "rxx", "ryy"):
            if len(target_qubits) != 2 or not params:
                raise ValueError(f"Gate '{gate_name}' requires 2 qubits and 1 parameter.")
            cls = {"rzz": cirq.ZZPowGate, "rxx": cirq.XXPowGate, "ryy": cirq.YYPowGate}[gate_name]
            # exp(-i theta/2 P(x)P) == PPPowGate(exponent=theta/pi, global_shift=-0.5)
            self.circuit.append(cls(exponent=params[0] / np.pi, global_shift=-0.5)(target_qubits[0], target_qubits[1]))

        elif gate_name == "sqrtiswap":
            if len(target_qubits) != 2:
                raise ValueError("Gate 'sqrtiswap' requires 2 qubits.")
            self.circuit.append(cirq.SQRT_ISWAP(target_qubits[0], target_qubits[1]))
        
        else:
            # Check if it's a custom gate or truly undefined
            if gate_name in self.custom_gates:
                raise RuntimeError(f"Custom gate '{gate_name}' should have been handled earlier")
            else:
                raise NameError(f"Gate '{gate_name}' is not defined. Available gates: {list(self.STD_GATES)}")
                
    def visit_QuantumMeasurementStatement(self, node):
        """
        Handles 'measure q -> c' statements.
        Marks the target variable as coming from a measurement.
        """
        q_arg = node.measure.qubit
        qreg_name = q_arg.name.name if hasattr(q_arg.name, 'name') else q_arg.name
        
        target = node.target
        creg_name = target.name.name if hasattr(target.name, 'name') else target.name

        if creg_name not in self.clbits:
            raise NameError(f"[QuantumMeasurement] Classical register '{creg_name}' not declared")

        # Determine the target qubits
        if hasattr(q_arg, 'indices') and q_arg.indices:
            q_indices = parse_index_set(q_arg.indices[0], len(self.qubits[qreg_name]), self.variables)
            qubits_to_measure = [self.qubits[qreg_name][i] for i in q_indices]
        else:
            qubits_to_measure = self.qubits[qreg_name]

        # Determine the target classical bits
        if hasattr(target, 'indices') and target.indices:
            c_indices = parse_index_set(target.indices[0][0], len(self.clbits[creg_name]), self.variables)
            clbit_keys = [self.clbits[creg_name][i] for i in c_indices]
        else:
            clbit_keys = self.clbits[creg_name]

        # Validate and Measure
        if len(qubits_to_measure) != len(clbit_keys):
            raise ValueError(
                f"[QuantumMeasurement] Register size mismatch: cannot measure "
                f"{len(qubits_to_measure)} qubits into {len(clbit_keys)} classical bits."
            )

        # Create a mapping
        key_map = {q: k for q, k in zip(qubits_to_measure, clbit_keys)}
        
        # Append the measurement operation
        if self._in_dynamic_block:
            raise ValueError("[QuantumMeasurement] Measurements inside a measurement-conditioned block are not supported.")
        self.circuit.append(cirq.measure_each(*qubits_to_measure, key_func=lambda q: key_map[q]))
        self._measured_keys.update(clbit_keys)
        
        # Mark the variable as from measurement
        if creg_name in self.variables:
            self.variables[creg_name]['from_measurement'] = True
             
        
         
        return None
    def visit_QuantumReset(self, node):
        """Handles reset statements."""
        target = node.qubits
        
        if hasattr(target, 'name'):
            if hasattr(target.name, 'name'):
                reg_name = target.name.name
            else:
                reg_name = target.name
        else:
            reg_name = str(target)
        
        if not hasattr(target, 'indices') or not target.indices:
            qubits_to_reset = self.qubits[reg_name]
            self.circuit.append(cirq.reset_each(*qubits_to_reset))
             
        else:
            idx_node = target.indices[0]
            if isinstance(idx_node, list):
                idx_node = idx_node[0]
            idx = get_index_value(idx_node)
            
            qubit_to_reset = self.qubits[reg_name][idx]
            self.circuit.append(cirq.reset(qubit_to_reset))
             
        
        return None

    def visit_QuantumMeasurementAssignment(self, node):
        """
        Handles 'c = measure q' statements.
        Marks the target variable as coming from a measurement.
        """
        lvalue = node.lvalue
        creg_name = lvalue.name.name if hasattr(lvalue.name, 'name') else lvalue.name

        rvalue = node.rvalue
        q_arg = rvalue.qubit if hasattr(rvalue, 'qubit') else rvalue
        qreg_name = q_arg.name.name if hasattr(q_arg.name, 'name') else q_arg.name

        if creg_name not in self.clbits:
            raise NameError(f"[QuantumMeasurementAssignment] Classical register '{creg_name}' not declared")
        if qreg_name not in self.qubits:
            raise NameError(f"[QuantumMeasurementAssignment] Qubit register '{qreg_name}' not declared")

        # Determine the target qubits
        if hasattr(q_arg, "indices") and q_arg.indices:
            index_specifier = q_arg.indices[0]
            q_indices = parse_index_set(index_specifier, len(self.qubits[qreg_name]), self.variables)
            qubits_to_measure = [self.qubits[qreg_name][i] for i in q_indices]
        else:
            qubits_to_measure = self.qubits[qreg_name]

        # Determine the target classical bits
        if hasattr(lvalue, "indices") and lvalue.indices:
            index_specifier = lvalue.indices[0][0]
            c_indices = parse_index_set(index_specifier, len(self.clbits[creg_name]), self.variables)
            clbit_keys = [self.clbits[creg_name][i] for i in c_indices]
        else:
            clbit_keys = self.clbits[creg_name]

        # Validate
        if len(qubits_to_measure) != len(clbit_keys):
            raise ValueError(
                f"[QuantumMeasurementAssignment] Register size mismatch: cannot assign measurement of "
                f"{len(qubits_to_measure)} qubits to {len(clbit_keys)} classical bits."
            )
        
        # Create a mapping
        key_map = {q: k for q, k in zip(qubits_to_measure, clbit_keys)}
        
        # Append measurement
        if self._in_dynamic_block:
            raise ValueError("[QuantumMeasurementAssignment] Measurements inside a measurement-conditioned block are not supported.")
        self.circuit.append(cirq.measure_each(*qubits_to_measure, key_func=lambda q: key_map[q]))
        self._measured_keys.update(clbit_keys)
        
        # Mark the variable as from measurement
        if creg_name in self.variables:
            self.variables[creg_name]['from_measurement'] = True
             
        
         
        return None

    def visit_Measurement(self, node):
        """Handles basic measurement node."""
        q = self.qubits[node.qubit.name][node.qubit.index]
        c = self.clbits[node.target.name][node.target.index]
        self.circuit.append(cirq.measure(q, key=c))
        self._measured_keys.add(c)

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

    def finalize(self, visited_block=None):
        """Finalize and return the circuit or variables for classical-only programs."""
        if self.circuit is None:
            self.circuit = cirq.Circuit()
        return self.circuit

    def output_spec(self):
        """
        Describe how results must be reported (see qsim.backends.base.BaseBackend):
        declared classical bits in declaration order (bit 0 first), or all qubits
        when nothing was measured.
        """
        qubits = []
        for name in self._declared_qregs:
            qubits.extend(self.qubits.get(name, []))
        clbits = []
        for name in self._declared_cregs:
            keys = self.clbits.get(name)
            if not keys:
                continue
            info = self.variables.get(name, {})
            value = info.get("value", 0) if isinstance(info, dict) else 0
            try:
                value = int(value)
            except (TypeError, ValueError):
                value = 0
            for i, key in enumerate(keys):
                clbits.append((key, (value >> i) & 1))
        return {
            "measured": bool(self._measured_keys),
            "qubits": qubits,
            "clbits": clbits,
        }
