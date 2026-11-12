import sys
import os
import re
from typing import Dict, Any, Optional, Tuple
# from config.config import VERBOSE, vprint, new_log_session
# Patch: Config module missing, defining dependencies locally
VERBOSE = False
def vprint(*args): pass
def new_log_session(name): pass

# Add the project root directory to Python path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
sys.path.insert(0, project_root)

# Import the user's own quantum converters (independently per framework)
convert_qiskit_to_qasm3 = None
convert_cirq_to_qasm3 = None
convert_pennylane_to_qasm3 = None
ConversionResult = None

try:
    from quantum_converters.base.ConversionResult import ConversionResult
except ImportError as e:
    print(f"Import error: ConversionResult unavailable: {e}")

try:
    from quantum_converters.converters.qiskit_to_qasm import convert_qiskit_to_qasm3 as _qiskit_convert
    convert_qiskit_to_qasm3 = _qiskit_convert
    print("OK Qiskit converter available (unified)")
except ImportError as e:
    print(f"Qiskit converter import error: {e}")

# Removed exec-based cirq_to_qasm import to disable fallback
try:
    from quantum_converters.converters.cirq_to_qasm import convert_cirq_to_qasm3 as _cirq_convert
    convert_cirq_to_qasm3 = _cirq_convert
    print("OK Cirq converter available (unified)")
except ImportError as e:
    print(f"Cirq converter import error: {e}")

try:
    from quantum_converters.converters.pennylane_to_qasm import convert_pennylane_to_qasm3 as _pl_convert
    convert_pennylane_to_qasm3 = _pl_convert
    print("OK PennyLane converter available (unified AST-first)")
except ImportError as e:
    print(f"PennyLane converter import error: {e}")

# Import AST parsers for circuit gate extraction
QiskitASTParser = None
CirqASTParser = None
PennyLaneASTParser = None
GateNode = None
MeasurementNode = None
ForLoopNode = None
BarrierNode = None
ResetNode = None

try:
    from quantum_converters.parsers.qiskit_parser import QiskitASTParser
    print("OK QiskitASTParser available")
except ImportError as e:
    print(f"QiskitASTParser import error: {e}")

try:
    from quantum_converters.parsers.cirq_parser import CirqASTParser
    print("OK CirqASTParser available")
except ImportError as e:
    print(f"CirqASTParser import error: {e}")

try:
    from quantum_converters.parsers.pennylane_parser import PennyLaneASTParser
    print("OK PennyLaneASTParser available")
except ImportError as e:
    print(f"PennyLaneASTParser import error: {e}")

try:
    from quantum_converters.base.circuit_ast import GateNode, MeasurementNode, ForLoopNode, BarrierNode, ResetNode
    print("OK CircuitAST nodes available")
except ImportError as e:
    print(f"CircuitAST import error: {e}")


def _env_number(name: str, default: float) -> float:
    try:
        return max(0.0, float(os.getenv(name, "") or default))
    except ValueError:
        return float(default)


# Wall-clock budget for one isolated conversion (static parse + exec fallback).
CONVERT_TIMEOUT_SECONDS: float = _env_number("USER_CODE_CONVERT_TIMEOUT", 20)
# Limits for expanding `for` loops when building the /parse gate list.  The
# AST parser keeps loops symbolic; expanding `range(10**9)` here used to hang
# the API process.
PARSE_MAX_GATES: int = int(_env_number("USER_CODE_PARSE_MAX_GATES", 5000))
PARSE_MAX_LOOP_ITERATIONS: int = int(_env_number("USER_CODE_PARSE_MAX_LOOP_ITERATIONS", 100000))


class _ParseBudgetExceeded(Exception):
    """Raised internally when loop expansion for visualisation gets too big."""


def _convert_in_child(code: str, framework: str, style: str) -> Dict[str, Any]:
    """Child-process entry point for isolated conversions (module-level for pickling).

    The process boundary (isolated_exec) is what makes the converters' exec()
    fallback safe; the import blocklist is applied as well, as defence in
    depth, to code the converters compile from the user's source.
    """
    try:
        from qcanvas.sandbox import restricted_imports
    except Exception:  # pragma: no cover - sandbox module missing
        return ConversionService().convert_to_qasm(code, framework, style)
    with restricted_imports():
        return ConversionService().convert_to_qasm(code, framework, style)


class ConversionService:
    """Service for converting quantum circuit code between different frameworks and OpenQASM"""
    
    def __init__(self):
        self.converters = {
            "qiskit": convert_qiskit_to_qasm3,
            "cirq": convert_cirq_to_qasm3,
            "pennylane": convert_pennylane_to_qasm3
        }
    
    def convert_to_qasm(self, code: str, framework: str, style: str = "classic") -> Dict[str, Any]:
        """
        Convert quantum circuit code from specified framework to OpenQASM 3

        Args:
            code: The source code in the specified framework
            framework: The source framework ("qiskit", "cirq", or "pennylane")
            style: Output style ("classic" or "compact")

        Returns:
            Dictionary containing conversion result and metadata
        """
        self._initialize_conversion_request(framework)

        if not self._validate_framework(framework):
            return self._create_error_response(f"Unsupported framework: {framework}", framework)

        try:
            converter_func = self.converters.get(framework)
            if converter_func is None:
                return self._create_error_response(f"No converter available for framework: {framework}", framework)

            result = self._execute_conversion(converter_func, code, framework)
            if not result["success"]:
                return result

            qasm_code = result["qasm_code"]
            stats = result["stats"]

            return self._finalize_conversion(qasm_code, stats, framework, style)

        except Exception as e:
            return self._create_error_response(f"Conversion failed: {str(e)}", framework)

    async def convert_to_qasm_isolated(self, code: str, framework: str, style: str = "classic",
                                       timeout: Optional[float] = None) -> Dict[str, Any]:
        """Same contract as :meth:`convert_to_qasm`, but safe to call from an async route.

        The converters may fall back to ``exec()`` of the user's source, so the
        whole conversion runs in a hardened, killable child process (see
        ``app.services.isolated_exec``) and the event loop is never blocked.

        Raises ``UserCodeBusyError`` (an ``HTTPException`` with status 503 and
        a friendly "server busy, try again" detail) when every execution slot
        stays busy for ``USER_CODE_QUEUE_TIMEOUT`` seconds.
        """
        if not self._validate_framework(framework):
            return self._create_error_response(f"Unsupported framework: {framework}", framework)

        from app.services.isolated_exec import run_isolated_async

        budget = float(timeout) if timeout else CONVERT_TIMEOUT_SECONDS
        outcome = await run_isolated_async(
            _convert_in_child,
            args=(code, framework, style),
            timeout=budget,
            label="convert",
        )
        if outcome.ok and isinstance(outcome.value, dict):
            return outcome.value
        if outcome.timed_out:
            message = (f"Conversion timed out after {budget:g} seconds and was stopped. "
                       "Check your code for infinite loops or very long computations.")
        else:
            message = f"Conversion failed: {outcome.error or 'unknown error'}"
        return self._create_error_response(message, framework)

    def _initialize_conversion_request(self, framework: str) -> None:
        """Initialize logging and verbose output for conversion request."""
        try:
            new_log_session(f"convert_{framework}")
        except Exception:
            pass

    def _validate_framework(self, framework: str) -> bool:
        """Validate that the framework is supported."""
        return framework in ["qiskit", "cirq", "pennylane"]

    def _create_error_response(self, error_msg: str, framework: str) -> Dict[str, Any]:
        """Create a standardized error response."""
        return {
            "success": False,
            "error": error_msg,
            "framework": framework,
            "qasm_code": None,
            "qasm_version": "3",
            "conversion_stats": None
        }

    def _execute_conversion(self, converter_func, code: str, framework: str) -> Dict[str, Any]:
        """Execute the conversion using the provided converter function."""
        if VERBOSE:
            vprint(f"[ConversionService] Using user's {framework} converter")

        try:
            result = converter_func(code)
            if VERBOSE:
                vprint(f"[ConversionService] Converter returned type: {type(result)}")

            return self._process_conversion_result(result)
        except Exception as converter_error:
            if VERBOSE:
                vprint(f"[ConversionService] Error in {framework} converter:", str(converter_error))
            return self._create_error_response(f"Conversion error: {str(converter_error)}", framework)

    def _process_conversion_result(self, result) -> Dict[str, Any]:
        """Process the result from a converter function."""
        qasm_code = None
        stats = None

        if ConversionResult is not None and isinstance(result, ConversionResult):
            qasm_code = result.qasm_code
            if VERBOSE:
                vprint(f"[ConversionService] QASM length: {len(qasm_code) if qasm_code else 0}")
            stats = self._extract_stats_from_conversion_result(result)
        else:
            qasm_code = str(result)
            if VERBOSE:
                vprint(f"[ConversionService] String QASM length: {len(qasm_code) if qasm_code else 0}")
            stats = self._extract_stats_from_string_result(qasm_code)

        return {
            "success": True,
            "qasm_code": qasm_code,
            "stats": stats
        }

    def _extract_stats_from_conversion_result(self, result: ConversionResult) -> Dict[str, Any]:
        """Extract statistics from a ConversionResult object."""
        return {
            "qubits": getattr(result.stats, 'n_qubits', None),
            "gates": getattr(result.stats, 'gate_counts', None),
            "depth": getattr(result.stats, 'depth', None),
            "conversion_time": None
        }

    def _extract_stats_from_string_result(self, qasm_code: str) -> Dict[str, Any]:
        """Extract statistics from a string QASM result."""
        return {
            "qubits": self._count_qubits(qasm_code) if qasm_code else None,
            "gates": self._count_gates(qasm_code) if qasm_code else None,
            "depth": None,
            "conversion_time": None
        }

    def _finalize_conversion(self, qasm_code: str, stats: Dict[str, Any], framework: str, style: str) -> Dict[str, Any]:
        """Finalize the conversion by applying styling and returning success response."""
        if not qasm_code:
            return self._create_error_response("Conversion failed - no QASM output generated", framework)

        if style == "compact":
            qasm_code = self._format_compact(qasm_code)

        if VERBOSE:
            vprint("[ConversionService] Conversion complete. Returning response.")

        return {
            "success": True,
            "qasm_code": qasm_code,
            "error": None,
            "framework": framework,
            "qasm_version": "3",
            "conversion_stats": stats
        }

    def _fallback_conversion(self, code: str, framework: str) -> str:
        """Fallback conversion removed for Cirq as per user request"""
        if framework == "qiskit":
            return self._basic_qiskit_conversion(code)
        elif framework == "pennylane":
            return self._basic_pennylane_conversion(code)
        else:
            raise ValueError(f"Unsupported framework or fallback removed: {framework}")
    
    def _basic_qiskit_conversion(self, code: str) -> str:
        """Heuristic Qiskit-to-QASM conversion without importing qiskit."""
        import re
        import math

        num_qubits = self._extract_qubit_count_qiskit(code)

        qasm_lines = [
            "OPENQASM 3.0;",
            "include \"stdgates.inc\";",
            "",
            f"qubit[{num_qubits}] q;",
            ""
        ]

        gate_patterns = self._get_qiskit_gate_patterns()
        param_evaluator = self._create_param_evaluator()

        for line in code.splitlines():
            qasm_gate = self._convert_qiskit_line_to_qasm(line, gate_patterns, param_evaluator)
            if qasm_gate:
                qasm_lines.append(qasm_gate)

        return '\n'.join(qasm_lines)

    def _extract_qubit_count_qiskit(self, code: str) -> int:
        """Extract the number of qubits from Qiskit code."""
        import re

        patterns = [
            r"QuantumRegister\((\d+)",
            r"QuantumCircuit\((\d+)",
            r"create_\w+\((\d+)\)"
        ]

        for pattern in patterns:
            match = re.search(pattern, code)
            if match:
                return int(match.group(1))

        return 2  # Default fallback

    def _get_qiskit_gate_patterns(self) -> Dict[str, list]:
        """Get mapping of Qiskit gate patterns to QASM gates."""
        return {
            'single_qubit_no_param': [
                ('qc.h\\((\\d+)\\)', 'h q[{0}];'),
                ('qc.x\\((\\d+)\\)', 'x q[{0}];'),
                ('qc.y\\((\\d+)\\)', 'y q[{0}];'),
                ('qc.z\\((\\d+)\\)', 'z q[{0}];'),
                ('qc.s\\((\\d+)\\)', 's q[{0}];'),
                ('qc.t\\((\\d+)\\)', 't q[{0}];'),
            ],
            'single_qubit_param': [
                ('qc.rx\\(([^,]+),(\\d+)\\)', 'rx({0}) q[{1}];'),
                ('qc.ry\\(([^,]+),(\\d+)\\)', 'ry({0}) q[{1}];'),
                ('qc.rz\\(([^,]+),(\\d+)\\)', 'rz({0}) q[{1}];'),
                ('qc.(?:p|u1)\\(([^,]+),(\\d+)\\)', 'p({0}) q[{1}];'),
            ],
            'two_qubit_no_param': [
                ('qc.cx\\((\\d+),(\\d+)\\)', 'cx q[{0}], q[{1}];'),
                ('qc.cz\\((\\d+),(\\d+)\\)', 'cz q[{0}], q[{1}];'),
                ('qc.swap\\((\\d+),(\\d+)\\)', 'swap q[{0}], q[{1}];'),
            ],
            'two_qubit_param': [
                ('qc.cp\\(([^,]+),(\\d+),(\\d+)\\)', 'cp({0}) q[{1}], q[{2}];'),
            ]
        }

    def _create_param_evaluator(self):
        """Create a parameter evaluator function."""
        import math

        def eval_param(expr: str) -> str:
            try:
                expr = expr.replace('np.pi', str(math.pi)).replace('numpy.pi', str(math.pi)).replace('pi', str(math.pi))
                return str(float(eval(expr, {"__builtins__": {}}, {})))
            except Exception:
                return expr

        return eval_param

    def _convert_qiskit_line_to_qasm(self, line: str, gate_patterns: Dict[str, list], param_evaluator) -> Optional[str]:
        """Convert a single Qiskit code line to QASM."""
        import re

        s = line.strip().replace(' ', '')

        # Skip measurements
        if s.startswith('qc.measure'):
            return None

        # Check single qubit gates without parameters
        for pattern, qasm_template in gate_patterns['single_qubit_no_param']:
            match = re.search(pattern, s)
            if match:
                return qasm_template.format(int(match.group(1)))

        # Check single qubit gates with parameters
        for pattern, qasm_template in gate_patterns['single_qubit_param']:
            match = re.search(pattern, s)
            if match:
                param = param_evaluator(match.group(1))
                qubit = int(match.group(2))
                return qasm_template.format(param, qubit)

        # Check two qubit gates without parameters
        for pattern, qasm_template in gate_patterns['two_qubit_no_param']:
            match = re.search(pattern, s)
            if match:
                return qasm_template.format(int(match.group(1)), int(match.group(2)))

        # Check two qubit gates with parameters
        for pattern, qasm_template in gate_patterns['two_qubit_param']:
            match = re.search(pattern, s)
            if match:
                param = param_evaluator(match.group(1))
                qubit1 = int(match.group(2))
                qubit2 = int(match.group(3))
                return qasm_template.format(param, qubit1, qubit2)

        return None
    
    def _basic_cirq_conversion(self, code: str) -> str:
        """Heuristic Cirq-to-QASM conversion without importing cirq."""
        import re

        num_qubits, name_to_idx = self._extract_cirq_qubit_mapping(code)

        qasm_lines = [
            "OPENQASM 3.0;",
            "include \"stdgates.inc\";",
            "",
            f"qubit[{num_qubits}] q;",
            ""
        ]

        qubit_indexer = self._create_cirq_qubit_indexer(name_to_idx)
        gate_patterns = self._get_cirq_gate_patterns()

        for line in code.splitlines():
            qasm_gate = self._convert_cirq_line_to_qasm(line, gate_patterns, qubit_indexer)
            if qasm_gate:
                qasm_lines.append(qasm_gate)

        return '\n'.join(qasm_lines)

    def _extract_cirq_qubit_mapping(self, code: str) -> Tuple[int, Dict[str, int]]:
        """Extract qubit count and name-to-index mapping from Cirq code."""
        import re

        name_to_idx = {}

        # Detect qubit mapping from `q0, q1, ... = cirq.LineQubit.range(N)`
        match = re.search(r"([a-zA-Z_]\w*(?:\s*,\s*[a-zA-Z_]\w*)+)\s*=\s*cirq\.LineQubit\.range\((\d+)\)", code)
        if match:
            names = [n.strip() for n in match.group(1).split(',')]
            num_qubits = int(match.group(2))
            for i, name in enumerate(names):
                name_to_idx[name] = i
        else:
            # Fallback: look for LineQubit.range without assignment
            match = re.search(r"LineQubit\.range\((\d+)\)", code)
            num_qubits = int(match.group(1)) if match else 2

        return num_qubits, name_to_idx

    def _create_cirq_qubit_indexer(self, name_to_idx: Dict[str, int]):
        """Create a qubit indexing function for Cirq."""
        import re

        def qidx(token: str) -> int:
            token = token.strip()
            if token in name_to_idx:
                return name_to_idx[token]
            match = re.search(r"\[(\d+)\]", token)
            if match:
                return int(match.group(1))
            # Fallback, try qN naming like q0
            match = re.search(r"(\d+)$", token)
            return int(match.group(1)) if match else 0

        return qidx

    def _get_cirq_gate_patterns(self) -> list[tuple[str, str]]:
        """Get Cirq gate patterns and their QASM equivalents."""
        return [
            (r"cirq\.H\(([^\)]+)\)", "h q[{0}];"),
            (r"cirq\.X\(([^\)]+)\)", "x q[{0}];"),
            (r"cirq\.Y\(([^\)]+)\)", "y q[{0}];"),
            (r"cirq\.Z\(([^\)]+)\)", "z q[{0}];"),
            (r"cirq\.CNOT\(([^,]+),([^\)]+)\)", "cx q[{0}], q[{1}];"),
            (r"cirq\.CZ\(([^,]+),([^\)]+)\)", "cz q[{0}], q[{1}];"),
            (r"cirq\.SWAP\(([^,]+),([^\)]+)\)", "swap q[{0}], q[{1}];"),
        ]

    def _convert_cirq_line_to_qasm(self, line: str, gate_patterns: list[tuple[str, str]], qubit_indexer) -> Optional[str]:
        """Convert a single Cirq code line to QASM."""
        import re

        s = line.strip().replace(' ', '')

        for pattern, qasm_template in gate_patterns:
            match = re.search(pattern, s)
            if match:
                groups = [qubit_indexer(group) for group in match.groups()]
                return qasm_template.format(*groups)

        return None
    
    def _basic_pennylane_conversion(self, _code: str) -> str:
        """Basic PennyLane to QASM conversion"""
        return """OPENQASM 3.0;
include "stdgates.inc";

// Converted from PennyLane (basic fallback)
qubit[2] q;

h q[0];
cx q[0], q[1];
"""
    
    def _format_compact(self, qasm_code: str) -> str:
        """Format QASM code in compact style by removing extra whitespace"""
        lines = qasm_code.split('\n')
        compact_lines = []
        
        for line in lines:
            stripped = line.strip()
            if stripped:
                compact_lines.append(stripped)
        
        return '\n'.join(compact_lines)
    
    def _count_qubits(self, qasm_code: str) -> int:
        """Count the number of qubits in QASM code"""
        lines = qasm_code.split('\n')
        for line in lines:
            if 'qubit[' in line:
                # Extract number from qubit[n]
                match = re.search(r'qubit\[(\d+)\]', line)
                if match:
                    return int(match.group(1))
        return 2  # Default fallback
    
    def _count_gates(self, qasm_code: str) -> Dict[str, int]:
        """Count the number of gates in QASM code"""
        gate_counts = {}
        lines = qasm_code.split('\n')
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('//') and not line.startswith('OPENQASM') and not line.startswith('include') and not line.startswith('qubit') and not line.startswith('bit'):
                # Extract gate name (first word after stripping)
                parts = line.split()
                if parts:
                    gate_name = parts[0]
                    gate_counts[gate_name] = gate_counts.get(gate_name, 0) + 1
        
        return gate_counts
    
    def get_supported_frameworks(self) -> list:
        """Get list of supported frameworks"""
        return ["qiskit", "cirq", "pennylane"]
    
    def validate_code(self, code: str, framework: str) -> Dict[str, Any]:
        """
        Validate code syntax for the specified framework
        
        Args:
            code: The source code to validate
            framework: The framework to validate against
            
        Returns:
            Dictionary containing validation result
        """
        if framework not in ["qiskit", "cirq", "pennylane"]:
            return {
                "valid": False,
                "error": f"Unsupported framework: {framework}"
            }
        
        try:
            # Heuristic validation: accept common patterns for each framework
            fw = framework.lower()
            is_valid = False
            if fw == "qiskit":
                is_valid = ("from qiskit" in code) or ("import qiskit" in code) or ("QuantumCircuit(" in code)
            elif fw == "cirq":
                is_valid = ("import cirq" in code) or ("cirq.Circuit(" in code)
            elif fw == "pennylane":
                is_valid = ("import pennylane" in code) or ("qml.device(" in code) or ("qml." in code)

            if not is_valid:
                return {
                    "valid": False,
                    "error": f"Provided code does not look like {framework} code. Include the proper imports or circuit creation."
                }
            
            # Try to parse the code
            import ast
            ast.parse(code)
            return {"valid": True, "error": None}
            
        except SyntaxError as e:
            return {
                "valid": False,
                "error": f"Syntax error: {str(e)}"
            }
        except Exception as e:
            return {
                "valid": False,
                "error": f"Validation error: {str(e)}"
            }
    
    def _get_format_guide(self, framework: str) -> str:
        """
        Get format guide for the specified framework
        
        Args:
            framework: The framework name
            
        Returns:
            String containing format instructions
        """
        guides = {
            "qiskit": """Qiskit Code Format:
Your code must define a function called 'get_circuit()' that returns a QuantumCircuit object.

Example:
from qiskit import QuantumCircuit

def get_circuit():
    qc = QuantumCircuit(2)
    qc.h(0)  # Hadamard gate on qubit 0
    qc.cx(0, 1)  # CNOT gate between qubits 0 and 1
    return qc""",
            
            "cirq": """Cirq Code Format:
Your code must define a function called 'get_circuit()' that returns a Circuit object.

Example:
import cirq

def get_circuit():
    q0, q1 = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(q0),  # Hadamard gate on qubit 0
        cirq.CNOT(q0, q1)  # CNOT gate between qubits 0 and 1
    )
    return circuit""",
            
            "pennylane": """PennyLane Code Format:
Your code must define a function called 'get_circuit()' that returns a qnode function.

Example:
import pennylane as qml

def get_circuit():
    dev = qml.device('default.qubit', wires=2)
    
    @qml.qnode(dev)
    def circuit():
        qml.Hadamard(wires=0)  # Hadamard gate on qubit 0
        qml.CNOT(wires=[0, 1])  # CNOT gate between qubits 0 and 1
        return qml.expval(qml.PauliZ(0))
    
    return circuit"""
        }
        
        return guides.get(framework, "Format guide not available for this framework.")
    
    def parse_circuit_gates(self, code: str, framework: str) -> Dict[str, Any]:
        """
        Parse quantum circuit code and extract gates for visualization.
        Uses AST-based parsing for accurate gate extraction.
        
        Args:
            code: The source code to parse
            framework: The framework ("qiskit", "cirq", or "pennylane")
            
        Returns:
            Dictionary containing:
                - success: bool
                - gates: List of gate dictionaries
                - qubits: Number of qubits
                - error: Error message if failed
        """
        if framework not in ["qiskit", "cirq", "pennylane"]:
            return {
                "success": False,
                "error": f"Unsupported framework: {framework}",
                "gates": None,
                "qubits": None
            }
        
        try:
            # Select the appropriate parser
            parser = None
            if framework == "qiskit" and QiskitASTParser:
                parser = QiskitASTParser()
            elif framework == "cirq" and CirqASTParser:
                parser = CirqASTParser()
            elif framework == "pennylane" and PennyLaneASTParser:
                parser = PennyLaneASTParser()
            
            if parser is None:
                return {
                    "success": False,
                    "error": f"Parser not available for framework: {framework}",
                    "gates": None,
                    "qubits": None
                }
            
            # Parse the code to CircuitAST
            circuit_ast = parser.parse(code)
            
            # Convert CircuitAST operations to gate list for visualization
            gates = self._convert_ast_to_gates(circuit_ast)
            
            # Assign timestamps based on circuit layers
            gates = self._assign_timestamps(gates)
            
            return {
                "success": True,
                "gates": gates,
                "qubits": circuit_ast.qubits,
                "error": None
            }
            
        except ValueError as e:
            return {
                "success": False,
                "error": str(e),
                "gates": None,
                "qubits": None
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Parse error: {str(e)}",
                "gates": None,
                "qubits": None
            }
    
    def _convert_ast_to_gates(self, circuit_ast) -> list:
        """
        Convert CircuitAST operations to a list of gate dictionaries
        suitable for frontend visualization.

        Loop expansion is bounded (PARSE_MAX_GATES gates and
        PARSE_MAX_LOOP_ITERATIONS loop iterations); past that the gate list is
        truncated instead of hanging the server on e.g. ``range(10**9)``.
        """
        gates = []
        budget = {"iterations": 0}
        try:
            self._process_operations(circuit_ast.operations, gates, {}, budget)
        except _ParseBudgetExceeded:
            pass
        return gates[:PARSE_MAX_GATES]

    def _process_operations(self, operations: list, gates: list, var_context: dict,
                            budget: Optional[dict] = None) -> None:
        """
        Recursively process operations, expanding loops and handling variable substitution.

        Args:
            operations: List of AST operation nodes
            gates: Output list to append gate dictionaries to
            var_context: Dictionary mapping variable names to their current values
            budget: Shared counters used to stop runaway loop expansion
        """
        if budget is None:
            budget = {"iterations": 0}
        for op in operations:
            if len(gates) >= PARSE_MAX_GATES:
                raise _ParseBudgetExceeded()
            if ForLoopNode and isinstance(op, ForLoopNode):
                # Expand for loop by iterating through range
                loop_var = op.variable
                for i in range(op.range_start, op.range_end):
                    budget["iterations"] += 1
                    if budget["iterations"] > PARSE_MAX_LOOP_ITERATIONS or len(gates) >= PARSE_MAX_GATES:
                        raise _ParseBudgetExceeded()
                    # Create new context with loop variable value
                    new_context = var_context.copy()
                    new_context[loop_var] = i
                    # Recursively process body with updated context
                    self._process_operations(op.body, gates, new_context, budget)

            elif GateNode and isinstance(op, GateNode):
                gate_dict = self._gate_node_to_dict(op, var_context)
                if gate_dict:
                    gates.append(gate_dict)
            
            elif MeasurementNode and isinstance(op, MeasurementNode):
                qubit = self._resolve_qubit(op.qubit, var_context)
                gate_dict = {
                    "type": "measure",
                    "qubit": qubit,
                }
                gates.append(gate_dict)
            
            elif ResetNode and isinstance(op, ResetNode):
                qubit = self._resolve_qubit(op.qubit, var_context)
                gate_dict = {
                    "type": "reset",
                    "qubit": qubit,
                }
                gates.append(gate_dict)
            
            elif BarrierNode and isinstance(op, BarrierNode):
                # Drawn as a dashed separator; it also stops gates sliding
                # left past it, which is what the barrier means.
                qubits = [self._resolve_qubit(q, var_context) for q in (op.qubits or [])]
                gate_dict = {"type": "barrier", "qubit": qubits[0] if qubits else 0}
                if qubits:
                    gate_dict["qubits"] = qubits
                gates.append(gate_dict)
    
    def _resolve_qubit(self, qubit, var_context: dict) -> int:
        """
        Resolve a qubit index, substituting variable values from context.
        """
        if isinstance(qubit, int):
            return qubit
        elif isinstance(qubit, str):
            # Check if it's a variable in our context
            if qubit in var_context:
                return var_context[qubit]
            # Try to parse as integer
            try:
                return int(qubit)
            except ValueError:
                return 0
        return 0
    
    def _gate_node_to_dict(self, op, var_context: dict) -> dict:
        """
        Convert a GateNode to a gate dictionary, resolving variable qubit indices.
        """
        # Resolve all qubit indices
        resolved_qubits = []
        for q in op.qubits:
            resolved_qubits.append(self._resolve_qubit(q, var_context))
        
        # Parsers express some gates as base + modifiers (qc.sdg -> s{inv},
        # qc.mcx -> x{ctrl: n}). Fold them back into the conventional name so
        # the diagram draws S† / a multi-controlled X instead of S / a box.
        name = op.name.lower()
        modifiers = getattr(op, "modifiers", None) or {}
        if modifiers.get("inv"):
            name = str({"s": "sdg", "t": "tdg", "sx": "sxdg"}.get(name, name))
        n_ctrl = modifiers.get("ctrl")
        if isinstance(n_ctrl, int) and 0 < n_ctrl < len(op.qubits):
            name = ("c" * n_ctrl + name) if n_ctrl <= 2 else ("mc" + name)

        gate_dict = {
            "type": name,
            "qubit": resolved_qubits[0] if resolved_qubits else 0,
        }
        
        # Handle two-qubit gates (control-target)
        if len(resolved_qubits) >= 2:
            if name in ['cx', 'cnot', 'cz', 'cy', 'ch', 'swap', 'cswap']:
                gate_dict["control"] = resolved_qubits[0]
                gate_dict["target"] = resolved_qubits[1]
            else:
                gate_dict["qubits"] = resolved_qubits
        
        # Handle three-qubit gates
        if len(resolved_qubits) >= 3:
            gate_dict["qubits"] = resolved_qubits
        
        # Handle parameterized gates
        if op.parameters:
            angle = self._param_to_angle(op.parameters[0], var_context)
            if angle is not None:
                gate_dict["angle"] = angle

        return gate_dict

    @staticmethod
    def _param_to_angle(param, var_context: dict) -> Optional[float]:
        """Numeric value of a gate parameter, or None when it is symbolic.

        Parsers hand parameters over either as numbers or as source text such as
        ``"pi/2"``, ``"-np.pi/4"`` or ``"2*theta"`` (with ``theta`` bound by a
        loop). Text is evaluated with the static evaluator, never ``eval``.
        """
        if isinstance(param, bool):
            return None
        if isinstance(param, (int, float)):
            return float(param)
        if not isinstance(param, str) or not param.strip() or len(param) > 200:
            return None
        try:
            import ast as _ast
            import math as _math
            from quantum_converters.base.safe_eval import static_number

            value = float(static_number(_ast.parse(param.strip(), mode="eval"), var_context))
            return value if _math.isfinite(value) else None
        except Exception:  # NotStatic (symbolic), SyntaxError, overflow...
            return None
    
    def _assign_timestamps(self, gates: list) -> list:
        """
        Assign timestamps to gates based on circuit layers.
        Gates on different qubits that don't overlap get the same timestamp.
        """
        if not gates:
            return gates
        
        # Track next available timestamp for each qubit
        qubit_next_time: Dict[int, int] = {}
        
        result = []
        for gate in gates:
            # Get all qubits this gate operates on
            gate_qubits = set()
            if 'qubit' in gate:
                gate_qubits.add(gate['qubit'])
            if 'control' in gate:
                gate_qubits.add(gate['control'])
            if 'target' in gate:
                gate_qubits.add(gate['target'])
            if 'qubits' in gate and gate['qubits']:
                gate_qubits.update(gate['qubits'])
            # A multi-qubit gate's connecting line crosses every wire between
            # its outermost qubits, so it occupies that whole span.
            if len(gate_qubits) > 1:
                gate_qubits = set(range(min(gate_qubits), max(gate_qubits) + 1))

            # Find earliest timestamp where all qubits are free
            timestamp = 0
            for q in gate_qubits:
                next_time = qubit_next_time.get(q, 0)
                timestamp = max(timestamp, next_time)
            
            # Update next available time for all qubits
            for q in gate_qubits:
                qubit_next_time[q] = timestamp + 1
            
            gate_with_timestamp = gate.copy()
            gate_with_timestamp["timestamp"] = timestamp
            result.append(gate_with_timestamp)
        
        return result
