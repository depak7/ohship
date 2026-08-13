"""One-off: delete legacy AX plans and recreate with proper Done records."""

from uuid import UUID

from sqlmodel import Session, create_engine, select

from ohship.config import settings
from ohship.models import Plan, PlanStatus, User, utcnow
from ohship.services.done import post_done
from ohship.services.plans import delete_plan

ORG_ID = UUID("aabb51b7-9f76-4e5e-802d-40fe5d1e0d3f")
OLD_PLAN_IDS = [
    UUID("7f2a725d-cacc-4601-a4f5-46b41a48f14a"),
    UUID("ed3cc394-866d-4a38-bb97-51601f4accd8"),
]

SHIPLOG_SCOPE = """## History

### 2026-08-13 — Shareable links + Done handoff
- Team vs Anyone share links (`visibility`, `share_token`, migration 004)
- Public `/share/{token}` page (Done-first, no login)
- Share sidebar on plan detail
- Done handoff: assign teammates, **Sent to me** filter, auto-copy Anyone link
- MCP: `set_plan_share`, `post_done(..., handoff_to)`

### 2026-08-13 — Reviewers + direct ship
- GitHub-style Reviewers sidebar; request review from teammates
- **Mark as Done** from any pre-done status (auto self-approve + claim)
- Open in coding agent prompt

### 2026-08-13 — Cursor + MCP wiring
- Local stack: Postgres 5433, API 8000, frontend 3000
- Cursor IDE config; MCP OAuth HTTP endpoint

### 2026-08-12 — OhShip Phase 1
- Plan → Approve → Done state machine, FastAPI, Next.js UI, MCP tools
- Auth, orgs, invites; Donelog → OhShip rename

## Todo

- [ ] Fix MCP OAuth 401 on `POST /mcp` after token issue (if still flaky)
- [ ] Optional: Google OAuth env for production login
- [ ] Optional Phase 2: CLI, deploy story, richer Done search
"""

SHARE_DONE_SUMMARY = """## What shipped

Google Docs-style **Team vs Anyone** sharing and **Done handoff** for teammates + link copy.

### Share links
- `Plan.visibility` + `share_token` (Alembic 004)
- `POST /api/v1/plans/{id}/share` — visibility + rotate
- `GET /api/v1/public/plans/{token}` — no auth, PublicPlan DTO
- Share sidebar: Team / Anyone, copy link, reset link
- Public page `/share/[token]` — Done-first when shipped

### Done handoff
- `done_handoffs` table
- `post_done(..., handoff_to)` + **Sent to me** list filter
- Post Done form: teammate checkboxes + auto Anyone link copy

### MCP & tests
- `set_plan_share`, `post_done(..., handoff_to)`
- Integration tests: public 200/404, handoff filter, auth on private routes
"""

REVIEWERS_DONE_SUMMARY = """## What shipped

Review workflow improvements for team plans.

- **Reviewers sidebar** on plan detail (GitHub-style Add reviewer dropdown)
- Request review from org teammates without auto-submitting
- **Open in coding agent** — copies MCP prompt for reviewers
- **Requested of me** filter on plans list
- Owner can self-approve; optional review path remains available
"""


def main() -> None:
    engine = create_engine(settings.database_url)
    with Session(engine) as session:
        owner = session.exec(
            select(User).where(User.email == "mcp.agent@example.com")
        ).first()
        if not owner:
            owner = session.exec(select(User).order_by(User.created_at)).first()  # type: ignore[attr-defined]
        if not owner:
            raise SystemExit("No user found")

        for plan_id in OLD_PLAN_IDS:
            plan = session.get(Plan, plan_id)
            if plan:
                delete_plan(session, plan)
                print(f"Deleted plan {plan_id}")

        shiplog = Plan(
            organization_id=ORG_ID,
            title="Shiplog",
            intent=(
                "Living ship log for OhShip: permanent History of what shipped "
                "and a Todo list of what remains."
            ),
            scope=SHIPLOG_SCOPE,
            acceptance_criteria=(
                "- History reflects shipped work, newest first\n"
                "- Todo lists only open work\n"
                "- Shipped slices have Done records on their own plans"
            ),
            owner_id=owner.id,
            team="AX",
            project="ohship",
            status=PlanStatus.in_progress,
            claimed_by_id=owner.id,
            approved_at=utcnow(),
            approved_by_id=owner.id,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(shiplog)
        session.commit()
        session.refresh(shiplog)
        print(f"Created Shiplog {shiplog.id}")

        share_plan = Plan(
            organization_id=ORG_ID,
            title="Shareable links + Done handoff",
            intent="Google Docs-style Team vs Anyone share links and Done handoff to teammates.",
            scope="See Done summary for full implementation details.",
            acceptance_criteria=(
                "- Team vs Anyone visibility with share token\n"
                "- Public read-only share page\n"
                "- Done handoff to org members + Anyone link copy"
            ),
            owner_id=owner.id,
            team="AX",
            project="ohship",
            status=PlanStatus.draft,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(share_plan)
        session.commit()
        session.refresh(share_plan)
        post_done(
            session,
            share_plan,
            owner,
            SHARE_DONE_SUMMARY,
            [{"type": "plan", "url": f"http://localhost:3000/plans/{shiplog.id}", "label": "Shiplog"}],
        )
        print(f"Created + Done: Shareable links {share_plan.id}")

        reviewers_plan = Plan(
            organization_id=ORG_ID,
            title="Reviewers sidebar + coding agent",
            intent="Let owners request review from teammates and open plans in a coding agent.",
            scope="See Done summary.",
            acceptance_criteria=(
                "- Reviewers sidebar with Add reviewer\n"
                "- Requested of me filter\n"
                "- Agent prompt copy"
            ),
            owner_id=owner.id,
            team="AX",
            project="ohship",
            status=PlanStatus.draft,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        session.add(reviewers_plan)
        session.commit()
        session.refresh(reviewers_plan)
        post_done(session, reviewers_plan, owner, REVIEWERS_DONE_SUMMARY, [])
        print(f"Created + Done: Reviewers {reviewers_plan.id}")


if __name__ == "__main__":
    main()
