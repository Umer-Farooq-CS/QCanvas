"""
Sandboxed Python Executor for Hybrid CPU-QPU Execution.

This module provides a secure execution environment for user-provided Python code
that includes quantum circuit compilation and simulation.

IMPORTANT: the API never calls ``execute_sandboxed`` in its own process any
more.  ``backend/app/api/routes/hybrid.py`` runs ``execute_sandboxed_job`` in a
throw-away child process via ``app.services.isolated_exec`` (hard wall-clock
kill, scrubbed environment, rlimits, unprivileged uid).  That child process is
the security boundary.  The restrictions in this module (import blocklist,
trimmed builtins, AST guard, module proxies) are defence in depth and also give
students clear error messages.  The global ``builtins.__import__`` hook and the
``sys.stdout`` swap are process-wide, which is fine in a one-job child process
but NOT safe for concurrent in-process use.

Security features (all configurable via config/config.py):
- Blocked dangerous imports (os, subprocess, sys, socket, etc.)
- Blocked file system access (open, pathlib, io)
- Blocked network access (socket, urllib, requests)
- Blocked shell execution (subprocess, os.system)
- Restricted builtins (no exec, eval, compile, __import__)
- Execution timeout
- Memory limits

Usage:
    from qcanvas_runtime.sandbox import execute_sandboxed
    result = execute_sandboxed(user_code, timeout=30)
    print(result.stdout)
"""

import ast
import sys
import os
import io
import time
import signal
import traceback
import threading
import types
from typing import Any, Dict, Optional, Set
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import builtins

# Add project root to path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from .result import HybridExecutionResult, SimulationResult
# QSim wrapper module (provides qsim.run)
from . import qsim as qsim_wrapper

# Import configuration
try:
    from config.config import (
        HYBRID_EXECUTION_ENABLED,
        HYBRID_BLOCK_DANGEROUS_IMPORTS,
        HYBRID_BLOCK_FILE_ACCESS,
        HYBRID_BLOCK_NETWORK,
        HYBRID_BLOCK_SHELL,
        HYBRID_RESTRICT_BUILTINS,
        HYBRID_BLOCK_CODE_EXECUTION,
        HYBRID_MAX_EXECUTION_TIME,
        HYBRID_MAX_MEMORY_MB,
        HYBRID_MAX_SIMULATION_RUNS,
        HYBRID_MAX_OUTPUT_SIZE,
        HYBRID_ALLOWED_MODULES,
        HYBRID_BLOCKED_MODULES,
        HYBRID_BLOCKED_BUILTINS,
        HYBRID_VERBOSE_LOGGING,
        HYBRID_ALLOW_PRINT,
        HYBRID_CAPTURE_RESULTS,
    )
except ImportError:
    # Fallback defaults if config not available
    HYBRID_EXECUTION_ENABLED = True
    HYBRID_BLOCK_DANGEROUS_IMPORTS = True
    HYBRID_BLOCK_FILE_ACCESS = True
    HYBRID_BLOCK_NETWORK = True
    HYBRID_BLOCK_SHELL = True
    HYBRID_RESTRICT_BUILTINS = True
    HYBRID_BLOCK_CODE_EXECUTION = True
    HYBRID_MAX_EXECUTION_TIME = 60
    HYBRID_MAX_MEMORY_MB = 512
    HYBRID_MAX_SIMULATION_RUNS = 100
    HYBRID_MAX_OUTPUT_SIZE = 100000
    HYBRID_ALLOWED_MODULES = ['cirq', 'qiskit', 'pennylane', 'fastqsim', 'numpy', 'math']
    HYBRID_BLOCKED_MODULES = ['os', 'posix', 'nt', 'sys', 'subprocess', 'socket', 'shutil', 'ctypes',
                              'importlib', 'builtins', 'pickle', 'marshal', 'multiprocessing',
                              'threading', '_thread', 'signal', 'gc', 'inspect', 'types', 'io',
                              'pathlib', 'tempfile', 'asyncio', 'code', 'runpy', 'timeit', 'string']
    HYBRID_BLOCKED_BUILTINS = ['exec', 'eval', 'compile', '__import__', 'open']
    HYBRID_VERBOSE_LOGGING = False
    HYBRID_ALLOW_PRINT = True
    HYBRID_CAPTURE_RESULTS = True


def _log(message: str) -> None:
    """Log message if verbose logging is enabled."""
    if HYBRID_VERBOSE_LOGGING:
        print(f"[Sandbox] {message}")


class SecurityViolationError(Exception):
    """Raised when code attempts a blocked operation."""
    pass


class OutputCapture:
    """Captures stdout and stderr with size limits."""
    
    def __init__(self, max_size: int = HYBRID_MAX_OUTPUT_SIZE):
        self.max_size = max_size
        self._stdout_buffer = io.StringIO()
        self._stderr_buffer = io.StringIO()
        self._stdout_size = 0
        self._stderr_size = 0
        self._original_stdout = None
        self._original_stderr = None
        
        # Standard stream attributes for third-party library compatibility
        self.encoding = sys.stdout.encoding if (sys.stdout and hasattr(sys.stdout, 'encoding')) else "utf-8"
        if not self.encoding:
            self.encoding = "utf-8"
        self.errors = "strict"
        
    def isatty(self) -> bool:
        """Standard IO stream attribute."""
        return False
    
    def __enter__(self):
        self._original_stdout = sys.stdout
        self._original_stderr = sys.stderr
        sys.stdout = self
        sys.stderr = self._create_stderr_wrapper()
        return self
    
    def __exit__(self, *args):
        sys.stdout = self._original_stdout
        sys.stderr = self._original_stderr
    
    def write(self, text: str) -> int:
        """Write to stdout with size limit."""
        if self._stdout_size >= self.max_size:
            return 0
        
        remaining = self.max_size - self._stdout_size
        text_to_write = text[:remaining]
        self._stdout_buffer.write(text_to_write)
        self._stdout_size += len(text_to_write)
        
        # Also write to original stdout for real-time feedback
        if self._original_stdout and HYBRID_VERBOSE_LOGGING:
            self._original_stdout.write(text_to_write)
        
        return len(text_to_write)
    
    def flush(self) -> None:
        """Flush the buffer."""
        self._stdout_buffer.flush()
        if self._original_stdout:
            self._original_stdout.flush()
    
    def _create_stderr_wrapper(self):
        """Create a stderr wrapper."""
        capture = self
        
        class StderrWrapper:
            def __init__(self):
                self.encoding = sys.stderr.encoding if (sys.stderr and hasattr(sys.stderr, 'encoding')) else "utf-8"
                if not self.encoding:
                    self.encoding = "utf-8"
                self.errors = "strict"
                
            def isatty(self) -> bool:
                return False

            def write(self, text: str) -> int:
                if capture._stderr_size >= capture.max_size:
                    return 0
                remaining = capture.max_size - capture._stderr_size
                text_to_write = text[:remaining]
                capture._stderr_buffer.write(text_to_write)
                capture._stderr_size += len(text_to_write)
                return len(text_to_write)
            
            def flush(self) -> None:
                capture._stderr_buffer.flush()
        
        return StderrWrapper()
    
    @property
    def stdout(self) -> str:
        return self._stdout_buffer.getvalue()
    
    @property
    def stderr(self) -> str:
        return self._stderr_buffer.getvalue()


class WrappedFastQSimJob:
    def __init__(self, original_job, qasm_code, shots, backend):
        self._original_job = original_job
        self._qasm_code = qasm_code
        self._shots = shots
        self._backend = backend

    def result(self, *args, **kwargs):
        # Call the original job's result
        res = self._original_job.result(*args, **kwargs)

        # Now gather the stats!
        try:
            counts = res.counts if hasattr(res, 'counts') else {}
            probs = res.probs if hasattr(res, 'probs') else {}
            statevector = res.statevector if hasattr(res, 'statevector') else None
            # Extract performance and billing telemetry from the original job
            exec_time_sec = getattr(self._original_job, 'execution_time_seconds', getattr(res, 'execution_time_seconds', 0.0))
            cpu_time_sec = getattr(self._original_job, 'cpu_seconds_total', 0.0)
            peak_ram_mb = getattr(self._original_job, 'peak_memory_mb', 0.0)
            billing_cpu = getattr(self._original_job, 'billing_cpu_millicore_seconds', 0.0)
            billing_mem = getattr(self._original_job, 'billing_memory_gb_seconds', 0.0)
            
            # Tags and user metadata round-trip
            tags = getattr(self._original_job, 'tags', {})
            job_metadata = getattr(self._original_job, 'metadata', {})
            
            # Lifecycle timestamps (safely converted to ISO strings)
            queue_enqueued_at = getattr(self._original_job, 'queue_enqueued_at', None)
            if hasattr(queue_enqueued_at, 'isoformat'):
                queue_enqueued_at = queue_enqueued_at.isoformat()
            execution_started_at = getattr(self._original_job, 'execution_started_at', None)
            if hasattr(execution_started_at, 'isoformat'):
                execution_started_at = execution_started_at.isoformat()
            execution_finished_at = getattr(self._original_job, 'execution_finished_at', None)
            if hasattr(execution_finished_at, 'isoformat'):
                execution_finished_at = execution_finished_at.isoformat()
            completed_at = getattr(self._original_job, 'completed_at', None)
            if hasattr(completed_at, 'isoformat'):
                completed_at = completed_at.isoformat()

            total_counts = sum(counts.values()) if counts else 0
            probabilities = {}
            if total_counts > 0:
                for state, count in counts.items():
                    probabilities[state] = count / total_counts
            elif probs:
                probabilities = dict(probs)

            exec_time_str = f"{exec_time_sec * 1000:.2f}ms" if exec_time_sec else "0.00ms"
            if exec_time_sec > 0 and cpu_time_sec > 0:
                cpu_pct = min((cpu_time_sec / exec_time_sec) * 100.0, 100.0)
                cpu_time_str = f"{cpu_pct:.1f}%"
            else:
                cpu_time_str = f"{cpu_time_sec * 1000:.1f}%" if cpu_time_sec else "0.0%"
            peak_ram_str = f"{peak_ram_mb:.1f}MB" if peak_ram_mb else "0.1MB"

            sim_result = SimulationResult(
                counts=dict(counts) if counts else {},
                probabilities=probabilities,
                statevector=statevector,
                shots=self._shots,
                backend=self._backend,
                execution_time=exec_time_str,
                simulation_time=exec_time_str,
                memory_usage=peak_ram_str,
                cpu_usage=cpu_time_str,
                fidelity=100.0,
                n_qubits=len(next(iter(counts.keys()))) if counts else 0,
                metadata={
                    "backend": self._backend,
                    "shots": self._shots,
                    "job_id": getattr(self._original_job, 'job_id', None),
                    "online": True,
                    "successful_shots": total_counts,
                    "execution_time_seconds": exec_time_sec,
                    "cpu_seconds_total": cpu_time_sec,
                    "peak_memory_mb": peak_ram_mb,
                    "billing_cpu_millicore_seconds": billing_cpu,
                    "billing_memory_gb_seconds": billing_mem,
                    "tags": tags,
                    "metadata": job_metadata,
                    "queue_enqueued_at": queue_enqueued_at,
                    "execution_started_at": execution_started_at,
                    "execution_finished_at": execution_finished_at,
                    "completed_at": completed_at,
                    "execution_time": exec_time_str,
                    "simulation_time": exec_time_str,
                    "memory_usage": peak_ram_str,
                    "cpu_usage": cpu_time_str,
                },
            )

            # Save this run to qsim's simulation results so that the sandbox extracts it!
            qsim_wrapper._simulation_results.append(sim_result.to_dict())

            # Print to frontend captured console
            print(f"🎯 [FastQSim] Captured simulation stats: Backend: '{self._backend}', Shots: {self._shots}, Counts: {counts}")

            # Write directly to original backend terminal (bypassing sandbox output capture)
            try:
                import sys as _sys
                # Try to find the root original stdout if nested
                orig_stdout = _sys.stdout
                while hasattr(orig_stdout, '_original_stdout') and orig_stdout._original_stdout:
                    orig_stdout = orig_stdout._original_stdout
                orig_stdout.write(f"\n🎯 [Sandbox Interceptor] Captured FastQSim Cloud Job Stats! Backend: '{self._backend}', Shots: {self._shots}, Counts: {counts}\n")
                orig_stdout.flush()
            except Exception:
                pass

        except Exception as e:
            print(f"⚠️ Error capturing fastqsim simulation stats: {e}")

        return res

    def __getattr__(self, name):
        return getattr(self._original_job, name)


class WrappedFastQSimClient:
    def __init__(self, original_client):
        self._original_client = original_client

    def run(self, circuit, shots=2048, asynchronous=False, backend="cirq", **kwargs):
        # Call the original client run
        job = self._original_client.run(
            circuit=circuit,
            shots=shots,
            asynchronous=asynchronous,
            backend=backend,
            **kwargs
        )
        return WrappedFastQSimJob(job, circuit, shots, backend)

    def __getattr__(self, name):
        return getattr(self._original_client, name)


class WrappedFastQSimModule:
    def __init__(self, original_fastqsim):
        self._original_fastqsim = original_fastqsim

    def init(self, *args, **kwargs):
        client = self._original_fastqsim.init(*args, **kwargs)
        return WrappedFastQSimClient(client)

    def __getattr__(self, name):
        return getattr(self._original_fastqsim, name)


USER_CODE_FILENAME = '<user_code>'

_FILE_ACCESS_MODULES = frozenset({'pathlib', 'io', '_io', 'tempfile', 'glob', 'shutil', 'fileinput'})
_NETWORK_MODULES = frozenset({'socket', '_socket', 'ssl', 'urllib', 'urllib3', 'http', 'requests',
                              'aiohttp', 'httpx', 'ftplib', 'smtplib', 'websocket', 'websockets'})
_SHELL_MODULES = frozenset({'subprocess', '_posixsubprocess', 'pty', 'pexpect', 'ptyprocess', 'os'})

# Sub-modules of otherwise-allowed packages that hand out raw ctypes, compile
# native code, or read/write arbitrary files (np.load(allow_pickle=True) is a
# pickle -> code execution primitive).
_BLOCKED_SUBMODULES = frozenset({
    'numpy.ctypeslib', 'numpy.distutils', 'numpy.f2py', 'numpy.lib.npyio', 'numpy.lib.format',
    'numpy.testing', 'scipy.weave', 'pennylane.data',
})

# (module, attribute) pairs that are getattr()/pickle/file-IO bypasses.
_BLOCKED_MEMBERS = frozenset({
    ('operator', 'attrgetter'), ('operator', 'methodcaller'),
    ('numpy', 'load'), ('numpy', 'save'), ('numpy', 'savez'), ('numpy', 'savez_compressed'),
    ('numpy', 'loadtxt'), ('numpy', 'savetxt'), ('numpy', 'genfromtxt'), ('numpy', 'fromfile'),
    ('numpy', 'fromregex'), ('numpy', 'memmap'), ('numpy', 'DataSource'),
})

# Attribute values implemented in these modules are never handed to user code
# through a module proxy (e.g. a library that does `from os import system`).
_DANGEROUS_IMPL_MODULES = frozenset({
    'os', 'posix', 'nt', 'subprocess', '_posixsubprocess', 'socket', '_socket', 'shutil',
    'pickle', '_pickle', 'marshal', 'ctypes', '_ctypes', 'multiprocessing', '_multiprocessing',
    'signal', '_signal', 'importlib', '_imp', 'sys', 'gc', 'inspect', 'pty', 'resource', 'fcntl',
    'io', '_io', 'pathlib', 'tempfile', 'glob', 'runpy', 'code', 'codeop', 'threading', '_thread',
})

# Module attributes that may be read even though they start with "_".
_SAFE_MODULE_DUNDERS = frozenset({'__name__', '__doc__', '__version__', '__all__', '__package__'})


def _blocked_module_names() -> Set[str]:
    blocked: Set[str] = set()
    if HYBRID_BLOCK_DANGEROUS_IMPORTS:
        blocked.update(HYBRID_BLOCKED_MODULES)
    if HYBRID_BLOCK_FILE_ACCESS:
        blocked.update(_FILE_ACCESS_MODULES)
    if HYBRID_BLOCK_NETWORK:
        blocked.update(_NETWORK_MODULES)
    if HYBRID_BLOCK_SHELL:
        blocked.update(_SHELL_MODULES)
    return blocked


def _is_blocked_module_name(full_name: str, blocked: Set[str]) -> bool:
    if not full_name:
        return False
    if full_name.split('.')[0] in blocked:
        return True
    return any(full_name == sub or full_name.startswith(sub + '.') for sub in _BLOCKED_SUBMODULES)


class SandboxedModule:
    """Read-only view of a module handed to user code.

    Blocks private attributes (``random._os``), sub-modules / members that are
    themselves blocked (``numpy.ctypeslib``, ``qcanvas.os``, ``np.load``) and
    wraps sub-modules recursively.  Everything else is returned unchanged, so
    classes, functions and constants behave normally.
    """

    __slots__ = ('_SandboxedModule__target', '_SandboxedModule__blocked')

    def __init__(self, target: Any, blocked: Set[str]):
        object.__setattr__(self, '_SandboxedModule__target', target)
        object.__setattr__(self, '_SandboxedModule__blocked', blocked)

    def __getattribute__(self, name: str) -> Any:
        target = object.__getattribute__(self, '_SandboxedModule__target')
        blocked = object.__getattribute__(self, '_SandboxedModule__blocked')
        return _guarded_module_getattr(target, name, blocked)

    def __setattr__(self, name: str, value: Any) -> None:
        raise SecurityViolationError("Modifying modules is not allowed in the sandbox.")

    def __delattr__(self, name: str) -> None:
        raise SecurityViolationError("Modifying modules is not allowed in the sandbox.")

    def __repr__(self) -> str:
        target = object.__getattribute__(self, '_SandboxedModule__target')
        return f"<module '{getattr(target, '__name__', '?')}'>"


def _guarded_module_getattr(target: Any, name: str, blocked: Set[str]) -> Any:
    owner = getattr(target, '__name__', type(target).__name__)
    if name == '__class__':
        # isinstance() and friends probe __class__; report the proxy type,
        # never the wrapped module's.
        return SandboxedModule
    if name.startswith('__') and name.endswith('__') and name not in _SAFE_MODULE_DUNDERS:
        # Behave like "no such attribute" so hasattr()-style probes by
        # libraries keep working.
        raise AttributeError(f"module '{owner}' has no attribute '{name}' in the sandbox")
    if name.startswith('_') and name not in _SAFE_MODULE_DUNDERS:
        raise SecurityViolationError(
            f"Access to private attribute '{owner}.{name}' is not allowed in the sandbox."
        )
    if (owner, name) in _BLOCKED_MEMBERS:
        raise SecurityViolationError(f"'{owner}.{name}' is not available in the sandbox.")

    value = getattr(target, name)  # AttributeError propagates normally

    if isinstance(value, types.ModuleType):
        sub_name = getattr(value, '__name__', '') or ''
        if _is_blocked_module_name(sub_name, blocked):
            raise SecurityViolationError(
                f"Access to module '{sub_name}' (via '{owner}.{name}') is blocked in the sandbox."
            )
        return SandboxedModule(value, blocked)

    if callable(value):
        try:
            impl_module = getattr(value, '__module__', None)
            impl_name = getattr(value, '__name__', None)
        except Exception:
            impl_module = impl_name = None
        if isinstance(impl_module, str):
            if (impl_module, impl_name) in _BLOCKED_MEMBERS:
                raise SecurityViolationError(f"'{owner}.{name}' is not available in the sandbox.")
            if blocked and impl_module.split('.')[0] in _DANGEROUS_IMPL_MODULES:
                raise SecurityViolationError(
                    f"'{owner}.{name}' comes from blocked module '{impl_module}' and is not available."
                )
    return value


class RestrictedImporter:
    """Custom import hook that blocks dangerous modules.

    Rules are enforced for imports made *directly* by code compiled from a
    string while user code runs: the user's own frames (``<user_code>``) and
    any other string-compiled code (``<string>``, ``<cirq_source>``,
    ``<timeit-src>`` ...), because user code can make libraries exec strings
    it controls.  Imports done by library code living in real files (e.g.
    cirq lazily importing ``os``) are allowed.
    """

    def __init__(self, blocked_modules: Set[str], allowed_modules: Set[str], wrap_modules: bool = True):
        self.blocked_modules = set(blocked_modules)
        self.allowed_modules = allowed_modules
        self.wrap_modules = wrap_modules
        self._original_import = builtins.__import__
        self._installed = False

    def _caller_is_untrusted(self) -> bool:
        try:
            caller_frame = sys._getframe(2)  # 0: here, 1: __call__, 2: importer
        except Exception:
            return True
        filename = caller_frame.f_code.co_filename if caller_frame else ''
        if filename == USER_CODE_FILENAME:
            return True
        return filename.startswith('<') and not filename.startswith('<frozen')

    def __call__(self, name: str, globals: Optional[Dict] = None,
                 locals: Optional[Dict] = None, fromlist: tuple = (),
                 level: int = 0) -> Any:
        """Custom import function that checks against blocked/allowed lists."""
        if not self._caller_is_untrusted():
            return self._original_import(name, globals, locals, fromlist, level)

        base_module = name.split('.')[0]

        # Special case: always route `import qsim` to our safe wrapper
        if base_module == 'qsim' and level == 0 and self.wrap_modules:
            return SandboxedModule(qsim_wrapper, self.blocked_modules)

        # Special case: wrap fastqsim to capture its results
        if base_module == 'fastqsim' and level == 0 and self.wrap_modules:
            real_fastqsim = self._original_import(name, globals, locals, fromlist, level)
            return SandboxedModule(WrappedFastQSimModule(real_fastqsim), self.blocked_modules)

        if base_module in self.blocked_modules:
            if HYBRID_BLOCK_FILE_ACCESS and base_module in _FILE_ACCESS_MODULES:
                reason = "File access is disabled."
            elif HYBRID_BLOCK_NETWORK and base_module in _NETWORK_MODULES:
                reason = "Network access is disabled."
            elif HYBRID_BLOCK_SHELL and base_module in _SHELL_MODULES:
                reason = "Shell access is disabled."
            else:
                reason = f"Module '{base_module}' is not allowed in hybrid execution."
            raise SecurityViolationError(f"Import of '{name}' is blocked for security reasons. {reason}")

        if _is_blocked_module_name(name, self.blocked_modules):
            raise SecurityViolationError(f"Import of '{name}' is blocked for security reasons.")
        for item in fromlist or ():
            if isinstance(item, str) and _is_blocked_module_name(f"{name}.{item}", self.blocked_modules):
                raise SecurityViolationError(f"Import of '{name}.{item}' is blocked for security reasons.")

        module = self._original_import(name, globals, locals, fromlist, level)
        if self.wrap_modules and isinstance(module, types.ModuleType):
            return SandboxedModule(module, self.blocked_modules)
        return module

    def install(self) -> None:
        """Install the restricted importer."""
        builtins.__import__ = self
        self._installed = True

    def uninstall(self) -> None:
        """Restore the original import function."""
        if builtins.__import__ is self:
            builtins.__import__ = self._original_import
        self._installed = False


@contextmanager
def restricted_imports(wrap_modules: bool = False):
    """Apply the import blocklist to string-compiled code inside the block.

    Used around the framework->QASM converters (whose fallback exec()s the
    user's source) in the isolated conversion child.  ``wrap_modules`` is off
    by default there because the converters inspect the exec namespace.
    """
    importer = RestrictedImporter(_blocked_module_names(), set(HYBRID_ALLOWED_MODULES),
                                  wrap_modules=wrap_modules)
    importer.install()
    try:
        yield importer
    finally:
        importer.uninstall()


# Attribute names that are the classic ways out of a Python sandbox
# (object graph walking, frame / code introspection).
_BLOCKED_ATTRIBUTES = frozenset({
    '__class__', '__base__', '__bases__', '__mro__', 'mro', '__subclasses__',
    '__globals__', '__builtins__', '__dict__', '__code__', '__closure__', '__func__',
    '__self__', '__getattribute__', '__reduce__', '__reduce_ex__', '__import__',
    '__loader__', '__spec__', '__traceback__', '__init_subclass__', '__subclasshook__',
    '__defaults__', '__kwdefaults__', '__objclass__', '__getstate__', '__setstate__',
    'f_globals', 'f_locals', 'f_back', 'f_builtins', 'f_code', 'f_trace',
    'gi_frame', 'gi_code', 'gi_yieldfrom', 'cr_frame', 'cr_code', 'cr_await',
    'ag_frame', 'ag_code', 'tb_frame', 'tb_next', 'co_code', 'co_consts', 'co_names',
    'func_globals',
})
_BLOCKED_NAMES = frozenset({'__builtins__', '__import__', '__loader__', '__spec__', '__build_class__'})


def find_unsafe_constructs(tree: ast.AST) -> list:
    """Return ``[(lineno, message), ...]`` for sandbox-escape constructs."""
    problems = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in _BLOCKED_ATTRIBUTES:
            problems.append((getattr(node, 'lineno', None),
                             f"Access to attribute '{node.attr}' is not allowed in the sandbox."))
        elif isinstance(node, ast.Name) and node.id in _BLOCKED_NAMES:
            problems.append((getattr(node, 'lineno', None),
                             f"Use of '{node.id}' is not allowed in the sandbox."))
    return problems


def _create_safe_builtins() -> Dict[str, Any]:
    """Create a dictionary of safe builtin functions."""
    # Start with all builtins
    safe_builtins = dict(builtins.__dict__)
    
    if HYBRID_RESTRICT_BUILTINS:
        # Remove blocked builtins
        for name in HYBRID_BLOCKED_BUILTINS:
            # Keep __import__ so that Python's import system continues to work;
            # actual import security is enforced by RestrictedImporter instead.
            if name == '__import__':
                continue
            safe_builtins.pop(name, None)
        
        # Additional safety: remove dangerous functions
        if HYBRID_BLOCK_CODE_EXECUTION:
            # Block direct code-evaluation helpers but keep __import__
            for name in ['exec', 'eval', 'compile']:
                safe_builtins.pop(name, None)
        
        if HYBRID_BLOCK_FILE_ACCESS:
            safe_builtins.pop('open', None)
            safe_builtins.pop('input', None)

        # Import machinery handles that bypass the import hook.
        for name in ('__loader__', '__spec__'):
            safe_builtins.pop(name, None)

    return safe_builtins


def _create_execution_globals(blocked_modules: Optional[Set[str]] = None) -> Dict[str, Any]:
    """Create the global namespace for code execution."""
    # Import qcanvas and qsim for the sandboxed environment
    from . import core as qcanvas_module
    from . import qsim as qsim_module
    from . import result as result_module
    
    # Create safe builtins
    safe_builtins = _create_safe_builtins()
    blocked = _blocked_module_names() if blocked_modules is None else blocked_modules

    # Build the global namespace
    globals_dict = {
        '__builtins__': safe_builtins,
        '__name__': '__main__',
        '__doc__': None,

        # QCanvas API (modules are wrapped so e.g. `qcanvas.os` is not reachable)
        'qcanvas': SandboxedModule(qcanvas_module, blocked),
        'compile': qcanvas_module.compile,
        'compile_and_execute': qcanvas_module.compile_and_execute,

        # QSim API (as a module)
        'qsim': SandboxedModule(qsim_module, blocked),
        
        # Result types
        'SimulationResult': result_module.SimulationResult,
    }
    
    # Add print if allowed
    if HYBRID_ALLOW_PRINT:
        globals_dict['print'] = builtins.print
    
    return globals_dict


def _extract_error_line(tb_string: str, code: str) -> Optional[int]:
    """Extract the user-code line number from a traceback string."""
    import re

    # Prefer the deepest frame that belongs to the user's program.
    matches = re.findall(r'File "<user_code>", line (\d+)', tb_string)
    if matches:
        return int(matches[-1])

    # Fall back to the last "line X" in the traceback
    matches = re.findall(r'line (\d+)', tb_string)
    if matches:
        return int(matches[-1])  # Return the last (most specific) line number

    return None


def execute_sandboxed(
    code: str,
    timeout: Optional[int] = None,
    framework_hint: Optional[str] = None
) -> HybridExecutionResult:
    """
    Execute Python code in a sandboxed environment.

    This function runs user-provided Python code with security restrictions.
    The code has access to:
    - qcanvas.compile() for circuit compilation
    - qsim.run() for quantum simulation
    - print() for output
    - Standard safe modules (numpy, math, cirq, qiskit, pennylane)

    The API calls this inside a dedicated child process (see
    ``execute_sandboxed_job``) with ``timeout=0``; the parent enforces the
    wall-clock limit by killing the process.  A positive ``timeout`` is only a
    best-effort, in-process fallback: Python cannot kill a thread, so a
    runaway loop keeps burning CPU in the background after the timeout.

    Args:
        code: Python code to execute
        timeout: Maximum execution time in seconds (default from config,
            0 = no in-process timeout)
        framework_hint: Hint about the quantum framework being used

    Returns:
        HybridExecutionResult with stdout, simulation results, and any errors

    Example:
        >>> code = '''
        ... import cirq
        ... from qcanvas import compile
        ... import qsim
        ...
        ... q = cirq.LineQubit.range(2)
        ... circuit = cirq.Circuit([cirq.H(q[0]), cirq.CNOT(q[0], q[1])])
        ... qasm = compile(circuit, framework="cirq")
        ... print(f"QASM: {qasm[:50]}...")
        ... result = qsim.run(qasm, shots=100)
        ... print(f"Counts: {result.counts}")
        ... '''
        >>> result = execute_sandboxed(code)
        >>> print(result.stdout)
    """
    if not HYBRID_EXECUTION_ENABLED:
        return HybridExecutionResult.from_error(
            "Hybrid execution is disabled",
            error_type="DisabledError"
        )

    # Use config timeout if not specified
    if timeout is None:
        timeout = HYBRID_MAX_EXECUTION_TIME

    _log(f"Executing code with timeout={timeout}s")

    # Clear previous simulation results
    from . import qsim as qsim_module
    qsim_module.clear_simulation_results()

    # Track generated QASM
    last_qasm = None

    start_time = time.time()

    # Syntax check and static guard before anything is installed.
    try:
        tree = ast.parse(code, filename=USER_CODE_FILENAME, mode='exec')
    except SyntaxError as e:
        return HybridExecutionResult.from_error(
            f"Syntax error: {e.msg}",
            error_type="SyntaxError",
            error_line=e.lineno
        )
    except (ValueError, MemoryError, RecursionError) as e:
        return HybridExecutionResult.from_error(
            f"Could not parse the program: {e}",
            error_type="SyntaxError",
        )
    if HYBRID_RESTRICT_BUILTINS:
        problems = find_unsafe_constructs(tree)
        if problems:
            line, message = problems[0]
            return HybridExecutionResult.from_error(
                message,
                error_type="SecurityViolationError",
                error_line=line,
            )

    # Set up output capture
    output_capture = OutputCapture(max_size=HYBRID_MAX_OUTPUT_SIZE)

    # Set up restricted importer
    blocked_set = _blocked_module_names()
    allowed_set = set(HYBRID_ALLOWED_MODULES)
    restricted_importer = RestrictedImporter(blocked_set, allowed_set)

    try:
        compiled_code = builtins.compile(tree, USER_CODE_FILENAME, 'exec')

        # Install security hooks
        restricted_importer.install()

        # Create execution environment
        exec_globals = _create_execution_globals(blocked_set)
        exec_locals = exec_globals

        # Execute with timeout
        def execute_code():
            with output_capture:
                exec(compiled_code, exec_globals, exec_locals)

        if timeout and timeout > 0:
            # Best-effort in-process timeout (see docstring).  Do NOT use
            # `with ThreadPoolExecutor(...)`: its __exit__ waits for the
            # runaway thread, which turned a timeout into a permanent hang.
            executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sandbox")
            future = executor.submit(execute_code)
            try:
                future.result(timeout=timeout)
            except FuturesTimeoutError:
                executor.shutdown(wait=False, cancel_futures=True)
                # The worker thread is still inside `with output_capture`;
                # give the process its real streams back.
                if sys.stdout is output_capture:
                    sys.stdout = output_capture._original_stdout
                    sys.stderr = output_capture._original_stderr
                restricted_importer.uninstall()
                return HybridExecutionResult(
                    success=False,
                    stdout=output_capture.stdout,
                    error=f"Execution timed out after {timeout} seconds",
                    error_type="TimeoutError",
                    execution_time=f"{(time.time() - start_time)*1000:.2f}ms",
                )
            executor.shutdown(wait=False)
        else:
            # No in-process timeout (the isolated runner enforces one)
            execute_code()

        # Get execution time
        execution_time = time.time() - start_time

        # Get simulation results
        simulation_results = qsim_module.get_simulation_results()

        # Get last generated QASM if any compile was called
        for name, value in list(exec_locals.items()):
            if isinstance(value, str) and 'OPENQASM' in value:
                last_qasm = value
                break

        return HybridExecutionResult(
            success=True,
            stdout=output_capture.stdout,
            stderr=output_capture.stderr,
            qasm_generated=last_qasm,
            simulation_results=simulation_results,
            execution_time=f"{execution_time*1000:.2f}ms",
        )

    except (Exception, SystemExit) as e:
        # Make sure we restore the original import mechanism before
        # Python's traceback machinery tries to import stdlib modules
        # like 'os' and 'linecache' internally.
        try:
            restricted_importer.uninstall()
        except Exception:
            pass

        # Get full traceback
        tb_string = traceback.format_exc()
        error_line = _extract_error_line(tb_string, code)

        # Get error type
        error_type = type(e).__name__

        # Get error message
        error_msg = str(e)
        if not error_msg:
            error_msg = error_type

        _log(f"Execution error: {error_type}: {error_msg}")
        _log(f"Traceback:\n{tb_string}")

        return HybridExecutionResult(
            success=False,
            stdout=output_capture.stdout if output_capture else "",
            stderr=tb_string if not isinstance(e, SecurityViolationError) else "",
            error=error_msg,
            error_type=error_type,
            error_line=error_line,
            execution_time=f"{(time.time() - start_time)*1000:.2f}ms",
            simulation_results=qsim_module.get_simulation_results(),
        )

    finally:
        # Always restore original import
        restricted_importer.uninstall()


def execute_sandboxed_job(
    code: str,
    framework_hint: Optional[str] = None,
    online_mode: Optional[bool] = None,
) -> Dict[str, Any]:
    """Child-process entry point used by the hybrid API route.

    Runs ``execute_sandboxed`` without an in-process timeout (the parent kills
    the whole process when the wall-clock budget is exceeded) and returns a
    plain, JSON-serialisable dict.
    """
    from . import qsim as qsim_module

    if online_mode is not None:
        qsim_module.set_online_mode_override(bool(online_mode))
    result = execute_sandboxed(code, timeout=0, framework_hint=framework_hint)
    return result.to_dict()


def validate_code(code: str) -> Dict[str, Any]:
    """
    Validate Python code without executing it.
    
    Checks for:
    - Syntax errors
    - Blocked imports
    - Dangerous patterns
    
    Args:
        code: Python code to validate
        
    Returns:
        Dictionary with 'valid' boolean and optional 'errors' list
    """
    errors = []
    warnings = []
    
    # Check syntax
    try:
        import ast
        tree = ast.parse(code)
    except SyntaxError as e:
        return {
            'valid': False,
            'errors': [f"Syntax error at line {e.lineno}: {e.msg}"]
        }
    
    # Check for blocked imports
    blocked = _blocked_module_names()
    if blocked:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_blocked_module_name(alias.name, blocked):
                        errors.append(
                            f"Line {node.lineno}: Import of '{alias.name}' is blocked"
                        )

            elif isinstance(node, ast.ImportFrom):
                if node.module and _is_blocked_module_name(node.module, blocked):
                    errors.append(
                        f"Line {node.lineno}: Import from '{node.module}' is blocked"
                    )

    # Check for blocked builtins usage
    if HYBRID_RESTRICT_BUILTINS:
        for line, message in find_unsafe_constructs(tree):
            errors.append(f"Line {line}: {message}")
        # `compile` / `compile_and_execute` are qcanvas's own functions in the
        # sandbox namespace, not the Python builtins.
        provided = {'compile', 'compile_and_execute'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in HYBRID_BLOCKED_BUILTINS and node.func.id not in provided:
                        errors.append(
                            f"Line {node.lineno}: Use of '{node.func.id}()' is blocked"
                        )
    
    # Check for open() calls
    if HYBRID_BLOCK_FILE_ACCESS:
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == 'open':
                    errors.append(f"Line {node.lineno}: File access is blocked")
    
    return {
        'valid': len(errors) == 0,
        'errors': errors if errors else None,
        'warnings': warnings if warnings else None,
    }
