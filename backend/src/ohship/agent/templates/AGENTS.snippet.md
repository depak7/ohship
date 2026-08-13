<!-- ohship:begin -->

## OhShip (plans)

**Any coding agent:** Before product work, read this section. When you ship, **update OhShip via MCP** — the plan is the source of truth, not chat history.

OhShip is **Plan → Approve → Done**: markdown plans humans and agents share. Connect the `ohship` MCP server once (see below).

### When to use it

Use OhShip when work is tied to a **plan_id** or a new feature slice in an org **project**. Do not log shipped work as long suggestion threads — use **Done**.

### Agent loop

1. `list_orgs` — note `organization_id` and project name
2. `get_plan(plan_id)` before coding (or `create_plan` for new work; **project** is required)
3. `update_plan` only while status is `draft` or `changes_requested`
4. `post_done(plan_id, summary, links_json, handoff_notes)` when shipped — **always** record finished work here
5. `request_notifyees(plan_id, notify_ids)` for teammates; copy Anyone share link for people outside the org

### Do

| Do | Why |
|----|-----|
| Read the plan before editing code | Intent and acceptance criteria live in OhShip |
| `post_done` with summary + links when finished | Done is the permanent record |
| `request_notifyees` for the next implementer | They see it under **Sent to me** |

### Don't

| Don't | Why |
|-------|-----|
| Use `add_suggestion` to record shipped work | Suggestions are for review feedback, not history |
| Skip `get_plan` when a plan_id is known | Avoid coding against stale scope |
| Leave shipped work only in chat or local notes | Update the plan in OhShip via MCP |

MCP server: `{api_url}/mcp` (OAuth). Re-run installer: `curl -fsSL {install_url} | bash`

<!-- ohship:end -->
