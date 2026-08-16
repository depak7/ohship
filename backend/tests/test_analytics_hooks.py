"""Every funnel hook fires with the right name and props.

These exist so a refactor that silently deletes a `track()` call fails a test rather than
quietly ending the launch metrics.
"""

from fastapi.testclient import TestClient


def _names(events: list[dict]) -> list[str]:
    return [e["name"] for e in events]


def _find(events: list[dict], name: str) -> dict:
    match = [e for e in events if e["name"] == name]
    assert match, f"{name} not tracked; got {_names(events)}"
    return match[0]


def test_install_fetch_is_tracked_and_classified(client: TestClient, captured_events):
    res = client.get("/install", headers={"User-Agent": "curl/8.4.0"})
    assert res.status_code == 200
    assert _find(captured_events, "install-fetched")["data"]["client"] == "curl"


def test_install_by_a_crawler_is_tagged_not_dropped(client: TestClient, captured_events):
    """We keep bots so the denominator stays honest — they're filtered in Umami."""
    client.get("/install", headers={"User-Agent": "Googlebot/2.1 (Mozilla/5.0)"})
    event = _find(captured_events, "install-fetched")
    assert event["data"]["client"] == "bot"
    assert event["data"]["ua_family"] == "googlebot"


def test_signup_and_login_are_tracked(client: TestClient, captured_events):
    res = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ana", "email": "ana@test.com", "password": "password123"},
    )
    assert res.status_code == 201
    assert _find(captured_events, "signup")["data"]["method"] == "email"

    captured_events.clear()
    res = client.post(
        "/api/v1/auth/login", json={"email": "ana@test.com", "password": "password123"}
    )
    assert res.status_code == 200
    assert _find(captured_events, "login")["data"]["method"] == "email"


def test_failed_login_is_not_tracked_as_a_login(client: TestClient, captured_events):
    client.post(
        "/api/v1/auth/signup",
        json={"name": "Ana", "email": "ana@test.com", "password": "password123"},
    )
    captured_events.clear()
    res = client.post("/api/v1/auth/login", json={"email": "ana@test.com", "password": "wrong"})
    assert res.status_code == 401
    assert "login" not in _names(captured_events)


def test_no_email_ever_reaches_a_payload(client: TestClient, captured_events):
    client.post(
        "/api/v1/auth/signup",
        json={"name": "Ana", "email": "ana@test.com", "password": "password123"},
    )
    blob = repr(captured_events)
    assert "ana@test.com" not in blob
    assert "password123" not in blob


def test_org_and_plan_funnel_is_tracked(client: TestClient, captured_events):
    token = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ana", "email": "ana@test.com", "password": "password123"},
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}"}

    captured_events.clear()
    org = client.post("/api/v1/orgs", json={"name": "Acme"}, headers=auth).json()
    assert _find(captured_events, "org-created")

    captured_events.clear()
    plan = client.post(
        "/api/v1/plans",
        json={
            "organization_id": org["id"],
            "title": "Ship the thing",
            "intent": "why",
            "acceptance_criteria": "how",
            "project": "checkout",
        },
        headers=auth,
    ).json()
    created = _find(captured_events, "plan-created")
    assert created["data"]["has_project"] == "true"
    assert created["data"]["source"] == "web"
    assert "Ship the thing" not in repr(captured_events)  # no titles

    captured_events.clear()
    client.post(
        f"/api/v1/plans/{plan['id']}/done",
        json={"summary": "shipped", "links": [], "handoff_notes": "next up"},
        headers=auth,
    )
    done = _find(captured_events, "done-posted")
    assert done["data"]["links"] == "0"
    assert done["data"]["has_handoff"] == "true"


def test_mcp_user_agent_marks_the_source_as_mcp(client: TestClient, captured_events):
    """MCP tools call these same routes; only the UA distinguishes them."""
    token = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ana", "email": "ana@test.com", "password": "password123"},
    ).json()["access_token"]
    auth = {"Authorization": f"Bearer {token}", "User-Agent": "planlog-mcp/0.1.0"}
    org = client.post("/api/v1/orgs", json={"name": "Acme"}, headers=auth).json()

    captured_events.clear()
    client.post(
        "/api/v1/plans",
        json={
            "organization_id": org["id"],
            "title": "Agent plan",
            "intent": "why",
            "acceptance_criteria": "how",
            "project": "checkout",
        },
        headers=auth,
    )
    created = _find(captured_events, "plan-created")
    assert created["data"]["source"] == "mcp"
    assert created["data"]["client"] == "mcp"


def test_slow_umami_never_delays_a_response(client: TestClient, captured_events, monkeypatch):
    """The web dyno runs one uvicorn worker, so a blocking send would cost the whole app
    throughput. track() must only ever hand work to the queue."""
    import time

    class _SlowQueue:
        def put_nowait(self, event):
            time.sleep(0)  # queueing is the only thing on the request path
            captured_events.append(event)

    monkeypatch.setattr(__import__("planlog").analytics, "_queue", _SlowQueue())

    start = time.perf_counter()
    for _ in range(50):
        client.get("/install", headers={"User-Agent": "curl/8.4.0"})
    elapsed = time.perf_counter() - start

    assert len(captured_events) == 50
    assert elapsed < 2.0, f"50 install fetches took {elapsed:.2f}s"
