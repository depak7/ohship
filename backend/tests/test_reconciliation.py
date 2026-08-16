"""Acceptance-criteria reconciliation.

Drift hides in silence, so most of these assert on what happens when the agent *doesn't*
say something rather than when it does.
"""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from planlog.auth import hash_api_key
from planlog.models import Organization, OrgMembership, OrgRole, Plan, PlanStatus, User
from planlog.services.done import post_done
from planlog.services.helpers import build_reconciliation, parse_criteria


@pytest.fixture
def owner(session: Session) -> User:
    user = User(name="Owner", email="owner@test.com", api_key_hash=hash_api_key("k"))
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture
def plan(session: Session, owner: User) -> Plan:
    org = Organization(name="Acme", slug="acme", created_by_id=owner.id)
    session.add(org)
    session.commit()
    session.refresh(org)
    session.add(OrgMembership(organization_id=org.id, user_id=owner.id, role=OrgRole.owner))
    plan = Plan(
        organization_id=org.id,
        title="Ship it",
        intent="why",
        acceptance_criteria="- tax correct\n- tests pass",
        owner_id=owner.id,
        project="checkout",
    )
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


# --------------------------------------------------------------------------- parser


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("- [ ] EU VAT correct\n- [x] tests pass", ["EU VAT correct", "tests pass"]),
        ("- one\n- two", ["one", "two"]),
        ("* alpha\n+ beta", ["alpha", "beta"]),
        ("1. first\n2) second", ["first", "second"]),
        ("Intro prose\n- real one\n- real two", ["real one", "real two"]),
        # No list markers at all: one criterion, not zero. An unparseable plan should still
        # be reconcilable rather than silently having nothing to check.
        ("Everything works end to end.", ["Everything works end to end."]),
        ("", []),
        ("   \n  ", []),
    ],
)
def test_parse_criteria(raw, expected):
    assert parse_criteria(raw) == expected


# --------------------------------------------------------------------------- reconcile


def test_unreported_criteria_are_named_not_omitted():
    """The failure mode this feature exists for: an agent quietly not mentioning something."""
    out = build_reconciliation("- a\n- b\n- c", [{"criterion": "a", "status": "met"}])
    assert [o["status"] for o in out] == ["met", "unreported", "unreported"]
    assert len(out) == 3


def test_reporting_nothing_still_covers_every_criterion():
    out = build_reconciliation("- a\n- b", None)
    assert [o["criterion"] for o in out] == ["a", "b"]
    assert all(o["status"] == "unreported" for o in out)


def test_matching_ignores_case_and_whitespace():
    out = build_reconciliation("-  EU VAT correct ", [{"criterion": "eu vat correct", "status": "met"}])
    assert out[0]["status"] == "met"
    assert out[0]["criterion"] == "EU VAT correct"  # the plan's wording wins


def test_invented_criteria_cannot_manufacture_a_pass():
    out = build_reconciliation("- real", [{"criterion": "made up", "status": "met"}])
    statuses = {o["criterion"]: o["status"] for o in out}
    assert statuses["real"] == "unreported"
    assert statuses["made up"] == "extra"


def test_unknown_status_falls_back_to_unreported():
    out = build_reconciliation("- a", [{"criterion": "a", "status": "definitely-shipped"}])
    assert out[0]["status"] == "unreported"


def test_notes_are_kept_for_drift():
    out = build_reconciliation(
        "- a", [{"criterion": "a", "status": "changed", "note": "API forced a different shape"}]
    )
    assert out[0]["note"] == "API forced a different shape"


# --------------------------------------------------------------------------- service


def test_post_done_records_outcomes(session: Session, plan: Plan, owner: User):
    plan.acceptance_criteria = "- tax correct\n- tests pass\n- docs updated"
    session.add(plan)
    session.commit()

    done = post_done(
        session, plan, owner, "Shipped", [], None, None, None,
        [
            {"criterion": "tax correct", "status": "met"},
            {"criterion": "tests pass", "status": "changed", "note": "covered by integration"},
        ],
    )
    by_text = {o["criterion"]: o for o in done.reconciliation}
    assert by_text["tax correct"]["status"] == "met"
    assert by_text["tests pass"]["status"] == "changed"
    assert by_text["docs updated"]["status"] == "unreported"


def test_post_done_without_reconciliation_still_lists_criteria(
    session: Session, plan: Plan, owner: User
):
    """'Optional but flagged': accepted, but never displayed as passing."""
    done = post_done(session, plan, owner, "Shipped", [])
    assert done.reconciliation
    assert all(o["status"] == "unreported" for o in done.reconciliation)
    assert plan.status == PlanStatus.done


# --------------------------------------------------------------------------- API


def _auth(client: TestClient) -> dict:
    token = client.post(
        "/api/v1/auth/signup",
        json={"name": "Ana", "email": "ana@test.com", "password": "password123"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_reconciliation_round_trips_through_the_api(client: TestClient):
    auth = _auth(client)
    org = client.post("/api/v1/orgs", json={"name": "Acme"}, headers=auth).json()
    plan = client.post(
        "/api/v1/plans",
        json={
            "organization_id": org["id"],
            "title": "Idempotent webhooks",
            "intent": "why",
            "acceptance_criteria": "- replay is a no-op\n- returns 200 not 409\n- sweep runs daily",
            "project": "payments",
        },
        headers=auth,
    ).json()

    body = client.post(
        f"/api/v1/plans/{plan['id']}/done",
        json={
            "summary": "shipped",
            "links": [],
            "reconciliation": [
                {"criterion": "replay is a no-op", "status": "met"},
                {"criterion": "returns 200 not 409", "status": "changed", "note": "409 on malformed"},
                {"criterion": "sweep runs daily", "status": "dropped", "note": "moved to a cron"},
            ],
        },
        headers=auth,
    ).json()

    outcomes = {o["criterion"]: o for o in body["done"]["reconciliation"]}
    assert outcomes["replay is a no-op"]["status"] == "met"
    assert outcomes["returns 200 not 409"]["status"] == "changed"
    assert outcomes["sweep runs daily"]["note"] == "moved to a cron"


# --------------------------------------------------------------------------- MCP layer


def test_api_client_post_done_sends_handoff_notes_and_reconciliation(monkeypatch):
    """There was no MCP-layer test at all, which is why a missing handoff_notes param
    survived while agent_ship_prompt was actively telling agents to send it."""
    from planlog.mcp.api_client import PlanlogAPIClient

    sent: dict = {}

    def fake_request(self, method, path, **kwargs):
        sent.update({"method": method, "path": path, **kwargs})
        return {"ok": True}

    monkeypatch.setattr(PlanlogAPIClient, "_request", fake_request)
    client = PlanlogAPIClient(base_url="http://x", access_token="t", organization_id="o")
    client.post_done(
        "plan-1",
        "summary",
        [],
        "residual",
        ["user-1"],
        "handoff notes",
        [{"criterion": "a", "status": "met"}],
    )

    body = sent["json"]
    assert body["handoff_notes"] == "handoff notes"
    assert body["reconciliation"] == [{"criterion": "a", "status": "met"}]


def test_ship_prompt_only_names_params_the_tool_accepts():
    """The prompt tells agents which params to pass; if it names one that doesn't exist,
    every agent following it fails."""
    import inspect

    from planlog.mcp.api_client import PlanlogAPIClient
    from planlog.services.helpers import agent_ship_prompt

    class _P:
        id = "abc"
        title = "t"
        status = PlanStatus.approved

    prompt = agent_ship_prompt(_P())
    accepted = set(inspect.signature(PlanlogAPIClient.post_done).parameters)
    for name in ("handoff_notes", "summary", "plan_id"):
        if f"{name}=" in prompt:
            assert name in accepted, f"ship prompt tells agents to send {name!r}, which post_done rejects"
