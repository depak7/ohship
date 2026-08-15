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

The installer is **interactive**. It asks two questions, then writes only what you picked:

1. **Where** — this project only, or globally (every project on this laptop).
2. **Which agents** — detected ones are pre-selected; press Enter to accept, or pick numbers.

| Agent | Instructions | MCP config (project) | MCP config (global) |
| --- | --- | --- | --- |
| Cursor | `.cursor/rules/planlog.mdc` | `.cursor/mcp.json` | `~/.cursor/mcp.json` + `~/.cursor/skills/planlog/` |
| Claude Code | `CLAUDE.md` | `.mcp.json` | `claude mcp add --scope user` (falls back to `~/.claude.json`), `~/.claude/CLAUDE.md` |
| Codex CLI | `AGENTS.md` | — (Codex is user-scoped) | `~/.codex/config.toml`, `~/.codex/AGENTS.md` |
| Gemini CLI | `GEMINI.md` | `.gemini/settings.json` | `~/.gemini/settings.json`, `~/.gemini/GEMINI.md` |
| Copilot / VS Code | `.github/copilot-instructions.md` | `.vscode/mcp.json` | VS Code user `mcp.json` |
| Windsurf | `.windsurf/rules/planlog.md` | — (Windsurf is user-scoped) | `~/.codeium/windsurf/mcp_config.json` |
| opencode | `AGENTS.md` | `opencode.json` (`mcp` key) | `~/.config/opencode/opencode.json`, `~/.config/opencode/AGENTS.md` |
| Any other | `AGENTS.md` | — | — |

Configs that allow comments (`.vscode/mcp.json`, `opencode.jsonc`) are never rewritten — if
yours has comments the installer prints the snippet to paste instead of dropping them.

Re-running is safe: the `planlog:begin … planlog:end` block is **replaced**, not duplicated, and
existing MCP servers in each config are preserved.

Skip the prompts (CI, dotfiles, no terminal):

```bash
curl -fsSL https://planlog.depak.dev/install | bash -s -- --global --agent claude --agent cursor
curl -fsSL https://planlog.depak.dev/install | bash -s -- --yes   # use auto-detected agents
```

Without a terminal (`/dev/tty` unavailable) the installer skips the picker and uses auto-detection.

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

### Deploying: run exactly one web worker

**The `--workers 1` in `backend/Procfile` is load-bearing.** MCP Streamable HTTP keeps live
sessions in a per-process dict, so with two workers the router sends `initialize` to one
process and `tools/list` to another. The second answers `Session not found` and the client
reports **"Reconnected to planlog, but fetching tools failed: Not connected"**.

It's easy to reintroduce: Heroku's Python buildpack sets `WEB_CONCURRENCY` (2 on a Basic
dyno) and uvicorn silently honours it unless `--workers` is passed. The tell in the logs is a
`Created new transport with session ID: X` followed by `Rejected request with unknown or
expired session ID: X` **with no teardown line in between** — the session isn't gone, it's
alive in the other process. The app logs a warning at startup when `WEB_CONCURRENCY > 1`.

To scale past one worker, switch MCP to `stateless_http=True` first (Planlog's tools are all
request/response, so nothing depends on server-initiated streaming).

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
