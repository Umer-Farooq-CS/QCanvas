"""
Safe static evaluation of numeric Python expressions found in user source code.

The AST parsers must never run user code (no eval/exec).  This walks a Python
expression AST and computes its value when it only involves literals, known
numeric variables, pi, simple arithmetic and a whitelist of math functions.
Anything else raises NotStatic, so callers can treat the value as symbolic or
report the construct as unsupported.
"""

import ast
import math
import operator
from typing import Any, Dict, Mapping

import numpy as np


class NotStatic(Exception):
    """The expression cannot be evaluated without running the program."""


_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}

_CONSTANTS = {"pi": math.pi, "e": math.e, "tau": math.tau}
_FUNCTIONS = {
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "arcsin": math.asin, "asin": math.asin,
    "arccos": math.acos, "acos": math.acos, "arctan": math.atan, "atan": math.atan,
    "arctan2": math.atan2, "atan2": math.atan2, "exp": math.exp, "log": math.log, "sqrt": math.sqrt,
    "abs": abs, "radians": math.radians, "deg2rad": math.radians, "float": float, "int": int,
}
_MODULES = {"np", "numpy", "math", "pnp", "jnp"}
_MAX_POW = 4096


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool)


def static_eval(node: ast.AST, variables: Mapping[str, Any] = None) -> Any:
    """
    Evaluate ``node`` statically. Returns an int/float, or a (nested) list/tuple of
    numbers for list literals. Raises NotStatic otherwise.
    """
    variables = variables or {}

    def ev(n):
        if isinstance(n, ast.Expression):
            return ev(n.body)
        if isinstance(n, ast.Constant):
            if _is_number(n.value):
                return n.value
            raise NotStatic(f"non-numeric literal {n.value!r}")
        if isinstance(n, ast.Name):
            if n.id in variables:
                val = variables[n.id]
                if _is_number(val):
                    return val
                if isinstance(val, (list, tuple)) and all(_is_number(v) for v in _flatten(val)):
                    return val
                raise NotStatic(f"'{n.id}' is not a known number")
            if n.id in _CONSTANTS:
                return _CONSTANTS[n.id]
            raise NotStatic(f"unknown name '{n.id}'")
        if isinstance(n, ast.Attribute):
            if isinstance(n.value, ast.Name) and n.value.id in _MODULES and n.attr in _CONSTANTS:
                return _CONSTANTS[n.attr]
            raise NotStatic(f"unsupported attribute {ast.unparse(n)}")
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN_OPS:
            a, b = ev(n.left), ev(n.right)
            if not (_is_number(a) and _is_number(b)):
                raise NotStatic("arithmetic on non-numbers")
            if isinstance(n.op, ast.Pow) and abs(b) > _MAX_POW:
                raise NotStatic("exponent too large")
            try:
                return _BIN_OPS[type(n.op)](a, b)
            except (ZeroDivisionError, OverflowError, ValueError) as e:
                raise NotStatic(str(e))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UNARY_OPS:
            v = ev(n.operand)
            if not _is_number(v):
                raise NotStatic("unary op on non-number")
            return _UNARY_OPS[type(n.op)](v)
        if isinstance(n, ast.Call) and not n.keywords:
            fname = None
            if isinstance(n.func, ast.Name):
                fname = n.func.id
            elif isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id in _MODULES:
                fname = n.func.attr
            if fname == "array" and len(n.args) == 1:
                return ev(n.args[0])
            if fname in _FUNCTIONS:
                args = [ev(a) for a in n.args]
                if not all(_is_number(a) for a in args):
                    raise NotStatic("function of non-numbers")
                try:
                    return _FUNCTIONS[fname](*args)
                except (ValueError, OverflowError, TypeError) as e:
                    raise NotStatic(str(e))
            raise NotStatic(f"unsupported call {ast.unparse(n)}")
        if isinstance(n, (ast.List, ast.Tuple)):
            return [ev(e) for e in n.elts]
        if isinstance(n, ast.Subscript):
            base = ev(n.value)
            idx_node = n.slice
            if hasattr(ast, "Index") and isinstance(idx_node, getattr(ast, "Index")):
                idx_node = idx_node.value
            indices = [ev(e) for e in idx_node.elts] if isinstance(idx_node, ast.Tuple) else [ev(idx_node)]
            cur = base
            for idx in indices:
                if not isinstance(cur, (list, tuple)) or not isinstance(idx, (int, np.integer)):
                    raise NotStatic("unsupported subscript")
                try:
                    cur = cur[int(idx)]
                except IndexError:
                    raise NotStatic("index out of range")
            return cur
        raise NotStatic(f"unsupported expression {type(n).__name__}")

    return ev(node)


def static_number(node: ast.AST, variables: Mapping[str, Any] = None):
    """Like static_eval but only accepts a scalar number."""
    value = static_eval(node, variables)
    if not _is_number(value):
        raise NotStatic("not a scalar number")
    return value


def _flatten(seq):
    for item in seq:
        if isinstance(item, (list, tuple)):
            yield from _flatten(item)
        else:
            yield item
