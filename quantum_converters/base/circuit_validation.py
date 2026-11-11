"""
Structural validation of a CircuitAST before it is turned into OpenQASM.

The static (AST-based) parsers translate Python source without running it.  When
they meet something they cannot model exactly they used to emit *plausible but
wrong* QASM (unresolved names, out-of-range qubits, dropped gates).  This module
is the safety net: it rejects any CircuitAST that is not fully resolved so the
caller can fall back to a faithful path (runtime execution) or report a clear
error -- never silently simulate the wrong circuit.

Usage:
    validate_circuit_ast(circuit_ast)          # raises UnsupportedCircuitError
"""

import ast
import itertools
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence

from quantum_converters.base.circuit_ast import (
    BarrierNode, CircuitAST, ForLoopNode, GateNode, IfStatementNode, MeasurementNode, ResetNode,
)


class UnsupportedCircuitError(ValueError):
    """The source program uses something the converter cannot translate faithfully."""


# name -> (number of qubits, number of parameters); modifiers add control qubits.
GATE_SIGNATURES: Dict[str, tuple] = {
    "id": (1, 0), "i": (1, 0), "x": (1, 0), "y": (1, 0), "z": (1, 0), "h": (1, 0),
    "s": (1, 0), "sdg": (1, 0), "t": (1, 0), "tdg": (1, 0), "sx": (1, 0),
    "rx": (1, 1), "ry": (1, 1), "rz": (1, 1), "p": (1, 1), "phase": (1, 1), "u1": (1, 1),
    "u2": (1, 2), "u": (1, 3), "u3": (1, 3), "U": (1, 3),
    "cx": (2, 0), "CX": (2, 0), "cy": (2, 0), "cz": (2, 0), "ch": (2, 0), "swap": (2, 0), "iswap": (2, 0),
    "crx": (2, 1), "cry": (2, 1), "crz": (2, 1), "cp": (2, 1), "cphase": (2, 1), "cu1": (2, 1),
    "rxx": (2, 1), "ryy": (2, 1), "rzz": (2, 1),
    "cu3": (2, 3), "cu": (2, 4),
    "ccx": (3, 0), "ccz": (3, 0), "cswap": (3, 0),
    "gphase": (0, 1),
}

# Identifiers allowed inside parameter expressions besides declared parameters / loop vars.
_MATH_NAMES = {
    "pi", "π", "tau", "τ", "euler", "ℇ", "e",
    "sin", "cos", "tan", "arcsin", "arccos", "arctan", "exp", "ln", "log", "sqrt",
}
_IDENT_RE = re.compile(r"[^\W\d][\w]*", re.UNICODE)
_MAX_LOOP_COMBINATIONS = 4096


def _safe_int_eval(expr: str, env: Dict[str, int]) -> int:
    """Evaluate a small integer expression (loop-variable arithmetic) without eval()."""
    tree = ast.parse(str(expr), mode="eval")

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in env:
                raise UnsupportedCircuitError(f"unresolved name '{node.id}' in index expression '{expr}'")
            return env[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            v = ev(node.operand)
            return -v if isinstance(node.op, ast.USub) else v
        if isinstance(node, ast.BinOp):
            a, b = ev(node.left), ev(node.right)
            if isinstance(node.op, ast.Add):
                return a + b
            if isinstance(node.op, ast.Sub):
                return a - b
            if isinstance(node.op, ast.Mult):
                return a * b
            if isinstance(node.op, ast.FloorDiv):
                return a // b
            if isinstance(node.op, ast.Mod):
                return a % b
            if isinstance(node.op, ast.Pow):
                return a ** b
        raise UnsupportedCircuitError(f"cannot evaluate index expression '{expr}'")

    return ev(tree)


class _Validator:
    def __init__(self, circuit: CircuitAST):
        self.circuit = circuit
        self.n_qubits = int(circuit.qubits or 0)
        self.n_clbits = int(circuit.clbits or 0)
        params = circuit.parameters or []
        self.param_names = set(params if not isinstance(params, dict) else params.keys())
        self.array_params = dict(getattr(circuit, "array_parameters", {}) or {})
        self.errors: List[str] = []

    # -- helpers ---------------------------------------------------------
    def _envs(self, loops: Sequence[tuple]) -> Iterable[Dict[str, int]]:
        if not loops:
            yield {}
            return
        names = [name for name, _ in loops]
        ranges = [values for _, values in loops]
        total = 1
        for r in ranges:
            total *= max(1, len(r))
        if total > _MAX_LOOP_COMBINATIONS:
            # Check the extremes only.
            ranges = [sorted({r[0], r[-1]}) if r else r for r in ranges]
        for combo in itertools.product(*ranges):
            yield dict(zip(names, combo))

    def _check_index(self, value: Any, size: int, kind: str, loops, where: str) -> None:
        if isinstance(value, bool):
            self.errors.append(f"{where}: invalid {kind} index {value!r}")
            return
        if isinstance(value, int):
            if not 0 <= value < size:
                self.errors.append(f"{where}: {kind} index {value} is out of range (register size {size})")
            return
        if isinstance(value, str):
            try:
                for env in self._envs(loops):
                    v = _safe_int_eval(value, env)
                    if not 0 <= v < size:
                        self.errors.append(
                            f"{where}: {kind} index '{value}' evaluates to {v}, out of range (register size {size})")
                        return
            except UnsupportedCircuitError as e:
                self.errors.append(f"{where}: {e}")
            except (SyntaxError, ZeroDivisionError):
                self.errors.append(f"{where}: invalid {kind} index '{value}'")
            return
        self.errors.append(f"{where}: unresolved {kind} index {value!r}")

    def _check_param(self, value: Any, loops, where: str) -> None:
        if isinstance(value, bool) or value is None:
            self.errors.append(f"{where}: missing/invalid parameter {value!r}")
            return
        if isinstance(value, (int, float)):
            return
        try:
            import numpy as np
            if isinstance(value, np.number):
                return
        except Exception:
            pass
        if not isinstance(value, str):
            self.errors.append(f"{where}: unsupported parameter value {value!r}")
            return
        text = value.strip()
        if not text or text == "expr":
            self.errors.append(f"{where}: could not determine a parameter value")
            return
        loop_vars = {name for name, _ in loops}
        for ident in _IDENT_RE.findall(text):
            if ident in _MATH_NAMES or ident in loop_vars:
                continue
            if ident in self.param_names or ident in self.array_params:
                continue
            self.errors.append(f"{where}: parameter expression '{text}' uses unknown name '{ident}'")
            return

    def _check_condition(self, condition: str, loops, where: str) -> None:
        text = str(condition)
        loop_vars = {name for name, _ in loops}
        for ident in _IDENT_RE.findall(text):
            if ident in ("c", "true", "false") or ident in loop_vars:
                continue
            self.errors.append(
                f"{where}: condition '{text}' depends on '{ident}', which is not a measured classical bit")
            return
        for match in re.finditer(r"\bc\[([^\]]+)\]", text):
            self._check_index(match.group(1).strip(), self.n_clbits, "classical bit", loops, where)
        if re.search(r"\bc\b(?!\s*\[)", text) and self.n_clbits == 0:
            self.errors.append(f"{where}: condition '{text}' reads classical bits but none are declared")

    # -- walk ---------------------------------------------------------------
    def walk(self, ops, loops: tuple = ()) -> None:
        for op in ops:
            if isinstance(op, GateNode):
                self._gate(op, loops)
            elif isinstance(op, MeasurementNode):
                self._check_index(op.qubit, self.n_qubits, "qubit", loops, "measure")
                self._check_index(op.clbit, self.n_clbits, "classical bit", loops, "measure")
            elif isinstance(op, ResetNode):
                self._check_index(op.qubit, self.n_qubits, "qubit", loops, "reset")
            elif isinstance(op, BarrierNode):
                for q in op.qubits or []:
                    self._check_index(q, self.n_qubits, "qubit", loops, "barrier")
            elif isinstance(op, ForLoopNode):
                start, end = op.range_start, op.range_end
                if not isinstance(start, int) or not isinstance(end, int) or isinstance(start, bool) or isinstance(end, bool):
                    self.errors.append(
                        f"for-loop over '{op.variable}': range bounds ({start!r}, {end!r}) are not compile-time integers")
                    continue
                values = list(range(start, end))
                self.walk(op.body, loops + ((op.variable, values),))
            elif isinstance(op, IfStatementNode):
                self._check_condition(op.condition, loops, "if")
                self.walk(op.body, loops)
                if op.else_body:
                    self.walk(op.else_body, loops)
            else:
                self.errors.append(f"unsupported operation {type(op).__name__}")

    def _gate(self, op: GateNode, loops) -> None:
        name = op.name
        where = f"gate '{name}'"
        sig = GATE_SIGNATURES.get(name)
        if sig is None:
            self.errors.append(f"{where}: not a supported OpenQASM gate")
            return
        n_q, n_p = sig
        modifiers = op.modifiers or {}
        n_ctrl = 0
        for key in ("ctrl", "negctrl"):
            if key in modifiers:
                val = modifiers[key]
                n_ctrl += len(val) if isinstance(val, (list, tuple)) else int(val)
        expected_q = n_q + n_ctrl
        if len(op.qubits) != expected_q:
            self.errors.append(f"{where}: expects {expected_q} qubit(s), got {len(op.qubits)}")
        if len(op.parameters or []) != n_p:
            self.errors.append(f"{where}: expects {n_p} parameter(s), got {len(op.parameters or [])}")
        for q in op.qubits:
            self._check_index(q, self.n_qubits, "qubit", loops, where)
        if all(isinstance(q, int) for q in op.qubits) and len(set(op.qubits)) != len(op.qubits):
            self.errors.append(f"{where}: the same qubit is used twice {op.qubits}")
        for p in op.parameters or []:
            self._check_param(p, loops, where)


def validate_circuit_ast(circuit: CircuitAST, framework: Optional[str] = None) -> None:
    """Raise UnsupportedCircuitError listing every problem found (empty list == OK)."""
    v = _Validator(circuit)
    if v.n_qubits <= 0 and circuit.operations:
        v.errors.append("could not determine the number of qubits")
    v.walk(circuit.operations)
    if v.errors:
        unique = list(dict.fromkeys(v.errors))
        prefix = f"{framework} " if framework else ""
        raise UnsupportedCircuitError(
            f"The {prefix}circuit could not be translated exactly: " + "; ".join(unique[:8])
            + (f" (+{len(unique) - 8} more)" if len(unique) > 8 else "")
        )
