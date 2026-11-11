from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import sys
import os
import re
import uuid

# Add the project root directory to Python path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
sys.path.insert(0, project_root)

from app.models.schemas import ConversionRequest
from app.services.simulation_service import SimulationService
from app.config.database import get_db
from app.config.settings import settings
from sqlalchemy.orm import Session
from app.models.database_models import User, Simulation, SimulationBackend, ExecutionStatus
from app.api.routes.auth import get_optional_user
from app.core.middleware import limiter, limit_from_settings
from app.core.concurrency import BusyError, busy_response, release_db_connection, simulation_runner
from fastapi import Depends, Request
from starlette.concurrency import run_in_threadpool
from typing import Tuple

router = APIRouter(prefix="/api/simulator", tags=["simulator"])

# Initialize simulation service
simulation_service = SimulationService()

# ---------------------------------------------------------------------------
# ALGORITHM HINT → ACTIVITY TYPE MAPPING
# ---------------------------------------------------------------------------
# The frontend may pass an optional "algorithm_hint" field with the name of
# the algorithm the user is implementing. We map that to the correct
# gamification activity type.
ALGORITHM_HINT_MAP: Dict[str, str] = {
    # Canonical names (lowercase)
    "deutsch":       "algorithm_deutsch",
    "deutsch_jozsa": "algorithm_deutsch",
    "deutsch-jozsa": "algorithm_deutsch",
    "grover":        "algorithm_grover",
    "grover_search": "algorithm_grover",
    "shor":          "algorithm_shor",
    "shor_factoring": "algorithm_shor",
    "vqe":           "algorithm_vqe",
    "variational_quantum_eigensolver": "algorithm_vqe",
    "qaoa":          "algorithm_qaoa",
    "quantum_approximate_optimization": "algorithm_qaoa",
}

# ---------------------------------------------------------------------------
# QASM STRUCTURAL ANALYSIS
# Inspects gate sequences to detect structural properties of the circuit.
# Returns a list of activity_types that should be logged.
# ---------------------------------------------------------------------------
def analyse_qasm_for_achievements(qasm_code: str) -> List[str]:
    """
    Inspect the QASM gate sequence to detect structural circuit properties.

    Returns a list of zero or more gamification activity_types to award.
    These are ADDITIVE — entanglement AND superposition can both fire on the
    same circuit.
    """
    activities: List[str] = []
    code_lower = qasm_code.lower()

    # ------------------------------------------------------------------
    # 1. SUPERPOSITION — Hadamard gate present
    #    Any `h q[N]` or `h q_name` pattern.
    # ------------------------------------------------------------------
    if re.search(r'\bh\s+\w', code_lower):
        activities.append("superposition_circuit")

    # ------------------------------------------------------------------
    # 2. ENTANGLEMENT — two-qubit entangling gate present
    #    cx / cnot / cz / ch / cy / crx / cry / crz / cu / ccx / swap / cswap / iswap
    # ------------------------------------------------------------------
    entangling_pattern = r'\b(cx|cnot|cz|ch|cy|crx|cry|crz|cu|ccx|ccu|swap|cswap|iswap)\b'
    if re.search(entangling_pattern, code_lower):
        activities.append("entangled_circuit")

    # ------------------------------------------------------------------
    # 3. QAOA fingerprint — alternating cost (cx-rz-cx) + mixer (rx) layers
    #    Look for rz(...) AND rx(...) both present (necessary condition).
    #    Also look for the cx flanking rz (ZZ-interaction pattern).
    # ------------------------------------------------------------------
    has_rz = bool(re.search(r'\brz\s*\(', code_lower))
    has_rx = bool(re.search(r'\brx\s*\(', code_lower))
    has_cx_rz_cx = bool(re.search(r'cx\b.*\brz\s*\(.*\bcx\b', code_lower, re.DOTALL))
    if has_rz and has_rx and has_cx_rz_cx:
        activities.append("algorithm_qaoa")

    # ------------------------------------------------------------------
    # 4. VQE fingerprint — parameterized rotations WITHOUT the cx-rz-cx
    #    cost-layer pattern. ry/rx/rz with numeric angles + entanglement.
    # ------------------------------------------------------------------
    has_ry = bool(re.search(r'\bry\s*\(', code_lower))
    has_cx = bool(re.search(r'\bcx\b', code_lower))
    # VQE: has parameterized rotations + entanglement but NOT detected as QAOA
    if has_ry and has_cx and "algorithm_qaoa" not in activities:
        # Must have at least 2 rotation angles (variational form heuristic)
        angle_count = len(re.findall(r'\bry\s*\(', code_lower)) + len(re.findall(r'\brx\s*\(', code_lower))
        if angle_count >= 2:
            activities.append("algorithm_vqe")

    # ------------------------------------------------------------------
    # 5. Grover fingerprint — ccx (Toffoli) gate + h + x gates
    #    The diffusion operator always needs ccx + H + X gates together.
    # ------------------------------------------------------------------
    has_ccx = bool(re.search(r'\bccx\b', code_lower))
    has_x   = bool(re.search(r'\bx\s+\w', code_lower))
    has_h   = bool(re.search(r'\bh\s+\w', code_lower))
    if has_ccx and has_h and has_x:
        activities.append("algorithm_grover")

    # ------------------------------------------------------------------
    # 6. Shor / QFT fingerprint — cascading phase rotations (cp gate with
    #    fractions of pi) + swap gates = Quantum Fourier Transform subroutine
    # ------------------------------------------------------------------
    cp_gates = re.findall(r'\bcp\s*\((.*?)\)', code_lower)
    has_swap = bool(re.search(r'\bswap\b', code_lower))
    # Need at least 2 different cp angles (cascade) and swap gates
    if len(cp_gates) >= 2 and has_swap:
        activities.append("algorithm_shor")

    # ------------------------------------------------------------------
    # 7. Deutsch-Jozsa fingerprint — H-Oracle-H sandwich:
    #    H gates at the very start AND near the end, with different gates
    #    in between (the oracle). 
    #    We detect this by checking: first gate is H, last measurement is
    #    preceded by H, and ancilla qubit gets X+H at start.
    # ------------------------------------------------------------------
    lines = [l.strip() for l in qasm_code.splitlines() if l.strip() and not l.strip().startswith('//') and not l.strip().startswith('OPENQASM') and not l.strip().startswith('include') and not l.strip().startswith('qreg') and not l.strip().startswith('creg')]
    gate_lines = [l for l in lines if not l.startswith('measure')]
    if gate_lines:
        first_gate = gate_lines[0].lower()
        last_few = " ".join(gate_lines[-3:]).lower()
        first_is_h = first_gate.startswith('h ')
        last_has_h = bool(re.search(r'\bh\s+', last_few))
        has_x_anchor = bool(re.search(r'\bx\s+\w', qasm_code.lower()))
        if first_is_h and last_has_h and has_x_anchor:
            # Only add Deutsch if Grover not already detected (avoid double-reporting)
            if "algorithm_grover" not in activities:
                activities.append("algorithm_deutsch")

    return activities


# ---------------------------------------------------------------------------
# SERVER-SIDE SAFETY LIMITS
# A statevector needs 2^n amplitudes, so a single careless "qubit[40] q;" can
# exhaust the container's RAM. Requests above the caps are rejected up front.
# ---------------------------------------------------------------------------
_COMMENT_RE = re.compile(r"//[^\n]*|/\*.*?\*/", re.DOTALL)
_QUBIT_ARRAY_RE = re.compile(r"\bqubit\s*\[\s*([A-Za-z_]\w*|\d+)\s*\]")
_QUBIT_SINGLE_RE = re.compile(r"\bqubit\s+[A-Za-z_]\w*\s*;")
_QREG_RE = re.compile(r"\bqreg\s+[A-Za-z_]\w*\s*\[\s*(\d+)\s*\]")
_PHYSICAL_QUBIT_RE = re.compile(r"\$(\d+)\b")
_CONST_TEMPLATE = r"\bconst\s+u?int(?:\s*\[\s*\d+\s*\])?\s+{name}\s*=\s*(\d+)\s*;"

SUPPORTED_FRAMEWORKS = {"qiskit", "cirq", "pennylane"}


def count_declared_qubits(qasm_code: str) -> int:
    """Total qubits declared in an OpenQASM 2/3 program (comments ignored)."""
    code = _COMMENT_RE.sub(" ", qasm_code)
    total = 0
    for match in _QUBIT_ARRAY_RE.finditer(code):
        size = match.group(1)
        if size.isdigit():
            total += int(size)
        else:
            const = re.search(_CONST_TEMPLATE.format(name=re.escape(size)), code)
            if const:
                total += int(const.group(1))
    total += len(_QUBIT_SINGLE_RE.findall(code))
    total += sum(int(n) for n in _QREG_RE.findall(code))
    physical = [int(n) for n in _PHYSICAL_QUBIT_RE.findall(code)]
    if physical:
        total += max(physical) + 1
    return total


def validate_simulation_request(qasm_code: str, shots: Any, max_qubits: int) -> Tuple[Optional[int], Optional[str]]:
    """Returns (shots_as_int, None) or (None, user-facing error message)."""
    max_chars = settings.SIM_MAX_QASM_CHARS
    if len(qasm_code) > max_chars:
        return None, f"The circuit is too large ({len(qasm_code):,} characters). The limit is {max_chars:,} characters."

    try:
        if isinstance(shots, bool) or (isinstance(shots, float) and not shots.is_integer()):
            raise ValueError
        shots_int = int(shots)
    except (TypeError, ValueError):
        return None, "shots must be a whole number."
    if shots_int < 0:
        return None, "shots cannot be negative."
    max_shots = settings.SIM_MAX_SHOTS
    if shots_int > max_shots:
        return None, f"Too many shots ({shots_int:,}). The maximum is {max_shots:,} shots per run."

    qubits = count_declared_qubits(qasm_code)
    if qubits > max_qubits:
        return None, (
            f"This circuit uses {qubits} qubits, but the simulator allows at most {max_qubits} "
            f"qubits per run (memory doubles with every extra qubit). Please reduce the number of qubits."
        )
    return shots_int, None


def _rate_limit_compute():
    return limit_from_settings("RATE_LIMIT_COMPUTE_PER_USER", "RATE_LIMIT_COMPUTE_PER_IP")


# ---------------------------------------------------------------------------
# POST-RUN BOOKKEEPING (sync DB work, executed in the threadpool)
# ---------------------------------------------------------------------------
def _award_legacy_simulation_xp(db: Session, user_id: str, username: str, backend: str, shots: int, result: Dict[str, Any]) -> None:
    try:
        from app.services.gamification_service import GamificationService

        metadata = {
            "backend": backend,
            "shots": shots,
            "qubits": result.get("metadata", {}).get("num_qubits", 0) if result.get("metadata") else 0
        }
        GamificationService.award_xp(
            db=db,
            user_id=user_id,
            activity_type='simulation_run',
            metadata=metadata
        )
        print(f"✅ Awarded XP to user {username} for simulation")
    except Exception as e:
        # Don't fail the request if gamification fails
        print(f"❌ Failed to award XP for simulation: {e}")


def _record_qsim_success(
    db: Session,
    user_id: str,
    request_data: Dict[str, Any],
    backend: str,
    shots: int,
    qasm_input: str,
    result: Dict[str, Any],
) -> None:
    """Award XP and store simulation history. Never raises."""
    try:
        from app.services.gamification_service import GamificationService

        qubits = result.get("results", {}).get("metadata", {}).get("num_qubits", 0)
        base_metadata = {"backend": backend, "shots": shots, "qubits": qubits}

        # Always award simulation_run XP
        GamificationService.award_xp(
            db=db,
            user_id=user_id,
            activity_type='simulation_run',
            metadata=base_metadata
        )

        # ── Specialization Tracking ─────────────────────────────────
        # Log the specific input framework used (or fallback to backend if QASM)
        input_framework_val = str(request_data.get("input_framework") or "").strip().lower()
        if input_framework_val not in SUPPORTED_FRAMEWORKS:
            input_framework_val = backend.lower()
        framework_activity = f"{input_framework_val}_circuit"

        GamificationService.award_xp(
            db=db,
            user_id=user_id,
            activity_type=framework_activity,
            metadata=base_metadata
        )
        print(f"✅ Specialization tracking → logged '{framework_activity}'")

        # ── Algorithm hint (sent explicitly by the frontend) ─────────
        algorithm_hint = str(request_data.get("algorithm_hint") or "").strip().lower()
        if algorithm_hint:
            mapped_activity = ALGORITHM_HINT_MAP.get(algorithm_hint)
            if mapped_activity:
                GamificationService.award_xp(
                    db=db,
                    user_id=user_id,
                    activity_type=mapped_activity,
                    metadata={**base_metadata, "detected_by": "algorithm_hint", "hint": algorithm_hint}
                )
                print(f"✅ Algorithm hint '{algorithm_hint}' → logged '{mapped_activity}'")

        # ── QASM structural analysis ─────────────────────────────────
        detected_activities = analyse_qasm_for_achievements(qasm_input)
        for act in detected_activities:
            # Don't double-log if the hint already covered this activity
            if act == ALGORITHM_HINT_MAP.get(algorithm_hint):
                continue
            GamificationService.award_xp(
                db=db,
                user_id=user_id,
                activity_type=act,
                metadata={**base_metadata, "detected_by": "qasm_analysis"}
            )
            print(f"✅ QASM analysis detected → logged '{act}'")

    except Exception as e:
        # Don't fail the request if gamification fails
        print(f"❌ Failed to award XP for simulation: {e}")

    # Save simulation history.
    try:
        # SimulationBackend values are lowercase ("statevector", ...); QSim backends
        # (cirq/qiskit/pennylane) aren't in the enum, so they are stored as STATEVECTOR.
        backend_enum = SimulationBackend.STATEVECTOR
        try:
            backend_enum = SimulationBackend(str(backend).lower())
        except ValueError:
            pass  # Keep default

        sim_record = Simulation(
            user_id=uuid.UUID(str(user_id)),
            qasm_code=qasm_input,
            backend=backend_enum,
            shots=shots,
            results_json=result.get("results"),
            status=ExecutionStatus.SUCCESS,
            execution_time_ms=int(float(str(result.get("results", {}).get("metadata", {}).get("execution_time", "0")).replace("ms", ""))) if result.get("results") else 0
        )
        db.add(sim_record)
        db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"Failed to save simulation history: {e}")


# ---------------------------------------------------------------------------
# ENDPOINTS
# The simulation itself runs in the threadpool via simulation_runner (at most
# SIM_MAX_CONCURRENCY per worker), so the event loop keeps serving other users.
# ---------------------------------------------------------------------------
@router.post("/execute")
@limiter.limit(_rate_limit_compute())
async def execute_qasm(
    request: Request,
    request_data: dict,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Execute OpenQASM code using the quantum simulator (legacy)

    Args:
        request: FastAPI Request (for rate limiting)
        request_data: Dictionary containing qasm_code, backend, shots, etc.

    """
    try:
        qasm_code = request_data.get("qasm_code")
        backend = request_data.get("backend", "statevector")
        shots = request_data.get("shots", 1024)

        if not qasm_code:
            raise HTTPException(status_code=400, detail="qasm_code is required")
        if not isinstance(qasm_code, str) or not isinstance(backend, str):
            raise HTTPException(status_code=400, detail="qasm_code and backend must be strings")

        shots, error = validate_simulation_request(qasm_code, shots, settings.SIM_LEGACY_MAX_QUBITS)
        if error:
            raise HTTPException(status_code=400, detail=error)

        user_id = str(current_user.id) if current_user else None
        username = current_user.username if current_user else None
        await release_db_connection(db)

        # Execute the simulation (off the event loop, bounded)
        try:
            result = await simulation_runner.run(
                simulation_service.execute_qasm,
                qasm_code=qasm_code,
                backend=backend,
                shots=shots
            )
        except BusyError:
            return busy_response("simulator")

        # Award XP for successful simulation if user is authenticated
        if user_id and result.get("success"):
            await run_in_threadpool(_award_legacy_simulation_xp, db, user_id, username, backend, shots, result)

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simulation failed: {str(e)}")

@router.post("/execute-qsim")
@limiter.limit(_rate_limit_compute())
async def execute_qasm_with_qsim(
    request: Request,
    request_data: dict,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Execute OpenQASM code using QSim backend

    Args:
        request: FastAPI Request
        request_data: Dictionary containing qasm_input, backend (cirq/qiskit/pennylane), shots

    Returns:
        JSON response with QSim simulation results
    """
    try:
        qasm_input = request_data.get("qasm_input")
        backend = request_data.get("backend", "cirq")
        shots = request_data.get("shots", 1024)

        if not qasm_input:
            return JSONResponse(
                content={"success": False, "error": "qasm_input is required"},
                status_code=400
            )
        if not isinstance(qasm_input, str) or not isinstance(backend, str):
            return JSONResponse(
                content={"success": False, "error": "qasm_input and backend must be strings"},
                status_code=400
            )

        max_qubits = settings.SIM_MAX_QUBITS
        if backend.strip().lower() == "pennylane":
            max_qubits = min(max_qubits, settings.SIM_MAX_QUBITS_PENNYLANE)
        shots, error = validate_simulation_request(qasm_input, shots, max_qubits)
        if error:
            return JSONResponse(content={"success": False, "error": error}, status_code=400)

        user_id = str(current_user.id) if current_user else None
        await release_db_connection(db)

        # Execute with QSim - wrap in try-except to catch any unexpected exceptions
        try:
            result = await simulation_runner.run(
                simulation_service.execute_qasm_with_qsim,
                qasm_code=qasm_input,
                backend=backend,
                shots=shots
            )
        except BusyError:
            return busy_response("simulator")
        except Exception as service_error:
            # If service itself raises an exception (shouldn't happen, but safety check)
            import traceback
            error_trace = traceback.format_exc()
            print(f"Unexpected exception in simulation_service.execute_qasm_with_qsim: {service_error}")
            print(error_trace)
            return JSONResponse(
                content={
                    "success": False,
                    "error": f"Service error: {str(service_error)}"
                },
                status_code=500
            )

        # Check if simulation failed and return appropriate status code
        if not result.get("success", False):
            return JSONResponse(
                content=result,
                status_code=400  # Use 400 for simulation failures (bad input/execution)
            )

        # Award XP + save history for authenticated users (sync DB work, off the event loop)
        if user_id:
            await run_in_threadpool(
                _record_qsim_success, db, user_id, request_data, backend, shots, qasm_input, result
            )

        return JSONResponse(content=result)

    except HTTPException:
        raise
    except Exception as e:
        # Log the full error for debugging
        import traceback
        error_trace = traceback.format_exc()
        print(f"QSim execution error in route handler: {e}")
        print(error_trace)

        # Return error response instead of raising HTTPException to ensure proper format
        error_detail = str(e)
        # Try to extract more specific error message
        if hasattr(e, '__cause__') and e.__cause__:
            error_detail = str(e.__cause__)
        elif hasattr(e, 'args') and e.args:
            error_detail = str(e.args[0])

        return JSONResponse(
            content={
                "success": False,
                "error": f"QSim simulation failed: {error_detail}"
            },
            status_code=500
        )

@router.get("/backends")
async def get_available_backends():
    """
    Get list of available simulation backends

    Returns:
        List of available backend names
    """
    try:
        backends = simulation_service.get_available_backends()
        return {"backends": backends}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get backends: {str(e)}")

@router.get("/limits")
async def get_simulation_limits():
    """Server-side simulation caps, so the UI can show them up front."""
    return {
        "max_qubits": settings.SIM_MAX_QUBITS,
        "max_qubits_pennylane": min(settings.SIM_MAX_QUBITS, settings.SIM_MAX_QUBITS_PENNYLANE),
        "max_shots": settings.SIM_MAX_SHOTS,
        "max_qasm_chars": settings.SIM_MAX_QASM_CHARS,
    }

@router.get("/health")
async def simulator_health():
    """
    Health check for the simulator service

    Returns:
        Health status of the simulator service
    """
    try:
        status = simulation_service.health_check()
        return status
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
