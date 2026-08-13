#!/usr/bin/env bash
# One-command Planlog agent setup — works from any project, no Planlog repo clone required.
#
# Production:
#   curl -fsSL https://planlog.depak.dev/install | bash
#
# Local dev (cloned repo):
#   ./scripts/install-agent.sh
#
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${REPO:-.}"
API_URL="${PLANLOG_API_URL:-http://localhost:8000}"
INSTALL_URL="${PLANLOG_INSTALL_URL:-https://planlog.depak.dev/install}"
GIT_PKG="git+https://github.com/depak7/ohship#subdirectory=backend"

usage() {
  cat <<EOF
Usage: install-agent.sh [planlog-agent options]

  --repo PATH          Target project (default: .)
  --api-url URL        Planlog API (default: http://localhost:8000)
  --all-agents         Create all standard agent MD files
  --stdio              stdio MCP (needs --api-key, --org-id)
  --no-global-skill    Skip ~/.cursor/skills/planlog
  -h, --help           Show help

Env: REPO, PLANLOG_API_URL, PLANLOG_API_KEY, PLANLOG_ORG_ID

One-liner (any project):
  curl -fsSL $INSTALL_URL | bash
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

run_install() {
  uv run planlog-agent install --repo "$(cd "$REPO" && pwd)" --api-url "$API_URL" "$@"
}

# 1) Cloned planlog repo — use local package
if [[ -f "$ROOT/backend/pyproject.toml" ]] && command -v uv >/dev/null 2>&1; then
  (cd "$ROOT/backend" && run_install "$@")
  exit 0
fi

# 2) uvx from GitHub (no clone)
if command -v uv >/dev/null 2>&1; then
  exec uvx --from "$GIT_PKG" planlog-agent install --repo "$(cd "$REPO" && pwd)" --api-url "$API_URL" "$@"
fi

# 3) pip fallback
if command -v python3 >/dev/null 2>&1; then
  python3 -m pip install -q "$GIT_PKG" 2>/dev/null || python3 -m pip install -q --user "$GIT_PKG"
  exec planlog-agent install --repo "$(cd "$REPO" && pwd)" --api-url "$API_URL" "$@"
fi

echo "Planlog agent install requires uv (recommended) or python3 + pip." >&2
echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
echo "Then re-run: curl -fsSL $INSTALL_URL | bash" >&2
exit 1
