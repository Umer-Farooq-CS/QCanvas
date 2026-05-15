"""
Jupyter Kernel Gateway WebSocket executor for FastQubit pods.

FastQubit provisions a Jupyter Kernel Gateway pod per session.
This module sends Python code to that pod over its /channels WebSocket
using the Jupyter wire protocol (execute_request / execute_reply).

The browser cannot set the required X-WS-Token header directly on a
WebSocket upgrade, so this server-side module proxies the connection.
"""

from __future__ import annotations

import json
import os
import ssl
import time
from typing import Any

try:
    import websocket
    from jupyter_client.session import Session
    KERNEL_WS_AVAILABLE = True
except ImportError:
    KERNEL_WS_AVAILABLE = False
    websocket = None
    Session = None


def _sslopts() -> dict[str, Any]:
    if os.getenv("FASTQUBIT_WS_INSECURE_SSL", "").strip().lower() in ("1", "true", "yes"):
        return {"cert_reqs": ssl.CERT_NONE}
    return {}


def _ws_headers(ws_token: str) -> list[str]:
    headers = [f"X-WS-Token: {ws_token}"]
    origin = os.getenv("FASTQUBIT_WS_ORIGIN", "").strip()
    if origin:
        headers.append(f"Origin: {origin}")
    return headers


def execute_python_on_kernel(
    ws_url: str,
    ws_token: str,
    code: str,
    timeout: float = 300.0,
) -> dict[str, Any]:
    """
    Send one execute_request on the kernel /channels WebSocket and collect
    stdout/stderr/errors until execute_reply arrives (or timeout).

    Args:
        ws_url:    WebSocket URL from the FastQubit session (e.g. wss://…/channels)
        ws_token:  X-WS-Token header value from the FastQubit session
        code:      Python source code to execute on the pod
        timeout:   Maximum seconds to wait for execute_reply

    Returns:
        dict with keys: ok, stdout, stderr, errors, execute_reply, (error)
    """
    if not KERNEL_WS_AVAILABLE:
        return {
            "ok": False,
            "error": "websocket-client and jupyter_client packages are required for pod execution. "
                     "Add them to requirements.txt.",
            "stdout": "",
            "stderr": "",
            "errors": [],
        }

    sess = Session()
    req = sess.msg(
        "execute_request",
        content={
            "code": code,
            "silent": False,
            "store_history": True,
            "user_expressions": {},
            "allow_stdin": False,
            "stop_on_error": True,
        },
    )
    req["channel"] = "shell"
    msg_id = req["header"]["msg_id"]

    sslopt = _sslopts()
    ws = None
    stdout: list[str] = []
    stderr: list[str] = []
    errors: list[dict[str, Any]] = []
    execute_reply: dict[str, Any] | None = None
    decode_failures = 0
    deadline = time.monotonic() + timeout

    try:
        ws = websocket.create_connection(
            ws_url,
            header=_ws_headers(ws_token),
            sslopt=sslopt if sslopt else None,
            timeout=30,
        )
        ws.send(json.dumps(req, default=str))

        while time.monotonic() < deadline:
            ws.settimeout(max(1.0, min(30.0, deadline - time.monotonic())))
            raw = ws.recv()
            if raw is None:
                break
            if isinstance(raw, (bytes, bytearray)):
                raw = bytes(raw).decode("utf-8", errors="replace")
            if not isinstance(raw, str):
                stderr.append(f"[kernel_ws] non-text frame: {type(raw).__name__}\n")
                continue
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError as exc:
                decode_failures += 1
                stderr.append(f"[kernel_ws] JSONDecodeError ({exc}): {raw[:200]!r}...\n")
                if decode_failures > 25:
                    return {
                        "ok": False,
                        "error": "Too many non-JSON WebSocket frames — wrong protocol or gateway?",
                        "stdout": "".join(stdout),
                        "stderr": "".join(stderr),
                        "errors": errors,
                    }
                continue

            header = msg.get("header") or {}
            parent = msg.get("parent_header") or {}
            mt = header.get("msg_type")
            parent_id = parent.get("msg_id")

            if parent_id and parent_id != msg_id:
                continue

            if mt == "stream":
                name = (msg.get("content") or {}).get("name", "stdout")
                text = (msg.get("content") or {}).get("text", "")
                if name == "stderr":
                    stderr.append(text)
                else:
                    stdout.append(text)
            elif mt == "error":
                errors.append(msg.get("content") or {})
            elif mt == "execute_result":
                data = (msg.get("content") or {}).get("data", {})
                if "text/plain" in data:
                    stdout.append(str(data["text/plain"]))
            elif mt == "execute_reply" and (parent_id == msg_id or parent_id is None):
                execute_reply = msg.get("content") or {}
                break

        if execute_reply is None:
            return {
                "ok": False,
                "error": "Timed out waiting for execute_reply from kernel WebSocket",
                "stdout": "".join(stdout),
                "stderr": "".join(stderr),
                "errors": errors,
            }

        status = execute_reply.get("status")
        return {
            "ok": status == "ok",
            "status": status,
            "stdout": "".join(stdout),
            "stderr": "".join(stderr),
            "errors": errors,
            "execute_reply": execute_reply,
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": f"WebSocket error: {exc}",
            "stdout": "".join(stdout),
            "stderr": "".join(stderr),
            "errors": errors,
        }
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
