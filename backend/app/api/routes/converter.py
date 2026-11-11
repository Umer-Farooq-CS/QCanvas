from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List
import sys
import os

# Add the project root directory to Python path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
sys.path.insert(0, project_root)

from app.models.schemas import ConversionRequest, ConversionResponse, ParseResponse
from app.services.isolated_exec import UserCodeBusyError
from app.services.conversion_service import ConversionService
from app.config.database import get_db
from sqlalchemy.orm import Session
from app.models.database_models import User, Conversion, ConversionStats, QuantumFramework, ExecutionStatus
from app.api.routes.auth import get_optional_user
from typing import Optional
import uuid

from app.core.middleware import limiter, limit_from_settings
from app.core.concurrency import BusyError, busy_response, conversion_runner, release_db_connection
from fastapi import Request
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/api/converter", tags=["converter"])

# Initialize conversion service
conversion_service = ConversionService()

def _record_conversion_success(db: Session, user_id: str, request_data: ConversionRequest, result: dict) -> None:
    """Award XP and store conversion history. Runs in the threadpool; never raises."""
    # Award XP for successful conversion
    try:
        from app.services.gamification_service import GamificationService

        # Extract conversion metadata for XP tracking
        metadata = {
            "source_framework": request_data.framework,
            "target_framework": "openqasm",
            "qubits": result.get("conversion_stats", {}).get("qubits", 0) if result.get("conversion_stats") else 0,
            "gates": sum(result.get("conversion_stats", {}).get("gates", {}).values()) if result.get("conversion_stats") and result.get("conversion_stats").get("gates") else 0
        }

        GamificationService.award_xp(
            db=db,
            user_id=user_id,
            activity_type='conversion',
            metadata=metadata
        )
    except Exception as e:
        # Don't fail the request if gamification fails
        print(f"Failed to award XP for conversion: {e}")

    # Save conversion history.
    # NOTE: QuantumFramework (CIRQ, QISKIT, PENNYLANE) has no OPENQASM member and
    # conversions.target_framework is NOT NULL, so QISKIT is stored as a
    # placeholder target until the enum gets an OPENQASM value (needs a migration).
    try:
        source_fw = QuantumFramework(request_data.framework)
        conversion_record = Conversion(
            user_id=uuid.UUID(str(user_id)),
            source_framework=source_fw,
            target_framework=QuantumFramework.QISKIT, # Placeholder for OpenQASM
            source_code=request_data.code,
            qasm_code=result["qasm_code"],
            status=ExecutionStatus.SUCCESS,
            execution_time_ms=0 # We don't track time yet
        )
        db.add(conversion_record)
        db.commit()
        db.refresh(conversion_record)

        if result.get("conversion_stats"):
            stats_data = result["conversion_stats"]
            stats_record = ConversionStats(
                conversion_id=conversion_record.id,
                num_qubits=stats_data.get("qubits", 0) or 0,
                num_gates=sum(stats_data.get("gates", {}).values()) if stats_data.get("gates") else 0,
                circuit_depth=stats_data.get("depth", 0) or 0
            )
            db.add(stats_record)
            db.commit()
    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass
        print(f"Failed to save conversion history: {e}")


@router.post("/convert", response_model=ConversionResponse)
@limiter.limit(limit_from_settings("RATE_LIMIT_COMPUTE_PER_USER", "RATE_LIMIT_COMPUTE_PER_IP"))
async def convert_to_qasm(
    request: Request,
    request_data: ConversionRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """
    Convert quantum circuit code from specified framework to OpenQASM 3.0
    
    Args:
        request: FastAPI Request object (for rate limiting)
        request_data: ConversionRequest containing code, framework, and options
        
    Returns:
        ConversionResponse with OpenQASM code or error details
    """
    try:
        # Validate the request
        if not request_data.code.strip():
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        
        if request_data.framework not in ["qiskit", "cirq", "pennylane"]:
            raise HTTPException(status_code=400, detail="Unsupported framework")
        
        user_id = str(current_user.id) if current_user else None
        # Don't pin a DB pool connection while the (possibly slow) conversion runs.
        await release_db_connection(db)

        # Perform the conversion off the event loop, at most CONVERT_MAX_CONCURRENCY per worker.
        try:
            async with conversion_runner.slot():
                # Runs in an isolated, killable child process (user code may be exec'd).
                result = await conversion_service.convert_to_qasm_isolated(code=request_data.code, framework=request_data.framework, style=request_data.style)
        except (BusyError, UserCodeBusyError):
            return busy_response("converter")

        if result["success"]:
            # Award XP + save history (sync DB work, off the event loop)
            if user_id:
                await run_in_threadpool(_record_conversion_success, db, user_id, request_data, result)

            return ConversionResponse(
                success=True,
                qasm_code=result["qasm_code"],
                framework=result["framework"],
                qasm_version=result["qasm_version"],
                conversion_stats=result["conversion_stats"]
            )
        else:
            return ConversionResponse(
                success=False,
                error=result["error"],
                framework=result["framework"],
                qasm_version=result["qasm_version"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        # Return graceful error response with 200 to satisfy error handling workflow tests
        return ConversionResponse(
            success=False,
            error=f"Internal server error: {str(e)}",
            framework=getattr(request_data, 'framework', 'unknown'),
            qasm_version=getattr(request_data, 'qasm_version', '3.0')
        )

@router.get("/frameworks", response_model=List[str])
async def get_supported_frameworks():
    """
    Get list of supported quantum computing frameworks
    
    Returns:
        List of supported framework names
    """
    try:
        frameworks = conversion_service.get_supported_frameworks()
        return frameworks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get frameworks: {str(e)}")

@router.post("/validate")
async def validate_code(request: ConversionRequest):
    """
    Validate quantum circuit code syntax for the specified framework
    
    Args:
        request: ConversionRequest containing code and framework
        
    Returns:
        JSON response with validation result
    """
    try:
        if not request.code.strip():
            raise HTTPException(status_code=400, detail="Code cannot be empty")
        
        validation_result = await run_in_threadpool(
            conversion_service.validate_code,
            code=request.code,
            framework=request.framework
        )
        
        return JSONResponse(content=validation_result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/parse", response_model=ParseResponse)
@limiter.limit(limit_from_settings("RATE_LIMIT_PARSE_PER_USER", "RATE_LIMIT_PARSE_PER_IP"))
async def parse_circuit_gates(
    request: Request,
    request_data: ConversionRequest
):
    """
    Parse quantum circuit code and extract gates for visualization.
    Uses AST-based parsing for accurate gate extraction without code execution.
    
    Args:
        request: FastAPI Request object (for rate limiting)
        request_data: ConversionRequest containing code and framework
        
    Returns:
        ParseResponse with gates list, qubit count, or error details
    """
    try:
        if not request_data.code.strip():
            return ParseResponse(
                success=False,
                error="Code cannot be empty",
                framework=request_data.framework
            )
        
        if request_data.framework not in ["qiskit", "cirq", "pennylane"]:
            return ParseResponse(
                success=False,
                error="Unsupported framework",
                framework=request_data.framework
            )
        
        # Parse the circuit using AST parsers
        result = await run_in_threadpool(
            conversion_service.parse_circuit_gates,
            code=request_data.code,
            framework=request_data.framework
        )
        
        if result["success"]:
            return ParseResponse(
                success=True,
                gates=result["gates"],
                qubits=result["qubits"],
                framework=request_data.framework
            )
        else:
            return ParseResponse(
                success=False,
                error=result["error"],
                framework=request_data.framework
            )
            
    except Exception as e:
        return ParseResponse(
            success=False,
            error=f"Parse error: {str(e)}",
            framework=getattr(request_data, 'framework', 'unknown')
        )


@router.get("/health")
async def converter_health():
    """
    Health check for the converter service
    
    Returns:
        Health status of the converter service
    """
    try:
        # Test if converters are working
        frameworks = conversion_service.get_supported_frameworks()
        return {
            "status": "healthy",
            "frameworks_available": len(frameworks),
            "supported_frameworks": frameworks
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
