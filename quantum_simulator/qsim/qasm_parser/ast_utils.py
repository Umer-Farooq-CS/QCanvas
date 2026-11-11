import pyqasm
import os
from qsim.qasm_parser.parser import parse_openqasm3

def list_node_types(module: pyqasm.Qasm3Module):
    """Return all unique AST node types in a parsed module."""
    return {type(stmt).__name__ for stmt in module._statements}


def collect_all_nodes(example_dir="../../examples/test.qasm"):
    all_nodes = set()
    for fname in os.listdir(example_dir):
        if fname.endswith(".qasm"):
            path = os.path.join(example_dir, fname)
            with open(path) as f:
                qasm_code = f.read()
            try:
                module = parse_openqasm3(qasm_code)
                nodes = list_node_types(module)
                all_nodes |= nodes  # union
            except Exception as e:
                print(f"⚠️ Failed parsing {fname}: {e}")
    return all_nodes


if __name__ == "__main__":
    # Developer utility only: never scan the filesystem at import time.
    import sys
    node_types = collect_all_nodes(sys.argv[1] if len(sys.argv) > 1 else "examples")
    print("Unique AST node types found across examples:")
    for node in sorted(node_types):
        print(" -", node)
