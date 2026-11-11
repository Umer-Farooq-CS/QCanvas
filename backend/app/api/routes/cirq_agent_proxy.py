"""
Reverse proxy to the Cirq-RAG-Code-Assistant FastAPI service.

Browser calls: {QCanvas API}/api/cirq-agent/api/v1/...
Forwarded to:  {CIRQ_AGENT_URL}/api/v1/...

Uses a long read timeout because the pipeline is synchronous and often 15–60+ seconds.
"""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.config.database import get_db
from app.config.settings import settings
from app.core.concurrency import release_db_connection
from app.models.database_models import User, UserRole
from app.api.routes.auth import get_current_user

router = APIRouter(prefix="/api/cirq-agent", tags=["cirq-agent"])

_CIRQ_TIMEOUT = httpx.Timeout(120.0, connect=15.0)

# Only these request headers are forwarded upstream. In particular the user's
# Authorization (QCanvas session JWT) and Cookie headers are NOT forwarded: the
# Cirq agent authenticates this proxy via X-API-Key only.
_FORWARDED_REQUEST_HEADERS = frozenset(
    {
        "accept",
        "accept-language",
        "content-type",
        "x-request-id",
    }
)

# Upstream response headers worth passing back to the browser.
_FORWARDED_RESPONSE_HEADERS = (
    "retry-after",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "x-request-id",
)


def _forward_request_headers(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in request.headers.items():
        if key.lower() in _FORWARDED_REQUEST_HEADERS:
            out[key] = value

    # Inject the X-API-Key expected by the Cirq agent.
    api_key = settings.CIRQ_RAG_API_KEY
    if api_key:
        out["X-API-Key"] = api_key

    return out


def _forward_response_headers(upstream: httpx.Response) -> dict[str, str]:
    out: dict[str, str] = {}
    for name in _FORWARDED_RESPONSE_HEADERS:
        value = upstream.headers.get(name)
        if value is not None:
            out[name] = value
    return out


@router.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
)
async def proxy_cirq_agent(
    path: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if current_user.role != UserRole.ADMIN:
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "You do not have permission to use the Cirq-RAG assistant."},
        )

    base = settings.CIRQ_AGENT_URL.rstrip("/")
    normalized_path = path.lstrip("/")

    # Be tolerant of CIRQ_AGENT_URL values that already include /api/v1.
    # This prevents forwarding to /api/v1/api/v1/* and resulting 404s.
    if base.endswith("/api/v1"):
        if normalized_path == "api/v1":
            normalized_path = ""
        elif normalized_path.startswith("api/v1/"):
            normalized_path = normalized_path[len("api/v1/"):]

    url = f"{base}/{normalized_path}" if normalized_path else base
    q = str(request.query_params)
    if q:
        url = f"{url}?{q}"

    body = await request.body()
    headers = _forward_request_headers(request)
    # Same session as get_current_user's; don't hold its pool connection for up
    # to two minutes while the upstream pipeline runs.
    await release_db_connection(db)

    async with httpx.AsyncClient(timeout=_CIRQ_TIMEOUT) as client:
        try:
            upstream = await client.request(
                request.method,
                url,
                content=body if body else None,
                headers=headers,
            )
        except httpx.ConnectError:
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Could not connect to the Cirq AI backend. "
                    "Ensure the service is running and CIRQ_AGENT_URL is correct."
                },
            )
        except httpx.TimeoutException:
            return JSONResponse(
                status_code=504,
                content={
                    "detail": "The Cirq AI pipeline timed out. Try a simpler prompt or reduce max optimization loops."
                },
            )

    ct = upstream.headers.get("content-type", "application/json")
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=ct,
        headers=_forward_response_headers(upstream),
    )
