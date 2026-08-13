#!/usr/bin/env bash
# One-command Planlog agent setup — works from any project, no Planlog repo clone required.
#
#   curl -fsSL __PLANLOG_INSTALL_URL__ | bash
#
# Env: PLANLOG_API_URL, REPO, PLANLOG_API_KEY, PLANLOG_ORG_ID
#
set -euo pipefail

REPO="${REPO:-.}"
API_URL="${PLANLOG_API_URL:-__PLANLOG_DEFAULT_API_URL__}"
INSTALL_URL="__PLANLOG_INSTALL_URL__"
GIT_PKG="git+https://github.com/depak7/ohship#subdirectory=backend"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"

usage() {
  cat <<EOF
Usage: install-agent.sh [planlog-agent options]

  --repo PATH          Target project (default: .)
  --api-url URL        Planlog API (default: __PLANLOG_DEFAULT_API_URL__)
  --all-agents         Create AGENTS.md, CLAUDE.md, GEMINI.md, copilot-instructions.md
  --stdio              stdio MCP (needs --api-key, --org-id)
  --no-global-skill    Skip ~/.cursor/skills/planlog
  -h, --help           Show help

One-liner (any project):
  curl -fsSL $INSTALL_URL | bash
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

run_uv() {
  uv run planlog-agent install --repo "$(cd "$REPO" && pwd)" --api-url "$API_URL" "$@"
}

# 1) Same repo as this script (dev / cloned planlog)
if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/../backend/pyproject.toml" ]]; then
  if command -v uv >/dev/null 2>&1; then
    (cd "$SCRIPT_DIR/../backend" && run_uv "$@")
    exit 0
  fi
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
