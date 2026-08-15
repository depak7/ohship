#!/usr/bin/env bash
# Local dev wrapper — runs the same installer the public /install endpoint serves.
#
# Production:
#   curl -fsSL https://planlog.depak.dev/install | bash
#
# Local dev (cloned repo):
#   ./scripts/install-agent.sh                    # interactive picker
#   ./scripts/install-agent.sh --global           # laptop-wide
#   ./scripts/install-agent.sh --agent claude -y  # non-interactive
#
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="${REPO:-.}"
API_URL="${PLANLOG_API_URL:-http://localhost:8000}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required for the local wrapper: https://docs.astral.sh/uv/getting-started/installation/" >&2
  exit 1
fi

REPO_ABS="$(cd "$REPO" && pwd)"
cd "$ROOT/backend"
exec uv run planlog-agent install --repo "$REPO_ABS" --api-url "$API_URL" "$@"
