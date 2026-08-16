"""Launch-funnel analytics via Umami.

Disabled unless ``UMAMI_WEBSITE_ID`` is set, so local dev, the test suite and self-hosters
make no network calls at all.

Three things about this module are load-bearing and easy to break:

1. **Umami silently drops any request without a ``User-Agent``** and still answers 200. That
   makes a missing header the one failure mode where everything looks fine and nothing is
   recorded, so the header is built in exactly one place and the shared client sets a default
   too. ``test_analytics.py`` fails if it ever goes missing.

2. **Umami identity is ``hash(IP + User-Agent + website + daily salt)``** — it uses no
   cookies. So an event sent without forwarding the caller's IP and UA is attributed to the
   dyno, inventing a phantom visitor. ``track(request=...)`` forwards both.

3. **The web dyno runs a single uvicorn worker** (see ``backend/Procfile``), so any blocking
   call on a request path costs the whole app throughput, MCP included. ``track()`` only ever
   hands work to a queue drained by one background consumer.

Events queued but not yet sent are lost when the dyno restarts. These are growth counters,
not billing records, so that is deliberately not engineered around.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
from fastapi import Request

from planlog.config import settings

logger = logging.getLogger(__name__)

SERVER_UA = "Planlog/0.1.0 (+https://planlog.depak.dev)"
_MAX_QUEUE = 512
_SEND_TIMEOUT = 5.0
_DRAIN_ON_SHUTDOWN = 2.0

_queue: asyncio.Queue[dict[str, Any]] | None = None
_loop: asyncio.AbstractEventLoop | None = None
_dropped = 0
_logged_first_send = False


# --------------------------------------------------------------------------- taxonomy

# The allowlist *is* the documentation, and it is the only place a reviewer has to read to
# audit what leaves the building. Adding a property necessarily shows up in this diff.
# Values must be enums, bools or buckets — never user input.
EVENTS: dict[str, frozenset[str]] = {
    "install-fetched": frozenset(),
    "signup": frozenset({"method"}),
    "login": frozenset({"method"}),
    "org-created": frozenset(),
    "mcp-client-registered": frozenset({"agent"}),
    "mcp-agent-connected": frozenset({"agent"}),
    "plan-created": frozenset({"source", "has_project"}),
    "plan-approved": frozenset({"source"}),
    "done-posted": frozenset({"source", "links", "has_handoff", "reconciled", "drifted"}),
}

# Attached to every event from the captured User-Agent; not declared per-event above.
_IMPLICIT_PROPS = ("client", "ua_family")

_AGENTS = ("claude", "cursor", "opencode", "windsurf", "vscode", "copilot", "gemini", "cline", "zed")


def normalize_agent(client_name: str | None) -> str:
    """Bounded enum for the MCP client name — the raw value is unbounded cardinality."""
    name = (client_name or "").lower()
    return next((agent for agent in _AGENTS if agent in name), "other")


# --------------------------------------------------------------------------- UA parsing

_BOT_HINTS = ("bot", "crawl", "spider", "slurp", "preview", "monitor", "uptime", "headless")
_CLI_PREFIXES = {
    "curl": "curl",
    "wget": "wget",
    "httpie": "cli",
    "python-requests": "cli",
    "python-httpx": "cli",
    "go-http-client": "cli",
    "powershell": "cli",
    "planlog-mcp": "mcp",
}


def client_kind(ua: str | None) -> str:
    """Classify a User-Agent. Tag, never drop — dropping loses the denominator."""
    value = (ua or "").strip().lower()
    if not value:
        return "unknown"
    for prefix, kind in _CLI_PREFIXES.items():
        if value.startswith(prefix):
            return kind
    # Must precede the mozilla check: bots spoof it, e.g. "Googlebot/2.1 (Mozilla/5.0 ...)".
    if any(hint in value for hint in _BOT_HINTS):
        return "bot"
    if value.startswith("mozilla/"):
        return "browser"
    return "other"


def ua_family(ua: str | None) -> str:
    """First token of the UA, bounded. Lets an unknown client be identified without a deploy."""
    value = (ua or "").strip().lower()
    if not value:
        return "unknown"
    return value.split("/")[0].split(" ")[0][:24] or "unknown"


# --------------------------------------------------------------------------- sanitising


def _clean_value(value: Any) -> str | None:
    """Enums, bools and buckets only. Anything that smells like user input is dropped."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or len(text) > 32 or "@" in text:
        return None
    return text


def _clean_props(event: str, props: dict[str, Any]) -> dict[str, str]:
    allowed = EVENTS[event]
    cleaned: dict[str, str] = {}
    for key, raw in props.items():
        if key not in allowed:
            logger.warning("analytics: dropping undeclared prop %r on %r", key, event)
            continue
        value = _clean_value(raw)
        if value is None:
            logger.warning("analytics: dropping unusable value for %r on %r", key, event)
            continue
        cleaned[key] = value
    return cleaned


def _from_request(request: Request) -> dict[str, str]:
    # Heroku puts the real client first and appends its own hop, so first-wins is correct here.
    forwarded = request.headers.get("x-forwarded-for", "")
    ip = forwarded.split(",")[0].strip()
    if not ip and request.client:
        ip = request.client.host
    return {
        "ua": request.headers.get("user-agent", ""),
        "ip": ip,
        "hostname": request.url.hostname or "",
        # .path, never .url — query strings here carry ?code=, ?token= and ?state=.
        "path": request.url.path,
    }


# --------------------------------------------------------------------------- public API


def enabled() -> bool:
    return bool(settings.umami_website_id)


def track(event: str, *, request: Request | None = None, **props: Any) -> None:
    """Record a funnel event. Sync, non-blocking, and never raises."""
    try:
        if not enabled() or _queue is None or _loop is None:
            return
        if event not in EVENTS:
            logger.warning("analytics: unknown event %r", event)
            return

        context = _from_request(request) if request is not None else {}
        ua = context.get("ua", "")
        data = _clean_props(event, props)
        data["client"] = client_kind(ua)
        data["ua_family"] = ua_family(ua)

        _loop.call_soon_threadsafe(
            _offer,
            {
                "name": event,
                "data": data,
                "ua": ua,
                "ip": context.get("ip", ""),
                "hostname": context.get("hostname", ""),
                "path": context.get("path", "/"),
            },
        )
    except Exception:  # analytics must never break a request
        logger.debug("analytics: track failed", exc_info=True)


def _offer(event: dict[str, Any]) -> None:
    """Runs on the event loop. Drops rather than blocking when the queue is full."""
    global _dropped
    if _queue is None:
        return
    try:
        _queue.put_nowait(event)
    except asyncio.QueueFull:
        _dropped += 1
        if _dropped % 100 == 1:
            logger.warning("analytics: queue full, dropped %d events", _dropped)


# --------------------------------------------------------------------------- transport


def _build_headers(event: dict[str, Any]) -> dict[str, str]:
    """The only place outbound headers are built. A missing UA means Umami records nothing."""
    ua = (event.get("ua") or "").strip() or SERVER_UA
    headers = {"User-Agent": ua, "Content-Type": "application/json"}
    ip = (event.get("ip") or "").strip()
    if ip:
        headers["X-Forwarded-For"] = ip
    return headers


def _build_payload(event: dict[str, Any]) -> dict[str, Any]:
    hostname = event.get("hostname") or "planlog.depak.dev"
    return {
        "type": "event",
        "payload": {
            "website": settings.umami_website_id,
            "name": event["name"],
            "hostname": hostname,
            "url": event.get("path") or "/",
            "data": event.get("data") or {},
        },
    }


async def _post(client: httpx.AsyncClient, event: dict[str, Any]) -> None:
    global _logged_first_send
    response = await client.post(
        "/api/send", json=_build_payload(event), headers=_build_headers(event)
    )
    if response.status_code >= 400:
        logger.warning("analytics: umami rejected %s with %s", event["name"], response.status_code)
    elif not _logged_first_send:
        _logged_first_send = True
        logger.info("analytics: umami accepted event=%s status=%s", event["name"], response.status_code)


async def _consume(client: httpx.AsyncClient) -> None:
    assert _queue is not None
    while True:
        event = await _queue.get()
        try:
            await _post(client, event)
        except Exception:
            # No retries: on a single consumer a retry loop turns "Umami is down" into
            # "the queue fills and analytics stops entirely". Dropping is the right failure.
            logger.debug("analytics: send failed", exc_info=True)
        finally:
            _queue.task_done()


@asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Owns the queue, the consumer task and one long-lived HTTP client."""
    global _queue, _loop
    if not enabled():
        logger.info("analytics: disabled (UMAMI_WEBSITE_ID unset)")
        yield
        return

    _loop = asyncio.get_running_loop()
    _queue = asyncio.Queue(maxsize=_MAX_QUEUE)
    async with httpx.AsyncClient(
        base_url=settings.umami_host.rstrip("/"),
        timeout=httpx.Timeout(_SEND_TIMEOUT),
        limits=httpx.Limits(max_connections=4),
        # Belt and braces: even if _build_headers is ever bypassed, httpx would otherwise
        # send "python-httpx/x.y" and merge every visitor into one.
        headers={"User-Agent": SERVER_UA},
    ) as client:
        task = asyncio.create_task(_consume(client))
        try:
            yield
        finally:
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(_queue.join(), timeout=_DRAIN_ON_SHUTDOWN)
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            _queue = None
            _loop = None
