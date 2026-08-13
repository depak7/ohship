#!/usr/bin/env bash
# One-command OhShip agent setup — works from any project, no OhShip repo clone required.
#
#   curl -fsSL __OHSHIP_INSTALL_URL__ | bash
#
# Env: OHSHIP_API_URL, REPO, OHSHIP_API_KEY, OHSHIP_ORG_ID
#
set -euo pipefail

REPO="${REPO:-.}"
API_URL="${OHSHIP_API_URL:-__OHSHIP_DEFAULT_API_URL__}"
INSTALL_URL="__OHSHIP_INSTALL_URL__"
GIT_PKG="git+https://github.com/depak7/ohship#subdirectory=backend"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"

usage() {
  cat <<EOF
Usage: install-agent.sh [ohship-agent options]

  --repo PATH          Target project (default: .)
  --api-url URL        OhShip API (default: __OHSHIP_DEFAULT_API_URL__)
  --all-agents         Create AGENTS.md, CLAUDE.md, GEMINI.md, copilot-instructions.md
  --stdio              stdio MCP (needs --api-key, --org-id)
  --no-global-skill    Skip ~/.cursor/skills/ohship
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
  uv run ohship-agent install --repo "$(cd "$REPO" && pwd)" --api-url "$API_URL" "$@"
}

# 1) Same repo as this script (dev / cloned ohship)
if [[ -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/../backend/pyproject.toml" ]]; then
  if command -v uv >/dev/null 2>&1; then
    (cd "$SCRIPT_DIR/../backend" && run_uv "$@")
    exit 0
  fi
fi

# 2) uvx from GitHub (no clone)
if command -v uv >/dev/null 2>&1; then
  exec uvx --from "$GIT_PKG" ohship-agent install --repo "$(cd "$REPO" && pwd)" --api-url "$API_URL" "$@"
fi

# 3) pip fallback
if command -v python3 >/dev/null 2>&1; then
  python3 -m pip install -q "$GIT_PKG" 2>/dev/null || python3 -m pip install -q --user "$GIT_PKG"
  exec ohship-agent install --repo "$(cd "$REPO" && pwd)" --api-url "$API_URL" "$@"
fi

echo "OhShip agent install requires uv (recommended) or python3 + pip." >&2
echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
echo "Then re-run: curl -fsSL $INSTALL_URL | bash" >&2
exit 1
