"""Unit tests for the Umami analytics module. Nothing here touches the network."""

import asyncio

import httpx
import pytest
from fastapi import Request

from planlog import analytics

# Captured before the autouse guard in conftest replaces _post with a raiser. These two tests
# deliberately drive the real transport through httpx.MockTransport.
_REAL_POST = analytics._post


def _request(headers: dict[str, str] | None = None, path: str = "/install") -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "query_string": b"code=secret123",
            "headers": raw,
            "client": ("10.0.0.9", 1234),
            "server": ("planlog.depak.dev", 443),
            "scheme": "https",
        }
    )


# --------------------------------------------------------------------------- User-Agent


@pytest.mark.parametrize("ua", [None, "", "   ", "curl/8.4.0"])
def test_build_headers_always_has_user_agent(ua):
    """Umami silently drops requests with no UA and still returns 200."""
    headers = analytics._build_headers({"ua": ua})
    assert headers.get("User-Agent", "").strip()


@pytest.mark.anyio
async def test_outbound_request_never_uses_the_httpx_default_ua():
    """A dropped explicit header falls back to python-httpx/x.y, which merges every
    visitor into one. This is the assertion that actually catches that regression."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="ok")

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://cloud.umami.is",
        headers={"User-Agent": analytics.SERVER_UA},
    ) as client:
        await _REAL_POST(client, {"name": "install-fetched", "data": {}, "path": "/install"})

    ua = seen[0].headers["user-agent"]
    assert ua and "httpx" not in ua.lower()


# --------------------------------------------------------------------------- payload


@pytest.mark.anyio
async def test_payload_shape_and_client_ip(monkeypatch):
    monkeypatch.setattr(analytics.settings, "umami_website_id", "site-123")
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, text="ok")

    event = {
        "name": "signup",
        "data": {"method": "email", "client": "browser"},
        "ua": "Mozilla/5.0",
        "ip": "1.2.3.4",
        "hostname": "planlog.depak.dev",
        "path": "/api/v1/auth/signup",
    }
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://cloud.umami.is"
    ) as client:
        await _REAL_POST(client, event)

    body = seen[0].read().decode()
    assert '"type": "event"' in body or '"type":"event"' in body
    payload = seen[0].headers
    assert payload["user-agent"] == "Mozilla/5.0"
    # Heroku puts the real client first; that is the one Umami must hash on.
    assert payload["x-forwarded-for"] == "1.2.3.4"

    built = analytics._build_payload(event)["payload"]
    assert built["website"] == "site-123"
    assert built["name"] == "signup"
    assert built["hostname"] == "planlog.depak.dev"
    assert built["url"] == "/api/v1/auth/signup"


def test_forwarded_for_takes_the_first_hop():
    req = _request({"x-forwarded-for": "1.2.3.4, 10.0.0.1", "user-agent": "curl/8.4.0"})
    assert analytics._from_request(req)["ip"] == "1.2.3.4"


def test_query_string_never_leaks_into_the_url():
    """?code= and ?token= live in these query strings."""
    req = _request({"user-agent": "curl/8.4.0"})
    assert analytics._from_request(req)["path"] == "/install"
    assert "secret123" not in analytics._from_request(req)["path"]


# --------------------------------------------------------------------------- safety


def test_disabled_is_a_noop(monkeypatch):
    monkeypatch.setattr(analytics.settings, "umami_website_id", "")
    monkeypatch.setattr(analytics, "_queue", None)
    analytics.track("signup", method="email")  # must not raise


def test_track_never_raises_without_a_loop(monkeypatch):
    monkeypatch.setattr(analytics.settings, "umami_website_id", "site-123")
    monkeypatch.setattr(analytics, "_loop", None)
    analytics.track("signup", method="email")


def test_unknown_event_is_dropped(captured_events):
    analytics.track("not-a-real-event", method="email")
    assert captured_events == []


def test_undeclared_props_are_dropped(captured_events):
    analytics.track("signup", method="email", sneaky="value")
    assert captured_events[0]["data"]["method"] == "email"
    assert "sneaky" not in captured_events[0]["data"]


def test_no_pii_reaches_the_payload(captured_events):
    analytics.track("signup", method="alice@example.com")
    assert "method" not in captured_events[0]["data"]

    captured_events.clear()
    analytics.track("plan-created", source="x" * 200)
    assert "source" not in captured_events[0]["data"]


def test_queue_full_drops_without_raising(monkeypatch):
    monkeypatch.setattr(analytics.settings, "umami_website_id", "site-123")
    full = asyncio.Queue(maxsize=1)
    full.put_nowait({"name": "filler"})
    monkeypatch.setattr(analytics, "_queue", full)
    before = analytics._dropped
    analytics._offer({"name": "signup"})
    assert analytics._dropped == before + 1


# --------------------------------------------------------------------------- UA parsing


@pytest.mark.parametrize(
    "ua,expected",
    [
        ("curl/8.4.0", "curl"),
        ("Wget/1.21.4", "wget"),
        ("python-requests/2.31", "cli"),
        ("planlog-mcp/0.1.0", "mcp"),
        ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "browser"),
        # Bots spoof Mozilla, so the bot check has to win.
        ("Googlebot/2.1 (Mozilla/5.0; +http://www.google.com/bot.html)", "bot"),
        ("Mozilla/5.0 (compatible; bingbot/2.0)", "bot"),
        ("Slackbot-LinkExpanding 1.0", "bot"),
        ("Better Uptime Bot", "bot"),
        ("", "unknown"),
        (None, "unknown"),
        ("SomeRandomThing/9", "other"),
    ],
)
def test_client_kind(ua, expected):
    assert analytics.client_kind(ua) == expected


def test_ua_family_is_bounded():
    assert analytics.ua_family("curl/8.4.0") == "curl"
    assert analytics.ua_family("Go-http-client/2.0") == "go-http-client"
    assert len(analytics.ua_family("x" * 100)) <= 24


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Claude Code", "claude"),
        ("Cursor", "cursor"),
        ("opencode", "opencode"),
        ("Some Unknown Client", "other"),
        (None, "other"),
    ],
)
def test_normalize_agent(name, expected):
    assert analytics.normalize_agent(name) == expected
