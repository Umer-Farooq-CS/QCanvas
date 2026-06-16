"""
Metrics Collector Module

Collects evaluation metrics including the published code-quality formula,
objective code validation helpers, and statistical helpers for multi-trial
benchmarks.
"""

import ast
import math
from typing import Dict, Any, List, Optional
import numpy as np
import sympy
import cirq

from collections import defaultdict

from ..cirq_rag_code_assistant.config.logging import get_logger

logger = get_logger(__name__)

REQUIRED_CIRQ_IMPORTS = ("cirq",)


def _syntax_valid(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _correct_imports(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in REQUIRED_CIRQ_IMPORTS:
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in REQUIRED_CIRQ_IMPORTS:
                return True
    return "import cirq" in code or "from cirq" in code


def _has_measurement(code: str, validation_result: Dict[str, Any]) -> bool:
    if "cirq.measure" in code or "cirq.Moment" in code:
        if "measure" in code.lower():
            return True
    compilation = validation_result.get("compilation", {})
    circuit = compilation.get("circuit")
    if circuit is not None:
        try:
            import cirq
            for op in circuit.all_operations():
                if isinstance(op, cirq.GateOperation) and isinstance(
                    op.gate, cirq.MeasurementGate
                ):
                    return True
            if any("measure" in str(m).lower() for m in circuit):
                return True
        except Exception:
            pass
    return "cirq.measure" in code


def _circuit_non_empty(validation_result: Dict[str, Any]) -> bool:
    compilation = validation_result.get("compilation", {})
    circuit = compilation.get("circuit")
    if circuit is not None:
        try:
            return len(list(circuit.all_operations())) > 0
        except Exception:
            pass
    return compilation.get("success", False)


def _has_simulation(code: str) -> bool:
    return "cirq.Simulator" in code or ".simulate(" in code or ".run(" in code


def _has_qubit_definition(code: str) -> bool:
    return "cirq.LineQubit" in code or "cirq.GridQubit" in code or "cirq.NamedQubit" in code


def _has_comments(code: str) -> bool:
    try:
        tree = ast.parse(code)
        if ast.get_docstring(tree):
            return True
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)):
                if ast.get_docstring(node):
                    return True
    except SyntaxError:
        pass
    
    for line in code.split('\n'):
        if '#' in line.strip():
            return True
    return False


def _is_concise(code: str) -> bool:
    """Checks if lines of code are within a reasonable boundary (not overly bloated)."""
    loc = len([line for line in code.split('\n') if line.strip()])
    return 3 <= loc <= 150


def _is_optimized(code: str, validation_result: Dict[str, Any]) -> bool:
    """Heuristic to check if the circuit is reasonably optimized (e.g. depth <= 100 or uses optimization APIs)."""
    if "cirq.optimize" in code or "cirq.transformers" in code:
        return True
    
    compilation = validation_result.get("compilation", {})
    circuit = compilation.get("circuit")
    if circuit is not None:
        try:
            depth = len(circuit)
            if 0 < depth <= 100:
                return True
        except Exception:
            pass
    return False


def normalize_circuit_qubits(circuit: cirq.Circuit) -> cirq.Circuit:
    """Normalize all qubits in the circuit to sorted LineQubits to prevent Hilbert space mismatches."""
    qubits = sorted(list(circuit.all_qubits()))
    mapping = {q: cirq.LineQubit(i) for i, q in enumerate(qubits)}
    return circuit.transform_qubits(mapping)


def strip_measurements(circuit: cirq.Circuit) -> cirq.Circuit:
    """Remove measurement gates from a circuit to compare state preparation vectors directly."""
    clean_ops = [op for op in circuit.all_operations() if not isinstance(op.gate, cirq.MeasurementGate)]
    return cirq.Circuit(clean_ops)


BASELINE_CODES = {
    "BM-001": """
import cirq
q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit(cirq.H(q0), cirq.CNOT(q0, q1), cirq.measure(q0, q1, key='result'))
""",
    "BM-002": """
import cirq
q = cirq.LineQubit.range(3)
circuit = cirq.Circuit(cirq.H(q[0]), cirq.CNOT(q[0], q[1]), cirq.CNOT(q[1], q[2]), cirq.measure(*q, key='result'))
""",
    "BM-003": """
import cirq
q = cirq.LineQubit(0)
circuit = cirq.Circuit(cirq.X(q), cirq.H(q), cirq.measure(q, key='result'))
""",
    "BM-004": """
import cirq
q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit(cirq.CNOT(q0, q1), cirq.CNOT(q0, q1), cirq.measure(q0, q1, key='result'))
""",
    "BM-005": """
import cirq
q_anc, q_a, q_b = cirq.LineQubit.range(3)
circuit = cirq.Circuit(cirq.H(q_anc), cirq.CSWAP(q_anc, q_a, q_b), cirq.H(q_anc), cirq.measure(q_anc, key='result'))
""",
    "BM-006": """
import cirq
q = cirq.LineQubit.range(3)
circuit = cirq.Circuit(
    cirq.H.on_each(*q),
    cirq.CCZ(*q),
    cirq.H.on_each(*q),
    cirq.X.on_each(*q),
    cirq.CCZ(*q),
    cirq.X.on_each(*q),
    cirq.H.on_each(*q),
    cirq.measure(*q, key='result')
)
""",
    "BM-007": """
import cirq
import numpy as np
qubits = cirq.LineQubit.range(3)
circuit = cirq.Circuit(
    cirq.H(qubits[0]),
    cirq.CZ(qubits[1], qubits[0])**(1/2),
    cirq.H(qubits[1]),
    cirq.CZ(qubits[2], qubits[0])**(1/4),
    cirq.CZ(qubits[2], qubits[1])**(1/2),
    cirq.H(qubits[2]),
    cirq.SWAP(qubits[0], qubits[2]),
    cirq.measure(*qubits, key='result')
)
""",
    "BM-008": """
import cirq
msg, alice, bob = cirq.LineQubit.range(3)
circuit = cirq.Circuit(
    cirq.H(alice),
    cirq.CNOT(alice, bob),
    cirq.CNOT(msg, alice),
    cirq.H(msg),
    cirq.measure(msg, alice, key='m'),
    cirq.CNOT(alice, bob),
    cirq.CZ(msg, bob),
    cirq.measure(bob, key='result')
)
""",
    "BM-009": """
import cirq
q_sys, q_anc = cirq.LineQubit.range(2)
circuit = cirq.Circuit(
    cirq.H(q_anc),
    cirq.X(q_sys),
    cirq.CZ(q_anc, q_sys)**0.5,
    cirq.H(q_anc),
    cirq.measure(q_anc, key='result')
)
""",
    "BM-010": """
import cirq
q0, q1, q2 = cirq.LineQubit.range(3)
circuit = cirq.Circuit(cirq.X(q0), cirq.X(q1), cirq.TOFFOLI(q0, q1, q2), cirq.measure(q0, q1, q2, key='result'))
""",
    "BM-011": """
import cirq
import sympy
qubits = cirq.LineQubit.range(4)
theta = [sympy.Symbol(f'theta_{i}') for i in range(4)]
circuit = cirq.Circuit()
for i, q in enumerate(qubits):
    circuit.append(cirq.ry(theta[i])(q))
for i in range(3):
    circuit.append(cirq.CNOT(qubits[i], qubits[i+1]))
circuit.append(cirq.measure(*qubits, key='result'))
""",
    "BM-012": """
import cirq
import sympy
qubits = cirq.LineQubit.range(4)
gamma = sympy.Symbol('gamma')
beta = sympy.Symbol('beta')
circuit = cirq.Circuit()
circuit.append(cirq.H.on_each(*qubits))
for i in range(4):
    circuit.append(cirq.ZZ(qubits[i], qubits[(i+1)%4])**gamma)
for q in qubits:
    circuit.append(cirq.rx(2 * beta)(q))
circuit.append(cirq.measure(*qubits, key='result'))
""",
    "BM-013": """
import cirq
x0, x1, x2, y = cirq.LineQubit.range(4)
circuit = cirq.Circuit(
    cirq.X(y),
    cirq.H.on_each(x0, x1, x2, y),
    cirq.CNOT(x0, y),
    cirq.CNOT(x1, y),
    cirq.H.on_each(x0, x1, x2),
    cirq.measure(x0, x1, x2, key='result')
)
""",
    "BM-014": """
import cirq
import numpy as np
qubits = cirq.LineQubit.range(4)
circuit = cirq.Circuit()
for i in range(4):
    circuit.append(cirq.H(qubits[i]))
    for j in range(i+1, 4):
        theta = np.pi / (2**(j-i))
        circuit.append(cirq.CZ(qubits[j], qubits[i])**(theta/np.pi))
circuit.append(cirq.SWAP(qubits[0], qubits[3]))
circuit.append(cirq.SWAP(qubits[1], qubits[2]))
circuit.append(cirq.measure(*qubits, key='result'))
""",
    "BM-015": """
import cirq
qubits = cirq.LineQubit.range(4)
circuit = cirq.Circuit(
    cirq.H(qubits[0]),
    cirq.H(qubits[1]),
    cirq.CNOT(qubits[0], qubits[2]),
    cirq.CNOT(qubits[1], qubits[3]),
    cirq.H(qubits[0]),
    cirq.H(qubits[1]),
    cirq.measure(qubits[0], qubits[1], key='result')
)
""",
    "BM-016": """
import cirq
import sympy
qubits = cirq.LineQubit.range(3)
phi = [sympy.Symbol(f'phi_{i}') for i in range(3)]
circuit = cirq.Circuit(
    cirq.H.on_each(*qubits),
    cirq.rz(phi[0])(qubits[0]),
    cirq.CNOT(qubits[0], qubits[1]),
    cirq.rz(phi[1])(qubits[1]),
    cirq.CNOT(qubits[0], qubits[1]),
    cirq.measure(*qubits, key='result')
)
""",
    "BM-017": """
import cirq
coin = cirq.LineQubit(0)
position = cirq.LineQubit.range(1, 3)
circuit = cirq.Circuit(
    cirq.H(coin),
    cirq.CNOT(coin, position[0]),
    cirq.measure(coin, *position, key='result')
)
""",
    "BM-018": """
import cirq
q_state, q_anc = cirq.LineQubit.range(2)
circuit = cirq.Circuit(
    cirq.H(q_anc),
    cirq.H(q_state),
    cirq.CZ(q_anc, q_state),
    cirq.H(q_anc),
    cirq.measure(q_anc, key='result')
)
""",
    "BM-019": """
import cirq
import sympy
q0, q1, q2 = cirq.LineQubit.range(3)
t = sympy.Symbol('t')
circuit = cirq.Circuit(
    cirq.H(q0),
    cirq.H(q1),
    cirq.CNOT(q0, q1),
    cirq.rz(t)(q1),
    cirq.CNOT(q0, q1),
    cirq.measure(q0, q1, q2, key='result')
)
""",
    "BM-020": """
import cirq
import sympy
qubits = cirq.LineQubit.range(4)
theta = sympy.Symbol('theta')
circuit = cirq.Circuit()
for q in qubits:
    circuit.append(cirq.ry(theta)(q))
for i in range(3):
    circuit.append(cirq.CNOT(qubits[i], qubits[i+1]))
circuit.append(cirq.measure(*qubits, key='result'))
"""
}


def get_baseline_circuit(prompt_id: str) -> Optional[cirq.Circuit]:
    """Compile and return the canonical baseline circuit for a given prompt ID."""
    code = BASELINE_CODES.get(prompt_id)
    if not code:
        return None
    try:
        local_vars = {}
        exec(code, {"cirq": cirq, "np": np, "sympy": sympy}, local_vars)
        return local_vars.get("circuit")
    except Exception as e:
        logger.error(f"Error compiling baseline circuit for {prompt_id}: {e}")
        return None


def compute_hybrid_quantum_score(
    gen_circuit: Optional[cirq.Circuit],
    prompt_id: str,
    syntax_valid: bool = False,
    compilation_success: bool = False,
    w1: float = 0.5,
    w2: float = 0.5,
) -> Dict[str, Any]:
    """
    Computes the hybrid code quality score gating resource efficiency 
    behind functional quantum correctness and state fidelity simulation.
    """
    result = {
        "q_score": 0.0,
        "fidelity": 0.0,
        "func_gate": 0.0,
        "depth_ratio": 0.0,
        "gate_ratio": 0.0,
        "syntax_valid": syntax_valid,
        "compilation_success": compilation_success,
    }

    if gen_circuit is None:
        return result

    base_circuit = get_baseline_circuit(prompt_id)
    if base_circuit is None:
        return result

    try:
        # 1. Resolve parameters for symbol-heavy circuits (e.g. VQE, QAOA)
        for circuit_obj in [gen_circuit, base_circuit]:
            param_names = cirq.parameter_names(circuit_obj)
            if param_names:
                resolver = cirq.ParamResolver({name: 0.5 for name in param_names})
                if circuit_obj is gen_circuit:
                    gen_circuit = cirq.resolve_parameters(gen_circuit, resolver)
                else:
                    base_circuit = cirq.resolve_parameters(base_circuit, resolver)

        # 2. Normalize qubits and strip measurements for fidelity simulation
        clean_gen = strip_measurements(normalize_circuit_qubits(gen_circuit))
        clean_base = strip_measurements(normalize_circuit_qubits(base_circuit))

        # 3. Simulate state vector preparation
        sim = cirq.Simulator()
        res_gen = sim.simulate(clean_gen)
        res_base = sim.simulate(clean_base)

        state_gen = res_gen.final_state_vector
        state_base = res_base.final_state_vector

        # Calculate overlap (state fidelity)
        fidelity = float(np.abs(np.vdot(state_base, state_gen)) ** 2)
        result["fidelity"] = fidelity

        # Functional validation coefficient gate
        func_gate = 0.40 * (1.0 if syntax_valid and compilation_success else 0.0) + 0.60 * fidelity
        result["func_gate"] = func_gate

        if fidelity < 1e-4:
            result["q_score"] = 0.0
            return result

        # 4. Resource Efficiency Stage
        gen_depth = len(gen_circuit)
        base_depth = len(base_circuit)

        gen_gates = len(list(gen_circuit.all_operations()))
        base_gates = len(list(base_circuit.all_operations()))

        # Ratios penalize bloating; capped at 1.0 if generated out-optimizes baseline
        depth_ratio = min(1.0, base_depth / max(1, gen_depth))
        gate_ratio = min(1.0, base_gates / max(1, gen_gates))

        result["depth_ratio"] = depth_ratio
        result["gate_ratio"] = gate_ratio

        # Composite Final Score
        q_score = func_gate * ((w1 * depth_ratio) + (w2 * gate_ratio))
        result["q_score"] = float(q_score)

    except Exception as e:
        logger.error(f"Error in compute_hybrid_quantum_score: {e}")
        result["q_score"] = 0.0

    return result


def compute_code_quality_score(
    code: str,
    validation_result: Optional[Dict[str, Any]] = None,
    prompt_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Published code quality formula:

    CodeQuality(c) = 0.30 × SyntaxValid
                  + 0.30 × CompilationSuccess
                  + 0.20 × HasMeasurement
                  + 0.10 × CircuitNonEmpty
                  + 0.10 × CorrectImports

    All components are binary, so the score is in [0, 1].
    If prompt_id is provided, the Hybrid Quantum Quality Score is also calculated.
    """
    validation_result = validation_result or {}
    compilation = validation_result.get("compilation", {})
    gen_circuit = compilation.get("circuit")

    components = {
        "syntax_valid": 1.0 if _syntax_valid(code) else 0.0,
        "compilation_success": 1.0 if compilation.get("success", False) else 0.0,
        "has_measurement": 1.0 if _has_measurement(code, validation_result) else 0.0,
        "circuit_non_empty": 1.0 if _circuit_non_empty(validation_result) else 0.0,
        "correct_imports": 1.0 if _correct_imports(code) else 0.0,
    }

    score = (
        0.30 * components["syntax_valid"]
        + 0.30 * components["compilation_success"]
        + 0.20 * components["has_measurement"]
        + 0.10 * components["circuit_non_empty"]
        + 0.10 * components["correct_imports"]
    )

    result_dict = {
        "code_quality_score": score,
        "components": components,
        "hybrid_quantum_score": None
    }

    if prompt_id:
        syntax_valid_bool = components["syntax_valid"] == 1.0
        compilation_success_bool = components["compilation_success"] == 1.0
        hybrid_res = compute_hybrid_quantum_score(
            gen_circuit=gen_circuit,
            prompt_id=prompt_id,
            syntax_valid=syntax_valid_bool,
            compilation_success=compilation_success_bool
        )
        result_dict["hybrid_quantum_score"] = hybrid_res["q_score"]
        result_dict["hybrid_quantum_components"] = hybrid_res

    return result_dict


def assess_code_objectively(code: str) -> Dict[str, Any]:
    """Compile and validate generated code with objective runtime checks."""
    from ..tools.compiler import CirqCompiler

    compiler = CirqCompiler()
    compilation = compiler.compile(code, execute=True)

    objective_validation = {
        "compilation": compilation,
        "circuit_validation": {},
        "validation_passed": False,
        "errors": compilation.get("errors", []),
    }

    if not compilation.get("success", False):
        return objective_validation

    circuit = compilation.get("circuit")
    if circuit is not None:
        try:
            objective_validation["circuit_validation"] = compiler.validate_circuit(circuit)
        except Exception as exc:
            objective_validation["errors"] = objective_validation.get("errors", []) + [str(exc)]
            return objective_validation

    objective_validation["validation_passed"] = (
        compilation.get("success", False)
        and objective_validation["circuit_validation"].get("valid", False)
        and _correct_imports(code)
        and _circuit_non_empty(objective_validation)
        and _has_measurement(code, objective_validation)
    )
    return objective_validation


def compute_statistics(values: List[float]) -> Dict[str, float]:
    """Return mean, std, and 95% CI for a list of numeric values."""
    if not values:
        return {"mean": 0.0, "std": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "n": 0}

    n = len(values)
    mean = sum(values) / n
    if n == 1:
        std = 0.0
    else:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(variance)

    if n > 1:
        se = std / math.sqrt(n)
        margin = 1.96 * se
    else:
        margin = 0.0

    return {
        "mean": mean,
        "std": std,
        "ci_lower": mean - margin,
        "ci_upper": mean + margin,
        "n": n,
    }


def wilson_ci(successes: int, trials: int, z: float = 1.96) -> Dict[str, float]:
    """Wilson score interval for binomial proportion (success rate)."""
    if trials == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "n": 0}

    p = successes / trials
    denom = 1 + z**2 / trials
    centre = (p + z**2 / (2 * trials)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2))

    return {
        "mean": p,
        "ci_lower": max(0.0, centre - margin),
        "ci_upper": min(1.0, centre + margin),
        "n": trials,
    }


class MetricsCollector:
    """Collects and aggregates evaluation metrics."""

    def __init__(self):
        """Initialize the MetricsCollector."""
        self.metrics: Dict[str, List[Any]] = defaultdict(list)
        logger.info("Initialized MetricsCollector")

    def collect_code_quality(
        self,
        code: str,
        validation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Collect code quality metrics using the published formula."""
        quality = compute_code_quality_score(code, validation_result)

        metrics = {
            "code_length": len(code),
            "num_lines": len(code.split("\n")),
            "syntax_valid": quality["components"]["syntax_valid"] == 1.0,
            "compilation_success": quality["components"]["compilation_success"] == 1.0,
            "code_quality_score": quality["code_quality_score"],
            "quality_components": quality["components"],
        }

        self.metrics["code_quality"].append(metrics)
        return metrics

    def collect_agent_performance(
        self,
        agent_name: str,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Collect agent performance metrics."""
        metrics = {
            "agent": agent_name,
            "total_requests": stats.get("total_requests", 0),
            "successful_requests": stats.get("successful_requests", 0),
            "failed_requests": stats.get("failed_requests", 0),
            "success_rate": (
                stats.get("successful_requests", 0) / stats.get("total_requests", 1)
                if stats.get("total_requests", 0) > 0
                else 0
            ),
        }

        self.metrics["agent_performance"].append(metrics)
        return metrics

    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all collections."""
        aggregated: Dict[str, Any] = {}

        if self.metrics["code_quality"]:
            quality_metrics = self.metrics["code_quality"]
            scores = [m["code_quality_score"] for m in quality_metrics]
            stats = compute_statistics(scores)
            aggregated["code_quality"] = {
                "total_samples": len(quality_metrics),
                "avg_code_length": sum(m["code_length"] for m in quality_metrics)
                / len(quality_metrics),
                "syntax_valid_rate": sum(m["syntax_valid"] for m in quality_metrics)
                / len(quality_metrics),
                "compilation_success_rate": sum(
                    m["compilation_success"] for m in quality_metrics
                )
                / len(quality_metrics),
                "avg_code_quality_score": stats["mean"],
                "code_quality_std": stats["std"],
                "code_quality_ci_lower": stats["ci_lower"],
                "code_quality_ci_upper": stats["ci_upper"],
            }

        if self.metrics["agent_performance"]:
            perf_metrics = self.metrics["agent_performance"]
            aggregated["agent_performance"] = {
                "total_agents": len(perf_metrics),
                "avg_success_rate": sum(m["success_rate"] for m in perf_metrics)
                / len(perf_metrics),
            }

        return aggregated

    def reset(self) -> None:
        """Reset all collected metrics."""
        self.metrics.clear()
