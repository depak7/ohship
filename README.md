# Planlog

A lightweight **Plan → Approve → Done** layer for engineering teams.

Engineers and agents post readable **markdown** plans. Reviewers approve or suggest changes. Done becomes permanent history. Teams share work through **organizations** and **projects**.

**Agent workflow:** see [`AGENTS.md`](AGENTS.md). One command from **any project**:

```bash
curl -fsSL https://planlog.depak.dev/install | bash
```

## Stack

- **API**: FastAPI + SQLModel + PostgreSQL + Alembic
- **Auth**: Email/password + Google OAuth (JWT)
- **MCP**: Streamable HTTP + OAuth (same login) · optional stdio + API key
- **Frontend**: Next.js + Tailwind

## Quick Start

### One command (recommended)

```bash
./scripts/setup-dev.sh
```

Starts Postgres, runs migrations, installs deps, and wires agent instructions into `AGENTS.md` (and other agent MD files if present).

Then in two terminals:

```bash
# Terminal 1 — API (REST + MCP OAuth + /mcp)
cd backend && uv run uvicorn planlog.api.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && pnpm dev
```

Or use Make: `make dev` (same as `setup-dev.sh`).

### Agent only (any app repo)

```bash
curl -fsSL https://planlog.depak.dev/install | bash
```

The script is served from your Planlog instance (`GET /install`) with the API URL baked in — no repo clone needed.

Override the API (e.g. self-hosted):

```bash
PLANLOG_API_URL=https://planlog.depak.dev curl -fsSL https://planlog.depak.dev/install | bash
```

Auto-detects your coding agent (Cursor, Claude Code, Copilot, etc.):

- Grafts Planlog instructions into `AGENTS.md` / `CLAUDE.md` / other agent MD files
- Wires MCP (`.cursor/mcp.json`, `.mcp.json` for Claude Code)
- Installs Cursor skill at `~/.cursor/skills/planlog/`

From a cloned Planlog repo (local dev): `./scripts/install-agent.sh --repo /path/to/your/app`

### Manual Quick Start

```bash
docker compose up -d postgres
cd backend && uv sync
export DATABASE_URL=postgresql://planlog:planlog@localhost:5433/planlog
uv run alembic upgrade head

# Terminal 1 — API
uv run uvicorn planlog.api.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend && pnpm install && pnpm dev
```

Open http://localhost:3000 → **Create account** → **Create organization** → write a plan.

## Auth

| Who | How |
|-----|-----|
| Humans (web) | Email + password, or Google |
| Agents (MCP) | **OAuth** — same email/Google login via browser consent |
| Agents (legacy) | API key + stdio (`planlog-mcp`) |

### MCP OAuth (recommended)

Point your agent at the HTTP MCP endpoint (Cursor, Claude Code, etc.). OAuth is discovered automatically:

```json
{
  "mcpServers": {
    "planlog": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

Or run `curl -fsSL https://planlog.depak.dev/install | bash` to merge MCP config into your project.

Flow:
1. Cursor hits `/mcp` → 401 + protected-resource metadata
2. Discovers Planlog as authorization server
3. Opens `/authorize` → redirects to web **Allow access** page
4. You sign in with email or Google (existing account)
5. Click **Allow** → Cursor gets a JWT and can call tools as you

Endpoints:
- MCP: `http://localhost:8000/mcp`
- AS metadata: `/.well-known/oauth-authorization-server`
- RS metadata: `/.well-known/oauth-protected-resource/mcp`

### MCP stdio + API key (optional)

See [`.cursor/mcp.json.example`](.cursor/mcp.json.example). Needs `PLANLOG_API_KEY` and `PLANLOG_ORG_ID`. Bootstrap user: `cd backend && uv run planlog-seed`.

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
- Plans are grouped by **project** (required); team is optional metadata

## Markdown-first plans

Plans are documents, not tickets:

- Intent / scope / acceptance criteria are markdown
- Detail page has **Rendered MD** and **Source** views
- API returns a combined `markdown` field for agents and UIs

## MCP Tools

`whoami`, `list_orgs`, `create_plan`, `update_plan`, `submit_for_review`, `request_reviewers`, `request_notifyees`, `add_suggestion`, `approve_plan`, `request_changes`, `claim_plan`, `post_done`, `set_plan_share`, `get_plan`, `list_plans`

See [`AGENTS.md`](AGENTS.md) for when agents should call each tool.

## Environment Variables

See [`backend/.env.example`](backend/.env.example).

## Development

```bash
make test
# or
cd backend && uv sync --extra dev && uv run pytest
```

## License

MIT
