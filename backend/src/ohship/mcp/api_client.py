import json
import os
from typing import Any

import httpx


class OhShipAPIError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        self.message = message
        self.status_code = status_code
        super().__init__(message)


class OhShipAPIClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        access_token: str | None = None,
        organization_id: str | None = None,
    ):
        self.base_url = (base_url or os.environ.get("OHSHIP_API_URL", "http://localhost:8000")).rstrip("/")
        self.access_token = (
            access_token
            or os.environ.get("OHSHIP_ACCESS_TOKEN")
            or api_key
            or os.environ.get("OHSHIP_API_KEY", "")
        )
        self.organization_id = organization_id or os.environ.get("OHSHIP_ORG_ID", "")
        if not self.access_token:
            raise OhShipAPIError(
                "Authentication required. Use MCP OAuth login, or set OHSHIP_ACCESS_TOKEN / OHSHIP_API_KEY."
            )

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    def _org_id(self, organization_id: str | None = None) -> str:
        org_id = organization_id or self.organization_id
        if not org_id:
            raise OhShipAPIError(
                "organization_id is required (pass it, or set OHSHIP_ORG_ID, or call list_orgs first)."
            )
        return org_id

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=30.0) as client:
            response = client.request(method, url, headers=self._headers(), **kwargs)
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("detail", detail)
            except Exception:
                pass
            raise OhShipAPIError(str(detail), response.status_code)
        if response.status_code == 204:
            return None
        return response.json()

    def list_orgs(self) -> list[dict[str, Any]]:
        return self._request("GET", "/api/v1/orgs")

    def create_plan(
        self,
        title: str,
        intent: str,
        acceptance_criteria: str,
        scope: str | None = None,
        team: str | None = None,
        project: str | None = None,
        organization_id: str | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/v1/plans",
            json={
                "title": title,
                "intent": intent,
                "acceptance_criteria": acceptance_criteria,
                "scope": scope,
                "team": team,
                "project": project,
                "organization_id": self._org_id(organization_id),
            },
        )

    def update_plan(self, plan_id: str, **fields: Any) -> dict[str, Any]:
        payload = {k: v for k, v in fields.items() if v is not None}
        return self._request("PATCH", f"/api/v1/plans/{plan_id}", json=payload)

    def submit_for_review(self, plan_id: str, reviewer_ids: list[str] | None = None) -> dict[str, Any]:
        payload = {"reviewer_ids": reviewer_ids or []}
        return self._request("POST", f"/api/v1/plans/{plan_id}/submit", json=payload)

    def request_reviewers(self, plan_id: str, reviewer_ids: list[str]) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/plans/{plan_id}/reviewers",
            json={"reviewer_ids": reviewer_ids},
        )

    def add_suggestion(self, plan_id: str, content: str) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/plans/{plan_id}/suggestions",
            json={"content": content},
        )

    def approve_plan(self, plan_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/plans/{plan_id}/approve")

    def request_changes(self, plan_id: str, content: str | None = None) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/plans/{plan_id}/request-changes",
            json={"content": content} if content else {},
        )

    def claim_plan(self, plan_id: str) -> dict[str, Any]:
        return self._request("POST", f"/api/v1/plans/{plan_id}/claim")

    def post_done(
        self,
        plan_id: str,
        summary: str,
        links: list[dict[str, str]] | None = None,
        residual_notes: str | None = None,
        handoff_to: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/plans/{plan_id}/done",
            json={
                "summary": summary,
                "links": links or [],
                "residual_notes": residual_notes,
                "handoff_to": handoff_to or [],
            },
        )

    def set_plan_share(
        self,
        plan_id: str,
        visibility: str,
        rotate: bool = False,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/v1/plans/{plan_id}/share",
            json={"visibility": visibility, "rotate": rotate},
        )

    def get_plan(self, plan_id: str) -> dict[str, Any]:
        return self._request("GET", f"/api/v1/plans/{plan_id}")

    def list_plans(
        self,
        status: str | None = None,
        owner_id: str | None = None,
        team: str | None = None,
        project: str | None = None,
        claimed_by: str | None = None,
        organization_id: str | None = None,
        reviewer_id: str | None = None,
        handoff_to: str | None = None,
    ) -> dict[str, Any]:
        params: dict[str, str] = {"organization_id": self._org_id(organization_id)}
        if status:
            params["status"] = status
        if owner_id:
            params["owner_id"] = owner_id
        if team:
            params["team"] = team
        if project:
            params["project"] = project
        if claimed_by:
            params["claimed_by"] = claimed_by
        if reviewer_id:
            params["reviewer_id"] = reviewer_id
        if handoff_to:
            params["handoff_to"] = handoff_to
        return self._request("GET", "/api/v1/plans", params=params)


def format_result(data: Any) -> str:
    return json.dumps(data, indent=2, default=str)
