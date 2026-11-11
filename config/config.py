"""
Shared config used by converters/parsers.

This module exists primarily to satisfy imports like `from config.config import VERBOSE, vprint`.
Keep it dependency-free so tests can import converter modules without requiring
the full backend configuration stack.
"""

from __future__ import annotations

from typing import Any


# Verbose debug printing for converters/parsers.
VERBOSE: bool = False


# Some converters gate extra QASM variable/constant emission on these flags.
INCLUDE_VARS: bool = True
INCLUDE_CONSTANTS: bool = True


def vprint(*args: Any, **kwargs: Any) -> None:
    """Verbose print helper (no-op unless VERBOSE=True)."""
    if VERBOSE:
        print(*args, **kwargs)

"""
Global configuration for QCanvas.

Centralizes runtime flags and tunables to avoid scattering constants
throughout the codebase. Import from this module rather than redefining
per-file settings.

Also provides a simple logging facility that writes all verbose
messages to per-run log files under the `logs/` directory regardless of
the VERBOSE console flag.
"""

# Verbose logging for parsers/converters (set to False to silence)
VERBOSE: bool = True

# Global builder prelude flags (used by all converters)
# Controls whether classical variables and mathematical constants are emitted
# in the standard prelude. Adjust here to affect all conversion outputs.
INCLUDE_VARS: bool = False
INCLUDE_CONSTANTS: bool = True

import os
import sys
from datetime import datetime
from typing import Any

# Ensure logs directory and a per-run log file exist
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
LOG_ROOT_DIR = os.path.join(_PROJECT_ROOT, "logs")
try:
    os.makedirs(LOG_ROOT_DIR, exist_ok=True)
except OSError:
    pass

def _month_dir_for(dt: datetime) -> str:
    """Return directory path logs/YYYY/Mon for the given datetime, creating it if needed."""
    year = dt.strftime("%Y")
    month_abbr = dt.strftime("%b")  # Jan, Feb, ...
    month_dir = os.path.join(LOG_ROOT_DIR, year, month_abbr)
    try:
        os.makedirs(month_dir, exist_ok=True)
    except OSError:
        pass
    return month_dir

_RUN_DT = datetime.now()
_RUN_TIMESTAMP = _RUN_DT.strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(_month_dir_for(_RUN_DT), f"run_{_RUN_TIMESTAMP}.log")
_SESSION_COUNTER = 0

# Emit a header for this run
def _emit_log_header() -> None:
    header_lines = [
        "=" * 80,
        "QCanvas Run Log",
        f"Start Time: {datetime.now().isoformat(timespec='seconds')}",
        f"Process: pid={os.getpid()} python={sys.version.split()[0]}",
        f"Working Dir: {os.getcwd()}",
        f"Verbose Console: {VERBOSE}",
        "=" * 80,
        "",
    ]
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write("\n".join(header_lines))
    except OSError:
        # Never break the app (or a sandboxed, unprivileged child) over logging.
        pass

if not os.path.exists(LOG_FILE):
    _emit_log_header()


def new_log_session(name: str = "run") -> str:
    """Rotate to a new per-session log file with a friendly name.

    Example: new_log_session("convert_qiskit") → logs/convert_qiskit_2025-10-03_19-30-12_01.log
    Returns the path to the new log file.
    """
    global LOG_FILE, _SESSION_COUNTER
    _SESSION_COUNTER += 1
    now = datetime.now()
    ts = now.strftime("%Y-%m-%d_%H-%M-%S")
    safe = "".join(ch for ch in name if ch.isalnum() or ch in ("-", "_")) or "run"
    LOG_FILE = os.path.join(_month_dir_for(now), f"{safe}_{ts}_{_SESSION_COUNTER:02d}.log")
    _emit_log_header()
    return LOG_FILE


def _write_log_line(message: str) -> None:
    """Append a single line to the current run log file."""
    try:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        # Never break the app due to logging
        pass


def vprint(*args: Any, **kwargs: Any) -> None:
    """Verbose print routed to console (when VERBOSE) and always to log file.

    Usage:
        from config.config import vprint
        vprint("message", var=val)
    """
    # Build a single string like print would
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    msg = sep.join(str(a) for a in args)

    # Console output controlled by VERBOSE
    if VERBOSE:
        # Use built-in print with the original kwargs
        print(msg, end=end)

    # Always write to log file without the trailing end
    _write_log_line(msg)

# =============================================================================
# FRONTEND / API ROUTING SETTINGS
# =============================================================================
# These flags control how the frontend should talk to the backend API.
# NOTE: The Next.js frontend cannot import this Python module directly, so you
# should keep the equivalent setting in `frontend/lib/api.ts` in sync manually.
#
# When DISABLE_REMOTE_API_FALLBACK is True:
#   - The frontend should ONLY use the local backend
#   - No automatic fallback to the Railway/production URL
# When False:
#   - The frontend may fall back to NEXT_PUBLIC_API_BASE / Railway when
#     the local backend is not reachable.

DISABLE_REMOTE_API_FALLBACK: bool = True


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None and raw.strip() != "" else default
    except ValueError:
        value = default
    return max(minimum, value)


# =============================================================================
# HYBRID EXECUTION SECURITY SETTINGS
# =============================================================================
# These settings control security restrictions for hybrid CPU-QPU execution.
# By default, all restrictions are ENABLED (True = blocked/restricted).
# Set to False to disable specific restrictions (use with caution!).
#
# NOTE: the real security boundary is the per-run child process
# (backend/app/services/isolated_exec.py: separate process, scrubbed env,
# rlimits, privilege drop, hard wall-clock kill). Everything below is
# defence in depth inside that child.

# Block dangerous imports (os, subprocess, sys, socket, shutil, pickle, etc.)
HYBRID_BLOCK_DANGEROUS_IMPORTS: bool = _env_bool("HYBRID_BLOCK_DANGEROUS_IMPORTS", True)

# Block file system access (open(), pathlib, io, tempfile, glob)
HYBRID_BLOCK_FILE_ACCESS: bool = True

# Block network access (socket, urllib, requests, http, ftplib)
HYBRID_BLOCK_NETWORK: bool = True

# Block shell/subprocess execution (subprocess, os.system, os.popen)
HYBRID_BLOCK_SHELL: bool = True

# Restrict builtins to safe functions only
HYBRID_RESTRICT_BUILTINS: bool = True

# Block code execution functions (exec, eval, compile, __import__)
HYBRID_BLOCK_CODE_EXECUTION: bool = True

# =============================================================================
# HYBRID EXECUTION LIMITS
# =============================================================================
# Maximum wall-clock execution time in seconds for one hybrid run. This is a
# hard server-side cap: a client may ask for less, never for more. The run is
# killed (child process terminated) when it is exceeded.
HYBRID_MAX_EXECUTION_TIME: int = _env_int("HYBRID_MAX_EXECUTION_TIME", 60, minimum=1)

# Maximum memory usage in MB (0 = no limit)
HYBRID_MAX_MEMORY_MB: int = 512

# Maximum number of simulation runs per execution (0 = no limit)
HYBRID_MAX_SIMULATION_RUNS: int = 10000

# Maximum output size in characters (0 = no limit)
HYBRID_MAX_OUTPUT_SIZE: int = 100000

# =============================================================================
# HYBRID EXECUTION ALLOWED MODULES
# =============================================================================
# List of allowed module prefixes for import
HYBRID_ALLOWED_MODULES: list = [
    'cirq',
    'qiskit', 
    'pennylane',
    'fastqsim',
    'qml',
    'numpy',
    'math',
    'typing',
    'dataclasses',
    'collections',
    'functools',
    'itertools',
    'operator',
    're',
    'json',
    'copy',
    'random',
    'time',  # Only time.sleep limited by timeout
    'datetime',
    'decimal',
    'fractions',
    'cmath',
    'statistics',
]

# =============================================================================
# HYBRID EXECUTION BLOCKED MODULES
# =============================================================================
# Explicit list of blocked modules (checked before allowed list)
HYBRID_BLOCKED_MODULES: list = [
    # OS / process / low-level system
    'os',
    'posix',
    'nt',
    'posixpath',
    'ntpath',
    'sys',
    'subprocess',
    '_posixsubprocess',
    '_winapi',
    'msvcrt',
    'winreg',
    'socket',
    '_socket',
    'select',
    'selectors',
    'ssl',
    'shutil',
    'pickle',
    '_pickle',
    'copyreg',
    'shelve',
    'dill',
    'cloudpickle',
    'joblib',
    'marshal',
    'ctypes',
    '_ctypes',
    'cffi',
    'mmap',
    'multiprocessing',
    '_multiprocessing',
    'concurrent',
    'asyncio',
    'threading',
    '_thread',
    'signal',
    '_signal',
    'faulthandler',
    'atexit',
    'resource',
    'pty',
    'tty',
    'termios',
    'fcntl',
    'pwd',
    'grp',
    'crypt',
    'platform',
    'sysconfig',
    'site',
    # Import machinery / interpreter introspection ("builtins tricks")
    'builtins',
    'importlib',
    'imp',
    '_imp',
    'zipimport',
    'pkgutil',
    'runpy',
    'code',
    'codeop',
    'gc',
    'inspect',
    'types',
    'string',   # string.Formatter().get_field() is a getattr() bypass
    'traceback',
    'linecache',
    'tracemalloc',
    'pdb',
    'bdb',
    'trace',
    'timeit',   # timeit.timeit("<any code>") compiles and runs strings
    'cProfile',
    'profile',
    'webbrowser',
    'logging',  # FileHandler writes arbitrary files
    # Archives / databases (file access)
    'zipfile',
    'tarfile',
    'dbm',
    'sqlite3',
    'fileinput',
    'filecmp',
    '_io',
    # File system helpers (additional to HYBRID_BLOCK_FILE_ACCESS)
    'tempfile',
    'glob',
    'pathlib',
    'io',
    # Network / HTTP
    'urllib',
    'http',
    'ftplib',
    'smtplib',
    'poplib',
    'imaplib',
    'nntplib',
    'telnetlib',
    'requests',
    'aiohttp',
    'httpx',
    'websocket',
    # Remote access / SSH / automation
    'paramiko',
    'fabric',
    'pexpect',
    'ptyprocess',
]

# =============================================================================
# HYBRID EXECUTION BLOCKED BUILTINS
# =============================================================================
# Builtin functions that are blocked when HYBRID_RESTRICT_BUILTINS is True
HYBRID_BLOCKED_BUILTINS: list = [
    'exec',
    'eval', 
    'compile',
    '__import__',
    'open',
    'input',
    'breakpoint',
    'help',
    'credits',
    'license',
    'copyright',
    'quit',
    'exit',
    'globals',
    'locals',
    'vars',
    'dir',
    'getattr',
    'setattr',
    'delattr',
    'hasattr',
    'memoryview',
    'bytearray',
]

# =============================================================================
# HYBRID EXECUTION FEATURE FLAGS
# =============================================================================
# Enable/disable hybrid execution feature entirely
HYBRID_EXECUTION_ENABLED: bool = True

# Enable verbose logging for hybrid execution (for debugging)
HYBRID_VERBOSE_LOGGING: bool = False

# Allow print() statements in hybrid code
HYBRID_ALLOW_PRINT: bool = True

# Capture and return simulation results automatically
HYBRID_CAPTURE_RESULTS: bool = True

