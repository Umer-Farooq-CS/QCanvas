from fastapi import APIRouter
from fastapi.responses import JSONResponse
from app.models.schemas import HealthResponse
from datetime import datetime

router = APIRouter(prefix="/api/health", tags=["health"])


# Liveness: no DB / Redis / simulator work, so load balancers and load tests can
# hit it as often as they like. Served on both "/api/health" and "/api/health/"
# (without the first, "/api/health" answered with a 307 redirect).
@router.get("", response_model=HealthResponse, include_in_schema=False)
@router.get("/", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for the QCanvas backend

    Returns:
        HealthResponse with status, timestamp, and version
    """
    return HealthResponse(
        status="healthy",
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0"
    )


@router.get("/ready")
def readiness_check():
    """
    Readiness: verifies the database answers a trivial query. Plain `def`, so it
    runs in the threadpool and never blocks the event loop. Use this for deploy
    checks, not for high-frequency load-balancer probes.
    """
    from sqlalchemy import text
    from app.config.database import engine

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ready", "database": "ok"}
    except Exception:
        return JSONResponse(status_code=503, content={"status": "not_ready", "database": "unavailable"})
