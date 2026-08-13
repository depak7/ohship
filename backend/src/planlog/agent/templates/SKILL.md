---
name: planlog
description: >-
  Planlog Plan → Approve → Done. Use when a plan_id is mentioned, starting feature
  work in an org project, or shipping — get_plan before coding, post_done when shipped.
---

# Planlog

Before product work on a plan: **`get_plan`**. When shipped: **`post_done`** — do not leave finished work only in chat.

## Agent loop

1. `list_orgs` — note `organization_id` and project
2. `get_plan(plan_id)` before coding (or `create_plan`; **project** required)
3. `update_plan` only while `draft` or `changes_requested`
4. `post_done(plan_id, summary, links_json, handoff_notes)` when shipped
5. `request_notifyees(plan_id, notify_ids)` for handoffs

## Rules

- **Do** read the plan first; **post_done** with summary + links when finished
- **Don't** use `add_suggestion` for shipped work (review feedback only)
- Skip Planlog for chores, deps, or formatting with no plan

MCP: `{api_url}/mcp` (OAuth). Search project files for `planlog:begin` for full instructions.
