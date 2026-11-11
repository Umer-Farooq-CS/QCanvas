"""
Run untrusted, user-supplied Python in a short-lived child process.

Why a child process
-------------------
User code (hybrid execution, and the exec() fallback inside the framework ->
QASM converters) used to run *inside* the API process.  That meant an
infinite loop hung a worker forever, a crash or MemoryError took the API
down, ``sys.stdout`` / ``builtins.__import__`` / simulation results were
shared between concurrent users, and anything in the API's memory or
environment (SECRET_KEY, DATABASE_URL, AWS creds, ...) was one attribute walk
away.  Here every job gets its own process which is:

* killed (terminate, then kill, whole process group) when its wall-clock
  budget runs out;
* started from a *clean* interpreter on Linux (``forkserver``; see below)
  so the API's secrets, sockets and DB connections are not in it;
* given an allow-listed environment (secrets are not inherited);
* resource-limited on POSIX (address space, CPU seconds, file size, no core
  dumps) and, when the API runs as root, demoted to an unprivileged uid;
* only able to talk back as JSON over a pipe (the parent never unpickles
  anything the child produced).

Start method
------------
* Linux: ``forkserver`` (default).  The fork server is launched once from a
  clean environment and pre-imports cirq / qiskit / pennylane / qsim, so each
  job is just a fork of that warm, secret-free process (~tens of ms).
  Plain ``fork`` of the API process is *not* the default because the child
  would inherit the API's memory (settings objects holding SECRET_KEY, DB
  URLs, session tokens), its open file descriptors (the uvicorn listening
  socket, Postgres connections) and its initial environment block (readable
  at /proc/self/environ even after os.environ is scrubbed), and forking a
  multi-threaded process can deadlock the child on locks held by other
  threads.  ``USER_CODE_START_METHOD=fork`` is still available as an escape
  hatch.
* Windows / macOS: ``spawn`` (fresh interpreter per job: slower, but local
  development works).

Concurrency
-----------
``run_isolated_async`` gates on a per-event-loop ``asyncio.Semaphore`` (no
threads are consumed while queued) and then does the blocking wait on a
dedicated thread pool, so the event loop never blocks.  A process-wide
``threading.BoundedSemaphore`` is the hard cap shared by sync and async
callers.  If no slot frees up within ``USER_CODE_QUEUE_TIMEOUT`` seconds,
``UserCodeBusyError`` (an HTTP 503 when FastAPI is present) is raised.

Environment variables (all optional)
------------------------------------
USER_CODE_MAX_CONCURRENCY   max simultaneous child processes (default: effective CPU count, min 2)
USER_CODE_QUEUE_TIMEOUT     seconds to wait for a free slot before 503 (default 30)
USER_CODE_MEMORY_LIMIT_MB   RLIMIT_AS headroom above the warm baseline (default 1536; 0 = off)
USER_CODE_START_METHOD      forkserver | fork | spawn (default: forkserver on Linux, else spawn)
USER_CODE_STARTUP_TIMEOUT   seconds a child may take to become ready (default 15, 90 for spawn)
USER_CODE_MAX_FILE_MB       RLIMIT_FSIZE in MB (default 16)
USER_CODE_RLIMIT_NPROC      RLIMIT_NPROC (default 0 = not set; see _harden_child)
USER_CODE_RUN_AS_UID        auto | off | <uid> (default auto: 65534 when the API runs as root)
USER_CODE_RUN_AS_GID        gid to use with RUN_AS_UID (default: same number as the uid)
USER_CODE_MAX_RESULT_MB     max size of the JSON result a child may send back (default 8)
USER_CODE_ENV_ALLOW         extra comma-separated env var names to pass to the child
"""

from __future__ import annotations

import asyncio
import functools
import json
import logging
import math
import os
import shutil
import signal
import sys
import tempfile
import threading
import time
import traceback
import weakref
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Sequence

import multiprocessing as mp

logger = logging.getLogger(__name__)

_IS_POSIX = os.name == "posix"
_IS_LINUX = sys.platform.startswith("linux")

# Marker placed in the fork server's (clean) environment so this module knows
# to pre-import the heavy libraries when the fork server imports it.
_WORKER_MARKER = "QCANVAS_USER_CODE_WORKER"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _env_int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name)
    try:
        value = int(raw) if raw is not None and raw.strip() != "" else default
    except ValueError:
        logger.warning("Ignoring invalid %s=%r", name, raw)
        value = default
    return max(minimum, value)


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.getenv(name)
    try:
        value = float(raw) if raw is not None and raw.strip() != "" else default
    except ValueError:
        logger.warning("Ignoring invalid %s=%r", name, raw)
        value = default
    return max(minimum, value)


def _effective_cpu_count() -> int:
    """CPU count that respects container limits (affinity and cgroup quota)."""
    try:
        count = len(os.sched_getaffinity(0))  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        count = os.cpu_count() or 1
    quota_cpus: Optional[float] = None
    try:  # cgroup v2
        with open("/sys/fs/cgroup/cpu.max", "r", encoding="ascii") as fh:
            quota, period = fh.read().split()[:2]
        if quota != "max":
            quota_cpus = int(quota) / int(period)
    except (OSError, ValueError):
        try:  # cgroup v1
            with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "r", encoding="ascii") as fh:
                quota_us = int(fh.read().strip())
            with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us", "r", encoding="ascii") as fh:
                period_us = int(fh.read().strip())
            if quota_us > 0 and period_us > 0:
                quota_cpus = quota_us / period_us
        except (OSError, ValueError):
            pass
    if quota_cpus:
        count = min(count, max(1, math.ceil(quota_cpus)))
    return max(1, count)


def _default_start_method() -> str:
    if _IS_LINUX and "forkserver" in mp.get_all_start_methods():
        return "forkserver"
    return "spawn"


MAX_CONCURRENCY: int = _env_int("USER_CODE_MAX_CONCURRENCY", max(2, _effective_cpu_count()), minimum=1)
QUEUE_TIMEOUT: float = _env_float("USER_CODE_QUEUE_TIMEOUT", 30.0)
MEMORY_LIMIT_MB: int = _env_int("USER_CODE_MEMORY_LIMIT_MB", 1536)
MAX_FILE_MB: int = _env_int("USER_CODE_MAX_FILE_MB", 16)
RLIMIT_NPROC: int = _env_int("USER_CODE_RLIMIT_NPROC", 0)
MAX_RESULT_BYTES: int = _env_int("USER_CODE_MAX_RESULT_MB", 8, minimum=1) * 1024 * 1024

START_METHOD: str = (os.getenv("USER_CODE_START_METHOD") or "").strip().lower() or _default_start_method()
if START_METHOD not in mp.get_all_start_methods():
    logger.warning("USER_CODE_START_METHOD=%r is not available here; using %r", START_METHOD, _default_start_method())
    START_METHOD = _default_start_method()

STARTUP_TIMEOUT: float = _env_float(
    "USER_CODE_STARTUP_TIMEOUT", 90.0 if START_METHOD == "spawn" else 15.0, minimum=1.0
)

# Seconds between SIGTERM and SIGKILL when stopping a child.
_TERMINATE_GRACE = 0.5


def _resolve_run_as() -> Optional[tuple]:
    if not _IS_POSIX:
        return None
    raw = (os.getenv("USER_CODE_RUN_AS_UID") or "auto").strip().lower()
    if raw in ("off", "none", "no", "false", "0", ""):
        return None
    if raw == "auto":
        if os.geteuid() != 0:  # type: ignore[attr-defined]
            return None
        uid = 65534  # "nobody" on Debian/Ubuntu (python:*-slim images)
    else:
        try:
            uid = int(raw)
        except ValueError:
            logger.warning("Ignoring invalid USER_CODE_RUN_AS_UID=%r", raw)
            return None
    gid = _env_int("USER_CODE_RUN_AS_GID", uid)
    return (uid, gid)


RUN_AS: Optional[tuple] = _resolve_run_as()

# Base directory for per-run scratch HOME/TMPDIR when we drop privileges.
_SCRATCH_ROOT = os.path.join(tempfile.gettempdir(), "qcanvas-user-code")


# ---------------------------------------------------------------------------
# Environment scrubbing
# ---------------------------------------------------------------------------

# Only these variables reach user code.  Everything else (SECRET_KEY,
# DATABASE_URL, POSTGRES_*, AWS_*, RESEND_*, OTP_PEPPER, *_TOKEN, *_KEY, ...)
# is dropped.  An allow-list is used on purpose: new secrets added to the
# deployment later are excluded automatically.
_ENV_ALLOW_EXACT = {
    "PATH", "HOME", "USER", "LOGNAME", "LANG", "LANGUAGE", "TZ", "TERM",
    "TMPDIR", "TEMP", "TMP",
    "PYTHONPATH", "PYTHONHASHSEED", "PYTHONUNBUFFERED", "PYTHONIOENCODING",
    "PYTHONDONTWRITEBYTECODE", "PYTHONUTF8", "VIRTUAL_ENV",
    "MPLBACKEND", "MPLCONFIGDIR",
    "FASTQSIM_ONLINE_MODE", "FASTQSIM_EXECUTION_MODE",
    # Windows essentials (local development with the spawn start method).
    "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "COMSPEC", "PATHEXT", "USERPROFILE",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE", "OS",
    _WORKER_MARKER,
}
_ENV_ALLOW_PREFIXES = ("LC_", "OMP_", "OPENBLAS_", "MKL_", "NUMEXPR_", "RAYON_", "MALLOC_", "QISKIT_")

# Belt and braces: even an allow-listed name is dropped if it looks secret.
_SECRET_EXACT = {
    "SECRET_KEY", "DATABASE_URL", "REDIS_URL", "OTP_PEPPER", "CIRQ_RAG_API_KEY",
    "FASTQSIM_API_TOKEN", "FASTQUBIT_SESSION_TOKEN", "FASTQUBIT_USER_ID",
}
_SECRET_PREFIXES = ("POSTGRES_", "AWS_", "RESEND_", "DATABASE_", "SMTP_", "SSM_")
_SECRET_MARKERS = ("SECRET", "PASSWORD", "PASSWD", "TOKEN", "PEPPER", "CREDENTIAL", "PRIVATE", "API_KEY", "APIKEY")
_SECRET_SUFFIXES = ("_KEY", "_PASS", "_PWD", "_DSN", "_URL", "_URI")

# Thread pools of numeric libraries: one thread per child (we already run
# many children in parallel) and few malloc arenas so RLIMIT_AS is not eaten
# by per-thread arena reservations.
_WORKER_THREAD_ENV = {
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "NUMEXPR_NUM_THREADS": "1",
    "RAYON_NUM_THREADS": "1",
    "MALLOC_ARENA_MAX": "2",
    "QISKIT_PARALLEL": "FALSE",
    "QISKIT_NUM_PROCS": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}


def _extra_allowed() -> set:
    raw = os.getenv("USER_CODE_ENV_ALLOW") or ""
    return {name.strip() for name in raw.split(",") if name.strip()}


def is_secret_env_name(name: str) -> bool:
    upper = name.upper()
    if upper in _SECRET_EXACT:
        return True
    if upper.startswith(_SECRET_PREFIXES):
        return True
    if any(marker in upper for marker in _SECRET_MARKERS):
        return True
    return upper.endswith(_SECRET_SUFFIXES)


def build_child_env(source: Mapping[str, str]) -> Dict[str, str]:
    """Return the environment user code is allowed to see."""
    extra = _extra_allowed()
    clean: Dict[str, str] = {}
    for name, value in source.items():
        upper = name.upper()
        allowed = upper in _ENV_ALLOW_EXACT or upper.startswith(_ENV_ALLOW_PREFIXES) or name in extra
        if allowed and (name in extra or not is_secret_env_name(name)):
            clean[name] = value
    for name, value in _WORKER_THREAD_ENV.items():
        clean.setdefault(name, value)
    return clean


def _apply_env(clean: Mapping[str, str], overrides: Optional[Mapping[str, str]]) -> None:
    os.environ.clear()
    os.environ.update(clean)
    if overrides:
        os.environ.update({str(k): str(v) for k, v in overrides.items()})


# ---------------------------------------------------------------------------
# Errors and results
# ---------------------------------------------------------------------------

try:  # Surface "busy" as a proper HTTP 503 when running inside FastAPI.
    from fastapi import HTTPException as _BusyBase
except Exception:  # pragma: no cover - fastapi is always installed in the backend
    _BusyBase = None


BUSY_MESSAGE = (
    "The server is busy running other students' code right now. "
    "Please wait a few seconds and try again."
)

if _BusyBase is not None:
    class UserCodeBusyError(_BusyBase):
        """All execution slots stayed busy for longer than the queue timeout."""

        def __init__(self, message: str = BUSY_MESSAGE, retry_after: int = 5):
            super().__init__(status_code=503, detail=message, headers={"Retry-After": str(retry_after)})
            self.message = message
            self.retry_after = retry_after

        def __str__(self) -> str:
            return self.message
else:  # pragma: no cover
    class UserCodeBusyError(Exception):  # type: ignore[no-redef]
        def __init__(self, message: str = BUSY_MESSAGE, retry_after: int = 5):
            super().__init__(message)
            self.message = message
            self.retry_after = retry_after
            self.status_code = 503


@dataclass
class IsolatedOutcome:
    """What happened to one isolated job.  ``value`` is JSON-decoded data."""

    ok: bool
    value: Any = None
    error: Optional[str] = None
    error_type: Optional[str] = None
    traceback: Optional[str] = None
    timed_out: bool = False
    exitcode: Optional[int] = None
    duration: float = 0.0          # total, including process start-up
    startup_seconds: float = 0.0   # until the child reported "ready"
    pid: Optional[int] = None


# ---------------------------------------------------------------------------
# Child side
# ---------------------------------------------------------------------------

def _json_default(obj: Any) -> Any:
    try:
        import numpy as np  # noqa: WPS433 (already imported in the worker)

        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.generic):
            return obj.item()
    except Exception:
        pass
    if isinstance(obj, complex):
        return [obj.real, obj.imag]
    if isinstance(obj, (set, frozenset, tuple)):
        return list(obj)
    if isinstance(obj, bytes):
        return obj.decode("utf-8", "replace")
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass
    return str(obj)


def _send(conn, message: Dict[str, Any]) -> None:
    conn.send_bytes(json.dumps(message, default=_json_default).encode("utf-8"))


def _setrlimit(resource_mod, which: int, soft: int, hard: int) -> None:
    cur_soft, cur_hard = resource_mod.getrlimit(which)
    inf = resource_mod.RLIM_INFINITY
    if cur_hard != inf:
        hard = min(hard, cur_hard) if hard != inf else cur_hard
        soft = min(soft, hard) if soft != inf else hard
    resource_mod.setrlimit(which, (soft, hard))


def _current_address_space_bytes() -> int:
    try:
        with open("/proc/self/statm", "r", encoding="ascii") as fh:
            pages = int(fh.read().split()[0])
        return pages * os.sysconf("SC_PAGE_SIZE")
    except (OSError, ValueError, IndexError):
        return 0


def _prctl(option: int, arg2: int) -> bool:
    try:
        import ctypes

        libc = ctypes.CDLL(None, use_errno=True)
        ulong = ctypes.c_ulong
        return libc.prctl(ctypes.c_int(option), ulong(arg2), ulong(0), ulong(0), ulong(0)) == 0
    except Exception:
        return False


_PR_SET_DUMPABLE = 4
_PR_SET_NO_NEW_PRIVS = 38


def _harden_child(opts: Mapping[str, Any]) -> None:
    """Lock the freshly started child down before any user code runs."""
    # Own process group, so the parent can kill everything the job spawns.
    if _IS_POSIX:
        try:
            os.setsid()
        except OSError:
            pass

    # Secrets out of the environment (and out of os.environ for user code).
    _apply_env(build_child_env(os.environ), opts.get("env"))
    sys.dont_write_bytecode = True

    if not _IS_POSIX:
        return

    import resource

    _setrlimit(resource, resource.RLIMIT_CORE, 0, 0)

    timeout = float(opts.get("timeout") or 0)
    if timeout > 0:
        usage = resource.getrusage(resource.RUSAGE_SELF)
        used = usage.ru_utime + usage.ru_stime
        soft = int(math.ceil(used + timeout)) + 2
        _setrlimit(resource, resource.RLIMIT_CPU, soft, soft + 3)

    memory_mb = int(opts.get("memory_mb") or 0)
    if memory_mb > 0:
        # Limit *additional* address space on top of the warm baseline: the
        # pre-imported cirq/qiskit/pennylane already reserve a lot of virtual
        # memory, so an absolute figure would either break imports or be
        # meaninglessly generous depending on the machine.
        baseline = _current_address_space_bytes()
        limit = baseline + memory_mb * 1024 * 1024
        _setrlimit(resource, resource.RLIMIT_AS, limit, limit)

    file_mb = int(opts.get("file_mb") or 0)
    if file_mb > 0:
        size = file_mb * 1024 * 1024
        _setrlimit(resource, resource.RLIMIT_FSIZE, size, size)

    # RLIMIT_NPROC counts every process/thread of the *uid*, including the API
    # server's own threads when we do not change uid, and it is ignored for
    # root.  It is therefore opt-in; fork bombs are already prevented by the
    # import blocklist, the process-group kill and RLIMIT_CPU.
    nproc = int(opts.get("nproc") or 0)
    if nproc > 0:
        try:
            _setrlimit(resource, resource.RLIMIT_NPROC, nproc, nproc)
        except (ValueError, OSError):
            pass

    if _IS_LINUX:
        _prctl(_PR_SET_NO_NEW_PRIVS, 1)
        # If the container runs short of memory, the kernel's OOM killer
        # should pick a student's job, not the API process.
        try:
            with open("/proc/self/oom_score_adj", "w", encoding="ascii") as fh:
                fh.write("1000")
        except OSError:
            pass

    run_as = opts.get("run_as")
    if run_as:
        uid, gid = int(run_as[0]), int(run_as[1])
        if os.geteuid() == 0:
            scratch = os.path.join(_SCRATCH_ROOT, str(os.getpid()))
            try:
                os.makedirs(_SCRATCH_ROOT, mode=0o711, exist_ok=True)
                os.makedirs(scratch, mode=0o700, exist_ok=True)
                os.chown(scratch, uid, gid)
                for name in ("HOME", "TMPDIR", "TEMP", "TMP", "MPLCONFIGDIR"):
                    os.environ[name] = scratch
                tempfile.tempdir = scratch
            except OSError:
                pass
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
            if os.getuid() != uid or os.geteuid() != uid:
                raise RuntimeError("privilege drop failed")
        elif os.geteuid() != uid:
            # Configured to run as another account but we can't switch
            # (not root): fail closed instead of running as the API's uid.
            raise RuntimeError("privilege drop not possible (API is not root)")

    if _IS_LINUX:
        # Other processes running as the same uid (e.g. another student's
        # job) may not ptrace us or read /proc/<pid>/{mem,environ}.
        _prctl(_PR_SET_DUMPABLE, 0)


def _child_main(conn, func: Callable[..., Any], args: Sequence[Any], kwargs: Mapping[str, Any],
                opts: Mapping[str, Any]) -> None:
    """Entry point of the child process (must stay a module-level function)."""
    try:
        _harden_child(opts)
    except BaseException as exc:  # noqa: BLE001 - never run user code unhardened
        try:
            _send(conn, {"kind": "result", "ok": False, "error_type": "SandboxSetupError",
                         "error": f"Could not set up the execution sandbox: {exc}"})
        finally:
            os._exit(3)

    try:
        _send(conn, {"kind": "ready"})
    except BaseException:
        os._exit(4)

    # Last line of defence if the parent dies before it can kill us: exit on
    # our own shortly after the wall-clock budget.
    budget = float(opts.get("timeout") or 0)
    if budget > 0:
        watchdog = threading.Timer(budget + 15.0, os._exit, args=(124,))
        watchdog.daemon = True
        watchdog.start()

    message: Dict[str, Any]
    try:
        value = func(*args, **dict(kwargs))
        message = {"kind": "result", "ok": True, "value": value}
    except MemoryError:
        message = {"kind": "result", "ok": False, "error_type": "MemoryError",
                   "error": "The program ran out of memory."}
    except BaseException as exc:  # noqa: BLE001 - includes SystemExit from user code
        message = {"kind": "result", "ok": False, "error_type": type(exc).__name__,
                   "error": str(exc) or type(exc).__name__,
                   "traceback": traceback.format_exc(limit=20)[-8000:]}

    try:
        _send(conn, message)
    except BaseException as exc:  # noqa: BLE001 - e.g. MemoryError while encoding
        try:
            _send(conn, {"kind": "result", "ok": False, "error_type": "ResultError",
                         "error": f"The result could not be sent back: {type(exc).__name__}: {exc}"})
        except BaseException:
            pass
    try:
        conn.close()
        sys.stdout.flush()
        sys.stderr.flush()
    except BaseException:
        pass
    # Skip interpreter shutdown: no atexit handlers, no joining of threads the
    # job may have left behind.
    os._exit(0)


# ---------------------------------------------------------------------------
# Fork server management (Linux)
# ---------------------------------------------------------------------------

_forkserver_lock = threading.Lock()
_forkserver_ready = False


def _forkserver_alive() -> bool:
    try:
        from multiprocessing import forkserver as _fs

        pid = getattr(_fs._forkserver, "_forkserver_pid", None)  # noqa: SLF001
    except Exception:
        return False
    if not pid:
        return False
    try:
        with open(f"/proc/{pid}/stat", "r", encoding="ascii", errors="replace") as fh:
            state = fh.read().rsplit(")", 1)[1].split()[0]
        return state not in ("Z", "X", "x")
    except (OSError, IndexError):
        return False


def _ensure_forkserver(ctx) -> None:
    """Start (or restart) the fork server from a clean environment."""
    global _forkserver_ready
    if _forkserver_ready and _forkserver_alive():
        return
    with _forkserver_lock:
        if _forkserver_ready and _forkserver_alive():
            return
        from multiprocessing import forkserver as _fs

        ctx.set_forkserver_preload([__name__])
        clean = build_child_env(os.environ)
        clean[_WORKER_MARKER] = "1"
        # Python <= 3.11's fork server ignores the parent's sys.path, so the
        # preload (`app.services.isolated_exec`, which lives in backend/) would
        # fail silently and every job would re-import cirq/qiskit/pennylane.
        # Hand the project directories over via PYTHONPATH instead.
        clean["PYTHONPATH"] = _project_pythonpath(clean.get("PYTHONPATH"))
        saved = dict(os.environ)
        # The fork server inherits os.environ at launch.  Swap in the clean
        # environment for the few milliseconds it takes to launch it, so the
        # server and every job it forks never see the API's secrets (not even
        # in /proc/<pid>/environ).
        try:
            os.environ.clear()
            os.environ.update(clean)
            _fs.ensure_running()
        finally:
            os.environ.clear()
            os.environ.update(saved)
        _forkserver_ready = True
        logger.info("User-code fork server running (pid %s)", getattr(_fs._forkserver, "_forkserver_pid", "?"))  # noqa: SLF001


# Child process names start with this; used to recognise our own processes.
_PROCESS_NAME_PREFIX = "qcanvas-user-code-"


def _install_preparation_patch() -> None:
    """Stop spawn/forkserver children of *ours* from re-importing ``__main__``.

    By default every spawn/forkserver child re-runs the parent's main script
    (e.g. backend/start.py -> the whole FastAPI app, settings, DB engine) as
    ``__mp_main__``.  That would be slow and would pull the app's secrets back
    into the child.  Our child entry point lives in this module, so the main
    module is never needed.  Other multiprocessing users are unaffected.
    """
    from multiprocessing import spawn as _spawn

    original = _spawn.get_preparation_data
    if getattr(original, "_qcanvas_patched", False):
        return

    @functools.wraps(original)
    def get_preparation_data(name, *args, **kwargs):
        data = original(name, *args, **kwargs)
        if isinstance(name, str) and name.startswith(_PROCESS_NAME_PREFIX):
            data.pop("init_main_from_path", None)
            data.pop("init_main_from_name", None)
        return data

    get_preparation_data._qcanvas_patched = True  # type: ignore[attr-defined]
    _spawn.get_preparation_data = get_preparation_data


_install_preparation_patch()


def _project_pythonpath(existing: Optional[str]) -> str:
    """sys.path entries that are not part of the interpreter installation."""
    install_roots = {os.path.realpath(p) for p in {sys.prefix, sys.base_prefix, sys.exec_prefix} if p}
    entries = []
    for entry in sys.path:
        if not entry or not os.path.isdir(entry):
            continue
        real = os.path.realpath(entry)
        if any(real == root or real.startswith(root + os.sep) for root in install_roots):
            continue
        if real not in entries:
            entries.append(real)
    for entry in (existing or "").split(os.pathsep):
        if entry and entry not in entries:
            entries.append(entry)
    return os.pathsep.join(entries)


def _get_context():
    ctx = mp.get_context(START_METHOD)
    if START_METHOD == "forkserver":
        _ensure_forkserver(ctx)
    return ctx


def prestart() -> None:
    """Start the fork server now (call once at application startup).

    Optional: it is started lazily on the first job otherwise.  Starting it at
    import/startup time is preferable because the brief os.environ swap then
    happens before request threads exist.
    """
    if START_METHOD == "forkserver":
        try:
            _get_context()
        except Exception:
            logger.exception("Could not pre-start the user-code fork server")


def _warm_worker_imports() -> None:
    """Runs inside the fork server: import heavy libraries once.

    Only imports - no circuits are run here, because some libraries start
    thread pools on first use and forking a multi-threaded process is unsafe.
    """
    for name in (
        "numpy",
        "cirq",
        "qiskit",
        "qiskit.qasm3",
        "pennylane",
        "qsim",
        "qcanvas.result",
        "qcanvas.qsim",
        "qcanvas.core",
        "qcanvas.sandbox",
        "app.services.conversion_service",
    ):
        try:
            __import__(name)
        except BaseException:  # noqa: BLE001 - must never kill the fork server
            pass


if os.environ.get(_WORKER_MARKER) == "1" and mp.parent_process() is None:
    # We are being imported by the fork server's preload step.
    _warm_worker_imports()


# ---------------------------------------------------------------------------
# Parent side
# ---------------------------------------------------------------------------

_thread_slots = threading.BoundedSemaphore(MAX_CONCURRENCY)
_executor_lock = threading.Lock()
_executor: Optional[ThreadPoolExecutor] = None
_loop_semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()

_stats_lock = threading.Lock()
_stats = {"running": 0, "started": 0, "timeouts": 0, "crashes": 0, "busy_rejections": 0}


def get_stats() -> Dict[str, Any]:
    with _stats_lock:
        data = dict(_stats)
    data.update(max_concurrency=MAX_CONCURRENCY, start_method=START_METHOD,
                queue_timeout=QUEUE_TIMEOUT, memory_limit_mb=MEMORY_LIMIT_MB,
                run_as_uid=RUN_AS[0] if RUN_AS else None)
    return data


def _bump(key: str, delta: int = 1) -> None:
    with _stats_lock:
        _stats[key] += delta


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    with _executor_lock:
        if _executor is None:
            _executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENCY, thread_name_prefix="user-code")
        return _executor


def _get_loop_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _loop_semaphores.get(loop)
    if sem is None:
        sem = asyncio.Semaphore(MAX_CONCURRENCY)
        _loop_semaphores[loop] = sem
    return sem


def _stop_process(proc) -> None:
    """Terminate, then kill, the child and its whole process group."""
    if proc.pid is None:
        return
    group_signalled = False
    if _IS_POSIX and proc.exitcode is None:
        try:
            os.killpg(proc.pid, signal.SIGTERM)
            group_signalled = True
        except OSError:
            pass
    if proc.exitcode is None:
        try:
            proc.terminate()
        except Exception:
            pass
        proc.join(_TERMINATE_GRACE)
    if _IS_POSIX and group_signalled:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
    if proc.exitcode is None:
        try:
            proc.kill()
        except Exception:
            pass
        proc.join(5)


def _receive(conn, proc, deadline: float):
    """Wait for one message until ``deadline``.

    Returns ("message", dict) | ("timeout", None) | ("eof", None) | ("too_large", None) | ("garbage", None).
    """
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return "timeout", None
        try:
            ready = conn.poll(min(remaining, 0.25))
        except (EOFError, OSError):
            return "eof", None
        if ready:
            try:
                data = conn.recv_bytes(MAX_RESULT_BYTES)
            except EOFError:
                return "eof", None
            except OSError:
                return "too_large", None
            try:
                message = json.loads(data.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                return "garbage", None
            if not isinstance(message, dict):
                return "garbage", None
            return "message", message
        if not proc.is_alive():
            # Child is gone; anything it wrote is already in the pipe.
            try:
                if conn.poll(0):
                    continue
            except (EOFError, OSError):
                pass
            return "eof", None


def _describe_exit(exitcode: Optional[int], memory_mb: int) -> tuple:
    if exitcode is None:
        return "WorkerCrashed", "The execution worker stopped responding."
    if exitcode < 0:
        signum = -exitcode
        try:
            name = signal.Signals(signum).name
        except ValueError:
            name = f"signal {signum}"
        if name == "SIGKILL":
            return ("MemoryError",
                    "The program was killed by the system, most likely because it used too much memory"
                    + (f" (limit about {memory_mb} MB)." if memory_mb else "."))
        if name == "SIGXCPU":
            return "TimeoutError", "The program used too much CPU time and was stopped."
        if name == "SIGXFSZ":
            return "SecurityViolationError", "The program tried to write a file that is too large."
        return "WorkerCrashed", f"The program crashed ({name})."
    if exitcode == 3:
        return "SandboxSetupError", "The execution sandbox could not be set up."
    if exitcode != 0:
        return "WorkerCrashed", f"The execution worker exited unexpectedly (exit code {exitcode})."
    return "WorkerCrashed", "The program finished without returning a result."


def _cleanup_scratch(pid: Optional[int]) -> None:
    if pid is None or RUN_AS is None:
        return
    shutil.rmtree(os.path.join(_SCRATCH_ROOT, str(pid)), ignore_errors=True)


def _run_in_child(func: Callable[..., Any], args: Sequence[Any], kwargs: Mapping[str, Any], *,
                  timeout: float, env: Optional[Mapping[str, str]], label: str,
                  memory_mb: int) -> IsolatedOutcome:
    started = time.monotonic()
    if SAME_UID_REFUSED:
        return IsolatedOutcome(
            ok=False, error_type="ConfigurationError",
            error="Code execution is disabled: the server is not configured to run "
                  "user code under a separate account. (Admins: run the API as root "
                  "so it can drop to USER_CODE_RUN_AS_UID, or set "
                  "USER_CODE_ALLOW_SAME_UID=true for development.)")
    try:
        ctx = _get_context()
        parent_conn, child_conn = ctx.Pipe(duplex=False)
    except Exception as exc:
        logger.exception("Could not prepare isolated worker")
        return IsolatedOutcome(ok=False, error_type="WorkerStartError",
                               error=f"Could not start the execution worker: {exc}")

    opts = {
        "timeout": timeout,
        "memory_mb": memory_mb,
        "file_mb": MAX_FILE_MB,
        "nproc": RLIMIT_NPROC,
        "run_as": RUN_AS,
        "env": dict(env or {}),
    }
    proc = ctx.Process(target=_child_main, args=(child_conn, func, tuple(args), dict(kwargs), opts),
                       name=f"{_PROCESS_NAME_PREFIX}{label}", daemon=True)
    try:
        proc.start()
    except Exception as exc:
        parent_conn.close()
        child_conn.close()
        logger.exception("Could not start isolated worker")
        return IsolatedOutcome(ok=False, error_type="WorkerStartError",
                               error=f"Could not start the execution worker: {exc}",
                               duration=time.monotonic() - started)
    child_conn.close()  # the parent must not hold the write end, or EOF never arrives
    _bump("started")
    _bump("running")

    outcome: Optional[IsolatedOutcome] = None
    ready_at: Optional[float] = None
    try:
        status, message = _receive(parent_conn, proc, started + STARTUP_TIMEOUT)
        if status == "timeout":
            outcome = IsolatedOutcome(ok=False, error_type="WorkerStartError",
                                      error="The execution worker did not start in time. "
                                            "The server may be overloaded; please try again.")
        elif status == "message" and message.get("kind") == "ready":
            ready_at = time.monotonic()
            status, message = _receive(parent_conn, proc, ready_at + timeout)
            if status == "timeout":
                _bump("timeouts")
                outcome = IsolatedOutcome(ok=False, timed_out=True, error_type="TimeoutError",
                                          error=f"Execution timed out after {timeout:g} seconds and was stopped.")

        if outcome is not None:
            pass
        elif status == "message" and message.get("kind") == "result":
            outcome = IsolatedOutcome(
                ok=bool(message.get("ok")),
                value=message.get("value"),
                error=message.get("error"),
                error_type=message.get("error_type"),
                traceback=message.get("traceback"),
            )
            proc.join(1.0)  # let it exit on its own before we start killing
        elif status == "too_large":
            outcome = IsolatedOutcome(ok=False, error_type="OutputTooLarge",
                                      error=f"The result was larger than {MAX_RESULT_BYTES // (1024 * 1024)} MB.")
        elif status == "garbage":
            outcome = IsolatedOutcome(ok=False, error_type="WorkerCrashed",
                                      error="The execution worker returned an invalid result.")
    finally:
        _stop_process(proc)
        parent_conn.close()
        _bump("running", -1)
        _cleanup_scratch(proc.pid)

    if outcome is None:  # EOF / child died without a result
        _bump("crashes")
        error_type, error = _describe_exit(proc.exitcode, memory_mb)
        outcome = IsolatedOutcome(ok=False, error_type=error_type, error=error)
    outcome.exitcode = proc.exitcode
    outcome.pid = proc.pid
    outcome.duration = time.monotonic() - started
    outcome.startup_seconds = (ready_at - started) if ready_at is not None else outcome.duration
    try:
        proc.close()
    except Exception:
        pass
    return outcome


def run_isolated(func: Callable[..., Any], args: Sequence[Any] = (), kwargs: Optional[Mapping[str, Any]] = None,
                 *, timeout: float, env: Optional[Mapping[str, str]] = None, label: str = "job",
                 memory_mb: Optional[int] = None, queue_timeout: Optional[float] = None) -> IsolatedOutcome:
    """Run ``func(*args, **kwargs)`` in a hardened child process (blocking).

    ``func`` must be a module-level function importable in a fresh
    interpreter and must return JSON-serialisable data.  ``env`` adds
    variables to the child's scrubbed environment.  Raises
    ``UserCodeBusyError`` when no slot frees up within the queue timeout.
    """
    wait = QUEUE_TIMEOUT if queue_timeout is None else queue_timeout
    if not _thread_slots.acquire(timeout=wait):
        _bump("busy_rejections")
        raise UserCodeBusyError()
    try:
        return _run_in_child(func, args, kwargs or {}, timeout=float(timeout), env=env, label=label,
                             memory_mb=MEMORY_LIMIT_MB if memory_mb is None else int(memory_mb))
    finally:
        _thread_slots.release()


async def run_isolated_async(func: Callable[..., Any], args: Sequence[Any] = (),
                             kwargs: Optional[Mapping[str, Any]] = None, *, timeout: float,
                             env: Optional[Mapping[str, str]] = None, label: str = "job",
                             memory_mb: Optional[int] = None) -> IsolatedOutcome:
    """Async wrapper around :func:`run_isolated` that never blocks the event loop."""
    sem = _get_loop_semaphore()
    queued_at = time.monotonic()
    try:
        await asyncio.wait_for(sem.acquire(), timeout=QUEUE_TIMEOUT)
    except asyncio.TimeoutError:
        _bump("busy_rejections")
        raise UserCodeBusyError() from None
    try:
        remaining = max(0.5, QUEUE_TIMEOUT - (time.monotonic() - queued_at))
        call = functools.partial(run_isolated, func, args, kwargs, timeout=timeout, env=env, label=label,
                                 memory_mb=memory_mb, queue_timeout=remaining)
        return await asyncio.get_running_loop().run_in_executor(_get_executor(), call)
    finally:
        sem.release()


# ---------------------------------------------------------------------------
# Same-uid policy and parent hardening
# ---------------------------------------------------------------------------
# If user code would run as the API's own uid (POSIX, API not root, no
# USER_CODE_RUN_AS_UID), a sandbox escape could read the API's memory and
# /proc/<pid>/environ. Refuse unless explicitly allowed (dev) or the deploy
# says it's development. Windows/macOS spawn is development-only by design.
def _same_uid_refused() -> bool:
    if not _IS_POSIX:
        return False
    # A configured RUN_AS only isolates us if we can actually switch to it
    # (i.e. we're root) and it's a different account from the API's own.
    if RUN_AS is not None and os.geteuid() == 0 and RUN_AS[0] != 0:  # type: ignore[attr-defined]
        return False
    if (os.getenv("USER_CODE_ALLOW_SAME_UID") or "").strip().lower() in ("1", "true", "yes", "on"):
        return False
    env_name = (os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "").strip().lower()
    if env_name in ("development", "dev", "local", "test"):
        return False
    return True


SAME_UID_REFUSED = _same_uid_refused()
if SAME_UID_REFUSED:
    logger.error(
        "User-code execution DISABLED: it would run as the API's own uid. Run the "
        "API as root (it drops to USER_CODE_RUN_AS_UID / nobody) or set "
        "USER_CODE_ALLOW_SAME_UID=true for development."
    )

# Make the API process itself non-dumpable so same-uid processes (e.g. an
# escaped child) can't ptrace it or read /proc/<pid>/environ or mem.
if _IS_POSIX:
    try:
        _prctl(_PR_SET_DUMPABLE, 0)
    except Exception:  # pragma: no cover - best effort
        logger.warning("Could not mark API process non-dumpable", exc_info=True)


__all__ = [
    "IsolatedOutcome",
    "UserCodeBusyError",
    "BUSY_MESSAGE",
    "MAX_CONCURRENCY",
    "QUEUE_TIMEOUT",
    "START_METHOD",
    "build_child_env",
    "is_secret_env_name",
    "get_stats",
    "prestart",
    "run_isolated",
    "run_isolated_async",
]
