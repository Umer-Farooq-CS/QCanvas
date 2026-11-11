"""
Bounded offloading of CPU-heavy work (simulation, conversion) from the event loop.

Each worker process gets at most ``max_concurrency`` jobs of a kind running at
once; further requests wait (without holding a thread) up to ``queue_timeout``
seconds and then receive a 503 "busy, retry" response. This keeps the event
loop and the shared threadpool free for cheap requests (auth, files, health)
even when many students press "Run" at the same moment.
"""
from __future__ import annotations

import asyncio
import weakref
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Optional

from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from app.config.settings import settings


class BusyError(Exception):
    """Raised when no execution slot became free within the queue timeout."""


class BoundedRunner:
    def __init__(self, name: str, concurrency_setting: str, timeout_setting: str) -> None:
        self.name = name
        self._concurrency_setting = concurrency_setting
        self._timeout_setting = timeout_setting
        # One semaphore per event loop (tests create several loops).
        self._semaphores: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = (
            weakref.WeakKeyDictionary()
        )

    @property
    def max_concurrency(self) -> int:
        return max(1, int(getattr(settings, self._concurrency_setting)))

    @property
    def queue_timeout(self) -> float:
        return float(getattr(settings, self._timeout_setting))

    def _semaphore(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        sem = self._semaphores.get(loop)
        if sem is None:
            sem = asyncio.Semaphore(self.max_concurrency)
            self._semaphores[loop] = sem
        return sem

    def reset(self) -> None:
        """Drop semaphores so new settings take effect (tests)."""
        self._semaphores = weakref.WeakKeyDictionary()

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        sem = self._semaphore()
        timeout: Optional[float] = self.queue_timeout
        if timeout is not None and timeout <= 0:
            timeout = None
        try:
            await asyncio.wait_for(sem.acquire(), timeout=timeout)
        except asyncio.TimeoutError:
            raise BusyError(self.name) from None
        try:
            yield
        finally:
            sem.release()

    async def run(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        async with self.slot():
            return await run_in_threadpool(func, *args, **kwargs)


simulation_runner = BoundedRunner("simulation", "SIM_MAX_CONCURRENCY", "SIM_QUEUE_TIMEOUT_SECONDS")
conversion_runner = BoundedRunner("conversion", "CONVERT_MAX_CONCURRENCY", "CONVERT_QUEUE_TIMEOUT_SECONDS")


def busy_response(what: str = "simulator", retry_after: int = 5) -> JSONResponse:
    message = f"The {what} is busy right now. Please try again in a few seconds."
    return JSONResponse(
        status_code=503,
        content={"success": False, "error": message, "detail": message, "code": "busy", "retry_after": retry_after},
        headers={"Retry-After": str(retry_after)},
    )


async def release_db_connection(db: Any) -> None:
    """
    Return the session's pooled connection before long-running work.

    The auth dependency's user lookup leaves the session holding a connection
    (open transaction) for the rest of the request; during a multi-second
    simulation or a wait for a busy slot that would pin one pool connection per
    queued request and exhaust the pool. The session stays usable afterwards
    (it reconnects lazily); already-loaded attributes of detached objects such
    as ``current_user.id`` remain readable.
    """
    if db is None:
        return
    try:
        await run_in_threadpool(db.close)
    except Exception:
        pass
