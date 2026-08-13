#!/usr/bin/env bash
# Wire Planlog MCP + agent instructions (delegates to planlog-agent / install-agent.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  cat <<EOF
Usage: setup-agent.sh [options]

  --repo PATH          Target repo (default: current directory)
  --all-agents         Graft into all standard agent MD files
  --with-cursor        Force Cursor MCP + rule
  --no-global-skill    Skip ~/.cursor/skills/planlog
  --api-url URL        Planlog API base (default: http://localhost:8000)
  --stdio              MCP via stdio + API key (requires --api-key and --org-id)
  --api-key KEY        For stdio mode
  --org-id UUID        For stdio mode
  --always-apply       Set Cursor rule alwaysApply: true
  -h, --help           Show this help

From any project (no Planlog clone):
  curl -fsSL https://planlog.depak.dev/install | bash

Idempotent: safe to re-run.
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

exec bash "$ROOT/scripts/install-agent.sh" "$@"
