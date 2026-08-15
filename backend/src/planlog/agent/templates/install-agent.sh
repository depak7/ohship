#!/usr/bin/env bash
# One-command Planlog agent setup — works from any project, no Planlog repo clone required.
#
#   curl -fsSL __PLANLOG_INSTALL_URL__ | bash
#
# The installer asks which agents to wire up. Under `curl | bash` stdin is the script
# itself, so we hand the child process /dev/tty (or /dev/null when there is no terminal,
# in which case it falls back to auto-detected agents).
#
# Pass options through the pipe with `-s --`:
#   curl -fsSL __PLANLOG_INSTALL_URL__ | bash -s -- --global --agent claude --agent cursor
#
# Env: PLANLOG_API_URL, REPO, PLANLOG_API_KEY, PLANLOG_ORG_ID
#
set -euo pipefail

REPO="${REPO:-.}"
API_URL="${PLANLOG_API_URL:-__PLANLOG_DEFAULT_API_URL__}"
INSTALL_URL="__PLANLOG_INSTALL_URL__"
GIT_PKG="git+https://github.com/depak7/ohship#subdirectory=backend"

usage() {
  cat <<EOF
Usage: curl -fsSL $INSTALL_URL | bash -s -- [options]

  --global             Install for every project on this laptop (user config)
  --agent NAME         cursor | claude | codex | gemini | copilot | windsurf | universal
                       (repeatable; skips the interactive picker)
  --repo PATH          Target project (default: .)
  --api-url URL        Planlog API (default: __PLANLOG_DEFAULT_API_URL__)
  --all-agents         Create every standard agent instruction file
  --stdio              stdio MCP (needs --api-key, --org-id)
  --no-global-skill    Skip ~/.cursor/skills/planlog
  -y, --yes            Non-interactive: use auto-detected agents
  -h, --help           Show help
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

# Give the installer a real terminal so it can prompt; /dev/null makes it non-interactive.
if { : >/dev/tty; } 2>/dev/null; then
  STDIN_SRC=/dev/tty
else
  STDIN_SRC=/dev/null
fi

REPO_ABS="$(cd "$REPO" && pwd)"

# 1) Running from a cloned Planlog repo — use the local package.
SCRIPT_PATH="${BASH_SOURCE[0]:-}"
if [[ -n "$SCRIPT_PATH" && -f "$SCRIPT_PATH" ]]; then
  SCRIPT_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
  for CANDIDATE in "$SCRIPT_DIR/.." "$SCRIPT_DIR/../../../../.."; do
    if [[ -f "$CANDIDATE/backend/pyproject.toml" ]] && command -v uv >/dev/null 2>&1; then
      cd "$CANDIDATE/backend"
      exec uv run planlog-agent install --repo "$REPO_ABS" --api-url "$API_URL" "$@" <"$STDIN_SRC"
    fi
  done
fi

# 2) uvx from GitHub (no clone).
if command -v uv >/dev/null 2>&1; then
  exec uvx --from "$GIT_PKG" planlog-agent install \
    --repo "$REPO_ABS" --api-url "$API_URL" "$@" <"$STDIN_SRC"
fi

# 3) pip fallback — invoke via `-m` so a --user install needs no PATH changes.
if command -v python3 >/dev/null 2>&1; then
  if ! python3 -m pip install -q "$GIT_PKG" && ! python3 -m pip install -q --user "$GIT_PKG"; then
    echo "pip install failed. Install uv instead: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
  fi
  exec python3 -m planlog.agent.install install \
    --repo "$REPO_ABS" --api-url "$API_URL" "$@" <"$STDIN_SRC"
fi

echo "Planlog agent install requires uv (recommended) or python3 + pip." >&2
echo "Install uv: https://docs.astral.sh/uv/getting-started/installation/" >&2
echo "Then re-run: curl -fsSL $INSTALL_URL | bash" >&2
exit 1
