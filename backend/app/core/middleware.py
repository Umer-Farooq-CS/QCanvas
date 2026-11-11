"""
Cross-cutting HTTP concerns: rate limiting, security headers and the API audit log.

Rate limiting
-------------
* Requests carrying a valid session JWT are limited per USER ("user:<id>"),
  everything else per real client IP ("ip:<addr>"). The client IP comes from
  X-Forwarded-For using FORWARDED_TRUSTED_HOPS (the entry appended by our own
  load balancer, which the client cannot spoof), so users behind the ALB no
  longer share a single bucket.
* Limits come from settings (env-configurable) and are read on every request.
* Counters live in Redis when it is reachable at startup (shared by all worker
  processes), otherwise in process memory. If Redis dies later, slowapi falls
  back to memory instead of failing requests.

Audit log
---------
Pure ASGI middleware that only enqueues a small dict per request; a background
thread batches the rows into the api_activity table. Logging can never block
the event loop or fail a request.
"""
from __future__ import annotations

import logging
import math
import queue
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config.settings import settings
from app.utils.jwt_auth import verify_token

logger = logging.getLogger("qcanvas.middleware")


# ============================================================================
# CLIENT IDENTIFICATION
# ============================================================================

def _header_from_scope(scope: Scope, name: str) -> Optional[str]:
    target = name.lower().encode("latin-1")
    for key, value in scope.get("headers") or []:
        if key.lower() == target:
            return value.decode("latin-1")
    return None


def client_ip_from_scope(scope: Scope) -> str:
    """
    Best-effort real client IP.

    1. CLIENT_IP_HEADER (e.g. CF-Connecting-IP) if configured and present.
    2. X-Forwarded-For: each proxy APPENDS the address it received the request
       from, so the entry FORWARDED_TRUSTED_HOPS from the right is the one
       written by our outermost trusted proxy (unspoofable by the client).
       uvicorn's proxy_headers with forwarded_allow_ips="*" uses the LEFTMOST
       entry instead, which the client controls, so we don't rely on it here.
    3. The socket peer address.
    """
    custom_header = (settings.CLIENT_IP_HEADER or "").strip()
    if custom_header:
        value = _header_from_scope(scope, custom_header)
        if value and value.strip():
            return value.split(",")[0].strip()

    hops = settings.FORWARDED_TRUSTED_HOPS
    if hops and hops > 0:
        xff = _header_from_scope(scope, "x-forwarded-for")
        if xff:
            entries = [part.strip() for part in xff.split(",") if part.strip()]
            if entries:
                return entries[-hops] if len(entries) >= hops else entries[0]

    client = scope.get("client")
    if client and client[0]:
        return str(client[0])
    return "unknown"


def get_client_ip(request: Request) -> str:
    return client_ip_from_scope(request.scope)


def _bearer_token(scope: Scope) -> Optional[str]:
    auth = _header_from_scope(scope, "authorization")
    if not auth:
        return None
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def user_id_from_scope(scope: Scope) -> Optional[str]:
    """User id from a valid session JWT. Purpose tokens (with an "intent" claim) are ignored."""
    token = _bearer_token(scope)
    if not token:
        return None
    try:
        payload = verify_token(token)
    except Exception:
        return None
    if not payload or payload.get("intent"):
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def rate_limit_key(request: Request) -> str:
    """slowapi key function: per user when signed in, otherwise per real client IP."""
    user_id = user_id_from_scope(request.scope)
    if user_id:
        return f"user:{user_id}"
    return f"ip:{get_client_ip(request)}"


# ============================================================================
# CONFIGURABLE LIMITS
# ============================================================================

def limit_from_settings(user_setting: str, ip_setting: Optional[str] = None) -> Callable[[str], str]:
    """
    Build a slowapi dynamic limit provider that reads its value from settings on
    every request. With ``ip_setting`` the limit differs for signed-in users
    (``user_setting``) and anonymous callers keyed by IP (``ip_setting``).
    """

    def provider(key: str) -> str:
        if ip_setting and not str(key).startswith("user:"):
            return getattr(settings, ip_setting)
        return getattr(settings, user_setting)

    provider.__name__ = f"limit_{user_setting.lower()}"
    return provider


# Endpoints in other modules that pass a plain limit string (a literal, or a
# settings value read once at import). The ConfigurableLimiter swaps it for a
# provider that reads the same setting on every request, so values can be
# changed (e.g. in tests or via a settings reload) and stray literals can't
# silently lock a whole venue out. Callable limits are left untouched.
ENDPOINT_LIMIT_OVERRIDES: Dict[str, Callable[[str], str]] = {
    "app.api.routes.auth.create_guest_session": limit_from_settings("GUEST_CREATE_RATE_LIMIT"),
    "app.api.routes.auth.login": limit_from_settings("RATE_LIMIT_LOGIN"),
    "app.api.routes.auth.register": limit_from_settings("RATE_LIMIT_REGISTER"),
    "app.api.routes.auth.register_admin": limit_from_settings("RATE_LIMIT_REGISTER_ADMIN"),
    "app.api.routes.auth.send_signup_otp": limit_from_settings("RATE_LIMIT_OTP_SEND"),
    "app.api.routes.auth.resend_signup_otp": limit_from_settings("RATE_LIMIT_OTP_SEND"),
    "app.api.routes.auth.verify_signup_otp": limit_from_settings("RATE_LIMIT_OTP_VERIFY"),
    "app.api.routes.auth.send_password_reset_otp": limit_from_settings("RATE_LIMIT_PASSWORD_RESET"),
    "app.api.routes.auth.verify_password_reset_otp": limit_from_settings("RATE_LIMIT_OTP_VERIFY"),
    "app.api.routes.auth.complete_password_reset": limit_from_settings("RATE_LIMIT_PASSWORD_RESET"),
}


class ConfigurableLimiter(Limiter):
    """Limiter whose hard-coded per-route literals can be overridden from settings."""

    def limit(self, limit_value, *args, **kwargs):  # type: ignore[override]
        parent_limit = super().limit

        def decorator(func):
            name = f"{func.__module__}.{func.__name__}"
            value = limit_value
            if not callable(limit_value) and name in ENDPOINT_LIMIT_OVERRIDES:
                value = ENDPOINT_LIMIT_OVERRIDES[name]
            return parent_limit(value, *args, **kwargs)(func)

        return decorator


# ============================================================================
# STORAGE SELECTION
# ============================================================================

def _redis_reachable(url: str, timeout: float) -> bool:
    try:
        import redis  # type: ignore

        client = redis.Redis.from_url(url, socket_connect_timeout=timeout, socket_timeout=timeout)
        try:
            return bool(client.ping())
        finally:
            try:
                client.close()
            except Exception:
                pass
    except Exception:
        return False


def resolve_rate_limit_storage() -> str:
    configured = (settings.RATE_LIMIT_STORAGE_URI or "").strip()
    if configured and configured.lower() != "auto":
        return configured
    redis_url = settings.REDIS_URL
    if redis_url and _redis_reachable(redis_url, settings.RATE_LIMIT_REDIS_TIMEOUT_SECONDS):
        return redis_url
    return "memory://"


def _build_limiter() -> Limiter:
    storage_uri = resolve_rate_limit_storage()
    storage_options: Dict[str, Any] = {}
    if storage_uri.startswith(("redis://", "rediss://")):
        timeout = settings.RATE_LIMIT_REDIS_TIMEOUT_SECONDS
        # Never let a slow/dead Redis hang requests; slowapi falls back to memory on errors.
        storage_options = {"socket_connect_timeout": timeout, "socket_timeout": timeout}
    try:
        built = ConfigurableLimiter(
            key_func=rate_limit_key,
            storage_uri=storage_uri,
            storage_options=storage_options,
            in_memory_fallback_enabled=True,
            swallow_errors=True,
            key_prefix="qcanvas-rl",
            enabled=settings.RATE_LIMIT_ENABLED,
        )
    except Exception as exc:  # bad URI / missing driver: never block startup
        logger.warning("Rate limit storage %r unusable (%s); using memory://", storage_uri, exc)
        storage_uri = "memory://"
        built = ConfigurableLimiter(
            key_func=rate_limit_key,
            storage_uri=storage_uri,
            swallow_errors=True,
            key_prefix="qcanvas-rl",
            enabled=settings.RATE_LIMIT_ENABLED,
        )
    built.qcanvas_storage_uri = "redis" if storage_uri.startswith(("redis://", "rediss://")) else storage_uri  # type: ignore[attr-defined]
    return built


limiter = _build_limiter()


def _retry_after_seconds(request: Request, exc: RateLimitExceeded) -> int:
    try:
        view = getattr(request.state, "view_rate_limit", None)
        if view:
            item, args = view
            reset_at = limiter.limiter.get_window_stats(item, *args)[0]
            return max(1, int(math.ceil(reset_at - time.time())))
    except Exception:
        pass
    try:
        return max(1, int(exc.limit.limit.get_expiry()))
    except Exception:
        return 60


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Friendly JSON 429 with a Retry-After header (exposed to the browser via CORS)."""
    retry_after = _retry_after_seconds(request, exc)
    message = (
        f"Too many requests right now. Please wait {retry_after} second"
        f"{'' if retry_after == 1 else 's'} and try again."
    )
    return JSONResponse(
        status_code=429,
        content={
            "success": False,
            "error": message,
            "detail": message,
            "code": "rate_limited",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )


# ============================================================================
# SECURITY HEADERS (pure ASGI)
# ============================================================================

_SECURITY_HEADERS = (
    ("X-Frame-Options", "DENY"),
    ("X-Content-Type-Options", "nosniff"),
    ("Strict-Transport-Security", "max-age=31536000; includeSubDomains"),
    # Add your API domain to the connect-src so the browser allows the fetch
    (
        "Content-Security-Policy",
        "default-src 'self'; "
        "connect-src 'self' https://api.qcanvas.codes https://www.qcanvas.codes; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://fastapi.tiangolo.com",
    ),
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _SECURITY_HEADERS:
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_headers)


# ============================================================================
# AUDIT LOG (pure ASGI + background batch writer)
# ============================================================================

_AUDIT_SKIP_EXACT = frozenset(
    {"/", "/health", "/api/health", "/api/health/", "/docs", "/redoc", "/openapi.json", "/favicon.ico"}
)
_AUDIT_SKIP_PREFIXES = ("/api/health/", "/docs/")


def _audit_should_skip(method: str, path: str) -> bool:
    if method in ("OPTIONS", "HEAD"):
        return True
    if path in _AUDIT_SKIP_EXACT or path.startswith(_AUDIT_SKIP_PREFIXES):
        return True
    if path.endswith("/health") or path.endswith("/health/"):
        return True
    extra = settings.AUDIT_LOG_EXCLUDE_PATHS
    if extra:
        for prefix in extra.split(","):
            prefix = prefix.strip()
            if prefix and path.startswith(prefix):
                return True
    return False


class AuditLogWriter:
    """
    Collects audit rows in a bounded in-memory queue and inserts them in batches
    from a daemon thread. Rows are dropped (and counted) if the queue is full or
    the database is unavailable: auditing is best effort and must never slow
    down or break the API.
    """

    def __init__(
        self,
        session_factory: Optional[Callable[[], Any]] = None,
        batch_size: Optional[int] = None,
        flush_interval: Optional[float] = None,
        max_queue: Optional[int] = None,
    ) -> None:
        self._session_factory = session_factory
        self.batch_size = batch_size or settings.AUDIT_LOG_BATCH_SIZE
        self.flush_interval = flush_interval or settings.AUDIT_LOG_FLUSH_INTERVAL_SECONDS
        self._queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=max_queue or settings.AUDIT_LOG_MAX_QUEUE)
        self._thread: Optional[threading.Thread] = None
        self._start_lock = threading.Lock()
        self._write_lock = threading.Lock()
        self._stop = threading.Event()
        self.dropped = 0
        self.written = 0
        self._last_error_log = 0.0

    # -- request path ---------------------------------------------------------
    def submit(self, record: Dict[str, Any]) -> None:
        if self._thread is None:
            self._ensure_started()
        try:
            self._queue.put_nowait(record)
        except queue.Full:
            self.dropped += 1

    # -- background -----------------------------------------------------------
    def _ensure_started(self) -> None:
        with self._start_lock:
            if self._thread is not None:
                return
            self._stop.clear()
            thread = threading.Thread(target=self._run, name="audit-log-writer", daemon=True)
            thread.start()
            self._thread = thread

    def _drain(self, first: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        batch: List[Dict[str, Any]] = [first] if first is not None else []
        while len(batch) < self.batch_size:
            try:
                batch.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return batch

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                first = self._queue.get(timeout=self.flush_interval)
            except queue.Empty:
                continue
            try:
                self._write(self._drain(first))
            except Exception as exc:  # pragma: no cover - defensive
                self._log_error(f"audit writer loop error: {exc}")

    def flush(self) -> None:
        """Synchronously write everything currently queued (shutdown/tests)."""
        while True:
            batch = self._drain()
            if not batch:
                return
            self._write(batch)

    def shutdown(self, timeout: float = 5.0) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
        self._thread = None
        try:
            self.flush()
        except Exception as exc:
            self._log_error(f"audit flush on shutdown failed: {exc}")

    # -- persistence ----------------------------------------------------------
    def _log_error(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_error_log > 60:
            self._last_error_log = now
            logger.warning("%s (dropped so far: %d)", message, self.dropped)

    @staticmethod
    def _to_row(record: Dict[str, Any]) -> Dict[str, Any]:
        user_id = None
        token = record.get("token")
        if token:
            try:
                payload = verify_token(token)
                if payload and not payload.get("intent") and payload.get("sub"):
                    user_id = uuid.UUID(str(payload["sub"]))
            except Exception:
                user_id = None
        return {
            "user_id": user_id,
            "endpoint": (record.get("path") or "")[:255],
            "method": (record.get("method") or "")[:10],
            "status_code": int(record.get("status_code") or 0),
            "ip_address": (record.get("ip") or "unknown")[:45],
            "user_agent": record.get("user_agent") or "unknown",
            "response_time_ms": int(record.get("response_time_ms") or 0),
        }

    def _get_session(self):
        if self._session_factory is None:
            from app.config.database import SessionLocal

            self._session_factory = SessionLocal
        return self._session_factory()

    def _insert(self, rows: List[Dict[str, Any]]) -> None:
        from sqlalchemy import insert
        from app.models.database_models import ApiActivity

        db = self._get_session()
        try:
            db.execute(insert(ApiActivity.__table__), rows)
            db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
            raise
        finally:
            db.close()

    def _write(self, batch: List[Dict[str, Any]]) -> None:
        if not batch:
            return
        with self._write_lock:
            rows = [self._to_row(r) for r in batch]
            try:
                self._insert(rows)
                self.written += len(rows)
                return
            except Exception as exc:
                from sqlalchemy.exc import DataError, IntegrityError

                if not isinstance(exc, (IntegrityError, DataError)):
                    # DB down / pool exhausted: drop the batch rather than pile up.
                    self.dropped += len(rows)
                    self._log_error(f"Failed to write audit log batch: {exc}")
                    return
            # A bad row (e.g. user deleted -> FK violation) shouldn't sink the batch.
            for row in rows:
                try:
                    self._insert([row])
                    self.written += 1
                except Exception:
                    try:
                        self._insert([{**row, "user_id": None}])
                        self.written += 1
                    except Exception as exc:
                        self.dropped += 1
                        self._log_error(f"Failed to write audit log row: {exc}")


audit_log_writer = AuditLogWriter()


class AuditLogMiddleware:
    """Records method/path/status/latency for API calls without touching the DB on the request path."""

    def __init__(self, app: ASGIApp, writer: Optional[AuditLogWriter] = None) -> None:
        self.app = app
        self.writer = writer or audit_log_writer

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not settings.AUDIT_LOG_ENABLED:
            await self.app(scope, receive, send)
            return
        method = scope.get("method", "GET")
        path = scope.get("path", "")
        if _audit_should_skip(method, path):
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_holder = [500]

        async def send_capturing_status(message: Message) -> None:
            if message["type"] == "http.response.start":
                status_holder[0] = message.get("status", 500)
            await send(message)

        try:
            await self.app(scope, receive, send_capturing_status)
        finally:
            try:
                self.writer.submit(
                    {
                        "path": path,
                        "method": method,
                        "status_code": status_holder[0],
                        "ip": client_ip_from_scope(scope),
                        "user_agent": _header_from_scope(scope, "user-agent") or "unknown",
                        "token": _bearer_token(scope),
                        "response_time_ms": int((time.perf_counter() - start) * 1000),
                    }
                )
            except Exception:
                pass
