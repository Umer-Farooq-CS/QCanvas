"""
Hybrid Execution API Routes.

Provides endpoints for executing Python code with quantum circuits
in a sandboxed environment with qcanvas and qsim access.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import asyncio
import logging
import sys
import os

logger = logging.getLogger(__name__)

# Add the project root directory to Python path
current_file = os.path.abspath(__file__)
# backend/app/api/routes/hybrid.py -> backend/
backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
# Also add project root (parent of backend)
project_root = os.path.dirname(backend_root)

if backend_root not in sys.path:
    sys.path.insert(0, backend_root)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Import sandbox execution
try:
    from qcanvas.sandbox import execute_sandboxed, execute_sandboxed_job, validate_code
    from qcanvas.result import HybridExecutionResult
    from qcanvas import qsim as qsim_wrapper
    SANDBOX_AVAILABLE = True
    print("✓ Sandbox module imported successfully")
except ImportError as e:
    print(f"Warning: Sandbox not available: {e}")
    import traceback
    traceback.print_exc()
    SANDBOX_AVAILABLE = False
    execute_sandboxed = None
    execute_sandboxed_job = None
    validate_code = None
    qsim_wrapper = None

# User code never runs in this process: every run gets its own child process.
from app.services.isolated_exec import (
    UserCodeBusyError,
    get_stats as get_isolation_stats,
    prestart as prestart_isolated_runner,
    run_isolated_async,
)

# Start the clean fork server now (Linux), while the app is still importing
# and no request threads exist yet.  No-op on Windows/macOS.
prestart_isolated_runner()

# Variables FastQSim's SDK needs inside the child.  They are only passed when
# the run actually needs FastQSim (online mode or `import fastqsim`).
_FASTQSIM_CHILD_ENV = ("FASTQUBIT_SESSION_TOKEN", "FASTQUBIT_ENDPOINT", "FASTQSIM_EXECUTION_MODE")

# Check if QSim is available (needed for sandbox execution)
try:
    from qsim import run_qasm
    QSIM_AVAILABLE = True
    print("✓ QSim module available for hybrid execution")
except ImportError as e:
    print(f"Warning: QSim not available for hybrid execution: {e}")
    QSIM_AVAILABLE = False

# Import config for status endpoint
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
        HYBRID_ALLOWED_MODULES,
    )
except ImportError:
    HYBRID_EXECUTION_ENABLED = False
    HYBRID_BLOCK_DANGEROUS_IMPORTS = True
    HYBRID_BLOCK_FILE_ACCESS = True
    HYBRID_BLOCK_NETWORK = True
    HYBRID_BLOCK_SHELL = True
    HYBRID_RESTRICT_BUILTINS = True
    HYBRID_BLOCK_CODE_EXECUTION = True
    HYBRID_MAX_EXECUTION_TIME = 30
    HYBRID_MAX_MEMORY_MB = 512
    HYBRID_MAX_SIMULATION_RUNS = 100
    HYBRID_ALLOWED_MODULES = []


router = APIRouter(prefix="/api/hybrid", tags=["hybrid"])


class HybridExecuteRequest(BaseModel):
    """Request model for hybrid execution."""
    code: str = Field(..., description="Python code to execute")
    framework: Optional[str] = Field(None, description="Framework hint (cirq, qiskit, pennylane)")
    timeout: Optional[int] = Field(None, description="Execution timeout in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": """
import cirq
from qcanvas import compile
import qsim

q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1]),
    cirq.measure(q[0], q[1], key='result')
])

qasm = compile(circuit, framework="cirq")
print(f"Generated QASM:\\n{qasm}")

result = qsim.run(qasm, shots=100, backend="cirq")
print(f"Counts: {result.counts}")
""",
                "framework": "cirq",
                "timeout": 30
            }
        }


class HybridValidateRequest(BaseModel):
    """Request model for code validation."""
    code: str = Field(..., description="Python code to validate")


class HybridExecuteResponse(BaseModel):
    """Response model for hybrid execution."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    qasm_generated: Optional[str] = None
    simulation_results: List[Dict[str, Any]] = []
    execution_time: str = ""
    error: Optional[str] = None
    error_line: Optional[int] = None
    error_type: Optional[str] = None


class HybridValidateResponse(BaseModel):
    """Response model for code validation."""
    valid: bool
    errors: Optional[List[str]] = None
    warnings: Optional[List[str]] = None


class HybridStatusResponse(BaseModel):
    """Response model for hybrid execution status."""
    enabled: bool
    sandbox_available: bool
    security_settings: Dict[str, Any]
    limits: Dict[str, Any]
    allowed_modules: List[str]


def effective_timeout(requested: Optional[int]) -> int:
    """Clients may ask for a shorter timeout, never a longer one."""
    cap = max(1, int(HYBRID_MAX_EXECUTION_TIME))
    if requested is None:
        return cap
    try:
        requested = int(requested)
    except (TypeError, ValueError):
        return cap
    return max(1, min(requested, cap))


def _ensure_fastqsim_session() -> None:
    """Blocking: make sure a FastQSim session token exists in os.environ."""
    try:
        from app.services.simulation_service import SimulationService
        ok, err = SimulationService()._ensure_fastqsim_session()
        if not ok:
            logger.warning("FastQSim session pre-provisioning warning: %s", err)
    except Exception as e:
        logger.warning("Failed to pre-provision FastQSim session: %s", e)


@router.post("/execute", response_model=HybridExecuteResponse)
async def execute_hybrid(request: HybridExecuteRequest):
    """
    Execute Python code with quantum circuits in a sandboxed environment.
    
    The code has access to:
    - `from qcanvas import compile` - Compile circuits to QASM
    - `import qsim` and `qsim.run()` - Execute QASM simulations
    - `print()` - Output text (captured and returned)
    - Quantum frameworks: cirq, qiskit, pennylane
    - Safe modules: numpy, math, etc.
    
    Security restrictions are applied based on config settings.

    The code runs in a separate, resource-limited child process that is killed
    after min(request.timeout, HYBRID_MAX_EXECUTION_TIME) seconds.  When all
    execution slots stay busy for USER_CODE_QUEUE_TIMEOUT seconds the endpoint
    answers HTTP 503 with a "server busy, try again" message.

    Returns:
        HybridExecuteResponse with stdout, simulation results, and errors
    """
    if not SANDBOX_AVAILABLE:
        return HybridExecuteResponse(
            success=False,
            error="Hybrid execution is not available. Sandbox module failed to load. Check backend logs for details.",
            error_type="ImportError"
        )
    
    if not HYBRID_EXECUTION_ENABLED:
        return HybridExecuteResponse(
            success=False,
            error="Hybrid execution is disabled in configuration. Set HYBRID_EXECUTION_ENABLED=True in config/config.py",
            error_type="DisabledError"
        )
    
    if not QSIM_AVAILABLE:
        return HybridExecuteResponse(
            success=False,
            error="QSim simulation backend is not available. qsim.run() will not work.",
            error_type="ImportError",
            stdout="Note: You can still use qcanvas.compile() for QASM generation."
        )
    
    try:
        exec_timeout = effective_timeout(request.timeout)

        # Resolve FastQSim online mode once here (cached; may hit AWS SSM) so
        # the child process never has to, and provision a session only when
        # the run will actually talk to FastQSim.  Both are blocking network
        # calls, so they run off the event loop.
        online_mode = False
        if qsim_wrapper is not None:
            try:
                online_mode = await asyncio.to_thread(qsim_wrapper.resolve_online_mode)
            except Exception as e:
                logger.warning("Could not resolve FastQSim online mode: %s", e)
        uses_fastqsim = online_mode or ("fastqsim" in request.code)
        child_env: Dict[str, str] = {}
        if uses_fastqsim:
            await asyncio.to_thread(_ensure_fastqsim_session)
            child_env = {k: os.environ[k] for k in _FASTQSIM_CHILD_ENV if os.environ.get(k)}

        outcome = await run_isolated_async(
            execute_sandboxed_job,
            kwargs={
                "code": request.code,
                "framework_hint": request.framework,
                "online_mode": online_mode,
            },
            timeout=exec_timeout,
            env=child_env,
            label="hybrid",
        )

        if outcome.ok and isinstance(outcome.value, dict):
            data = outcome.value
        else:
            # The child was killed (timeout / memory) or crashed.
            data = {
                "success": False,
                "error": outcome.error or "Execution failed.",
                "error_type": outcome.error_type or "ExecutionError",
                "stderr": "",
            }
        data.setdefault("execution_time", f"{outcome.duration * 1000:.2f}ms")

        sims = data.get("simulation_results") or []
        logger.info(
            "hybrid run: success=%s error_type=%s sims=%d duration=%.2fs",
            data.get("success"), data.get("error_type"), len(sims), outcome.duration,
        )

        # Convert to response model
        return HybridExecuteResponse(
            success=bool(data.get("success")),
            stdout=data.get("stdout") or "",
            stderr=data.get("stderr") or "",
            qasm_generated=data.get("qasm_generated"),
            simulation_results=sims,
            execution_time=data.get("execution_time") or "",
            error=data.get("error"),
            error_line=data.get("error_line"),
            error_type=data.get("error_type"),
        )

    except UserCodeBusyError as e:
        return JSONResponse(
            status_code=503,
            headers={"Retry-After": str(e.retry_after)},
            content={
                "detail": e.message,
                "success": False,
                "stdout": "",
                "stderr": "",
                "simulation_results": [],
                "execution_time": "",
                "error": e.message,
                "error_type": "ServerBusy",
            },
        )

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"Hybrid execution error: {e}")
        print(error_trace)
        
        return HybridExecuteResponse(
            success=False,
            error=f"Execution failed: {str(e)}",
            error_type=type(e).__name__,
            stderr=error_trace,
        )


@router.post("/validate", response_model=HybridValidateResponse)
async def validate_hybrid(request: HybridValidateRequest):
    """
    Validate Python code without executing it.
    
    Checks for:
    - Syntax errors
    - Blocked imports
    - Dangerous patterns
    
    Returns:
        HybridValidateResponse with validation result
    """
    if not SANDBOX_AVAILABLE:
        return HybridValidateResponse(
            valid=False,
            errors=["Validation is not available. Sandbox module failed to load."]
        )
    
    try:
        result = validate_code(request.code)
        
        return HybridValidateResponse(
            valid=result.get('valid', False),
            errors=result.get('errors'),
            warnings=result.get('warnings'),
        )
        
    except Exception as e:
        return HybridValidateResponse(
            valid=False,
            errors=[f"Validation error: {str(e)}"]
        )


@router.get("/status", response_model=HybridStatusResponse)
async def get_hybrid_status():
    """
    Get the current status and configuration of hybrid execution.
    
    Returns security settings, limits, and available modules.
    """
    return HybridStatusResponse(
        enabled=HYBRID_EXECUTION_ENABLED and SANDBOX_AVAILABLE and QSIM_AVAILABLE,
        sandbox_available=SANDBOX_AVAILABLE,
        security_settings={
            "block_dangerous_imports": HYBRID_BLOCK_DANGEROUS_IMPORTS,
            "block_file_access": HYBRID_BLOCK_FILE_ACCESS,
            "block_network": HYBRID_BLOCK_NETWORK,
            "block_shell": HYBRID_BLOCK_SHELL,
            "restrict_builtins": HYBRID_RESTRICT_BUILTINS,
            "block_code_execution": HYBRID_BLOCK_CODE_EXECUTION,
        },
        limits={
            "max_execution_time": HYBRID_MAX_EXECUTION_TIME,
            "max_memory_mb": get_isolation_stats().get("memory_limit_mb"),
            "max_simulation_runs": HYBRID_MAX_SIMULATION_RUNS,
            "max_concurrent_runs": get_isolation_stats().get("max_concurrency"),
            "queue_timeout": get_isolation_stats().get("queue_timeout"),
        },
        allowed_modules=list(HYBRID_ALLOWED_MODULES),
    )


@router.get("/health")
async def hybrid_health():
    """
    Health check for hybrid execution service.
    """
    issues = []
    if not SANDBOX_AVAILABLE:
        issues.append("Sandbox module not loaded")
    if not QSIM_AVAILABLE:
        issues.append("QSim module not available")
    if not HYBRID_EXECUTION_ENABLED:
        issues.append("Hybrid execution disabled in config")
    
    return {
        "status": "healthy" if not issues else "degraded",
        "sandbox_available": SANDBOX_AVAILABLE,
        "qsim_available": QSIM_AVAILABLE,
        "hybrid_enabled": HYBRID_EXECUTION_ENABLED,
        "isolation": get_isolation_stats(),
        "issues": issues if issues else None,
    }

