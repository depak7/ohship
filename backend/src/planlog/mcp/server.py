"""Planlog MCP server — stdio (API key) or Streamable HTTP (OAuth)."""

from __future__ import annotations

import asyncio
import os
from urllib.parse import urlparse

from pydantic import AnyHttpUrl

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from planlog.config import settings
from planlog.mcp.api_client import PlanlogAPIClient, PlanlogAPIError, format_result
from planlog.oauth.provider import MCP_SCOPE
from planlog.oauth.token_verifier import PlanlogTokenVerifier


def _client() -> PlanlogAPIClient:
    """Build API client from OAuth context (HTTP) or env (stdio)."""
    token = None
    try:
        access = get_access_token()
        if access and access.token:
            token = access.token
    except Exception:
        token = None

    return PlanlogAPIClient(
        base_url=settings.api_url,
        access_token=token,
        organization_id=os.environ.get("PLANLOG_ORG_ID") or None,
    )


def _error_message(e: Exception) -> str:
    if isinstance(e, PlanlogAPIError):
        return f"Error ({e.status_code}): {e.message}"
    return f"Error: {e}"


def mcp_transport_security() -> TransportSecuritySettings:
    """Allow the public API hostname. Default MCP protection only permits localhost."""
    api = urlparse(settings.api_url)
    host = api.hostname or "localhost"
    origin = f"{api.scheme or 'https'}://{host}"
    frontend = settings.frontend_url.rstrip("/")
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=[
            host,
            f"{host}:*",
            "127.0.0.1:*",
            "localhost:*",
            "[::1]:*",
        ],
        allowed_origins=[
            origin,
            f"{origin}:*",
            frontend,
            "http://127.0.0.1:*",
            "http://localhost:*",
            "http://[::1]:*",
        ],
    )


def create_mcp_server(*, enable_oauth: bool = False) -> MCPServer:
    """Create MCP server. enable_oauth=True for Streamable HTTP with OAuth RS mode."""
    kwargs: dict = {
        "name": "planlog",
        "instructions": (
            "Planlog — Plan → Approve → Done. "
            "Authenticate via OAuth (HTTP) or API key (stdio). "
            "Call list_orgs before create_plan/list_plans. "
            "Flow: draft → in_review → approved → in_progress → done; "
            "post_done ships from any pre-done status (auto self-approve). "
            "Use add_suggestion for review feedback only; use post_done for shipped work. "
            "request_notifyees queues teammates; they see Done under Sent to me."
        ),
    }
    if enable_oauth:
        kwargs["token_verifier"] = PlanlogTokenVerifier()
        kwargs["auth"] = AuthSettings(
            issuer_url=AnyHttpUrl(settings.api_url.rstrip("/") + "/"),
            resource_server_url=AnyHttpUrl(settings.api_url.rstrip("/") + "/mcp"),
            required_scopes=[MCP_SCOPE],
            client_registration_options=ClientRegistrationOptions(
                enabled=True,
                valid_scopes=[MCP_SCOPE],
                default_scopes=[MCP_SCOPE],
            ),
        )
        # AS routes are mounted on FastAPI separately; MCP is resource server only.

    mcp = MCPServer(**kwargs)
    _register_tools(mcp)
    return mcp


def _register_tools(mcp: MCPServer) -> None:
    @mcp.tool()
    def whoami() -> str:
        """Show the authenticated MCP identity (OAuth subject or API key user)."""
        try:
            access = get_access_token()
            if access:
                return format_result(
                    {
                        "client_id": access.client_id,
                        "subject": access.subject,
                        "scopes": access.scopes,
                        "claims": access.claims,
                    }
                )
        except Exception:
            pass
        return format_result({"auth": "stdio/env", "hint": "Using PLANLOG_API_KEY / PLANLOG_ACCESS_TOKEN"})

    @mcp.tool()
    def list_orgs() -> str:
        """List organizations for the authenticated user."""
        try:
            return format_result(_client().list_orgs())
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def create_plan(
        title: str,
        intent: str,
        acceptance_criteria: str,
        scope: str | None = None,
        team: str | None = None,
        project: str | None = None,
        organization_id: str | None = None,
    ) -> str:
        """Create a new Plan in draft status. project is required.

        Write acceptance_criteria as a markdown list, one criterion per line ("- ..."), because
        each line is reconciled individually when the plan ships. A single prose blob is treated
        as one criterion and loses that resolution.
        """
        try:
            return format_result(
                _client().create_plan(
                    title,
                    intent,
                    acceptance_criteria,
                    scope,
                    team,
                    project,
                    organization_id,
                )
            )
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def update_plan(
        plan_id: str,
        title: str | None = None,
        intent: str | None = None,
        scope: str | None = None,
        acceptance_criteria: str | None = None,
        team: str | None = None,
        project: str | None = None,
    ) -> str:
        """Update an editable Plan (draft or changes_requested)."""
        try:
            return format_result(
                _client().update_plan(
                    plan_id,
                    title=title,
                    intent=intent,
                    scope=scope,
                    acceptance_criteria=acceptance_criteria,
                    team=team,
                    project=project,
                )
            )
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def submit_for_review(plan_id: str, reviewer_ids: str | None = None) -> str:
        """Request review. Optionally assign teammates as comma-separated reviewer_ids. The owner can still approve."""
        try:
            ids = [part.strip() for part in reviewer_ids.split(",") if part.strip()] if reviewer_ids else None
            return format_result(_client().submit_for_review(plan_id, ids))
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def request_reviewers(plan_id: str, reviewer_ids: str) -> str:
        """Ask specific teammates to review. reviewer_ids is a comma-separated list of user UUIDs. Also returns agent_prompt to open in their coding agent."""
        try:
            ids = [part.strip() for part in reviewer_ids.split(",") if part.strip()]
            return format_result(_client().request_reviewers(plan_id, ids))
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def request_notifyees(plan_id: str, notify_ids: str) -> str:
        """Add teammates to notify on Done (any plan status). notify_ids is comma-separated user UUIDs. Already-done plans notify immediately."""
        try:
            ids = [part.strip() for part in notify_ids.split(",") if part.strip()]
            return format_result(_client().request_notifyees(plan_id, ids))
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def add_suggestion(plan_id: str, content: str) -> str:
        """Add a suggestion or comment to a Plan."""
        try:
            return format_result(_client().add_suggestion(plan_id, content))
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def approve_plan(plan_id: str) -> str:
        """Approve a Plan that is in review. Owner or any teammate can approve."""
        try:
            return format_result(_client().approve_plan(plan_id))
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def request_changes(plan_id: str, content: str | None = None) -> str:
        """Request changes on a Plan in review, optionally with a comment."""
        try:
            return format_result(_client().request_changes(plan_id, content))
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def claim_plan(plan_id: str) -> str:
        """Claim an approved Plan and move it to in_progress."""
        try:
            return format_result(_client().claim_plan(plan_id))
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def post_done(
        plan_id: str,
        summary: str,
        links_json: str = "[]",
        residual_notes: str | None = None,
        handoff_to: str | None = None,
        handoff_notes: str | None = None,
        reconciliation_json: str = "[]",
    ) -> str:
        """Post a Done summary from any pre-done status (auto self-approves and claims).

        links_json is a JSON array of {type, url, label}. handoff_to is comma-separated user UUIDs.
        handoff_notes is what the next person needs to know.

        reconciliation_json accounts for every acceptance criterion in the plan: a JSON array of
        {criterion, status, note} where criterion is the criterion text from get_plan, and status
        is "met", "changed" or "dropped". Give a note for anything not met — that is how plan
        drift becomes visible instead of being buried in the summary. Criteria you omit are
        recorded as unreported, not as met.
        """
        import json

        try:
            links = json.loads(links_json) if links_json else []
            outcomes = json.loads(reconciliation_json) if reconciliation_json else []
            ids = [part.strip() for part in handoff_to.split(",") if part.strip()] if handoff_to else None
            return format_result(
                _client().post_done(
                    plan_id, summary, links, residual_notes, ids, handoff_notes, outcomes
                )
            )
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def set_plan_share(plan_id: str, visibility: str, rotate: bool = False) -> str:
        """Set plan sharing: visibility is 'team' (org only) or 'anyone' (link without login). rotate=true issues a new link."""
        try:
            return format_result(_client().set_plan_share(plan_id, visibility, rotate))
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def get_plan(plan_id: str) -> str:
        """Get full Plan details including markdown, suggestions, and Done."""
        try:
            return format_result(_client().get_plan(plan_id))
        except Exception as e:
            return _error_message(e)

    @mcp.tool()
    def list_plans(
        status: str | None = None,
        owner_id: str | None = None,
        team: str | None = None,
        project: str | None = None,
        claimed_by: str | None = None,
        organization_id: str | None = None,
        reviewer_id: str | None = None,
        handoff_to: str | None = None,
    ) -> str:
        """List Plans with optional filters. Pass reviewer_id to see plans requested of that user. Pass handoff_to=me (via filter value) for done handoffs."""
        try:
            return format_result(
                _client().list_plans(
                    status, owner_id, team, project, claimed_by, organization_id, reviewer_id, handoff_to
                )
            )
        except Exception as e:
            return _error_message(e)


# Default stdio instance (API key / env auth)
mcp = create_mcp_server(enable_oauth=False)


def main() -> None:
    """stdio entrypoint for local Cursor config with API keys."""
    asyncio.run(mcp.run_stdio_async())


if __name__ == "__main__":
    main()
