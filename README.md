# OhShip

A lightweight **Plan → Approve → Done** layer for engineering teams.

Engineers and agents post readable **markdown** plans. Reviewers approve or suggest changes. Done becomes permanent history. Teams share work through **organizations** and invite links.

## Stack

- **API**: FastAPI + SQLModel + PostgreSQL + Alembic
- **Auth**: Email/password + Google OAuth (JWT)
- **MCP**: Streamable HTTP + OAuth (same login) · optional stdio + API key
- **Frontend**: Next.js + Tailwind

## Quick Start

```bash
docker compose up -d postgres
cd backend && uv sync
export DATABASE_URL=postgresql://ohship:ohship@localhost:5433/ohship
uv run alembic upgrade head

# Terminal 1 — API (serves REST + MCP OAuth + /mcp)
uv run uvicorn ohship.api.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && pnpm install && pnpm dev
```

Open http://localhost:3000 → **Create account** → **Create organization** → write a plan.

## Auth

| Who | How |
|-----|-----|
| Humans (web) | Email + password, or Google |
| Agents (MCP) | **OAuth** — same email/Google login via browser consent |
| Agents (legacy) | API key + stdio (`ohship-mcp`) |

### MCP OAuth (recommended)

Point Cursor at the HTTP MCP endpoint. Cursor discovers OAuth automatically:

```json
{
  "mcpServers": {
    "ohship": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Flow:
1. Cursor hits `/mcp` → 401 + protected-resource metadata
2. Discovers OhShip as authorization server
3. Opens `/authorize` → redirects to web **Allow access** page
4. You sign in with email or Google (existing account)
5. Click **Allow** → Cursor gets a JWT and can call tools as you

Endpoints:
- MCP: `http://localhost:8000/mcp`
- AS metadata: `/.well-known/oauth-authorization-server`
- RS metadata: `/.well-known/oauth-protected-resource/mcp`

### MCP stdio + API key (optional)

See [`.cursor/mcp.json.example`](.cursor/mcp.json.example). Needs `OHSHIP_API_KEY` and `OHSHIP_ORG_ID`.

### Google OAuth (optional, for web + MCP consent)

1. Create an OAuth client in Google Cloud Console
2. Redirect URI: `http://localhost:8000/api/v1/auth/google/callback`
3. Set in `backend/.env`:

```bash
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
```

## Organizations

- Anyone can create an organization
- Invite teammates with a shareable link (`/invite/:token`)
- All members can see every plan and Done record in that org

## Markdown-first plans

Plans are documents, not tickets:

- Intent / scope / acceptance criteria are markdown
- Detail page has **Rendered MD** and **Source** views
- API returns a combined `markdown` field for agents and UIs

## MCP Tools

`whoami`, `list_orgs`, `create_plan`, `update_plan`, `submit_for_review`, `add_suggestion`, `approve_plan`, `request_changes`, `claim_plan`, `post_done`, `get_plan`, `list_plans`

## Environment Variables

See [`backend/.env.example`](backend/.env.example).

## Development

```bash
cd backend
uv sync --extra dev
uv run pytest
```

## License

MIT
