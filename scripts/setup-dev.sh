#!/usr/bin/env bash
# Bootstrap local Planlog dev stack + agent wiring.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NO_DOCKER=false
NO_SEED=false
SKIP_AGENT=false

usage() {
  cat <<EOF
Usage: setup-dev.sh [options]

  --no-docker     Skip docker compose postgres (use existing DATABASE_URL)
  --no-seed       Skip bootstrap user seed
  --skip-agent    Do not run setup-agent.sh
  -h, --help      Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-docker) NO_DOCKER=true; shift ;;
    --no-seed) NO_SEED=true; shift ;;
    --skip-agent) SKIP_AGENT=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

cd "$ROOT"

if [[ "$NO_DOCKER" != true ]]; then
  echo "Starting Postgres..."
  docker compose up -d postgres
fi

# Backend env
if [[ ! -f backend/.env ]]; then
  cp backend/.env.example backend/.env
  echo "Created backend/.env from example"
fi

# Frontend env
if [[ ! -f frontend/.env.local ]]; then
  printf 'NEXT_PUBLIC_API_URL=http://localhost:8000\n' > frontend/.env.local
  echo "Created frontend/.env.local"
fi

echo "Installing backend dependencies..."
cd "$ROOT/backend"
uv sync

echo "Running migrations..."
set -a
# shellcheck source=/dev/null
source "$ROOT/backend/.env"
set +a
export DATABASE_URL="${DATABASE_URL:-postgresql://planlog:planlog@localhost:5433/planlog}"
uv run alembic upgrade head

if [[ "$NO_SEED" != true ]]; then
  echo "Seeding bootstrap user (if missing)..."
  uv run planlog-seed || true
fi

cd "$ROOT/frontend"
if command -v pnpm >/dev/null 2>&1; then
  echo "Installing frontend dependencies..."
  pnpm install --silent 2>/dev/null || pnpm install
fi

if [[ "$SKIP_AGENT" != true ]]; then
  echo "Running agent setup..."
  bash "$ROOT/scripts/setup-agent.sh" --repo "$ROOT"
fi

cat <<EOF

Dev stack ready.

Terminal 1 — API:
  cd backend && uv run uvicorn planlog.api.main:app --reload --port 8000

Terminal 2 — Frontend:
  cd frontend && pnpm dev

Open http://localhost:3000 → create account → create organization → write a plan.

MCP: http://localhost:8000/mcp (OAuth) — see AGENTS.md
EOF
